import copy
import json
import re
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from studio import store, editorial, editorial_pilot, models, h3
from studio.directing_models import validate_director_plan
from studio.editorial_timing import timeline


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path)
    from studio import engine
    monkeypatch.setattr(engine.POOL,'submit',lambda *args:None)
    store.init()
    plan=json.loads((Path(__file__).parent/'fixtures/editorial-source.json').read_text())
    with store.db() as c:
        c.execute('INSERT INTO projects(id,title,idea,style,revision,production,created,updated) VALUES(?,?,?,?,?,?,?,?)',
            ('pilot',plan['title'],'test','test',1,store.encode(plan),store.now(),store.now()))
    return store.project('pilot')


def trial(p):
    sid,plan,notes,cues,prov=editorial_pilot.build(p)
    return editorial.create(p['id'],sid,plan,notes,cues,prov)


def test_complete_trial_uses_existing_contract_and_preserves_source(project):
    before=copy.deepcopy(project)
    t=trial(project)
    validate_director_plan(t['plan'],require_complete=True)
    result=editorial.public(project,t)
    assert len(result['timeline']['visual'])==9
    assert result['timeline']['duration']==53.5
    assert result['baseline_timeline']['duration']==54
    assert result['timeline']['warnings']==[]
    assert store.project('pilot')==before
    assert not store.jobs('pilot') and not store.assets('pilot')
    assert result['images']=={}
    assert all(p['ready'] is False and p['execution_mode'] is None for p in result['artifacts']['prompts'])


def test_prompts_exact_language_and_same_version(project):
    t=trial(project)
    art=editorial.artifacts(t)
    names=[e['name'] for e in t['plan']['canon'] if e['kind']=='character']
    for p in art['prompts']:
        shot=next(s for s in t['plan']['shots'] if s['id']==p['shot_id'])
        h3.validate_refinement(p['text'],p,shot)
        body=p['text']
        for d in shot['dialogue']: body=body.replace(d['text'],'')
        for name in names: body=body.replace(name,'')
        assert not re.search(r'[\u3400-\u9fff]',body)
        assert p['plan_hash']==store.digest(t['plan'])
        assert p['trial_version']==1
    silent=next(p for p in art['prompts'] if p['shot_id'].endswith('_reveal'))
    assert '十二樓。' in silent['text']
    assert 'Silent articulation only, with no audible words' in silent['text']
    from studio.postproduction import silent_dialogue
    assert silent_dialogue(next(s for s in t['plan']['shots'] if s['id'].endswith('_reveal'))['dialogue'][0])


def test_media_reference_is_immutable_and_invalidated_by_hand_change(project,monkeypatch):
    from studio import continuity
    t=trial(project);shot=t['plan']['shots'][0];fid=shot['keyframes'][0]['id']
    image=store.DATA/'test.png';image.write_bytes(b'test image placeholder, never served')
    asset=dict(id='image_v1',target_id=fid,path='test.png',status='approved',job_id=None,
        dependency_hash=continuity.target_hash(t['plan'],fid))
    monkeypatch.setattr(store,'assets',lambda pid:[asset])
    result=editorial.public(project,t)
    assert result['images'][shot['id']]['asset_id']=='image_v1'
    assert result['images'][shot['id']]['source']=='imported'
    # Reuse reads the same asset; it does not invent another generation job.
    t['plan']['edit_plan'].append({**t['plan']['edit_plan'][0],'id':'second_use'})
    assert editorial.public(project,t)['images'][shot['id']]['asset_id']=='image_v1'
    shot['start_state'][0]['value']='empty; held in 陳樂言’s right hand'
    assert shot['id'] not in editorial.public(project,t)['images']


def test_save_versions_stale_rejection_and_no_destructive_side_effects(project):
    t=trial(project);original_hash=store.digest(t['plan']);rows=editorial.scope(t['plan'],t['scene_id'])['edit_plan']
    rows[0]['planned_edit_out']=1.8
    updated=editorial.save('pilot',t['id'],editorial.TrialEdit(version=1,edit_plan=rows,audio_cues=t['audio_cues']))
    assert updated['version']==2 and updated['history_count']==1
    assert updated['artifacts']['plan_hash']!=original_hash
    with pytest.raises(ValueError,match='另一視窗'):
        editorial.save('pilot',t['id'],editorial.TrialEdit(version=1,edit_plan=rows,audio_cues=t['audio_cues']))
    with store.db() as c: c.execute('UPDATE projects SET revision=2 WHERE id="pilot"')
    assert editorial.listing('pilot')['trials'][0]['stale']
    with pytest.raises(ValueError,match='正式方案已改變'):
        editorial.save('pilot',t['id'],editorial.TrialEdit(version=2,edit_plan=rows,audio_cues=t['audio_cues']))


def test_identity_evidence_is_not_self_certifying():
    assert editorial.evidence_check(dict(goal='named_identity',carrier='generic_hand',prior_identity_basis='audience saw her face'))=='revise'
    assert editorial.evidence_check(dict(goal='named_identity',carrier='visible_face'))=='uncertain'
    assert editorial.evidence_check(dict(goal='withhold_identity',carrier='silhouette'))=='unreviewed'


def test_flashback_edit_order_cannot_rewrite_story_state_and_no_cut_control(project):
    t=trial(project);before=editorial.artifacts(t)['states']
    sc=editorial.scope(t['plan'],t['scene_id'])
    # Reuse an earlier, unharmed story instant AFTER the bloodied hand.
    sc['edit_plan'].append({**sc['edit_plan'][4],'id':'flashback'})
    t['plan']['edit_plan']=sc['edit_plan']
    editorial.validate_trial(t,t['baseline'])
    assert editorial.artifacts(t)['states']==before
    assert 'bloodied' in next(s for s in sc['shots'] if s['id'].endswith('_aftermath'))['start_state'][1]['value']
    hold=next(s for s in sc['shots'] if s['id'].endswith('_reveal'))
    one={'shots':[hold],'edit_plan':[next(e for e in sc['edit_plan'] if e['shot_id']==hold['id'])]}
    assert timeline(one,editorial.original_audio(one))['duration']==10
    assert len(timeline(one,editorial.original_audio(one))['visual'])==1


def test_story_and_dialogue_cannot_be_silently_changed(project):
    t=trial(project)
    t['plan']['canon'][0]['facts'].append('invented handover')
    with pytest.raises(ValueError,match='原作'):
        editorial.validate_trial(t,t['baseline'])
    t=trial(project)
    next(s for s in t['plan']['shots'] if s['dialogue'])['dialogue'][0]['text']='改寫對白'
    with pytest.raises(ValueError,match='對白'):
        editorial.validate_trial(t,t['baseline'])


def test_adoption_is_one_formal_revision_and_requires_fresh_source(project,monkeypatch):
    from studio import engine,asset_library,directing
    monkeypatch.setattr(asset_library,'write_catalog',lambda pid:None)
    t=trial(project)
    result=editorial.adopt('pilot',t['id'],editorial.TrialAdoption(version=1))
    assert result=={'revision':2,'directing_review':'unreviewed'}
    p=store.project('pilot')
    assert p['production']==t['plan']
    assert store.setting('editorial_applied:pilot')['audio_cues']==t['audio_cues']
    assert all(s['status']=='unreviewed' for s in directing.state(p)['scenes'])
    assert editorial.adopt('pilot',t['id'],editorial.TrialAdoption(version=1))['revision']==2
    assert store.project('pilot')['revision']==2
    assert editorial.listing('pilot')['trials'][0]['status']=='adopted'
    assert not editorial.listing('pilot')['trials'][0]['stale']


def test_formal_save_keeps_mapping_and_audio_in_one_revision(project,monkeypatch):
    from studio import asset_library,editorial_records
    monkeypatch.setattr(asset_library,'write_catalog',lambda pid:None)
    t=trial(project);editorial.adopt('pilot',t['id'],editorial.TrialAdoption(version=1))
    rows=copy.deepcopy(editorial.scope(t['plan'],t['scene_id'])['edit_plan']);rows[0]['planned_edit_out']=1.8
    updated=editorial.save('pilot',t['id'],editorial.TrialEdit(version=1,production_revision=2,edit_plan=rows,audio_cues=t['audio_cues']))
    p=store.project('pilot')
    assert p['revision']==3 and updated['status']=='adopted'
    assert p['production']['edit_plan'][0]['planned_edit_out']==1.8
    result=editorial_records.state(p)
    assert result['scenes'][0]['status']=='current'
    assert len(result['scenes'][0]['mapping'])==9
    assert next(c for c in result['audio'] if c['text']=='走！')['timeline_in']==23.5
    assert store.setting('editorial_scenes:pilot')[t['scene_id']]['version']==2


def test_audio_timeline_uses_project_offset_and_only_current_assets(project,monkeypatch):
    from studio import asset_library,editorial_records
    monkeypatch.setattr(asset_library,'write_catalog',lambda pid:None)
    t=trial(project);editorial.adopt('pilot',t['id'],editorial.TrialAdoption(version=1))
    p=store.project('pilot');plan=p['production']
    # An unrelated first scene adds ten seconds without invalidating this scene's annotations.
    extra=copy.deepcopy(plan['shots'][0]);extra.update(id='earlier',scene_id='earlier_scene',duration=10)
    plan['shots'].insert(0,extra);plan['scenes'].insert(0,{**plan['scenes'][0],'id':'earlier_scene'})
    plan['edit_plan'].insert(0,{**plan['edit_plan'][0],'id':'earlier_cut','shot_id':'earlier','planned_edit_out':10})
    result=editorial_records.state(p)
    cue=next(c for c in result['audio'] if c['text']=='走！')
    assert cue['scene_timeline_in']==23.5 and cue['timeline_in']==33.5
    assert cue['audio_asset'] is None
    plan['shots'][2]['start_state'][0]['value']='changed hand'
    result=editorial_records.state(p)
    assert next(s for s in result['scenes'] if s['scene_id']==t['scene_id'])['status']=='stale'
    assert any(c['scene_id']==t['scene_id'] for c in result['audio'])  # Hand state does not alter saved sound timing.


def test_review_receives_frozen_audio_and_old_review_does_not_certify_it(project,monkeypatch):
    from studio import asset_library,editorial_records,directing
    monkeypatch.setattr(asset_library,'write_catalog',lambda pid:None)
    t=trial(project);editorial.adopt('pilot',t['id'],editorial.TrialAdoption(version=1));p=store.project('pilot')
    payload=directing.build(p,models.JobRequest(capability='directing_qc'))
    assert payload['editorial_source'][t['scene_id']]['audio_cues']==t['audio_cues']
    assert 'J/L-cut is legal' in payload['prompt']
    review={'verdict':'pass','summary':'test only','coverage':[],'issues':[]}
    directing.record_review('pilot',p['production'],review,'old')
    assert directing.state(p)['scenes'][0]['status']=='unreviewed'
    directing.record_review('pilot',p['production'],review,'new',editorial_source=payload['editorial_source'])
    assert directing.state(p)['scenes'][0]['status']=='pass'
    records=editorial_records.records('pilot');records[t['scene_id']]['audio_cues'][0]['timeline_in']+=.2
    store.put_setting('editorial_scenes:pilot',records)
    assert directing.state(p)['scenes'][0]['status']=='unreviewed'


def test_dialogue_cannot_be_reassigned_or_mouth_only_turned_into_speech(project):
    t=trial(project)
    t['audio_cues'][0]['entity_id']='c_leyan'
    with pytest.raises(ValueError,match='原有說話者'):editorial.validate_trial(t,t['baseline'])
    t=trial(project);t['audio_cues'][0]['delivery']='shout'
    with pytest.raises(ValueError,match='有聲／無聲'):editorial.validate_trial(t,t['baseline'])


def test_atomic_revision_and_editorial_settings_on_failure(project,monkeypatch):
    from studio import engine,asset_library
    monkeypatch.setattr(asset_library,'write_catalog',lambda pid:None)
    before=store.project('pilot')
    with pytest.raises(TypeError):
        engine.save_plan('pilot',before['production'],1,'test',setting_updates={'bad':object()})
    assert store.project('pilot')==before
    assert store.setting('bad') is None


def test_formal_edit_does_not_restore_old_other_scenes(project,monkeypatch):
    from studio import engine,asset_library
    monkeypatch.setattr(asset_library,'write_catalog',lambda pid:None)
    t=trial(project);editorial.adopt('pilot',t['id'],editorial.TrialAdoption(version=1))
    p=store.project('pilot');changed=copy.deepcopy(p['production'])
    sc={**copy.deepcopy(changed['scenes'][0]),'id':'other_scene','title':'另一場最新版本','director_plan':None}
    shot=copy.deepcopy(changed['shots'][0]);shot.update(id='other_shot',scene_id=sc['id'],shot_purpose='',direction=None)
    shot['keyframes'][0]['id']='other_frame'
    changed['scenes'].append(sc);changed['shots'].append(shot)
    changed['edit_plan'].append({**changed['edit_plan'][0],'id':'other_edit','shot_id':'other_shot'})
    engine.save_plan('pilot',changed,2,'新增另一場')
    assert editorial.listing('pilot')['trials'][0]['status']=='adopted'
    current=editorial.listing('pilot')['trials'][0]
    assert current['plan']==store.project('pilot')['production']
    assert current['artifacts']['plan_hash']==store.digest(current['plan'])
    rows=editorial.scope(t['plan'],t['scene_id'])['edit_plan'];rows[0]['planned_edit_out']=1.8
    updated=editorial.save('pilot',t['id'],editorial.TrialEdit(version=1,production_revision=3,edit_plan=rows,audio_cues=t['audio_cues']))
    assert updated['status']=='adopted'
    assert store.project('pilot')['production']['scenes'][-1]==sc
    assert store.project('pilot')['production']['shots'][-1]==shot


def test_every_scene_can_open_without_generation_and_reuse_candidate(project):
    req=editorial.OpenScene(scene_id=project['production']['scenes'][0]['id'],production_revision=1)
    a=editorial.open_scene('pilot',req);b=editorial.open_scene('pilot',req)
    assert a['id']==b['id'] and a['status']=='draft'
    assert store.project('pilot')['revision']==1
    assert not store.jobs('pilot')


def test_audio_export_maps_only_selected_current_take(project,monkeypatch):
    from studio import asset_library,editorial_records
    monkeypatch.setattr(asset_library,'write_catalog',lambda pid:None)
    t=trial(project);editorial.adopt('pilot',t['id'],editorial.TrialAdoption(version=1))
    p=store.project('pilot')
    shot=next(s for s in p['production']['shots'] if any(d['text']=='走！' for d in s['dialogue']))
    index=next(i for i,d in enumerate(shot['dialogue']) if d['text']=='走！')
    take={'id':'voice_v2','kind':'line','character_id':shot['dialogue'][index]['entity_id'],
        'state':'succeeded','current':True,'result':{'sha256':'immutable-source-hash'}}
    p['postproduction']={'selected_lines':{f'{shot["id"]}:{index}':'voice_v2'},'takes':[take]}
    cue=next(c for c in editorial_records.state(p)['audio'] if c['text']=='走！')
    assert cue['audio_asset']['take_id']=='voice_v2'
    assert cue['audio_asset']['path'].endswith('-voice_v2.wav')
    take['current']=False
    assert next(c for c in editorial_records.state(p)['audio'] if c['text']=='走！')['audio_asset'] is None


def test_formal_zip_includes_project_audio_and_mapping(project,monkeypatch):
    import io,zipfile
    from studio import app as app_module,asset_library,postproduction,video_render
    monkeypatch.setattr(asset_library,'write_catalog',lambda pid:None)
    postproduction.init();video_render.init()
    t=trial(project);editorial.adopt('pilot',t['id'],editorial.TrialAdoption(version=1))
    with zipfile.ZipFile(io.BytesIO(app_module.export('pilot').body)) as z:
        audio=json.loads(z.read('edit/audio-timeline.json'))
        production=json.loads(z.read('production.json'))
        assert audio==production['editorial']
        assert len(audio['scenes'][0]['mapping'])==9
        assert next(c for c in audio['audio'] if c['text']=='走！')['timeline_in']==23.5
        assert 'edit/plan.json' in z.namelist()


def test_route_and_save_contract(project):
    from studio.app import app
    t=trial(project)
    client=TestClient(app)  # no lifespan: never initialize production or GPU services
    assert client.get('/editorial').status_code==200
    r=client.get('/api/projects/pilot/editorial').json()
    assert r['trials'][0]['id']==t['id']
    rows=editorial.scope(t['plan'],t['scene_id'])['edit_plan']
    data={'version':1,'edit_plan':rows,'audio_cues':t['audio_cues']}
    assert client.put('/api/projects/pilot/editorial/'+t['id'],json=data).status_code==200
    assert client.put('/api/projects/pilot/editorial/'+t['id'],json=data).status_code==400
    assert client.put('/api/projects/pilot/editorial/'+t['id'],json=data,headers={'Origin':'https://foreign.example'}).status_code==403
