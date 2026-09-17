"""Storyboard edit uses and native H3 generation are independently addressable.

A group is one generated clip, never a selection for each constituent source Shot.
All cut ranges remain planned until the user records observed boundaries on a take.
"""
import copy
import hashlib
import json
import re
from typing import Literal
from fastapi import APIRouter
from pydantic import Field, model_validator, model_serializer
from . import store, models, continuity, asset_library, asset_roles, production_methods
from . import storyboard_usage

router = APIRouter()
POLICY = 'h3-montage-group-v1'
PLAN_CONTRACT_VERSION = 3


class UseContract(models.Strict):
    frame_uses: list[storyboard_usage.FrameUse] | None = Field(default=None,max_length=480)

    @model_serializer(mode='wrap')
    def compact_uses(self, handler):
        value=handler(self)
        if value.get('frame_uses') is None:value.pop('frame_uses',None)
        return value

class Definition(UseContract):
    id: str = Field(pattern=r'^mg_[a-f0-9]{16}$')
    title: str = Field(min_length=1, max_length=160)
    edit_ids: list[str] = Field(min_length=2, max_length=12)
    mode: Literal['I2VA', 'FL2VA', 'REF2VA']
    reference_targets: list[str] = Field(default_factory=list, max_length=9)
    reason: str = Field(min_length=1, max_length=2000)

class Save(models.Strict):
    revision: int
    production_revision: int
    group: Definition

class PromptSave(models.Strict):
    revision: int
    source_hash: str
    text: str

class Archive(models.Strict):
    revision: int
    archived: bool

class Adoption(models.Strict):
    revision: int

class Boundary(models.Strict):
    edit_id: str
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)

class Observed(models.Strict):
    source_hash: str
    boundaries: list[Boundary] = Field(min_length=2, max_length=12)
    note: str = Field(min_length=1, max_length=2000)


def is_group(gid):
    return bool(re.fullmatch(r'mg_[a-f0-9]{16}', gid or ''))


def config(pid):
    return store.setting('generation-groups:' + pid, {'revision': 0, 'groups': {}})


def resolve(p, definition):
    """Resolve consecutive edit uses; retain repeats as different edit IDs."""
    definition = Definition.model_validate(definition).model_dump()
    plan = p.get('production') or {}
    edits = plan.get('edit_plan', [])
    indices = {e['id']: i for i, e in enumerate(edits)}
    ids = definition['edit_ids']
    if len(set(ids)) != len(ids) or any(i not in indices for i in ids):
        raise ValueError('分組必須引用目前剪接表中不同的 edit ID。')
    positions = [indices[i] for i in ids]
    if positions != list(range(positions[0], positions[0] + len(ids))):
        raise ValueError('分組必須沿用連續的剪接次序；請先在導演方案調整順序。')
    shots = {s['id']: s for s in plan['shots']}
    members, cursor = [], 0.0
    speakers = {e['id']: f'S{i+1}' for i, e in enumerate(e for e in plan['canon'] if e['kind'] in ('character','crowd','voice'))}
    for index in positions:
        edit = edits[index]; shot = shots[edit['shot_id']]
        begin, end = edit['planned_edit_in'], edit['planned_edit_out']
        length = round(end - begin, 6)
        if not 0 <= begin < end <= shot['duration']:
            raise ValueError('分鏡選用範圍已失效。')
        dialogue = []
        for line in shot['dialogue']:
            if line['end'] <= begin or line['start'] >= end:
                continue
            if line['start'] < begin or line['end'] > end:
                raise ValueError('分組切點截斷對白；請先調整剪接範圍，或使用獨立聲音時間線。')
            dialogue.append({**line, 'start': round(cursor + line['start'] - begin, 6),
                             'end': round(cursor + line['end'] - begin, 6), 'speaker_id': speakers[line['entity_id']]})
        members.append({'edit_id': edit['id'], 'shot_id': shot['id'], 'scene_id': shot['scene_id'],
            'title': shot['title'], 'start': cursor, 'end': round(cursor + length, 6),
            'source_in': begin, 'source_out': end, 'edit': edit, 'shot': shot, 'dialogue': dialogue})
        cursor = round(cursor + length, 6)
    if len({m['scene_id'] for m in members}) != 1:
        raise ValueError('本版分組只支援同一 Scene；跨場請分開生成。')
    if not 4 <= cursor <= 15:
        raise ValueError('整組 H3 時長須為 4–15 秒；組內短鏡不受 4 秒下限限制。')
    scene = next(s for s in plan['scenes'] if s['id'] == members[0]['scene_id'])
    needed = {scene['location_id']} | {eid for m in members for eid in m['shot']['entity_ids']}
    canon = [e for e in plan['canon'] if e['id'] in needed]
    allowed = {e['id'] for e in canon if asset_roles.is_visual(e)} | {f['id'] for m in members for f in m['shot']['keyframes']}
    targets = definition['reference_targets']
    if len(set(targets)) != len(targets) or any(t not in allowed for t in targets):
        raise ValueError('參考圖必須來自組內分鏡或相關視覺身份，且不可重複。')
    if definition['mode'] != 'REF2VA' and targets:
        raise ValueError('首幀／首尾幀模式只使用對應端點；額外參考請選 Ref2VA。')
    return {'definition': definition, 'members': members, 'scene_id': scene['id'], 'scene': scene,
            'canon': canon, 'style': plan['style'], 'duration': cursor}


def prompt_source(p, gid):
    cfg = config(p['id']); entry = cfg['groups'].get(gid)
    if not entry: raise ValueError('找不到此生成分組。')
    if entry.get('archived'):raise ValueError('此分組已停用；原有工作和影片保留。')
    resolved = resolve(p, entry['definition']); mode = resolved['definition']['mode']
    members = resolved['members']; n = len(members); duration = resolved['duration']
    from . import storyboard_board
    board=storyboard_board.require_review(p,resolved['scene_id'],edit_ids=resolved['definition']['edit_ids'])
    targets = []
    if mode == 'REF2VA':
        targets = [(t, 'reference') for t in resolved['definition']['reference_targets']]
        if not targets: raise ValueError('請選用 1–9 張參考圖；不會自動改用文字生成。')
        alignment = 'Reference pictures establish appearance or the described storyboard composition; they do not lock cut times.'
    else:
        for member, moment in [(members[0], 'start')] + ([(members[-1], 'end')] if mode == 'FL2VA' else []):
            time=member['source_in'] if moment=='start' else member['source_out']
            frame=storyboard_board.frame_at(member['shot'],time)
            if not frame or (frame['moment']=='key' and (not board or not any(a['anchor']['frame_id']==frame['id'] for panel in board for a in panel['anchors']))):
                raise ValueError('所選剪接端點沒有已逐格審閱的對應畫面；請先安排視覺圖板或選 Ref2VA。')
            targets.append((frame['id'], moment))
        alignment = 'For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.'
        if mode == 'FL2VA':
            alignment += f' At {duration:.3f} seconds, <Picture 2> (from [Shot {n}]) is fully referenced as the final frame.'
    assets = p.get('assets') if 'assets' in p else store.assets(p['id'])
    refs = []
    for target, moment in targets:
        asset = continuity.approved_for(p['production'], assets, target)
        if not asset: raise ValueError(f'參考圖 {target} 尚未完成並批准。')
        path = asset_library.safe_path(asset['path'])
        if not path.is_file(): raise ValueError('已批准的參考圖檔案遺失。')
        entity = next((e for e in resolved['canon'] if e['id'] == target), None)
        frame = next((f for m in members for f in m['shot']['keyframes'] if f['id'] == target), None)
        refs.append({'target_id': target, 'asset_id': asset['id'], 'path': asset['path'],
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'label': f'Picture {len(refs)+1}',
            'moment': moment, 'scope': 'local', 'role': entity['kind'] if entity else 'storyboard',
            'description': entity['name'] if entity else frame['description']})
    uses=[]
    from . import conditioning
    conditioning.check_group(p,[m['shot_id'] for m in members],mode,refs)
    if 'frame_uses' in resolved['definition']:
        item={**resolved['definition'],'execution':'native_montage'}
        uses=storyboard_usage.bind(p,storyboard_usage.compile_uses(item,storyboard_usage.intent(p,resolved['scene_id']),p['production']),refs)
    return {**({'storyboard_usage':uses} if uses else {}),**({'storyboard_review':board} if board else {}),'policy': POLICY, 'kind': 'generation_group', 'shot_id': gid, 'mode': mode,
            **resolved, 'references': refs, 'alignment': alignment,
            'method_hash': production_methods.status()['hash']}


def timestamp(value):
    milliseconds = round(value * 1000)
    return f'{milliseconds // 60000:02d}:{milliseconds // 1000 % 60:02d}.{milliseconds % 1000:03d}'


def headers(src):
    return ['[Shot 1]'] + [f'[Shot {i+1}] At {timestamp(m["start"])}, the camera cuts to' for i, m in enumerate(src['members']) if i]


def dialogue_tags(src):
    return [f'<d>[{d["language"]}] {d["text"]}</d>' for m in src['members'] for d in m['dialogue']]


def speech_clauses(src, member):
    names={e['id']:e['name'] for e in src['canon']}
    return [f'From {d["start"]:.3f} to {d["end"]:.3f} seconds, {names[d["entity_id"]]} ({d["speaker_id"]}) says: <d>[{d["language"]}] {d["text"]}</d>' for d in member['dialogue']]


def build(p, req):
    from . import prompt_preparation
    if req.capability != 'h3_video_prompt':
        raise ValueError('生成分組使用已選做法；請在分組設定更改圖片模式。')
    src = prompt_source(p, req.target_id)
    prompt = '''Write ONE complete native multi-shot H3 video prompt for this approved ordered storyboard group. Return JSON {text:string, frame_issues:string[]}. English prose except exact original names and verbatim dialogue. Begin with the exact alignment, blank line, then exactly integrated_multimodal_description:, overall_soundscape:, non_diegetic_music: in order. Use the supplied shot headers verbatim, in order, exactly once INSIDE the integrated body. First shot has no cut timestamp. Every subsequent header specifies a hard editorial CUT, not a pan, morph or dissolve. Do not add cuts/views, reorder, merge or omit members. The group is ONE generation; each member is an editorial view, not a 4-second minimum source. Preserve composition, readable visual evidence, eye lines, hand/prop states and motivated cut reasons. The original source Shot is context: depict ONLY source_in..source_out, shift its events to the member's group start..end, do not replay the full source action or dialogue. Use the supplied group-time dialogue records with stable speaker IDs and exact tags, in that member's block, each exactly once. Omitted original-source dialogue outside the selected interval is not part of this group. Do not invent new events or premature information. Reference roles are explicit: identity is not a locked camera/keyframe; storyboard composition refs are not guaranteed timed cuts. I2VA/FL2VA fix only supplied endpoints. For REF2VA, a shared reference-role preamble may precede [Shot 1] inside the integrated body; describe each Picture's role there; no subject_definitions or shared global prompt. Explain concrete image/continuity discrepancies separately in Traditional Chinese frame_issues, while returning complete intended action without concealing discrepancies by morphing. Keep soundscape for physical/ambient sound only; no extra speech/narration/lyrics. Keep text below 7000 characters. No tools or media generation.\n'''
    return {'video_source': src, 'video_hash': store.digest(src), 'video_request_hash': store.digest([src,req.feedback,req.source_prompt]),
            'source_prompt': req.source_prompt, 'images': [str(store.DATA / r['path']) for r in src['references']],
            'prompt': prompt + prompt_preparation.SCOPE_RULES + '\nMANDATORY VERBATIM SPEECH CLAUSES: copy each entire clause exactly once in its matching Shot block. No quotation-only or screenplay-style substitution. Delivery/expression direction may surround the clause but not alter it.\n' + store.encode({str(i+1):speech_clauses(src,m) for i,m in enumerate(src['members'])}) + '\nEXACT HEADERS:\n' + store.encode(headers(src)) + '\nSOURCE DATA:\n' + store.encode(prompt_preparation.model_context(src)) + '\nUSER DRAFT:\n' + (req.source_prompt or '') + '\nFEEDBACK:\n' + req.feedback}


def validate_result(result, src):
    from . import prompt_preparation
    text = result['text'].replace('\r\n','\n'); result['text'] = text
    if len(text) > 7000 or not text.startswith(src['alignment'] + '\n\n'):
        raise ValueError('請保留整組的圖片對齊指令，提示詞不得超過 7000 字元。')
    fields = ['integrated_multimodal_description:', 'overall_soundscape:', 'non_diegetic_music:']
    positions = [text.find(f) for f in fields]
    if any(p < 0 for p in positions) or positions != sorted(positions) or any(text.count(f) != 1 for f in fields):
        raise ValueError('整組提示詞須保留三個 H3 段落及次序。')
    body = text[positions[0]+len(fields[0]):positions[1]].strip()
    if (src['mode']!='REF2VA' and not body.startswith('[Shot 1]')) or re.findall(r'\[Shot (\d+)\]', body) != [str(i+1) for i in range(len(src['members']))]:
        raise ValueError('分組鏡號必須完整、唯一並符合分鏡次序。')
    for h in headers(src):
        if body.count(h) != 1: raise ValueError('切鏡時間或鏡號已改變；請保留分組的精確切鏡標記。')
    blocks = re.split(r'\[Shot \d+\]', body)[1:]
    for member, block in zip(src['members'], blocks):
        expected = [f'<d>[{d["language"]}] {d["text"]}</d>' for d in member['dialogue']]
        if re.findall(r'<d>.*?</d>', block, re.S) != expected:
            raise ValueError('請逐字保留每個分鏡的對白及次序，不可把整段原 Shot 對白重播。')
        if any(block.count(clause)!=1 for clause in speech_clauses(src,member)):
            raise ValueError('請逐字保留對白子句的時間、說話者編號與原句。')
    if '<d>' in text[positions[1]:] or re.search(r'subject_definitions:|<Subject\s',text):
        raise ValueError('分組使用整合提示詞；不可混入主體段落或在聲景放入對白。')
    if not set(re.findall(r'Picture\s+(\d+)', text)) <= {str(i+1) for i in range(len(src['references']))}:
        raise ValueError('提示詞引用未附上的圖片。')
    prompt_preparation.english(text, prompt_preparation.original_names(src['canon']).values())


def render_source(p, gid):
    src = prompt_source(p,gid); prompt = config(p['id'])['groups'][gid].get('prompt', {})
    if prompt.get('source_hash') != store.digest(src):
        raise ValueError('請先生成並採用目前分組及圖片的 H3 提示詞。')
    validate_result({'text': prompt['text']}, src)
    mapping = [{k:m[k] for k in ('edit_id','shot_id','start','end','source_in','source_out')} for m in src['members']]
    return {**src, 'text': prompt['text'], 'global_prompt':'', 'frame_rate':24,
            'basis':src, 'strategy':{}, 'guide_from_previous':False,
            'mapping': {'status':'planned', 'boundaries':mapping}}


def arrangements(p, jobs=None):
    """Project the saved adoption, independently of newer candidate jobs."""
    cfg=config(p['id']); jobs=store.jobs(p['id']) if jobs is None else jobs
    by_job={j['id']:j for j in jobs}; plan=p.get('production') or {}
    scenes={s['id']:s for s in plan.get('scenes',[])}
    shots={s['id']:s for s in plan.get('shots',[])}
    edits={e['id']:e for e in plan.get('edit_plan',[])}
    rows=[]
    for scene_id,saved in cfg.get('plans',{}).items():
        job=by_job.get(saved.get('job_id'),{})
        status='current'; reason='已採用安排已接入下方 H3 製作。'
        if job.get('input',{}).get('group_plan_source',{}).get('plan_contract_version')!=PLAN_CONTRACT_VERSION:
            status='legacy'; reason='此舊安排未包含目前的逐張用圖契約，或曾混用剪接範圍與生成模式規則。既有模式與紀錄保留；請重新安排並採用。'
        else:
            try: current=plan_matches(planning_source(p,scene_id),saved.get('source_hash'),job)
            except (ValueError,KeyError): current=False
            if not current:
                status='stale'; reason='剪接意圖或製作方法已更新；已保存的安排需重新檢視並採用。'
        items=[]
        for index,item in enumerate(saved.get('result',{}).get('groups',[])):
            members=[];gid=''
            if status=='current':
                for eid in item['edit_ids']:
                    edit=edits[eid];shot=shots[edit['shot_id']]
                    members.append({'edit_id':eid,'shot_id':shot['id'],'title':shot['title'],
                        'source_in':edit['planned_edit_in'],'source_out':edit['planned_edit_out'],'duration':shot['duration']})
                if item['execution']=='native_montage':
                    candidate='mg_'+hashlib.sha256(f'{saved["job_id"]}:{index}'.encode()).hexdigest()[:16]
                    entry=cfg['groups'].get(candidate)
                    if entry and not entry.get('archived'):gid=candidate
            items.append({**copy.deepcopy(item),'members':members,'group_id':gid})
        rows.append({'scene_id':scene_id,'title':scenes.get(scene_id,{}).get('title','已移除場景'),
            'job_id':saved['job_id'],'summary':saved.get('result',{}).get('summary',''),
            'status':status,'reason':reason,'items':items})
    return rows


def source_arrangement(p, sid):
    """Only current independent-source requirements enter source prompt work."""
    uses=[]
    for arrangement in arrangements(p):
        if arrangement['status']!='current':continue
        for item in arrangement['items']:
            if item['execution']!='separate_source':continue
            for member in item['members']:
                if member['shot_id']==sid:
                    uses.append({**member,'reason':item['reason'],'checks':item['checks'],
                        **({'frame_uses':storyboard_usage.compile_uses(item,storyboard_usage.intent(p,arrangement['scene_id']),p['production'])} if 'frame_uses' in item else {})})
    if not uses:return None
    return {'execution':'separate_source','edit_uses':uses,
        'timing_rule':'Generate the entire original source from time zero through its full duration. These edit ranges are for later trimming, not generation endpoints or restrictions on image conditioning. Preserve applicable adopted visual requirements and use checks to assess the result; do not invent extra action or guarantee timing.'}


def state(p, jobs=None):
    cfg = config(p['id']); rows=[]; jobs=store.jobs(p['id']) if jobs is None else jobs
    for gid, entry in cfg['groups'].items():
        if entry.get('archived'):continue
        row = {**entry['definition'], 'shot_id':gid, 'kind':'generation_group', 'prompt':entry.get('prompt',{}),
               'checks':entry.get('checks',[]), 'reference_requirements':[],
               'reasons':[], 'source_hash':'', 'members':[], 'duration':0, 'ready':False, 'references':[]}
        try:
            row.update(resolve(p,entry['definition']))
            target_ids = list(entry['definition']['reference_targets'])
            if entry['definition']['mode']!='REF2VA':
                endpoints=[(row['members'][0],'start')]+([(row['members'][-1],'end')] if entry['definition']['mode']=='FL2VA' else [])
                from . import storyboard_board
                target_ids=[f['id'] for m,moment in endpoints if (f:=storyboard_board.frame_at(m['shot'],m['source_in'] if moment=='start' else m['source_out']))]
                for member,moment in endpoints:
                    time=member['source_in'] if moment=='start' else member['source_out']
                    if not storyboard_board.frame_at(member['shot'],time):
                        row['reference_requirements'].append({'target_id':None,'shot_id':member['shot_id'],
                            'source_time':time,'title':f'{member["title"]} · {time} 秒的{moment}畫面',
                            'role':'storyboard','asset':None,'ready':False,'action':'storyboard_plan'})
            assets=p.get('assets') if 'assets' in p else store.assets(p['id'])
            entities={e['id']:e for e in row['canon']}
            frames={f['id']:f for m in row['members'] for f in m['shot']['keyframes']}
            for target in target_ids:
                asset=continuity.approved_for(p['production'],assets,target)
                identity=entities.get(target)
                row['reference_requirements'].append({'target_id':target,'title':identity['name'] if identity else frames[target]['description'],
                    'role':identity['kind'] if identity else 'storyboard','asset':asset,
                    'ready':bool(asset and asset_library.safe_path(asset['path']).is_file())})
            src=prompt_source(p,gid); row.update(source_hash=store.digest(src),references=src['references'])
            row['ready']=entry.get('prompt',{}).get('source_hash')==row['source_hash']
            if not row['ready']:row['reasons'].append('請生成並採用目前分組的完整 H3 提示詞。')
        except (ValueError,OSError) as e:row['reasons'].append(str(e))
        j=next((j for j in jobs if j['target_id']==gid and j['capability']=='h3_video_prompt'),None)
        if j:row['job']={k:j[k] for k in ('id','state','result','error') } | {'stale': j['input'].get('video_hash')!=row['source_hash'], 'adopted':row['prompt'].get('job_id')==j['id']}
        rows.append(row)
    plans=[]
    for scene in (p.get('production') or {}).get('scenes',[]):
        j=next((j for j in jobs if j['target_id']==scene['id'] and j['capability']=='h3_group_plan'),None)
        if j:
            try: current=plan_matches(planning_source(p,scene['id']),j['input'].get('group_plan_hash'),j)
            except (ValueError,KeyError): current=False
            from . import generation_pipeline, engine
            plans.append({k:j[k] for k in ('id','state','result','error','target_id')} | {
                'progress':generation_pipeline.progress(j),'resumable':bool(j['input'].get('generation_pipeline') and current and j['state'] in ('failed','interrupted') and not engine.cancel_requested(j['id'])),
                'title':scene['title'],'stale':not current or j['input'].get('group_plan_source',{}).get('plan_contract_version')!=PLAN_CONTRACT_VERSION,
                'contract_current':j['input'].get('group_plan_source',{}).get('plan_contract_version')==PLAN_CONTRACT_VERSION,
                'adopted':cfg.get('plans',{}).get(scene['id'],{}).get('job_id')==j['id']})
    return {'revision':cfg['revision'],'rows':rows,'plans':plans,'arrangements':arrangements(p,jobs),'archived':[{'id':gid,'title':entry['definition']['title']} for gid,entry in cfg['groups'].items() if entry.get('archived')]}


@router.put('/api/projects/{pid}/generation-groups')
def save(pid: str, request: Save):
    from . import engine
    with engine.LOCK:
        p=store.project(pid); cfg=config(pid)
        if request.revision!=cfg['revision'] or request.production_revision!=p['revision']:
            raise ValueError('分組或分鏡已更新；請重新載入。')
        d=request.group.model_dump(); resolved=resolve(p,d)
        previous=cfg['groups'].get(d['id'],{}).get('definition',{})
        if 'frame_uses' in previous and 'frame_uses' not in d:d['frame_uses']=previous['frame_uses']
        if 'frame_uses' in d:
            storyboard_usage.compile_uses({**d,'execution':'native_montage'},storyboard_usage.intent(p,resolved['scene_id']),p['production'])
        if any(s['id']==d['id'] for s in p['production']['shots']):raise ValueError('分組 ID 不可與原 Shot 相同。')
        entry=cfg['groups'].setdefault(d['id'],{}); entry['definition']=d
        cfg['revision']+=1;store.put_setting('generation-groups:'+pid,cfg)
        return cfg


@router.put('/api/projects/{pid}/generation-groups/{gid}/prompt')
def save_prompt(pid: str, gid: str, request: PromptSave):
    from . import engine
    with engine.LOCK:
        cfg=config(pid);src=prompt_source(store.project(pid),gid)
        if cfg['revision']!=request.revision or store.digest(src)!=request.source_hash:
            raise ValueError('分組、圖片或分鏡已更新；草稿不可覆蓋新版。')
        validate_result({'text':request.text},src)
        cfg['groups'][gid]['prompt']={'text':request.text,'source_hash':request.source_hash,'job_id':''}
        cfg['revision']+=1;store.put_setting('generation-groups:'+pid,cfg)
        return cfg


@router.post('/api/projects/{pid}/generation-groups/adopt/{jid}')
def adopt(pid: str, jid: str, request: Adoption):
    from . import engine
    with engine.LOCK:
        cfg=config(pid);j=store.job(jid)
        if j['project_id']!=pid or j['capability']!='h3_video_prompt' or j['state']!='succeeded' or not is_group(j['target_id']):
            raise ValueError('只能採用本作品已完成的分組提示詞。')
        src=prompt_source(store.project(pid),j['target_id'])
        if cfg['revision']!=request.revision or store.digest(src)!=j['input'].get('video_hash'):
            raise ValueError('分組或圖片已更新，請重新生成。')
        validate_result(j['result'],src)
        cfg['groups'][j['target_id']]['prompt']={**j['result'],'source_hash':store.digest(src),'job_id':jid}
        cfg['revision']+=1;store.put_setting('generation-groups:'+pid,cfg)
        return cfg


@router.post('/api/projects/{pid}/generation-groups/takes/{tid}/boundaries')
def observe(pid: str, tid: str, request: Observed):
    from . import engine, video_render
    with engine.LOCK:
        t=video_render.take(pid,tid)
        if not is_group(t['shot_id']) or t['state']!='succeeded':raise ValueError('請選用已完成的分組影片。')
        if request.source_hash!=t['source_hash']:raise ValueError('影片來源不符。')
        video_render.output_path(t)
        expected=t['request']['source']['mapping']['boundaries']; rows=[b.model_dump() for b in request.boundaries]
        if [r['edit_id'] for r in rows]!=[r['edit_id'] for r in expected]:raise ValueError('實際切鏡紀錄必須完整保留分鏡次序。')
        previous=0
        for r in rows:
            if r['start']!=previous or not r['start']<r['end']<=t['result']['duration']+0.001:
                raise ValueError('請填寫從 0 秒開始、連續且不超過成片的實際切鏡範圍。')
            previous=r['end']
        receipt={'status':'user_observed','take_id':tid,'source_hash':t['source_hash'],
                 'boundaries':[{**e,**r} for e,r in zip(expected,rows)],'note':request.note,'recorded':store.now()}
        history=store.setting('generation-group-boundary-history:'+tid,[])
        previous=store.setting('generation-group-boundaries:'+tid)
        if previous and previous not in history:history.append(previous)
        store.put_setting('generation-group-boundary-history:'+tid,[*history,receipt])
        store.put_setting('generation-group-boundaries:'+tid,receipt)
        return receipt

# Planning is independent of pixel readiness; source shots and assets are not mutated.
class PlanItem(UseContract):
    @model_validator(mode='before')
    @classmethod
    def empty_provider_annotations(cls, value):
        # These two empty annotations carry no content. Nonempty or other
        # unknown fields still fail; raw provider/result.json is preserved.
        if isinstance(value,dict):
            value={k:v for k,v in value.items() if not (k in ('reason_note','checks_note') and v=='')}
        return value

    title: str = Field(min_length=1,max_length=160)
    edit_ids: list[str] = Field(min_length=1,max_length=12)
    execution: Literal['native_montage','separate_source']
    mode: Literal['I2VA','FL2VA','REF2VA'] | None = Field(description='Required null for separate_source; select a concrete mode only for native_montage. Independent source modes belong to the source video workspace.')
    reference_targets: list[str] = Field(max_length=9)
    reason: str = Field(min_length=1,max_length=2000)
    checks: list[str] = Field(min_length=1,max_length=6)

    @model_validator(mode='after')
    def conditioning_scope(self):
        if self.execution=='separate_source' and (self.mode is not None or self.reference_targets):
            raise ValueError('獨立來源的 mode 必須為 null、參考列表必須為空；請在逐鏡影片準備判斷生成模式。')
        if self.execution=='native_montage' and self.mode is None:
            raise ValueError('多鏡分組必須指定生成模式。')
        return self

class GroupPlan(models.Strict):
    summary: str = Field(min_length=1,max_length=2000)
    groups: list[PlanItem] = Field(min_length=1,max_length=40)


def planning_source(p,scene_id):
    plan=p['production']
    scene=next((s for s in plan['scenes'] if s['id']==scene_id),None)
    if not scene:raise ValueError('請選擇場景安排生成分組。')
    shots=[s for s in plan['shots'] if s['scene_id']==scene_id]; ids={s['id'] for s in shots}
    edits=[e for e in plan.get('edit_plan',[]) if e['shot_id'] in ids]
    if not edits:raise ValueError('請先完成場景的剪接次序。')
    needed={scene['location_id']}|{e for s in shots for e in s['entity_ids']}
    assets=p.get('assets') if 'assets' in p else store.assets(p['id'])
    readiness={}
    for shot in shots:
        for frame in shot['keyframes']:
            asset=continuity.approved_for(plan,assets,frame['id'])
            readiness[frame['id']]={'description_exists':True,'approved_image_available':bool(asset and asset_library.safe_path(asset['path']).is_file()),'asset_id':asset['id'] if asset else ''}
    from . import storyboard_board
    board=storyboard_board.scene_state(p,scene_id,assets)
    reviewed_frames=[a['frame_id'] for panel in board['panels'] for a in panel['anchors'] if a['ready']]
    from . import conditioning
    selected={s['id']:value['plan'] for s in shots if (value:=conditioning.saved(p,s['id']))}
    return {**({'source_conditioning':selected} if selected else {}),'storyboard_intent':storyboard_usage.intent(p,scene_id),'storyboard_reviewed_frames':reviewed_frames,'plan_contract_version':PLAN_CONTRACT_VERSION,'frame_readiness':readiness,'production':{'shots':shots,'scenes':[scene],'canon':[e for e in plan['canon'] if e['id'] in needed],
                          'style':plan['style'],'edit_plan':edits}, 'scene_id':scene_id,
            'edit_positions':{e['id']:i for i,e in enumerate(plan.get('edit_plan',[])) if e['shot_id'] in ids},
            'method_hash':production_methods.status()['hash']}


def planning_fingerprint(src):
    """Intent only. Creating, approving or reviewing a required image fulfils a plan."""
    value=copy.deepcopy(src)
    value.pop('frame_readiness',None)
    value.pop('storyboard_reviewed_frames',None)
    for shot in value['production']['shots']:
        shot.pop('keyframes',None)
    return store.digest({'contract':'generation-intent-v1','source':value})


def plan_matches(src, saved_hash, job):
    frozen=job.get('input',{}).get('group_plan_source')
    original=job.get('input',{}).get('group_plan_hash')
    if not frozen or saved_hash!=original:return False
    # Read-only migration: prove the old snapshot before using its narrower projection.
    if original not in (store.digest(frozen),planning_fingerprint(frozen)):return False
    return planning_fingerprint(src)==planning_fingerprint(frozen)


def build_plan(p,req):
    src=planning_source(p,req.target_id)
    prompt='''Act as the Studio director arranging H3 generation from an ALREADY ADOPTED storyboard/edit sequence. Return the supplied schema with concise Traditional Chinese explanations. Cover every edit_id exactly once, in original order. Do not change screenplay, shots, edit ranges, rhythm or revelation order. Choose a concrete execution, not alternatives.

GROUPING DECISION
native_montage uses 2+ consecutive edit uses in ONE 4–15 second clip; internal views may be shorter than 4 seconds. separate_source uses ONE edit use, generating its entire existing 4–15 second source and trimming afterward. Compare concrete visual risks: coherent same-space reframing can benefit from native cuts; exact evidence, changed subjects, complex blocking, critical sightlines or exact cut timing may justify independent generation. Do not default to separate sources because of frame count or force grouping to reduce jobs. Only compare consecutive edit uses; nonadjacent edits cannot form a group.

STORYBOARD IMAGE USE CONTRACT
For EVERY storyboard_intent anchor belonging to each group's edit_ids, return exactly one frame_uses entry: anchor_id, use (image_conditioning or planning_only), reason, boundary_exception. Do not omit approved stills or mistake their presence in source text for image input. Keep semantic role, source_time and scene_time distinct. Opening and CUT/new-view opening are strong generation boundary candidates: prefer an image-conditioned new source or include that actual composition image in a supported native group. Choosing planning_only for a boundary requires a concrete nonempty boundary_exception, visible for human adoption. Other key poses need a reasoned image_conditioning or planning_only decision; do not feed all frames into Ref2VA automatically. Planning-only means H3 will NOT receive this image through this contract; state how much relies on text and later footage review. A same-source timed keyframe is NOT automatically a cut; new camera setups must already be in the adopted editorial/source plan.
Native I2VA can bind only the group's first exact opening; FL2VA additionally its final exact endpoint; REF2VA must list every promised frame_id in reference_targets. An internal CUT image cannot be promised as a native I2VA input. For separate_source retain mode:null and references:[]; image_conditioning may require existing source start/end frames, which the source strategy must honour. This does not choose its mode. Interior/trimmed frames cannot be promised as full-source endpoints: choose a supported native REF2VA group, explicitly explain a planning-only exception, or request upstream boundary revision in the reasoning instead of claiming unsupported arbitrary splitting. This compiler does not invent new source shots, durations or cuts. With no adopted board use frame_uses:[] or omit it.

SEPARATE_SOURCE CONTRACT
Return mode: null and reference_targets: []. This planner does not choose or recommend a conditioning mode for an independent source, including in title, reason, checks or summary. The existing per-source video workspace owns that decision using its full source direction and actual references. Generate from time 0 to the ORIGINAL source duration, THEN trim edit_in..edit_out. For an 8-second source trimmed to 0.2..5.4, neither the nonzero edit-in nor the early edit-out excludes I2VA or FL2VA from the source workspace's choices; REF2VA is not required by trimming. Empty references mean the source workspace supplies its own approved inputs, not text-only generation or absence of references. Explain independent generation through visual and editorial needs, not mode restrictions.

NATIVE_MONTAGE CONTRACT ONLY
Honour source_conditioning when present: required source reference demands must survive in the group reference_targets and require REF2VA. Unresolved temporal or unsupported media constraints cannot be bypassed by grouping.
Choose I2VA, FL2VA or REF2VA for the group. I2VA requires an image at the first member's exact source_in; normally this is its start frame at zero. FL2VA also requires an image at the last member's exact source_out; normally its original end. Interior endpoint times are allowed ONLY when a frame exists at that exact source_time and its ID is in storyboard_reviewed_frames. Never substitute a source opening for a trimmed opening. These constraints apply only to native group conditioning. REF2VA selects 1–9 actual target IDs from related visual canon and/or group storyboard frames; do not invent IDs. Add references for new visual information when needed; simple reframing may reuse an opening image. Native groups must not straddle a dialogue line with a cut; use separate_source if the edit requires independent audio handling.

EVIDENCE AND REVIEW
Frame descriptions are plans, not inspected pixels. Consult frame_readiness; missing pixels may be prepared later but must never be called approved or inspected. Endpoint images constrain start/end appearance and pose only: they do not guarantee stationary hold duration, precise camera speed, action timing, intermediate states or cuts. Identity and composition references likewise do not guarantee timing. One generation likewise cannot guarantee continuity across its internal cuts: neither native montage nor independent generation guarantees correct hand/prop states, light positions, badge angles, readability or performance. Describe comparative tradeoffs rather than guaranteed success. Put such requirements in concrete generated-footage checks, never claims of guaranteed control. No contact-sheet shortcut. Provide honest grouping reasons and checks for readable evidence, cut versus pan, screen direction and hand/prop state. No tools or media generation.
'''
    prompt=prompt.replace('Interior endpoint times are allowed ONLY when a frame exists at that exact source_time and its ID is in storyboard_reviewed_frames.', 'Interior endpoint times are valid planning requirements even before a frame exists. Record the exact source time; Studio will require that frame and its pixel review before freezing or submitting. Never treat missing images as invalid grouping intent.')
    from . import shot_state
    return {'group_plan_source':src,'group_plan_hash':planning_fingerprint(src),'prompt':prompt+json.dumps(shot_state.model_view(src),ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\nUSER FEEDBACK:\n'+req.feedback,'images':[]}


def validate_plan(result,src):
    result=GroupPlan.model_validate(result).model_dump()
    from . import conditioning
    for item in result['groups']:
        if item['execution']!='native_montage':continue
        shot_ids={e['shot_id'] for e in src['production']['edit_plan'] if e['id'] in item['edit_ids']}
        for sid in shot_ids:
            selected=src.get('source_conditioning',{}).get(sid)
            if not selected:continue
            if selected.get('unresolved_constraints') or any(d['required'] and d['role'] in conditioning.UNSUPPORTED for d in selected.get('reference_demands') or []):
                raise ValueError('來源有未解決 conditioning 需求，不能用 native group 繞過。')
            if selected['mode']=='REF2VA' and (item['mode']!='REF2VA' or not {d['entity_id'] for d in selected['reference_demands'] if d['required']}<=set(item['reference_targets'])):
                raise ValueError('生成分組須承接已採用 source reference demands。')
    if [i for g in result['groups'] for i in g['edit_ids']] != [e['id'] for e in src['production']['edit_plan']]:
        raise ValueError('生成安排必須完整保留每個剪接項目及次序。')
    for item in result['groups']:
        storyboard_usage.compile_uses(item,src.get('storyboard_intent',[]),src['production'])
        if item['execution']=='separate_source':
            if len(item['edit_ids'])!=1 or item['reference_targets']:raise ValueError('獨立來源每項只引用一個剪接項目。')
        else:
            positions=[src['edit_positions'][eid] for eid in item['edit_ids']]
            if positions!=list(range(positions[0],positions[0]+len(positions))):raise ValueError('不可跨越其他場景的剪接項目合組。')
            d={k:item[k] for k in ('title','edit_ids','mode','reference_targets','reason','frame_uses') if k in item};d['id']='mg_'+'0'*16
            resolved=resolve(src,d)
            if item['mode']=='REF2VA' and not item['reference_targets']:raise ValueError('Ref2VA 分組必須列出實際參考目標。')
            # Exact endpoint controls are requirements, not pixel-readiness validation.
    return result


@router.post('/api/projects/{pid}/generation-groups/plan-adopt/{jid}')
def adopt_plan(pid: str,jid: str,request: Adoption):
    from . import engine
    with engine.LOCK:
        cfg=config(pid);j=store.job(jid)
        if j['project_id']!=pid or j['capability']!='h3_group_plan' or j['state']!='succeeded':raise ValueError('只能採用本作品已完成的生成安排。')
        if j['input'].get('group_plan_source',{}).get('plan_contract_version')!=PLAN_CONTRACT_VERSION:
            raise ValueError('這份舊安排可能混用剪接與生成模式規則，請重新安排後再採用。原始結果已保留。')
        src=planning_source(store.project(pid),j['target_id'])
        if cfg['revision']!=request.revision or not plan_matches(src,j['input'].get('group_plan_hash'),j):raise ValueError('分鏡或生成安排已更新，請重新規劃。')
        result=validate_plan(j['result'],src)
        if j['input'].get('generation_pipeline'):
            from . import generation_pipeline
            generation_pipeline.require_complete(j,result)
        previous=cfg.get('plans',{}).get(src['scene_id'],{}).get('job_id')
        if previous and previous!=jid:
            for entry in cfg['groups'].values():
                if entry.get('plan_job_id')==previous:entry['archived']=True
        for index,item in enumerate(result['groups']):
            if item['execution']!='native_montage':continue
            gid='mg_'+hashlib.sha256(f'{jid}:{index}'.encode()).hexdigest()[:16]
            if gid not in cfg['groups']:
                cfg['groups'][gid]={'definition':{'id':gid,**{k:item[k] for k in ('title','edit_ids','mode','reference_targets','reason','frame_uses') if k in item}},
                                    'plan_job_id':jid,'checks':item['checks']}
            cfg['groups'][gid]['archived']=False
        cfg.setdefault('plans',{})[src['scene_id']]={'job_id':jid,'source_hash':j['input']['group_plan_hash'],'intent_hash':planning_fingerprint(src),'result':result}
        cfg['revision']+=1;store.put_setting('generation-groups:'+pid,cfg)
        return cfg


@router.post('/api/projects/{pid}/generation-groups/{gid}/archive')
def archive(pid: str, gid: str, request: Archive):
    from . import engine
    with engine.LOCK:
        store.project(pid);cfg=config(pid)
        if cfg['revision']!=request.revision or gid not in cfg['groups']:raise ValueError('分組已更新或不存在。')
        cfg['groups'][gid]['archived']=request.archived
        cfg['revision']+=1;store.put_setting('generation-groups:'+pid,cfg)
        return cfg
