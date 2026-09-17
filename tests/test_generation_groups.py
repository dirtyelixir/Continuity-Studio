"""Protocol fixtures only: no provider is invoked and no production data is used."""
import copy
import io
import json
import zipfile
import pytest
from studio import generation_groups as gg, store, engine, models, video_render as vr, h3_render_graph as graph
from test_production import client, plan, create, add_asset
from test_video_render import local, schema

GID='mg_'+'a'*16

@pytest.fixture
def montage(plan):
    plan=copy.deepcopy(plan);a=plan['shots'][0];a['dialogue']=[]
    b=copy.deepcopy(a);b.update(id='reaction',title='Receive the light',framing='Close-up',action='Look at the light',
        keyframes=[{'id':'reaction_start','moment':'start','description':'Ada looks down'}, {'id':'reaction_end','moment':'end','description':'Ada looks at the light'}],
        dialogue=[{'entity_id':'ada','language':'English','text':'Light.','delivery':'quietly','start':4,'end':5}])
    plan['shots'].append(b)
    plan['edit_plan']=[{'id':'view1','shot_id':'shot','planned_edit_in':0,'planned_edit_out':3,'cut_in_reason':'Find the switch','cut_out_reason':'See its effect','continuity_note':'Ada left'},
                       {'id':'view2','shot_id':'reaction','planned_edit_in':3,'planned_edit_out':6,'cut_in_reason':'Receive the light','cut_out_reason':'Hold recognition','continuity_note':'Ada looks right'}]
    return models.Production.model_validate(plan).model_dump()


def definition(mode='I2VA',**changes):
    return {'id':GID,'title':'Discovery and reaction','edit_ids':['view1','view2'],'mode':mode,
            'reference_targets':[],'reason':'Cut to the readable response',**changes}


def save(client,pid,d=None):
    return client.put(f'/api/projects/{pid}/generation-groups',json={'revision':gg.config(pid)['revision'],
        'production_revision':store.project(pid)['revision'],'group':d or definition()})


def text_for(src):
    parts=[]
    for h,m in zip(gg.headers(src),src['members']):
        parts.append(h+' Ada looks at the light. '+' '.join(gg.speech_clauses(src,m)))
    return src['alignment']+'\n\nintegrated_multimodal_description: '+'\n'.join(parts)+'\n\noverall_soundscape: Wind.\n\nnon_diegetic_music: N/A'


def ready(client,pid):
    src=gg.prompt_source(store.project(pid),GID)
    response=client.put(f'/api/projects/{pid}/generation-groups/{GID}/prompt',json={'revision':gg.config(pid)['revision'], 'source_hash':store.digest(src),'text':text_for(src)})
    assert response.status_code==200,response.text
    return src


def test_order_short_views_repeats_and_limits(montage):
    p={'production':montage};r=gg.resolve(p,definition())
    assert [(m['start'],m['end']) for m in r['members']]==[(0,3),(3,6)]
    assert r['members'][1]['dialogue'][0]['start']==4
    for d in [definition(edit_ids=['view2','view1']),definition(edit_ids=['view1','view1']),definition(edit_ids=['missing','view2'])]:
        with pytest.raises(ValueError):gg.resolve(p,d)
    montage['edit_plan'][1]['shot_id']='shot';montage['edit_plan'][1]['planned_edit_in']=3
    r=gg.resolve(p,definition());assert len(r['members'])==2 and {m['shot_id'] for m in r['members']}=={'shot'}
    montage['edit_plan'][0]['planned_edit_out']=0.5;montage['edit_plan'][1]['planned_edit_in']=5.5
    with pytest.raises(ValueError,match='4–15'):gg.resolve(p,definition())


def test_invalid_partial_dialogue_cross_scene_and_excess_duration(montage):
    p={'production':montage};montage['edit_plan'][1]['planned_edit_in']=4.5
    with pytest.raises(ValueError,match='對白'):gg.resolve(p,definition())
    montage['edit_plan'][1]['planned_edit_in']=3;montage['shots'][1]['scene_id']='other'
    with pytest.raises(ValueError,match='Scene'):gg.resolve(p,definition())
    montage['shots'][1]['scene_id']='scene'
    for s in montage['shots']:s['duration']=15
    for e in montage['edit_plan']:e.update(planned_edit_in=0,planned_edit_out=15)
    with pytest.raises(ValueError,match='4–15'):gg.resolve(p,definition())


@pytest.mark.parametrize('mode,count',[('I2VA',1),('FL2VA',2),('REF2VA',3)])
def test_mode_refs_and_final_shot(client,montage,mode,count):
    pid=create(client,montage)
    for t in ['start','reaction_end','ada','room']:add_asset(pid,montage,t)
    d=definition(mode,reference_targets=['ada','room','reaction_end'] if mode=='REF2VA' else [])
    assert save(client,pid,d).status_code==200
    src=gg.prompt_source(store.project(pid),GID)
    assert len(src['references'])==count
    if mode=='FL2VA':
        assert src['references'][-1]['target_id']=='reaction_end' and '(from [Shot 2])' in src['alignment']
    if mode=='REF2VA':assert [r['role'] for r in src['references']]==['character','location','storyboard']
    ready(client,pid)
    render=vr.source(store.project(pid),GID)
    assert render['mapping']['status']=='planned' and render['duration']==6 and render['global_prompt']==''


def test_reference_validation_and_trimmed_start(client,montage):
    pid=create(client,montage);add_asset(pid,montage,'start')
    assert save(client,pid,definition('REF2VA',reference_targets=['missing'])).status_code==400
    assert save(client,pid,definition('REF2VA',reference_targets=['ada','ada'])).status_code==400
    assert save(client,pid,definition(reference_targets=['ada'])).status_code==400
    assert save(client,pid,definition('REF2VA')).status_code==200
    with pytest.raises(ValueError,match='1–9'):gg.prompt_source(store.project(pid),GID)
    assert save(client,pid).status_code==200
    edited=copy.deepcopy(montage);edited['edit_plan'][0]['planned_edit_in']=1
    engine.save_plan(pid,edited,1,'Test trimmed opening')
    with pytest.raises(ValueError,match='端點'):gg.prompt_source(store.project(pid),GID)
    assert models.Production.model_validate(edited)


def test_native_prompt_job_adopt_and_staleness(client,montage):
    pid=create(client,montage);aid=add_asset(pid,montage,'start');assert save(client,pid).status_code==200
    client.post('/api/settings/routing',json={'capability':'h3_video_prompt','provider_id':'manual'})
    response=client.post(f'/api/projects/{pid}/jobs',json={'capability':'h3_video_prompt','target_id':GID})
    assert response.status_code==200,response.text
    j=response.json()['job'];src=j['input']['video_source'];text=text_for(src)
    assert 'camera cuts to' in j['input']['prompt']
    assert client.post('/api/jobs/'+j['id']+'/manual',json={'text':text,'frame_issues':[]}).status_code==200
    assert client.post(f'/api/projects/{pid}/generation-groups/adopt/{j["id"]}',json={'revision':gg.config(pid)['revision']}).status_code==200
    p=client.get('/api/projects/'+pid).json()
    assert p['generation_groups']['rows'][0]['ready'] and p['video_renders']['groups'][GID]['ready']
    assert GID not in p['video_renders']['shots']
    for bad in [text.replace('00:03.000','00:02.000'),text.replace('[Shot 2]','[Shot 3]'),text.replace('Light.','Lights.'),text+' Picture 9',text.replace('(S1)','(S2)')]:
        with pytest.raises(ValueError):gg.validate_result({'text':bad},src)
    with store.db() as c:c.execute("UPDATE assets SET status='rejected' WHERE id=?",(aid,))
    with pytest.raises(ValueError):vr.source(store.project(pid),GID)
    assert client.post(f'/api/projects/{pid}/generation-groups/adopt/{j["id"]}',json={'revision':gg.config(pid)['revision']}).status_code==400


def test_group_director_plan_and_adoption(client,montage):
    pid=create(client,montage)
    client.post('/api/settings/routing',json={'capability':'h3_group_plan','provider_id':'manual'})
    response=client.post(f'/api/projects/{pid}/jobs',json={'capability':'h3_group_plan','target_id':'scene'})
    assert response.status_code==200,response.text
    j=response.json()['job']
    item={k:v for k,v in definition().items() if k!='id'}|{'execution':'native_montage','checks':['Check the cut is visible.']}
    result={'summary':'Discovery then reaction.','groups':[item]}
    assert client.post('/api/jobs/'+j['id']+'/manual',json=result).status_code==200
    before=store.project(pid)
    r=client.post(f'/api/projects/{pid}/generation-groups/plan-adopt/{j["id"]}',json={'revision':0})
    assert r.status_code==200,r.text
    assert len(r.json()['groups'])==1 and store.project(pid)==before
    assert client.get('/api/projects/'+pid).json()['generation_groups']['plans'][0]['adopted']
    with pytest.raises(ValueError):gg.validate_plan({'summary':'Bad','groups':[dict(item,edit_ids=['view2','view1'])]},j['input']['group_plan_source'])


def test_group_render_single_submission_whole_selection_and_mapping_export(client,local,montage):
    pid,remote=local
    engine.save_plan(pid,montage,store.project(pid)['revision'],'Test montage')
    add_asset(pid,montage,'start');assert save(client,pid).status_code==200;ready(client,pid)
    p=client.get('/api/projects/'+pid).json();hash_=p['video_renders']['groups'][GID]['source_hash']
    req={'source_hash':hash_,'request_key':store.uid(),'settings':{'seed':42}}
    response=client.post(f'/api/projects/{pid}/video-workflow/{GID}/generate',json=req)
    assert response.status_code==200,response.text
    t=response.json()
    assert client.post(f'/api/projects/{pid}/video-workflow/{GID}/generate',json=req).json()['id']==t['id']
    assert len(t['request']['source']['mapping']['boundaries'])==2
    vr.run(pid,t['id']);done=vr.take(pid,t['id']);assert done['state']=='succeeded',done['error']
    timeline=json.loads(remote['graph']['12']['inputs']['timeline_data'])
    assert len(timeline['segments'])==1 and '[Shot 2] At 00:03.000, the camera cuts to' in timeline['segments'][0]['prompt']
    assert remote['posts']==1
    assert client.post(f'/api/projects/{pid}/video-renders/{t["id"]}/adopt',json={'source_hash':hash_}).status_code==200
    with store.db() as c:
        selections=[dict(r) for r in c.execute('SELECT * FROM video_selections WHERE project_id=?',(pid,))]
    assert selections==[{'project_id':pid,'shot_id':GID,'take_id':t['id']}]
    path=f'/api/projects/{pid}/generation-groups/takes/{t["id"]}/boundaries'
    data={'source_hash':hash_,'note':'Test-only protocol observation, not a real clip.', 'boundaries':[{'edit_id':'view1','start':0,'end':2.9},{'edit_id':'view2','start':2.9,'end':6.5}]}
    assert client.post(path,json={**data,'boundaries':list(reversed(data['boundaries']))}).status_code==400
    assert client.post(path,json=data).status_code==200
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+pid+'/export').content)) as z:
        mapping=json.loads(z.read('video/'+t['id']+'-storyboard-mapping.json'))
        assert mapping['status']=='user_observed' and mapping['boundaries'][1]['start']==2.9
        assert json.loads(z.read('video/'+t['id']+'-provenance.json'))['request']['source']['mapping']['status']=='planned'
        assert 'video/'+t['id']+'.mp4' in z.namelist()


def test_ref_preamble_exact_speech_timing_and_empty_annotations(client,montage):
    pid=create(client,montage);add_asset(pid,montage,'ada');assert save(client,pid,definition('REF2VA',reference_targets=['ada'])).status_code==200
    src=gg.prompt_source(store.project(pid),GID);text=text_for(src).replace('integrated_multimodal_description: ','integrated_multimodal_description: Picture 1 supplies Ada appearance.\n')
    gg.validate_result({'text':text},src)
    with pytest.raises(ValueError):gg.validate_result({'text':text.replace('4.000 to 5.000','1.000 to 2.000')},src)
    item={k:v for k,v in definition().items() if k!='id'}|{'execution':'native_montage','checks':['Check cut'],'reason_note':'','checks_note':''}
    assert 'reason_note' not in gg.PlanItem.model_validate(item).model_dump()
    with pytest.raises(ValueError):gg.PlanItem.model_validate({**item,'reason_note':'do not discard this'})
    with pytest.raises(ValueError):gg.PlanItem.model_validate({**item,'unknown':''})


def test_plan_cross_scene_global_order_cannot_hide_intervening_edit(client,montage):
    pid=create(client,montage);p=store.project(pid);src=gg.planning_source(p,'scene')
    assert all(not f['approved_image_available'] for f in src['frame_readiness'].values())
    src['edit_positions']['view2']=2
    item={k:v for k,v in definition().items() if k!='id'}|{'execution':'native_montage','checks':['Check cut']}
    with pytest.raises(ValueError,match='跨越'):gg.validate_plan({'summary':'Test','groups':[item]},src)


def test_archive_preserves_definition_and_prompt_and_can_restore(client,montage):
    pid=create(client,montage);add_asset(pid,montage,'start');assert save(client,pid).status_code==200;ready(client,pid)
    before=copy.deepcopy(gg.config(pid)['groups'][GID]);path=f'/api/projects/{pid}/generation-groups/{GID}/archive'
    assert client.post(path,json={'revision':gg.config(pid)['revision'],'archived':True}).status_code==200
    state=client.get('/api/projects/'+pid).json()
    assert state['generation_groups']['rows']==[] and state['generation_groups']['archived'][0]['id']==GID
    with pytest.raises(ValueError,match='停用'):vr.source(store.project(pid),GID)
    assert gg.config(pid)['groups'][GID]['prompt']==before['prompt']
    assert client.post(path,json={'revision':gg.config(pid)['revision'],'archived':False}).status_code==200
    assert vr.source(store.project(pid),GID)['text']==before['prompt']['text']
