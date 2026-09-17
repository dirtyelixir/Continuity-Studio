"""Integration evidence: durable planning, semantic review gates, edit/source separation."""
import copy
import io
import json
import zipfile
import pytest
from studio import directing,engine,models,store,providers,serial_story,continuity,image_prompts
from test_production import client,plan,create,add_asset


def directed(plan):
    p=copy.deepcopy(plan)
    for scene in p['scenes']:
        scene['director_plan']={'beats':[{'id':'B01','event':scene['summary'],'intent':{
            'audience_knowledge_before':'燈未亮。','audience_must_learn':'Ada 成功開燈。',
            'emotional_target':'期待轉成驚喜。','visual_priority':'Ada 的表情及燈光變化。',
            'reveal_strategy':'按下開關後才亮起。','coverage_strategy':'在可讀的中景保留表演及燈光變化。'}}], 'reveal_order':['B01']}
    p['edit_plan']=[]
    for s in p['shots']:
        s.update(generation_duration=s['duration'],shot_purpose='讓觀眾明白 Ada 成功開燈。',direction={
            'beat_ids':['B01'],'subject_ids':[s['entity_ids'][0]],'visual_carrier':'人物表情和房間燈光。',
            'readability':'中景臉部及燈光變化可見，保留一秒反應。',
            'cut_in_reason':'開始按開關。','cut_out_reason':'觀眾看到亮燈及反應。','next_shot_relationship':'本場完成。'})
        p['edit_plan'].append({'id':'E_'+s['id'],'shot_id':s['id'],'planned_edit_in':0,'planned_edit_out':s['duration'],
            'cut_in_reason':'動作起點。','cut_out_reason':'反應完成。','continuity_note':'使用完整表演；出點等於來源終點。'})
    return models.Production.model_validate(p).model_dump()


def reviewed(p,verdict='pass'):
    return {'verdict':verdict,'summary':'逐節拍檢查可讀的視覺承載及揭示次序。',
        'coverage':[{'scene_id':sc['id'],'beat_id':b['id'],
                     'shot_ids':[s['id'] for s in p['shots'] if s['scene_id']==sc['id'] and b['id'] in s['direction']['beat_ids']],
                     'verdict':verdict,'required_communication':b['intent']['audience_must_learn'],
                     'evidence':b['event'],'reason':'畫面可傳達指定變化。' if verdict=='pass' else '表情承載不足。',
                     'recommendation':'按方案拍攝並驗證實際畫面。' if verdict=='pass' else '收緊景別或改變調度。'}
                    for sc in p['scenes'] for b in sc['director_plan']['beats']], 'issues':[]}


def proposal_job(client,plan):
    p=client.post('/api/projects',json={'title':'Director test','idea':'A keeper fixes a lamp.'}).json()
    for cap in ('narrative','directing_qc'):
        client.post('/api/settings/routing',json={'capability':cap,'provider_id':'manual'})
    j=client.post('/api/projects/'+p['id']+'/jobs',json={'capability':'narrative'}).json()['job']
    r=client.post('/api/jobs/'+j['id']+'/manual',json=plan)
    assert r.status_code==200,r.text
    return p,r.json()


def check_proposal(client,p,j,result):
    r=client.post('/api/projects/'+p['id']+'/jobs',json={'capability':'directing_qc','target_id':j['id']})
    assert r.status_code==200,r.text
    q=r.json()['job']
    r=client.post('/api/jobs/'+q['id']+'/manual',json=result)
    assert r.status_code==200,r.text
    return q


def test_new_manual_proposal_requires_formal_directing(client,plan):
    p=client.post('/api/projects',json={'title':'Legacy candidate','idea':'A keeper fixes a lamp.'}).json()
    client.post('/api/settings/routing',json={'capability':'narrative','provider_id':'manual'})
    j=client.post('/api/projects/'+p['id']+'/jobs',json={'capability':'narrative'}).json()['job']
    r=client.post('/api/jobs/'+j['id']+'/manual',json=plan)
    assert r.status_code==400 and store.project(p['id'])['production'] is None


def test_review_adoption_stale_edit_and_export(client,plan):
    d=directed(plan);p,j=proposal_job(client,d)
    assert client.post('/api/jobs/'+j['id']+'/adopt',json={'revision':0}).status_code==400
    check_proposal(client,p,j,reviewed(d))
    assert client.post('/api/jobs/'+j['id']+'/adopt',json={'revision':0}).status_code==200
    current=store.project(p['id'])
    assert directing.state(current)['scenes'][0]['status']=='pass'
    directing.require_scope(current,'start')
    # One generation, two independent uses, including a 1.6-second reaction.
    changed=copy.deepcopy(current['production'])
    changed['edit_plan'].append({**changed['edit_plan'][0],'id':'reaction','planned_edit_in':1.8,'planned_edit_out':3.4})
    engine.save_plan(p['id'],changed,1,'Edit reuse')
    current=store.project(p['id'])
    assert current['production']['shots']==d['shots']
    assert directing.state(current)['scenes'][0]['status']=='unreviewed'
    with pytest.raises(ValueError,match='審查'):directing.require_scope(current,'start')
    assert directing.edit_rows(changed)[1]['planned_screen_duration']==1.6
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+p['id']+'/export').content)) as z:
        assert {'director/plan.json','director/review.json','director/plan.md','edit/plan.json'}<=set(z.namelist())
        assert json.loads(z.read('edit/plan.json'))[1]['shot_id']=='shot'


def test_overloaded_review_blocks_adoption_and_can_revise_candidate(client,plan):
    d=directed(plan);p,j=proposal_job(client,d)
    result=reviewed(d,'revise');result['issues']=[{'code':'SHOT_OVERLOADED','shot_ids':['shot'],'beat_ids':['B01'],
        'evidence':'Press switch','reason':'此測試審查指出兩個競爭目的。','recommendation':'拆分成有獨立目的的鏡頭。'}]
    check_proposal(client,p,j,result)
    r=client.post('/api/jobs/'+j['id']+'/adopt',json={'revision':0});assert r.status_code==400
    revised=client.post('/api/projects/'+p['id']+'/jobs',json={'capability':'narrative','proposal_id':j['id'],'feedback':'先保留反應。'})
    assert revised.status_code==200,revised.text
    prompt=store.job(revised.json()['job']['id'])['input']['prompt']
    assert 'CANDIDATE TO REVISE' in prompt and d['shots'][0]['shot_purpose'] in prompt


def test_fabricated_review_evidence_rejected(client,plan):
    d=directed(plan);p,j=proposal_job(client,d)
    q=client.post('/api/projects/'+p['id']+'/jobs',json={'capability':'directing_qc','target_id':j['id']}).json()['job']
    bad=reviewed(d);bad['coverage'][0]['evidence']='NOT PRESENT IN THE FROZEN PLAN'
    assert client.post('/api/jobs/'+q['id']+'/manual',json=bad).status_code==400


def test_legacy_no_fabricated_planning_and_frame_hash_preserved(client,plan):
    pid=create(client,plan);p=store.project(pid)
    assert directing.state(p)['scenes'][0]['status']=='legacy'
    assert directing.edit_rows(p['production'])==[]
    directing.require_scope(p,'start')
    assert image_prompts.source(plan,'start').get('director_boundary') is None
    historical=copy.deepcopy(plan)
    historical['scenes'][0].pop('director_plan',None)
    for k in ('direction','shot_purpose','generation_duration'):historical['shots'][0].pop(k,None)
    assert continuity.target_hash(historical,'start')==continuity.target_hash(plan,'start')


def test_source_and_keyframe_carry_adopted_purpose(client,plan):
    d=directed(plan)
    basis=image_prompts.source(d,'start')
    assert basis['director_boundary']['shot_purpose']==d['shots'][0]['shot_purpose']
    from studio import prompt_preparation
    source=prompt_preparation.source(d,'scene')
    assert source['shots'][0]['direction']['visual_carrier']==d['shots'][0]['direction']['visual_carrier']


def test_chapter_namespace_keeps_edit_source_links(client,plan):
    p=client.post('/api/projects',json={'title':'Series','idea':'A continuing story.','source_kind':'outline'}).json()
    ch=serial_story.save_draft(p['id'],models.ChapterDraft(title='One',brief='A keeper fixes a lamp.'))
    frozen=serial_story.snapshot(store.project(p['id']),ch)
    d=directed(plan);merged=serial_story.merge(store.project(p['id']),d,frozen)
    assert merged['edit_plan'][0]['shot_id']==ch['id']+'__shot'
    assert merged['scenes'][0]['director_plan']==d['scenes'][0]['director_plan']
    assert merged['shots'][0]['direction']['beat_ids']==['B01']
    engine.save_plan(p['id'],merged,0,'chapter')
    ch2=serial_story.save_draft(p['id'],models.ChapterDraft(title='Two',brief='Another keeper story.'))
    frozen2=serial_story.snapshot(store.project(p['id']),ch2)
    both=serial_story.merge(store.project(p['id']),d,frozen2)
    assert [e['shot_id'] for e in both['edit_plan']]==[ch['id']+'__shot',ch2['id']+'__shot']


def test_automatic_proposal_schedules_independent_qc(client,plan,monkeypatch):
    d=directed(plan);p,j=proposal_job(client,d)
    j['input']['provider_config']={**providers.DEFAULT}
    scheduled=[]
    monkeypatch.setattr(engine,'enqueue',lambda pid,req:scheduled.append((pid,req)))
    engine.finish(j,d)
    assert len(scheduled)==1 and scheduled[0][1].capability=='directing_qc'
    assert scheduled[0][1].target_id==j['id']


def test_review_correction_is_bounded_preserves_verdict_and_original(plan,tmp_path,monkeypatch):
    d=directed(plan);bad=reviewed(d,'revise');bad['coverage'][0]['evidence']='Joined: '+bad['coverage'][0]['evidence']
    original=json.dumps(bad,ensure_ascii=False);(tmp_path/'result.json').write_text(original)
    calls=[]
    def correction(provider,cap,prompt,images,work):
        calls.append(work);assert cap=='directing_qc' and not images
        fixed=reviewed(d,'revise');work.mkdir();(work/'result.json').write_text(json.dumps(fixed))
        return fixed
    monkeypatch.setattr(providers,'run',correction)
    assert directing.run_review(providers.DEFAULT,'frozen',tmp_path,d)['verdict']=='revise'
    assert (tmp_path/'result.json').read_text()==original
    assert directing.run_review(providers.DEFAULT,'frozen',tmp_path,d)['verdict']=='revise'
    assert len(calls)==1
    (tmp_path/'repair-1'/'result.json').write_text(original)
    with pytest.raises(ValueError):directing.run_review(providers.DEFAULT,'frozen',tmp_path,d)
    assert len(calls)==1


def test_edit_manifest_reuses_only_selected_current_source(plan):
    d=directed(plan);d['edit_plan'].append({**d['edit_plan'][0],'id':'again'})
    p={'production':d,'video_renders':{'takes':[{'id':'take','shot_id':'shot','selected':True,'current':True,'state':'succeeded'}]}}
    rows=directing.edit_manifest(p)
    assert all(r['source_video']['take_id']=='take' and r['source_video']['path']=='video/take.mp4' for r in rows)
    assert rows[0]['source_video']['source_in']==rows[1]['source_video']['source_in']
    assert rows[1]['source_video']['timeline_in']==rows[0]['source_video']['timeline_out']
    p['video_renders']['takes'][0]['current']=False
    assert directing.edit_manifest(p)[0]['source_video'] is None


def test_cross_scene_edit_order_and_source_rewrite_invalidate_review_basis(plan):
    d=directed(plan);sc=copy.deepcopy(d['scenes'][0]);sc['id']='other';d['scenes'].append(sc)
    s=copy.deepcopy(d['shots'][0]);s.update(id='second',scene_id='other')
    for f in s['keyframes']:f['id']='other_'+f['id']
    d['shots'].append(s);d['edit_plan'].append({**d['edit_plan'][0],'id':'other_edit','shot_id':'second'})
    before=directing.scene_source(d,'scene')
    d['edit_plan'].reverse()
    assert directing.scene_source(d,'scene')!=before
    before=directing.scene_source(d,'scene');d['screenplay']+=' A different reveal.'
    assert directing.scene_source(d,'scene')!=before


def test_director_gate_before_h3_and_image_preparation(client,plan):
    d=directed(plan);pid=create(client,d)
    for target in ('ada','room'):add_asset(pid,d,target)
    for cap,target in [('h3','shot'),('image_prepare','start')]:
        with pytest.raises(ValueError,match='審查'):
            engine.build_input(store.project(pid),models.JobRequest(capability=cap,target_id=target))
    directing.record_review(pid,d,reviewed(d),'manual-test')
    inp,_=engine.build_input(store.project(pid),models.JobRequest(capability='h3',target_id='shot'))
    assert d['shots'][0]['shot_purpose'] in inp['prompt']
