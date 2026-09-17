# Continuity Studio — architecture map (review snapshot)

> Generated for an architecture review of the code in this snapshot. Every number below was
> measured from this tree with `review/analyze_repo.py` + `review/build_indexes.py`
> (rerun both to reproduce: see "Reproduce the numbers"). Claims about *intent* are quoted
> from the project's own docs/source; nothing here is inferred from anything outside this snapshot.

## 1. What the application is

A single-user, loopback-only FastAPI + SQLite application that turns a story idea into
production-ready visual planning and prompts: idea → story → screenplay → cast/locations →
scenes → shots → storyboards/keyframes → image prompts → real image generation and human
review → MiniMax H3 (Ref2VA) video prompts, with a final local ComfyUI render path.

It is not a library and not a service mesh: one process, one data directory, one SQLite
database, one browser SPA, plus outbound calls to *replaceable providers* (Astra via the
local Codex CLI by default, HTTP providers, a local Qwen gateway, ComfyUI, a shared VRAM
Manager). `README.md` is the product/run summary; `docs/` is the project's own record.

## 2. Measured size of the snapshot

| area | files | lines | notes |
| --- | ---: | ---: | --- |
| `studio/` (flat Python package) | 83 modules | 15,219 | 42,007-byte `app.py`, 63,843-byte `engine.py` |
| `tests/` | 102 test files | 13,294 | plus `tests/fixtures/` |
| `static/` (browser SPA) | 42 `.js` + 3 `.css` + 2 `.html` | — | `app.js` alone is 142,873 bytes |
| `scripts/` | 64 `.mjs` + Python | — | number-prefixed UI/behaviour checks run by Node |
| `docs/` | 44 files | — | `STATE.md` 271 KB, `DECISIONS.md` 98 KB, `ACCEPTANCE.md` 63 KB |
| `workflows/` | Studio-owned ComfyUI workflow copies + `OWNERSHIP.md` | — | "never require external workflow JSON at runtime" |
| `skill-packages/`, `extensions/`, `studio/bundled/` | method bundles | — | package must stay byte-identical to `studio/bundled/` (`tests/test_skill_package_sync.py`) |

Test code is ~87 % of the line count of application code.

## 3. Runtime shape

```
browser SPA (static/, 42 JS modules, zh-Hant default)
        │  64 HTTP routes, all in studio/app.py
        ▼
studio/app.py  ── route handlers ──► studio/engine.py  (job execution)
        │                                   │
        │                                   ├─ chapter_pipeline / directing_pipeline /
        │                                   │  generation_pipeline / storyboard_board
        │                                   ├─ comfy_images / local_images (image jobs)
        │                                   └─ video_workflow / video_render / h3_render_graph
        ▼                                   ▼
studio/store.py (SQLite, WAL)      studio/providers.py (22 capability names)
data/studio.sqlite3 + data/jobs/…  kinds: codex │ http │ manual
```

* Entry point: `run.sh` → `uvicorn studio.app:app --host 127.0.0.1 --port 4760`
  (`STUDIO_DATA`, `STUDIO_PORT` override). One data directory may be owned by one server
  only — enforced by an `fcntl` lock on `data/server.lock` in the FastAPI `lifespan`.
* `studio/app.py`: 64 routes, **51 internal module imports**, and the app `lifespan`
  (lock + `store.init()` + `postproduction.init()` + `video_render.init()` +
  `engine.start_pending()` + `comfy_recovery.start()`).
* `studio/engine.py`: the job executor; **43 internal imports**, one module. It owns
  `POOL = JobPool()`, plan persistence (`save_plan`), job dispatch, image/asset requirements,
  and restart handling.
* Explicit job lanes (`studio/job_queue.py`): three bounded `ThreadPoolExecutor`s —
  `text` ×2 workers, `chapter` ×1, `image` ×1 — so "a renderer cannot occupy a text worker".

## 4. Domain model and persistence

Seven tables, all created by one `executescript` in `studio/store.py` (105 lines):
`projects, revisions, jobs, assets, settings, events, story_chapters`.

* `projects.production` and `revisions.production` are **JSON blobs in TEXT columns**;
  `store.row()` decodes `production`, `input`, `result`, `reference_ids`, `review` on read.
  The project carries `revision` (int) and jobs carry the revision they were planned against.
* `revisions` is an append-only version history (`UNIQUE(project_id, number)`) with a `reason`.
* `assets` carry `dependency_hash`, `reference_ids` (JSON), `status`, `review` (JSON),
  `source_asset_id`, `job_id`. Reference invalidation is hash-driven: "Replacing or rejecting a
  reference invalidates dependent work; nothing is deleted" (README).
* `shot_state.py` (359 lines) is described by its own docstring as the
  "Canonical state compiler and mandatory, durable Production pre-commit gate"; a compiling
  canonical shot state (`canonical-shot-state-v1`) is the "sole authority" per
  `docs/CANONICAL_SHOT_STATE.md`.
* Schema evolution is inline and idempotent: `store.init()` re-`CREATE TABLE IF NOT EXISTS`
  then `PRAGMA table_info` + `ALTER TABLE` for each added column. There is no migration
  version table and no down-migration path (see question A5).
* One connection per operation (`store.db()` context manager, `timeout=30`, WAL,
  `foreign_keys=ON`); a request-scoped read cache exists for job history only
  (`store.reuse_job_reads`).

## 5. Job and state model

`jobs.state` is text: `queued`, `running`, `awaiting_input`, `interrupted` (plus terminal
states written by the executor, e.g. `cancelled`/failed paths). At startup `store.init()`
rewrites any left-over `running` row to `interrupted`, and `engine.start_pending()` re-queues
`queued`/`interrupted` work — "Never auto-resubmit running work".

Cancellation is deliberately split: `queued` → immediate `cancelled`; a `running` job gets a
`cancel-requested` marker and is finalised as "did not adopt this result" on restart
(observed contract, documented in `.hermes` ops notes and reflected in the code path).

## 6. Provider abstraction

* `studio/providers.py` (253 lines): `BUILTINS` lists **22 capability names**
  (e.g. `narrative`, `storyboard`, `directing_qc`, `image_prepare`, `image`, `image_review`,
  `h3_scene`, `h3_shot`, `h3_global`, `h3_guidance`, `h3_video_prompt`, `voice_defaults`,
  `qc`, `storyboard_frames`, `h3_group_plan`, …). Routing is stored in `settings['routing']`;
  `resolve(capability)` picks a provider, `supports()` matches `provider['capabilities']`.
* Three provider kinds (`studio/models.py`): `codex`, `http`, `manual`. The default is
  `Astra · Codex` (`gpt-6-astra`), executed as
  `codex exec --ignore-user-config --ephemeral --skip-git-repo-check -s workspace-write|read-only
  -m <model> --json --output-schema <schema> -o <output>` — i.e. **the capability contract is a
  JSON schema passed to a CLI agent**, with `strict_schema` applied for codex providers.
* Context budgets are per kind (`studio/context_limits.py`): codex 131,072, deepseek 1,048,576,
  http 32,768.
* Documented invariant (README, AGENTS.md, `docs/STATE.md`): **no silent fallback, no automatic
  downgrade** to a weaker/local model; a refused provider is retried once after an explicit
  VRAM-manager warm (`providers.warm_local_qwen`, receipt `<work>/qwen-warm.json`) and then
  re-raised honestly.
* GPU work is never started directly: the app calls the shared VRAM Manager
  (`/vram/status`, `/vram/gpu/acquire|release`, `/vram/comfy/mode|recover`, `/vram/qwen/warm`).

## 7. Knowledge layer (prompts are data)

* `studio/bundled/` holds four versioned method bundles: `studio-production-methods`,
  `director-skill` (20 director styles), `editorial-knowledge`, `short-drama-storyboard`.
* `skill-packages/continuity-studio/` is a *derived, byte-for-byte* copy of those bundles for
  external agents; `scripts/export_skill_package.py` derives it and
  `tests/test_skill_package_sync.py` fails on drift.
* `studio/skills.py` (704 lines) is a deliberately dependency-free registry: it discovers
  `SKILL.md` directories from `~/.agents/skills`, `~/.codex/skills` and `extensions/`, installs
  them as content-hashed snapshots, and copies **only** `SKILL.md` and `references/**/*.md|txt`
  under a 1 MB cap, with no scripts/symlinks. Its docstring states the design goal explicitly:
  "No imports from other studio modules (bounded, self-contained)."
* `workflows/` keeps complete Studio-owned copies of the ComfyUI graphs plus `OWNERSHIP.md` and
  `inventory.json`/`runtime-schemas.json`; `tests/test_workflow_ownership.py` enforces that the
  app never depends on external workflow files at runtime.

## 8. UI layer

`static/` is a hand-rolled SPA (no framework, no build step): `app.js` (142 KB) plus 41 focused
modules (`directing-plan.js`, `generation-groups.js`, `storyboard-board.js`, `video-render.js`,
`editorial.js`, `locale-zh.js`, …) and `style.css` (43 KB). Every route is server-rendered JSON
behind 64 FastAPI endpoints. `scripts/*.mjs` (64 files) are Node-based behavioural checks that
exercise the real frontend modules — a second test surface beside pytest.

## 9. Test and evidence culture

* 102 pytest files / 13,294 lines; `tests/conftest.py` installs an **autouse offline boundary**
  that neutralises the canonical-state compiler unless a test carries the `canonical_state`
  marker, and forbids implicit provider calls ("A test must explicitly supply its canonical
  semantic provider").
* `pytest.ini` declares one custom marker (`canonical_state`) and excludes `backups`, `.venv`.
* `docs/STATE.md` + `docs/DECISIONS.md` + `docs/ACCEPTANCE.md` are append-only dated journals:
  each entry states what was measured, what was *not* verified, which tests passed, and where
  the evidence JSON lives (`data/acceptance/…` — excluded from this snapshot).
* No CI configuration, no linter/formatter config, no type-checker config, no `pyproject.toml`
  exists in the snapshot; `requirements.lock.txt` pins the runtime to exact versions.

## 10. Structural characteristics worth challenging

These are measured observations from this snapshot, phrased as the questions they raise.
They are the intended focus of the review.

1. **`app.py` is a single router module**: 64 routes, 675 lines, 51 internal imports. It is
   simultaneously the HTTP surface, the thumbnail/image-serving layer, zip export, settings
   and provider administration. There is no router/package split (`studio/*.py` is flat, with
   only `bundled/` as a subpackage).
2. **`engine.py` holds the entire job executor**: dispatch, plan persistence, canonical
   pre-commit, image requirement, recovery, and 43 internal imports in 719 lines. Conversely
   `job_queue.py` (43 lines) owns only lanes. Is "job execution" one responsibility or several?
3. **Two hub modules dominate everything**: `store` is imported by 58 modules and `models` by
   29. `continuity` (18), `engine` (15), `asset_roles` (15), `asset_library` (13) follow.
   Everything reaches the database and the domain contracts through these two; any change to
   them is a global change.
4. **Flat 83-module package with no layer subpackages**: naming (`chapter_*`, `directing_*`,
   `editorial_*`, `h3_*`, `comfy_*`, `video_*`) is the only grouping mechanism, and several
   prefixes hold 6–10 modules. An import-linter or explicit layer rule does not exist.
5. **Schema evolution is hand-rolled** (`PRAGMA table_info` + `ALTER TABLE` in `init()`, no
   version table); the project JSON blobs have no schema version field comparable to
   `canonical-shot-state-v1`, while other artifacts do (`chapter-stages-v2`,
   `studio-local-images-v6`, `generation-stages-v1`).
6. **Concurrency is three global thread lanes with no per-project fairness**; `JobPool` reads
   the job from the database to pick a lane at submit time, and `store.db()` opens a fresh
   connection per operation with a 30 s timeout. What happens under a long image job plus
   several waiting text jobs is a real design question, not a hypothetical one.
7. **The 22-capability router is data-driven but the capability *shapes* are code**: each
   capability still has bespoke branching in `engine`/pipelines (`capability=='shot_state_prepare'`,
   `capability=="storyboard_frames"`, `capability=='voice_defaults'`, …). Is the capability
   abstraction actually uniform, or a thin wrapper over per-capability special cases?
8. **26 of 83 modules have no textual reference from any test file** (see
   `review/module-inventory.md`), including `shot_prompts`, `scene_prompts`, `guidance`,
   `directing_auto`, `job_queue`, `take_lifecycle`, `voice_defaults`. Each may be covered
   indirectly, but the mapping is not explicit.
9. **Code style is compressed**: `import json, shutil, threading, traceback`, semicolon-joined
   statements (56 in `engine.py`, 49 in `editorial_pilot.py`), 96 lines over 120 chars in
   `engine.py`, no spaces after commas in many modules. This is self-consistent across the
   whole tree but is outside PEP 8 and outside what most static tooling expects.
10. **Docs are the de-facto architecture record**: `docs/STATE.md` (271 KB) is append-only and
    arguably the highest-value artifact in the repo, but it is neither indexed nor chunked, and
    the newest entry is at the *top*. A reviewer or a new agent must read it linearly to find
    the current truth. `docs/DECISIONS.md` (98 KB) has the same shape.

## 11. Reproduce the numbers

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.lock.txt
.venv/bin/python review/analyze_repo.py      # review/module-map.json, review/http-and-db.json
.venv/bin/python review/build_indexes.py     # review/module-inventory.md, review/docs-index.md
.venv/bin/python -m pytest -q                # suite state recorded in SNAPSHOT.md
```

`review/module-map.json` contains the full per-module record (LOC, bytes, internal imports,
importers, docstring, style counters, test references) and `review/http-and-db.json` the full
route and table lists, so any figure above can be re-derived mechanically.
