import copy
import pytest
from studio import models, continuity

@pytest.fixture
def plan():
    data = {'title': 'Test', 'logline': 'A keeper turns on a light.', 'story': 'Ada fixes a lamp.', 'screenplay': 'ADA: Light.', 'style': 'Stop-motion',
        'canon': [
            {'id': 'ada', 'kind': 'character', 'name': 'Ada', 'description': 'Black bob and yellow coat', 'facts': ['Three coat buttons']},
            {'id': 'room', 'kind': 'location', 'name': 'Workshop', 'description': 'Round window behind a wooden bench', 'facts': ['Window at rear']},
            {'id': 'lamp', 'kind': 'prop', 'name': 'Lantern', 'description': 'Brass lantern with a glass chimney', 'facts': ['Cracked chimney']},
        ],
        'scenes': [{'id': 'scene', 'title': 'Workshop', 'location_id': 'room', 'time_of_day': 'Night', 'summary': 'Light the lamp'}],
        'shots': [{'id': 'shot', 'scene_id': 'scene', 'title': 'The switch', 'duration': 6, 'entity_ids': ['ada'], 'framing': 'Medium', 'angle': 'Eye-level', 'camera': 'Slow 10cm push', 'blocking': 'Ada left', 'action': 'Press switch', 'expression': 'Surprised', 'start_state': [{'entity_id': 'ada', 'key': 'hand', 'value': 'lowered'}], 'end_state': [{'entity_id': 'ada', 'key': 'hand', 'value': 'raised'}], 'transition_note': '', 'beats': [{'start': 0, 'end': 6, 'action': 'Raise hand and press switch'}], 'dialogue': [{'entity_id': 'ada', 'text': 'Light.', 'language': 'English', 'start': 3, 'end': 4, 'delivery': 'quietly'}], 'keyframes': [{'id': 'start', 'moment': 'start', 'description': 'Ada hand lowered'}, {'id': 'end', 'moment': 'end', 'description': 'Ada hand raised'}], 'soundscape': 'Wind and a switch click.', 'music': 'N/A'}],
    }
    return models.Production.model_validate(data).model_dump()


def approved_asset(pid, plan, target_id, note=''):
    return {'id': f'a-{target_id}', 'target_id': target_id, 'status': 'approved', 'dependency_hash': continuity.target_hash(plan, target_id), 'note': note}


def test_character_sheet_layout_constant():
    assert continuity.CHARACTER_SHEET_LAYOUT == 'four-view-v2'
    inst = continuity.CHARACTER_SHEET_INSTRUCTION
    assert isinstance(inst, str) and inst
    # The four panels, in order, left to right
    assert inst.index('front-facing full-body view') < inst.index('full-body profile facing image-left')
    assert inst.index('full-body profile facing image-left') < inst.index('full-body rear')
    assert inst.index('full-body rear') < inst.index('front-facing head-and-shoulders close-up')
    assert 'LEFT TO RIGHT' in inst
    assert 'exactly four vertical panels' in inst
    assert 'roughly 30 to 35 percent' in inst
    assert 'Clean white seamless background' in inst
    assert 'no visible panel borders' in inst
    assert 'captions, text labels or extra viewpoints' in inst


def test_character_generation_prompt_requires_four_panel_sheet(plan):
    prompt = continuity.image_prompt(plan, 'ada', [])
    assert 'Create one canonical character reference image for Ada.' in prompt
    assert 'exactly four vertical panels arranged LEFT TO RIGHT' in prompt
    for phrase in ['front-facing full-body view', 'full-body profile facing image-left',
                   'front-facing head-and-shoulders close-up', 'full-body rear']:
        assert phrase in prompt
    assert 'roughly 30 to 35 percent' in prompt
    assert 'Clean white seamless background' in prompt
    assert 'no visible panel borders' in prompt
    assert 'captions, text labels or extra viewpoints' in prompt
    assert 'No watermarks, captions, text labels or montage.' not in prompt
    assert 'no collage' not in prompt
    assert 'three-quarter' not in prompt
    # Preserves project style, no photorealism drift
    assert '"legacy_style_context": "Stop-motion"' in prompt
    assert 'do not replace stylized art with photorealism' in prompt
    # Supplied user image is layout inspiration only
    assert 'target-specific layout rules and reference roles separately' in prompt
    # Revision feedback is preserved
    assert '"requested_revision": ""' in prompt


def test_character_revision_prompt_keeps_sheet_and_feedback(plan):
    prompt = continuity.image_prompt(plan, 'ada', [], 'Make the coat sleeve shorter')
    assert 'exactly four vertical panels arranged LEFT TO RIGHT' in prompt
    assert 'full-body rear' in prompt
    assert '"requested_revision": "Make the coat sleeve shorter"' in prompt
    assert 'No watermarks, captions, text labels or montage.' not in prompt


def test_storyboard_keyframe_uses_character_sheet_reference(plan):
    refs = [approved_asset('p', plan, 'ada'), approved_asset('p', plan, 'room')]
    refs, missing = continuity.references(plan, refs, 'start')
    assert missing == []
    prompt = continuity.image_prompt(plan, 'start', refs)
    # Single still keyframe, not sequential panels
    assert 'Single still composition, not sequential panels.' in prompt
    assert 'Ada hand lowered' in prompt
    assert 'SOURCE FOR INTERPRETATION ONLY' in prompt
    # Character reference role: extract one identity, never reproduce the sheet
    assert 'CHARACTER Ada; authoritative identity/design source' in prompt
    assert 'Extract ONE single character identity from it' in prompt
    assert 'Never reproduce the panels, separators or four duplicate figures in this image' in prompt
    # Location identity is reusable; floor/room details obey the target's scope.
    assert 'LOCATION Workshop; authoritative shared architecture, connected layout' in prompt
    assert 'explicit target sublocation and time govern signage and lighting' in prompt
    assert 'never override an incompatible layout or same-place fixed anchor' in prompt


def test_storyboard_end_frame_includes_opening_reference(plan):
    refs = [approved_asset('p', plan, 'ada'), approved_asset('p', plan, 'room'),
            {'id': 'a-start', 'target_id': 'start', 'status': 'approved', 'dependency_hash': continuity.target_hash(plan, 'start'), 'note': ''}]
    refs, missing = continuity.references(plan, refs, 'end')
    assert missing == []
    assert 'a-start' in [r['id'] for r in refs]
    prompt = continuity.image_prompt(plan, 'end', refs)
    assert 'Never reproduce the panels, separators or four duplicate figures in this image' in prompt
    assert 'approved storyboard composition; preserve spatial arrangement and identity' in prompt


def test_location_prompt_unchanged(plan):
    prompt = continuity.image_prompt(plan, 'room', [])
    assert 'Create one canonical location reference image for Workshop.' in prompt
    assert 'Show one coherent view of the connected layout and fixed spatial anchors, without characters.' in prompt
    assert 'exactly four vertical panels' not in prompt
    assert 'SOURCE FOR INTERPRETATION ONLY' in prompt
    assert 'photorealistic human' not in prompt


def test_prop_prompt_unchanged(plan):
    prompt = continuity.image_prompt(plan, 'lamp', [])
    assert 'Create one canonical prop reference image for Lantern.' in prompt
    assert 'Show a clear three-quarter full view of the object and its distinctive details. One subject, no collage, no captions.' in prompt
    assert 'exactly four vertical panels' not in prompt
    assert 'SOURCE FOR INTERPRETATION ONLY' in prompt
    assert 'photorealistic human' not in prompt


def test_prop_with_character_reference_keeps_single_view(plan):
    ref = approved_asset('p', plan, 'ada')
    prompt = continuity.image_prompt(plan, 'lamp', [ref])
    # Character sheet instruction must NOT leak into a prop target
    assert 'exactly four vertical panels' not in prompt
    assert 'Show a clear three-quarter full view of the object and its distinctive details. One subject, no collage, no captions.' in prompt
    assert 'SOURCE FOR INTERPRETATION ONLY' in prompt
    # Character reference role is present
    assert 'CHARACTER Ada' in prompt


def test_hashes_and_context_unchanged_by_prompt_constants(plan):
    base = continuity.target_hash(plan, 'ada')
    # Changing feedback changes the prompt but not the target hash
    p1 = continuity.image_prompt(plan, 'ada', [])
    p2 = continuity.image_prompt(plan, 'ada', [], 'Fix the coat')
    assert p1 != p2
    assert continuity.target_hash(plan, 'ada') == base
    # Canon change still invalidates the hash
    changed = copy.deepcopy(plan)
    changed['canon'][0]['description'] = 'Black bob and red coat'
    assert continuity.target_hash(changed, 'ada') != base
    # Context payload unchanged in shape for entity targets
    ctx = continuity.context(plan, 'ada')
    assert ctx['style'] == 'Stop-motion'
    assert ctx['entity']['id'] == 'ada'


def test_character_reference_note_retained_as_interpretation_context(plan):
    ref = approved_asset('p', plan, 'ada', 'Approved interpretation: rounder jaw')
    prompt = continuity.image_prompt(plan, 'ada', [ref])
    assert '"reference_notes_context": [{"note": "Approved interpretation: rounder jaw"' in prompt
    assert 'Approved director note:' not in prompt
    assert 'CHARACTER Ada; authoritative identity/design source' in prompt


def test_character_revision_with_approved_source_has_no_panel_prohibition(plan):
    ref=approved_asset('p',plan,'ada')
    prompt=continuity.image_prompt(plan,'ada',[ref],'Keep identity; make the required sheet')
    assert 'all four requested panels' in prompt
    assert 'Never reproduce the panels' not in prompt
    assert 'no collage' not in prompt and 'or montage' not in prompt
    assert 'do not mirror a profile' in prompt
