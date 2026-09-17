"""Real Studio contracts against isolated DBs and mocked H3 transport only."""
import copy
import json
import pytest
from studio import store, engine, models, editorial, editorial_records as er
from studio import directing, directing_approvals, generation_groups as gg
from studio import video_render as vr, take_lifecycle as life, edit_segments
from test_production import client, plan, create, add_asset
from test_generation_groups import montage, definition, save as save_group, ready as ready_group, GID
from test_generation_arrangements import adopt_arrangement
from test_storyboard_board import adopt as adopt_board, proposed
from test_directing import directed
from test_video_render import local, schema, request_for, send


def adopt_editorial(pid):
    p=store.project(pid)
    t=editorial.open_scene(pid,editorial.OpenScene(scene_id='scene',production_revision=p['revision']))
    editorial.adopt(pid,t['id'],editorial.TrialAdoption(version=t['version']))


@pytest.mark.parametrize('legacy',[False,True])
def test_supplemental_frame_preserves_audio_and_human_approval(client,plan,legacy):
    pid=create(client,directed(plan));adopt_editorial(pid)
    if legacy:
        saved=store.setting('editorial_scenes:'+pid)
        saved['scene'].pop('audio_dep');saved['scene'].pop('review_dep')
        store.put_setting('editorial_scenes:'+pid,saved)
    p=store.project(pid);before=er.state(p);context=er.review_context(p)
    directing_approvals.approve(pid,p['revision'],directing_approvals.basis(p))
    records=store.setting('editorial_scenes:'+pid);history=store.setting('directing_human_approvals:'+pid)
    adopt_board(client,pid,proposed(p,extra=True))
    p=store.project(pid)
    assert er.state(p)['audio']==before['audio'] and er.review_context(p)==context
    assert 'scene' in directing_approvals.scene_approvals(p)
    trial=store.setting('editorial_trials:'+pid)[-1]
    assert editorial.status(p,trial)=='adopted'
    assert store.setting('editorial_scenes:'+pid)==records
    assert store.setting('directing_human_approvals:'+pid)==history


@pytest.mark.parametrize('legacy',[False,True])
@pytest.mark.parametrize('change',['framing','music','soundscape','dialogue','timing'])
def test_audio_projection_retains_visual_independence_and_real_invalidation(client,montage,legacy,change):
    pid=create(client,montage);adopt_editorial(pid)
    if legacy:
        saved=store.setting('editorial_scenes:'+pid)
        saved['scene'].pop('audio_dep');saved['scene'].pop('review_dep')
        store.put_setting('editorial_scenes:'+pid,saved)
    p=store.project(pid);before=er.state(p)['audio'];assert before
    if change in ('framing','music','soundscape'):p['production']['shots'][0][change]='Changed specification'
    elif change=='dialogue':p['production']['shots'][1]['dialogue'][0]['text']='Changed.'
    else:p['production']['edit_plan'][0]['planned_edit_out']=2.5
    after=er.state(p)
    assert (after['audio']==before)==(change in ('framing','music','soundscape'))
    assert (after['scenes'][0]['audio_status']=='current')==(change in ('framing','music','soundscape'))


def test_legacy_snapshot_must_be_proven_and_default_audio_still_works(client,montage):
    pid=create(client,montage)
    assert er.state(store.project(pid))['audio']
    adopt_editorial(pid);saved=store.setting('editorial_scenes:'+pid)
    for k in ('audio_dep','review_dep'):saved['scene'].pop(k)
    saved['scene']['scene_hash']='unproven';store.put_setting('editorial_scenes:'+pid,saved)
    assert not er.state(store.project(pid))['audio']
    assert er.review_context(store.project(pid))=={}


def test_plan_survives_image_fulfillment_and_extra_frame_but_not_timing(client,montage):
    pid,_=adopt_arrangement(client,montage)
    before=gg.source_arrangement(store.project(pid),'shot');assert before
    add_asset(pid,montage,'start')
    assert gg.source_arrangement(store.project(pid),'shot')==before
    p=store.project(pid);p['production']['shots'][0]['keyframes'].append({'id':'key1','moment':'key','source_time':1,'description':'Still','state':[]})
    engine.save_plan(pid,p['production'],p['revision'],'Fulfil control requirement')
    assert gg.source_arrangement(store.project(pid),'shot')==before
    p=store.project(pid);p['production']['edit_plan'][0]['planned_edit_out']=2.5
    engine.save_plan(pid,p['production'],p['revision'],'Change edit intent')
    assert gg.arrangements(store.project(pid))[0]['status']=='stale'


def test_missing_interior_control_adopts_as_requirement_but_blocks_freeze(client,montage):
    montage['edit_plan'][0]['planned_edit_in']=1
    pid,job=adopt_arrangement(client,montage,True)
    state=client.get('/api/projects/'+pid).json();row=state['generation_groups']['rows'][0]
    requirement=row['reference_requirements'][0]
    assert not requirement['ready'] and requirement['target_id'] is None
    assert requirement['source_time']==1 and requirement['action']=='storyboard_plan'
    req={'source_hash':'a'*64,'request_key':store.uid(),'settings':{}}
    for action in ('freeze','generate'):
        assert client.post(f'/api/projects/{pid}/video-workflow/{row["id"]}/{action}',json=req).status_code==400
    assert gg.arrangements(store.project(pid))[0]['status']=='current'
    with store.db() as c:assert c.execute('SELECT count(*) FROM video_takes').fetchone()[0]==0


def completed(client,local):
    pid,remote=local;req=request_for(client,pid)
    frozen=client.post(f'/api/projects/{pid}/video-workflow/shot/freeze',json=req)
    assert frozen.status_code==200,frozen.text
    frozen=frozen.json()
    assert remote['posts']==0
    with store.db() as c:assert c.execute('SELECT count(*) FROM video_takes').fetchone()[0]==0
    t=send(client,pid,{**req,'frozen_id':frozen['id']});vr.run(pid,t['id'])
    assert vr.take(pid,t['id'])['state']=='succeeded'
    assert vr.take(pid,t['id'])['request']==frozen
    return pid,req,t,frozen


def test_frozen_attempt_and_successful_take_survive_unrelated_readiness_changes(client,local):
    pid,req,t,frozen=completed(client,local)
    vr.adopt(pid,t['id'],vr.Adopt(source_hash=req['source_hash']))
    p=store.project(pid);p['production']['shots'][0]['keyframes'].append({'id':'extra','moment':'key','source_time':2,'description':'Documentary still','state':[]})
    engine.save_plan(pid,p['production'],p['revision'],'Add documentary still')
    state=client.get('/api/projects/'+pid).json();row=state['video_renders']['takes'][0]
    assert not state['video_renders']['shots']['shot']['ready']
    assert row['execution_state']=='succeeded' and row['current'] and row['selected']
    assert row['review_status']=='accepted' and not row['used_in_edit']
    assert vr.take(pid,t['id'])['request']==frozen
    assert json.loads((vr.folder(t['id'])/'request.json').read_text())==frozen
    assert client.get(f'/api/projects/{pid}/video-renders/{t["id"]}/file').status_code==200


def test_compatibility_review_is_version_bound_and_does_not_rewrite_history(client,local):
    pid,req,t,frozen=completed(client,local)
    p=store.project(pid);p['production']['shots'][0]['framing']='Wide'
    engine.save_plan(pid,p['production'],p['revision'],'Change visual direction')
    path=f'/api/projects/{pid}/video-renders/{t["id"]}'
    row=client.get('/api/projects/'+pid).json()['video_renders']['takes'][0]
    assert row['compatibility']['status']=='needs_review' and row['execution_state']=='succeeded'
    assert client.post(path+'/adopt',json={'source_hash':req['source_hash']}).status_code==400
    assert client.post(path+'/review',json={'decision':'accepted','compatibility_hash':'a'*64}).status_code==400
    data={'decision':'accepted','compatibility_hash':row['compatibility']['current_hash']}
    assert client.post(path+'/review',json=data).status_code==200
    assert client.post(path+'/adopt',json={'source_hash':req['source_hash']}).status_code==200
    assert vr.take(pid,t['id'])['request']==frozen
    assert client.post(path+'/review',json={**data,'decision':'rejected'}).status_code==200
    row=client.get('/api/projects/'+pid).json()['video_renders']['takes'][0]
    assert row['review_status']=='rejected' and row['execution_state']=='succeeded'
    assert len(life.reviews(pid,t['id']))==3


def test_unified_single_edit_binding_is_independent_of_selection_and_preserves_stale_use(client,local):
    pid,req,t,frozen=completed(client,local)
    p=store.project(pid);p['production']=editorial.complete_edits(p['production'])
    engine.save_plan(pid,p['production'],p['revision'],'Define edit')
    token=life.compatibility(store.project(pid),vr.take(pid,t['id']))['current_hash']
    vr.review_take(pid,t['id'],vr.TakeReview(decision='accepted',compatibility_hash=token))
    e=store.project(pid)['production']['edit_plan'][0]
    payload={'version':0,'production_revision':store.project(pid)['revision'],'take_id':t['id'],'edit_id':e['id'],
        'source_in':0.2,'source_out':5.5,'timeline_in':0,'note':'Test-only observed range.'}
    url=f'/api/projects/{pid}/edit-segments'
    assert client.put(url,json={**payload,'source_out':999}).status_code==400
    assert client.put(url,json=payload).status_code==200
    assert client.put(url,json=payload).status_code==400
    state=client.get('/api/projects/'+pid).json();row=state['video_renders']['takes'][0]
    assert row['used_in_edit'] and not row['selected'] and state['edit_segments']['complete']
    material=directing.edit_manifest(state)[0]['source_video']
    assert material['take_id']==t['id'] and material['source_in']==0.2 and material['timeline_out']==5.3
    p=store.project(pid);p['production']['edit_plan'][0]['planned_edit_out']=5
    engine.save_plan(pid,p['production'],p['revision'],'Change edit')
    state=client.get('/api/projects/'+pid).json()
    assert state['edit_segments']['segments'][0]['status']=='needs_review'
    assert state['video_renders']['takes'][0]['used_in_edit']
    assert vr.take(pid,t['id'])['request']==frozen


def test_group_uses_same_edit_binding_and_archived_take_remains_readable(client,local,montage):
    pid,remote=local;p=store.project(pid)
    engine.save_plan(pid,montage,p['revision'],'Group plan');add_asset(pid,montage,'start')
    assert save_group(client,pid).status_code==200;ready_group(client,pid)
    src=vr.source(store.project(pid),GID)
    req=vr.Generate(source_hash=store.digest(src),request_key=store.uid())
    t=vr.generate(pid,GID,req);vr.run(pid,t['id']);vr.adopt(pid,t['id'],vr.Adopt(source_hash=t['source_hash']))
    observed=gg.Observed(source_hash=t['source_hash'],note='Test-only observed cuts.',boundaries=[
        gg.Boundary(edit_id='view1',start=0,end=2.9),gg.Boundary(edit_id='view2',start=2.9,end=6.5)])
    gg.observe(pid,t['id'],observed)
    projected=client.get('/api/projects/'+pid).json()['edit_segments']['segments']
    assert projected[0]['material']['timeline_out']==projected[1]['material']['timeline_in']==2.9
    gg.observe(pid,t['id'],observed)
    assert len(store.setting('generation-group-boundary-history:'+t['id']))==2
    payload={'version':0,'production_revision':store.project(pid)['revision'],'take_id':t['id'],'edit_id':'view1',
        'source_in':0,'source_out':2.9,'timeline_in':0,'note':'Test-only group observation.'}
    assert client.put(f'/api/projects/{pid}/edit-segments',json=payload).status_code==200
    cfg=gg.config(pid);cfg['groups'][GID]['archived']=True;store.put_setting('generation-groups:'+pid,cfg)
    state=client.get('/api/projects/'+pid).json()
    assert state['generation_groups']['rows']==[]
    assert state['video_renders']['takes'][0]['used_in_edit']
    assert directing.edit_manifest(state)[0]['source_video']['take_id']==t['id']


def test_impact_preview_is_read_only_and_preserves_audio_on_visual_change(client,montage):
    pid,_=adopt_arrangement(client,montage);p=store.project(pid)
    plan=copy.deepcopy(p['production']);plan['shots'][0]['keyframes'].append({'id':'extra','moment':'key','source_time':1,'description':'Still','state':[]})
    with store.db() as c:before=[tuple(r) for r in c.execute('SELECT * FROM settings')]
    response=client.post(f'/api/projects/{pid}/plan-impact',json={'revision':p['revision'],'production':plan})
    assert response.status_code==200,response.text
    assert response.json()['dialogue_audio_unchanged'] and response.json()['generation_units_change']==[]
    assert store.project(pid)==p
    with store.db() as c:assert [tuple(r) for r in c.execute('SELECT * FROM settings')]==before


def test_single_source_strategy_survives_control_fulfillment(client,plan):
    from test_video_workflow import begin,adopt
    from studio import video_workflow
    pid=create(client,plan);j=begin(client,pid,'h3_strategy')
    result={'mode':'I2VA','reason':'Anchor the opening.','evidence':['Raise hand and press switch'],
        'start_blueprint':'Ada left, hand lowered.','end_blueprint':'',
        'checks':['Check hand.','Check light.']}
    assert client.post('/api/jobs/'+j['id']+'/manual',json=result).status_code==200
    add_asset(pid,plan,'start')
    p=store.project(pid);p['production']['shots'][0]['keyframes'].append({'id':'extra','moment':'key','source_time':1,'description':'Still','state':[]})
    engine.save_plan(pid,p['production'],p['revision'],'Add control')
    assert adopt(client,pid,j).status_code==200
    assert not video_workflow.state(store.project(pid))['shots'][0]['strategy_stale']


def test_frozen_request_rejects_stale_or_tampered_submission(client,local):
    pid,remote=local;req=request_for(client,pid)
    frozen=vr.freeze(pid,'shot',vr.Generate(**req));key='frozen-video-request:'+pid+':'+frozen['id']
    broken=copy.deepcopy(frozen);broken['settings']['seed']=123;store.put_setting(key,broken)
    response=client.post(f'/api/projects/{pid}/video-workflow/shot/generate',json={**req,'frozen_id':frozen['id']})
    assert response.status_code==400 and remote['posts']==0
    store.put_setting(key,frozen)
    with store.db() as c:c.execute("UPDATE assets SET status='rejected' WHERE project_id=?",(pid,))
    assert client.post(f'/api/projects/{pid}/video-workflow/shot/generate',json={**req,'frozen_id':frozen['id']}).status_code==400
    assert store.setting(key)==frozen


def test_legacy_take_can_recover_compatibility_without_new_request_readiness(client,local):
    pid,req,t,frozen=completed(client,local)
    legacy=copy.deepcopy(frozen)
    for key in ('editorial_basis','generation_intent','id','contract_version','request_hash'):legacy.pop(key)
    with store.db() as c:c.execute('UPDATE video_takes SET request=? WHERE id=?',(store.encode(legacy),t['id']))
    p=store.project(pid);p['production']['shots'][0]['keyframes'].append({'id':'extra','moment':'key','source_time':2,'description':'Still','state':[]})
    engine.save_plan(pid,p['production'],p['revision'],'Extra documentation')
    state=client.get('/api/projects/'+pid).json()
    assert not state['video_renders']['shots']['shot']['ready']
    assert state['video_renders']['takes'][0]['compatibility']['status']=='compatible'
    assert vr.take(pid,t['id'])['request']==legacy


def test_editorial_impact_reports_cue_change_without_writing_it(client,montage):
    pid=create(client,montage);adopt_editorial(pid)
    t=store.setting('editorial_trials:'+pid)[-1];p=store.project(pid)
    cues=copy.deepcopy(t['audio_cues']);cues[0]['timeline_in']-=0.1
    request={'version':t['version'],'production_revision':p['revision'],'edit_plan':p['production']['edit_plan'],'audio_cues':cues}
    response=client.post(f'/api/projects/{pid}/editorial/{t["id"]}/impact',json=request)
    assert response.status_code==200,response.text
    assert not response.json()['dialogue_audio_unchanged']
    assert store.setting('editorial_trials:'+pid)[-1]==t


def test_missing_output_does_not_erase_success_but_cannot_complete_edit(client,local):
    pid,req,t,_=completed(client,local)
    vr.adopt(pid,t['id'],vr.Adopt(source_hash=req['source_hash']))
    (vr.folder(t['id'])/'output.mp4').rename(vr.folder(t['id'])/'test-moved.mp4')
    row=client.get('/api/projects/'+pid).json()['video_renders']['takes'][0]
    assert row['execution_state']=='succeeded' and not row['media_available']
    assert row['review_status']=='accepted' and row['video_url'] is None
