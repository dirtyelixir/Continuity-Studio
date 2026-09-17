from studio import store
from test_production import client,plan,create,add_asset


def test_delete_only_unreferenced_rejected_original(client,plan):
    pid=create(client,plan);aid=add_asset(pid,plan,'ada');path=store.DATA/next(a for a in store.assets(pid) if a['id']==aid)['path']
    assert client.delete('/api/assets/'+aid).status_code==400
    with store.db() as c:c.execute('UPDATE assets SET status="rejected" WHERE id=?',(aid,))
    child=add_asset(pid,plan,'start',refs=[aid])
    assert client.delete('/api/assets/'+aid).status_code==400
    assert path.exists()
    with store.db() as c:c.execute('UPDATE assets SET reference_ids="[]" WHERE id=?',(child,))
    assert client.delete('/api/assets/'+aid).status_code==200
    assert not path.exists() and all(a['id']!=aid for a in store.assets(pid))
    assert any(a['id']==child for a in store.assets(pid))


def test_saved_or_active_references_block_deletion(client,plan):
    pid=create(client,plan);aid=add_asset(pid,plan,'ada',status='rejected')
    store.put_setting('test-reference',{'asset_id':aid})
    assert client.delete('/api/assets/'+aid).status_code==400
    store.put_setting('test-reference',{})
    client.post('/api/settings/routing',json={'capability':'image_review','provider_id':'manual'})
    j=client.post(f'/api/projects/{pid}/jobs',json={'capability':'image_review','target_id':aid})
    assert j.status_code==200
    assert client.delete('/api/assets/'+aid).status_code==400
    assert any(a['id']==aid for a in store.assets(pid))


def test_reject_deletes_original_and_completed_review_copy(client,plan):
    from studio import asset_library
    import json,shutil
    pid=create(client,plan);aid=add_asset(pid,plan,'ada',status='pending')
    asset=store.assets(pid)[0];path=store.DATA/asset['path']
    work=store.DATA/'jobs'/'review';work.mkdir(parents=True)
    copied=work/'reference-1.png';shutil.copyfile(path,copied)
    untouched=work/'reference-2.png';shutil.copyfile(path,untouched)
    with store.db() as c:
        c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',('review',pid,'image_review',aid,'succeeded','manual',store.encode({'images':[str(path)]}),store.now(),store.now()))
    r=client.post('/api/assets/'+aid+'/decision',json={'status':'rejected','note':'Wrong face'})
    assert r.status_code==200 and r.json()['deleted']
    assert not path.exists() and not copied.exists() and untouched.exists()
    assert not store.assets(pid) and store.job('review')['state']=='succeeded'
    with store.db() as c:
        assert any('Wrong face' in e['detail'] for e in c.execute('SELECT detail FROM events WHERE kind="decision"'))


def test_reject_waits_for_active_job_and_cleans_after_cancel(client,plan):
    pid=create(client,plan);aid=add_asset(pid,plan,'ada',status='pending')
    path=store.DATA/store.assets(pid)[0]['path']
    client.post('/api/settings/routing',json={'capability':'image_review','provider_id':'manual'})
    j=client.post(f'/api/projects/{pid}/jobs',json={'capability':'image_review','target_id':aid}).json()['job']
    r=client.post('/api/assets/'+aid+'/decision',json={'status':'rejected'})
    assert r.status_code==200 and not r.json()['deleted']
    assert r.json()['deletion_pending_reason'] and path.exists()
    assert client.post('/api/jobs/'+j['id']+'/cancel').status_code==200
    assert not path.exists() and not store.assets(pid)


def test_purge_rejected_chain_preserves_approved_asset(client,plan):
    from studio import asset_deletion
    pid=create(client,plan);root=add_asset(pid,plan,'ada',status='rejected')
    child=add_asset(pid,plan,'start',refs=[root],status='rejected')
    kept=add_asset(pid,plan,'room')
    result=asset_deletion.purge_rejected(pid)
    assert set(result['deleted_asset_ids'])=={root,child} and not result['pending_deletions']
    assert [a['id'] for a in store.assets(pid)]==[kept]


def test_deleted_version_filename_is_never_reused(client,plan):
    from studio import asset_library
    pid=create(client,plan);aid=add_asset(pid,plan,'ada',status='pending')
    old=store.DATA/store.assets(pid)[0]['path']
    first=asset_library.next_path(pid,'ada');dest=store.DATA/first;dest.parent.mkdir(parents=True,exist_ok=True);old.rename(dest)
    with store.db() as c:c.execute('UPDATE assets SET path=? WHERE id=?',(str(first),aid))
    assert client.post('/api/assets/'+aid+'/decision',json={'status':'rejected'}).json()['deleted']
    assert asset_library.next_path(pid,'ada')!=first


def test_cleanup_never_deletes_unrelated_provider_result(client,plan,tmp_path):
    import json,shutil
    pid=create(client,plan);aid=add_asset(pid,plan,'ada',status='pending')
    original=store.DATA/store.assets(pid)[0]['path'];outside=tmp_path/'user-upload.png';shutil.copyfile(original,outside)
    work=store.DATA/'jobs'/'generation';work.mkdir(parents=True)
    (work/'result.json').write_text(json.dumps({'image_path':str(outside)}))
    with store.db() as c:c.execute('UPDATE assets SET job_id="generation" WHERE id=?',(aid,))
    assert client.post('/api/assets/'+aid+'/decision',json={'status':'rejected'}).json()['deleted']
    assert outside.exists()
