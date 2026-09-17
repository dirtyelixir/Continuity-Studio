"""One material mapping for single-source and native montage takes.

Existing selections are read-only suggestions; observed legacy group ranges are
projected without rewriting their receipts. Explicit edits have append-only history.
"""
from fastapi import APIRouter
from pydantic import Field
from . import store, models

router=APIRouter()


def config(pid):
    return store.setting('edit-segments:'+pid,{'version':0,'segments':{},'history':[]})


def edit_hash(edit):
    return store.digest({k:edit[k] for k in ('id','shot_id','planned_edit_in','planned_edit_out','timeline_in','timeline_out')})


def state(p):
    from . import directing
    cfg=config(p['id']) if p.get('id') else {'segments':{},'version':0}
    takes=p.get('video_renders',{}).get('takes',[])
    byid={t['id']:t for t in takes};rows=[]
    edits=directing.edit_rows(p['production']) if p.get('production') else []
    byedit={e['id']:e for e in edits}
    for e in edits:
        bound=cfg['segments'].get(e['id']);status='unassigned';material=None
        if bound:
            material=dict(bound);t=byid.get(bound['take_id'])
            status='current' if (t and t['state']=='succeeded' and t.get('media_available',True) and t['current'] and t.get('review_status')=='accepted'
                and bound['edit_hash']==edit_hash(e)) else 'needs_review'
        else:
            candidates=[t for t in takes if t['selected'] and t['current'] and t.get('media_available',True) and t['state']=='succeeded' and t.get('review_status','accepted')=='accepted']
            for t in candidates:
                mapped=next((b for b in (t.get('mapping') or {}).get('boundaries',[]) if b['edit_id']==e['id']),None)
                if mapped and (t.get('mapping') or {}).get('status')=='user_observed':
                    first=t['mapping']['boundaries'][0]['edit_id']
                    if first not in byedit:continue
                    offset=byedit[first]['timeline_in']
                    material={'take_id':t['id'],'source_in':mapped['start'],'source_out':mapped['end'],
                        'timeline_in':round(offset+mapped['start'],6),'timeline_out':round(offset+mapped['end'],6)}
                    status='legacy_observed';break
                if t['shot_id']==e['shot_id']:
                    material={'take_id':t['id'],'source_in':e['planned_edit_in'],'source_out':e['planned_edit_out'],
                        'timeline_in':e['timeline_in'],'timeline_out':e['timeline_out']}
                    status='planned_unverified'
        rows.append({'edit_id':e['id'],'shot_id':e['shot_id'],'title':e['shot_title'],'status':status,
            'planned':e,'material':material})
    used=[r for r in rows if r['status'] in ('current','legacy_observed')]
    warnings=[];ordered=sorted(used,key=lambda r:r['material']['timeline_in'])
    end=0
    for r in ordered:
        m=r['material']
        if abs(m['timeline_in']-end)>0.001:warnings.append({'edit_id':r['edit_id'],'code':'TIMELINE_GAP_OR_OVERLAP'})
        end=m['timeline_out']
    return {'version':cfg['version'],'segments':rows,'warnings':warnings,
        'complete':bool(rows) and len(used)==len(rows) and not warnings}


class Binding(models.Strict):
    version:int
    production_revision:int
    edit_id:str
    take_id:str
    source_in:float=Field(ge=0,allow_inf_nan=False)
    source_out:float=Field(gt=0,allow_inf_nan=False)
    timeline_in:float=Field(ge=0,allow_inf_nan=False)
    note:str=Field(min_length=1,max_length=2000)


@router.put('/api/projects/{pid}/edit-segments')
def bind(pid: str,request: Binding):
    from . import engine, directing, video_render, take_lifecycle
    with engine.LOCK:
        p=store.project(pid);cfg=config(pid)
        if cfg['version']!=request.version or p['revision']!=request.production_revision:raise ValueError('剪接資料已更新，請重新載入。')
        edit=next((e for e in directing.edit_rows(p['production']) if e['id']==request.edit_id),None)
        t=video_render.take(pid,request.take_id)
        if not edit:raise ValueError('找不到目前剪接項目。')
        with store.db() as c:
            selected=c.execute('SELECT take_id FROM video_selections WHERE project_id=? AND shot_id=?',(pid,t['shot_id'])).fetchone()
        if t['state']!='succeeded' or take_lifecycle.review_status(pid,t['id'],bool(selected and selected['take_id']==t['id']))!='accepted':
            raise ValueError('請先看片並接受此候選。')
        if not take_lifecycle.accepted_compatibility(take_lifecycle.compatibility(p,t)):raise ValueError('請先核對此影片與現版的兼容性。')
        source=t['request']['source']
        member=next((b for b in source.get('mapping',{}).get('boundaries',[]) if b['edit_id']==edit['id'] and b['shot_id']==edit['shot_id']),None)
        if t['shot_id']!=edit['shot_id'] and not member:raise ValueError('此 Take 未包含所選剪接項目的來源。')
        video_render.output_path(t)
        if not request.source_in<request.source_out<=t['result']['duration']+0.001:raise ValueError('素材範圍須在實際影片時長之內。')
        record={'take_id':t['id'],'edit_id':edit['id'],'source_in':request.source_in,'source_out':request.source_out,
            'timeline_in':request.timeline_in,'timeline_out':round(request.timeline_in+request.source_out-request.source_in,6),
            'edit_hash':edit_hash(edit),'note':request.note,'recorded':store.now(),'actor':'user'}
        cfg['segments'][edit['id']]=record;cfg['history'].append(record);cfg['version']+=1
        store.put_setting('edit-segments:'+pid,cfg)
        return cfg
