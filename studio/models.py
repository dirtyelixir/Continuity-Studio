from typing import Literal
from pydantic import BaseModel, Field, model_validator, model_serializer, ConfigDict
from .directing_models import SceneDirectorPlan, ShotDirection, EditDecision, validate_director_plan
from .shot_state_models import ShotState

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Entity(Strict):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    kind: Literal['character', 'crowd', 'voice', 'location', 'prop']
    name: str
    description: str
    facts: list[str]
    scope: Literal['auto','public','scene'] = 'auto'

class Scene(Strict):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    title: str
    location_id: str
    time_of_day: str
    summary: str
    director_plan: SceneDirectorPlan | None = None

class State(Strict):
    entity_id: str
    key: str
    value: str

class Beat(Strict):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    action: str

class Dialogue(Strict):
    entity_id: str
    text: str
    language: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    delivery: str

class Frame(Strict):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    moment: Literal['start','end','key']
    description: str
    source_time: float | None = Field(default=None,ge=0,allow_inf_nan=False,
        description='Required inside the Shot for intermediate (key) frames. Omit or use null for start/end frames; their times belong to the Shot endpoints.')
    state: list[State] | None = Field(default=None,
        description='Required for intermediate (key) frames. Omit or use null for start/end frames, which use the Shot start_state/end_state.')

    @model_validator(mode='after')
    def exact_moment(self):
        if self.moment=='key' and (self.source_time is None or self.state is None):
            raise ValueError('Intermediate storyboard frames require source_time and explicit frozen state')
        if self.moment!='key' and (self.source_time is not None or self.state is not None):
            raise ValueError('Endpoint frames use their source Shot endpoint states')
        return self

    @model_serializer(mode='wrap')
    def compact(self, handler):
        # Preserve legacy frame JSON/dependency hashes when optional fields are absent.
        return {k:v for k,v in handler(self).items() if v is not None}

class Shot(Strict):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    scene_id: str
    title: str
    duration: float = Field(ge=4,le=15)
    generation_duration: float | None = Field(default=None,ge=4,le=15)
    shot_purpose: str = ''
    direction: ShotDirection | None = None
    entity_ids: list[str]
    framing: str
    angle: str
    camera: str
    blocking: str
    action: str
    expression: str
    start_state: list[State]
    end_state: list[State]
    transition_note: str
    beats: list[Beat]
    dialogue: list[Dialogue]
    keyframes: list[Frame] = Field(min_length=1,max_length=8)
    soundscape: str
    music: str
    canonical_state: ShotState | None = None

    @model_validator(mode='before')
    @classmethod
    def remove_redundant_endpoint_frames(cls, data):
        # Only raw dict Shot input: copy, never mutate the caller's structure.
        if not isinstance(data,dict):return data
        raw_start=data.get('start_state');raw_end=data.get('end_state')
        if not isinstance(raw_start,list) or not isinstance(raw_end,list) or not isinstance(data.get('keyframes'),list):return data
        data=data.copy();data['keyframes']=list(data['keyframes'])
        for i,frame in enumerate(data['keyframes']):
            if not isinstance(frame,dict) or frame.get('moment') not in ('start','end'):continue
            frame=frame.copy()
            reference=raw_start if frame.get('moment')=='start' else raw_end
            time=0 if frame.get('moment')=='start' else data.get('duration')
            value=frame.get('source_time')
            # Do not coerce strings/bools or discard mismatches: Frame rejects them.
            if (type(value) in (int,float) and type(time) in (int,float) and value==time):
                frame.pop('source_time')
            state=frame.get('state')
            if isinstance(state,list) and state==reference:
                frame.pop('state')
            data['keyframes'][i]=frame
        return data

    @model_serializer(mode='wrap')
    def compact_state(self, handler):
        value = handler(self)
        if value.get('canonical_state') is None:
            value.pop('canonical_state', None)
        return value

class StoryChapter(Strict):
    id: str
    title: str
    story: str
    screenplay: str
    scene_ids: list[str] = Field(min_length=1)

class Production(Strict):
    title: str
    logline: str
    story: str
    screenplay: str
    style: str
    canon: list[Entity] = Field(min_length=1)
    scenes: list[Scene] = Field(min_length=1)
    shots: list[Shot] = Field(min_length=1)
    chapters: list[StoryChapter] = Field(default_factory=list)
    edit_plan: list[EditDecision] = Field(default_factory=list)

    @model_validator(mode='after')
    def relationships(self):
        entities={x.id:x for x in self.canon}; scenes={x.id:x for x in self.scenes}
        if self.chapters:
            owned=[sid for ch in self.chapters for sid in ch.scene_ids]
            if len({ch.id for ch in self.chapters})!=len(self.chapters) or len(owned)!=len(set(owned)) or set(owned)!=set(scenes):
                raise ValueError('Story chapters must uniquely own every scene')
            if any(sum(s.scene_id in ch.scene_ids for s in self.shots)>40 for ch in self.chapters):
                raise ValueError('Each story chapter supports up to 40 shots')
        elif len(self.shots)>40: raise ValueError('A single production proposal supports up to 40 shots')
        all_ids=[x.id for x in self.canon+self.scenes+self.shots]+[f.id for s in self.shots for f in s.keyframes]
        if len(all_ids)!=len(set(all_ids)): raise ValueError('All entity, scene, shot and frame IDs must be unique')
        for scene in self.scenes:
            if scene.location_id not in entities or entities[scene.location_id].kind!='location': raise ValueError('Scene must link a canonical location')
        for shot in self.shots:
            if shot.scene_id not in scenes: raise ValueError('Unknown scene')
            allowed=set(shot.entity_ids)|{scenes[shot.scene_id].location_id}
            if not allowed<=entities.keys(): raise ValueError('Unknown shot entity')
            if len(shot.entity_ids)!=len(set(shot.entity_ids)): raise ValueError('Duplicate shot entity')
            for st in shot.start_state+shot.end_state:
                if st.entity_id not in allowed: raise ValueError('State entity must belong to shot')
            for states in [shot.start_state,shot.end_state]:
                keys=[(s.entity_id,s.key) for s in states]
                if len(keys)!=len(set(keys)): raise ValueError('Duplicate state key')
            for b in shot.beats+shot.dialogue:
                if b.start>=b.end or b.end>shot.duration: raise ValueError('Timing must fit within shot duration')
            for d in shot.dialogue:
                if d.entity_id not in allowed or entities[d.entity_id].kind not in ('character','crowd','voice'): raise ValueError('Dialogue must link a character in the shot')
            moments=[(x.moment,x.source_time if x.moment=='key' else None) for x in shot.keyframes]
            if len(set(moments))!=len(moments): raise ValueError('Only one keyframe per moment')
            for frame in shot.keyframes:
                if frame.moment=='key':
                    if not 0 < frame.source_time < shot.duration:raise ValueError('Intermediate frame time must lie inside its source Shot')
                    keys=[(x.entity_id,x.key) for x in frame.state]
                    if any(x.entity_id not in allowed for x in frame.state) or len(keys)!=len(set(keys)):raise ValueError('Invalid storyboard frozen state')
        validate_director_plan(self.model_dump())
        return self

class ImageResult(Strict):
    image_path: str
    notes: str

from .image_loras import Selection as ImageLoraSelection

class PreparedImage(Strict):
    target_id: str
    visual_style: str = Field(min_length=1,max_length=500)
    appearance: str = Field(min_length=1,max_length=1800)
    composition: str = Field(min_length=1,max_length=1400)
    lighting: str = Field(min_length=1,max_length=600)
    requested_changes: str = Field(max_length=4000)
    omitted_context: list[str] = Field(max_length=20)
    conflicts: list[str] = Field(max_length=10)
    local_lora_selection: ImageLoraSelection | None = None

class ReviewResult(Strict):
    verdict: Literal['pass','revise','uncertain']
    summary: str
    issues: list[str]

class StateCheck(Strict):
    """One declared state fact compared against the candidate's actual pixels.

    ``match`` is deliberately nullable: a fact that cannot be judged from the image is
    neither confirmed nor contradicted, and collapsing that into False would turn every
    unverifiable detail into a reported defect.
    """
    entity_id: str
    key: str
    declared: str
    observed: str
    match: bool | None

class ImageReviewResult(ReviewResult):
    character_sheet: Literal['pass','revise','uncertain','not_applicable'] = 'uncertain'
    state_checks: list[StateCheck] = Field(default_factory=list)

class TextResult(Strict):
    text: str

class CreateProject(Strict):
    title: str = Field(min_length=1,max_length=150)
    idea: str = Field(min_length=3,max_length=20000)
    style: str = Field(default='Warm illustrated realism, restrained colors, coherent natural lighting.',max_length=3000)
    source_kind: Literal['outline','idea','story','screenplay'] = 'idea'
    source_filename: str = Field(default='',max_length=255)

class SourceCoverage(Strict):
    source_id: str
    shot_ids: list[str] = Field(min_length=1)
    treatment: str = Field(min_length=1)

class ChapterDraft(Strict):
    title: str = Field(min_length=1,max_length=150)
    brief: str = Field(min_length=3,max_length=20000)
    source_kind: Literal['idea','story','screenplay'] = 'idea'
    version: int = 0

class OutlineEdit(Strict):
    idea: str = Field(min_length=3,max_length=20000)
    brief_revision: int

class StoryboardProposal(Strict):
    production: Production
    coverage: list[SourceCoverage] = Field(min_length=1)
    adaptation_notes: list[str]

class JobRequest(Strict):
    capability: str
    proposal_id: str = ''
    target_id: str = ''
    feedback: str = Field(default='',max_length=10000)
    force: bool = False
    source_asset_id: str = ''
    image_provider: str = ''
    image_operation: Literal['auto','new','reference','sheet','portrait','face_swap','edit','inpaint','outpaint'] = 'auto'
    image_region: list[int] | None = None
    image_padding: list[int] | None = None
    video_model: str = Field(default='', max_length=300)
    strategy_mode: Literal['AUTO','I2VA','FL2VA','REF2VA'] = 'AUTO'
    source_prompt: str | None = Field(default=None,max_length=7000)
    input_reference_ids: list[str] = Field(default_factory=list)

class DirectorApproach(Strict):
    camera: str = Field(min_length=1)
    blocking: str = Field(min_length=1)
    editing: str = Field(min_length=1)
    lighting_color: str = Field(min_length=1)
    keyframe_example: str = Field(min_length=1)

class DirectorCandidate(Strict):
    style_id: str
    fit_reason: str = Field(min_length=1)
    source_evidence: list[str] = Field(min_length=1,max_length=4)
    approach: DirectorApproach
    tradeoff: str = Field(min_length=1)

class DirectorRecommendations(Strict):
    story_reading: str = Field(min_length=1)
    candidates: list[DirectorCandidate] = Field(min_length=3,max_length=3)

class DirectorSelection(Strict):
    job_id: str = ''
    style_id: str = ''
    revision: int

class RevisionRequest(Strict):
    revision: int

class PlanEdit(Strict):
    revision: int
    production: Production

class Decision(Strict):
    status: Literal['approved','rejected']
    note: str = ''
    acknowledge_sheet_issues: bool = False

class SceneAssetBatchRequest(Strict):
    token: str = Field(min_length=1,max_length=100)
    image_provider: str = Field(min_length=1,max_length=100)

class ProviderConfig(Strict):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    name: str
    kind: Literal['codex','http','manual']
    model: str
    base_url: str = ''
    key_env: str = ''
    capabilities: list[str]
    context_window: int | None = Field(default=None, ge=4096, le=2097152)
    max_output_tokens: int | None = Field(default=None, ge=256, le=393216)
    tokenizer: Literal['estimate','llama_cpp'] = 'estimate'

    @model_validator(mode='after')
    def context_limits(self):
        if self.context_window and self.max_output_tokens and self.max_output_tokens + 1024 >= self.context_window:
            raise ValueError('上下文容量須大於輸出預留及 1024 tokens 安全空間。')
        return self

class ProviderContextLimits(Strict):
    provider_id: str
    context_window: int = Field(ge=4096, le=2097152)
    max_output_tokens: int = Field(ge=256, le=393216)
    tokenizer: Literal['estimate','llama_cpp'] = 'estimate'

    @model_validator(mode='after')
    def usable_context(self):
        if self.max_output_tokens + 1024 >= self.context_window:
            raise ValueError('上下文容量須大於輸出預留及 1024 tokens 安全空間。')
        return self


class ProviderProfile(Strict):
    mode: Literal['astra','deepseek','local_qwen']
    image_provider: str | None = None
    model: str = 'deepseek-v4-pro'
    vision_model: str = 'deepseek-v4-flash-vision-exp'
    key_env: str = 'DEEPSEEK_API_KEY'
    api_key: str | None = None

class Routing(Strict):
    capability: str
    provider_id: str

class H3ChapterPrompt(Strict):
    shot_id: str
    shot_prompt: str

class H3ScenePrompts(Strict):
    global_prompt: str
    chapters: list[H3ChapterPrompt]

class ChapterDelivery(Strict):
    prompt_edited: bool = False
    shot_prompt: str = ''
    reference_frame: Literal['none','start','end','both'] = 'none'
    guide_from_previous: bool | None = None
    guidance_mode: Literal['auto','manual'] = 'auto'
    guidance_notes: str = ''

class SceneDelivery(Strict):
    prompt_edited: bool = False
    global_prompt: str = ''
    chapters: dict[str,ChapterDelivery] = Field(default_factory=dict)

class DeliveryEdit(Strict):
    revision: int
    production_revision: int
    continuity_enabled: bool
    context_frames: Literal[5,22,39,56]
    scenes: dict[str,SceneDelivery]


class ShotGuidanceDecision(Strict):
    shot_id: str
    previous_shot_id: str | None
    decision: Literal['start','cut','extend','uncertain']
    reason: str = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)

class ShotGuidanceReview(Strict):
    decisions: list[ShotGuidanceDecision] = Field(min_length=1)

class PreparedSubject(Strict):
    entity_id: str
    name_en: str = Field(min_length=1,max_length=100)
    appearance: str = Field(min_length=1,max_length=400)

class PreparedShot(Strict):
    shot_id: str
    shot_prompt: str = Field(min_length=1,max_length=4800)

class PreparedScene(Strict):
    scene_id: str
    visual_setting: str = Field(min_length=1,max_length=850)
    subjects: list[PreparedSubject]
    shots: list[PreparedShot]

class ReferenceDemand(Strict):
    entity_id: str
    role: Literal['character_identity','object_identity','environment_reference','appearance_consistency','reusable_visual_reference','motion_reference','video_reference','audio_reference']
    required: bool
    reason: str = Field(min_length=1,max_length=1200)
    evidence: list[str] = Field(min_length=1,max_length=3)

class ConditioningDecision(Strict):
    mode: Literal['I2VA','FL2VA','REF2VA']
    reason: str = Field(min_length=1,max_length=2000)
    evidence: list[str] = Field(min_length=1,max_length=3)
    reference_demands: list[ReferenceDemand] | None = Field(default=None,max_length=24)
    unresolved_constraints: list[str] = Field(default_factory=list,max_length=8)

class VideoStrategy(ConditioningDecision):
    start_blueprint: str = Field(min_length=1,max_length=3000)
    end_blueprint: str = Field(max_length=3000)
    checks: list[str] = Field(min_length=2,max_length=6)

class VideoWorkflowEdit(Strict):
    revision: int
    mode: Literal['I2VA','FL2VA','REF2VA'] | None = None
    text: str | None = Field(default=None,max_length=7000)
    source_hash: str = ''

class VideoAdopt(Strict):
    revision: int

class VideoFrameAdd(Strict):
    revision: int
    moment: Literal['start','end']
    description: str = Field(min_length=3,max_length=3000)

class VideoPromptResult(Strict):
    text: str = Field(max_length=7000)
    frame_issues: list[str] = Field(default_factory=list,max_length=8)
