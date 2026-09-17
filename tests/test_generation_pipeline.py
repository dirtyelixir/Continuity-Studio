"""Adaptive planning protocol; all sources, files and provider calls are isolated."""
import copy
import json

import pytest
import httpx

from studio import context_limits as limits, engine, generation_groups as gg
from studio import generation_pipeline as gp, models, providers, store
from test_production import client, plan, create
from test_generation_groups import montage


def test_http_length_receipt_is_explicit_and_never_validated_as_complete(tmp_path,monkeypatch):
    provider={**providers.LOCAL_QWEN,'tokenizer':'estimate'}
    provider['context_policy']=limits.freeze(provider,probe=False)
    real=httpx.Client
    def handler(request):
        payload=json.loads(request.content)
        assert payload['max_tokens']==provider['max_output_tokens']
        assert request.headers['X-VRAM-Wait-Seconds']=='0'
        return httpx.Response(200,json={'choices':[{'finish_reason':'length','message':{'content':json.dumps(response(['view1']))}}],'usage':{'completion_tokens':8192}})
    monkeypatch.setattr(providers.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    with pytest.raises(RuntimeError,match='truncated'):
        providers.run(provider,'h3_group_plan','Plan the original source.',[],tmp_path)
    assert gp.Planner.exhausted(tmp_path)
    assert not (tmp_path/'result.json').exists()


def test_qwen_unavailable_tokenizer_stops_without_fallback(montage,tmp_path,monkeypatch):
    inp=input_for(montage,kind='http')
    inp['provider_config']={**providers.LOCAL_QWEN,'context_policy':limits.freeze(providers.LOCAL_QWEN,probe=False)}
    job,work=setup_job(tmp_path,monkeypatch,inp);calls=[];fake(monkeypatch,calls)
    real=httpx.Client
    monkeypatch.setattr(limits.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(lambda req:httpx.Response(503,json={'error':'busy'})),**kw))
    with pytest.raises(ValueError,match='未能經所選服務商核對 token'):
        gp.run(job,work)
    assert not calls and not (work/'generation-complete.json').exists()


def input_for(production, output=32768, window=131072, kind='codex'):
    ids = [e['id'] for e in production['edit_plan']]
    source = {'production':production, 'scene_id':'scene', 'edit_positions':dict(zip(ids,range(len(ids)))),
              'plan_contract_version':gg.PLAN_CONTRACT_VERSION, 'storyboard_intent':[],
              'frame_readiness':{}, 'storyboard_reviewed_frames':[], 'method_hash':'test'}
    provider = {'id':'test','kind':kind,'context_policy':limits.freeze({'kind':kind,'context_window':window,'max_output_tokens':output},probe=False)}
    return {'generation_pipeline':gp.VERSION,'group_plan_source':source,'group_plan_hash':gg.planning_fingerprint(source),
            'prompt':'Complete original planning source:\n'+gp.encode(source)+'\nKeep all original dialogue.',
            'provider_config':provider,'schema':providers.strict_schema(gg.GroupPlan.model_json_schema())}


def response(ids, native=False):
    item = lambda es: {'title':'安排','edit_ids':es,'execution':'native_montage' if native else 'separate_source',
                      'mode':'I2VA' if native else None,'reference_targets':[], 'reason':'核對畫面與切鏡。','checks':['核對接觸位置。']}
    return {'summary':'已核對來源。','groups':[item(ids)] if native else [item([eid]) for eid in ids]}


def fake(monkeypatch, calls, fail=None, merge=False, length_first=False):
    def run(provider, cap, prompt, images, work):
        assert cap=='h3_group_plan' and images==[]
        assert json.loads((work/'context-budget.json').read_text())['fits']
        start=prompt.index('{"edit_positions":')
        source,_=json.JSONDecoder().raw_decode(prompt,start)
        ids=[e['id'] for e in source['production']['edit_plan']]
        calls.append({'provider':copy.deepcopy(provider),'ids':ids,'prompt':prompt,'work':work,'source':source})
        if fail and len(calls)==fail:raise RuntimeError('transport failed')
        if length_first and len(calls)==1:
            (work/'transport.json').write_text('{"finish_reason":"length"}')
            (work/'result.json').write_text(json.dumps(response(ids)))
            raise RuntimeError('output ended at length')
        return response(ids, native=merge and '"phase":"boundary"' in prompt)
    monkeypatch.setattr(providers,'run',run)


def setup_job(tmp_path, monkeypatch, inp):
    monkeypatch.setattr(store,'DATA',tmp_path)
    return {'id':'job','input':inp},tmp_path/'jobs/job'


def test_small_fitting_source_keeps_one_original_call(montage,tmp_path,monkeypatch):
    inp=input_for(montage);original=copy.deepcopy(inp);job,work=setup_job(tmp_path,monkeypatch,inp)
    calls=[];fake(monkeypatch,calls)
    result=gp.run(job,work)
    assert len(calls)==1 and calls[0]['prompt']==inp['prompt']
    assert inp==original and calls[0]['provider']==inp['provider_config']
    gp.require_complete(job,result)


def test_full_request_keeps_unedited_scene_sources_and_scopes_conditioning(montage,tmp_path,monkeypatch):
    extra=copy.deepcopy(montage['shots'][0]);extra['id']='unused'
    montage['shots'].append(extra)
    inp=input_for(montage)
    inp['group_plan_source']['source_conditioning']={'shot':{'intent':'original A'},'reaction':{'intent':'original B'}}
    inp['prompt']='Original source:\n'+gp.encode(inp['group_plan_source'])
    job,work=setup_job(tmp_path,monkeypatch,inp)
    runner=gp.Planner(job,work)
    assert runner.task('root',runner.ids)['prompt']==inp['prompt']
    partial=gp.scope(inp['group_plan_source'],['view1'])
    assert partial['source_conditioning']=={'shot':{'intent':'original A'}}
    assert [s['id'] for s in partial['production']['shots']]==['shot']


def test_output_budget_splits_and_reconciles_native_group_across_batches(montage,tmp_path,monkeypatch):
    inp=input_for(montage,output=2000);job,work=setup_job(tmp_path,monkeypatch,inp)
    calls=[];fake(monkeypatch,calls,merge=True)
    result=gp.run(job,work)
    assert [c['ids'] for c in calls]==[['view1'],['view2'],['view1','view2']]
    assert len(result['groups'])==1 and result['groups'][0]['execution']=='native_montage'
    for call in calls[:2]:
        for shot in call['source']['production']['shots']:
            assert shot==next(s for s in montage['shots'] if s['id']==shot['id'])
    gp.require_complete(job,result)
    assert gp.progress(job)['completed']==3


def test_input_overflow_uses_boundary_projection_after_reading_full_sources(montage,tmp_path,monkeypatch):
    for shot in montage['shots']:
        shot['keyframes'][0]['description']='完整原文  \n' * 700
    inp=input_for(montage);job,work=setup_job(tmp_path,monkeypatch,inp)
    runner=gp.Planner(job,work)
    one=max(limits.count(runner.provider,runner.task('rootL',['view1'])['prompt'],runner.schema,runner.policy),
            limits.count(runner.provider,runner.task('rootR',['view2'])['prompt'],runner.schema,runner.policy))
    inp['provider_config']['context_policy']['context_window']=one+32768+1024+100
    calls=[];fake(monkeypatch,calls)
    result=gp.run(job,work)
    assert len(calls)==3
    assert all(c['source']['production']['shots'][0]['keyframes'][0].get('description') for c in calls[:2])
    assert '"projected"' not in calls[-1]['prompt']
    assert 'omits only source keyframe descriptions' in calls[-1]['prompt']
    assert json.loads((work/'root-node.json').read_text())['projected']
    gp.require_complete(job,result)


def test_explicit_resume_keeps_completed_batches_and_no_transport_retry(montage,tmp_path,monkeypatch):
    inp=input_for(montage,output=2000);job,work=setup_job(tmp_path,monkeypatch,inp)
    calls=[];fake(monkeypatch,calls,fail=2)
    with pytest.raises(RuntimeError,match='transport'):gp.run(job,work)
    assert len(calls)==2 and not (work/'generation-complete.json').exists()
    first=(work/'rootL-checkpoint.json').read_bytes()
    with pytest.raises(ValueError,match='未全部完成'):gp.require_complete(job,response(['view1','view2']))
    calls=[];fake(monkeypatch,calls)
    result=gp.run(job,work)
    assert [c['ids'] for c in calls]==[['view2'],['view1','view2']]
    assert (work/'rootL-checkpoint.json').read_bytes()==first
    gp.require_complete(job,result)


def test_proven_length_exhaustion_splits_without_using_even_valid_partial_output(montage,tmp_path,monkeypatch):
    inp=input_for(montage);job,work=setup_job(tmp_path,monkeypatch,inp)
    calls=[];fake(monkeypatch,calls,length_first=True)
    result=gp.run(job,work)
    assert len(calls)==4 and not (work/'root-checkpoint.json').exists()
    assert (work/'root-attempt-001/result.json').exists()
    gp.require_complete(job,result)
    calls.clear();gp.run(job,work);assert not calls


def test_smallest_original_unit_overflow_stops_before_spending(montage,tmp_path,monkeypatch):
    inp=input_for(montage,window=3000,output=1200);job,work=setup_job(tmp_path,monkeypatch,inp)
    calls=[];fake(monkeypatch,calls)
    with pytest.raises(ValueError,match='單一完整分鏡'):gp.run(job,work)
    assert calls==[] and not (work/'result.json').exists()


def test_cancel_and_tampered_checkpoint_block_completion(montage,tmp_path,monkeypatch):
    inp=input_for(montage,output=2000);job,work=setup_job(tmp_path,monkeypatch,inp)
    calls=[];fake(monkeypatch,calls)
    result=gp.run(job,work)
    checkpoint=work/'rootB-checkpoint.json';value=json.loads(checkpoint.read_text());value['result']['summary']='changed';checkpoint.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='未全部完成'):gp.require_complete(job,result)
    (work/'cancel-requested').touch()
    with pytest.raises(RuntimeError,match='取消'):gp.run(job,work)


def test_changed_frozen_provider_cannot_mix_checkpoints(montage,tmp_path,monkeypatch):
    inp=input_for(montage,output=2000);job,work=setup_job(tmp_path,monkeypatch,inp)
    calls=[];fake(monkeypatch,calls,fail=2)
    with pytest.raises(RuntimeError):gp.run(job,work)
    inp['provider_config']['context_policy']['max_output_tokens']+=1
    with pytest.raises(ValueError,match='凍結來源'):gp.run(job,work)
    assert len(calls)==2


def test_nested_batches_cover_reused_sources_in_exact_edit_order(montage,tmp_path,monkeypatch):
    for index in range(2,6):
        montage['edit_plan'].append({**montage['edit_plan'][index%2],'id':'reuse'+str(index)})
    inp=input_for(montage,output=2000);job,work=setup_job(tmp_path,monkeypatch,inp)
    calls=[];fake(monkeypatch,calls)
    result=gp.run(job,work)
    assert [eid for g in result['groups'] for eid in g['edit_ids']]==[e['id'] for e in montage['edit_plan']]
    assert len(calls)==11  # Six complete source decisions and five split boundaries.
    gp.require_complete(job,result)
    (work/'rootRB-checkpoint.json').unlink()
    with pytest.raises(ValueError,match='未全部完成'):gp.require_complete(job,result)


def test_boundary_failure_preserves_both_local_results(montage,tmp_path,monkeypatch):
    inp=input_for(montage,output=2000);job,work=setup_job(tmp_path,monkeypatch,inp)
    calls=[];fake(monkeypatch,calls,fail=3)
    with pytest.raises(RuntimeError,match='transport'):gp.run(job,work)
    assert len(list(work.glob('*-checkpoint.json')))==2
    calls=[];fake(monkeypatch,calls)
    result=gp.run(job,work)
    assert len(calls)==1 and calls[0]['ids']==['view1','view2']
    gp.require_complete(job,result)


def test_missing_image_use_never_becomes_completed_plan(montage,tmp_path,monkeypatch):
    inp=input_for(montage)
    inp['group_plan_source']['storyboard_intent']=[{'anchor_id':'a','edit_id':'view1'}]
    inp['prompt']='Source:\n'+gp.encode(inp['group_plan_source'])
    job,work=setup_job(tmp_path,monkeypatch,inp);calls=[];fake(monkeypatch,calls)
    with pytest.raises(ValueError,match='逐張'):gp.run(job,work)
    assert not (work/'generation-complete.json').exists()


def test_cancellation_after_provider_result_cannot_checkpoint_or_adopt(montage,tmp_path,monkeypatch):
    inp=input_for(montage);job,work=setup_job(tmp_path,monkeypatch,inp)
    def run(*args):
        (work/'cancel-requested').touch()
        return response(['view1','view2'])
    monkeypatch.setattr(providers,'run',run)
    with pytest.raises(RuntimeError,match='取消'):gp.run(job,work)
    assert not list(work.glob('*-checkpoint.json'))
    with pytest.raises(ValueError,match='未全部完成'):gp.require_complete(job,response(['view1','view2']))


def test_recover_complete_raw_attempt_without_submitting_again(montage,tmp_path,monkeypatch):
    inp=input_for(montage);job,work=setup_job(tmp_path,monkeypatch,inp)
    calls=[]
    def interrupted(provider,cap,prompt,images,attempt):
        calls.append(prompt)
        (attempt/'result.json').write_text(json.dumps(response(['view1','view2'])))
        raise RuntimeError('connection ended after output')
    monkeypatch.setattr(providers,'run',interrupted)
    with pytest.raises(RuntimeError):gp.run(job,work)
    result=gp.run(job,work)
    assert len(calls)==1
    gp.require_complete(job,result)


def test_native_tokenizer_drives_splitting_and_keeps_frozen_qwen_provider(montage,tmp_path,monkeypatch):
    inp=input_for(montage,kind='http',window=10000,output=2000)
    inp['provider_config'].update(id='local_qwen',base_url='http://manager.invalid/v1',tokenizer='llama_cpp')
    inp['provider_config']['context_policy']['tokenizer']='llama_cpp'
    measured=[]
    def measure(provider,text,policy):
        assert provider['id']=='local_qwen' and policy['tokenizer']=='llama_cpp'
        assert 'Return JSON matching this schema:' in text
        measured.append(text);return 1000
    monkeypatch.setattr(limits,'measure',measure)
    job,work=setup_job(tmp_path,monkeypatch,inp);calls=[];fake(monkeypatch,calls)
    result=gp.run(job,work)
    assert len(calls)==3 and measured
    assert all(c['provider']==inp['provider_config'] for c in calls)
    assert all(r['count_method']=='chat-template-tokenizer' for r in gp.receipts(job))
    gp.require_complete(job,result)


def test_new_api_jobs_use_pipeline_manual_and_old_jobs_keep_contract(client,montage,monkeypatch):
    pid=create(client,montage)
    j=client.post(f'/api/projects/{pid}/jobs',json={'capability':'h3_group_plan','target_id':'scene'}).json()['job']
    assert j['input']['generation_pipeline']==gp.VERSION
    assert client.get('/api/jobs/'+j['id']).json()['progress']['kind']=='generation_stages'
    assert client.get('/api/projects/'+pid).json()['jobs'][0]['input']['generation_pipeline']==gp.VERSION
    with store.db() as c:c.execute('update jobs set state="failed" where id=?',(j['id'],))
    assert client.post('/api/jobs/'+j['id']+'/resume').status_code==200
    with store.db() as c:c.execute('update jobs set state="failed" where id=?',(j['id'],))
    old=copy.deepcopy(j);old['input'].pop('generation_pipeline')
    # A legacy completed response remains valid; no retroactive receipt requirement.
    with store.db() as c:c.execute('update jobs set input=? where id=?',(store.encode(old['input']),j['id']))
    engine.finish(old,response(['view1','view2']))
    assert store.job(j['id'])['state']=='succeeded'
    client.post('/api/settings/routing',json={'capability':'h3_group_plan','provider_id':'manual'})
    manual=client.post(f'/api/projects/{pid}/jobs',json={'capability':'h3_group_plan','target_id':'scene'}).json()['job']
    assert 'generation_pipeline' not in manual['input']


def test_api_blocks_partial_adoption_and_stale_resume(client,montage):
    pid=create(client,montage)
    j=client.post(f'/api/projects/{pid}/jobs',json={'capability':'h3_group_plan','target_id':'scene'}).json()['job']
    candidate=response(['view1','view2'])
    with store.db() as c:
        c.execute('update jobs set state="succeeded",result=? where id=?',(store.encode(candidate),j['id']))
    r=client.post(f'/api/projects/{pid}/generation-groups/plan-adopt/'+j['id'],json={'revision':0})
    assert r.status_code==400 and '未全部完成' in r.text
    with store.db() as c:c.execute('update jobs set state="failed" where id=?',(j['id'],))
    p=store.project(pid);changed=copy.deepcopy(p['production']);changed['shots'][0]['action']='Different action'
    engine.save_plan(pid,changed,p['revision'],'test scope change')
    assert client.post('/api/jobs/'+j['id']+'/resume').status_code==400
