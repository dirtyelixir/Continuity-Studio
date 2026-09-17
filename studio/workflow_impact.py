"""Read-only preview of a proposed editorial baseline revision."""
from . import store, continuity, generation_groups, editorial_records, take_lifecycle


def preview(p,plan):
    after={**p,'production':plan};assets=store.assets(p['id']);frames=[]
    for asset in assets:
        if asset['status'] not in ('approved','pending'):continue
        try:changed=continuity.target_hash(p['production'],asset['target_id'])!=continuity.target_hash(plan,asset['target_id'])
        except ValueError:changed=True
        if changed:frames.append(asset['target_id'])
    from . import storyboard_board
    for scene in p['production']['scenes']:
        before=storyboard_board.scene_state(p,scene['id'],assets)
        try:updated=storyboard_board.scene_state(after,scene['id'],assets)
        except (ValueError,KeyError,StopIteration):updated={'panels':[]}
        ready={a['frame_id'] for panel in updated['panels'] for a in panel['anchors'] if a['ready']}
        frames.extend(a['frame_id'] for panel in before['panels'] for a in panel['anchors'] if a['ready'] and a['frame_id'] not in ready)
    units=[]
    for sid,saved in generation_groups.config(p['id']).get('plans',{}).items():
        try:
            changed=generation_groups.planning_fingerprint(generation_groups.planning_source(p,sid))!=generation_groups.planning_fingerprint(generation_groups.planning_source(after,sid))
        except (ValueError,KeyError):changed=True
        if changed:units.extend(i['title'] for i in saved['result']['groups'])
    from . import video_render
    with store.db() as c:
        takes=[video_render.decode(r) for r in c.execute("SELECT * FROM video_takes WHERE project_id=? AND state='succeeded'",(p['id'],))]
    needs_review=[]
    for t in takes:
        old=take_lifecycle.compatibility(p,t);new=take_lifecycle.compatibility(after,t)
        if old['current_hash']!=new['current_hash'] and not take_lifecycle.accepted_compatibility(new):needs_review.append(t['id'])
    audio=[s['id'] for s in p['production']['scenes'] if editorial_records.audio_projection(p['production'],s['id'])!=editorial_records.audio_projection(plan,s['id'])]
    return {'assets_require_review':sorted(set(frames)),'generation_units_change':units,
        'takes_retained_needing_review':needs_review,'audio_changed_scenes':audio,
        'dialogue_audio_unchanged':not audio,'production_revision':p['revision']}
