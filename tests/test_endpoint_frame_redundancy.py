import copy
import json

import pytest
from pydantic import ValidationError

from studio import models, store, providers
from test_production import plan, client


@pytest.mark.parametrize('moment,index,time', [('start',0,0.0),('end',1,6.0)])
@pytest.mark.parametrize('fields', [('source_time',),('state',),('source_time','state')])
def test_exact_redundancy_preserves_output_and_input(plan,moment,index,time,fields):
    candidate=copy.deepcopy(plan)
    shot=candidate['shots'][0];frame=shot['keyframes'][index]
    if 'source_time' in fields:frame['source_time']=time
    if 'state' in fields:frame['state']=copy.deepcopy(shot[moment+'_state'])
    before=json.dumps(candidate)
    assert models.Production.model_validate(candidate).model_dump()==plan
    assert json.dumps(candidate)==before


@pytest.mark.parametrize('index,value', [(0,.1),(0,'0'),(0,False),(0,True),(0,float('nan')),(0,float('inf')),(1,0),(1,5.99),(1,'6'),(1,True)])
def test_wrong_or_coerced_times_remain_invalid(plan,index,value):
    shot=plan['shots'][0];frame=shot['keyframes'][index]
    frame.update(source_time=value,state=copy.deepcopy(shot[frame['moment']+'_state']))
    with pytest.raises(ValidationError):models.Production.model_validate(plan)


@pytest.mark.parametrize('index,time',[(0,0),(1,6)])
def test_conflicting_state_is_not_discarded(plan,index,time):
    frame=plan['shots'][0]['keyframes'][index]
    frame.update(source_time=time,state=[{'entity_id':'ada','key':'hand','value':'different'}])
    before=copy.deepcopy(plan)
    with pytest.raises(ValidationError,match='Endpoint frames'):models.Production.model_validate(plan)
    assert plan==before


def test_null_legacy_and_interior_frames_unchanged(plan):
    original=copy.deepcopy(plan)
    for frame in plan['shots'][0]['keyframes']:frame.update(source_time=None,state=None)
    assert models.Production.model_validate(plan).model_dump()==original
    middle={'id':'middle','moment':'key','description':'One instant','source_time':2.5,'state':[]}
    plan['shots'][0]['keyframes'].append(middle)
    assert models.Production.model_validate(plan).model_dump()['shots'][0]['keyframes'][-1]==middle
    middle['source_time']=0
    with pytest.raises(ValidationError,match='inside'):models.Production.model_validate(plan)


def test_standalone_frame_stays_strict(plan):
    frame={**plan['shots'][0]['keyframes'][0],'source_time':0,'state':plan['shots'][0]['start_state']}
    with pytest.raises(ValidationError,match='Endpoint frames'):models.Frame.model_validate(frame)


def test_recovery_preserves_raw_and_never_regenerates_narrative(client,plan,monkeypatch):
    pid=client.post('/api/projects',json={'title':'Recovery','idea':'Lamp'}).json()['id']
    jid='endpoint-recovery';work=store.DATA/'jobs'/jid;work.mkdir(parents=True)
    candidate=copy.deepcopy(plan)
    candidate['shots'][0]['keyframes'][0].update(source_time=0,state=copy.deepcopy(candidate['shots'][0]['start_state']))
    raw=json.dumps(candidate);(work/'result.json').write_text(raw)
    with store.db() as c:
        c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,error,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (jid,pid,'narrative','','failed','astra',store.encode({'revision':0}),'original validation failure',store.now(),store.now()))
    monkeypatch.setattr(providers,'run',lambda *a,**k:pytest.fail('Unexpected provider call in controlled recovery'))
    result=client.post('/api/jobs/'+jid+'/recover',json={})
    assert result.status_code==200,result.text
    assert result.json()['state']=='succeeded' and result.json()['result']==plan
    assert (work/'result.json').read_text()==raw
    assert store.project(pid)['revision']==0
    assert client.post('/api/jobs/'+jid+'/recover',json={}).status_code==400


def test_recovery_tracks_running_and_preserves_latest_failure(client,plan,monkeypatch):
    from studio import engine
    pid=client.post('/api/projects',json={'title':'Recovery','idea':'Lamp'}).json()['id']
    jid='failed-recovery';work=store.DATA/'jobs'/jid;work.mkdir(parents=True)
    (work/'result.json').write_text(json.dumps(plan))
    with store.db() as c:
        c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,error,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (jid,pid,'narrative','','failed','astra','{}','Original format error',store.now(),store.now()))
    def fail(job,result):
        assert store.job(jid)['state']=='running'
        raise ValueError('Actual semantic conflict')
    monkeypatch.setattr(engine,'finish',fail)
    response=client.post('/api/jobs/'+jid+'/recover',json={})
    assert response.status_code==400
    assert store.job(jid)['state']=='failed' and store.job(jid)['error']=='Actual semantic conflict'
    receipt=json.loads(next((work/'recovery-attempts').glob('*/receipt.json')).read_text())
    assert receipt['original_error']=='Original format error' and receipt['state']=='failed'
    assert json.loads((work/'result.json').read_text())==plan
