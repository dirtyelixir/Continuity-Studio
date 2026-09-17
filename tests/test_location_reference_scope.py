"""Location scope reaches all image stages without rewriting durable canon."""
import copy
from pathlib import Path

import pytest

from studio import continuity, engine, image_prompts, models, providers, store
from test_production import client, plan, create, add_asset
from test_image_prompt_assembly import prepared


def stairs(plan):
    plan['canon'][1].update(name='Fire stairs', description='Concrete switchback stairs with green rails',
                            facts=['The twelfth-floor left doorframe has a unique dark scrape.'])
    plan['shots'][0]['keyframes'][0]['description'] = 'Ada on the nineteenth-floor landing; the green door bears 19.'
    return plan


def test_location_authority_propagates_to_prepare_render_and_review(client, plan):
    plan = stairs(plan)
    pid = create(client, plan)
    refs = [add_asset(pid, plan, name) for name in ('ada', 'room')]
    before = copy.deepcopy(store.project(pid))
    old_hash = continuity.target_hash(plan, 'start')
    data, _ = engine.build_input(before, models.JobRequest(capability='image', target_id='start'))
    location_role = next(role for role in data['image_reference_roles'] if 'LOCATION' in role)
    assert 'sublocation' in location_role and 'same-place fixed anchor' in location_role
    assert location_role in data['prompt']
    assert 'Scene may span several floors or rooms' in data['prompt']
    assert data['image_source']['visual_context']['canon'][1]['facts'] == plan['canon'][1]['facts']
    result = prepared('start')
    result['composition'] = 'Ada on the landing beside the green door marked 19.'
    rendered = image_prompts.compile_prompt(result, data['image_source'], data['image_task'], data['image_reference_roles'])
    assert location_role in rendered and 'Preserve expressly required in-scene lettering' in rendered
    assert 'No watermarks, captions, text labels or montage.' not in rendered
    data.update(image_prompt_stage='render', image_preparation=result)
    aid = add_asset(pid, plan, 'start', refs, status='pending')
    with store.db() as c:
        c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',
                  ('scope-generation', pid, 'image', 'start', 'succeeded', 'astra', store.encode(data), store.now(), store.now()))
        c.execute('UPDATE assets SET job_id=? WHERE id=?', ('scope-generation', aid))
    review, _ = engine.build_input(before, models.JobRequest(capability='image_review', target_id=aid))
    assert 'Judge required floor/room lettering against the target frame' in review['prompt']
    assert 'same-place fixed anchors remain conflicts' in review['review_context']['reference_policy']
    assert review['review_context']['render_brief']['composition'] == result['composition']
    assert store.project(pid) == before and continuity.target_hash(plan, 'start') == old_hash


def test_scope_policy_invalidates_preparation_reuse_without_canon_change(client, plan):
    pid = create(client, stairs(plan))
    for name in ('ada', 'room'):
        add_asset(pid, plan, name)
    data, _ = engine.build_input(store.project(pid), models.JobRequest(capability='image', target_id='start'))
    paths = [Path(p) for p in data['images']]
    current = image_prompts.preparation_fingerprint(data, paths)
    legacy = copy.deepcopy(data)
    legacy['image_source']['policy'] = 'single-image-brief-v4'
    assert image_prompts.preparation_fingerprint(legacy, paths) != current
    legacy = copy.deepcopy(data)
    legacy['production_method']['hash'] = 'old-location-authority-method'
    assert image_prompts.preparation_fingerprint(legacy, paths) != current
    assert data['dependency_hash'] == continuity.target_hash(plan, 'start')


def test_same_place_conflict_still_stops_before_renderer(client, plan, monkeypatch):
    pid = create(client, stairs(plan))
    for name in ('ada', 'room'):
        add_asset(pid, plan, name)
    monkeypatch.setattr(engine.POOL, 'submit', lambda *args: None)
    calls = []
    def conflict(provider, capability, prompt, images, work):
        calls.append(capability)
        result = prepared('start')
        result['conflicts'] = ['The same fixed doorway is required on incompatible walls.']
        return result
    monkeypatch.setattr(providers, 'run', conflict)
    before = store.assets(pid)
    job = engine.enqueue(pid, models.JobRequest(capability='image', target_id='start'))['job']
    engine.execute(job['id'])
    assert calls == ['image_prepare', 'image_prepare']
    assert store.job(job['id'])['state'] == 'failed'
    assert store.assets(pid) == before


@pytest.mark.parametrize('composition', ['The door bears 19.', 'The sign reads 19.', 'Visible lettering: 19.'])
def test_required_signage_is_not_dependent_on_model_word_choice(plan, composition):
    result = prepared('start')
    result['composition'] = composition
    prompt = image_prompts.compile_prompt(result, image_prompts.source(stairs(plan), 'start'), 'One frozen frame.', [])
    assert composition in prompt
    assert 'Preserve expressly required in-scene lettering' in prompt
    assert 'No watermarks, captions, text labels or montage.' not in prompt
