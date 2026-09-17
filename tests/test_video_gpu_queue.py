"""Pre-admission retries only: isolated manager and Comfy protocol fixtures."""
from contextlib import contextmanager
import json

import httpx
import pytest

from studio import comfy_runtime as runtime, video_render as vr
from test_production import client, plan
from test_h3_render_graph import schema
from test_video_render import local, request_for, send


@pytest.mark.parametrize('path,reason', [
    ('/vram/gpu/acquire', 'GPU busy; timed out waiting for its current owner'),
    ('/vram/comfy/mode', '有工作／預約；請等工作完成再啟動或切換'),
    ('/vram/comfy/mode', 'ComfyUI 有生成／排隊／提交中工作，未有切換模式'),
])
def test_exact_pre_admission_busy_classification(path, reason):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(409, json={'error': reason})), base_url='http://test') as c:
        with pytest.raises(runtime.AdmissionBusy):
            runtime.request(c, 'POST', path)


@pytest.mark.parametrize('reason', ['Admissions paused by immediate release', 'Lease cancelled or owner exited',
    '模式設定已更新，但 ComfyUI 未通過啟動檢查；請查看服務紀錄', 'GPU busy'])
def test_other_refusals_do_not_retry(reason):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(409, json={'error': reason})), base_url='http://test') as c:
        with pytest.raises(ValueError) as caught:
            runtime.request(c, 'POST', '/vram/comfy/mode')
        assert not isinstance(caught.value, runtime.AdmissionBusy)


def test_native_pending_lease_timeout_and_release(monkeypatch):
    calls=[]
    def handler(r):
        body=json.loads(r.content) if r.content else {}
        calls.append((r.url.path, body))
        if r.url.path=='/vram/status':
            return httpx.Response(200,json={'ok':True,'comfy_mode':{'running':'h3','configured':'h3'}})
        if r.url.path=='/vram/gpu/acquire':
            assert body['timeout']==30
            assert r.extensions['timeout']['read'] > 30
            return httpx.Response(409,json={'ok':False,'error':'GPU busy; timed out waiting for its current owner'})
        assert r.url.path=='/vram/gpu/release'
        return httpx.Response(200,json={'ok':True})
    original=httpx.Client
    monkeypatch.setattr(runtime.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    with pytest.raises(runtime.AdmissionBusy):
        with runtime.reserve('h3',wait_seconds=30):
            pytest.fail('must not yield')
    assert calls[-1][1]['token']==calls[1][1]['token']


def test_repeated_busy_retains_same_take_then_submits_once(client,local,monkeypatch):
    pid,remote=local
    request=request_for(client,pid)
    take=send(client,pid,request)
    attempts=[]
    @contextmanager
    def reserve(mode, **kw):
        attempts.append(mode)
        current=vr.take(pid,take['id'])
        assert current['state']=='queued' and '等候 GPU' in current['error']
        assert remote['posts']==0 and not remote['uploads']
        assert send(client,pid,{**request,'request_key':'newrequestkey1234'})['id']==take['id']
        if len(attempts)<=3:
            raise runtime.AdmissionBusy('GPU busy')
        yield {'mode':mode}
    monkeypatch.setattr(runtime,'reserve',reserve)
    monkeypatch.setattr(vr.STOP,'wait',lambda _:False)
    vr.run(pid,take['id'])
    assert len(attempts)==4 and remote['posts']==1
    assert vr.take(pid,take['id'])['state']=='succeeded'


def test_shutdown_retains_unsubmitted_queue(client,local,monkeypatch):
    pid,remote=local;take=send(client,pid,request_for(client,pid))
    @contextmanager
    def reserve(*a,**kw):
        raise runtime.AdmissionBusy('GPU busy')
        yield
    monkeypatch.setattr(runtime,'reserve',reserve)
    monkeypatch.setattr(vr.STOP,'wait',lambda _:True)
    vr.run(pid,take['id'])
    assert vr.take(pid,take['id'])['state']=='queued'
    assert remote['posts']==0 and not remote['uploads']


def test_ambiguous_admission_is_not_retried(client,local,monkeypatch):
    pid,remote=local;take=send(client,pid,request_for(client,pid));calls=[]
    @contextmanager
    def reserve(*a,**kw):
        calls.append(1)
        raise httpx.ReadTimeout('ambiguous manager response')
        yield
    monkeypatch.setattr(runtime,'reserve',reserve)
    vr.run(pid,take['id'])
    assert len(calls)==1 and remote['posts']==0
    assert vr.take(pid,take['id'])['state']=='failed'


def test_busy_error_after_admission_does_not_replay_body(client,local,monkeypatch):
    pid,remote=local;take=send(client,pid,request_for(client,pid));calls=[]
    def submit(*args):
        calls.append(1)
        raise runtime.AdmissionBusy('not an admission error here')
    monkeypatch.setattr(vr.provider,'submit',submit)
    vr.run(pid,take['id'])
    assert len(calls)==1 and vr.take(pid,take['id'])['state']=='uncertain'
