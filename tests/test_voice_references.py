import importlib.util,io,zipfile
from pathlib import Path
import pytest
from studio import postproduction as pp,store,voxcpm_provider
from test_production import client,plan,create
from test_postproduction import setup_voice,wav,adopted


def attachment(client,pid,version=1):
    r=client.post(f'/api/projects/{pid}/voices/ada/upload',data={'version':version,'attachment':'true'},files={'file':('voice.wav',wav(),'audio/wav')})
    assert r.status_code==200,r.text
    return r.json()


def save_ref(client,pid,p,t,mode='timbre',text=''):
    return client.put(f'/api/projects/{pid}/voices/ada',json={**pp.config(p),'version':p['version'],'reference_take_id':t['id'],'reference_mode':mode,'reference_text':text})


def test_attach_before_first_save_is_not_adopted_or_generated(client,plan):
    pid=create(client,plan);t=attachment(client,pid,0)
    assert t['kind']=='reference' and t['state']=='succeeded'
    assert pp.profile(pid,'ada')['version']==0 and pp.profile(pid,'ada')['selected_take_id'] is None
    assert client.post(f'/api/projects/{pid}/voice-takes/{t["id"]}/adopt',json={'version':0}).status_code==400
    assert not store.jobs(pid)
    state=client.get(f'/api/projects/{pid}').json()['postproduction']
    assert state['reference_modes']==['timbre','clone'] and state['takes'][0]['audio_url']


def test_validation_scope_noop_and_remove(client,plan):
    pid,p=setup_voice(client,plan);t=attachment(client,pid)
    assert save_ref(client,pid,p,t,'clone',' ').status_code==400
    assert save_ref(client,pid,p,t,'unknown','hello').status_code==422
    other,op=setup_voice(client,plan);ot=attachment(client,other)
    assert save_ref(client,pid,p,ot).status_code==400
    r=save_ref(client,pid,p,t,'clone','Original words.');assert r.status_code==200,r.text;p=r.json()
    assert pp.voice_reference(pid,'ada',p)['text']=='Original words.'
    # Legacy client omits new fields; source and mode remain intact.
    r=client.put(f'/api/projects/{pid}/voices/ada',json={k:p[k] for k in ('version','description','language','sample_text','seed')})
    assert r.status_code==200 and r.json()['reference_take_id']==t['id'];p=r.json()
    r=client.put(f'/api/projects/{pid}/voices/ada',json={**pp.config(p),'version':p['version'],'reference_take_id':None})
    assert r.status_code==200 and 'reference_take_id' not in pp.config(r.json())
    assert pp.audio_path(t).read_bytes()==wav()


@pytest.mark.parametrize('mode',['timbre','clone'])
def test_frozen_reference_runs_and_line_inherits_selected_mode(client,plan,monkeypatch,mode):
    monkeypatch.setattr(pp.POOL,'submit',lambda *a:None)
    pid,p=setup_voice(client,plan);t=attachment(client,pid)
    p=save_ref(client,pid,p,t,mode,'Original reference words.').json()
    r=client.post(f'/api/projects/{pid}/voices/ada/generate',json={'version':p['version']});assert r.status_code==200,r.text
    candidate=r.json();assert candidate['request']['voice_reference']=={'take_id':t['id'],'sha256':t['result']['sha256'],'mode':mode,'text':'Original reference words.'}
    seen=[]
    def synth(request,output,work):
        seen.append(request);output.write_bytes(wav());return {**pp.inspect_wav(wav()),'model':'test-only'}
    monkeypatch.setattr(voxcpm_provider,'synthesize',synth)
    pp.run(candidate['id'],pid)
    assert seen[-1]['reference_path']==str(pp.audio_path(t)) and seen[-1]['reference_mode']==mode
    assert bool(seen[-1]['control'])==(mode=='timbre')
    assert client.post(f'/api/projects/{pid}/voice-takes/{candidate["id"]}/adopt',json={'version':p['version']}).status_code==200
    p=pp.profile(pid,'ada')
    unchanged=save_ref(client,pid,p,t,mode,'Original reference words.').json()
    assert unchanged['selected_take_id']==candidate['id']
    line=client.post(f'/api/projects/{pid}/voice-lines/generate',json={'shot_id':'shot','dialogue_index':0}).json();pp.run(line['id'],pid)
    assert seen[-1]['text']=='Light.' and seen[-1]['reference_path']==str(pp.audio_path(pp.take(pid,candidate['id'])))
    if mode=='clone':assert seen[-1]['reference_mode']=='clone' and seen[-1]['reference_text']==p['sample_text'] and not seen[-1]['control']
    else:assert 'reference_mode' not in seen[-1] and seen[-1]['control']
    z=zipfile.ZipFile(io.BytesIO(client.get(f'/api/projects/{pid}/export').content))
    assert z.read(f'postproduction/reference/ada-{t["id"]}.wav')==wav()
    # Detaching invalidates selected candidate, retaining all bytes.
    r=client.put(f'/api/projects/{pid}/voices/ada',json={**pp.config(unchanged),'version':unchanged['version'],'reference_take_id':None})
    assert r.status_code==200 and r.json()['selected_take_id'] is None
    assert not pp.current(pid,pp.take(pid,candidate['id']))


def test_tamper_fails_before_synthesis(client,plan,monkeypatch):
    monkeypatch.setattr(pp.POOL,'submit',lambda *a:None)
    monkeypatch.setattr(voxcpm_provider,'synthesize',lambda *a:pytest.fail('tampered reference reached model'))
    pid,p=setup_voice(client,plan);t=attachment(client,pid);p=save_ref(client,pid,p,t).json()
    candidate=client.post(f'/api/projects/{pid}/voices/ada/generate',json={'version':p['version']}).json()
    pp.audio_path(t).write_bytes(b'changed');pp.run(candidate['id'],pid)
    assert pp.take(pid,candidate['id'])['state']=='failed'
    assert client.post(f'/api/projects/{pid}/voices/ada/generate',json={'version':p['version']}).status_code==400


def test_worker_actual_parameter_modes():
    spec=importlib.util.spec_from_file_location('voice_reference_worker',Path(__file__).parents[1]/'scripts/voxcpm_worker.py');worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    base={'text':'New words.','seed':42,'control':'warm','reference_path':'/tmp/voice.wav'}
    timbre=worker.generation_args(base)
    assert timbre['reference_wav_path']=='/tmp/voice.wav' and 'prompt_wav_path' not in timbre and timbre['text']=='(warm)New words.'
    clone=worker.generation_args({**base,'reference_mode':'clone','reference_text':'Original words.'})
    assert clone['reference_wav_path']==clone['prompt_wav_path']=='/tmp/voice.wav' and clone['prompt_text']=='Original words.' and clone['text']=='New words.'
    with pytest.raises(ValueError,match='逐字稿'):worker.generation_args({**base,'reference_mode':'clone'})
    with pytest.raises(ValueError):worker.generation_args({**base,'reference_mode':'invalid'})
