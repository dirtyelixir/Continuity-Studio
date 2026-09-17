"""Shared mode decision and deterministic reference-demand compiler. No provider calls.

Shot strategy and image-demand planning share this contract. Assets fulfil intent;
they never infer it. Legacy routes remain readable until a new decision is adopted.
"""
import copy,hashlib,re
from . import models,store,continuity,asset_roles,asset_library

VERSION=1
UNSUPPORTED={'motion_reference','video_reference','audio_reference'}
RULES='''UNIFIED CONDITIONING DECISION v1. Decide from this shot's requirements, not storyboard count, source trims or all available scene assets. Default I2VA when a composed opening sufficiently conveys staging and identity. FL2VA only when the actual source ending needs image anchoring. REF2VA when reusable character/object/appearance/environment references are necessary and an opening composition is insufficient or would unnecessarily constrain the intended staging. Multiple characters alone do not force REF2VA. Return reference_demands: [] for I2VA/FL2VA. For REF2VA select the smallest necessary set: entity_id, semantic role, required, specific reason, and 1–3 exact excerpts from this shot's requirements/canon supporting that need. Scope is this shot, not the Scene's union. Exclude irrelevant or offscreen entities; do not infer demand from mere asset availability. Multiple roles for the same entity share one image slot. Optional demands are explicitly omitted from execution by default; make a demand required only when this generation needs it. Do not fabricate approved asset IDs or Picture numbers: Studio assigns those deterministically after adoption. Do not list timeline storyboard frames as identity references. character_identity/object_identity/environment_reference/appearance_consistency/reusable_visual_reference use canon image assets. motion_reference/video_reference/audio_reference are not supported in the current Studio one-click path; required demands for these remain unresolved. A timestamp-critical intermediate state cannot be satisfied by general references: record it in unresolved_constraints (including an internal-segmentation candidate if appropriate), never promise timed interpolation. Preserve editorial cuts, source timings, plot, dialogue, canon and approved images. Never split an editorial shot because it has multiple frames.'''


def requirements(p,sid):
    shot=next(s for s in p['production']['shots'] if s['id']==sid)
    scene=next(s for s in p['production']['scenes'] if s['id']==shot['scene_id'])
    ids=set(shot['entity_ids'])|{scene['location_id']}
    return {'shot':{k:copy.deepcopy(v) for k,v in shot.items() if k!='keyframes'},
        'location_id':scene['location_id'],'style':p['production']['style'],
        'canon':[copy.deepcopy(e) for e in p['production']['canon'] if e['id'] in ids]}


def decision(value):
    return models.ConditioningDecision.model_validate({k:value[k] for k in models.ConditioningDecision.model_fields if k in value}).model_dump()


def strings(value):
    if isinstance(value,str):yield value
    elif isinstance(value,dict):
        for v in value.values():yield from strings(v)
    elif isinstance(value,list):
        for v in value:yield from strings(v)


def validate(value,req):
    plan=decision(value);demands=plan['reference_demands']
    if demands is None and plan['mode']!='REF2VA':demands=[];plan['reference_demands']=[]
    if demands is None:raise ValueError('模式方案須明確列出 reference_demands；不會從 Scene 素材自動補入。')
    if plan['mode']!='REF2VA' and demands:raise ValueError('只有 Ref2VA 使用 reference demands；首尾時間約束不能混作身份參考。')
    if plan['mode']=='REF2VA' and not any(d['required'] for d in demands):raise ValueError('Ref2VA 至少需要一項真正必要的 reference demand。')
    canon={e['id']:e for e in req['canon']};seen=set();texts=list(strings(req))
    for d in demands:
        key=(d['entity_id'],d['role'])
        if key in seen:raise ValueError('同一身份及 reference role 不可重複。')
        seen.add(key)
        entity=canon.get(d['entity_id'])
        if not entity:raise ValueError('Reference demand 不屬於本鏡，不能帶入其他鏡頭的 Scene 素材。')
        if not d['reason'].strip() or any(not q.strip() or not any(q in t for t in texts) for q in d['evidence']):
            raise ValueError('Reference demand 必須有本鏡需求／身份原文依據。')
        role,kind=d['role'],entity['kind']
        allowed={'character_identity':{'character','crowd'},'object_identity':{'prop'},'environment_reference':{'location'},'appearance_consistency':{'character','crowd','prop'}}
        if role in allowed and kind not in allowed[role]:raise ValueError('Reference role 與 canon 類型不符。')
        if role not in UNSUPPORTED and not asset_roles.is_visual(entity):raise ValueError('此身份沒有可用於影像 conditioning 的視覺角色。')
    if len({d['entity_id'] for d in demands if d['required'] and d['role'] not in UNSUPPORTED})>9:
        raise ValueError('本鏡 required references 超過 H3 九個圖片槽；請修訂需求，不能靜默略去。')
    if any(not s.strip() for s in plan['unresolved_constraints']):raise ValueError('未解決約束必須具體說明。')
    return plan


def saved(p,sid):
    return store.setting('video-workflow:'+p['id'],{'shots':{}})['shots'].get(sid,{}).get('conditioning')


def snapshot(p,sid,value,job_id):
    req=requirements(p,sid)
    return {'version':VERSION,'plan':validate(value,req),'requirements_hash':store.digest(req),'job_id':job_id}


def current(p,sid):
    entry=saved(p,sid)
    if entry and entry.get('version')!=VERSION:raise ValueError('不支援此 conditioning decision 版本；請重新分析。')
    if entry and entry['requirements_hash']!=store.digest(requirements(p,sid)):
        raise ValueError('本鏡 conditioning 需求已更新，請重新分析及採用；不會沿用過期選圖。')
    return entry


def resolve(p,sid,*,strict=True):
    entry=current(p,sid)
    if not entry:return None
    return resolve_plan(p,sid,entry['plan'],strict=strict)


def resolve_plan(p,sid,plan,*,strict=True):
    plan=validate(plan,requirements(p,sid));assets=p.get('assets') if 'assets' in p else store.assets(p['id'])
    canon={e['id']:e for e in p['production']['canon']};refs=[];rows=[];errors=list(plan['unresolved_constraints'])
    image_entities=list(dict.fromkeys(d['entity_id'] for d in plan['reference_demands'] if d['required'] and d['role'] not in UNSUPPORTED))
    slots={eid:i+1 for i,eid in enumerate(image_entities)};by_asset={}
    for demand in plan['reference_demands']:
        entity=canon[demand['entity_id']];d={**demand,'name':entity['name'],'kind':entity['kind'],
            'status':'optional_omitted','asset_id':None,'sha256':None,'label':None,'subject':None,'asset':None}
        if not d['required']:rows.append(d);continue
        if d['role'] in UNSUPPORTED:
            d['status']='unsupported';errors.append(entity['name']+'：目前不支援 '+d['role']);rows.append(d);continue
        n=slots[entity['id']];d.update(label=f'Picture {n}',subject=f'Subject {n}')
        a=continuity.approved_for(p['production'],assets,entity['id'])
        path=asset_library.safe_path(a['path']) if a else None
        if not a or not path.is_file():
            d['status']='missing';errors.append(entity['name']+'：缺少目前有效的已批准 reference');rows.append(d);continue
        if a['id'] not in by_asset:
            refs.append({'target_id':entity['id'],'asset_id':a['id'],'path':a['path'],
                'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'label':f'Picture {n}','subject':f'Subject {n}',
                'role':d['role'],'name':entity['name'],'kind':entity['kind'],'scope':'local'})
            by_asset[a['id']]=refs[-1]
        ref=by_asset[a['id']]
        d.update(status='ready',asset=a,**{k:ref[k] for k in ('asset_id','sha256','label','subject')});rows.append(d)
    if strict and errors:raise ValueError('未解決的 conditioning 約束：'+'；'.join(errors))
    return {'plan':plan,'demands':rows,'references':refs,'unresolved':errors}


def check_source(source):
    if 'reference_demands' not in source:return
    refs=source['references'];required=[d for d in source['reference_demands'] if d['required']]
    keys=lambda r:(r['asset_id'],r['sha256'],r['label'],r['subject'],r.get('target_id',r.get('entity_id')))
    if source['mode']!='REF2VA' or any(d['status']!='ready' for d in required) or not required:
        raise ValueError('Ref2VA required demand 未完成，不能建立 graph。')
    if len(refs)!=len({keys(r) for r in refs}) or [r['label'] for r in refs]!=[f'Picture {i+1}' for i in range(len(refs))] or [r['subject'] for r in refs]!=[f'Subject {i+1}' for i in range(len(refs))] or {keys(d) for d in required}!={keys(r) for r in refs}:
        raise ValueError('Ref2VA 實際用圖與凍結 reference demands 不一致。')


def check_group(p,shot_ids,mode,references):
    for sid in set(shot_ids):
        entry=current(p,sid)
        if not entry:continue
        resolved=resolve(p,sid)
        if entry['plan']['mode']!='REF2VA':continue
        if mode!='REF2VA' or not {r['asset_id'] for r in resolved['references']}<={r['asset_id'] for r in references}:
            raise ValueError('Native group 沒有承接已採用 source 的 required reference demands。')


def prompt_context(source,old_refs):
    """Remove obsolete Scene slot identities from interpretation text, not saved prose."""
    out=copy.deepcopy(source)
    names={r[k]:r.get('name',r.get('target_id','reference')) for r in old_refs for k in ('label','subject') if r.get(k)}
    for key in ('current_prompt','global_prompt'):
        text=out.get(key,'')
        # Dialogue words are immutable, including any literal bracketed words.
        parts=re.split(r'(<d>.*?</d>)',text,flags=re.S)
        out[key]=''.join(part if part.startswith('<d>') else re.sub(r'<((?:Picture|Subject) \d+)>',lambda m:names.get(m[1],m[0]),part) for part in parts)
    return out
