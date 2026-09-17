"""Studio-owned recovery policy; only VRAM Manager may repair the GPU service.

Unsent jobs may continue after repair. A submitted prompt is reconciled with
the manager's saved snapshot; never replay it merely because HTTP recovered.
"""
import json
import logging
import threading
from pathlib import Path

import httpx

from . import store, comfy_health, comfy_runtime

LOCK=threading.Lock()
STOP=threading.Event()
THREAD=None


def path():return store.DATA/'runtime'/'comfy-recovery.json'


def process_identity(pid):
    return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]


def write(destination,value):
    destination.parent.mkdir(parents=True,exist_ok=True)
    tmp=destination.with_suffix('.tmp');tmp.write_text(store.encode(value));tmp.replace(destination)


def state():
    try:return json.loads(path().read_text())
    except FileNotFoundError:return {'phase':'idle','message':''}


def report(phase,message,**data):
    result={'phase':phase,'message':message,'updated':store.now(),**data}
    write(path(),result);return result


def receipt_jobs():
    with store.db() as c:
        rows=c.execute("SELECT id FROM jobs WHERE provider='comfy_local' AND capability='image'").fetchall()
    result={}
    for row in rows:
        work=store.DATA/'jobs'/row['id']
        try:
            receipt=json.loads((work/'comfy-receipt.json').read_text())
            if receipt.get('prompt_id') and receipt.get('phase') not in ('render_complete','execution_error') and not (work/'service-recovery.json').exists():
                result[receipt['prompt_id']]=row['id']
        except (OSError,ValueError):continue
    return result


def reconcile(result):
    from . import engine
    for entry in result.get('affected',[]):
        # A restart receipt cannot authorize access to arbitrary filesystem paths.
        jid=entry.get('job_id','')
        if not isinstance(jid,str) or len(jid)!=16 or any(x not in '0123456789abcdef' for x in jid):continue
        work=store.DATA/'jobs'/jid
        with engine.LOCK:
            job=store.job(jid)
            if not job or job['provider']!='comfy_local' or job['capability']!='image':continue
            try:receipt=json.loads((work/'comfy-receipt.json').read_text())
            except (OSError,ValueError):continue
            if receipt.get('prompt_id')!=entry.get('prompt_id'):continue
            note=work/'service-recovery.json'
            if note.exists():continue
            history=entry.get('history') or {}
            complete=history.get('status',{}).get('completed') and history.get('status',{}).get('status_str')=='success'
            if complete:write(work/'recovered-history.json',history)
            write(note,{'operation_id':result['operation_id'],'prompt_id':entry['prompt_id'],
                'old_pid':result['old_pid'],'new_pid':result['new_pid'],
                'outcome':'history_saved' if complete else 'lost','queue_state':entry['queue_state'],
                'message':'原結果已保存，可取回核對。' if complete else '本機服務已復原；原工作因服務崩潰中斷，回條保留，沒有自動重送。'})
            if engine.cancel_requested(jid):engine.complete_cancel(jid)
            elif job['state'] in ('failed','interrupted'):
                message='本機服務已復原；原結果已保存，可取回核對。' if complete else '本機服務已復原；原工作因服務崩潰中斷。可重新生成；原回條保留，沒有自動重送。'
                with store.db() as c:c.execute('UPDATE jobs SET error=?,updated=? WHERE id=?',(message,store.now(),jid))


def tick(*, required=False):
    # One Studio reporter; Manager independently serializes all clients.
    if not LOCK.acquire(blocking=required):return state()
    try:
        owned=receipt_jobs()
        if not owned and not required:return state()
        with httpx.Client(base_url=comfy_runtime.manager_url(),timeout=httpx.Timeout(130,connect=3),trust_env=False) as c:
            response=c.get('/vram/status',timeout=10);response.raise_for_status();manager=response.json()
            previous=manager.get('comfy_recovery') or {}
            if previous.get('ready'):
                reconcile(previous)
                owned=receipt_jobs()
            pid=(manager.get('comfy') or {}).get('pid')
            failure=comfy_health.worker_failure(pid)
            if not failure:
                comfy=manager.get('comfy') or {}
                if comfy.get('ok') and comfy.get('monitor_alive') and not comfy.get('last_error'):
                    if previous.get('ready'):
                        return report('ready','本機出圖服務已復原；未送出的工作可繼續。已送出的工作已保留回條並核對狀態。',operation_id=previous['operation_id'])
                    return report('ready','本機出圖服務正常。')
                return report('waiting','本機出圖服務尚未就緒；沒有確認執行緒崩潰，不會自動重啟。')
            if not owned:
                return report('blocked','出圖服務故障，但沒有可核對的 Studio 回條；已保留現場，沒有自動重啟。')
            identity=process_identity(pid)
            operation=f'{pid}-{identity}'
            report('recovering','本機出圖服務故障，正交由 VRAM Manager 核實及復原；文字工作可繼續。',operation_id=operation)
            response=c.post('/vram/comfy/recover',json={'expected_pid':pid,'expected_identity':identity,'owned_prompts':owned})
            if response.status_code==409:
                return report('waiting','自動復原暫緩：'+response.json().get('error','Manager 尚未允許'),operation_id=operation)
            if response.status_code==404:
                return report('blocked','VRAM Manager 尚未支援受控復原接口；沒有呼叫全域釋放。',operation_id=operation)
            response.raise_for_status();result=response.json()
            if not result.get('ready'):
                return report('blocked','自動復原已停止：'+result.get('message','需要檢查服務狀態'),operation_id=operation)
            # Independently verify the new process, mode and actual HTTP readiness.
            verify=c.get('/vram/status',timeout=10);verify.raise_for_status();verified=verify.json()
            runtime=verified.get('comfy_mode') or {}
            with httpx.Client(base_url='http://127.0.0.1:8188',timeout=10,trust_env=False) as renderer:
                r=renderer.get('/vram/status');r.raise_for_status();live=r.json()
            if (live.get('pid')!=result.get('new_pid') or live.get('pid')==pid or not live.get('monitor_alive') or
                    live.get('last_error') or not live.get('ok') or runtime.get('running')!=result.get('mode')):
                return report('blocked','Manager 已回覆，但出圖服務尚未通過復原核對；沒有重新送出工作。',operation_id=operation)
            reconcile(result)
            return report('ready','本機出圖服務已由 VRAM Manager 復原；未送出的工作可繼續，原回條已保存。',operation_id=operation)
    except (OSError,ValueError,httpx.HTTPError) as exc:
        # Keep operation identity after an uncertain POST response. The next
        # check reads Manager's durable outcome and does not start a new attempt.
        return report('waiting','暫未確認服務復原，稍後會核對同一次復原紀錄；沒有重送圖片。',
                      operation_id=state().get('operation_id'),error_class=type(exc).__name__)
    finally:LOCK.release()


def ensure_ready(work):
    result=tick(required=True)
    if result.get('phase') in ('recovering','waiting','blocked'):
        raise RuntimeError(result['message'])


def start():
    global THREAD
    if THREAD and THREAD.is_alive():return
    STOP.clear()
    def watch():
        while not STOP.is_set():
            try:tick()
            except Exception:logging.exception('ComfyUI recovery observer failed')
            STOP.wait(15)
    THREAD=threading.Thread(target=watch,name='studio-comfy-recovery',daemon=True);THREAD.start()


def shutdown():
    STOP.set()
    if THREAD:THREAD.join(timeout=1)
