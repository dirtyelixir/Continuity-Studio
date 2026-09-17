import importlib.util, json, subprocess
from pathlib import Path
import pytest
from studio import voxcpm_provider as v
from test_postproduction import wav


def prepare(monkeypatch,tmp_path):
    monkeypatch.setattr(v,'status',lambda:{'ready':True})
    released=[];monkeypatch.setattr(v,'release',lambda manager,token:released.append(token))
    return tmp_path/'out.wav',tmp_path/'job',released


def test_real_command_evidence_and_pcm_verification(monkeypatch,tmp_path):
    output,work,released=prepare(monkeypatch,tmp_path)
    class Process:
        def __init__(self,command,**kwargs):
            assert command[0].endswith('/VoxCPM/.venv/bin/python') and command[1].endswith('/scripts/voxcpm_worker.py')
            assert kwargs['start_new_session'] and kwargs['env']['HF_HUB_OFFLINE']=='1'
            req=json.loads(Path(command[2]).read_text());assert req['text']=='Exact words.' and req['control']=='warm'
            output.write_bytes(wav());(work/'result.json').write_text(json.dumps({'sample_rate':8000}))
        def wait(self,timeout):assert timeout==900;return 0
    monkeypatch.setattr(v.subprocess,'Popen',Process)
    r=v.synthesize({'text':'Exact words.','control':'warm','seed':42},output,work)
    assert r['duration']==3 and r['sample_rate']==8000 and len(r['sha256'])==64 and released


def test_timeout_kills_child_before_release(monkeypatch,tmp_path):
    output,work,released=prepare(monkeypatch,tmp_path);events=[]
    class Process:
        pid=123
        def __init__(self,*a,**k):self.calls=0
        def wait(self,timeout):
            self.calls+=1
            if self.calls==1:raise subprocess.TimeoutExpired('worker',timeout)
            events.append('exit');return -15
    monkeypatch.setattr(v.subprocess,'Popen',Process);monkeypatch.setattr(v.os,'killpg',lambda *a:events.append('kill'))
    monkeypatch.setattr(v,'release',lambda *a:events.append('release'))
    with pytest.raises(RuntimeError,match='逾時'):v.synthesize({'text':'Hello','seed':1},output,work)
    assert events==['kill','exit','release']


def test_invalid_silent_and_missing_runtime_fail_closed(monkeypatch,tmp_path):
    path=tmp_path/'bad.wav';path.write_bytes(b'not wav')
    with pytest.raises(ValueError):v.validate_audio(path)
    import io,wave
    b=io.BytesIO()
    with wave.open(b,'wb') as w:w.setparams((1,2,8000,0,'NONE',''));w.writeframes(b'\0'*16000)
    path.write_bytes(b.getvalue())
    with pytest.raises(ValueError):v.validate_audio(path)
    monkeypatch.setenv('STUDIO_VOXCPM_MODEL',str(tmp_path/'missing'))
    assert not v.status()['ready']
    with pytest.raises(ValueError,match='缺少'):v.synthesize({'text':'Hi','seed':1},path,tmp_path/'job')


def test_worker_denied_lease_never_imports_gpu(monkeypatch,tmp_path):
    spec=importlib.util.spec_from_file_location('test_voice_worker',Path(__file__).parents[1]/'scripts/voxcpm_worker.py');worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    calls=[];monkeypatch.setattr(worker,'control',lambda *a:(calls.append(a[1]) or {'phase':'denied'}))
    import builtins
    original=builtins.__import__
    def controlled(name,*a,**k):
        if name in ['torch','voxcpm']:raise AssertionError('GPU import before lease')
        return original(name,*a,**k)
    monkeypatch.setattr(builtins,'__import__',controlled)
    path=tmp_path/'request.json';path.write_text(json.dumps({'manager':'http://manager','token':'owned'}))
    with pytest.raises(RuntimeError,match='未批准'):worker.main(path)
    assert calls==['/vram/gpu/acquire']
