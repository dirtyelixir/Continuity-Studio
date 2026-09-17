"""Sync tests for the agent-facing Continuity Studio skill package.

The package at ``skill-packages/continuity-studio/`` must stay a byte-for-byte
derivative of the Studio-owned bundles (``studio/bundled/``) so agents receive the
same versioned writing rules as the Studio runtime, from one maintained source.
``scripts/export_skill_package.py`` owns the derivation; these tests fail if the
package drifts from Studio again.

Fast, stdlib-only, no network, no GPU, no generation.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKAGE = REPO / 'skill-packages' / 'continuity-studio'
PROVENANCE = PACKAGE / 'provenance.json'
METHOD_MANIFEST = REPO / 'studio' / 'bundled' / 'studio-production-methods' / 'manifest.json'
WRITING_REF = 'references/prompt-writing.md'
WRITING_CAPABILITIES = ('narrative', 'storyboard', 'image_prepare', 'image', 'h3_video_prompt')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_provenance() -> dict:
    return json.loads(PROVENANCE.read_text())


def package_files(root: Path) -> dict:
    out = {}
    for path in sorted(root.rglob('*')):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = sha256(path)
    return out


def test_copied_sources_match_studio_byte_for_byte():
    provenance = load_provenance()
    for dest, src in provenance['copied_sources'].items():
        src_root = REPO / src
        want = {}
        for path in sorted(src_root.rglob('*')):
            if path.is_file():
                want[path.relative_to(src_root).as_posix()] = sha256(path)
        got = package_files(PACKAGE / dest)
        missing = sorted(set(want) - set(got))
        extra = sorted(set(got) - set(want))
        changed = sorted(rel for rel in set(want) & set(got) if want[rel] != got[rel])
        assert not missing, '%s: files missing from package copy: %s' % (dest, missing)
        assert not extra, '%s: files in package copy absent from source: %s' % (dest, extra)
        assert not changed, '%s: files differ from Studio source: %s' % (dest, changed)


def test_provenance_files_match_disk():
    provenance = load_provenance()
    # provenance.json cannot hash its own bytes; the package's own verify_package.py
    # makes the same exclusion.
    actual = {rel: digest for rel, digest in package_files(PACKAGE).items()
              if rel != 'provenance.json'}
    listed = provenance['files']
    missing_paths = sorted(set(listed) - set(actual))
    assert not missing_paths, 'provenance lists paths that do not exist: %s' % missing_paths
    stale = sorted(rel for rel in set(listed) & set(actual) if listed[rel] != actual[rel])
    assert not stale, 'provenance hashes do not match bytes on disk: %s' % stale
    unlisted = sorted(set(actual) - set(listed))
    assert not unlisted, 'package files not listed in provenance: %s' % unlisted


def test_provenance_method_version_is_live():
    live = json.loads(METHOD_MANIFEST.read_text())['version']
    assert load_provenance()['source_method_version'] == live


def test_shared_writing_reference_present_and_routed():
    # Present in the package copy of the methods bundle.
    copied = PACKAGE / 'references' / 'methods' / WRITING_REF
    assert copied.is_file(), 'shared writing reference missing from package copy'
    # Identical bytes to the Studio source.
    original = REPO / 'studio' / 'bundled' / 'studio-production-methods' / WRITING_REF
    assert sha256(copied) == sha256(original)
    # Routed for the writing capabilities in BOTH manifests.
    studio_manifest = json.loads(METHOD_MANIFEST.read_text())
    copied_manifest = json.loads((PACKAGE / 'references' / 'methods' / 'manifest.json').read_text())
    for manifest in (studio_manifest, copied_manifest):
        for capability in WRITING_CAPABILITIES:
            routes = manifest['routes'].get(capability, [])
            assert WRITING_REF in routes, (
                '%s not routed for %s in %s'
                % (WRITING_REF, capability, manifest.get('id', 'manifest'))
            )


def test_export_check_passes_after_fresh_export():
    export = [sys.executable, str(REPO / 'scripts' / 'export_skill_package.py')]
    run = subprocess.run(export, cwd=str(REPO), capture_output=True, text=True)
    assert run.returncode == 0, 'export failed:\n%s%s' % (run.stdout, run.stderr)
    check = subprocess.run(export + ['--check'], cwd=str(REPO), capture_output=True, text=True)
    assert check.returncode == 0, (
        'export_skill_package.py --check failed after fresh export:\n%s%s'
        % (check.stdout, check.stderr)
    )
