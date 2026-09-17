# Snapshot provenance

| item | value |
| --- | --- |
| Source working tree | `/home/navievroom/Documents/ChatGPT/Video Production Pipline/` |
| Source git branch | `codex/continuity-studio` |
| Source HEAD (context only) | `a759e832f25bfae7512b68b8f78d44dcd3556c8a` — *"Judge incoming shot guidance with evidence-backed Astra reviews"*, 2026-09-08 20:42 +0800 |
| Snapshot contents | the **working tree**, not HEAD — 344 of the 395 changed paths were uncommitted at capture time |
| Captured | 2026-09-17 ~13:20 HKT |
| Refreshed | 2026-09-17 13:46 HKT — see "Refresh" below |
| Snapshot size | 12 MB, 517 files |
| Preparation | read-only on the source tree: files copied with `rsync -a`; nothing in the source was modified, built, migrated or deleted |

## What is inside

| area | files | lines | role |
| --- | ---: | ---: | --- |
| `studio/` | 141 | 23,058 | application (83 Python modules + `studio/bundled/` method bundles) |
| `tests/` | 106 | 15,857 | 102 pytest files + fixtures |
| `static/` | 48 | 3,765 | browser SPA (42 JS modules, 3 CSS, HTML) |
| `docs/` | 44 | 4,449 | the project's own decisions / state / acceptance record |
| `scripts/` | 70 | 2,781 | 64 Node `.mjs` front-end behaviour checks + Python utilities |
| `workflows/` | 19 | 16,671 | Studio-owned ComfyUI workflow copies, `OWNERSHIP.md`, inventory, runtime schemas |
| `skill-packages/` | 69 | 9,299 | derived agent-facing skill package (byte-synced to `studio/bundled/`) |
| `extensions/` | 2 | 6 | extension-contract example |
| `review/` | 7 | 4,698 | **generated for this review** — see below |
| root files | 11 | — | `README.md`, `AGENTS.md`, `ARCHITECTURE.md`, `REVIEW_BRIEF.md`, `SNAPSHOT.md`, `requirements.txt`, `requirements.lock.txt`, `pytest.ini`, `run.sh`, `VERSION`, `.gitignore` |

## Refresh (2026-09-17 13:46 HKT)

The first capture was taken at ~13:20 while the source tree was still being edited; three files
changed at 13:27–13:29, after the capture and before the first push. This refresh replaces those
three files and re-measures everything that depends on them. Nothing else differs from the source
working tree — verified by comparing the SHA-256 of all 499 files across `studio/`, `tests/`,
`static/`, `docs/`, `scripts/`, `workflows/`, `skill-packages/` and `extensions/` (0 different,
0 missing on either side). The source tree was read-only throughout.

| file | first capture | refreshed | delta |
| --- | ---: | ---: | ---: |
| `studio/prompt_writing.py` | 390 lines / 19,447 B | 476 lines / 23,830 B | +86 lines |
| `tests/test_prompt_writing.py` | 6 tests / 244 lines | 16 tests / 406 lines | +10 tests |
| `tests/test_prompt_writing_wiring.py` | 5 tests / 213 lines | 9 tests / 322 lines | +4 tests |

The change is substantive, not only added tests: `composition_conflict` was removed from
`BLOCKING_CODES`, so it is now **advisory rather than blocking** — one fewer condition can raise
`ConflictError` and stop a prompt from compiling. The same edit added `_names()` (a sentence-initial
capital is not treated as a proper name, so ordinary prose no longer disables the ownership check),
`_is_prohibition()` (a prohibition is not a requirement and therefore cannot contradict one) and
`_visibility_claims()` (a time-bounded claim is not a contradiction of an unqualified one).

Re-measured figures that depend on those files:

| figure | first capture | refreshed |
| --- | ---: | ---: |
| `studio/` (83 modules) | 15,219 lines | 15,305 lines |
| `tests/` (102 test files) | 13,294 lines | 13,565 lines |
| whole-suite result | 2 failed / 1145 passed | 2 failed / 1164 passed |

All +19 newly collected cases are inside those two test files: they collect 42 cases together now,
the whole suite collects 1166 and 1124 without them, and the first capture totalled 1147 — so
1147 − 1124 = 23 cases in the older versions, and 42 − 23 = 19. `review/http-and-db.json` and
`review/docs-index.md` are byte-unchanged after regeneration (routes 64, tables 7).

The superseded version of every replaced file remains in git history at commit `81ccb1b`.

## What is deliberately excluded

* `data/` (5.9 GB) — the durable canon: `studio.sqlite3`, all generated images and every job's
  frozen inputs/outputs. Excluded: it is user production work, and the review does not need it.
* `backups/` (5.0 GB) — dated copies of the whole app + data.
* `reviews/` (981 MB) — the project's own dated evidence archives (SQLite snapshots, rendered
  media, verification JSON).
* `.git/` (245 MB), `.venv/`, `__pycache__/`, `.pytest_cache/` — regenerable.
* Any generated media, API keys or credentials. No credential material exists in the tree:
  providers read keys from the environment, and a scan of `studio/ static/ tests/ docs/
  scripts/ workflows/` found no key-shaped strings.

Consequence for review: you cannot inspect real stored productions, rendered images, or the
actual database contents. Every structural claim in `ARCHITECTURE.md` is derived from code and
docs only, and is reproducible from this snapshot.

## Files added by this snapshot (not part of the application)

* `ARCHITECTURE.md` — measured module map, data model, job/provider model, structural questions.
* `REVIEW_BRIEF.md` — what to review, how to read the snapshot, the 15 questions asked.
* `SNAPSHOT.md` — this file.
* `review/analyze_repo.py` — static analyzer (AST-based; LOC, internal imports, importers,
  docstrings, style counters, HTTP routes, SQLite tables, textual test references).
* `review/build_indexes.py` — renders the two markdown indexes from the analyzer output.
* `review/module-map.json` — full per-module record (83 entries).
* `review/http-and-db.json` — all 64 routes and 7 tables.
* `review/module-inventory.md`, `review/docs-index.md` — generated tables.
* `review/pytest-2026-09-17.log` — the raw test log quoted below.

The only modification to an existing file is a pointer block at the top of `README.md`.

## Test status in this snapshot (measured, not claimed)

Command: `.venv/bin/python -m pytest -q -p no:cacheprovider` from the snapshot root, using the
project's own locked environment (Python 3.12.3, pytest 9.1.1). For the refresh below the
interpreter was the source tree's `.venv/bin/python` — same interpreter version and same
`requirements.lock.txt` as the capture, with the working directory set to the snapshot root so
imports and fixtures resolve inside the snapshot.

```
2 failed, 1164 passed, 2 warnings in 128.24s (0:02:08)
```

Both failures are in `tests/test_image_loras.py`:

* `test_engine_automatically_applies_and_freezes_selection`
* `test_explicit_retry_reuses_original_failed_brief_with_audited_evidence`

Root cause, identified from the code: the test's own provider double writes a **pure-white
256×256 PNG** (`tests/test_image_loras.py:113`, `Image.new('RGB',(256,256),'white')`), and
`studio/image_output_quality.py:79` rejects exactly-all-white output before an asset can be
persisted ("圖片全白（所有像素均為純白 RGB）"), so the job fails instead of succeeding. This is
a fixture-versus-gate conflict, not an observed product fault: either the fixture should emit a
textured image, or the gate's white rejection is wrong for a real render. Which side should
change is an upstream decision — recorded here rather than patched, because patching either side
would be a product/verification decision, not a snapshot decision.

The suite does not require GPU, ComfyUI or a network provider: `tests/conftest.py` installs an
autouse boundary that neutralises the canonical-state compiler unless a test carries the
`canonical_state` marker and raises if a test tries to call a provider implicitly.

The project's own record (`docs/STATE.md`, 2026-09-17) describes the same period as
"3 failed / 1103 passed — the same three pre-existing failures"; the counts differ because that
entry was measured against a different working-tree revision. The third failure it names,
`tests/test_montage_methods.py::test_exported_method_copy_is_complete_and_relocatable`, passes in
this snapshot (17 passed, reproduced 3×); `studio/image_prompts.py` was changed after that entry
was written, so it was fixed rather than being intermittent. This snapshot states its own
measured result.

## How to reproduce every figure

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock.txt
.venv/bin/python review/analyze_repo.py     # -> review/module-map.json, review/http-and-db.json
.venv/bin/python review/build_indexes.py    # -> review/module-inventory.md, review/docs-index.md
.venv/bin/python -m pytest -q               # suite state above
```

The application itself starts with `./run.sh` and serves `http://127.0.0.1:4760`, but it expects
a local ComfyUI, a local Qwen gateway and a shared VRAM Manager, and it owns a live production
database — so it is not expected to be run for this review. Reading `studio/`, `tests/` and
`docs/` plus `review/module-map.json` is sufficient.

## Integrity of the generated artifacts

```
190ec25e00fbff2f1962da0fdcc4bed651e22a68939bf0ffbae85606abb96cf0  review/module-map.json
68acf3b9c53b21cccd36e2bb3b28b70a857cbe2c88e60f8dbf501b5ddf9e92c4  review/http-and-db.json
5e85077a25f9646f8f10a33efcc10297f5cf3ee8707bbdee582d1a8168ed3609  review/module-inventory.md
410f3571ab3e897d9ff5903ea659f5d3c4d9ddaae49d0377507c4c726a36cebc  review/docs-index.md
7c70723efadb22e828cdab15f1ce650c7a109b7ead4328c458859b58e8196c32  review/pytest-2026-09-17.log
30d3953854feaaaeaa0b68bbdfae3c9c4857e057e004ef3a136885b301a6d2f8  ARCHITECTURE.md
b4cdb147d56952d0739d5191d05d425157d6a5716768781e89077865eb0619a2  REVIEW_BRIEF.md
```

`review/http-and-db.json` and `review/docs-index.md` keep their original digests, which is the
expected result of a regeneration that changes nothing in them.
