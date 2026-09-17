"""Readable production snapshots, separate from canonical storage."""
import io,json,re,shutil,subprocess,tempfile,zipfile
from pathlib import Path
from urllib.parse import quote
from . import store


def root(pid):
    store.project(pid)
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',pid): raise ValueError('Invalid project')
    path=store.DATA/'productions'/pid
    if any(p.is_symlink() for p in [store.DATA/'productions',path]): raise ValueError('Folder cannot be a symbolic link')
    return path


def snapshot_file(pid,snapshot,name):
    if not re.fullmatch(r'[0-9a-f]{24}',snapshot): raise ValueError('Invalid snapshot')
    base=root(pid)/snapshot
    rel=Path(name)
    if rel.is_absolute() or '..' in rel.parts: raise ValueError('Invalid file path')
    path=base/rel
    if base.is_symlink() or any(p.is_symlink() for p in [path,*path.parents] if p!=base.parent):
        raise ValueError('Symbolic links are not served')
    if not path.resolve().is_relative_to(base.resolve()) or not path.is_file(): raise ValueError('File not found')
    return path


def materialize(pid,production,package=None):
    base=root(pid);base.mkdir(parents=True,exist_ok=True)
    snapshot=store.digest(production)[:24];destination=base/snapshot
    if destination.is_symlink(): raise ValueError('Snapshot cannot be a symbolic link')
    if not destination.exists():
        temporary=Path(tempfile.mkdtemp(prefix='.preparing-',dir=base))
        try:
            if package is not None:
                with zipfile.ZipFile(io.BytesIO(package)) as z:
                    for item in z.infolist():
                        rel=Path(item.filename)
                        if rel.is_absolute() or '..' in rel.parts: raise ValueError('Invalid package path')
                        target=temporary/rel
                        if item.is_dir(): target.mkdir(parents=True,exist_ok=True);continue
                        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(item))
            else:
                (temporary/'production.json').write_text(json.dumps(production,ensure_ascii=False,indent=2))
                (temporary/'idea.md').write_text('# '+production['title']+'\n\n'+production['idea']+'\n\n## Visual direction\n\n'+production['style'])
                if production.get('source_kind','idea')!='idea':
                    (temporary/'source').mkdir()
                    (temporary/'source'/'original.txt').write_text(production['idea'])
            # Another request may already have completed this identical snapshot.
            if not destination.exists(): temporary.rename(destination)
        finally:
            if temporary.exists(): shutil.rmtree(temporary)
    files=[]
    for path in sorted(destination.rglob('*')):
        if not path.is_file() or path.is_symlink(): continue
        name=path.relative_to(destination).as_posix()
        try: snapshot_file(pid,snapshot,name)
        except ValueError: continue
        files.append({'name':name,'size':path.stat().st_size,'url':f'/api/projects/{pid}/folder/{snapshot}/'+quote(name,safe='/')})
    return {'path':str(destination.resolve()),'files':files}


def open_folder(path):
    opener=shutil.which('xdg-open')
    if not opener: raise ValueError('File manager opener unavailable. Copy the folder path instead.')
    try:
        result=subprocess.run([opener,path],capture_output=True,timeout=8)
    except (OSError,subprocess.TimeoutExpired):
        raise ValueError('Could not confirm the file manager opened. Copy the folder path instead.') from None
    if result.returncode: raise ValueError('File manager could not open this folder. Copy the folder path instead.')
    return {'path':path,'opened':True}


def reveal_file(path):
    """Ask the desktop file manager to select the existing original file."""
    opener=shutil.which('gdbus')
    if not opener: raise ValueError('File selection service unavailable. Original image: '+str(path))
    args=[opener,'call','--session','--dest','org.freedesktop.FileManager1',
          '--object-path','/org/freedesktop/FileManager1','--method',
          'org.freedesktop.FileManager1.ShowItems',json.dumps([path.as_uri()]),'']
    try:
        result=subprocess.run(args,capture_output=True,timeout=8)
    except (OSError,subprocess.TimeoutExpired):
        raise ValueError('Could not reveal the original image: '+str(path)) from None
    if result.returncode: raise ValueError('File manager could not select the original image: '+str(path))
    return {'path':str(path),'revealed':True}
