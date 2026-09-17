import io
from pathlib import Path
import pytest
from PIL import Image
from studio import store,engine,models,input_references,character_sheets
from test_production import client,plan,create


def picture():
    b=io.BytesIO();Image.new('RGB',(300,300),'red').save(b,format='PNG');return b.getvalue()


def upload(client,pid,purpose='style',target=''):
    r=client.post('/api/projects/'+pid+'/input-references',data={'purpose':purpose,'target_id':target},files={'file':('我的參考.png',picture(),'image/png')})
    assert r.status_code==200,r.text
    return r.json()


def test_upload_only_stores_original_no_images_jobs_or_approvals(client,plan):
    pid=create(client,plan);before=store.project(pid)
    ref=upload(client,pid)
    assert not store.jobs(pid) and not store.assets(pid)
    assert store.project(pid)==before
    assert (store.DATA/ref['path']).read_bytes()==picture()
    assert 'Style References/作品共用-風格參考-v001.png' in ref['path']
    assert ref['original_filename']=='我的參考.png'
    p=client.get('/api/projects/'+pid).json()
    assert p['input_references']==[ref]
    assert client.get(f'/api/projects/{pid}/input-references/{ref["id"]}/image').content==picture()


def test_explicit_generation_attaches_selected_refs_and_role_instructions(client,plan):
    pid=create(client,plan);style=upload(client,pid);identity=upload(client,pid,'identity','ada')
    # Opening a form, saving a reference or compiling a request is not execution.
    data,_=engine.build_input(store.project(pid),models.JobRequest(capability='image',target_id='ada',input_reference_ids=[style['id'],identity['id']]))
    assert [r['id'] for r in data['input_references']]==[style['id'],identity['id']]
    assert str(store.DATA/style['path']) in data['images'] and str(store.DATA/identity['path']) in data['images']
    assert 'STYLE ONLY' in data['image_prompt'] and 'SUBJECT/DESIGN INPUT' in data['image_prompt']
    assert data['character_sheet_layout']=='four-view-v2'
    assert not data['reference_ids'] and not store.jobs(pid) and not store.assets(pid)
    empty,_=engine.build_input(store.project(pid),models.JobRequest(capability='image',target_id='ada'))
    assert not empty['input_references'] and str(store.DATA/style['path']) not in empty['images']


def test_wrong_project_target_duplicate_or_changed_input_rejected(client,plan):
    pid=create(client,plan);other=create(client,plan)
    ref=upload(client,pid,'identity','ada')
    for project_id,target,ids in [(other,'ada',[ref['id']]),(pid,'room',[ref['id']]),(pid,'ada',[ref['id'],ref['id']])]:
        with pytest.raises(ValueError):input_references.resolve(project_id,target,ids)
    (store.DATA/ref['path']).write_bytes(b'changed')
    with pytest.raises(ValueError,match='改動'):input_references.resolve(pid,'ada',[ref['id']])
    assert not store.jobs(pid) and not store.jobs(other)


def test_invalid_upload_and_missing_target_do_not_create_jobs(client,plan):
    pid=create(client,plan)
    for purpose,target,content in [('style','',b'invalid'),('identity','',picture()),('identity','missing',picture()),('other','ada',picture())]:
        r=client.post('/api/projects/'+pid+'/input-references',data={'purpose':purpose,'target_id':target},files={'file':('x.png',content)})
        assert r.status_code==400
    assert not input_references.list_for(pid) and not store.jobs(pid)


def test_input_limit_counts_layout_and_never_silently_drops_selected_files(client,plan,monkeypatch,tmp_path):
    pid=create(client,plan)
    guide=tmp_path/'guide.png';guide.write_bytes(picture());monkeypatch.setattr(character_sheets,'guide_path',lambda:guide)
    refs=[upload(client,pid) for _ in range(5)]
    with pytest.raises(ValueError,match='6 張輸入'):
        engine.build_input(store.project(pid),models.JobRequest(capability='image',target_id='ada',input_reference_ids=[r['id'] for r in refs]))
    assert not store.jobs(pid)


def test_named_versions_are_independent_originals_and_exported(client,plan,tmp_path):
    import zipfile
    pid=create(client,plan)
    source=tmp_path/'messy screenshot.png';source.write_bytes(picture())
    r=client.post('/api/projects/'+pid+'/input-references',data={'purpose':'identity','target_id':'ada'},files={'file':(source.name,source.read_bytes(),'image/png')})
    assert r.status_code==200
    first=r.json();source.unlink()
    second=upload(client,pid,'identity','ada')
    assert 'Characters/Ada/Source References/Ada-外觀參考-v001.png' in first['path']
    assert second['path'].endswith('Ada-外觀參考-v002.png')
    assert input_references.path_for(first).read_bytes()==picture()
    assert client.get('/api/projects/'+pid+'/input-references/'+first['id']+'/path').json()['path']==str(store.DATA/first['path'])
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+pid+'/export').content)) as z:
        assert z.read(first['path'])==picture() and z.read(second['path'])==picture()
        assert first['original_filename'] in z.read('production-reference-index.json').decode()
    assert not store.jobs(pid) and not store.assets(pid)


def test_legacy_reference_organization_preserves_identity_and_old_path(client,plan):
    import hashlib
    pid=create(client,plan)
    old=store.DATA/'assets'/'legacy.png';old.write_bytes(picture())
    ref={'id':'old-ref','project_id':pid,'target_id':'ada','purpose':'identity','name':'Screenshot.png','path':'assets/legacy.png','sha256':hashlib.sha256(picture()).hexdigest(),'created':store.now()}
    store.put_setting('input-references:'+pid,[ref])
    assert input_references.organize(pid)==['old-ref']
    updated=input_references.get(pid,'old-ref')
    assert updated['sha256']==ref['sha256'] and updated['original_filename']=='Screenshot.png'
    assert updated['previous_paths']==['assets/legacy.png'] and old.read_bytes()==picture()
    assert input_references.path_for(updated).read_bytes()==picture()
    assert input_references.organize(pid)==[]
