# Resumable chapter proposals

Studio uses `chapter-stages-v2` for new non-manual narrative/storyboard jobs targeting a story chapter. Single-work and manual production contracts remain unchanged. The original user-selected capability resolves a provider once; all internal stages use that frozen provider/model, original source, mandatory production method and extension instructions. Internal schemas are not separately selectable routing capabilities.

## Execution and review

1. Save chapter writing, canon and scene descriptions. With an adopted chapter, matching adopted source/writing provenance and no rewrite feedback/candidate revision, reuse the exact frozen writing and canon, recording `origin=adopted-writing`; otherwise Astra writes this bounded foundation.
2. Astra plans dramatic beats and concise shot briefs separately for each scene. Each scene is checkpointed, with globally unique IDs and a total chapter limit of 40 source shots.
3. Full shots are produced sequentially in batches of at most three, with the saved outline, original request and earlier shot boundaries in context. IDs, scene, entity membership, duration and beat links are frozen by the outline. Timing, entity, frame-ID and direction-link checks run before saving each batch.
4. Finalization plans ordered edit ranges and complete source coverage. For more than 80 source units, or recovery of a truncated legacy final, Studio saves the edit order separately and maps source units in batches of at most 80. Each substep is independently checkpointed; any cross-batch missing-shot links receive a sparse coverage correction. Full production, director-plan and source checks still run before assembly. Completed legacy finals (including valid raw results saved before a crash) retain their original contract.
5. Existing independent `directing_qc` reviews the assembled candidate. Adoption still requires passing QC, matching source/revision/direction and explicit user adoption. Partial stages cannot be adopted and create no media.

## Durable continuation

Each job owns flat attempt directories beneath `data/jobs/<id>/`, plus atomic JSON checkpoints. Every checkpoint binds the original full input, stage prompt/schema and result hash. Existing canonical asset scope is restored deterministically if a provider tries to reclassify it; checkpoints list restored scope IDs while raw provider output remains unchanged. Actual canon description/fact changes still fail validation. Raw results are preserved even on validation failure. A valid raw result written before a crash can be validated and checkpointed without a new provider call. A checkpoint mismatch fails closed.

Transport failure stops immediately, retaining completed stages. A stage may receive one structural correction per execution; no automatic transport retry or provider fallback is added. Codex itself retains its existing bounded transport retry policy. Each provider call retains the 20-minute total deadline; a complete multi-stage job may exceed 20 minutes while saving meaningful intermediate progress.

The job row and detail modal show stage/shot progress. `POST /api/jobs/<id>/resume` queues the same failed/interrupted job and skips validated stages. It uses the original provider even when routing has changed. Resume rejects cancellation, another active job for the same capability/target, source/revision/direction changes, method changes and incompatible pipeline versions. A changed creative direction needs a new proposal. Original v1 global-outline jobs retain their original resumable stage contract; v2 uses writing plus per-scene planning. During structural correction the UI explicitly says it is correcting returned output. Ordinary server startup marks in-flight jobs interrupted; queued jobs retain their original IDs and inputs and are dispatched by the existing queue recovery.

Older monolithic failures have no staged checkpoints; retry creates a new staged job. Existing originals stay intact. The UI distinguishes continuation from creating a fresh proposal.

## Long request delivery

The Codex adapter now reads its already-frozen `request.txt` through file-backed stdin. The former one-second `communicate(payload)` loop changed to `communicate(None)` after timeout. On this Python runtime a slow reader could leave a long pipe input partially written forever. A 200,000-byte delayed-reader reproduction stalled at 65,536 bytes; the fixed adapter regression verifies a larger Unicode request reaches a real delayed child byte-for-byte. This is a confirmed local defect, not proof that both historical provider stalls had that cause. No model, auth, provider transport setting or GPU service changed.

## Limits

This saves stage completion, not model-internal reasoning or partial JSON. A failed stage may still need a fresh model call. Status describes saved progress and cannot prove remote model activity. Full source context is retained in each stage for continuity; this increases aggregate input usage. Quality, complete story coverage and inter-shot performance remain subject to independent director review and user adoption. A blueprint requiring creative revision must be regenerated; later stages cannot silently change it.

Acceptance records: `data/acceptance/chapter-stages-20260910/`.

## Real acceptance refinement

The first live v1 outline returned 62,767 bytes after about 10.6 minutes, with 7 scenes and 39 shot briefs. Its only canon differences were asset scope metadata; the original validator rejected these and launched a long correction without showing that change of activity. Agent stopped only its own acceptance job, preserved the raw output, verified it passes when canonical scopes are restored, and refined the default workflow to v2. Do not describe this v1 attempt as a transport timeout: it returned a real output and was explicitly cancelled during correction. Both historical user attempts remain unchanged.

Adoption stores a per-chapter source/writing receipt. Existing chapters may use the verified historical adoption job as a compatibility receipt. Missing/mismatched provenance, edited drafts/outlines and restored older writing disable automatic writing reuse; Astra receives the current request instead.

The real v2 chapter job `04e0bf5c885b4c11` completed all 23 stages: one reused writing checkpoint, seven scene plans, fourteen shot batches and one edit plan. It produced seven scenes, 40 full source shots and 40 edit decisions in 3,651 seconds. All 22 Astra calls succeeded on their first stage attempt; the longest took 233.85 seconds. Total chapter time is still substantial, but no individual call approached the 1,200-second deadline. Story, screenplay, canon, title, logline and style match the adopted writing exactly. Existing production remains revision 4 and unadopted; independent review is recorded separately in the acceptance evidence.


## DeepSeek HTTP transport (2026-09-13)

DeepSeek stages request SSE, handling keep-alive comments and saving received content separately as provider-partial.txt. A successful stop and DONE terminal are required before result.json can be written; partial output is not a checkpoint and cannot resume mid-JSON. transport.json records safe counters/timing without credentials or reasoning text. The generic statement above about a 20-minute deadline refers to Codex: HTTP retains its 900-second read timeout, with additional cancellation/elapsed checks between SSE lines and at completion. A silent read can block until that read timeout. No automatic transport retry or provider fallback is introduced. One exact previously failed first-stage request passed live transport/schema acceptance in 84.89 seconds; the original production and historical failures were preserved.

## Final-stage length recovery (2026-09-13)

A 663-unit chapter repeatedly exhausted DeepSeek output while returning the combined edit table and source coverage. The three partial responses stopped around P332, P356 and P572. Resuming the same oversized final request could never guarantee completion, even though all 40 shots and the preceding 22 checkpoints were intact.

Finalization now uses versioned flat keys (`23-edit-bounded-v1-order`, `…-coverage-001`, etc.) beside untouched legacy attempts. Original stage prompts, schemas, full-input hashes and saved results remain unchanged. Partial JSON is diagnostic evidence only. The outer progress remains 22/23 until assembly, with separate saved finalization counts and source-unit progress. A resume skips completed order/coverage steps and uses the same frozen provider. Rows with saved stages prioritize continuation and hide the adjacent start-over action; with all shots saved the action reads 接續剩餘整理.

Regression coverage includes a truncated second coverage batch, preserved checkpoint bytes, migration from a truncated legacy final, complete legacy raw-result recovery, cross-batch link repair and rejected foreign/tampered source and shot links. Acceptance evidence is in `data/acceptance/chapter-final-resume-20260913/`.

Live acceptance completed the original DeepSeek job `e2126da10989427c` at 13:19:55 HKT: 10 finalization substeps across 13 complete provider calls, including three successful structural corrections (JSON syntax, source ordering and an invalid shot link). There was no truncation. All 663 source units are covered; 40 saved shots and 22 original checkpoint hashes are unchanged. Existing adopted production remains revision 5 unchanged. The independent director review was automatically started; the candidate has not been adopted.
