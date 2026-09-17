"""Automatic review orchestration uses isolated saved sources and no providers."""
import copy
import pytest
from studio import directing, directing_auto, engine, models, store, production_methods
from test_production import client, plan, create
from test_directing import directed, reviewed, proposal_job, check_proposal


def reviews(pid):
    return [j for j in store.jobs(pid) if j['capability']=='directing_qc' and not j['target_id']]


def change(pid):
    p=store.project(pid);d=copy.deepcopy(p['production'])
    d['shots'][0]['direction']['readability']+=' 保留更多反應時間。'
    return engine.save_plan(pid,d,p['revision'],'Changed directing intent')


def test_save_queues_once_and_views_are_read_only(client,plan):
    pid=create(client,directed(plan));j=reviews(pid)[0]
    assert j['state']=='queued'
    for _ in range(2):
        directing_auto.reconcile(pid)
        p=client.get('/api/projects/'+pid).json()
        assert p['directing']['current_review']['job_id']==j['id']
        assert p['directing']['scenes'][0]['status']=='unreviewed'
    engine.save_plan(pid,p['production'],p['revision'],'Unrelated revision')
    assert len(reviews(pid))==1
    engine.finish(j,reviewed(j['input']['directing_source']))
    change(pid)
    assert len(reviews(pid))==2
    assert directing.state(store.project(pid))['current_review']['state']=='queued'


def test_newer_save_waits_for_old_source_then_queues_latest(client,plan):
    pid=create(client,directed(plan));old=reviews(pid)[0]
    change(pid);change(pid)
    state=directing.state(store.project(pid))
    assert state['current_review']['state']=='deferred'
    assert state['current_review']['result'] is None
    assert len(reviews(pid))==1
    engine.finish(old,reviewed(old['input']['directing_source']))
    fresh=reviews(pid)[0]
    assert len(reviews(pid))==2 and fresh['id']!=old['id']
    assert fresh['input']['directing_source']==store.project(pid)['production']
    assert directing.state(store.project(pid))['scenes'][0]['status']=='unreviewed'
    with pytest.raises(ValueError,match='審查'):
        directing.require_scope(store.project(pid),'start')


@pytest.mark.parametrize('terminal',['failed','interrupted','cancelled','revise','uncertain'])
def test_terminal_same_source_does_not_auto_retry(client,plan,terminal):
    pid=create(client,directed(plan));j=reviews(pid)[0]
    if terminal in ('revise','uncertain'):
        engine.finish(j,reviewed(j['input']['directing_source'],terminal))
    else:
        with store.db() as c:c.execute('UPDATE jobs SET state=? WHERE id=?',(terminal,j['id']))
        directing_auto.on_terminal(j)
    directing_auto.reconcile_all()
    assert len(reviews(pid))==1
    assert directing.state(store.project(pid))['current_review']['state']==('succeeded' if terminal in ('revise','uncertain') else terminal)


@pytest.mark.parametrize('terminal',['failed','cancelled'])
def test_failed_or_cancelled_old_job_releases_latest(client,plan,monkeypatch,terminal):
    pid=create(client,directed(plan));j=reviews(pid)[0];change(pid)
    if terminal=='cancelled':
        assert client.post('/api/jobs/'+j['id']+'/cancel').status_code==200
    else:
        def fail(*args,**kwargs):raise RuntimeError('Isolated provider failure')
        monkeypatch.setattr(directing,'run_review',fail)
        engine.execute(j['id'])
    assert store.job(j['id'])['state']==terminal
    assert len(reviews(pid))==2
    assert reviews(pid)[0]['input']['directing_source']==store.project(pid)['production']


def test_startup_reconciles_method_change_and_missing_review(client,plan,monkeypatch):
    pid=create(client,directed(plan));j=reviews(pid)[0]
    engine.finish(j,reviewed(j['input']['directing_source']))
    original=production_methods.snapshot
    def changed(cap):
        text,meta=original(cap);return text,{**meta,'hash':'test-new-method'}
    monkeypatch.setattr(production_methods,'snapshot',changed)
    engine.start_pending();engine.start_pending()
    assert len(reviews(pid))==2
    assert directing.state(store.project(pid))['scenes'][0]['status']=='unreviewed'
    # Simulate a historical save that predated the automatic hook.
    other=create(client,plan)
    with store.db() as c:c.execute('UPDATE projects SET production=? WHERE id=?',(store.encode(directed(plan)),other))
    engine.start_pending()
    assert len(reviews(other))==1


def test_legacy_deleted_and_passed_proposal_adoption_are_not_requeued(client,plan):
    legacy=create(client,plan);assert not reviews(legacy)
    p,j=proposal_job(client,directed(plan));check_proposal(client,p,j,reviewed(directed(plan)))
    assert client.post('/api/jobs/'+j['id']+'/adopt',json={'revision':0}).status_code==200
    assert not reviews(p['id'])
    assert directing.state(store.project(p['id']))['current_review']['result']['verdict']=='pass'
    with store.db() as c:c.execute('UPDATE projects SET production=?,deleted_at=? WHERE id=?',(store.encode(directed(plan)),store.now(),legacy))
    directing_auto.reconcile_all();directing_auto.reconcile(legacy)
    assert not reviews(legacy)


def test_manual_handoff_and_durable_submission_failure(client,plan,monkeypatch):
    client.post('/api/settings/routing',json={'capability':'directing_qc','provider_id':'manual'})
    pid=create(client,directed(plan))
    assert directing.state(store.project(pid))['current_review']['state']=='awaiting_input'
    other=create(client,plan);original=engine.enqueue;calls=[]
    def fail(*args):calls.append(args);raise ValueError('Test unavailable review service')
    monkeypatch.setattr(engine,'enqueue',fail)
    p=engine.save_plan(other,directed(plan),1,'Saved despite review outage')
    assert p['revision']==2
    assert directing.state(p)['current_review']['error']=='Test unavailable review service'
    directing_auto.reconcile(other);assert len(calls)==1
    monkeypatch.setattr(engine,'enqueue',original)
    # Explicit retry can clear the failed-submission display with a real receipt.
    engine.enqueue(other,models.JobRequest(capability='directing_qc'))
    assert directing.state(p)['current_review']['state']=='awaiting_input'


def test_concurrent_reconciliation_and_editorial_source_change(client,plan,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    pid=create(client,directed(plan));j=reviews(pid)[0]
    engine.finish(j,reviewed(j['input']['directing_source']))
    from studio import editorial_records
    monkeypatch.setattr(editorial_records,'review_context',lambda *args:{'scene':{'audio':'changed test cue'}})
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _:directing_auto.reconcile(pid),range(4)))
    assert len(reviews(pid))==2
    latest=reviews(pid)[0]
    assert latest['input']['editorial_source']=={'scene':{'audio':'changed test cue'}}
    assert directing_auto.fingerprint(store.project(pid))==latest['input']['directing_request_hash']
