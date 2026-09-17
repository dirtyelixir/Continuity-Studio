"""Provider-facing scope and immutable snapshot behavior for acting instructions."""
import hashlib
import json
import shutil

import pytest

from studio import production_methods


@pytest.mark.parametrize('capability', [
    'narrative', 'storyboard', 'h3', 'h3_prepare', 'h3_shot',
    'h3_scene', 'h3_video_prompt', 'qc', 'directing_qc',
])
def test_performance_reaches_planning_execution_and_review(capability):
    text, metadata = production_methods.snapshot(capability)
    body = production_methods.reference('performance.md')
    assert text.count(body) == 1
    assert metadata['instruction_files'].count('references/performance.md') == 1
    assert metadata['mandatory']


@pytest.mark.parametrize('capability', [
    'h3_global', 'image', 'image_prepare', 'image_review', 'h3_strategy',
    'h3_guidance', 'director_style', 'unknown',
])
def test_performance_body_does_not_leak_into_unrelated_tasks(capability):
    text, metadata = production_methods.snapshot(capability)
    assert production_methods.reference('performance.md') not in text
    assert 'references/performance.md' not in metadata['instruction_files']


def test_new_method_changes_future_snapshot_without_rewriting_frozen_job(tmp_path, monkeypatch):
    bundle = tmp_path / 'methods'
    shutil.copytree(production_methods.ROOT, bundle)
    monkeypatch.setattr(production_methods, 'ROOT', bundle)
    text, metadata = production_methods.snapshot('h3_shot')
    frozen = tmp_path / 'production-method.json'
    frozen.write_text(json.dumps({'prompt': text, 'production_method': metadata}))
    before = frozen.read_bytes()
    path = bundle / 'references/performance.md'
    path.write_text(path.read_text() + '\nIsolated revised method.\n')
    with pytest.raises(ValueError, match='固定版本'):
        production_methods.snapshot('h3_shot')
    manifest_path = bundle / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['files']['references/performance.md'] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    updated_text, updated_metadata = production_methods.snapshot('h3_shot')
    assert updated_text != text
    assert updated_metadata['hash'] != metadata['hash']
    assert frozen.read_bytes() == before
    assert json.loads(before)['prompt'] == text
