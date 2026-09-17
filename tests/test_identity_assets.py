import copy
import io
import hashlib
import pytest
from PIL import Image
from studio import store,engine,continuity,identity_assets,providers
from test_production import client,plan,create,add_asset


def png():
    b=io.BytesIO();Image.new('RGB',(300,400),'orange').save(b,format='PNG');return b.getvalue()


def test_stale_source_can_be_explicitly_adopted_without_rewriting_history(client,plan,monkeypatch):
    pid=create(client,plan);aid=add_asset(pid,plan,'ada');child=add_asset(pid,plan,'start',[aid])
    changed=copy.deepcopy(plan);changed['canon'][0]['description']='New description'
    engine.save_plan(pid,changed,1,'Identity changed')
    before=next(a for a in store.assets(pid) if a['id']==aid)
    path=store.DATA/before['path'];raw=path.read_bytes()
    monkeypatch.setattr(providers,'run',lambda *a:pytest.fail('Adoption never generates or reviews'))
    result=client.post(f'/api/projects/{pid}/identity-assets/ada',data={'revision':2,'asset_id':aid})
    assert result.status_code==200,result.text
    adopted=continuity.approved_for(changed,store.assets(pid),'ada')
    assert adopted['id']!=aid and adopted['source_asset_id']==aid
    assert (store.DATA/adopted['path']).read_bytes()==raw
    assert adopted['note'].startswith('[人工覆核採用]')
    assert next(a for a in store.assets(pid) if a['id']==aid)==before
    assert next(a for a in store.assets(pid) if a['id']==child)['status']=='stale'
    repeat=client.post(f'/api/projects/{pid}/identity-assets/ada',data={'revision':2,'asset_id':aid})
    assert repeat.json()['asset_id']==adopted['id'] and len(store.assets(pid))==3
    assert not store.jobs(pid)


def test_upload_and_identity_edit_are_adopted_against_saved_settings(client,plan,monkeypatch):
    pid=create(client,plan);ent={**plan['canon'][0],'description':'Uploaded design'}
    monkeypatch.setattr(providers,'run',lambda *a:pytest.fail('No provider calls'))
    r=client.post(f'/api/projects/{pid}/identity-assets/ada',data={'revision':1,'entity':store.encode(ent)},files={'file':('design.png',png(),'image/png')})
    assert r.status_code==200,r.text
    saved=store.project(pid);assert saved['revision']==2 and saved['production']['canon'][0]['description']=='Uploaded design'
    a=continuity.approved_for(saved['production'],store.assets(pid),'ada')
    assert a['id']==r.json()['asset_id'] and a['provider']=='manual' and a['reference_ids']==[]
    assert not store.jobs(pid)


@pytest.mark.parametrize('failure',['revision','other_asset','other_entity','bad_image','both','none','frame','voice'])
def test_invalid_selection_does_not_change_production(client,plan,failure):
    pid=create(client,plan);aid=add_asset(pid,plan,'ada');other=add_asset(pid,plan,'room')
    before=store.project(pid);assets=store.assets(pid);data={'revision':1,'asset_id':aid};files=None;target='ada'
    if failure=='revision':data['revision']=0
    elif failure=='other_asset':data['asset_id']=other
    elif failure=='other_entity':data['entity']=store.encode(plan['canon'][1])
    elif failure=='bad_image':data.pop('asset_id');files={'file':('broken.png',b'broken','image/png')}
    elif failure=='both':files={'file':('image.png',png(),'image/png')}
    elif failure=='none':data.pop('asset_id')
    elif failure=='frame':target='start'
    else:data['entity']=store.encode({**plan['canon'][0],'kind':'voice'})
    r=client.post(f'/api/projects/{pid}/identity-assets/{target}',data=data,files=files)
    assert r.status_code in (400,422),r.text
    assert store.project(pid)==before and store.assets(pid)==assets


def test_current_candidate_uses_existing_approval_and_invalidates_previous_references(client,plan):
    pid=create(client,plan);previous=add_asset(pid,plan,'ada');child=add_asset(pid,plan,'start',[previous]);aid=add_asset(pid,plan,'ada',status='pending')
    r=identity_assets.save(pid,'ada',1,asset_id=aid)
    assert r['asset_id']==aid and len(store.assets(pid))==3
    assert next(a for a in store.assets(pid) if a['id']==previous)['status']=='superseded'
    assert next(a for a in store.assets(pid) if a['id']==child)['status']=='stale'
