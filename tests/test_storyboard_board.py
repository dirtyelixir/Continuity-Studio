"""Isolated contract/API fixtures; colored fixture images are not media acceptance."""
import copy
import io
import zipfile
from unittest.mock import patch
import pytest
from studio import storyboard_board as board,models,store,engine,continuity,h3,image_prompts,generation_groups as groups,directing,video_render
from test_production import client,plan,create,add_asset
from test_generation_groups import montage,definition,save,GID


def proposed(p,sid='scene',extra=False):
    src=board.source(p,sid);shots={s['id']:s for s in src['shots']};panels=[]
    for edit in src['edits']:
        shot=shots[edit['shot_id']];times=[edit['planned_edit_in']]
        if extra and edit==src['edits'][0]:times.append(2)
        anchors=[]
        for time in times:
            f=board.frame_at(shot,time)
            anchors.append({'time':time,'reuse_frame_id':f['id'] if f else '', 'description':f['description'] if f else 'Ada looks at the switch at this exact instant.',
                'state':shot['start_state'] if time==0 else shot['end_state'] if time==shot['duration'] else f['state'] if f else [{'entity_id':'ada','key':'hand','value':'reaching for switch'}], 'purpose':'Let the viewer read this state.'})
        panels.append({'edit_id':edit['id'],'reason':'Make the reveal legible.','anchors':anchors})
    return {'scene_id':sid,'summary':'Read the switch then its effect.','panels':panels}


def legacy_job(client,pid):
    # Exercise recovery/adoption of requests frozen before the image-demand contract.
    with patch.object(board, "planning_source", board.source):
        return client.post(f'/api/projects/{pid}/jobs',json={'capability':'storyboard_frames','target_id':'scene'})


def adopt(client,pid,result=None):
    p=store.project(pid);result=result or proposed(p)
    response=legacy_job(client,pid)
    assert response.status_code==200,response.text
    job=response.json()['job'];engine.finish(store.job(job['id']),result)
    response=client.post(f'/api/projects/{pid}/storyboard/adopt/{job["id"]}',json={'revision':board.config(pid)['revision'],'production_revision':p['revision']})
    assert response.status_code==200,response.text
    return response.json()


def approve_all(client,pid):
    p=store.project(pid);r=board.scene_state(p,'scene')
    for target in {a['frame_id'] for panel in r['panels'] for a in panel['anchors']}:
        if not continuity.approved_for(p['production'],store.assets(pid),target):add_asset(pid,p['production'],target,status='pending')
    for panel in board.scene_state(p,'scene')['panels']:
        for a in panel['anchors']:
            response=client.post(f'/api/projects/{pid}/storyboard/scene/review/{a["id"]}',json={'revision':board.config(pid)['revision'],'token':a['token'],'asset_id':a['asset']['id'],'verdict':'approved','note':'The frame communicates the intended state.'})
            assert response.status_code==200,response.text
    assert board.scene_state(p,'scene')['ready']


def test_intermediate_contract_and_legacy_hash(plan):
    old=copy.deepcopy(plan);hashes=[continuity.target_hash(old,f['id']) for f in old['shots'][0]['keyframes']]
    frame={'id':'middle','moment':'key','description':'Hand halfway up','source_time':2,'state':[{'entity_id':'ada','key':'hand','value':'halfway'}]}
    plan['shots'][0]['keyframes'].append(frame);plan=models.Production.model_validate(plan).model_dump()
    assert [continuity.target_hash(plan,f['id']) for f in plan['shots'][0]['keyframes'][:2]]==hashes
    assert directing.review_hash(plan)==directing.review_hash(old)
    assert directing.scene_source(plan,'scene')==directing.scene_source(old,'scene')
    assert plan['shots'][0]['keyframes'][0]==old['shots'][0]['keyframes'][0]
    assert image_prompts.source(plan,'middle')['visual_context']['moment_state']==frame['state']
    assert '2.0 seconds' in continuity.image_task(plan,'middle')
    for change in [{'source_time':0},{'source_time':6},{'source_time':float('nan')},{'state':None},{'moment':'end'},{'state':[{'entity_id':'missing','key':'x','value':'y'}]}]:
        bad=copy.deepcopy(plan);bad['shots'][0]['keyframes'][-1].update(change)
        with pytest.raises(ValueError):models.Production.model_validate(bad)
    bad=copy.deepcopy(plan);bad['shots'][0]['keyframes'].append({**frame,'id':'duplicate'})
    with pytest.raises(ValueError):models.Production.model_validate(bad)


def test_adopt_preserves_sources_assets_and_methods(client,montage):
    pid=create(client,montage);start=add_asset(pid,montage,'start');result=proposed(store.project(pid),extra=True)
    cfg=adopt(client,pid,result);after=store.project(pid)['production']
    for before,s in zip(montage['shots'],after['shots']):
        assert {k:v for k,v in before.items() if k!='keyframes'}=={k:v for k,v in s.items() if k!='keyframes'}
        assert s['keyframes'][:2]==before['keyframes']
    assert after['edit_plan']==montage['edit_plan'] and after['canon']==montage['canon']
    assert next(a for a in store.assets(pid) if a['id']==start)['status']=='approved'
    assert not board.scene_state(store.project(pid),'scene')['stale']
    assert len(cfg['scenes']['scene']['panels'])==2
    job=next(j for j in store.jobs(pid) if j['capability']=='storyboard_frames')
    files=job['input']['production_method']['instruction_files']
    assert 'references/visual-skills/dramaturgy.md' in files and 'references/storyboard.md' in files
    assert len(after['shots'][0]['keyframes'])==3 and len(after['shots'][1]['keyframes'])==3
    # Legacy H3 still only uses source endpoints, never the intermediate anchor.
    for target in [f['id'] for s in after['shots'] for f in s['keyframes']]:add_asset(pid,after,target)
    refs=h3.compile_shot(after,after['shots'][0],store.assets(pid))['references']
    assert [r['moment'] for r in refs]==['start','end']


@pytest.mark.parametrize('change',['order','missing','time','reuse','state','description','duplicate'])
def test_reject_invalid_board(montage,change):
    p={'production':montage};result=proposed(p);src=board.source(p,'scene')
    if change=='order':result['panels'].reverse()
    if change=='missing':result['panels'].pop()
    if change=='time':result['panels'][0]['anchors'][0]['time']=0.5
    if change=='reuse':result['panels'][1]['anchors'][0]['reuse_frame_id']='start'
    if change=='state':result['panels'][0]['anchors'][0]['state']=[]
    if change=='description':result['panels'][0]['anchors'][0]['description']='Changed opening'
    if change=='duplicate':result['panels'][0]['anchors']*=2
    with pytest.raises(ValueError):board.validate(result,src)


def test_plan_staleness_and_cross_project_adoption(client,montage):
    pid=create(client,montage);p=store.project(pid);data=engine.build_input(p,models.JobRequest(capability='storyboard_frames',target_id='scene'))
    r=legacy_job(client,pid).json()['job'];engine.finish(store.job(r['id']),proposed(p))
    other=create(client,montage)
    body={'revision':0,'production_revision':1}
    assert client.post(f'/api/projects/{other}/storyboard/adopt/{r["id"]}',json=body).status_code==400
    updated=copy.deepcopy(montage);updated['shots'][0]['expression']='Uneasy';engine.save_plan(pid,updated,1,'Change acting')
    body['production_revision']=2
    assert client.post(f'/api/projects/{pid}/storyboard/adopt/{r["id"]}',json=body).status_code==400
    assert not board.config(pid)['scenes']


def test_image_bound_reviews_and_edit_context(client,montage):
    pid=create(client,montage);adopt(client,pid);p=store.project(pid)
    with pytest.raises(ValueError,match='逐格'):board.require_review(p,'scene')
    approve_all(client,pid);a=board.scene_state(p,'scene')['panels'][0]['anchors'][0];old=a['asset']['id']
    new=add_asset(pid,p['production'],a['frame_id'],status='pending')
    engine.decide_asset(new,'approved','Human approved replacement')
    assert not board.scene_state(p,'scene')['ready']
    r=client.post(f'/api/projects/{pid}/storyboard/scene/review/{a["id"]}',json={'revision':board.config(pid)['revision'],'token':a['token'],'asset_id':new,'verdict':'approved'})
    assert r.status_code==400
    approve_all(client,pid)
    path=store.DATA/next(x for x in store.assets(pid) if x['id']==new)['path'];path.write_bytes(path.read_bytes()+b'changed bytes')
    assert not board.scene_state(p,'scene')['ready']
    # Old approvals are kept as evidence, never silently reused for different bytes.
    assert board.config(pid)['scenes']['scene']['reviews']
    changed=copy.deepcopy(p['production']);changed['edit_plan'][0]['cut_out_reason']='A new comparison'
    engine.save_plan(pid,changed,p['revision'],'Change edit context')
    assert board.scene_state(store.project(pid),'scene')['stale']


def test_review_revision_and_record_revise_without_deletion(client,plan):
    pid=create(client,plan);adopt(client,pid);approve_all(client,pid);p=store.project(pid);a=board.scene_state(p,'scene')['panels'][0]['anchors'][0]
    body={'revision':board.config(pid)['revision']-1,'token':a['token'],'asset_id':a['asset']['id'],'verdict':'revise','note':'Eyeline is wrong'}
    url=f'/api/projects/{pid}/storyboard/scene/review/{a["id"]}'
    assert client.post(url,json=body).status_code==400
    body['revision']+=1;assert client.post(url,json=body).status_code==200
    assert not board.scene_state(p,'scene')['ready']
    assert (store.DATA/a['asset']['path']).is_file() and any(x['id']==a['asset']['id'] for x in store.assets(pid))


def test_trimmed_group_uses_reviewed_interior_frame(client,montage):
    montage['edit_plan'][0]['planned_edit_in']=1
    pid=create(client,montage);adopt(client,pid);save(client,pid)
    with pytest.raises(ValueError,match='圖板'):groups.prompt_source(store.project(pid),GID)
    approve_all(client,pid);p=store.project(pid);src=groups.prompt_source(p,GID)
    anchor=board.scene_state(p,'scene')['panels'][0]['anchors'][0]
    assert src['references'][0]['target_id']==anchor['frame_id'] and anchor['frame']['moment']=='key'
    assert src['references'][0]['moment']=='start' and src['duration']==5
    assert src['storyboard_review'][0]['anchors'][0]['asset_id']==anchor['asset']['id']
    planning=groups.planning_source(p,'scene')
    result={'summary':'Native group','groups':[{'title':'Read and react','edit_ids':['view1','view2'],'execution':'native_montage','mode':'I2VA','reference_targets':[],'reason':'Coherent views','checks':['Check cuts']} ]}
    result['groups'][0]['frame_uses']=[{'anchor_id':a['anchor_id'],'use':'image_conditioning' if i==0 else 'planning_only',
        'reason':'Use the exact trimmed opening.' if i==0 else 'Review this native cut in footage.',
        'boundary_exception':'' if i==0 else 'This deliberately chosen native cut relies on the prompt; its opening image will not be supplied.'}
        for i,a in enumerate(planning['storyboard_intent'])]
    groups.validate_plan(result,planning)
    planning['storyboard_reviewed_frames']=[]
    assert groups.validate_plan(result,planning)  # Pixel review is checked by prompt_source/freeze, not planning.


@pytest.mark.parametrize('mode', ['I2VA', 'FL2VA'])
@pytest.mark.parametrize('stale', [False, True])
def test_project_read_reports_board_gate_without_blocking_workspace(client,montage,mode,stale):
    from studio import video_workflow
    pid=create(client,montage)
    adopt(client,pid)
    assert save(client,pid).status_code==200
    p=store.project(pid)
    # Approved source images do not imply human review of their board panels.
    for shot in p['production']['shots']:
        for frame in shot['keyframes']:
            add_asset(pid,p['production'],frame['id'])
    cfg=video_workflow.config(pid)
    cfg['shots']['shot']={'mode':mode}
    store.put_setting('video-workflow:'+pid,cfg)
    if stale:
        changed=copy.deepcopy(p['production'])
        changed['edit_plan'][0]['cut_out_reason']='Changed editorial intent'
        engine.save_plan(pid,changed,p['revision'],'Update edit context')
        p=store.project(pid)
    response=client.get(f'/api/projects/{pid}')
    assert response.status_code==200,response.text
    data=response.json()
    assert not data['storyboard']['scenes'][0]['ready']
    assert data['storyboard']['scenes'][0]['stale']==stale
    row=next(r for r in data['video_workflow']['shots'] if r['shot_id']=='shot')
    assert not row['ready'] and row['source_hash']==''
    assert any('逐格審閱' in reason for reason in row['reasons'])
    group=next(r for r in data['generation_groups']['rows'] if r['shot_id']==GID)
    assert not group['ready'] and any('逐格審閱' in reason for reason in group['reasons'])
    # The original submission gates still reject the same unreviewed source.
    for call in (lambda: video_workflow.prompt_source(p,'shot'),
                 lambda: video_workflow.packet(p,'shot'),
                 lambda: video_render.source(p,'shot'),
                 lambda: groups.prompt_source(p,GID)):
        with pytest.raises(ValueError,match='逐格審閱'):
            call()


def test_batch_preview_dependencies_dedup_failure_and_uncertain(client,montage,monkeypatch):
    from test_scene_asset_batch import enqueue_stub
    pid=create(client,montage);adopt(client,pid);p=store.project(pid)
    r=board.preview(pid,'scene');assert r['generate_count']==0 and all(x['state']=='blocked' for x in r['items'])
    for target in ('ada','room'):add_asset(pid,p['production'],target)
    calls=enqueue_stub(monkeypatch);r=board.preview(pid,'scene');assert r['generate_count']==2
    req=board.Batch(token=r['token'],image_provider='comfy_local');first=board.submit(pid,'scene',req)
    assert len(calls)==2 and board.submit(pid,'scene',req)==first and len(calls)==2
    assert board.preview(pid,'scene')['generate_count']==0
    with pytest.raises(ValueError):board.submit(pid,'scene',board.Batch(token=r['token'],image_provider='astra'))
    with store.db() as c:c.execute("UPDATE jobs SET state='failed' WHERE capability='image'")
    def interrupt(pid,req):raise KeyboardInterrupt()
    monkeypatch.setattr(engine,'enqueue',interrupt)
    r=board.preview(pid,'scene');req=board.Batch(token=r['token'],image_provider='comfy_local')
    with pytest.raises(KeyboardInterrupt):board.submit(pid,'scene',req)
    assert board.submit(pid,'scene',req)['state']=='submitting'
    assert 'active' in [i['state'] for i in board.preview(pid,'scene')['items']]


def test_export_current_approved_board_and_no_fake_missing_images(client,montage):
    pid=create(client,montage);adopt(client,pid);p=store.project(pid)
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as z:board.export(z,p)
    with zipfile.ZipFile(buffer) as z:assert not any(n.startswith('storyboard/images/') for n in z.namelist())
    approve_all(client,pid);buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as z:board.export(z,p)
    with zipfile.ZipFile(buffer) as z:
        assert sum(n.startswith('storyboard/images/') for n in z.namelist())==2
        assert '已逐格批准' in z.read('storyboard/index.html').decode()
        assert 'user_observed' not in z.read('storyboard/manifest.json').decode()
    response=client.get(f'/api/projects/{pid}')
    assert response.status_code==200 and response.json()['storyboard']['scenes'][0]['ready']


def test_legacy_ref2_both_never_attaches_intermediate_frames(client,plan):
    from studio import delivery
    plan['shots'][0]['keyframes'].append({'id':'middle','moment':'key','description':'Hand halfway up','source_time':2,'state':[]})
    pid=create(client,plan)
    for target in ['ada','room','start','end','middle']:add_asset(pid,plan,target)
    p=store.project(pid)
    config=delivery.configuration(pid);config['scenes']={'scene':{'chapters':{'shot':{'reference_frame':'both'}}}}
    result=delivery.scene_bundle(p,p['production']['scenes'][0],config,False)
    assert [r['moment'] for r in result['references'] if r['role']=='composition']==['start','end']
    assert not any(r['target_id']=='middle' for r in result['references'])


def test_repeat_adoption_preserves_reviews_and_pending_batch_token(client,plan,monkeypatch):
    from test_scene_asset_batch import enqueue_stub
    pid=create(client,plan);cfg=adopt(client,pid);jid=cfg['scenes']['scene']['job_id'];approve_all(client,pid)
    before=board.config(pid);revision=store.project(pid)['revision']
    assert client.post(f'/api/projects/{pid}/storyboard/adopt/{jid}',json={'revision':0,'production_revision':1}).json()==before
    assert board.config(pid)==before and store.project(pid)['revision']==revision
    # A changed canonical input invalidates a batch preview before new generation.
    pid=create(client,plan);adopt(client,pid);p=store.project(pid)
    for target in ['ada','room']:add_asset(pid,p['production'],target)
    enqueue_stub(monkeypatch);preview=board.preview(pid,'scene')
    add_asset(pid,p['production'],'room')
    with pytest.raises(ValueError,match='更新'):board.submit(pid,'scene',board.Batch(token=preview['token'],image_provider='comfy_local'))


def test_full_export_includes_portable_board(client,plan):
    pid=create(client,plan);adopt(client,pid);approve_all(client,pid)
    response=client.get(f'/api/projects/{pid}/export');assert response.status_code==200,response.text if response.status_code!=200 else ''
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:assert 'storyboard/index.html' in z.namelist()
