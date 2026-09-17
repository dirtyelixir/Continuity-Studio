import copy,hashlib
from pathlib import Path
import pytest
from PIL import Image
from pydantic import ValidationError
from studio import store,engine,models,providers,identity_from_image
from test_production import client,plan,create,add_asset

RESULT={'description':'黑色短髮，黃色雨衣。','facts':['三顆深色鈕扣。'],'uncertainties':['背部細節不清晰。']}

@pytest.fixture
def setup(client,plan,monkeypatch):
    monkeypatch.setattr(engine.POOL,'submit',lambda *args:None)
    monkeypatch.setattr(providers,'resolve',lambda cap:{'id':'vision','kind':'http','capabilities':[cap],'model':'vision'})
    pid=create(client,plan);aid=add_asset(pid,plan,'ada')
    return client,pid,aid

def request(client,pid,aid,target='ada'):
    return client.post(f'/api/projects/{pid}/jobs',json={'capability':'identity_from_image','target_id':target,'source_asset_id':aid})

def test_exact_source_frozen_dedup_and_no_adoption(setup,monkeypatch):
    client,pid,aid=setup;before=store.project(pid);assets=store.assets(pid)
    r=request(client,pid,aid);assert r.status_code==200,r.text
    job=r.json()['job'];data=job['input'];path=Path(data['images'][0])
    assert path.parent==store.DATA/'jobs'/job['id']
    assert data['source_asset_id']==aid and data['reference_ids']==[aid]
    assert hashlib.sha256(path.read_bytes()).hexdigest()==data['identity_source']['sha256']
    assert request(client,pid,aid).json()['job']['id']==job['id']
    second=add_asset(pid,before['production'],'ada')
    rejected=add_asset(pid,before['production'],'ada',status='rejected')
    assert request(client,pid,second).status_code==400
    original=store.DATA/assets[0]['path'];Image.new('RGB',(256,256),'blue').save(original)
    seen=[]
    def run(provider,cap,prompt,images,work):
        assert cap=='identity_from_image' and images==[path]
        assert hashlib.sha256(images[0].read_bytes()).hexdigest()==data['identity_source']['sha256']
        assert '四視圖' in prompt and '逐字' in prompt
        seen.append(provider);return RESULT
    monkeypatch.setattr(providers,'run',run);engine.execute(job['id'])
    saved=store.job(job['id']);assert saved['state']=='succeeded',saved['error'];assert saved['result']==RESULT
    assert store.project(pid)==before
    assert {a['id']:a['status'] for a in store.assets(pid)}=={aid:'approved',second:'approved',rejected:'rejected'}
    assert len(seen)==1

def test_foreign_wrong_missing_and_voice_sources(setup,plan):
    client,pid,aid=setup
    other=create(client,plan);foreign=add_asset(other,plan,'ada');room=add_asset(pid,plan,'room')
    for source in ('',foreign,room,'absent'):assert request(client,pid,source).status_code==400
    assert request(client,pid,aid,'start').status_code==400
    p=copy.deepcopy(plan);p['canon'][0]['kind']='voice'
    engine.save_plan(pid,p,1,'voice')
    assert request(client,pid,aid).status_code==400

def test_missing_corrupt_and_changed_pixels(setup,monkeypatch):
    client,pid,aid=setup;asset=store.assets(pid)[0];path=store.DATA/asset['path']
    raw=path.read_bytes();path.unlink();assert request(client,pid,aid).status_code==400
    path.write_bytes(b'bad');assert request(client,pid,aid).status_code==400
    path.write_bytes(raw);job=request(client,pid,aid).json()['job']
    Path(job['input']['images'][0]).write_bytes(b'changed')
    monkeypatch.setattr(providers,'run',lambda *args:pytest.fail('corrupt frozen input must never reach provider'))
    engine.execute(job['id']);assert store.job(job['id'])['state']=='failed'

def test_schema_requires_meaningful_bounded_fields():
    model=providers.result_model('identity_from_image');assert model is identity_from_image.IdentityResult
    for bad in ({**RESULT,'description':' '},{**RESULT,'facts':[' ']},{**RESULT,'scope':'public'},{**RESULT,'facts':[]}):
        with pytest.raises(ValidationError):model.model_validate(bad)
    assert 'identity_from_image' in providers.BUILTINS

def test_manual_draft_and_cancel_never_edit_canon(setup,monkeypatch):
    client,pid,aid=setup;before=store.project(pid)
    monkeypatch.setattr(providers,'resolve',lambda cap:{'id':'manual','kind':'manual','capabilities':[cap],'model':'human'})
    job=request(client,pid,aid).json()['job'];assert job['state']=='awaiting_input'
    assert Path(job['input']['images'][0]).is_file()
    response=client.post('/api/jobs/'+job['id']+'/manual',json=RESULT);assert response.status_code==200,response.text
    assert store.project(pid)==before
    job=request(client,pid,aid).json()['job'];client.post('/api/jobs/'+job['id']+'/cancel')
    engine.finish(store.job(job['id']),RESULT)
    assert store.job(job['id'])['state']=='cancelled'
    assert store.project(pid)==before
