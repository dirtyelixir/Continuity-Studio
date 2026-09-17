import copy
import pytest
from studio import scene_asset_batch as batch,store,engine,models,continuity
from test_production import client,plan,create,add_asset


def enqueue_stub(monkeypatch):
    calls=[]
    monkeypatch.setattr(engine,'image_provider',lambda req:{'id':req.image_provider,'kind':'comfy'})
    def run(pid,req):
        jid=store.uid();calls.append(req.target_id)
        with store.db() as c:c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',(jid,pid,'image',req.target_id,'queued',req.image_provider,'{}',store.now(),store.now()))
        return {'job':store.job(jid)}
    monkeypatch.setattr(engine,'enqueue',run)
    return calls


def test_scene_membership_public_reuse_and_voice_exclusion(client,plan):
    p=copy.deepcopy(plan);p['canon'][0]['scope']='public'
    p['canon'] += [{**p['canon'][0],'id':'unrelated','name':'Other public'}, {**p['canon'][0],'id':'radio','kind':'voice','name':'Radio'}]
    p['shots'][0]['entity_ids'].append('radio');pid=create(client,p);aid=add_asset(pid,p,'ada')
    before=store.project(pid);out=batch.preview(pid,'scene')
    assert [i['target_id'] for i in out['items']]==['ada','room']
    assert out['items'][0]['state']=='approved' and out['items'][0]['asset_id']==aid
    assert out['generate_count']==1 and store.project(pid)==before
    assert not store.jobs(pid)


def test_pending_and_unresolved_work_skip(client,plan):
    from studio import comfy_images
    pid=create(client,plan);add_asset(pid,plan,'ada',status='pending')
    jid=store.uid()
    with store.db() as c:c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)',(jid,pid,'image','room','failed','comfy_local','{}',None,'',store.now(),store.now()))
    work=store.DATA/'jobs'/jid;work.mkdir(parents=True)
    # Use the adapter's actual unresolved receipt format.
    (work/'comfy-receipt.json').write_text('{"phase":"submitted","prompt_id":"remote"}')
    assert comfy_images.unresolved(work)
    out=batch.preview(pid,'scene');assert [i['state'] for i in out['items']]==['pending','active']
    assert out['generate_count']==0


def test_submit_queues_once_and_other_scene_reuses_shared_queue(client,plan,monkeypatch):
    p=copy.deepcopy(plan);p['scenes'].append({**p['scenes'][0],'id':'second'})
    shot=copy.deepcopy(p['shots'][0]);shot['id']='second_shot';shot['scene_id']='second'
    for f in shot['keyframes']:f['id']='second_'+f['id']
    p['shots'].append(shot);pid=create(client,p);calls=enqueue_stub(monkeypatch)
    preview=batch.preview(pid,'scene');first=batch.submit(pid,'scene',preview['token'],'comfy_local')
    assert calls==['ada','room'] and all(i['state']=='queued' for i in first['items'])
    assert batch.submit(pid,'scene',preview['token'],'comfy_local')==first and len(calls)==2
    assert batch.preview(pid,'second')['generate_count']==0
    with pytest.raises(ValueError,match='更換'):batch.submit(pid,'scene',preview['token'],'astra')


def test_stale_token_and_revision_block_before_enqueue(client,plan,monkeypatch):
    pid=create(client,plan);calls=enqueue_stub(monkeypatch);old=batch.preview(pid,'scene')
    add_asset(pid,plan,'ada')
    with pytest.raises(ValueError,match='更新'):batch.submit(pid,'scene',old['token'],'comfy_local')
    old=batch.preview(pid,'scene');engine.save_plan(pid,plan,1,'New revision')
    with pytest.raises(ValueError,match='更新'):batch.submit(pid,'scene',old['token'],'comfy_local')
    assert calls==[]


def test_partial_failure_and_interruption_do_not_replay(client,plan,monkeypatch):
    pid=create(client,plan);calls=enqueue_stub(monkeypatch)
    def failing(pid,req):calls.append(req.target_id);raise ValueError('Provider unavailable')
    monkeypatch.setattr(engine,'enqueue',failing);p=batch.preview(pid,'scene')
    r=batch.submit(pid,'scene',p['token'],'comfy_local');assert all(i['state']=='failed' for i in r['items'])
    assert batch.submit(pid,'scene',p['token'],'comfy_local')==r and len(calls)==2
    # An interrupted enqueue has a durable intent but no final result.
    pid=create(client,plan);p=batch.preview(pid,'scene')
    def interrupted(pid,req):calls.append(req.target_id);raise KeyboardInterrupt()
    monkeypatch.setattr(engine,'enqueue',interrupted)
    with pytest.raises(KeyboardInterrupt):batch.submit(pid,'scene',p['token'],'comfy_local')
    before=len(calls);r=batch.submit(pid,'scene',p['token'],'comfy_local')
    assert r['state']=='submitting' and r['items'][0]['state']=='submitting' and len(calls)==before


def test_missing_scene_deleted_project_manual_provider_and_stale_assets(client,plan,monkeypatch):
    pid=create(client,plan);add_asset(pid,plan,'ada',status='stale');p=batch.preview(pid,'scene')
    assert p['generate_count']==2
    with pytest.raises(ValueError):batch.preview(pid,'missing')
    monkeypatch.setattr(engine,'image_provider',lambda req:{'kind':'manual'})
    with pytest.raises(ValueError,match='人工'):batch.submit(pid,'scene',p['token'],'manual')
    with store.db() as c:c.execute('UPDATE projects SET deleted_at=? WHERE id=?',(store.now(),pid))
    with pytest.raises(ValueError):batch.preview(pid,'scene')
    assert not store.jobs(pid)


def test_routes_validate_preview_and_record_queue_receipt(client,plan,monkeypatch):
    pid=create(client,plan);calls=enqueue_stub(monkeypatch);url=f'/api/projects/{pid}/scenes/scene/asset-batch'
    p=client.get(url).json();r=client.post(url,json={'token':p['token'],'image_provider':'comfy_local'})
    assert r.status_code==200,r.text
    assert r.json()['state']=='complete' and calls==['ada','room']
    assert client.post(url,json={'token':p['token'],'image_provider':'comfy_local'}).json()==r.json()


def test_new_explicit_preview_can_retry_failures_but_never_uncertain_intent(client,plan,monkeypatch):
    pid=create(client,plan);calls=enqueue_stub(monkeypatch)
    def fail(pid,req):raise ValueError('temporary failure')
    monkeypatch.setattr(engine,'enqueue',fail);first=batch.preview(pid,'scene');batch.submit(pid,'scene',first['token'],'comfy_local')
    second=batch.preview(pid,'scene');assert second['token']!=first['token'] and second['generate_count']==2
    def interrupt(pid,req):raise KeyboardInterrupt()
    monkeypatch.setattr(engine,'enqueue',interrupt)
    with pytest.raises(KeyboardInterrupt):batch.submit(pid,'scene',second['token'],'comfy_local')
    third=batch.preview(pid,'scene');assert third['items'][0]['state']=='active' and third['generate_count']==1
