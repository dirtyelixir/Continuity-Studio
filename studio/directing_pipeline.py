"""Budgeted directing review over frozen originals; only complete aggregate is a review."""
import copy
import json
from pydantic import Field
from . import store, providers, context_limits
from .directing_models import Strict, DirectingReview, DirectingIssue, validate_directing_review, has_evidence
from typing import Literal

VERSION = 'directing-stages-v1'


class CrossCheck(Strict):
    id: str = Field(min_length=1)
    verdict: Literal['pass', 'revise', 'uncertain']
    evidence: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)


class CrossReview(Strict):
    verdict: Literal['pass', 'revise', 'uncertain']
    summary: str = Field(min_length=1)
    checks: list[CrossCheck]
    issues: list[DirectingIssue]


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def atomic(path, value):
    from .chapter_pipeline import atomic_json
    atomic_json(path, value)


def schema(provider, cap):
    value = providers.result_model(cap).model_json_schema()
    return providers.strict_schema(value) if provider['kind'] == 'codex' else value


def answer_items(plan):
    """Deterministic count of answer lines the aggregate review must report."""
    beats=sum(len((s.get('director_plan') or {}).get('beats',[])) for s in plan['scenes'])
    return beats+len(plan.get('edit_plan',[]))+len(plan.get('chapters',[]))

# One monolithic review answer needs a bounded share of the output budget: each answer
# item (beat coverage row, check) plus one summary line is one answer line at ~3000
# UTF-8-byte units (the existing beat batch unit), and one full output reservation is
# spent on the answer. A reasoning model may additionally spend the rest of the budget on
# reasoning before any answer (the 2026-09-14 zero-answer-character failure), so the
# estimate is compared against half of max_output_tokens rather than the whole budget.
OUTPUT_ANSWER_LINE_UNITS = 3000
OUTPUT_BUDGET_SHARE = 2


def output_risk(provider, plan):
    policy=provider['context_policy']
    return (answer_items(plan)+1)*OUTPUT_ANSWER_LINE_UNITS>policy['max_output_tokens']//OUTPUT_BUDGET_SHARE


def needs_stages(provider, prompt, plan):
    policy=provider['context_policy']
    beats=sum(len((s.get('director_plan') or {}).get('beats',[])) for s in plan['scenes'])
    if beats>max(1,min(4,policy['max_output_tokens']//3000)):
        return True
    # A huge input window (e.g. 1,048,576) never triggers the overflow check below, so a
    # review whose required answer cannot fit the output budget still needs the bounded
    # staged path; the old beat rule alone capped at 4 beats regardless of answer size.
    if output_risk(provider,plan):
        return True
    # Exact native counting remains in worker admission; no enqueue-time model load.
    if policy['tokenizer']=='llama_cpp':
        return True
    tokens=context_limits.count(provider,prompt,schema(provider,'directing_qc'),policy)
    return not context_limits.fits(tokens,policy)


def progress(job):
    if not job['input'].get('directing_pipeline'):
        return None
    try:
        return json.loads((store.DATA/'jobs'/job['id']/'review-progress.json').read_text())
    except (OSError, ValueError):
        return {'kind': 'directing_stages', 'label': '正在計算審查批次', 'completed': 0, 'total': 0}


def cancelled(work):
    if (work/'cancel-requested').exists():
        raise RuntimeError('使用者已取消工作。')


def prepare(provider, prompt, plan):
    """Plan all required calls before spending; never clip an atomic review unit."""
    policy = provider['context_policy']
    original = store.encode(plan)
    if prompt.count(original) != 1:
        raise ValueError('未能識別凍結審查原文；請建立新的審查工作。')
    instructions = prompt.replace(original, '[Frozen original is partitioned below; this is a scoped review.]', 1)
    baseline = {k: plan[k] for k in ('title', 'logline', 'style', 'story', 'screenplay', 'canon') if k in plan}
    # Chapter narrative remains original, independent of top-level aggregation.
    baseline['chapters'] = [{k: c[k] for k in ('id', 'title', 'story', 'screenplay', 'scene_ids') if k in c} for c in plan.get('chapters', [])]
    tasks = []
    def add(cap, payload, keys, label, scope):
        task_prompt = instructions + '\nSCOPED REVIEW CONTRACT (coverage is limited to requested IDs):\n' + encode(payload)
        tokens = context_limits.count(provider, task_prompt, schema(provider, cap), policy)
        return {'capability': cap, 'prompt': task_prompt, 'keys': keys, 'label': label,
                'scope': scope, 'input_tokens': tokens, 'fits': context_limits.fits(tokens, policy)}
    def required(task):
        if not task['fits']:
            raise ValueError('最小必要審查單元仍超出預算：'+task['label']+'。請調整所選模型容量或作品範圍；原文及已保存成果保留。')
        tasks.append(task)
    beat_limit = max(1, min(4, policy['max_output_tokens']//3000))
    # A small complete review retains the original request and one normal result.
    # A review whose required answer exceeds its own output share must NOT collapse back
    # into one call just because its input happens to fit a very large window.
    full_count=context_limits.count(provider,prompt,schema(provider,'directing_qc'),policy)
    keys=[[s['id'],b['id']] for s in plan['scenes'] for b in (s.get('director_plan') or {}).get('beats',[])]
    if len(keys)<=beat_limit and context_limits.fits(full_count,policy) and not output_risk(provider,plan):
        return [{'capability':'directing_qc','prompt':prompt,'keys':keys,'label':'完整導演審查','scope':plan,'input_tokens':full_count,'fits':True}]
    for scene in plan['scenes']:
        beats = (scene.get('director_plan') or {}).get('beats', [])
        cursor = 0
        while cursor < len(beats):
            take = min(beat_limit, len(beats)-cursor)
            while True:
                selected = beats[cursor:cursor+take]
                ids = {b['id'] for b in selected}
                shots = [s for s in plan['shots'] if s['scene_id']==scene['id'] and ids.intersection(s['direction']['beat_ids'])]
                # Retain every beat referenced by those full shots, including competing purposes.
                linked = ids | {b for s in shots for b in s['direction']['beat_ids']}
                focused = {**scene, 'director_plan': {**scene['director_plan'], 'beats': [b for b in beats if b['id'] in linked]}}
                scope = {**baseline, 'scenes': [focused], 'shots': shots,
                         'edit_plan': [e for e in plan.get('edit_plan', []) if e['shot_id'] in {s['id'] for s in shots}]}
                keys = [[scene['id'], b['id']] for b in selected]
                payload = {'task': 'Review ONLY requested scene/beat IDs exactly once using DirectingReview. All linked shots are complete originals. Check overloaded purposes, exact frame moments, dialogue/actions and edit ranges. Other linked beats are context, not additional coverage. Missing information means uncertain. Keep evidence to one literal excerpt. Do not certify pixels.',
                           'requested_coverage': keys, 'original_source': scope}
                task = add('directing_qc', payload, keys, scene.get('title',scene['id'])+' · 節拍 '+str(cursor+1)+'–'+str(cursor+take), scope)
                if task['fits'] or take == 1: break
                take -= 1
            required(task)
            cursor += take
    # Direct-source global navigation, never a model summary. Every beat and edit use remains visible.
    navigation = [{'scene_id': s['id'], 'beats': [{'id': b['id'], 'event': b['event'], 'audience_must_learn': b['intent']['audience_must_learn'], 'shot_ids':[shot['id'] for shot in plan['shots'] if shot['scene_id']==s['id'] and b['id'] in (shot.get('direction') or {}).get('beat_ids',[])]} for b in (s.get('director_plan') or {}).get('beats', [])],
                   'reveal_order': (s.get('director_plan') or {}).get('reveal_order', [])} for s in plan['scenes']]
    edits = plan.get('edit_plan', [])
    order = [[e['id'], e['shot_id'], e['planned_edit_in'], e['planned_edit_out']] for e in edits]
    global_base = {k:v for k,v in baseline.items() if k!='canon'}
    by_shot = {s['id']:s for s in plan['shots']}
    # Global timeline plus each actual adjacent edit use (including reused/nonconsecutive sources).
    windows = [('global', [])] + [('cut-'+str(n), edits[max(0,n-1):n+1]) for n in range(len(edits))]
    for key, window in windows:
        selected = [by_shot[sid] for sid in dict.fromkeys(e['shot_id'] for e in window)]
        # Full local shots already reviewed above. Boundary tasks use original timing/state/communication fields.
        fields = ('id','scene_id','title','duration','action','beats','dialogue','start_state','end_state','direction','shot_purpose','transition_note')
        projected = [{k:s[k] for k in fields if k in s} for s in selected]
        entity_ids = {eid for s in selected for eid in s.get('entity_ids', [])}
        scene_ids = {s['scene_id'] for s in selected}
        entity_ids |= {s['location_id'] for s in plan['scenes'] if s['id'] in scene_ids}
        payload = {'task': 'Return CrossReview, not DirectingReview. Complete every requested check exactly once. Global review receives the complete original story and screenplay. Cut review receives the complete screenplay; story-wide interpretation belongs to the separate global check. Every task receives the entire ACTUAL edit order. The global check also receives all beat events/learning requirements and their carrier shot IDs; cut checks receive the exact boundary originals, with global reveal review performed separately. For global check verify reveal ordering and missing/duplicated story communication globally. For cut checks assess the selected adjacent edit uses including within-shot cut times, original action/dialogue, state continuity and J/L audio legality. Do not infer edit endpoint states from generation endpoints; use timed beats. Missing evidence means uncertain. Quote one exact original excerpt per check and issue. Local detailed beat review is separate; never repeat coverage. Keep explanations concise; no tools or media.',
                   'phase_authority': 'This is one phase of a mandatory complete audit, NOT a standalone full-plan review. Every local beat phase must finish before this phase executes. Those phases receive COMPLETE original shots, keyframes, all linked beat intents, canon, story and screenplay, and own frozen-moment synchronization, visual readability, framing and within-shot performance review. This phase owns ONLY '+('global narrative/reveal order across the actual edit sequence.' if key=='global' else 'the requested adjacent edit boundaries, retained action/dialogue and cut-point continuity.')+' Apply mandatory craft rules only within that responsibility. Do not issue missing-context findings or request that the user supply keyframes/full shot plans already assigned to the local phases. Do not certify or re-review another phase. Preserve real issues in your own scope; if its supplied evidence is inconclusive, return uncertain with a specific in-scope reason.',
                   'requested_checks': [key], 'check_windows': {key:[e['id'] for e in window]}, 'original_narrative': global_base if key=='global' else {k:v for k,v in global_base.items() if k!='story'}, 'all_scene_beats': navigation if key=='global' else [],
                   'edit_order_columns': ['edit_id','shot_id','in','out'], 'complete_edit_order': order,
                   'selected_edits': window, 'original_shot_boundaries': projected,
                   'canon': [e for e in plan.get('canon',[]) if e['id'] in entity_ids]}
        # Evidence may only cite material actually supplied to this call.
        scope = {'payload': payload, 'shot_ids': [s['id'] for s in selected]}
        required(add('directing_cross_qc', payload, [key], '跨場揭示與剪接全局核對' if key=='global' else '剪接接點 '+str(int(key[4:])+1), scope))
    # Greedily batch adjacent boundary checks; count the exact union, not a size guess.
    batched=[]
    for task in tasks:
        if batched and task['capability']=='directing_cross_qc' and task['keys']!=['global'] and batched[-1]['capability']=='directing_cross_qc' and batched[-1]['keys']!=['global'] and len(batched[-1]['keys']) < beat_limit:
            previous=batched[-1]
            payload=copy.deepcopy(previous['scope']['payload'])
            other=task['scope']['payload']
            payload['requested_checks']+=other['requested_checks']
            payload['check_windows'].update(other['check_windows'])
            for field in ('selected_edits','original_shot_boundaries','canon'):
                existing={v['id'] for v in payload[field]}
                payload[field]+=[v for v in other[field] if v['id'] not in existing]
            scope={'payload':payload, 'shot_ids':[v['id'] for v in payload['original_shot_boundaries']]}
            merged=add('directing_cross_qc',payload,payload['requested_checks'],previous['label'].split(' 至 ')[0]+' 至 '+task['label'],scope)
            if merged['fits']:
                batched[-1]=merged
                continue
        batched.append(task)
    return batched


def validate(task, result, plan):
    if task['capability']=='directing_qc':
        return validate_directing_review(result, task['scope'], expected_coverage={tuple(k) for k in task['keys']})
    result = CrossReview.model_validate(result).model_dump()
    got=[c['id'] for c in result['checks']]
    if got != task['keys']:
        # Name the expected and actual ids: the single structural repair can only fix this if
        # the error says which identifiers were required. Without them a model that answered the
        # right check under a descriptive name sees only "cover every requested check" and
        # cannot tell that its naming is the defect.
        raise ValueError('跨場審查必須完整涵蓋指定檢查，不可重複或遺漏。checks[].id 必須逐字等於 requested_checks 並保持同一順序：期望 '+encode(task['keys'])+'，實際 '+encode(got)+'。')
    material={k:v for k,v in task['scope']['payload'].items() if k in ('original_narrative','all_scene_beats','selected_edits','original_shot_boundaries','canon')}
    for c in result['checks']:
        if not has_evidence(material,c['evidence']):
            raise ValueError('跨場審查證據必須是本批原文的逐字摘錄。')
    if result['verdict']=='pass' and (result['issues'] or any(c['verdict']!='pass' for c in result['checks'])):
        raise ValueError('跨場審查有問題或未通過檢查時不能整體通過。')
    for issue in result['issues']:
        if not has_evidence(material,issue['evidence']):
            raise ValueError('跨場問題引用了本批未提供的內容。')
    validate_directing_review({k:result[k] for k in ('verdict','summary','issues')} | {'coverage':[]}, plan, expected_coverage=set())
    return result


def run(job, work):
    inp = job['input']; provider=inp['provider_config']; plan=inp['directing_source']
    if inp.get('directing_pipeline') != VERSION:
        raise ValueError('未知審查階段版本；保留原始成果。')
    cancelled(work)
    tasks=prepare(provider, inp['prompt'], plan)
    identity=store.digest([VERSION, inp, tasks])
    manifest=work/'review-manifest.json'
    record={'version':VERSION, 'input_hash':identity, 'tasks':[{'index':n, 'label':t['label'], 'keys':t['keys'], 'input_tokens':t['input_tokens'], 'capability':t['capability']} for n,t in enumerate(tasks)]}
    if manifest.exists() and json.loads(manifest.read_text()) != record:
        raise ValueError('審查進度與凍結原文或預算不符；不能混合不同版本。')
    atomic(manifest, record)
    atomic(work/'review-source.json', plan)
    results=[]
    for n,task in enumerate(tasks):
        cancelled(work)
        status={'kind':'directing_stages','label':'正在審查：'+task['label'],'completed':n,'total':len(tasks)}
        atomic(work/'review-progress.json',status)
        path=work/f'review-{n:04d}-checkpoint.json'
        fingerprint=store.digest([identity,n,task])
        if path.exists():
            saved=json.loads(path.read_text())
            if saved.get('input_hash')!=fingerprint or saved.get('result_hash')!=store.digest(saved.get('result')):
                raise ValueError('審查階段保存內容不符；未重新生成或採用。')
            result=validate(task,saved['result'],plan)
        else:
            # Each explicit resume creates a new attempt for only the unfinished unit.
            attempts=sorted(work.glob(f'review-{n:04d}-attempt-*'))
            recovered=None
            for previous in reversed(attempts):
                meta=previous/'identity.json'
                if not meta.exists() or json.loads(meta.read_text()).get('input_hash')!=fingerprint:
                    raise ValueError('審查嘗試來源不符；保留原始檔案。')
                transport=previous/'transport.json'
                if transport.exists() and json.loads(transport.read_text()).get('finish_reason')=='length':
                    continue
                raw=previous/'result.json'
                if raw.exists():
                    try: recovered=validate(task,json.loads(raw.read_text()),plan)
                    except ValueError: continue
                    break
            if recovered is not None:
                cancelled(work)
                atomic(path,{'input_hash':fingerprint,'result_hash':store.digest(recovered),'result':recovered})
                results.append(recovered)
                continue
            attempt=work/f'review-{n:04d}-attempt-{len(attempts)+1:03d}'
            attempt.mkdir()
            atomic(attempt/'identity.json',{'input_hash':fingerprint})
            (attempt/'request.txt').write_text(task['prompt'])
            context_limits.check(provider,task['prompt'],schema(provider,task['capability']),attempt)
            result=providers.run(provider,task['capability'],task['prompt'],[],attempt)
            try:
                result=validate(task,result,plan)
            except ValueError as exc:
                cancelled(work)
                # One structural repair with complete original request; never retry transport/exhaustion.
                correction=task['prompt']+'\nONE STRUCTURAL CORRECTION. Preserve substantive findings; do not change revise/uncertain to pass. Repair only schema, IDs or literal evidence. ERROR: '+str(exc)+'\nPREVIOUS RESULT:\n'+encode(result)
                repair=work/f'review-{n:04d}-repair-{len(attempts)+1:03d}'
                repair.mkdir()
                context_limits.check(provider,correction,schema(provider,task['capability']),repair)
                result=validate(task,providers.run(provider,task['capability'],correction,[],repair),plan)
            cancelled(work)
            atomic(path,{'input_hash':fingerprint,'result_hash':store.digest(result),'result':result})
        results.append(result)
    cancelled(work)
    rank={'pass':0,'uncertain':1,'revise':2}
    verdict=max((r['verdict'] for r in results),key=rank.get)
    coverage=[c for r in results for c in r.get('coverage',[])]
    issues=[i for r in results for i in r['issues']]
    for r in results:
        for check in r.get('checks',[]):
            if check['verdict']!='pass':
                issues.append({'code':'OTHER','shot_ids':[],'beat_ids':[], **{k:check[k] for k in ('evidence','reason','recommendation')}})
    # Keep every stage's finding, including nonpass cross checks without issues.
    result={'verdict':verdict,'summary':'已完成全部分段及跨場審查。\n'+'\n'.join(t['label']+'：'+r['summary'] for t,r in zip(tasks,results)), 'coverage':coverage,'issues':issues}
    result=validate_directing_review(result,plan)
    atomic(work/'result.json',result)
    atomic(work/'review-complete.json', {'input_hash':store.digest(inp),'result_hash':store.digest(result),'manifest_hash':store.digest(record),'completed':len(tasks)})
    atomic(work/'review-progress.json',{'kind':'directing_stages','label':'全部審查已完成','completed':len(tasks),'total':len(tasks)})
    return result


def require_complete(job, result):
    work=store.DATA/'jobs'/job['id']
    try:
        receipt=json.loads((work/'review-complete.json').read_text())
        manifest=json.loads((work/'review-manifest.json').read_text())
        assert receipt['input_hash']==store.digest(job['input'])
        assert receipt['result_hash']==store.digest(result)
        assert receipt['manifest_hash']==store.digest(manifest)
        assert receipt['completed']==len(manifest['tasks'])>0
        for n in range(receipt['completed']):
            checkpoint=json.loads((work/f'review-{n:04d}-checkpoint.json').read_text())
            assert checkpoint['result_hash']==store.digest(checkpoint['result'])
    except (OSError, ValueError, KeyError, AssertionError):
        raise ValueError('必要審查階段未全部完成；不能採用部分審查結果。') from None


def require_fresh(job):
    from . import directing, models
    p=store.project(job['project_id'])
    if p['revision']!=job['input']['revision']:
        raise ValueError('作品已更新；請以目前版本建立審查，舊進度保留。')
    rebuilt=directing.build(p,models.JobRequest(capability='directing_qc',target_id=job['target_id'],feedback=job['input'].get('feedback','')))
    if rebuilt['directing_request_hash']!=job['input']['directing_request_hash']:
        raise ValueError('審查來源已更新；不能接續舊版本。')


def can_resume(job, revision):
    """Whether POST /api/jobs/{id}/resume would accept this job.

    Mirrors the endpoint's require_fresh gate without rebuilding the request: callers reach this
    only after matching the job by its directing_request_hash, so the source half has already
    passed and the remaining gate is the project revision the endpoint also compares (a revision
    bump blocks a resume even when the review source is unchanged - see the endpoint test).
    Views must ask this rather than restate the condition: a restated copy omitted the revision
    check and offered "接續導演內容審查" for a job the endpoint refused with HTTP 400.
    """
    if not job['input'].get('directing_pipeline') or job['state'] not in ('failed', 'interrupted'):
        return False
    if job['input'].get('revision') != revision:
        return False
    from . import engine
    return not engine.cancel_requested(job['id'])


def receipts(job):
    if not job['input'].get('directing_pipeline'):
        return []
    work=store.DATA/'jobs'/job['id']
    rows=[]
    for path in sorted(work.glob('review-*/context-budget.json')):
        try:
            receipt=json.loads(path.read_text())
            rows.append({'attempt':path.parent.name,'mode':'分段導演審查','input_tokens':receipt['input_tokens'],'full_input_tokens':receipt['input_tokens']})
        except (OSError,ValueError,KeyError):
            continue
    return rows
