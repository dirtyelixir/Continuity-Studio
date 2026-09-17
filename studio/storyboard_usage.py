"""Compile adopted board intent into existing generation routes, without media mutation.

Editorial roles and execution uses are separate. Source timestamps never imply cuts.
Legacy plans remain readable; only explicit new use contracts assert image coverage.
"""
import copy
import hashlib
import json
from pathlib import Path
from typing import Literal
from pydantic import Field
from . import models, store


class FrameUse(models.Strict):
    anchor_id: str
    use: Literal['image_conditioning', 'planning_only']
    reason: str = Field(min_length=1, max_length=1200)
    boundary_exception: str = Field(default='', max_length=1200)


def intent(p, scene_id):
    """Immutable intent projection: no pixels, approval counters or job availability."""
    from . import storyboard_board as board
    entry=board.config(p['id'])['scenes'].get(scene_id) if p.get('id') else None
    if not entry:return []
    src=board.source(p,scene_id)
    if entry['source_hash']!=store.digest(src):
        raise ValueError('視覺圖板已過期，請重新安排圖板後再編譯生成用途。')
    shots={s['id']:s for s in src['shots']};edits={e['id']:e for e in src['edits']}
    rows=[];cursor=0.0
    for index,panel in enumerate(entry['panels']):
        edit=edits[panel['edit_id']];shot=shots[panel['shot_id']]
        for n,a in enumerate(panel['anchors']):
            frame=next(f for f in shot['keyframes'] if f['id']==a['frame_id'])
            role=a.get('semantic_role') or (('opening' if index==0 else 'cut_opening') if n==0 else ('final_frame' if frame['moment']=='end' else 'intermediate_keyframe'))
            rows.append({'anchor_id':a['id'],'edit_id':panel['edit_id'],'shot_id':shot['id'],
                'frame_id':frame['id'],'source_time':a['time'],
                'scene_time':round(cursor+a['time']-edit['planned_edit_in'],6),
                'role':role,'boundary_candidate':n==0,'moment':frame['moment'],
                'purpose':a['purpose'],'description':frame['description'],
                'state':shot['start_state'] if frame['moment']=='start' else shot['end_state'] if frame['moment']=='end' else frame['state'],
                'cut_reason':panel['reason'],
                **({'required_binding':a['generation_binding'],'required_mode':panel['image_plan']['mode']} if a.get('generation_binding') else {})})
            if a.get('generation_binding') and not edit['planned_edit_in']<=a['time']<=edit['planned_edit_out']:
                rows[-1]['scene_time']=None
        cursor+=edit['planned_edit_out']-edit['planned_edit_in']
    return rows


def compile_uses(item, rows, production):
    """Reject missing decisions and claims unsupported by the selected route.

Independent full-source mode stays with the source strategy. Its exact endpoint
requirements are passed on, then checked against actual selected image references.
Arbitrary intra-source segments are not invented here.
"""
    expected=[r for r in rows if r['edit_id'] in item['edit_ids']]
    uses=[FrameUse.model_validate(u).model_dump() for u in (item.get('frame_uses') or [])]
    if len(uses)!=len(expected) or {u['anchor_id'] for u in uses}!={r['anchor_id'] for r in expected}:
        raise ValueError('生成安排須逐張交代圖板用途，不能省略、重複或引用其他剪接的畫面。')
    by_id={u['anchor_id']:u for u in uses}
    edits={e['id']:e for e in production['edit_plan']}
    first,last=edits[item['edit_ids'][0]],edits[item['edit_ids'][-1]]
    result=[]
    for row in expected:
        u=by_id[row['anchor_id']]
        if not u['reason'].strip():raise ValueError('分鏡用途必須有具體原因。')
        binding='planning_only'
        if u['use']=='planning_only':
            if row.get('required_binding'):raise ValueError('圖板已採用實際用圖要求，生成安排不能將它降為 planning-only。')
            if row['boundary_candidate'] and not u['boundary_exception'].strip():
                raise ValueError('開場／CUT 入點預設是影像約束候選；只供規劃須明示不傳圖的例外原因。')
        elif item['execution']=='separate_source':
            if row['moment'] not in ('start','end'):
                raise ValueError('獨立來源只生成完整 source：中間畫面不能冒充首尾幀。請用可引用此圖的原生 Ref2VA 分組、修訂上游生成邊界，或明示 planning-only 例外。')
            binding='source_'+row['moment']
        elif item['mode']=='REF2VA':
            if row.get('required_binding'):raise ValueError('已採用的首尾時間約束不能當成 Ref2VA 一般參考；請先修訂用圖方案。')
            if row['frame_id'] not in item['reference_targets']:
                raise ValueError('承諾用作影像約束的分鏡未列入 Ref2VA reference_targets。')
            binding='reference'
        elif row['edit_id']==first['id'] and abs(row['source_time']-first['planned_edit_in'])<1e-6:
            binding='start'
        elif item['mode']=='FL2VA' and row['edit_id']==last['id'] and abs(row['source_time']-last['planned_edit_out'])<1e-6:
            binding='end'
        else:
            raise ValueError('此 I2VA／FL2VA 分組不會收到該中間／CUT 圖片；請調整分組或明示 planning-only 決定。')
        result.append({**row,**u,'binding':binding})
    return result


def source_uses(p, sid):
    from . import generation_groups as groups
    # A generation-needed board owns a source requirement even before grouping.
    # Existing generation_groups may add requirements but cannot erase it.
    shot=next(s for s in p['production']['shots'] if s['id']==sid)
    from . import storyboard_board as board
    entry=board.config(p['id'])['scenes'].get(shot['scene_id'],{})
    result=[]
    if entry.get('image_policy') in board.IMAGE_POLICIES:
        result=[{**r,'use':'image_conditioning','reason':'已採用生成所需圖片方案。',
            'boundary_exception':'','binding':'source_'+r['required_binding']}
            for r in intent(p,shot['scene_id']) if r['shot_id']==sid]
    for arrangement in groups.arrangements(p):
        if arrangement['status']!='current':
            edits={e['id']:e['shot_id'] for e in p['production'].get('edit_plan',[])}
            if any(i.get('frame_uses') and i['execution']=='separate_source' and any(edits.get(e)==sid for e in i['edit_ids']) for i in arrangement['items']):
                raise ValueError('已採用的分鏡用圖安排已過期，請重新安排；不會靜默移除用圖要求。')
            continue
        for item in arrangement['items']:
            if item['execution']=='separate_source' and any(m['shot_id']==sid for m in item['members']):
                result+=compile_uses(item,intent(p,arrangement['scene_id']),p['production'])
    return list({u['anchor_id']:u for u in result}.values())


def bind(p, uses, references):
    """Resolve each promised image to the exact reviewed asset, not just a frame ID."""
    from . import storyboard_board as board
    if not uses:return []
    scenes={s['id']:s['scene_id'] for s in p['production']['shots']}
    review={}
    for sid in {scenes[u['shot_id']] for u in uses}:
        for panel in board.scene_state(p,sid,p.get('assets'))['panels']:
            for a in panel['anchors']:review[a['id']]=a
    result=[]
    for use in uses:
        a=review.get(use['anchor_id'])
        if not a or not a['ready']:raise ValueError('分鏡用途所引用的畫面尚未完成目前版本的逐格審閱。')
        fp=a['review']['fingerprint']
        ref=next((r for r in references if r['asset_id']==fp['asset_id'] and r.get('sha256',fp['sha256'])==fp['sha256']),None)
        if use['use']=='image_conditioning' and not ref:
            raise ValueError('生成安排承諾使用分鏡 '+use['frame_id']+'，但目前模式的實際 image input 沒有此圖。請更新來源模式／生成安排。')
        result.append({**use,'asset_id':fp['asset_id'],'sha256':fp['sha256'],
            'actual_input':bool(ref),'input_label':ref['label'] if ref else None,
            'input_moment':ref.get('moment') if ref else None})
    return result


def check_graph_source(source):
    """Last deterministic guard, including offline/exported frozen requests."""
    refs=source['references']
    for u in source.get('storyboard_usage',[]):
        if u['use']=='image_conditioning' and not any(r['asset_id']==u['asset_id'] and r.get('sha256')==u['sha256'] and r['label']==u['input_label'] for r in refs):
            raise ValueError('凍結圖板用圖承諾與 H3 實際輸入不一致；尚未提交。')


def submitted_inputs(p):
    """Evidence of submitted graph bindings; never a claim of successful pixels."""
    with store.db() as c:
        takes=[dict(r) for r in c.execute('SELECT id,state,prompt_id,request FROM video_takes WHERE project_id=? ORDER BY created',(p['id'],))]
    result=[]
    for take in takes:
        root=store.DATA/'video'/take['id']
        try:
            request=json.loads(take['request']);src=request['source']
            transport=json.loads((root/'transport.json').read_text())
            receipt=json.loads((root/'receipt.json').read_text())
            graph=json.loads((root/'graph.json').read_text())
            if receipt.get('prompt_id')!=take['prompt_id'] or not take['prompt_id']:continue
            strict_demands='reference_demands' in src
            if strict_demands:
                from . import conditioning
                conditioning.check_source(src)
                if receipt.get('studio_workflow_hash')!=store.digest(graph):continue
            timeline=json.loads(graph['12']['inputs']['timeline_data'])
            bound=[]
            for seg in timeline.get('segments',[]):
                bound += [(key,seg[key]) for key in ('startImage','endImage') if seg.get(key)]
                bound += [('reference',r) for r in seg.get('refs',[])]
            bound += [('reference',r) for r in timeline.get('global',{}).get('refs',[])]
            for index,ref in enumerate(src['references']):
                upload=transport.get('uploads',{}).get(ref['asset_id'])
                if not upload:continue
                path=str(Path(upload['subfolder'])/upload['name'])
                if strict_demands:
                    frozen=root/f'input-{index}{Path(ref["path"]).suffix.lower()}'
                    if upload.get('verified_sha256')!=ref['sha256'] or hashlib.sha256(frozen.read_bytes()).hexdigest()!=ref['sha256']:continue
                roles=[kind for kind,r in bound if r.get('imageFile')==path and (not strict_demands or r.get('index')==int(ref['label'].split()[-1])-1)]
                if roles:result.append({'take_id':take['id'],'state':take['state'],'unit_id':src['shot_id'],
                    'mode':src['mode'],'asset_id':ref['asset_id'],'sha256':ref['sha256'],
                    'roles':roles,'prompt_id':take['prompt_id'],'graph_path':str(root/'graph.json')})
        except (OSError,ValueError,KeyError,TypeError):
            continue  # Incomplete evidence is unknown, never an inferred submission.
    return result


def annotate(p, scenes):
    """UI projection: current plan intentions and actual receipts shown separately."""
    from . import generation_groups as groups
    submissions=submitted_inputs(p);arrangements=groups.arrangements(p)
    for scene in scenes:
        try:rows=intent(p,scene['scene_id'])
        except ValueError:rows=[]
        roles={r['anchor_id']:r for r in rows};planned={}
        for r in rows:
            if r.get('required_binding'):
                planned[r['anchor_id']]={**r,'use':'image_conditioning','binding':'source_'+r['required_binding'],
                    'unit_id':r['shot_id'],'route_active':True,'reason':'已採用 '+r['required_mode']+' 所需圖片；提交前核對實際素材。'}
        for a in arrangements:
            if a['scene_id']!=scene['scene_id'] or a['status']!='current':continue
            for item in a['items']:
                try:compiled=compile_uses(item,rows,p['production'])
                except ValueError:continue
                for use in compiled:
                    planned[use['anchor_id']]={**use,'unit_id':item.get('group_id') or use['shot_id'],
                        'route_active':item['execution']=='separate_source' or bool(item.get('group_id'))}
        for panel in scene['panels']:
            for anchor in panel['anchors']:
                fp=(anchor.get('review') or {}).get('fingerprint',{})
                matches=[s for s in submissions if anchor['ready'] and s['asset_id']==fp.get('asset_id') and s['sha256']==fp.get('sha256')]
                anchor['generation_usage']={'role':roles.get(anchor['id'],{}).get('role','unknown'),
                    'scene_time':roles.get(anchor['id'],{}).get('scene_time'),
                    'planned':planned.get(anchor['id']),'submitted':copy.deepcopy(matches)}
