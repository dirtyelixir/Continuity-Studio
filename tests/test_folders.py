import subprocess
from pathlib import Path
import pytest
from studio import folders,store
from test_production import client,plan,create,add_asset


def test_real_production_folder_and_file_preview(client,plan):
    pid=create(client,plan);aid=add_asset(pid,plan,'ada')
    r=client.post(f'/api/projects/{pid}/folder',json={});assert r.status_code==200
    data=r.json();path=Path(data['path']);assert path.is_dir()
    files={f['name']:f for f in data['files']}
    assert {'production.json','screenplay.md','h3/drafts/shot.txt'}<=files.keys()
    image=files[f'assets/{pid}/{aid}.png']
    assert client.get(image['url']).content==(store.DATA/'assets'/pid/(aid+'.png')).read_bytes()
    assert 'Light.' in client.get(files['screenplay.md']['url']).text
    (path/'my-notes.txt').write_text('Keep this')
    again=client.post(f'/api/projects/{pid}/folder',json={}).json()
    assert again['path']==data['path'] and (path/'my-notes.txt').read_text()=='Keep this'
    changed=dict(plan,title='New title')
    client.put(f'/api/projects/{pid}/plan',json={'revision':1,'production':changed})
    new=client.post(f'/api/projects/{pid}/folder',json={}).json()
    assert new['path']!=data['path'] and (path/'my-notes.txt').exists()


def test_idea_folder_before_adopting_plan(client):
    p=client.post('/api/projects',json={'title':'An idea','idea':'A robot discovers a star'}).json()
    result=client.post(f'/api/projects/{p["id"]}/folder',json={}).json()
    files={f['name']:f for f in result['files']}
    assert 'A robot discovers a star' in client.get(files['idea.md']['url']).text


def test_folder_rejects_path_and_symlink_escapes(client,plan,tmp_path):
    pid=create(client,plan);data=client.post(f'/api/projects/{pid}/folder',json={}).json();path=Path(data['path'])
    secret=tmp_path/'private.txt';secret.write_text('not public');(path/'escape.txt').symlink_to(secret)
    with pytest.raises(ValueError): folders.snapshot_file(pid,path.name,'../private.txt')
    with pytest.raises(ValueError): folders.snapshot_file(pid,path.name,'escape.txt')
    assert client.get(f'/api/projects/{pid}/folder/{path.name}/escape.txt').status_code==400
    assert client.get(f'/api/projects/{pid}/folder/bad/production.json').status_code==400
    assert client.post('/api/projects/missing/folder',json={}).status_code==400


def test_open_file_manager_success_and_failure(client,plan,monkeypatch):
    pid=create(client,plan);calls=[]
    monkeypatch.setattr(folders.shutil,'which',lambda _: '/usr/bin/xdg-open')
    def opened(args,**kwargs): calls.append(args);return subprocess.CompletedProcess(args,0)
    monkeypatch.setattr(folders.subprocess,'run',opened)
    r=client.post(f'/api/projects/{pid}/folder/open',json={})
    assert r.status_code==200 and r.json()['opened'] and calls==[['/usr/bin/xdg-open',r.json()['path']]]
    monkeypatch.setattr(folders.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess(a,1))
    assert client.post(f'/api/projects/{pid}/folder/open',json={}).status_code==400


def test_ui_assets_are_versioned_and_revalidated(client,tmp_path,monkeypatch):
    static=tmp_path/'static';static.mkdir()
    (static/'index.html').write_text('<script src="/static/app.js"></script><link href="/static/style.css">')
    (static/'app.js').write_text('old UI');(static/'style.css').write_text('body{}')
    monkeypatch.setattr(store,'ROOT',tmp_path)
    first=client.get('/');assert first.headers['cache-control']=='no-cache'
    assert '/static/app.js?v=' in first.text and '/static/style.css?v=' in first.text
    (static/'app.js').write_text('Production folder')
    second=client.get('/');assert second.text!=first.text
    assert client.get('/static/app.js').headers['cache-control']=='no-cache'


def test_reveal_selects_original_without_creating_a_copy(client,plan,monkeypatch):
    pid=create(client,plan);aid=add_asset(pid,plan,'ada');original=store.DATA/'assets'/pid/(aid+'.png')
    before=original.read_bytes();calls=[]
    monkeypatch.setattr(folders.shutil,'which',lambda _: '/usr/bin/gdbus')
    def reveal(args,**kwargs):calls.append(args);return subprocess.CompletedProcess(args,0)
    monkeypatch.setattr(folders.subprocess,'run',reveal)
    response=client.post(f'/api/assets/{aid}/reveal',json={})
    assert response.status_code==200 and response.json()=={'path':str(original),'revealed':True}
    import json
    assert calls[0][-3:] == ['org.freedesktop.FileManager1.ShowItems',json.dumps([original.as_uri()]),'']
    assert original.read_bytes()==before and not (store.DATA/'productions').exists()
    assert client.post('/api/assets/missing/reveal',json={}).status_code==400
    monkeypatch.setattr(folders.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess(a,1))
    assert client.post(f'/api/assets/{aid}/reveal',json={}).status_code==400
