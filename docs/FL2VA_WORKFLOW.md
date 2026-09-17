# H3 frame workflow — research and product decisions (2026-09-09)

## What the evidence supports

- [MiniMax H3 official repository](https://github.com/MiniMax-AI/MiniMax-H3): the base FL2VA family supports zero, one or two frame inputs. Studio offers explicit I2VA (opening only) and FL2VA (opening + ending); it keeps Ref2VA separately. A missing or rejected frame never silently selects text-only generation in the new workflow.
- [Official base prompt guide](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md): retain exact alignment and the three fields integrated_multimodal_description, overall_soundscape, non_diegetic_music. Ref2VA identity definitions are a different prompt contract. Names/dialogue retain their original language; explanatory prose is English.
- [Official ComfyUI H3 guide](https://docs.comfy.org/tutorials/video/minimax/minimax-h3): image-to-video and reference-to-video use different models/conditioning. Turbo step count and model choice materially affect both speed and output. [AMD's launch examples](https://www.amd.com/en/developer/resources/technical-articles/2026/day-0-support-for-minimax-h3-on-amd-gpus.html) do not establish a same-resolution/same-step benchmark for this host.

The user's pasted discussion is research input, not a verified benchmark. We found no matched evidence for “10–30% faster”, “many times faster”, or a universal “70–80% FL2VA” quota. End-to-end cost includes making/revising/approving one or two keyframes, model switching, rendering and retries. No new GPU benchmark or video generation is performed by this revamp.

## Content-led selection

Start with an opening frame when it can establish identities, composition and hands clearly. Add an ending frame when a specifically required final composition, pose or prop state merits the extra preparation cost. Movement, many characters or a changing prop alone do not mandate two frames. Ref2VA remains useful for reusable identity references and freer staging. Astra returns a reviewable per-Shot recommendation with exact source excerpts, endpoint blueprints and concrete visual checks. Users can choose any supported mode directly.

Endpoints do not guarantee intermediate hand/prop correctness. Keep canonical timing and shot boundaries; do not mechanically divide existing continuous shots into 3-second fragments. Fix wrong ownership/doorway geography in a keyframe before approval. The live Scene 01 candidate's review requests precisely those corrections; it remains pending.

“Hybrid” means choosing per Shot and scheduling separate model-family batches. The new handoff treats Shots as independent clips with reference-previous off; intentional seamless extensions remain an explicit later editing/rendering decision. Existing Ref2VA boundary judgments and manual overrides are preserved.

## Installed Director audit (read-only)

Root: `/home/navievroom/comfy/ComfyUI/custom_nodes/ComfyUI_MiniMaxH3_Director/`.

- `lib/task_modes.py:10`: task enum includes `t2v`, `i2v`, `fl2v`, `r2v`, `v2v`, `rv2v`.
- `director/fl2v_timeline.py:34`: seconds convert at 24 fps, then round UP to the next `17k+5` count. Duration can differ from requested seconds; review output dialogue/tail timing.
- `director/fl2v_timeline.py:458`: start-only produces i2v conditioning; start+end pairs the endpoints. End-only and empty prompt-only groups also exist in the plugin, but Studio does not silently select them.
- `director/fl2v_timeline.py:640`: Director reinforces/sanitizes the per-group prompt. Studio exports the official complete prompt, not an undocumented direct timeline injection.
- `director/fl2v_timeline.py:675–716`: start and end become reference slots 0 and 1, plan task key is `fl2v`, global is disabled, and previous-segment continuity is separately resolved.
- `director/fl2v_timeline.py:761`: the entire built plan has global task key `fl2v`; `director/plan.py:687` dispatches to that builder early. Do not mix Ref2VA identity groups into the same frame-mode plan.

The local Qwen audit could not start (GPU busy, HTTP 503). Parent performed the bounded read-only audit. No GPU service, plugin, authentication or sibling project changed.

## User flow and persistence

**影片準備**: choose Scene/Shot → select a mode or request Astra advice → inspect/edit/import/approve frame(s) → generate a mode-specific prompt → compare and explicitly adopt → optionally edit/save → copy prompt and obtain exact images/handoff JSON. No render starts from mode selection, recommendation, adoption, copy or export.

`video-workflow:{project_id}` stores versioned per-Shot selections, adopted recommendations and prompts independently of production and Ref2VA settings. Candidate jobs are persistent. Source/mode/frame changes invalidate old candidates/prompts. Drafts survive navigation/reload in browser session storage, separately per mode; save/copy/adopt protect unsubmitted drafts. Only ready current frame jobs export under `video-workflow/FL2VA/`; `status.json` lists blocked Shots, and original `ref2/` and legacy `h3/` exports remain available. Handoff JSON is NOT directly importable ComfyUI workflow JSON.

Adding a missing endpoint is explicit and revisioned. The endpoint description enters the canonical Shot; existing frozen sibling frames are preserved only when their original dependency hash was current and this operation changes nothing except adding the endpoint. Effective Scene/Shot Ref2VA prose is frozen so this addition cannot replace saved wording with a fallback. Other edits retain normal dependency invalidation.

## Acceptance

Full initial suite: 236 tests passed, 11 JavaScript regression scripts passed. Final cross-frame-conflict policy adds one regression, with final results in STATE.md. New API tests cover exact mode/slot selection, no fallback, candidate/manual text preservation, canonical/asset/mode staleness, cross-project adoption rejection, exact current dialogue, source evidence, endpoint addition and ZIP inclusion.

Live Astra strategy c5890b166d7b45b8 recommended I2VA for 下一站：長洲 / Shot 01: precise opening depth planes, but no required exact final composition; adding a tail brings little benefit. Parent reviewed and adopted the advice. Browser verified latest pending image e98766f0ad12407a's candidate review (wrong-hand jug and lit skyline), blocked prompt generation, and automatic blueprint + review feedback in the edit form. No image was generated or approved by this task.

All live Smallest Fix frame images were rejected, so positive prompt transport was exercised in an explicitly labelled, separate SQLite/image copy on port 4761. Two existing real images were treated as approved ONLY in that transport fixture; live rejection states remain unchanged. Real Astra prompt e9115a6177714f09 exposed a pair/source geometry/framing conflict. Initial browser adoption, draft reload/save, copy guard, clipboard equality and ZIP equality passed in the fixture; this is not creative approval. That observation motivated the final structured-conflict policy, which blocks such a result from adoption and handoff. Final real job bc3a70d8378b4291 returned empty text and two concrete repair requirements (Pip feet and lantern geometry). API/UI adoption, packet and ready export all blocked, verified against the final policy.

No speed or generated-video quality benchmark is claimed. H3 render remains external. Evidence: data/acceptance/fl2va-workflow/.

## Current override — complete prompts with advisory image concerns (2026-09-09 evening)

The historical acceptance above describes the superseded v2 conflict veto. Current copyable-prompt-v3 always requires complete valid H3 text, even when approved images have discrepancies. Warnings remain outside copied prose and survive adoption/manual saves; they no longer block adoption or handoff. The user decides whether to repair the approved image. Source/frame freshness, approvals, exact dialogue/labels/structure and draft guards still apply. Full candidates are visible inline with adopt-and-copy, and empty historical reviews are clearly labelled. Live Shot 01 now has a complete adopted I2VA prompt; native browser copy/paste verified 5099 characters. See data/acceptance/h3-copyable-prompt/verification.json.
