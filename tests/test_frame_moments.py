import copy
import json
import pytest
from studio import image_prompts as ip, frame_moments as fm, providers, store
from test_production import plan
from test_image_prompt_assembly import prepared


def test_start_end_and_exact_interior_states(plan):
    shot=plan['shots'][0]
    shot['keyframes'].append({'id':'middle','moment':'key','source_time':2.5,'description':'Ada reaching.',
                             'state':[{'entity_id':'ada','key':'hand','value':'reaching'}]})
    for target,time,states,path in [('start',0,shot['start_state'],'start_state'),
                                   ('end',6,shot['end_state'],'end_state'),
                                   ('middle',2.5,shot['keyframes'][-1]['state'],'keyframes[middle].state')]:
        c=ip.source(plan,target)['frame_moment_contract']
        assert c['source_time']==time and c['states']==states and c['state_source'].endswith(path)
        assert c['temporal_context']['beats']==shot['beats']
        assert c['identity_names']=={'ada':'Ada','room':'Workshop'}


def test_source_immutability_full_audit_hash_and_entity_scope(plan):
    original=copy.deepcopy(plan);basis=ip.source(plan,'start');result=prepared('start')
    receipt=fm.audit(result,basis)
    assert receipt['source_hash']==store.digest(basis) and receipt['result_hash']==store.digest(result)
    assert 'not a deterministic proof' in receipt['semantic_note']
    changed=copy.deepcopy(basis);changed['frame_moment_contract']['temporal_context']['beats'][0]['action']='Changed event'
    assert fm.audit(result,changed)['source_hash']!=receipt['source_hash']
    basis['frame_moment_contract']['states'][0]['value']='changed'
    assert plan==original
    entity=ip.source(plan,'ada')
    assert 'frame_moment_contract' not in entity and fm.audit(prepared('ada'),entity) is None
    assert 'FROZEN-MOMENT RECONCILIATION' not in ip.instruction(entity,'task',[])


def test_preparation_instruction_owns_clear_precedence(plan):
    basis=ip.source(plan,'start','Keep the requested creative change.')
    text=ip.instruction(basis,'One still',[])
    assert 'FROZEN-MOMENT RECONCILIATION' in text
    for phrase in ('omitted_context','requested revision','authoritative state or timeline','different scopes'):
        assert phrase in text


@pytest.mark.parametrize('blocked',[False,True])
def test_terminal_audits_preserve_original_source_and_results(plan,tmp_path,monkeypatch,blocked):
    basis=ip.source(plan,'start');candidate=prepared('start')
    candidate['omitted_context']=['Aligned stale raised-hand description to lowered-hand state.']
    if blocked:candidate['conflicts']=['Two authoritative requirements cannot both hold.']
    calls=[]
    monkeypatch.setattr(providers,'run',lambda *a:calls.append(a) or copy.deepcopy(candidate))
    request=ip.instruction(basis,'One still',[])
    if blocked:
        with pytest.raises(ip.ConflictError):ip.prepare(providers.DEFAULT,basis,'One still',[],request,tmp_path)
    else:ip.prepare(providers.DEFAULT,basis,'One still',[],request,tmp_path)
    audit=json.loads((tmp_path/'moment-alignment.json').read_text())
    assert audit['conflicts']==candidate['conflicts'] and audit['omitted_context']==candidate['omitted_context']
    assert json.loads((tmp_path/'source.json').read_text())==basis
    assert json.loads((tmp_path/'result.json').read_text())==candidate
    assert len(calls)==(2 if blocked else 1)
    assert (tmp_path/'render-prompt.txt').exists() is (not blocked)
