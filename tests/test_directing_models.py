"""Tests for the pure directing data-contract module studio/directing_models.py.

Self-contained dict fixtures only — no media, database or network.
"""
import copy
import math

import pytest

from studio import directing_models as dm
from studio.directing_models import (
    validate_directing_review,
    validate_director_plan,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_intent():
    return {
        'audience_knowledge_before': '觀眾以為門後空無一人。',
        'audience_must_learn': '門後其實藏著一封舊信。',
        'emotional_target': '由平靜轉為驚疑。',
        'visual_priority': '先露門框，再露信。',
        'reveal_strategy': '由遠到近逐層揭露。',
        'coverage_strategy': '每個節點至少一鏡。',
    }


def make_plan():
    """A fully planned production with one scene, two beats, two shots, two edits."""
    return {
        'scenes': [
            {
                'id': 'sc1',
                'location_id': 'loc_hall',
                'director_plan': {
                    'beats': [
                        {'id': 'b1', 'event': '主角推門。', 'intent': make_intent()},
                        {'id': 'b2', 'event': '主角看見舊信。', 'intent': make_intent()},
                    ],
                    'reveal_order': ['b1', 'b2'],
                },
            }
        ],
        'shots': [
            {
                'id': 's1',
                'scene_id': 'sc1',
                'duration': 8.0,
                'generation_duration': 8.0,
                'entity_ids': ['c_hero', 'loc_hall'],
                'shot_purpose': '建立門後空間並鋪陳推門動作。',
                'direction': {
                    'beat_ids': ['b1', 'b2'],   # one shot, many beats, one purpose
                    'subject_ids': ['c_hero', 'loc_hall'],
                    'visual_carrier': '門框與信件。',
                    'readability': '主角面部清楚。',
                    'cut_in_reason': '從走廊入場。',
                    'cut_out_reason': '信件入畫即停。',
                    'next_shot_relationship': '接續信件特寫。',
                },
            },
            {
                'id': 's2',
                'scene_id': 'sc1',
                'duration': 6.0,
                'generation_duration': 6.0,
                'entity_ids': ['c_hero', 'loc_hall'],
                'shot_purpose': '特寫信件揭示真相。',
                'direction': {
                    'beat_ids': ['b2'],
                    'subject_ids': ['c_hero'],
                    'visual_carrier': '信件。',
                    'readability': '信紙文字清楚。',
                    'cut_in_reason': '信件入畫。',
                    'cut_out_reason': '主角反應完成。',
                    'next_shot_relationship': '收束到下一場。',
                },
            },
        ],
        'edit_plan': [
            {'id': 'e1', 'shot_id': 's1', 'planned_edit_in': 0.0, 'planned_edit_out': 4.0,
             'cut_in_reason': '開場。', 'cut_out_reason': '推門完成。', 'continuity_note': '保持光線。'},
            {'id': 'e2', 'shot_id': 's1', 'planned_edit_in': 4.0, 'planned_edit_out': 8.0,
             'cut_in_reason': '信件入畫。', 'cut_out_reason': '揭示完成。', 'continuity_note': '維持節奏。'},
            {'id': 'e3', 'shot_id': 's2', 'planned_edit_in': 1.0, 'planned_edit_out': 5.5,
             'cut_in_reason': '特寫開始。', 'cut_out_reason': '反應結束。', 'continuity_note': '聲音連續。'},
        ],
    }


def legacy_plan():
    """No directing data anywhere: every scene/shot/edit field missing."""
    return {
        'scenes': [
            {'id': 'sc1', 'location_id': 'loc_hall'},
            {'id': 'sc2', 'location_id': 'loc_room'},
        ],
        'shots': [
            {'id': 's1', 'scene_id': 'sc1', 'duration': 8.0, 'entity_ids': ['c_hero'], 'shot_purpose': ''},
            {'id': 's2', 'scene_id': 'sc2', 'duration': 6.0, 'entity_ids': ['c_hero'], 'shot_purpose': ''},
        ],
        'edit_plan': [],
    }


def mixed_plan():
    """One planned scene + one legacy scene in the same plan (chapter compatibility)."""
    plan = make_plan()
    plan['scenes'].append({'id': 'sc2', 'location_id': 'loc_room'})
    plan['shots'].append({
        'id': 's3', 'scene_id': 'sc2', 'duration': 5.0, 'entity_ids': ['c_hero'], 'shot_purpose': '',
    })
    return plan


def make_review(plan=None):
    plan = plan or make_plan()
    return {
        'verdict': 'pass',
        'summary': '兩節點皆由鏡頭清楚承載。',
        'coverage': [
            {
                'beat_id': 'b1',
                'scene_id': 'sc1',
                'shot_ids': ['s1'],
                'verdict': 'pass',
                'required_communication': '觀眾須知門後有信。',
                'evidence': '主角推門。',
                'reason': '鏡頭 s1 承載 b1。',
                'recommendation': '維持。',
            },
            {
                'beat_id': 'b2',
                'scene_id': 'sc1',
                'shot_ids': ['s1', 's2'],
                'verdict': 'pass',
                'required_communication': '觀眾須見舊信。',
                'evidence': '主角看見舊信。',
                'reason': '鏡頭 s1、s2 承載 b2。',
                'recommendation': '維持。',
            },
        ],
        'issues': [],
    }


# ---------------------------------------------------------------------------
# Plan validation: good / multi-beat single-purpose / repeated edit ranges
# ---------------------------------------------------------------------------

def test_good_plan_validates():
    validate_director_plan(make_plan())


def test_multi_beat_single_purpose_shot_allowed():
    """One shot serving two beats under a single purpose must pass (no overload inference)."""
    validate_director_plan(make_plan())
    # shot s1 carries both b1 and b2 yet has exactly one shot_purpose — accepted.
    assert make_plan()['shots'][0]['shot_purpose'] == '建立門後空間並鋪陳推門動作。'


def test_repeated_source_edit_ranges_allowed():
    """Multiple edit entries may reference the same shot; repeated ranges are fine."""
    plan = make_plan()
    plan['edit_plan'] = [
        {'id': 'e1', 'shot_id': 's1', 'planned_edit_in': 0.0, 'planned_edit_out': 2.0,
         'cut_in_reason': 'a', 'cut_out_reason': 'b', 'continuity_note': 'c'},
        {'id': 'e2', 'shot_id': 's1', 'planned_edit_in': 2.0, 'planned_edit_out': 4.0,
         'cut_in_reason': 'a', 'cut_out_reason': 'b', 'continuity_note': 'c'},
        {'id': 'e3', 'shot_id': 's1', 'planned_edit_in': 4.0, 'planned_edit_out': 8.0,
         'cut_in_reason': 'a', 'cut_out_reason': 'b', 'continuity_note': 'c'},
        {'id': 'e4', 'shot_id': 's2', 'planned_edit_in': 0.0, 'planned_edit_out': 6.0,
         'cut_in_reason': 'a', 'cut_out_reason': 'b', 'continuity_note': 'c'},
    ]
    validate_director_plan(plan)  # three entries on s1, one on s2 — no forced new generation


# ---------------------------------------------------------------------------
# Legacy & mixed legacy
# ---------------------------------------------------------------------------

def test_legacy_plan_all_missing_allowed():
    validate_director_plan(legacy_plan())


def test_mixed_legacy_allowed():
    validate_director_plan(mixed_plan())


def test_legacy_complete_mode_fails_missing_plan():
    plan = legacy_plan()
    with pytest.raises(ValueError, match='director_plan'):
        validate_director_plan(plan, require_complete=True)


def test_mixed_complete_mode_fails_missing_plan_on_legacy_scene():
    plan = mixed_plan()
    with pytest.raises(ValueError, match='director_plan'):
        validate_director_plan(plan, require_complete=True)


# ---------------------------------------------------------------------------
# Partial data in a planned scene must fail
# ---------------------------------------------------------------------------

def test_planned_scene_shot_missing_purpose_fails():
    plan = make_plan()
    del plan['shots'][1]['shot_purpose']
    with pytest.raises(ValueError, match='shot_purpose'):
        validate_director_plan(plan)


def test_planned_scene_shot_missing_direction_fails():
    plan = make_plan()
    del plan['shots'][1]['direction']
    with pytest.raises(ValueError, match='direction'):
        validate_director_plan(plan)


def test_planned_scene_beat_missing_from_shots_fails():
    plan = make_plan()
    # remove b2 from both shots so no shot covers it
    plan['shots'][0]['direction']['beat_ids'] = ['b1']
    plan['shots'][1]['direction']['beat_ids'] = ['b1']
    with pytest.raises(ValueError, match='沒有被任何鏡頭涵蓋'):
        validate_director_plan(plan)


# ---------------------------------------------------------------------------
# Wrong IDs
# ---------------------------------------------------------------------------

def test_shot_references_unknown_beat_fails():
    plan = make_plan()
    plan['shots'][0]['direction']['beat_ids'] = ['b1', 'bX']
    with pytest.raises(ValueError, match='不屬於場景'):
        validate_director_plan(plan)


def test_shot_references_unknown_subject_fails():
    plan = make_plan()
    plan['shots'][0]['direction']['subject_ids'] = ['c_ghost']
    with pytest.raises(ValueError, match='主體'):
        validate_director_plan(plan)


def test_reveal_order_not_permutation_fails():
    plan = make_plan()
    plan['scenes'][0]['director_plan']['reveal_order'] = ['b1']
    with pytest.raises(ValueError, match='揭示順序'):
        validate_director_plan(plan)


def test_reveal_order_extra_id_fails():
    plan = make_plan()
    plan['scenes'][0]['director_plan']['reveal_order'] = ['b1', 'b2', 'b3']
    with pytest.raises(ValueError, match='揭示順序'):
        validate_director_plan(plan)


def test_duplicate_beat_ids_fails():
    plan = make_plan()
    plan['scenes'][0]['director_plan']['beats'][1]['id'] = 'b1'
    with pytest.raises(ValueError, match='唯一'):
        validate_director_plan(plan)


def test_edit_references_unknown_shot_fails():
    plan = make_plan()
    plan['edit_plan'][0]['shot_id'] = 'sX'
    with pytest.raises(ValueError, match='不存在的鏡頭'):
        validate_director_plan(plan)


# ---------------------------------------------------------------------------
# Bad / NaN edit ranges and duration mismatch
# ---------------------------------------------------------------------------

def test_edit_out_not_greater_than_in_fails():
    plan = make_plan()
    plan['edit_plan'][0]['planned_edit_in'] = 4.0
    plan['edit_plan'][0]['planned_edit_out'] = 4.0
    with pytest.raises(ValueError, match='範圍'):
        validate_director_plan(plan)


def test_edit_out_beyond_duration_fails():
    plan = make_plan()
    plan['edit_plan'][0]['planned_edit_out'] = 9.0  # > duration 8.0
    with pytest.raises(ValueError, match='範圍'):
        validate_director_plan(plan)


def test_edit_negative_in_fails():
    plan = make_plan()
    plan['edit_plan'][0]['planned_edit_in'] = -1.0
    with pytest.raises(ValueError):
        validate_director_plan(plan)


def test_edit_nan_range_fails():
    plan = make_plan()
    plan['edit_plan'][0]['planned_edit_in'] = math.nan
    with pytest.raises(ValueError):
        validate_director_plan(plan)


def test_edit_infinite_range_fails():
    plan = make_plan()
    plan['edit_plan'][0]['planned_edit_out'] = math.inf
    with pytest.raises(ValueError):
        validate_director_plan(plan)


def test_generation_duration_mismatch_fails():
    plan = make_plan()
    plan['shots'][0]['generation_duration'] = 7.0  # != duration 8.0
    with pytest.raises(ValueError, match='生成時長'):
        validate_director_plan(plan)


def test_duplicate_edit_ids_fails():
    plan = make_plan()
    plan['edit_plan'][1]['id'] = plan['edit_plan'][0]['id']
    with pytest.raises(ValueError, match='重複'):
        validate_director_plan(plan)


# ---------------------------------------------------------------------------
# Complete mode
# ---------------------------------------------------------------------------

def test_complete_mode_passes_for_full_plan():
    validate_director_plan(make_plan(), require_complete=True)


def test_complete_mode_requires_generation_duration():
    plan = make_plan()
    del plan['shots'][0]['generation_duration']
    with pytest.raises(ValueError, match='generation_duration'):
        validate_director_plan(plan, require_complete=True)


def test_complete_mode_requires_edit_covering_every_shot():
    plan = make_plan()
    # drop the edit for s2 so s2 is uncovered
    plan['edit_plan'] = [
        {'id': 'e1', 'shot_id': 's1', 'planned_edit_in': 0.0, 'planned_edit_out': 8.0,
         'cut_in_reason': 'a', 'cut_out_reason': 'b', 'continuity_note': 'c'},
    ]
    with pytest.raises(ValueError, match='缺少編輯決定'):
        validate_director_plan(plan, require_complete=True)


def test_planned_scene_shot_requires_edit_even_mixed():
    plan = mixed_plan()
    # remove the edit covering s1 (planned scene) entirely
    plan['edit_plan'] = [
        {'id': 'e3', 'shot_id': 's2', 'planned_edit_in': 1.0, 'planned_edit_out': 5.5,
         'cut_in_reason': 'a', 'cut_out_reason': 'b', 'continuity_note': 'c'},
    ]
    with pytest.raises(ValueError, match='缺少編輯決定'):
        validate_director_plan(plan)


def test_legacy_shot_without_edit_ok_in_mixed_non_complete():
    plan = mixed_plan()
    # cover both planned-scene shots (s1, s2); legacy s3 (sc2) has none and that's fine
    plan['edit_plan'] = [
        {'id': 'e1', 'shot_id': 's1', 'planned_edit_in': 0.0, 'planned_edit_out': 8.0,
         'cut_in_reason': 'a', 'cut_out_reason': 'b', 'continuity_note': 'c'},
        {'id': 'e2', 'shot_id': 's2', 'planned_edit_in': 0.0, 'planned_edit_out': 6.0,
         'cut_in_reason': 'a', 'cut_out_reason': 'b', 'continuity_note': 'c'},
    ]
    validate_director_plan(plan)


# ---------------------------------------------------------------------------
# Review validation
# ---------------------------------------------------------------------------

def test_good_review_normalizes():
    normalized = validate_directing_review(make_review(), make_plan())
    assert normalized['verdict'] == 'pass'
    assert len(normalized['coverage']) == 2
    assert {c['beat_id'] for c in normalized['coverage']} == {'b1', 'b2'}


def test_review_missing_beat_fails():
    review = make_review()
    review['coverage'] = review['coverage'][:1]  # drop b2
    with pytest.raises(ValueError, match='缺少'):
        validate_directing_review(review, make_plan())


def test_review_duplicate_coverage_fails():
    review = make_review()
    review['coverage'].append(copy.deepcopy(review['coverage'][0]))
    with pytest.raises(ValueError, match='重複'):
        validate_directing_review(review, make_plan())


def test_review_fabricated_evidence_fails():
    review = make_review()
    review['coverage'][0]['evidence'] = '一段從未出現在方案中的話。'
    with pytest.raises(ValueError, match='逐字摘錄'):
        validate_directing_review(review, make_plan())


def test_review_evidence_from_linked_shot_ok():
    """Evidence can be an excerpt of a linked shot's serialized structure."""
    review = make_review()
    review['coverage'][0]['evidence'] = '建立門後空間並鋪陳推門動作。'  # from shot s1
    normalized = validate_directing_review(review, make_plan())
    assert normalized['coverage'][0]['evidence'] == '建立門後空間並鋪陳推門動作。'


def test_review_pass_with_issue_fails():
    review = make_review()
    review['issues'] = [
        {'code': 'CONTINUITY', 'shot_ids': ['s1'], 'beat_ids': ['b1'],
         'evidence': '保持光線。', 'reason': '光線跳動。', 'recommendation': '修正。'},
    ]
    with pytest.raises(ValueError, match='不能包含任何問題'):
        validate_directing_review(review, make_plan())


def test_review_pass_with_nonpass_coverage_fails():
    review = make_review()
    review['coverage'][1]['verdict'] = 'revise'
    with pytest.raises(ValueError, match='每個節點也必須為 pass'):
        validate_directing_review(review, make_plan())


def test_review_nonpass_verdict_with_issue_ok():
    review = make_review()
    review['verdict'] = 'revise'
    review['issues'] = [
        {'code': 'UNREADABLE_CARRIER', 'shot_ids': ['s2'], 'beat_ids': ['b2'],
         'evidence': '信紙文字清楚。', 'reason': '文字偏小。', 'recommendation': '拉近。'},
    ]
    normalized = validate_directing_review(review, make_plan())
    assert normalized['verdict'] == 'revise' and len(normalized['issues']) == 1


def test_review_shot_link_not_carrying_beat_fails():
    review = make_review()
    # s2 carries only b2, not b1 — linking b1 coverage to s2 is invalid
    review['coverage'][0]['shot_ids'] = ['s2']
    with pytest.raises(ValueError, match='並未承載'):
        validate_directing_review(review, make_plan())


def test_review_unknown_shot_link_fails():
    review = make_review()
    review['coverage'][0]['shot_ids'] = ['sX']
    with pytest.raises(ValueError, match='不存在的鏡頭'):
        validate_directing_review(review, make_plan())


def test_review_issue_unknown_beat_fails():
    review = make_review()
    review['verdict'] = 'revise'
    review['issues'] = [
        {'code': 'OTHER', 'shot_ids': [], 'beat_ids': ['bX'],
         'evidence': '主角推門。', 'reason': 'r', 'recommendation': 'c'},
    ]
    with pytest.raises(ValueError, match='不存在的節點'):
        validate_directing_review(review, make_plan())


def test_review_beat_id_local_to_any_scene_ok():
    """Issue beat ids are checked against any scene's beats (local ids)."""
    plan = make_plan()
    plan['scenes'].append({
        'id': 'sc2',
        'location_id': 'loc_room',
        'director_plan': {
            'beats': [{'id': 'c1', 'event': '另一場的事件。', 'intent': make_intent()}],
            'reveal_order': ['c1'],
        },
    })
    plan['shots'].append({
        'id': 's3', 'scene_id': 'sc2', 'duration': 5.0, 'generation_duration': 5.0,
        'entity_ids': ['c_hero', 'loc_room'], 'shot_purpose': '另一場。',
        'direction': {
            'beat_ids': ['c1'], 'subject_ids': ['c_hero'],
            'visual_carrier': 'v', 'readability': 'r',
            'cut_in_reason': 'a', 'cut_out_reason': 'b', 'next_shot_relationship': 'n',
        },
    })
    review = make_review(plan)
    review['verdict'] = 'revise'
    review['coverage'].append({
        'beat_id': 'c1', 'scene_id': 'sc2', 'shot_ids': ['s3'], 'verdict': 'pass',
        'required_communication': 'rc', 'evidence': '另一場的事件。', 'reason': 'r', 'recommendation': 'c',
    })
    review['issues'] = [
        {'code': 'OTHER', 'shot_ids': ['s3'], 'beat_ids': ['c1'],
         'evidence': '另一場的事件。', 'reason': 'r', 'recommendation': 'c'},
    ]
    normalized = validate_directing_review(review, plan)
    assert {c['beat_id'] for c in normalized['coverage']} == {'b1', 'b2', 'c1'}


# ---------------------------------------------------------------------------
# Model-level strictness
# ---------------------------------------------------------------------------

def test_models_forbid_extra_fields():
    with pytest.raises(ValueError):
        dm.DramaticBeat(id='b1', event='e', intent=make_intent(), extra='x')


def test_nonblank_strings_reject_whitespace():
    with pytest.raises(ValueError):
        dm.DramaticBeat(id='  ', event='e', intent=make_intent())


def test_edit_decision_bounds_enforced():
    with pytest.raises(ValueError):
        dm.EditDecision(id='e1', shot_id='s1', planned_edit_in=4.0, planned_edit_out=4.0,
                        cut_in_reason='a', cut_out_reason='b', continuity_note='c')
