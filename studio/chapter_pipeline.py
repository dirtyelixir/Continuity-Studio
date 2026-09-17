"""Checkpointed chapter proposals. Only the assembled result can become a proposal.

Every attempt retains its own request/output. Resume uses the original frozen input
and provider, and never submits a completed stage again or bypasses final/QC checks.
"""
import copy
import json
import os
from pathlib import Path

from pydantic import Field

from . import models, store, providers, directing, serial_story, storyboarding
from . import chapter_context

VERSION = 'chapter-stages-v2'
SUPPORTED = {'chapter-stages-v1', VERSION}
BATCH_SIZE = 3
COVERAGE_BATCH_SIZE = 80


class ShotBrief(models.Strict):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    scene_id: str
    title: str
    purpose: str = Field(min_length=1)
    action: str = Field(min_length=1)
    duration: float = Field(ge=4, le=15)
    entity_ids: list[str]
    beat_ids: list[str] = Field(min_length=1)


class ChapterOutline(models.Strict):
    title: str
    logline: str
    story: str
    screenplay: str
    style: str
    canon: list[models.Entity] = Field(min_length=1)
    scenes: list[models.Scene] = Field(min_length=1)
    shot_briefs: list[ShotBrief] = Field(min_length=1, max_length=40)


class ChapterShots(models.Strict):
    shots: list[models.Shot] = Field(min_length=1, max_length=BATCH_SIZE)


class ChapterEdit(models.Strict):
    edit_plan: list[models.EditDecision] = Field(min_length=1)
    coverage: list[models.SourceCoverage]
    adaptation_notes: list[str]


class ChapterEditOrder(models.Strict):
    edit_plan: list[models.EditDecision] = Field(min_length=1, max_length=120)
    adaptation_notes: list[str] = Field(max_length=20)


class ChapterCoverage(models.Strict):
    coverage: list[models.SourceCoverage] = Field(min_length=1, max_length=COVERAGE_BATCH_SIZE)


class ChapterWriting(models.Strict):
    title: str
    logline: str
    story: str
    screenplay: str
    style: str
    canon: list[models.Entity] = Field(min_length=1)
    scenes: list[models.Scene] = Field(min_length=1, max_length=40)


class ChapterScene(models.Strict):
    scene_id: str
    director_plan: models.SceneDirectorPlan
    shot_briefs: list[ShotBrief] = Field(min_length=1, max_length=40)


STAGE_MODELS = {'chapter_outline': ChapterOutline, 'chapter_shots': ChapterShots,
                'chapter_edit': ChapterEdit, 'chapter_writing': ChapterWriting,
                'chapter_scene': ChapterScene, 'chapter_edit_order': ChapterEditOrder,
                'chapter_coverage': ChapterCoverage, 'chapter_source_index': chapter_context.SourceIndex}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    with temp.open('w') as f:
        f.write(store.encode(value))
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def progress(job):
    if not job['input'].get('chapter_pipeline'):
        return None
    path = store.DATA / 'jobs' / job['id'] / 'progress.json'
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {'kind': 'chapter_stages', 'label': '等待建立章節綱要', 'completed': 0,
                'total': 0, 'completed_shots': 0, 'total_shots': 0}


def _cancel(work):
    if (work / 'cancel-requested').exists():
        raise RuntimeError('使用者已取消工作。')


def _stage(job, work, key, kind, prompt, check, status, reused=None, scope=None):
    """Reuse validated checkpoints/raw outputs; one correction for invalid output.

    Transport errors return immediately. A user resume can retry the unfinished
    stage, retaining every earlier attempt, including malformed or partial output.
    """
    _cancel(work)
    identity = store.digest([job['input'], key, kind, prompt,
                             STAGE_MODELS[kind].model_json_schema()])
    saved = work / (key + '-checkpoint.json')
    if saved.exists():
        record = json.loads(saved.read_text())
        if record['input_hash'] != identity or store.digest(record['result']) != record['result_hash']:
            raise ValueError('已保存階段與原始請求不符；請建立新方案，舊檔案仍保留。')
        return check(record['result'])
    status.update(label=status['next_label'], updated=store.now())
    atomic_json(work / 'progress.json', status)

    def checkpoint(value):
        submitted = STAGE_MODELS[kind].model_validate(value).model_dump()
        value = check(submitted)
        original_scopes = {e['id']: e.get('scope','auto') for e in submitted.get('canon', [])}
        restored = [e['id'] for e in value.get('canon', []) if e['id'] in original_scopes and e.get('scope','auto') != original_scopes[e['id']]]
        _cancel(work)
        atomic_json(saved, {'input_hash': identity, 'result_hash': store.digest(value), 'result': value,
                            'origin': 'adopted-writing' if reused is not None else 'provider-output',
                            'restored_canonical_scopes': restored})
        return value

    if reused is not None:
        return checkpoint(reused)

    previous = None
    error = ''
    attempts = sorted(work.glob(key + '-attempt-*'))
    # A process can exit after writing a valid result but before checkpointing it.
    for attempt in reversed(attempts):
        meta = attempt / 'stage-context.json'
        # A crash between mkdir and the atomic context write has no provider output
        # to trust/reuse. Retain that empty attempt and continue in a new directory.
        if not meta.is_file() and not (attempt / 'result.json').exists() and not (attempt / 'request.txt').exists():
            continue
        if not meta.is_file() or json.loads(meta.read_text()).get('input_hash') != identity:
            raise ValueError('階段嘗試來源不符；不能混合不同請求的輸出。')
        raw = attempt / 'result.json'
        if raw.is_file() and raw.stat().st_size:
            previous = raw.read_text()
            try:
                return checkpoint(json.loads(providers.json_content(previous)))
            except ValueError as exc:
                error = str(exc)
                break
    prompt, context_receipt = chapter_context.adapt(job, work, key, kind, prompt, scope, status)
    status.update(label=status['next_label'], updated=store.now())
    atomic_json(work / 'progress.json', status)
    budget = 1 if previous else 2
    for offset in range(budget):
        _cancel(work)
        attempt = work / f'{key}-attempt-{len(attempts) + offset + 1:03d}'
        attempt.mkdir(exist_ok=False)
        atomic_json(attempt / 'stage-context.json', {'input_hash': identity, 'kind': kind})
        if context_receipt:
            atomic_json(attempt / 'context-selection.json', context_receipt)
        request = prompt
        if previous:
            status.update(label='正在修正：' + status['next_label'].removeprefix('正在'), updated=store.now())
            atomic_json(work / 'progress.json', status)
            request += '\nONE STRUCTURAL CORRECTION: fix the reported schema/link errors while preserving the frozen story and valid creative decisions. Return only this stage.\nERROR:\n' + error[:6000] + '\nPREVIOUS OUTPUT:\n' + previous[:2_000_000]
        try:
            value = providers.run(job['input']['provider_config'], kind, request, [], attempt)
            # Custom providers/test adapters must have the same durable raw evidence.
            if not (attempt / 'result.json').exists():
                atomic_json(attempt / 'result.json', value)
            return checkpoint(value)
        except ValueError as exc:
            raw = attempt / 'result.json'
            if offset == budget - 1 or not raw.is_file() or not raw.stat().st_size:
                raise
            previous, error = raw.read_text(), str(exc)
    raise RuntimeError('章節階段未完成。')


def validate_outline(value, existing):
    value = ChapterOutline.model_validate(value).model_dump()
    canon = {e['id']: e for e in value['canon']}
    scenes = {s['id']: s for s in value['scenes']}
    briefs = value['shot_briefs']
    ids = [e['id'] for e in value['canon'] + value['scenes'] + briefs]
    if len(ids) != len(set(ids)):
        raise ValueError('章節綱要中的角色、場景及鏡頭 ID 必須唯一。')
    for old in existing:
        if old['id'] in canon:
            # Scope is application-owned organization, not a creative canon change.
            # Keep the canonical value; the provider's unmodified raw output remains.
            canon[old['id']]['scope'] = old.get('scope','auto')
            if models.Entity.model_validate(old) != models.Entity.model_validate(canon[old['id']]):
                raise ValueError('章節綱要必須沿用既有 canon：' + old['id'])
    for scene in scenes.values():
        if canon.get(scene['location_id'], {}).get('kind') != 'location' or not scene['director_plan']:
            raise ValueError('章節綱要的場景必須連結地點及完整導演節拍。')
        beats = [b['id'] for b in scene['director_plan']['beats']]
        if len(beats) != len(set(beats)) or sorted(beats) != sorted(scene['director_plan']['reveal_order']):
            raise ValueError('章節綱要的戲劇節拍及揭示順序不符。')
        local = [b for b in briefs if b['scene_id'] == scene['id']]
        if not local or {bid for b in local for bid in b['beat_ids']} != set(beats):
            raise ValueError('鏡頭綱要必須涵蓋每個場景節拍。')
    for brief in briefs:
        if brief['scene_id'] not in scenes or not set(brief['entity_ids']) <= canon.keys() or len(brief['entity_ids']) != len(set(brief['entity_ids'])):
            raise ValueError('鏡頭綱要的場景或角色引用無效。')
        if len(brief['beat_ids']) != len(set(brief['beat_ids'])) or any(not b.strip() for b in brief['beat_ids']):
            raise ValueError('鏡頭綱要的戲劇節拍引用不可重複或空白。')
    return value


def validate_shots(value, outline, expected, completed):
    value = ChapterShots.model_validate(value).model_dump()
    shots = value['shots']
    if [s['id'] for s in shots] != [s['id'] for s in expected]:
        raise ValueError('本階段只可傳回指定鏡頭，並保留指定順序。')
    for shot, brief in zip(shots, expected):
        if any(shot[k] != brief[k] for k in ('scene_id', 'duration', 'entity_ids')):
            raise ValueError('鏡頭必須沿用已保存綱要的場景、時長及角色。')
        if shot['generation_duration'] != shot['duration'] or not shot['shot_purpose'].strip() or not shot['direction']:
            raise ValueError('鏡頭必須包含生成時長、單一用途及導演資料。')
        if shot['direction']['beat_ids'] != brief['beat_ids']:
            raise ValueError('鏡頭必須承載綱要指定的戲劇節拍。')
        scene = next(s for s in outline['scenes'] if s['id'] == shot['scene_id'])
        if not set(shot['direction']['subject_ids']) <= set(shot['entity_ids']) | {scene['location_id']}:
            raise ValueError('鏡頭的視覺主體必須存在於鏡頭或場景。')
    # Production's timing/entity/global-ID checks still apply before a batch is saved.
    # Complete beat/edit coverage is checked on final assembly, never on a partial batch.
    partial = {k: copy.deepcopy(v) for k, v in outline.items() if k != 'shot_briefs'}
    partial['shots'] = copy.deepcopy(completed + shots)
    for scene in partial['scenes']:
        scene['director_plan'] = None
    for shot in partial['shots']:
        shot['direction'], shot['shot_purpose'] = None, ''
    models.Production.model_validate(partial)
    return value


def run(job, work):
    work.mkdir(parents=True, exist_ok=True)
    if job['input']['chapter_pipeline'] not in SUPPORTED:
        raise ValueError('分階段工作版本已改變，請建立新方案。')
    base = job['input']['prompt']
    common = '\nSTAGED CHAPTER EXECUTION: Follow all frozen creative, source, canon and mandatory method instructions above. This stage contract overrides only the requested OUTPUT SHAPE. Never generate a complete Production in an intermediate stage. No tools, media, provider changes or invented placeholders. Preserve exact source dialogue and established IDs.\n'
    status = {'kind': 'chapter_stages', 'label': '', 'next_label': '正在建立全章劇情及鏡頭綱要',
              'completed': 0, 'total': 0, 'completed_shots': 0, 'total_shots': 0}
    if job['input']['chapter_pipeline'] == 'chapter-stages-v1':
        # Keep already-created jobs resumable with their original stage contract.
        outline_prompt = base + common + '''STAGE: CHAPTER OUTLINE. Return title/logline/story/screenplay/style/canon/scenes and shot_briefs only. Make the complete chapter's dramatic decisions now: each scene needs director_plan with beats/reveal_order, and each shot_brief one primary purpose, visible action, exact source duration, entities and beat links. Use only as many shots as the chapter needs, at most 40. Preserve existing writing/canon when revising unless feedback requires changes. A shot brief is concise; do NOT write detailed camera, timed beats, state arrays, keyframes or edit ranges yet. These will be produced in small batches from this saved blueprint. Include all dialogue in screenplay so later stages cannot lose it. Return only the ChapterOutline JSON.'''
        outline = _stage(job, work, '01-outline', 'chapter_outline', outline_prompt,
                         lambda v: validate_outline(v, job['input'].get('chapter_canon', [])), status)
        status['completed'] = 1
    else:
        outline = _outline_by_scene(job, work, base, common, status)
    briefs = outline['shot_briefs']
    output_budget = job['input']['provider_config'].get('context_policy', {}).get('max_output_tokens', 32768)
    batch_size = min(BATCH_SIZE, max(1, output_budget // 6000))
    first_batch = status['completed'] + 1
    status.update(total=first_batch + (len(briefs) + batch_size - 1) // batch_size, total_shots=len(briefs))
    shots = []
    for offset in range(0, len(briefs), batch_size):
        expected = briefs[offset:offset + batch_size]
        status['next_label'] = f'正在完成鏡頭 {offset + 1}–{offset + len(expected)}／{len(briefs)}'
        boundary = [{'id': s['id'], 'scene_id': s['scene_id'], 'end_state': s['end_state'],
                     'action': s['action'], 'dialogue': s['dialogue']} for s in shots]
        prompt = base + common + '''STAGE: SHOT DETAILS. Return ONLY the requested shots in exact order using ChapterShots JSON. Preserve the saved outline's scene_id/duration/entity_ids/beat_ids exactly. Write actionable full shot direction, timing, dialogue and frozen keyframes. generation_duration equals duration. Carry one primary purpose. Check continuous physical and prop states against completed shots, and leave the planned transition into upcoming shot briefs possible. Do not rewrite story, canon, scenes, other shots or final edits.\nSAVED CHAPTER OUTLINE:\n''' + store.encode(outline) + '\nCOMPLETED SHOT BOUNDARIES:\n' + store.encode(boundary) + '\nREQUESTED SHOT BRIEFS:\n' + store.encode(expected)
        result = _stage(job, work, f'{first_batch + offset // batch_size:02d}-shots', 'chapter_shots', prompt,
                        lambda v: validate_shots(v, outline, expected, shots), status,
                        scope={'writing': outline, 'scene_ids': sorted({b['scene_id'] for b in expected}),
                               'requested_briefs': expected, 'chapter_shot_briefs': briefs,
                               'completed_boundaries': boundary, 'previous_shot': shots[-1:]})
        shots.extend(result['shots'])
        status.update(completed=status['completed'] + 1, completed_shots=len(shots))
    status['next_label'] = '正在整理全章剪接順序及檢查完整性'
    plan = {k: v for k, v in outline.items() if k != 'shot_briefs'}
    plan.update(shots=shots, chapters=[])
    def assemble(value):
        value = ChapterEdit.model_validate(value).model_dump()
        full = models.Production.model_validate({**plan, 'edit_plan': value['edit_plan']}).model_dump()
        directing.validate_director_plan(full, require_complete=True)
        serial_story.validate_proposal(full, job['input']['serial_source'])
        if job['capability'] == 'storyboard':
            result = {'production': full, 'coverage': value['coverage'], 'adaptation_notes': value['adaptation_notes']}
            storyboarding.validate(result, job['input']['source'])
        elif value['coverage']:
            raise ValueError('故事創作的 coverage 必須為空；原文分鏡才需要來源對照。')
        return value
    prompt = base + common + '''STAGE: FINAL EDIT PLAN. All saved scenes/shots are immutable. Return only ChapterEdit JSON: edit_plan, coverage and adaptation_notes. Design the whole chapter's ordered edit ranges with justified cut points and continuity. Every source shot needs a valid range; a source may appear more than once when justified. Do not replay irreversible actions or cut away required dialogue/performances. No actual footage is generated or trimmed. For narrative return coverage=[]; for storyboard cover every frozen source unit in exact source order with valid shot IDs.\nSAVED PRODUCTION:\n''' + store.encode(plan)
    key = f'{status["total"]:02d}-edit'
    # Keep the exact legacy prompt/schema identity for already completed finals.
    # A complete raw result can also survive a crash before checkpointing.
    complete = (work / (key + '-checkpoint.json')).exists()
    if not complete:
        for raw in work.glob(key + '-attempt-*/result.json'):
            try:
                assemble(json.loads(raw.read_text()))
                complete = True
                break
            except ValueError:
                pass
    units = job['input'].get('source', {}).get('units', [])
    truncated = any(json.loads(p.read_text()).get('status') == 'truncated'
                    for p in work.glob(key + '-attempt-*/transport.json'))
    coverage_size = min(COVERAGE_BATCH_SIZE, max(1, output_budget // 200))
    if not complete and (len(units) > coverage_size or truncated):
        edits = _bounded_final(job, work, key, base + common, plan, assemble, status)
    else:
        edits = _stage(job, work, key, 'chapter_edit', prompt, assemble, status,
                       scope={'writing': plan, 'all_source': True, 'shots': shots})
    result = models.Production.model_validate({**plan, 'edit_plan': edits['edit_plan']}).model_dump()
    if job['capability'] == 'storyboard':
        result = {'production': result, 'coverage': edits['coverage'], 'adaptation_notes': edits['adaptation_notes']}
    _cancel(work)
    atomic_json(work / 'result.json', result)
    status.update(completed=status['total'], label='章節方案已組合，待獨立導演審查', updated=store.now())
    atomic_json(work / 'progress.json', status)
    return result


def _bounded_final(job, work, key, context, plan, assemble, status):
    """Finalize existing shots without one unbounded coverage response.

    Versioned keys coexist with historical attempts; no partial JSON is adopted.
    The outer final stage remains one stage, with independently durable substeps.
    """
    prefix = key + '-bounded-v1'
    units = job['input'].get('source', {}).get('units', []) if job['capability'] == 'storyboard' else []
    output_budget = job['input']['provider_config'].get('context_policy', {}).get('max_output_tokens', 32768)
    batch_size = min(COVERAGE_BATCH_SIZE, max(1, output_budget // 200))
    total = 1 + (len(units) + batch_size - 1) // batch_size
    status['finalization'] = {'completed': 0, 'total': total, 'covered_units': 0, 'total_units': len(units)}
    status['next_label'] = '正在整理已保存鏡頭的剪接表（原文對照會分批保存）'

    def check_order(value):
        full = models.Production.model_validate({**plan, 'edit_plan': value['edit_plan']}).model_dump()
        directing.validate_director_plan(full, require_complete=True)
        serial_story.validate_proposal(full, job['input']['serial_source'])
        return value

    prompt = context + '''STAGE: FINAL EDIT ORDER ONLY. Saved writing, scenes and shots are immutable. Return ChapterEditOrder JSON: edit_plan and concise adaptation_notes ONLY. Do NOT output coverage or repeat source text. Design the whole chapter's ordered edit ranges, preserving required dialogue, performances, reveal order and irreversible actions. Every saved shot needs a valid range. Justify cuts and transitions concisely; no footage is generated or trimmed. Source traceability is handled in separate bounded calls.\nSAVED PRODUCTION:\n''' + store.encode(plan)
    edits = _stage(job, work, prefix + '-order', 'chapter_edit_order', prompt, check_order, status,
                   scope={'writing': plan, 'shots': plan['shots']})
    status['finalization']['completed'] = 1
    coverage = []
    shot_ids = {s['id'] for s in plan['shots']}
    source_ids = [u['id'] for u in units]

    def check_coverage(value, expected=None):
        entries = value['coverage']
        ids = [c['source_id'] for c in entries]
        if expected is not None and ids != expected:
            raise ValueError('只可輸出本批指定原文，必須完整、依序且不重複。')
        if len(ids) != len(set(ids)) or not set(ids) <= set(source_ids):
            raise ValueError('原文對照含無效或重複的原文 ID。')
        for entry in entries:
            links = entry['shot_ids']
            if len(links) != len(set(links)) or not set(links) <= shot_ids or not entry['treatment'].strip():
                raise ValueError('原文對應含無效、重複的鏡頭或空白說明。')
        return value

    for offset in range(0, len(units), batch_size):
        batch = units[offset:offset + batch_size]
        status['next_label'] = f'正在核對原文 {offset + 1}–{offset + len(batch)}／{len(units)}（鏡頭已保存）'
        prompt = context + '''STAGE: ONE SOURCE COVERAGE BATCH ONLY. Return ChapterCoverage JSON with exactly one coverage entry per REQUESTED SOURCE UNIT in the supplied order, and nothing else. Never output coverage for other units, an edit plan, story or shots. Map each passage faithfully to valid saved shot IDs; write a concise Traditional Chinese treatment (one short sentence, no source quotations). Headings/exposition may map as context. Do not claim dialogue/actions absent from saved shots; describe any adaptation gap honestly for independent review. All saved production decisions are immutable.\nSAVED PRODUCTION:\n''' + store.encode(plan) + '\nREQUESTED SOURCE UNITS:\n' + store.encode(batch)
        value = _stage(job, work, f'{prefix}-coverage-{offset // batch_size + 1:03d}',
                       'chapter_coverage', prompt,
                       lambda v: check_coverage(v, [u['id'] for u in batch]), status,
                       scope={'writing': plan, 'source_ids': [u['id'] for u in batch],
                              'requested_source_units': batch, 'shots': plan['shots']})
        coverage.extend(value['coverage'])
        status['finalization'].update(completed=status['finalization']['completed'] + 1,
                                      covered_units=len(coverage))
    result = {**edits, 'coverage': coverage}
    claimed = {s for c in coverage for s in c['shot_ids']}
    missing = sorted(shot_ids - claimed) if units else []
    if missing:
        # Cross-batch completeness may need a sparse patch referencing earlier
        # source units. Never force unrelated shots onto the last source batch.
        status['finalization']['total'] = total + 1
        status['next_label'] = '正在補核跨批次的鏡頭原文依據'
        def repair_check(value):
            check_coverage(value)
            patch = {c['source_id']: c for c in value['coverage']}
            revised = [patch.get(c['source_id'], c) for c in coverage]
            assemble({**edits, 'coverage': revised})
            return value
        prompt = context + '''STAGE: SPARSE SOURCE COVERAGE CORRECTION ONLY. Return ChapterCoverage JSON for only the source units needing corrected links, at most 80 entries. Every saved shot must have truthful source support. Use any appropriate frozen source units, not just the last batch. Preserve existing valid links when replacing an entry; identify adaptation gaps honestly. Do not change shots, writing or edit decisions.\nSAVED PRODUCTION:\n''' + store.encode(plan) + '\nSAVED COVERAGE:\n' + store.encode(coverage) + '\nSHOTS WITHOUT SOURCE LINKS:\n' + store.encode(missing)
        value = _stage(job, work, prefix + '-coverage-repair', 'chapter_coverage', prompt, repair_check, status)
        patch = {c['source_id']: c for c in value['coverage']}
        result['coverage'] = [patch.get(c['source_id'], c) for c in coverage]
        status['finalization']['completed'] += 1
    return assemble(result)


def _outline_by_scene(job, work, base, common, status):
    existing = job['input'].get('chapter_canon', [])
    def writing_check(value):
        value = ChapterWriting.model_validate(value).model_dump()
        ids = [e['id'] for e in value['canon'] + value['scenes']]
        if len(ids) != len(set(ids)):
            raise ValueError('劇本的角色及場景 ID 必須唯一。')
        canon = {e['id']: e for e in value['canon']}
        for old in existing:
            if old['id'] in canon:
                canon[old['id']]['scope'] = old.get('scope','auto')
                if models.Entity.model_validate(old) != models.Entity.model_validate(canon[old['id']]):
                    raise ValueError('必須沿用既有 canon：' + old['id'])
        for scene in value['scenes']:
            if canon.get(scene['location_id'], {}).get('kind') != 'location':
                raise ValueError('劇本場景必須連結既有地點。')
            if scene['director_plan'] is not None:
                raise ValueError('此階段只建立劇本和場景；director_plan 必須為 null，下一階段逐場規劃。')
        return value
    reused = copy.deepcopy(job['input'].get('chapter_writing'))
    if reused:
        for scene in reused['scenes']:
            scene['director_plan'] = None
    status['next_label'] = '保存已採用劇本及設定' if reused else '正在建立章節劇本及場景'
    prompt = base + common + '''STAGE: CHAPTER WRITING ONLY. Return ChapterWriting JSON: title/logline/story/screenplay/style/canon/scenes. Develop or preserve the chapter's complete story and exact dialogue; establish canonical identities and scene descriptions. Every scene director_plan MUST be null. Do not design dramatic beats, shot briefs, detailed shots, keyframes or edits yet. Later independent calls will plan each scene from this saved writing. Do not condense away required source events. Reuse authoritative canon unchanged.'''
    writing = _stage(job, work, '01-writing', 'chapter_writing', prompt, writing_check, status, reused=reused,
                     scope={'foundation': True})
    status.update(completed=1, total=0)  # Full stage count is known after scene planning.
    scenes, briefs = [], []
    for index, scene in enumerate(writing['scenes']):
        remaining = 40 - len(briefs) - (len(writing['scenes']) - index - 1)
        if remaining < 1:
            raise ValueError('本章鏡頭綱要超過 40 個鏡頭，請修訂章節範圍。')
        def scene_check(value):
            value = ChapterScene.model_validate(value).model_dump()
            if value['scene_id'] != scene['id'] or any(b['scene_id'] != scene['id'] for b in value['shot_briefs']):
                raise ValueError('只可規劃本階段指定的場景。')
            if len(value['shot_briefs']) > remaining:
                raise ValueError(f'本場景最多可使用 {remaining} 個鏡頭，須為其他場景保留位置。')
            reserved = {b['id'] for b in briefs} | {s['id'] for s in writing['scenes']} | {e['id'] for e in writing['canon']}
            if any(b['id'] in reserved for b in value['shot_briefs']):
                raise ValueError('本場鏡頭 ID 與其他場景／鏡頭／角色重複。')
            validate_outline({**writing, 'scenes':[{**scene, 'director_plan':value['director_plan']}],
                              'shot_briefs':value['shot_briefs']}, existing)
            return value
        status['next_label'] = f'正在規劃場景 {index + 1}／{len(writing["scenes"])}：{scene["title"]}'
        prompt = base + common + '''STAGE: ONE SCENE DIRECTOR OUTLINE. Return only ChapterScene JSON for the requested scene: scene_id/director_plan/shot_briefs. Preserve all saved chapter writing/canon and existing shot IDs wherever corresponding shots remain. Design this scene's dramatic beats, reveal order and concise source-shot briefs with one primary purpose each. Do not write full shot details, keyframes, timed states or edits. Respect neighbouring scenes and completed shot briefs; no duplicate IDs. Include every required event/dialogue from this scene. Do not add future scenes or make the whole chapter's plan in this response. The remaining shot budget is a ceiling, not a target; choose only coverage that the scene requires.\nSAVED WRITING:\n''' + store.encode(writing) + '\nCOMPLETED SCENE SHOT BRIEFS:\n' + store.encode(briefs) + '\nREQUESTED SCENE:\n' + store.encode(scene) + '\nMAXIMUM SHOTS FOR THIS SCENE: ' + str(remaining)
        result = _stage(job, work, f'{index + 2:02d}-scene', 'chapter_scene', prompt, scene_check, status,
                        scope={'writing': writing, 'scene_ids': [scene['id']], 'requested_scene': scene,
                               'maximum_shots': remaining, 'reserved_briefs': briefs})
        scenes.append({**scene, 'director_plan':result['director_plan']})
        briefs.extend(result['shot_briefs'])
        status.update(completed=status['completed'] + 1)
    return validate_outline({**writing, 'scenes':scenes, 'shot_briefs':briefs}, existing)


def require_fresh(job):
    """Resume is the same frozen job, never an implicit regeneration on new canon."""
    from . import director_styles, production_methods
    if job['input']['chapter_pipeline'] not in SUPPORTED:
        raise ValueError('分階段工作版本已改變，請建立新方案。')
    p = store.project(job['project_id'])
    if p['revision'] != job['input']['revision']:
        raise ValueError('製作版本已改變，請建立新方案；原有階段仍保留。')
    frozen = job['input']['serial_source']
    if serial_story.snapshot(p, serial_story.chapter(p['id'], job['target_id'])) != frozen:
        raise ValueError('大綱或章節已改變，請建立新方案；原有階段仍保留。')
    director_styles.check_adoption(job)
    method = job['input'].get('production_method', {})
    if method.get('hash') != production_methods.snapshot(job['capability'])[1]['hash']:
        raise ValueError('製作方法已更新，請建立新方案；原有階段仍保留。')
