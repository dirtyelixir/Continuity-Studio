import copy
import json

import pytest

from studio import chapter_pipeline as cp, store, engine, models, providers, serial_story
from test_production import client, plan
from test_directing import directed


@pytest.fixture
def production(plan):
    p = copy.deepcopy(plan)
    p['shots'] = []
    for i in range(4):
        shot = copy.deepcopy(plan['shots'][0])
        shot['id'] = f'shot{i}'
        for n, frame in enumerate(shot['keyframes']):
            frame['id'] = f'frame{i}_{n}'
        p['shots'].append(shot)
    return directed(p)


def outputs(p, coverage=None):
    outline = {k: copy.deepcopy(p[k]) for k in ('title','logline','story','screenplay','style','canon','scenes')}
    outline['shot_briefs'] = [{k:s[k] for k in ('id','scene_id','title','duration','entity_ids')} | {
        'purpose':s['shot_purpose'], 'action':s['action'], 'beat_ids':s['direction']['beat_ids']} for s in p['shots']]
    return [outline, {'shots':p['shots'][:3]}, {'shots':p['shots'][3:]},
            {'edit_plan':p['edit_plan'], 'coverage':coverage or [], 'adaptation_notes':[]}]


def setup_job(client, monkeypatch, kind='idea'):
    monkeypatch.setattr(engine.POOL, 'submit', lambda *args: None)
    p = client.post('/api/projects',json={'title':'連載','idea':'Ada 修燈的故事。','source_kind':'outline'}).json()
    ch = client.post(f'/api/projects/{p["id"]}/chapters',json={'title':'第一章','brief':'Ada fixes a lamp.','source_kind':kind}).json()
    cap = 'narrative' if kind == 'idea' else 'storyboard'
    r = client.post(f'/api/projects/{p["id"]}/jobs',json={'capability':cap,'target_id':ch['id']})
    assert r.status_code == 200, r.text
    j = r.json()['job']
    assert j['input']['chapter_pipeline'] == cp.VERSION
    return p, ch, j


def fake_provider(monkeypatch, results, calls, fail=None):
    def run(provider, capability, prompt, images, work):
        calls.append((capability, work.name, provider['id']))
        assert 'MANDATORY STUDIO PRODUCTION METHOD' in prompt
        assert provider['id'] == 'astra'
        if fail and fail(capability, work):
            raise RuntimeError('test-only transport timeout')
        if capability=='chapter_writing':
            value={k:copy.deepcopy(v) for k,v in results[0].items() if k!='shot_briefs'}
            for scene in value['scenes']:scene['director_plan']=None
            return value
        if capability=='chapter_scene':
            return {'scene_id':results[0]['scenes'][0]['id'],'director_plan':copy.deepcopy(results[0]['scenes'][0]['director_plan']),'shot_briefs':copy.deepcopy(results[0]['shot_briefs'])}
        if capability=='chapter_shots':
            requested=json.loads(prompt.split('REQUESTED SHOT BRIEFS:\n',1)[1].split('\nONE STRUCTURAL CORRECTION:',1)[0])
            all_shots=results[1]['shots']+results[2]['shots']
            return {'shots':[copy.deepcopy(next(s for s in all_shots if s['id']==b['id'])) for b in requested]}
        return copy.deepcopy(results[0 if capability=='chapter_outline' else 3])
    monkeypatch.setattr(providers, 'run', run)


def test_failed_batch_resume_reuses_saved_stages_and_keeps_adoption_gate(client, monkeypatch, production):
    p,ch,j = setup_job(client,monkeypatch)
    calls=[];fail=[True]
    fake_provider(monkeypatch,outputs(production),calls,lambda cap,w: fail[0] and w.name.startswith('04-'))
    engine.execute(j['id'])
    failed = store.job(j['id'])
    assert failed['state'] == 'failed' and failed['result'] is None
    work = store.DATA/'jobs'/j['id']
    assert not (work/'result.json').exists()
    assert cp.progress(failed)['completed_shots'] == 3
    first = (work/'01-writing-checkpoint.json').read_bytes()
    assert client.post('/api/jobs/'+j['id']+'/adopt',json={'revision':0}).status_code == 400
    # Routing changes must not silently switch an existing job's provider on resume.
    store.put_setting('routing',{'narrative':'manual'})
    fail[0]=False
    assert client.post('/api/jobs/'+j['id']+'/resume').status_code == 200
    assert client.post('/api/jobs/'+j['id']+'/resume').status_code == 400
    engine.execute(j['id'])
    final = store.job(j['id'])
    assert final['state']=='succeeded' and final['result']==production
    assert [c[0] for c in calls]==['chapter_writing','chapter_scene','chapter_shots','chapter_shots','chapter_shots','chapter_edit']
    assert (work/'01-writing-checkpoint.json').read_bytes()==first
    assert (work/'04-shots-attempt-001').is_dir() and (work/'04-shots-attempt-002').is_dir()
    assert list(work.glob('failure-before-resume-*'))
    assert store.project(p['id'])['production'] is None
    assert client.post('/api/jobs/'+j['id']+'/adopt',json={'revision':0}).status_code==400
    assert any(x['capability']=='directing_qc' for x in store.jobs(p['id']))
    assert client.get('/api/projects/'+p['id']).json()['jobs'][1]['progress']['completed_shots']==4


def test_restart_recovery_accepts_valid_raw_stage_without_resubmission(client,monkeypatch,production):
    p,ch,j=setup_job(client,monkeypatch);calls=[]
    # Production execute marks running before entering the staged provider.
    with store.db() as c:c.execute('UPDATE jobs SET state="running" WHERE id=?',(j['id'],))
    fake_provider(monkeypatch,outputs(production),calls)
    work=store.DATA/'jobs'/j['id'];cp.run(j,work)
    # Simulate a crash after raw output but before checkpoint, and a server restart.
    (work/'03-shots-checkpoint.json').unlink()
    (work/'result.json').unlink()
    store.init()
    assert store.job(j['id'])['state']=='interrupted'
    def forbidden(*args): raise AssertionError('completed output was resubmitted')
    monkeypatch.setattr(providers,'run',forbidden)
    assert client.post('/api/jobs/'+j['id']+'/resume').status_code==200
    engine.execute(j['id'])
    assert store.job(j['id'])['result']==production


@pytest.mark.parametrize('mutation',['outline','chapter','revision','director','cancel','active'])
def test_resume_rejects_changed_sources_cancellation_and_duplicate_work(client,monkeypatch,mutation):
    p,ch,j=setup_job(client,monkeypatch)
    with store.db() as c:
        c.execute('UPDATE jobs SET state="failed" WHERE id=?',(j['id'],))
        if mutation=='revision': c.execute('UPDATE projects SET revision=1 WHERE id=?',(p['id'],))
        if mutation=='outline': c.execute('UPDATE projects SET idea="changed" WHERE id=?',(p['id'],))
        if mutation=='chapter': c.execute('UPDATE story_chapters SET version=1 WHERE id=?',(ch['id'],))
    if mutation=='director': store.put_setting('director_style:'+p['id'],{'id':'changed-direction'})
    if mutation=='cancel':
        work=store.DATA/'jobs'/j['id'];work.mkdir(parents=True);(work/'cancel-requested').touch()
    if mutation=='active':
        client.post(f'/api/projects/{p["id"]}/jobs',json={'capability':'narrative','target_id':ch['id']})
    assert client.post('/api/jobs/'+j['id']+'/resume').status_code==400
    assert store.job(j['id'])['state']=='failed'


def test_checkpoint_tampering_fails_closed(client,monkeypatch,production):
    p,ch,j=setup_job(client,monkeypatch);calls=[]
    fake_provider(monkeypatch,outputs(production),calls)
    work=store.DATA/'jobs'/j['id'];cp.run(j,work)
    path=work/'01-writing-checkpoint.json';data=json.loads(path.read_text());data['result']['title']='tampered';path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='不符'): cp.run(j,work)
    assert len(calls)==5


def test_bad_stage_gets_one_correction_and_cancellation_prevents_checkpoint(client,monkeypatch,production):
    p,ch,j=setup_job(client,monkeypatch);results=outputs(production);calls=[]
    fake_provider(monkeypatch,results,calls)
    original=providers.run
    def run(provider,cap,prompt,images,work):
        value=original(provider,cap,prompt,images,work)
        if cap=='chapter_shots' and work.name.endswith('001'):
            value['shots'][0]['id']='wrong'
        return value
    monkeypatch.setattr(providers,'run',run)
    work=store.DATA/'jobs'/j['id'];cp.run(j,work)
    assert len(calls)==7
    assert (work/'03-shots-attempt-001/result.json').is_file()
    assert (work/'03-shots-attempt-002/result.json').is_file()
    (work/'cancel-requested').touch()
    with pytest.raises(RuntimeError,match='取消'): cp.run(j,work)
    assert len(calls)==7


def test_storyboard_final_coverage_is_checked(client,monkeypatch,production):
    p,ch,j=setup_job(client,monkeypatch,'story');calls=[]
    coverage=[{'source_id':u['id'],'shot_ids':[s['id'] for s in production['shots']],'treatment':'Preserved'} for u in j['input']['source']['units']]
    fake_provider(monkeypatch,outputs(production,coverage),calls)
    engine.execute(j['id'])
    result=store.job(j['id'])
    assert result['state']=='succeeded',result['error']
    assert result['result']['coverage']==coverage
    assert result['result']['production']==production


def test_outline_rejects_canon_changes_and_missing_beat(production):
    outline=outputs(production)[0]
    modified=copy.deepcopy(outline);modified['canon'][0]['description']='changed'
    with pytest.raises(ValueError,match='canon'): cp.validate_outline(modified,production['canon'])
    modified=copy.deepcopy(outline);modified['shot_briefs'][0]['beat_ids']=['missing']
    with pytest.raises(ValueError,match='節拍'): cp.validate_outline(modified,production['canon'])
    modified=copy.deepcopy(outline);modified['canon'][0]['scope']='public'
    checked=cp.validate_outline(modified,production['canon'])
    assert checked['canon'][0]['scope']==production['canon'][0]['scope']
    assert modified['canon'][0]['scope']=='public'  # Raw provider evidence stays intact.
    modified=copy.deepcopy(outline);modified['shot_briefs'][0]['beat_ids']*=2
    with pytest.raises(ValueError,match='節拍'): cp.validate_outline(modified,production['canon'])


def test_manual_and_nonchapter_generation_remain_existing_contract(client,monkeypatch):
    monkeypatch.setattr(engine.POOL,'submit',lambda *args:None)
    p=client.post('/api/projects',json={'title':'Short','idea':'A lamp glows.'}).json()
    j=client.post(f'/api/projects/{p["id"]}/jobs',json={'capability':'narrative'}).json()['job']
    assert not j['input'].get('chapter_pipeline')


def test_cancel_during_provider_return_never_checkpoints_or_finishes(client,monkeypatch,production):
    p,ch,j=setup_job(client,monkeypatch)
    def run(provider,cap,prompt,images,work):
        (work.parent/'cancel-requested').touch()
        return {k:v for k,v in outputs(production)[0].items() if k!='shot_briefs'}
    monkeypatch.setattr(providers,'run',run)
    engine.execute(j['id'])
    work=store.DATA/'jobs'/j['id']
    assert store.job(j['id'])['state']=='cancelled'
    assert not list(work.glob('*checkpoint.json'))
    assert not (work/'result.json').exists()
    assert store.project(p['id'])['production'] is None


def test_empty_attempt_after_crash_does_not_block_resume(client,monkeypatch,production):
    p,ch,j=setup_job(client,monkeypatch);calls=[]
    work=store.DATA/'jobs'/j['id'];(work/'01-writing-attempt-001').mkdir(parents=True)
    fake_provider(monkeypatch,outputs(production),calls)
    assert cp.run(j,work)==production
    assert calls[0][1]=='01-writing-attempt-002'
    assert not list((work/'01-writing-attempt-001').iterdir())


def test_v1_jobs_remain_resumable_with_original_stage_contract(client,monkeypatch,production):
    p,ch,j=setup_job(client,monkeypatch);calls=[]
    j['input']['chapter_pipeline']='chapter-stages-v1'
    fake_provider(monkeypatch,outputs(production),calls)
    work=store.DATA/'jobs'/j['id']
    assert cp.run(j,work)==production
    assert [c[0] for c in calls]==['chapter_outline','chapter_shots','chapter_shots','chapter_edit']
    assert (work/'01-outline-checkpoint.json').is_file()
    assert cp.run(j,work)==production
    assert len(calls)==4


def test_adopted_writing_is_saved_verbatim_without_model_call(client,monkeypatch,production):
    p,ch,j=setup_job(client,monkeypatch);calls=[]
    adopted=copy.deepcopy(production)
    adopted['chapters']=[{'id':ch['id'],'title':ch['title'],'story':production['story'],
                          'screenplay':production['screenplay'],'scene_ids':['scene']}]
    with store.db() as c:
        c.execute('UPDATE projects SET production=?,revision=1 WHERE id=?',(store.encode(adopted),p['id']))
        c.execute('UPDATE jobs SET state="failed" WHERE id=?',(j['id'],))
    store.put_setting('chapter_source:'+p['id']+':'+ch['id'],serial_story.writing_provenance(j['input']['serial_source'],production))
    j=client.post(f'/api/projects/{p["id"]}/jobs',json={'capability':'narrative','target_id':ch['id']}).json()['job']
    assert j['input']['chapter_writing']['screenplay']==production['screenplay']
    fake_provider(monkeypatch,outputs(production),calls)
    work=store.DATA/'jobs'/j['id'];result=cp.run(j,work)
    assert result['story']==production['story'] and result['screenplay']==production['screenplay']
    assert result['canon']==production['canon']
    assert [c[0] for c in calls]==['chapter_scene','chapter_shots','chapter_shots','chapter_edit']
    checkpoint=json.loads((work/'01-writing-checkpoint.json').read_text())
    assert checkpoint['origin']=='adopted-writing'
    with store.db() as c:c.execute('UPDATE jobs SET state="failed" WHERE id=?',(j['id'],))
    revised=client.post(f'/api/projects/{p["id"]}/jobs',json={'capability':'narrative','target_id':ch['id'],'feedback':'Rewrite the ending.'}).json()['job']
    assert not revised['input'].get('chapter_writing')
    with store.db() as c:
        c.execute('UPDATE jobs SET state="failed" WHERE id=?',(revised['id'],))
        c.execute('UPDATE story_chapters SET brief="A different story",version=version+1 WHERE id=?',(ch['id'],))
    changed=client.post(f'/api/projects/{p["id"]}/jobs',json={'capability':'narrative','target_id':ch['id']}).json()['job']
    assert not changed['input'].get('chapter_writing')


def bounded_provider(monkeypatch, production, calls, fail_batch=None, missing=False):
    fake_provider(monkeypatch, outputs(production), calls)
    original = providers.run
    def run(provider, cap, prompt, images, work):
        if cap not in ('chapter_edit_order', 'chapter_coverage'):
            return original(provider, cap, prompt, images, work)
        calls.append((cap, work.name, provider['id']))
        assert 'MANDATORY STUDIO PRODUCTION METHOD' in prompt
        if cap == 'chapter_edit_order':
            return {'edit_plan': copy.deepcopy(production['edit_plan']), 'adaptation_notes': []}
        if fail_batch and fail_batch in work.name:
            (work/'provider-partial.txt').write_text('{"coverage":[')
            cp.atomic_json(work/'transport.json', {'status':'truncated'})
            raise RuntimeError('DeepSeek 輸出達到長度上限')
        if 'coverage-repair' in work.name:
            rows = json.loads(prompt.split('SAVED COVERAGE:\n')[1].split('\nSHOTS WITHOUT SOURCE LINKS:')[0])
            return {'coverage':[{**rows[0], 'shot_ids':[s['id'] for s in production['shots']]}]}
        units = json.loads(prompt.split('REQUESTED SOURCE UNITS:\n')[1].split('\nONE STRUCTURAL CORRECTION:')[0])
        return {'coverage':[{'source_id':u['id'], 'shot_ids':[s['id'] for s in production['shots'][:1 if missing else 4]], 'treatment':'Preserved source action.'} for u in units]}
    monkeypatch.setattr(providers, 'run', run)


def long_job(client, monkeypatch, production):
    _, _, job = setup_job(client, monkeypatch, 'story')
    source = job['input']['source']
    source['units'] = [{'id':f'P{i}', 'text':'Ada fixes a lamp.'} for i in range(161)]
    source['source_text'] = '\n'.join(u['text'] for u in source['units'])
    production['story'] = source['source_text']
    return job, store.DATA/'jobs'/job['id']


def test_long_final_resume_skips_saved_shots_order_and_coverage(client, monkeypatch, production):
    job, work = long_job(client, monkeypatch, production)
    calls=[]
    bounded_provider(monkeypatch, production, calls, fail_batch='coverage-002')
    with pytest.raises(RuntimeError, match='長度上限'):
        cp.run(job, work)
    saved={p.name:p.read_bytes() for p in work.glob('*-checkpoint.json')}
    assert len(saved)==6  # writing, scene, two shot batches, order, first coverage
    assert cp.progress(job)['finalization']['covered_units']==80
    assert not (work/'result.json').exists()
    calls.clear()
    bounded_provider(monkeypatch, production, calls)
    result=cp.run(job, work)
    assert result['production']==production
    assert [x['source_id'] for x in result['coverage']]==[u['id'] for u in job['input']['source']['units']]
    assert [x[1] for x in calls]==['05-edit-bounded-v1-coverage-002-attempt-002','05-edit-bounded-v1-coverage-003-attempt-001']
    assert all((work/name).read_bytes()==value for name,value in saved.items())
    assert cp.progress(job)['finalization']=={'completed':4,'total':4,'covered_units':161,'total_units':161}
    assert cp.progress(job)['completed']==5


def test_legacy_truncated_final_migrates_without_changing_checkpoints(client, monkeypatch, production):
    _, _, job=setup_job(client,monkeypatch,'story');work=store.DATA/'jobs'/job['id'];calls=[]
    fake_provider(monkeypatch,outputs(production),calls)
    original=providers.run
    def truncate(provider,cap,prompt,images,attempt):
        if cap=='chapter_edit':
            cp.atomic_json(attempt/'transport.json', {'status':'truncated'})
            (attempt/'provider-partial.txt').write_text('{"edit_plan":[')
            raise RuntimeError('length')
        return original(provider,cap,prompt,images,attempt)
    monkeypatch.setattr(providers,'run',truncate)
    with pytest.raises(RuntimeError,match='length'):cp.run(job,work)
    saved={p.name:p.read_bytes() for p in work.glob('*-checkpoint.json')}
    bounded_provider(monkeypatch,production,calls)
    assert cp.run(job,work)['production']==production
    assert all((work/name).read_bytes()==value for name,value in saved.items())
    assert (work/'05-edit-attempt-001/provider-partial.txt').read_text()=='{"edit_plan":['
    assert not (work/'05-edit-attempt-002').exists()


def test_cross_batch_missing_shot_repairs_only_source_links(client, monkeypatch, production):
    job,work=long_job(client,monkeypatch,production);calls=[]
    bounded_provider(monkeypatch,production,calls,missing=True)
    result=cp.run(job,work)
    assert result['production']==production
    assert len(result['coverage'])==161
    assert len(result['coverage'][0]['shot_ids'])==4
    assert cp.progress(job)['finalization']['completed']==5
    calls.clear()
    assert cp.run(job,work)==result
    assert calls==[]


@pytest.mark.parametrize('corruption',['hash','foreign_source','foreign_shot','duplicate_source'])
def test_bounded_coverage_rejects_corrupt_checkpoint(client,monkeypatch,production,corruption):
    job,work=long_job(client,monkeypatch,production);calls=[]
    bounded_provider(monkeypatch,production,calls)
    cp.run(job,work)
    path=work/'05-edit-bounded-v1-coverage-001-checkpoint.json'
    record=json.loads(path.read_text())
    if corruption=='hash':record['input_hash']='foreign-input'
    else:
        rows=record['result']['coverage']
        if corruption=='foreign_source':rows[0]['source_id']='other-source'
        if corruption=='foreign_shot':rows[0]['shot_ids']=['other-shot']
        if corruption=='duplicate_source':rows[1]['source_id']=rows[0]['source_id']
        record['result_hash']=store.digest(record['result'])
    cp.atomic_json(path,record);calls.clear()
    with pytest.raises(ValueError):cp.run(job,work)
    assert calls==[]


def test_complete_legacy_long_result_reuses_original_contract(client,monkeypatch,production):
    job,work=long_job(client,monkeypatch,production);calls=[]
    # Simulate a final completed under the original monolithic implementation.
    coverage=[{'source_id':u['id'],'shot_ids':[s['id'] for s in production['shots']],'treatment':'Preserved'} for u in job['input']['source']['units']]
    monkeypatch.setattr(cp,'COVERAGE_BATCH_SIZE',1000)
    fake_provider(monkeypatch,outputs(production,coverage),calls)
    result=cp.run(job,work)
    saved=(work/'05-edit-checkpoint.json').read_bytes()
    monkeypatch.setattr(cp,'COVERAGE_BATCH_SIZE',80)
    calls.clear()
    assert cp.run(job,work)==result
    assert calls==[] and (work/'05-edit-checkpoint.json').read_bytes()==saved
    # Same guarantee after a crash before the legacy checkpoint was written.
    (work/'05-edit-checkpoint.json').unlink()
    assert cp.run(job,work)==result
    assert calls==[]
