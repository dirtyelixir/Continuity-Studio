"""Persistent, explicitly submitted per-Shot video takes and recoverable Comfy jobs."""
import hashlib
import json
import secrets
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext, contextmanager, ExitStack
from pathlib import Path

import httpx
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import Field

from . import asset_library, continuity, delivery, engine, h3_render_graph as graph, models, store, video_workflow
from . import comfy_video_provider as provider, comfy_runtime
from . import h3_render_settings as render_settings, h3_render_prompt
from .h3_render_settings import RenderSettings
from . import take_lifecycle

router = APIRouter()
POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix='studio-video')
STOP = threading.Event()
WORKERS = set()
WORKER_LOCK = threading.Lock()
UNRESOLVED = ('queued', 'preparing', 'submitting', 'submitted', 'running', 'uncertain', 'recoverable')


class Generate(models.Strict):
    source_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    request_key: str = Field(pattern=r'^[a-zA-Z0-9_-]{16,80}$')
    settings: RenderSettings = Field(default_factory=RenderSettings)
    frozen_id: str | None = Field(default=None,pattern=r'^[a-f0-9]{16}$')


class Adopt(models.Strict):
    source_hash: str = Field(pattern=r'^[a-f0-9]{64}$')


def init():
    STOP.clear()
    with store.db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS video_takes(
          id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), shot_id TEXT NOT NULL,
          request_key TEXT NOT NULL, state TEXT NOT NULL, source_hash TEXT NOT NULL,
          request TEXT NOT NULL, prompt_id TEXT NOT NULL, result TEXT, error TEXT NOT NULL DEFAULT '',
          created TEXT NOT NULL, updated TEXT NOT NULL, UNIQUE(project_id,request_key));
        CREATE TABLE IF NOT EXISTS video_selections(
          project_id TEXT NOT NULL REFERENCES projects(id), shot_id TEXT NOT NULL,
          take_id TEXT NOT NULL REFERENCES video_takes(id), PRIMARY KEY(project_id,shot_id));
        ''')
        # Queued takes cannot have uploaded/submitted: all side effects follow
        # the persisted preparing state. Resume these same frozen requests only.
        queued = [(r['project_id'], r['id']) for r in c.execute("SELECT * FROM video_takes WHERE state='queued' ORDER BY created,id")]
        c.execute("UPDATE video_takes SET state='failed',error='工作台重啟時尚未送出影片；可重新生成。' WHERE state='preparing'")
        c.execute("UPDATE video_takes SET state='uncertain',error='工作台重啟，正在查詢原有 ComfyUI 工作。' WHERE state='submitting'")
        pending = [(r['project_id'], r['id']) for r in c.execute("SELECT * FROM video_takes WHERE state IN ('submitted','running','uncertain')")]
    for pid, tid in pending:
        schedule(pid, tid, resume=True)
    for pid, tid in queued:
        schedule(pid, tid)


def shutdown():
    STOP.set()


def decode(row):
    d = dict(row)
    d['request'] = json.loads(d['request'])
    d['result'] = json.loads(d['result']) if d['result'] else None
    return d


def take(pid, tid):
    with store.db() as c:
        row = c.execute('SELECT * FROM video_takes WHERE project_id=? AND id=?', (pid, tid)).fetchone()
    if not row:
        raise ValueError('找不到本作品的影片工作。')
    return decode(row)


def folder(tid):
    if len(tid) != 16 or any(c not in '0123456789abcdef' for c in tid):
        raise ValueError('影片工作編號無效。')
    path = store.DATA / 'video' / tid
    if not path.resolve().is_relative_to(store.DATA.resolve()):
        raise ValueError('影片目錄不在作品儲存區。')
    return path


def file_hash(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def source(p, sid):
    from . import generation_groups
    if generation_groups.is_group(sid):return generation_groups.render_source(p,sid)
    shot = video_workflow.shot_for(p, sid)
    from . import storyboard_board
    board=storyboard_board.require_review(p,shot['scene_id'],shot_ids=[sid])
    assets = p.get('assets') if 'assets' in p else store.assets(p['id'])
    cfg = video_workflow.config(p['id'])
    entry = cfg['shots'].get(sid, {})
    mode = entry.get('mode', 'I2VA')
    storyboard_board.require_source_mode(p,sid,mode)
    if mode == 'REF2VA' and not entry.get('conditioning'):
        bundle = p.get('delivery') or delivery.project_bundle(p)
        scene = next(s for s in bundle['scenes'] if s['scene_id'] == shot['scene_id'])
        ch = next(s for s in scene['chapters'] if s['shot_id'] == sid)
        issues = list(ch['issues']) + list(ch['missing_references'])
        if scene['preparation']['required']:
            issues.append('請先完成 Scene／Shot 的有效提示詞。')
        flag = ch['guidance'].get('continuityFromPrev')
        if flag is None:
            issues.append('請先完成本鏡的接續判斷。')
        elif flag:
            issues.append('此鏡需要引用上一段影片，請使用導演台接續流程；一鍵生成目前處理獨立鏡頭，不會關掉接續設定。')
        if issues:
            raise ValueError('；'.join(issues))
        shared = {r['asset_id'] for r in scene['references']}
        refs = [{**r, 'scope': 'shared' if r['asset_id'] in shared else 'local'} for r in ch['references']]
        text, global_prompt = ch['shot_prompt'], scene['global_prompt']
        basis = {'shot': shot, 'delivery_hash': scene['delivery_hash'], 'guidance': ch['guidance']}
    else:
        src = video_workflow.prompt_source(p, sid)
        current = entry.get('prompt', {})
        if current.get('source_hash') != store.digest(src):
            raise ValueError('請先生成、採用並儲存目前模式的影片提示詞。')
        text, global_prompt = current['text'], ''
        video_workflow.validate_prompt(text, src)
        refs = src['references']
        basis = src
    exact = []
    for ref in refs:
        asset = next((a for a in assets if a['id'] == ref['asset_id']), None)
        if not asset or not continuity.approved_for(p['production'], [asset], asset['target_id']):
            raise ValueError('影片素材已不是目前有效的批准版本。')
        path = asset_library.safe_path(asset['path'])
        if not path.is_file():
            raise ValueError('影片參考圖片檔案遺失。')
        exact.append({k: ref[k] for k in ('asset_id', 'label', 'moment', 'scope', 'target_id', 'role', 'name', 'subject', 'kind') if k in ref} |
                     {'path': asset['path'], 'sha256': file_hash(path)})
    if not exact:
        raise ValueError('影片缺少批准參考素材。')
    from . import storyboard_usage
    uses=storyboard_usage.bind(p,storyboard_usage.source_uses(p,sid),exact)
    result={**({'reference_demands':basis['reference_demands'],'conditioning':basis['conditioning']} if basis.get('prompt_policy')=='ref-demand-prompt-v1' else {}),**({'storyboard_usage':uses} if uses else {}),**({'storyboard_review':board} if board else {}),'policy': 'studio-comfy-video-v1', 'shot_id': sid, 'scene_id': shot['scene_id'],
            'mode': mode, 'duration': shot['duration'], 'frame_rate': 24, 'text': text,
            'global_prompt': global_prompt, 'references': exact, 'basis': basis,
            'strategy': entry.get('strategy'), 'guide_from_previous': False}
    from . import conditioning
    conditioning.check_source(result)
    return result


def state(p, jobs=None):
    ready = {}
    for shot in (p['production'] or {}).get('shots', []):
        try:
            src = source(p, shot['id'])
            ready[shot['id']] = {'ready': True, 'source_hash': store.digest(src), 'reasons': []}
        except (ValueError, OSError) as e:
            ready[shot['id']] = {'ready': False, 'source_hash': '', 'reasons': [str(e)]}
        frames = graph.frame_count(shot['duration'])
        ready[shot['id']]['timing'] = {'duration': shot['duration'], 'frame_rate': 24,
                                      'frame_count': frames, 'aligned_duration': frames / 24}
    from . import h3_lora_advice, generation_groups
    h3_lora_advice.attach(ready, jobs if jobs is not None else store.jobs(p['id']))
    group_ready = {}
    for gid, entry in generation_groups.config(p['id'])['groups'].items():
        row = {'ready': False, 'source_hash': '', 'reasons': []}
        try:
            resolved = generation_groups.resolve(p, entry['definition'])
            frames = graph.frame_count(resolved['duration'])
            row['timing'] = {'duration': resolved['duration'], 'frame_rate': 24,
                             'frame_count': frames, 'aligned_duration': frames/24}
            src = source(p,gid)
            row.update(ready=True, source_hash=store.digest(src))
        except (ValueError, OSError) as e: row['reasons'].append(str(e))
        group_ready[gid] = row
    h3_lora_advice.attach(group_ready, jobs if jobs is not None else store.jobs(p['id']))
    with store.db() as c:
        takes = [decode(r) for r in c.execute('SELECT * FROM video_takes WHERE project_id=? ORDER BY created DESC', (p['id'],))]
        selected = {r['shot_id']: r['take_id'] for r in c.execute('SELECT * FROM video_selections WHERE project_id=?', (p['id'],))}
        pending_frozen=[json.loads(r['value']) for r in c.execute('SELECT value FROM settings WHERE key LIKE ?',('frozen-video-request:'+p['id']+':%',))]
    attempted={t['request'].get('id') for t in takes}
    pending_frozen=[{k:f[k] for k in ('id','unit_id','source_hash','requested_settings','created','request_hash')}
        for f in pending_frozen if f['id'] not in attempted]
    result = []
    for t in takes:
        compatibility=take_lifecycle.compatibility(p,t)
        current=take_lifecycle.accepted_compatibility(compatibility)
        is_selected=selected.get(t['shot_id'])==t['id']
        review=take_lifecycle.review_status(p['id'],t['id'],is_selected)
        try:output_path(t,verify=False);media_available=True
        except ValueError:media_available=False
        result.append({k: t[k] for k in ('id', 'shot_id', 'state', 'source_hash', 'prompt_id', 'result', 'error', 'created', 'updated')} |
                      {'kind': 'generation_group' if generation_groups.is_group(t['shot_id']) else 'shot',
                        'mapping': store.setting('generation-group-boundaries:'+t['id'],t['request']['source'].get('mapping')),
                        'current': current, 'selected': is_selected,
                        'execution_state':t['state'],'review_status':review,'compatibility':compatibility,
                        'attempt_id':t['id'],'frozen_request_id':t['request'].get('id'),
                        'media_available':media_available,
                        'used_in_edit':False,
                       'settings': t['request']['settings'], 'mode': t['request']['source']['mode'],
                       'video_url': f'/api/projects/{p["id"]}/video-renders/{t["id"]}/file' if media_available else None})
    return {'shots': ready, 'groups': group_ready, 'takes': result, 'frozen_requests':pending_frozen,
        'defaults': graph.defaults(), 'defaults_by_mode': {m: graph.defaults(m) for m in ('I2VA','FL2VA','REF2VA')}, 'provider': 'MiniMax H3 · 本機 ComfyUI'}


def freeze_request(p,sid,request,src):
    """Materialize a complete immutable request before an attempt can be created."""
    from . import directing, generation_groups
    rid=store.uid()
    settings=render_settings.normalize(request.settings.model_dump(),src['mode'])
    if settings['seed'] is None:settings['seed']=secrets.randbits(32)
    work=store.DATA/'video-requests'/rid
    work.mkdir(parents=True,exist_ok=False)
    for i,ref in enumerate(src['references']):
        original=asset_library.safe_path(ref['path']);content=original.read_bytes()
        if hashlib.sha256(content).hexdigest()!=ref['sha256']:raise ValueError('凍結時參考圖片已改變。')
        (work/f'input-{i}{original.suffix.lower()}').write_bytes(content)
    mapping=src.get('mapping') or {'status':'planned','boundaries':[
        {'edit_id':e['id'],'shot_id':sid,'source_in':e['planned_edit_in'],'source_out':e['planned_edit_out'],
         'timeline_in':e['timeline_in'],'timeline_out':e['timeline_out']}
        for e in directing.edit_rows(p['production']) if e['shot_id']==sid]}
    frozen={'id':rid,'contract_version':1,'project_id':p['id'],'production_revision':p['revision'],
        'created':store.now(),'unit_id':sid,'kind':'generation_group' if generation_groups.is_group(sid) else 'single_source',
        'source_hash':store.digest(src),'source':src,'mapping':mapping,
        'editorial_basis':take_lifecycle.unit_basis(p,sid),
        'generation_intent':take_lifecycle.generation_intent(p,sid),
        'prompt_version':store.digest([src['text'],src.get('global_prompt','')]),
        'prompt_assembly':h3_render_prompt.assemble(src,settings),'settings':settings,
        'requested_settings':request.settings.model_dump(),
        'original_workflow_sha256':graph.ORIGINAL_SHA256,'provider':'comfyui-h3'}
    frozen['request_hash']=store.digest(frozen)
    (work/'request.json').write_text(store.encode(frozen))
    store.put_setting('frozen-video-request:'+p['id']+':'+rid,frozen)
    return frozen


@router.post('/api/projects/{pid}/video-workflow/{sid}/freeze')
def freeze(pid: str,sid: str,request: Generate):
    from . import directing
    with engine.LOCK:
        p=store.project(pid);directing.require_scope(p,sid);src=source(p,sid)
        if store.digest(src)!=request.source_hash:raise ValueError('來源已更新，請重新載入後凍結。')
        if file_hash(graph.ORIGINAL)!=graph.ORIGINAL_SHA256:raise ValueError('工作流版本已改變。')
        return freeze_request(p,sid,request,src)


def update(pid, tid, state, *, error='', result=None, prompt_id=None):
    with store.db() as c:
        c.execute('UPDATE video_takes SET state=?,error=?,updated=? WHERE project_id=? AND id=?',
                  (state, str(error)[:2500], store.now(), pid, tid))
        if result is not None:
            c.execute('UPDATE video_takes SET result=? WHERE id=?', (store.encode(result), tid))
        if prompt_id is not None:
            c.execute('UPDATE video_takes SET prompt_id=? WHERE id=?', (prompt_id, tid))


def schedule(pid, tid, resume=False):
    with WORKER_LOCK:
        if tid in WORKERS:
            return
        WORKERS.add(tid)
    try:
        POOL.submit(run, pid, tid, resume)
    except Exception:
        with WORKER_LOCK:
            WORKERS.discard(tid)
        raise


class ApplyLoraAdvice(models.Strict):
    job_id: str = Field(pattern=r'^[a-f0-9]{16}$')
    model: str = Field(min_length=1, max_length=300)


@router.post('/api/projects/{pid}/video-workflow/{sid}/lora-advice-selection')
def lora_advice_selection(pid: str, sid: str, request: ApplyLoraAdvice):
    from . import h3_lora_advice
    return {'other_loras': h3_lora_advice.selection(pid, sid, request.model, request.job_id)}


@router.post('/api/projects/{pid}/video-workflow/{sid}/prompt-preview')
def prompt_preview(pid: str, sid: str, settings: RenderSettings):
    src = source(store.project(pid), sid)
    cfg = render_settings.normalize(settings.model_dump(), src['mode'])
    return h3_render_prompt.assemble(src, cfg)


@router.post('/api/projects/{pid}/video-workflow/{sid}/generate')
def generate(pid: str, sid: str, request: Generate):
    from . import directing
    with engine.LOCK:
        with store.db() as c:
            prior = c.execute('SELECT * FROM video_takes WHERE project_id=? AND request_key=?', (pid, request.request_key)).fetchone()
        if prior:
            prior = decode(prior)
            if prior['shot_id'] != sid or prior['source_hash'] != request.source_hash or prior['request']['requested_settings'] != request.settings.model_dump() or request.frozen_id and prior['request'].get('id')!=request.frozen_id:
                raise ValueError('這個送出編號已用於不同內容，請重新載入。')
            return prior
        p = store.project(pid)
        directing.require_scope(p,sid)
        src = source(p, sid)
        if store.digest(src) != request.source_hash:
            raise ValueError('分鏡、模式、提示詞或圖片已更新；請重新載入後生成。')
        with store.db() as c:
            prior = c.execute('SELECT * FROM video_takes WHERE project_id=? AND shot_id=? AND state IN (' + ','.join('?' for _ in UNRESOLVED) + ')', (pid, sid, *UNRESOLVED)).fetchone()
        if prior:
            return decode(prior)
        if file_hash(graph.ORIGINAL) != graph.ORIGINAL_SHA256:
            raise ValueError('收藏的原始工作流已更改，請先核對版本。')
        tid, stamp = store.uid(), store.now()
        frozen=store.setting('frozen-video-request:'+pid+':'+request.frozen_id,{}) if request.frozen_id else freeze_request(p,sid,request,src)
        if not frozen or frozen.get('unit_id')!=sid or frozen['source_hash']!=request.source_hash or frozen['requested_settings']!=request.settings.model_dump():
            raise ValueError('凍結請求與本次送出不符，請重新凍結。')
        if store.digest({k:v for k,v in frozen.items() if k!='request_hash'})!=frozen['request_hash']:
            raise ValueError('凍結請求內容已改變，未建立工作。')
        settings=frozen['settings']
        work = folder(tid)
        work.mkdir(parents=True, exist_ok=False)
        # Immutable input bytes are materialized before any background upload.
        for i, ref in enumerate(src['references']):
            original = store.DATA/'video-requests'/frozen['id']/f'input-{i}{Path(ref["path"]).suffix.lower()}'
            content = original.read_bytes()
            if hashlib.sha256(content).hexdigest() != ref['sha256']:
                raise ValueError('素材在送出時改變，未建立生成工作。')
            (work / f'input-{i}{original.suffix.lower()}').write_bytes(content)
        (work / 'request.json').write_text(store.encode(frozen))
        prompt_id = str(uuid.uuid4())
        with store.db() as c:
            c.execute('INSERT INTO video_takes VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                      (tid, pid, sid, request.request_key, 'queued', request.source_hash, store.encode(frozen), prompt_id, None, '', stamp, stamp))
            store.event(c, pid, 'video_requested', f'{sid}：影片生成 {tid}')
        schedule(pid, tid)
        return take(pid, tid)


class AdmissionStopped(RuntimeError):
    pass


@contextmanager
def queued_reservation(pid, tid):
    update(pid, tid, 'queued', error='正在等候 GPU／影片服務；輪到本工作會自動開始，毋須再次按生成。')
    with ExitStack() as stack:
        while not STOP.is_set():
            try:
                # The manager holds a real pending lease during each window.
                # Renew only explicit pre-admission contention on the same take.
                evidence = stack.enter_context(comfy_runtime.reserve('h3', wait_seconds=30))
                break
            except comfy_runtime.AdmissionBusy:
                if STOP.wait(1):
                    raise AdmissionStopped()
        else:
            raise AdmissionStopped()
        if STOP.is_set():
            raise AdmissionStopped()
        # Deliberately outside the retry catch: never replay uploads or /prompt.
        yield evidence


def run(pid, tid, resume=False):
    work = folder(tid)
    submitted = resume
    try:
        t = take(pid, tid)
        reservation = nullcontext() if resume else queued_reservation(pid, tid)
        with reservation, provider.client() as c:
            if not resume:
                if STOP.is_set():
                    return
                update(pid, tid, 'preparing')
                evidence = provider.check_guard(c)
                info = provider.schema(c)
                req = t['request']
                if req.get('request_hash') and store.digest({k:v for k,v in req.items() if k!='request_hash'})!=req['request_hash']:
                    raise ValueError('原始凍結請求已改變，尚未送出影片。')
                generation_source = h3_render_prompt.generation_source(req['source'], req['prompt_assembly']) if req.get('prompt_assembly') else req['source']
                # Validate the graph before uploading anything; names will be replaced by verified receipts.
                preview = {r['asset_id']: {'name': f'input-{i}.png', 'subfolder': 'ContinuityStudio/' + tid, 'type': 'input'} for i, r in enumerate(req['source']['references'])}
                graph.build_graph(generation_source, preview, req['settings'], tid, info)
                if store.digest(source(store.project(pid), t['shot_id'])) != t['source_hash']:
                    raise ValueError('等待期間素材或分鏡已更新，尚未送出影片。')
                uploaded = {}
                for i, ref in enumerate(req['source']['references']):
                    path = work / f'input-{i}{Path(ref["path"]).suffix.lower()}'
                    if file_hash(path) != ref['sha256']:
                        raise ValueError('已凍結的參考圖片被更改，尚未送出影片。')
                    uploaded[ref['asset_id']] = provider.upload(c, tid, ref, path)
                workflow = graph.build_graph(generation_source, uploaded, req['settings'], tid, info)
                (work / 'graph.json').write_text(store.encode(workflow))
                (work / 'transport.json').write_text(store.encode({'guard': evidence, 'schema_hash': store.digest(info), 'uploads': uploaded}))
                # Serialize the final freshness check with Studio creative mutations.
                with engine.LOCK:
                    if store.digest(source(store.project(pid), t['shot_id'])) != t['source_hash']:
                        raise ValueError('上傳期間分鏡或素材已更新，尚未送出影片。')
                    if STOP.is_set():
                        return
                    update(pid, tid, 'submitting')
                submitted = True  # Persist intent before the only POST; timeout is ambiguous.
                receipt = provider.submit(c, workflow, tid, t['prompt_id'])
                (work / 'receipt.json').write_text(store.encode(receipt))
                update(pid, tid, 'submitted', prompt_id=receipt['prompt_id'])
                t['prompt_id'] = receipt['prompt_id']
            workflow = json.loads((work / 'graph.json').read_text())
            errors = 0
            while not STOP.is_set():
                try:
                    found = provider.inspect(c, tid, t['prompt_id'], store.digest(workflow), search=resume)
                    if found['state'] == 'unknown':
                        update(pid, tid, 'uncertain', error='暫未在 ComfyUI 隊列或歷史找到這次工作；為免重複生成，只可重新查詢。')
                        return
                    t['prompt_id'] = found['prompt_id']
                    if found['state'] == 'history':
                        history = found['history']
                        (work / 'history.json').write_text(store.encode(history))
                        descriptor = provider.history_result(history)
                        update(pid, tid, 'recoverable', error='影片已生成，正在回收成片。', prompt_id=t['prompt_id'])
                        output = work / 'output.mp4'
                        result = provider.download(c, descriptor, tid, output)
                        settings = t['request']['settings']
                        if (result['width'], result['height']) != render_settings.output_dimensions(settings):
                            raise ValueError('成片尺寸與本次生成設定不符，尚未採入 Studio。')
                        if settings.get('audio_mode', 'generate') == 'generate' and not result.get('audio_channels'):
                            raise ValueError('選擇聲畫一起生成，但成片缺少音軌。')
                        if settings.get('audio_mode') == 'mute' and result.get('audio_channels'):
                            raise ValueError('選擇靜音影片，但成片仍含音軌。')
                        expected_seconds = graph.frame_count(t['request']['source']['duration']) / 24
                        if abs(result['duration'] - expected_seconds) > 0.5:
                            raise ValueError('成片時長與本鏡對齊影格差異過大，請查看 ComfyUI 工作記錄。')
                        result.update(path=str(output.relative_to(store.DATA)), workflow_hash=store.digest(workflow),
                                      requested_duration=t['request']['source']['duration'], prompt_id=t['prompt_id'])
                        (work / 'result.json').write_text(store.encode(result))
                        update(pid, tid, 'succeeded', result=result, prompt_id=t['prompt_id'])
                        return
                    update(pid, tid, found['state'], prompt_id=t['prompt_id'])
                    errors = 0
                except httpx.HTTPError as e:
                    errors += 1
                    if errors >= 3:
                        raise RuntimeError('ComfyUI 連線中斷；原工作保留，可重新查詢，未重新生成。') from e
                if STOP.wait(3):
                    return
    except AdmissionStopped:
        pass  # Keep the unsubmitted frozen take queued for normal startup.
    except provider.Rejected as e:
        update(pid, tid, 'failed', error=e)
    except Exception as e:
        current = take(pid, tid)['state']
        state_name = 'recoverable' if current == 'recoverable' or (work / 'history.json').exists() else 'uncertain' if submitted else 'failed'
        update(pid, tid, state_name, error=('送出狀態未能確認；請重新查詢原工作。' if state_name == 'uncertain' else '') + str(e))
    finally:
        with WORKER_LOCK:
            WORKERS.discard(tid)


@router.get('/api/video-provider/options')
def provider_options():
    return provider.options()


@router.get('/api/video-provider/status')
def provider_status():
    return provider.status()


@router.post('/api/video-provider/prepare')
def prepare_provider():
    # An explicit preparation action may switch via the manager; GET stays passive.
    # The generation worker reacquires and verifies its own reservation on submit.
    with comfy_runtime.reserve('h3'):
        result = provider.status()
        if result['ready']:
            result['message'] = 'H3 影片服務已準備好；尚未開始生成影片。'
        return result


@router.get('/api/projects/{pid}/video-renders/{tid}')
def detail(pid: str, tid: str):
    t = take(pid, tid)
    t['job_attempt']={'id':tid,'execution_state':t['state'],'frozen_request_id':t['request'].get('id'),
        'request_hash':t['request'].get('request_hash'),'prompt_id':t['prompt_id']}
    t['review_history']=take_lifecycle.reviews(pid,tid)
    t['boundary_history']=store.setting('generation-group-boundary-history:'+tid,[])
    t['compatibility']=take_lifecycle.compatibility(store.project(pid),t)
    t['evidence_files'] = [p.name for p in folder(tid).glob('*.json')]
    from . import storyboard_usage
    submitted=[s for s in storyboard_usage.submitted_inputs({'id':pid}) if s['take_id']==tid]
    t['image_inputs']=[{**ref,'submission_verified':any(s['asset_id']==ref['asset_id'] and s['sha256']==ref['sha256'] for s in submitted)}
        for ref in t['request']['source']['references']]
    return t


@router.post('/api/projects/{pid}/video-renders/{tid}/recover')
def recover(pid: str, tid: str):
    with engine.LOCK:
        t = take(pid, tid)
        if t['state'] not in ('uncertain', 'recoverable', 'submitted', 'running'):
            raise ValueError('此工作不需要重新查詢。')
        if not (folder(tid) / 'graph.json').is_file():
            raise ValueError('找不到原始送出資料，請查看工作記錄；不會重新生成。')
        schedule(pid, tid, resume=True)
    return take(pid, tid)


def output_path(t, verify=True):
    path = folder(t['id']) / 'output.mp4'
    if not t['result'] or not path.is_file() or path.is_symlink():
        raise ValueError('找不到完整成片。')
    if verify and file_hash(path) != t['result']['sha256']:
        raise ValueError('成片檔案被更改，請重新回收原始輸出。')
    return path


@router.get('/api/projects/{pid}/video-renders/{tid}/file')
def video_file(pid: str, tid: str):
    t = take(pid, tid)
    return FileResponse(output_path(t), media_type='video/mp4', filename=f'{asset_library.clean_name(t["shot_id"])}-{tid}.mp4', content_disposition_type='inline')


@router.post('/api/projects/{pid}/video-renders/{tid}/adopt')
def adopt(pid: str, tid: str, data: Adopt):
    with engine.LOCK:
        t = take(pid, tid)
        compatible=take_lifecycle.compatibility(store.project(pid),t)
        if t['state'] != 'succeeded' or not take_lifecycle.accepted_compatibility(compatible) or t['source_hash'] != data.source_hash:
            raise ValueError('此影片尚未完成或素材／方向已更新，不能採用為目前成片。')
        output_path(t)
        take_lifecycle.record(pid,tid,'accepted')
        with store.db() as c:
            c.execute('INSERT OR REPLACE INTO video_selections VALUES(?,?,?)', (pid, t['shot_id'], tid))
            store.event(c, pid, 'video_adopted', tid)
    return take(pid, tid)


class TakeReview(models.Strict):
    decision: str = Field(pattern=r'^(accepted|rejected)$')
    compatibility_hash: str = Field(pattern=r'^[a-f0-9]{64}$')


@router.post('/api/projects/{pid}/video-renders/{tid}/review')
def review_take(pid: str,tid: str,request: TakeReview):
    with engine.LOCK:
        t=take(pid,tid)
        if t['state']!='succeeded':raise ValueError('請先等候影片完成。')
        output_path(t)
        compatible=take_lifecycle.compatibility(store.project(pid),t)
        if compatible['current_hash']!=request.compatibility_hash:raise ValueError('看片期間來源已更新，請重新核對。')
        return take_lifecycle.record(pid,tid,request.decision,request.compatibility_hash)


def add_export(z, p):
    data = p['video_renders']
    from . import generation_groups
    z.writestr('video/takes.json', store.encode(data))
    z.writestr('video/generation-groups.json', store.encode(generation_groups.config(p['id'])))
    from . import edit_segments
    segments=edit_segments.state(p)
    z.writestr('edit/segments.json',store.encode(segments))
    z.writestr('edit/segment-history.json',store.encode(edit_segments.config(p['id'])))
    used={r['material']['take_id'] for r in segments['segments'] if r['material'] and r['status'] in ('current','legacy_observed')}
    for row in p.get('generation_groups', {}).get('rows', []):
        if row['ready']:
            packet = generation_groups.render_source(p, row['id'])
            z.writestr('video-workflow/groups/' + row['id'] + '/handoff.json', store.encode(packet))
            z.writestr('video-workflow/groups/' + row['id'] + '/prompt.txt', packet['text'])
    for item in data['takes']:
        if (item['selected'] or item['id'] in used) and item.get('review_status','accepted')=='accepted' and item['current'] and item['state'] == 'succeeded':
            t = take(p['id'], item['id'])
            z.write(output_path(t), 'video/' + t['id'] + '.mp4')
            z.writestr('video/' + t['id'] + '-provenance.json', store.encode(t))
            if item.get('mapping'):
                z.writestr('video/' + t['id'] + '-storyboard-mapping.json', store.encode(item['mapping']))
                z.writestr('video/' + t['id'] + '-storyboard-mapping-history.json',store.encode(store.setting('generation-group-boundary-history:'+t['id'],[])))
