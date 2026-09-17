"""Single source for frozen dynamic state; prose alignment remains model work."""
import copy
from . import store, continuity

CONTRACT_VERSION = 'frame-moment-contract-v1'


def build(plan, target_id):
    kind, target, shot = continuity.find_target(plan, target_id)
    if kind != 'frame':
        return None
    moment = target['moment']
    time = 0 if moment == 'start' else shot['duration'] if moment == 'end' else target['source_time']
    states = target['state'] if moment == 'key' else shot[moment+'_state']
    if shot.get('canonical_state'):
        from .shot_state import states_at
        states=states_at(shot,time)
    scene = next(s for s in plan['scenes'] if s['id'] == shot['scene_id'])
    ids = set(shot['entity_ids']) | {scene['location_id']}
    return {'version': CONTRACT_VERSION, 'target_id': target_id, 'shot_id': shot['id'],
            'moment': moment, 'source_time': time, 'shot_duration': shot['duration'],
            'state_source': f"shots[{shot['id']}].keyframes[{target_id}].state" if moment == 'key' else f"shots[{shot['id']}].{moment}_state",
            **({'state_source':f"shots[{shot['id']}].canonical_state.moments[time={time:g}]",'canonical_version':shot['canonical_state']['version']} if shot.get('canonical_state') else {}),
            'states': copy.deepcopy(states),
            'identity_names': {e['id']:e['name'] for e in plan['canon'] if e['id'] in ids},
            'temporal_context': {'beats': copy.deepcopy(shot['beats']),
                                 'note': 'Event timing is context only, never multi-instant render text. A contradiction between authoritative state and timeline remains a conflict.'},
            'precedence': ['For explicit dynamic facts, exact moment state takes precedence over descriptive prose, including pose, eyeline, ownership, power/damage and reveal.',
                           'Frame description supplies composition and compatible unspecified detail. Keep specified offscreen facts offscreen; do not force all tracked entities into view.',
                           'Preserve explicit requested revisions. Do not silently discard a requested creative change to comply with old state; report incompatible authoritative requirements.'],
            'repair_policy': 'Automatically align stale descriptive dynamic detail to the exact state. In omitted_context quote the superseded phrase and applied state. Preserve original production; never guess semantics by keyword rules. Unresolved authoritative state/timeline/request conflicts must remain in conflicts.'}


def audit(result, basis):
    contract = basis.get('frame_moment_contract')
    if not contract:
        return None
    if result.get('target_id') != basis['target_id']:
        raise ValueError('Prepared brief target does not match the frame source.')
    return {'version': CONTRACT_VERSION, 'source_hash': store.digest(basis),
            'result_hash': store.digest(result),
            **{k:copy.deepcopy(contract[k]) for k in ('target_id','shot_id','moment','source_time','state_source','states')},
            'omitted_context': list(result.get('omitted_context') or []),
            'conflicts': list(result.get('conflicts') or []),
            'semantic_note': 'Records provider interpretation; not a deterministic proof of synchronization or rendered-pixel quality.'}


def write(work, result, basis):
    record = audit(result, basis)
    if record is not None:
        (work/'moment-alignment.json').write_text(store.encode(record))
    return record
