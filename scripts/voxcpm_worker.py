#!/usr/bin/env python3
"""One actual synthesis, with a PID-owned VRAM lease before all GPU imports."""
import gc, json, os, sys, traceback
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def control(base,route,payload):
    req=Request(base+route,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urlopen(req,timeout=90) as r:return json.load(r)
    except HTTPError as exc:
        if exc.code!=409 or route!='/vram/gpu/acquire':raise
        try:detail=json.loads(exc.read(8192)).get('error','GPU 忙碌')
        except (ValueError,UnicodeError):detail='GPU 忙碌'
        raise RuntimeError('GPU 資源未就緒，VRAM Manager 暫未批准配音。請待目前工作完成或本機服務復原後再生成。原因：'+str(detail)[:500]) from None


def generation_args(r):
    mode=r.get('reference_mode','timbre')
    if mode not in ('timbre','clone'):raise ValueError('未知的參考聲音模式。')
    if mode=='clone' and (not r.get('reference_path') or not r.get('reference_text','').strip()):
        raise ValueError('Clone 需要參考音訊及完整逐字稿。')
    text=f'({r["control"]}){r["text"]}' if r.get('control') and mode!='clone' else r['text']
    args={'text':text,'seed':r['seed'],'cfg_value':2.0,'inference_timesteps':10,'normalize':False,'denoise':False,'retry_badcase':False}
    if r.get('reference_path'):args['reference_wav_path']=r['reference_path']
    if mode=='clone':args.update(prompt_wav_path=r['reference_path'],prompt_text=r['reference_text'])
    return args


def main(request_file):
    source=Path(request_file);r=json.loads(source.read_text());model=None;torch=None;wav=None;acquired=False
    try:
        lease=control(r['manager'],'/vram/gpu/acquire',{'token':r['token'],'workload':'continuity-voxcpm','pid':os.getpid(),'timeout':30})
        if lease.get('phase')!='granted':raise RuntimeError('VRAM Manager 未批准此工作。')
        acquired=True
        args=generation_args(r)
        import torch
        import numpy as np
        import soundfile as sf
        from voxcpm import VoxCPM
        if not torch.cuda.is_available():raise RuntimeError('VoxCPM2 GPU 不可用；沒有改用其他供應器。')
        model=VoxCPM.from_pretrained(r['model'],load_denoiser=False,optimize=False,device='cuda',local_files_only=True)
        wav=model.generate(**args)
        if not np.isfinite(wav).all() or len(wav)==0 or np.max(np.abs(wav))<0.0006:raise RuntimeError('VoxCPM2 回傳無效或靜音波形。')
        sf.write(r['output'],wav,model.tts_model.sample_rate,subtype='PCM_16')
        result={'sample_rate':model.tts_model.sample_rate,'model':r['model'],'seed':r['seed']}
    finally:
        # Drop the model before releasing its reservation; process exit also tears down GPU context.
        model=None;wav=None;gc.collect()
        try:
            if torch is not None:
                torch.cuda.empty_cache()
                if torch.cuda.is_available():torch.cuda.synchronize()
        finally:
            if acquired:control(r['manager'],'/vram/gpu/release',{'token':r['token']})
    (source.parent/'result.json').write_text(json.dumps(result))

if __name__=='__main__':
    try:main(sys.argv[1])
    except Exception:
        traceback.print_exc();sys.exit(1)
