#!/usr/bin/env python3
"""Check this portable package without importing Studio or contacting a service."""
import hashlib
import json
from pathlib import Path
import re


def verify(root):
    root = Path(root).resolve()
    manifest = json.loads((root / 'provenance.json').read_text())
    expected = manifest['files']
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*')
              if p.is_file() and p.name != 'provenance.json'}
    # Nested upstream provenance files are themselves part of the payload.
    actual.update(p.relative_to(root).as_posix() for p in root.rglob('provenance.json')
                  if p != root / 'provenance.json')
    if actual != set(expected):
        raise ValueError('Package file set differs from its manifest')
    for name, digest in expected.items():
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('Nonportable package path: ' + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Changed or damaged file: ' + name)
    for rel in ('SKILL.md', 'references/production-contract.md',
                'references/h3-contract.md', 'references/studio-operation.md'):
        path = root / rel
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', path.read_text()):
            if target.startswith(('https:', 'http:', '#')):
                continue
            resolved = (path.parent / target.split('#')[0]).resolve()
            if not resolved.is_relative_to(root) or not resolved.is_file():
                raise ValueError('Missing or external operational reference: ' + target)
    methods = root / 'references/methods'
    upstream = json.loads((methods / 'manifest.json').read_text())
    for name, digest in upstream['files'].items():
        if hashlib.sha256((methods / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Studio source snapshot mismatch: ' + name)
    return {'ok': True, 'package_version': manifest['version'],
            'method_version': upstream['version'], 'files_verified': len(expected)}


if __name__ == '__main__':
    print(json.dumps(verify(Path(__file__).resolve().parents[1])))
