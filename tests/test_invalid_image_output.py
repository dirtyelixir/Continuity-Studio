"""Transport completion cannot turn an empty rendered image into an asset."""
import io
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image

from studio import comfy_images as comfy, engine, store, models
from test_local_images import setup_transport, offline_image_catalog
from test_production import client, plan, create, add_asset


def test_black_comfy_output_preserves_receipt_and_never_reposts(monkeypatch,tmp_path):
    provider,requests,_=setup_transport(monkeypatch,tmp_path)
    buf=io.BytesIO();Image.new('RGB',(1024,1024),'black').save(buf,format='PNG')
    original=comfy.httpx.Client
    def make_client(**kwargs):
        client=original(**kwargs);get=client.get
        def read(url,**options):
            response=get(url,**options)
            return httpx.Response(200,content=buf.getvalue(),request=response.request) if url=='/view' else response
        client.get=read
        return client
    monkeypatch.setattr(comfy.httpx,'Client',make_client)
    for _ in range(2):
        with pytest.raises(ValueError):comfy.run(provider,'same prompt',[],tmp_path)
    receipt=json.loads((tmp_path/'comfy-receipt.json').read_text())
    assert receipt['phase']=='invalid_output' and receipt['prompt_id']=='pid'
    assert receipt['sha256'] and (tmp_path/'render.png').read_bytes()==buf.getvalue()
    assert not (tmp_path/'result.json').exists()
    assert not comfy.unresolved(tmp_path)
    assert len([r for r in requests if r.url.path=='/prompt'])==1
    assert not json.loads((tmp_path/'output-quality.json').read_text())['valid']


def test_generic_provider_blank_output_cannot_be_persisted(client,plan):
    pid=create(client,plan)
    client.post('/api/settings/routing',json={'capability':'image','provider_id':'manual'})
    j=engine.enqueue(pid,models.JobRequest(capability='image',target_id='room'))['job']
    work=store.DATA/'jobs'/j['id'];work.mkdir(parents=True,exist_ok=True)
    path=work/'blank.png';Image.new('RGB',(256,256),'black').save(path)
    # Exercise the common persistence boundary independent of prompt preparation.
    j['input'].pop('image_source',None)
    with pytest.raises(ValueError):engine.persist_image(j,{'image_path':str(path),'notes':'Bad output'})
    assert not store.assets(pid)
    assert path.is_file()


def test_legacy_black_output_is_read_only_failure_and_cannot_be_approved(client,plan):
    pid=create(client,plan);aid=add_asset(pid,plan,'start',status='pending')
    a=store.assets(pid)[0];path=store.DATA/a['path'];Image.new('RGB',(256,256),'black').save(path)
    with store.db() as c:c.execute('UPDATE assets SET job_id=?,provider=? WHERE id=?',('legacy-render','comfy_local',aid))
    before=store.assets(pid)
    response=client.get('/api/projects/'+pid)
    assert response.status_code==200,response.text
    result=next(a for a in response.json()['assets'] if a['id']==aid)
    assert not result['image_output_quality']['valid']
    assert store.assets(pid)==before and path.is_file()
    with pytest.raises(ValueError):engine.decide_asset(aid,'approved','Accept',True)
    assert store.assets(pid)==before


def test_legacy_black_cannot_be_used_as_edit_source(client,plan):
    pid=create(client,plan);aid=add_asset(pid,plan,'room',status='pending')
    a=store.assets(pid)[0];Image.new('RGB',(256,256),'black').save(store.DATA/a['path'])
    with store.db() as c:c.execute('UPDATE assets SET job_id=? WHERE id=?',('legacy-render',aid))
    with pytest.raises(ValueError,match='修改來源無有效畫面'):
        engine.enqueue(pid,models.JobRequest(capability='image_prepare',target_id='room',source_asset_id=aid))
