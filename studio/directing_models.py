"""Pure data contracts for the Scene -> dramatic beats -> shots -> edit ranges pipeline.

These models are self-contained (own ``Strict`` base, no ``studio.models`` import) so the
directing layer can be validated and tested independently of the storyboard Production
schema. ``validate_director_plan`` and ``validate_directing_review`` are the two entry
points; both raise ``ValueError`` with Traditional Chinese messages on failure.
"""
import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

    @field_validator('*', mode='after')
    @classmethod
    def _reject_blank(cls, value):
        """Reject whitespace-only strings (``min_length=1`` alone allows ``'  '``)."""
        if isinstance(value, str) and not value.strip():
            raise ValueError('must not be blank')
        return value


Nonblank = Field(min_length=1)
"""A nonblank string: pydantic rejects ``''`` via min_length; whitespace-only values are
rejected by the validators (min_length alone does not reject ``'  '``)."""


class DirectorialIntent(Strict):
    audience_knowledge_before: str = Nonblank
    audience_must_learn: str = Nonblank
    emotional_target: str = Nonblank
    visual_priority: str = Nonblank
    reveal_strategy: str = Nonblank
    coverage_strategy: str = Nonblank


class DramaticBeat(Strict):
    id: str = Nonblank
    event: str = Nonblank
    intent: DirectorialIntent


class SceneDirectorPlan(Strict):
    beats: list[DramaticBeat] = Field(min_length=1)
    reveal_order: list[str]
    """Exactly a permutation of ``beats[].id`` — the order the audience meets each beat."""


class ShotDirection(Strict):
    beat_ids: list[str] = Field(min_length=1)
    subject_ids: list[str] = Field(min_length=1)
    visual_carrier: str = Nonblank
    readability: str = Nonblank
    cut_in_reason: str = Nonblank
    cut_out_reason: str = Nonblank
    next_shot_relationship: str = Nonblank

    @field_validator('beat_ids', 'subject_ids')
    @classmethod
    def unique_ids(cls, values):
        if len(values) != len(set(values)) or any(_blank(v) for v in values):
            raise ValueError('節拍及主體引用不可空白或重複')
        return values


class EditDecision(Strict):
    id: str = Nonblank
    shot_id: str = Nonblank
    planned_edit_in: float = Field(ge=0)
    planned_edit_out: float = Field(gt=0)
    cut_in_reason: str = Nonblank
    cut_out_reason: str = Nonblank
    continuity_note: str = Nonblank

    @model_validator(mode='after')
    def _range(self):
        # ``in < out`` (gt=0 alone allows in==out); also guards against NaN.
        if not (self.planned_edit_in < self.planned_edit_out):
            raise ValueError('planned_edit_in must be less than planned_edit_out')
        return self


class BeatCoverage(Strict):
    beat_id: str = Nonblank
    scene_id: str = Nonblank
    shot_ids: list[str] = Field(min_length=1)
    verdict: Literal['pass', 'revise', 'uncertain']
    required_communication: str = Nonblank
    evidence: str = Nonblank
    reason: str = Nonblank
    recommendation: str = Nonblank


class DirectingIssue(Strict):
    code: Literal['SHOT_OVERLOADED', 'REVEAL_ORDER', 'UNREADABLE_CARRIER',
                  'CONTINUITY', 'EDIT_RANGE', 'OTHER']
    shot_ids: list[str] = Field(default_factory=list)
    beat_ids: list[str] = Field(default_factory=list)
    evidence: str = Nonblank
    reason: str = Nonblank
    recommendation: str = Nonblank


class DirectingReview(Strict):
    verdict: Literal['pass', 'revise', 'uncertain']
    summary: str = Nonblank
    coverage: list[BeatCoverage] = Field(default_factory=list)
    issues: list[DirectingIssue] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blank(value) -> bool:
    return not isinstance(value, str) or not value.strip()


def _is_planned_scene(scene: dict) -> bool:
    return isinstance(scene.get('director_plan'), dict)


def _scene_shots(shot_by_id: dict, scene_id: str) -> list[dict]:
    return [s for s in shot_by_id.values() if s.get('scene_id') == scene_id]


def _finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _finite(value) -> bool:
    return _finite_number(value)


def _validate_scene_plan(scene: dict, scene_plan: dict, shots: list[dict], shot_by_id: dict):
    """Validate one planned scene's beats/reveal order and its shots. Returns nothing."""
    scene_id = scene['id']

    plan = SceneDirectorPlan.model_validate(scene_plan)
    beats = {b.id: b for b in plan.beats}

    # 1) unique beat IDs within the scene
    if len(beats) != len(plan.beats):
        raise ValueError(f'場景 {scene_id} 的戲劇節點 ID 必須唯一')

    # 2) reveal_order is exactly a permutation of beat ids
    if sorted(plan.reveal_order) != sorted(beats.keys()):
        raise ValueError(f'場景 {scene_id} 的揭示順序必須剛好重現所有戲劇節點 ID')

    # 3) every shot in the scene must carry a single nonblank purpose + valid direction
    for shot in shots:
        shot_id = shot['id']
        if _blank(shot.get('shot_purpose', '')):
            raise ValueError(f'鏡頭 {shot_id} 缺少單一用途說明 shot_purpose')
        direction = shot.get('direction')
        if not isinstance(direction, dict):
            raise ValueError(f'鏡頭 {shot_id} 缺少有效的方向 direction')
        try:
            sd = ShotDirection.model_validate(direction)
        except Exception:
            raise ValueError(f'鏡頭 {shot_id} 的方向 direction 不合法')
        # beat ids must belong to this scene
        unknown_beats = [b for b in sd.beat_ids if b not in beats]
        if unknown_beats:
            raise ValueError(f'鏡頭 {shot_id} 引用了不屬於場景 {scene_id} 的節點')
        # subject ids must be present in shot.entity_ids or scene.location_id
        allowed = set(shot.get('entity_ids') or []) | {scene.get('location_id')}
        unknown_subjects = [s for s in sd.subject_ids if s not in allowed]
        if unknown_subjects:
            raise ValueError(f'鏡頭 {shot_id} 的主體不存在於鏡頭或場景中')
        shot_by_id[shot_id] = shot

    # 4) all scene beats must be covered by at least one shot
    covered = set()
    for shot in shots:
        if isinstance(shot.get('direction'), dict):
            covered.update(shot['direction'].get('beat_ids') or [])
    missing = [b for b in beats.keys() if b not in covered]
    if missing:
        raise ValueError(f'場景 {scene_id} 的節點沒有被任何鏡頭涵蓋：{", ".join(missing)}')


def _validate_edits(edit_plan, shot_by_id, require_complete, planned_scene_ids):
    """Validate the production edit_plan. Returns the set of shot ids referenced."""
    edit_ids = set()
    covered_shots = set()

    for entry in edit_plan:
        if not isinstance(entry, dict):
            raise ValueError('編輯清單必須為物件清單')
        try:
            e = EditDecision.model_validate(entry)
        except ValueError as exc:
            raise ValueError('剪接決定或時間範圍不合法') from exc
        if e.id in edit_ids:
            raise ValueError(f'編輯決定 ID 重複：{e.id}')
        edit_ids.add(e.id)
        if e.shot_id not in shot_by_id:
            raise ValueError(f'編輯決定 {e.id} 引用了不存在的鏡頭 {e.shot_id}')
        shot = shot_by_id[e.shot_id]
        # bounds 0 <= in < out <= shot.duration with finite numbers
        duration = shot.get('duration')
        if not _finite(duration):
            raise ValueError(f'鏡頭 {e.shot_id} 缺少有效的時長')
        if not (0 <= e.planned_edit_in < e.planned_edit_out <= duration):
            raise ValueError(f'編輯決定 {e.id} 的範圍不在 0<=in<out<=時長 內')
        # generation_duration must equal duration when supplied
        gen = shot.get('generation_duration')
        if gen is not None:
            if not _finite(gen):
                raise ValueError(f'鏡頭 {e.shot_id} 的生成時長必須為有限數字')
            if gen != duration:
                raise ValueError(f'鏡頭 {e.shot_id} 的生成時長必須等於時長')
        covered_shots.add(e.shot_id)

    # Complete mode: every shot must have an edit entry
    if require_complete:
        for shot in shot_by_id.values():
            if shot['id'] not in covered_shots:
                raise ValueError(f'完整模式下鏡頭 {shot["id"]} 缺少編輯決定')
    # Planned-scene shots require edit entries even in mixed legacy mode
    for shot in shot_by_id.values():
        if shot.get('scene_id') in planned_scene_ids and shot['id'] not in covered_shots:
            raise ValueError(f'已規劃場景 {shot["scene_id"]} 的鏡頭 {shot["id"]} 缺少編輯決定')

    return covered_shots


def validate_director_plan(plan: dict, require_complete: bool = False) -> None:
    """Validate a Production-style dict (or model) for the directing pipeline.

    ``require_complete=False`` allows legacy/mixed scenes (chapter compatibility); any
    partial data in a planned scene still fails. ``require_complete=True`` additionally
    requires scene plans for every scene, generation_duration on every shot, and edit
    entries covering every shot. Raises ``ValueError`` with Traditional Chinese messages.
    """
    if isinstance(plan, dict):
        plan_dict = plan
    else:
        dump = getattr(plan, 'model_dump', None)
        plan_dict = dump() if callable(dump) else dict(vars(plan))

    scenes = plan_dict.get('scenes') or []
    shots = plan_dict.get('shots') or []
    edit_plan = plan_dict.get('edit_plan') or []

    shot_by_id = {s['id']: s for s in shots}
    if len(shot_by_id) != len(shots):
        raise ValueError('鏡頭 ID 必須唯一')

    planned_scene_ids = set()
    for scene in scenes:
        if isinstance(scene, dict):
            scene_id = scene['id']
            if _is_planned_scene(scene):
                planned_scene_ids.add(scene_id)
                _validate_scene_plan(scene, scene['director_plan'],
                                     _scene_shots(shot_by_id, scene_id), shot_by_id)

    for shot in shots:
        gen=shot.get('generation_duration')
        if gen is not None and (not _finite(gen) or gen != shot.get('duration')):
            raise ValueError('生成時長必須是有限數字並等於來源時長')
        if shot.get('scene_id') not in planned_scene_ids and (shot.get('direction') is not None or shot.get('shot_purpose')):
            raise ValueError('鏡頭已有導演資料，但所屬場景缺少導演方案')

    # Complete mode: every scene must be planned, every shot must have generation_duration
    if require_complete:
        for scene in scenes:
            if isinstance(scene, dict) and not _is_planned_scene(scene):
                raise ValueError(f'完整模式下場景 {scene["id"]} 缺少導演方案 director_plan')
        for shot in shots:
            if shot.get('generation_duration') is None:
                raise ValueError(f'完整模式下鏡頭 {shot["id"]} 缺少生成時長 generation_duration')

    _validate_edits(edit_plan, shot_by_id, require_complete, planned_scene_ids)


def _planned_beats(plan: dict) -> list[tuple[str, str]]:
    """Return (scene_id, beat_id) for every planned scene in the plan."""
    out = []
    for scene in plan.get('scenes') or []:
        if isinstance(scene, dict) and _is_planned_scene(scene):
            scene_id = scene['id']
            for b in (scene['director_plan'].get('beats') or []):
                out.append((scene_id, b['id']))
    return out





def has_evidence(material, excerpt):
    """One literal source span, including real newlines/quotes; no joined excerpts."""
    def in_value(value):
        if isinstance(value,str): return excerpt in value
        if isinstance(value,dict): return any(in_value(v) for v in value.values())
        if isinstance(value,list): return any(in_value(v) for v in value)
        return False
    return bool(excerpt) and (in_value(material) or excerpt in json.dumps(material,ensure_ascii=False))


def validate_directing_review(review: dict, plan: dict, *, expected_coverage=None) -> dict:
    """Validate and normalize a ``DirectingReview`` against the plan.

    Checks: exactly one coverage per planned scene+beat, no duplicates, valid local shot
    links that carry the beat, valid issue shot/beat ids (beat ids may be local to any
    scene), evidence is a literal excerpt of the serialized scene+linked-shot structure,
    and a ``pass`` verdict cannot contain nonpass coverage or any issues.
    Returns the normalized review dict. Raises ``ValueError`` (Traditional Chinese).
    """
    if isinstance(review, dict):
        review_dict = review
    else:
        dump = getattr(review, 'model_dump', None)
        review_dict = dump() if callable(dump) else dict(vars(review))

    if isinstance(plan, dict):
        plan_dict = plan
    else:
        dump = getattr(plan, 'model_dump', None)
        plan_dict = dump() if callable(dump) else dict(vars(plan))

    try:
        rv = DirectingReview.model_validate(review_dict)
    except Exception:
        raise ValueError('導演覆核結構不合法')

    scenes = plan_dict.get('scenes') or []
    shots = plan_dict.get('shots') or []
    shot_by_id = {s['id']: s for s in shots}

    planned = _planned_beats(plan_dict)
    planned_keys = set(planned) if expected_coverage is None else set(expected_coverage)
    if not planned_keys <= set(planned):
        raise ValueError('審查範圍引用了未規劃節拍')

    # All shot ids that carry each beat, per scene (for link validation).
    shot_beats_by_scene: dict[str, dict[str, set[str]]] = {}
    for scene in scenes:
        if not (isinstance(scene, dict) and _is_planned_scene(scene)):
            continue
        sid = scene['id']
        mapping = {}
        for shot in shot_by_id.values():
            if shot.get('scene_id') != sid:
                continue
            direction = shot.get('direction')
            if isinstance(direction, dict):
                for b in direction.get('beat_ids') or []:
                    mapping.setdefault(b, set()).add(shot['id'])
        shot_beats_by_scene[sid] = mapping

    seen_keys = set()
    for cov in rv.coverage:
        key = (cov.scene_id, cov.beat_id)
        if key not in planned_keys:
            raise ValueError(f'覆核涵蓋了未規劃的節點 {cov.beat_id}')
        if key in seen_keys:
            raise ValueError(f'節點 {cov.beat_id} 的覆核重複')
        seen_keys.add(key)
        if len(cov.shot_ids)!=len(set(cov.shot_ids)):
            raise ValueError('覆核的鏡頭引用不可重複')
        # valid local shot links carrying the beat
        carrying = shot_beats_by_scene.get(cov.scene_id, {}).get(cov.beat_id, set())
        for shot_id in cov.shot_ids:
            if shot_id not in shot_by_id:
                raise ValueError(f'覆核引用了不存在的鏡頭 {shot_id}')
            if shot_id not in carrying:
                raise ValueError(f'覆核的鏡頭 {shot_id} 並未承載節點 {cov.beat_id}')

    if seen_keys != planned_keys:
        missing = [f'{sid}/{bid}' for sid, bid in planned if (sid, bid) not in seen_keys]
        raise ValueError('覆核必須涵蓋每個已規劃節點；缺少：' + ', '.join(missing))

    # issue shot/beat ids valid (beat ids may be local to any scene)
    all_beats = {bid for _, bid in planned}
    for issue in rv.issues:
        for shot_id in issue.shot_ids:
            if shot_id not in shot_by_id:
                raise ValueError(f'問題引用了不存在的鏡頭 {shot_id}')
        for beat_id in issue.beat_ids:
            if beat_id not in all_beats:
                raise ValueError(f'問題引用了不存在的節點 {beat_id}')
        linked=[shot_by_id[sid] for sid in issue.shot_ids]
        scene_ids={s['scene_id'] for s in linked}
        relevant=[s for s in scenes if s['id'] in scene_ids or any(b['id'] in issue.beat_ids for b in (s.get('director_plan') or {}).get('beats',[]))]
        material={'scenes':relevant,'shots':linked,'edit_plan':[e for e in plan_dict.get('edit_plan',[]) if e['shot_id'] in issue.shot_ids]}
        if not issue.shot_ids and not issue.beat_ids:material=plan_dict
        if not has_evidence(material,issue.evidence):
            raise ValueError('問題證據必須引用相關鏡頭、節拍或剪接資料的逐字摘錄')

    # evidence must be a literal excerpt of the serialized scene+linked-shot structure
    for cov in rv.coverage:
        scene = next((s for s in scenes if s.get('id') == cov.scene_id), None)
        if scene is None:
            raise ValueError(f'覆核引用了不存在的場景 {cov.scene_id}')
        linked = [shot_by_id[sid] for sid in cov.shot_ids if sid in shot_by_id]
        if not has_evidence({'scene':scene,'shots':linked},cov.evidence):
            raise ValueError(f'節點 {cov.beat_id} 的證據不是場景與連結鏡頭的逐字摘錄')

    # pass cannot contain nonpass coverage or any issues
    if rv.verdict == 'pass':
        if any(c.verdict != 'pass' for c in rv.coverage):
            raise ValueError('覆核結論為 pass 時，每個節點也必須為 pass')
        if rv.issues:
            raise ValueError('覆核結論為 pass 時不能包含任何問題')

    return rv.model_dump()
