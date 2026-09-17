"""Saved grouping decisions reach H3 without applying stale mode advice."""
import copy

import pytest

from studio import generation_groups as gg, store, video_workflow, shot_prompts, models
from test_generation_groups import montage, definition
from test_production import client, plan, create


def adopt_arrangement(client, montage, native=False):
    pid=create(client,montage)
    client.post('/api/settings/routing',json={'capability':'h3_group_plan','provider_id':'manual'})
    response=client.post(f'/api/projects/{pid}/jobs',json={'capability':'h3_group_plan','target_id':'scene'})
    assert response.status_code==200,response.text
    job=response.json()['job']
    items=([{k:v for k,v in definition().items() if k!='id'}|{'execution':'native_montage','checks':['Keep the hard cut.']}] if native else [
        {'title':e['id'],'edit_ids':[e['id']],'execution':'separate_source','mode':None,'reference_targets':[],
         'reason':'Critical readable evidence.','checks':['Keep the switch readable.']} for e in montage['edit_plan']])
    result={'summary':'Adopted arrangement.','groups':items}
    response=client.post('/api/jobs/'+job['id']+'/manual',json=result)
    assert response.status_code==200,response.text
    response=client.post(f'/api/projects/{pid}/generation-groups/plan-adopt/{job["id"]}',json={'revision':0})
    assert response.status_code==200,response.text
    return pid,store.job(job['id'])


def test_independent_adoption_reaches_h3_source_and_read_only_state(client,montage):
    pid,job=adopt_arrangement(client,montage)
    before=(store.project(pid),gg.config(pid),store.jobs(pid),video_workflow.config(pid))
    p=client.get('/api/projects/'+pid).json()
    adopted=p['generation_groups']['arrangements'][0]
    assert adopted['status']=='current' and adopted['job_id']==job['id']
    member=adopted['items'][1]['members'][0]
    assert (member['shot_id'],member['source_in'],member['source_out'],member['duration'])==('reaction',3,6,6)
    source=video_workflow.source(p,'reaction')['generation_arrangement']
    assert source['edit_uses'][0]['checks']==['Keep the switch readable.']
    assert source['edit_uses'][0]['source_in']==3
    assert 'entire original source' in source['timing_rule']
    scene,chapter=shot_prompts.locate(p,'reaction',p['delivery'])
    assert shot_prompts.basis(p,scene,chapter)['generation_arrangement']==source
    request=video_workflow.build(p,models.JobRequest(capability='h3_strategy',target_id='reaction'))
    assert 'Keep the switch readable.' in request['prompt'] and 'entire original source' in request['prompt']
    assert before==(store.project(pid),gg.config(pid),store.jobs(pid),video_workflow.config(pid))


def test_new_candidate_does_not_hide_adoption(client,montage):
    pid,job=adopt_arrangement(client,montage)
    newer=copy.deepcopy(job);newer['id']='new-candidate';newer['result']['summary']='Not adopted.'
    state=gg.state(store.project(pid),[newer,job])
    assert state['plans'][0]['id']=='new-candidate' and not state['plans'][0]['adopted']
    assert state['arrangements'][0]['job_id']==job['id']
    assert state['arrangements'][0]['summary']=='Adopted arrangement.'


@pytest.mark.parametrize('fault',['legacy','stale'])
def test_inapplicable_adoption_cannot_enter_prompt_sources(client,montage,fault):
    pid,job=adopt_arrangement(client,montage)
    cfg=gg.config(pid)
    if fault=='legacy':
        job['input']['group_plan_source'].pop('plan_contract_version')
        with store.db() as c:c.execute('UPDATE jobs SET input=? WHERE id=?',(store.encode(job['input']),job['id']))
    else:cfg['plans']['scene']['source_hash']='outdated';store.put_setting('generation-groups:'+pid,cfg)
    p=store.project(pid);a=gg.arrangements(p)[0]
    assert a['status']==fault
    assert all(not item['members'] and not item['group_id'] for item in a['items'])
    assert gg.source_arrangement(p,'shot') is None
    assert 'generation_arrangement' not in video_workflow.source(p,'shot')


def test_native_routes_to_active_group_and_archive_removes_route(client,montage):
    pid,_=adopt_arrangement(client,montage,True)
    p=store.project(pid);a=gg.arrangements(p)[0];gid=a['items'][0]['group_id']
    assert gid in gg.config(pid)['groups']
    assert gg.source_arrangement(p,'shot') is None
    cfg=gg.config(pid);cfg['groups'][gid]['archived']=True;store.put_setting('generation-groups:'+pid,cfg)
    assert gg.arrangements(p)[0]['items'][0]['group_id']==''
