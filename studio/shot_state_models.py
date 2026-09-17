"""Authored semantic timeline; endpoint/frame fields are compatibility projections."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Fact(Strict):
    entity_id: str
    key: str = Field(pattern=r'^[a-z][a-z0-9_]*$')
    value: str | None = Field(min_length=1)


class Moment(Strict):
    time: float = Field(ge=0, allow_inf_nan=False)
    state: list[Fact]


class Change(Strict):
    entity_id: str
    key: str
    before: str
    after: str


class Transition(Strict):
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    changes: list[Change] = Field(min_length=1)


class Composition(Strict):
    frame_id: str
    text: str = Field(min_length=1, max_length=2400)


class ShotState(Strict):
    version: Literal['canonical-shot-state-v1'] = 'canonical-shot-state-v1'
    moments: list[Moment] = Field(min_length=2)
    transitions: list[Transition]
    compositions: list[Composition]


class StatePreparation(Strict):
    canonical_state: ShotState
    reconciliations: list[str]
    conflicts: list[str]
