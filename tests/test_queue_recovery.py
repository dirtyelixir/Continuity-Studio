import json
import threading
from contextlib import nullcontext

import httpx
import pytest

from studio import comfy_health, comfy_images, engine, job_queue, local_images, store
from test_production import client, plan, create


def insert(pid, jid, capability='h3_strategy', state='queued', chapter=False):
    with store.db() as c:
        c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                  (jid,pid,capability,'',state,'deepseek',store.encode({'chapter_pipeline':chapter}),None,'',store.now(),store.now()))


def test_blocked_renderer_and_chapter_do_not_block_text(client, plan):
    pid=create(client,plan)
    insert(pid,'image','image');insert(pid,'chapter','storyboard',chapter=True)
    insert(pid,'text');insert(pid,'second-image','image')
    pool=job_queue.JobPool();release=threading.Event()
    image_started=threading.Event();chapter_started=threading.Event();second_started=threading.Event()
    def blocked(event):
        event.set();assert release.wait(5)
    try:
        first=pool.submit(lambda _:blocked(image_started),'image')
        chapter=pool.submit(lambda _:blocked(chapter_started),'chapter')
        assert image_started.wait(2) and chapter_started.wait(2)
        second=pool.submit(lambda _:second_started.set(),'second-image')
        assert pool.submit(lambda _:'text-completed','text').result(timeout=2)=='text-completed'
        assert not second_started.is_set()
        release.set();first.result(timeout=2);chapter.result(timeout=2);second.result(timeout=2)
    finally:
        release.set();pool.shutdown(wait=True)


def test_global_queue_projection_and_cancelled_entry_skipped(client,plan):
    pid=create(client,plan);other=create(client,plan)
    insert(other,'busy-image','image','running');insert(pid,'waiting-image','image')
    insert(other,'busy-chapter','storyboard','running',chapter=True);insert(pid,'waiting-text')
    snapshot=job_queue.snapshot()
    assert snapshot['waiting-image']['running']==1
    assert snapshot['waiting-image']['position']==1
    assert snapshot['waiting-text']['running']==0
    shown=client.get('/api/jobs/waiting-image').json()['queue']
    assert shown['label']=='圖片生成' and shown['running_projects']==['Test']
    assert next(j for j in client.get('/api/projects/'+pid).json()['jobs'] if j['id']=='waiting-image')['queue']==shown
    assert client.post('/api/jobs/waiting-image/cancel').json()['state']=='cancelled'
    engine.execute('waiting-image')
    assert store.job('waiting-image')['state']=='cancelled'
    assert 'waiting-image' not in job_queue.snapshot()


def test_restart_preserves_queue_but_never_resubmits_running(client,plan,monkeypatch):
    pid=create(client,plan)
    insert(pid,'waiting');insert(pid,'running',state='running');insert(pid,'cancelled',state='running')
    work=store.DATA/'jobs'/'cancelled';work.mkdir(parents=True);(work/'cancel-requested').touch()
    waiting=store.job('waiting');scheduled=[]
    monkeypatch.setattr(engine.POOL,'submit',lambda fn,jid:scheduled.append(jid))
    store.init();engine.start_pending()
    assert scheduled==['waiting']
    assert store.job('waiting')==waiting
    assert store.job('running')['state']=='interrupted'
    assert store.job('cancelled')['state']=='cancelled'


def test_dead_renderer_fails_before_paid_preparation(client,plan,monkeypatch):
    pid=create(client,plan);insert(pid,'image','image')
    with store.db() as c:c.execute('UPDATE jobs SET provider="comfy_local" WHERE id="image"')
    def dead(work):raise RuntimeError('ComfyUI 執行緒已停止')
    monkeypatch.setattr(comfy_images,'preflight',dead)
    monkeypatch.setattr(engine.providers,'run',lambda *a:pytest.fail('No paid preparation or image request'))
    engine.execute('image')
    assert store.job('image')['state']=='failed'
    assert '執行緒已停止' in store.job('image')['error']


def saved_receipt(work):
    import hashlib
    plan=local_images.select({'image_source':{'target_kind':'prop'},'images':[], 'image_reference_roles':[], 'source_asset_id':''})
    receipt={'phase':'submitted','prompt_id':'original',
             'plan_hash':hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest(),
             'prompt_hash':hashlib.sha256(b'exact').hexdigest()}
    (work/'comfy-receipt.json').write_text(json.dumps(receipt))
    return {**local_images.PROVIDER,'local_plan':plan},receipt


def transport(monkeypatch, handler):
    real=httpx.Client
    monkeypatch.setattr(comfy_images.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))


def test_cancel_exits_poll_without_remote_interrupt_or_late_adoption(tmp_path,monkeypatch):
    provider,receipt=saved_receipt(tmp_path);requests=[]
    def handler(req):
        requests.append(req.url.path)
        assert req.method=='GET' and req.url.path=='/history/original'
        assert req.extensions['timeout']['read']==10
        (tmp_path/'cancel-requested').touch()
        return httpx.Response(200,json={})
    transport(monkeypatch,handler)
    monkeypatch.setattr(comfy_images.time,'sleep',lambda _:pytest.fail('Cancellation should exit before sleeping'))
    with pytest.raises(RuntimeError,match='取消'):comfy_images.run(provider,'exact',[],tmp_path)
    assert requests==['/history/original']
    assert json.loads((tmp_path/'comfy-receipt.json').read_text())==receipt
    assert not (tmp_path/'result.json').exists()


def test_dead_executor_fails_wait_and_blocks_new_submission(tmp_path,monkeypatch):
    provider,receipt=saved_receipt(tmp_path);requests=[]
    failure={'kind':'executor_stopped','pid':123,'message':'ComfyUI 執行緒已停止'}
    def handler(req):
        requests.append(req.url.path)
        assert req.method=='GET'
        if req.url.path=='/history/original':return httpx.Response(200,json={})
        assert req.url.path=='/vram/status'
        return httpx.Response(200,json={'ok':True,'monitor_alive':True,'pid':123})
    transport(monkeypatch,handler)
    monkeypatch.setattr(comfy_health,'worker_failure',lambda pid:failure)
    monkeypatch.setattr(comfy_images.time,'sleep',lambda _:pytest.fail('Do not keep polling dead worker'))
    with pytest.raises(RuntimeError,match='已停止'):comfy_images.run(provider,'exact',[],tmp_path)
    assert json.loads((tmp_path/'comfy-service-error.json').read_text())==failure
    assert json.loads((tmp_path/'comfy-receipt.json').read_text())==receipt
    new=tmp_path/'new';new.mkdir()
    from studio import comfy_recovery
    def blocked(work):raise RuntimeError('ComfyUI 執行緒已停止')
    monkeypatch.setattr(comfy_recovery,'ensure_ready',blocked)
    monkeypatch.setattr(comfy_images.comfy_runtime,'reserve',lambda _:nullcontext())
    with pytest.raises(RuntimeError,match='已停止'):comfy_images.run(provider,'exact',[],new)
    assert '/prompt' not in requests and not (new/'comfy-receipt.json').exists()


def test_slow_healthy_renderer_is_not_declared_dead(tmp_path,monkeypatch):
    provider,_=saved_receipt(tmp_path);sleeps=[]
    def handler(req):
        if req.url.path=='/history/original':return httpx.Response(200,json={})
        assert req.url.path=='/vram/status'
        return httpx.Response(200,json={'ok':True,'monitor_alive':True,'pid':123})
    transport(monkeypatch,handler);monkeypatch.setattr(comfy_health,'worker_failure',lambda _:None)
    def sleep(seconds):
        sleeps.append(seconds);(tmp_path/'cancel-requested').touch()
    monkeypatch.setattr(comfy_images.time,'sleep',sleep)
    with pytest.raises(RuntimeError,match='取消'):comfy_images.run(provider,'exact',[],tmp_path)
    assert sleeps==[2] and not (tmp_path/'comfy-service-error.json').exists()


def test_receipt_recovery_prefers_completed_output_even_after_executor_died(tmp_path,monkeypatch):
    from test_local_images import setup_transport
    provider,requests,_=setup_transport(monkeypatch,tmp_path,lost=True)
    with pytest.raises(RuntimeError,match='狀態未明'):comfy_images.run(provider,'exact',[],tmp_path)
    monkeypatch.setattr(comfy_health,'worker_failure',lambda _:pytest.fail('Read existing history before checking current executor'))
    assert comfy_images.run(provider,'exact',[],tmp_path)['image_path']
    assert len([r for r in requests if r.url.path=='/prompt'])==1


def test_local_journal_requires_exact_executor_thread_death(tmp_path,monkeypatch):
    # Fake only the read-only process identity and journal boundary.
    from pathlib import Path
    root=tmp_path/'proc';(root/'123').mkdir(parents=True)
    comfy=tmp_path/'ComfyUI';comfy.mkdir();(root/'123'/'cwd').symlink_to(comfy)
    (root/'123'/'cmdline').write_bytes(b'python3\0main.py\0')
    (root/'123'/'stat').write_text('123 (python3) '+' '.join(['0']*19+['100']+['0']*4))
    (root/'stat').write_text('btime 1000\n')
    monkeypatch.setattr(comfy_health,'Path',lambda value:root if value=='/proc' else root/'stat' if value=='/proc/stat' else Path(value))
    from types import SimpleNamespace
    logs=['CUDA memory warning','Exception in thread Thread-3 (prompt_worker):']
    def journal(cmd,**kwargs):
        assert '_PID=123' in cmd and '-b' in cmd and kwargs['timeout']==3
        return SimpleNamespace(returncode=0,stdout=logs.pop(0))
    monkeypatch.setattr(comfy_health.subprocess,'run',journal)
    assert comfy_health.worker_failure(123) is None
    assert comfy_health.worker_failure(123)['kind']=='executor_stopped'
    assert comfy_health.worker_failure(None) is None
