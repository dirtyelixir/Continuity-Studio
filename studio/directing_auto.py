"""Continue saved directing intent into one independent review per frozen source.

Only save/startup/terminal hooks write. Read-only views never submit work. A
failed or non-passing attempt is a result to handle, not an automatic retry loop.
"""
from . import store, directing, editorial_records

ACTIVE = {'queued', 'running', 'awaiting_input'}


def fingerprint(p):
    plan = p.get('production')
    if not plan or not any(s.get('director_plan') for s in plan['scenes']):
        return None
    annotations = editorial_records.review_context(p)
    basis = directing.review_hash(plan)
    return store.digest([basis, annotations]) if annotations else basis


def error_key(pid, basis):
    return 'directing_auto_error:' + pid + ':' + basis


def current_review(p, jobs=None, scenes=None):
    """Return current-source receipt; never show an old verdict as current."""
    basis = fingerprint(p)
    if basis is None:
        return None
    jobs = store.jobs(p['id']) if jobs is None else jobs
    reviews = [j for j in jobs if j['capability'] == 'directing_qc' and not j['target_id']]
    match = next((j for j in reviews if j['input'].get('directing_request_hash') == basis), None)
    if match:
        from . import directing_pipeline, engine
        return {'state':match['state'], 'job_id':match['id'], 'error':match.get('error',''),
                'result':match['result'] if match['state'] == 'succeeded' else None,
                'progress':directing_pipeline.progress(match),
                'resumable':directing_pipeline.can_resume(match, p['revision'])}
    # Passing proposal adoption may certify all scenes without a whole-plan job.
    formal = [s for s in (scenes or []) if s['status'] != 'legacy']
    if formal and all(s['status'] == 'pass' for s in formal):
        return {'state':'succeeded', 'job_id':None, 'error':'', 'result':{'verdict':'pass'}}
    failure = store.setting(error_key(p['id'], basis))
    if failure:
        return {'state':'failed', 'job_id':None, 'error':failure['error'], 'result':None}
    previous = next((j for j in reviews if j['state'] in ACTIVE), None)
    if previous:
        return {'state':'deferred', 'job_id':previous['id'], 'error':'', 'result':None}
    return {'state':'missing', 'job_id':None, 'error':'', 'result':None}


def reconcile(pid):
    from . import engine, models
    with engine.LOCK:
        p = store.project(pid, include_deleted=True)
        if p.get('deleted_at') is not None:
            return
        basis = fingerprint(p)
        if basis is None:
            return
        status = directing.state(p, store.jobs(pid))
        if not any(s['status'] == 'unreviewed' for s in status['scenes']):
            return  # Retain substantive verdicts and already certified adoption.
        receipt = status['current_review']
        if receipt['state'] != 'missing':
            return receipt
        try:
            return engine.enqueue(pid, models.JobRequest(capability='directing_qc'))
        except Exception as exc:
            # The production save already succeeded. Preserve one actionable error
            # for this exact source, including failures before a job can be created.
            error = str(exc)[:1500]
            store.put_setting(error_key(pid, basis), {'error':error, 'created':store.now()})
            with store.db() as c:
                store.event(c, pid, 'directing_review_error', error)
            return {'state':'failed', 'job_id':None, 'error':error, 'result':None}


def after_save(pid):
    """A review scheduling error must never report a committed plan as unsaved."""
    try:
        return reconcile(pid)
    except Exception as exc:
        with store.db() as c:
            store.event(c, pid, 'directing_review_error', str(exc)[:1500])


def reconcile_all():
    with store.db() as c:
        ids = [r['id'] for r in c.execute('SELECT id FROM projects WHERE deleted_at IS NULL AND production IS NOT NULL')]
    for pid in ids:
        after_save(pid)


def on_terminal(job):
    if job['capability'] == 'directing_qc' and not job['target_id']:
        after_save(job['project_id'])
