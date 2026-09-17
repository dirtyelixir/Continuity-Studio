import copy,io,json,zipfile
import pytest
from studio import delivery,engine,models,shot_prompts,store
from test_production import client,plan,create
from test_shot_references import setup_props


def start(client,pid,source=None):
    client.post('/api/settings/routing',json={'capability':'h3_shot','provider_id':'manual'})
    req={'capability':'h3_shot','target_id':'shot','feedback':'Make the action clearer.'}
    if source is not None:req['source_prompt']=source
    r=client.post('/api/projects/'+pid+'/jobs',json=req);assert r.status_code==200,r.text
    return r.json()['job']


def finish(client,job):
    text=job['input']['shot_prompt_source']['current_prompt'].replace('detailed_description:','detailed_description:\nKeep the camera fixed and the action legible.',1)
    r=client.post('/api/jobs/'+job['id']+'/manual',json={'text':text});assert r.status_code==200,r.text
    return text


def test_regeneration_from_draft_is_reviewable_and_adoption_changes_only_one_shot(client,plan):
    pid=setup_props(client,plan);p=store.project(pid);assets=store.assets(pid)
    before=client.get('/api/projects/'+pid).json();scene=before['delivery']['scenes'][0]
    draft=scene['chapters'][0]['shot_prompt']+'\nEditorial draft.'
    job=start(client,pid,draft)
    assert job['input']['source_prompt']==draft and not job['input']['images']
    assert job['input']['shot_prompt_source']['current_prompt']==scene['chapters'][0]['shot_prompt']
    assert start(client,pid,draft)['id']==job['id']
    conflict=client.post('/api/projects/'+pid+'/jobs',json={'capability':'h3_shot','target_id':'shot','source_prompt':'Different draft'})
    assert conflict.status_code==400
    text=finish(client,job)
    ready=client.get('/api/projects/'+pid).json()
    assert ready['delivery']['scenes'][0]['chapters'][0]['shot_prompt']==scene['chapters'][0]['shot_prompt']
    assert ready['shot_prompt_regenerations']['shot']['state']=='succeeded'
    assert not ready['shot_prompt_regenerations']['shot']['stale']
    adopted=client.post('/api/projects/'+pid+'/shot-prompts/'+job['id']+'/adopt',json={})
    assert adopted.status_code==200,adopted.text
    after=client.get('/api/projects/'+pid).json();result=after['delivery']['scenes'][0]
    assert result['global_prompt']==scene['global_prompt']
    assert result['chapters'][0]['shot_prompt']==text
    assert result['chapters'][1]['shot_prompt']==scene['chapters'][1]['shot_prompt']
    assert not result['chapters'][0]['issues']
    assert after['shot_prompt_regenerations']['shot']['adopted']
    assert store.project(pid)==p and store.assets(pid)==assets
    again=client.post('/api/projects/'+pid+'/shot-prompts/'+job['id']+'/adopt',json={})
    assert again.json()['revision']==adopted.json()['revision']
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+pid+'/export').content)) as z:
        assert z.read('ref2/scenes/scene/chapters/shot/shot.txt').decode()==text
    assert store.job(job['id'])['input']['source_prompt']==draft


def test_stale_global_and_foreign_job_cannot_overwrite_current_prompt(client,plan):
    pid=setup_props(client,plan);job=start(client,pid);finish(client,job)
    other=create(client,plan)
    assert client.post('/api/projects/'+other+'/shot-prompts/'+job['id']+'/adopt',json={}).status_code==400
    cfg=delivery.configuration(pid);cfg['scenes']={'scene':{'global_prompt':job['input']['shot_prompt_source']['global_prompt']+'\nCooler lighting.','prompt_edited':True,'chapters':{}}}
    store.put_setting('delivery:'+pid,cfg)
    r=client.post('/api/projects/'+pid+'/shot-prompts/'+job['id']+'/adopt',json={})
    assert r.status_code==400 and '已更新' in r.text
    assert client.get('/api/projects/'+pid).json()['shot_prompt_regenerations']['shot']['stale']


def test_unrelated_shot_edit_survives_adoption(client,plan):
    pid=setup_props(client,plan);job=start(client,pid);text=finish(client,job)
    scene=delivery.scene_bundle(store.project(pid),plan['scenes'][0]);other=scene['chapters'][1]['shot_prompt']+'\nKeep this saved direction.'
    cfg=delivery.configuration(pid);cfg['scenes']={'scene':{'chapters':{'shot2':{'shot_prompt':other,'prompt_edited':True}}}}
    store.put_setting('delivery:'+pid,cfg)
    r=client.post('/api/projects/'+pid+'/shot-prompts/'+job['id']+'/adopt',json={});assert r.status_code==200,r.text
    result=delivery.scene_bundle(store.project(pid),plan['scenes'][0])
    assert result['chapters'][0]['shot_prompt']==text and result['chapters'][1]['shot_prompt']==other


def test_invalid_dialogue_labels_and_extra_global_rejected(client,plan):
    pid=setup_props(client,plan);job=start(client,pid);source=job['input']['shot_prompt_source'];text=source['current_prompt']
    for bad in [text.replace('Light.','Extra words.'),text+'\n<Picture 9>',text+'\nsubject_definitions: duplicate']:
        with pytest.raises(ValueError):shot_prompts.validate({'text':bad},source)
    assert store.job(job['id'])['state']=='awaiting_input'


def test_ready_scene_required_but_missing_images_do_not_block_text_regeneration(client,plan):
    pid=setup_props(client,plan,False);job=start(client,pid)
    assert job['state']=='awaiting_input'
    plain=create(client,plan)
    r=client.post('/api/projects/'+plain+'/jobs',json={'capability':'h3_shot','target_id':'shot'})
    assert r.status_code==400 and '英文提示詞整理' in r.text


def test_shared_original_names_are_allowed_even_when_character_is_not_in_this_shot(client,plan):
    from test_production import add_asset
    pid=setup_props(client,plan)
    p=store.project(pid);p['production']['canon'].append({'id':'other','kind':'character','name':'黃太','description':'A woman.','facts':[]})
    scene,chapter=shot_prompts.locate(p,'shot')
    extra={'target_id':'other','asset_id':'other-image','label':'Picture 4','subject':'Subject 4','role':'character','name':'黃太'}
    chapter['references'].append(extra);scene['global_prompt']+='\n<Subject 4> is 黃太 from <Picture 4>.'
    source=shot_prompts.basis(p,scene,chapter)
    shot_prompts.validate({'text':chapter['shot_prompt']},source)
