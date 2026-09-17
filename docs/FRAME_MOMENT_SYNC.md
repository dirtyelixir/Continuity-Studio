# Frozen-moment synchronization

The primary authoring and synchronization boundary is now [canonical shot state](CANONICAL_SHOT_STATE.md): extraction/compilation and independent semantic validation run before a formal Production revision is written. This module remains the render-stage safety net and legacy reader, not the normal resolution of independently authored frame state.

The diagnosis exposed two separately authored descriptions of the same instant: `frame_01_start.description` said Pip looked at the lantern base while `shot_01.start_state` said Pip looked at Ada. Structural Production validation checked IDs, times and shapes; it could not compare the meaning of those two strings. Image preparation previously treated them as equal authorities, so its single conflict re-evaluation correctly refused to choose. The defect entered production revision 10, before the image jobs.

## Authority and generation

For new frame preparation, the versioned frame moment contract gives the exact structured start/end/interior state authority over explicitly specified dynamic facts (eyeline, pose, hand/prop ownership, power, damage and reveal). The keyframe description supplies composition and compatible additional detail. This is a scoped rule; it does not turn every arbitrary state string into an infallible fact or override explicit revision requests. Timed beats remain interpretation context, never an instruction to depict several instants.

The configured image preparer aligns stale descriptive dynamic detail automatically and records the original phrase and applied state in omitted_context. Original production, source snapshots and earlier results remain historical records. No regular expressions guess the meaning of creative prose. Upstream production/revision requests explicitly require affected states, beats and keyframe descriptions to be updated together. Directing review explicitly checks their consistency before adoption.

Before a new frame reaches its real renderer, the same configured preparer performs a separate text check of the ACTUAL compiled brief against its moment, timeline and requested changes. An actionable revise result triggers at most one complete image-brief correction and one recheck. An uncertain check, a failed correction or unresolved authoritative conflict stops before rendering. This adds a text check per new frame execution; it does not regenerate or charge for media on a failed preflight. Image review still evaluates the actual resulting pixels, since text consistency cannot guarantee model execution.

## Persistence and recovery

The preparation's moment-alignment.json retains its source/result association and model reconciliation notes. Engine image jobs persist final alignment and image_moment_verification before submitting a renderer. moment-check/, moment-repair/ and moment-recheck/ retain provider outputs. moment-verification.json records attempt intent before calling the provider; incomplete/failed work cannot silently repeat on recovery. Accepted recovery verifies source, provider, references, input/output hashes and compiled text. Historical jobs without this contract are not relabelled checked.

Explicit image_prepare jobs use the same preparation and verification path. The full job endpoint exposes a read-only preflight receipt, including a failure before render-stage input was written. Job details show the preflight outcome and reconciliation notes above technical records. These receipts certify a model text check, not human approval or successful media production.

## This incident

The source timeline has Pip watching Ada at the opening and at 4.8 seconds, then lowering its lens toward the switch during 6.2–8.0 seconds. A corrected opening brief therefore keeps Pip looking at Ada and the lantern off. Opening-v002/v003 are preserved but stale; v003 visibly has an illuminated bulb. The old failed jobs remain failed historical receipts. New work derives its moment contract from current source and does not require manually replacing the contradictory descriptive sentence.

Acceptance evidence is in data/acceptance/moment-sync-20260913/. Deployment and actual-provider evidence are reported in docs/STATE.md after verification completes.
