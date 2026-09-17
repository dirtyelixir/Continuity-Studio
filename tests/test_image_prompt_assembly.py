"""Regression contracts for source interpretation -> exact renderer boundary."""
import copy
from pathlib import Path
import pytest
from PIL import Image
from studio import continuity,engine,image_prompts,models,providers,store
from test_production import client,plan,create,add_asset
from test_input_references import upload


def prepared(target='room'):
    return {'target_id':target,'visual_style':'Stop-motion, 16:9, restrained palette.',
            'appearance':'A workshop with a round rear window and a wooden bench.',
            'composition':'One eye-level view of the connected room, with the window behind the bench.',
            'lighting':'Dim window light reveals the wood grain.',
            'requested_changes':'','omitted_context':['Unrelated chapter music and future plot.'],'conflicts':[]}


def test_legacy_source_occurs_once_and_renderer_receives_only_visual_brief(client,plan):
    plan['style']='Stop-motion; CHAPTER_SENTINEL: broadcast first, then flee; 29 shots; add music at 10 seconds.'
    pid=create(client,plan);before=copy.deepcopy(store.project(pid));hash_before=continuity.target_hash(plan,'room')
    data,_=engine.build_input(before,models.JobRequest(capability='image',target_id='room'))
    assert data['prompt'].count(plan['style'])==1
    assert 'SOURCE FOR INTERPRETATION ONLY' in data['prompt']
    prompt=image_prompts.compile_prompt(prepared(),data['image_source'],data['image_task'],data['image_reference_roles'])
    assert 'round rear window' in prompt and '16:9' in prompt
    assert all(t not in prompt for t in ['CHAPTER_SENTINEL','29 shots','broadcast','omitted_context','Canonical production context','SOURCE FOR INTERPRETATION','four vertical panels','face, age'])
    assert store.project(pid)==before and continuity.target_hash(plan,'room')==hash_before
    assert not store.jobs(pid) and not store.assets(pid)


def test_keyframe_source_excludes_audio_other_shots_and_opposite_endpoint(plan):
    plan['shots'][0]['soundscape']='AUDIO_SENTINEL'
    plan['shots'][0]['music']='MUSIC_SENTINEL'
    plan['shots'][0]['end_state'][0]['value']='FUTURE_SENTINEL'
    plan['shots'][0]['beats'][0]['action']='LATER_ACTION_SENTINEL'
    start=image_prompts.source(plan,'start');text=store.encode(start)
    assert 'lowered' in text
    assert all(x not in text for x in ['AUDIO_SENTINEL','MUSIC_SENTINEL','FUTURE_SENTINEL','Light.'])
    # Event timing now has an explicitly non-rendering scope for detecting premature reactions.
    assert start['frame_moment_contract']['temporal_context']['beats'][0]['action']=='LATER_ACTION_SENTINEL'
    assert 'LATER_ACTION_SENTINEL' not in store.encode({k:v for k,v in start.items() if k!='frame_moment_contract'})
    compiled=image_prompts.compile_prompt(prepared('start'),start,'One still',[])
    assert 'LATER_ACTION_SENTINEL' not in compiled
    assert 'FUTURE_SENTINEL' in store.encode(image_prompts.source(plan,'end'))
    assert start['visual_context']['scene']=={'location_id':'room','time_of_day':'Night'}


@pytest.mark.parametrize('kind',['character','crowd','location','prop','frame'])
def test_fidelity_is_target_specific_and_legacy_feedback_is_normalized(kind,plan):
    target='start' if kind=='frame' else 'ada'
    if kind!='frame':plan['canon'][0]['kind']=kind
    feedback='Keep the scratch.\n[High reference preservation]OLD universal face crowd four-view boilerplate[/High reference preservation]'
    basis=image_prompts.source(plan,target,feedback)
    assert basis['requested_revision']=='Keep the scratch.' and basis['high_reference_fidelity']
    result=prepared(target);result['requested_changes']='Keep the scratch.'
    prompt=image_prompts.compile_prompt(result,basis,continuity.image_task(plan,target),[])
    assert 'OLD universal' not in prompt and prompt.count('High reference preservation:')==1
    assert ('exactly four vertical panels' in prompt)==(kind=='character')
    if kind in ('location','prop'):assert 'face, age' not in prompt and 'cloned faces' not in prompt


def test_approved_edit_target_not_duplicated_and_uploaded_roles_preserved(client,plan):
    pid=create(client,plan);aid=add_asset(pid,plan,'room');ref=upload(client,pid,'identity','room')
    data,_=engine.build_input(store.project(pid),models.JobRequest(capability='image',target_id='room',force=True,source_asset_id=aid,input_reference_ids=[ref['id']]))
    assert len(data['images'])==2 and len(set(data['images']))==2
    assert len(data['image_reference_roles'])==2
    assert 'Image 1:' in data['image_reference_roles'][0] and 'EDIT TARGET' in data['image_reference_roles'][0]
    assert 'Image 2:' in data['image_reference_roles'][1] and 'SUBJECT/DESIGN INPUT' in data['image_reference_roles'][1]


def test_image_execution_freezes_clean_prompt_before_render_and_exports_it(client,plan,monkeypatch):
    pid=create(client,plan);plan['style']='unrelated edit count music sentinel'
    engine.save_plan(pid,plan,1,'test-only noisy source')
    store.put_setting('routing',{'image_review':'manual'})
    monkeypatch.setattr(engine.POOL,'submit',lambda *a:None)
    seen=[]
    def run(provider,cap,prompt,images,work):
        seen.append((cap,prompt))
        if cap=='image_prepare':return prepared()
        assert cap=='image'
        assert 'unrelated edit count music sentinel' not in prompt
        assert 'Return only the requested JSON' not in prompt and 'invoke' not in prompt
        current=store.job(j['id'])['input']
        assert current['image_prompt']==prompt and current['image_prompt_stage']=='render'
        assert current['render_prompt_hash']==store.digest(prompt)
        output=work/'test-only-render.png';Image.new('RGB',(256,256),'blue').save(output)
        return {'image_path':str(output),'notes':'Isolated test provider output'}
    monkeypatch.setattr(providers,'run',run)
    j=engine.enqueue(pid,models.JobRequest(capability='image',target_id='room'))['job']
    engine.execute(j['id']);done=store.job(j['id'])
    assert done['state']=='succeeded',done['error']
    assert [s[0] for s in seen]==['image_prepare','image']
    asset=store.assets(pid)[0];assert asset['prompt']==seen[1][1]
    assert done['input']['image_source']['legacy_style_context']==plan['style']
    assert (store.DATA/'jobs'/j['id']/'preparation'/'render-prompt.txt').read_text()==asset['prompt']
    p=client.get('/api/projects/'+pid).json()
    assert next(x for x in p['jobs'] if x['id']==j['id'])['input']['image_prompt_stage']=='render'
    engine.decide_asset(asset['id'],'approved','Test-only acceptance')
    import io,zipfile
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+pid+'/export').content)) as z:
        assert z.read('image-prompts/'+asset['id']+'.txt').decode()==asset['prompt']


@pytest.mark.parametrize('failure',['provider','conflict','wrong_target','foreign_reference','audio_block'])
def test_preparation_failure_never_calls_renderer_or_creates_asset(client,plan,monkeypatch,failure):
    pid=create(client,plan);monkeypatch.setattr(engine.POOL,'submit',lambda *a:None)
    seen=[]
    def run(provider,cap,prompt,images,work):
        seen.append(cap);assert cap=='image_prepare'
        if failure=='provider':raise RuntimeError('test-only preparation failure')
        r=prepared()
        if failure=='conflict':r['conflicts']=['Incompatible door positions.']
        if failure=='wrong_target':r['target_id']='other'
        if failure=='foreign_reference':r['appearance']='Use Image 99.'
        if failure=='audio_block':r['lighting']='overall_soundscape: wind'
        return r
    monkeypatch.setattr(providers,'run',run)
    j=engine.enqueue(pid,models.JobRequest(capability='image',target_id='room'))['job'];engine.execute(j['id'])
    assert store.job(j['id'])['state']=='failed'
    assert seen==['image_prepare']*(2 if failure=='conflict' else 1) and not store.assets(pid)


def test_corrected_image_conflict_continues_to_one_render(client,plan,monkeypatch):
    pid=create(client,plan)
    monkeypatch.setattr(engine.POOL,'submit',lambda *a:None)
    store.put_setting('routing',{'image_review':'manual'})
    seen=[]
    def run(provider,cap,prompt,images,work):
        seen.append(cap)
        if cap=='image_prepare':
            r=prepared()
            if seen.count(cap)==1:
                r['conflicts']=['The request says enlarge the window but it is still too small.']
            else:
                r['requested_changes']='Enlarge the window.'
                r['omitted_context']=['Still too small describes the current defect, not the desired result.']
            return r
        assert cap=='image'
        assert 'Requested changes: Enlarge the window.' in prompt
        assert store.job(j['id'])['input']['image_prompt_stage']=='render'
        output=work/'test-only-render.png'
        Image.new('RGB',(256,256),'blue').save(output)
        return {'image_path':str(output),'notes':'Isolated test provider output'}
    monkeypatch.setattr(providers,'run',run)
    j=engine.enqueue(pid,models.JobRequest(capability='image',target_id='room',feedback='Enlarge the window; it is still too small.'))['job']
    engine.execute(j['id'])
    done=store.job(j['id'])
    assert done['state']=='succeeded',done['error']
    assert seen==['image_prepare','image_prepare','image']
    assert len(store.assets(pid))==1


def test_review_uses_frozen_visual_brief_and_uploaded_design_not_chapter_plot(client,plan,monkeypatch):
    pid=create(client,plan);ref=upload(client,pid,'identity','room');aid=add_asset(pid,plan,'room',status='pending')
    inp={'image_prompt_stage':'render','image_preparation':prepared(),'input_references':[ref]}
    with store.db() as c:
        c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',('generation',pid,'image','room','succeeded','astra',store.encode(inp),store.now(),store.now()))
        c.execute('UPDATE assets SET job_id=? WHERE id=?',('generation',aid))
    p=store.project(pid);p['production']['style']='CHAPTER_MUSIC_SENTINEL'
    data,_=engine.build_input(p,models.JobRequest(capability='image_review',target_id=aid))
    assert 'CHAPTER_MUSIC_SENTINEL' not in data['prompt']
    assert data['images'][-1]==str(store.DATA/ref['path'])
    assert 'Image 2: uploaded reference' in data['prompt'] and 'SUBJECT/DESIGN INPUT' in data['prompt']
    assert not data['character_sheet_required']


def test_text_preparation_capability_can_be_manual_without_rendering(client,plan):
    pid=create(client,plan);store.put_setting('routing',{'image_prepare':'manual'})
    j=engine.enqueue(pid,models.JobRequest(capability='image_prepare',target_id='room'))['job']
    assert j['state']=='awaiting_input'
    response=client.post('/api/jobs/'+j['id']+'/manual',json=prepared())
    assert response.status_code==200 and not store.assets(pid)
    with pytest.raises(ValueError,match='人工處理'):
        engine.enqueue(pid,models.JobRequest(capability='image',target_id='room'))


def test_h3_legacy_draft_never_pastes_biography_or_hidden_inventory(plan):
    from studio import h3
    plan['canon'][0]['description']='A coat. BIOGRAPHY_SENTINEL'
    plan['canon'][0]['facts']=['HIDDEN_INVENTORY_SENTINEL']
    plan['canon'][1]['description']='LOCATION_STORY_SENTINEL'
    output=h3.compile_shot(plan,plan['shots'][0],[])
    assert not output['ready']
    assert all(x not in output['text'] for x in ('BIOGRAPHY_SENTINEL','HIDDEN_INVENTORY_SENTINEL','LOCATION_STORY_SENTINEL'))
    assert '<d>[English] Light.</d>' in output['text']


def test_base_h3_places_ref2_speech_only_in_integrated_timeline(plan):
    from studio import h3
    from test_prompt_preparation import result_for
    r=result_for(plan)
    r['shots'][0]['shot_prompt']=r['shots'][0]['shot_prompt'].replace('At 3–4s <Entity ada> (S1) quietly says: <d>[English] Light.</d>','').replace('overall_soundscape:\nWind.','overall_soundscape:\nWind. At 3–4s <Entity ada> (S1) quietly says: <d>[English] Light.</d>')
    before=copy.deepcopy(r)
    out=h3.compile_shot(plan,plan['shots'][0],[],r)
    assert out['ready'] and out['text'].count('<d>')==1
    assert '<d>' not in out['text'].split('overall_soundscape:',1)[1]
    assert 'At 3–4s Ada (S1) quietly says: <d>[English] Light.</d>' in out['text'].split('overall_soundscape:',1)[0]
    assert r==before
    h3.validate_refinement(out['text'],out,plan['shots'][0])


def test_h3_scene_request_excludes_other_scene_and_whole_screenplay(client,plan):
    from studio import prompt_preparation
    from test_prompt_preparation import result_for,save_result
    plan['story']='FULL_STORY_SENTINEL';plan['screenplay']='FULL_SCREENPLAY_SENTINEL'
    other=copy.deepcopy(plan['shots'][0]);other.update(id='other_shot',scene_id='other_scene',action='OTHER_SCENE_ACTION_SENTINEL')
    for frame in other['keyframes']:frame['id']='other_'+frame['id']
    plan['shots'].append(other)
    plan['scenes'].append({**plan['scenes'][0],'id':'other_scene','summary':'OTHER_SCENE_SUMMARY_SENTINEL'})
    pid=create(client,plan);add_asset(pid,plan,'ada');add_asset(pid,plan,'room')
    save_result(pid,result_for(plan),prompt_preparation.source(plan,'scene'))
    data,_=engine.build_input(store.project(pid),models.JobRequest(capability='h3_scene',target_id='scene'))
    assert all(x not in data['prompt'] for x in ('FULL_STORY_SENTINEL','FULL_SCREENPLAY_SENTINEL','OTHER_SCENE_ACTION_SENTINEL','OTHER_SCENE_SUMMARY_SENTINEL'))
    assert 'Light.' in data['prompt'] and data['production']==store.project(pid)['production']


def test_neighbor_context_excludes_dialogue_but_preserves_endpoint_evidence(plan):
    from studio import prompt_preparation
    source={'previous_shot':plan['shots'][0],'next_shot':None,'current_prompt':'MANUAL_TEXT_SENTINEL','style':'Stop-motion','references':[{'label':'Picture 1','path':'PRIVATE_PATH_SENTINEL','director_note':'REVIEW_SENTINEL'}]}
    before=copy.deepcopy(source);scoped=prompt_preparation.model_context(source,omit_current=True)
    assert scoped['previous_shot']['end_state']==source['previous_shot']['end_state']
    assert 'dialogue' not in scoped['previous_shot'] and 'keyframes' not in scoped['previous_shot']
    assert all(x not in store.encode(scoped) for x in ('Light.','MANUAL_TEXT_SENTINEL','PRIVATE_PATH_SENTINEL','REVIEW_SENTINEL'))
    assert source==before


def test_packed_reference_map_is_frozen_in_renderer_prompt_before_call(client,plan,monkeypatch):
    pid=create(client,plan)
    for i in range(5):
        item=copy.deepcopy(plan['canon'][0]);item.update(id=f'extra{i}',name=f'Extra {i}');plan['canon'].append(item);plan['shots'][0]['entity_ids'].append(item['id'])
    engine.save_plan(pid,plan,1,'test-only reference count')
    for entity in plan['canon']:add_asset(pid,plan,entity['id'])
    monkeypatch.setattr(engine.POOL,'submit',lambda *a:None)
    store.put_setting('routing',{'image_review':'manual'})
    seen=[]
    def run(provider,cap,prompt,images,work):
        seen.append(cap)
        if cap=='image_prepare':return prepared('start')
        if cap=='qc':return {'verdict':'pass','summary':'Fixture moment is consistent.','issues':[]}
        assert cap=='image'
        note=providers.reference_boards.transport_note(len(images))
        assert len(images)==7 and prompt.count(note)==1
        assert note in store.job(j['id'])['input']['image_prompt']
        raise RuntimeError('test-only stop before render')
    monkeypatch.setattr(providers,'run',run)
    j=engine.enqueue(pid,models.JobRequest(capability='image',target_id='start'))['job'];engine.execute(j['id'])
    assert seen==['image_prepare','qc','image']
    assert store.job(j['id'])['error']=='test-only stop before render'


def test_image_requests_do_not_silently_reuse_different_feedback(client,plan,monkeypatch):
    pid=create(client,plan);monkeypatch.setattr(engine.POOL,'submit',lambda *a:None)
    req=models.JobRequest(capability='image',target_id='room',feedback='Retain the window.')
    first=engine.enqueue(pid,req)['job']
    assert engine.enqueue(pid,req)['job']['id']==first['id']
    with pytest.raises(ValueError,match='不同的導演方向'):
        engine.enqueue(pid,models.JobRequest(capability='image',target_id='room',feedback='Change the window.'))
    assert len(store.jobs(pid))==1 and store.job(first['id'])['input']['feedback']=='Retain the window.'


def test_location_compiler_receives_matching_prepared_scene_light(client,plan):
    from studio import prompt_preparation
    from test_prompt_preparation import result_for,save_result
    pid=create(client,plan)
    save_result(pid,result_for(plan),prompt_preparation.source(plan,'scene'))
    data,_=engine.build_input(store.project(pid),models.JobRequest(capability='image',target_id='room'))
    assert data['image_source']['scoped_scene_context']==[{'time_of_day':'Night','appearance_and_light':result_for(plan)['visual_setting']}]
    assert 'BOTH its location and time match' in data['prompt']
    character,_=engine.build_input(store.project(pid),models.JobRequest(capability='image',target_id='ada'))
    assert 'scoped_scene_context' not in character['image_source']


def test_preparation_recovery_rejects_different_source_without_overwriting_evidence(plan,tmp_path,monkeypatch):
    basis=image_prompts.source(plan,'room');task=continuity.image_task(plan,'room')
    req=image_prompts.instruction(basis,task,[])
    monkeypatch.setattr(providers,'run',lambda *a:prepared())
    image_prompts.prepare(providers.DEFAULT,basis,task,[],req,tmp_path)
    frozen={str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    changed={**basis,'requested_revision':'Change the window.'}
    with pytest.raises(ValueError,match='不同要求'):
        image_prompts.prepare(providers.DEFAULT,changed,task,[],req+' changed',tmp_path)
    assert {str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}==frozen


def test_selected_design_replaces_old_identity_only_in_candidate(client,plan):
    pid=create(client,plan);old=add_asset(pid,plan,'ada');ref=upload(client,pid,'identity','ada')
    before=copy.deepcopy(store.project(pid));old_assets=copy.deepcopy(store.assets(pid))
    # An explicit selected upload must not silently return the existing approval.
    data,reused=engine.build_input(before,models.JobRequest(capability='image',target_id='ada',input_reference_ids=[ref['id']]))
    assert reused is None and data['image_source']['primary_design_input']
    assert old not in data['reference_ids']
    assert str(store.DATA/old_assets[0]['path']) not in data['images']
    assert 'PRIMARY SUBJECT/DESIGN INPUT' in data['image_reference_roles'][-1]
    assert 'Do not blend it back into the old design' in data['prompt']
    assert store.project(pid)==before and store.assets(pid)==old_assets
    # A style-only upload never replaces established identity.
    style=upload(client,pid)
    styled,_=engine.build_input(before,models.JobRequest(capability='image_prepare',target_id='ada',input_reference_ids=[style['id']]))
    assert not styled['image_source']['primary_design_input'] and old in styled['reference_ids']
    assert str(store.DATA/style['path']) in styled['images']


def test_preparation_and_renderer_receive_identical_pixels(client,plan,monkeypatch):
    import hashlib
    pid=create(client,plan);ref=upload(client,pid,'identity','room')
    monkeypatch.setattr(engine.POOL,'submit',lambda *a:None)
    store.put_setting('routing',{'image_review':'manual'})
    seen=[]
    def run(provider,cap,prompt,images,work):
        seen.append((cap,[hashlib.sha256(p.read_bytes()).hexdigest() for p in images]))
        if cap=='image_prepare':
            assert images and len(images)==1
            return prepared()
        assert cap=='image' and seen[0][1]==seen[1][1]==[ref['sha256']]
        inp=store.job(j['id'])['input']
        assert inp['reference_manifest'][0]['sha256']==ref['sha256']
        raise RuntimeError('test-only stop before media')
    monkeypatch.setattr(providers,'run',run)
    j=engine.enqueue(pid,models.JobRequest(capability='image',target_id='room',input_reference_ids=[ref['id']]))['job']
    engine.execute(j['id'])
    assert store.job(j['id'])['error']=='test-only stop before media'
    assert [s[0] for s in seen]==['image_prepare','image']


def test_preparation_recovery_detects_changed_reference_pixels(plan,tmp_path,monkeypatch):
    basis=image_prompts.source(plan,'room');task=continuity.image_task(plan,'room')
    req=image_prompts.instruction(basis,task,[])
    ref=tmp_path/'source.png';Image.new('RGB',(20,20),'red').save(ref)
    monkeypatch.setattr(providers,'run',lambda *a:prepared())
    work=tmp_path/'preparation'
    image_prompts.prepare(providers.DEFAULT,basis,task,[],req,work,images=[ref])
    saved=(work/'result.json').read_bytes()
    Image.new('RGB',(20,20),'blue').save(ref)
    with pytest.raises(ValueError,match='參考圖'):
        image_prompts.prepare(providers.DEFAULT,basis,task,[],req,work,images=[ref])
    assert (work/'result.json').read_bytes()==saved


def test_primary_design_review_uses_candidate_brief_not_superseded_description(client,plan):
    pid=create(client,plan);ref=upload(client,pid,'identity','room')
    data,_=engine.build_input(store.project(pid),models.JobRequest(capability='image',target_id='room',input_reference_ids=[ref['id']]))
    data.update(image_preparation=prepared(),image_prompt_stage='render')
    aid=add_asset(pid,plan,'room')
    with store.db() as c:
        c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',('design-job',pid,'image','room','succeeded','astra',store.encode(data),store.now(),store.now()))
        c.execute('UPDATE assets SET job_id=? WHERE id=?',('design-job',aid))
    reviewed,_=engine.build_input(store.project(pid),models.JobRequest(capability='image_review',target_id=aid))
    assert 'description' not in reviewed['review_context']['target']
    assert 'PRIMARY SUBJECT/DESIGN INPUT: candidate must match' in reviewed['prompt']
    assert str(store.DATA/ref['path']) in reviewed['images']


def test_review_must_report_declared_state_against_the_candidate_pixels(client,plan):
    """A declared prop fact must be read back from Image 1, not assumed from the brief.

    Measured defect: a review passed a lantern that the brief declared unlit while the
    pixels showed a glowing filament, because nothing asked it to compare the two.
    """
    pid=create(client,plan);aid=add_asset(pid,plan,'room',status='pending')
    brief=prepared('room');brief['lighting']='The lantern emits no light; its glass chimney remains dark and unlit.'
    inp={'image_prompt_stage':'render','image_preparation':brief,'input_references':[]}
    with store.db() as c:
        c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',('generation',pid,'image','room','succeeded','astra',store.encode(inp),store.now(),store.now()))
        c.execute('UPDATE assets SET job_id=? WHERE id=?',('generation',aid))
    data,_=engine.build_input(store.project(pid),models.JobRequest(capability='image_review',target_id=aid))
    prompt=data['prompt']
    assert 'state_checks' in prompt and 'declared' in prompt and 'observed' in prompt and 'match' in prompt
    assert 'Image 1' in prompt
    # An emitted-light contradiction is the hard fail; wording facts stay reportable only.
    assert 'illumination' in prompt and 'advisory' in prompt
    assert data['review_context']['render_brief']['lighting']==brief['lighting']
