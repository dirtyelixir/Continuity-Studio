#!/usr/bin/env python3
"""Re-derive the agent-facing Continuity Studio skill package from the Studio bundles.

The package at ``skill-packages/continuity-studio/`` carries copies of the Studio-owned
instruction bundles under ``references/``. Hand-copied, those copies drift from the
source of truth (``studio/bundled/``), and ``studio/production_methods.py`` refuses to
load a file whose sha256 differs from its manifest -- so a stale package silently serves
an agent the wrong writing rules. This script owns the derivation:

* mirrors every ``copied_sources`` entry (all regular files, nested included) from
  ``studio/bundled/<name>`` into the package, removing files that no longer exist in
  the source (only inside those copied directories, never elsewhere in the package);
* recomputes the provenance ``files`` map by hashing every regular file in the package;
* refreshes ``source_method_version`` from the live Studio method manifest version and
  ``snapshot_date``.

All hand-written package files (SKILL.md, schemas, scripts, top-level provenance
wording) are preserved verbatim.

Usage:  python3 scripts/export_skill_package.py [--check]

``--check`` exits non-zero and lists exactly what is out of date (missing, changed,
extra copied files, stale provenance hashes, version mismatch) without writing anything.
Running the export twice in a row changes nothing the second time (idempotent).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKAGE = REPO / 'skill-packages' / 'continuity-studio'
PROVENANCE = PACKAGE / 'provenance.json'
METHOD_MANIFEST = REPO / 'studio' / 'bundled' / 'studio-production-methods' / 'manifest.json'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_provenance() -> dict:
    return json.loads(PROVENANCE.read_text())


def package_files(root: Path) -> dict:
    """Hash of every regular file in the package, sorted, package-relative POSIX paths."""
    out = {}
    for path in sorted(root.rglob('*')):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = sha256(path)
    return out


def live_method_version() -> str:
    return json.loads(METHOD_MANIFEST.read_text())['version']


def source_files(src_root: Path) -> dict:
    """Regular files under a bundle root, relative POSIX paths -> sha256.

    Skips symlinks and refuses entries that escape the bundle root.
    """
    out = {}
    root = src_root.resolve()
    for path in sorted(src_root.rglob('*')):
        if not path.is_file():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('Source entry escapes the bundle: %s' % path)
        out[path.relative_to(src_root).as_posix()] = sha256(path)
    return out


def check(provenance: dict) -> list:
    """Out-of-date items as human-readable strings; empty list means in sync."""
    problems = []
    for dest, src in provenance['copied_sources'].items():
        src_root = REPO / src
        want = source_files(src_root)
        got = package_files(PACKAGE / dest)
        for rel in sorted(want):
            target = PACKAGE / dest / rel
            if not target.is_file():
                problems.append('missing: %s/%s' % (dest, rel))
            elif sha256(target) != want[rel]:
                problems.append('changed: %s/%s' % (dest, rel))
        for rel in sorted(got):
            if rel not in want:
                problems.append('extra: %s/%s' % (dest, rel))
    # provenance.json hashes its own bytes, so it can never be listed consistently;
    # the package's own verify_package.py makes the same exclusion.
    actual = {rel: digest for rel, digest in package_files(PACKAGE).items()
              if rel != PROVENANCE.name}
    for rel in sorted(provenance['files']):
        if rel not in actual:
            problems.append('stale provenance entry: %s' % rel)
        elif provenance['files'][rel] != actual[rel]:
            problems.append('stale hash: %s' % rel)
    for rel in sorted(actual):
        if rel not in provenance['files']:
            problems.append('unlisted file: %s' % rel)
    if provenance.get('source_method_version') != live_method_version():
        problems.append('source_method_version: %s != live %s'
                        % (provenance.get('source_method_version'), live_method_version()))
    return problems


def export() -> int:
    provenance = load_provenance()
    for dest, src in provenance['copied_sources'].items():
        src_root = REPO / src
        dest_root = PACKAGE / dest
        dest_root.mkdir(parents=True, exist_ok=True)
        want = source_files(src_root)
        # Remove files in the destination that no longer exist in the source,
        # scoped strictly to this copied directory.
        for path in sorted(dest_root.rglob('*')):
            if path.is_file() and path.relative_to(dest_root).as_posix() not in want:
                path.unlink()
        # Copy / refresh every source file.
        for rel in sorted(want):
            target = dest_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if not (target.is_file() and sha256(target) == want[rel]):
                tmp = target.with_name(target.name + '.tmp-%d' % os.getpid())
                tmp.write_bytes((src_root / rel).read_bytes())
                os.replace(tmp, target)
        # Drop directories left empty by the removal pass.
        for path in sorted((p for p in dest_root.rglob('*') if p.is_dir()),
                           key=lambda p: len(p.parts), reverse=True):
            try:
                path.rmdir()
            except OSError:
                pass
    provenance['files'] = package_files(PACKAGE)
    provenance['snapshot_date'] = datetime.date.today().isoformat()
    provenance['source_method_version'] = live_method_version()
    # provenance.json hashes its own bytes, so it can never be listed consistently;
    # drop it the way the package's own verify_package.py does.
    provenance['files'].pop('provenance.json', None)
    tmp = PROVENANCE.with_name(PROVENANCE.name + '.tmp-%d' % os.getpid())
    tmp.write_text(json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    os.replace(tmp, PROVENANCE)
    return 0


def main(argv) -> int:
    if '--check' in argv:
        problems = check(load_provenance())
        if problems:
            print('skill package is out of date:')
            for problem in problems:
                print('  ' + problem)
            return 1
        print('skill package is in sync with Studio')
        return 0
    export()
    print('skill package exported from Studio bundles (method version %s)' % live_method_version())
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
