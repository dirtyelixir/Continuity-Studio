#!/usr/bin/env python3
"""Recompute the Studio method bundle manifest: file hashes, versions, writing-prompt routes.

The bundle is content-addressed: ``studio/production_methods.py`` refuses to load a file whose
sha256 differs from the manifest, so every edit to a reference must come with a refreshed
manifest. Doing that by hand is how the manifest and the files drift apart, so this script owns it.

It also owns *where* the shared prompt-writing principles are routed. Adding a capability here is
how a writer receives the principles at runtime, because
``production_methods.snapshot(capability)`` already injects the routed files into that
capability's model instruction. There is no second copy to keep in step.

Usage:  python3 scripts/update_method_manifest.py [--check]

``--check`` exits non-zero if the manifest is stale, for use in tests and CI.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / 'studio' / 'bundled' / 'studio-production-methods'
MANIFEST = ROOT / 'manifest.json'

# The one shared writing reference. Routed into every capability that WRITES or REVISES prompt
# text. Reviewing capabilities keep their own review/directing references: they judge consistency,
# and the deterministic checks in studio/prompt_writing.py already cover the mechanical faults.
# Keeping this list tight matters — the reference is carried into every job's instruction, and a
# capability that does not write prompts paying for it is pure cost (and can push a chapter
# over its context budget, which silently adds whole extra stages).
WRITING_REF = 'references/prompt-writing.md'
WRITING_ROUTES = (
    'narrative', 'storyboard', 'storyboard_frames',
    'image_prepare', 'image',
    'h3', 'h3_prepare', 'h3_shot', 'h3_global', 'h3_scene', 'h3_video_prompt',
    'h3_strategy', 'h3_group_plan',
)


def files():
    out = {}
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file() or path.name == 'manifest.json':
            continue
        out[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def expected(manifest):
    """The manifest this bundle should have, given its current file contents."""
    data = json.loads(json.dumps(manifest))
    data['files'] = files()
    # Routes are declarative: the writers get the reference, everyone else does not carry it.
    for capability, entries in data['routes'].items():
        entries[:] = [e for e in entries if e != WRITING_REF]
        if capability in WRITING_ROUTES:
            entries.insert(0, WRITING_REF)
    return data


def staleness(manifest):
    want = expected(manifest)
    return [key for key in ('files', 'routes') if want[key] != manifest[key]]


def main(argv):
    manifest = json.loads(MANIFEST.read_text())
    stale = staleness(manifest)
    if '--check' in argv:
        if stale:
            print('method manifest is stale: ' + ', '.join(stale))
            return 1
        print('method manifest is current')
        return 0
    if not stale:
        print('method manifest already current; version %s' % manifest['version'])
        return 0
    updated = expected(manifest)
    major, minor, patch = (int(x) for x in manifest['version'].split('.'))
    updated['version'] = '%d.%d.%d' % (major, minor + 1, patch)
    MANIFEST.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n')
    print('method manifest updated: %s -> %s (changed: %s)' % (manifest['version'], updated['version'], ', '.join(stale)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
