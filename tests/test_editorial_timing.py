"""Behavioral tests for the pure editorial-timeline helper (UI text-card animatic)."""
import copy
import math
import pytest

from studio.editorial_timing import timeline


def shot(sid, duration=4.0, dialogue=()):
    return {'id': sid, 'duration': duration, 'dialogue': list(dialogue), 'note': f'shot {sid}'}


def line(start, end, text, entity_id='c1', language='yue'):
    return {'start': start, 'end': end, 'text': text, 'language': language, 'entity_id': entity_id}


def edit(eid, sid, e_in, e_out, **extra):
    row = {'id': eid, 'shot_id': sid, 'planned_edit_in': e_in, 'planned_edit_out': e_out,
           'cut_in_reason': '起', 'cut_out_reason': '止', 'continuity_note': '註'}
    row.update(extra)
    return row


def cue(cid, sid, s_in, s_out, t_in, kind='dialogue', text='', **extra):
    row = {'id': cid, 'shot_id': sid, 'source_in': s_in, 'source_out': s_out,
           'timeline_in': t_in, 'kind': kind, 'text': text}
    row.update(extra)
    return row


def plan(*edits):
    shots = [e['shot_id'] for e in edits]
    by_id = {}
    for e in edits:
        by_id.setdefault(e['shot_id'], 0)
        by_id[e['shot_id']] += 1
    return {'shots': [shot(sid) for sid in dict.fromkeys(shots)], 'edit_plan': list(edits)}


# --- visual layout -----------------------------------------------------------

def test_visual_sequence_is_sequential_and_retains_edit_fields():
    p = plan(edit('E1', 's1', 0.5, 2.5), edit('E2', 's2', 1.0, 3.5))
    p['shots'][0].update(dialogue=[line(0.5, 2.5, '你好')])
    p['shots'][1].update(dialogue=[line(1.0, 3.0, '再見')])
    cues = [cue('A1', 's1', 0.5, 2.5, 0.0, text='你好'), cue('A2', 's2', 1.0, 3.0, 2.0, text='再見')]
    result = timeline(p, cues)
    assert [v['id'] for v in result['visual']] == ['E1', 'E2']
    v0, v1 = result['visual']
    assert v0['timeline_in'] == 0.0 and v0['timeline_out'] == 2.0
    assert v1['timeline_in'] == 2.0 and v1['timeline_out'] == 4.5
    assert result['duration'] == 4.5
    # original edit fields retained verbatim
    assert v0['planned_edit_in'] == 0.5 and v0['cut_out_reason'] == '止'
    assert v1['planned_edit_in'] == 1.0 and v1['continuity_note'] == '註'


def test_visual_rounds_to_six_digits():
    p = plan(edit('E1', 's1', 0, 1 / 3), edit('E2', 's2', 0, 1 / 3))
    result = timeline(p, [])
    assert result['visual'][0]['timeline_out'] == round(1 / 3, 6)
    assert result['visual'][1]['timeline_in'] == round(1 / 3, 6)
    assert result['visual'][1]['timeline_out'] == round(2 / 3, 6)
    assert result['duration'] == round(2 / 3, 6)


# --- reused source -----------------------------------------------------------

def test_reused_source_twice_plays_independently_and_covers_once():
    # Same 4s shot, same source dialogue used by two separate edit entries.
    p = plan(edit('E1', 's1', 0.0, 2.0), edit('E2', 's1', 2.0, 4.0))
    p['shots'][0].update(dialogue=[line(0.0, 4.0, '整段台詞')])
    cues = [cue('A1', 's1', 0.0, 4.0, 0.0, text='整段台詞')]
    result = timeline(p, cues)
    assert result['duration'] == 4.0
    assert len(result['visual']) == 2
    assert result['visual'][0]['timeline_out'] == 2.0
    assert result['visual'][1]['timeline_in'] == 2.0
    # The one explicit cue covers the exact entire source dialogue -> no warning,
    # even though the image is cut in the middle of it.
    assert result['warnings'] == []


# --- L / J cuts --------------------------------------------------------------

def test_l_cut_audio_starts_before_visual():
    # L cut: the sound of shot B starts while shot A is still on screen.
    p = plan(edit('E1', 'sA', 0.0, 2.0), edit('E2', 'sB', 0.0, 2.0))
    p['shots'][1].update(dialogue=[line(0.0, 1.0, 'B 先講')])
    cues = [cue('A1', 'sB', 0.0, 1.0, 1.0, text='B 先講')]  # starts at 1.0, before B image at 2.0
    result = timeline(p, cues)
    a = result['audio'][0]
    assert a['timeline_in'] == 1.0 and a['timeline_out'] == 2.0
    # legal: audio crosses into A's image; dialogue covered -> no warning
    assert result['warnings'] == []
    assert result['duration'] == 4.0


def test_j_cut_audio_continues_after_visual_cut():
    # J cut: shot A's dialogue keeps playing after the cut to shot B.
    p = plan(edit('E1', 'sA', 0.0, 2.0), edit('E2', 'sB', 0.0, 2.0))
    p['shots'][0].update(dialogue=[line(1.0, 3.0, 'A 的台詞')])
    cues = [cue('A1', 'sA', 1.0, 3.0, 1.0, text='A 的台詞')]  # plays 1.0-3.0; image of A ends at 2.0
    result = timeline(p, cues)
    a = result['audio'][0]
    assert a['timeline_in'] == 1.0 and a['timeline_out'] == 3.0
    assert result['warnings'] == []


def test_audio_may_refer_to_shot_not_currently_showing():
    # The cue belongs to sB but is placed during sA's screen time (and vice versa).
    p = plan(edit('E1', 'sA', 0.0, 2.0), edit('E2', 'sB', 0.0, 2.0))
    p['shots'][1].update(dialogue=[line(0.0, 1.0, 'B 台詞')])
    cues = [cue('A1', 'sB', 0.0, 1.0, 0.5, text='B 台詞')]
    result = timeline(p, cues)
    assert result['audio'][0]['timeline_out'] == 1.5
    assert result['warnings'] == []


# --- omitted dialogue warnings -----------------------------------------------

def test_omitted_dialogue_warns_and_covered_dialogue_does_not():
    p = plan(edit('E1', 's1', 0.0, 4.0))
    p['shots'][0].update(dialogue=[line(0.5, 1.5, '第一句'), line(2.0, 3.0, '第二句')])
    # Only the first line is explicitly covered.
    cues = [cue('A1', 's1', 0.5, 1.5, 0.5, text='第一句')]
    result = timeline(p, cues)
    assert result['warnings'] == [{'code': 'DIALOGUE_UNCOVERED', 'shot_id': 's1', 'text': '第二句'}]


def test_partial_source_range_does_not_cover_full_dialogue():
    p = plan(edit('E1', 's1', 0.0, 4.0))
    p['shots'][0].update(dialogue=[line(1.0, 3.0, '完整台詞')])
    # Cue covers only the middle of the source dialogue range -> not fully covered.
    cues = [cue('A1', 's1', 1.5, 2.5, 0.5, text='完整台詞')]
    result = timeline(p, cues)
    assert result['warnings'] == [{'code': 'DIALOGUE_UNCOVERED', 'shot_id': 's1', 'text': '完整台詞'}]


def test_cue_entity_id_must_match_dialogue_entity():
    p = plan(edit('E1', 's1', 0.0, 4.0))
    p['shots'][0].update(dialogue=[line(1.0, 2.0, '台詞', entity_id='c1')])
    wrong = [cue('A1', 's1', 1.0, 2.0, 1.0, text='台詞', entity_id='c2')]
    assert timeline(p, wrong)['warnings'] == [{'code': 'DIALOGUE_UNCOVERED', 'shot_id': 's1', 'text': '台詞'}]
    right = [cue('A1', 's1', 1.0, 2.0, 1.0, text='台詞', entity_id='c1')]
    assert timeline(p, right)['warnings'] == []


def test_sound_kind_does_not_cover_dialogue():
    p = plan(edit('E1', 's1', 0.0, 4.0))
    p['shots'][0].update(dialogue=[line(1.0, 2.0, '台詞')])
    cues = [cue('S1', 's1', 1.0, 2.0, 1.0, kind='sound', text='台詞')]
    assert timeline(p, cues)['warnings'] == [{'code': 'DIALOGUE_UNCOVERED', 'shot_id': 's1', 'text': '台詞'}]


def test_unedited_shot_dialogue_does_not_warn():
    p = {'shots': [shot('s1'), shot('s2')],
         'edit_plan': [edit('E1', 's1', 0.0, 2.0)]}
    p['shots'][1].update(dialogue=[line(0.5, 1.5, '未被剪到的鏡頭台詞')])
    result = timeline(p, [])
    assert result['warnings'] == []


# --- audio is explicit, never derived or truncated ---------------------------

def test_audio_not_derived_or_truncated():
    # The cue runs to 3.0 although the shot's image only shows 0-2; it is
    # returned exactly as placed (only timeline_out is computed).
    p = plan(edit('E1', 's1', 0.0, 2.0), edit('E2', 's2', 0.0, 2.0))
    p['shots'][0].update(dialogue=[line(1.0, 3.0, 'A 台詞')])
    cues = [cue('A1', 's1', 1.0, 3.0, 1.0, text='A 台詞')]
    result = timeline(p, cues)
    assert result['audio'][0]['source_in'] == 1.0
    assert result['audio'][0]['source_out'] == 3.0
    assert result['audio'][0]['timeline_out'] == 3.0
    # no derived cue for s2's (missing) dialogue appears
    assert len(result['audio']) == 1


# --- rejection cases ----------------------------------------------------------

def test_nonfinite_and_bool_timing_rejected():
    base = plan(edit('E1', 's1', 0.0, 2.0))
    with pytest.raises(ValueError):
        timeline({**base, 'shots': [shot('s1', duration=math.nan)]}, [])
    with pytest.raises(ValueError):
        timeline({**base, 'edit_plan': [edit('E1', 's1', 0.0, math.inf)]}, [])
    with pytest.raises(ValueError):
        # bool is a subclass of int: True must not be accepted as a number
        timeline({**base, 'edit_plan': [edit('E1', 's1', True, 2.0)]}, [])
    with pytest.raises(ValueError):
        timeline(plan(edit('E1', 's1', 0.0, 2.0)),
                 [cue('A1', 's1', 0.0, 1.0, math.nan)])


def test_negative_timeline_rejected():
    p = plan(edit('E1', 's1', 0.0, 2.0))
    with pytest.raises(ValueError):
        timeline(p, [cue('A1', 's1', 0.0, 1.0, -0.5)])


def test_duplicated_ids_rejected():
    p = plan(edit('E1', 's1', 0.0, 2.0), edit('E1', 's1', 2.0, 4.0))
    with pytest.raises(ValueError):
        timeline(p, [])
    p2 = plan(edit('E1', 's1', 0.0, 2.0))
    with pytest.raises(ValueError):
        timeline(p2, [cue('A1', 's1', 0.0, 1.0, 0.0), cue('A1', 's1', 0.0, 1.0, 1.0)])


def test_nonexistent_shot_rejected():
    p = {'shots': [], 'edit_plan': [edit('E1', 's1', 0.0, 2.0)]}
    with pytest.raises(ValueError):
        timeline(p, [])
    p2 = plan(edit('E1', 's1', 0.0, 2.0))
    with pytest.raises(ValueError):
        timeline(p2, [cue('A1', 'nope', 0.0, 1.0, 0.0)])


def test_out_of_source_range_rejected():
    p = plan(edit('E1', 's1', 0.0, 4.0))
    with pytest.raises(ValueError):
        timeline(p, [cue('A1', 's1', 3.0, 5.0, 3.0)])  # source_out > duration
    with pytest.raises(ValueError):
        timeline(p, [cue('A1', 's1', 2.0, 1.0, 0.0)])  # in >= out
    with pytest.raises(ValueError):
        timeline({**p, 'edit_plan': [edit('E1', 's1', 3.0, 5.0)]}, [])  # edit out > duration


def test_cue_beyond_full_timeline_rejected():
    p = plan(edit('E1', 's1', 0.0, 2.0))  # full timeline = 2.0
    with pytest.raises(ValueError):
        timeline(p, [cue('A1', 's1', 0.0, 1.0, 1.5)])  # ends at 2.5 > 2.0
    with pytest.raises(ValueError):
        timeline(p, [cue('A1', 's1', 0.0, 1.0, 2.5)])  # starts beyond end


def test_edit_range_not_within_source_rejected():
    p = plan(edit('E1', 's1', -0.5, 2.0))
    with pytest.raises(ValueError):
        timeline(p, [])
    p2 = plan(edit('E1', 's1', 2.0, 2.0))
    with pytest.raises(ValueError):
        timeline(p2, [])


def test_invalid_kind_rejected():
    p = plan(edit('E1', 's1', 0.0, 2.0))
    with pytest.raises(ValueError):
        timeline(p, [cue('A1', 's1', 0.0, 1.0, 0.0, kind='music')])


# --- purity -------------------------------------------------------------------

def test_inputs_never_mutated():
    p = plan(edit('E1', 's1', 0.0, 2.0))
    p['shots'][0].update(dialogue=[line(0.5, 1.5, '台詞')])
    cues = [cue('A1', 's1', 0.5, 1.5, 0.5, text='台詞')]
    p_before = copy.deepcopy(p)
    cues_before = copy.deepcopy(cues)
    timeline(p, cues)
    assert p == p_before
    assert cues == cues_before
    # output rows must not be the same objects as the inputs
    result = timeline(p, cues)
    assert result['visual'][0] is not p['edit_plan'][0]
    assert result['audio'][0] is not cues[0]


def test_empty_plan_and_cues():
    result = timeline({'shots': [], 'edit_plan': []}, [])
    assert result == {'duration': 0.0, 'visual': [], 'audio': [], 'warnings': []}
