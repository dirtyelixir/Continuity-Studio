"""Detailed visual revisions survive preparation without losing requirements."""
import copy
import json
from pathlib import Path

import pytest

from studio import image_prompts as ip, models, providers
from test_image_conflict_repair import case, invoke


def test_long_revision_survives_correction_and_saved_reuse(case, monkeypatch):
    calls = []
    changes = ('Keep the lantern unlit. Restore the blue rim. Flatten the tarnish. '
               'Keep one left cheek curl. Touch the wire handle. Clarify the pin. '
               'Darken the scarred ironbound bench. ')
    changes = (changes * 7)[:1026]
    assert len(changes) == 1026

    def run(*args):
        calls.append(args)
        result = copy.deepcopy(case[2])
        if len(calls) == 2:
            result.update(conflicts=[], requested_changes=changes)
            # Real transports validate before returning to prepare().
            return models.PreparedImage.model_validate(result).model_dump()
        return result

    monkeypatch.setattr(providers, 'run', run)
    result, prompt = invoke(case)
    assert result['requested_changes'] == changes
    assert 'Requested changes: ' + changes in prompt
    assert invoke(case) == (result, prompt)
    assert len(calls) == 2
    decision = case[0][-1].with_name('preparation-correction') / 'decision.json'
    assert json.loads(decision.read_text())['state'] == 'accepted'


def test_revision_limit_matches_owned_schema_and_preserves_boundaries(case):
    schema = Path(__file__).resolve().parents[1] / 'skill-packages/continuity-studio/schemas/prepared-image.schema.json'
    assert json.loads(schema.read_text())['properties']['requested_changes']['maxLength'] == 4000
    assert models.PreparedImage.model_json_schema()['properties']['requested_changes']['maxLength'] == 4000
    result = copy.deepcopy(case[2])
    result.update(conflicts=[], requested_changes='修' * 4000)
    assert ip.validate(result, case[0][1])['requested_changes'] == result['requested_changes']
    result['requested_changes'] += '訂'
    with pytest.raises(ValueError, match='requested_changes'):
        ip.validate(result, case[0][1])


def test_long_revision_cannot_bypass_total_prompt_limit(case):
    result = copy.deepcopy(case[2])
    result.update(conflicts=[], requested_changes='R' * 4000)
    with pytest.raises(ValueError, match='7500'):
        ip.compile_prompt(result, case[0][1], 'T' * 4000, [])
