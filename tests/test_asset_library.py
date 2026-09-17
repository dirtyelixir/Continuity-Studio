import copy,json
from pathlib import Path
from PIL import Image
from studio import store,engine,asset_library,h3
from test_production import client,plan,create,add_asset


def test_migration_preserves_bytes_ids_references_and_old_paths(client,plan):
    pid=create(client,plan);ada=add_asset(pid,plan,'ada');room=add_asset(pid,plan,'room');start=add_asset(pid,plan,'start',[ada,room]);add_asset(pid,plan,'ada',status='rejected')
    before={a['id']:a for a in store.assets(pid)};pixels={a['id']:(store.DATA/a['path']).read_bytes() for a in before.values()}
    old_h3=h3.compile_shot(plan,plan['shots'][0],list(before.values()))
    moves=asset_library.migrate_project(pid);assert len(moves)==4
    after={a['id']:a for a in store.assets(pid)}
    for aid,a in after.items():
        assert (store.DATA/a['path']).read_bytes()==pixels[aid]
        assert {k:v for k,v in a.items() if k!='path'}=={k:v for k,v in before[aid].items() if k!='path'}
        assert (store.DATA/before[aid]['path']).is_symlink()
        assert (store.DATA/before[aid]['path']).resolve()==(store.DATA/a['path']).resolve()
    assert '/Characters/Ada/Ada-reference-v' in after[ada]['path']
    assert '/Scenes/S01-Workshop/SH01-The switch/Opening-v001.png' in after[start]['path']
    new_h3=h3.compile_shot(plan,plan['shots'][0],list(after.values()))
    assert old_h3['references']!=new_h3['references'] and asset_library.same_references(old_h3['references'],new_h3['references'])
    assert asset_library.migrate_project(pid)==[]
    listing=(store.DATA/'assets'/'Test'/'Characters'/'Ada'/'Versions.md').read_text();assert 'approved' in listing and 'rejected' in listing
    assert client.get('/api/assets/'+start+'/image').content==pixels[start]


def test_new_images_get_versioned_original_names_and_metadata(client,plan):
    pid=create(client,plan)
    for version in [1,2]:
        jid=store.uid();source=store.DATA/'jobs'/jid/'input.png';source.parent.mkdir(parents=True);Image.new('RGB',(256,256),'blue').save(source)
        from studio import continuity
        job={'id':jid,'project_id':pid,'target_id':'ada','provider':'manual','input':{'dependency_hash':continuity.target_hash(plan,'ada'),'reference_ids':[],'image_prompt':'Original prompt','context':{},'production':plan}}
        with engine.LOCK:result=engine.persist_image(job,{'image_path':str(source),'notes':''})
        a=next(a for a in store.assets(pid) if a['id']==result['asset_id'])
        path=store.DATA/a['path'];assert path.name==f'Ada-reference-v{version:03d}.png'
        assert path.with_name(path.stem+'-prompt.txt').read_text()=='Original prompt'
        assert json.loads(path.with_suffix('.json').read_text())['id']==a['id']
    with store.db() as c:c.execute('UPDATE assets SET review=? WHERE id=?',(store.encode({'verdict':'pass','summary':'Test-only four-view review','issues':[],'character_sheet':'pass'}),a['id']))
    engine.decide_asset(a['id'],'approved','')
    assert 'approved' in (path.parent/'Versions.md').read_text()
    engine.decide_asset(a['id'],'rejected','Director changed direction')
    assert not path.exists() and not path.with_suffix('.json').exists()
    with store.db() as c:
        assert c.execute('SELECT count(*) FROM events WHERE kind="asset_deleted" AND project_id=?',(pid,)).fetchone()[0]==1


def test_safe_names_duplicate_projects_and_stable_folder(client,plan):
    first=create(client,plan);second=create(client,plan)
    assert asset_library.layout(first)['folder']=='Test'
    assert asset_library.layout(second)['folder']=='Test (2)'
    changed=copy.deepcopy(plan);changed['title']='Renamed'
    engine.save_plan(first,changed,1,'Rename')
    assert asset_library.layout(first)['folder']=='Test'
    assert asset_library.clean_name('../阿達 / test:*')=='-阿達 - test--'
    assert asset_library.clean_name('CON')=='CON-item'
    import pytest
    with pytest.raises(ValueError):asset_library.safe_path('../outside.png')


def test_library_open_uses_named_original_root(client,plan,monkeypatch):
    from studio import folders
    pid=create(client,plan);add_asset(pid,plan,'ada');asset_library.migrate_project(pid)
    paths=[]
    def opened(path):paths.append(path);return {'path':path,'opened':True}
    monkeypatch.setattr(folders,'open_folder',opened)
    response=client.post(f'/api/projects/{pid}/library/open',json={})
    assert response.status_code==200 and paths==[str(store.DATA/'assets'/'Test')]
    snapshot=client.post(f'/api/projects/{pid}/folder',json={}).json()
    assert snapshot['library_path']==paths[0] and snapshot['path']!=paths[0]


def test_copy_path_returns_resolved_original_without_export_or_desktop_action(client,plan):
    pid=create(client,plan);aid=add_asset(pid,plan,'ada')
    asset=store.assets(pid)[0];original=store.DATA/asset['path']
    named=store.DATA/'assets'/'作品 有空格'/'Ada 四視圖.png';named.parent.mkdir();original.rename(named);original.symlink_to(named)
    before=copy.deepcopy(store.assets(pid));pixels=named.read_bytes()
    response=client.get('/api/assets/'+aid+'/path')
    assert response.status_code==200 and response.json()=={'path':str(named.resolve())}
    assert store.assets(pid)==before and named.read_bytes()==pixels
    assert not (store.DATA/'productions').exists()
    assert client.get('/api/assets/missing/path').status_code==400
    named.unlink()
    assert client.get('/api/assets/'+aid+'/path').status_code==400
    outside=store.DATA/'outside.png';outside.write_bytes(pixels)
    original.unlink();original.symlink_to(outside)
    assert client.get('/api/assets/'+aid+'/path').status_code==400
