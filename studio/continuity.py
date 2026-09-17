from . import production_methods
from .store import digest
from . import crowds,asset_roles

CHARACTER_SHEET_LAYOUT = 'four-view-v2'
CHARACTER_SHEET_INSTRUCTION = production_methods.reference('character-sheet.md')

def find_target(plan,target_id):
    for e in plan['canon']:
        if e['id']==target_id:
            if not asset_roles.is_visual(e): raise ValueError('這是只聞其聲的聲音資產，請到後製配音；不會製作圖片。')
            return 'entity',e,None
    for s in plan['shots']:
        for f in s['keyframes']:
            if f['id']==target_id: return 'frame',f,s
    raise ValueError('Unknown visual target')

def context(plan,target_id):
    kind,target,shot=find_target(plan,target_id)
    if kind=='entity': return {'style':plan['style'],'entity':asset_roles.visual_identity(target)}
    scene=next(s for s in plan['scenes'] if s['id']==shot['scene_id'])
    ids=set(shot['entity_ids'])|{scene['location_id']}
    i=plan['shots'].index(shot)
    previous=plan['shots'][i-1] if i else None
    # Empty compatibility fields must not invalidate approved historical keyframes.
    shot_context={k:v for k,v in shot.items() if k not in ('generation_duration','shot_purpose','direction') or v not in (None,'')}
    shot_context=dict(shot_context,keyframes=[f for f in shot_context['keyframes'] if f['moment']!='key'])
    scene_context={k:v for k,v in scene.items() if k!='director_plan' or v is not None}
    return {'style':plan['style'],'frame':target,'shot':shot_context,'scene':scene_context,'canon':[asset_roles.visual_identity(e) for e in plan['canon'] if e['id'] in ids and asset_roles.is_visual(e)], 'previous_shot':{'id':previous['id'],'end_state':previous['end_state'],'scene_id':previous['scene_id']} if previous else None}

def target_hash(plan,target_id): return digest(context(plan,target_id))

def approved_for(plan,assets,target_id):
    if any(e['id']==target_id and not asset_roles.is_visual(e) for e in plan['canon']):return None
    expected=target_hash(plan,target_id)
    return next((a for a in assets if a['target_id']==target_id and a['status']=='approved' and a['dependency_hash']==expected),None)

def references(plan,assets,target_id):
    kind,target,shot=find_target(plan,target_id)
    if kind=='entity':
        own=approved_for(plan,assets,target_id)
        return ([own] if own else []),[]
    c=context(plan,target_id); refs=[]; missing=[]
    for e in c['canon']:
        a=approved_for(plan,assets,e['id'])
        if a: refs.append(a)
        else: missing.append(e['name'])
    # An approved opening is the strongest spatial/identity anchor for the end frame.
    if target['moment'] in ('end','key'):
        opening=next((f for f in shot['keyframes'] if f['moment']=='start'),None)
        if opening:
            a=approved_for(plan,assets,opening['id'])
            if a: refs.append(a)
    return refs,missing

def image_task(plan,target_id):
    kind,target,shot=find_target(plan,target_id)
    if kind=='frame':
        if target['moment']=='key':
            intent=f'Create one single-moment storyboard image at {target["source_time"]} seconds within this source Shot. The target description and explicit frozen state specify THIS instant; do not substitute the source opening/ending or a collage/action sequence.'
        else:intent=f'Create one storyboard keyframe: the exact {target["moment"]} moment. Single still composition, not sequential panels. Do not depict later actions in the shot.'
        if any(e['kind']=='voice' and e['id'] in shot['entity_ids'] for e in plan['canon']):
            intent+=' Audio-only identities have no visible body or face; never depict their speakers.'
        return intent
    intent=f'Create one canonical {target["kind"]} reference image for {target["name"]}. '
    if target['kind']=='character': return intent+CHARACTER_SHEET_INSTRUCTION
    if target['kind']=='crowd': return intent+crowds.IMAGE
    if target['kind']=='location': return intent+'Show one coherent view of the connected layout and fixed spatial anchors, without characters.'
    return intent+'Show a clear three-quarter full view of the object and its distinctive details. One subject, no collage, no captions.'


def image_reference_roles(plan,target_id,refs):
    kind,target,_=find_target(plan,target_id)
    character_sheet=kind=='entity' and target['kind']=='character'
    entities={e['id']:e for e in plan['canon']}
    def role(a):
        e=entities.get(a['target_id'])
        if not e:
            if kind=='frame' and target['moment']=='key':return 'approved source-opening spatial and identity reference; preserve fixed geography and identity, while the target description controls the camera framing and changed state at the specified intermediate time'
            return 'approved storyboard composition; preserve spatial arrangement and identity'
        if e['kind']=='location': return f'LOCATION {e["name"]}; authoritative shared architecture, connected layout, openings, railings, materials and colors. The explicit target sublocation and time govern signage and lighting. Preserve fixed marks at their established sublocation; do not transfer unique damage from another floor or room. Reuse compatible shared architecture across explicitly different floors or rooms; never override an incompatible layout or same-place fixed anchor'
        if e['kind']=='crowd': return f'CROWD {e["name"]}; '+crowds.REFERENCE
        if e['kind']=='character':
            identity=f'CHARACTER {e["name"]}; authoritative identity/design source. '
            if character_sheet: return identity+'Preserve identity in all four requested panels; follow the required sheet layout, not the source composition.'
            return identity+'Extract ONE single character identity from it. Never reproduce the panels, separators or four duplicate figures in this image. Ignore the sheet background and staging'
        return f'{e["kind"].upper()} {e["name"]}; authoritative object design, materials and distinctive details; ignore incidental background and staging'
    # Approval notes remain provenance, never appended as rendering commands.
    return [f'Image {i+1}: {role(a).rstrip(chr(46))}.' for i,a in enumerate(refs)]


def image_prompt(plan,target_id,refs,feedback=''):
    """Preparation request, not renderer prose. Used by previews and image jobs."""
    from . import image_prompts
    basis=image_prompts.source(plan,target_id,feedback)
    basis['reference_notes_context']=[{'target_id':a['target_id'],'note':a['note']} for a in refs if a.get('note')]
    return image_prompts.instruction(basis,image_task(plan,target_id),image_reference_roles(plan,target_id,refs))


def qc(plan,assets):
    issues=[]
    prev=None
    for s in plan['shots']:
        if not s['beats']: issues.append({'level':'warning','target_id':s['id'],'message':'No timed action beats.'})
        if prev and prev['scene_id']==s['scene_id']:
            end={(x['entity_id'],x['key']):x['value'] for x in prev['end_state']}
            for st in s['start_state']:
                key=(st['entity_id'],st['key'])
                if key in end and end[key]!=st['value'] and not s['transition_note'].strip(): issues.append({'level':'error','target_id':s['id'],'message':f'Unexplained state change for {key[0]}.{key[1]}: {end[key]} → {st["value"]}'})
        prev=s
        for f in s['keyframes']:
            _,missing=references(plan,assets,f['id'])
            if missing: issues.append({'level':'pending','target_id':f['id'],'message':'Approve references: '+', '.join(missing)})
    return issues
