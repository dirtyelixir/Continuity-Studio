import io,json,zipfile,os,shutil,hashlib
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from fastapi import FastAPI,Request,UploadFile,File,Form
from fastapi.responses import FileResponse,JSONResponse,Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from . import storyboard_board,generation_groups,postproduction,provider_profiles,video_render,production_methods,chapter_pipeline,editorial,editorial_records,job_queue,comfy_recovery
from . import asset_roles,store,models,engine,continuity,providers,h3,skills,folders,asset_library,delivery,character_sheets,comfy_bridge,storyboarding,input_references,director_styles,serial_story,prompt_preparation,shot_prompts,scene_prompts,video_workflow,project_deletion,directing

@asynccontextmanager
async def lifespan(app):
    import fcntl
    store.DATA.mkdir(parents=True,exist_ok=True)
    lease=(store.DATA/'server.lock').open('a')
    try:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        lease.close()
        raise RuntimeError('Another Continuity Studio server already owns this data directory')
    try:
        store.init()
        postproduction.init()
        video_render.init()
        engine.start_pending()
        comfy_recovery.start()
        yield
    finally:
        comfy_recovery.shutdown()
        video_render.shutdown()
        fcntl.flock(lease,fcntl.LOCK_UN)
        lease.close()

app=FastAPI(title='Continuity Studio',lifespan=lifespan)
app.include_router(postproduction.router)
app.include_router(video_render.router)
app.include_router(generation_groups.router)
app.include_router(storyboard_board.router)
app.include_router(editorial.router)
from . import edit_segments
app.include_router(edit_segments.router)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver'])

@app.middleware('http')
async def origin_guard(request,call_next):
    origin=request.headers.get('origin')
    if request.method not in ['GET','HEAD','OPTIONS'] and origin:
        if urlparse(origin).netloc!=request.headers.get('host'):
            return JSONResponse({'detail':'Cross-origin writes are not allowed'},403)
    if request.method not in ['GET','HEAD','OPTIONS']:
        parts=request.url.path.strip('/').split('/')
        pid=None
        if len(parts)>=3 and parts[:2]==['api','projects'] and parts[3:]!=['undelete']:
            pid=parts[2]
        elif len(parts)>=3 and parts[0]=='api' and parts[1] in ('assets','jobs'):
            with store.db() as c:
                row=c.execute('SELECT project_id FROM '+parts[1]+' WHERE id=?',(parts[2],)).fetchone()
                if row:pid=row['project_id']
        if pid:
            with store.db() as c:
                row=c.execute('SELECT deleted_at FROM projects WHERE id=?',(pid,)).fetchone()
            if row and row['deleted_at'] is not None:
                return JSONResponse({'detail':'作品已刪除，請先到「已刪除作品」還原。'},410)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    if request.url.path=='/' or request.url.path.startswith('/static/'):
        response.headers['Cache-Control']='no-cache'
    return response

@app.exception_handler(ValueError)
async def invalid(request,exc): return JSONResponse({'detail':str(exc)},status_code=400)

@app.get('/api/character-sheet-guide')
def character_sheet_guide():
    path=character_sheets.guide_path()
    if not path.is_file(): return JSONResponse({'detail':'No layout example saved'},404)
    return FileResponse(path,media_type='image/jpeg' if path.suffix.lower() in ('.jpg','.jpeg') else 'image/png')

@app.get('/api/health')
def health(): return {'ok':True,'name':'Continuity Studio','codex_installed':bool(shutil.which('codex')),'project_deletion':True,'production_methods':True,'canonical_shot_state':1,'canonical_frame_projection':2}

@app.get('/api/projects')
def projects(deleted:bool=False):
    return project_deletion.list_projects(deleted)

class ProjectDeletion(models.Strict):
    confirmation_title: str
    revision: int

@app.delete('/api/projects/{pid}')
def delete_project(pid:str,data:ProjectDeletion):
    with engine.LOCK:return project_deletion.delete(pid,data.confirmation_title,data.revision)

@app.post('/api/projects/{pid}/undelete')
def undelete_project(pid:str):
    with engine.LOCK:return project_deletion.restore(pid)

@app.post('/api/projects')
def create(data:models.CreateProject):
    if not data.title.strip() or not data.idea.strip(): raise ValueError('請填寫作品名稱和內容。')
    if data.source_kind!='idea':
        from .story_import import extract_story
        extract_story('source.txt',data.idea.encode('utf-8'))
        storyboarding.source_units(data.idea)
    pid=store.uid()
    with store.db() as c:
        filename=data.source_filename.replace('\\','/').split('/')[-1]
        c.execute('INSERT INTO projects(id,title,idea,style,source_kind,source_filename,created,updated) VALUES(?,?,?,?,?,?,?,?)',(pid,data.title,data.idea,data.style,data.source_kind,filename,store.now(),store.now()))
        store.event(c,pid,'created',data.title)
    return store.project(pid)

@app.post('/api/story-import/preview')
async def story_import_preview(file:UploadFile=File(...)):
    from .story_import import extract_story,MAX_FILE_BYTES
    try: content=await file.read(MAX_FILE_BYTES+1)
    finally: await file.close()
    result=extract_story(file.filename or '',content)
    result['units']=storyboarding.source_units(result['text'])
    return result

@app.get('/api/projects/{pid}')
@store.reuse_job_reads
def state(pid:str):
    p=store.project(pid);assets=store.assets(pid);jobs=store.jobs(pid)
    p['workflow_contract_version']=1
    p['local_runtime']=comfy_recovery.state()
    p['director_styles']=director_styles.state(p,jobs)
    p['directing']=directing.state(p,jobs)
    p['postproduction']=postproduction.state(p)
    p['editorial']=editorial_records.state(p)
    p['asset_groups']=asset_roles.groups(p['production']) if p['production'] else None
    p['visual_entity_ids']=[e['id'] for e in (p['production'] or {}).get('canon',[]) if asset_roles.is_visual(e)]
    p['assets']=assets
    p['story_chapters']=serial_story.chapters(pid)
    p['input_references']=input_references.list_for(pid)
    queues=job_queue.snapshot()
    for j in jobs:
        j['queue']=queues.get(j['id'])
        if j['input'].get('chapter_pipeline') or j['input'].get('directing_pipeline') or j['input'].get('generation_pipeline'):
            j['cancel_requested']=engine.cancel_requested(j['id'])
    p['jobs']=[{**j,'progress':job_progress(j),'input':{k:j['input'].get(k) for k in ['revision','reference_ids','feedback','skills','plan_hash','compiled','delivery_hash','source_asset_id','input_reference_ids','image_prompt_stage','layout_reference','input_references','local_image_plan','image_provider','image_operation','image_region','image_padding','production_method','image_preparation_origin','image_moment_verification','image_moment_alignment','chapter_pipeline','directing_pipeline','generation_pipeline']}} for j in jobs]
    p['qc']=continuity.qc(p['production'],assets) if p['production'] else []
    prepared_scenes={s['id']:prompt_preparation.prepared(p,s['id'])[0] for s in p['production']['scenes']} if p['production'] else {}
    p['h3']=[h3.compile_shot(p['production'],s,assets,prepared_scenes.get(s['scene_id'])) for s in p['production']['shots']] if p['production'] else []
    for compiled in p['h3']:
        refined=next((j for j in jobs if j['capability']=='h3' and j['target_id']==compiled['shot_id'] and j['state']=='succeeded' and j['input'].get('plan_hash')==store.digest(p['production']) and asset_library.same_references(j['input'].get('compiled',{}).get('references',[]),compiled['references'])),None)
        if refined: compiled['text']=refined['result']['text'];compiled['refined_by']=refined['provider'];compiled['ready']=True
    with store.db() as c:
        p['revisions']=[dict(r) for r in c.execute('SELECT number,reason,created FROM revisions WHERE project_id=? ORDER BY number DESC',(pid,))]
        p['events']=[dict(r) for r in c.execute('SELECT * FROM events WHERE project_id=? ORDER BY id DESC LIMIT 40',(pid,))]
    p['delivery']=delivery.project_bundle(p)
    p['scene_prompt_regenerations']=scene_prompts.status(p,jobs)
    p['shot_prompt_regenerations']=shot_prompts.status(p,jobs)
    p['video_workflow']=video_workflow.state(p,jobs)
    p['video_renders']=video_render.state(p,jobs)
    p['edit_segments']=edit_segments.state(p)
    for take in p['video_renders']['takes']:
        take['edit_ids']=[s['edit_id'] for s in p['edit_segments']['segments'] if s['material'] and s['material']['take_id']==take['id'] and s['status'] in ('current','legacy_observed','needs_review')]
        take['used_in_edit']=bool(take['edit_ids'])
    p['generation_groups']=generation_groups.state(p,jobs)
    p['storyboard']=storyboard_board.state(p,jobs)
    p['character_sheets']=character_sheets.project_status(p)
    # Read-only diagnostics for historical generated files; keep saved reviews
    # and execution receipts intact, even if an old worker called them success.
    from .image_output_quality import inspect_image
    for asset in assets:
        if asset.get('job_id') and asset.get('status') in ('pending','approved'):
            asset['image_output_quality']=inspect_image(asset_library.safe_path(asset['path']))
    return p

@app.put('/api/projects/{pid}/video-workflow/{sid}')
def video_save(pid:str,sid:str,data:models.VideoWorkflowEdit):
    with engine.LOCK:return video_workflow.save(pid,sid,data)

@app.post('/api/projects/{pid}/video-workflow/adopt/{jid}')
def video_adopt(pid:str,jid:str,data:models.VideoAdopt):
    with engine.LOCK:return video_workflow.adopt(pid,jid,data.revision)

@app.post('/api/projects/{pid}/video-workflow/{sid}/frame')
def video_frame(pid:str,sid:str,data:models.VideoFrameAdd):
    with engine.LOCK:return video_workflow.add_frame(pid,sid,data.moment,data.description,data.revision)

@app.get('/api/projects/{pid}/video-workflow/{sid}/packet')
def video_packet(pid:str,sid:str):
    with engine.LOCK:return video_workflow.packet(store.project(pid),sid)

@app.post('/api/projects/{pid}/scene-prompts/{jid}/adopt')
def adopt_scene_prompt(pid:str,jid:str):
    with engine.LOCK: return scene_prompts.adopt(pid,jid)

@app.post('/api/projects/{pid}/shot-prompts/{jid}/adopt')
def adopt_shot_prompt(pid:str,jid:str):
    with engine.LOCK: return shot_prompts.adopt(pid,jid)

@app.put('/api/projects/{pid}/delivery')
def save_delivery(pid:str,data:models.DeliveryEdit):
    with engine.LOCK: return delivery.save_configuration(pid,data.model_dump())

@app.put('/api/projects/{pid}/outline')
def edit_outline(pid:str,data:models.OutlineEdit): return serial_story.save_outline(pid,data)

@app.post('/api/projects/{pid}/chapters')
def create_chapter(pid:str,data:models.ChapterDraft): return serial_story.save_draft(pid,data)

@app.put('/api/projects/{pid}/chapters/{cid}')
def edit_chapter(pid:str,cid:str,data:models.ChapterDraft): return serial_story.save_draft(pid,data,cid)

@app.put('/api/projects/{pid}/plan')
def save(pid:str,data:models.PlanEdit): return engine.save_plan(pid,data.production.model_dump(),data.revision,'Director edit')

@app.post('/api/projects/{pid}/plan-impact')
def plan_impact(pid:str,data:models.PlanEdit):
    from . import workflow_impact
    p=store.project(pid)
    if p['revision']!=data.revision:raise ValueError('方案已更新，請重新載入。')
    return workflow_impact.preview(p,data.production.model_dump())

@app.post('/api/projects/{pid}/restore/{number}')
def restore(pid:str,number:int,data:models.RevisionRequest):
    with store.db() as c: old=c.execute('SELECT production FROM revisions WHERE project_id=? AND number=?',(pid,number)).fetchone()
    if not old: raise ValueError('Revision not found')
    return engine.save_plan(pid,json.loads(old[0]),data.revision,f'Restored revision {number}',restore=True)

@app.post('/api/projects/{pid}/guidance/analyze')
def analyze_guidance(pid:str):
    with engine.LOCK:
        p=store.project(pid)
        if not p['production']: raise ValueError('請先建立並採用分鏡方案。')
        bundle=delivery.project_bundle(p);review=bundle['guidance_review']
        if review['status']!='pending': return review
        return engine.enqueue(pid,models.JobRequest(capability='h3_guidance'))

@app.post('/api/projects/{pid}/jobs')
def start_job(pid:str,data:models.JobRequest): return engine.enqueue(pid,data)

@app.get('/api/projects/{pid}/scenes/{scene_id}/asset-batch')
def preview_scene_assets(pid:str,scene_id:str):
    from . import scene_asset_batch
    with engine.LOCK:return scene_asset_batch.preview(pid,scene_id)

@app.post('/api/projects/{pid}/scenes/{scene_id}/asset-batch')
def generate_scene_assets(pid:str,scene_id:str,data:models.SceneAssetBatchRequest):
    from . import scene_asset_batch
    return scene_asset_batch.submit(pid,scene_id,data.token,data.image_provider)

def job_progress(j):
    from . import directing_pipeline
    from . import generation_pipeline
    from . import proposal_progress
    return generation_pipeline.progress(j) or directing_pipeline.progress(j) or chapter_pipeline.progress(j) or proposal_progress.progress(j)


@app.get('/api/jobs/{jid}')
def job(jid:str):
    j=store.job(jid)
    from . import saved_proposal
    j['saved_proposal']=saved_proposal.preview(j)
    from . import frame_moment_guard
    j['moment_verification']=frame_moment_guard.receipt(j)
    j['queue']=job_queue.snapshot().get(jid)
    j['progress']=job_progress(j)
    from . import directing_pipeline
    from . import generation_pipeline
    j['context_usage']=generation_pipeline.receipts(j) or directing_pipeline.receipts(j) or chapter_pipeline.chapter_context.receipts(j)
    from . import context_limits
    j['budget_usage']=context_limits.receipt(j)
    if j['input'].get('chapter_pipeline') or j['input'].get('directing_pipeline') or j['input'].get('generation_pipeline'):
        j['cancel_requested']=engine.cancel_requested(jid)
    if j['state']=='succeeded' and j['capability'] in ('narrative','storyboard') and j['input'].get('directing_policy'):
        r=directing.proposal_review(j)
        revision=store.project(j['project_id'])['revision']
        j['directing_review']={'required':True,'state':r['state'] if r else 'missing','job_id':r['id'] if r else None,'result':r['result'] if r and r['state']=='succeeded' else None,'error':r.get('error','') if r else '', 'progress':job_progress(r) if r else None, 'resumable':bool(r and directing_pipeline.can_resume(r,revision))}
    if j.get('directing_review'):
        from . import directing_approvals
        j['directing_review'].update(human_approval=directing_approvals.proposal(j),approval_source_hash=directing_approvals.basis(store.project(j['project_id']),j))
    return j

class DirectingHumanApproval(models.Strict):
    revision: int
    source_hash: str
    proposal_id: str = ''
    note: str = ''

@app.post('/api/projects/{pid}/directing-approval')
def approve_directing(pid:str,data:DirectingHumanApproval):
    from . import directing_approvals
    return directing_approvals.approve(pid,data.revision,data.source_hash,data.proposal_id,data.note)

@app.post('/api/projects/{pid}/director-style')
def select_director(pid:str,data:models.DirectorSelection):
    with engine.LOCK: return {'selected':director_styles.choose(pid,data)}

@app.post('/api/jobs/{jid}/adopt')
def adopt(jid:str,data:models.RevisionRequest):
    j=store.job(jid)
    if j['state']!='succeeded' or j['capability'] not in ['narrative','storyboard']: raise ValueError('Only a completed production proposal can be adopted')
    if data.revision!=j['input']['revision']: raise ValueError('Proposal was created from an earlier revision. Develop a revised proposal to avoid overwriting newer decisions.')
    plan=j['result']
    if j['input'].get('serial_source'):
        director_styles.check_adoption(j)
        if j['capability']=='storyboard': storyboarding.validate(j['result'],j['input']['source'])
        current=store.project(j['project_id'])
        plan=serial_story.merge(current,j['result'].get('production',j['result']),j['input']['serial_source'])
        return engine.save_plan(j['project_id'],plan,data.revision,'Adopted chapter '+j['target_id']+' via '+j['provider'],director_job=j)
    if j['capability']=='storyboard':
        storyboarding.validate(j['result'],j['input']['source'])
        current=store.project(j['project_id'])
        if current['idea']!=j['input']['source']['source_text'] or current['source_kind']!=j['input']['source']['source_kind']:
            raise ValueError('方案來源與目前原文不同，請重新建立分鏡。')
        plan=j['result']['production']
    director_styles.check_adoption(j)
    return engine.save_plan(j['project_id'],plan,data.revision,'Adopted '+j['provider']+' '+j['capability']+' proposal',director_job=j)

@app.post('/api/jobs/{jid}/cancel')
def cancel_pending(jid:str):
    with engine.LOCK,store.db() as c:
        j=store.row(c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())
        if not j or j['state'] not in ['queued','running','awaiting_input']: raise ValueError('此工作已結束，不能取消。')
        work=store.DATA/'jobs'/jid;work.mkdir(parents=True,exist_ok=True);(work/'cancel-requested').touch()
        if j['state']=='running':
            message='已要求取消；正在停止本機結果等待，不會採用結果。' if j['provider']=='comfy_local' else '已要求取消；等待服務商結束，不會採用結果。'
            c.execute('UPDATE jobs SET error=?,updated=? WHERE id=?',(message,store.now(),jid))
        else:c.execute('UPDATE jobs SET state="cancelled",updated=? WHERE id=?',(store.now(),jid))
        store.event(c,j['project_id'],'cancelled',f'{j["capability"]}: {j["target_id"]}')
    from . import directing_auto
    if j['state']!='running':directing_auto.on_terminal(j)
    from . import asset_deletion
    with engine.LOCK: asset_deletion.purge_rejected(j['project_id'])
    return store.job(jid)

@app.post('/api/jobs/{jid}/recover')
def recover(jid:str):
    j=store.job(jid)
    if j['state'] not in ['failed','interrupted']: raise ValueError('Only failed or interrupted jobs can be recovered')
    output=store.DATA/'jobs'/jid/'result.json'
    repaired=store.DATA/'jobs'/jid/'repair-1'/'result.json'
    if j['capability'] in ('storyboard','directing_qc') and repaired.is_file(): output=repaired
    if not output.is_file(): raise ValueError('No saved provider result exists. Retry is needed.')
    with engine.LOCK:
        if store.job(jid)['state'] not in ['failed','interrupted']: raise ValueError('Job was already recovered')
        result=json.loads(output.read_text())
        attempt=store.DATA/'jobs'/jid/'recovery-attempts'/store.uid()
        attempt.mkdir(parents=True,exist_ok=True)
        receipt={'state':'running','started':store.now(),'original_state':j['state'],'original_error':j['error'],'source':str(output.relative_to(store.DATA/'jobs'/jid))}
        (attempt/'receipt.json').write_text(store.encode(receipt))
        with store.db() as c:
            c.execute('UPDATE jobs SET state="running",error="",updated=? WHERE id=?',(store.now(),jid))
        try:
            engine.finish(j,result)
        except Exception as exc:
            receipt.update(state='failed',error=str(exc),finished=store.now())
            (attempt/'receipt.json').write_text(store.encode(receipt))
            with store.db() as c:
                c.execute('UPDATE jobs SET state="failed",error=?,updated=? WHERE id=? AND state="running"',(str(exc),store.now(),jid))
            raise
        receipt.update(state=store.job(jid)['state'],finished=store.now())
        (attempt/'receipt.json').write_text(store.encode(receipt))
    return store.job(jid)

@app.post('/api/jobs/{jid}/resume')
def resume_chapter(jid:str):
    with engine.LOCK:
        j=store.job(jid)
        if not (j['input'].get('chapter_pipeline') or j['input'].get('directing_pipeline') or j['input'].get('generation_pipeline')) or j['state'] not in ('failed','interrupted'):
            raise ValueError('只有失敗或中斷的分階段工作可以接續。')
        if engine.cancel_requested(jid):
            raise ValueError('已取消的工作不能接續；請建立新方案。')
        if j['input'].get('generation_pipeline'):
            from . import generation_pipeline
            generation_pipeline.require_fresh(j)
        elif j['input'].get('directing_pipeline'):
            from . import directing_pipeline
            directing_pipeline.require_fresh(j)
        else:
            chapter_pipeline.require_fresh(j)
        with store.db() as c:
            active=c.execute('SELECT id FROM jobs WHERE project_id=? AND capability=? AND target_id=? AND state IN ("queued","running","awaiting_input")',
                             (j['project_id'],j['capability'],j['target_id'])).fetchone()
            if active: raise ValueError('同一章節已有工作正在處理，請先等待它完成。')
            work=store.DATA/'jobs'/jid
            if (work/'failure.txt').is_file():
                shutil.copyfile(work/'failure.txt',work/('failure-before-resume-'+store.uid()+'.txt'))
            c.execute('UPDATE jobs SET state="queued",error="",updated=? WHERE id=?',(store.now(),jid))
            store.event(c,j['project_id'],'resume','接續已保存階段：'+jid)
        engine.POOL.submit(engine.execute,jid)
    return {'job':store.job(jid)}

@app.post('/api/jobs/{jid}/manual')
def manual(jid:str,data:dict):
    j=store.job(jid)
    if j['state']!='awaiting_input': raise ValueError('Job is not awaiting manual output')
    if j['capability']=='image': raise ValueError('Use image upload for manual image jobs')
    engine.finish(j,data)
    return store.job(jid)

@app.delete('/api/assets/{aid}')
def delete_asset(aid:str):
    from . import asset_deletion
    with engine.LOCK:return asset_deletion.delete_rejected(aid)

@app.post('/api/assets/{aid}/decision')
def decide(aid:str,data:models.Decision):
    return engine.decide_asset(aid,data.status,data.note,data.acknowledge_sheet_issues)

@app.post('/api/projects/{pid}/identity-assets/{target_id}')
async def save_identity_asset(pid:str,target_id:str,revision:int=Form(...),entity:str=Form(''),asset_id:str=Form(''),file:UploadFile|None=File(None)):
    from . import identity_assets
    content=None
    if file is not None:
        try:content=await file.read(40_000_001)
        finally:await file.close()
    return identity_assets.save(pid,target_id,revision,json.loads(entity) if entity else None,asset_id,content)

def asset_path(aid:str):
    with store.db() as c: a=c.execute('SELECT path FROM assets WHERE id=?',(aid,)).fetchone()
    if not a: raise ValueError('Image not found')
    p=(store.DATA/a['path']).resolve()
    if not p.is_relative_to((store.DATA/'assets').resolve()): raise ValueError('Invalid image path')
    if not p.is_file(): raise ValueError('Original image file is missing')
    return p

@app.get('/api/assets/{aid}/image')
def image(aid:str):
    return FileResponse(asset_path(aid),media_type='image/png')

@app.post('/api/assets/{aid}/comfy')
def send_asset_to_comfy(aid:str):
    return comfy_bridge.send_image(aid,asset_path(aid))

@app.get('/api/assets/{aid}/path')
def original_image_path(aid:str):
    return {'path':str(asset_path(aid))}

@app.post('/api/assets/{aid}/reveal')
def reveal_asset(aid:str):
    return folders.reveal_file(asset_path(aid))

@app.post('/api/projects/{pid}/input-references')
async def upload_input_reference(pid:str,file:UploadFile=File(...),purpose:str=Form('style'),target_id:str=Form('')):
    try: content=await file.read(40_000_001)
    finally: await file.close()
    with engine.LOCK:
        return input_references.save(pid,content,file.filename or 'reference.png',purpose,target_id)

@app.get('/api/projects/{pid}/input-references/{rid}/image')
def input_reference_image(pid:str,rid:str):
    ref=input_references.get(pid,rid)
    return FileResponse(input_references.path_for(ref))

@app.get('/api/projects/{pid}/input-references/{rid}/path')
def input_reference_path(pid:str,rid:str):
    return {'path':str(input_references.path_for(input_references.get(pid,rid)))}

@app.post('/api/projects/{pid}/input-references/{rid}/reveal')
def reveal_input_reference(pid:str,rid:str):
    return folders.reveal_file(input_references.path_for(input_references.get(pid,rid)))

@app.post('/api/projects/{pid}/upload/{target_id}')
async def upload(pid:str,target_id:str,file:UploadFile=File(...)):
    p=store.project(pid)
    if not p['production']: raise ValueError('Adopt a plan before importing a reference')
    refs,missing=continuity.references(p['production'],store.assets(pid),target_id)
    kind,_,_=continuity.find_target(p['production'],target_id)
    if kind=='frame' and missing: raise ValueError('Approve canonical references before importing a frame')
    content=await file.read(40_000_001)
    if len(content)>40_000_000: raise ValueError('Maximum upload is 40MB')
    jid=store.uid();work=store.DATA/'jobs'/jid;work.mkdir(parents=True,exist_ok=True)
    path=work/'upload.png';path.write_bytes(content)
    inp={'dependency_hash':continuity.target_hash(p['production'],target_id),'context':continuity.context(p['production'],target_id),'reference_ids':[r['id'] for r in refs],'image_prompt':'Director-imported visual reference','revision':p['revision']}
    if inp['context'].get('entity',{}).get('kind')=='character':inp['character_sheet_layout']=continuity.CHARACTER_SHEET_LAYOUT
    j={'id':jid,'project_id':pid,'target_id':target_id,'capability':'image','provider':'manual','input':inp}
    with store.db() as c: c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',(jid,pid,'image',target_id,'running','manual',store.encode(inp),store.now(),store.now()))
    try: engine.finish(j,{'image_path':str(path),'notes':'Imported by director'})
    except Exception as e:
        with store.db() as c: c.execute('UPDATE jobs SET state="failed",error=? WHERE id=?',(str(e),jid))
        raise ValueError('Could not import image: '+str(e))
    with store.db() as c: c.execute('UPDATE jobs SET state="succeeded",result=?,updated=? WHERE project_id=? AND target_id=? AND capability="image" AND state="awaiting_input"',(store.encode({'imported_by':jid}),store.now(),pid,target_id))
    return store.job(jid)

@app.get('/api/settings')
def settings():
    roots=[str(Path.home()/'.agents'/'skills'),str(Path.home()/'.codex'/'skills'),str(store.ROOT/'extensions')]
    installed=skills.list_installed(str(store.DATA/'skills'))
    capabilities=sorted(set(providers.BUILTINS+[c for s in installed if s['enabled'] for c in s['capabilities'] if c!='*']))
    from . import context_limits
    context_profiles={p['id']:context_limits.freeze(p,probe=False) for p in providers.all_providers() if p['kind'] not in ('manual','comfy')}
    return {'providers':providers.all_providers(),'context_profiles':context_profiles,'routing':providers.routing(),'profile':provider_profiles.settings(capabilities),'capabilities':capabilities,'skills':installed,'discovered':skills.discover(roots),'codex_installed':bool(shutil.which('codex')),'production_methods':production_methods.status()}

@app.post('/api/settings/context-limits')
def set_context_limits(data:models.ProviderContextLimits):
    p=next((p for p in providers.all_providers() if p['id']==data.provider_id),None)
    if not p or p['kind'] in ('manual','comfy'): raise ValueError('請選擇可執行文字工作的服務商。')
    if data.tokenizer=='llama_cpp' and p['kind']!='http': raise ValueError('llama.cpp 計數只適用於相容 HTTP 接口。')
    limits=store.setting('provider_context_limits',{})
    limits[data.provider_id]=data.model_dump(exclude={'provider_id'})
    store.put_setting('provider_context_limits',limits)
    return {'ok':True}

@app.post('/api/settings/profile')
def set_provider_profile(data:models.ProviderProfile):
    installed=skills.list_installed(str(store.DATA/'skills'))
    capabilities=[c for s in installed if s['enabled'] for c in s['capabilities'] if c!='*']
    return provider_profiles.apply(**data.model_dump(),capabilities=capabilities)

@app.get('/api/settings/local-images')
def local_image_catalog():
    from . import local_images
    return {'operations':local_images.OPERATIONS,'recipes':local_images.RECIPES,'version':local_images.VERSION}

@app.get('/api/settings/local-images/recovery')
def local_recovery_status():return comfy_recovery.state()

@app.post('/api/settings/local-images/check')
def check_local_images():
    from . import comfy_images
    return comfy_images.check()

@app.post('/api/jobs/{jid}/recover-image')
def recover_local_image(jid:str):
    from . import comfy_images
    with engine.LOCK:
        j=store.job(jid)
        if not j or j['capability']!='image' or j['provider']!='comfy_local' or j['state'] not in ('failed','interrupted') or not comfy_images.unresolved(store.DATA/'jobs'/jid):
            raise ValueError('此工作沒有待取回的本機圖片。')
        with store.db() as c:c.execute('UPDATE jobs SET state="queued",error="",updated=? WHERE id=?',(store.now(),jid))
        engine.POOL.submit(engine.execute,jid)
    return store.job(jid)

@app.post('/api/settings/deepseek/check')
def check_deepseek():
    return provider_profiles.check_connection()

@app.post('/api/settings/qwen/check')
def check_qwen():
    return provider_profiles.check_qwen_connection()

@app.post('/api/settings/providers')
def provider(data:models.ProviderConfig):
    if data.id in ['astra','deepseek','local_qwen','manual','comfy_local']: raise ValueError('Built-in providers are protected')
    if data.kind!='http': raise ValueError('Custom providers currently use the HTTP adapter')
    p=urlparse(data.base_url)
    if p.scheme not in ['http','https'] or not p.hostname or p.username or p.password: raise ValueError('Use an HTTP(S) base URL without embedded credentials')
    if data.key_env and not data.key_env.replace('_','').isalnum(): raise ValueError('Use an environment variable name, not a key value')
    from . import context_limits
    context_limits.freeze(data.model_dump(),probe=False)
    items=store.setting('providers',[]);items=[p for p in items if p['id']!=data.id]+[data.model_dump()]
    store.put_setting('providers',items)
    return {'ok':True}

@app.post('/api/settings/routing')
def route(data:models.Routing):
    p=next((p for p in providers.all_providers() if p['id']==data.provider_id),None)
    if not p or not providers.supports(p,data.capability): raise ValueError('Provider does not support capability')
    r=providers.routing();r[data.capability]=data.provider_id;store.put_setting('routing',r)
    return {'ok':True}

@app.post('/api/skills/install')
def install(data:dict):
    return skills.install(data['source'],str(store.DATA/'skills'))

@app.post('/api/skills/{sid}/enable')
def enable(sid:str,data:dict):
    return skills.set_enabled(str(store.DATA/'skills'),sid,data['enabled'],data.get('granted_permissions',[]))

@app.get('/api/projects/{pid}/export')
def export(pid:str):
    p=state(pid)
    if not p['production']: raise ValueError('Adopt a production plan before exporting')
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('director/plan.json',store.encode({'scenes':p['production']['scenes'],'shots':p['production']['shots']}))
        z.writestr('director/review.json',store.encode(p['directing']))
        z.writestr('director/plan.md',directing.report(p))
        z.writestr('edit/plan.json',store.encode(directing.edit_manifest(p)))
        z.writestr('edit/audio-timeline.json',store.encode(p['editorial']))
        z.writestr('edit/README.txt','畫面範圍見 plan.json；獨立聲音時間見 audio-timeline.json。timeline_in/out 以整份正式剪接起點計時，scene_timeline_in 以場景起點計時。無聲口形不代表已有聲音；audio_asset=null 代表尚未對應有效音檔。所有範圍仍為預定剪接，未執行裁剪或混音。過時場景不會輸出可執行聲音標記。\n')
        storyboard_board.export(z,p)
        postproduction.add_export(z,p)
        video_render.add_export(z,p)
        z.writestr('production-reference-index.json',store.encode(p['input_references']))
        for ref in p['input_references']:
            z.write(input_references.path_for(ref),ref['path'])
            z.writestr(ref['path']+'.json',store.encode(ref))
        z.writestr('production.json',json.dumps(p,ensure_ascii=False,indent=2))
        methods=[{'job_id':j['id'],'provider':j['provider'],'capability':j['capability'],
                  **{k:j['input'].get(k) for k in ('production_method','skills','prompt','image_source','image_task','image_reference_roles','image_prompt','render_prompt_hash','image_preparation_origin','image_preparation_fingerprint','image_moment_verification','image_moment_alignment')}}
                 for j in store.jobs(pid) if j['input'].get('production_method')]
        z.writestr('production-methods/used-methods.json',store.encode(methods))
        for job in store.jobs(pid):
            if job['capability']=='image' and job['input'].get('image_lora_context'):
                prefix='local-images/'+job['id']+'/'
                z.writestr(prefix+'selection.json',store.encode(job['input'].get('local_image_plan')))
                work=store.DATA/'jobs'/job['id']
                for name in ('comfy-graph.json','comfy-receipt.json','image-lora-selection.json','image-lora-evidence.json','render-prompt.txt'):
                    if (work/name).is_file():z.write(work/name,prefix+name)
        if p.get('source_kind')=='outline':
            z.writestr('story/outline.txt',p['idea'])
            z.writestr('story/chapter-drafts.json',store.encode(p['story_chapters']))
            for ch in p['production'].get('chapters',[]):
                z.writestr('story/chapters/'+ch['id']+'/story.txt',ch['story'])
                z.writestr('story/chapters/'+ch['id']+'/screenplay.txt',ch['screenplay'])
        if p.get('source_kind','idea')!='idea':
            z.writestr('source/original.txt',p['idea'])
            z.writestr('source/metadata.json',store.encode({'kind':p['source_kind'],'filename':p['source_filename'],'text_hash':store.digest(p['idea'])}))
            proposal=next((j for j in store.jobs(pid) if j['capability']=='storyboard' and j['state']=='succeeded' and j['result']['production']==p['production']),None)
            if proposal:
                z.writestr('source/storyboard-coverage.md',storyboarding.report(proposal['result'],proposal['input']['source']))
                z.writestr('source/storyboard-skill.json',store.encode(proposal['input']['skills']))
        z.writestr('character-reference-requirements.md',character_sheets.requirements_markdown())
        if character_sheets.guide_path().is_file():z.write(character_sheets.guide_path(),'reference-guides/character-four-view'+character_sheets.guide_path().suffix)
        z.writestr('screenplay.md','# '+p['title']+'\n\n'+p['production']['screenplay'])
        z.writestr('asset-groups.json',store.encode(asset_roles.groups(p['production'])))
        z.writestr('director-style.json',store.encode(director_styles.state(p,store.jobs(pid))))
        z.writestr('README.md','video-workflow/groups/ contains ready native multi-shot group prompts, role-labelled image references and planned edit-to-clip mappings. These groups are each ONE H3 generation, independent of the legacy per-Shot paths. video/*-storyboard-mapping.json distinguishes planned timing from user-observed boundaries; adopting a group does not select it separately for every member Shot. video-workflow/ contains explicit per-Shot selections and ready frame-conditioned handoffs. I2VA and FL2VA use the FL2VA model family; Ref2VA uses its separate model and handoff. Do not combine the two families in one Director run. Unready frame shots have no ready handoff and never fall back to T2VA. Ref2VA remains available: ref2/ contains per-scene global prompts, per-Shot director/storyboard and complete prompts, references and motion-guidance handoff notes. h3/ retains prepared legacy keyframe-mode prompts; h3/drafts/ contains unprepared shot drafts for review only, not ready rendering instructions. This package also contains canonical production, reference provenance and image prompts. Canonical generated images include only current approved versions. Uploaded production-reference originals are also preserved, with their own metadata; they are not automatically approved canon. Review status in production.json. video/takes.json records H3 render status; video/ includes only explicitly adopted, current successful MP4 takes and provenance. Presence of preparation files alone does not mean a video has been generated. Upload images in each Ref2VA Shot manifest order. Legacy h3/ mode alone follows approved keyframe availability.\n')
        z.writestr('video-workflow/status.json',store.encode(p['video_workflow']))
        for row in p['video_workflow']['shots']:
            if row['ready']:
                packet=video_workflow.packet(p,row['shot_id'])
                z.writestr('video-workflow/FL2VA/'+row['shot_id']+'/handoff.json',store.encode(packet))
                z.writestr('video-workflow/FL2VA/'+row['shot_id']+'/prompt.txt',packet['text'])
        for item in p['h3']:
            z.writestr(('h3/' if item.get('ready') else 'h3/drafts/')+item['shot_id']+'.txt',item['text'])
            z.writestr('h3/'+item['shot_id']+'.json',json.dumps(item,ensure_ascii=False,indent=2))
        handoff={'mode':'REF2VA','chapter_meaning':'One shot = one director segment/prompt group','continuity_enabled':p['delivery']['configuration']['continuity_enabled'],'context_frames':p['delivery']['configuration']['context_frames'],'scenes':[],'chapter_order':[s['id'] for s in p['production']['shots']],'instructions':'For a scene with one shared global, enable Director common/global parameters and paste global plus each Shot prompt separately. The global prompt belongs only to the Scene; Shots have no global override. Set the common/global prompt and scene.references images for the current Scene. Put each Shot local_references images only in that segment at the assigned Picture slots, leaving common slots unchanged; clear obsolete local images when switching Shots. Paste the full Shot prompt, including its leading prop definitions, into its segment. For external tools requiring combined text, complete.txt is derived from that Scene global plus the Shot prompt. Enable segment guidance and per-Shot reference previous as recorded. This is a handoff manifest, not a directly importable ComfyUI workflow. Video generation was not run.'}
        for scene in p['delivery']['scenes']:
            folder='ref2/scenes/'+scene['scene_id']
            z.writestr(folder+'/global.txt',scene['global_prompt'])
            z.writestr(folder+'/scene.json',json.dumps(scene,ensure_ascii=False,indent=2))
            handoff['scenes'].append({'scene_id':scene['scene_id'],'title':scene['title'],'chapters':[c['shot_id'] for c in scene['chapters']]})
            for chapter in scene['chapters']:
                path=folder+'/chapters/'+chapter['shot_id']
                z.writestr(path+'/shot.txt',chapter['shot_prompt'])
                z.writestr(path+'/complete.txt',chapter['text'])
                z.writestr(path+'/references-and-guidance.json',json.dumps({k:chapter[k] for k in ['scene_id','mode','duration','references','local_references','missing_references','guidance','issues']},ensure_ascii=False,indent=2))
        z.writestr('ref2/handoff.json',json.dumps(handoff,ensure_ascii=False,indent=2))
        for a in p['assets']:
            if a['status']=='approved':
                z.write(store.DATA/a['path'],a['path'])
                z.writestr('image-prompts/'+a['id']+'.txt',a['prompt'])
    return Response(buffer.getvalue(),media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="continuity-{pid}.zip"'})

@app.post('/api/projects/{pid}/folder')
def production_folder(pid:str):
    with engine.LOCK:
        p=state(pid)
        snapshot=folders.materialize(pid,p,export(pid).body if p['production'] else None)
        snapshot['library_path']=str(asset_library.write_catalog(pid))
        return snapshot

@app.post('/api/projects/{pid}/library/open')
def open_asset_library(pid:str):
    with engine.LOCK: path=asset_library.write_catalog(pid)
    return folders.open_folder(str(path))

@app.post('/api/projects/{pid}/folder/open')
def open_production_folder(pid:str):
    return folders.open_folder(production_folder(pid)['path'])

@app.get('/api/projects/{pid}/folder/{snapshot}/{filename:path}')
def production_file(pid:str,snapshot:str,filename:str):
    path=folders.snapshot_file(pid,snapshot,filename)
    types={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp'}
    return FileResponse(path,media_type=types.get(path.suffix.lower(),'text/plain'),headers={'Content-Security-Policy':"default-src 'none'; sandbox"})

app.mount('/static',StaticFiles(directory=store.ROOT/'static'),name='static')
@app.get('/')
def index():
    static=store.ROOT/'static'
    html=(static/'index.html').read_text()
    for name in ['app.js','style.css']:
        version=hashlib.sha256((static/name).read_bytes()).hexdigest()[:16]
        html=html.replace('/static/'+name,'/static/'+name+'?v='+version)
    return Response(html,media_type='text/html')
