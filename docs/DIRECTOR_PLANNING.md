# Director planning — Continuity Studio 0.1

Scene → dramatic beats and directorial intent → purposeful source Shots → independent directing QC → storyboard image production / H3 execution → source video → planned edit decisions.

## User workflow

Use the existing new/revised production proposal entry, including imported stories/screenplays and individual series chapters. New proposals must contain the formal director layer. Automatic text providers enqueue an independent `directing_qc` job after the proposal completes, using the configured reviewer (Astra by default). Review failure or unavailable service retains the candidate and blocks adoption; no fallback or media production occurs. Manual proposals expose an explicit review action, using the same routed QC capability. A manual QC provider can submit the structured review through the existing manual job UI.

The proposal dialog shows audience knowledge, emotional intent, visual priority, reveal order, each Shot's purpose/carrier/cut reasons, source duration and planned edit duration. It shows the review's exact source evidence and recommended repairs. `按意見修訂方案` references the saved candidate server-side and uses the current provider to create another reviewable proposal; source text, current canon, revision and chapter scope remain authoritative.

The production handbook contains `導演規劃與剪接`. Change numeric in/out points (fractional seconds), cut reasons and cut-point continuity notes; reuse a source, move an edit earlier or remove a redundant use. Source Shots still needed for the planned coverage must retain at least one edit use. Saving creates a revision and requires renewed semantic review. Source footage is retained. The shot page and proposal show the primary purpose. Existing Shot editing also exposes that purpose.

## Durable contract

Stored inside the existing canonical Production JSON in SQLite and revision history:

- `Scene.director_plan.beats[]`: stable local beat ID, event and `intent` containing audience_knowledge_before, audience_must_learn, emotional_target, visual_priority, reveal_strategy and coverage_strategy.
- `Scene.director_plan.reveal_order`: an explicit permutation of this scene's beat IDs.
- `Shot.shot_purpose`: one primary purpose. `Shot.direction` links the scene's beats and canonical subjects, and records visual_carrier, readability, cut_in_reason, cut_out_reason and next_shot_relationship. Several beats may serve one purpose; punctuation or a CU quota cannot detect overload.
- `Shot.generation_duration`: explicit for new proposals, equal to legacy `duration`, which remains the source-generation timing used by H3, timed actions/dialogue and voice. Studio's existing 4–15-second source constraint remains an application contract, not a newly asserted provider limit.
- `Production.edit_plan[]`: ordered id, shot_id, planned_edit_in, planned_edit_out, cut reasons and continuity_note. Multiple entries can reference the same source Shot. Screen duration is derived as out minus in, never a conflicting editable duration. Derived timeline positions are exported.

Each source Shot is one continuous setup/take. A new setup needs its own source Shot; a new edit use of existing source footage does not. A 5-second source may contribute only seconds 1.8–3.4 (1.6 seconds on screen). The planner must locate required actions and dialogue inside selected ranges. Cut-point states must be considered separately from full source endpoints. Text keyframe descriptions remain drafts in the proposed production; actual keyframe generation and H3 preparation for formally planned scenes require current passing QC.

Legacy missing/null fields remain unplanned history, with no fabricated intent, timing or pass verdict. Existing workflows continue until the user requests a new proposal. Empty compatibility fields are omitted from historical keyframe dependency hashes, preserving existing approved references. A series may contain old unplanned chapters alongside newly planned chapters. Merge namespaces scene/shot/edit IDs and preserves local beat references, unaffected chapters, canon and existing asset records.

## Review and freshness

`directing_qc` returns one evidence-linked coverage judgment per planned scene/beat plus specific issues such as SHOT_OVERLOADED, UNREADABLE_CARRIER, REVEAL_ORDER and EDIT_RANGE. It evaluates readability and causal/emotional communication, not counts of CU/insert/reaction shot types. A readable two-shot or continuous reframing can pass without an extra cut. Pass requires every coverage judgment to pass and no reported issues. Evidence must be a single literal source excerpt, with explanations in separate fields.

Structural checks validate finite ranges, source duration equality, unique IDs, local beat/subject links, full planned-beat/source coverage and exact evidence. They do not prove semantic truth or generated visual quality. Automated review has at most one correction for malformed schema/link/evidence output; both original and correction are retained. It never retries merely to turn a revise/uncertain verdict into pass. Network failures are not retried by that correction path.

Review jobs freeze the complete candidate and production-method hash. Adoption requires a current passing review for new proposals. Adopted per-scene review records bind source story/screenplay, canon, scene, source Shots, applicable edit order/ranges and the review method. Changes invalidate review; stale findings stay in history. Keyframe preparation and H3 generation/preparation are gated for changed planned scenes. Explicitly selected video takes remain separately recorded; source video identity is not replaced by a trim edit.

## Handoff and ownership

New rules live in Studio's mandatory hash-pinned production-method bundle v1.1.0, alongside the existing Studio-owned short-drama shot-craft snapshot and DirectorSKILL style modules. The new formal contract is authored from the user's requirements; no external skill or workflow JSON is loaded at runtime. Provider selection does not disable the contract.

Downstream writers receive the adopted Shot purpose, direction and scene intent. Keyframe preparation receives scoped readability/reveal constraints and freezes the source endpoint. H3 performs the adopted continuous setup; it cannot independently invent another reveal or coverage plan. Existing image/video and dialogue validation remains in place; compliance of actual generated performance still requires visual review.

ZIP export includes `director/plan.json`, `director/plan.md`, `director/review.json` and `edit/plan.json`. Repeated edits reference the same Shot and, when available, the same selected/current successful source MP4. Absent/stale/unselected takes are not represented as available footage. All ranges are explicitly `planned_unverified`: this feature does not render a final edit or automatically verify precise usable points in generated footage.

## Acceptance

Evidence directory: `data/acceptance/director-planning-20260910/`.

- Full `python -m pytest tests -q`: 489 passed before the final bounded-review correction and additional integration checks. Focused final verification is recorded in the evidence file.
- The root collection command also found the user's complete backup tree and reported duplicate test modules; explicit `tests/` scope avoids executing backup copies. Backups were not altered.
- Browser on isolated storage at port 4761: purpose/intent/review visible; 6-second source and 1.6-second edit displayed independently; changing out point to 3.5 updates screen duration to 1.7 and invalidates QC; reusing the source adds a second edit while retaining one source Shot.
- Real Astra forward case and semantic reviewer evidence are saved separately from test fixtures. No image, voice or video rendering is part of these acceptance runs.

Final checks: 87 directing/relationship/legacy/chapter tests and 95 downstream/H3/image/workflow tests passed after the final corrections. Real Astra normal case passed after a single evidence-format repair; a second, deliberately unreadable reaction case was rejected with UNREADABLE_CARRIER. Live idle deployment preserved all database table rows and passed integrity checks. See verification.json and deployment.json.
