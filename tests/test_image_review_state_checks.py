"""Contracts for the machine-checkable declared-versus-observed state checks.

A model verdict is a fallible judgement and, as measured, not even reproducible for the
same prompt and pixels. The state checks exist so a declared prop fact (is the lantern
emitting light?) can be read back as data instead of trusted as prose.
"""
import pytest
from pydantic import ValidationError
from studio import models

OLD_RECORD = {'verdict': 'pass', 'summary': 'Looks right.', 'issues': [], 'character_sheet': 'not_applicable'}


def test_previous_records_without_state_checks_still_parse():
    """Existing saved reviews predate the field and must keep loading unchanged."""
    result = models.ImageReviewResult.model_validate(OLD_RECORD)
    assert result.state_checks == []
    assert result.model_dump()['state_checks'] == []


def test_state_check_carries_declared_and_observed_values():
    result = models.ImageReviewResult.model_validate({**OLD_RECORD, 'verdict': 'revise',
        'issues': ['The lantern is lit.'],
        'state_checks': [{'entity_id': 'prop_lantern', 'key': 'power',
                          'declared': 'Off; unlit - dark glass chimney, no filament glow',
                          'observed': 'the glass chimney glows with a visible filament',
                          'match': False}]})
    check = result.state_checks[0]
    assert (check.entity_id, check.key, check.match) == ('prop_lantern', 'power', False)
    assert check.declared.startswith('Off; unlit') and 'glows' in check.observed


def test_unverifiable_check_is_reported_without_claiming_a_match():
    """Not visible must be distinguishable from both matched and contradicted."""
    result = models.ImageReviewResult.model_validate({**OLD_RECORD, 'verdict': 'uncertain',
        'state_checks': [{'entity_id': 'prop_lantern', 'key': 'power', 'declared': 'Off; unlit',
                          'observed': 'not visible in this crop', 'match': None}]})
    assert result.state_checks[0].match is None


def test_unknown_fields_are_still_rejected():
    with pytest.raises(ValidationError):
        models.ImageReviewResult.model_validate({**OLD_RECORD, 'unexpected': 'x'})


def test_text_review_schema_is_not_widened():
    """Only image_review reads pixels, so only its schema carries state checks."""
    assert 'state_checks' not in models.ReviewResult.model_fields
    assert 'state_checks' in models.ImageReviewResult.model_fields
