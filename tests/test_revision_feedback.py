import pytest
from studio.revision_feedback import canonical_feedback
from test_canonical_shot_state import gate, legacy, client

pytestmark=pytest.mark.canonical_state


@pytest.mark.parametrize('feedback',[
    'Director requests a revision to shot_01: . Preserve all other shots and canonical identities unless the requested change requires continuity updates. Preserve stable IDs.',
    'Revise shot shot_01: . Preserve all other shots in this chapter and all shared canon IDs and facts.',
])
def test_empty_owned_template_means_autonomous_generation(feedback):
    for shot in ('shot_01','shot_02'):
        text=canonical_feedback(feedback,shot)
        assert 'expects autonomous generation' in text
        assert 'this source is '+shot in text
        assert 'report actual state/timing contradictions normally' in text


@pytest.mark.parametrize('feedback',[
    '', 'Keep Pip looking at Ada.',
    'Director requests a revision to shot_01: keep the lantern dark. Preserve all other shots and canonical identities unless the requested change requires continuity updates. Preserve stable IDs.',
    'Revise shot shot_01: pause. Preserve all other shots in this chapter and all shared canon IDs and facts.',
    'Director requests a revision to shot_01: . Keep the lamp dark.',
])
def test_never_reinterprets_authored_feedback(feedback):
    assert canonical_feedback(feedback,'shot_02')==feedback


def test_real_prepare_path_records_interpretation_and_keeps_semantic_gate(gate,legacy,tmp_path):
    import json
    from studio import shot_state,providers
    feedback='Director requests a revision to shot_01: . Preserve all other shots and canonical identities unless the requested change requires continuity updates. Preserve stable IDs.'
    shot_state.prepare_plan(legacy,provider=providers.DEFAULT,work=tmp_path/'prepared',feedback=feedback)
    sources=list((tmp_path/'prepared').glob('*/source.json'))
    assert len(sources)==1
    assert 'expects autonomous generation' in json.loads(sources[0].read_text())['revision_request']
    assert gate==['shot_state_prepare','qc']
