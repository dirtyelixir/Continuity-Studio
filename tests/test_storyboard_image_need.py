"""New image-demand contract; legacy board fixtures retain their frozen contract."""
import copy
import json
import pytest
from studio import storyboard_board as board,storyboard_usage as usage,store,engine,models,video_workflow as video,h3_render_graph as graph
from test_production import client,plan,create,add_asset
from test_generation_groups import montage
from test_storyboard_board import approve_all,adopt as adopt_legacy,proposed
from test_video_render import schema


def proposal(p,mode='I2VA',unresolved=None):
    src=board.source(p,'scene');shots={s['id']:s for s in src['shots']};panels=[]
    for edit in src['edits']:
        s=shots[edit['shot_id']];anchors=[]
        for t in ([0,s['duration']] if mode=='FL2VA' else [0]):
            f=board.frame_at(s,t)
            anchors.append({'time':t,'reuse_frame_id':f['id'] if f else '',
                'description':f['description'] if f else 'The adopted final composition.',
                'state':s['start_state'] if t==0 else s['end_state'],'purpose':'Required model endpoint.'})
        panels.append({'edit_id':edit['id'],'reason':'Preserve editorial use.','anchors':anchors,
            'image_plan':{'mode':mode,'reason':'Source endpoints constrain this continuous take.',
                'evidence':[s['keyframes'][0]['description']], 'unresolved_constraints':unresolved or []},
            'planning_notes':['The middle gesture remains timed direction in the video prompt; no review-only image.']})
    return {'scene_id':'scene','summary':'Generate only required constraints.','panels':panels}


def adopt_new(client,pid,result):
    p=store.project(pid)
    j=client.post(f'/api/projects/{pid}/jobs',json={'capability':'storyboard_frames','target_id':'scene'}).json()['job']
    engine.finish(store.job(j['id']),result)
    r=client.post(f'/api/projects/{pid}/storyboard/adopt/{j["id"]}',json={'revision':board.config(pid)['revision'],'production_revision':p['revision']})
    assert r.status_code==200,r.text
    return r.json()


def test_three_stills_do_not_create_shots_or_three_image_jobs(client,plan):
    plan['shots'][0]['keyframes'].append({'id':'middle','moment':'key','source_time':2,'description':'A gesture','state':[]})
    pid=create(client,plan);before=store.project(pid)['production'];old=add_asset(pid,before,'middle')
    adopt_new(client,pid,proposal(store.project(pid)))
    p=store.project(pid);panels=board.scene_state(p,'scene')['panels']
    assert p['production']==before and len(p['production']['shots'])==1
    assert len(panels[0]['anchors'])==1 and panels[0]['anchors'][0]['time']==0
    assert panels[0]['planning_notes'] and video.config(pid)['shots']['shot']['mode']=='I2VA'
    assert [i['target_id'] for i in board.preview(pid,'scene')['items']]==['start']
    assert next(a for a in store.assets(pid) if a['id']==old)['status']=='approved'
    approve_all(client,pid)
    src=video.prompt_source(store.project(pid),'shot')
    assert len(src['references'])==1 and src['storyboard_usage'][0]['actual_input']


def test_fl2va_end_is_really_bound_and_cannot_downgrade(client,plan,schema):
    pid=create(client,plan);adopt_new(client,pid,proposal(store.project(pid),'FL2VA'));approve_all(client,pid)
    p=store.project(pid);src=video.prompt_source(p,'shot')
    assert len(src['storyboard_usage'])==2 and all(u['actual_input'] for u in src['storyboard_usage'])
    source={**src,'shot_id':'shot','duration':6,'text':'Test','global_prompt':''}
    # Production render fills exact hashes before build_graph; preserve that invariant here.
    for ref in source['references']:ref['sha256']=next(u['sha256'] for u in src['storyboard_usage'] if u['asset_id']==ref['asset_id'])
    uploads={r['asset_id']:{'name':r['asset_id']+'.png','type':'input','subfolder':'test'} for r in src['references']}
    g=graph.build_graph(source,uploads,{**graph.defaults('FL2VA'),'seed':1},'a'*16,schema)
    timeline=json.loads(g['12']['inputs']['timeline_data'])
    assert len(timeline['segments'])==1
    assert timeline['segments'][0]['endImage']['imageFile'].endswith(src['references'][1]['asset_id']+'.png')
    cfg=video.config(pid);cfg['shots']['shot']['mode']='I2VA';store.put_setting('video-workflow:'+pid,cfg)
    with pytest.raises(ValueError,match='模式'):video.prompt_source(p,'shot')


@pytest.mark.parametrize('bad',['extra','fake_endpoint','missing_plan','fake_evidence'])
def test_need_contract_rejects_over_storyboarding(client,plan,bad):
    pid=create(client,plan);p=store.project(pid);result=proposal(p)
    panel=result['panels'][0]
    if bad=='extra':panel['anchors'].append({**panel['anchors'][0],'time':2})
    if bad=='fake_endpoint':panel['image_plan']['mode']='FL2VA';panel['anchors'].append({**panel['anchors'][0],'time':5.8})
    if bad=='missing_plan':panel.pop('image_plan')
    if bad=='fake_evidence':panel['image_plan']['evidence']=['Invented visual necessity']
    with pytest.raises(ValueError):board.validate(result,board.planning_source(p,'scene'))


def test_hard_middle_constraint_stops_spending_and_handoff(client,plan):
    pid=create(client,plan)
    adopt_new(client,pid,proposal(store.project(pid),unresolved=['At 2s the evidence must match an exact intermediate composition; internal conditioning is not implemented.']))
    p=store.project(pid);assert not board.scene_state(p,'scene')['ready']
    with pytest.raises(ValueError,match='約束'):board.preview(pid,'scene')
    with pytest.raises(ValueError,match='約束'):board.require_review(p,'scene')
    with pytest.raises(ValueError,match='約束'):video.prompt_source(p,'shot')
    assert not store.assets(pid)


def test_trimmed_source_uses_real_source_opening_without_new_cut(client,montage):
    pid=create(client,montage);before=store.project(pid)['production']
    adopt_new(client,pid,proposal(store.project(pid)));p=store.project(pid)
    assert p['production']==before
    panels=board.scene_state(p,'scene')['panels']
    assert panels[1]['edit']['planned_edit_in']==3 and panels[1]['anchors'][0]['time']==0
    rows=usage.intent(p,'scene');assert rows[1]['scene_time'] is None and rows[1]['role']=='shot_opening'


def test_legacy_board_remains_unchanged_until_new_plan_adopted(client,plan):
    pid=create(client,plan);adopt_legacy(client,pid,proposed(store.project(pid),extra=True));approve_all(client,pid)
    old=board.config(pid);assets=store.assets(pid)
    board.planning_source(store.project(pid),'scene')
    assert board.config(pid)==old and store.assets(pid)==assets
    assert len(board.scene_state(store.project(pid),'scene')['panels'][0]['anchors'])==2
    adopt_new(client,pid,proposal(store.project(pid)))
    new=board.config(pid)['scenes']['scene']
    assert new['history'][-1]['reviews']==old['scenes']['scene']['reviews']
    assert len(new['panels'][0]['anchors'])==1
    assert store.assets(pid)==assets


def test_new_proposal_mode_concurrency_and_stale_board_read(client,plan):
    pid=create(client,plan);p=store.project(pid)
    j=client.post(f'/api/projects/{pid}/jobs',json={'capability':'storyboard_frames','target_id':'scene'}).json()['job']
    engine.finish(store.job(j['id']),proposal(p))
    store.put_setting('video-workflow:'+pid,{'revision':1,'shots':{'shot':{'mode':'FL2VA'}}})
    r=client.post(f'/api/projects/{pid}/storyboard/adopt/{j["id"]}',json={'revision':0,'production_revision':p['revision']})
    assert r.status_code==400 and not board.config(pid)['scenes']
    adopt_new(client,pid,proposal(store.project(pid)));p=store.project(pid)
    changed=copy.deepcopy(p['production']);changed['shots'][0]['expression']='Different intention'
    engine.save_plan(pid,changed,p['revision'],'Change direction')
    assert client.get('/api/projects/'+pid).status_code==200
    with pytest.raises(ValueError):video.prompt_source(store.project(pid),'shot')


def joined_evidence(result,src,make):
    shots={s['id']:s for s in src['shots']};edits={e['id']:e for e in src['edits']}
    for panel in result['panels']:
        text=shots[edits[panel['edit_id']]['shot_id']]['keyframes'][0]['description']
        panel['image_plan']['evidence']=[make(text)]


def test_ellipsis_joined_excerpts_are_verbatim_but_paraphrase_is_still_rejected(client,plan):
    """A model may elide two real passages; invented or reworded evidence stays rejected."""
    pid=create(client,plan);p=store.project(pid);src=board.planning_source(p,'scene')
    words=src['shots'][0]['keyframes'][0]['description'].split(' ')
    left,right=' '.join(words[:6]),' '.join(words[-8:])
    result=proposal(p)
    for accepted in [left+' ... '+right,left+' \u2026 '+right,left+' [...] '+right,'   '+'   '.join(left.split())+'   ']:
        joined_evidence(result,src,lambda _t,text=accepted:text and accepted)
        board.validate(result,src)
    for rejected in [left+' ... '+'Invented visual necessity','Invented visual necessity',left+' ... ','...','']:
        joined_evidence(result,src,lambda _t,text=rejected:text and rejected)
        with pytest.raises(ValueError,match='用圖需要'):board.validate(result,src)
    # The whole entry may also be one ordinary exact excerpt, unchanged from before.
    joined_evidence(result,src,lambda text:text)
    board.validate(result,src)


def test_provider_extra_informational_keys_do_not_discard_a_valid_plan(client,plan):
    """Real 2026-09-13 failures: planning_notes_count / reuse_frame_note rejected a whole plan."""
    pid=create(client,plan);p=store.project(pid);src=board.planning_source(p,'scene')
    result=proposal(p);result['schema_version']=2
    for panel in result['panels']:
        panel['planning_notes_count']=len(panel['planning_notes'])
        for anchor in panel['anchors']:
            anchor['reuse_frame_note']=None
            anchor['confidence']=0.9
    board.validate(result,src)  # Unknown keys are informational, not a semantic contradiction.
    # The schema the provider is asked for still forbids additional properties.
    from studio.providers import strict_schema
    for model in (board.BoardPlan,board.Panel,board.Anchor):
        schema=json.loads(json.dumps(strict_schema(model.model_json_schema())))
        assert schema['additionalProperties'] is False,model.__name__
        assert set(schema['required'])==set(schema['properties']),model.__name__
    # A real semantic error is still rejected: unknown keys are not a loophole.
    result['panels'][0]['anchors'].append({**result['panels'][0]['anchors'][0],'time':2})
    with pytest.raises(ValueError):board.validate(result,src)


def test_adopted_fresh_board_is_not_presented_as_a_later_failure(client,plan):
    """After adoption a later failed retry must not report the scene as 安排失敗."""
    pid=create(client,plan);p=store.project(pid)
    first=client.post(f'/api/projects/{pid}/jobs',json={'capability':'storyboard_frames','target_id':'scene'}).json()['job']
    engine.finish(store.job(first['id']),proposal(p))
    client.post(f'/api/projects/{pid}/storyboard/adopt/{first["id"]}',json={'revision':board.config(pid)['revision'],'production_revision':p['revision']})
    second=client.post(f'/api/projects/{pid}/jobs',json={'capability':'storyboard_frames','target_id':'scene'}).json()['job']
    with store.db() as c:c.execute("UPDATE jobs SET state='failed',error=? WHERE id=?",('用圖需要須引用本鏡已有導演資料作依據。',second['id']))
    row=board.state(store.project(pid))['scenes'][0]
    assert row['adopted'] and not row['stale']
    # The adopted, still-fresh board owns the status line, not the newer failed attempt.
    assert row['job']['id']==first['id'] and row['job']['adopted'] is True
    assert row['candidates'][0]['id']==second['id'] and row['candidates'][0]['usable'] is False
    # Genuine in-flight work still takes the slot ahead of the adopted record.
    third=client.post(f'/api/projects/{pid}/jobs',json={'capability':'storyboard_frames','target_id':'scene'}).json()['job']
    with store.db() as c:c.execute("UPDATE jobs SET state='running' WHERE id=?",(third['id'],))
    assert board.state(store.project(pid))['scenes'][0]['job']['id']==third['id']
    # A stale adopted board must not mask a newer attempt either.
    changed=copy.deepcopy(store.project(pid)['production']);changed['shots'][0]['expression']='Different intention'
    engine.save_plan(pid,changed,store.project(pid)['revision'],'Change acting')
    assert board.state(store.project(pid))['scenes'][0]['stale']


def test_later_failure_keeps_earlier_usable_plan_reachable(client,plan):
    """A failed retry must not hide an earlier succeeded plan; both stay visible with real states."""
    pid=create(client,plan);p=store.project(pid)
    first=client.post(f'/api/projects/{pid}/jobs',json={'capability':'storyboard_frames','target_id':'scene'}).json()['job']
    engine.finish(store.job(first['id']),proposal(p))
    second=client.post(f'/api/projects/{pid}/jobs',json={'capability':'storyboard_frames','target_id':'scene'}).json()['job']
    with store.db() as c:c.execute("UPDATE jobs SET state='failed',error=? WHERE id=?",('用圖需要須引用本鏡已有導演資料作依據。',second['id']))
    row=board.state(store.project(pid))['scenes'][0]
    assert row['job']['id']==second['id'] and row['job']['state']=='failed'
    assert row['candidates'][0]['id']==second['id'] and row['candidates'][0]['usable'] is False
    assert [c['id'] for c in row['candidates'] if c['usable']]==[first['id']]
    scene=client.get(f'/api/projects/{pid}').json()['storyboard']['scenes'][0]
    assert [c['id'] for c in scene['candidates'] if c['usable']]==[first['id']]
    assert not scene['candidates'][0]['usable'] and scene['candidates'][0]['error']
    # In-flight work owns the progress slot instead of a newer terminal record being required.
    with store.db() as c:c.execute("UPDATE jobs SET state='running',error='' WHERE id=?",(second['id'],))
    assert board.state(store.project(pid))['scenes'][0]['job']['state']=='running'
