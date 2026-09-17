"""Version-bound human directing decisions, independent of AI review verdicts."""
from . import store, directing, editorial_records


def basis(p, job=None):
    if job:
        return store.digest([job['id'], job['input']['revision'], directing.proposal_plan(job)])
    return store.digest([p['production'], editorial_records.review_context(p)])


def history(pid):
    return store.setting('directing_human_approvals:'+pid, [])


def proposal(job):
    p=store.project(job['project_id'])
    if p['revision']!=job['input']['revision']:return None
    expected=basis(p,job)
    return next((r for r in reversed(history(p['id'])) if r.get('proposal_id')==job['id'] and r['source_hash']==expected),None)


def scene_approvals(p):
    plan=p.get('production')
    if not plan:return {}
    annotations=editorial_records.review_context(p)
    expected={s['id']:store.digest([directing.scene_source(plan,s['id']),annotations.get(s['id'],{})]) for s in plan['scenes'] if s.get('director_plan')}
    found={}
    for record in reversed(history(p['id'])):
        for sid,value in record.get('scene_hashes',{}).items():
            if sid not in found and expected.get(sid)==value:found[sid]=record
    return found


def persist(p, note, job=None, scene_ids=None, inherited=None):
    plan=directing.proposal_plan(job) if job else p['production']
    from . import directing_auto
    current_hash=None if job else directing_auto.fingerprint(p)
    review=directing.proposal_review(job) if job else next((j for j in store.jobs(p['id']) if j['capability']=='directing_qc' and not j['target_id'] and j['input'].get('directing_request_hash')==current_hash),None)
    record={'id':store.uid(),'actor':'user','approved_at':store.now(),'revision':p['revision'],
            'source_hash':basis(p,job),'proposal_id':job['id'] if job else '', 'note':note,
            'review_job_id':review['id'] if review else None,
            'ai_verdict':(review.get('result') or {}).get('verdict') if review and review['state']=='succeeded' else None,
            'inherited_from':inherited['id'] if inherited else None}
    if inherited:
        record.update(review_job_id=inherited['review_job_id'],ai_verdict=inherited['ai_verdict'])
    if not job:
        annotations=editorial_records.review_context(p)
        record['scene_hashes']={s['id']:store.digest([directing.scene_source(plan,s['id']),annotations.get(s['id'],{})]) for s in plan['scenes'] if s.get('director_plan') and (scene_ids is None or s['id'] in scene_ids)}
    records=history(p['id']);records.append(record)
    with store.db() as c:
        c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('directing_human_approvals:'+p['id'],store.encode(records)))
        store.event(c,p['id'],'directing_human_approval','人工批准導演方案 · '+record['id'])
    return record


def approve(pid, revision, source_hash, proposal_id='', note=''):
    from . import engine
    with engine.LOCK:
        p=store.project(pid)
        if p['revision']!=revision:raise ValueError('作品已更新，請重新查看方案後批准。')
        job=store.job(proposal_id) if proposal_id else None
        if job and (job['project_id']!=pid or job['capability'] not in ('narrative','storyboard') or job['state']!='succeeded' or job['input']['revision']!=revision):
            raise ValueError('請選擇本作品目前版本已完成的製作方案。')
        plan=directing.proposal_plan(job) if job else p['production']
        if not plan or not any(s.get('director_plan') for s in plan['scenes']):raise ValueError('尚未有可批准的導演方案。')
        directing.validate_director_plan(plan,require_complete=bool(job))
        if source_hash!=basis(p,job):raise ValueError('方案內容已更新，請重新查看後批准。')
        existing=proposal(job) if job else next((r for r in reversed(history(pid)) if not r.get('proposal_id') and r['source_hash']==source_hash),None)
        return existing or persist(p,note,job)


def inherit(job, plan, approval):
    ids=[s['id'] for s in directing.proposal_plan(job)['scenes']]
    if job['input'].get('serial_source'):
        prefix=job['target_id']+'__'
        ids=[sid if sid.startswith(prefix) else prefix+sid for sid in ids]
    return persist(store.project(job['project_id']),approval['note'],scene_ids=ids,inherited=approval)
