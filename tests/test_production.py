import copy,json,io,zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from studio import store,models,continuity,engine,providers,h3,skills
from studio.app import app

@pytest.fixture
def plan():
    data={'title':'Test','logline':'A keeper turns on a light.','story':'Ada fixes a lamp.','screenplay':'ADA: Light.','style':'Stop-motion',
    'canon':[{'id':'ada','kind':'character','name':'Ada','description':'Black bob and yellow coat','facts':['Three coat buttons']},{'id':'room','kind':'location','name':'Workshop','description':'Round window behind a wooden bench','facts':['Window at rear']}],
    'scenes':[{'id':'scene','title':'Workshop','location_id':'room','time_of_day':'Night','summary':'Light the lamp'}],
    'shots':[{'id':'shot','scene_id':'scene','title':'The switch','duration':6,'entity_ids':['ada'],'framing':'Medium','angle':'Eye-level','camera':'Slow 10cm push','blocking':'Ada left','action':'Press switch','expression':'Surprised','start_state':[{'entity_id':'ada','key':'hand','value':'lowered'}],'end_state':[{'entity_id':'ada','key':'hand','value':'raised'}],'transition_note':'','beats':[{'start':0,'end':6,'action':'Raise hand and press switch'}],'dialogue':[{'entity_id':'ada','text':'Light.','language':'English','start':3,'end':4,'delivery':'quietly'}],'keyframes':[{'id':'start','moment':'start','description':'Ada hand lowered'},{'id':'end','moment':'end','description':'Ada hand raised'}],'soundscape':'Wind and a switch click.','music':'N/A'}]}

    return models.Production.model_validate(data).model_dump()

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path)
    # Unit/API fixtures never dispatch external providers in background threads.
    monkeypatch.setattr(engine.POOL,'submit',lambda *args:None)
    from studio import comfy_recovery
    monkeypatch.setattr(comfy_recovery,'start',lambda:None)  # Real watchdog has separate isolated tests.
    with TestClient(app) as c: yield c

def create(client,plan):
    p=client.post('/api/projects',json={'title':'Test','idea':'A keeper fixes a lamp'}).json()
    assert client.put(f'/api/projects/{p["id"]}/plan',json={'revision':0,'production':plan}).status_code==200
    return p['id']

def add_asset(pid,plan,target,refs=None,status='approved'):
    from PIL import Image
    aid=store.uid();path=store.DATA/'assets'/pid/(aid+'.png');path.parent.mkdir(parents=True,exist_ok=True);Image.new('RGB',(256,256),'orange').save(path)
    with store.db() as c: c.execute('INSERT INTO assets(id,project_id,target_id,kind,path,status,dependency_hash,reference_ids,prompt,provider,created) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(aid,pid,target,'entity' if target in ['ada','room'] else 'frame',str(path.relative_to(store.DATA)),status,continuity.target_hash(plan,target),store.encode(refs or []),'Test-only image','test',store.now()))
    return aid

def test_relationship_and_timing_rejection(plan):
    models.Production.model_validate(plan)
    for field,value in [('duration',20),('scene_id','missing'),('entity_ids',['missing'])]:
        p=copy.deepcopy(plan);p['shots'][0][field]=value
        with pytest.raises(ValueError):models.Production.model_validate(p)
    p=copy.deepcopy(plan);p['shots'][0]['dialogue'][0]['end']=9
    with pytest.raises(ValueError):models.Production.model_validate(p)

def test_optimistic_revision_and_restore(client,plan):
    pid=create(client,plan);changed=copy.deepcopy(plan);changed['title']='Changed'
    assert client.put(f'/api/projects/{pid}/plan',json={'revision':0,'production':changed}).status_code==400
    assert client.put(f'/api/projects/{pid}/plan',json={'revision':1,'production':changed}).status_code==200
    r=client.post(f'/api/projects/{pid}/restore/1',json={'revision':2});assert r.status_code==200
    assert r.json()['title']=='Test' and r.json()['revision']==3

def test_references_required_and_automatic_reuse(client,plan):
    pid=create(client,plan)
    r=client.post(f'/api/projects/{pid}/jobs',json={'capability':'image','target_id':'start'});assert r.status_code==400 and 'Approve canonical' in r.text
    ada=add_asset(pid,plan,'ada');room=add_asset(pid,plan,'room')
    refs,missing=continuity.references(plan,store.assets(pid),'start');assert not missing and {a['id'] for a in refs}=={ada,room}
    r=client.post(f'/api/projects/{pid}/jobs',json={'capability':'image','target_id':'ada'});assert r.json()['reused_asset']['id']==ada
    assert not store.jobs(pid)

def test_canon_change_invalidates_dependencies(client,plan):
    pid=create(client,plan);add_asset(pid,plan,'ada');add_asset(pid,plan,'room');add_asset(pid,plan,'start',status='pending')
    p=copy.deepcopy(plan);p['canon'][0]['facts']=['Four buttons']
    engine.save_plan(pid,p,1,'Changed costume')
    result={a['target_id']:a['status'] for a in store.assets(pid)}
    assert result=={'ada':'stale','room':'approved','start':'stale'}

def test_reference_replacement_invalidates_pending_and_approved(client,plan):
    pid=create(client,plan);old=add_asset(pid,plan,'ada');room=add_asset(pid,plan,'room');start=add_asset(pid,plan,'start',[old,room]);end=add_asset(pid,plan,'end',[old,room,start],status='pending');new=add_asset(pid,plan,'ada',status='pending')
    with store.db() as c:c.execute('UPDATE assets SET review=? WHERE id=?',(store.encode({'verdict':'pass','summary':'Test-only four-view review','issues':[],'character_sheet':'pass'}),new))
    engine.decide_asset(new,'approved','')
    result={a['id']:a['status'] for a in store.assets(pid)}
    assert result[old]=='superseded' and result[start]=='stale' and result[end]=='stale'
    with pytest.raises(ValueError,match='reference'):engine.decide_asset(end,'approved','override')

def test_rejected_reference_cannot_approve_dependent(client,plan):
    pid=create(client,plan);ada=add_asset(pid,plan,'ada');room=add_asset(pid,plan,'room');a=add_asset(pid,plan,'start',[ada,room],status='pending')
    engine.decide_asset(ada,'rejected','bad');
    with pytest.raises(ValueError,match='reference'):engine.decide_asset(a,'approved','')

def test_h3_anchors_and_verbatim_dialogue(client,plan):
    pid=create(client,plan);s=plan['shots'][0]
    assert h3.compile_shot(plan,s,[])['mode']=='T2VA'
    first=add_asset(pid,plan,'start');h=h3.compile_shot(plan,s,store.assets(pid));assert h['mode']=='I2VA';assert '<d>[English] Light.</d>' in h['text']
    last=add_asset(pid,plan,'end');h=h3.compile_shot(plan,s,store.assets(pid));assert h['mode']=='FL2VA';assert '6.00-second mark' in h['text'];assert [r['asset_id'] for r in h['references']]==[first,last]
    assert h['text'].index('integrated_multimodal_description:')<h['text'].index('overall_soundscape:')<h['text'].index('non_diegetic_music:')

def test_manual_provider_is_real_replaceable_capability(client,plan):
    pid=create(client,plan)
    client.post('/api/settings/routing',json={'capability':'qc','provider_id':'manual'})
    j=client.post(f'/api/projects/{pid}/jobs',json={'capability':'qc'}).json()['job'];assert j['state']=='awaiting_input'
    r=client.post('/api/jobs/'+j['id']+'/manual',json={'verdict':'pass','summary':'Reviewed timing and continuity.','issues':[]});assert r.status_code==200 and r.json()['state']=='succeeded'
    assert providers.resolve('narrative')['id']=='astra'

def test_export_contains_real_files_and_reference_order(client,plan):
    pid=create(client,plan);ada=add_asset(pid,plan,'ada');first=add_asset(pid,plan,'start',[ada]);add_asset(pid,plan,'end',[first],status='rejected')
    r=client.get(f'/api/projects/{pid}/export');assert r.status_code==200
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        names=z.namelist();assert 'production.json' in names and 'h3/drafts/shot.txt' in names
        assert len([n for n in names if n.endswith('.png')])==2
        h=json.loads(z.read('h3/shot.json'));assert h['references'][0]['path'] in names

def test_origin_guard_and_unknown_asset(client):
    assert client.post('/api/projects',headers={'Origin':'https://untrusted.example'},json={'title':'x','idea':'abc'}).status_code==403
    assert client.get('/api/assets/missing/image').status_code==400

def test_restart_marks_uncertain_jobs(client,plan):
    pid=create(client,plan)
    with store.db() as c:c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',('interrupted-test',pid,'image','ada','running','astra','{}',store.now(),store.now()))
    store.init();assert store.job('interrupted-test')['state']=='interrupted';assert store.project(pid)['production']==plan

def test_stale_proposal_cannot_overwrite(client,plan):
    pid=create(client,plan)
    with store.db() as c:c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,result,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',('proposal',pid,'narrative','','succeeded','astra',store.encode({'revision':0}),store.encode(plan),store.now(),store.now()))
    assert client.post('/api/jobs/proposal/adopt',json={'revision':1}).status_code==400

def test_skill_installed_ids_roundtrip_and_tamper(tmp_path):
    src=tmp_path/'source';src.mkdir();(src/'SKILL.md').write_text('---\nname: custom\ndescription: custom production instructions\n---\nMake a continuity checklist.')
    (src/'studio.json').write_text(json.dumps({'id':'custom','version':'1.0.0','capabilities':['checklist']}))
    root=str(tmp_path/'installed');s=skills.install(str(src),root)
    assert skills.list_installed(root)[0]['id']==s['id']
    skills.set_enabled(root,s['id'],True,['project:read']);text,meta=skills.instructions(root,'checklist');assert 'checklist' in text
    (Path(s['skill_dir'])/'SKILL.md').write_text('---\nname: altered\ndescription: changed\n---\nTampered')
    with pytest.raises(ValueError,match='integrity'):skills.instructions(root,'checklist')
    (src/'studio.json').write_text(json.dumps({'id':'custom','version':'../../escape'}))
    with pytest.raises(ValueError,match='version'):skills.install(str(src),root)

def test_explicit_edit_source_is_not_canonical_reference(client,plan):
    pid=create(client,plan);candidate=add_asset(pid,plan,'ada',status='pending')
    req=models.JobRequest(capability='image',target_id='ada',force=True,source_asset_id=candidate,feedback='Move pin')
    inp,reuse=engine.build_input(store.project(pid),req)
    assert inp['source_asset_id']==candidate and inp['reference_ids']==[]
    assert len(inp['images'])==1 and 'EDIT TARGET' in inp['prompt']
    other=add_asset(pid,plan,'room',status='pending')
    with pytest.raises(ValueError,match='Edit source'):engine.build_input(store.project(pid),req.model_copy(update={'source_asset_id':other}))

def test_reject_approved_reference_invalidates_existing_frame(client,plan):
    pid=create(client,plan);ada=add_asset(pid,plan,'ada');frame=add_asset(pid,plan,'start',[ada]);engine.decide_asset(ada,'rejected','Wrong identity')
    assert next(a for a in store.assets(pid) if a['id']==frame)['status']=='stale'

def test_saved_result_recovery_without_provider_call(client,plan):
    pid=create(client,plan);jid='recoverable';work=store.DATA/'jobs'/jid;work.mkdir(parents=True)
    (work/'result.json').write_text(json.dumps({'verdict':'pass','summary':'Saved result','issues':[]}))
    with store.db() as c:c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',(jid,pid,'qc','','interrupted','manual','{}',store.now(),store.now()))
    r=client.post('/api/jobs/'+jid+'/recover',json={});assert r.status_code==200 and r.json()['state']=='succeeded'
    assert client.post('/api/jobs/'+jid+'/recover',json={}).status_code==400

def test_switch_away_from_manual_does_not_block_new_provider(client,plan,monkeypatch):
    pid=create(client,plan)
    client.post('/api/settings/routing',json={'capability':'qc','provider_id':'manual'})
    first=client.post(f'/api/projects/{pid}/jobs',json={'capability':'qc'}).json()['job']
    client.post('/api/settings/routing',json={'capability':'qc','provider_id':'astra'})
    monkeypatch.setattr(engine.POOL,'submit',lambda *args:None)
    second=client.post(f'/api/projects/{pid}/jobs',json={'capability':'qc'}).json()['job']
    assert second['provider']=='astra' and first['id']!=second['id']
    assert store.job(first['id'])['state']=='cancelled'
    assert client.post('/api/jobs/'+second['id']+'/cancel',json={}).status_code==200
    engine.execute(second['id']);assert store.job(second['id'])['state']=='cancelled'
