"""Scene-derived image batches with explicit preview and durable deduplication."""
import json
from . import asset_roles, continuity, engine, models, store


def preview(pid, scene_id):
    with engine.LOCK:
        p=store.project(pid);plan=p['production']
        if not plan:raise ValueError('請先建立並採用製作方案。')
        scene=next((s for s in plan['scenes'] if s['id']==scene_id),None)
        if not scene:raise ValueError('找不到此場景。')
        ids={scene['location_id']}|{i for s in plan['shots'] if s['scene_id']==scene_id for i in s['entity_ids']}
        assets=store.assets(pid);jobs=store.jobs(pid);items=[]
        uncertain=set()
        with store.db() as c:
            for row in c.execute("SELECT value FROM settings WHERE key LIKE 'scene-asset-batch:%'"):
                receipt=json.loads(row['value'])
                if receipt.get('project_id')==pid and receipt.get('state')=='submitting':
                    uncertain.update(i['target_id'] for i in receipt['items'] if i['state']=='submitting')
        for e in plan['canon']:
            if e['id'] not in ids or not asset_roles.is_visual(e):continue
            expected=continuity.target_hash(plan,e['id'])
            current=continuity.approved_for(plan,assets,e['id'])
            pending=next((a for a in assets if a['target_id']==e['id'] and a['status']=='pending' and a['dependency_hash']==expected),None)
            active=None
            for j in jobs:
                if j['capability']!='image' or j['target_id']!=e['id']:continue
                if j['state'] in ('queued','running','awaiting_input'):
                    active=j;break
                if j['provider']=='comfy_local' and j['state'] in ('failed','interrupted'):
                    from . import comfy_images
                    if comfy_images.unresolved(store.DATA/'jobs'/j['id']):active=j;break
            state='approved' if current else 'pending' if pending else 'active' if active or e['id'] in uncertain else 'generate'
            reason={'approved':'沿用已批准圖片','pending':'已有候選待審','active':'已有工作，先等候或取回結果','generate':'補齊缺少或待更新的資產'}[state]
            items.append({'target_id':e['id'],'name':e['name'],'kind':e['kind'],'state':state,'reason':reason,
                          'dependency_hash':expected,'asset_id':(current or pending or {}).get('id'),
                          'job_id':active['id'] if active else None})
        body={'project_id':pid,'scene_id':scene_id,'scene_title':scene['title'],'revision':p['revision'],'items':items,'previous_batch':store.setting('scene-asset-batch-latest:'+pid+':'+scene_id)}
        return {**body,'token':store.digest(body),'generate_count':sum(i['state']=='generate' for i in items)}


def submit(pid, scene_id, token, image_provider):
    with engine.LOCK:
        p=store.project(pid)
        if not p['production'] or not any(s['id']==scene_id for s in p['production']['scenes']):raise ValueError('找不到此場景。')
        key='scene-asset-batch:'+store.digest([pid,scene_id,token])
        saved=store.setting(key)
        if saved:
            if saved['image_provider']!=image_provider:raise ValueError('此批次已提交，不能更換服務後重送。')
            return saved  # Also preserves uncertain/incomplete submissions without replay.
        provider=engine.image_provider(models.JobRequest(capability='image',image_provider=image_provider))
        if provider['kind']=='manual':raise ValueError('請選擇可生成圖片的服務；人工匯入不適用於批量生成。')
        plan=preview(pid,scene_id)
        if plan['token']!=token:raise ValueError('場景或資產狀態已更新，請重新開啟批量製作清單。')
        receipt={**plan,'image_provider':image_provider,'state':'submitting',
                 'items':[{**i,'state':'planned' if i['state']=='generate' else 'skipped'} for i in plan['items']]}
        store.put_setting(key,receipt)
        store.put_setting('scene-asset-batch-latest:'+pid+':'+scene_id,token)
        for row in receipt['items']:
            if row['state']!='planned':continue
            row['state']='submitting';store.put_setting(key,receipt)
            try:
                result=engine.enqueue(pid,models.JobRequest(capability='image',target_id=row['target_id'],image_provider=image_provider,force=False))
                if result.get('job'):row.update(state='queued',job_id=result['job']['id'])
                else:row.update(state='skipped',asset_id=result['reused_asset']['id'])
            except Exception as error:
                row.update(state='failed',error=str(error))
            store.put_setting(key,receipt)
        receipt['state']='complete';store.put_setting(key,receipt)
        return receipt
