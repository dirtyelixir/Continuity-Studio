import json

import httpx
import pytest

from studio import comfy_recovery as recovery,comfy_images,store,engine
from test_production import client,plan,create


def setup_job(client,plan,state='failed'):
    pid=create(client,plan);jid=store.uid()
    with store.db() as c:
        c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)',(jid,pid,'image','room',state,'comfy_local','{}',None,'dead worker',store.now(),store.now()))
    work=store.DATA/'jobs'/jid;work.mkdir(parents=True)
    receipt={'prompt_id':'original','phase':'submitted','token':'original-token'}
    (work/'comfy-receipt.json').write_text(json.dumps(receipt))
    return jid,work,receipt


def wire(monkeypatch,jid,*,lost=False,busy=False,wrong_pid=False):
    calls=[];server={'ready':False}
    result={'ok':True,'ready':True,'state':'ready','operation_id':'10-100','old_pid':10,'new_pid':11,'mode':'klein',
            'affected':[{'job_id':jid,'prompt_id':'original','queue_state':'pending'}]}
    def handler(req):
        calls.append((req.method,req.url.port,req.url.path))
        if req.url.path=='/vram/comfy/recover':
            assert json.loads(req.content)=={'expected_pid':10,'expected_identity':'100','owned_prompts':{'original':jid}}
            if busy:return httpx.Response(409,json={'error':'有其他 GPU 工作'})
            server['ready']=True
            if lost:raise httpx.ReadTimeout('lost response')
            return httpx.Response(200,json=result)
        assert req.url.path=='/vram/status'
        live={'pid':11 if server['ready'] else 10,'ok':True,'monitor_alive':True,'last_error':None}
        if req.url.port==8188:
            if wrong_pid:live['pid']=99
            return httpx.Response(200,json=live)
        return httpx.Response(200,json={'ok':True,'comfy':live,'comfy_mode':{'running':'klein','configured':'klein'},'comfy_recovery':result if server['ready'] else {}})
    original=httpx.Client
    monkeypatch.setattr(recovery.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    monkeypatch.setattr(recovery.comfy_health,'worker_failure',lambda pid:{'kind':'executor_stopped'} if pid==10 else None)
    monkeypatch.setattr(recovery,'process_identity',lambda pid:'100')
    return calls,server,result


def test_studio_calls_only_scoped_manager_and_reconciles_without_repost(client,plan,monkeypatch):
    jid,work,receipt=setup_job(client,plan);before=(work/'comfy-receipt.json').read_bytes()
    calls,_,_=wire(monkeypatch,jid)
    assert recovery.tick()['phase']=='ready'
    assert json.loads((work/'service-recovery.json').read_text())['outcome']=='lost'
    assert (work/'comfy-receipt.json').read_bytes()==before
    assert not comfy_images.unresolved(work)
    assert '沒有自動重送' in store.job(jid)['error']
    recovery.tick()
    assert [p for m,_,p in calls if m=='POST']==['/vram/comfy/recover']
    assert client.get('/api/settings/local-images/recovery').json()['phase']=='ready'


def test_lost_recovery_response_queries_same_durable_outcome(client,plan,monkeypatch):
    jid,work,_=setup_job(client,plan);calls,_,_=wire(monkeypatch,jid,lost=True)
    assert recovery.tick()['phase']=='waiting'
    assert not (work/'service-recovery.json').exists()
    assert recovery.tick()['phase']=='ready'
    assert (work/'service-recovery.json').exists()
    assert len([c for c in calls if c[0]=='POST'])==1


def test_manager_refusal_preserves_work_and_does_not_use_global_release(client,plan,monkeypatch):
    jid,work,_=setup_job(client,plan);calls,_,_=wire(monkeypatch,jid,busy=True)
    assert recovery.tick()['phase']=='waiting'
    assert not (work/'service-recovery.json').exists()
    assert comfy_images.unresolved(work)
    assert all(path!='/vram/release-now' for _,_,path in calls)


def test_wrong_live_pid_never_claims_recovery(client,plan,monkeypatch):
    jid,work,_=setup_job(client,plan);wire(monkeypatch,jid,wrong_pid=True)
    assert recovery.tick()['phase']=='blocked'
    assert not (work/'service-recovery.json').exists()


def test_cancelled_job_is_not_revived(client,plan,monkeypatch):
    jid,work,_=setup_job(client,plan,state='cancelled');(work/'cancel-requested').touch()
    wire(monkeypatch,jid);recovery.tick()
    assert store.job(jid)['state']=='cancelled'
    assert not (work/'result.json').exists()


def test_completed_history_retained_and_unknown_job_path_rejected(client,plan):
    jid,work,_=setup_job(client,plan)
    history={'status':{'completed':True,'status_str':'success'},'outputs':{'save':{'images':[]}}}
    result={'operation_id':'10-100','old_pid':10,'new_pid':11,'affected':[
        {'job_id':'../../outside','prompt_id':'original','queue_state':'pending'},
        {'job_id':jid,'prompt_id':'wrong','queue_state':'pending'},
        {'job_id':jid,'prompt_id':'original','queue_state':'running','history':history}]}
    recovery.reconcile(result)
    assert json.loads((work/'recovered-history.json').read_text())==history
    assert comfy_images.unresolved(work)
    assert store.job(jid)['state']=='failed'  # Recoverable output is not automatic adoption.


def test_lost_prompt_after_external_restart_exits_without_long_poll(tmp_path,monkeypatch):
    from test_queue_recovery import saved_receipt,transport
    provider,receipt=saved_receipt(tmp_path)
    (tmp_path/'runtime-mode.json').write_text(json.dumps({'comfy_pid':10}))
    def handler(req):
        assert req.method=='GET'
        if req.url.path=='/history/original':return httpx.Response(200,json={})
        if req.url.path=='/vram/status':return httpx.Response(200,json={'ok':True,'monitor_alive':True,'pid':11})
        assert req.url.path=='/queue'
        return httpx.Response(200,json={'queue_running':[],'queue_pending':[]})
    transport(monkeypatch,handler);monkeypatch.setattr(comfy_images.comfy_health,'worker_failure',lambda pid:None)
    monkeypatch.setattr(comfy_images.time,'sleep',lambda _:pytest.fail('Lost receipt must not wait 30 minutes'))
    with pytest.raises(RuntimeError,match='沒有自動重送'):comfy_images.run(provider,'exact',[],tmp_path)
    assert not comfy_images.unresolved(tmp_path)
    assert json.loads((tmp_path/'comfy-receipt.json').read_text())==receipt


def test_preflight_calls_managed_repair_then_rechecks_renderer(tmp_path,monkeypatch):
    visits=[]
    def ready(*args):
        visits.append('check')
        if len(visits)==1:raise comfy_images.ExecutorStopped('dead')
    monkeypatch.setattr(comfy_images,'executor_ready',ready)
    monkeypatch.setattr(recovery,'ensure_ready',lambda work:visits.append('manager'))
    comfy_images.preflight(tmp_path)
    assert visits==['check','manager','check']
