import copy
import pytest
from studio import store,engine,models,delivery,prompt_preparation
from test_production import client,plan,create,add_asset


def result_for(plan):
    return {'scene_id':'scene','visual_setting':'Stop-motion. Night light through the workshop window.','subjects':[{'entity_id':'ada','name_en':'Ada','appearance':'Black bob, yellow coat with three buttons.'},{'entity_id':'room','name_en':'Workshop','appearance':'Round rear window and wooden bench.'}], 'shots':[{'shot_id':'shot','shot_prompt':'summary:\n[reference generation] <Entity ada> presses the switch.\n\nretention_analysis:\n<Entity ada>: preserve identity.\n\ndetailed_description:\n[Shot 1] One 6-second shot. <Entity ada> raises her own hand from 0–3s and presses the switch. At 3–4s <Entity ada> (S1) quietly says: <d>[English] Light.</d>\n\noverall_soundscape:\nWind.\n\nnon_diegetic_music:\nNone.'}]}


def save_result(pid,result,basis):
    with store.db() as c:c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,result,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',(store.uid(),pid,'h3_prepare','scene','succeeded','test',store.encode({'preparation_hash':store.digest(basis)}),store.encode(result),store.now(),store.now()))


def test_prepared_prose_resolves_later_approved_images_without_new_text_job(client,plan):
    plan['style']='全章導演說明，最後一幕加入音樂。';plan['shots'][0]['action']='她按開關'
    pid=create(client,plan);basis=prompt_preparation.source(plan,'scene');result=result_for(plan)
    save_result(pid,result,basis)
    before=store.project(pid)
    a=delivery.scene_bundle(before,plan['scenes'][0]);assert 'Ada' in a['chapters'][0]['shot_prompt']
    assert '全章' not in a['global_prompt']+a['chapters'][0]['shot_prompt']
    assert not a['preparation']['required']
    add_asset(pid,plan,'ada');add_asset(pid,plan,'room')
    b=delivery.scene_bundle(before,plan['scenes'][0])
    assert '<Subject 1>' in b['chapters'][0]['shot_prompt'] and '<Picture 1>' in b['global_prompt']
    assert '最後一幕' not in b['chapters'][0]['shot_prompt']
    assert len(store.jobs(pid))==1 and store.project(pid)==before
    changed=copy.deepcopy(before);changed['production']['shots'][0]['beats'][0]['action']='Changed action'
    assert prompt_preparation.prepared(changed,'scene')[0] is None


def test_language_and_entity_and_dialogue_validation(plan):
    basis=prompt_preparation.source(plan,'scene');r=result_for(plan)
    prompt_preparation.validate(r,basis)
    for changed in ['中文動作','<Entity other> moves.','<Picture 1> image.','<d>[English] Extra.</d>']:
        bad=copy.deepcopy(r);bad['shots'][0]['shot_prompt']+='\n'+changed
        with pytest.raises(ValueError):prompt_preparation.validate(bad,basis)
    prompt_preparation.english('English. <d>[yue-HK] 樂仔。行未？</d>')


def test_chinese_fallback_is_not_presented_as_ready_copyable_prompt(client,plan):
    plan['style']='全章很長的導演說明';plan['shots'][0]['beats'][0]['action']='角色按開關'
    pid=create(client,plan);state=client.get('/api/projects/'+pid).json()['delivery']['scenes'][0]
    assert state['preparation']['required'] and state['preparation']['status']=='needed'
    assert '全章' not in state['global_prompt'] and '角色按' not in state['chapters'][0]['shot_prompt']
    data,_=engine.build_input(store.project(pid),models.JobRequest(capability='h3_prepare',target_id='scene'))
    assert not data['images'] and 'Every action clause identifies its actor' in data['prompt']
    assert not store.jobs(pid)


def test_shot_fallback_does_not_repeat_project_style(plan):
    plan['style']='WHOLE PROJECT EDITORIAL NOTES AND LATER SCENES'
    assert plan['style'] not in delivery.chapter_draft(plan,plan['shots'][0],[])


def test_global_fallback_never_leaks_canon_or_review_bookkeeping(client,plan):
    plan['style']='EDITORIAL: 29 shots; reveal the broadcast later.'
    plan['canon'][0]['description']='Visible coat; her father died six years ago.'
    plan['canon'][0]['facts']=['Hidden knife in right pocket.', 'Mother lives upstairs.']
    plan['scenes'][0]['summary']='Later the water supply is destroyed.'
    pid=create(client,plan);add_asset(pid,plan,'ada')
    refs,_=delivery.refs_for_scene(plan,plan['scenes'][0],store.assets(pid))
    refs[0]['director_note']='[人工覆核採用] 使用者已確認採用此圖。'
    text=delivery.global_draft(plan,plan['scenes'][0],refs)
    assert '<Subject 1>' in text and '<Picture 1>' in text
    for forbidden in [plan['style'],plan['scenes'][0]['summary'],plan['canon'][0]['description'],*plan['canon'][0]['facts'],refs[0]['director_note'],'Approved visual interpretation:']:
        assert forbidden not in text
    prompt_preparation.english(text)
    assert 'father died' in store.project(pid)['production']['canon'][0]['description']


def test_preparation_and_refinement_exclude_global_bookkeeping(client,plan):
    pid=create(client,plan);add_asset(pid,plan,'ada');add_asset(pid,plan,'room')
    for capability in ('h3_prepare','h3_scene'):
        data,_=engine.build_input(store.project(pid),models.JobRequest(capability=capability,target_id='scene'))
        assert prompt_preparation.GLOBAL_RULES in data['prompt']


def test_original_names_survive_preparation_delivery_and_legacy_export(client,plan):
    from studio import h3
    plan['canon'][0]['name']='陳樂言'
    plan['shots'][0]['dialogue'][0]['text']='Ada, Light.'
    raw=result_for(plan)
    raw['shots'][0]['shot_prompt']=raw['shots'][0]['shot_prompt'].replace('Light.</d>','Ada, Light.</d>')
    raw['subjects'][0]['name_en']='Chan Leyan'
    raw['subjects'][1]['name_en']="Leyan's Workshop"
    basis=prompt_preparation.source(plan,'scene')
    prepared=prompt_preparation.normalize(raw,basis)
    assert prepared['subjects'][0]['name_en']=='陳樂言'
    assert prepared['subjects'][1]['name_en']=="陳樂言's Workshop"
    assert raw['subjects'][0]['name_en']=='Chan Leyan'
    prompt_preparation.validate(prepared,basis)
    with pytest.raises(ValueError,match='人名'):prompt_preparation.validate(raw,basis)
    pid=create(client,plan);save_result(pid,raw,basis)
    p=store.project(pid)
    out=delivery.scene_bundle(p,plan['scenes'][0])
    assert '陳樂言 presses' in out['chapters'][0]['shot_prompt']
    add_asset(pid,plan,'ada');add_asset(pid,plan,'room')
    out=delivery.scene_bundle(p,plan['scenes'][0])
    assert '<Subject 1> is 陳樂言 from <Picture 1>' in out['global_prompt']
    assert not out['preparation']['required']
    assert not out['chapters'][0]['issues']
    assert '<d>[English] Ada, Light.</d>' in out['chapters'][0]['shot_prompt']
    legacy=h3.compile_shot(plan,plan['shots'][0],[],prepared)
    h3.validate_refinement(legacy['text'],legacy,plan['shots'][0])
    assert '陳樂言' in legacy['text'] and 'Chan Leyan' not in legacy['text']


def test_name_language_exception_is_limited_to_canonical_spellings():
    prompt_preparation.english('陳樂言 walks. <d>[yue-HK] 行。</d>', ['陳樂言'])
    for bad in ('陳樂言走向門。','樂言 walks.','陌生人 walks.'):
        with pytest.raises(ValueError):prompt_preparation.english(bad,['陳樂言'])


def test_dialogue_attribute_normalization_preserves_original_words(plan):
    original=result_for(plan)
    original['shots'][0]['shot_prompt']=original['shots'][0]['shot_prompt'].replace('<d>[English] ', '<d language="English">')
    normalized=prompt_preparation.normalize(original)
    prompt_preparation.validate(normalized,prompt_preparation.source(plan,'scene'))
    assert '<d language=' in original['shots'][0]['shot_prompt']
    assert '<d>[English] Light.</d>' in normalized['shots'][0]['shot_prompt']
    for text in ['Описание камеры','カメラの動き']:
        with pytest.raises(ValueError):prompt_preparation.english(text)


def test_english_source_still_requires_scene_scoping_before_handoff(client,plan):
    pid=create(client,plan)
    b=delivery.scene_bundle(store.project(pid),plan['scenes'][0])
    assert b['preparation']['required'] and b['preparation']['status']=='needed'


def test_prepared_keyframe_prompt_is_english_and_does_not_reintroduce_style_book(client,plan):
    from studio import h3
    plan['style']='全書導演說明及最後一幕';pid=create(client,plan)
    result=result_for(plan)
    out=h3.compile_shot(plan,plan['shots'][0],[],result)
    prompt_preparation.english(out['text'])
    assert plan['style'] not in out['text']
    assert '<Entity ' not in out['text']
    h3.validate_refinement(out['text'],out,plan['shots'][0])


def test_silent_mouthed_words_stay_silent(plan):
    from studio import speech_direction
    shot=copy.deepcopy(plan['shots'][0]);shot['dialogue'][0]['delivery']='只有口形，無聲'
    text=speech_direction.direction(plan,shot)
    assert 'Silent articulation only' in text and 'No audible dialogue' in text
    assert 'Speak only' not in text
