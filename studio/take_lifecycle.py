"""Take compatibility is editorial evidence, independent of execution readiness.

Receipts are append-only settings records. Frozen requests and successful outputs
are never rewritten when an editor changes direction or rejects a candidate.
"""
import copy
import json
from . import store, asset_roles, asset_library, continuity


def shot_intent(shot):
    result=copy.deepcopy(shot)
    result.pop('keyframes',None)
    return result


def unit_basis(p, sid, definition=None):
    from . import generation_groups as groups
    plan=p['production']
    if groups.is_group(sid):
        definition=definition or groups.config(p['id'])['groups'].get(sid,{}).get('definition')
        if not definition:raise ValueError('原生成分組已無目前定義。')
        resolved=groups.resolve(p,definition)
        shots=[m['shot'] for m in resolved['members']]
        unit={'definition':resolved['definition'],'members':[
            {k:m[k] for k in ('edit_id','shot_id','source_in','source_out','start','end')}
            for m in resolved['members']]}
    else:
        shots=[s for s in plan['shots'] if s['id']==sid]
        if not shots:raise ValueError('原來源 Shot 已移除。')
        unit={'shot_id':sid}
    scene=next(s for s in plan['scenes'] if s['id']==shots[0]['scene_id'])
    ids={scene['location_id']}|{e for s in shots for e in s['entity_ids']}
    first=plan['shots'].index(shots[0]);last=plan['shots'].index(shots[-1])
    previous=plan['shots'][first-1] if first else None
    following=plan['shots'][last+1] if last+1<len(plan['shots']) else None
    return {'version':1,'unit':unit,'shots':[shot_intent(s) for s in shots],
        'scene':scene,'style':plan['style'],
        'incoming':{k:previous[k] for k in ('id','scene_id','end_state')} if previous else None,
        'outgoing':{k:following[k] for k in ('id','scene_id','start_state')} if following else None,
        'canon':[asset_roles.visual_identity(e) for e in plan['canon'] if e['id'] in ids]}


def legacy_basis(p,t):
    """Recover only from a revision proven to contain the frozen source Shot(s)."""
    src=t['request']['source']
    raw=src.get('basis',{}).get('source',src.get('basis',{}))
    frozen_shots=[m['shot'] for m in src.get('members',[])] or ([raw['shot']] if raw.get('shot') else [])
    if not frozen_shots:return None
    with store.db() as c:
        rows=c.execute('SELECT production FROM revisions WHERE project_id=? AND created<=? ORDER BY number DESC',
                       (p['id'],t['created'])).fetchall()
    for row in rows:
        plan=json.loads(row['production'])
        neighbors=[raw[k] for k in ('previous_shot','next_shot') if raw.get(k)]
        if all(s in plan['shots'] for s in [*frozen_shots,*neighbors]):
            try:return unit_basis({**p,'production':plan},t['shot_id'],src.get('definition'))
            except (ValueError,KeyError,StopIteration):return None
    return None


def reviews(pid,tid):
    return store.setting('video-take-reviews:'+pid+':'+tid,[])


def generation_intent(p,sid):
    """Saved choices only; no readiness gates, image reads or prompt rebuilding."""
    from . import generation_groups, video_workflow, delivery
    if generation_groups.is_group(sid):
        entry=generation_groups.config(p['id'])['groups'].get(sid,{})
        return {'mode':entry.get('definition',{}).get('mode'),'text':entry.get('prompt',{}).get('text')}
    entry=video_workflow.config(p['id'])['shots'].get(sid,{})
    result={'mode':entry.get('mode','I2VA'),'strategy':(entry.get('strategy') or {}).get('result'),
        'text':entry.get('prompt',{}).get('text')}
    if result['mode']=='REF2VA':
        shot=next((s for s in p['production']['shots'] if s['id']==sid),{})
        scene=delivery.configuration(p['id']).get('scenes',{}).get(shot.get('scene_id'),{})
        result.update(text=scene.get('chapters',{}).get(sid,{}).get('shot_prompt'),global_prompt=scene.get('global_prompt'))
    return result


def compatibility(p,t):
    reasons=[]
    original=t['request'].get('editorial_basis') or legacy_basis(p,t)
    try:current=unit_basis(p,t['shot_id'])
    except (ValueError,KeyError,StopIteration):
        current=None;reasons.append('原來源或分組已改動，請對照目前剪接重新核對。')
    if original is None:reasons.append('舊工作缺少可證明的完整依賴快照，需要人工核對。')
    elif current!=original:reasons.append('目前剪接／畫面意圖與原生成快照不同。')
    intent=generation_intent(p,t['shot_id'])
    if 'generation_intent' in t['request']:
        if intent!=t['request']['generation_intent']:reasons.append('已保存的生成模式、做法或提示詞已更改。')
    elif intent.get('text') and intent['text']!=t['request']['source']['text']:
        reasons.append('目前已保存提示詞與原影片不同，需要看片核對。')
    assets=p.get('assets') if 'assets' in p else store.assets(p['id'])
    refs=[]
    for ref in t['request']['source']['references']:
        asset=next((a for a in assets if a['id']==ref['asset_id']),None)
        approved=None
        if asset:
            try:approved=continuity.approved_for(p['production'],assets,asset['target_id'])
            except ValueError:pass
        signature={'asset_id':ref['asset_id'],'approved_id':approved['id'] if approved else None,'sha256':None}
        if approved:
            try:
                path=asset_library.safe_path(approved['path'])
                if path.is_file():
                    from .video_render import file_hash
                    signature['sha256']=file_hash(path)
            except (ValueError,OSError):pass
        if signature['approved_id']!=ref['asset_id'] or signature['sha256']!=ref['sha256']:
            reasons.append('原參考圖片的目前批准版本或檔案已改變。')
        refs.append(signature)
    fingerprint=store.digest({'version':1,'take':t['id'],'basis':current,'references':refs,'intent':intent})
    receipt=next((r for r in reversed(reviews(p['id'],t['id'])) if r.get('compatibility_hash')==fingerprint),None)
    status='compatible' if not reasons else 'needs_review'
    if receipt and receipt.get('compatibility_accepted'):status='reviewed_compatible'
    return {'status':status,'current_hash':fingerprint,'reasons':list(dict.fromkeys(reasons))}


def accepted_compatibility(value):
    return value['status'] in ('compatible','reviewed_compatible')


def review_status(pid,tid,selected=False):
    history=reviews(pid,tid)
    return history[-1]['decision'] if history else ('accepted' if selected else 'unreviewed')


def record(pid,tid,decision,compatibility_hash=None):
    history=reviews(pid,tid)
    receipt={'decision':decision,'recorded':store.now(),'actor':'user',
        'compatibility_hash':compatibility_hash,'compatibility_accepted':decision=='accepted' and bool(compatibility_hash)}
    store.put_setting('video-take-reviews:'+pid+':'+tid,[*history,receipt])
    return receipt
