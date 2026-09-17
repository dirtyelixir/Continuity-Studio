"""Explicit, reviewable H3 frame workflow; never infer text-only delivery."""
import copy,re
from . import store,continuity,h3,delivery,shot_prompts,prompt_preparation,models,asset_roles

MODES=('I2VA','FL2VA','REF2VA')
POLICY='frame-workflow-v1'

def config(pid):return store.setting('video-workflow:'+pid,{'revision':0,'shots':{}})
def shot_for(p,sid):
    shot=next((s for s in (p['production'] or {}).get('shots',[]) if s['id']==sid),None)
    if not shot:raise ValueError('找不到這個 Shot。')
    return shot

def source(p,sid):
    scene,chapter=shot_prompts.locate(p,sid,p.get('delivery'))
    data=shot_prompts.basis(p,scene,chapter)
    # Image availability is a readiness concern, not a creative plan revision.
    data.pop('references',None);data.pop('local_references',None)
    from . import storyboard_board,storyboard_usage
    board=storyboard_board.config(p['id'])['scenes'].get(shot_for(p,sid)['scene_id'],{})
    if board.get('image_policy') in storyboard_board.IMAGE_POLICIES:
        try:data['image_requirements']=[r for r in storyboard_usage.intent(p,shot_for(p,sid)['scene_id']) if r['shot_id']==sid]
        except ValueError as error:data['image_requirements_error']=str(error)
    return {'policy':POLICY,**data}

def strategy_fingerprint(src):
    value=copy.deepcopy(src)
    for key in ('shot','previous_shot','next_shot'):
        if value.get(key):value[key].pop('keyframes',None)
    return store.digest({'contract':'source-generation-intent-v1','source':value})

def strategy_source(p,sid):
    from . import conditioning
    return {**source(p,sid),'conditioning_contract':conditioning.VERSION,'conditioning_requirements':conditioning.requirements(p,sid)}

def strategy_matches(src,saved_hash,job):
    frozen=job.get('input',{}).get('video_source')
    if frozen and not frozen.get('conditioning_contract'):
        src={k:v for k,v in src.items() if k not in ('conditioning_contract','conditioning_requirements')}
    original=job.get('input',{}).get('video_hash')
    comparable=copy.deepcopy([src,frozen])
    for value in comparable:
        if value is not None and value.get('image_requirements')==[]:value.pop('image_requirements')
    return bool(frozen and saved_hash==original and original in (store.digest(frozen),strategy_fingerprint(frozen))
        and strategy_fingerprint(comparable[0])==strategy_fingerprint(comparable[1]))

def frames(p,shot,mode):
    result=[];assets=p.get('assets') if 'assets' in p else store.assets(p['id'])
    for moment in (('start','end') if mode=='FL2VA' else ('start',)):
        f=next((f for f in shot['keyframes'] if f['moment']==moment),None)
        approved=continuity.approved_for(p['production'],assets,f['id']) if f else None
        candidate=approved or next((a for a in assets if f and a['target_id']==f['id']),None)
        result.append({'moment':moment,'frame_id':f['id'] if f else '', 'description':f['description'] if f else '',
            'asset':candidate,'ready':bool(approved and (store.DATA/approved['path']).is_file())})
    return result

def _frame_asset_id(frame):
    """Return the current approved file id for a frame, if it is usable."""
    return frame['asset']['id'] if frame.get('ready') and frame.get('asset') else ''

def _strategy_refresh_moments(p,sid,entry,mode=None):
    """Find endpoints whose adopted blueprint still needs a newly approved image.

    A strategy blueprint is a frozen visual contract.  When it changes, an old
    approved frame must not silently continue to satisfy the video handoff.
    The baseline asset id lets the requirement clear only after the user has
    actually generated and approved a replacement frame.
    """
    strategy=entry.get('strategy') or {}
    refresh=dict(strategy.get('refresh_frame_ids') or {})
    moments=list(strategy.get('refresh_moments') or [])
    if mode is None: mode=entry.get('mode','I2VA')
    shot=shot_for(p,sid)
    current={f['moment']:_frame_asset_id(f) for f in frames(p,shot,mode)}
    pending=[]
    for moment in moments:
        if current.get(moment,'')==refresh.get(moment,''):
            pending.append(moment)
    return pending

def reference_cards(p,shot):
    """Expose the same visual canon dependencies used by frame rendering."""
    plan=p['production'];assets=p.get('assets') if 'assets' in p else store.assets(p['id'])
    if shot['keyframes']:
        entities=continuity.context(plan,shot['keyframes'][0]['id'])['canon']
    else:
        scene=next(s for s in plan['scenes'] if s['id']==shot['scene_id'])
        ids=set(shot['entity_ids'])|{scene['location_id']}
        entities=[e for e in plan['canon'] if e['id'] in ids and asset_roles.is_visual(e)]
    result=[]
    for entity in entities:
        tid=entity['id'];approved=continuity.approved_for(plan,assets,tid)
        versions=sorted((a for a in assets if a['target_id']==tid),key=lambda a:a.get('created',''),reverse=True)
        asset=approved or next(iter(versions),None)
        status=asset['status'] if asset else 'missing'
        if asset and asset['dependency_hash']!=continuity.target_hash(plan,tid):status='stale'
        if asset and not (store.DATA/asset['path']).is_file():status='missing_file'
        result.append({'target_id':tid,'name':entity['name'],'kind':entity['kind'],
            'asset':asset,'status':status,'ready':bool(approved and status=='approved')})
    return result

def prompt_source(p,sid):
    shot=shot_for(p,sid);entry=config(p['id'])['shots'].get(sid,{});mode=entry.get('mode','I2VA')
    from . import conditioning
    selected=conditioning.current(p,sid)
    if selected and selected['plan']['mode']!=mode:raise ValueError('模式與已採用 conditioning decision 不符，請重新分析。')
    if selected:conditioning.resolve(p,sid)
    if mode=='REF2VA' and not selected:raise ValueError('Ref2VA 請使用原有 Scene 公共參數及 Shot 提示詞工作台。')
    from . import storyboard_board
    storyboard_board.require_source_mode(p,sid,mode)
    board=storyboard_board.require_review(p,shot['scene_id'],shot_ids=[sid])
    if mode=='REF2VA':
        setup=delivery.configuration(p['id'])['scenes'].get(shot['scene_id'],{}).get('chapters',{}).get(sid,{})
        _,chapter=shot_prompts.locate(p,sid,p.get('delivery'))
        if setup.get('guide_from_previous') or chapter.get('guidance',{}).get('continuityFromPrev') is True:raise ValueError('此鏡要求上段影片引導；reference demand 路線不會靜默停用。')
        return {**delivery.demand_prompt_source(p,sid,source(p,sid)),**({'storyboard_review':board} if board else {})}
    fs=frames(p,shot,mode)
    if not all(f['ready'] for f in fs):raise ValueError('請先完成並批准所選模式需要的首／尾幀；不會自動改成純文字生成。')
    pending=_strategy_refresh_moments(p,sid,entry,mode)
    if pending:
        labels='、'.join('首幀' if m=='start' else '尾幀' for m in pending)
        raise ValueError(f'{labels}藍圖已更新，請重新生成並批准對應關鍵幀後再製作影片。')
    refs=[{'moment':f['moment'],'asset_id':f['asset']['id'],'path':f['asset']['path'],'label':f'Picture {i+1}'} for i,f in enumerate(fs)]
    approved=[f['asset'] for f in fs]
    compiled=h3.compile_shot(p['production'],shot,approved)
    from . import storyboard_usage
    uses=storyboard_usage.bind(p,storyboard_usage.source_uses(p,sid),refs)
    return {**({'storyboard_usage':uses} if uses else {}),**({'storyboard_review':board} if board else {}),'prompt_policy':'copyable-prompt-v3','source':source(p,sid),'mode':mode,'references':refs,'alignment':compiled['text'].split('\n\n')[0]}

def build(p,req):
    from . import generation_groups
    if generation_groups.is_group(req.target_id):return generation_groups.build(p,req)
    src=strategy_source(p,req.target_id) if req.capability=='h3_strategy' else prompt_source(p,req.target_id)
    if req.capability=='h3_strategy':
        prompt='''You are the production director deciding the appropriate H3 conditioning for ONE existing Shot. Return the schema, with Traditional Chinese explanations and concrete single-moment frame blueprints. Choose I2VA (one opening frame, default when sufficient), FL2VA (opening AND ending frame only when a specific final composition/state needs anchoring), or REF2VA (reusable identity references with freer staging). Compare creative control and frame preparation effort. No speed percentages, fixed mode quotas, guaranteed mid-shot hands or continuity. Do not automatically require an end frame merely for walking, prop movement, many characters or a changed state. Never create editorial cuts from storyboard frame count. Internal Generation Segments are distinct from editorial Shots, but arbitrary internal splitting is not currently executable in this source workflow; report that limitation for a hard intermediate image constraint. Do not change plot/dialogue/timing/style, invent precise coordinates or draw offscreen voice-only speakers. evidence contains 1–3 SHORT EXACT excerpts from source strings supporting your choice. start_blueprint: camera/framing, foreground/midground/background, visible subjects, screen direction, gaze, left/right hand ownership, prop state and lighting at time zero; no movement sequence. end_blueprint: equivalent final frozen composition if FL2VA, otherwise empty. checks: 2–6 concrete visual review questions, including any occluded detail that cannot be verified. Canon is authoritative; current prompt preserves the user's latest direction. Return JSON only. No tools or generation.\n'''
    else:
        prompt='''Write a complete English MiniMax H3 frame-conditioned video prompt for this ONE Shot, using the attached approved first frame (Picture 1) and, ONLY in FL2VA, last frame (Picture 2). Return JSON {text:string, frame_issues:string[]}. Begin with the EXACT supplied alignment string, then exactly integrated_multimodal_description:, overall_soundscape:, non_diegetic_music: in that order. Put a blank line after the alignment instruction. Start the integrated body with [Shot 1]. Put ALL dialogue tags and stable speaker IDs (S1), (S2) inside integrated_multimodal_description with their timings; overall_soundscape is only ambience, physical sounds and nonverbal sounds, never dialogue tags. Do NOT carry over Ref2VA subject_definitions, summary, retention_analysis, detailed_description, <Subject N> or identity-reference Picture numbering. Characters retain original names; all other prose English except verbatim <d>[language] words</d>. Copy each dialogue tag from current_prompt exactly once, preserving original timings, speaker and delivery (the user's saved text takes precedence for dialogue words). Do not add narration, lyrics, events, references, cuts or dialogue. Retain current shot's duration, timed action, camera, blocking, hands and plot boundaries. Inspect attached frames for composition. Frame constraints control endpoints, not a guaranteed middle trajectory: describe a physically plausible continuous bridge with explicit hand ownership, avoid instantaneous morphing. Always return a COMPLETE nonempty text prompt, even when approved images have discrepancies. Put concrete Traditional Chinese image/source differences in frame_issues separately as advisory notes for the user. Do not place review commentary or conflicting instructions in the H3 text. Follow the saved storyboard and dialogue for intended action/hand ownership; avoid claiming that a discrepant starting image already shows a correct pose, and do not invent a prop transfer or morph to conceal the discrepancy. An approved frame reflects a human choice; visual concerns must not suppress the requested prompt. When no concrete discrepancy is observed, frame_issues is empty. No global prompt is pasted for this mode: include necessary visual style, ambience and sound direction from source. Keep below 7000 characters. Do not use tools or generate media.\n'''
    if req.capability=='h3_strategy' and req.strategy_mode!='AUTO':
        prompt+='\nUSER SELECTED MODE: '+req.strategy_mode+'. Return this exact mode and design the blueprint for it. Explain tradeoffs honestly.\n'
    if req.capability=='h3_strategy':
        from . import conditioning
        prompt+='\n'+conditioning.RULES+'\nThis decision is shared with image-demand planning; selected demands, not the Scene union, drive new REF2VA input.\n'
        prompt+='\nRespect generation_arrangement.edit_uses.frame_uses image_conditioning requirements. A required source end image excludes I2VA. Do not replace an adopted required frame with prose or change its blueprint unnecessarily; planning_only images are not additional model inputs.\n'
    if src.get('prompt_policy')=='ref-demand-prompt-v1':
        prompt='''Write one complete self-contained English REF2VA prompt for this continuous source Shot. Return {text,frame_issues}. Begin with the EXACT supplied alignment (subject_definitions), blank line, then summary: beginning [reference generation], retention_analysis:, detailed_description:, overall_soundscape:, non_diegetic_music: exactly once in this order. All selected Picture/Subject roles are defined in alignment. Do not import Scene slot numbers or add unselected references. Copy every current_prompt dialogue tag exactly once, preserving source speaker/timings and wording. Preserve full source duration, original actions, camera direction, staging, sound and visual style. References constrain identity/appearance/environment, never exact intermediate timestamps. Do not add cuts, actions, video/audio references, narration or lyrics. Inspect attached approved references and put advisory differences in Traditional Chinese frame_issues. Keep text under 7000 characters. No tools or media generation.\n'''
    return {'strategy_mode':req.strategy_mode,'video_source':src,'video_hash':strategy_fingerprint(src) if req.capability=='h3_strategy' else store.digest(src),'video_request_hash':store.digest([src,req.feedback,req.source_prompt,req.strategy_mode]),'source_prompt':req.source_prompt,
        'prompt':prompt+'\n'+prompt_preparation.SCOPE_RULES+'\nFROZEN SOURCE FOR INTERPRETATION ONLY:\n'+store.encode({**src,'source':prompt_preparation.model_context(src['source'])} if 'source' in src else prompt_preparation.model_context(src))+'\nCURRENT FRAME PROMPT DRAFT (if supplied):\n'+(req.source_prompt or '')+'\nUSER FEEDBACK:\n'+req.feedback,
        'images':[str(store.DATA/r['path']) for r in src.get('references',[])]}

def validate_strategy(result,src,requested_mode="AUTO"):
    if src.get('image_requirements_error'):raise ValueError(src['image_requirements_error'])
    if requested_mode!="AUTO" and result.get("mode")!=requested_mode:raise ValueError("建議未按你指定的模式製作，請重新生成。")
    result=models.VideoStrategy.model_validate(result).model_dump()
    if src.get('conditioning_contract'):
        from . import conditioning
        conditioning.validate(result,src['conditioning_requirements'])
    def strings(x):
        if isinstance(x,str):yield x
        elif isinstance(x,dict):
            for v in x.values():yield from strings(v)
        elif isinstance(x,list):
            for v in x:yield from strings(v)
    texts=list(strings(src))
    if any(not any(q in t for t in texts) for q in result['evidence']):raise ValueError('模式建議的劇情依據必須引用原文。')
    if (result['mode']=='FL2VA')!=bool(result['end_blueprint'].strip()):raise ValueError('只有首尾幀模式需要尾幀藍圖。')
    uses=[u for edit in src.get('generation_arrangement',{}).get('edit_uses',[]) for u in edit.get('frame_uses',[])]
    if result['mode']=='I2VA' and any(r.get('required_binding')=='end' for r in src.get('image_requirements',[])):
        raise ValueError('已採用的圖板需要 FL2VA 尾幀；不可靜默改為只傳首幀。')
    if result['mode']=='I2VA' and any(u['use']=='image_conditioning' and u['moment']=='end' for u in uses):
        raise ValueError('生成安排要求尾幀圖片，I2VA 無法承接；請選擇能傳入該圖的模式。')

def validate_result(result,src):
    if src.get("kind")=="generation_group":
        from . import generation_groups
        return generation_groups.validate_result(result,src)
    text=result['text'].replace('\r\n','\n')
    first,sep,rest=text.partition('\n')
    if first==src['alignment'] and sep:
        text=first+'\n\n'+rest.lstrip('\n')
    result['text']=text
    if result.get('frame_issues'):
        if any(not issue.strip() for issue in result['frame_issues']):raise ValueError('請列出具體的關鍵幀修訂原因。')
    validate_prompt(result['text'],src)


def validate_prompt(text,src):
    if src.get('prompt_policy')=='ref-demand-prompt-v1':return delivery.validate_demand_prompt(text,src)
    if len(text)>7000:raise ValueError('提示詞超過 7000 字元。')
    fields=['integrated_multimodal_description:','overall_soundscape:','non_diegetic_music:']
    positions=[text.find(f) for f in fields]
    if any(x<0 for x in positions) or positions!=sorted(positions) or any(text.count(f)!=1 for f in fields):raise ValueError('請保留 H3 的三個提示詞段落。')
    if not text.startswith(src['alignment']+'\n\n'):raise ValueError('首／尾幀對齊說明不可更改。')
    if re.search(r'<Subject\s|subject_definitions:|retention_analysis:|detailed_description:|\bsummary:',text):raise ValueError('首尾幀提示詞不可混入 Ref2VA 主體及段落格式。')
    if not set(re.findall(r'Picture\s+(\d+)',text))<=set(str(i+1) for i in range(len(src['references']))):raise ValueError('提示詞含未附上的圖片編號。')
    if '<d>' in text.split('overall_soundscape:',1)[1]:raise ValueError('對白標籤必須放在 integrated_multimodal_description，不可放在環境聲或配樂段落。')
    tags=lambda t:re.findall(r'<d>.*?</d>',t,re.S)
    if tags(text)!=tags(src['source']['current_prompt']):raise ValueError('請逐字保留目前 Shot 的對白標籤和次序。')
    prompt_preparation.english(text,prompt_preparation.original_names(src['source']['canon']).values())
    # Shared writing checks, against the mode actually selected for this video.
    from . import prompt_writing
    kind=prompt_writing.task_for_video(src.get('strategy') or src.get('mode') or '')
    _,blocking=prompt_writing.check({'video_prompt':text},kind,
                                    reference_count=len(src.get('references') or []))
    if blocking:raise ValueError('影片提示詞有可機械判定的寫作錯誤：'+prompt_writing.finding_text(blocking))

def save(pid,sid,req):
    p=store.project(pid);shot_for(p,sid);cfg=config(pid)
    if req.revision!=cfg['revision']:raise ValueError('影片設定已更新，請重新載入後再儲存。')
    entry=cfg['shots'].setdefault(sid,{})
    if req.mode is not None:entry['mode']=req.mode
    if req.text is not None:
        # Temporarily selected mode is not allowed to bypass the current basis.
        if req.mode is not None:raise ValueError('請先儲存模式，再編輯提示詞。')
        src=prompt_source(p,sid)
        if req.source_hash!=store.digest(src):raise ValueError('分鏡、模式或圖片已更新；草稿仍保留，請重新生成。')
        validate_prompt(req.text,src)
        entry['prompt']={'text':req.text,'source_hash':req.source_hash,'job_id':'','frame_issues':entry.get('prompt',{}).get('frame_issues',[])}
    cfg['revision']+=1;store.put_setting('video-workflow:'+pid,cfg);return cfg

def adopt(pid,jid,revision):
    p=store.project(pid);j=store.job(jid);cfg=config(pid)
    if j['project_id']!=pid or j['capability'] not in ('h3_strategy','h3_video_prompt') or j['state']!='succeeded':raise ValueError('只能採用本作品已完成的影片準備方案。')
    if cfg['revision']!=revision:raise ValueError('影片設定已更新，請重新載入。')
    src=(strategy_source(p,j['target_id']) if j['input'].get('video_source',{}).get('conditioning_contract') else source(p,j['target_id'])) if j['capability']=='h3_strategy' else prompt_source(p,j['target_id'])
    current=strategy_matches(src,j['input']['video_hash'],j) if j['capability']=='h3_strategy' else store.digest(src)==j['input']['video_hash']
    if not current:raise ValueError('分鏡、提示詞或圖片已更新，請按最新內容重新分析／生成。')
    entry=cfg['shots'].setdefault(j['target_id'],{})
    if j['capability']=='h3_strategy':
        validate_strategy(j['result'],src,j['input'].get('strategy_mode','AUTO'))
        old=entry.get('strategy') or {}
        old_result=old.get('result') or {}
        new_result=j['result']
        new_mode=new_result['mode']
        refresh_ids=dict(old.get('refresh_frame_ids') or {})
        refresh_moments=list(old.get('refresh_moments') or [])
        if old_result and new_mode!='REF2VA':
            shot=shot_for(p,j['target_id'])
            current={f['moment']:_frame_asset_id(f) for f in frames(p,shot,new_mode)}
            for moment in (('start','end') if new_mode=='FL2VA' else ('start',)):
                if old_result.get(moment+'_blueprint','').strip()!=new_result.get(moment+'_blueprint','').strip():
                    # Keep an unresolved baseline until its replacement is
                    # approved; once resolved, a later blueprint change starts
                    # a fresh requirement from the new current asset.
                    if moment not in refresh_moments or current.get(moment,'')!=refresh_ids.get(moment,''):
                        refresh_ids[moment]=current.get(moment,'')
                    if moment not in refresh_moments: refresh_moments.append(moment)
        strategy={'result':new_result,'source_hash':j['input']['video_hash'],'job_id':jid,'intent_hash':strategy_fingerprint(src)}
        if refresh_moments and new_mode!='REF2VA':
            strategy['refresh_moments']=refresh_moments
            strategy['refresh_frame_ids']=refresh_ids
        entry.update(mode=new_mode,strategy=strategy)
        if src.get('conditioning_contract'):
            from . import conditioning
            entry['conditioning']=conditioning.snapshot(p,j['target_id'],new_result,jid)
    else:
        validate_prompt(j['result']['text'],src);entry['prompt']={'text':j['result']['text'],'source_hash':store.digest(src),'job_id':jid,'frame_issues':j['result'].get('frame_issues',[])}
    cfg['revision']+=1;store.put_setting('video-workflow:'+pid,cfg);return cfg

def state(p,jobs=None):
    from . import conditioning
    cfg=config(p['id']);rows=[];jobs=store.jobs(p['id']) if jobs is None else jobs
    for shot in (p['production'] or {}).get('shots',[]):
        sid=shot['id'];entry=cfg['shots'].get(sid,{});mode=entry.get('mode','I2VA');src=strategy_source(p,sid);src_hash=store.digest(src)
        fs=[] if mode=='REF2VA' and entry.get('conditioning') else frames(p,shot,mode);prompt=entry.get('prompt',{});basis_hash='';reasons=[]
        selected=entry.get('conditioning');demands=[];cards=reference_cards(p,shot)
        if selected:
            try:
                resolved=conditioning.resolve(p,sid,strict=False);demands=resolved['demands'];reasons+=resolved['unresolved']
                if mode=='REF2VA':
                    fs=[];cards=[{'target_id':d['entity_id'],'name':d['name'],'kind':d['kind'],'asset':d['asset'],
                        'ready':d['status']=='ready','status':'approved' if d['status']=='ready' else 'missing'} for d in demands if d['required']]
            except ValueError as error:reasons.append(str(error))
        if mode!='REF2VA' or selected:
            for f in fs:
                if not f['ready']:reasons.append(('首幀' if f['moment']=='start' else '尾幀')+'尚未完成並批准')
            for moment in (_strategy_refresh_moments(p,sid,entry,mode) if mode!='REF2VA' else []):
                reasons.append(('首幀' if moment=='start' else '尾幀')+'藍圖已更新，請重新生成並批准')
            if not reasons:
                # Readiness failures belong to this shot, not the project GET.
                # Keep prompt_source's submission gates authoritative.
                try:basis_hash=store.digest(prompt_source(p,sid))
                except (ValueError,OSError) as error:reasons.append(str(error))
            if not prompt:reasons.append('尚未生成並採用此模式的提示詞')
            elif prompt.get('source_hash')!=basis_hash:reasons.append('提示詞需要按目前分鏡及圖片更新')
        else:reasons.append('請到 Ref2VA 工作台完成公共參數、參考圖及接續判斷')
        row={'shot_id':sid,'scene_id':shot['scene_id'],'title':shot['title'],'duration':shot['duration'],'mode':mode,'selected':bool(entry.get('mode')),
            'references':cards,'frames':fs,'prompt':prompt,'source_hash':basis_hash,'ready':not reasons,'reasons':reasons,'strategy':entry.get('strategy'),
            'conditioning':selected,'reference_demands':demands,
            'strategy_stale':bool(entry.get('strategy') and not strategy_matches(src,entry['strategy']['source_hash'],next((j for j in jobs if j['id']==entry['strategy'].get('job_id')),{}))),'jobs':{}}
        for cap in ('h3_strategy','h3_video_prompt'):
            j=next((j for j in jobs if j['capability']==cap and j['target_id']==sid),None)
            if j:row['jobs'][cap]={'id':j['id'],'state':j['state'],'error':j['error'],'result':j['result'],
                'stale':not strategy_matches(src,j['input'].get('video_hash'),j) if cap=='h3_strategy' else j['input'].get('video_hash')!=basis_hash,
                'adopted':entry.get('strategy' if cap=='h3_strategy' else 'prompt',{}).get('job_id')==j['id']}
        latest=row['jobs'].get('h3_video_prompt',{})
        row['frame_issues']=(latest.get('result') or {}).get('frame_issues',[]) if not latest.get('stale',True) else prompt.get('frame_issues',[])
        rows.append(row)
    return {'revision':cfg['revision'],'shots':rows}

def packet(p,sid):
    row=next(r for r in state(p)['shots'] if r['shot_id']==sid)
    if not row['ready']:raise ValueError('；'.join(row['reasons']))
    src=prompt_source(p,sid)
    if src.get('prompt_policy')=='ref-demand-prompt-v1':
        return {'shot_id':sid,'mode':'REF2VA','model_family':'REF2VA','director_task':'r2v','duration':row['duration'],
            'frame_rate':24,'text':row['prompt']['text'],'global_prompt':'','guide_from_previous':False,
            'references':src['references'],'reference_demands':src['reference_demands'],
            'instructions':'本鏡專用 Ref2VA：按 Picture 編號載入明示參考圖，清除其他共用 references／prompt。完整提示詞包含本鏡 Subject 定義。未支援上段影片或 audio/video reference。'}
    return {'shot_id':sid,'mode':row['mode'],'model_family':'FL2VA','director_task':'fl2v','duration':row['duration'],'frame_rate':24,'render_frame_count':round(row['duration']*24)+(5-round(row['duration']*24)%17)%17,
        'text':row['prompt']['text'],'frame_issues':row['frame_issues'],'references':src['references'],'global_prompt':'','guide_from_previous':False,
        'instructions':'導演台切到首尾幀 fl2v。每個 Shot 一組；Picture 1 放首幀，只有 FL2VA 才把 Picture 2 放尾幀。清除原有 Ref2VA 公共提示詞與主體槽；本提示詞貼本組。每組獨立生成，不勾引用上段。時長由導演台按 24fps／17k+5 幀對齊；輸出後檢查對白及首尾動作。此為交接資料，不是可直接匯入的 ComfyUI workflow。'}

def add_frame(pid,sid,moment,description,revision):
    from . import engine,asset_library
    p=store.project(pid);shot=shot_for(p,sid)
    description=description.strip()
    if len(description)<3:raise ValueError('請填寫具體的靜止畫面描述。')
    if p['revision']!=revision:raise ValueError('分鏡版本已更新，請重新載入。')
    if any(f['moment']==moment for f in shot['keyframes']):raise ValueError('此 Shot 已有這個關鍵幀。')
    plan=copy.deepcopy(p['production']);edited=next(s for s in plan['shots'] if s['id']==sid)
    fid=store.uid();edited['keyframes'].append({'id':fid,'moment':moment,'description':description})
    models.Production.model_validate(plan)
    assets=store.assets(pid);preserved=[a for a in assets if a['target_id'] in {f['id'] for f in shot['keyframes']} and a['status'] in ('approved','pending') and a['dependency_hash']==continuity.target_hash(p['production'],a['target_id'])]
    scene,_=shot_prompts.locate(p,sid);cfg=delivery.configuration(pid)
    # Freeze effective Ref2VA prose before the additional frame changes preparation hashes.
    setup=cfg['scenes'].setdefault(scene['scene_id'],{'chapters':{}});setup['global_prompt']=scene['global_prompt']
    for ch in scene['chapters']:setup.setdefault('chapters',{}).setdefault(ch['shot_id'],{})['shot_prompt']=ch['shot_prompt']
    saved=engine.save_plan(pid,plan,revision,'新增影片準備'+moment+'關鍵幀')
    saved_plan=saved['production'];saved_shot=next(s for s in saved_plan['shots'] if s['id']==sid)
    # Legacy conversion may repair an old frame's semantic description. Such
    # images must stay stale; only proven identical canonical moments can retain
    # their applicability when a sibling composition is added.
    if shot.get('canonical_state'):
        before={f['id']:f for f in shot['keyframes']}
        after={f['id']:f for f in saved_shot['keyframes']}
        preserved=[a for a in preserved if before[a['target_id']]==after.get(a['target_id'])
            and shot['canonical_state']['moments']==saved_shot['canonical_state']['moments']
            and shot['canonical_state']['transitions']==saved_shot['canonical_state']['transitions']]
    elif saved_shot.get('canonical_state'):preserved=[]
    # This endpoint adds only a sibling frame: existing frozen moments are identical.
    with store.db() as c:
        for a in preserved:c.execute('UPDATE assets SET dependency_hash=?,status=?,note=? WHERE id=?',(continuity.target_hash(saved_plan,a['target_id']),a['status'],a['note'],a['id']))
    cfg['production_revision']=revision+1;delivery.save_configuration(pid,cfg)
    asset_library.write_catalog(pid)
    return {'frame_id':fid}
