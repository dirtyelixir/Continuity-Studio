"""Studio-owned, mandatory production instructions; no provider or external skill dependency."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent / 'bundled' / 'studio-production-methods'


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _bundle():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    contents = {}
    for name, expected in manifest['files'].items():
        path = ROOT / name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('Studio 製作方法必須使用專案內的完整檔案。')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Studio 製作方法與固定版本不符；未開始生成。')
        contents[name] = raw.decode('utf-8').strip()
    return manifest, contents


def reference(name):
    return _bundle()[1]['references/' + name]


def snapshot(capability):
    """Loaded by the app, not selected by the model. Full prompt is frozen per job."""
    manifest, contents = _bundle()
    selected = ['SKILL.md', *manifest['routes'].get(capability, [])]
    text = '\n\n'.join(contents[name] for name in selected)
    metadata = {k: manifest[k] for k in ('id', 'name', 'version')}
    metadata.update(hash=_digest(manifest), mandatory=True, capability=capability,
                    files=manifest['files'], instruction_files=selected)
    return text, metadata


def render_contract(kind):
    manifest, contents = _bundle()
    rules = json.loads(contents['references/render-rules.json'])
    if kind not in rules['targets']:
        raise ValueError('沒有適用於此圖片目標的 Studio 製作規格。')
    return {'version': rules['version'], 'method_hash': _digest(manifest),
            'target_kind': kind, 'rules': [*rules['common'], *rules['targets'][kind]]}


def status():
    manifest, _ = _bundle()
    return {**{k: manifest[k] for k in ('id', 'name', 'version')},
            'hash': _digest(manifest), 'mandatory': True,
            'capabilities': list(manifest['routes']), 'image_prompt_reuse': True}
