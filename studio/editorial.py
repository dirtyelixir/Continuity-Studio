"""Scene-scoped, versioned editorial trials using the existing Production contract.

Trials are candidates, never another authority for production or media routing.
Only explicit adoption writes a normal Production revision via engine.save_plan.
"""
import copy
import hashlib
import json
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from . import store, models, continuity, h3, editorial_records

router = APIRouter()
BUNDLE = store.ROOT / 'studio/bundled/editorial-knowledge'


def knowledge():
    manifest = json.loads((BUNDLE / 'provenance.json').read_text())
    for f in manifest['files']:
        if hashlib.sha256((BUNDLE / f['file']).read_bytes()).hexdigest() != f['sha256']:
            raise ValueError('剪接參考文件版本不符，請修復本機知識庫。')
    return manifest


def basis(p):
    return store.digest([p['revision'], p['production']])


def scope(plan, sid):
    ids = {s['id'] for s in plan['shots'] if s['scene_id'] == sid}
    return {'shots': [s for s in plan['shots'] if s['id'] in ids],
            'edit_plan': [e for e in plan['edit_plan'] if e['shot_id'] in ids]}


def complete_edits(plan):
    """Legacy plans have no edit rows; supply explicit full-length planned ranges."""
    result = copy.deepcopy(plan)
    covered = {e['shot_id'] for e in result.get('edit_plan', [])}
    result.setdefault('edit_plan', []).extend(dict(id='original_'+s['id'], shot_id=s['id'],
        planned_edit_in=0, planned_edit_out=s['duration'], cut_in_reason='沿用原鏡頭次序',
        cut_out_reason='原鏡頭結束', continuity_note=s['transition_note'] or '沿用原鏡頭起止狀態，剪接前看片核對。')
        for s in result['shots'] if s['id'] not in covered)
    return result


def state_refs(shot):
    # References are content addressed and read by Shot, never rewritten by edit order.
    return {k: store.digest(shot[k]) for k in ('start_state', 'end_state')}


def evidence_check(requirement):
    """Conservative text-only sufficiency, never a claim about generated pixels."""
    if requirement.get('goal') == 'named_identity' and requirement.get('carrier') == 'generic_hand':
        return 'revise'
    if requirement.get('goal') == 'named_identity' and not requirement.get('prior_identity_basis'):
        return 'uncertain'
    return 'unreviewed'


def validate_trial(trial, baseline):
    from .editorial_timing import timeline
    # Validate raw timings before Pydantic can coerce booleans or strings to floats.
    timeline(scope(trial['plan'],trial['scene_id']), trial['audio_cues'])
    trial['plan'] = models.Production.model_validate(trial['plan']).model_dump()
    sid = trial['scene_id']
    if not any(s['id'] == sid for s in baseline['scenes']):
        raise ValueError('試行場景不存在。')
    # A scene trial cannot modify canon, writing, chapters or any other scene.
    for key in ('title', 'logline', 'story', 'screenplay', 'style', 'canon', 'chapters'):
        if trial['plan'].get(key) != baseline.get(key):
            raise ValueError('一場戲試行不可修改原作、人物設定或其他章節。')
    for key in ('scenes', 'shots'):
        field = 'id' if key == 'scenes' else 'scene_id'
        if [s for s in trial['plan'][key] if s[field] != sid] != [s for s in baseline[key] if s[field] != sid]:
            raise ValueError('一場戲試行不可修改其他場景。')
    other = {s['id'] for s in baseline['shots'] if s['scene_id'] != sid}
    if [e for e in trial['plan']['edit_plan'] if e['shot_id'] in other] != [e for e in baseline['edit_plan'] if e['shot_id'] in other]:
        raise ValueError('一場戲試行不可修改其他場景剪接。')
    # Exact original speaker, language, utterance and order must survive splitting.
    lines = lambda p: [(d['entity_id'], d['language'], d['text']) for s in p['shots'] if s['scene_id']==sid for d in s['dialogue']]
    if lines(trial['plan']) != lines(baseline):
        raise ValueError('試行必須保留原有對白、人物、語言及次序。')
    shots={s['id']:s for s in trial['plan']['shots']}
    for cue in trial['audio_cues']:
        if cue['kind']!='dialogue':continue
        match=next((d for d in shots[cue['shot_id']]['dialogue'] if d['entity_id']==cue.get('entity_id') and d['text']==cue['text'] and d['start']==cue['source_in'] and d['end']==cue['source_out']),None)
        if match is None or cue.get('delivery')!=match['delivery']:
            raise ValueError('對白標記必須對應原有說話者、完整句子、來源時間及有聲／無聲設定。')
    return timeline(scope(trial['plan'], sid), trial['audio_cues'])


def status(p,t):
    record=editorial_records.records(p['id']).get(t['scene_id'],{})
    adopted=record.get('trial_id')==t['id'] and record.get('version')==t['version']
    if adopted and editorial_records._review_current(p['id'],record,p['production'],t['scene_id']) and editorial_records._audio_current(p['id'],record,p['production'],t['scene_id']):
        return 'adopted'
    return 'draft' if not t.get('adopted_revision') and t['base_hash']==basis(p) else 'stale'


def settings_for(pid,t,trials):
    record=editorial_records.adoption_record(t)
    scenes=editorial_records.records(pid);scenes[t['scene_id']]=record
    return {'editorial_scenes:'+pid:scenes,'editorial_applied:'+pid:record,'editorial_trials:'+pid:trials}


def compiled_settings(pid,t,trials,plan):
    """Bind editorial receipts to the actual pre-commit compiled Production."""
    if plan!=t['plan']:
        original=copy.deepcopy(t['plan'])
        t.setdefault('state_compilation_history',[]).append({'plan':original,'baseline':copy.deepcopy(t['baseline'])})
        old={s['id']:s for s in original['shots']};new={s['id']:s for s in plan['shots']}
        # Non-edited source shots in the comparison baseline get the identical
        # validated projection. Authored alternative shots remain historical.
        t['baseline']['shots']=[copy.deepcopy(new[s['id']]) if old.get(s['id'])==s else s for s in t['baseline']['shots']]
        t['plan']=copy.deepcopy(plan)
    return settings_for(pid,t,trials)


def create(pid, sid, candidate, notes, audio_cues, provenance):
    from . import engine
    with engine.LOCK:
        p = store.project(pid)
        if provenance.get('source_hash') != basis(p):
            raise ValueError('試行撰寫期間正式來源已改變，請重新核對。')
        baseline = complete_edits(models.Production.model_validate(p['production']).model_dump())
        trial = dict(id=store.uid(), project_id=pid, scene_id=sid, version=1,
            title=next(s['title'] for s in candidate['scenes'] if s['id']==sid)+' · 剪接方案', base_hash=basis(p), base_revision=p['revision'],
            baseline=baseline, plan=candidate, notes=notes, audio_cues=audio_cues,
            knowledge=knowledge(), provenance=provenance, created=store.now(), history=[])
        validate_trial(trial, baseline)
        trials = store.setting('editorial_trials:'+pid, [])
        trials.append(trial)
        store.put_setting('editorial_trials:'+pid, trials)
        return trial


def find(pid, tid):
    store.project(pid)
    trials = store.setting('editorial_trials:'+pid, [])
    item = next((t for t in trials if t['id']==tid), None)
    if item is None:
        raise ValueError('找不到剪接試行。')
    return trials, item


def artifacts(trial):
    """Derive prompt drafts, storyboard cards and state references from ONE revision."""
    rows = scope(trial['plan'], trial['scene_id'])
    prompts = []
    view = copy.deepcopy(trial['plan'])
    labels = trial['provenance'].get('prompt_labels', {})
    for e in view['canon']:
        if e['kind'] not in ('character', 'crowd', 'voice') and e['id'] in labels:
            e['name'] = labels[e['id']]
    for s in rows['shots']:
        compiled = h3.compile_shot(view, s, [])
        # Text draft only: a missing reference must never silently route generation to T2VA.
        compiled.update(ready=False, execution_mode=None,
            readiness='文字草稿；尚未選定生成模式及核對所需參考圖，不能送出生成。',
            plan_hash=store.digest(trial['plan']), trial_version=trial['version'])
        prompts.append(compiled)
    return {'plan_hash':store.digest(trial['plan']), 'prompts':prompts,
            'states':{s['id']:state_refs(s) for s in rows['shots']}}


def public(p, trial):
    from .editorial_timing import timeline
    result = copy.deepcopy(trial)
    result.pop('history', None)
    result['history_count'] = len(trial['history'])
    result['status'] = status(p,trial)
    result['stale'] = result['status']=='stale'
    result['production_revision']=p['revision']
    if result['status']=='adopted':
        # The saved candidate remains historical; formal output uses today's full
        # Production, including current neighbouring scenes/reference dependencies.
        result['plan']=copy.deepcopy(p['production'])
    result['timeline'] = validate_trial(copy.deepcopy(trial), trial['baseline'])
    base = scope(trial['baseline'],trial['scene_id'])
    result['baseline_timeline'] = timeline(base, original_audio(base))
    result['artifacts'] = artifacts(result)
    if result['status']=='adopted':
        from . import directing
        review_state=directing.state(p)
        result['directing_status']=next((s['status'] for s in review_state['scenes'] if s['scene_id']==trial['scene_id']),'unreviewed')
        result['directing_review']=review_state.get('current_review')
    for note in result['notes'].values():
        note['evidence']['status'] = evidence_check(note['evidence'])
    # Only immutable, still-valid approved images may be shown as storyboard evidence.
    assets = store.assets(p['id'])
    result['images'] = {}
    for s in scope(result['plan'],trial['scene_id'])['shots']:
        f = next((f for f in s['keyframes'] if f['moment']=='start'), None)
        a = continuity.approved_for(result['plan'], assets, f['id']) if f else None
        if a and (store.DATA/a['path']).is_file():
            result['images'][s['id']] = {'asset_id':a['id'], 'job_id':a.get('job_id'),
                'source':'generated' if a.get('job_id') else 'imported',
                'url':'/api/assets/'+a['id']+'/image', 'dependency_hash':a['dependency_hash']}
    return result


def original_audio(scoped):
    shots = {s['id']:s for s in scoped['shots']}
    cues=[]; cursor=0
    for e in scoped['edit_plan']:
        for i,d in enumerate(shots[e['shot_id']]['dialogue']):
            if e['planned_edit_in'] <= d['start'] and d['end'] <= e['planned_edit_out']:
                cues.append(dict(id=e['id']+'_d'+str(i),shot_id=e['shot_id'],
                    source_in=d['start'],source_out=d['end'],timeline_in=cursor+d['start']-e['planned_edit_in'],
                    kind='dialogue',text=d['text'],entity_id=d['entity_id'],delivery=d['delivery']))
        cursor += e['planned_edit_out']-e['planned_edit_in']
    return cues


class TrialEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int
    edit_plan: list[dict]
    audio_cues: list[dict]
    production_revision: int | None = None


class TrialAdoption(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int


@router.post('/api/projects/{pid}/editorial/{tid}/adopt')
def adopt(pid: str, tid: str, req: TrialAdoption):
    from . import engine
    with engine.LOCK:
        trials, t = find(pid,tid)
        p = store.project(pid)
        if t['version']==req.version and status(p,t)=='adopted':
            return {'revision':p['revision'],'directing_review':'unreviewed'}
        if t['version'] != req.version or t['base_hash'] != basis(p):
            raise ValueError('方案版本已改變，請重新載入及比較後再採用。')
        checked = validate_trial(copy.deepcopy(t), t['baseline'])
        if checked['warnings']:
            raise ValueError('有原有對白缺少完整聲音標記，請先修訂再採用。')
        # Explicit human plan edit, not an invented successful provider review.
        # Normal directing.require_ready still gates downstream generation.
        t['adopted_revision'] = p['revision']+1
        result = engine.save_plan(pid,t['plan'],p['revision'],f'人工採用剪接方案 {tid} v{t["version"]}；導演內容待審查',
            setting_updates=lambda plan:compiled_settings(pid,t,trials,plan))
        return {'revision':result['revision'],'directing_review':'unreviewed'}


@router.get('/api/projects/{pid}/editorial')
def listing(pid: str):
    p = store.project(pid)
    return {'project_id':pid, 'workflow_contract_version':1,'title':p['title'], 'production_revision':p['revision'], 'scenes':(p.get('production') or {}).get('scenes',[]), 'trials':[
        public(p,t) for t in store.setting('editorial_trials:'+pid, [])]}


class OpenScene(BaseModel):
    scene_id: str
    production_revision: int


@router.post('/api/projects/{pid}/editorial/open')
def open_scene(pid: str, req: OpenScene):
    from . import engine
    with engine.LOCK:
        p=store.project(pid)
        if req.production_revision!=p['revision']:raise ValueError('正式版本已更新，請重新載入。')
        existing=next((t for t in reversed(store.setting('editorial_trials:'+pid,[])) if t['scene_id']==req.scene_id and status(p,t)!='stale'),None)
        if existing:return public(p,existing)
        plan=complete_edits(models.Production.model_validate(p['production']).model_dump())
        if not any(s['id']==req.scene_id for s in plan['scenes']):raise ValueError('找不到此場景。')
        local=scope(plan,req.scene_id)
        notes={s['id']:dict(source_shot_id=s['id'],story_order=i+1,
            state_in_ref=state_refs(s)['start_state'],state_out_ref=state_refs(s)['end_state'],
            change_event={'source_excerpt':s['transition_note'],'authority':'目前正式分鏡'},
            evidence={'goal':'action_or_reaction','carrier':(s.get('direction') or {}).get('visual_carrier','沿用目前分鏡，畫面證據尚未驗證。')},
            no_cut_reason=(s.get('direction') or {}).get('cut_out_reason','沿用目前來源鏡頭；尚未新增剪接判斷。')) for i,s in enumerate(local['shots'])}
        prov={'origin':'existing_formal_shots','source_hash':basis(p),'source_revision':p['revision'],
            'limitations':['沿用現有鏡頭及時長，未自動增寫戲劇或生成媒體。','文字卡與時間標記不是實際影片或音檔。']}
        t=create(pid,req.scene_id,plan,notes,original_audio(local),prov)
        return public(p,t)


@router.put('/api/projects/{pid}/editorial/{tid}')
def save(pid: str, tid: str, req: TrialEdit):
    from . import engine
    with engine.LOCK:
        trials, t = find(pid,tid)
        p=store.project(pid)
        if t['version'] != req.version:
            raise ValueError('試行已在另一視窗修改，請重新載入後再儲存。')
        formal=status(p,t)=='adopted'
        if status(p,t)=='stale':
            raise ValueError('正式方案已改變；舊試行已保留，請先重新比較來源。')
        if formal and req.production_revision!=p['revision']:
            raise ValueError('正式版本已更新，請重新載入後再儲存剪接。')
        previous=copy.deepcopy(t); previous.pop('history',None)
        validation_baseline=t['baseline']
        if formal:
            # Merge only these edit decisions into today's full plan; never restore old siblings.
            validation_baseline=copy.deepcopy(p['production'])
            t['plan']=copy.deepcopy(p['production'])
        ids={s['id'] for s in scope(t['plan'],t['scene_id'])['shots']}
        if any(e.get('shot_id') not in ids for e in req.edit_plan):
            raise ValueError('只可剪接本試行場景的來源鏡頭。')
        old=t['plan']['edit_plan']; position=next((i for i,e in enumerate(old) if e['shot_id'] in ids),len(old))
        outside=[e for e in old if e['shot_id'] not in ids]
        t['plan']['edit_plan']=outside[:position]+req.edit_plan+outside[position:]
        t['audio_cues']=req.audio_cues
        checked=validate_trial(t,validation_baseline)
        if formal and checked['warnings']:
            raise ValueError('有原有對白缺少完整聲音標記，請核對後再儲存正式剪接。')
        t['history'].append(previous); t['version']+=1; t['updated']=store.now()
        if formal:
            t['adopted_revision']=p['revision']+1
            # Keep source comparison of this scene, but accept unrelated current scenes.
            merged=copy.deepcopy(validation_baseline)
            for key,field in [('shots','scene_id'),('scenes','id')]:
                merged[key]=[s for s in t['baseline'][key] if s[field]==t['scene_id']]+[s for s in merged[key] if s[field]!=t['scene_id']]
            # Validation is against original source; ordering outside the scene is preserved.
            merged['edit_plan']=[e for e in t['baseline']['edit_plan'] if e['shot_id'] in {s['id'] for s in t['baseline']['shots'] if s['scene_id']==t['scene_id']}]+[e for e in validation_baseline['edit_plan'] if e['shot_id'] not in ids]
            t['baseline']=merged
            p=engine.save_plan(pid,t['plan'],p['revision'],'更新正式剪接與聲音時間表',setting_updates=lambda plan:compiled_settings(pid,t,trials,plan))
        else:store.put_setting('editorial_trials:'+pid,trials)
        return public(p,t)


@router.post('/api/projects/{pid}/editorial/{tid}/impact')
def impact(pid: str,tid: str,req: TrialEdit):
    from . import workflow_impact
    _,t=find(pid,tid);p=store.project(pid)
    if req.version!=t['version'] or req.production_revision!=p['revision']:raise ValueError('剪接資料已更新。')
    plan=copy.deepcopy(p['production']);ids={s['id'] for s in scope(plan,t['scene_id'])['shots']}
    if any(e.get('shot_id') not in ids for e in req.edit_plan):raise ValueError('只可修改本場剪接。')
    old=plan['edit_plan'];position=next((i for i,e in enumerate(old) if e['shot_id'] in ids),len(old))
    outside=[e for e in old if e['shot_id'] not in ids]
    plan['edit_plan']=outside[:position]+req.edit_plan+outside[position:]
    plan=models.Production.model_validate(plan).model_dump()
    result=workflow_impact.preview(p,plan)
    if req.audio_cues!=t['audio_cues']:
        result['dialogue_audio_unchanged']=False
        result['audio_changed_scenes']=list(set(result['audio_changed_scenes'])|{t['scene_id']})
    return result


@router.get('/api/projects/{pid}/editorial/{tid}/export')
def export(pid: str, tid: str):
    _, t=find(pid,tid)
    return public(store.project(pid),t)


@router.get('/editorial')
def page():
    return FileResponse(store.ROOT/'static/editorial.html',headers={'Cache-Control':'no-cache'})
