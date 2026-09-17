# Architecture review — Continuity Studio

This repository is a **snapshot of a working local application** handed over for an
architecture and design review. `ARCHITECTURE.md` is the measured map of the code;
`review/` holds the generated inventories; `docs/` is the project's own record.

Please review the **architecture and design decisions** — module responsibilities, coupling
between them, and how the production pipeline is layered. Implementation-level pickiness
(style, naming, formatting) is known and deliberately out of scope except where it signals a
structural problem.

## How to read this snapshot efficiently

| Step | File | Why |
| --- | --- | --- |
| 1 | `README.md` | what the product is and what a user does with it |
| 2 | `ARCHITECTURE.md` | measured module map, data model, job model, provider model |
| 3 | `review/module-inventory.md` | all 83 modules with LOC, deps, importers, test refs |
| 4 | `docs/DECISIONS.md` (first ~150 lines) | the decisions that were made and why; ordering is only approximately reverse-chronological |
| 5 | `docs/STATE.md` (first ~3 sections) | newest live state; append-only, newest at the top |
| 6 | `studio/app.py`, `studio/engine.py`, `studio/store.py`, `studio/providers.py` | the four structural centres |
| 7 | `studio/shot_state.py`, `studio/job_queue.py`, `studio/models.py` | canonical-state gate, lanes, domain contracts |

`review/module-map.json` has the machine-readable version of everything in step 3, including
per-module docstrings, import lists and style counters.

## What is intentionally this way (please don't "fix" these)

* **Single-user, loopback-only desktop tool.** No auth, no multi-tenancy, no horizontal
  scaling, no network exposure. Binding is `127.0.0.1` and one process owns one data directory
  via an `fcntl` lock.
* **Local-first models.** Default intelligence is Astra over a local Codex CLI login; local
  Qwen, ComfyUI and a shared VRAM Manager are explicit execution dependencies. No cloud API is
  required on the default path and no silent downgrade is allowed.
* **SQLite + JSON blobs** rather than an ORM or a document store: one file, one writer, WAL.
* **No frontend build step** (hand-rolled ES modules) and **no CI/lint/type-check config** in
  the snapshot; both are conscious choices, not omissions to be patched casually.
* **Canonical-state pre-commit gate** is a hard product requirement: nothing durable is written
  when the canonical shot state does not compile.

## The questions we actually want answered

**A. Module responsibilities and boundaries**

1. `app.py` = HTTP surface + 64 routes + image/thumbnail serving + zip export + settings and
   provider admin, with 51 internal imports. Where should the seams be, and would splitting it
   into per-capability routers genuinely reduce coupling or just move it?
2. `engine.py` = job dispatch + plan persistence + canonical pre-commit + asset requirement +
   recovery + restart reconciliation (43 internal imports). Is "job execution" one
   responsibility, or should this decompose into *runner*, *job-type handlers*, and
   *plan persistence*? What is the smallest cut that still keeps restart behaviour correct?
3. `store` (imported by 58 modules) and `models` (29) are universal hubs. Is that acceptable
   for an app this size, or is the real problem that *domain logic* leaks into these two?
4. 83 flat modules with prefix-grouping only (`chapter_*`, `directing_*`, `editorial_*`,
   `h3_*`, `comfy_*`, `video_*`). Would layer subpackages + an enforced import rule help, or
   is the flat layout the right trade-off without tooling to enforce anything?
5. `skills.py` is deliberately self-contained (no internal imports) while nearly every other
   module is hub-dependent. Should that pattern (bounded, dependency-free subsystem) be the
   template for other subsystems — for example provider adapters, or the editorial stack?

**B. Coupling and data flow**

6. Capability routing is data (`settings['routing']`, 22 capability names) but the *shapes*
   of those capabilities are code (per-capability branching in `engine`, `chapter_pipeline`,
   `generation_pipeline`, …). Is the capability abstraction earning its keep, and what is the
   right seam between "route a capability" and "know what that capability returns"?
7. Reference and dependency invalidation is hash-based (`assets.dependency_hash`,
   `reference_ids`, `source_asset_id`, project `revision` + `brief_revision`). Is there a
   single component that *owns* invalidation semantics today, and if not, should there be one?
8. There are four partly overlapping pipeline stacks — `chapter_pipeline`, `directing_pipeline`,
   `generation_pipeline`/`generation_groups`, and `storyboard_board`/`video_render`. Where do
   they genuinely differ, and where is the same idea implemented twice? Which one should the
   others be expressed in terms of?
9. `shot_state.py` is described as the canonical compiler **and** the mandatory durable
   pre-commit gate. Should compilation and the write-gate be one component, given that every
   post-canonical feature must go through it?

**C. Persistence, concurrency, job model**

10. Schema evolution is hand-rolled (`PRAGMA table_info` + `ALTER TABLE` inside `init()`), with
    no migration version table; artifact versions are tracked per-feature
    (`canonical-shot-state-v1`, `chapter-stages-v2`, `generation-stages-v1`,
    `studio-local-images-v6`). Is that the right layered compromise, and what would a minimal
    honest migration mechanism look like here?
11. `JobPool` = three global bounded lanes (text×2, chapter×1, image×1) chosen from the job row
    at submit time; `store.db()` opens one connection per operation (WAL, 30 s timeout).
    Under a long image job plus many queued chapter jobs, what fails first and what should the
    lane policy actually be? Is per-project fairness worth it?
12. Job lifecycle is deliberately split: `queued` cancels immediately, a `running` job gets a
    marker and is settled on restart as "do not adopt this result"; startup rewrites `running`
    → `interrupted` and re-queues `queued`/`interrupted`. Is this state machine complete, and
    where would a crash *between* those steps leave the system in a state nobody tests?
13. Evidence/provenance is written per artifact (`data/jobs/<id>/`, `data/acceptance/<slug>/`),
    and `docs/STATE.md` records what was *not* verified. Should provenance be a first-class
    table/key in the data model instead of a convention?

**D. Testability and the shape of the safety net**

14. 102 pytest files (13,565 lines) against 83 modules (15,305 lines), plus 64 Node `.mjs`
    front-end checks. `tests/conftest.py` neutralises the canonical compiler unless a test is
    marked `canonical_state`. Does that autouse boundary hide integration risk, and where
    should the real end-to-end seam be instead?
15. 26 modules have no textual test reference. Does the test suite's shape match the
    architecture's risk (which modules are *actually* load-bearing), or is it distributed by
    whatever was easiest to test at the time?

## What a useful answer looks like

* Findings ordered by **architectural cost**, each tied to a concrete file (and line where it
  matters), with the *specific* change and what it breaks.
* Where you think a boundary is wrong, say what the boundary should be and which existing
  behaviour would need to move — not just "extract a service".
* Distinguish **"this will hurt at 3× the size"** from **"this is wrong now"**.
* If you think the current structure is right for the constraints, say so and name the
  constraints you used. A short "no change" verdict is a valid review result.
* Known-unknowns list: what you could not judge from the snapshot (see `SNAPSHOT.md` for what
  is deliberately excluded — no database, no generated media, no runtime services, no git
  history).
