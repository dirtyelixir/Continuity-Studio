"""One global prompt per Scene, with independent Shot prompts."""
import copy,re
from . import asset_roles,crowds,store,continuity,guidance,speech_direction,prompt_preparation

FIELDS=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
CONTEXT_FRAMES=[5,22,39,56]


def demand_prompt_source(p,sid,context):
    """Compile one source's explicit demands into a self-contained Ref2VA layout.

    Keep legacy shared Scene prompts untouched. New text is prepared and reviewed
    through the existing source h3_video_prompt capability, with exact definitions.
    """
    from . import conditioning,shot_prompts
    resolved=conditioning.resolve(p,sid);refs=resolved['references']
    _,chapter=shot_prompts.locate(p,sid)
    context=conditioning.prompt_context(context,chapter['references'])
    context['canon']=conditioning.requirements(p,sid)['canon'];context.pop('global_prompt',None)
    if 'summary:' in context.get('current_prompt',''):
        context['current_prompt']='summary:'+context['current_prompt'].split('summary:',1)[1]
    definitions='subject_definitions:\n'+'\n'.join(
        f'<{r["subject"]}> is {r["name"]} from <{r["label"]}>. Use this image for {', '.join(d['role'].replace('_',' ') for d in resolved['demands'] if d['required'] and d['asset_id']==r['asset_id'])}; preserve its visible design.' for r in refs)
    return {'prompt_policy':'ref-demand-prompt-v1','source':context,'mode':'REF2VA',
        'references':refs,'alignment':definitions,'conditioning':conditioning.current(p,sid),
        'reference_demands':[{k:v for k,v in d.items() if k!='asset'} for d in resolved['demands']]}


def validate_demand_prompt(text,src):
    if not text.startswith(src['alignment']+'\n\n'):raise ValueError('Reference role／Picture／Subject 定義不可更改。')
    # No alternative role definitions may be injected after the fixed preamble.
    if text.split('summary:',1)[0].strip()!=src['alignment']:raise ValueError('請保留唯一的 reference 定義。')
    validate_complete(text,src['references'],src['source']['shot'],prompt_preparation.original_names(src['source']['canon']).values())
    tags=lambda t:re.findall(r'<d>.*?</d>',t,re.S)
    if tags(text)!=tags(src['source']['current_prompt']):raise ValueError('請保留本鏡原有對白標籤及次序。')


def configuration(pid):
    config=copy.deepcopy(store.setting('delivery:'+pid,{'revision':0,'continuity_enabled':True,'context_frames':22,'scenes':{}}))
    # Legacy overrides remain in saved settings/history, but no longer participate.
    for scene in config['scenes'].values():
        for shot in scene.get('chapters',{}).values():shot.pop('global_prompt',None)
    return config


def save_configuration(pid,data):
    p=store.project(pid);current=configuration(pid)
    if data['revision']!=current['revision'] or data['production_revision']!=p['revision']:raise ValueError('Direction changed. Reload before saving.')
    if data['context_frames'] not in CONTEXT_FRAMES:raise ValueError('Choose 5, 22, 39 or 56 context frames')
    allowed_scenes={s['id'] for s in p['production']['scenes']}
    if set(data['scenes'])-allowed_scenes:raise ValueError('Unknown scene')
    for sid,scene in data['scenes'].items():
        allowed_shots={s['id'] for s in p['production']['shots'] if s['scene_id']==sid}
        if set(scene.get('chapters',{}))-allowed_shots:raise ValueError('Chapter must belong to this scene')
        if len(scene.get('global_prompt',''))>7000:raise ValueError('Global prompt exceeds 7000 characters')
        for chapter in scene.get('chapters',{}).values():
            if chapter.get('reference_frame','none') not in ['none','start','end','both']:raise ValueError('Invalid storyboard reference choice')
            if 'global_prompt' in chapter:raise ValueError('全域提示詞只屬於 Scene，Shot 只有分鏡提示詞。')
            if len(chapter.get('shot_prompt',''))>7000:raise ValueError('Prompt exceeds 7000 characters')
    updated={k:data[k] for k in ['continuity_enabled','context_frames','scenes']};updated['revision']=current['revision']+1
    history=store.setting('delivery-history:'+pid,[])
    history.append({'revision':updated['revision'],'created':store.now(),'configuration':updated})
    store.put_setting('delivery-history:'+pid,history);store.put_setting('delivery:'+pid,updated)
    with store.db() as c:store.event(c,pid,'direction','Saved Ref2VA scene/chapter direction revision '+str(updated['revision']))
    return updated


def refs_for_scene(plan,scene,assets):
    shots=[s for s in plan['shots'] if s['scene_id']==scene['id']]
    needed={scene['location_id']}|{eid for s in shots for eid in s['entity_ids']}
    refs=[];missing=[]
    for entity in plan['canon']:
        if entity['id'] not in needed or not asset_roles.is_visual(entity) or entity['kind']=='prop':continue
        a=continuity.approved_for(plan,assets,entity['id'])
        if not a:missing.append(entity['name']);continue
        n=len(refs)+1
        refs.append({'asset_id':a['id'],'target_id':entity['id'],'path':a['path'],'label':f'Picture {n}','subject':f'Subject {n}','role':entity['kind'],'name':entity['name'],'director_note':a['note']})
    return refs,missing


def refs_for_shot(plan,shot,assets,offset):
    refs=[];missing=[]
    for entity in plan['canon']:
        if entity['kind']!='prop' or entity['id'] not in shot['entity_ids']:continue
        a=continuity.approved_for(plan,assets,entity['id'])
        if not a:missing.append(entity['name']);continue
        n=offset+len(refs)+1
        refs.append({'asset_id':a['id'],'target_id':entity['id'],'path':a['path'],'label':f'Picture {n}','subject':f'Subject {n}','role':'prop','name':entity['name'],'director_note':a['note']})
    return refs,missing


def shot_definitions(refs,prepared):
    definitions={e['entity_id']:e for e in (prepared or {}).get('subjects',[])}
    lines=[]
    for ref in refs:
        entity=definitions.get(ref['target_id'])
        identity=entity['name_en'] if entity else 'the prop'
        appearance=entity['appearance'] if entity else 'Preserve its visible design.'
        lines.append(f'<{ref["subject"]}> is {identity} from <{ref["label"]}>. {appearance} Apply only within this Shot as directed below.')
    return '\n'.join(lines)


def validate_shared(text,refs):
    pictures={r['label'].split()[-1] for r in refs}
    subjects={r['subject'].split()[-1] for r in refs if r.get('subject')}
    if set(re.findall(r'<Picture\s+(\d+)>',text))-pictures or set(re.findall(r'<Subject\s+(\d+)>',text))-subjects:
        raise ValueError('Scene 公共參數只能定義共用圖片；道具圖片與定義請放到相應 Shot。')


def global_draft(plan,scene,refs):
    # Canon facts, approval notes and project style are reasoning context, not
    # ready-to-paste visual direction. Only preparation may distil that context.
    lines=['subject_definitions:']
    for ref in refs:
        identity=ref['name'] if ref['role'] in ('character','crowd','voice') else 'the '+ref['role']
        lines.append(f'<{ref["subject"]}> is {identity} shown in <{ref["label"]}>. Preserve its visible identity and design.')
    if any(r['role']=='character' for r in refs):lines.append('Character references may be four-view identity sheets. Each defines one subject across angles; do not reproduce the reference panels or duplicate that character in the video.')
    if any(r['role']=='crowd' for r in refs):lines.append(crowds.REFERENCE)
    lines.append('Scene-wide appearance and lighting: Awaiting scene preparation.')
    return '\n'.join(lines)


def chapter_draft(plan,shot,refs):
    labels={r['target_id']:'<'+r['subject']+'>' for r in refs if r.get('subject')}
    names={e['id']:e['name'] for e in plan['canon']}
    speakers={}
    for s in plan['shots']:
        for d in s['dialogue']:
            if d['entity_id'] not in speakers:speakers[d['entity_id']]=f'S{len(speakers)+1}'
    states=lambda ss:'; '.join(f'{labels.get(s["entity_id"],names[s["entity_id"]])} {s["key"]}: {s["value"]}' for s in ss)
    scene=next(s for s in plan['scenes'] if s['id']==shot['scene_id'])
    used=set(shot['entity_ids'])|{scene['location_id']}
    retained='\n'.join(f'<{r["subject"]}> (appears in [Shot 1]): fully_preserved - preserve the defined {r["role"]} identity and design.' for r in refs if r.get('subject') and r['target_id'] in used)
    detail='[Shot 1] One '+f'{shot["duration"]:.2f}'+'-second segment. '+shot['framing']+' '+shot['angle']+' '+shot['camera']+' '+shot['blocking']+' '+shot['expression']+' Opening state: '+states(shot['start_state'])+'.\n'
    detail+='\n'.join(f'{b["start"]:.2f}–{b["end"]:.2f}s: {b["action"]}' for b in shot['beats'])
    for d in shot['dialogue']:
        detail+=f'\n{d["start"]:.2f}–{d["end"]:.2f}s: {labels.get(d["entity_id"],names[d["entity_id"]])} ({speakers[d["entity_id"]]}), delivery: {d["delivery"]} Says: <d>[{d["language"]}] {d["text"]}</d>'
    detail+='\nEnding state: '+states(shot['end_state'])+'.'
    text='summary:\n[reference generation] '+shot['action']+'\n\nretention_analysis:\n'+retained+'\n\ndetailed_description:\n'+detail+'\n\noverall_soundscape:\n'+shot['soundscape']+'\n\nnon_diegetic_music:\n'+(shot['music'] or 'N/A')
    return speech_direction.apply(text,plan,shot,labels)


def normalize_result(result):
    """Supply the fixed task marker without rewriting provider prose; raw output stays on disk."""
    result=copy.deepcopy(result)
    for chapter in result['chapters']:
        chapter['shot_prompt']=re.sub(r'(^summary:\s*)(?!\[)(?=\S)',r'\1[reference generation] ',chapter['shot_prompt'],count=1)
    return result


def validate_complete(text,refs,shot,names=(),*,check_dialogue=True):
    positions=[text.find(k+':') for k in FIELDS]
    if any(p<0 for p in positions) or positions!=sorted(positions) or any(text.count(k+':')!=1 for k in FIELDS):raise ValueError('Ref2VA requires all six sections exactly once in order')
    if not re.search(r'summary:\s*\[reference generation\]',text):raise ValueError('Ref2VA summary must begin with [reference generation]')
    pictures={r['label'].split()[-1] for r in refs};subjects={r['subject'].split()[-1] for r in refs if r.get('subject')}
    if set(re.findall(r'<Picture\s+(\d+)>',text))-pictures or set(re.findall(r'<Subject\s+(\d+)>',text))-subjects:raise ValueError('Prompt contains an unresolved reference label')
    if re.search(r'<(?:Video|Audio)\s+\d+>',text):raise ValueError('No video/audio reference asset is attached; motion guidance is a separate setting')
    definitions=text.split('summary:')[0]
    for ref in refs:
        if '<'+ref['label']+'>' not in definitions or (ref.get('subject') and '<'+ref['subject']+'>' not in definitions):raise ValueError('Scene and Shot definitions must identify every attached reference before summary')
    if len(text)>7000:raise ValueError('Combined prompt exceeds the director UI limit of approximately 7000 characters')
    if check_dialogue:speech_direction.validate_dialogue(text,shot)
    prompt_preparation.english(text,[*names,*(r['name'] for r in refs if r['role'] in ('character','crowd','voice'))])


def scene_bundle(p,scene,config=None,use_jobs=True):
    plan=p['production'];original_names=prompt_preparation.original_names(plan['canon']).values();assets=p.get('assets') or store.assets(p['id']);config=config or configuration(p['id'])
    setup=config['scenes'].get(scene['id'],{});refs,missing=refs_for_scene(plan,scene,assets)
    shots=[s for s in plan['shots'] if s['scene_id']==scene['id']]
    frame_inputs=[];composition_refs=[]
    for shot in shots:
        selection=setup.get('chapters',{}).get(shot['id'],{}).get('reference_frame','none')
        for frame in shot['keyframes']:
            if frame['moment'] in ('start','end') and selection in [frame['moment'],'both']:
                a=continuity.approved_for(plan,assets,frame['id']);frame_inputs.append(a['id'] if a else None)
                if a:composition_refs.append({'asset_id':a['id'],'target_id':frame['id'],'path':a['path'],'label':f'Picture {len(refs)+len(composition_refs)+1}','role':'composition','name':shot['title']+' · '+frame['moment'],'moment':frame['moment'],'shot_id':shot['id']})
    prepared,preparation=prompt_preparation.prepared(p,scene['id'])
    source_data={'frames':frame_inputs,'composition_scope':'scene' if composition_refs else None,'plan':plan,'scene_id':scene['id'],'refs':[{k:v for k,v in r.items() if k!='path'} for r in refs],'setup':setup}
    local_by_shot={shot['id']:refs_for_shot(plan,shot,assets,len(refs)+len(composition_refs)) for shot in shots}
    # Preserve unrelated legacy refinements; prop layouts need fresh slot mapping.
    if any(e['kind']=='prop' and any(e['id'] in s['entity_ids'] for s in shots) for e in plan['canon']):
        source_data['shot_reference_policy']='props-per-shot-v1'
        source_data['local_references']={sid:[{k:v for k,v in r.items() if k!='path'} for r in pair[0]] for sid,pair in local_by_shot.items()}
    if prepared:source_data['prepared']=store.digest(prepared)
    source_hash=store.digest(source_data)
    generated=None;generated_provider=''
    if use_jobs:
        jobs=p.get('jobs') or store.jobs(p['id'])
        generated_job=next((j for j in jobs if j['capability']=='h3_scene' and j['state']=='succeeded' and j['input'].get('delivery_hash')==source_hash),None)
        generated=generated_job['result'] if generated_job else None
        generated_provider=generated_job.get('provider','provider') if generated_job else ''
    prepared_global=None
    if prepared:
        definitions={e['entity_id']:e for e in prepared['subjects']}
        prepared_global='subject_definitions:\n'+'\n'.join(f'<{r["subject"]}> is {definitions[r["target_id"]]["name_en"]} from <{r["label"]}>. {definitions[r["target_id"]]["appearance"]}' for r in refs)
        prepared_global+='\nScene-wide appearance and lighting: '+prepared['visual_setting']
        if any(r['role']=='character' for r in refs):prepared_global+='\nIndividual character sheets define one identity across views; do not reproduce the panels or duplicate the person.'
        if any(r['role']=='crowd' for r in refs):prepared_global+='\n'+crowds.REFERENCE
    global_prompt=(generated or {}).get('global_prompt') or setup.get('global_prompt') or prepared_global or global_draft(plan,scene,refs)
    saved_scene_complete=bool(setup.get('global_prompt') and all(setup.get('chapters',{}).get(shot['id'],{}).get('shot_prompt') for shot in shots))
    needs_preparation=not (prepared or generated or saved_scene_complete)
    try:prompt_preparation.english(global_prompt,original_names)
    except ValueError:
        needs_preparation=True
        if not setup.get('prompt_edited') and not generated:global_prompt='subject_definitions:\nEnglish scene directions are not prepared yet.'
    refs=refs+composition_refs
    for ref in composition_refs:
        if not (setup.get('prompt_edited') and not generated) and '<'+ref['label']+'>' not in global_prompt:
            global_prompt+=f'\n<{ref["label"]}> is the {ref["moment"]} composition reference for Shot {ref["shot_id"]}. Apply its framing and staging only when requested in the Shot prompt; preserve the shared subject identities.'
    chapters=[]
    for shot in shots:
        index=plan['shots'].index(shot);chapter_setup=setup.get('chapters',{}).get(shot['id'],{})
        local_refs,local_missing=local_by_shot[shot['id']]
        chapter_refs=[dict(r) for r in refs]+local_refs;frame_missing=[]
        selected_frame=chapter_setup.get('reference_frame','none')
        for f in shot['keyframes']:
            if f['moment'] in ('start','end') and selected_frame in [f['moment'],'both'] and not continuity.approved_for(plan,assets,f['id']):
                frame_missing.append('Approve the requested '+f['moment']+' composition reference first')
        generated_chapter=next((c for c in (generated or {}).get('chapters',[]) if c['shot_id']==shot['id']),{})
        prepared_shot=next((x['shot_prompt'] for x in (prepared or {}).get('shots',[]) if x['shot_id']==shot['id']),None)
        if prepared_shot:prepared_shot=prompt_preparation.resolve(prepared_shot,prepared['subjects'],chapter_refs)
        prompt=generated_chapter.get('shot_prompt') or chapter_setup.get('shot_prompt') or prepared_shot or chapter_draft(plan,shot,chapter_refs)
        manual_prompt=chapter_setup.get('prompt_edited') and not generated_chapter
        names={e['entity_id']:e['name_en'] for e in (prepared or {}).get('subjects',[])}
        names.update({r['target_id']:'<'+r['subject']+'>' for r in chapter_refs if r.get('subject')})
        if not manual_prompt:prompt=speech_direction.apply(prompt,plan,shot,names)
        try:prompt_preparation.english(prompt,original_names)
        except ValueError:
            needs_preparation=True
            if not manual_prompt and not generated_chapter:prompt='summary:\n[reference generation] English Shot directions are not prepared yet.\n\nretention_analysis:\nPending.\n\ndetailed_description:\nPrepare this Scene before copying its Shot prompts.\n\noverall_soundscape:\nPending.\n\nnon_diegetic_music:\nPending.'
        for ref in composition_refs:
            if not manual_prompt and ref['shot_id']==shot['id'] and '<'+ref['label']+'>' not in prompt:
                prompt=prompt.replace('detailed_description:',f'detailed_description:\nUse <{ref["label"]}> for the {ref["moment"]} composition of this Shot.',1)
        if local_refs and not manual_prompt and not generated_chapter:
            prefix=prompt.split('summary:',1)[0]
            missing_definitions=[r for r in local_refs if '<'+r['label']+'>' not in prefix or '<'+r['subject']+'>' not in prefix]
            if missing_definitions:prompt=shot_definitions(missing_definitions,prepared)+'\n\n'+prompt
        combined=global_prompt+'\n\n'+prompt;issues=frame_missing
        try:validate_shared(global_prompt,refs)
        except ValueError as e:issues.append(str(e))
        try:validate_complete(combined,chapter_refs,shot,original_names)
        except ValueError as e:issues.append(str(e))
        if missing:issues.append('Approve scene references: '+', '.join(missing))
        if local_missing:issues.append('Approve this Shot references: '+', '.join(local_missing))
        if len(chapter_refs)>9:issues.append('Ref2VA supports at most nine image slots in this director; split the scene or reduce its reference set.')
        prev=plan['shots'][index-1] if index else None
        enabled=bool(config['continuity_enabled'] and prev and chapter_setup.get('guide_from_previous',False))
        chapters.append({'shot_id':shot['id'],'title':shot['title'],'number':index+1,'mode':'REF2VA','duration':shot['duration'],'scene_id':scene['id'],'shot_prompt':prompt,'text':combined,'references':chapter_refs,'local_references':local_refs,'missing_references':missing+local_missing,'issues':issues,'refined_by':generated_provider if generated else '',
            'guidance':{'enabled':enabled,'previous_shot_id':prev['id'] if prev else None,'previous_title':prev['title'] if prev else None,'cross_scene':bool(prev and prev['scene_id']!=scene['id']),'context_frames':config['context_frames'],'notes':chapter_setup.get('guidance_notes') or ('Continue from previous segment ending: '+states_text(prev['end_state'],plan)+'. Establish current opening: '+states_text(shot['start_state'],plan)+'. '+prev['transition_note'] if prev else 'First segment: no previous generated segment.'),'continuityFromPrev':bool(prev and chapter_setup.get('guide_from_previous',False))}})
    return {'scene_id':scene['id'],'title':scene['title'],'preparation':{**preparation,'required':needs_preparation},'mode':'REF2VA','global_prompt':global_prompt,'references':refs,'missing_references':missing,'chapters':chapters,'delivery_hash':source_hash,'refined_by':generated_provider if generated else ''}


def states_text(states,plan):
    names={e['id']:e['name'] for e in plan['canon']}
    return '; '.join(names[s['entity_id']]+' '+s['key']+': '+s['value'] for s in states)


def project_bundle(p):
    config=configuration(p['id'])
    bundle={'configuration':config,'scenes':[scene_bundle(p,s,config) for s in p['production']['scenes']] if p['production'] else [],'mode':'REF2VA','chapter_meaning':'One director segment / prompt group per shot'}
    return guidance.apply(p,bundle) if p['production'] else bundle


def validate_result(result,compiled,plan):
    validate_shared(result['global_prompt'],compiled['references'])
    expected={c['shot_id'] for c in compiled['chapters']}
    if len(result['chapters'])!=len(expected) or {c['shot_id'] for c in result['chapters']}!=expected:raise ValueError('Scene result must include every chapter exactly once')
    for chapter in result['chapters']:
        source=next(c for c in compiled['chapters'] if c['shot_id']==chapter['shot_id'])
        shot=next(s for s in plan['shots'] if s['id']==chapter['shot_id'])
        validate_complete(result['global_prompt']+'\n\n'+chapter['shot_prompt'],source['references'],shot,prompt_preparation.original_names(plan['canon']).values())
    return result
