"""Compact only JSON formatting; preserve creative text and budget enforcement."""
import copy
import json

import pytest

from studio import context_limits, generation_groups as gg, models, providers, store
from test_production import client, plan, create
from test_generation_groups import montage


def test_embedded_source_roundtrips_unicode_and_literal_whitespace(client, montage):
    literal = '阿晴  看向開關。\n\tKeep  two spaces, "quotes", \\slashes and 雨衣。'
    montage['shots'][0]['action'] = literal
    pid = create(client, montage)
    project = store.project(pid)
    before = copy.deepcopy(project)
    data = gg.build_plan(project, models.JobRequest(capability='h3_group_plan', target_id='scene'))
    start = data['prompt'].index('{"edit_positions":')
    source, end = json.JSONDecoder().raw_decode(data['prompt'], start)
    assert source == data['group_plan_source']
    assert source['production']['shots'][0]['action'] == literal
    assert data['group_plan_hash'] == gg.planning_fingerprint(source)
    assert project == before
    assert end < len(data['prompt'])
    assert len(data['prompt'][start:end].encode()) < len(store.encode(source).encode())


def test_exact_wire_fits_without_changing_fixed_output_or_safety_reserves(client, montage):
    pid = create(client, montage)
    data = gg.build_plan(store.project(pid), models.JobRequest(capability='h3_group_plan', target_id='scene'))
    start = data['prompt'].index('{"edit_positions":')
    source, end = json.JSONDecoder().raw_decode(data['prompt'], start)
    previous = data['prompt'][:start] + store.encode(source) + data['prompt'][end:]
    schema = providers.strict_schema(gg.GroupPlan.model_json_schema())
    old_size = len(context_limits.wire_text(previous, schema).encode())
    policy = {'context_window': old_size + 32768 + 1024 - 1,
              'max_output_tokens': 32768, 'safety_tokens': 1024, 'tokenizer': 'estimate'}
    frozen = copy.deepcopy(policy)
    provider = {'context_policy': policy}
    with pytest.raises(ValueError, match='必要上下文超出'):
        context_limits.check(provider, previous, schema)
    receipt = context_limits.check(provider, data['prompt'], schema)
    assert receipt['fits']
    assert receipt['input_tokens'] < old_size
    assert policy == frozen
