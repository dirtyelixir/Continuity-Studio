import copy
import json
import pytest
from studio import frame_moment_guard as guard, image_prompts, providers, store, engine, models
from test_production import client, plan, create, add_asset
from test_image_prompt_assembly import prepared


def invoke(tmp_path, monkeypatch, replies, basis=None):
    basis = basis or {'target_id':'start','target_kind':'frame','high_reference_fidelity':False,
                      'frame_moment_contract':{'states':[{'entity_id':'ada','key':'hand','value':'lowered'}]}}
    result = prepared('start')
    calls = []
    def run(provider, cap, prompt, images, work):
        calls.append((provider,cap,prompt))
        value = replies[len(calls)-1]
        if isinstance(value, Exception):raise value
        return copy.deepcopy(value)
    monkeypatch.setattr(providers,'run',run)
    args=(providers.DEFAULT,basis,'One still',[],'Original request',result,
          image_prompts.compile_prompt(result,basis,'One still',[]),[],tmp_path/'job')
    return args,calls


PASS={'verdict':'pass','summary':'The actual brief follows the moment.','issues':[]}
REVISE={'verdict':'revise','summary':'Hand contradicts start state.','issues':['Keep Ada hand lowered, not raised.']}


def test_success_durable_reuse_and_changed_source_refused(tmp_path,monkeypatch):
    args,calls=invoke(tmp_path,monkeypatch,[PASS])
    a=guard.ensure(*args);b=guard.ensure(*args)
    assert a==b and len(calls)==1 and a[2]['state']=='accepted'
    assert a[2]['repaired'] is False
    changed=list(args);changed[1]=copy.deepcopy(args[1]);changed[1]['target_id']='other'
    with pytest.raises(ValueError,match='來源'):guard.ensure(*changed)
    assert len(calls)==1


def test_same_provider_one_repair_then_recheck(tmp_path,monkeypatch):
    corrected=prepared('start');corrected['composition']='Ada with her hand lowered.'
    corrected['omitted_context']=['Superseded raised hand with authoritative lowered hand.']
    corrected=models.PreparedImage.model_validate(corrected).model_dump()
    args,calls=invoke(tmp_path,monkeypatch,[REVISE,corrected,PASS])
    result,prompt,receipt=guard.ensure(*args)
    assert result==corrected and 'hand lowered' in prompt and receipt['repaired']
    assert [x[1] for x in calls]==['qc','image_prepare','qc']
    assert all(x[0]==providers.DEFAULT for x in calls)
    assert guard.ensure(*args)[0]==corrected and len(calls)==3


@pytest.mark.parametrize('replies',[[RuntimeError('transport')], [REVISE,prepared('start'),REVISE],
                                 [{'verdict':'uncertain','summary':'Ambiguous authoritative state.','issues':[]}],
                                 [REVISE,{**prepared('start'),'conflicts':['Two explicit requested states disagree.']}],
                                 [REVISE,{**prepared('start'),'target_id':'wrong'}]])
def test_unresolved_incomplete_and_invalid_repairs_never_repeat(tmp_path,monkeypatch,replies):
    args,calls=invoke(tmp_path,monkeypatch,replies)
    with pytest.raises((ValueError,RuntimeError)):guard.ensure(*args)
    used=len(calls)
    with pytest.raises(ValueError,match='未重複'):guard.ensure(*args)
    assert len(calls)==used and used<=3
    assert json.loads((args[-1]/'moment-verification.json').read_text())['state']=='blocked'


def test_cancellation_and_entity_skip(tmp_path,monkeypatch):
    args,calls=invoke(tmp_path,monkeypatch,[PASS]);args[-1].mkdir()
    (args[-1]/'cancel-requested').touch()
    with pytest.raises(RuntimeError,match='取消'):guard.ensure(*args)
    assert not calls
    changed=list(args);changed[1]={**args[1]};changed[1].pop('frame_moment_contract')
    assert guard.ensure(*changed)[2] is None and not calls


def test_tampered_verified_brief_is_not_consumed(tmp_path,monkeypatch):
    args,calls=invoke(tmp_path,monkeypatch,[PASS]);guard.ensure(*args)
    path=args[-1]/'moment-verification.json';receipt=json.loads(path.read_text())
    receipt['prepared_image']['composition']='Changed after verification.'
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError,match='不完整'):guard.ensure(*args)
    assert len(calls)==1


def test_generation_and_revision_prompts_require_joint_state_update(client,plan):
    pid=create(client,plan)
    inp,_=engine.build_input(store.project(pid),models.JobRequest(capability='narrative',feedback='Change the acting.'))
    assert guard.PLANNING in inp['prompt']
    assert guard.PLANNING in inp['context_instructions']


def test_failed_preflight_blocks_actual_engine_renderer(client,plan,monkeypatch):
    pid=create(client,plan)
    for target in ('ada','room'):add_asset(pid,plan,target)
    calls=[]
    def run(provider,cap,prompt,images,work):
        calls.append(cap)
        if cap=='image_prepare':return prepared('start')
        assert cap=='qc', 'Rendering must never be reached on a failed text preflight'
        return REVISE
    monkeypatch.setattr(providers,'run',run)
    job=engine.enqueue(pid,models.JobRequest(capability='image',target_id='start'))['job']
    engine.execute(job['id'])
    saved=store.job(job['id'])
    assert saved['state']=='failed' and calls==['image_prepare','qc','image_prepare','qc']
    assert not any(a.get('job_id')==job['id'] for a in store.assets(pid))
    r=client.get('/api/jobs/'+job['id']).json()
    assert r['moment_verification']['state']=='blocked'
    assert store.project(pid)['revision']==1
