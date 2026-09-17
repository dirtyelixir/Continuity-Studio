import io,zipfile
import pytest
from studio import delivery,scene_prompts,store
from test_production import client,plan,create
from test_shot_references import setup_props


def start(client,pid,source=None):
    client.post('/api/settings/routing',json={'capability':'h3_global','provider_id':'manual'})
    req={'capability':'h3_global','target_id':'scene','feedback':'Keep lighting restrained.'}
    if source is not None:req['source_prompt']=source
    r=client.post('/api/projects/'+pid+'/jobs',json=req)
    assert r.status_code==200,r.text
    return r.json()['job']


def finish(client,job):
    text=job['input']['scene_prompt_source']['current_prompt']+'\nKeep the scene lighting restrained.'
    r=client.post('/api/jobs/'+job['id']+'/manual',json={'text':text})
    assert r.status_code==200,r.text
    return text


def test_draft_candidate_review_and_adoption_preserve_all_shots(client,plan):
    pid=setup_props(client,plan);before=client.get('/api/projects/'+pid).json();scene=before['delivery']['scenes'][0]
    original=store.project(pid);assets=store.assets(pid);draft=scene['global_prompt']+'\nEditable draft.'
    job=start(client,pid,draft)
    assert job['input']['source_prompt']==draft and not job['input']['images']
    assert start(client,pid,draft)['id']==job['id']
    assert client.post('/api/projects/'+pid+'/jobs',json={'capability':'h3_global','target_id':'scene','source_prompt':'Different draft'}).status_code==400
    text=finish(client,job);ready=client.get('/api/projects/'+pid).json()
    assert ready['delivery']==before['delivery']
    assert ready['scene_prompt_regenerations']['scene']['state']=='succeeded'
    assert not ready['scene_prompt_regenerations']['scene']['stale']
    r=client.post('/api/projects/'+pid+'/scene-prompts/'+job['id']+'/adopt',json={});assert r.status_code==200,r.text
    after=client.get('/api/projects/'+pid).json();result=after['delivery']['scenes'][0]
    assert result['global_prompt']==text
    assert [c['shot_prompt'] for c in result['chapters']]==[c['shot_prompt'] for c in scene['chapters']]
    assert all(not c['issues'] for c in result['chapters'])
    assert after['scene_prompt_regenerations']['scene']['adopted']
    assert store.project(pid)==original and store.assets(pid)==assets
    assert client.post('/api/projects/'+pid+'/scene-prompts/'+job['id']+'/adopt',json={}).json()['revision']==r.json()['revision']
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+pid+'/export').content)) as z:
        assert z.read('ref2/scenes/scene/global.txt').decode()==text
        for c in scene['chapters']:assert z.read('ref2/scenes/scene/chapters/'+c['shot_id']+'/shot.txt').decode()==c['shot_prompt']


def test_stale_shot_edit_and_foreign_job_reject_adoption(client,plan):
    pid=setup_props(client,plan);job=start(client,pid);finish(client,job)
    other=create(client,plan)
    assert client.post('/api/projects/'+other+'/scene-prompts/'+job['id']+'/adopt',json={}).status_code==400
    assert client.post('/api/projects/'+pid+'/shot-prompts/'+job['id']+'/adopt',json={}).status_code==400
    cfg=delivery.configuration(pid);text=job['input']['scene_prompt_source']['chapters'][1]['shot_prompt']+'\nSaved new direction.'
    cfg['scenes']={'scene':{'chapters':{'shot2':{'shot_prompt':text,'prompt_edited':True}}}};store.put_setting('delivery:'+pid,cfg)
    r=client.post('/api/projects/'+pid+'/scene-prompts/'+job['id']+'/adopt',json={})
    assert r.status_code==400 and '已更新' in r.text
    assert client.get('/api/projects/'+pid).json()['scene_prompt_regenerations']['scene']['stale']


def test_invalid_global_sections_and_reference_mappings_rejected(client,plan):
    pid=setup_props(client,plan);job=start(client,pid);source=job['input']['scene_prompt_source'];text=source['current_prompt']
    scene_prompts.validate({'text':text},source)
    for bad in [text+'\nsummary: shot action',text+'\n<d>Extra dialogue</d>',text+'\nsubject_definitions:',text+'\n<Subject 9> from <Picture 9>.',text.replace('<Picture 1>','<Picture 2>'),text+'x'*7000]:
        with pytest.raises(ValueError):scene_prompts.validate({'text':bad},source)


def test_preparation_required_images_optional(client,plan):
    pid=setup_props(client,plan,False);assert start(client,pid)['state']=='awaiting_input'
    other=create(client,plan)
    r=client.post('/api/projects/'+other+'/jobs',json={'capability':'h3_global','target_id':'scene'})
    assert r.status_code==400 and '英文提示詞整理' in r.text


def test_existing_manual_dialogue_edit_does_not_block_global_only_change(client,plan):
    pid=setup_props(client,plan);scene=delivery.scene_bundle(store.project(pid),plan['scenes'][0])
    edited=scene['chapters'][0]['shot_prompt'].replace('Light.','Ready.')
    cfg=delivery.configuration(pid);cfg['scenes']={'scene':{'chapters':{'shot':{'shot_prompt':edited,'prompt_edited':True}}}};store.put_setting('delivery:'+pid,cfg)
    job=start(client,pid);text=finish(client,job)
    r=client.post('/api/projects/'+pid+'/scene-prompts/'+job['id']+'/adopt',json={});assert r.status_code==200,r.text
    after=delivery.scene_bundle(store.project(pid),plan['scenes'][0])
    assert after['global_prompt']==text and after['chapters'][0]['shot_prompt']==edited
    assert any('canonical dialogue' in issue for issue in after['chapters'][0]['issues'])
