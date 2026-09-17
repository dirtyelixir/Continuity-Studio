from studio import store,engine
from test_production import client,plan,create


def test_running_cancel_discards_late_output_and_blocks_duplicate(client,plan):
    pid=create(client,plan)
    client.post('/api/settings/routing',json={'capability':'h3_strategy','provider_id':'manual'})
    j=client.post(f'/api/projects/{pid}/jobs',json={'capability':'h3_strategy','target_id':'shot'}).json()['job']
    with store.db() as c:c.execute('UPDATE jobs SET state="running" WHERE id=?',(j['id'],))
    r=client.post('/api/jobs/'+j['id']+'/cancel');assert r.status_code==200
    assert r.json()['state']=='running' and '已要求取消' in r.json()['error']
    engine.finish(j,{}) # No result validation or persistence after cancellation.
    assert store.job(j['id'])['state']=='cancelled'
    assert not store.assets(pid)


def test_manual_cancel_is_immediate(client,plan):
    pid=create(client,plan);client.post('/api/settings/routing',json={'capability':'h3_strategy','provider_id':'manual'})
    j=client.post(f'/api/projects/{pid}/jobs',json={'capability':'h3_strategy','target_id':'shot'}).json()['job']
    assert client.post('/api/jobs/'+j['id']+'/cancel').json()['state']=='cancelled'
    assert client.post('/api/jobs/'+j['id']+'/cancel').status_code==400


def test_codex_cancel_terminates_only_its_process_group(tmp_path,monkeypatch):
    import subprocess,pytest,signal
    from studio import providers
    work=tmp_path/'job';work.mkdir();(work/'cancel-requested').touch();signals=[]
    class Process:
        pid=12345
        def __init__(self,*args,**kwargs):assert kwargs['start_new_session']
        def communicate(self,*args,**kwargs):raise subprocess.TimeoutExpired('codex',1)
        def wait(self,timeout):return 0
    monkeypatch.setattr(providers.shutil,'which',lambda x:'/mock/codex')
    monkeypatch.setattr(providers.subprocess,'Popen',Process)
    monkeypatch.setattr(providers.os,'killpg',lambda pid,sig:signals.append((pid,sig)))
    with pytest.raises(RuntimeError,match='取消'):providers.codex_run(providers.DEFAULT,'image','test',[],work)
    assert signals==[(12345,signal.SIGTERM)]
