import copy
import httpx
import pytest
from studio import comfy_bridge,store
from test_production import client,plan,create,add_asset


def mock_comfy(monkeypatch,handler):
    original=httpx.Client
    monkeypatch.setattr(comfy_bridge.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))


def test_send_original_to_local_input_without_changing_project(client,plan,monkeypatch):
    pid=create(client,plan);aid=add_asset(pid,plan,'ada');before=copy.deepcopy(store.assets(pid))
    pixels=(store.DATA/before[0]['path']).read_bytes();calls=[]
    subfolder='Continuity Studio/Test-'+pid
    def upload(request):
        calls.append(request)
        assert str(request.url)=='http://127.0.0.1:8188/upload/image'
        assert request.method=='POST' and pixels in request.content
        assert b'name="overwrite"\r\n\r\nfalse' in request.content
        assert b'name="type"\r\n\r\ninput' in request.content
        assert subfolder.encode() in request.content
        return httpx.Response(200,json={'name':'Ada-reference.png','subfolder':subfolder,'type':'input'})
    mock_comfy(monkeypatch,upload)
    response=client.post('/api/assets/'+aid+'/comfy',json={})
    assert response.status_code==200 and len(calls)==1
    assert response.json()['relative_path']==subfolder+'/Ada-reference.png'
    assert store.assets(pid)==before and (store.DATA/before[0]['path']).read_bytes()==pixels
    assert not store.jobs(pid)
    assert client.post('/api/assets/missing/comfy',json={}).status_code==400 and len(calls)==1


@pytest.mark.parametrize('failure',['offline','http','invalid'])
def test_transfer_failure_is_reported_without_success(client,plan,monkeypatch,failure):
    pid=create(client,plan);aid=add_asset(pid,plan,'ada');before=copy.deepcopy(store.assets(pid))
    def upload(request):
        if failure=='offline':raise httpx.ConnectError('offline',request=request)
        return httpx.Response(503) if failure=='http' else httpx.Response(200,json={'name':'other.png','type':'output'})
    mock_comfy(monkeypatch,upload)
    response=client.post('/api/assets/'+aid+'/comfy',json={})
    assert response.status_code==400 and 'ComfyUI' in response.json()['detail']
    assert store.assets(pid)==before
