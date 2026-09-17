"""Fail-closed local VoxCPM2 adapter. GPU lifetime is a child process lifetime."""
import array, hashlib, json, os, signal, subprocess, uuid, wave
from pathlib import Path
from urllib.request import Request, urlopen


def configuration():
    return {'python':os.environ.get('STUDIO_VOXCPM_PYTHON','/home/navievroom/VoxCPM/.venv/bin/python'),
            'model':os.environ.get('STUDIO_VOXCPM_MODEL','/home/navievroom/comfy/ComfyUI/models/tts/VoxCPM/VoxCPM2'),
            'pythonpath':os.environ.get('STUDIO_VOXCPM_PYTHONPATH','/home/navievroom/VoxCPM/runtime:/home/navievroom/VoxCPM/src:/home/navievroom/comfy/ComfyUI/.venv/lib/python3.12/site-packages'),
            'manager':os.environ.get('STUDIO_VRAM_URL','http://127.0.0.1:8082').rstrip('/')}


def status():
    cfg=configuration();missing=[]
    if not Path(cfg['python']).is_file():missing.append('VoxCPM Python')
    model=Path(cfg['model'])
    for name in ['config.json','tokenizer.json','tokenizer_config.json']:
        if not (model/name).is_file():missing.append(name)
    for names in [('model.safetensors','pytorch_model.bin'),('audiovae.pth','audiovae.safetensors')]:
        if not any((model/n).is_file() for n in names):missing.append('/'.join(names))
    result={'ready':not missing,'runtime_ready':not missing,'model':cfg['model'],'error':'缺少本機 VoxCPM2 檔案：'+', '.join(missing) if missing else ''}
    if missing:return result
    try:
        with urlopen(cfg['manager']+'/vram/status',timeout=5) as response:state=json.load(response)
        workloads=sorted(set(state.get('gpu_workloads',{}).values()))
        if state.get('paused') or state.get('maintenance') or state.get('transition'):
            result.update(ready=False,error='VRAM Manager 正在暫停或切換，本機配音暫未就緒。')
        elif state.get('gpu_leases'):
            result.update(ready=False,error='GPU 正由其他工作使用（'+', '.join(workloads or ['GPU 工作'])+'）；請待工作完成或服務復原後再生成配音。')
        result['gpu_workloads']=workloads
    except Exception:
        result.update(ready=False,error='暫時無法連線至 VRAM Manager，尚未開始配音。')
    return result


def validate_audio(path):
    try:
        with wave.open(str(path),'rb') as w:
            rate=w.getframerate();n=w.getnframes();channels=w.getnchannels();width=w.getsampwidth();raw=w.readframes(n)
            if rate<8000 or channels not in [1,2] or width!=2 or n<rate//10 or len(raw)!=n*channels*width:raise ValueError()
            samples=array.array('h',raw)
            if max(abs(x) for x in samples)<20:raise ValueError()
        return {'sample_rate':rate,'duration':n/rate,'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}
    except Exception:raise ValueError('VoxCPM2 未產生有效的非靜音 PCM WAV。') from None


def release(manager,token):
    req=Request(manager+'/vram/gpu/release',data=json.dumps({'token':token}).encode(),headers={'Content-Type':'application/json'},method='POST')
    with urlopen(req,timeout=10) as r:return json.load(r)


def synthesize(request,output,workdir):
    cfg=configuration();ready=status()
    if not ready['ready']:raise ValueError(ready['error'])
    if not request.get('text','').strip():raise ValueError('配音文字不能留空。')
    output=Path(output).resolve();workdir=Path(workdir).resolve();workdir.mkdir(parents=True,exist_ok=True);output.parent.mkdir(parents=True,exist_ok=True)
    token='continuity-voxcpm-'+uuid.uuid4().hex
    payload={**request,'output':str(output),'model':cfg['model'],'manager':cfg['manager'],'token':token}
    inp=workdir/'request.json';inp.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    env={**os.environ,'PYTHONPATH':cfg['pythonpath'],'VOXCPM_DISABLE_COMPILE':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
    worker=Path(__file__).resolve().parent.parent/'scripts'/'voxcpm_worker.py'
    with (workdir/'worker.log').open('w') as log:
        proc=subprocess.Popen([cfg['python'],str(worker),str(inp)],stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
        try:code=proc.wait(timeout=900)
        except BaseException:
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=10)
            try:release(cfg['manager'],token)
            except Exception:pass # dead PID is independently pruned by the manager
            raise RuntimeError('VoxCPM2 工作逾時或被中斷；請查看工作記錄。') from None
    try:release(cfg['manager'],token)
    except Exception as e:
        raise RuntimeError('VoxCPM2 已退出，但未能確認 VRAM 預留已釋放：'+str(e)) from e
    if code:
        detail=(workdir/'worker.log').read_text(errors='replace')[-2000:]
        raise RuntimeError('VoxCPM2 生成失敗：'+detail)
    result_file=workdir/'result.json'
    if not result_file.is_file():raise ValueError('VoxCPM2 沒有回傳生成結果。')
    result=json.loads(result_file.read_text());verified=validate_audio(output)
    if result.get('sample_rate')!=verified['sample_rate']:raise ValueError('VoxCPM2 音檔取樣率與結果不符。')
    return {**verified,'model':cfg['model'],'seed':request['seed']}
