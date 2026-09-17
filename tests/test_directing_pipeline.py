import copy
import json
import pytest
from studio import directing_pipeline as dp, directing, providers, store, engine, models, context_limits
from test_production import client, plan
from test_directing import directed, reviewed, proposal_job


def input_for(plan, window=16000, output=3000, kind='codex', tokenizer=None):
    policy={'kind':kind,'context_window':window,'max_output_tokens':output}
    if tokenizer:
        policy['tokenizer']=tokenizer
    return {'directing_pipeline':dp.VERSION,'directing_source':plan,
            'prompt':'Review every beat. FROZEN PLAN:\n'+store.encode(plan)+'\nUser feedback: keep dialogue.',
            'provider_config':{**providers.DEFAULT,'kind':kind,'context_policy':context_limits.freeze(policy)}}


def many(plan):
    plan=directed(plan)
    for n in range(1,6):
        scene=copy.deepcopy(plan['scenes'][0]);scene['id']='scene'+str(n)
        shot=copy.deepcopy(plan['shots'][0]);shot['id']='shot'+str(n);shot['scene_id']=scene['id']
        for f in shot['keyframes']: f['id']+=str(n)
        plan['scenes'].append(scene);plan['shots'].append(shot)
        plan['edit_plan'].append({**plan['edit_plan'][0],'id':'edit'+str(n),'shot_id':shot['id']})
    plan['edit_plan'].append({**plan['edit_plan'][0],'id':'reuse'})
    return plan


def response(task,plan,verdict='pass'):
    if task['capability']=='directing_qc':
        rv=reviewed(task['scope'],verdict)
        rv['coverage']=[c for c in rv['coverage'] if [c['scene_id'],c['beat_id']] in task['keys']]
        return rv
    return {'verdict':verdict,'summary':'全局與接點核對結果。','checks':[{'id':k,'verdict':verdict,'evidence':plan['screenplay'],'reason':'檢查原文及實際剪接。','recommendation':'核對表演。'} for k in task['keys']], 'issues':[]}


def fake_runner(monkeypatch,inp,calls,fail=None,cross_verdict='pass'):
    tasks=dp.prepare(inp['provider_config'],inp['prompt'],inp['directing_source'])
    by_prompt={t['prompt']:t for t in tasks}
    def run(provider,cap,prompt,images,work):
        assert provider==inp['provider_config'] and not images
        task=by_prompt[prompt]
        assert context_limits.fits(context_limits.count(provider,prompt,dp.schema(provider,cap),provider['context_policy']),provider['context_policy'])
        calls.append(prompt)
        if fail is not None and len(calls)==fail:raise RuntimeError('transport stopped')
        return response(task,inp['directing_source'],cross_verdict if cap=='directing_cross_qc' else 'pass')
    monkeypatch.setattr(providers,'run',run)
    return tasks


def test_plan_covers_every_original_beat_shot_and_edit_pair(plan):
    p=many(plan);inp=input_for(p);tasks=dp.prepare(inp['provider_config'],inp['prompt'],p)
    assert len(tasks)>1
    keys=[tuple(k) for t in tasks if t['capability']=='directing_qc' for k in t['keys']]
    assert len(keys)==len(set(keys))==6
    assert {s['id'] for t in tasks if t['capability']=='directing_qc' for s in t['scope']['shots']}=={s['id'] for s in p['shots']}
    for t in tasks:
        assert t['fits']
        if t['capability']=='directing_qc':
            for shot in t['scope']['shots']:assert shot==next(s for s in p['shots'] if s['id']==shot['id'])
    cross=[t for t in tasks if t['capability']=='directing_cross_qc']
    assert sorted(k for t in cross for k in t['keys'])==sorted(['global']+['cut-'+str(n) for n in range(7)])
    last=next(t for t in cross if 'cut-6' in t['keys'])['scope']['payload']
    assert last['check_windows']['cut-6']==['edit5','reuse']
    assert last['complete_edit_order'][-1][1]=='shot'
    assert p==inp['directing_source']


def test_checkpoints_resume_and_complete_gate(plan,tmp_path,monkeypatch):
    p=many(plan);inp=input_for(p);job={'id':'j','input':inp};work=tmp_path/'jobs'/'j';work.mkdir(parents=True)
    monkeypatch.setattr(store,'DATA',tmp_path)
    calls=[];tasks=fake_runner(monkeypatch,inp,calls,fail=3)
    with pytest.raises(RuntimeError,match='transport'):dp.run(job,work)
    saved={f.name:f.read_bytes() for f in work.glob('*checkpoint.json')}
    assert len(saved)==2 and not (work/'result.json').exists()
    with pytest.raises(ValueError,match='未全部完成'):dp.require_complete(job,reviewed(p))
    calls=[];fake_runner(monkeypatch,inp,calls)
    result=dp.run(job,work)
    assert len(calls)==len(tasks)-2
    assert all((work/name).read_bytes()==data for name,data in saved.items())
    assert result['verdict']=='pass' and len(result['coverage'])==6
    dp.require_complete(job,result)
    calls.clear();assert dp.run(job,work)==result and not calls
    changed=copy.deepcopy(job);changed['input']['prompt']+=' Different instructions'
    with pytest.raises(ValueError,match='不符'):dp.run(changed,work)


def test_cross_uncertainty_and_findings_cannot_be_lost(plan,tmp_path,monkeypatch):
    p=many(plan);inp=input_for(p);calls=[];fake_runner(monkeypatch,inp,calls,cross_verdict='uncertain')
    result=dp.run({'id':'j','input':inp},tmp_path)
    assert result['verdict']=='uncertain' and result['issues']
    assert all(c['verdict']=='pass' for c in result['coverage'])
    assert result['issues'][0]['recommendation']=='核對表演。'


def test_cross_missing_duplicate_and_fabricated_evidence_rejected(plan):
    p=many(plan);inp=input_for(p);task=next(t for t in dp.prepare(inp['provider_config'],inp['prompt'],p) if t['capability']=='directing_cross_qc')
    rv=response(task,p)
    for change in ('missing','duplicate','evidence','verdict'):
        bad=copy.deepcopy(rv)
        if change=='missing':bad['checks']=[]
        if change=='duplicate':bad['checks']*=2
        if change=='evidence':bad['checks'][0]['evidence']='FABRICATED_SOURCE'
        if change=='verdict':bad['checks'][0]['verdict']='uncertain'
        with pytest.raises(ValueError):dp.validate(task,bad,p)


def test_cross_renamed_check_id_names_expected_and_actual(plan):
    """A model that answers the right check under a descriptive name must be told which id was
    required, otherwise the single structural repair cannot correct it (real case 338b3c2415ca4454:
    'global' answered as 'global_reveal_order', repaired into the same name, job failed)."""
    p=many(plan);inp=input_for(p);task=next(t for t in dp.prepare(inp['provider_config'],inp['prompt'],p) if t['capability']=='directing_cross_qc')
    assert task['keys']==['global'], task['keys']
    renamed=copy.deepcopy(response(task,p))
    renamed['checks'][0]['id']='global_reveal_order'
    with pytest.raises(ValueError) as exc:
        dp.validate(task,renamed,p)
    message=str(exc.value)
    assert '"global"' in message and 'global_reveal_order' in message, message
    # The verbatim id is accepted, so the contract is a naming rule and not a content block.
    assert dp.validate(task,response(task,p),p)['checks'][0]['id']=='global'


def test_cross_check_order_must_match_requested_checks(plan):
    """Order carries the coverage mapping, so a reordered batch is rejected with both lists shown."""
    p=many(plan);inp=input_for(p)
    base=next(t for t in dp.prepare(inp['provider_config'],inp['prompt'],p) if t['capability']=='directing_cross_qc')
    task=copy.deepcopy(base); task['keys']=['global','cut-0']
    good={'verdict':'pass','summary':'兩項核對。','issues':[],
          'checks':[{'id':k,'verdict':'pass','evidence':p['screenplay'],'reason':'核對原文及實際剪接。','recommendation':'核對表演。'} for k in task['keys']]}
    assert [c['id'] for c in dp.validate(task,good,p)['checks']]==['global','cut-0']
    reordered=copy.deepcopy(good); reordered['checks']=list(reversed(reordered['checks']))
    with pytest.raises(ValueError) as exc:
        dp.validate(task,reordered,p)
    # The message uses the pipeline's own compact encoding, so assert against it directly.
    assert dp.encode(task['keys']) in str(exc.value)
    assert 'cut-0' in str(exc.value) and '"global"' in str(exc.value)


def test_cancel_and_oversize_stop_before_calls(plan,tmp_path,monkeypatch):
    p=many(plan);inp=input_for(p);calls=[];fake_runner(monkeypatch,inp,calls)
    (tmp_path/'cancel-requested').touch()
    with pytest.raises(RuntimeError,match='取消'):dp.run({'input':inp},tmp_path)
    assert not calls
    p['screenplay']='不可刪除原文'*10000
    with pytest.raises(ValueError,match='最小必要'):dp.prepare(inp['provider_config'],input_for(p)['prompt'],p)
    assert not calls


def test_small_review_preserves_full_prompt(plan):
    p=directed(plan);inp=input_for(p,131072,32768)
    tasks=dp.prepare(inp['provider_config'],inp['prompt'],p)
    assert len(tasks)==1 and tasks[0]['prompt']==inp['prompt'] and tasks[0]['scope']==p


def test_api_resume_frozen_provider_and_reject_stale(client,plan,monkeypatch):
    p,proposal=proposal_job(client,many(plan))
    client.post('/api/settings/routing',json={'capability':'directing_qc','provider_id':'astra'})
    job=client.post('/api/projects/'+p['id']+'/jobs',json={'capability':'directing_qc','target_id':proposal['id']}).json()['job']
    assert job['input']['directing_pipeline']==dp.VERSION
    with store.db() as c:c.execute('UPDATE jobs SET state="failed" WHERE id=?',(job['id'],))
    r=client.get('/api/jobs/'+proposal['id']).json()['directing_review'];assert r['resumable']
    original=store.job(job['id'])['input']
    client.post('/api/settings/routing',json={'capability':'directing_qc','provider_id':'deepseek'})
    assert client.post('/api/jobs/'+job['id']+'/resume').status_code==200
    assert store.job(job['id'])['input']==original
    with store.db() as c:
        c.execute('UPDATE jobs SET state="failed" WHERE id=?',(job['id'],))
        c.execute('UPDATE projects SET revision=revision+1 WHERE id=?',(p['id'],))
    assert client.post('/api/jobs/'+job['id']+'/resume').status_code==400


def test_resumable_flag_agrees_with_the_resume_endpoint(client,plan,monkeypatch):
    """The view must never offer 接續 for a job the endpoint refuses. A project revision bump
    blocks a resume even when the review source is unchanged, but the flag restated the gate
    without the revision check, so it showed a working button that could only return HTTP 400
    (real case 338b3c2415ca4454)."""
    p,proposal=proposal_job(client,many(plan))
    client.post('/api/settings/routing',json={'capability':'directing_qc','provider_id':'astra'})
    job=client.post('/api/projects/'+p['id']+'/jobs',json={'capability':'directing_qc','target_id':proposal['id']}).json()['job']
    with store.db() as c:
        c.execute('UPDATE jobs SET state="failed" WHERE id=?',(job['id'],))
        c.execute('UPDATE projects SET revision=revision+1 WHERE id=?',(p['id'],))
    review=client.get('/api/jobs/'+proposal['id']).json()['directing_review']
    # The same job is still the current review for this source, and it is still failed.
    assert review['job_id']==job['id'] and review['state']=='failed'
    assert client.post('/api/jobs/'+job['id']+'/resume').status_code==400
    assert review['resumable'] is False


def test_valid_raw_result_recovered_without_repeating_provider(plan,tmp_path,monkeypatch):
    p=directed(plan);inp=input_for(p,131072,32768);job={'id':'j','input':inp};calls=[]
    tasks=fake_runner(monkeypatch,inp,calls)
    result=dp.run(job,tmp_path)
    checkpoint=next(tmp_path.glob('*checkpoint.json'))
    raw=next(tmp_path.glob('*attempt-*'))/'result.json';raw.write_text(json.dumps(json.loads(checkpoint.read_text())['result']))
    checkpoint.unlink();calls.clear()
    assert dp.run(job,tmp_path)==result and not calls
    checkpoint=next(tmp_path.glob('*checkpoint.json'));checkpoint.unlink()
    (raw.parent/'transport.json').write_text(json.dumps({'finish_reason':'length'}))
    assert dp.run(job,tmp_path)==result and len(calls)==1


def test_cancel_during_call_never_saves_or_repairs(plan,tmp_path,monkeypatch):
    p=directed(plan);inp=input_for(p,131072,32768)
    calls=[]
    def run(*args):
        calls.append(1);(tmp_path/'cancel-requested').touch()
        return {'verdict':'pass','summary':'bad','coverage':[],'issues':[]}
    monkeypatch.setattr(providers,'run',run)
    with pytest.raises(RuntimeError,match='取消'):dp.run({'input':inp},tmp_path)
    assert calls==[1] and not list(tmp_path.glob('*checkpoint.json')) and not (tmp_path/'result.json').exists()


def test_single_structural_repair_preserves_nonpass(plan,tmp_path,monkeypatch):
    p=directed(plan);inp=input_for(p,131072,32768);calls=[]
    def run(provider,cap,prompt,images,work):
        calls.append(prompt)
        rv=reviewed(p,'revise')
        if len(calls)==1:rv['coverage'][0]['evidence']='WRONG QUOTE'
        else:assert 'ONE STRUCTURAL CORRECTION' in prompt
        return rv
    monkeypatch.setattr(providers,'run',run)
    result=dp.run({'input':inp},tmp_path)
    assert result['verdict']=='revise' and len(calls)==2



def test_multiline_verbatim_evidence_is_source_text_not_json_escaping(plan):
    from studio.directing_models import has_evidence
    original='他說：「保留原文。」\n下一行是完整句子。'
    assert has_evidence({'screenplay':original},original)
    assert not has_evidence({'first':'他說：「保留原文。」','second':'下一行是完整句子。'},original)
    assert not has_evidence({'screenplay':original},'他說：保留原文。')


def test_output_risk_stages_when_answer_exceeds_half_budget(plan):
    # DeepSeek-like budget: a 1,048,576 window almost always fits any input, so the old
    # overflow trigger never fired; only the output-risk estimate can engage staging here.
    p=directed(plan)
    for n in range(2,15):
        p['edit_plan'].append({**p['edit_plan'][0],'id':'extra'+str(n),'planned_edit_in':0.2*n,'planned_edit_out':0.4*n})
    inp=input_for(p,1048576,32768,'deepseek')
    # The input genuinely fits: only the required answer is at risk.
    assert context_limits.fits(context_limits.count(inp['provider_config'],inp['prompt'],dp.schema(inp['provider_config'],'directing_qc'),inp['provider_config']['context_policy']),inp['provider_config']['context_policy'])
    assert dp.answer_items(p)==15 and (dp.answer_items(p)+1)*dp.OUTPUT_ANSWER_LINE_UNITS>32768//dp.OUTPUT_BUDGET_SHARE
    assert dp.needs_stages(inp['provider_config'],inp['prompt'],p)
    tasks=dp.prepare(inp['provider_config'],inp['prompt'],p)
    # One call would have to report on 15 answer items; the bounded path splits it instead
    # of collapsing back to monolithic just because the input window is huge.
    assert len(tasks)>1
    assert sum(1 for t in tasks if t['capability']=='directing_qc' for _ in t['keys'])==1
    assert all(t['fits'] for t in tasks)
    cross=[t for t in tasks if t['capability']=='directing_cross_qc']
    assert sorted(k for t in cross for k in t['keys'])==sorted(['global']+['cut-'+str(n) for n in range(14)])


def test_output_risk_does_not_collapse_back_to_monolithic(plan):
    # Regression for the real gap: the trigger alone was not enough while prepare() still
    # returned one task whenever keys<=beat_limit and the (huge) input window fit.
    p=directed(plan)
    for n in range(2,15):
        p['edit_plan'].append({**p['edit_plan'][0],'id':'extra'+str(n),'planned_edit_in':0.2*n,'planned_edit_out':0.4*n})
    inp=input_for(p,1048576,32768,'deepseek')
    keys=sum(len((s.get('director_plan') or {}).get('beats',[])) for s in p['scenes'])
    assert keys<=max(1,min(4,32768//3000)), 'the beat rule alone would not stage this plan'
    assert dp.output_risk(inp['provider_config'],p)
    assert len(dp.prepare(inp['provider_config'],inp['prompt'],p))>1


def test_small_review_keeps_monolithic_on_large_window(plan):
    # 1 beat + 1 edit: (2+1)*3000 = 9000 units, well under 32768//2 = 16384.
    p=directed(plan);inp=input_for(p,1048576,32768,'deepseek')
    assert not dp.needs_stages(inp['provider_config'],inp['prompt'],p)
    tasks=dp.prepare(inp['provider_config'],inp['prompt'],p)
    assert len(tasks)==1 and tasks[0]['prompt']==inp['prompt'] and tasks[0]['scope']==p


def test_output_risk_stages_one_beat_review_with_many_edit_uses(plan):
    # The case the old beat rule missed: 1-4 beats but a large required answer.
    p=directed(plan)
    for n in range(2,15):
        p['edit_plan'].append({**p['edit_plan'][0],'id':'extra'+str(n),'planned_edit_in':0.2*n,'planned_edit_out':0.4*n})
    inp=input_for(p,1048576,32768,'deepseek')
    assert dp.needs_stages(inp['provider_config'],inp['prompt'],p)
    tasks=dp.prepare(inp['provider_config'],inp['prompt'],p)
    assert len(tasks)>1
    assert sum(1 for t in tasks if t['capability']=='directing_qc' for _ in t['keys'])==1


def test_staged_list_complete_and_unfit_stage_fails(plan):
    p=directed(plan)
    for n in range(2,15):
        p['edit_plan'].append({**p['edit_plan'][0],'id':'extra'+str(n),'planned_edit_in':0.2*n,'planned_edit_out':0.4*n})
    inp=input_for(p,1048576,32768,'deepseek')
    tasks=dp.prepare(inp['provider_config'],inp['prompt'],p)
    assert sorted(k for t in tasks if t['capability']=='directing_cross_qc' for k in t['keys'])==sorted(['global']+['cut-'+str(n) for n in range(14)])
    assert sum(1 for t in tasks if t['capability']=='directing_qc' for _ in t['keys'])==1
    # One required stage whose exact request no longer fits must fail the whole plan.
    # A 1,048,576-byte window still fits a 420 KB screenplay, so the window must be small
    # enough that the smallest atomic review unit genuinely cannot fit.
    broken=copy.deepcopy(p);broken['screenplay']='超出預算的原文'*20000
    with pytest.raises(ValueError,match='最小必要'):
        small=input_for(broken,16000,3000,'deepseek')
        dp.prepare(small['provider_config'],small['prompt'],broken)


def test_beat_and_llamacpp_triggers_still_stage(plan):
    p=many(plan);inp=input_for(p)
    assert dp.needs_stages(inp['provider_config'],inp['prompt'],p)
    llama=copy.deepcopy(inp);llama['provider_config']['context_policy']['tokenizer']='llama_cpp'
    small=directed(plan);small_inp=input_for(small,1048576,32768)
    small_llama=copy.deepcopy(small_inp);small_llama['provider_config']['context_policy']['tokenizer']='llama_cpp'
    assert dp.needs_stages(small_llama['provider_config'],small_llama['prompt'],small)
    assert not dp.needs_stages(small_inp['provider_config'],small_inp['prompt'],small)


def test_staging_is_deterministic_for_same_inputs(plan):
    p=directed(plan)
    for n in range(2,15):
        p['edit_plan'].append({**p['edit_plan'][0],'id':'extra'+str(n),'planned_edit_in':0.2*n,'planned_edit_out':0.4*n})
    inp=input_for(p,1048576,32768,'deepseek')
    first=dp.prepare(inp['provider_config'],inp['prompt'],p)
    second=dp.prepare(inp['provider_config'],inp['prompt'],p)
    assert first==second
    assert store.digest([dp.VERSION,inp['provider_config'],inp['prompt'],first])==store.digest([dp.VERSION,inp['provider_config'],inp['prompt'],second])
