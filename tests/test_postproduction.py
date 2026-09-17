import copy,io,math,struct,wave,zipfile
import pytest
from studio import postproduction as pp, store, engine
from test_production import client,plan,create


def wav(seconds=3):
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setparams((1,2,8000,0,'NONE','not compressed'))
        w.writeframes(b''.join(struct.pack('<h',int(1500*math.sin(i*.2))) for i in range(8000*seconds)))
    return out.getvalue()


def setup_voice(client,plan):
    pid=create(client,plan)
    data={'version':0,'description':'Warm, clear adult voice','language':'English','sample_text':'Hello, welcome to my workshop.','seed':42}
    r=client.put(f'/api/projects/{pid}/voices/ada',json=data);assert r.status_code==200,r.text
    return pid,r.json()


def uploaded(client,pid,p):
    r=client.post(f'/api/projects/{pid}/voices/ada/upload',data={'version':p['version']},files={'file':('ref.wav',wav(),'audio/wav')})
    assert r.status_code==200,r.text
    return r.json()


def adopted(client,pid,p):
    t=uploaded(client,pid,p)
    r=client.post(f'/api/projects/{pid}/voice-takes/{t["id"]}/adopt',json={'version':p['version']});assert r.status_code==200,r.text
    return t


def test_profile_persistence_conflict_and_canon_unchanged(client,plan):
    pid,p=setup_voice(client,plan);before=store.project(pid)
    assert pp.profile(pid,'ada')==p
    assert client.put(f'/api/projects/{pid}/voices/ada',json={**pp.config(p),'version':0}).status_code==400
    assert client.put(f'/api/projects/{pid}/voices/room',json={**pp.config(p),'version':0}).status_code==400
    assert store.project(pid)==before and not store.assets(pid) and not store.jobs(pid)
    assert client.get(f'/api/projects/{pid}').json()['postproduction']['profiles']==[p]


def test_uploaded_candidate_explicit_adoption_and_wrong_project(client,plan):
    pid,p=setup_voice(client,plan);t=uploaded(client,pid,p)
    assert pp.profile(pid,'ada')['selected_take_id'] is None
    other=create(client,plan)
    assert client.get(f'/api/projects/{other}/voice-takes/{t["id"]}/audio').status_code==400
    assert client.post(f'/api/projects/{other}/voice-takes/{t["id"]}/adopt',json={'version':1}).status_code==400
    assert client.post(f'/api/projects/{pid}/voice-takes/{t["id"]}/adopt',json={'version':0}).status_code==400
    assert client.post(f'/api/projects/{pid}/voice-takes/{t["id"]}/adopt',json={'version':1}).status_code==200
    assert client.get(f'/api/projects/{pid}/voice-takes/{t["id"]}/audio').content==wav()
    assert pp.profile(pid,'ada')['selected_take_id']==t['id']


def test_profile_edit_invalidates_candidate_preserves_bytes(client,plan):
    pid,p=setup_voice(client,plan);t=adopted(client,pid,p);p=pp.profile(pid,'ada')
    assert client.put(f'/api/projects/{pid}/voices/ada',json={**pp.config(p),'description':'new voice','version':p['version']}).status_code==200
    assert not pp.profile(pid,'ada')['selected_take_id'] and not pp.current(pid,t)
    assert pp.audio_path(t).read_bytes()==wav()
    assert client.post(f'/api/projects/{pid}/voice-takes/{t["id"]}/adopt',json={'version':3}).status_code==400


def test_voice_line_freezes_exact_dialogue_ref_and_detects_changes(client,plan,monkeypatch):
    monkeypatch.setattr(pp.POOL,'submit',lambda *a:None)
    pid,p=setup_voice(client,plan)
    assert client.post(f'/api/projects/{pid}/voice-lines/generate',json={'shot_id':'shot','dialogue_index':0}).status_code==400
    ref=adopted(client,pid,p)
    r=client.post(f'/api/projects/{pid}/voice-lines/generate',json={'shot_id':'shot','dialogue_index':0});assert r.status_code==200,r.text
    t=r.json();assert t['request']['text']=='Light.' and t['request']['source']['voice_take_id']==ref['id']
    duplicate=client.post(f'/api/projects/{pid}/voice-lines/generate',json={'shot_id':'shot','dialogue_index':0}).json();assert duplicate['id']==t['id']
    new=copy.deepcopy(plan);new['shots'][0]['dialogue'][0]['text']='A different line.';engine.save_plan(pid,new,1,'change')
    assert not pp.current(pid,t)


def test_real_adapter_boundary_and_export_selection(client,plan,monkeypatch):
    from studio import voxcpm_provider
    monkeypatch.setattr(pp.POOL,'submit',lambda *a:None)
    pid,p=setup_voice(client,plan);ref=adopted(client,pid,p)
    def fake(request,output,work):
        assert request['text']=='Light.' and request['reference_path']==str(pp.audio_path(ref))
        output.write_bytes(wav());return {**pp.inspect_wav(wav()),'model':'test-only'}
    monkeypatch.setattr(voxcpm_provider,'synthesize',fake)
    t=client.post(f'/api/projects/{pid}/voice-lines/generate',json={'shot_id':'shot','dialogue_index':0}).json();pp.run(t['id'],pid)
    done=pp.take(pid,t['id']);assert done['state']=='succeeded' and done['result']['overrun']
    r=client.post(f'/api/projects/{pid}/voice-takes/{t["id"]}/adopt',json={'version':2});assert r.status_code==200,r.text
    z=zipfile.ZipFile(io.BytesIO(client.get(f'/api/projects/{pid}/export').content))
    assert any(n.startswith('postproduction/line/') and n.endswith('.wav') for n in z.namelist())
    assert any(n.startswith('postproduction/voice/') and n.endswith('.wav') for n in z.namelist())
    new=copy.deepcopy(plan);new['shots'][0]['dialogue'][0]['start']=2;engine.save_plan(pid,new,1,'timing')
    z=zipfile.ZipFile(io.BytesIO(client.get(f'/api/projects/{pid}/export').content));assert not any(n.startswith('postproduction/line/') and n.endswith('.wav') for n in z.namelist())


def test_generation_failure_is_visible_and_restart_does_not_retry(client,plan,monkeypatch):
    from studio import voxcpm_provider
    monkeypatch.setattr(pp.POOL,'submit',lambda *a:None)
    pid,p=setup_voice(client,plan)
    t=client.post(f'/api/projects/{pid}/voices/ada/generate',json={'version':1}).json()
    monkeypatch.setattr(voxcpm_provider,'synthesize',lambda *a:(_ for _ in ()).throw(RuntimeError('GPU busy')))
    pp.run(t['id'],pid);assert pp.take(pid,t['id'])['state']=='failed' and 'GPU busy' in pp.take(pid,t['id'])['error']
    t2=client.post(f'/api/projects/{pid}/voices/ada/generate',json={'version':1}).json();pp.init()
    assert pp.take(pid,t2['id'])['state']=='interrupted'


def test_audio_validation_tamper_and_symlink(client,plan):
    pid,p=setup_voice(client,plan)
    for content in [b'bad',wav(1)]:
        assert client.post(f'/api/projects/{pid}/voices/ada/upload',data={'version':1},files={'file':('x.wav',content)}).status_code==400
    t=uploaded(client,pid,p);path=pp.audio_path(t);path.write_bytes(b'changed')
    assert client.get(f'/api/projects/{pid}/voice-takes/{t["id"]}/audio').status_code==400
    path.unlink();elsewhere=store.DATA/'outside.wav';elsewhere.write_bytes(wav());path.symlink_to(elsewhere)
    assert client.get(f'/api/projects/{pid}/voice-takes/{t["id"]}/audio').status_code==400


def test_explicit_silent_mouthing_cannot_be_synthesized(client,plan,monkeypatch):
    monkeypatch.setattr(pp.POOL,'submit',lambda *a:None)
    plan['shots'][0]['dialogue'][0]['delivery']='只有口形，無聲'
    pid,p=setup_voice(client,plan);adopted(client,pid,p)
    r=client.post(f'/api/projects/{pid}/voice-lines/generate',json={'shot_id':'shot','dialogue_index':0})
    assert r.status_code==400 and '無聲口形' in r.text
    assert client.get(f'/api/projects/{pid}').json()['postproduction']['silent_lines']==['shot:0']
