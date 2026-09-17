"""Controlled schema outputs verify compilation, not the real model's reasoning."""
import copy,json
import pytest
from studio import conditioning as c,store,models,engine,video_workflow as v,video_render as vr,delivery,storyboard_board as board
from test_production import client,plan,create,add_asset
from test_video_render import local,schema,send,request_for
from test_video_workflow import begin,adopt

def choice():
    return dict(mode='REF2VA',reason='Freely stage reusable Ada and workshop appearances.',evidence=['Raise hand and press switch'],
        reference_demands=[dict(entity_id=e,role=r,required=True,reason='Preserve this needed appearance.',evidence=[q]) for e,r,q in [('ada','character_identity','Black bob and yellow coat'),('room','environment_reference','Round window behind a wooden bench')]],
        unresolved_constraints=[],start_blueprint='Ada in workshop, free camera position.',end_blueprint='',checks=['Verify Ada.','Verify workshop.'])

def select(client,pid):
    j=begin(client,pid,'h3_strategy');assert j['input']['strategy_mode']=='AUTO'
    response=client.post('/api/jobs/'+j['id']+'/manual',json=choice());assert response.status_code==200,response.text
    assert adopt(client,pid,j).status_code==200
    return j

def ref_text(src):
    return src['alignment']+'\n\nsummary: [reference generation] One continuous 6-second view of Ada.\n\nretention_analysis: Preserve <Subject 1> from <Picture 1> and the workshop from <Picture 2>.\n\ndetailed_description: [Shot 1] Ada raises her hand and presses the switch. At 3 to 4 seconds Ada says <d>[English] Light.</d>\n\noverall_soundscape: Wind and a switch click.\n\nnon_diegetic_music: N/A'

def prepare(client,pid):
    j=begin(client,pid);r=client.post('/api/jobs/'+j['id']+'/manual',json={'text':ref_text(j['input']['video_source']),'frame_issues':[]});assert r.status_code==200,r.text
    assert adopt(client,pid,j).status_code==200
    return j

def test_demands_to_frozen_graph_and_verified_receipt(client,local,plan):
    pid,remote=local
    for eid in ('ada','room'):add_asset(pid,plan,eid)
    select(client,pid);prepare(client,pid)
    p=store.project(pid);src=vr.source(p,'shot');packet=v.packet(p,'shot')
    assert [(r['target_id'],r['role'],r['label']) for r in src['references']]==[('ada','character_identity','Picture 1'),('room','environment_reference','Picture 2')]
    assert len(src['reference_demands'])==2 and packet['reference_demands']==src['reference_demands']
    request=request_for(client,pid);frozen=vr.freeze(pid,'shot',vr.Generate(**request))
    assert frozen['source']['reference_demands']==src['reference_demands']
    t=send(client,pid,request);vr.run(pid,t['id']);detail=vr.detail(pid,t['id'])
    assert detail['state']=='succeeded',detail['error']
    assert all(r['submission_verified'] for r in detail['image_inputs'])
    assert set(remote['uploads'])=={r['asset_id'] for r in src['references']}
    tl=json.loads(remote['graph']['12']['inputs']['timeline_data']);assert not tl['global']['refs']
    assert [r['index'] for r in tl['segments'][0]['refs']]==[0,1]
    assert tl['segments'][0]['prompt']==detail['request']['source']['text']
    root=vr.folder(t['id']);graph_file=root/'graph.json';receipt_file=root/'receipt.json'
    original_graph=graph_file.read_text();original_receipt=receipt_file.read_text()
    bad=json.loads(original_graph);timeline=json.loads(bad['12']['inputs']['timeline_data']);timeline['segments'][0]['refs'][0]['index']=8
    bad['12']['inputs']['timeline_data']=json.dumps(timeline);graph_file.write_text(store.encode(bad))
    receipt=json.loads(original_receipt);receipt['studio_workflow_hash']=store.digest(bad);receipt_file.write_text(store.encode(receipt))
    assert not vr.detail(pid,t['id'])['image_inputs'][0]['submission_verified']
    graph_file.write_text(original_graph);receipt_file.write_text(original_receipt)
    transport=root/'transport.json';saved=transport.read_text();bad=json.loads(saved);bad['uploads'][src['references'][0]['asset_id']]['verified_sha256']='wrong'
    transport.write_text(store.encode(bad));assert not vr.detail(pid,t['id'])['image_inputs'][0]['submission_verified']
    transport.write_text(saved)
    receipt_file.unlink()
    assert not any(r['submission_verified'] for r in vr.detail(pid,t['id'])['image_inputs'])

def test_scope_omission_dedup_and_required_missing(client,plan):
    plan['canon'].append(dict(plan['canon'][0],id='pip',name='Pip'))
    # Pip remains linked to another shot in this Scene, with a real test asset.
    other=copy.deepcopy(plan['shots'][0]);other.update(id='other',entity_ids=['pip'],start_state=[],end_state=[],dialogue=[],keyframes=[{'id':'other_start','moment':'start','description':'Pip alone'}]);plan['shots'].append(other)
    pid=create(client,plan);add_asset(pid,plan,'ada');add_asset(pid,plan,'pip');p=store.project(pid);decision=choice()
    r=c.resolve_plan(p,'shot',decision,strict=False);assert r['unresolved'] and r['demands'][1]['status']=='missing' and r['demands'][1]['label']=='Picture 2'
    with pytest.raises(ValueError,match='約束'):c.resolve_plan(p,'shot',decision)
    add_asset(pid,plan,'room');decision['reference_demands'].append({**decision['reference_demands'][0],'role':'appearance_consistency'})
    r=c.resolve_plan(p,'shot',decision);assert len(r['references'])==2 and r['demands'][2]['label']=='Picture 1'
    assert 'pip' not in {r['target_id'] for r in r['references']}
    decision['reference_demands'][1]['required']=False
    r=c.resolve_plan(p,'shot',decision);assert len(r['references'])==1 and r['demands'][1]['status']=='optional_omitted' and r['demands'][1]['label'] is None
    decision['reference_demands'][0]['entity_id']='pip'
    with pytest.raises(ValueError,match='本鏡'):c.validate(decision,c.requirements(p,'shot'))

@pytest.mark.parametrize('change',[{'role':'object_identity'},{'entity_id':'start'},{'evidence':['Invented quote']},{'reason':' '}])
def test_invalid_demands_rejected(client,plan,change):
    pid=create(client,plan);d=choice();d['reference_demands'][0].update(change)
    with pytest.raises(ValueError):c.validate(d,c.requirements(store.project(pid),'shot'))

@pytest.mark.parametrize('role',['video_reference','audio_reference','motion_reference'])
def test_unsupported_required_never_silently_dropped(client,plan,role):
    pid=create(client,plan);d=choice();d['reference_demands'][0]['role']=role;add_asset(pid,plan,'room')
    with pytest.raises(ValueError,match=role):c.resolve_plan(store.project(pid),'shot',d)


def test_unresolved_stale_rejected_asset_and_hash_changes(client,plan):
    pid=create(client,plan);a=add_asset(pid,plan,'ada');add_asset(pid,plan,'room');select(client,pid)
    p=store.project(pid);src=v.prompt_source(p,'shot')
    asset=next(a for a in store.assets(pid) if a['target_id']=='ada')
    (store.DATA/asset['path']).write_bytes(b'changed pixels')
    assert store.digest(v.prompt_source(p,'shot'))!=store.digest(src)
    with store.db() as db:db.execute('update assets set status="rejected" where id=?',(a,))
    with pytest.raises(ValueError,match='約束'):v.prompt_source(p,'shot')
    changed=copy.deepcopy(p);changed['production']['shots'][0]['camera']='Changed camera'
    with pytest.raises(ValueError,match='更新'):c.current(changed,'shot')
    d=choice();d['unresolved_constraints']=['Exact 2s pose requires internal segmentation.']
    with pytest.raises(ValueError,match='Exact 2s'):c.resolve_plan(p,'shot',d)


def test_graph_contract_rejects_mapping_tampering(client,plan):
    pid=create(client,plan);add_asset(pid,plan,'ada');add_asset(pid,plan,'room');select(client,pid)
    src=v.prompt_source(store.project(pid),'shot');c.check_source(src)
    for field,value in [('label','Picture 9'),('subject','Subject 9'),('target_id','pip'),('sha256','other')]:
        bad=copy.deepcopy(src);bad['references'][0][field]=value
        with pytest.raises(ValueError,match='不一致'):c.check_source(bad)
    bad=copy.deepcopy(src);bad['references'].append(bad['references'][0])
    with pytest.raises(ValueError):c.check_source(bad)
    with pytest.raises(ValueError):delivery.validate_demand_prompt(ref_text(src).replace('Subject 1> is Ada','Subject 1> is Pip'),src)


@pytest.mark.parametrize('select_first',[True,False])
def test_ref_board_reuses_strategy_and_needs_zero_new_images(client,plan,select_first):
    from test_storyboard_image_need import proposal,adopt_new
    pid=create(client,plan);add_asset(pid,plan,'ada');add_asset(pid,plan,'room')
    if select_first:select(client,pid)
    before=store.project(pid)['production'];r=proposal(store.project(pid))
    for panel in r['panels']:panel.update(anchors=[],image_plan=c.decision(choice()))
    adopt_new(client,pid,r);p=store.project(pid)
    assert p['production']==before and board.scene_state(p,'scene')['ready']
    if select_first:assert not v.state(p)['shots'][0]['strategy_stale']
    assert board.preview(pid,'scene')['generate_count']==0
    assert c.current(p,'shot')['plan']['mode']=='REF2VA'
    assert len(v.prompt_source(p,'shot')['references'])==2


def test_group_cannot_bypass_required_source_references(client,plan):
    pid=create(client,plan);add_asset(pid,plan,'ada');add_asset(pid,plan,'room');select(client,pid);p=store.project(pid)
    refs=c.resolve(p,'shot')['references'];c.check_group(p,['shot'],'REF2VA',refs)
    for mode,selected in [('I2VA',refs),('REF2VA',refs[:1])]:
        with pytest.raises(ValueError,match='required'):c.check_group(p,['shot'],mode,selected)


def test_existing_continuation_decision_cannot_be_silently_disabled(client,plan,monkeypatch):
    pid=create(client,plan);add_asset(pid,plan,'ada');add_asset(pid,plan,'room');select(client,pid)
    p=store.project(pid);scene,chapter=v.shot_prompts.locate(p,'shot');chapter['guidance']['continuityFromPrev']=True
    monkeypatch.setattr(v.shot_prompts,'locate',lambda *a,**k:(scene,chapter))
    with pytest.raises(ValueError,match='上段影片'):v.prompt_source(p,'shot')
