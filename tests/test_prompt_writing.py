"""The prompt-writing case library: original need -> weaker prompt -> better prompt -> reusable reason.

This is what teaches the general ability. Each case carries the *reason* the improvement works, so a
writer (human or agent) can reuse the reasoning on a scene nobody wrote an example for — the point is
not to memorise a lantern rule.

Honest scope
------------
Only cases whose fault is mechanically provable assert a finding code. Where a fault is genuinely a
matter of judgment (an over-played emotion, a weak composition), the case records the reasoning and
asserts only that the *better* prompt does not trip the mechanical checks — pretending a keyword rule
settles taste would be worse than admitting the limit. The negative cases at the bottom exist to stop
the rules over-reaching: a lamp that should be lit may be lit, an approved montage is not a
continuity error, and ordered action belongs in video.

Every better prompt must come back clean. That is the regression guard.
"""
import re

import pytest

from studio import prompt_writing as pw


def findings(text, kind, refs=None, states=()):
    found, _ = pw.check({'t': text} if isinstance(text, str) else text, kind,
                        reference_count=refs, declared_states=states)
    return {f['code'] for f in found}


def blocking(text, kind, refs=None):
    _, hard = pw.check({'t': text} if isinstance(text, str) else text, kind, reference_count=refs)
    return [f['code'] for f in hard]


# ---------------------------------------------------------------------------
# Case library
# ---------------------------------------------------------------------------

CASES = [
    {
        'id': 'two_people_ownership',
        'need': 'Two characters handle one prop; the audience must know who holds it when.',
        'weaker': 'He hands the parcel to her and takes it straight back, then gives it to her again.',
        'better': ("Ada passes the parcel to Pip with her right hand and keeps her left hand on the counter; "
                   "Pip receives it in both pincers and holds it against its chest."),
        'expect': 'ownership_ambiguity',
        'reason': ('A clause using both "he" and "her" with no name lets the generator decide who acts and '
                   'who owns the object. Naming the actor and the receiving party removes the choice, and '
                   'stating which hand does what keeps possession readable in a still.'),
    },
    {
        'id': 'start_frame_no_premature_result',
        'need': 'The opening keyframe must show the state before the action, not its result.',
        'weaker': ("Ada touches the switch and then flips it on, the bulb lights and Pip looks up in surprise."),
        'better': ("Ada's fingertips rest on the switch, which is still down; the glass chimney is dark and "
                   "unlit; Pip faces her with its lens steady."),
        'expect': 'still_action_leak',
        'reason': ('"and then" chains two instants into one frame, so the renderer picks whichever end it likes '
                   'and the opening frame can arrive already carrying the outcome. One frozen instant with its '
                   'own state keeps the start frame usable as a start frame.'),
    },
    {
        'id': 'composition_scale_conflict',
        'need': 'The evidence the shot exists to show must actually be legible at the chosen scale.',
        'weaker': ("Extreme close-up on the toggle, while the wide shot also keeps the small badge on the far "
                   "pegboard clearly visible."),
        'better': ("Tight close-up on the lantern's brass base, the toggle filling the lower right frame and "
                   "reading as a hard black silhouette; the pegboard stays far behind and soft."),
        'expect': 'composition_conflict',
        'reason': ('A close scale and a wide scale in one frame cannot both win, and a small distant object '
                   'cannot also display fine detail. Choose which one the shot exists for and let the other '
                   'stay soft, instead of asking for both and letting the renderer choose.'),
    },
    {
        'id': 'reference_does_not_own_state',
        'need': 'A design reference supplies design, not the object\'s current switch or fill state.',
        'weaker': "Use Image 4 for the lantern and copy its illumination state so the lantern looks bright.",
        'better': ("Preserve the lantern's silhouette, material and proportions from Image 4; the lantern itself "
                   "is switched off with dark glass and no emitted light."),
        'expect': 'reference_overreach',
        'reason': ('An object reference is authoritative for shape, material and marks, not for whether the '
                   'object is currently on. Inheriting illumination from a reference is how a prop arrives '
                   'already lit in a scene that needs it off.'),
    },
    {
        'id': 'emission_needs_a_cause',
        'need': 'Light in the frame must be attributable, or the generator invents a source.',
        'weaker': "A soft warm glow fills the workshop and everything reads bright and warm.",
        'better': ("The only light is the low amber wall sconce raking across the bench and deep blue night "
                   "coming through the circular rear window; surfaces outside those two falls read dark."),
        'expect': 'cause_ambiguity',
        'reason': ('An unattributed glow can be satisfied by any object in frame, which is how a prop starts '
                   'emitting light for no narrative reason. Naming the sources and what they do and do not '
                   'reach removes the choice. This is the general cause-and-effect rule, not a lantern rule.'),
    },
    {
        'id': 'emotion_shown_not_labelled',
        'need': 'Quiet emotion must be shown through behaviour, not inflated into display.',
        'weaker': "Ada is extremely sad and dramatic, tears streaming down her face, eyes wide, sobbing.",
        'better': ("Ada's gaze stays on the dark glass; her shoulders are drawn in and her grip on the wire "
                   "handle has not loosened; she does not look at Pip."),
        'expect': None,          # judgment, not mechanically provable — recorded, not enforced
        'reason': ('Emotional adjectives describe the writer\'s reaction, not an image. Visible behaviour — where '
                   'the gaze stays, what the shoulders do, what she does not look at — is renderable, and '
                   'understatement reads as true where tears read as performance.'),
    },
    {
        'id': 'redundancy_spends_attention',
        'need': 'Repeating one requirement does not increase control; it spends attention.',
        'weaker': None,          # built below
        'better': ("The workshop is lit only by the low amber wall sconce at rear left; the lantern on the bench "
                   "is dark and unlit; Ada stands behind the bench with her hands at rest."),
        'expect': 'redundancy',
        'reason': ('A phrase repeated until it dominates the text crowds out the details that actually decide '
                   'the image. Say a requirement once, clearly, and spend the rest of the text on what is not '
                   'yet specified.'),
    },
    {
        'id': 'video_ordered_action_is_correct',
        'need': 'A video prompt carries ordered movement; the still-image freeze rule must not be applied.',
        'weaker': None,          # same text as `better`; this case asserts NON-firing
        'better': ("Ada crosses to the bench, then lifts the lantern, then carries it toward the door while "
                   "Pip watches from the counter."),
        'expect': None,
        'reason': ('Ordered action separated by "then" is exactly what a video needs. The still-image rule that '
                   'forbids sequential instants applies to one frozen frame, and applying it to a video would '
                   'strip the movement the shot exists for.'),
    },
    {
        'id': 'new_scene_unseen_in_examples',
        'need': 'A scene none of the examples covers: a night platform with a poster and a pillar.',
        'weaker': ("He gives her the ticket and she takes it from him while the timetable poster is hidden "
                   "behind the pillar and the timetable is clearly readable."),
        'better': ("Nadia hands Tomas the ticket and keeps her pass in her left hand; the pillar hides the "
                   "poster's lower half, and the departure row above the pillar stays legible."),
        'expect': 'ownership_ambiguity',
        'reason': ('The same two faults from the earlier cases appear in a scene with different people and '
                   'objects: an unresolved pronoun pair for a hand-over, and one subject demanded to be both '
                   'hidden and legible. The reasoning transfers; the examples were never about the lantern.'),
    },
]


def _build_redundancy():
    filler = ("The bench sits under the circular rear window, tools hang in neat rows on the pegboard, "
              "and the floorboards carry the grain of painted wood. ")
    phrase = "the warm amber sconce light rakes across the brass base"
    body = (filler * 3) + phrase + '. ' + (filler * 2) + phrase + '. ' + (filler * 2) + phrase + '.'
    return body


CASES[6]['weaker'] = _build_redundancy()
CASES[7]['weaker'] = CASES[7]['better']


@pytest.mark.parametrize('case', CASES, ids=[c['id'] for c in CASES])
def test_case_library(case):
    kind = 'video_i2va' if case['id'] == 'video_ordered_action_is_correct' else \
        ('exact_start_keyframe' if case['id'] == 'start_frame_no_premature_result' else
         ('prop_design' if case['id'] == 'reference_does_not_own_state' else 'still_frame'))
    weaker, better = case['weaker'], case['better']

    if case['expect']:
        assert case['expect'] in findings(weaker, kind), \
            f"{case['id']}: expected {case['expect']} in the weaker prompt"
    # The better prompt must never trip a blocking check, and must not carry the fault it fixed.
    assert not blocking(better, kind), f"{case['id']}: better prompt must not block"
    if case['expect']:
        assert case['expect'] not in findings(better, kind), \
            f"{case['id']}: better prompt still shows {case['expect']}"
    assert case['reason'].strip(), 'every case teaches a reusable reason'


# ---------------------------------------------------------------------------
# Negative controls: the rules must not over-reach
# ---------------------------------------------------------------------------

NEGATIVE = [
    ('lit_lamp_may_be_lit', 'still_frame',
     "The lantern is lit: its filament glows inside the glass and throws warm light across the bench, "
     "the lantern itself the brightest thing in frame.",
     'A lamp the story needs switched on must be allowed to shine. Declared state decides, not a blanket ban.'),
    ('intentional_montage_is_not_a_continuity_error', 'montage_group',
     "A montage of four beats in one generation: Ada arrives at the door, then opens the shutter, "
     "then the lamp catches, then the beam sweeps out over the sea.",
     'An authorised montage legitimately holds several actions and changes of place in one generation.'),
    ('different_composition_is_not_a_continuity_error', 'shot_prompt',
     "A deliberate reverse: this shot mirrors the previous framing, Ada now on screen right looking left, "
     "keeping the same workshop and the same lantern on the bench.",
     'Narrative and spatial continuity do not require identical compositions; a changed angle is a choice, '
     'not an inconsistency.'),
    ('declared_off_state_is_not_a_fault', 'exact_start_keyframe',
     "Ada's hand rests beside the lantern; the lantern is switched off, its glass dark, the toggle down.",
     'Stating the canonical off state plainly is correct and must never be reported as a problem.'),
    ('missing_information_is_not_a_conflict', 'still_frame',
     "Ada stands at the bench in the workshop at night, the lantern beside her.",
     'Silence in the source is not a contradiction; the checks must not invent a fault from what was never said.'),
]


@pytest.mark.parametrize('name,kind,text,why', NEGATIVE, ids=[n[0] for n in NEGATIVE])
def test_negative_controls(name, kind, text, why):
    assert not blocking(text, kind), f'{name}: must not block — {why}'
    assert findings(text, kind) == set(), f'{name}: must be entirely clean — {why}'


# ---------------------------------------------------------------------------
# Shared contract behaviour
# ---------------------------------------------------------------------------

def test_principles_reach_every_writer_and_are_one_file():
    """Studio runtime and the agent package must serve the same writing principles."""
    from pathlib import Path
    import studio.production_methods as pm
    studio_copy = Path(pm.__file__).parent / 'bundled/studio-production-methods/references/prompt-writing.md'
    agent_copy = (Path(pm.__file__).parent.parent /
                  'skill-packages/continuity-studio/references/methods/references/prompt-writing.md')
    assert studio_copy.read_bytes() == agent_copy.read_bytes(), 'one source, one copy, identical bytes'
    for capability in ('narrative', 'storyboard', 'image_prepare', 'image', 'h3_video_prompt'):
        text, _ = pm.snapshot(capability)
        assert 'Decide what the frame is for' in text, f'{capability} must receive the principles'


def test_task_contracts_never_invent_renderer_syntax():
    """Every task must agree with what this pipeline really supports."""
    for name in pw.supported_tasks():
        entry = pw.task(name)
        assert entry['syntax']['negative_prompt'] is False
        assert entry['syntax']['weighting'] is False
        assert entry['checks'], f'{name} must declare which checks apply'


def test_unsupported_syntax_is_caught_for_each_form():
    for text in ('a lantern (toggle:1.3) in the dark workshop',
                 'a lantern [warm light:1.4] on the bench',
                 'negative prompt: no glow, a lantern',
                 '0-3s: Ada crosses to the bench in the workshop'):
        assert 'unsupported_syntax' in findings(text, 'still_frame'), text


def test_reference_slot_beyond_supplied_images_blocks():
    assert 'reference_slot_missing' in blocking('Match the brass tone of Image 5 against the bench.', 'still_frame', refs=4)
    assert not blocking('Match the brass tone of Image 3 against the bench.', 'still_frame', refs=4)


# ---------------------------------------------------------------------------
# Occlusion and composition: legitimate partial visibility must stay clean
# ---------------------------------------------------------------------------

OCCLUSION_LEGITIMATE = [
    ('body_hidden_face_visible', 'still_frame',
     "Ada's lower body is hidden by the workbench, while her face stays clearly visible above it.",
     'Hiding one part while showing another is ordinary staging, not a contradiction.'),
    ('behind_prop_face_visible', 'still_frame',
     "Ada stands behind the bench, half hidden by the lantern, her face clearly visible.",
     'A figure partly behind an object with a readable face is a normal shot.'),
    ('prop_back_hidden_toggle_visible', 'still_frame',
     "The lantern's back is turned away and not visible, while its right-side toggle is clearly visible.",
     'An object can hide one face and present another; the toggle is the evidence the shot needs.'),
    ('negative_form_hidden', 'still_frame',
     "The lantern is not visible from this angle; the lantern's toggle is clearly visible.",
     'A negated visibility claim states what is excluded, so it cannot conflict with a requirement.'),
    ('occluded_then_enters_is_fine_on_video', 'video_i2va',
     "Pip is occluded by the crate at the start, then moves into frame and is clearly visible.",
     'Over a shot, a subject may begin hidden and become visible; only a still image must hold one instant.'),
    ('prohibition_about_visibility', 'still_frame',
     "Do not let the toggle be hidden; the toggle must stay clearly visible.",
     'A prohibition plus its requirement agree with each other; they do not contradict.'),
]


@pytest.mark.parametrize('name,kind,text,why', OCCLUSION_LEGITIMATE,
                         ids=[c[0] for c in OCCLUSION_LEGITIMATE])
def test_legitimate_partial_occlusion_is_clean(name, kind, text, why):
    assert not blocking(text, kind), f'{name}: must never block — {why}'
    assert findings(text, kind) == set(), f'{name}: must be entirely clean — {why}'


def test_a_sequential_occlusion_is_only_a_still_image_fault():
    """The same sentence is fine over time and wrong in a frozen instant — the task decides."""
    text = "Pip is occluded by the crate at the start, then moves into frame and is clearly visible."
    assert 'still_action_leak' in findings(text, 'still_frame')
    assert findings(text, 'video_i2va') == set()


def test_real_visibility_contradiction_is_reported_but_never_blocks():
    """The same subject, hidden and clearly visible in one breath: worth flagging, never enforcing.

    Reporting it is useful. Blocking on it would be pretending a keyword rule can read composition,
    and a warning must never be able to change the plan or the canonical state.
    """
    text = ('The brass toggle is hidden behind Ada\'s hand, and the brass toggle is '
            'clearly visible from camera.')
    found = findings(text, 'still_frame')
    assert 'composition_conflict' in found, 'the clearest same-subject case should still be reported'
    assert not blocking(text, 'still_frame'), 'a composition warning must never block'


def test_no_composition_finding_can_ever_block():
    """Severity policy: only mechanically provable faults may block."""
    assert 'composition_conflict' not in pw.BLOCKING_CODES
    assert pw.BLOCKING_CODES == frozenset({'unsupported_syntax', 'reference_slot_missing'})


# ---------------------------------------------------------------------------
# Generalisation: a scene the case library never taught
# ---------------------------------------------------------------------------

NEW_SCENE = {
    'text': ("Night shift on a harbour breakwater. Two dockhands in oilskins work the winch: "
             "the taller one braces the drum, the shorter one feeds the cable. A storm lamp hangs "
             "from the gantry, its own flame the only warm light, throwing their shadows long "
             "across wet stone. The breakwater's far end is lost in spray."),
    'kind': 'still_frame',
}


def test_new_scene_is_not_flagged_and_keeps_its_stated_source():
    """A scene with no lantern and no bench: the rules must generalise, not just recognise the example."""
    found = findings(NEW_SCENE['text'], NEW_SCENE['kind'])
    assert found == set(), f'a clean new scene must stay clean, got {found}'
    assert not blocking(NEW_SCENE['text'], NEW_SCENE['kind'])


def test_new_scene_faults_are_caught_the_same_way():
    """The same faults, in an unseen scene, are caught by the same rules."""
    unsourced_glow = ('Night shift on a harbour breakwater. The whole gantry shines with a warm glow '
                      'and the stone glitters.')
    assert 'cause_ambiguity' in findings(unsourced_glow, 'still_frame'), \
        'glow with no stated source must be flagged in any scene'

    nameless_pair = ('One of them lifts the crate while the other steadies it, and then he takes the '
                     'hook from her before it swings.')
    assert 'ownership_ambiguity' in findings(nameless_pair, 'still_frame')

    invented_syntax = 'The winch drum (tension:1.4) turns while the gantry lamp glows from its own flame.'
    assert 'unsupported_syntax' in blocking(invented_syntax, 'still_frame')

    missing_slot = 'Match the breakwater stonework to Image 6 in tone and wetness.'
    assert 'reference_slot_missing' in blocking(missing_slot, 'still_frame', refs=3)


def test_new_scene_occlusion_stays_advisory():
    partial = ('Night shift on a harbour breakwater. The winch is hidden behind the taller dockhand, '
               'while the cable drum is clearly visible beside him, lit by the storm lamp hanging '
               'from the gantry.')
    assert not blocking(partial, 'still_frame')


# ---------------------------------------------------------------------------
# Coverage: every capability that WRITES a prompt must receive the rules
# ---------------------------------------------------------------------------

def test_every_writing_capability_receives_the_shared_rules():
    """A route audit, so a new writing entry point cannot silently miss the shared method.

    Reviewing capabilities are deliberately excluded: they judge consistency and already carry their
    own review references plus the deterministic checks.
    """
    import json
    from pathlib import Path
    import studio.production_methods as pm
    manifest = json.loads((Path(pm.__file__).parent / 'bundled/studio-production-methods/manifest.json').read_text())
    writers = ('narrative', 'storyboard', 'storyboard_frames', 'image', 'image_prepare',
               'h3', 'h3_prepare', 'h3_shot', 'h3_scene', 'h3_global',
               'h3_strategy', 'h3_video_prompt', 'h3_group_plan')
    for capability in writers:
        files = manifest['routes'].get(capability, [])
        assert any('prompt-writing' in f for f in files), \
            f'{capability} writes prompts but does not receive the shared writing rules'
    for capability in writers:
        text, _ = pm.snapshot(capability)
        assert 'Decide what the frame is for' in text, \
            f'{capability} is routed the file but the snapshot does not contain the principles'


def test_video_tasks_are_distinct_not_one_fixed_template():
    """T2I, image edit, I2V and montage must not all share one rigid template."""
    assert pw.task_for_video('I2VA') == 'video_i2va'
    assert pw.task_for_video('FL2VA') == 'video_fl2va'
    assert pw.task_for_video('REF2VA') == 'video_ref2va'
    assert len({pw.task_for_video(m) for m in ('I2VA', 'FL2VA', 'REF2VA')}) == 3, \
        'the three video modes must not collapse onto one task'

    still = pw.task('exact_start_keyframe')
    video = pw.task('video_i2va')
    assert still['kind'] != video['kind']
    # A frozen-instant rule belongs to stills; a video may carry ordered action.
    assert 'still_action_leak' in still['checks']
    assert 'still_action_leak' not in video['checks'], \
        'the still-image instant rule must not be applied to video progression'

    edit = pw.task('image_edit')
    assert 'requires_fields' in edit and edit['requires_fields'], \
        'image edit must demand an explicit what-changes / what-is-kept delta'


def test_image_tasks_follow_the_target_not_a_single_template():
    assert pw.task_for_image('character') == 'character_sheet'
    assert pw.task_for_image('location') == 'location_plate'
    assert pw.task_for_image('prop') == 'prop_design'
    assert pw.task_for_image('frame', moment='start') == 'exact_start_keyframe'
    assert pw.task_for_image('frame', moment='end') == 'still_frame'
    assert pw.task_for_image('frame', operation='inpaint') == 'image_edit'

