"""One managed ComfyUI submission, durable receipt and exact-node output recovery."""
import hashlib
import json
import time
import uuid
from contextlib import nullcontext
from pathlib import Path
import httpx
from PIL import Image
from . import local_images, comfy_runtime, comfy_health, image_output_quality

BASE_URL='http://127.0.0.1:8188'
WAIT_SECONDS=1800
POLL_TIMEOUT=httpx.Timeout(10,connect=3)


class ExecutorStopped(RuntimeError):pass


def recovery_guard(work):
    note=work/'service-recovery.json'
    if note.exists() and json.loads(note.read_text()).get('outcome')=='lost':
        raise RuntimeError('本機服務已復原；原工作因服務崩潰中斷。可重新生成；原回條保留，沒有自動重送。')


def cancel_guard(work):
    if (work/'cancel-requested').exists():
        save(work/'comfy-wait-status.json', {'state':'cancelled', 'remote_state':'unconfirmed',
            'message':'已停止等待，不採用結果；原本機工作回條保留。'})
        raise RuntimeError('使用者已取消；已停止等待本機圖片，不採用結果。')


def executor_ready(c, work=None):
    r=c.get('/vram/status',timeout=POLL_TIMEOUT);r.raise_for_status();state=r.json()
    failure=comfy_health.worker_failure(state.get('pid'))
    if failure:
        if work:save(work/'comfy-service-error.json',failure)
        raise ExecutorStopped(failure['message'])
    if not state.get('ok') or not state.get('monitor_alive') or state.get('last_error'):
        raise RuntimeError('ComfyUI 的 VRAM Manager 保護失效；已停止等待，工作回條保留。')
    return state


def preflight(work):
    cancel_guard(work)
    repair=False
    with httpx.Client(base_url=BASE_URL,timeout=POLL_TIMEOUT,trust_env=False) as probe:
        try:executor_ready(probe,work)
        except httpx.ConnectError:pass  # The manager may start an idle/offline runtime.
        except ExecutorStopped:repair=True
    if repair:
        from . import comfy_recovery
        comfy_recovery.ensure_ready(work)
        cancel_guard(work)
        with httpx.Client(base_url=BASE_URL,timeout=POLL_TIMEOUT,trust_env=False) as probe:
            executor_ready(probe,work)


def save(path, value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2));temp.replace(path)


def control_ready(client):
    state=client.get('/vram/status');state.raise_for_status();s=state.json()
    if not s.get('ok') or not s.get('monitor_alive') or s.get('last_error'): raise ValueError('ComfyUI 的 VRAM Manager 保護未就緒；沒有送出工作。')


def check():
    results=[]
    try:
        with httpx.Client(base_url=BASE_URL,timeout=30,trust_env=False) as c:
            executor_ready(c)
            control_ready(c);r=c.get('/object_info');r.raise_for_status();info=r.json()
        for key,recipe in local_images.RECIPES.items():
            n=0 if key=='krea_new' else 2 if key in ('krea_two','klein_face') else 1
            p={'recipe':key,'width':1024,'height':1024,'seed':1,'region':[20,20,40,40],'padding':[64,0,64,0]}
            try:local_images.validate_graph(local_images.build(p,'Readiness only',[f'input{i}.png' for i in range(n)],'check'),info);error=''
            except ValueError as exc:error=str(exc)
            results.append({'id':key,'name':recipe['name'],'ready':not error,'error':error})
        return {'ok':all(r['ready'] for r in results),'recipes':results,'message':'依賴檢查；不代表已完成圖片品質驗證。'}
    except (httpx.HTTPError,ValueError,RuntimeError) as exc:
        return {'ok':False,'recipes':results,'message':'無法確認本機圖片服務：'+str(exc)}


def unresolved(work):
    try:recovery_guard(Path(work))
    except RuntimeError:return False
    p=Path(work)/'comfy-receipt.json'
    return p.exists() and json.loads(p.read_text()).get('phase') not in ('execution_error','invalid_output')


def find_submission(c, receipt):
    """Reconcile a lost POST response by our unique extra_data token, never repost."""
    q=c.get('/queue');q.raise_for_status()
    for row in q.json().get('queue_running',[])+q.json().get('queue_pending',[]):
        if row[3].get('studio_submission')==receipt['token']:return row[1]
    h=c.get('/history',params={'max_items':500});h.raise_for_status()
    for pid,row in h.json().items():
        prompt=row.get('prompt',[])
        if len(prompt)>3 and prompt[3].get('studio_submission')==receipt['token']:return pid
    raise RuntimeError('送出狀態未明，沒有再次生成。請稍後按「取回本機結果」，或在 ComfyUI 核對；原工作回條已保存。')


def run(provider, prompt, images, work):
    work=Path(work);work.mkdir(parents=True,exist_ok=True)
    receipt_path=work/'comfy-receipt.json';plan=provider['local_plan']
    cancel_guard(work)
    recovery_guard(work)
    if plan['origins']!=local_images.origins():raise ValueError('保存的原始工作流已變更，請先核對版本。')
    reservation = nullcontext() if receipt_path.exists() else comfy_runtime.reserve('klein')
    # Fail before acquiring a lease or submitting more work to a dead executor.
    if not receipt_path.exists():
        preflight(work)
    with reservation as runtime, httpx.Client(base_url=BASE_URL,timeout=httpx.Timeout(30,connect=3),trust_env=False) as c:
        cancel_guard(work)
        if runtime: save(work/'runtime-mode.json', runtime)
        if receipt_path.exists():
            receipt=json.loads(receipt_path.read_text())
            if receipt['plan_hash']!=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest() or receipt['prompt_hash']!=hashlib.sha256(prompt.encode()).hexdigest(): raise ValueError('回條與工作輸入不一致；禁止重新送出。')
            if receipt.get('phase')=='execution_error':raise RuntimeError('ComfyUI 已確認執行失敗；請檢視錯誤後建立新工作。')
            if receipt.get('phase')=='invalid_output':raise ValueError(receipt['error'])
        else:
            if len(images)!=plan['reference_count']:raise ValueError('工作參考圖數量不一致；沒有生成。')
            if plan['version']!=local_images.VERSION:raise ValueError('本機適配版本已更新，請建立新工作；原工作不會改用新版。')
            control_ready(c)
            r=c.get('/object_info');r.raise_for_status();info=r.json()
            graph=local_images.build(plan,prompt,[f'reference-{i}.png' for i in range(len(images))],'ContinuityStudio/'+work.name)
            local_images.validate_graph(graph,info)
            uploads=[]
            for i,path in enumerate(images):
                path=Path(path);raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
                with path.open('rb') as f:
                    r=c.post('/upload/image',data={'type':'input','subfolder':'ContinuityStudio/'+work.name,'overwrite':'false'},files={'image':(f'reference-{i}-{digest[:12]}.png',f,'image/png')})
                r.raise_for_status();item=r.json()
                if item.get('type')!='input' or item.get('subfolder')!='ContinuityStudio/'+work.name or not item.get('name') or '/' in item['name'] or '\\' in item['name']:raise ValueError('ComfyUI 回傳無效輸入位置。')
                # Verify uploaded bytes; preserve all roles and order.
                v=c.get('/view',params={'filename':item['name'],'subfolder':item['subfolder'],'type':'input'});v.raise_for_status()
                if hashlib.sha256(v.content).hexdigest()!=digest:raise ValueError('ComfyUI 輸入像素檔案校驗失敗。')
                uploads.append({**item,'source':str(path),'sha256':digest})
            graph=local_images.build(plan,prompt,[x['subfolder']+'/'+x['name'] for x in uploads],'ContinuityStudio/'+work.name)
            save(work/'comfy-graph.json',graph);save(work/'local-plan.json',plan);save(work/'comfy-inputs.json',uploads)
            receipt={'token':uuid.uuid4().hex,'phase':'submitting','plan_hash':hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest(),'prompt_hash':hashlib.sha256(prompt.encode()).hexdigest(),'graph_hash':hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest()}
            cancel_guard(work)
            save(receipt_path,receipt)
            try:
                r=c.post('/prompt',json={'prompt':graph,'client_id':receipt['token'],'extra_data':{'studio_submission':receipt['token'],'studio_job':work.name}})
                if r.status_code>=400:
                    receipt.update(phase='execution_error' if r.status_code==400 else 'submission_unknown',error=r.text[:2500]);save(receipt_path,receipt)
                    raise RuntimeError('ComfyUI 拒絕工作：'+r.text[:1200])
                body=r.json()
                if body.get('node_errors') or not body.get('prompt_id'):raise RuntimeError('ComfyUI 沒有回傳有效工作編號，請取回結果核對。')
                receipt.update(prompt_id=body['prompt_id'],phase='submitted');save(receipt_path,receipt)
            except httpx.HTTPError as exc:
                raise RuntimeError('ComfyUI 送出回應中斷；狀態未明，請取回本機結果，不能盲目重試。') from exc
        if not receipt.get('prompt_id'):
            receipt.update(prompt_id=find_submission(c,receipt),phase='submitted');save(receipt_path,receipt)
        end=time.monotonic()+WAIT_SECONDS
        next_health=0
        while True:
            cancel_guard(work)
            recovery_guard(work)
            r=c.get('/history/'+receipt['prompt_id'],timeout=POLL_TIMEOUT);r.raise_for_status();item=r.json().get(receipt['prompt_id'])
            cancel_guard(work)
            recovery_guard(work)
            recovered=work/'recovered-history.json'
            if not item and recovered.exists():item=json.loads(recovered.read_text())
            if item:
                save(work/'comfy-history.json',item)
                status=item.get('status',{})
                if status.get('status_str')=='error':
                    receipt.update(phase='execution_error',error=status.get('messages'));save(receipt_path,receipt)
                    raise RuntimeError('ComfyUI 圖片執行失敗；詳細錯誤已保存於工作紀錄。')
                if status.get('completed'):
                    outputs=item.get('outputs',{}).get('save',{}).get('images',[])
                    if len(outputs)!=1:raise ValueError('指定輸出節點未回傳唯一候選圖片；不會選取其他預覽。')
                    output=outputs[0]
                    if output.get('type')!='output' or '/' in output.get('filename','') or '\\' in output.get('filename','') or output.get('subfolder')!='ContinuityStudio':raise ValueError('ComfyUI 輸出位置不符合本工作約定。')
                    if not output['filename'].startswith(work.name+'_'):raise ValueError('ComfyUI 輸出名稱不屬於此工作。')
                    r=c.get('/view',params=output);r.raise_for_status()
                    cancel_guard(work)
                    if len(r.content)>40_000_000:raise ValueError('輸出圖片超過 40MB。')
                    path=work/'render.png';path.write_bytes(r.content)
                    with Image.open(path) as im:
                        padding=plan.get('padding') or [0,0,0,0]
                        if im.size!=(plan['width']+padding[0]+padding[2],plan['height']+padding[1]+padding[3]):raise ValueError('輸出尺寸與保存的工作設定不符。')
                        im.verify()
                    quality=image_output_quality.inspect_image(path)
                    save(work/'output-quality.json',quality)
                    if not quality['valid']:
                        receipt.update(phase='invalid_output',output=output,sha256=hashlib.sha256(r.content).hexdigest(),error=quality['message'])
                        save(receipt_path,receipt)
                        raise ValueError(quality['message'])
                    receipt.update(phase='render_complete',output=output,sha256=hashlib.sha256(r.content).hexdigest());save(receipt_path,receipt)
                    result={'image_path':str(path.resolve()),'notes':plan['name']+'；ComfyUI '+receipt['prompt_id']+'；'+plan['reason']}
                    save(work/'result.json',result)
                    return result
            if time.monotonic()>=next_health:
                current=executor_ready(c,work)
                runtime_file=work/'runtime-mode.json'
                old_pid=json.loads(runtime_file.read_text()).get('comfy_pid') if runtime_file.exists() else None
                if old_pid and current.get('pid') and old_pid!=current['pid']:
                    q=c.get('/queue',timeout=POLL_TIMEOUT);q.raise_for_status()
                    if not any(row[1]==receipt['prompt_id'] for key in ('queue_running','queue_pending') for row in q.json().get(key,[])):
                        save(work/'service-recovery.json',{'outcome':'lost','prompt_id':receipt['prompt_id'],'old_pid':old_pid,'new_pid':current['pid'],'source':'history_absent_and_process_changed'})
                        recovery_guard(work)
                next_health=time.monotonic()+10
            if time.monotonic()>=end:raise RuntimeError('等待本機圖片逾時；原工作可能仍在執行。請按取回本機結果，不會重複送出。')
            time.sleep(2)
