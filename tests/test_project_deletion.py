import pytest
from studio import store,engine,models
from test_production import client,plan,create,add_asset


def delete(client,pid,title='Test',revision=1):
    return client.request('DELETE','/api/projects/'+pid,json={'confirmation_title':title,'revision':revision})


def test_confirmation_and_revision(client,plan):
    pid=create(client,plan)
    assert client.delete('/api/projects/'+pid).status_code==422
    assert delete(client,pid,'wrong').status_code==400
    assert delete(client,pid,revision=0).status_code==400
    assert store.project(pid)['deleted_at'] is None
    assert client.post('/api/projects/'+pid+'/undelete').status_code==400


@pytest.mark.parametrize('state',['queued','running','awaiting_input'])
def test_active_jobs_block_delete(client,plan,state):
    pid=create(client,plan)
    with store.db() as c:
        c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',('job',pid,'image','ada',state,'manual','{}',store.now(),store.now()))
    assert delete(client,pid).status_code==400
    assert store.project(pid)['deleted_at'] is None
    assert store.job('job')['state']==state


@pytest.mark.parametrize('state',['queued','running','importing'])
def test_active_voice_blocks_delete(client,plan,state):
    pid=create(client,plan)
    with store.db() as c:
        c.execute('INSERT INTO voice_takes(id,project_id,character_id,kind,state,request,created,updated) VALUES(?,?,?,?,?,?,?,?)',('voice',pid,'ada','voice',state,'{}',store.now(),store.now()))
    assert delete(client,pid).status_code==400
    assert store.project(pid)['deleted_at'] is None


def test_delete_restore_preserves_children_files_and_other_work(client,plan):
    pid=create(client,plan);other=create(client,plan);aid=add_asset(pid,plan,'ada')
    asset=store.assets(pid)[0];path=store.DATA/asset['path'];original=path.read_bytes()
    store.put_setting('delivery:'+pid,{'revision':3,'continuity_enabled':True,'context_frames':22,'scenes':{}})
    with store.db() as c:
        c.execute('INSERT INTO story_chapters(id,project_id,number,title,brief,source_kind,created,updated) VALUES(?,?,?,?,?,?,?,?)',('chapter',pid,1,'Chapter','Brief','story',store.now(),store.now()))
        c.execute('INSERT INTO voice_takes(id,project_id,character_id,kind,state,request,created,updated) VALUES(?,?,?,?,?,?,?,?)',('voice',pid,'ada','voice','succeeded','{}',store.now(),store.now()))
        c.execute('INSERT INTO voice_profiles VALUES(?,?,?,?)',(pid,'ada',1,store.encode({'selected_take_id':None,'description':'Quiet','language':'English','sample_text':'Hello','seed':42})))
        c.execute('INSERT INTO voice_lines VALUES(?,?,?)',(pid,'line','voice'))
        c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',('job',pid,'image','ada','failed','manual','{}',store.now(),store.now()))
    before=store.project(pid);other_before=store.project(other)
    tables=['revisions','assets','jobs','story_chapters','voice_takes','voice_profiles','voice_lines','settings']
    def snapshot():
        with store.db() as c:return {t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in tables}
    children=snapshot()
    assert delete(client,pid).status_code==200
    assert {p['id'] for p in client.get('/api/projects').json()}=={other}
    assert {p['id'] for p in client.get('/api/projects?deleted=true').json()}=={pid}
    assert client.get('/api/projects/'+pid).status_code==400
    assert client.post('/api/projects/'+pid+'/jobs',json={'capability':'narrative'}).status_code==410
    assert client.put('/api/projects/'+pid+'/plan',json={'revision':1,'production':plan}).status_code==410
    assert client.post('/api/assets/'+aid+'/decision',json={'status':'rejected','note':'must not delete'}).status_code==410
    with pytest.raises(ValueError):engine.enqueue(pid,models.JobRequest(capability='narrative'))
    with pytest.raises(ValueError):engine.save_plan(pid,plan,1,'must not save')
    assert snapshot()==children and path.read_bytes()==original
    assert store.project(other)==other_before
    assert client.post('/api/projects/'+pid+'/undelete').status_code==200
    assert store.project(pid)==before
    assert snapshot()==children and path.read_bytes()==original
    assert client.get('/api/projects?deleted=true').json()==[]
    assert client.get('/api/projects/'+pid).status_code==200


def test_missing_project(client):
    assert delete(client,'missing').status_code==400
    assert client.post('/api/projects/missing/undelete').status_code==400
