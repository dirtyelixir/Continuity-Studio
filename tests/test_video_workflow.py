import copy,io,json,zipfile
import pytest
from studio import store,engine,models,video_workflow as video,delivery
from test_production import client,plan,create,add_asset


def configure(client,pid,**fields):
    return client.put(f'/api/projects/{pid}/video-workflow/shot',json={'revision':video.config(pid)['revision'],**fields})

def begin(client,pid,cap='h3_video_prompt'):
    client.post('/api/settings/routing',json={'capability':cap,'provider_id':'manual'})
    r=client.post(f'/api/projects/{pid}/jobs',json={'capability':cap,'target_id':'shot'})
    assert r.status_code==200,r.text
    return r.json()['job']

def output(job):
    src=job['input']['video_source']
    return src['alignment']+'\n\nintegrated_multimodal_description: [Shot 1] One continuous 6-second shot. Ada raises her hand and presses the switch. At 3 to 4 seconds Ada says <d>[English] Light.</d>\n\noverall_soundscape: Wind and a switch click.\n\nnon_diegetic_music: N/A'

def finish(client,job,text=None):
    r=client.post('/api/jobs/'+job['id']+'/manual',json={'text':text or output(job)})
    assert r.status_code==200,r.text

def adopt(client,pid,j):
    return client.post(f'/api/projects/{pid}/video-workflow/adopt/'+j['id'],json={'revision':video.config(pid)['revision']})


def test_explicit_mode_missing_rejected_frames_never_fall_back(client,plan):
    pid=create(client,plan)
    p=client.get('/api/projects/'+pid).json();row=p['video_workflow']['shots'][0]
    assert row['mode']=='I2VA' and not row['ready'] and not row['selected']
    assert client.get(f'/api/projects/{pid}/video-workflow/shot/packet').status_code==400
    add_asset(pid,plan,'start',status='pending');add_asset(pid,plan,'end')
    assert client.post(f'/api/projects/{pid}/jobs',json={'capability':'h3_video_prompt','target_id':'shot'}).status_code==400
    first=add_asset(pid,plan,'start');p=store.project(pid)
    src=video.prompt_source(p,'shot')
    assert src['mode']=='I2VA' and len(src['references'])==1 and src['references'][0]['asset_id']==first
    assert configure(client,pid,mode='FL2VA').status_code==200
    assert len(video.prompt_source(p,'shot')['references'])==2
    assert configure(client,pid,mode='REF2VA').status_code==200
    with pytest.raises(ValueError,match='Ref2VA'):video.prompt_source(p,'shot')
    assert client.put(f'/api/projects/{pid}/video-workflow/shot',json={'revision':0,'mode':'I2VA'}).status_code==400


def test_candidate_adoption_edit_export_and_exact_images(client,plan):
    pid=create(client,plan);first=add_asset(pid,plan,'start');last=add_asset(pid,plan,'end')
    original=store.project(pid);assets=store.assets(pid);ref=delivery.project_bundle(original)
    assert configure(client,pid,mode='FL2VA').status_code==200
    j=begin(client,pid);assert begin(client,pid)['id']==j['id']
    assert len(j['input']['images'])==2 and 'Picture 2' in j['input']['video_source']['alignment']
    finish(client,j)
    row=client.get('/api/projects/'+pid).json()['video_workflow']['shots'][0]
    assert not row['ready'] and not row['jobs']['h3_video_prompt']['stale']
    assert adopt(client,pid,j).status_code==200
    packet=client.get(f'/api/projects/{pid}/video-workflow/shot/packet').json()
    assert packet['mode']=='FL2VA' and packet['director_task']=='fl2v'
    assert packet['global_prompt']=='' and packet['guide_from_previous'] is False
    assert [r['asset_id'] for r in packet['references']]==[first,last]
    assert packet['text']==output(j)
    row=client.get('/api/projects/'+pid).json()['video_workflow']['shots'][0]
    edited=output(j).replace('Wind and','Low wind and')
    assert configure(client,pid,text=edited,source_hash=row['source_hash']).status_code==200
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+pid+'/export').content)) as z:
        assert z.read('video-workflow/FL2VA/shot/prompt.txt').decode()==edited
        assert json.loads(z.read('video-workflow/FL2VA/shot/handoff.json'))['text']==edited
        for r in packet['references']:assert r['path'] in z.namelist()
        assert 'ref2/scenes/scene/chapters/shot/shot.txt' in z.namelist()
    assert store.project(pid)==original and store.assets(pid)==assets and delivery.project_bundle(original)==ref


def test_stale_mode_frame_canon_and_cross_project_rejection(client,plan):
    pid=create(client,plan);first=add_asset(pid,plan,'start');add_asset(pid,plan,'end');j=begin(client,pid);finish(client,j)
    other=create(client,plan)
    assert adopt(client,other,j).status_code==400
    configure(client,pid,mode='FL2VA');assert adopt(client,pid,j).status_code==400
    configure(client,pid,mode='I2VA');assert adopt(client,pid,j).status_code==200
    with store.db() as c:c.execute('UPDATE assets SET status="rejected" WHERE id=?',(first,))
    assert client.get(f'/api/projects/{pid}/video-workflow/shot/packet').status_code==400
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+pid+'/export').content)) as z:assert 'video-workflow/FL2VA/shot/prompt.txt' not in z.namelist()
    add_asset(pid,plan,'start')
    assert adopt(client,pid,j).status_code==400
    assert client.get('/api/projects/'+pid).json()['video_workflow']['shots'][0]['jobs']['h3_video_prompt']['stale']


def test_prompt_validation_and_latest_manually_saved_dialogue(client,plan):
    pid=create(client,plan);add_asset(pid,plan,'start');j=begin(client,pid);src=j['input']['video_source'];good=output(j)
    for bad in [good.replace('Light.','New words.'),good+'\n<Subject 1>',good+'\nPicture 2',good.replace('integrated_multimodal_description:','summary:'),good.replace('0.00 seconds','1.00 seconds')]:
        with pytest.raises(ValueError):video.validate_prompt(bad,src)
    cfg=delivery.configuration(pid);scene=delivery.project_bundle(store.project(pid))['scenes'][0];text=scene['chapters'][0]['shot_prompt'].replace('Light.','Ready.')
    cfg.update(production_revision=1,scenes={'scene':{'global_prompt':scene['global_prompt'],'chapters':{'shot':{'shot_prompt':text,'prompt_edited':True}}}})
    delivery.save_configuration(pid,cfg)
    current=video.prompt_source(store.project(pid),'shot');video.validate_prompt(good.replace('Light.','Ready.'),current)
    with pytest.raises(ValueError):video.validate_prompt(good,current)
    assert adopt(client,pid,j).status_code==400


def test_strategy_exact_evidence_reviewable_and_no_render(client,plan):
    pid=create(client,plan);original=store.project(pid);j=begin(client,pid,'h3_strategy')
    result={'mode':'FL2VA','reason':'The final raised hand merits an ending anchor.','evidence':['Raise hand and press switch'],
        'start_blueprint':'Ada left, hand lowered; medium eye-level.','end_blueprint':'Ada left, hand raised; same medium view.',
        'checks':['Does the hand match canon?','Is Ada on the left?']}
    bad=copy.deepcopy(result);bad['evidence']=['Invented ungrounded claim']
    assert client.post('/api/jobs/'+j['id']+'/manual',json=bad).status_code==400
    assert client.post('/api/jobs/'+j['id']+'/manual',json=result).status_code==200
    assert video.config(pid)['shots']=={}
    assert adopt(client,pid,j).status_code==200
    assert video.config(pid)['shots']['shot']['mode']=='FL2VA'
    assert store.project(pid)==original and not store.assets(pid)
    assert len(store.jobs(pid))==1


def test_changed_adopted_blueprint_requires_new_frame_before_video_handoff(client,plan):
    pid=create(client,plan);add_asset(pid,plan,'start')
    first=begin(client,pid,'h3_strategy')
    original={'mode':'I2VA','reason':'The opening composition anchors the action.','evidence':['Raise hand and press switch'],
        'start_blueprint':'Ada left, hand lowered; medium eye-level.','end_blueprint':'',
        'checks':['Does Ada remain on the left?','Is the hand lowered at time zero?']}
    r=client.post('/api/jobs/'+first['id']+'/manual',json=original);assert r.status_code==200,r.text
    assert adopt(client,pid,first).status_code==200
    prompt=begin(client,pid);finish(client,prompt);assert adopt(client,pid,prompt).status_code==200
    before=client.get('/api/projects/'+pid).json()['video_workflow']['shots'][0]
    assert before['ready']

    changed=begin(client,pid,'h3_strategy')
    revised=dict(original,start_blueprint='Ada right, hand lowered; tight eye-level.')
    assert client.post('/api/jobs/'+changed['id']+'/manual',json=revised).status_code==200
    assert adopt(client,pid,changed).status_code==200
    row=client.get('/api/projects/'+pid).json()['video_workflow']['shots'][0]
    assert not row['ready']
    assert any('藍圖已更新' in reason for reason in row['reasons'])
    assert client.get(f'/api/projects/{pid}/video-workflow/shot/packet').status_code==400
    with pytest.raises(ValueError,match='藍圖已更新'):
        video.prompt_source(store.project(pid),'shot')


def test_add_missing_tail_preserves_frozen_start_and_effective_ref_prompts(client,plan):
    plan['shots'][0]['keyframes']=plan['shots'][0]['keyframes'][:1]
    pid=create(client,plan);a=add_asset(pid,plan,'start');b=add_asset(pid,plan,'ada')
    cfg=delivery.configuration(pid);scene=delivery.project_bundle(store.project(pid))['scenes'][0]
    manual=scene['chapters'][0]['shot_prompt'].replace('Light.','Ready.')
    cfg.update(production_revision=1,scenes={'scene':{'global_prompt':scene['global_prompt'],'chapters':{'shot':{'shot_prompt':manual,'prompt_edited':True}}}});delivery.save_configuration(pid,cfg)
    before=store.assets(pid)
    r=client.post(f'/api/projects/{pid}/video-workflow/shot/frame',json={'revision':1,'moment':'end','description':'Ada left; hand raised.'})
    assert r.status_code==200,r.text
    p=store.project(pid);assert p['revision']==2 and len(p['production']['shots'][0]['keyframes'])==2
    after={a['id']:a for a in store.assets(pid)}
    assert after[a]['status']=='approved' and after[b]==next(x for x in before if x['id']==b)
    assert video.frames(p,p['production']['shots'][0],'I2VA')[0]['ready']
    scene2=delivery.project_bundle(p)['scenes'][0]
    assert scene2['global_prompt']==scene['global_prompt'] and scene2['chapters'][0]['shot_prompt']==manual
    assert client.post(f'/api/projects/{pid}/video-workflow/shot/frame',json={'revision':2,'moment':'end','description':'Another ending'}).status_code==400
    changed=copy.deepcopy(p['production']);changed['shots'][0]['blocking']='Ada right';engine.save_plan(pid,changed,2,'Actual blocking change')
    assert next(x for x in store.assets(pid) if x['id']==a)['status']=='stale'


def test_image_concerns_do_not_replace_complete_prompt_or_block_human_adoption(client,plan):
    pid=create(client,plan);add_asset(pid,plan,'start');j=begin(client,pid)
    issues=['首幀人物站在另一側；請自行決定是否修圖。']
    r=client.post('/api/jobs/'+j['id']+'/manual',json={'text':'','frame_issues':issues})
    assert r.status_code==400
    r=client.post('/api/jobs/'+j['id']+'/manual',json={'text':output(j),'frame_issues':issues})
    assert r.status_code==200,r.text
    assert adopt(client,pid,j).status_code==200
    packet=client.get(f'/api/projects/{pid}/video-workflow/shot/packet').json()
    assert packet['text']==output(j) and packet['frame_issues']==issues
    assert issues[0] not in packet['text']
    assert client.get('/api/projects/'+pid).json()['video_workflow']['shots'][0]['ready']


def test_cosmetic_linebreak_normalization_preserves_exact_alignment_and_dialogue_scope(client,plan):
    pid=create(client,plan);add_asset(pid,plan,'start');j=begin(client,pid);src=j['input']['video_source']
    result={'text':output(j).replace('\n\nintegrated','\nintegrated'),'frame_issues':[]}
    video.validate_result(result,src);assert result['text']==output(j)
    with pytest.raises(ValueError):video.validate_prompt(output(j)+'\n<d>[English] More.</d>',src)
