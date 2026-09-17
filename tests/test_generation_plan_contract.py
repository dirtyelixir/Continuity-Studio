"""Planner modes belong to native groups; independent sources keep their own strategy."""
import copy
import pytest
from studio import generation_groups as gg, store
from test_production import client, plan, create
from test_generation_groups import montage, definition


def separate_result(src, mode=None):
    return {'summary':'Generate each full source and trim in editing.', 'groups':[
        {'title':e['id'], 'edit_ids':[e['id']], 'execution':'separate_source',
         'mode':mode, 'reference_targets':[], 'reason':'Inspect the evidence independently.',
         'checks':['Check the switch is readable in the generated footage.']}
        for e in src['production']['edit_plan']]}


@pytest.mark.parametrize('mode',['I2VA','FL2VA','REF2VA'])
def test_separate_rejects_concrete_mode_and_native_requires_one(mode):
    item={'title':'Source', 'edit_ids':['e'], 'execution':'separate_source', 'mode':mode,
          'reference_targets':[], 'reason':'Reason', 'checks':['Inspect']}
    with pytest.raises(ValueError,match='null'):gg.PlanItem.model_validate(item)
    assert gg.PlanItem.model_validate({**item,'mode':None}).mode is None
    native={**item,'execution':'native_montage','edit_ids':['e','f']}
    assert gg.PlanItem.model_validate(native).mode==mode
    with pytest.raises(ValueError,match='指定生成模式'):gg.PlanItem.model_validate({**native,'mode':None})
    with pytest.raises(ValueError,match='參考列表'):gg.PlanItem.model_validate({**item,'mode':None,'reference_targets':['ada']})


def test_trimmed_source_does_not_borrow_native_endpoint_constraints(client,montage):
    montage['shots'][0]['duration']=8
    montage['edit_plan'][0].update(planned_edit_in=0.2,planned_edit_out=5.4)
    pid=create(client,montage);src=gg.planning_source(store.project(pid),'scene')
    result=separate_result(src)
    assert gg.validate_plan(result,src)==result
    for mode in ['I2VA','FL2VA']:
        item={k:v for k,v in definition(mode).items() if k!='id'}|{'execution':'native_montage','checks':['Inspect']}
        assert gg.validate_plan({'summary':'Native','groups':[item]},src)  # Missing control becomes a requirement.
    src['production']['edit_plan'][0]['planned_edit_in']=0
    src['production']['edit_plan'][1]['planned_edit_out']=5.5
    item={k:v for k,v in definition('FL2VA').items() if k!='id'}|{'execution':'native_montage','checks':['Inspect']}
    assert gg.validate_plan({'summary':'Native','groups':[item]},src)


def test_current_contract_adopts_without_changing_source_modes_or_production(client,montage):
    pid=create(client,montage)
    client.post('/api/settings/routing',json={'capability':'h3_group_plan','provider_id':'manual'})
    j=client.post(f'/api/projects/{pid}/jobs',json={'capability':'h3_group_plan','target_id':'scene'}).json()['job']
    src=j['input']['group_plan_source'];assert src['plan_contract_version']==gg.PLAN_CONTRACT_VERSION
    old=copy.deepcopy(src);old.pop('plan_contract_version')
    assert store.digest(src)!=store.digest(old)
    prompt=j['input']['prompt']
    for text in ['SEPARATE_SOURCE CONTRACT','NATIVE_MONTAGE CONTRACT ONLY','mode: null','0.2..5.4','do not guarantee stationary hold duration','One generation likewise cannot guarantee continuity']:
        assert text in prompt
    before=store.project(pid)
    with store.db() as c: settings_before=dict(c.execute('SELECT key,value FROM settings'))
    result=separate_result(src)
    assert client.post('/api/jobs/'+j['id']+'/manual',json=result).status_code==200
    response=client.post(f'/api/projects/{pid}/generation-groups/plan-adopt/{j["id"]}',json={'revision':0})
    assert response.status_code==200,response.text
    assert response.json()['groups']=={} and store.project(pid)==before
    state=gg.state(store.project(pid));assert state['plans'][0]['contract_current'] and state['plans'][0]['adopted']
    with store.db() as c: settings_after=dict(c.execute('SELECT key,value FROM settings'))
    assert {k:v for k,v in settings_after.items() if k!='generation-groups:'+pid}==settings_before


def test_legacy_plan_kept_but_cannot_be_newly_adopted_even_with_current_hash(client,montage):
    pid=create(client,montage);src=gg.planning_source(store.project(pid),'scene')
    legacy=copy.deepcopy(src);legacy.pop('plan_contract_version')
    result=separate_result(src,'REF2VA');jid=store.uid()
    inp={'group_plan_source':legacy,'group_plan_hash':store.digest(src)}
    with store.db() as c:
        c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,result,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',
                  (jid,pid,'h3_group_plan','scene','succeeded','manual',store.encode(inp),store.encode(result),store.now(),store.now()))
    before=store.job(jid);cfg=gg.config(pid)
    response=client.post(f'/api/projects/{pid}/generation-groups/plan-adopt/{jid}',json={'revision':cfg['revision']})
    assert response.status_code==400 and '重新安排' in response.text
    assert store.job(jid)==before and gg.config(pid)==cfg
    projection=gg.state(store.project(pid))['plans'][0]
    assert not projection['contract_current'] and projection['stale']
