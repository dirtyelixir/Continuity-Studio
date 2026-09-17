"""Explicit human adoption of existing pixels as a current visual identity."""
import copy
import hashlib
import io
import shutil
from PIL import Image
from . import store, models, continuity, asset_library, engine, character_sheets


def save(pid, target_id, revision, entity=None, asset_id='', content=None):
    with engine.LOCK:
        p=store.project(pid)
        if p['revision']!=revision:raise ValueError('作品已更新，請重新開啟身份設定後再採用圖片。')
        kind,target,_=continuity.find_target(p['production'],target_id)
        if kind!='entity':raise ValueError('只可將圖片採用為角色、場景或道具身份資產。')
        candidate=copy.deepcopy(p['production'])
        if entity is not None:
            replacement=models.Entity.model_validate(entity).model_dump()
            if replacement['id']!=target_id:raise ValueError('身份設定屬於其他資產。')
            if replacement['kind']=='voice':raise ValueError('聲音身份不能採用圖片。')
            candidate['canon']=[replacement if e['id']==target_id else e for e in candidate['canon']]
            candidate=models.Production.model_validate(candidate).model_dump()
        if bool(asset_id)==(content is not None):raise ValueError('請選用一張現有圖片，或上傳一張圖片。')
        source=None;png=None
        if asset_id:
            source=next((a for a in store.assets(pid) if a['id']==asset_id and a['target_id']==target_id),None)
            if not source or source['status']=='rejected':raise ValueError('請選用這個身份的現有圖片。')
            source_path=asset_library.safe_path(source['path'])
            if source.get('job_id'):
                from .image_output_quality import require_image
                require_image(source_path)
            raw=source_path.read_bytes()
        else:raw=content
        if not raw or len(raw)>40_000_000:raise ValueError('圖片不可超過 40MB。')
        try:
            with Image.open(io.BytesIO(raw)) as im:im.verify()
            with Image.open(io.BytesIO(raw)) as im:
                if im.width<256 or im.height<256:raise ValueError('圖片長寬至少需 256 像素。')
                if content is not None:
                    buf=io.BytesIO();im.convert('RGB').save(buf,format='PNG');png=buf.getvalue()
        except (OSError, Image.DecompressionBombError) as exc:raise ValueError('無法讀取圖片，請使用 PNG、JPEG 或 WebP。') from exc
        expected=continuity.target_hash(candidate,target_id)
        pixel_hash=hashlib.sha256(raw).hexdigest()
        key='identity-adoption:'+store.digest([pid,target_id,expected,asset_id,pixel_hash])
        prior=store.setting(key)
        if prior:
            existing=next((a for a in store.assets(pid) if a['id']==prior['asset_id']),None)
            if existing and existing['status']=='approved' and existing['dependency_hash']==expected:
                return {'asset_id':existing['id'],'revision':p['revision'],'reused':True}
        # Validate source pixels and the whole edited production before any save.
        if candidate!=p['production']:
            p=engine.save_plan(pid,candidate,revision,'Director identity edit and image adoption')
        if source and source['dependency_hash']==expected and source['status']!='stale':
            # A current candidate still uses the normal reference validation gate.
            refs={a['id']:a for a in store.assets(pid)}
            valid_refs=all(r in refs and refs[r]['status']=='approved' and continuity.target_hash(p['production'],refs[r]['target_id'])==refs[r]['dependency_hash'] for r in source['reference_ids'])
            if valid_refs:
                note='使用者確認採用目前圖片，保留原審查意見。'
                if next(e for e in p['production']['canon'] if e['id']==target_id)['kind']!='character' or character_sheets.verified(source):note='[人工覆核採用] '+note
                engine.decide_asset(asset_id,'approved',note,True)
                return {'asset_id':asset_id,'revision':p['revision'],'reused':True}
        # New applicability record: the original image, dependency hash, review
        # and reference lineage remain untouched on the historical asset.
        aid=store.uid();out=store.DATA/asset_library.next_path(pid,target_id,p['production'])
        out.parent.mkdir(parents=True,exist_ok=True)
        if source:shutil.copy2(source_path,out)
        else:out.write_bytes(png)
        if source and hashlib.sha256(out.read_bytes()).hexdigest()!=pixel_hash:raise ValueError('圖片複製驗證失敗。')
        note='[人工覆核採用] '+('沿用現有圖片作為目前身份參考；原審查紀錄保留。' if source else '使用者上傳並確認採用為身份參考。')
        audit={'asset_id':aid,'source_asset_id':asset_id,'source_sha256':pixel_hash,'source_record':source,
               'revision':p['revision'],'dependency_hash':expected,'created':store.now(),'note':note}
        with store.db() as c:
            c.execute('INSERT INTO assets(id,project_id,target_id,kind,path,status,dependency_hash,reference_ids,prompt,provider,created,source_asset_id,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (aid,pid,target_id,'entity',str(out.relative_to(store.DATA)),'pending',expected,'[]','Director-selected existing image' if source else 'Director-uploaded identity image','manual',store.now(),asset_id,note))
            # This provenance also protects the historical source from deletion.
            c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,store.encode(audit)))
            store.event(c,pid,'identity_image',store.encode(audit))
        current_entity=next(e for e in p['production']['canon'] if e['id']==target_id)
        approval_note=note.removeprefix('[人工覆核採用] ') if current_entity['kind']=='character' else note
        engine.decide_asset(aid,'approved',approval_note,True)
        return {'asset_id':aid,'revision':p['revision'],'reused':False}
