import pytest
from studio import store,engine
from test_production import client,plan,create,add_asset

@pytest.mark.parametrize('verdict,note',[('revise',''),('uncertain',' \n '),(None,''),('revise','接受這個構圖。')])
def test_explicit_approval_allows_empty_note_and_preserves_review(client,plan,verdict,note):
    pid=create(client,plan);aid=add_asset(pid,plan,'start',status='pending')
    review={'verdict':verdict,'summary':'Check hand placement','issues':['Hand differs from plan'],'character_sheet':'not_applicable'} if verdict else None
    with store.db() as c:c.execute('UPDATE assets SET review=? WHERE id=?',(store.encode(review) if review else None,aid))
    before=store.assets(pid)[0];pixels=(store.DATA/before['path']).read_bytes()
    r=client.post('/api/assets/'+aid+'/decision',json={'status':'approved','note':note})
    assert r.status_code==200,r.text
    after=store.assets(pid)[0];assert after['status']=='approved' and after['review']==review
    if note.strip():assert after['note']==note
    else:assert '[人工覆核採用]' in after['note']
    assert after['dependency_hash']==before['dependency_hash'] and after['reference_ids']==before['reference_ids']
    assert (store.DATA/after['path']).read_bytes()==pixels and not store.jobs(pid)
    assert any(after['note'] in e['detail'] for e in client.get('/api/projects/'+pid).json()['events'])


def test_blank_approval_keeps_canon_and_reference_freshness_guards(client,plan):
    pid=create(client,plan);ref=add_asset(pid,plan,'room');aid=add_asset(pid,plan,'start',[ref],status='pending')
    with store.db() as c:c.execute('UPDATE assets SET dependency_hash="old" WHERE id=?',(aid,))
    assert client.post('/api/assets/'+aid+'/decision',json={'status':'approved'}).status_code==400
    from studio import continuity
    with store.db() as c:c.execute('UPDATE assets SET dependency_hash=? WHERE id=?',(continuity.target_hash(plan,'start'),aid))
    engine.decide_asset(ref,'rejected','Not usable')
    assert client.post('/api/assets/'+aid+'/decision',json={'status':'approved'}).status_code==400
    assert next(a for a in store.assets(pid) if a['id']==aid)['status']=='stale'
