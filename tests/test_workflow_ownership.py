"""Original ComfyUI/Downloads workflow files are not runtime dependencies."""
import builtins
import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from studio import local_images, h3_render_graph, store
from test_h3_render_graph import compile_graph


@pytest.fixture
def owned_workflows(tmp_path, monkeypatch):
    bundle = tmp_path / 'continuity-studio' / 'workflows'
    for path in (store.ROOT / 'workflows').rglob('*'):
        assert not path.is_symlink(), 'Workflow bundle must contain files, not external symlinks'
    shutil.copytree(store.ROOT / 'workflows', bundle)
    image_manifest = json.loads((bundle / 'local-images/manifest.json').read_text())
    video_manifest = json.loads((bundle / 'minimax-h3-director/manifest.json').read_text())
    external = {Path(row['source']) for row in image_manifest['source_workflows']}
    external.add(Path(video_manifest['original']['source_path']))
    external_roots = (Path('/home/navievroom/comfy/workflows'),
                      Path('/home/navievroom/comfy/ComfyUI/user'))
    attempted = []

    def missing(path):
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        p = Path(os.fsdecode(path)).absolute()
        if p in external or any(p.is_relative_to(root) for root in external_roots):
            attempted.append(str(p))
            raise FileNotFoundError('External workflow deliberately unavailable: ' + str(p))

    path_open, builtin_open, stat, scandir = Path.open, builtins.open, os.stat, os.scandir
    def guarded_path_open(self, *args, **kwargs):
        missing(self)
        return path_open(self, *args, **kwargs)
    def guarded_open(path, *args, **kwargs):
        missing(path)
        return builtin_open(path, *args, **kwargs)
    def guarded_stat(path, *args, **kwargs):
        missing(path)
        return stat(path, *args, **kwargs)
    def guarded_scandir(path):
        missing(path)
        return scandir(path)
    monkeypatch.setattr(Path, 'open', guarded_path_open)
    monkeypatch.setattr(builtins, 'open', guarded_open)
    monkeypatch.setattr(os, 'stat', guarded_stat)
    monkeypatch.setattr(os, 'scandir', guarded_scandir)
    monkeypatch.setattr(local_images, 'ROOT', bundle / 'local-images')
    monkeypatch.setattr(h3_render_graph, 'ORIGINAL', bundle / 'minimax-h3-director' / video_manifest['original']['archive_path'])
    yield bundle, image_manifest, video_manifest
    assert not attempted, 'Studio must not even probe external workflow files'


def test_archives_are_complete_owned_files(owned_workflows):
    bundle, image_manifest, video_manifest = owned_workflows
    for row in image_manifest['source_workflows']:
        path = bundle / 'local-images/original' / row['filename']
        assert not path.is_symlink() and path.resolve().is_relative_to(bundle)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
    assert not h3_render_graph.ORIGINAL.is_symlink()
    assert hashlib.sha256(h3_render_graph.ORIGINAL.read_bytes()).hexdigest() == h3_render_graph.ORIGINAL_SHA256 == video_manifest['original']['sha256']
    assert local_images.origins() == {r['filename']: r['sha256'] for r in image_manifest['source_workflows']}


@pytest.mark.parametrize('recipe', list(local_images.RECIPES))
def test_all_image_graphs_build_without_external_workflows(owned_workflows, recipe):
    bundle, _, _ = owned_workflows
    info = json.loads((bundle / 'local-images/runtime-schemas.json').read_text())
    count = 0 if recipe == 'krea_new' else 2 if recipe in ('krea_two', 'klein_face') else 1
    plan = local_images.select({'image_source': {'target_kind': 'frame'}, 'images': [], 'image_reference_roles': []})
    plan.update(recipe=recipe, reference_count=count, region=[20,20,40,40], padding=[64,0,64,0])
    graph = local_images.build(plan, 'STUDIO OWNED PROMPT', [f'studio-input-{i}.png' for i in range(count)], 'ContinuityStudio/owned')
    local_images.validate_graph(graph, info)
    assert sum(node['class_type'] == 'SaveImage' for node in graph.values()) == 1
    assert 'STUDIO OWNED PROMPT' in json.dumps(graph)
    assert 'workflow.json' not in json.dumps(graph)
    for row in owned_workflows[1]['source_workflows']:
        assert row['source'] not in json.dumps(graph)


@pytest.mark.parametrize('mode', ['I2VA', 'FL2VA', 'REF2VA'])
def test_video_graphs_build_without_external_workflows(owned_workflows, mode):
    info = json.loads((Path(__file__).parent / 'fixtures/h3_node_schema.json').read_text())
    source, graph, timeline = compile_graph(info, mode)
    assert timeline['segments'][0]['prompt'] == source['text']
    assert graph['7']['class_type'] == 'SaveVideo'
    assert owned_workflows[2]['original']['source_path'] not in json.dumps(graph)
