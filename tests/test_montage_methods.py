"""Actual request/stage integration, source ownership and review freshness."""
import copy
import hashlib
import json
import shutil

import pytest

from studio import engine, models, production_methods, providers, store, directing
from test_production import client, plan, create
from test_directing import directed, reviewed
from test_chapter_pipeline import production, setup_job, outputs, fake_provider


@pytest.mark.parametrize('capability', ['narrative', 'storyboard', 'qc', 'directing_qc'])
def test_owned_visual_skill_and_adaptation_reach_authoring_and_review(capability):
    text, meta = production_methods.snapshot(capability)
    original = production_methods.reference('visual-skills/dramaturgy.md')
    adaptation = production_methods.reference('montage.md')
    assert text.count(original) == text.count(adaptation) == 1
    assert text.index(original) < text.index(adaptation)
    assert meta['mandatory']
    provenance = json.loads(production_methods.reference('visual-skills/provenance.json'))
    for entry in provenance['files']:
        raw = (production_methods.ROOT / 'references/visual-skills' / entry['file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry['sha256']


@pytest.mark.parametrize('capability', ['image', 'image_prepare', 'image_review', 'h3',
                                      'h3_shot', 'h3_scene', 'h3_video_prompt', 'h3_strategy'])
def test_continuous_source_writers_do_not_receive_montage_cut_instructions(capability):
    text, _ = production_methods.snapshot(capability)
    assert production_methods.reference('montage.md') not in text
    assert production_methods.reference('visual-skills/dramaturgy.md') not in text


@pytest.mark.parametrize('mode', ['astra', 'deepseek'])
def test_real_engine_freezes_montage_in_both_full_and_scoped_inputs(client, plan, monkeypatch, mode):
    monkeypatch.setattr(engine.POOL, 'submit', lambda *a: None)
    client.post('/api/settings/profile', json={'mode': mode, 'image_provider': 'comfy_local'})
    _, _, job = setup_job(client, monkeypatch)
    body = production_methods.reference('montage.md')
    assert job['input']['prompt'].count(body) == 1
    assert job['input']['context_instructions'].count(body) == 1
    assert job['input']['provider_config']['id'] == mode
    pid = create(client, directed(plan))
    request, _ = engine.build_input(store.project(pid), models.JobRequest(capability='directing_qc'))
    assert request['prompt'].count(body) == 1
    assert request['images'] == []


def test_every_chapter_stage_receives_frozen_visual_method(client, monkeypatch, production):
    _, _, job = setup_job(client, monkeypatch)
    calls = []
    fake_provider(monkeypatch, outputs(production), calls)
    delegate = providers.run
    received = []
    def capture(provider, capability, prompt, images, work):
        assert production_methods.reference('montage.md') in prompt
        assert production_methods.reference('visual-skills/dramaturgy.md') in prompt
        received.append(capability)
        return delegate(provider, capability, prompt, images, work)
    monkeypatch.setattr(providers, 'run', capture)
    engine.execute(job['id'])
    assert store.job(job['id'])['state'] == 'succeeded'
    assert set(received) >= {'chapter_writing', 'chapter_scene', 'chapter_shots', 'chapter_edit'}


def test_late_review_cannot_be_certified_under_a_new_method(client, plan, monkeypatch):
    monkeypatch.setattr(engine.POOL, 'submit', lambda *a: None)
    p = directed(plan)
    pid = create(client, p)
    response = client.post('/api/projects/'+pid+'/jobs', json={'capability':'directing_qc'})
    job = store.job(response.json()['job']['id'])
    frozen = job['input']['production_method']['hash']
    original_snapshot = production_methods.snapshot
    def newer(capability):
        text, meta = original_snapshot(capability)
        return text, {**meta, 'hash':'new-method-after-job-started'}
    monkeypatch.setattr(production_methods, 'snapshot', newer)
    engine.finish(job, reviewed(p))
    record = store.setting('directing_reviews:'+pid)[p['scenes'][0]['id']]
    assert record['method_hash'] == frozen
    assert directing.state(store.project(pid))['scenes'][0]['status'] == 'unreviewed'


def test_exported_method_copy_is_complete_and_relocatable(tmp_path, monkeypatch):
    mirror = store.ROOT/'skill-packages/continuity-studio/references/methods'
    destination = tmp_path/'relocated-method'
    shutil.copytree(mirror, destination)
    before = production_methods.snapshot('storyboard')
    monkeypatch.setattr(production_methods, 'ROOT', destination)
    assert production_methods.snapshot('storyboard') == before
    (destination/'references/visual-skills/dramaturgy.md').write_text('tampered')
    with pytest.raises(ValueError, match='固定版本'):
        production_methods.snapshot('storyboard')
