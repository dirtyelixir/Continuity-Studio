"""Intent-to-input regression tests. Fixture pixels are protocol tests, not footage QC."""
import copy
import json
import pytest
from studio import storyboard_usage as usage,storyboard_board as board,generation_groups as gg
from studio import store,engine,video_workflow,video_render,h3_render_graph as graph
from test_production import client,plan,create,add_asset
from test_generation_groups import montage,definition,save,ready,GID
from test_storyboard_board import adopt,approve_all,proposed
from test_video_render import local,schema


def uses(rows,conditioned):
    return [{'anchor_id':r['anchor_id'],'use':'image_conditioning' if r['frame_id'] in conditioned else 'planning_only',
        'reason':'Use this composition in the model.' if r['frame_id'] in conditioned else 'Review the intended pose against the generated motion.',
        'boundary_exception':'Deliberately leave this cut to text and verify the resulting composition.' if r['boundary_candidate'] and r['frame_id'] not in conditioned else ''} for r in rows]


def native(rows,mode='I2VA',conditioned=None):
    conditioned=conditioned if conditioned is not None else [rows[0]['frame_id']]
    return {k:v for k,v in definition(mode).items() if k!='id'}|{'execution':'native_montage',
        'checks':['Inspect cut composition.'],'reference_targets':conditioned if mode=='REF2VA' else [],'frame_uses':uses(rows,conditioned)}


def adopt_generation(client,pid,result):
    client.post('/api/settings/routing',json={'capability':'h3_group_plan','provider_id':'manual'})
    j=client.post(f'/api/projects/{pid}/jobs',json={'capability':'h3_group_plan','target_id':'scene'}).json()['job']
    r=client.post('/api/jobs/'+j['id']+'/manual',json=result);assert r.status_code==200,r.text
    r=client.post(f'/api/projects/{pid}/generation-groups/plan-adopt/{j["id"]}',json={'revision':gg.config(pid)['revision']})
    assert r.status_code==200,r.text
    return j,r.json()


def test_roles_source_times_and_intent_freshness(client,montage):
    pid=create(client,montage);adopt(client,pid,proposed(store.project(pid),extra=True));p=store.project(pid)
    src=gg.planning_source(p,'scene');rows=src['storyboard_intent']
    assert [(r['role'],r['source_time'],r['scene_time']) for r in rows]==[
        ('opening',0,0),('intermediate_keyframe',2,2),('cut_opening',3,3)]
    before=gg.planning_fingerprint(src);approve_all(client,pid)
    assert gg.planning_fingerprint(gg.planning_source(p,'scene'))==before
    modified=copy.deepcopy(src);modified['storyboard_intent'][1]['purpose']='Critical evidence, must read clearly'
    assert gg.planning_fingerprint(modified)!=before
    assert rows[1]['boundary_candidate'] is False


@pytest.mark.parametrize('bad',['omitted','duplicate','foreign','false_input','unexplained_cut'])
def test_plan_rejects_silent_drops_and_false_binding(client,montage,bad):
    pid=create(client,montage);adopt(client,pid);src=gg.planning_source(store.project(pid),'scene');rows=src['storyboard_intent']
    item=native(rows)
    if bad=='omitted':item['frame_uses'].pop()
    elif bad=='duplicate':item['frame_uses'][1]=item['frame_uses'][0]
    elif bad=='foreign':item['frame_uses'][1]['anchor_id']='unrelated'
    elif bad=='false_input':item['frame_uses'][1]['use']='image_conditioning'
    else:item['frame_uses'][1]['boundary_exception']=' '
    with pytest.raises(ValueError):gg.validate_plan({'summary':'Plan','groups':[item]},src)
    assert gg.validate_plan({'summary':'Explicit native exception','groups':[native(rows)]},src)


def test_cut_reference_compiles_to_actual_graph_and_preserves_board(client,montage,schema):
    pid=create(client,montage);adopt(client,pid);approve_all(client,pid);p=store.project(pid)
    rows=usage.intent(p,'scene');targets=[r['frame_id'] for r in rows]
    old_board=board.config(pid);old_assets=store.assets(pid)
    j,cfg=adopt_generation(client,pid,{'summary':'Both views receive composition reference images.','groups':[native(rows,'REF2VA',targets)]})
    gid=next(iter(cfg['groups']));src=gg.prompt_source(p,gid)
    assert [r['target_id'] for r in src['references']]==targets
    assert all(u['actual_input'] for u in src['storyboard_usage'])
    source={**src,'text':'Test prompt','global_prompt':''}
    uploads={r['asset_id']:{'name':r['asset_id']+'.png','subfolder':'test','type':'input'} for r in src['references']}
    g=graph.build_graph(source,uploads,{**graph.defaults('REF2VA'),'seed':1},'a'*16,schema)
    timeline=json.loads(g['12']['inputs']['timeline_data'])
    assert len(timeline['segments'][0]['refs'])==2
    assert timeline['segments'][0]['refs'][1]['imageFile'].endswith(src['references'][1]['asset_id']+'.png')
    assert board.config(pid)==old_board and store.assets(pid)==old_assets and store.project(pid)==p
    # A later manual edit cannot silently remove a newly adopted binding contract.
    d=copy.deepcopy(cfg['groups'][gid]['definition']);d.pop('frame_uses');d['mode']='I2VA';d['reference_targets']=[]
    r=client.put(f'/api/projects/{pid}/generation-groups',json={'revision':cfg['revision'],'production_revision':p['revision'],'group':d})
    assert r.status_code==400


def test_ref2va_cannot_claim_missing_cut_reference(client,montage):
    pid=create(client,montage);adopt(client,pid);src=gg.planning_source(store.project(pid),'scene');rows=src['storyboard_intent']
    item=native(rows,'REF2VA',[r['frame_id'] for r in rows]);item['reference_targets'].pop()
    with pytest.raises(ValueError,match='reference_targets'):gg.validate_plan({'summary':'Invalid','groups':[item]},src)


def test_independent_cut_sources_bind_each_opening_and_tail_requirement(client,montage):
    montage['edit_plan'][1]['planned_edit_in']=0
    pid=create(client,montage);result=proposed(store.project(pid));shot=montage['shots'][0]
    result['panels'][0]['anchors'].append({'time':3,'reuse_frame_id':'','description':'A settled pose','state':[],'purpose':'Read this pose.'})
    adopt(client,pid,result);approve_all(client,pid);p=store.project(pid);rows=usage.intent(p,'scene')
    groups=[]
    for edit in montage['edit_plan']:
        relevant=[r for r in rows if r['edit_id']==edit['id']]
        groups.append({'title':edit['id'],'edit_ids':[edit['id']],'execution':'separate_source','mode':None,'reference_targets':[],
            'reason':'A new source anchors this camera setup.','checks':['Inspect the new composition.'],
            'frame_uses':uses(relevant,[relevant[0]['frame_id']])})
    adopt_generation(client,pid,{'summary':'Separate image-conditioned sources.','groups':groups})
    for sid in ['shot','reaction']:
        src=video_workflow.prompt_source(p,sid)
        assert len(src['references'])==1
        assert next(u for u in src['storyboard_usage'] if u['use']=='image_conditioning')['actual_input']
    assert video_workflow.prompt_source(p,'reaction')['storyboard_usage'][0]['role']=='cut_opening'
    assert len(video_workflow.prompt_source(p,'shot')['storyboard_usage'])==2


def test_source_end_requirement_blocks_i2va_and_stale_plan_cannot_drop_it(client,plan):
    plan['edit_plan']=[{'id':'view','shot_id':'shot','planned_edit_in':0,'planned_edit_out':6,'cut_in_reason':'Start','cut_out_reason':'End','continuity_note':'Same view'}]
    pid=create(client,plan);result=proposed(store.project(pid));shot=plan['shots'][0]
    result['panels'][0]['anchors'].append({'time':6,'reuse_frame_id':'end','description':shot['keyframes'][1]['description'],'state':shot['end_state'],'purpose':'The final composition must be supplied.'})
    adopt(client,pid,result);approve_all(client,pid);p=store.project(pid);rows=usage.intent(p,'scene')
    item={'title':'Source','edit_ids':['view'],'execution':'separate_source','mode':None,'reference_targets':[],
        'reason':'Anchor final state.','checks':['Inspect end pose.'],'frame_uses':uses(rows,[r['frame_id'] for r in rows])}
    adopt_generation(client,pid,{'summary':'Both endpoints required.','groups':[item]})
    with pytest.raises(ValueError,match='image input'):video_workflow.prompt_source(p,'shot')
    store.put_setting('video-workflow:'+pid,{'revision':1,'shots':{'shot':{'mode':'FL2VA'}}})
    src=video_workflow.prompt_source(p,'shot');assert len(src['references'])==2
    p['production']['shots'][0]['expression']='Changed intent'
    engine.save_plan(pid,p['production'],p['revision'],'New intent')
    with pytest.raises(ValueError,match='過期'):usage.source_uses(store.project(pid),'shot')


def test_trimmed_interior_is_not_falsely_promised_as_full_source_opening(client,montage):
    pid=create(client,montage);adopt(client,pid);p=store.project(pid);rows=usage.intent(p,'scene');r=rows[-1]
    item={'title':'Source','edit_ids':['view2'],'execution':'separate_source','mode':None,'reference_targets':[],
        'reason':'Reason','checks':['Inspect'],'frame_uses':uses([r],[r['frame_id']])}
    with pytest.raises(ValueError,match='中間畫面不能冒充首尾幀'):usage.compile_uses(item,rows,p['production'])


def test_frozen_upload_graph_receipts_and_missing_binding_refusal(client,local,montage,schema):
    pid,remote=local;engine.save_plan(pid,montage,store.project(pid)['revision'],'Test montage')
    adopt(client,pid);approve_all(client,pid);p=store.project(pid);rows=usage.intent(p,'scene')
    d=definition(frame_uses=uses(rows,[rows[0]['frame_id']]))
    assert save(client,pid,d).status_code==200
    ready(client,pid);src=video_render.source(p,GID)
    before=copy.deepcopy(src);src['references']=[]
    with pytest.raises(ValueError,match='凍結圖板'):graph.build_graph(src,{},graph.defaults(),'a'*16,schema)
    src=before
    req={'source_hash':store.digest(src),'request_key':store.uid(),'settings':{'seed':42}}
    r=client.post(f'/api/projects/{pid}/video-workflow/{GID}/freeze',json=req);assert r.status_code==200,r.text
    frozen=r.json();assert len(frozen['source']['storyboard_usage'])==2 and remote['posts']==0
    r=client.post(f'/api/projects/{pid}/video-workflow/{GID}/generate',json={**req,'frozen_id':frozen['id']});assert r.status_code==200,r.text
    tid=r.json()['id'];video_render.run(pid,tid)
    assert video_render.take(pid,tid)['state']=='succeeded' and remote['posts']==1
    actual=usage.submitted_inputs(p);assert len(actual)==1 and actual[0]['roles']==['startImage']
    board_state=board.state(p);a=board_state['scenes'][0]['panels'][0]['anchors'][0]
    assert len(a['generation_usage']['submitted'])==1
    # Upload alone is not submission evidence.
    (video_render.folder(tid)/'receipt.json').unlink()
    assert usage.submitted_inputs(p)==[]
