import copy
import json
from pathlib import Path
import pytest
from studio import shot_state, models, store, engine, providers, frame_moments
from test_production import client

REAL_PREPARE = shot_state.prepare_plan
pytestmark = pytest.mark.canonical_state


@pytest.fixture
def legacy():
    return models.Production.model_validate(json.loads((Path(__file__).parent/'fixtures/canonical_pip_legacy.json').read_text())).model_dump()


def track(plan):
    shot=plan['shots'][0]
    moments=[]
    for time in (0,2.5,4.5,4.8,6.2,7.8,8):
        facts=[('char_pip','gaze_target','char_ada' if time<=6.2 else 'prop_lantern.switch'),
            ('char_pip','pose','arms lowered'),('char_pip','position','on bench right'),
            ('char_pip','held_props','none'),('char_pip','badge','tilted clockwise'),
            ('char_ada','position','behind bench left'),('char_ada','gaze_target','prop_lantern'),
            ('char_ada','pose','fingertips on handle' if time<4.5 else 'hands resting on bench'),
            ('prop_lantern','position','upright at workbench center'),('prop_lantern','power','off')]
        moments.append({'time':time,'state':[{'entity_id':e,'key':k,'value':v} for e,k,v in facts]})
    return {'version':shot_state.VERSION,'moments':moments,
        'transitions':[{'start':2.5,'end':4.5,'changes':[{'entity_id':'char_ada','key':'pose','before':'fingertips on handle','after':'hands resting on bench'}]},
            {'start':6.2,'end':8,'changes':[{'entity_id':'char_pip','key':'gaze_target','before':'char_ada','after':'prop_lantern.switch'}]}],
        'compositions':[{'frame_id':f['id'],'text':'Low locked two-shot; toggle large in the lower-right foreground, hard black-on-brass contrast from the rear-left sconce.'} for f in shot['keyframes']]}


@pytest.fixture
def gate(client,monkeypatch,legacy):
    monkeypatch.setattr(shot_state,'prepare_plan',REAL_PREPARE)
    calls=[]
    def call(provider,cap,prompt,work):
        calls.append(cap)
        if cap=='shot_state_prepare':
            return {'canonical_state':track(legacy),'reconciliations':['Legacy opening prose aimed at base; exact opening and timeline require Ada.'],'conflicts':[]}
        return {'verdict':'pass','summary':'Test-only independent semantic checker','issues':[]}
    monkeypatch.setattr(shot_state,'_call',call)
    return calls


def test_pip_compiler_and_i2va_single_source(legacy):
    original=copy.deepcopy(legacy)
    s=shot_state.compile_shot({**legacy['shots'][0],'canonical_state':track(legacy)})
    opening=s['keyframes'][0]['description']
    assert 'char_pip.gaze_target: char_ada' in opening
    assert 'teal lens aimed at the lantern' not in opening
    assert shot_state.fact_map(shot_state.states_at(s,6.2))['char_pip','gaze_target']=='char_ada'
    assert shot_state.fact_map(shot_state.states_at(s,7.8))['char_pip','gaze_target']=='prop_lantern.switch'
    assert s['beats']==legacy['shots'][0]['beats']
    assert s['duration']==8 and len(legacy['shots'])==1
    p={**legacy,'shots':[s]}
    assert frame_moments.build(p,'frame_01_start')['states']==s['start_state']
    from studio import storyboard_board
    src={'scene':p['scenes'][0],'shots':[s],'edits':p['edit_plan'],'image_policy':storyboard_board.IMAGE_POLICIES[0]}
    result={'scene_id':src['scene']['id'],'summary':'I2VA','panels':[{'edit_id':src['edits'][0]['id'],'reason':'continuous',
        'anchors':[{'time':0,'reuse_frame_id':'frame_01_start','description':opening,'state':s['start_state'],'purpose':'source opening'}],
        'image_plan':{'mode':'I2VA','reason':'one continuous locked shot','evidence':[s['camera']], 'unresolved_constraints':[],'reference_demands':[]},'planning_notes':['ordinary gaze transition']} ]}
    shots,panels=storyboard_board.materialize(result,src,'test')
    assert len(shots)==1 and len(panels[0]['anchors'])==1
    compact=copy.deepcopy(result)
    compact['panels'][0]['anchors'][0].update(description='',state=[])
    assert storyboard_board.materialize(compact,src,'test')==(shots,panels)
    compact['panels'][0]['anchors'][0]['purpose']='Wrong independently authored gaze and pose'
    assert storyboard_board.materialize(compact,src,'test')==(shots,panels)
    assert panels[0]['anchors'][0]['purpose']=='來源首幀：固定 0 秒嘅構圖與狀態。'
    assert legacy==original


@pytest.mark.parametrize('mutation', ['duplicate','missing_moment','missing_fact','unknown_entity','early_change','transition_boundary','overlap'])
def test_deterministic_track_guards(legacy,mutation):
    s=copy.deepcopy(legacy['shots'][0]);s['canonical_state']=track(legacy);c=s['canonical_state']
    if mutation=='duplicate':c['moments'][0]['state'].append(c['moments'][0]['state'][0])
    if mutation=='missing_moment':c['moments']=[m for m in c['moments'] if m['time']!=4.8]
    if mutation=='missing_fact':c['moments'][1]['state'].pop()
    if mutation=='unknown_entity':
        for m in c['moments']:m['state'][0]['entity_id']='alien'
    if mutation=='early_change':c['moments'][1]['state'][0]['value']='prop_lantern.switch'
    if mutation=='transition_boundary':c['transitions'][1]['changes'][0]['before']='lamp'
    if mutation=='overlap':c['transitions'].append(copy.deepcopy(c['transitions'][1]))
    with pytest.raises(ValueError):shot_state.compile_shot(s,{'char_ada','char_pip','prop_lantern','loc_workshop'})


def test_formal_save_compiles_before_insert_and_reuses_receipt(client,gate,legacy):
    pid=client.post('/api/projects',json={'title':'Test','idea':'A lamp diagnosis'}).json()['id']
    saved=engine.save_plan(pid,legacy,0,'test migration')
    assert gate==['shot_state_prepare','qc']
    s=saved['production']['shots'][0]
    assert s['start_state']==shot_state.states_at(s,0)
    assert 'char_pip.gaze_target: char_ada' in s['keyframes'][0]['description']
    again=engine.save_plan(pid,saved['production'],1,'unrelated save')
    assert gate==['shot_state_prepare','qc'] and again['revision']==2
    with store.db() as c:
        persisted=json.loads(c.execute('SELECT production FROM revisions WHERE project_id=? AND number=1',(pid,)).fetchone()[0])
    shot_state.assert_compiled(persisted)


@pytest.mark.parametrize('field', ['description','state','drop_authority'])
def test_prose_only_revision_cannot_bypass_authority(client,gate,legacy,field):
    pid=client.post('/api/projects',json={'title':'Test','idea':'A lamp diagnosis'}).json()['id']
    saved=engine.save_plan(pid,legacy,0,'test')['production'];changed=copy.deepcopy(saved)
    if field=='description':changed['shots'][0]['keyframes'][0]['description']='Pip looks at the lamp'
    if field=='state':changed['shots'][0]['start_state'][0]['value']='lamp'
    if field=='drop_authority':changed['shots'][0].pop('canonical_state')
    with pytest.raises(ValueError):engine.save_plan(pid,changed,1,'bad edit')
    assert store.project(pid)['revision']==1


def test_canonical_revision_recompiles_all_affected_frames(client,gate,legacy):
    pid=client.post('/api/projects',json={'title':'Test','idea':'A lamp diagnosis'}).json()['id']
    saved=engine.save_plan(pid,legacy,0,'test')['production'];changed=copy.deepcopy(saved)
    for m in changed['shots'][0]['canonical_state']['moments']:
        next(f for f in m['state'] if f['entity_id']=='char_pip' and f['key']=='position')['value']='on a stool at screen right'
    new=engine.save_plan(pid,changed,1,'canonical position edit')['production']
    assert all('on a stool at screen right' in f['description'] for f in new['shots'][0]['keyframes'])
    assert gate==['shot_state_prepare','qc','qc']


@pytest.mark.parametrize('verdict', ['revise','uncertain'])
def test_semantic_rejection_prevents_all_transaction_writes(client,gate,legacy,monkeypatch,verdict):
    original=shot_state._call
    def call(p,c,prompt,w):
        if c=='qc':return {'verdict':verdict,'summary':'Pose/prop/timing contradiction','issues':['0s possession disagrees with beat']}
        return original(p,c,prompt,w)
    monkeypatch.setattr(shot_state,'_call',call)
    pid=client.post('/api/projects',json={'title':'Test','idea':'A lamp diagnosis'}).json()['id']
    with pytest.raises(ValueError,match='before commit'):
        engine.save_plan(pid,legacy,0,'must fail',setting_updates={'sentinel':{'bad':True}})
    assert store.project(pid)['revision']==0 and store.project(pid)['production'] is None
    assert store.setting('sentinel') is None
    with store.db() as c:assert c.execute('SELECT count(*) FROM revisions WHERE project_id=?',(pid,)).fetchone()[0]==0


def test_failed_attempt_does_not_repeat_provider(client,gate,legacy,monkeypatch):
    def broken(*args):raise RuntimeError('provider failure')
    monkeypatch.setattr(shot_state,'_call',broken)
    work=store.DATA/'one-frozen-attempt'
    with pytest.raises(RuntimeError):REAL_PREPARE(legacy,work=work)
    monkeypatch.setattr(shot_state,'_call',lambda *args:pytest.fail('must not retry'))
    with pytest.raises(ValueError,match='attempted'):REAL_PREPARE(legacy,work=work)


def test_unspecified_detail_is_not_a_physical_state_or_conflict(legacy):
    s=copy.deepcopy(legacy['shots'][0]);s['canonical_state']=track(legacy)
    for m in s['canonical_state']['moments']:
        m['state'].append({'entity_id':'char_ada','key':'expression','value':'mouth open in diagnosis' if m['time']==4.8 else None})
    out=shot_state.compile_shot(s)
    assert 'expression' not in out['keyframes'][0]['description']
    middle=next(f for f in out['keyframes'] if f.get('source_time')==4.8)
    assert 'char_ada.expression: mouth open in diagnosis' in middle['description']
    assert all(f['value'] is not None for f in out['start_state'])


def test_model_context_omits_only_reconstructible_canonical_projections(legacy):
    assert shot_state.model_view(legacy)==legacy
    s=shot_state.compile_shot({**legacy['shots'][0],'canonical_state':track(legacy)})
    original=copy.deepcopy(s);wire=shot_state.model_view(s)
    assert 'start_state' not in wire and 'description' not in wire['keyframes'][0]
    assert wire['canonical_state']==s['canonical_state']
    assert shot_state.compile_shot(wire)==s==original
    assert len(json.dumps(wire))<len(json.dumps(s))
    duplicated={'shots':[s],'requirements':{'shot':copy.deepcopy(s)},'canon':legacy['canon'],
        'conditioning_requirements':{'shot_01':{'shot':{k:v for k,v in s.items() if k!='keyframes'},'canon':copy.deepcopy(legacy['canon'])}}}
    compact=shot_state.model_view(duplicated)
    assert len(compact['canonical_state_library'])==1
    assert compact['conditioning_requirements']['shot_01']['source_canon_ref']=='canon'
    assert compact['canon']==legacy['canon']
    subset=compact['conditioning_requirements']['shot_01']['shot']
    assert 'keyframes' not in subset
    assert subset['canonical_shot_ref']==compact['shots'][0]['canonical_shot_ref']
    for item in [compact['shots'][0],compact['requirements']['shot']]:
        restored=copy.deepcopy(compact['canonical_shot_library'][item['canonical_shot_ref']])
        if 'keyframes' in item:restored['keyframes']=copy.deepcopy(item['keyframes'])
        restored['canonical_state']=copy.deepcopy(compact['canonical_state_library'][restored.pop('canonical_state_ref')])
        facts=restored['canonical_state'].pop('fact_library')
        for moment in restored['canonical_state']['moments']:
            moment['state']=[facts[i] for i in moment.pop('state_refs')]
        assert shot_state.compile_shot(restored)==s


def test_board_wire_compacts_without_changing_source_or_literal_whitespace(legacy,monkeypatch):
    from studio import storyboard_board
    s=shot_state.compile_shot({**legacy['shots'][0],'canonical_state':track(legacy)})
    src={'shots':[s],'requirements':{'shot':copy.deepcopy(s)},'note':'first  line\n第二行\tend'}
    before=copy.deepcopy(src)
    monkeypatch.setattr(storyboard_board,'planning_source',lambda *args:src)
    result=storyboard_board.build({},models.JobRequest(capability='storyboard_frames',target_id='scene'))
    wire=result['prompt'].split('SOURCE:\n',1)[1].split('\nDIRECTOR REQUEST:',1)[0]
    assert json.loads(wire)==shot_state.model_view(src)
    assert len(wire.encode())<len(store.encode(shot_state.model_view(src)).encode())
    assert result['board_source']==src==before
    assert result['board_hash']==store.digest(before)


def test_global_framing_motion_is_not_pasted_into_every_frozen_frame(legacy):
    s=copy.deepcopy(legacy['shots'][0]);s['canonical_state']=track(legacy)
    s['framing']='A two-shot framing the later hand crossing the lantern.'
    s['camera']='A slow push during the later embrace.'
    out=shot_state.compile_shot(s)
    assert all('later hand crossing' not in f['description'] and 'later embrace' not in f['description'] for f in out['keyframes'])
    assert out['framing']==s['framing'] and out['camera']==s['camera']
    assert 'Low locked two-shot' in out['keyframes'][0]['description']


@pytest.mark.parametrize('dimension', ['gaze_target','pose','position','held_props','expression','power'])
def test_all_semantic_dimensions_compile_from_one_authority(legacy,dimension):
    s=copy.deepcopy(legacy['shots'][0]);s['canonical_state']=track(legacy)
    for m in s['canonical_state']['moments']:
        m['state']=[f for f in m['state'] if (f['entity_id'],f['key'])!=('char_pip',dimension)]
        m['state'].append({'entity_id':'char_pip','key':dimension,'value':'canonical test value'})
    s['canonical_state']['transitions']=[t for t in s['canonical_state']['transitions'] if not any(c['entity_id']=='char_pip' and c['key']==dimension for c in t['changes'])]
    out=shot_state.compile_shot(s)
    assert all('char_pip.'+dimension+': canonical test value' in f['description'] for f in out['keyframes'])


def test_compiled_receipt_rejects_tampering(client,gate,legacy):
    REAL_PREPARE(legacy)
    for path in (store.DATA/'shot-state-checks'/'accepted').glob('*.json'):
        value=json.loads(path.read_text());value['shot']['start_state'][0]['value']='tampered';path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='integrity'):REAL_PREPARE(legacy)


def test_downstream_caption_conflict_is_checked_and_cannot_reuse_pass(legacy,tmp_path,monkeypatch):
    s=shot_state.compile_shot({**legacy['shots'][0],'canonical_state':track(legacy)})
    source={'shots':[s]};provider={'id':'test'};calls=[]
    def check(p,cap,prompt,work):
        calls.append(prompt)
        return {'verdict':'revise' if 'CONTRADICTORY' in prompt else 'pass','summary':'caption check',
            'issues':['caption conflicts with canonical opening'] if 'CONTRADICTORY' in prompt else []}
    monkeypatch.setattr(shot_state,'_call',check)
    artifact={'purpose':'opening readability'}
    shot_state.check_artifact(source,artifact,provider,tmp_path)
    shot_state.check_artifact(source,artifact,provider,tmp_path)
    assert len(calls)==1
    with pytest.raises(ValueError,match='caption conflicts'):
        shot_state.check_artifact(source,{'purpose':'CONTRADICTORY gaze'},provider,tmp_path)
    assert len(calls)==2
    with pytest.raises(ValueError,match='blocked'):
        shot_state.check_artifact(source,{'purpose':'CONTRADICTORY gaze'},provider,tmp_path)
    assert len(calls)==2
    assert 'EVERY anchor purpose' in calls[0]


def test_board_caption_gate_runs_before_success_and_legacy_adoption(client,gate,legacy,monkeypatch):
    from studio import storyboard_board as board
    pid=client.post('/api/projects',json={'title':'Caption gate','idea':'Test only'}).json()['id']
    p=engine.save_plan(pid,legacy,0,'test');s=p['production']['shots'][0]
    response=client.post(f'/api/projects/{pid}/jobs',json={'capability':'storyboard_frames','target_id':s['scene_id']})
    assert response.status_code==200,response.text
    j=store.job(response.json()['job']['id']);src=j['input']['board_source']
    result={'scene_id':s['scene_id'],'summary':'Test','panels':[{'edit_id':src['edits'][0]['id'],'reason':'continuous',
        'anchors':[{'time':0,'reuse_frame_id':s['keyframes'][0]['id'],'description':'','state':[],'purpose':'Wrong opening gaze'}],
        'image_plan':{'mode':'I2VA','reason':'locked opening','evidence':[s['camera']],'unresolved_constraints':[],'reference_demands':[]},'planning_notes':[]}]}
    monkeypatch.setattr(shot_state,'_call',lambda *args:{'verdict':'revise','summary':'Opening caption contradicts canonical gaze','issues':['gaze mismatch']})
    with pytest.raises(ValueError,match='artifact check blocked'):engine.finish(j,result)
    assert store.job(j['id'])['state']!='succeeded' and store.project(pid)['revision']==1
    # A pre-gate succeeded proposal must still be checked before adoption.
    with store.db() as c:c.execute('UPDATE jobs SET state="succeeded",result=? WHERE id=?',(store.encode(result),j['id']))
    before=copy.deepcopy(board.config(pid))
    with pytest.raises(ValueError,match='artifact check blocked'):
        board.adopt(pid,j['id'],board.Adoption(revision=before['revision'],production_revision=1))
    assert store.project(pid)['revision']==1 and board.config(pid)==before


def test_interrupted_artifact_check_requires_explicit_resume(legacy,tmp_path,monkeypatch):
    source={'shots':[shot_state.compile_shot({**legacy['shots'][0],'canonical_state':track(legacy)})]}
    calls=[]
    def interrupted(*args):calls.append(1);raise RuntimeError('transport interrupted')
    monkeypatch.setattr(shot_state,'_call',interrupted)
    with pytest.raises(RuntimeError):shot_state.check_artifact(source,{}, {},tmp_path)
    with pytest.raises(ValueError,match='blocked'):shot_state.check_artifact(source,{}, {},tmp_path)
    assert len(calls)==1
    monkeypatch.setattr(shot_state,'_call',lambda *args:{'verdict':'pass','summary':'Resumed exact check','issues':[]})
    shot_state.check_artifact(source,{}, {},tmp_path,resume=True)
    assert len(list(tmp_path.glob('*/explicit-resume-*/previous-verification.json')))==1
    shot_state.check_artifact(source,{}, {},tmp_path)


def test_cancellation_stops_before_semantic_provider(client,gate,legacy):
    work=store.DATA/'jobs'/'cancelled'/'canonical-state';work.mkdir(parents=True)
    (work.parent/'cancel-requested').touch()
    with pytest.raises(ValueError,match='cancelled'):REAL_PREPARE(legacy,work=work)
    assert not gate


def test_chapter_localization_preserves_canonical_frame_binding(legacy,monkeypatch):
    from studio import serial_story
    plan=copy.deepcopy(legacy);plan['shots'][0]=shot_state.compile_shot({**plan['shots'][0],'canonical_state':track(legacy)})
    chapter={'id':'chapter_a','title':'Chapter A'};frozen={'chapter':chapter}
    monkeypatch.setattr(serial_story,'chapter',lambda *args:chapter)
    monkeypatch.setattr(serial_story,'chapters',lambda *args:[chapter])
    monkeypatch.setattr(serial_story,'snapshot',lambda *args:frozen)
    merged=serial_story.merge({'id':'test','title':'Series','production':None},plan,frozen)
    shot_state.assert_compiled(merged)
    s=merged['shots'][0]
    assert {c['frame_id'] for c in s['canonical_state']['compositions']}=={f['id'] for f in s['keyframes']}
    assert all(f['id'].startswith('chapter_a__') for f in s['keyframes'])


def test_concurrent_edit_during_preflight_wins(client,gate,legacy,monkeypatch):
    pid=client.post('/api/projects',json={'title':'Test','idea':'A lamp diagnosis'}).json()['id']
    original=shot_state._call
    def concurrent(p,cap,prompt,work):
        if cap=='qc':
            with store.db() as c:c.execute('UPDATE projects SET revision=1,title=? WHERE id=?',('Concurrent winner',pid))
        return original(p,cap,prompt,work)
    monkeypatch.setattr(shot_state,'_call',concurrent)
    with pytest.raises(ValueError,match='Project changed'):engine.save_plan(pid,legacy,0,'stale submission')
    assert store.project(pid)['title']=='Concurrent winner'
    with store.db() as c:assert c.execute('SELECT count(*) FROM revisions WHERE project_id=?',(pid,)).fetchone()[0]==0


def test_h3_consumes_canonical_start_as_one_i2va_source(client,gate,legacy):
    from test_production import add_asset
    from studio import h3
    pid=client.post('/api/projects',json={'title':'Test','idea':'A lamp diagnosis'}).json()['id']
    plan=engine.save_plan(pid,legacy,0,'test')['production']
    add_asset(pid,plan,'frame_01_start')
    compiled=h3.compile_shot(plan,plan['shots'][0],store.assets(pid))
    assert compiled['mode']=='I2VA' and len(compiled['references'])==1
    assert compiled['text'].split('integrated_multimodal_description:',1)[1].count('[Shot 1]')==1


def test_one_structural_extraction_repair_then_independent_check(client,gate,legacy,monkeypatch):
    calls=[]
    def call(provider,cap,prompt,work):
        calls.append(work.name)
        if cap=='qc':return {'verdict':'pass','summary':'Test-only independent checker','issues':[]}
        value=track(legacy)
        if work.name=='extract':value['transitions']=[]
        return {'canonical_state':value,'conflicts':[],'reconciliations':['recorded correction']}
    monkeypatch.setattr(shot_state,'_call',call)
    result=REAL_PREPARE(legacy)
    shot_state.assert_compiled(result)
    assert calls==['extract','extract-repair','check']


def test_structural_repair_is_bounded_and_never_erases_source_conflict(client,gate,legacy,monkeypatch):
    calls=[]
    def invalid(p,c,prompt,w):
        calls.append(w.name);value=track(legacy);value['transitions']=[]
        return {'canonical_state':value,'conflicts':[],'reconciliations':[]}
    monkeypatch.setattr(shot_state,'_call',invalid)
    with pytest.raises(ValueError,match='outside a declared transition'):REAL_PREPARE(legacy)
    assert calls==['extract','extract-repair']
    calls.clear()
    def conflict(p,c,prompt,w):
        calls.append(w.name)
        return {'canonical_state':track(legacy),'conflicts':['Authoritative position contradicts its timed beat'],'reconciliations':[]}
    monkeypatch.setattr(shot_state,'_call',conflict)
    with pytest.raises(ValueError,match='source conflict'):REAL_PREPARE(legacy)
    assert calls==['extract']


def test_recovery_checks_before_marking_proposal_success(client,gate,legacy,monkeypatch):
    pid=client.post('/api/projects',json={'title':'Test','idea':'A lamp diagnosis'}).json()['id']
    jid=store.uid();inp={'provider_config':providers.DEFAULT,'revision':0,'feedback':''}
    with store.db() as c:c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',(jid,pid,'narrative','','running','astra',store.encode(inp),store.now(),store.now()))
    monkeypatch.setattr(shot_state,'_call',lambda *args:(_ for _ in ()).throw(ValueError('source contradiction')))
    with pytest.raises(ValueError):engine.finish(store.job(jid),legacy)
    assert store.job(jid)['state']!='succeeded' and store.project(pid)['revision']==0
