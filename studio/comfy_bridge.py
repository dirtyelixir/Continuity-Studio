"""Send existing images to the local ComfyUI input library via its upload API."""
import mimetypes
import httpx
from . import asset_library, store

BASE_URL = 'http://127.0.0.1:8188'


def send_image(aid, path):
    with store.db() as db:
        asset=store.row(db.execute('SELECT * FROM assets WHERE id=?',(aid,)).fetchone())
    if not asset:raise ValueError('圖片不存在。')
    project=store.project(asset['project_id'])
    subfolder='Continuity Studio/'+asset_library.clean_name(project['title'])+'-'+project['id']
    filename=asset_library.clean_name(path.stem)+'-'+aid+path.suffix.lower()
    try:
        with httpx.Client(timeout=30,trust_env=False) as client, path.open('rb') as source:
            response=client.post(BASE_URL+'/upload/image',data={'type':'input','subfolder':subfolder,'overwrite':'false'},files={'image':(filename,source,mimetypes.guess_type(path.name)[0] or 'image/png')})
            response.raise_for_status()
            result=response.json()
    except (httpx.HTTPError,ValueError,OSError) as error:
        raise ValueError('未能送到 ComfyUI 素材庫，請確認本機 ComfyUI（8188）已開啟，再重試。') from error
    if not isinstance(result,dict) or not isinstance(result.get('name'),str) or result.get('type')!='input' or result.get('subfolder')!=subfolder:
        raise ValueError('ComfyUI 未回傳有效的素材位置，請重試。')
    if '/' in result['name'] or '\\' in result['name'] or not result['name']:raise ValueError('ComfyUI 回傳的圖片名稱無效。')
    return {'asset_id':aid,'name':result['name'],'subfolder':subfolder,'type':'input','relative_path':subfolder+'/'+result['name'],'comfy_url':BASE_URL}
