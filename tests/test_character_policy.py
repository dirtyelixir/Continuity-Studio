import copy,json,io,zipfile
import pytest
from studio import character_sheets,engine,store,models,providers,continuity,asset_library
from test_production import client,plan,create,add_asset


def review_record(aid,sheet='pass',verdict='pass'):
    with store.db() as db:db.execute('UPDATE assets SET review=? WHERE id=?',(store.encode({'verdict':verdict,'summary':'Test-only review','issues':[],'character_sheet':sheet}),aid))


def test_character_approval_requires_actual_sheet_check(client,plan):
    pid=create(client,plan);aid=add_asset(pid,plan,'ada',status='pending')
    for check in [None,'revise','uncertain','not_applicable']:
        if check:review_record(aid,check)
        with pytest.raises(ValueError,match='四視圖'):engine.decide_asset(aid,'approved','Director override cannot bypass missing views')
    review_record(aid)
    engine.decide_asset(aid,'approved','')
    assert character_sheets.verified(store.assets(pid)[0])
    room=add_asset(pid,plan,'room',status='pending');engine.decide_asset(room,'approved','')


def test_legacy_identity_remains_available_but_is_not_claimed_four_view(client,plan):
    pid=create(client,plan);aid=add_asset(pid,plan,'ada');before=copy.deepcopy(store.assets(pid))
    p=client.get('/api/projects/'+pid).json()
    assert p['character_sheets']['characters'][0]['status']=='needs_four_view'
    assert p['character_sheets']['characters'][0]['approved_asset_id']==aid
    assert continuity.approved_for(plan,p['assets'],'ada')['id']==aid
    assert store.assets(pid)==before


def test_generation_and_review_have_separate_layout_reference(client,plan):
    pid=create(client,plan);aid=add_asset(pid,plan,'ada')
    guide=character_sheets.guide_path();guide.parent.mkdir();guide.write_bytes((store.DATA/store.assets(pid)[0]['path']).read_bytes())
    data,_=engine.build_input(store.project(pid),models.JobRequest(capability='image',target_id='ada',force=True))
    assert data['reference_ids']==[aid] and data['images'][-1]==str(guide)
    assert data['character_sheet_layout']=='four-view-v2' and 'LAYOUT EXAMPLE ONLY' in data['prompt']
    assert 'Do not copy this example man' in data['prompt']
    review,_=engine.build_input(store.project(pid),models.JobRequest(capability='image_review',target_id=aid))
    assert review['character_sheet_required'] and review['images'][-1]==str(guide)
    assert 'A single portrait can never pass' in review['prompt']
    room=add_asset(pid,plan,'room');review,_=engine.build_input(store.project(pid),models.JobRequest(capability='image_review',target_id=room))
    assert not review['character_sheet_required'] and 'character_sheet=not_applicable' in review['prompt']
    assert str(guide) not in review['images']


def test_reviewer_cannot_mark_failed_layout_as_overall_pass(client,plan):
    pid=create(client,plan);aid=add_asset(pid,plan,'ada',status='pending')
    client.post('/api/settings/routing',json={'capability':'image_review','provider_id':'manual'})
    j=client.post('/api/projects/'+pid+'/jobs',json={'capability':'image_review','target_id':aid}).json()['job']
    response=client.post('/api/jobs/'+j['id']+'/manual',json={'verdict':'pass','summary':'Good face, missing rear.','issues':[],'character_sheet':'revise'})
    assert response.status_code==200
    a=store.assets(pid)[0];assert a['review']['verdict']=='revise'
    with pytest.raises(ValueError,match='四視圖'):engine.decide_asset(aid,'approved','accept')


def test_named_versions_and_exported_layout_requirement(client,plan):
    pid=create(client,plan);add_asset(pid,plan,'ada')
    path=asset_library.next_path(pid,'ada',variant='four-view-v1')
    assert path.name=='Ada-four-view-v001.png'
    (store.DATA/path).parent.mkdir(parents=True,exist_ok=True);(store.DATA/path).write_bytes(b'test')
    assert asset_library.next_path(pid,'ada',variant='four-view-v1').name=='Ada-four-view-v002.png'
    guide=character_sheets.guide_path();guide.parent.mkdir();guide.write_bytes(b'layout example')
    z=zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+pid+'/export').content))
    assert 'four' in z.read('character-reference-requirements.md').decode().lower()
    assert z.read('reference-guides/character-four-view.jpg')==b'layout example'


@pytest.mark.parametrize('note',[None,'  ','Accept full-body front'])
def test_explicit_human_sheet_acceptance_preserves_review_and_invalidates_dependents(client,plan,note):
    pid=create(client,plan);old=add_asset(pid,plan,'ada');frame=add_asset(pid,plan,'start',[old]);aid=add_asset(pid,plan,'ada',[old],status='pending')
    review_record(aid,'revise','revise')
    original=next(a for a in store.assets(pid) if a['id']==aid)['review']
    endpoint='/api/assets/'+aid+'/decision'
    assert client.post(endpoint,json={'status':'approved','note':'Accept full-body front'}).status_code==400
    payload={'status':'approved','acknowledge_sheet_issues':True}
    if note is not None:payload['note']=note
    assert client.post(endpoint,json=payload).status_code==200
    assets={a['id']:a for a in store.assets(pid)}
    assert assets[aid]['status']=='approved' and assets[aid]['note']=='[人工覆核採用] '+((note or '').strip() or '使用者已確認採用此圖，保留原審查意見。')
    assert assets[aid]['review']==original and not character_sheets.verified(assets[aid])
    assert assets[old]['status']=='superseded' and assets[frame]['status']=='stale'
    assert continuity.approved_for(plan,list(assets.values()),'ada')['id']==aid
    assert any('[人工覆核採用]' in e['detail'] for e in client.get('/api/projects/'+pid).json()['events'])


def test_manual_sheet_acceptance_does_not_bypass_stale_canon_or_references(client,plan):
    pid=create(client,plan);old=add_asset(pid,plan,'ada');aid=add_asset(pid,plan,'ada',[old],status='pending')
    review_record(aid,'revise','revise')
    engine.decide_asset(old,'rejected','Rejected identity')
    with pytest.raises(ValueError,match='reference'):engine.decide_asset(aid,'approved','Accept layout',True)
    with store.db() as db:db.execute('UPDATE assets SET dependency_hash=? WHERE id=?',('old-canon',aid))
    with pytest.raises(ValueError,match='older canon'):engine.decide_asset(aid,'approved','Accept layout',True)
    assert next(a for a in store.assets(pid) if a['id']==aid)['status']!='approved'
