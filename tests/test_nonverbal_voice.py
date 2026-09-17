import io,struct,wave,zipfile
from studio import engine,postproduction as pp,store,voice_defaults as vd,models
from test_production import client,plan,create

DESCRIPTION='小型維修機械人的非語言電子音；以短促 beep／boop、高低音與停頓表達，不含人聲或可辨識字詞。'


def effect():
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setparams((1,2,8000,0,'NONE','not compressed'))
        w.writeframes(b''.join(struct.pack('<h',800 if i%20<10 else -800) for i in range(1600)))
    return out.getvalue()


def save(client,pid,version=0,**extra):
    return client.put(f'/api/projects/{pid}/voices/ada',json={'version':version,'sound_mode':'nonverbal','description':DESCRIPTION,**extra})


def test_nonverbal_no_language_and_no_tts_jobs(client,plan,monkeypatch):
    monkeypatch.setattr(pp.POOL,'submit',lambda *a:(_ for _ in ()).throw(AssertionError('must not enqueue TTS')))
    pid=create(client,plan);before=store.project(pid)
    r=save(client,pid,language='英文',sample_text='beep boop');assert r.status_code==200,r.text
    p=r.json();assert p['sound_mode']=='nonverbal' and p['language']==p['sample_text']==''
    assert pp.config(p)['sound_mode']=='nonverbal'
    assert client.post(f'/api/projects/{pid}/voices/ada/generate',json={'version':1}).status_code==400
    assert client.post(f'/api/projects/{pid}/voice-lines/generate',json={'shot_id':'shot','dialogue_index':0}).status_code==400
    assert not store.jobs(pid) and store.project(pid)==before
    with store.db() as c:assert not c.execute('SELECT id FROM voice_takes').fetchall()
    # An older client omitting the new field cannot turn an effect into speech.
    r=client.put(f'/api/projects/{pid}/voices/ada',json={'version':1,'description':DESCRIPTION,'language':'English','sample_text':'beep boop'})
    assert r.json()['sound_mode']=='nonverbal' and r.json()['sample_text']==''
    assert save(client,pid,2,reference_take_id='missing',reference_mode='clone',reference_text='beep').status_code==400


def test_short_effect_import_adopt_export_and_mode_change(client,plan):
    pid=create(client,plan);p=save(client,pid).json();raw=effect()
    r=client.post(f'/api/projects/{pid}/voices/ada/upload',data={'version':p['version']},files={'file':('robot.wav',raw,'audio/wav')})
    assert r.status_code==200,r.text
    t=r.json();assert t['request']['provider']=='uploaded' and t['request']['config']['sound_mode']=='nonverbal'
    assert pp.audio_path(t).read_bytes()==raw
    assert client.post(f'/api/projects/{pid}/voice-takes/{t["id"]}/adopt',json={'version':1}).status_code==200
    assert pp.profile(pid,'ada')['selected_take_id']==t['id']
    z=io.BytesIO()
    with zipfile.ZipFile(z,'w') as archive:pp.add_export(archive,{'id':pid,'postproduction':pp.state(store.project(pid))})
    with zipfile.ZipFile(z) as archive:assert archive.read(f'postproduction/voice/ada-{t["id"]}.wav')==raw
    p=pp.profile(pid,'ada')
    # Speech has meaningful required dialogue fields and a different configuration.
    assert client.put(f'/api/projects/{pid}/voices/ada',json={**pp.config(p),'version':p['version'],'sound_mode':'speech'}).status_code==400
    r=client.put(f'/api/projects/{pid}/voices/ada',json={**pp.config(p),'version':p['version'],'sound_mode':'speech','language':'英文','sample_text':'Hello'})
    assert r.status_code==200 and r.json()['selected_take_id'] is None and not pp.current(pid,t)
    assert pp.audio_path(t).read_bytes()==raw
    assert client.post(f'/api/projects/{pid}/voices/ada/upload',data={'version':r.json()['version']},files={'file':('short.wav',raw,'audio/wav')}).status_code==400


def test_unsaved_effect_attachment_and_clone_rejection(client,plan):
    pid=create(client,plan)
    r=client.post(f'/api/projects/{pid}/voices/ada/upload',data={'version':0,'attachment':'true','reference_sound_mode':'nonverbal'},files={'file':('short.wav',effect(),'audio/wav')})
    assert r.status_code==200,r.text
    tid=r.json()['id'];assert pp.profile(pid,'ada')['version']==0
    assert save(client,pid,reference_take_id=tid,reference_mode='clone',reference_text='beep').status_code==400
    assert save(client,pid,reference_take_id=tid,reference_mode='timbre').status_code==200


def test_nonverbal_semantic_proposal(client,plan,monkeypatch):
    monkeypatch.setattr(engine.POOL,'submit',lambda *a:None)
    pid=create(client,plan);p=store.project(pid)
    req=models.JobRequest(capability='voice_defaults',target_id='ada')
    data=vd.build(p,req)
    assert 'speech (spoken language) or nonverbal' in data['prompt'] and 'not words for a TTS narrator' in data['prompt']
    job=engine.enqueue(pid,req)['job']
    result={'character_id':'ada','sound_mode':'nonverbal','description':DESCRIPTION,'rationale':'角色以電子音表達，此處保存非語言聲音設計，不增加分鏡對白。','evidence':[p['production']['canon'][0]['description']]}
    engine.finish(job,result)
    assert pp.profile(pid,'ada')['default_voice']['sound_mode']=='nonverbal'
