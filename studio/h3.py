from .continuity import approved_for
from . import speech_direction,prompt_preparation

def compile_shot(plan,shot,assets,prepared=None):
    refs=[]
    for moment in ['start','end']:
        frame=next((f for f in shot['keyframes'] if f['moment']==moment),None)
        asset=approved_for(plan,assets,frame['id']) if frame else None
        if asset: refs.append({'moment':moment,'asset_id':asset['id'],'path':asset['path'],'label':f'Picture {len(refs)+1}'})
    dur=f'{shot["duration"]:.2f}'
    mode='T2VA'; prefix=''
    if len(refs)==2:
        mode='FL2VA';prefix=f'How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the {dur}-second mark of the target video.\n\n'
    elif refs:
        if refs[0]['moment']=='start':
            mode='I2VA';prefix='For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.\n\n'
        else:
            mode='L2VA';prefix=f'How the reference pictures align with the target video — <Picture 1> (from [Shot 1]) aligns with the {dur}-second mark of the target video.\n\n'
    ent={e['id']:e for e in plan['canon']};scene=next(s for s in plan['scenes'] if s['id']==shot['scene_id'])
    speaker_ids={e['id']:f'S{i+1}' for i,e in enumerate([e for e in plan['canon'] if e['kind'] in ('character','crowd','voice')])}
    # Raw canon may contain biography, hidden inventories and future events.
    # Unprepared output is only a shot draft; never concatenate those facts.
    loc=ent[scene['location_id']]
    states=lambda items: '; '.join(f'{ent[x["entity_id"]]["name"]} {x["key"]}: {x["value"]}' for x in items)
    body=f'[Shot 1] One continuous {dur}-second shot. {shot["framing"]}, {shot["angle"]}. {loc["name"]}. {scene["time_of_day"]}. Opening composition: {shot["blocking"]}. Starting state: {states(shot["start_state"])}. {shot["camera"]}. {shot["expression"]}. '
    if refs and refs[0]['moment']=='start': body+='Begin exactly from Picture 1, retaining its faces, clothes, props and spatial layout. '
    body+=' '.join(f'From {b["start"]:.2f} to {b["end"]:.2f} seconds, {b["action"]}' for b in shot['beats'])
    if not shot['beats']: body+=shot['action']
    for d in shot['dialogue']:
        body+=f' From {d["start"]:.2f} to {d["end"]:.2f} seconds, {ent[d["entity_id"]]["name"]} ({speaker_ids[d["entity_id"]]}) {d["delivery"]}, says: <d>[{d["language"]}] {d["text"]}</d>.'
    body+=f' At {dur} seconds, settle into: {states(shot["end_state"])}.'
    if refs and refs[-1]['moment']=='end': body+=f' Reach the exact final composition of {refs[-1]["label"]} by {dur} seconds through continuous movement.'
    soundscape=shot['soundscape'];music=shot['music'] or 'N/A';names={}
    if prepared:
        item=next(x for x in prepared['shots'] if x['shot_id']==shot['id'])
        prose=prompt_preparation.resolve(item['shot_prompt'],prepared['subjects'],[])
        names={e['entity_id']:e['name_en'] for e in prepared['subjects']}
        appearance=' '.join(e['name_en']+': '+e['appearance'] for e in prepared['subjects'] if e['entity_id'] in set(shot['entity_ids'])|{scene['location_id']})
        body=prepared['visual_setting']+' '+appearance+'\n'+prose.split('detailed_description:',1)[1].split('overall_soundscape:',1)[0].strip()
        if refs and refs[0]['moment']=='start':body+=' Begin exactly from Picture 1, preserving the approved opening composition.'
        if refs and refs[-1]['moment']=='end':body+=f' Reach the approved composition of {refs[-1]["label"]} by {dur} seconds.'
        soundscape=prose.split('overall_soundscape:',1)[1].split('non_diegetic_music:',1)[0].strip()
        music=prose.split('non_diegetic_music:',1)[1].strip()
        # Ref2VA often locates speech in soundscape; base H3 modes require the
        # tagged speech in the integrated timeline. Move the whole passage so
        # prose/timing is preserved instead of regex-editing dialogue clauses.
        if '<d>' in soundscape:
            body+='\n'+soundscape
            soundscape='Environmental and physical sounds follow the timed direction above.'
    text=prefix+'integrated_multimodal_description: '+body+'\n\noverall_soundscape: '+soundscape+'\n\nnon_diegetic_music: '+music
    text=speech_direction.apply(text,plan,shot,names,field='integrated_multimodal_description:')
    return {'shot_id':shot['id'],'mode':mode,'duration':shot['duration'],'text':text,'references':refs,'ready':bool(prepared),'original_names':list(prompt_preparation.original_names(plan['canon']).values())}

def validate_refinement(text,compiled,shot):
    import re
    fields=['integrated_multimodal_description:','overall_soundscape:','non_diegetic_music:']
    positions=[text.find(f) for f in fields]
    if any(p<0 for p in positions) or positions!=sorted(positions) or any(text.count(f)!=1 for f in fields):
        raise ValueError('H3 output must retain the three required fields in order')
    if compiled['references'] and not text.startswith(compiled['text'].split('\n\n')[0]):
        raise ValueError('H3 output changed the required frame-alignment instruction')
    permitted={str(i+1) for i in range(len(compiled['references']))}
    if not set(re.findall(r'Picture\s+(\d+)',text))<=permitted:
        raise ValueError('H3 output contains an unresolved reference label')
    speech_direction.validate_dialogue(text,shot)
    if '<d>' in text.split('overall_soundscape:',1)[1]:
        raise ValueError('首尾幀模式的對白必須放在 integrated_multimodal_description。')
    prompt_preparation.english(text,compiled.get('original_names',[]))
    return text
