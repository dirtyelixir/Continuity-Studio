"""Contracts for the affirmative off-state restatement.

Measured behaviour that motivates it: a brief declaring 'unlit ... no filament glow' produced a
glowing bulb from the same pixels, and this pipeline has no negative prompt (the klein graph
zeroes the negative conditioning at cfg 1.0), so the declared inactive state is restated as the
material that IS present. Unrelated briefs must stay byte-identical.
"""
import json

from studio import image_prompts


def prepared(**over):
    data = {'visual_style': 'Painted stop-motion look.', 'appearance': 'Lantern on a bench.',
            'composition': 'Single locked two-shot.', 'lighting': 'Two sources only.',
            'requested_changes': '', 'conflicts': [], 'target_id': 'frame_01_start',
            'omitted_context': []}
    data.update(over)
    return data


def basis(states, **over):
    data = {'target_id': 'frame_01_start', 'target_kind': 'frame', 'high_reference_fidelity': False,
            'frame_moment_contract': {'states': states,
                                      'identity_names': {'prop_lantern': 'Brass lantern'}}}
    data.update(over)
    return data


OFF = [{'entity_id': 'prop_lantern', 'key': 'power',
        'value': 'Off; unlit - dark glass chimney, no filament glow; it emits no light of its own.'},
       {'entity_id': 'char_ada', 'key': 'pose', 'value': 'Behind the bench.'}]


def test_declared_off_state_is_restated_affirmatively():
    states = OFF
    text = image_prompts.compile_prompt(prepared(), basis(states), 'One still', [])
    assert 'OFF-STATE RENDERING' in text
    assert 'Brass lantern (prop_lantern).power = "Off;' in text
    assert 'switched off' in text


def test_basis_without_a_declared_off_state_compiles_byte_identically():
    """The clause must not touch prompts that declare no inactive object."""
    lit = [dict(OFF[0], value='On; steady warm light.')]
    with_clause = image_prompts.compile_prompt(prepared(), basis(OFF), 'One still', [])
    without = image_prompts.compile_prompt(prepared(), basis(lit), 'One still', [])
    assert 'OFF-STATE RENDERING' not in without
    assert without == with_clause.replace(image_prompts.off_state_note(basis(OFF)) + '\n\n', '', 1)
    assert image_prompts.off_state_note(basis(lit)) == ''
    assert image_prompts.off_state_note({}) == ''
    assert image_prompts.off_state_note({'frame_moment_contract': None}) == ''


def test_only_power_and_illumination_keys_with_an_off_value_trigger_the_clause():
    assert image_prompts.off_state_note(basis([{'entity_id': 'p', 'key': 'toggle_position', 'value': 'Down.'}])) == ''
    assert image_prompts.off_state_note(basis([{'entity_id': 'p', 'key': 'power', 'value': 'Dim, flickering.'}])) == ''
    assert image_prompts.off_state_note(basis([{'entity_id': 'p', 'key': 'illumination', 'value': 'OFF'}])) != ''


def test_clause_is_lamp_agnostic_so_it_can_serve_any_prop():
    note = image_prompts.off_state_note(basis([{'entity_id': 'prop_radio', 'key': 'power', 'value': 'Off.'}]))
    for word in ('glass', 'bulb', 'filament', 'lamp'):
        assert word not in note.lower()
    assert 'prop_radio' in note
