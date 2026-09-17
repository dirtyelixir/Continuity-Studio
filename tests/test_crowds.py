import copy
from studio import store, models, engine, continuity, character_sheets, asset_library, delivery, postproduction, h3
from test_production import client, plan, create, add_asset


def as_crowd(plan):
    p=copy.deepcopy(plan)
    p['canon'][0].update(kind='crowd',name='街坊群',description='不同年齡的居民，舊便服',facts=['夜間聚會數十人；其他場景按分鏡設定'])
    return p


def test_crowd_generation_review_and_approval_do_not_require_turnaround(client,plan):
    p=as_crowd(plan);pid=create(client,p)
    data,_=engine.build_input(store.project(pid),models.JobRequest(capability='image',target_id='ada'))
    assert 'ensemble reference image' in data['image_prompt']
    assert 'NOT four views of one person' in data['image_prompt']
    assert 'One subject, no collage' not in data['image_prompt']
    assert 'character_sheet_layout' not in data and not data['images']
    assert asset_library.target_location(pid,'ada')['directory']=='Crowds/街坊群'
    aid=add_asset(pid,p,'ada',status='pending')
    review,_=engine.build_input(store.project(pid),models.JobRequest(capability='image_review',target_id=aid))
    assert not review['character_sheet_required']
    assert 'CROWD REFERENCE REVIEW' in review['prompt']
    assert 'character_sheet=not_applicable' in review['prompt']
    with store.db() as c:c.execute('UPDATE assets SET review=? WHERE id=?',(store.encode({'verdict':'pass','summary':'Group matches','issues':[],'character_sheet':'not_applicable'}),aid))
    engine.decide_asset(aid,'approved','')
    assert continuity.approved_for(p,store.assets(pid),'ada')['id']==aid
    project=client.get('/api/projects/'+pid).json()
    assert project['character_sheets']['characters']==[]
    assert not store.jobs(pid)


def test_crowd_references_remain_collective_in_shots_and_h3(client,plan):
    p=as_crowd(plan);pid=create(client,p)
    add_asset(pid,p,'ada');add_asset(pid,p,'room')
    data,_=engine.build_input(store.project(pid),models.JobRequest(capability='image',target_id='start'))
    assert 'CROWD 街坊群' in data['image_prompt']
    assert 'multiple distinct people' in data['image_prompt']
    assert 'Extract ONE single character identity' not in data['image_prompt']
    refs,missing=delivery.refs_for_scene(p,p['scenes'][0],store.assets(pid))
    assert not missing
    text=delivery.global_draft(p,p['scenes'][0],refs)
    assert 'not a mandatory headcount' in text
    assert 'Light.' in h3.compile_shot(p,p['shots'][0],[])['text']
    assert postproduction.character(pid,'ada')['kind']=='crowd'


def test_reclassification_preserves_other_canon_and_marks_only_dependencies(client,plan):
    pid=create(client,plan)
    old=add_asset(pid,plan,'ada');room=add_asset(pid,plan,'room');frame=add_asset(pid,plan,'start',[old,room])
    p=copy.deepcopy(plan);p['canon'][0]['kind']='crowd'
    saved=engine.save_plan(pid,p,1,'Correct collective classification')
    assert saved['production']==p
    assets={a['id']:a for a in store.assets(pid)}
    assert assets[room]['status']=='approved'
    assert assets[old]['status']==assets[frame]['status']=='stale'
    assert not store.jobs(pid)
    models.Production.model_validate(saved['production'])


def test_new_planning_explicitly_classifies_collective_cast(client,plan):
    pid=create(client,plan)
    data,_=engine.build_input(store.project(pid),models.JobRequest(capability='narrative'))
    assert 'kind=crowd' in data['prompt']
    assert 'first shot establish' in data['prompt']
