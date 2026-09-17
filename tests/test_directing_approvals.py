import copy
import pytest
from studio import store,engine,directing,directing_auto,directing_approvals,models,production_methods
from test_production import client,plan,create,add_asset
from test_directing import directed,reviewed,proposal_job,check_proposal


def approve(client,pid,job=None,note=''):
    p=store.project(pid)
    return client.post('/api/projects/'+pid+'/directing-approval',json={'revision':p['revision'],'source_hash':directing_approvals.basis(p,job),'proposal_id':job['id'] if job else '', 'note':note})


def test_human_overrides_failed_creative_review_without_changing_it(client,plan):
    d=directed(plan);pid=create(client,d);j=store.jobs(pid)[0]
    engine.finish(j,reviewed(d,'revise'));original=store.job(j['id'])
    with pytest.raises(ValueError):directing.require_scope(store.project(pid),'start')
    r=approve(client,pid,note='接受這個構圖');assert r.status_code==200,r.text
    state=client.get('/api/projects/'+pid).json()['directing']
    assert state['scenes'][0]['status']=='human_approved'
    assert state['scenes'][0]['ai_status']=='revise'
    assert state['scenes'][0]['review']['review']['verdict']=='revise'
    assert store.job(j['id'])==original
    for target in ('ada','room'):add_asset(pid,d,target)
    engine.build_input(store.project(pid),models.JobRequest(capability='h3',target_id='shot'))
    directing_auto.reconcile(pid);assert len(store.jobs(pid))==1
    assert approve(client,pid).json()['id']==r.json()['id']


@pytest.mark.parametrize('state',['queued','running','failed','interrupted','cancelled','awaiting_input'])
def test_human_can_decide_without_completed_ai_result_and_late_ai_cannot_revoke(client,plan,state):
    d=directed(plan);pid=create(client,d);j=store.jobs(pid)[0]
    with store.db() as c:c.execute('UPDATE jobs SET state=? WHERE id=?',(state,j['id']))
    assert approve(client,pid).status_code==200
    directing.require_scope(store.project(pid),'start')
    engine.finish(j,reviewed(d,'revise'))
    assert directing.state(store.project(pid))['scenes'][0]['status']=='human_approved'


def test_source_and_revision_guards_and_method_only_change(client,plan,monkeypatch):
    d=directed(plan);pid=create(client,d);p=store.project(pid)
    payload={'revision':p['revision'],'source_hash':directing_approvals.basis(p)}
    assert client.post('/api/projects/'+pid+'/directing-approval',json={**payload,'source_hash':'wrong'}).status_code==400
    assert approve(client,pid).status_code==200
    old_snapshot=production_methods.snapshot
    def changed(cap):
        text,meta=old_snapshot(cap);return text,{**meta,'hash':'new-method'}
    monkeypatch.setattr(production_methods,'snapshot',changed)
    directing.require_scope(store.project(pid),'start')
    updated=copy.deepcopy(d);updated['shots'][0]['direction']['readability']+=' closer'
    engine.save_plan(pid,updated,p['revision'],'new direction')
    assert client.post('/api/projects/'+pid+'/directing-approval',json=payload).status_code==400
    assert directing.state(store.project(pid))['scenes'][0]['status']=='unreviewed'
    with pytest.raises(ValueError):directing.require_scope(store.project(pid),'start')


def test_proposal_human_approval_can_adopt_and_inherits_honest_decision(client,plan):
    d=directed(plan);p,j=proposal_job(client,d);q=check_proposal(client,p,j,reviewed(d,'revise'))
    assert client.post('/api/jobs/'+j['id']+'/adopt',json={'revision':0}).status_code==400
    assert approve(client,p['id'],j).status_code==200
    api=client.get('/api/jobs/'+j['id']).json()
    assert api['directing_review']['human_approval']['actor']=='user'
    assert api['directing_review']['result']['verdict']=='revise'
    response=client.post('/api/jobs/'+j['id']+'/adopt',json={'revision':0})
    assert response.status_code==200,response.text
    current=store.project(p['id']);directing.require_scope(current,'start')
    assert directing.state(current)['scenes'][0]['status']=='human_approved'
    assert store.job(q['id'])['result']['verdict']=='revise'
    assert len(directing_approvals.history(p['id']))==2


def test_reject_other_project_and_incomplete_proposal(client,plan):
    p,j=proposal_job(client,directed(plan));other=create(client,directed(plan))
    assert approve(client,other,j).status_code==400
    payload={'revision':0,'source_hash':'bad','proposal_id':store.jobs(p['id'])[0]['id']}
    assert client.post('/api/projects/'+p['id']+'/directing-approval',json=payload).status_code==400


def test_editorial_changes_invalidate_human_scope(client,plan,monkeypatch):
    from studio import editorial_records
    pid=create(client,directed(plan));assert approve(client,pid).status_code==200
    monkeypatch.setattr(editorial_records,'review_context',lambda *args:{'scene':{'cue':'different timing'}})
    with pytest.raises(ValueError):directing.require_scope(store.project(pid),'start')


def test_chapter_approval_only_inherits_adopted_scene_ids(client,plan):
    from studio import serial_story
    p=client.post('/api/projects',json={'title':'Series','idea':'Ongoing story','source_kind':'outline'}).json()
    chapter=serial_story.save_draft(p['id'],models.ChapterDraft(title='One',brief='Fix lamp.'))
    d=directed(plan)
    fake={'id':'chapter-proposal','project_id':p['id'],'target_id':chapter['id'],'input':{'revision':0,'serial_source':True},'result':d}
    approval={'id':'human-original','note':'Keep this scene','review_job_id':'review-original','ai_verdict':'revise'}
    merged=serial_story.merge(store.project(p['id']),d,serial_story.snapshot(store.project(p['id']),chapter))
    engine.save_plan(p['id'],merged,0,'adopt test chapter')
    inherited=directing_approvals.inherit(fake,merged,approval)
    assert set(inherited['scene_hashes'])=={chapter['id']+'__scene'}
    assert inherited['review_job_id']=='review-original'
    assert directing.state(store.project(p['id']))['scenes'][0]['status']=='human_approved'
