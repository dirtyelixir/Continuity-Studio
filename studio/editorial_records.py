"""Version-bound editorial annotations consumed by review, playback and export.

Dependency projections are explicit and versioned so that each consumer can
react to exactly the fields it depends on:

* ``audio_cues`` depend on scene shot IDs/durations, dialogue,
  and the local edit order/ranges — NOT on visual keyframes, framing,
  style, or the visual canon.
* ``notes`` / ``knowledge`` (review annotations) retain the broader existing
  dependency set, but supplemental ``moment=='key'`` frames are excluded so
  that adding an unused intermediate visual frame does not stale them.

New adoption records store separate versioned dependency fingerprints
(``audio_dep`` / ``review_dep``).  Legacy records (pre-dating the split) must
compare against the saved editorial trial plan ONLY when their original
``scene_hash`` matches that saved snapshot; otherwise they are conservatively
stale.  Legacy records are never rewritten.
"""
import copy
from . import store
from .editorial_timing import timeline

AUDIO_DEPENDENCY_VERSION = 1
REVIEW_DEPENDENCY_VERSION = 1


def _local_shots(plan, sid):
    return [s for s in plan['shots'] if s['scene_id'] == sid]


def _local_ids(plan, sid):
    return {s['id'] for s in _local_shots(plan, sid)}


def _local_edits(plan, sid):
    ids = _local_ids(plan, sid)
    return [e for e in plan.get('edit_plan', []) if e['shot_id'] in ids]


def _audio_fields(shot):
    """Audio-relevant fields of a shot: identity, duration and dialogue. Saved cues own their text;
    H3 soundscape/music specifications are not consumed by this timeline."""
    return {
        'id': shot['id'],
        'duration': shot['duration'],
        'dialogue': shot.get('dialogue', []),
    }


def _edit_fields(edit):
    """Edit placement fields: identity, target shot and planned source range."""
    return {'id': edit['id'], 'shot_id': edit['shot_id'],
            'planned_edit_in': edit['planned_edit_in'],
            'planned_edit_out': edit['planned_edit_out']}


def audio_projection(plan, sid):
    """Explicit dependency projection for scene audio cues.

    Includes: scene identity, local shot IDs/durations/dialogue,
    and local edit order with planned ranges. Excludes: H3 music/soundscape, visual
    keyframes, framing/camera/blocking/states, style, and visual canon.
    """
    scene = next((s for s in plan['scenes'] if s['id'] == sid), None)
    shots = _local_shots(plan, sid)
    return {'version': AUDIO_DEPENDENCY_VERSION, 'scene': {'id': sid, 'exists': scene is not None},
            'shots': [_audio_fields(s) for s in sorted(shots,key=lambda s:s['id'])],
            'edit_plan': [_edit_fields(e) for e in _local_edits(plan, sid)]}


def _review_fields(shot):
    """Review-annotation fields: the full shot, minus supplemental interior
    ``moment=='key'`` frames (those are reviewed by the storyboard gate)."""
    return {**shot, 'keyframes': [f for f in shot.get('keyframes', []) if f.get('moment') != 'key']}


def review_projection(plan, sid):
    """Explicit dependency projection for review annotations (notes/knowledge).

    Retains the broader existing dependency set — full shots (including
    framing, states, keyframe endpoints), canon, and style — but excludes
    supplemental interior key frames so an unused intermediate visual frame
    does not stale the annotations.
    """
    scene = next((s for s in plan['scenes'] if s['id'] == sid), None)
    shots = _local_shots(plan, sid)
    ids = {s['id'] for s in shots}
    entities = {e for s in shots for e in s['entity_ids']} | ({scene['location_id']} if scene else set())
    return {'version': REVIEW_DEPENDENCY_VERSION, 'scene': scene,
            'shots': [_review_fields(s) for s in shots], 'edit_plan': _local_edits(plan,sid),
            'canon': [e for e in plan['canon'] if e['id'] in entities],
            'style': plan['style']}


def scene_hash(plan, sid):
    """Legacy whole-scene hash.  Kept byte-identical in input so that
    ``editorial.status()`` optimistic adoption detection is unchanged."""
    scene = next((s for s in plan['scenes'] if s['id'] == sid), None)
    shots = [s for s in plan['shots'] if s['scene_id'] == sid]
    ids = {s['id'] for s in shots}
    entities = {e for s in shots for e in s['entity_ids']} | ({scene['location_id']} if scene else set())
    return store.digest({'scene': scene, 'shots': shots,
                         'edit_plan': [e for e in plan.get('edit_plan', []) if e['shot_id'] in ids],
                         'canon': [e for e in plan['canon'] if e['id'] in entities],
                         'style': plan['style']})


def _audio_hash(plan, sid):
    return store.digest(audio_projection(plan, sid))


def _review_hash(plan, sid):
    return store.digest(review_projection(plan, sid))


def _legacy_trial(pid, record):
    """Saved editorial trial matching a legacy adoption record, or None."""
    t = next((t for t in store.setting('editorial_trials:' + pid, []) if t['id'] == record.get('trial_id')), None)
    return t if t and t['scene_id'] == record.get('scene_id') else None


def _legacy_current(pid, record, plan, sid):
    """A legacy record is current only if its saved ``scene_hash`` matches the
    snapshot of the saved trial plan it was adopted from.  Otherwise the
    original scene has changed in a way that cannot be reconstructed from the
    current plan, so it is conservatively stale."""
    if record.get('scene_hash') is None:
        return False
    t = _legacy_trial(pid, record)
    if t is None:
        return False
    return record['scene_hash'] == scene_hash(t['plan'], sid)


def _audio_current(pid, record, plan, sid):
    """Audio eligibility: new records compare their stored audio fingerprint
    against the current audio projection; legacy records fall back to the
    saved-trial-snapshot comparison above (never rewritten)."""
    if record.get('audio_dep'):
        return record['audio_dep'] == _audio_hash(plan, sid)
    return (record.get('scene_hash') == scene_hash(plan,sid) or
            _legacy_current(pid,record,plan,sid) and _audio_hash(_legacy_trial(pid,record)['plan'],sid)==_audio_hash(plan,sid))


def _review_current(pid, record, plan, sid):
    """Review-annotation eligibility with the same new/legacy split."""
    if record.get('review_dep'):
        return record['review_dep'] == _review_hash(plan, sid)
    return (record.get('scene_hash') == scene_hash(plan,sid) or
            _legacy_current(pid,record,plan,sid) and _review_hash(_legacy_trial(pid,record)['plan'],sid)==_review_hash(plan,sid))


def records(pid):
    result = store.setting('editorial_scenes:' + pid, {})
    legacy = store.setting('editorial_applied:' + pid, {})
    if legacy and not any(r.get('trial_id') == legacy.get('trial_id') and r.get('version') == legacy.get('version') for r in result.values()):
        t = next((t for t in store.setting('editorial_trials:' + pid, []) if t['id'] == legacy.get('trial_id')), None)
        if t and t['scene_id'] not in result and legacy.get('plan_hash') == store.digest(t['plan']):
            result[t['scene_id']] = {**legacy, 'scene_id': t['scene_id'], 'scene_hash': scene_hash(t['plan'], t['scene_id']), 'mapping': mapping(t)}
    return result


def review_context(p, plan=None):
    plan = plan or p.get('production')
    if not plan:
        return {}
    return {sid: {'audio_cues': r['audio_cues'], 'notes': r['notes'], 'knowledge': r.get('knowledge', {})}
            for sid, r in records(p['id']).items() if _review_current(p['id'], r, plan, sid) and _audio_current(p['id'],r,plan,sid)}


def adoption_record(t):
    """A new adoption record stores the legacy fields for compatibility plus
    separate versioned dependency fingerprints for the audio and review
    projections."""
    return dict(trial_id=t['id'], version=t['version'], scene_id=t['scene_id'],
                scene_hash=scene_hash(t['plan'], t['scene_id']), plan_hash=store.digest(t['plan']),
                audio_dep=_audio_hash(t['plan'], t['scene_id']), review_dep=_review_hash(t['plan'], t['scene_id']),
                audio_cues=copy.deepcopy(t['audio_cues']), notes=copy.deepcopy(t['notes']),
                knowledge=t['knowledge'], provenance=t['provenance'], mapping=mapping(t))


def mapping(t):
    original = {s['id']: s for s in t['baseline']['shots']}
    current = {s['id']: s for s in t['plan']['shots']}
    return [{'source_shot_id': n['source_shot_id'],
             'source_title': original.get(n['source_shot_id'], {}).get('title', n['source_shot_id']),
             'shot_id': sid,
             'source_frame_ids': [f['id'] for f in original.get(n['source_shot_id'], {}).get('keyframes', [])],
             'frame_ids': [f['id'] for f in current.get(sid, {}).get('keyframes', [])]} for sid, n in t['notes'].items()]


def state(p):
    plan = p.get('production')
    if not plan:
        return {'scenes': [], 'audio': [], 'warnings': []}
    shots = {s['id']: s for s in plan['shots']}
    edits = plan.get('edit_plan', [])
    rows = timeline({'shots': list(shots.values()), 'edit_plan': edits}, [])['visual']
    saved = records(p['id'])
    scenes = []
    audio = []
    warnings = []
    voices = p.get('postproduction', {})
    selected = voices.get('selected_lines', {})
    takes = {t['id']: t for t in voices.get('takes', []) if t.get('current') and t.get('state') == 'succeeded'}
    for sc in plan['scenes']:
        sid = sc['id']
        record = saved.get(sid)
        if not record:
            from .editorial import original_audio
            local_shots = [s for s in shots.values() if s['scene_id'] == sid]
            local_ids = {s['id'] for s in local_shots}
            record = {'scene_hash': scene_hash(plan, sid), 'trial_id': None, 'version': None, 'notes': {},
                      'audio_cues': original_audio({'shots': local_shots, 'edit_plan': [e for e in edits if e['shot_id'] in local_ids]})}
        status = 'current' if _review_current(p['id'],record,plan,sid) else 'stale'
        scene_rows = [e for e in rows if shots[e['shot_id']]['scene_id'] == sid]
        # A scene-local sound track cannot be placed as one block if other scenes interrupt it.
        indices = [i for i, e in enumerate(rows) if shots[e['shot_id']]['scene_id'] == sid]
        contiguous = bool(indices) and indices == list(range(indices[0], indices[-1] + 1))
        # Scene row tracks review annotations (broad dependency); audio validity
        # is judged independently against the narrow audio projection so that
        # purely visual changes keep the saved sound placement usable.
        if status == 'current' and not contiguous:
            status = 'needs_timeline_review'
        audio_valid = contiguous and _audio_current(p['id'], record, plan, sid)
        scenes.append({'scene_id': sid, 'status': status, 'trial_id': record['trial_id'], 'version': record['version'],
                       'mapping': record.get('mapping', []), 'audio_status':'current' if audio_valid else 'needs_review'})
        if not audio_valid:
            warnings.append({'code': 'EDITORIAL_AUDIO_STALE', 'scene_id': sid,
                             'message': '剪接聲音安排需要按目前分鏡重新核對。'})
        if status != 'current':
            warnings.append({'code': 'EDITORIAL_SOURCE_CHANGED', 'scene_id': sid,
                             'message': '剪接畫面狀態註記需要按目前分鏡重新核對；聲音有效性獨立顯示。'})
        if audio_valid:
            try:
                local = timeline({'shots': [s for s in shots.values() if s['scene_id'] == sid],
                                  'edit_plan': scene_rows}, record['audio_cues'])
            except ValueError as exc:
                scenes[-1]['status'] = 'needs_timeline_review'
                warnings.append({'code': 'EDITORIAL_INVALID', 'scene_id': sid, 'message': str(exc)})
                continue
            offset = scene_rows[0]['timeline_in']
            warnings.extend(local['warnings'])
            for cue in local['audio']:
                item = {**cue, 'scene_id': sid, 'scene_timeline_in': cue['timeline_in'],
                        'timeline_in': round(offset + cue['timeline_in'], 6),
                        'timeline_out': round(offset + cue['timeline_out'], 6),
                        'timing_status': 'planned_unverified', 'audio_asset': None}
                if cue['kind'] == 'dialogue':
                    shot = shots[cue['shot_id']]
                    index = next((i for i, d in enumerate(shot['dialogue']) if d['text'] == cue['text'] and d['entity_id'] == cue.get('entity_id') and d['start'] == cue['source_in'] and d['end'] == cue['source_out']), None)
                    t = takes.get(selected.get(f'{shot["id"]}:{index}'))
                    if t:
                        item['audio_asset'] = {'take_id': t['id'], 'path': f'postproduction/{t["kind"]}/{t["character_id"]}-{t["id"]}.wav',
                                               'sha256': t['result'].get('sha256'), 'source_in': 0, 'requires_duration_check': True}
                item['source_kind'] = 'saved_editorial' if sid in saved else 'default_shot_timing'
                audio.append(item)
    return {'scenes': scenes, 'audio': audio, 'warnings': warnings}
