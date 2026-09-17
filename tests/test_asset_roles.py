import copy,io
import pytest
from studio import asset_roles,models,store,engine,continuity,delivery,postproduction,h3,storyboarding
from test_production import client,plan,create,add_asset


def with_voice(plan):
    p=copy.deepcopy(plan)
    p['canon'].append({'id':'radio_voice','kind':'voice','name':'Broadcast','description':'Unseen radio voice','facts':['Never visible'],'scope':'scene'})
    p['shots'][0]['entity_ids'].append('radio_voice')
    p['shots'][0]['dialogue'][0]['entity_id']='radio_voice'
    return models.Production.model_validate(p).model_dump()


def test_voice_is_audio_not_visual_dependency(client,plan):
    p=with_voice(plan);pid=create(client,p)
    ada=add_asset(pid,p,'ada');room=add_asset(pid,p,'room')
    refs,missing=continuity.references(p,store.assets(pid),'start')
    assert not missing and [a['id'] for a in refs]==[ada,room]
    refs,missing=delivery.refs_for_scene(p,p['scenes'][0],store.assets(pid))
    assert not missing and 'radio_voice' not in [r['target_id'] for r in refs]
    prompt=continuity.image_prompt(p,'start',refs)
    assert 'never depict their speakers' in prompt
    assert not any(e['kind']=='voice' for e in continuity.context(p,'start')['canon'])
    text=h3.compile_shot(p,p['shots'][0],[])['text']
    assert 'Light.' in text and 'Audio-only identities' in text
    assert 'never depict their speakers' in delivery.chapter_draft(p,p['shots'][0],refs)
    assert postproduction.character(pid,'radio_voice')['kind']=='voice'
    assert any(v['character_id']=='radio_voice' for v in client.get(f'/api/projects/{pid}').json()['postproduction']['profiles'])
    assert not store.jobs(pid)


def test_api_blocks_voice_image_jobs_and_uploads(client,plan):
    pid=create(client,with_voice(plan));url=f'/api/projects/{pid}'
    r=client.post(url+'/jobs',json={'capability':'image','target_id':'radio_voice'})
    assert r.status_code==400 and '聲音資產' in r.text
    r=client.post(url+'/upload/radio_voice',files={'file':('image.png',b'not-an-image','image/png')})
    assert r.status_code==400 and '聲音資產' in r.text
    assert not store.jobs(pid) and not store.assets(pid)


def test_scope_only_does_not_stale_approved_images(client,plan):
    pid=create(client,plan);aid=add_asset(pid,plan,'ada');fid=add_asset(pid,plan,'start')
    prior=continuity.target_hash(plan,'ada');frame_prior=continuity.target_hash(plan,'start')
    changed=copy.deepcopy(plan);changed['canon'][0]['scope']='public'
    assert continuity.target_hash(changed,'ada')==prior
    assert continuity.target_hash(changed,'start')==frame_prior
    engine.save_plan(pid,changed,1,'Move protagonist to public')
    assert all(a['status']=='approved' for a in store.assets(pid))
    assert asset_roles.groups(changed)['public_ids']==['ada']
    assert asset_roles.groups(changed)['chapters'][0]['scenes'][0]['entity_ids']==['room']


def test_legacy_scope_hash_and_cross_chapter_reuse(plan):
    p=copy.deepcopy(plan)
    for e in p['canon']:e.pop('scope',None)
    assert continuity.target_hash(p,'ada')==continuity.target_hash(models.Production.model_validate(p).model_dump(),'ada')
    scene=copy.deepcopy(p['scenes'][0]);scene['id']='scene2';p['scenes'].append(scene)
    shot=copy.deepcopy(p['shots'][0]);shot['id']='shot2';shot['scene_id']='scene2'
    for f in shot['keyframes']:f['id']+='2'
    p['shots'].append(shot)
    p['chapters']=[{'id':str(i),'title':f'Chapter {i}','story':'','screenplay':'','scene_ids':[sid]} for i,sid in enumerate(('scene','scene2'))]
    groups=asset_roles.groups(p)
    assert set(groups['public_ids'])=={'ada','room'}
    assert all(sc['public_ids']==['ada','room'] and not sc['entity_ids'] for c in groups['chapters'] for sc in c['scenes'])


def test_voice_not_counted_in_image_slot_limit(plan):
    p=with_voice(plan)
    for i in range(5):
        voice=copy.deepcopy(p['canon'][-1]);voice['id']=f'voice_{i}';p['canon'].append(voice);p['shots'][0]['entity_ids'].append(voice['id'])
    source={'source_kind':'screenplay','source_text':p['screenplay'],'units':[{'id':'P001','text':p['screenplay']}],'reference_limit':5}
    proposal={'production':p,'coverage':[{'source_id':'P001','shot_ids':['shot'],'treatment':'Source preserved'}],'adaptation_notes':[]}
    storyboarding.validate(proposal,source)


def test_planning_contract_covers_main_protagonist_and_audio(client,plan):
    pid=create(client,plan)
    inp,_=engine.build_input(store.project(pid),models.JobRequest(capability='narrative'))
    assert 'scope=public for the main protagonist' in inp['prompt']
    assert 'kind=voice' in inp['prompt']


def test_multiple_public_assets_save_independently(client,plan):
    pid=create(client,plan)
    add_asset(pid,plan,'ada');add_asset(pid,plan,'room')
    url=f'/api/projects/{pid}'
    for target,scope,expected in [('ada','public',['ada']),('room','public',['ada','room']),('ada','scene',['room'])]:
        current=client.get(url).json()
        updated=copy.deepcopy(current['production'])
        next(e for e in updated['canon'] if e['id']==target)['scope']=scope
        response=client.put(url+'/plan',json={'revision':current['revision'],'production':updated})
        assert response.status_code==200
        saved=client.get(url).json()
        assert saved['asset_groups']['public_ids']==expected
        assert saved['production']['shots']==plan['shots']
        assert saved['production']['scenes']==plan['scenes']
        assert all(a['status']=='approved' for a in store.assets(pid))
