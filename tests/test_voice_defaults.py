import copy
import pytest
from studio import engine, models, postproduction as pp, providers, store, voice_defaults as vd
from test_production import client, plan, create


def robot(plan):
    plan['canon'][0].update(description='A small cream-painted maintenance robot with one teal lens.', facts=['Pip communicates with a single lens and precise gestures.'])
    return plan


def proposal(cid='ada'):
    return dict(character_id=cid, sound_mode='speech', description='小型維修機械人的中性合成聲線，輕微金屬共鳴；咬字準確，短句停頓俐落。', rationale='維修機械人的工作導向與小型機體形成這套聲音設計。', evidence=['maintenance robot'])


def prepare(client, pid, **extra):
    return client.post(f'/api/projects/{pid}/voices/ada/default', json={'version':0, **extra})


def test_semantic_source_routing_cached_design_and_save(client, plan, monkeypatch):
    monkeypatch.setattr(engine.POOL, 'submit', lambda *a: None)
    store.put_setting('default_provider', 'deepseek')
    pid=create(client, robot(plan));before=store.project(pid)
    response=prepare(client,pid);assert response.status_code==200,response.text
    job=response.json()['job']
    assert job['provider']=='deepseek' and job['capability']=='voice_defaults'
    assert job['input']['voice_default_source']['character']==store.project(pid)['production']['canon'][0]
    assert job['input']['voice_default_source']['performance_context']==store.project(pid)['production']['shots']
    assert 'maintenance robot' in job['input']['prompt'] and 'synthetic texture' in job['input']['prompt']
    assert providers.result_model('voice_defaults')==vd.VoiceDefault
    assert prepare(client,pid).json()['job']['id']==job['id']
    engine.finish(job,proposal())
    v=client.get(f'/api/projects/{pid}/voices/ada/default').json()['profile']
    assert v['version']==0 and v['description']=='' and v['default_voice']['description']==proposal()['description']
    assert v['default_voice']['job_id']==job['id']
    assert 'job' not in prepare(client,pid).json() and len(store.jobs(pid))==1
    assert store.project(pid)==before
    with store.db() as c:assert c.execute('SELECT count(*) FROM voice_takes').fetchone()[0]==0
    saved=client.put(f'/api/projects/{pid}/voices/ada',json={**pp.config(v),'description':v['default_voice']['description'],'version':0}).json()
    assert saved['version']==1 and saved['description']==proposal()['description']
    assert saved['selected_take_id'] is None
    assert prepare(client,pid).status_code==400


def test_stale_proposal_never_reused_and_existing_voice_never_overwritten(client, plan, monkeypatch):
    monkeypatch.setattr(engine.POOL,'submit',lambda *a:None)
    pid=create(client,robot(plan));job=prepare(client,pid).json()['job'];engine.finish(job,proposal())
    changed=copy.deepcopy(store.project(pid)['production']);changed['canon'][0]['description']='An ancient dragon with a quiet presence.'
    engine.save_plan(pid,changed,1,'role correction')
    assert 'default_voice' not in pp.profile(pid,'ada')
    v=pp.profile(pid,'ada')
    saved=client.put(f'/api/projects/{pid}/voices/ada',json={**pp.config(v),'description':'使用者指定的氣聲，保留既有的聲音身份。','version':0}).json()
    r=client.post(f'/api/projects/{pid}/voices/ada/default',json={'version':1}).json()
    assert r=={'profile':saved} and len(store.jobs(pid))==1


def test_no_fabricated_fallback_explicit_retry_and_source_validation(client, plan, monkeypatch):
    monkeypatch.setattr(engine.POOL,'submit',lambda *a:None)
    pid=create(client,robot(plan));job=prepare(client,pid).json()['job']
    with pytest.raises(ValueError,match='角色不符'):engine.finish(job,proposal('someone_else'))
    with pytest.raises(ValueError,match='原始設定'):engine.finish(job,{**proposal(),'evidence':['A young woman']})
    with store.db() as c:c.execute("UPDATE jobs SET state='failed',error='Service unavailable' WHERE id=?",(job['id'],))
    assert pp.profile(pid,'ada')['description']=='' and 'default_voice' not in pp.profile(pid,'ada')
    assert prepare(client,pid).json()['job']['id']==job['id']
    assert prepare(client,pid,retry=True).json()['job']['id']!=job['id']
    assert client.post(f'/api/projects/{pid}/voices/room/default',json={'version':0}).status_code==400


def test_pending_other_context_conflict(client,plan,monkeypatch):
    monkeypatch.setattr(engine.POOL,'submit',lambda *a:None)
    pid=create(client,robot(plan));prepare(client,pid)
    changed=copy.deepcopy(store.project(pid)['production']);changed['canon'][0]['facts'].append('Voice is deep and resonant.')
    engine.save_plan(pid,changed,1,'new voice fact')
    assert prepare(client,pid).status_code==400


def test_one_grounding_correction_same_provider(tmp_path,monkeypatch):
    calls=[]
    provider={'id':'chosen'}
    def run(p,cap,prompt,images,work):
        calls.append((p,cap,work));work.mkdir(exist_ok=True)
        result=proposal() if len(calls)>1 else {**proposal(),'evidence':['Invented quote']}
        (work/'result.json').write_text(store.encode(result))
        return result
    monkeypatch.setattr(providers,'run',run)
    context={'character':{'id':'ada','description':'A maintenance robot','facts':[]}}
    result=vd.run(provider,'design',tmp_path,context)
    assert result==proposal() and len(calls)==2
    assert all(p==provider and cap=='voice_defaults' for p,cap,_ in calls)
    assert calls[1][2]==tmp_path/'correction'
