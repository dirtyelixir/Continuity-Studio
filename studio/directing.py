"""Formal director planning, evidence-bound semantic review, and source-clip edit decisions."""
import copy
import json
from . import store, production_methods
from .directing_models import validate_director_plan, validate_directing_review

POLICY = 'studio-directing-v1'


def proposal_plan(job):
    return job['result'].get('production', job['result'])


def scene_source(plan, sid):
    scene = next(s for s in plan['scenes'] if s['id'] == sid)
    shots = [{**s,'keyframes':[f for f in s['keyframes'] if f['moment']!='key']} for s in plan['shots'] if s['scene_id']==sid]
    ids = {scene['location_id']} | {i for s in shots for i in s['entity_ids']}
    chapter=next((c for c in plan.get('chapters',[]) if sid in c['scene_ids']),plan)
    scope=set(chapter.get('scene_ids',[s['id'] for s in plan['scenes']]))
    shot_scope={s['id'] for s in plan['shots'] if s['scene_id'] in scope}
    return {'policy': POLICY, 'style': plan['style'], 'story':chapter['story'],'screenplay':chapter['screenplay'], 'scene': scene, 'shots': shots,
            'canon': [e for e in plan['canon'] if e['id'] in ids],
            'edit_order':[(e['id'],e['shot_id']) for e in plan.get('edit_plan',[]) if e['shot_id'] in shot_scope],
            'edit_plan': [e for e in plan.get('edit_plan', []) if e['shot_id'] in {s['id'] for s in shots}]}


def review_hash(plan):
    # Supplemental stills are reviewed by the image-bound visual storyboard gate.
    plan={**plan,'shots':[{**s,'keyframes':[f for f in s['keyframes'] if f['moment']!='key']} for s in plan['shots']]}
    return store.digest([POLICY, production_methods.snapshot('directing_qc')[1]['hash'], plan])


def build(p, req):
    if req.target_id:
        job = store.job(req.target_id)
        if job['project_id'] != p['id'] or job['capability'] not in ('narrative', 'storyboard') or job['state'] != 'succeeded':
            raise ValueError('請選擇本作品已完成的文字方案作導演審查。')
        plan = proposal_plan(job)
    else:
        plan = p['production']
    if not plan or not any(s.get('director_plan') for s in plan['scenes']):
        raise ValueError('請先建立包含戲劇節拍及導演意圖的新方案。')
    validate_director_plan(plan, require_complete=bool(req.target_id))
    prompt = '''Independently review this frozen Director Plan against its story/screenplay. Return the DirectingReview schema. Review every planned scene beat exactly once, identifying its required communication, linked visual carriers and whether their framing, blocking, performance time and planned edit ranges actually communicate it. Evidence must quote an exact literal excerpt from that scene or its linked shots. Do not count CU/insert/reaction categories or reward filling fields. Check audience knowledge and reveal order across the EDIT sequence, not only source Shot order. A shot may cover several beats serving one primary purpose. Flag SHOT_OVERLOADED when unrelated primary purposes or hidden editorial cuts compete; do not flag a continuous motivated push or punctuation alone. Recommend a specific repair: split, reframe, hold, adjust staging or edit ranges as appropriate. Preserve source events and dialogue. Check that selected edit ranges retain required dialogue/actions and that cut-point states connect; generation endpoints are not automatically the edit endpoints. Missing evidence means uncertain, never pass. Text planning can assess intended readability, not prove generated pixels or precise usable timing. All pass coverage and no issues are required for overall pass. Give Traditional Chinese explanations. No tools or media.\nFROZEN PLAN:\n'''
    prompt=prompt.replace('Evidence must quote an exact literal excerpt from that scene or its linked shots.', 'Each evidence field contains ONLY ONE continuous verbatim source excerpt from its scene or linked shots: no Shot ID prefix, added quotation marks, ellipsis or joined excerpts. Put explanations and additional observations in reason. Issue evidence may also quote its linked edit decision.')
    from .frame_moment_guard import REVIEW as moment_review
    prompt=moment_review+'\n'+prompt
    from . import editorial_records
    editorial_source=editorial_records.review_context(p,plan) if not req.target_id else {}
    if editorial_source:
        prompt+='EDITORIAL ANNOTATIONS (same source version): '+store.encode(editorial_source)+'\nEvaluate audio on its independent scene timeline: a planned J/L-cut is legal; never require speech to stop at a visual cut. Verify speaker/text identity, mouth-only silence, omitted dialogue, intentional offsets and story-state references. Do not infer identity recognition from a generic hand or an unfamiliar face. Annotation evidence is a plan, not generated-media proof. Cite related scene/Shot text as evidence in the existing review schema.\n'
    return {'directing_source': plan, 'editorial_source':editorial_source,
            'directing_request_hash': store.digest([review_hash(plan),editorial_source]) if editorial_source else review_hash(plan),
            'prompt': prompt + store.encode(plan) + '\nREQUEST:\n' + req.feedback, 'images': []}


def run_review(provider, prompt, work, plan):
    """One structural/evidence correction, never a retry to obtain a desired verdict."""
    from . import providers
    def checked(value): return validate_directing_review(value,plan)
    corrected=work/'repair-1'/'result.json'
    if corrected.is_file(): return checked(json.loads(corrected.read_text()))
    saved=work/'result.json'
    try:
        if saved.is_file(): return checked(json.loads(saved.read_text()))
        return checked(providers.run(provider,'directing_qc',prompt,[],work))
    except ValueError as exc:
        if not saved.is_file() or saved.stat().st_size>2_000_000: raise
        repair=prompt+'\nONE STRUCTURAL CORRECTION PASS. Repair only the stated schema/link/evidence errors; preserve substantive findings unless their evidence cannot support them. Do not turn revise/uncertain into pass to satisfy validation. Every evidence field must be ONE uninterrupted literal source excerpt without wrappers, labels, extra quotation marks or joined excerpts. Put commentary in reason.\nERROR: '+str(exc)+'\nPREVIOUS REVIEW:\n'+saved.read_text()
        (work/'repair-reason.txt').write_text(str(exc))
        return checked(providers.run(provider,'directing_qc',repair,[],work/'repair-1'))


def proposal_review(job, jobs=None):
    plan = proposal_plan(job)
    expected = review_hash(plan)
    return next((j for j in (jobs if jobs is not None else store.jobs(job['project_id']))
                 if j['capability'] == 'directing_qc' and j['target_id'] == job['id']
                 and j['input'].get('directing_request_hash') == expected), None)


def require_adoption(job):
    if not job['input'].get('directing_policy'):
        return None  # Historical proposals remain historical, never retroactively certified.
    validate_director_plan(proposal_plan(job), require_complete=True)
    review = proposal_review(job)
    from . import directing_approvals
    human = directing_approvals.proposal(job)
    if human:
        return {'human_approval':human,'ai_review':review}
    if not review or review['state'] != 'succeeded':
        raise ValueError('導演內容審查尚未完成；請先審查此方案。')
    result = validate_directing_review(review['result'], proposal_plan(job))
    if result['verdict'] != 'pass':
        raise ValueError('導演內容審查尚未通過；請按具體問題修訂方案。')
    return review


def record_review(pid, plan, review, job_id, scene_ids=None, editorial_source=None, method_hash=None):
    records = store.setting('directing_reviews:' + pid, {})
    for scene in plan['scenes']:
        sid = scene['id']
        if not scene.get('director_plan') or (scene_ids is not None and sid not in scene_ids):
            continue
        records[sid] = {'hash': store.digest(scene_source(plan, sid)), 'method_hash': production_methods.snapshot('directing_qc')[1]['hash'] if method_hash is None else method_hash,
                        'editorial_hash':store.digest((editorial_source or {}).get(sid,{})),
                        'job_id': job_id, 'review': copy.deepcopy(review)}
    store.put_setting('directing_reviews:' + pid, records)


def record_adoption(job, plan, review_job):
    if review_job and review_job.get('human_approval'):
        from . import directing_approvals
        ai=review_job.get('ai_review')
        if ai and ai['state']=='succeeded':record_adoption(job,plan,ai)
        directing_approvals.inherit(job,plan,review_job['human_approval'])
        return
    if not review_job:
        return
    review = copy.deepcopy(review_job['result'])
    source = proposal_plan(job)
    ids = [s['id'] for s in source['scenes']]
    if job['input'].get('serial_source'):
        prefix = job['target_id'] + '__'
        def local(value): return value if value.startswith(prefix) else prefix + value
        ids = [local(i) for i in ids]
        for c in review['coverage']:
            c['scene_id'] = local(c['scene_id'])
            c['shot_ids'] = [local(i) for i in c['shot_ids']]
        for issue in review['issues']:
            issue['shot_ids'] = [local(i) for i in issue['shot_ids']]
    record_review(job['project_id'], plan, review, review_job['id'], ids,
                  method_hash=review_job['input'].get('production_method', {}).get('hash', ''))


def state(p, jobs=None):
    plan = p.get('production')
    records = store.setting('directing_reviews:' + p['id'], {})
    method_hash = production_methods.snapshot('directing_qc')[1]['hash']
    scenes = []
    from . import directing_approvals
    humans=directing_approvals.scene_approvals(p)
    from . import editorial_records
    editorial_source=editorial_records.review_context(p)
    for scene in (plan or {}).get('scenes', []):
        record = records.get(scene['id'])
        current = bool(record and record['hash'] == store.digest(scene_source(plan, scene['id'])) and record.get('method_hash') == method_hash and record.get('editorial_hash',store.digest({}))==store.digest(editorial_source.get(scene['id'],{})))
        status = ('legacy' if not scene.get('director_plan') else record['review']['verdict'] if current else 'unreviewed')
        human=humans.get(scene['id'])
        scenes.append({'scene_id':scene['id'],'status':'human_approved' if human else status,'ai_status':status,'human_approval':human,'review':record if current else None})
    proposals = {}
    if jobs is not None:
        for j in jobs:
            if j['capability'] in ('narrative', 'storyboard') and j['state'] == 'succeeded' and j['input'].get('directing_policy'):
                r = proposal_review(j, jobs)
                proposals[j['id']] = {'required': True, 'job_id': r['id'] if r else None,
                    'state': r['state'] if r else 'missing', 'result': r['result'] if r and r['state'] == 'succeeded' else None,
                    'error': r.get('error', '') if r else '',
                    'human_approval':directing_approvals.proposal(j), 'approval_source_hash':directing_approvals.basis(p,j)}
    from . import directing_auto
    return {'policy': POLICY, 'scenes': scenes, 'proposals': proposals,
            'current_review':directing_auto.current_review(p,jobs,scenes),
            'approval_source_hash':directing_approvals.basis(p) if plan else None,
            'edit_plan': edit_rows(plan) if plan else []}


def require_scope(p, target_id=''):
    plan = p.get('production')
    if not plan:
        return
    from . import generation_groups
    if generation_groups.is_group(target_id):
        entry = generation_groups.config(p['id'])['groups'].get(target_id)
        if not entry: raise ValueError('找不到此生成分組。')
        target_id = generation_groups.resolve(p, entry['definition'])['scene_id']
    shot = next((s for s in plan['shots'] if s['id'] == target_id or any(f['id'] == target_id for f in s['keyframes'])), None)
    scene_ids = ({shot['scene_id']} if shot else {target_id} if any(s['id'] == target_id for s in plan['scenes']) else {s['id'] for s in plan['scenes']})
    status = state(p)
    pending = [s for s in status['scenes'] if s['scene_id'] in scene_ids and s['status'] not in ('legacy', 'pass', 'human_approved')]
    if pending:
        review = status.get('current_review') or {}
        message = {'queued':'導演內容審查已自動排隊，毋須再次提交。',
                   'running':'正在自動審查導演內容，毋須再次提交。',
                   'deferred':'最新方案會在上一版本審查結束後自動審查。',
                   'awaiting_input':'導演內容審查服務設為人工處理，請提交結果或選擇自動服務。',
                   'failed':'導演內容審查未能完成，請查看原因後重試。',
                   'interrupted':'導演內容審查已中斷，請查看原工作後重試。',
                   'cancelled':'導演內容審查已取消，請重新審查。'}.get(review.get('state'))
        if not message:
            message = '導演內容審查有意見需要處理，請查看結果並修訂方案。' if any(s['status'] in ('revise','uncertain') for s in pending) else '導演內容審查尚未完成。'
        raise ValueError(message+' 可在「故事與章節 → 劇情表達與剪接安排」查看進度或人工批准；通過或人工批准後可製作關鍵幀或 H3。')


def edit_rows(plan):
    shots = {s['id']: s for s in plan['shots']}
    cursor = 0
    rows = []
    for edit in plan.get('edit_plan', []):
        length = round(edit['planned_edit_out'] - edit['planned_edit_in'], 6)
        rows.append({**edit, 'shot_title': shots[edit['shot_id']]['title'],
                     'generation_duration': shots[edit['shot_id']]['duration'],
                     'planned_screen_duration': length, 'timeline_in': cursor,
                     'timeline_out': round(cursor + length, 6), 'timing_status': 'planned_unverified'})
        cursor = round(cursor + length, 6)
    return rows


def edit_manifest(p):
    from . import edit_segments
    return [{**r['planned'],'material_status':r['status'],
        'source_video':{**r['material'],'path':'video/'+r['material']['take_id']+'.mp4'} if r['material'] else None}
        for r in edit_segments.state(p)['segments']]


def report(p):
    lines = ['# 導演規劃與預定剪接', '', '剪接範圍是生成前計劃；尚未逐格驗證或實際裁剪來源影片。', '']
    for scene in p['production']['scenes']:
        lines += ['## ' + scene['title'], '']
        if not scene.get('director_plan'):
            lines += ['舊方案：未建立導演規劃。', '']; continue
        for beat in scene['director_plan']['beats']:
            lines += ['### ' + beat['id'] + ' · ' + beat['event'], '', store.encode(beat['intent']), '']
    lines += ['## 剪接表', '', '|段落|來源 Shot|素材秒數|取用範圍|成片秒數|', '|---|---|---|---|---|']
    for e in edit_rows(p['production']):
        lines.append(f'|{e["id"]}|{e["shot_id"]}|{e["generation_duration"]}|{e["planned_edit_in"]}–{e["planned_edit_out"]}|{e["planned_screen_duration"]}|')
    return '\n'.join(lines)
