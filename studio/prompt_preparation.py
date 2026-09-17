"""Scene-scoped English direction, independent of whether images are approved yet."""
import re,copy,unicodedata
from .shot_state import model_view
from . import asset_roles,store, speech_direction

VERSION='english-scoped-v1'
RULES=asset_roles.PLANNING+'''Write prompt descriptions in English. Preserve person/character names exactly as supplied by canon in their original language; never translate or romanize them. The legacy field name_en MUST contain the original canonical name for characters, crowds and voices. Exact dialogue inside <d> tags also retains its original language. Use entity tokens where appropriate; translate sound descriptions, acting, state, delivery, and music directions too. Describe visible source text in English and leave exact lettering to postproduction. Do not paste project production notes into prompts. Scene shared direction contains only this location's reusable appearance, light and atmosphere. Each Shot contains only its own camera, blocking, acting, actions, timing and sound. Exclude future/past scenes, chapter counts, adaptation decisions, canon bookkeeping, source conflicts, director/module names and method commentary. Extract only applicable concrete cinematography from broader style notes. Every action clause identifies its actor and object owner explicitly; never let a semicolon imply a different actor. Do not transfer one person's phone, hand, injury or action to another. Distinguish a battery level from dialogue or a person reading aloud. Preserve exact scripted utterances, language tags, timings, prop ownership and causality. Do not invent dialogue or story events.'''


def source(plan,sid):
    scene=next(s for s in plan['scenes'] if s['id']==sid)
    shots=[s for s in plan['shots'] if s['scene_id']==sid]
    ids={scene['location_id']}|{eid for s in shots for eid in s['entity_ids']}
    speakers={}
    for shot in plan['shots']:
        for d in shot['dialogue']:
            if d['entity_id'] not in speakers:speakers[d['entity_id']]=f'S{len(speakers)+1}'
    return {'version':VERSION,'scene':scene,'shots':shots,'canon':[asset_roles.visual_identity(e) for e in plan['canon'] if e['id'] in ids], 'style_context_for_interpretation_only':plan['style'],'speaker_ids':{k:v for k,v in speakers.items() if k in ids}}


GLOBAL_RULES='''Subject definitions contain only reference-image mapping and reusable visible identity: face, hair, body shape, clothing, visible accessories, prop shape/material/color and location layout. Do not copy canonical facts wholesale. Exclude biography, relationships, family history, habitual reactions, hidden pocket inventories, review verdicts, human approval notes, provenance and future prop events. No jewelry is a visible appearance constraint and may be retained when relevant. Props are Shot-specific references, never Scene-global definitions. Keep their reusable appearance in the separate subjects records for the compiler to place in each relevant Shot. Do not embed handheld prop inventories in character appearance or visual_setting. Put hand ownership, taking a phone from a pocket, changing water levels, injuries and reaction beats in the relevant Shot, not in the shared global. Scene atmosphere must be visible or audible, not a story synopsis or symbolic interpretation.'''
RULES+='\n'+GLOBAL_RULES

SCOPE_RULES='''Source style and neighboring Shots are interpretation context only, never text to paste into the output. Extract only this target's applicable visual/audio direction. Do not import neighboring dialogue, actions, biography, review notes or editorial bookkeeping. The editable starting text and user feedback guide the requested creative revision. Preserve natural object use and character eyelines: a character checking a screen is not an instruction to display it to the camera. Do not invent a screen-reveal gesture to make information readable. If coverage and a required reveal conflict, identify the conflict rather than silently changing character behavior.'''


def model_context(source,omit_current=False):
    """Narrow outbound reasoning context without changing saved source hashes."""
    data=copy.deepcopy(source)
    if 'style' in data:data['style_context_for_interpretation_only']=data.pop('style')
    if omit_current:data.pop('current_prompt',None)
    for key in ('previous_shot','next_shot'):
        if data.get(key):
            data[key]={k:v for k,v in data[key].items() if k in ('id','scene_id','framing','angle','blocking','start_state','end_state','transition_note')}
    def clean(value):
        if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k not in ('path','director_note')}
        if isinstance(value,list):return [clean(v) for v in value]
        return value
    from . import shot_state
    return shot_state.model_view(clean(data))


def instruction(basis):
    from . import prompt_writing
    return '''Prepare production-ready English Ref2VA directions for exactly the supplied Scene and its Shots, without generating media. Return scene_id, visual_setting, subjects [{entity_id,name_en,appearance}], shots [{shot_id,shot_prompt}]. Include every supplied canonical entity exactly once; For visual entities, appearance describes only this scene's reusable visible identity, clothing, materials and environment, excluding biography and state from other scenes. For kind=voice, appearance describes only the sound identity/source; never invent a visible body, face, clothing or image reference. Audio-only entity tokens belong in sound/dialogue, not visible retention. visual_setting is a concise paragraph for this Scene only, not a plot summary. Each shot_prompt has exactly these five sections in order: summary:, retention_analysis:, detailed_description:, overall_soundscape:, non_diegetic_music:. summary starts [reference generation]. Use <Entity entity_id> tokens for people/objects/locations in Shot prose; the app resolves them to the available image slots later. Do not invent Picture/Subject/Audio/Video references. retention_analysis covers entities actually visible/used in this Shot, not every possible scene asset. All Shots use local [Shot 1] and 0-to-duration timing. Include explicit camera/framing/blocking, opening/ending states, concrete timed action beats, facial expression and sound. Use supplied global S-number speaker IDs. Dialogue syntax MUST be exactly <d>[language] words</d>, for example <d>[yue-HK] exact original Cantonese</d>; never use XML attributes such as language=. Keep each shot_prompt under 4200 characters, visual_setting under 650 and each subject appearance under 240. Do not include global subject_definitions in a Shot. Internally check each action's actor, recipient and held object against canon, blocking and state before returning. No tools.\n'''+RULES+'\n'+SCOPE_RULES+'\nTASK CONTRACT:\n'+prompt_writing.contract_line('shot_prompt')+'\nSCENE SOURCE:\n'+store.encode(model_view(basis))


def original_names(canon):
    return {e['id']:e['name'] for e in canon if e['kind'] in ('character','crowd','voice')}


def preserve_names(result,canon):
    """Resolve name spelling from canon without modifying historical job output."""
    result=copy.deepcopy(result);names=original_names(canon);aliases={}
    for e in result['subjects']:
        if e['entity_id'] in names:
            old=e['name_en'];new=names[e['entity_id']]
            if old!=new:
                aliases[old]=new
                # Old prepared prop labels may use the last name alone possessively.
                if ' ' in old:aliases[old.rsplit(' ',1)[-1]+"'s"]=new+"'s"
            e['name_en']=new
    def replace(text):
        if not aliases:return text
        pattern=r'(?<![\w])('+ '|'.join(re.escape(x) for x in sorted(aliases,key=len,reverse=True))+r')(?![\w])'
        return ''.join(part if part.startswith('<d>') else re.sub(pattern,lambda m:aliases[m[0]],part) for part in re.split(r'(<d>[\s\S]*?</d>)',text))
    result['visual_setting']=replace(result['visual_setting'])
    for e in result['subjects']:
        e['name_en']=replace(e['name_en']);e['appearance']=replace(e['appearance'])
    for s in result['shots']:s['shot_prompt']=replace(s['shot_prompt'])
    return result


def english(text,names=()):
    prose=re.sub(r'<d>[\s\S]*?</d>','',text)
    for name in sorted(set(names),key=len,reverse=True):
        if name:prose=prose.replace(name,'')
    if any(c.isalpha() and 'LATIN' not in unicodedata.name(c,'') for c in prose):
        raise ValueError('除原作人名及對白外，提示詞必須使用英文；請整理英文提示詞。')


def normalize(result,basis=None):
    result=copy.deepcopy(result)
    for item in result['shots']:
        item['shot_prompt']=re.sub(r'<d\s+language=["\']([^"\']+)["\']\s*>',lambda m:'<d>['+m[1]+'] ',item['shot_prompt'])
        if basis:
            shot=next(s for s in basis['shots'] if s['id']==item['shot_id'])
            index=0
            def tag(match):
                nonlocal index
                raw=match[1];d=shot['dialogue'][index] if index<len(shot['dialogue']) else None;index+=1
                if d and raw.strip()==d['text'].strip():return '<d>['+d['language']+'] '+raw.strip()+'</d>'
                return match[0]
            item['shot_prompt']=re.sub(r'<d>([\s\S]*?)</d>',tag,item['shot_prompt'])
    return preserve_names(result,basis['canon']) if basis else result


def validate(result,basis):
    if result['scene_id']!=basis['scene']['id']:raise ValueError('Wrong prepared scene')
    ids=[e['id'] for e in basis['canon']]
    if sorted(x['entity_id'] for x in result['subjects'])!=sorted(ids):raise ValueError('Prepared subjects must match this scene')
    if [s['shot_id'] for s in result['shots']]!=[s['id'] for s in basis['shots']]:raise ValueError('Prepared shots must match source order')
    names=original_names(basis['canon'])
    english(result['visual_setting'],names.values())
    for e in result['subjects']:
        if e['entity_id'] in names and e['name_en']!=names[e['entity_id']]:raise ValueError('人名必須保留原作寫法，不可翻譯或音譯。')
        english(e['name_en']+' '+e['appearance'],names.values())
    fields=['summary:','retention_analysis:','detailed_description:','overall_soundscape:','non_diegetic_music:']
    for item,shot in zip(result['shots'],basis['shots']):
        text=item['shot_prompt'];english(text,names.values())
        indices=[text.find(f) for f in fields]
        if min(indices)<0 or indices!=sorted(indices) or any(text.count(f)!=1 for f in fields):raise ValueError('Prepared shot sections are invalid')
        if not re.search(r'summary:\s*\[reference generation\]',text):raise ValueError('Missing reference generation marker')
        allowed=set(shot['entity_ids'])|{basis['scene']['location_id']}
        if set(re.findall(r'<Entity ([^>]+)>',text))-allowed:raise ValueError('Prompt uses an entity outside this Shot')
        if re.search(r'<(?:Picture|Subject|Video|Audio)\s',text) or 'subject_definitions:' in text:raise ValueError('Preparation must use entity tokens, not final image slots')
        speech_direction.validate_dialogue(text,shot)
        if re.findall(r'<d>\s*\[([^\]]+)\]',text)!=[d['language'] for d in shot['dialogue']]:raise ValueError('Dialogue languages must match the source')
    return result


def prepared(p,sid):
    basis=source(p['production'],sid);digest=store.digest(basis)
    jobs=store.jobs(p['id'])
    def compatible(job):
        data=job['input']
        if data.get('preparation_hash')==digest:return True
        # Reuse preparations made during the scope rollout only when their
        # complete source still matches after removing organizational metadata.
        saved=data.get('preparation_source')
        if not isinstance(saved,dict) or store.digest(saved)!=data.get('preparation_hash'):return False
        normalized=copy.deepcopy(saved)
        normalized['canon']=[asset_roles.visual_identity(e) for e in normalized.get('canon',[])]
        return store.digest(normalized)==digest
    matches=[j for j in jobs if j['capability']=='h3_prepare' and j['target_id']==sid and compatible(j)]
    done=next((j for j in matches if j['state']=='succeeded'),None)
    latest=matches[0] if matches else None
    return (preserve_names(done['result'],basis['canon']) if done else None), {'status':'ready' if done else latest['state'] if latest else 'needed','job_id':(done or latest or {}).get('id')}


def resolve(text,subjects,refs):
    labels={r['target_id']:'<'+r['subject']+'>' for r in refs if r.get('subject')}
    names={e['entity_id']:e['name_en'] for e in subjects}
    return re.sub(r'<Entity ([^>]+)>',lambda m:labels.get(m[1],names[m[1]]),text)
