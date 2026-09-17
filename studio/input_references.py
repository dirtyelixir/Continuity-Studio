"""Director-uploaded production inputs; never canonical assets or generation jobs."""
import hashlib,io,json
from pathlib import Path
from urllib.parse import quote
from PIL import Image,UnidentifiedImageError
from . import store,asset_library,continuity


def list_for(pid):
    store.project(pid)
    return store.setting('input-references:'+pid,[])


def get(pid,rid):
    ref=next((r for r in list_for(pid) if r['id']==rid),None)
    if not ref: raise ValueError('找不到這張製作參考圖。')
    return ref


def path_for(ref):
    path=asset_library.safe_path(ref['path'])
    if not path.is_file(): raise ValueError('製作參考圖原檔不存在，請重新上傳。')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
        raise ValueError('製作參考圖原檔已被改動，請重新上傳以保留版本。')
    return path


def store_original(pid,target_id,purpose,content,ext):
    root=Path('assets')/asset_library.layout(pid)['folder']
    if target_id:
        target=asset_library.target_location(pid,target_id)
        directory=root/target['directory']/'Source References'
        label=asset_library.clean_name(target['label'])
    else:
        directory=root/'Style References';label='作品共用'
    purpose_name='風格參考' if purpose=='style' else '外觀參考'
    parent=asset_library.safe_path(directory);parent.mkdir(parents=True,exist_ok=True)
    version=1
    while True:
        # Reserve versions across formats as well: v001.png and v001.jpg are different uploads.
        stem=f'{label}-{purpose_name}-v{version:03d}'
        if any(parent.glob(stem+'.*')):version+=1;continue
        relative=directory/(stem+ext);path=asset_library.safe_path(relative)
        try:
            with path.open('xb') as f:f.write(content)
            break
        except FileExistsError:version+=1
    if hashlib.sha256(path.read_bytes()).digest()!=hashlib.sha256(content).digest():
        raise ValueError('參考圖保存驗證失敗，請重試。')
    return {'path':str(relative),'name':path.name,'version':version,'storage_version':2}


def write_catalog(pid):
    root=asset_library.safe_path(Path('assets')/asset_library.layout(pid)['folder'])
    refs=list_for(pid)
    lines=['# 製作參考圖索引','', '此處保存上傳原圖，不依賴原本檔案位置。參考圖不等於已批准的生成素材。','']
    for ref in refs:
        relative=Path(ref['path']).relative_to(root.relative_to(store.DATA))
        original=ref.get('original_filename',ref['name']).replace('\n',' ')
        lines.append(f'- [{ref["name"]}]({quote(relative.as_posix())}) · 原檔名：{original}')
    asset_library.write_text(root/'製作參考圖.md','\n'.join(lines)+'\n')
    asset_library.write_text(root/'production-reference-index.json',json.dumps(refs,ensure_ascii=False,indent=2)+'\n')


def organize(pid):
    """Explicit migration; retain old files for frozen generation requests and recovery."""
    refs=list_for(pid);changed=[]
    for ref in refs:
        if ref.get('storage_version')==2:continue
        old=path_for(ref);content=old.read_bytes()
        ref['original_filename']=ref['name'];ref['previous_paths']=[ref['path']]
        ref.update(store_original(pid,ref['target_id'],ref['purpose'],content,old.suffix))
        path_for(ref).with_suffix(old.suffix+'.json').write_text(json.dumps(ref,ensure_ascii=False,indent=2))
        changed.append(ref['id'])
    if changed:store.put_setting('input-references:'+pid,refs)
    if refs:write_catalog(pid)
    return changed


def save(pid,content,filename,purpose,target_id):
    p=store.project(pid)
    if purpose not in ['style','identity']: raise ValueError('請選擇風格參考或外觀／形狀參考。')
    target_name='Project Style'
    if target_id:
        if not p['production']: raise ValueError('請先採用製作方案，再指定角色、場景或道具。')
        kind,target,_=continuity.find_target(p['production'],target_id)
        target_name=target.get('name') or target.get('description') or target_id
    elif purpose!='style': raise ValueError('外觀參考需要指定製作對象。')
    if not content or len(content)>40_000_000: raise ValueError('參考圖片須小於 40 MB。')
    try:
        with Image.open(io.BytesIO(content)) as im:
            fmt=im.format
            if fmt not in ['PNG','JPEG','WEBP'] or im.width*im.height>40_000_000:
                raise ValueError('請上傳 PNG、JPEG 或 WebP 圖片，最多四千萬像素。')
            im.verify()
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError) as exc:
        raise ValueError('無法讀取圖片，請上傳有效的 PNG、JPEG 或 WebP。') from exc
    rid=store.uid();name=Path(filename.replace('\\','/')).name
    ext={'PNG':'.png','JPEG':'.jpg','WEBP':'.webp'}[fmt]
    stored=store_original(pid,target_id,purpose,content,ext)
    path=asset_library.safe_path(stored['path'])
    ref={'id':rid,'project_id':pid,'target_id':target_id,'purpose':purpose,'original_filename':name,**stored,'sha256':hashlib.sha256(content).hexdigest(),'created':store.now()}
    path.with_suffix(path.suffix+'.json').write_text(json.dumps(ref,ensure_ascii=False,indent=2))
    refs=list_for(pid);refs.append(ref);store.put_setting('input-references:'+pid,refs)
    write_catalog(pid)
    with store.db() as c:store.event(c,pid,'reference','已保存製作參考圖：'+name+'（未開始生成）')
    return ref


def resolve(pid,target_id,ids):
    if len(ids)!=len(set(ids)): raise ValueError('製作參考圖不能重複選取。')
    refs=[get(pid,rid) for rid in ids]
    for ref in refs:
        if ref['target_id'] and ref['target_id']!=target_id: raise ValueError('製作參考圖必須屬於目前對象或作品共用風格。')
        path_for(ref)
    return refs
