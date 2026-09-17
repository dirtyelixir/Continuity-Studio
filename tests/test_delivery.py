import copy,io,json,zipfile
import pytest
from studio import delivery,store,engine
from test_production import client,plan,create,add_asset


def established(client,plan):
    pid=create(client,plan);add_asset(pid,plan,'ada');add_asset(pid,plan,'room')
    return pid


def edit_payload(client,pid):
    p=client.get('/api/projects/'+pid).json();return {**p['delivery']['configuration'],'production_revision':p['revision']}


def test_default_ref2_uses_canon_not_forced_keyframes(client,plan):
    pid=established(client,plan);add_asset(pid,plan,'start');add_asset(pid,plan,'end')
    p=client.get('/api/projects/'+pid).json();scene=p['delivery']['scenes'][0];chapter=scene['chapters'][0]
    assert chapter['mode']=='REF2VA' and len(chapter['references'])==2
    assert [r['role'] for r in chapter['references']]==['character','location']
    assert not chapter['guidance']['enabled'] and not chapter['issues']
    delivery.validate_complete(chapter['text'],chapter['references'],plan['shots'][0])
    assert chapter['text'].startswith('subject_definitions:') and 'integrated_multimodal_description:' not in chapter['text']


def test_scene_global_and_cross_scene_guidance(client,plan):
    p2=copy.deepcopy(plan);p2['scenes'].append({**p2['scenes'][0],'id':'scene2','title':'Next scene'})
    p2['shots'][0]['transition_note']='Enter the next shot with a straight cut.'
    p2['shots'].append({**copy.deepcopy(p2['shots'][0]),'id':'shot2','scene_id':'scene2','keyframes':[{'id':'f2','moment':'start','description':'New scene moment'}]})
    p2['shots'][1]['transition_note']='An outgoing note for the following scene.'
    pid=established(client,p2);before=store.assets(pid)
    state=client.get('/api/projects/'+pid).json();scene=state['delivery']['scenes'][1];override=scene['global_prompt']+'\nMaintain the same palette.'
    payload=edit_payload(client,pid);payload['scenes']={'scene2':{'global_prompt':override,'chapters':{'shot2':{'guide_from_previous':True,'guidance_mode':'manual'}}}}
    assert client.put('/api/projects/'+pid+'/delivery',json=payload).status_code==200
    state=client.get('/api/projects/'+pid).json();c=state['delivery']['scenes'][1]['chapters'][0]
    assert 'global_source' not in c and 'global_prompt' not in c
    assert c['scene_id']=='scene2' and c['text']==override+'\n\n'+c['shot_prompt']
    assert c['guidance']['enabled'] and c['guidance']['cross_scene'] and c['guidance']['previous_shot_id']=='shot'
    assert 'Enter the next shot' in c['guidance']['notes'] and 'An outgoing note' not in c['guidance']['notes']
    assert state['revision']==1 and store.assets(pid)==before
    assert client.put('/api/projects/'+pid+'/delivery',json=payload).status_code==400
    payload=edit_payload(client,pid);payload['continuity_enabled']=False
    client.put('/api/projects/'+pid+'/delivery',json=payload)
    assert not client.get('/api/projects/'+pid).json()['delivery']['scenes'][1]['chapters'][0]['guidance']['enabled']
    assert len(store.setting('delivery-history:'+pid))==2


def test_optional_frame_changes_staleness_and_reference_labels(client,plan):
    pid=established(client,plan);first=add_asset(pid,plan,'start')
    payload=edit_payload(client,pid);payload['scenes']={'scene':{'chapters':{'shot':{'reference_frame':'start'}}}}
    client.put('/api/projects/'+pid+'/delivery',json=payload)
    scene=client.get('/api/projects/'+pid).json()['delivery']['scenes'][0]
    assert len(scene['chapters'][0]['references'])==3 and scene['chapters'][0]['references'][-1]['label']=='Picture 3'
    assert not scene['chapters'][0]['issues']
    with store.db() as db:db.execute('UPDATE assets SET status="rejected" WHERE id=?',(first,))
    after=client.get('/api/projects/'+pid).json()['delivery']['scenes'][0]
    assert after['delivery_hash']!=scene['delivery_hash'] and any('Approve the requested' in i for i in after['chapters'][0]['issues'])


def test_refinement_validates_six_fields_and_dialogue(client,plan):
    pid=established(client,plan);compiled=client.get('/api/projects/'+pid).json()['delivery']['scenes'][0]
    result={'global_prompt':compiled['global_prompt'],'chapters':[{'shot_id':c['shot_id'],'shot_prompt':c['shot_prompt']} for c in compiled['chapters']]}
    delivery.validate_result(result,compiled,plan)
    for bad in ['new dialogue','<Picture 9>','<Video 1>']:
        damaged=copy.deepcopy(result)
        if bad=='new dialogue':damaged['chapters'][0]['shot_prompt']=damaged['chapters'][0]['shot_prompt'].replace('Light.',bad)
        else:damaged['chapters'][0]['shot_prompt']+=' '+bad
        with pytest.raises(ValueError):delivery.validate_result(damaged,compiled,plan)
    bad=copy.deepcopy(result);bad['global_prompt']='subject_definitions:\nA vague scene.'
    with pytest.raises(ValueError):delivery.validate_result(bad,compiled,plan)


def test_manual_scene_provider_and_split_export(client,plan):
    pid=established(client,plan)
    client.post('/api/settings/routing',json={'capability':'h3_scene','provider_id':'manual'})
    job=client.post('/api/projects/'+pid+'/jobs',json={'capability':'h3_scene','target_id':'scene'}).json()['job']
    compiled=store.job(job['id'])['input']['compiled']
    result={'global_prompt':compiled['global_prompt'],'chapters':[{'shot_id':c['shot_id'],'shot_prompt':c['shot_prompt']} for c in compiled['chapters']]}
    response=client.post('/api/jobs/'+job['id']+'/manual',json=result);assert response.status_code==200
    assert client.get('/api/projects/'+pid).json()['delivery']['scenes'][0]['refined_by']
    z=zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+pid+'/export').content))
    assert z.read('ref2/scenes/scene/global.txt').decode()==result['global_prompt']
    assert not any('/chapters/' in name and name.endswith('/global.txt') for name in z.namelist())
    assert z.read('ref2/scenes/scene/chapters/shot/shot.txt').decode()==result['chapters'][0]['shot_prompt']
    manifest=json.loads(z.read('ref2/scenes/scene/chapters/shot/references-and-guidance.json'))
    assert all(r['path'] in z.namelist() for r in manifest['references'])
    assert 'not a directly importable' in json.loads(z.read('ref2/handoff.json'))['instructions']


def test_task_marker_normalization_preserves_raw_prose():
    raw={'global_prompt':'subject_definitions: A','chapters':[{'shot_id':'s','shot_prompt':'summary:\nAda waits.\n\nretention_analysis:\nKeep her.'}]}
    normalized=delivery.normalize_result(raw)
    assert normalized['chapters'][0]['shot_prompt']=='summary:\n[reference generation] Ada waits.\n\nretention_analysis:\nKeep her.'
    assert raw['chapters'][0]['shot_prompt'].startswith('summary:\nAda')
    assert delivery.normalize_result(normalized)==normalized


def test_many_shots_share_only_scene_global_and_reject_shot_override(client,plan):
    plan['shots'].append({**copy.deepcopy(plan['shots'][0]),'id':'shot2','keyframes':[{'id':'frame2','moment':'start','description':'Second shot'}]})
    pid=established(client,plan)
    payload=edit_payload(client,pid)
    scene=client.get('/api/projects/'+pid).json()['delivery']['scenes'][0]
    shared=scene['global_prompt']+'\nScene lighting remains warm.'
    payload['scenes']={'scene':{'global_prompt':shared,'chapters':{'shot':{'shot_prompt':scene['chapters'][0]['shot_prompt']+'\nA quiet pause.'}}}}
    assert client.put('/api/projects/'+pid+'/delivery',json=payload).status_code==200
    scene=client.get('/api/projects/'+pid).json()['delivery']['scenes'][0]
    for shot in scene['chapters']:
        assert 'global_prompt' not in shot and 'global_source' not in shot
        assert shot['text']==shared+'\n\n'+shot['shot_prompt'] and not shot['issues']
    assert scene['chapters'][0]['shot_prompt']!=scene['chapters'][1]['shot_prompt']
    payload=edit_payload(client,pid);payload['scenes']['scene']['chapters']['shot']['global_prompt']='Forbidden override'
    assert client.put('/api/projects/'+pid+'/delivery',json=payload).status_code==422
    # Old storage remains recoverable but cannot affect the active scene or Shot output.
    store.put_setting('delivery:'+pid,payload)
    current=client.get('/api/projects/'+pid).json()['delivery']
    assert 'global_prompt' not in current['configuration']['scenes']['scene']['chapters']['shot']
    assert current['scenes'][0]['global_prompt']==shared
    assert all('Forbidden override' not in c['text'] for c in current['scenes'][0]['chapters'])
    assert store.setting('delivery:'+pid)['scenes']['scene']['chapters']['shot']['global_prompt']=='Forbidden override'


def test_optional_compositions_share_scene_definitions_and_stable_slots(client,plan):
    plan['shots'].append({**copy.deepcopy(plan['shots'][0]),'id':'shot2','keyframes':[{'id':'frame2','moment':'start','description':'Second shot'}]})
    pid=established(client,plan);add_asset(pid,plan,'start');add_asset(pid,plan,'frame2')
    payload=edit_payload(client,pid);payload['scenes']={'scene':{'chapters':{'shot':{'reference_frame':'start'},'shot2':{'reference_frame':'start'}}}}
    assert client.put('/api/projects/'+pid+'/delivery',json=payload).status_code==200
    scene=client.get('/api/projects/'+pid).json()['delivery']['scenes'][0]
    assert len(scene['references'])==4
    assert '<Picture 3>' in scene['global_prompt'] and '<Picture 4>' in scene['global_prompt']
    for c in scene['chapters']:
        assert c['references']==scene['references'] and not c['issues']
        assert c['text']==scene['global_prompt']+'\n\n'+c['shot_prompt']
    assert '<Picture 3>' in scene['chapters'][0]['shot_prompt']
    assert '<Picture 4>' in scene['chapters'][1]['shot_prompt']
    result={'global_prompt':scene['global_prompt'],'chapters':[{'shot_id':c['shot_id'],'shot_prompt':c['shot_prompt']} for c in scene['chapters']]}
    delivery.validate_result(result,scene,plan)


def test_explicit_prompt_edits_preserve_exact_text_and_export(client,plan):
    pid=established(client,plan);before=store.project(pid);assets=store.assets(pid)
    p=client.get('/api/projects/'+pid).json();scene=p['delivery']['scenes'][0]
    shot=scene['chapters'][0]['shot_prompt'].replace('Speech and mouth movement:', 'Director mouth instruction:')+'\n\nMy own camera direction.\n'
    glob=scene['global_prompt']+'\nMy own scene lighting.\n'
    payload=edit_payload(client,pid)
    payload['scenes']={'scene':{'global_prompt':glob,'prompt_edited':True,'chapters':{'shot':{'shot_prompt':shot,'prompt_edited':True}}}}
    assert client.put('/api/projects/'+pid+'/delivery',json=payload).status_code==200
    saved=client.get('/api/projects/'+pid).json()['delivery']['scenes'][0]
    assert saved['global_prompt']==glob
    assert saved['chapters'][0]['shot_prompt']==shot
    assert store.project(pid)==before and store.assets(pid)==assets and not store.jobs(pid)
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+pid+'/export').content)) as z:
        assert z.read('ref2/scenes/scene/global.txt').decode()==glob
        assert z.read('ref2/scenes/scene/chapters/shot/shot.txt').decode()==shot
    assert client.put('/api/projects/'+pid+'/delivery',json=payload).status_code==400
