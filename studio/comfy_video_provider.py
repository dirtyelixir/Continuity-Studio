"""ComfyUI transport. Submission is never automatically retried."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path, PurePosixPath

import httpx

from . import h3_render_graph as graph


def configuration():
    return {'url': 'http://127.0.0.1:8188',
            'manager': os.environ.get('STUDIO_VRAM_URL', 'http://127.0.0.1:8082').rstrip('/')}


def client():
    return httpx.Client(base_url=configuration()['url'], timeout=20, trust_env=False)


def get(c, route):
    response = c.get(route)
    response.raise_for_status()
    return response.json()


def check_guard(c):
    if not shutil.which('ffprobe'):
        raise ValueError('缺少 ffprobe，未能驗證成片，尚未送出影片。')
    state = get(c, '/vram/status')
    if not state.get('ok') or not state.get('monitor_alive') or not state.get('pid'):
        raise ValueError('ComfyUI 的 VRAM Manager 保護未就緒，尚未送出影片。')
    with httpx.Client(timeout=10, trust_env=False) as manager:
        response = manager.get(configuration()['manager'] + '/vram/status')
        response.raise_for_status()
        status = response.json()
    if not status.get('ok') or status.get('paused'):
        raise ValueError('VRAM Manager 尚未開放工作，尚未送出影片。')
    if status.get('comfy_mode', {}).get('running') != 'h3':
        raise ValueError('ComfyUI 尚未切換至 H3；Studio 會在生成前自動切換，亦可按「準備影片服務」先行準備。')
    return {'comfy_pid': state['pid'], 'guarded': True, 'mode': 'h3'}


def schema(c):
    result = {}
    for name in (*graph.CLASSES, *graph.OPTIONAL_CLASSES):
        result.update(get(c, '/object_info/' + name))
    return result


def status():
    try:
        with client() as c:
            evidence = check_guard(c)
            info = schema(c)
            missing = [name for name in graph.CLASSES if name not in info]
            if missing:
                raise ValueError('ComfyUI 缺少節點：' + '、'.join(missing))
        return {'ready': True, 'name': 'MiniMax H3 · 本機 ComfyUI', 'message': 'ComfyUI 與 VRAM Manager 已連接；生成時會再檢查模型及素材。', **evidence}
    except (httpx.HTTPError, ValueError, KeyError) as error:
        return {'ready': False, 'name': 'MiniMax H3 · 本機 ComfyUI', 'message': '影片服務未就緒：' + str(error)[:500]}


def upload(c, job_id, ref, path):
    folder = 'ContinuityStudio/' + job_id
    filename = ref['asset_id'] + '-' + ref['sha256'][:16] + Path(path).suffix.lower()
    with Path(path).open('rb') as f:
        response = c.post('/upload/image', data={'type': 'input', 'subfolder': folder, 'overwrite': 'false'},
                          files={'image': (filename, f, 'application/octet-stream')})
    response.raise_for_status()
    receipt = response.json()
    graph.media_path(receipt)
    if receipt['subfolder'] != folder:
        raise ValueError('ComfyUI 未保存到本次影片的素材資料夾。')
    response = c.get('/view', params={'filename': receipt['name'], 'subfolder': folder, 'type': 'input'})
    response.raise_for_status()
    if hashlib.sha256(response.content).hexdigest() != ref['sha256']:
        raise ValueError('ComfyUI 收到的圖片與 Studio 原始素材不同，尚未送出影片。')
    return {**receipt,'verified_sha256':ref['sha256']}


class Rejected(ValueError):
    """Explicit pre-enqueue rejection; a new user action may try again."""


def submit(c, workflow, job_id, requested_id):
    # The existing ComfyUI middleware obtains/revalidates its process-owned lease.
    # No extra GPU lease, service restart, model eviction or retry is performed here.
    try:
        response = c.post('/prompt', json={'prompt': workflow, 'prompt_id': requested_id,
                          'client_id': 'continuity-studio',
                          'extra_data': {'continuity_studio_job_id': job_id, 'workflow_hash': _hash(workflow)}},
                          timeout=700)
    except (httpx.ConnectError, httpx.ConnectTimeout) as error:
        raise Rejected('未能連接 ComfyUI，影片尚未送出。') from error
    if response.status_code in (400, 422, 503):
        try:
            body = response.json()
        except ValueError:
            body = {}
        kind = body.get('error')
        # Only a known ComfyUI validation/admission response proves no enqueue.
        if isinstance(kind, dict) and (response.status_code == 400 or kind.get('type') == 'vram_manager_unavailable'):
            raise Rejected('ComfyUI 拒絕生成：' + json.dumps(body, ensure_ascii=False)[:2200])
    response.raise_for_status()
    data = response.json()
    if not isinstance(data.get('prompt_id'), str) or not data['prompt_id']:
        raise RuntimeError('ComfyUI 未回傳有效工作編號。')
    return {**data,'studio_workflow_hash':_hash(workflow)}


def _hash(data):
    from . import store
    return store.digest(data)


def _belongs(item, job_id, workflow_hash):
    prompt = item.get('prompt') if isinstance(item, dict) else item
    return (isinstance(prompt, (list, tuple)) and len(prompt) > 3 and isinstance(prompt[3], dict)
            and prompt[3].get('continuity_studio_job_id') == job_id
            and prompt[3].get('workflow_hash') == workflow_hash)


def inspect(c, job_id, prompt_id, workflow_hash, search=False):
    history = get(c, '/history/' + prompt_id)
    found = history.get(prompt_id)
    if found:
        if not _belongs(found, job_id, workflow_hash):
            raise ValueError('ComfyUI 結果不屬於這次影片工作，未回收檔案。')
        return {'state': 'history', 'prompt_id': prompt_id, 'history': found}
    queue = get(c, '/queue')
    for key, state in [('queue_running', 'running'), ('queue_pending', 'submitted')]:
        for position, item in enumerate(queue.get(key, [])):
            if _belongs(item, job_id, workflow_hash):
                return {'state': state, 'prompt_id': item[1], 'queue_position': position + 1}
    if search:
        # Older Comfy versions may ignore our client-generated prompt_id.
        for pid, item in get(c, '/history?max_items=500').items():
            if _belongs(item, job_id, workflow_hash):
                return {'state': 'history', 'prompt_id': pid, 'history': item}
    return {'state': 'unknown'}


def history_result(history):
    status = history.get('status', {})
    for kind, detail in status.get('messages', []):
        if kind in ('execution_error', 'execution_interrupted'):
            raise Rejected('ComfyUI 生成失敗：' + str(detail.get('exception_message') or kind)[:2000])
    if status.get('status_str') == 'error':
        raise Rejected('ComfyUI 回報生成失敗，請查看工作記錄。')
    if not status.get('completed'):
        raise RuntimeError('ComfyUI 結果尚未標示完成。')
    saved = history.get('outputs', {}).get('7', {})
    candidates = [v for key in ('images', 'gifs', 'videos') for v in saved.get(key, [])
                  if isinstance(v, dict) and str(v.get('filename', '')).lower().endswith('.mp4')]
    if len(candidates) != 1:
        raise RuntimeError('ComfyUI 已完成，但未回傳唯一 MP4 成片；保留工作供重新回收。')
    return candidates[0]


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                            capture_output=True, text=True, timeout=45, check=True)
    data = json.loads(result.stdout)
    video = next((s for s in data['streams'] if s.get('codec_type') == 'video'), None)
    audio = next((s for s in data['streams'] if s.get('codec_type') == 'audio'), None)
    if not video or float(data['format'].get('duration', 0)) <= 0:
        raise ValueError('輸出未包含有效影片，請查看 ComfyUI 工作記錄。')
    return {'duration': float(data['format']['duration']), 'width': video['width'], 'height': video['height'],
            'frame_count': int(video['nb_frames']) if str(video.get('nb_frames', '')).isdigit() else None,
            'frame_rate': video.get('avg_frame_rate'), 'audio_channels': audio.get('channels') if audio else 0,
            'video_codec': video.get('codec_name'), 'audio_codec': audio.get('codec_name') if audio else None}


def download(c, descriptor, job_id, destination):
    name, folder = descriptor.get('filename', ''), descriptor.get('subfolder', '')
    if (descriptor.get('type') != 'output' or PurePosixPath(folder) != PurePosixPath('ContinuityStudio') / job_id
            or '/' in name or '\\' in name or not name.endswith('.mp4')):
        raise ValueError('ComfyUI 成片位置與本次工作不符。')
    destination = Path(destination)
    partial = destination.with_suffix('.part.mp4')
    digest, size = hashlib.sha256(), 0
    with c.stream('GET', '/view', params={'filename': name, 'subfolder': folder, 'type': 'output'}, timeout=120) as response:
        response.raise_for_status()
        with partial.open('wb') as f:
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > 8 * 1024**3:
                    raise ValueError('影片超過單檔 8 GiB 上限，未完成回收。')
                f.write(chunk)
                digest.update(chunk)
    metadata = probe(partial)
    partial.replace(destination)
    return {**metadata, 'sha256': digest.hexdigest(), 'bytes': size, 'comfy_output': descriptor}


def options():
    """Read installed choices only; never load models, acquire GPU or submit a job."""
    from . import h3_render_settings as settings, h3_lora_catalog
    with client() as c:
        info = schema(c)
    def choices(cls, field):
        spec = graph._inputs(info.get(cls, {})).get(field, [[]])
        return spec[0] if isinstance(spec[0], list) else spec[1].get('options', []) if len(spec)>1 else []
    names = choices('LoraLoaderModelOnly', 'lora_name')
    # This is an H3 tool: omit known unrelated SD/Flux/Wan/audio LoRAs from the menu.
    loras = [{**h3_lora_catalog.preset(n), 'name':n,'family':settings.lora_family(n),
              'turbo':bool('turbo' in n.lower() and settings.lora_family(n)),
              'recommended_steps':settings.recommended_steps(n)} for n in names
             if 'h3' in n.lower() or 'minimax' in n.lower()]
    models = [{'name': n, 'family': settings.model_family(n)}
              for n in choices('UNETLoader', 'unet_name') if settings.model_family(n)]
    return {'models':models, 'loras':loras, 'attention':['default', *[k for k,v in graph.ATTENTION_CLASSES.items() if v in info and (k != 'kitchen' or 'comfy kitchen attention' in choices(v,'attention'))]],
            'upscale_models':choices('UpscaleModelLoader','model_name'),
            'second_pass_available':'MiniMaxH3DirectorRefine' in info and 'BasicScheduler' in info,
            'frame_rate':24}
