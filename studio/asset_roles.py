"""Shared identities, scene usage and audio-only cast are independent concepts."""
from . import store

PLANNING='''
ASSET CLASSIFICATION: Canon kind=voice represents a voice-only identity (radio/PA,
narration, telephone or unseen speaker who has no visual appearance in this work).
Do not invent a face, costume or turnaround for a voice. Keep its stable ID in
shot.entity_ids, state and dialogue for sound continuity; never request its image
or count it toward image-reference slots. A visible person speaking from offscreen
in another shot remains a character, not a voice-only identity. A radio device is
a separate visual prop. Preserve all existing voice identities and voice timing.
Canon scope=public for the main protagonist and identities intentionally shared
across the main storyline, even if only the first chapter exists. scope=scene for
chapter/scene-specific assets. scope=auto is for legacy or undecided scope only.
Shared identity does not mean present in every shot: shot.entity_ids and the Scene
location define actual usage. Reuse the same ID across scenes/chapters rather than
creating duplicate assets; do not promote a scene's pose or injury to universal canon.
'''

def is_visual(entity): return entity['kind']!='voice'

def visual_identity(entity):
    # Organization alone cannot invalidate a previously approved identity image.
    return {k:v for k,v in entity.items() if k!='scope'}

def visual_ids(plan,ids):
    visual={e['id'] for e in plan['canon'] if is_visual(e)}
    return [i for i in ids if i in visual]

def groups(plan):
    scenes=plan['scenes'];canon=plan['canon']
    uses={s['id']:set([s['location_id']]+[i for shot in plan['shots'] if shot['scene_id']==s['id'] for i in shot['entity_ids']]) for s in scenes}
    chapters=plan.get('chapters') or [{'id':'standalone','title':'本篇','scene_ids':[s['id'] for s in scenes]}]
    def public(e):
        if e.get('scope')=='public':return True
        if e.get('scope')=='scene':return False
        return sum(any(e['id'] in uses[sid] for sid in ch['scene_ids']) for ch in chapters)>1
    public_ids=[e['id'] for e in canon if public(e)];pub=set(public_ids)
    used=set().union(*uses.values()) if uses else set()
    return {'public_ids':public_ids,'chapters':[{'id':ch['id'],'title':ch['title'],'scenes':[{'id':s['id'],'title':s['title'],'entity_ids':[e['id'] for e in canon if e['id'] in uses[s['id']] and e['id'] not in pub],'public_ids':[i for i in public_ids if i in uses[s['id']]]} for s in scenes if s['id'] in ch['scene_ids']]} for ch in chapters], 'unassigned_ids':[e['id'] for e in canon if e['id'] not in used|pub]}

def voice_direction(plan,shot,names=None):
    names=names or {}
    voices=[e for e in plan['canon'] if e['kind']=='voice' and e['id'] in shot['entity_ids']]
    if not voices:return ''
    return 'Audio-only identities: '+', '.join(names.get(e['id'],e['id']) for e in voices)+'. These voices have no visible body or face; never depict their speakers or assign their lines/mouth movements to anyone on screen. Preserve their scripted source, sound and timing; they require no picture reference. '
