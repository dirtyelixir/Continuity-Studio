## Visual storyboard acceptance — 2026-09-13

18 dedicated Python cases pass. Related runs passed 79 existing tests, then 90 cases; a later 120-case run had 119 passes and one test-fixture configuration omission, corrected and covered by the final 18-case run. UI scripts cover board planning, review-token submission, progress routing, group rendering and source-page compatibility. Portable package hashes and the updated schema verify. Real DeepSeek job d6ed27d3809744a1 succeeded with three ordered panels against an isolated production copy. Browser exercised real-result adoption, existing-image import, per-panel review and a retained `revise` receipt for the visibly lit lantern in an unlit opening. Structural/interaction acceptance is not generated-video quality acceptance. No new image/video was rendered. Concurrent tasks/users had already adopted live board e686c81ce7e74f59 (production revision 13); this task preserved that state and performed its own adoption/review only in the isolated copy. Evidence: data/acceptance/storyboard-20260913/verification.json; workflow: docs/STORYBOARD.md.

## Mandatory production methods acceptance — 2026-09-09

429 Python tests passed, including 16 new method tests; skill validation and provider/profile, prompt-assembly, generation-status and image-reference JS checks passed. Isolated browser selected DeepSeek with local ComfyUI, applied and reloaded: all text/vision capability selectors showed DeepSeek and the mandatory method remained visible. Real Astra prepared one existing prop reference with the new method; a non-submitted Krea2 graph contained the exact compiled prompt. An independent skill forward test retained anatomical hands, pre-action state, specified lighting and source limits; focused acceptance review found no actionable defect. Tests use temporary data and mock HTTP where indicated; no real DeepSeek credential/quality acceptance is claimed. No new image/video was generated. Detailed evidence: data/acceptance/production-methods/verification.json; behavior/limits: docs/PRODUCTION_METHODS.md.

# MVP acceptance record — 2026-09-08

**Accepted:** the live verifier passed with 9 approved assets, 5 distinct planned frame images and three anchored H3 prompts (I2VA, FL2VA, FL2VA). Final status is recorded in STATE.md and data/acceptance/acceptance.json. This document describes what was exercised and its limits. The final automated run passed all **59 tests** (two upstream test-client deprecation warnings).

## Representative production

**The Smallest Fix**, project `91b816c3ac9549a2`. Original brief: a 25-second lighthouse-workshop comedy. Astra developed Ada (keeper), Pip (robot), a canonical workshop and a brass electric lantern into three shots with five single-moment keyframes. English dialogue, camera direction, timed beats, start/end state and scene relationships are persisted in revision 1.

The default integration was exercised through the installed authenticated Codex CLI with `gpt-6-astra`; the app initiated actual built-in image generation and vision review. No fake/demo-generation mode exists. All generated files were ingested into data/assets. Rendering did not use ComfyUI or local Qwen.

## Acceptance coverage

| Target | Evidence |
|---|---|
| Enter idea and return later | Browser clean-workspace create/reload test; live representative project's persisted idea and revision history |
| Narrative and dialogue | Real Astra proposal; browser review and adoption; screenplay plus timed “Definitely broken.” |
| Scenes, shots, storyboard plan | One scene, three shots totaling 25 seconds, five start/end frame records |
| Reusable character/location identities | Two characters, one location and one recurring prop; approved reference records |
| Real image generation | Codex tool-rendered PNGs, decoded and dimension-checked during ingestion; visible in browser |
| Identity and location continuity | Same approved reference IDs automatically applied across all shots; Astra vision plus owner inspection; specific defects revised |
| Asset/shot relationships and reuse | Stable target IDs, immutable input snapshots, approved-reference gates; generation of an already-approved target returns its saved asset without provider work |
| Image prompts and H3 prompts | Exact image request per asset; per-shot H3 fields, stable dialogue, reference labels and timing; ordered ZIP manifests |
| Provider switching | Clean browser test routed narrative to manual and produced awaiting_input; automated manual submission and local HTTP text/image/edit contract tests |
| Skills | performance-notes installed disabled, explicitly enabled, new performance_notes capability appeared, ran through Astra and returned shot-specific notes; no default changed |
| Persistence and recovery | Service restart/reload checks; optimistic revision tests; interruption marking and saved-result recovery tests; retained original/rejected alternatives |
| Continuity invalidation | Tests cover changed canon, replaced/rejected references, pending and approved dependent images, and stale proposal rejection |

## Real defects found and handled

- Ada's reference placed her pin on the wrong lapel. A local image edit corrected it while preserving her identity. Her stylized proportions and tactile patterned coat were explicitly accepted by the director despite an advisory review. The interpretation is stored with her approval.
- Shot 02 initially had an incorrect robot gaze and an extra prominent hair spiral. Targeted edits corrected the gaze and removed the extra spiral. Minor curved-bob rendition variation was explicitly accepted; visual review is probabilistic, not proof of pixel-identical identity.
- Shot 03's final pose initially tilted the robot away from Ada's hand. An edit corrected its lean toward her palm.
- The renderer's path-reading helper failed on this Linux host (`bwrap: Operation not permitted`). No storyboard images were produced by those attempts. Passing the already-attached conversation images succeeded without changing host sandbox settings or weakening the sandbox. Failed attempts remain in job history.
- The initial delegated skill module had inconsistent installation IDs and lacked safe version validation/integrity checks. Parent repaired it and verified the corrected contract.
- Reference replacement originally missed pending dependents. Fixed and tested. Rejection also invalidates downstream approved/pending frames.
- An unfinished manual handoff originally blocked switching providers. Provider-aware deduplication, explicit handoff cancellation and cancellation of queued work were fixed and tested.
- A final-frame render failed with a provider network error without producing an image. The failure was preserved and the retry was explicit.
- Provider labels, navigation scroll position, one-click approval of passing images, readable extension results and explicit edit-source provenance were improved during browser testing.

## Limits

This is a single-user local MVP with a small-project production model, not a finished cloud service. No H3 video render or audiovisual result was tested; H3 outputs are prompt/export packages based on the official base-mode guidance. Full-reference Ref2VA/video/audio attachments, collaboration, NLE assembly and arbitrary executable plugin scripts are deferred. The Astra image adapter supports five attached references per render. External paid APIs were not configured; their adapter transport was contract-tested against a local test server. Instruction skills do not constitute a general Codex plugin runtime.

Approved images preserve recognizable identities and major spatial/prop continuity in the representative project. Small rendering variations remain possible. The product exposes visual reviews, director overrides, image alternatives and regenerations rather than guaranteeing perfect model output.

## Reproduce

Run `.venv/bin/python -m pytest -q` for automated checks. Run `.venv/bin/python scripts/verify_project.py 91b816c3ac9549a2 --output data/acceptance` against the local service for read-only verification of the real project's images, shared references, review records, H3 anchors and exported files. This verifier never generates or approves an image.


## Ref2VA follow-up acceptance — 2026-09-08

Default delivery is now scene-global Ref2VA with one Director chapter per shot. Actual Astra job fd4a79666cca461f created one global and three chapter prompts. Final text satisfies six ordered fields, unchanged dialogue, stable four-image references and 7000-character ceiling. Runtime normalizes the fixed `[reference generation]` marker when the provider omits it, preserving raw result evidence. Chapter 1 starts fresh; chapters 2–3 reference their predecessor. Explicit cuts remain in the creative text.

Full suite passed 74 tests before the final focused normalization/transition changes; all six Ref2VA tests passed afterward. They cover scene inheritance, per-chapter override, cross-scene guidance, independent direction revisions, stale references, optional composition slots, provider result validation, split exports and marker normalization. Live verifier PASS includes exported global/shot/complete text equality, guidance settings, reference file membership, and unchanged original image/provenance checks. Production/canon, all 13 saved asset records, nine approvals and legacy H3 texts match the pre-change snapshot exactly.

Browser exercised deployed H3 delivery, scene generation, chapter override editor and guidance editor. No ComfyUI render or native workflow import is claimed; handoff.json is an instruction manifest. Only the one-scene sample ran live; cross-scene handling was exercised in tests.


## Character four-view policy follow-up

91 tests passed with two upstream warnings. New character images request the user's exact four-view layout, with layout/example inputs kept separate from approved identity. New approval requires the independent four-view review to pass. Front close-up, left/right full-body profiles and rear full-body, orientation/asymmetry, panel order and complete head/feet are explicit requirements. Single-frame storyboard prompts reject carrying over panels or duplicate figures. Old asset records and approvals are preserved; the live report labels Ada/Pip needs_four_view, so PASS for structural preservation is not a claim that old portraits meet the new sheet requirement. Actual image quality still requires reviewing a rendered candidate.

Browser verified the new character page, original example and four-view generation dialog. During verification a new app action started Ada image job f1f1d2387a994e4f. This code checkpoint does not claim it is complete or approved.

Subsequent live result: Ada asset 9ca22d17cccd4353 was generated and persisted under Characters/Ada/Ada-four-view-v001.png. Parent inspected the actual image; Astra review ee75b92e6ccb4f2d returned both overall and character_sheet pass. Pending approval is preserved. This verifies actual end-to-end generation, layout-only attachment, readable storage and review; it does not claim a new approved identity or a completed Pip sheet.

## Traditional Chinese interface

Default `zh-Hant` interface and `zh-HK` date formatting verified through live in-app and Chrome tabs. Ref2VA, Shot editor, character references, review controls, settings, shots, production folder and new-project form render Chinese interface text while original creative content remains unchanged. The production-folder dialog materialized/reused the normal export snapshot only; no approval, generation, routing or creative editing action was invoked. Production, revision and asset records equal the pre-localization snapshot.

85 locale assertions pass, including unknown-label fallback, diagnostic preservation and double spaces in original image paths. `node --check static/app.js`, `git diff --check`, six folder/cache tests and live HTML/locale-module cache checks pass. Two upstream Python deprecation warnings remain. External skill descriptions, user notes, generated reviews, prompts and raw JSON intentionally retain their source language.

## Human acceptance of character references

The review room now offers 人工確認採用 for character candidates without a passing four-view check. An explicit acknowledgement plus a nonblank reason is required; the saved note/event records human acceptance and the original review verdict remains intact. The regular approval path still requires a passing sheet check. Stale canon/reference protections and replacement invalidation remain effective. Character cards distinguish human acceptance from a passed four-view review.

24 character-policy and production tests passed (two upstream deprecation warnings), plus JS syntax/diff checks. Tests exercise the API acknowledgement, missing/blank reason rejection, retained review/event, superseded references and stale dependent frames, and refusal to bypass stale canon/input references. Studio restarted after verifying no queued/running jobs. The user's Chrome review tab was refreshed; Pip's enabled button and confirmation form were exercised, then cancelled. No live image was approved or generated by this change.

### No typing required for human acceptance

User rejected the mandatory acceptance-reason field. The sheet confirmation now has no text input; clicking 確認採用此圖 sends explicit acknowledgement and the server automatically saves a neutral human-acceptance record. Optional API notes remain supported. Review verdicts and stale-reference protections remain unchanged. Nine character-policy tests pass, covering omitted/whitespace/custom notes and required acknowledgement. JS syntax/diff checks pass. Restarted Studio with no active jobs and verified the user's Chrome dialog contains only cancel/confirm controls, with no required field. No live approval was submitted.

## Copy original image path

Added 複製圖片路徑 beside image controls in Ref2VA reference slots, shot frames, image lightboxes and character/location cards. A read-only asset path endpoint uses the same validated, resolved original file path as image serving/reveal. Clipboard text is the absolute filesystem path, preserving spaces and Unicode. Clipboard denial shows a selected readonly path for manual copying. No export snapshot, new image, desktop opener or approval is involved.

Eleven asset-library/folder tests pass, including the original resolved path, Unicode/spaces, unchanged asset records/pixels, missing files and symlink escape rejection. JS syntax/diff checks pass. Restarted Studio with no active jobs. Live in-app Ada button returned the successful copy toast with Characters/Ada/Ada-four-view-v001.png; Chrome was refreshed as well.

## Scene-only global prompts — final hierarchy correction

User clarified that only Scene owns a global Prompt; Shot has its own director/storyboard Prompt and no global override. Updated UI, edit schema, compiler, provider instructions, exports and current guide. Shot global copy/override controls and per-Shot global.txt exports removed. Combined text is always Scene global plus Shot prompt. Optional composition references are defined in a shared Scene reference list, keeping slots/global identical across Shots. Legacy global overrides stay in raw settings/history but are ignored in active configuration. Prompt compilation scope is included in freshness hashing so old compiled semantics cannot be silently reused.

Full suite: 98 tests pass with two upstream warnings. Coverage includes many Shots sharing one Scene global, independent Shot edits, cross-Scene guidance, API rejection of Shot globals, read-only legacy compatibility, shared optional reference slots and Scene-only global export. JS syntax/diff checks pass. Live API and ZIP verified one global per Scene and unchanged production/revision/assets. Both existing browsers refreshed; in-app page and Shot editor inspected, with no Shot global fields or controls. No live creative edit, approval or generation submitted. Studio restarted with no active jobs.

## Direct ComfyUI library transfer

After the user's GTK file picker returned Operation not supported for the suggested path shortcut, added 送到 ComfyUI 素材庫 to Studio image controls. It uploads original bytes to the existing local http://127.0.0.1:8188/upload/image API (input, overwrite=false), using a project-specific Continuity Studio subfolder and asset-specific filenames. Existing image picker is used afterward: 选已有, 缩略图, 使用所选文件. No changes to ComfyUI source, nodes, graph structure or prompts; no render submitted. Transport failures return Chinese errors and no success dialog.

Nine bridge/asset-library tests pass, plus JS syntax/diff checks. Live transfer of Ada, Pip, workshop and lantern succeeded. SHA-256 of ComfyUI /view bytes matches each Studio original. All four appeared at the top of the actual Director list_input_media response and visible existing-file picker. Studio UI button re-sent Ada successfully with the same server filename, exercising normal ComfyUI deduplication. Both Studio tabs refreshed. The user was actively editing ComfyUI; inspection selected no image or confirmation there. Studio restarted after confirming no active jobs; ComfyUI/GPU services were untouched.


## Ref2VA Director handoff page rebuilt

Replaced the all-scenes prompt document with a Scene selector and a sequential shared-parameters/Shot guide. Each step names the exact Director destination, exposes a bounded readonly prompt with one-click copy, and shows Shot duration/reference-previous settings. Scene alone owns the global prompt. Browser-only selection/copy receipts survive reload, are scoped by project and Scene, and match exact text so changed prompts are no longer marked copied. Clipboard denial selects the prompt for manual copying. Existing generation/edit controls remain available.

Scene references now support one sequential batch through the existing local ComfyUI bridge, per-image success/failure, and retry of only failed images. The UI explicitly distinguishes library upload from selecting Director image slots and copying from pasting. No ComfyUI workflow, provider, creative prompt, approval or guidance value was edited. Production/revision/assets/delivery matched before/after live API snapshots.

Validation: node scripts/check_director_page.mjs passes state persistence, project/Scene isolation, edited-text receipt invalidation, escaping and partial-transfer retry; 85 locale checks and JS syntax pass. Twelve delivery/Comfy bridge Python tests pass (two upstream deprecation warnings). In-app browser exercised shared/Shot copy, next-step navigation and reload persistence; actual Ctrl+V pasted all 3072 characters of the Scene prompt exactly into a temporary editor, then cancelled. Four-image batch displayed 4/4 success. Narrow 400px and desktop 1440px layouts visually checked. No service restart needed; Chrome disconnected during verification, so its existing tab could not be refreshed.


## Shot-aware reference-previous decisions implemented

Supersedes the earlier research-only/default-on behavior. New h3_guidance capability uses Astra to compare adjacent shot design and effective Scene/Shot prompts and returns per-shot start/cut/extend/uncertain, Traditional Chinese reason and source excerpts. Validators reject missing/duplicate/out-of-order shots, wrong previous-shot links and fabricated evidence. Results are matched to current policy/production/prompt/reference/notes hashes; stale results remain history, never current recommendations. Handoff automatically requests missing analysis, shows unknown while pending/uncertain/failed, and supports explicit retry and manual override. Legacy blanket guide booleans no longer count as overrides. Export includes decision/reason/evidence.

Live Astra job 81cebb2f00ef4cb6 succeeded: shot_01=start, shot_02=cut (50mm medium to 65mm tighter view), shot_03=cut (return to 50mm medium with a new push). API shows all three continuityFromPrev=false, with specific explanations and exact storyboard excerpts. Public-parameters guide says the master is unnecessary for this production. In-app Shot 2 displays 不勾選, Astra reason and expandable evidence; both existing Studio browser tabs reloaded. No production/creative prompt/approval or ComfyUI workflow was modified and no render submitted. Studio restarted only after verifying no active Studio jobs.

Validation: 107 Python tests passed (two upstream deprecation warnings), plus 85 locale assertions, JS syntax and Director state/render tests. New coverage checks exact review provenance, cross-shot links, exported decisions, legacy override handling, explicit manual/master interaction, uncertain vs off, prior-shot/prompt edit invalidation, immutable history and idempotent analysis requests. Frontend regression checks reviewed off reasons/evidence and unresolved labels. A final six-test guidance run also passed the additional empty-project/read-only-request regression.


## Explicit image generation and uploaded production inputs

User requires character/location/prop/frame images to start only after clicking Generate. Existing plan adoption remains text-only; removed the immediate bulk image action and made per-target generation forms explicit. Canon page has 上傳共用風格參考; each entity has 上傳製作參考 (style or subject/design input) and a separate 匯入完成圖片／四視圖 path. Uploaded inputs preserve original PNG/JPEG/WebP bytes with role, target, path, hash and JSON sidecar under the readable project asset library's Production References directory. Upload alone performs no generation/review/approval and leaves production/assets unchanged. Generation forms allow selecting applicable uploaded inputs; backend validates ownership, scope, duplicates, file integrity and total provider attachment budget, then supplies real image inputs with distinct style/design instructions. Job provenance and explicit retry preserve selected input IDs.

Also removed the 200-nonempty-line import rejection. A 350-line input is accepted and stored character-for-character; 20,000-character/file limits remain. Existing source traceability and storyboarding schema preserved.

Validation: 146 Python tests passed (two upstream warnings), 85 locale assertions, Director rendering/state tests and JavaScript syntax checks. Five focused input-reference tests passed again after retry-provenance additions. Tests verify upload creates no jobs/assets or production mutation, correct actual image paths and roles supplied only to explicit generation requests, unselected input exclusion, original byte retrieval, wrong-project/target/duplicate/tampered file rejection, and counting the layout in the actual provider input budget. Studio restarted with no active jobs. Live Chrome canon/upload/generation forms inspected and cancelled without generating or uploading any production image; the page clearly separates saved inputs from finished assets. Existing in-progress story-import work was preserved.


## Shot dialogue and mouth direction — 2026-09-08

38 focused tests pass. Read-only production compilation confirms The Smallest Fix combined prompts stay under 7000 characters with no issues. Saved revised Shot prompts through the live delivery API as direction revision 2; verified canonical production and asset records are identical before/after. Live browser selected The Smallest Fix → H3 / Ref2VA → Shot 03 and verified the actual textarea requires no speech or speech-like mouth movements throughout 0.00–9.00s. Shot 02 also verified. No image/video generation or ComfyUI edits.

Deployment limit: the general Python compiler/refinement/validation changes are on disk, but the service was NOT restarted because another project's narrative job 238a7527ba2f44ed was running. This work's revised prompts are already live through saved direction settings. Next safe service restart loads the general rules for future works. Existing provider prose/history is retained; this explicit delivery revision saves the user's revised handoff prompts. Opening H3 uses the app's existing automatic text-only guidance analysis behavior.


## Clickable Shot references — 2026-09-08

Live Chrome on project 54809c31ce4144b4: all seven source-shot reference chips have correct target IDs and accessible names; character opens 生成四視圖, prop/location open 生成圖片. Upload form offers style or identity reference and a return to the generation dialog. Typed feedback survives upload-form return. Cancelled all dialogs; no test input or image job saved. JavaScript syntax and whitespace checks pass; user can use the updated buttons now. Actual file upload/save was not repeated on live production storage.


## Drag-and-drop production references — live 2026-09-08

Generation and production-reference upload dialogs now offer a drop zone, ordinary file selection, local thumbnail/filename preview and explicit 保存參考圖. Dropping into generation opens the same target’s upload confirmation and retains generation draft/selected references for return. The original File is sent through FormData only on save; no image job starts. One PNG/JPEG/WebP at a time; invalid, empty, oversized or multiple drops show a message and retain the prior selection. The whole open dialog prevents file-drop navigation. Preview URLs and drag listeners are cleaned up on replacement/close.

Verification: JS syntax/diff checks and scripts/check_reference_drop.mjs pass. Event-handler regression checks exercise dropped/picked file identity, navigation prevention, preview, invalid/multiple-file retention, initial-file handoff and cleanup. Live Chrome verified drop zones and normal navigation/return in both dialogs on 下一站：長洲; no real desktop file drag or live reference upload was performed by the agent. Static changes are live after reload; no backend restart or generated media.

## VoxCPM2 postproduction — 2026-09-08

See VOXCPM.md and data/acceptance/voxcpm/verification.json (PASS). Live 下一站：長洲 has twelve distinct real 48 kHz audition candidates, all saved and awaiting user listening/selection. Isolated browser/API acceptance exercised voice reference adoption, exact Cantonese dialogue cloning, playback, line selection and four-WAV export. Twelve focused audio tests pass after the explicit-silence correction; the initial full suite passed 177 tests. Safe restarts preserved original source, production, visual assets and all audio records. These restarts also loaded the previously pending general speech-direction code. No existing job was interrupted.


## Managed production-reference originals — deployed 2026-09-08

Uploads now store byte-identical originals under the existing stable asset-library target directory (Characters/Locations/Props or Scene/Shot) in Source References; project-wide style inputs use Style References. Names use target + purpose + sequential version, preserving original_filename, ID, SHA-256, upload time and purpose/target in sidecars plus project indexes. Never overwrite old versions. Explicit legacy organization retains former files for frozen job inputs. Production ZIP now includes uploaded original bytes and their metadata, independently of canonical approval. UI shows saved/original names, original-file path copy and reveal controls.

13 focused input-reference/folder tests passed, covering deleting the external source after upload, unique versions, original-byte ZIP export and idempotent legacy organization. JS syntax/diff checks passed. Both normal jobs and voice_takes were idle before stop/backup/organization/restart; no active work interrupted. Backup: data/backups/reference-library-20260908-232805/. One live 昌叔 input migrated to Characters/昌叔/Source References/昌叔-外觀參考-v001.png; IDs/hash unchanged, old path retained, project and canonical asset rows identical. Live path endpoint/ZIP SHA-256 verified, browser shows clear saved name, original screenshot name and original-file controls. No new image/audio generation. This safe restart also loaded the previously pending general speech-direction code.


## Visible image-generation state — live 2026-09-08

Canonical asset cards and keyframe panels derive per-target state from real image jobs and matching image-review jobs. Gold bordered cards, a spinner, explicit queue/generation/review/manual/failure labels, elapsed waiting time and job-detail access replace the misleading idle appearance. Successful candidates show ready-for-review; failed/interrupted work stays actionable. No percentage or estimated completion is invented. Active targets disable duplicate generation; Shot reference shortcuts open current work status. Submission immediately displays a disabled submitting button, then incorporates the acknowledged job before polling. Elapsed labels update each second without rerendering form inputs. Existing four-second backend polling handles phase transitions.

Verification: scripts/check_generation_status.mjs covers queue/run/manual/review/completion/failure/interruption/cancellation, target isolation, ignoring obsolete failures after new assets, newest active generation precedence, elapsed clocks, escaping and non-spinning terminal state. JS syntax/diff checks pass. Real browser on 下一站：長洲 showed two running/two queued user jobs with disabled generation buttons and advancing clocks; later observed 昌叔兩個膠桶 automatically transition to image-generated/waiting-review and 長身螺絲批 to running. No test jobs or renders submitted; no service restart.


## Optional high reference preservation — live 2026-09-08

Generation dialog now includes 高度保留參考內容 (off by default). Selection adds explicit role-aware fidelity directions to the existing persisted job feedback and image prompt, so retries retain the instruction without a new backend field. Identity/design inputs preserve recognizable features/materials/colors/details; style-only and layout-only roles remain distinct and required character four-view framing remains. User edits and selected refs are preserved. Upload/return retains checkbox state. A new entity with no selected or approved content reference is prompted to select/upload one before submitting this mode. This is prompt guidance, not an exposed underlying image-model fidelity parameter or a pixel-identity guarantee.

Verified checkbox default/click/upload-return state in the live browser, then cancelled. Pure toggle checks confirm instruction addition/removal/idempotence. Built actual 昌叔 image request locally to confirm feedback and selected image references reach image_prompt without enqueueing. JS syntax/diff checks passed. Static changes are live without restart; no render submitted.

## Crowd reference completion — 2026-09-08

Live IAB verified 下一站：長洲 → 角色與場景: 屋苑倖存街坊群 displays 群眾演員 / 群像參考圖尚未生成 / 生成群像參考圖, without a four-view warning. Opening generation shows group-specific title, placeholder and high-fidelity help plus drag/drop inputs. Checked high fidelity, opened reference upload and returned: checkbox remains checked. Identity editor contains 素材類型 with current crowd selected and individual/crowd options. Cancelled all forms; no upload, image generation or additional revision was submitted. 陳樂言 retains 製作新版四視圖. Generic asset editor preserves name/description/facts; class changes use the existing versioned plan endpoint tested in test_crowds.py.

JS syntax passes for app/postproduction/fidelity, 85 locale assertions, reference-drop event regression and generation-status regression pass. Backend 48 focused tests passed before deployment. Local Qwen UI task did not complete before interruption; parent identified and terminated only its orphan worker, confirmed no edits, and completed the UI directly. No model/GPU/ComfyUI service was modified.

## Inline prompt editor — 2026-09-09

`node scripts/check_prompt_editor.mjs`: persisted/isolation/clear drafts, scope-correct Scene vs Shot saving, effective sibling prompt preservation, guidance retention, production/source conflicts, empty input, safe textarea escaping. Existing check_director_page and app syntax pass. 19 tests across delivery/speech_direction/guidance pass, including exact manual Scene/Shot text in API and ZIP, unchanged live production/assets/jobs and stale-save rejection.

Isolated browser at 4761 project 9a753b8a1c824acf: saved custom global text; edited Shot text, refreshed with draft intact, saved, confirmed API direction revision 2 and exact ZIP text; unsaved extra line was discarded and saved Shot remained. No image/audio jobs generated; guidance used manual provider. Hidden-IAB clipboard comparison returned false and is not acceptance evidence for the OS clipboard. Existing copy handler still reads the effective saved prompt; dirty drafts explicitly require saving first. Live 4760 page reloaded to show editable Scene prompt and Save/Discard without changing its creative text. Test tab/server closed. Backup and safe deployment recorded in STATE.md.
# English Scene/Shot delivery acceptance — 2026-09-09

Original-name correction: 30 preparation/delivery/provider/asset-role tests passed, plus the 12-test preparation suite after adding original names to the pending reference mapping. Original-name adaptation was checked against the latest successful prepared result from each of the 7 live Scenes: canonical character/crowd/voice names match exactly, the remaining prose passes the English check, and raw job output remains untouched. Original dialogue is excluded from name substitution. Legacy H3 validation receives the canonical name whitelist. Scope compatibility changes and tests belong to the concurrent asset-role task and were preserved.

Follow-up public-parameter regression: 23 tests in test_prompt_preparation.py, test_delivery.py and test_crowds.py passed. Added adversarial raw-global coverage with biography embedded in description, hidden pockets in facts, human adoption note, whole-project style and future Scene summary; none enters fallback text, while source canon remains intact. Both h3_prepare and h3_scene prompts receive the visual-only global contract. Live all 7 globals match their ZIP files and omit the reported text; first Scene's shared textarea verified in IAB. Existing prepared results remain unchanged. Service restart guarded on idle jobs and voice_takes.

- Request: English prompt prose except exact original dialogue; remove project-wide production notes from each Shot; explicitly assign the 17% phone check to Leyan, not Chang.
- Live project 下一站：長洲 / 54809c31ce4144b4: revision 3 changes only Shot 01 action and beats to clarify ownership. All original utterances remain exact. Prepared jobs by Scene: 2312e397a0104ce7, 780a1f08c4f14dda, 4070bab9fe28493e, 64508eb062114300, 62ce09c2dbe34124, 99dd21346c054b1e, c066ba8def2a4e2a. Provider output is retained; reviewed corrections are stored separately and logged.
- Executed `.venv/bin/python -m pytest -q tests/test_prompt_preparation.py tests/test_delivery.py tests/test_speech_direction.py tests/test_production.py tests/test_postproduction.py tests/test_providers.py`: 49 passed. Existing Starlette/httpx and anyio deprecation warnings only. `node scripts/check_director_page.mjs` and `node scripts/check_prompt_editor.mjs` passed. Coverage includes Scene isolation, exact dialogue/language tags, delayed reference resolution, stale-source invalidation, English-copy readiness, omitted project style, silent mouthed lines and legacy H3 preparation.
- Live GET state + production ZIP: all 7 Scene globals and 29 Shot prompts pass the language/dialogue checks; every global.txt, shot.txt and complete.txt matches the delivered API text. Original plan.style is absent from every Shot. Missing reference approval remains visible. These structural checks supplement, rather than establish, semantic review.
- Browser at 4760 after reload: first Shot displays English prose, Subject 1 checks his own Subject 7, only 17 percent remains; Subject 2 calls without handling the phone. Exact Cantonese lines stay inside their language-tagged dialogue blocks. Editable textarea and Save/Discard remain. No claim of generated video or lip-sync validation.
- Data preservation: assets, voice_profiles, voice_takes and voice_lines compare exactly with data/backups/english-prompts-20260909-001428/studio.sqlite3. Final service restart occurred only after both queues were verified idle. Earlier restart interrupted text guidance dc74cd54fac549c9 due to shell fallthrough after an idle assertion failure; replacement f76a75376cec48e1 succeeded and live guidance is ready. GPU/ComfyUI services were not changed.

## 2026-09-09 — H3 frame workflow

237 Python tests, 11 JS scripts, real live Astra mode/blueprint analysis and isolated real multimodal prompt/conflict runs verified. Live data/media/previous settings preserved exactly. Explicit modes, no text-only fallback, source/frame/draft conflict protection, blueprint repair feedback, current-dialogue retention and exact handoff export passed. Pair conflicts block handoff. See FL2VA_WORKFLOW.md and data/acceptance/fl2va-workflow/verification.json for evidence and the isolated-fixture limitation.


## DeepSeek profile — 2026-09-09

Deployed selection/API/transport acceptance: 259 full-suite tests, 46 final focused tests, 13 JavaScript scripts. Browser verified isolated apply/reload, custom override, missing-key response and return to Astra. Live page inspected after safe restart; all durable tables match the backup and integrity is ok. Real DeepSeek completions are NOT exercised: the service lacks DEEPSEEK_API_KEY. This is a verified settings/routing integration, not a creative-quality or authenticated-provider acceptance. No media generation. Detailed evidence: data/acceptance/deepseek-settings/verification.json; setup and limits: docs/DEEPSEEK.md.


## 2026-09-09 — Prompt assembly scope and provenance

See PROMPT_ASSEMBLY.md and data/acceptance/prompt-assembly/verification.json. Final full suite: 288 passed. Five real Astra text preparations reviewed; corrected cross-scene predawn lighting verified. Isolated API/provider tests exercise text-before-image, failure without rendering, exact persisted/delivered prompt and export, target-specific fidelity, reference packing, uploaded-reference review, distinct-request rejection and recovery-source integrity. Browser verified new/legacy prompt labeling. Idle deployment preserved all immediately preceding project, asset, job, chapter, voice and settings rows. No image, video or voice generation was initiated by this acceptance task; concurrent user work was preserved.
# Unified video preparation — 2026-09-09

One 影片準備 sidebar entry; REF2VA renders inline with Scene/Shot tabs and its existing save/copy/regenerate/reference/guidance controls. Frame modes remain mode-specific; old routes redirect without mode mutation. scripts/check_unified_video.mjs covers embedded selected-Shot scope, one heading/editor, mode branches, isolated drafts, and aliases. Existing workflow, handoff, editor, guidance-startup, regeneration and prompt-assembly checks passed. 17 relevant Python tests passed.

Test-only browser at 4761: saved Scene global, edited Shot, confirmed dirty-copy guard, switched to a different FL2VA Shot (two frame slots, no Ref2VA editor), returned with draft retained, reloaded, saved, clicked copy and observed successful receipt. API and ZIP equal the exact saved text. Clipboard-byte comparison timed out and is not claimed. Inspected full-page layout screenshot. Live 4760 navigation and existing locked I2VA mode verified; production data untouched. Static deployment requires page reload, no service restart. Isolated server/tab cleaned up.

## Reference design priority and visual preparation — 2026-09-09

292 full-suite and 35 final focused tests passed; isolated fixtures cover selected identity versus style-only inputs, explicit edit source, no automatic existing-asset reuse for selected references, unchanged canon/approval, matching preparation/render pixel hashes, changed-reference recovery rejection, and review authority. Actual Astra image_prepare processed the uploaded c_leyan image and correctly described the stockier green-jacket/backpack design while omitting old gray-shirt/slim features. No new media generated. JS checks cover uploaded-reference visibility, source deduplication, escaping and actual layout provenance. Evidence and deployment row equality: data/acceptance/reference-design-fix/. Internal image-tool arguments are absent from legacy CLI events; final rendered fidelity after this fix has not been live-tested.

## Older review reminders — 2026-09-09

JS regression covers older pending/stale with newer approval, newer pending after approval, unrelated targets, stale adoption, rejected newer attempts, retained version lists and input immutability. Existing image-reference evidence and generation-status checks plus syntax/diff checks passed. Actual staircase rows were read-only inputs for an in-memory reconstruction of the screenshot: obsolete candidate disappears from review while six versions remain. Live static responses match disk; no restart or asset decision. Evidence: data/acceptance/review-version-cutoff/.

## Rejected image disposal — 2026-09-09

297 tests pass; temporary-directory tests verify reject-to-delete response and files, minimal text audit, completed-review copy deletion, active reference deferral and cancellation cleanup, rejected dependency chains, untouched approved assets, non-reused version paths and unrelated provider-output protection. Initial full-suite failure was the obsolete expectation that rejection retains a sidecar; updated to require its deletion and retained text event. Live API removed 9 already-rejected versions/69 files from 下一站：長洲 after explicit user authorization. Other 25 asset rows and image hashes, projects/revisions/jobs/voice/settings rows matched before and after; no remaining rejects in that project, SQLite integrity ok. Source uploads and other projects' rejected versions preserved. Evidence: data/acceptance/rejected-image-disposal/{pytest-final.txt,deployment.json,cleanup-preview.json,cleanup-result.json}.

## Recoverable project deletion (2026-09-09)

作品管理 has per-work deletion with warning, exact-title confirmation, server revision and active-work guards; 已刪除作品 supports restore without file/child-row removal. Isolated browser verified wrong-name disabled, cancel, current-work deletion, trash reload/restore, cross-tab deletion and preserved other-work selection; warning screenshot inspected. Full suite 333 passed; final focused tests 15 passed, with two existing dependency warnings. JS syntax/unified-video/diff checks pass. Production deployed only after both queues idle; online backup row comparison across all 10 tables and integrity check passed. No live work was deleted. Evidence: data/acceptance/project-delete/.

## H3 one-click generation — 2026-09-09

337 full-suite Python tests passed before final deletion/UI integration; focused follow-up results recorded in data/acceptance/h3-one-click/verification.json. Protocol tests use temporary data and explicit mock media/transport. They cover frozen input mapping, idempotency, lost receipts/restarts without second generation, guarded GPU admission, download recovery, stale adoption, remote identity/path checks and selected MP4 export. JS checks cover frame/Ref2VA drafts, unresolved disablement, playback, adoption, recovery endpoints and settings expansion persistence. Isolated real browser shows the new section and accurate missing-approved-frame gate; service status/schema checks are read-only. No real video, ComfyUI update, GPU restart or creative approval performed. First real video execution and quality remain unverified.

## Approved imagery pale-green status — 2026-09-09

Applied the existing reference-approved palette to ready frame containers and approved asset/canon cards. Approved-frame review notes retain issues with an adoption-first label. Existing video-workflow/image-mapping/generation-status checks and syntax/diff checks passed; live served bytes and browser labels verified. No new media, approval change or restart.


## Local image alternatives (2026-09-09)

348 tests passed with two existing dependency warnings, plus provider/prompt/reference/upload JS checks and syntax/diff checks. Both named originals are archived with SHA-256; all implemented recipes match live node/model schemas. Actual Krea text generation and a browser-launched single-reference edit returned real images; the edited asset remained pending with passing Astra review. Actual Klein v3 produced distinct portrait/left/right/rear views after documented v1/v2 visual failures; small wardrobe discrepancies remain subject to review. Actual recovery reused the same Krea prompt_id and token. No visual acceptance claimed for two-input Krea, face transfer, masking or outpaint yet. Live v3 API/static parity verified with original Astra defaults intact; no task-initiated production data change or service restart. Evidence: data/acceptance/local-images/verification.json; implementation and limitations: docs/LOCAL_IMAGE_WORKFLOWS.md.


## Corrected character sheet standard (2026-09-09)

97 focused Python tests pass; frontend reference/prompt checks, syntax and diff checks pass. The v4 graph emits front-full, side-full, rear-full, enlarged face in that order on a 2048×1152 sheet. Live ComfyUI dependencies validate. The exact uploaded JPG is served as image/jpeg from a new versioned guide path; old guide remains untouched. Production restart occurred only after jobs, voice and video queues were idle; all DB rows stayed identical and integrity passed. No new media generated, so updated layout visual acceptance is not claimed. Evidence: data/acceptance/character-sheet-standard/verification.json.

## Expandable H3 settings — 2026-09-09

383 full Python tests pass (two upstream warnings). Tests cover user defaults, 4/8-step automatic values and overrides, model-family rejection, Director resolution math, true refine links, separate first/second model chains, standalone scaling, muted vs generated audio verification and missing selected capability failures. JS covers scoped setting persistence, actual changes, escaping and existing submission/draft guards. Twelve graph combinations compile against live ComfyUI schema without uploading or queueing. Isolated browser exercises preset4→manual6, 9:16, second pass,2×,silent output and extra LoRA. No real video or plugin/GPU-service update. Detailed evidence: data/acceptance/h3-settings/verification.json.

## 2026-09-09 — Klein/H3 runtime-mode correction and real four-view sample

The installed CLI launchers and opt-in SDPA patch were inspected. The live H3 process lacked --disable-smart-memory; Klein adds it. HERMES_FORCE_SDPA_MATH is unset in both current launchers, so the old SDPA patch is inert. Some historical launcher comments still claim otherwise. No external launcher, kernel patch or GPU service implementation was edited.

Replayed identical Klein v4 model/graph/prompt/seed: H3 mode produced black side/rear panels; switching only the attention node produced black output; the existing VRAM Manager's Klein-mode switch produced a complete 2048×1152 front/side/rear/portrait sheet. Mode switch includes a fresh process, so this is evidence for the working runtime profile, not isolated proof that smart-memory alone is the root cause. The sample has minor costume/framing drift and is not approved canon. Artifacts: data/acceptance/character-sheet-standard/demo-v4-klein-mode/render.png and runtime-investigation.json.

Studio now requests Klein for local image work and H3 for local video work through the existing /vram/comfy/mode endpoint. It respects paused admissions and manager refusal when work is active; no forced stop or blind mode retry. A process-owned ComfyUI-compatible GPU reservation pins the verified mode/PID across preparation and rendering, preventing a switch between check and submission. Recovery uses history only and does not change mode or acquire GPU. Current mode is left in place until another explicitly requested generation needs the other mode.

Validation: 82 focused Python tests passed (two existing dependency warnings), including both mode directions, paused/busy refusal, race rejection, release on failure and recovery without reservation. Real runtime reservation switched Klein→H3, verified PID and rejected an opposite-mode request while held. Studio restarted only after all state-bearing DB tables were idle; every table hash was unchanged and integrity was ok. Evidence: runtime-tests.txt, runtime-reservation.json, runtime-deployment.json. No H3 video was generated by this task.

## 2026-09-09 — Real location, crowd and prop samples

Generated examples from 下一站：長洲 canon using the deployed managed local adapter: 二十八樓走廊 (Krea2 Turbo, then Klein reference edit), 屋苑倖存街坊群 (Krea2 Turbo, eight-person representative ensemble), 五公升膠水樽 (Krea2 Turbo). All three categories produce visible images without black outputs. Crowd count differs from the sample prompt's seven, and age distribution skews older; no canonical count was fixed. The initial corridor and Krea2 Muse edit retained forbidden lighting; explicit Klein reference editing removed the corridor lamp/indicator illumination, but distant lit windows remain. These are user-review examples, not approved canon or a claim of perfect constraint adherence. No production DB/asset changes. Evidence, exact prompts/plans/runtime receipts and outputs: data/acceptance/non-character-samples-20260909/verification.json.

## 2026-09-09 — Portrait padding removed, v5 deployed

Fixed the user-reported white blocks: portrait now generates at full 704×1152, replacing the 704×960 image centered on pure white. Real same-seed Klein output has no artificial top/bottom strips; full head and shoulder/chest remain visible. Thirty-four focused tests pass. Idle Studio deployment preserved every database table and passed integrity check. Old files/receipts/approved assets untouched. Evidence: data/acceptance/character-sheet-standard/demo-v5-full-height/verification.json and render.png.

## Workflow ownership — verified and required (2026-09-09)

User requires Studio to survive deletion of external ComfyUI workflow JSON. All three complete original workflow copies are regular files under Studio workflows/; image routing/graphs and H3 I2VA/FL2VA/REF2VA graphs are owned Python code. External manifest source paths are provenance only. Added a permanent AGENTS.md contract, workflows/OWNERSHIP.md and 13 offline checks that relocate the owned bundle and make external workflow reads/probes fail. All 9 image recipes and all 3 H3 modes build successfully. The test caught 4 missing core node schemas in Studio's archived snapshot; copied the live definitions into its owned archive. Combined relevant tests: 73 passed. No production logic, services, DB, external files or generated media changed. ComfyUI/models/custom nodes/VRAM Manager remain explicit execution dependencies. Evidence: data/acceptance/workflow-ownership/verification.json.


## Overview usability — 2026-09-13

Task-first progress panel and chapter version/work separation verified live. 19 Python tests passed; overview guidance, chapter rendering/integration, existing Shots, staged progress and responsive interaction scripts passed. Browser verified review and chapter routes, non-submitted revision dialog, advanced directing expansion and preserved expansion, desktop and 390px layout. Static hashes match live service. No generation or adoption was initiated by this acceptance. Full evidence: data/acceptance/overview-ux-20260913/verification.json.

## 2026-09-13 — Formal editorial

623 full-suite checks; final 52 editorial/timing/directing checks; unified-video/directing JS regressions; temp browser formal save and source-Shot navigation; real browser v5/9cuts/53.5s. Live production/assets unchanged and SQLite integrity ok. Seven Scene states, 69 formal audio cues, nine old→new Shot/frame mappings. Evidence: data/acceptance/editorial-formal-20260913/verification.json. Creative review remains pending/revise; no claim of rendered edit or media approval.


## 2026-09-13 — Mandatory montage integration

Live method routing, immutable visual-skills provenance, chapter/full/scoped request integration, source-writer isolation, frozen-review freshness, saved edit-sequence UI and adoption safeguards verified. 226 relevant Python tests and four Node scripts passed. Real staged DeepSeek returned 10 source Shots / 10 edits with exact source preservation and distinct 51.5-second generation / 42.7-second screen durations. Real full review hit its output limit and remains blocked from adoption; smaller real controls returned substantive revise findings, including rejection of intentionally unreadable carriers. No creative-quality pass or rendered-film claim. Evidence: data/acceptance/montage-integration-20260913/verification.json; limits and workflow: docs/MONTAGE.md.

## 2026-09-13 — Native H3 storyboard generation groups

Backend/source, prompt and recovery checks pass; 12 new isolated tests verify ordered edit references, short views, role-labelled images, exact speech/cut constraints, stale protection, one Director segment and whole-group selection/mapping export. Browser saved the real 5,295-character DeepSeek prompt and group in an isolated copy, preserving open state and showing the ready generation control with no page overflow. Node checks cover group actions and observed coverage, plus existing video/settings/progress navigation. Real text/vision results and initial failures are preserved; no media generation or user production adoption. Full scope, limitations and evidence are documented in docs/GENERATION_GROUPS.md.


## 2026-09-13 — Frozen-moment synchronization before media

131 distinct focused Python cases pass across exact-time state ownership, immutable source/audit hashes, entity isolation, durable semantic correction, unresolved/uncertain failure before renderer, same-provider repair, recovery and tampering guards, endpoint/temporal scope, references, method reuse, formal directing and storyboard regression. Three Node suites pass, including escaped pending/accepted/repaired/blocked preflight notices above technical details. Original pinned methods and the 66-file portable package remain intact.

Real Astra prepared the unchanged revision-13 diagnosis source with its original four frozen references and automatically reconciled Pip toward Ada plus Ada's initial handle contact, retaining explicit omitted-context evidence and an unlit lantern. A distinct text preflight returned pass with no issues. This was text-only acceptance, not generated-image visual acceptance. Production revision and every database table digest were preserved across idle app deployment; live API exposes the new read-only receipt and serves exact updated static bytes. See data/acceptance/moment-sync-20260913/verification.json.


## Workflow architecture cleanup (2026-09-13; live)

238 relevant Python cases, including 25 new cleanup cases, pass. Thirteen Node suites cover planning/readiness, frozen request submission, review/use state, old-backend compatibility and routing. The final broad run includes observed group source offsets and retained boundary history. Evidence: reviews/workflow-cleanup-20260913/evidence/.

Read-only browser/API acceptance used an isolated copy at 4761 with all background workers disabled and non-read HTTP requests rejected. Both existing project revisions (13 and 5) remain readable. Verified production/revisions/video takes/selections/human approval preservation and SQLite integrity. Initial activation was deferred while live image jobs completed. The user subsequently authorized the idle restart: Studio PID 3626945 → 3786523 through ./run.sh. Live health and both project/editorial APIs pass with workflow_contract_version 1; all 13 table digests and 51 asset-file hashes are unchanged, SQLite integrity is ok, and job/video/voice queues remain empty. No media was generated for this acceptance. Backup and restart evidence: reviews/workflow-cleanup-20260913/evidence/live-activation/. Full implementation notes: reviews/workflow-cleanup-20260913/REPORT.md.


## Storyboard review usability — live static update (2026-09-13)

User could not locate the visual-board review required by H3. The same read-only task summary now exposes approved/pending/missing/repair counts and a direct review entry from the scene's H3 workspace, board page and review room; the production overview uses the same continuation action. Navigation names the destination 分鏡畫面與審閱. Other pages collapse the full workflow map, and context-specific tasks replace duplicate next cards while retaining a stable target for background refresh.

The review opens the first pending image, shows its ordinal and neighbouring images, then saves one version-bound human decision and opens the next pending image. Missing or repair-needed frames remain outstanding. A replacement image is not hidden by an old image's repair receipt. Saving guards duplicate clicks, errors preserve the form, and project changes stop submission. Single-version image IDs are hidden from the normal flow; the decision bar stays visible and initial focus keeps image context in view. Human approval and provider generation remain explicit existing actions.

22 existing storyboard Python cases, 9 Node suites and 6 JS syntax checks pass. Live browser verified the review-room entry opening The Smallest Fix frame 4/11 with the original 3 approved frames, neighbour images and visible decision controls; no production review or media submission was made. Static bytes match the running server, with no restart required. Evidence: reviews/storyboard-usability-20260913/evidence/verification.json. The interrupted local Qwen scope left the video entry change; parent inspected and completed acceptance.



## H3 service preparation switches through VRAM Manager — live (2026-09-13)

The generation worker already reserved H3 automatically, but the visible service check only inspected the current mode and instructed users to switch manually. Replace that dead end with an explicit 準備影片服務（自動切換 H3） action: POST /api/video-provider/prepare uses the same manager reservation, checks service/node readiness while held, then releases without uploading or submitting media. GET status remains read-only and explains automatic preparation. The button shows switching progress, prevents duplicate clicks and recovers after manager refusal. New video jobs still reacquire/revalidate their own reservation; recovery remains receipt-only.

37 Python cases and two Node suites pass. Real user-authorized preparation switched Klein PID 2932623 to verified H3 PID 3844858 through the existing VRAM Manager; no direct service control or generation occurred. Idle Studio restart 3786523 → 3846405 loaded the endpoint. A second live preparation succeeded without restarting an already-H3 process. SQLite integrity and all table digests were checked against the pre-restart backup. Evidence: reviews/h3-service-prepare-20260913/evidence/verification.json and live-switch.json.



## Image generation selector honors renderer capabilities — live static fix (2026-09-13)

The image dialog's older wildcard filter exposed local_qwen as an image renderer, even though backend admission and profile settings correctly reject it. It now uses shared supportsProvider checks, excludes Qwen/DeepSeek from rendering, keeps Klein/Krea2 and configured image APIs, and submits the visibly selected renderer explicitly. Unsupported saved drafts/defaults require a new valid choice instead of silently falling back; draft feedback/references remain untouched. The local controls validate the same capability rule.

31 Qwen/profile Python cases, three Node suites and JS syntax pass. Served static matches disk. Existing image route remains Astra; no setting, production, generation or backend restart was performed. User clarified that local Klein/Krea2 supplies images while Qwen supplies creative/vision work. Evidence: reviews/image-provider-choice-20260913/evidence/verification.json.



## Wait for transient VRAM transitions — UI live, backend activation pending (2026-09-13)

The old runtime status collapsed paused, maintenance and transition into one immediate error. Runtime status now waits up to 180 seconds of transition/maintenance polling, using only manager GETs, while actual paused state fails clearly without unpausing. Reservation still validates mode/PID after admission; busy manager refusals and ambiguous submissions are not retried.

The live service-prepare UI handles the old backend's exact pre-admission transition refusal by waiting and retrying only /video-provider/prepare, bounded to 180 seconds. It never wraps generation/upload or retries ambiguous transport errors. Once the backend is loaded, explicit paused and timeout messages stop this legacy retry path. 41 Python cases and three Node suites pass. Live preparation returned ready=true, H3 PID 3912377, without generation. Static parity verified. Backend activation deferred while directing job 482111088c554570 remains running; no automatic restart scheduled. Evidence: reviews/runtime-transition-wait-20260913/evidence/verification.json.



## 2026-09-14 — Autonomous Ref2VA planning acceptance

PASS: Real-data-derived shot with approved The Smallest Fix canon; real Astra AUTO selected REF2VA without a forced mode and independently selected Ada identity, lantern identity and workshop environment. Pip remains in the shot/canon source but has no demand, slot or upload. The image-demand board preserved these demands with zero new storyboard images. Prompt, explicit frozen request, take, verified upload hashes and graph indexes 0/1/2 preserve Picture 1/2/3. Actual ComfyUI history equals the submitted graph; H3 take fc49013b4c0a45d2 succeeded, 864×480, 107 frames, 4.459s with audio. All seven requested planning/submission conditions pass.

174 relevant Python cases across focused runs; seven Node UI suites; actual browser inspection without console errors. Additional tests cover missing/stale/rejected refs, duplicate roles, optional omission, unsupported media/timestamp constraints, invalid scope/evidence, prompt/slot/hash tampering, continuation/group bypass, legacy compatibility and zero-anchor stale-status regression. Full source/job/asset/receipt evidence and verifier: reviews/autonomous-ref2va-20260914/REPORT.md, evidence.json and verify.py. Live data digests unchanged. Generation remains isolated and unadopted.
