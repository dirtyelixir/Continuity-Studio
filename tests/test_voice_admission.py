import importlib.util,io,json
from pathlib import Path
from urllib.error import HTTPError
import pytest
from studio import postproduction as pp,voxcpm_provider as provider
from test_production import client,plan,create


def test_new_role_uses_dialogue_language_and_matching_sample(client,plan):
    pid=create(client,plan)
    p=pp.profile(pid,'ada')
    assert p['language']=='英文' and p['sample_text']==pp.AUDITION_TEXTS['英文']
    plan['canon'].append({'id':'pip','kind':'character','name':'Pip','description':'Robot','facts':[]})
    other=create(client,plan)
    assert pp.profile(other,'pip')['language']=='英文'


def test_save_corrects_only_known_default_sample(client,plan):
    pid=create(client,plan)
    data={'version':0,'description':'A clear young voice','language':'英文','sample_text':pp.AUDITION_TEXTS['粵語（香港）'],'seed':42}
    r=client.put(f'/api/projects/{pid}/voices/ada',json=data)
    assert r.status_code==200 and r.json()['sample_text']==pp.AUDITION_TEXTS['英文']
    data.update(version=1,sample_text='This is my own sentence.',language='國語（台灣）')
    r=client.put(f'/api/projects/{pid}/voices/ada',json=data)
    assert r.status_code==200 and r.json()['sample_text']=='This is my own sentence.'


def test_acquire_conflict_has_actionable_error_without_gpu_import(monkeypatch):
    spec=importlib.util.spec_from_file_location('admission_worker',Path(__file__).parents[1]/'scripts/voxcpm_worker.py');worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    def deny(*a,**k):raise HTTPError('http://manager/vram/gpu/acquire',409,'Conflict',None,io.BytesIO(b'{"error":"GPU busy: comfyui"}'))
    monkeypatch.setattr(worker,'urlopen',deny)
    with pytest.raises(RuntimeError,match='GPU 資源未就緒.*comfyui'):
        worker.control('http://manager','/vram/gpu/acquire',{})


@pytest.mark.parametrize('state,message',[({'gpu_leases':1,'gpu_workloads':{'owner':'comfyui'}},'comfyui'),({'maintenance':True},'切換'),({'paused':True},'切換')])
def test_status_discloses_admission_block(monkeypatch,state,message):
    monkeypatch.setattr(provider.Path,'is_file',lambda s:True)
    monkeypatch.setattr(provider,'urlopen',lambda *a,**k:io.BytesIO(json.dumps(state).encode()))
    result=provider.status()
    assert result['runtime_ready'] and not result['ready'] and message in result['error']


def test_status_idle_and_offline(monkeypatch):
    monkeypatch.setattr(provider.Path,'is_file',lambda s:True)
    monkeypatch.setattr(provider,'urlopen',lambda *a,**k:io.BytesIO(b'{"gpu_leases":0}'))
    assert provider.status()['ready']
    monkeypatch.setattr(provider,'urlopen',lambda *a,**k:(_ for _ in ()).throw(OSError('offline')))
    assert not provider.status()['ready'] and 'VRAM Manager' in provider.status()['error']
