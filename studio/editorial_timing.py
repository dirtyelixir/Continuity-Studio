"""Pure editorial timeline helper for the UI text-card animatic.

``timeline(plan, audio_cues)`` computes a deterministic, render-free preview of a
production: the visual sequence laid out by ``edit_plan`` (each entry's planned
source range placed back to back in sequence), the explicitly placed sound
cues (placed verbatim — audio may legally cross a visual cut or refer to a shot
that is not currently on screen), and a warning list that exposes source
dialogue in edited shots which no explicit dialogue cue fully covers.

The function is pure: no database, media, network, or rendering, and it never
mutates its inputs. It raises ``ValueError`` on malformed timing, duplicate IDs,
unknown shots, out-of-source ranges, negative timeline positions, or cues that
run beyond the full visual timeline.
"""
import math

__all__ = ['timeline']

_KINDS = ('dialogue', 'sound')


def _finite(value):
    """True for real (non-bool) finite numbers only."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _r6(value):
    return round(float(value), 6)


def _timeline_value(name, value, field):
    """Validate a non-negative finite timing value and return it as a float."""
    if not _finite(value):
        raise ValueError(f'{name} 的 {field} 必須為有限數字：{value!r}')
    value = float(value)
    if value < 0:
        raise ValueError(f'{name} 的 {field} 不可為負值：{value}')
    return value


def timeline(plan, audio_cues):
    """Build the animatic timeline from a plan and explicitly placed audio cues.

    ``plan`` must be a dict with ``shots`` (list of ``{id, duration,
    dialogue:[{start,end,text,language,entity_id}], ...}``) and ``edit_plan``
    (list of ``{id, shot_id, planned_edit_in, planned_edit_out, ...}``).
    ``audio_cues`` is a list of ``{id, shot_id, source_in, source_out,
    timeline_in, kind:'dialogue'|'sound', text:str, [entity_id]}``.

    Returns ``{'duration': float, 'visual': list, 'audio': list, 'warnings':
    list}``:

    - ``visual``: one entry per edit entry, in order, retaining all original
      edit fields plus sequential ``timeline_in`` / ``timeline_out`` (rounded
      to 6 digits).
    - ``audio``: one entry per cue, retaining all original cue fields plus
      ``timeline_out`` (rounded to 6 digits).
    - ``warnings``: ``{'code': 'DIALOGUE_UNCOVERED', 'shot_id', 'text'}`` for
      each source dialogue of an edited shot whose EXACT entire source range is
      not fully covered by at least one explicit dialogue cue of the same
      shot, text, and entity (when the cue carries one). A covered dialogue
      never warns, regardless of how the image is cut.
    """
    if not isinstance(plan, dict):
        raise ValueError('plan 必須為物件')
    shots = plan.get('shots')
    edits = plan.get('edit_plan')
    if not isinstance(shots, list):
        raise ValueError('plan.shots 必須為清單')
    if not isinstance(edits, list):
        raise ValueError('plan.edit_plan 必須為清單')
    if not isinstance(audio_cues, list):
        raise ValueError('audio_cues 必須為清單')

    # --- shots -------------------------------------------------------------
    shot_by_id = {}
    for shot in shots:
        if not isinstance(shot, dict):
            raise ValueError('shots 的每個項目必須為物件')
        sid = shot.get('id')
        if not isinstance(sid, str) or not sid:
            raise ValueError('每個鏡頭必須有非空白 id')
        if sid in shot_by_id:
            raise ValueError(f'鏡頭 ID 重複：{sid}')
        shot_by_id[sid] = shot

    # --- visual sequence -----------------------------------------------------
    visual = []
    cursor = 0.0
    for entry in edits:
        if not isinstance(entry, dict):
            raise ValueError('edit_plan 的每個項目必須為物件')
        eid = entry.get('id')
        if not isinstance(eid, str) or not eid:
            raise ValueError('每個編輯決定必須有非空白 id')
        for other in visual:
            if other.get('id') == eid:
                raise ValueError(f'編輯決定 ID 重複：{eid}')
        sid = entry.get('shot_id')
        if sid not in shot_by_id:
            raise ValueError(f'編輯決定 {eid} 引用了不存在的鏡頭 {sid!r}')
        shot = shot_by_id[sid]
        e_in = _timeline_value(f'編輯決定 {eid}', entry.get('planned_edit_in'), 'planned_edit_in')
        e_out = _timeline_value(f'編輯決定 {eid}', entry.get('planned_edit_out'), 'planned_edit_out')
        duration = _timeline_value(f'鏡頭 {sid}', shot.get('duration'), 'duration')
        if not (0 <= e_in < e_out <= duration):
            raise ValueError(f'編輯決定 {eid} 的範圍不在 0<=in<out<=時長 內')
        row = dict(entry)
        row['timeline_in'] = _r6(cursor)
        row['timeline_out'] = _r6(cursor + (e_out - e_in))
        visual.append(row)
        cursor += (e_out - e_in)
    duration = _r6(cursor)

    # --- audio cues ----------------------------------------------------------
    audio = []
    for cue in audio_cues:
        if not isinstance(cue, dict):
            raise ValueError('audio_cues 的每個項目必須為物件')
        cid = cue.get('id')
        if not isinstance(cid, str) or not cid:
            raise ValueError('每個音訊提示必須有非空白 id')
        for other in audio:
            if other.get('id') == cid:
                raise ValueError(f'音訊提示 ID 重複：{cid}')
        sid = cue.get('shot_id')
        if sid not in shot_by_id:
            raise ValueError(f'音訊提示 {cid} 引用了不存在的鏡頭 {sid!r}')
        shot = shot_by_id[sid]
        t_in = _timeline_value(f'音訊提示 {cid}', cue.get('timeline_in'), 'timeline_in')
        s_in = _timeline_value(f'音訊提示 {cid}', cue.get('source_in'), 'source_in')
        s_out = _timeline_value(f'音訊提示 {cid}', cue.get('source_out'), 'source_out')
        kind = cue.get('kind')
        if kind not in _KINDS:
            raise ValueError(f'音訊提示 {cid} 的 kind 必須為 dialogue 或 sound：{kind!r}')
        text = cue.get('text')
        if not isinstance(text, str):
            raise ValueError(f'音訊提示 {cid} 的 text 必須為字串')
        entity_id = cue.get('entity_id')
        if entity_id is not None and not isinstance(entity_id, str):
            raise ValueError(f'音訊提示 {cid} 的 entity_id 必須為字串')
        # Source range must exist in the shot.
        if s_in >= s_out:
            raise ValueError(f'音訊提示 {cid} 的來源範圍 source_in 必須小於 source_out')
        source_duration = _timeline_value(f'鏡頭 {sid}', shot.get('duration'), 'duration')
        if s_out > source_duration:
            raise ValueError(f'音訊提示 {cid} 的來源範圍超出鏡頭 {sid} 的時長')
        # Negative timeline_in already rejected; the cue must end within the
        # full visual timeline (it may cross a visual cut, so only the total
        # end is constrained here).
        if t_in > duration:
            raise ValueError(f'音訊提示 {cid} 的 timeline_in 超出完整時間線 {duration}')
        t_out = t_in + (s_out - s_in)
        if t_out > duration:
            raise ValueError(f'音訊提示 {cid} 超出完整時間線 {duration}')
        row = dict(cue)
        row['timeline_out'] = _r6(t_out)
        audio.append(row)

    # --- uncovered-dialogue warnings ----------------------------------------
    edited_shot_ids = dict.fromkeys(e.get('shot_id') for e in edits)
    cues_by_shot = {}
    for row in audio:
        if row.get('kind') == 'dialogue':
            cues_by_shot.setdefault(row['shot_id'], []).append(row)

    warnings = []
    for sid in edited_shot_ids:
        shot = shot_by_id[sid]
        for d in (shot.get('dialogue') or []):
            if not isinstance(d, dict):
                continue
            d_start = d.get('start')
            d_end = d.get('end')
            if not (_finite(d_start) and _finite(d_end)):
                continue
            d_start, d_end = float(d_start), float(d_end)
            if d_start >= d_end:
                continue
            d_text = d.get('text')
            d_entity = d.get('entity_id')
            covered = any(
                c.get('text') == d_text
                and (c.get('entity_id') is None or c.get('entity_id') == d_entity)
                and _finite(c.get('source_in')) and _finite(c.get('source_out'))
                and float(c['source_in']) <= d_start
                and float(c['source_out']) >= d_end
                for c in cues_by_shot.get(sid, ())
            )
            if not covered:
                warnings.append({'code': 'DIALOGUE_UNCOVERED', 'shot_id': sid, 'text': d_text})

    return {'duration': duration, 'visual': visual, 'audio': audio, 'warnings': warnings}
