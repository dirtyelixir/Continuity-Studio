"""Rejected images are discarded; preserve only text audit and in-use originals."""
from . import store,asset_library
import json,hashlib
from pathlib import Path
from PIL import Image


def pixel_signature(path):
    with Image.open(path) as im:
        rgb=im.convert('RGB')
        return rgb.size,hashlib.sha256(rgb.tobytes()).hexdigest()


def image_copies(asset,jobs,path):
    """Known provider output and completed-job input copies, never uploads.

    Paths from result files are untrusted: constrain storage and verify pixels
    against the rejected original before deleting a provider output.
    """
    candidates=set();boards=set()
    for job in jobs:
        if job['state'] in ('queued','running','awaiting_input'):continue
        work=store.DATA/'jobs'/job['id']
        for i,source in enumerate(job['input'].get('images',[]),1):
            if Path(source).resolve()!=path.resolve():continue
            for parent in (work,work/'inputs',work/'preparation',work/'preparation'/'inputs'):
                for suffix in ('.png','.jpg','.jpeg','.webp'):
                    candidates.add(parent/f'reference-{i}{suffix}')
            # Completed transport boards are disposable job copies, not assets.
            boards.add(work/'reference-board.png')
    if asset.get('job_id'):
        result=store.DATA/'jobs'/asset['job_id']/'result.json'
        if result.is_file():
            try:
                original=Path(json.loads(result.read_text()).get('image_path','')).resolve()
                roots=[(store.DATA/'jobs'/asset['job_id']).resolve(),Path.home()/'.codex'/'generated_images',Path.home()/'.codex'/'images']
                if any(original.is_relative_to(root.resolve()) for root in roots):candidates.add(original)
            except (ValueError,TypeError):pass
    # A different asset's stored original is never a disposable copy.
    protected={asset_library.safe_path(a['path']).resolve() for a in store.assets(asset['project_id']) if a['id']!=asset['id']}
    matches=[]
    signature=pixel_signature(path) if path.is_file() else None
    for copy in candidates:
        if not copy.is_file() or copy.is_symlink() or copy.resolve() in protected or copy.resolve()==path.resolve():continue
        if signature and pixel_signature(copy)==signature:matches.append(copy)
    return matches+[p for p in boards if p.is_file() and not p.is_symlink() and p.resolve() not in protected]


def delete_rejected(aid,*,dry_run=False):
    staged=[]
    try:
        with store.db() as c:
            asset=store.row(c.execute('SELECT * FROM assets WHERE id=?',(aid,)).fetchone())
            if not asset:raise ValueError('找不到此素材。')
            if asset['status']!='rejected':raise ValueError('只可刪除已拒絕版本。')
            path=asset_library.safe_path(asset['path'])
            for row in c.execute('SELECT * FROM assets WHERE id!=?',(aid,)):
                other=store.row(row)
                if aid in other['reference_ids'] or asset_library.safe_path(other['path']).resolve()==path.resolve():
                    raise ValueError('此版本仍被其他素材引用，不能刪除。')
            jobs=[store.row(row) for row in c.execute('SELECT * FROM jobs')]
            for job in jobs:
                if job['state'] not in ('queued','running','awaiting_input'):continue
                data=store.encode(job['input'])
                if job['target_id']==aid or aid in data or str(path.resolve()) in data or (job['capability']=='image' and job['target_id']==asset['target_id'] and job['project_id']==asset['project_id']):
                    raise ValueError('此素材仍有工作使用中，請待工作完成後再刪除。')
            for row in c.execute('SELECT value FROM settings'):
                if aid in row['value']:raise ValueError('此版本仍在已保存設定中使用，不能刪除。')
            copies=image_copies(asset,jobs,path)
            originals=[p for p in (path,path.with_suffix('.json'),path.with_name(path.stem+'-prompt.txt'),*copies) if p.exists()]
            for original in originals:
                if not original.is_file() or original.is_symlink():raise ValueError('此版本包含連結檔案，請先檢查素材路徑。')
            if dry_run:return {'asset_id':aid,'paths':[str(p) for p in originals]}
            for original in originals:
                if original.exists():
                    if not original.is_file() or original.is_symlink():raise ValueError('此版本包含連結檔案，請先檢查素材路徑。')
                    temporary=original.with_name('.'+original.name+'.deleting-'+aid)
                    original.rename(temporary);staged.append((original,temporary))
            c.execute('DELETE FROM assets WHERE id=?',(aid,))
            store.event(c,asset['project_id'],'asset_deleted',store.encode({'asset_id':aid,'target_id':asset['target_id'],'path':asset['path'],'status':'rejected','removed_copies':[str(p) for p in copies]}))
    except Exception:
        for original,temporary in reversed(staged):
            if temporary.exists():temporary.rename(original)
        raise
    for _,temporary in staged:temporary.unlink()
    asset_library.write_catalog(asset['project_id'])
    if not any(asset_library.safe_path(a['path']).parent==path.parent for a in store.assets(asset['project_id'])):
        versions=path.parent/'Versions.md'
        if versions.exists():versions.write_text('# Image versions\n\n此組已無保留版本。\n')
    return {'ok':True,'deleted_asset_id':aid}


def purge_rejected(pid):
    """Remove leaves first so rejected dependency chains can be discarded too.

    Caller holds engine.LOCK. In-use files stay pending and are retried after
    job completion/cancellation; callers must display any remaining reason.
    """
    deleted=[];blocked={}
    while True:
        candidates=[a for a in store.assets(pid) if a['status']=='rejected']
        progress=False;blocked={}
        for asset in candidates:
            try:
                delete_rejected(asset['id']);deleted.append(asset['id']);progress=True
            except (ValueError,OSError) as exc:
                blocked[asset['id']]=str(exc)
        if not progress:break
    return {'deleted_asset_ids':deleted,'pending_deletions':blocked}
