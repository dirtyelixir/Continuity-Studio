## 2026-09-14 — Empty optional revision feedback means autonomous generation

The user clarified that they were waiting for generation, not withholding a creative answer. Old Studio UI templates could emit `Director requests a revision to shot_01: .`; a canonical extractor then treated that empty system wrapper as missing user intent and blocked another Shot. Interpret only the exact empty Studio-owned templates as no additional user constraint, with explicit per-Shot context and normal state/timing checks. Preserve nonempty/authored feedback verbatim and retain the original job request. New UI submissions supply an explicit directorial-autonomy instruction when optional feedback is empty. Do not ask the user to fill an answer that Studio never required.

Recovery retains the original provider output and old error receipts, shows running while validation executes, and records the actual latest failure. Read-only failed-job details expose saved story/script/counts and latest per-Shot receipts without presenting an unaccepted candidate as canon. Concurrent production revisions remain protected by existing adoption freshness checks.

## 2026-09-14 — Exact endpoint redundancy can be normalized at the owning Shot

A provider can repeat a start/end frame time and state even though the endpoint already belongs to its Shot. Treat only exact matching numeric endpoint time and identical state arrays as redundant serialization: remove those duplicate fields from a copied candidate before Frame validation. Keep conflicting values invalid, keep standalone Frame strict, and preserve original raw outputs. This is format compatibility, never semantic reconciliation or permission to adopt a proposal. Recovery continues through canonical-state and directing gates using the original provider. See reviews/endpoint-frame-recovery-20260914/ for implementation and live acceptance status.

## 2026-09-13 — GPU contention stays in the video queue

The Manager already supports pending GPU leases; Studio's zero-second acquisition bypassed waiting. Use positive native admission windows. A video worker renews a 30-second window on the same durable queued Take only after exact, endpoint-specific pre-admission busy refusals, including a busy mode switch. Keep the retry catch outside the upload/submission body. Paused/cancelled admissions, unknown refusals, transport ambiguity and mode/PID mismatch still stop. Never retry /prompt automatically.

Queued Takes are provably before uploads and submission intent, so startup can resume their original frozen requests with the existing freshness gates. Preparing records still fail conservatively; submitting records remain receipt-only recovery. Historic failed Takes are not revived. There is no promised global FIFO position across renewed windows or across H3/Klein switches; the installed Manager cannot queue a mode switch atomically. No sibling Manager/service changes are part of this fix.

## 2026-09-13 — One authority per frozen-moment fact, text verification before media

Duplicated free prose cannot both independently define an eyeline or power state. For a new image request, exact structured start/end/interior state owns explicit dynamic facts; descriptions supply composition and compatible unspecified detail. Preserve explicit revisions and authoritative timeline constraints. Automatically reconcile lower-priority descriptive drift into the prepared brief with quoted provenance, retaining original production/history. Production generation and directing review must explicitly address state/description/timing synchronization.

A separate same-preparer check judges the actual compiled image brief before a frame render. One actionable repair/recheck is allowed, with durable attempt intent and no uncertain retry on recovery. This intentionally adds text verification before media cost; a model pass never certifies pixels or human acceptance. Scope the new policy to image/source instructions and complete request fingerprints; do not globally invalidate unrelated adopted directing reviews by changing the pinned shared-method bundle. No regular-expression semantic guesses, renderer fallback, automatic canon adoption or media retries are part of this repair.

## 2026-09-13 — Visual board owns exact moments and panel review

Keep editorial view count, frozen-image count and H3 generation count independent. Plan the complete ordered board from adopted edit uses, with anchors at exact edit-in and only justified additional states. Store interior keys with explicit source time/state; never mislabel them as original endpoints. Reuse an existing frame only at its own time and preserve source/canon/dialogue. Treat human per-panel approval as separate image-byte/source-bound evidence. An adopted board gates its downstream H3 scope; legacy unadopted paths remain available. Batch missing-image submission uses real configured renderers and durable deduplication, and export preserves the board and approved originals. See [STORYBOARD.md](STORYBOARD.md).

## 2026-09-13 — Adopted execution arrangements are visible H3 inputs

Treat the adopted grouping receipt and the latest grouping candidate separately. H3 routes an active saved group member to the group's complete workspace, while independent sources retain full generation duration and separately displayed editorial trims. Feed only current independent arrangement requirements into new source prompt requests; do not apply obsolete planner mode suggestions or rewrite saved media/prompts. An active native definition has its own validation and remains inspectable after its planning analysis becomes stale; stale analysis is not authority to bypass current generation gates. Keep independent-source navigation and archived-group recovery available.

## 2026-09-13 — Preserve detailed image revision requirements

Allow up to 4,000 characters in PreparedImage.requested_changes so a multi-issue visual review is not rejected by a summary-sized 1,000-character limit. Keep the runtime and owned export schema aligned, preserve the complete revision verbatim, and retain the 7,500-character compiled prompt guard. This capacity fix does not authorize automatic regeneration or reinterpret incomplete historical correction receipts as accepted results.

## 2026-09-13 — Output budgets are limits, not completion guarantees

Keep configured context capacity and output allocation separate. A passing input preflight cannot certify that a reasoning model will finish within max_tokens. Record numeric usage and reasoning counters without storing private reasoning, distinguish historical unknowns from zero, and show the frozen budget on exhaustion. Do not silently raise limits, disable thinking, change providers or automatically charge another attempt to obtain completion. Monolithic directing review still needs explicit output-aware decomposition before it can claim automatic recovery.

## 2026-09-13 — Work records lead with creative conclusions

Execution completion and creative acceptance must be stated separately. A directing-review record first shows its saved verdict, findings and actionable recommendations. Render shot names from the frozen reviewed source, keep original evidence accessible, and put manifests/hashes/raw transport records in a closed technical section below. Current, candidate and historical applicability determine next-action entry points; historical reviews cannot approve the current plan. Read-only live progress must refresh the actual result without expanding unrelated disclosures or replacing unchanged controls.

## 2026-09-13 — Human-approved identity pixels and scene-derived asset batches

A director may keep a visually preferred identity image even after canon changes or a failed four-view review. This is an explicit human adoption, not an automated review pass or a silent rewrite of old generation evidence. Preserve the historical asset and create a current applicability record when needed; accept uploaded images through the same manual authority. Keep revision/source guards and invalidate dependent references normally.

Scene batch membership comes from the scene location and actual shot entities, never manual scene assignment. Include needed public identities once, skip approved/pending/in-flight/unresolved work, and preview the concrete generate list before explicit submission. Preserve receipts before spending; duplicate requests return the same receipt and uncertain interrupted enqueue intent cannot automatically replay.

## 2026-09-13 — Background work must remain visible while the user works

Production navigation alone does not communicate execution. Place named queued/running/waiting work ahead of stage guidance and show live activity in each related stage, using existing queue receipts and saved checkpoints. Keep the newest terminal result visible and distinguish generation from adoption. Unknown capabilities remain visible globally even without a known stage mapping. Refresh only status surfaces while editing, viewing a dialog, playing media or awaiting a request; do not overwrite drafts or replace unchanged controls. Never infer a percentage, queue position or completion from elapsed time, and explicitly mark stale status after a read failure.

## 2026-09-13 — Guided proposal decisions

A blocked proposal must offer the applicable next action, with three visible steps: revision, automatic directing review, then human review/adoption. Keep raw review detail expandable. Pending review must not suggest unnecessary revision, and stale proposals must lead to planning from current production because the revision endpoint rejects old candidates. Revision submission opens progress for the exact returned job; read-only polling updates that dialog and stops when it closes or its project changes. Never auto-submit repairs, repeat review, adopt, or change creative providers. Existing freshness and director acceptance gates remain authoritative.

## 2026-09-13 — Keep grounded LoRA evidence without failing on surplus non-quotes

Each selected image LoRA must retain at least one exact nonempty quote from the returned visual brief. Deterministically discard only surplus evidence strings absent from those fields; preserve selected IDs, reasons, summary, weights, triggers and all visual content. Persist the original selection and discarded strings separately, include the audit in exports, and apply the unchanged strict final validator. No replacement quotes, adapter removal, provider calls or media retries are implied. All-invalid evidence and other schema/catalog/compatibility failures still stop.

An explicit identical retry may reuse an older brief saved before this citation failure, only after checking the original request/source, complete frozen reference manifest and pixel hashes, request fingerprint, normal brief validation, exact compiled prompt and corrected final LoRA plan. Cancelled jobs or any ComfyUI receipt exclude this fallback. Original failed job and files remain unchanged.

## 2026-09-13 — Workflow position and page location are distinct

The user's continued confusion supersedes an overview-only progress strip. Add a default production overview and a shared, read-only guide across production pages. Keep page navigation and the recommended production step separately labelled: users may browse references while a new story revision needs review, and different Shots can progress independently. Each stage has a clear completion criterion and direct destination; stage 5 opens the real editorial page, with optional voice work alongside it.

Use existing authoritative saved state, not new persisted workflow flags or a completion percentage. Same-revision story candidates can be reviewed without treating older successful jobs as unadopted; current revision work and aggregate directing-QC failures explain wait/recovery/revision before new media work. Respect each Shot's selected mode, freshness and backend render checks; never demand an unnecessary end frame or count orphan/stale/unselected video output as adopted. Recommendations open existing controls and do not automatically submit or adopt anything. Actual editorial/media verification remains explicit; no inferred whole-film completion.

## 2026-09-13 — Image-derived identity remains an editable proposal

The identity editor may request a vision analysis of the exact currently displayed entity image through the configured identity_from_image provider. The result is a queued, source-bound description/facts/uncertainties draft. Freeze pixels and identity/revision before execution; reject foreign images and voice-only identities. Images govern visible appearance, while nonvisual story facts must not be invented from appearance. Never save or approve canon on analysis completion. Show the candidate beside the existing editor fields; explicit application changes the draft only, can be undone, and normal version-checked Save establishes the revision. Name, entity ID/type and public/scene scope are not inferred from pixels.

## 2026-09-13 — Studio requests scoped Manager recovery of a proven dead executor

The user authorized completing automatic fault recovery through VRAM Manager. This supersedes the prior report-only behavior for the narrow verified ComfyUI failure case. Studio owns detection, when to request recovery, user-visible status and job/receipt reconciliation. Manager independently owns process identity, admission fencing, affected-queue ownership, service-scoped stop/start and readiness. Its existing global release operation is unsuitable because it can terminate unrelated compute clients; add a scoped endpoint instead.

Never infer death from idle GPU utilization, a slow request or missing logs. Only positively identified prompt_worker failure in this exact managed process permits automatic service replacement. Persist queue/history and intent before stopping. Keep the same mode; do not replay submitted graphs. Preserve waiting requests, refuse other granted work, serialize duplicate requests and retain failed attempts across coordinator restarts. A crash recurring within five minutes permanently blocks automatic repair of that incident until the underlying service is handled. See MANAGED_COMFY_RECOVERY.md and live acceptance evidence.

## 2026-09-13 — Isolate production queues and distinguish HTTP health from executor health

General text (2), staged chapter (1), and image (1) workers have independent bounded lanes. Every existing enqueue/resume/recover entry uses the same router; UI queue positions use submission/resume ordering and include running project names. Startup dispatches only never-started queued requests with original IDs/frozen inputs. Interrupted running work still requires explicit recovery; cancellation markers settle without provider calls.

For local images, cancellation stops result polling and blocks late adoption, preserving the remote receipt and avoiding global interrupts. Positive prompt_worker death in this exact local process's journal fails pending waits and blocks further paid preparation/submission. Short network waits and the existing overall timeout cover transport failure; absent logs or low utilization are not treated as proof of failure. Complete original history may still be recovered even if the current executor is unhealthy. Studio does not restart GPU services or automatically resubmit uncertain media.

# Continuity Studio — decisions (2026-09-08)

## 2026-09-13 — Recheck image interpretation conflicts before failing

The Huang Tai failure 549be70f5a174f62 misclassified a review's current-image defect (portrait still extends below hips) as a desired output requirement conflicting with its requested head-and-shoulders crop. Image preparation should perform one bounded re-evaluation of reported semantic conflicts using the same selected provider, original request and frozen reference pixels. It must preserve explicit desired changes, reference authority and genuine irreconcilable conflicts. Only a normally validated, compiled brief can reach the renderer; no automatic media retry or provider fallback. Preserve the original candidate and separate correction evidence, respect cancellation, and do not repeat an exhausted correction after recovery. Schema, transport and unrelated validation failures retain their existing behavior. Acceptance and deployment status are recorded in STATE.md.

## Product hypothesis and boundary
A solo narrative director needs a persistent, review-driven production book, not a prompt editor or autonomous swarm. Idea → narrative proposal → approved production bible (characters, locations, props) → scene/shot plan with single-moment keyframes → reference-first image production → visual review → per-shot H3 package. Small projects first. Final video rendering, multiplayer collaboration, arbitrary executable plugins and NLE are deferred.

## Architecture
Python/FastAPI serves a same-origin browser application with plain ES modules. SQLite transactions retain project documents, immutable revisions, assets, jobs and settings; local files contain actual images and job evidence. Chosen for local durability, simple backup and direct access to installed Codex, without Electron, a second frontend server or a distributed queue. Production documents have stable IDs and validated relationships; history is not canon. All mutations use revision checks. Jobs capture immutable input and produce reviewable proposals; stale jobs must not overwrite newer work. Worker process recovery marks uncertain in-flight work interrupted rather than spending again automatically.

Astra (gpt-6-astra) via authenticated Codex CLI is the default reasoning and image orchestration provider. Built-in image rendering through that CLI was exercised with real canonical assets, five storyboard keyframes and vision reviews; see ACCEPTANCE.md. Alternative OpenAI-compatible HTTP and manual providers are explicitly selected per capability. No automatic downgrade. Images are generated from approved canonical references, then inspected with Astra vision. Human approval establishes canonical identity. A failed review requires revision, not automatic repeated paid generation.

## Continuity
Project → scenes → shots → keyframes. Canonical entities hold identity facts and approved asset IDs. Shots link entities, carry explicit start/end states, framing, blocking, camera, beats and dialogue. Generation records persist the exact canon/shot snapshot, reference IDs, prompt, provider and digest. Approved references resolve automatically; no unapproved reference fallback. Canon or production edits invalidate dependent approvals; prior images remain retained. Image identity is probabilistic: reference conditioning plus visual review, never a claimed guarantee.

## Extensions
Instruction skills use SKILL.md plus a small versioned studio.json manifest. Discover locally; install an immutable hashed copy, disabled by default; explicitly enable and grant declared permissions. Instruction skills augment Astra; optional provider selection is separate. New text capabilities can register their own instruction contract and show in the Skills workspace without new routes. HTTP providers are server-configured, secrets remain in environment. No arbitrary shell scripts from downloaded manifests. Skills are version/hash pinned in job evidence. Built-in H3 export is a deterministic formatter of Astra-authored structured direction, replaceable by Astra/HTTP/skill capability.

## UX
A restrained warm-paper production workspace, dark navigation, scene/shot strip and large frame viewer. Review decisions are primary actions; prompts and provenance are expandable details. Visible job progress/errors/retry, editable canon and shots, rejection notes, preserved alternatives and ZIP export. No fake demo-generation path.

## Readable original asset library

User needs original local images organized for a nontechnical director. Stable IDs remain internal identity; original paths use project title, Characters/Locations/Props, and scene/shot names. Per-target sequential versions retain every candidate. Titles are sanitized with Unicode preserved; duplicate names receive numeric suffixes. A persisted layout registry keeps folder locations stable across later creative-title edits. Generated catalogs and prompt/provenance sidecars expose approval status without encoding a mutable status into the image filename.

Migration backs up database and original pixels, copies and hashes each image, updates only asset.path, then atomically replaces the historical pathname with a compatibility link. Frozen job evidence is unchanged. H3 freshness compares reference identity/role/label rather than file path, so reorganization cannot discard valid refined prompts. GUI reveal resolves the actual canonical image pathname.

## Scene owns the global Prompt

Latest user correction supersedes earlier Shot-inheritance/override wording: a Scene contains many Shots, and only the Scene owns a global Prompt. Each Shot owns only its director/storyboard Prompt. No Shot global field, override or per-Shot global file is exposed or accepted. Optional composition references are assigned stable slots and defined once in the Scene global; each Shot requests its own composition in its Shot Prompt. Combined text is a derived external-tool representation, not a second configurable global. Historical settings/results remain recoverable; legacy Shot globals are excluded from active configuration without mutating stored history.


## Evidence-backed incoming segment decisions

The Director handoff is an actionable instruction surface. Replace blanket previous-segment defaults with a separate h3_guidance provider capability (Astra by default). Analyze the full storyboard plus current delivered prompts, use structured start/cut/extend/uncertain decisions and Traditional Chinese reasons, validate order/previous-shot links/exact evidence excerpts. This is semantic director reasoning, not keyword classification. Motion Context extends continuous footage; shared identities/state/audio alone are insufficient. Unknown/stale decisions remain unknown. First segment is structurally off.

Reviews are immutable jobs keyed to a policy/content hash, reused across reloads and ignored when creative inputs change. Opening the handoff queues missing analysis; GET remains read-only, failures require explicit retry, and configured manual/HTTP providers remain respected. Explicit new manual overrides use guidance_mode=manual; legacy guide booleans cannot silently override AI decisions. Saved master settings and effective per-segment flags remain distinct. No ComfyUI modifications or video generation accompany this analysis.

## Source-preserving story import and storyboard planning

Pasted/imported stories are distinct from open-ended ideas. Use a new storyboard capability, Astra by default, returning the existing Production model plus source-to-shot coverage and stated adaptation assumptions. Preserve the submitted source independently; screenplay input is not rewritten by shot planning. Adopt through the existing revision mechanism, then reuse the image/canon/Ref2VA pipeline. Support bounded plain text, Markdown and DOCX body text; do not silently condense a novel to fit the short-project schema.

Use a content-pinned, licensed snapshot of the installed short-drama-storyboard craft references through a Studio JSON adapter. DirectorSKILL was initially deferred; the content-led director recommendation decision below supersedes that deferral. The shuohao segment/cut/I2VA model is incompatible with the current Scene/Shot/Ref2VA handoff without explicit adaptation; do not replace that hierarchy merely to install a skill. Hosnye remains research-only pending license clarity; the cajias marketplace is discovery/packaging, not an independent directing method. Structural coverage is not proof of semantic fidelity. See STORY_IMPORT.md for source versions, tradeoffs and limits.


## Images require an explicit generation action; uploaded production references

Creating/adopting a text plan only creates production descriptions. Uploading a production input stores immutable original bytes and a role/scope/hash sidecar; it creates neither image jobs nor approved assets. Separate project style inputs from target-specific style/identity inputs and from finished candidate imports. The generation form selects applicable inputs and is the sole canonical-card image launch path; remove the immediate bulk-generate action. Existing finished-image import/review remains available. Source inputs never silently become canonical references, never consume canonical approval IDs, and are frozen into job provenance with their role and original path. Selected inputs survive explicit job retry. Enforce the chosen image provider's actual attachment budget including canonical/layout inputs; do not silently omit selected images.

Nonempty source lines are traceability units, not a reason to reject a story. Remove the 200-line gate while preserving the existing 20,000-character and file/parser budgets and exact source coverage.


## Story outline and ongoing story chapters

New-work UI defaults to source_kind=outline: the project's idea stores the whole-series outline, independent of adopted production. A real story chapter contains Scenes → Shots; it is distinct from the historical Director `chapters` field meaning shot segments. Story chapter drafts live in SQLite story_chapters, with optimistic versions; outline edits use brief_revision. Legacy idea/story/screenplay projects retain their existing single-work behavior.

Astra develops only a selected chapter, using the frozen outline, shared canon and already adopted chapter writing as context. Production.chapters records chapter ownership and writing inside immutable production revisions. Adoption namespaces scene/shot/frame IDs per chapter, reuses canonical entity IDs, rejects redefinitions of existing canon, merges only that chapter, and preserves other chapters and their references. Proposal adoption checks production revision, outline/draft snapshot and selected directing method. Forty shots is a per-chapter limit; aggregate works can exceed it. No automatic future-chapter generation or conversion of legacy projects. Large-series context compaction is a future optimization; this iteration passes adopted chapter writing as context.

Visual medium is selectable at creation: realistic cinema, 2D, 3D, stop motion, watercolor, black-and-white comics, Astra suggestion or custom. Aspect ratio is separate, with optional notes. The resolved text persists as project style and enters chapter generation. Director recommendations are a separate story-level camera/staging choice; selecting one on an outline work saves it for the next selected chapter, never queues a storyboard of the whole outline. Existing adopted global production style stays stable when later chapters are merged, preserving approved image dependencies; directing instructions still enter chapter shot descriptions.


## Content-led director recommendations and one chosen method

Use the pinned MIT DirectorSKILL 2.1.0 snapshot as Astra's 20-lens knowledge base. Compare content, emotional beats, reveal order, medium and timing before returning three ranked, evidence-backed options with concrete methods and tradeoffs. No keyword-to-director lookup or pseudo-objective scores. The user chooses one, and the existing storyboard/narrative adapter receives that full module. Source, canon, explicit medium/aspect/duration and application constraints override upstream stylistic prescriptions. Short-drama-storyboard still supplies source/continuity craft; H3 still derives from adopted production.

Selection is separate from adoption: persist creative intent without changing production or images; freeze the selection in proposal input and reject adoption after the choice changes. Record applied direction atomically with the adopted revision, distinguishing series chapter scope. Recommendations become stale when their content basis changes, while a deliberately selected artistic direction persists. Story-level recommendations read the outline and adopted writing, not unadopted chapter drafts. Default Astra remains provider-switchable. See DIRECTOR_STYLES.md for versions, guardrails and live acceptance.
# Shot speech boundaries (2026-09-08)

Empty dialogue arrays must produce explicit non-speaking visual/audio direction, rather than leaving vocal performance unspecified. Spoken dialogue retains its words, language, speaker and timing as the guide for visible articulation; muting an export cannot repair unintended talking animation. Apply a deterministic speech-direction line to effective Ref2VA prompts so existing drafts and saved refinements benefit without rewriting stored creative provenance. Preserve explicit nonverbal breathing/laughing; never require a silent soundtrack just because no one speaks. Reject extra or duplicated tagged utterances. Do not promise precise later dubbing from text timing alone or automatically switch ComfyUI audio settings.

## VoxCPM2 character voices as postproduction

User explicitly selected VoxCPM. Use the installed VoxCPM2 model for the new postproduction audio capability; retain Astra for existing creative/image/review capabilities. Character voice identity is an explicitly adopted, immutable WAV reference, not a description or random seed alone. Voice settings, jobs and line selections live in dedicated SQLite tables, independent of visual revisions. Exact dialogue/timing/reference hashes determine whether a take is current. Adopted audio enters production exports with provenance. Natural duration remains intact; overrun is reported for editing. Runtime obtains a PID-owned existing VRAM Manager lease before GPU imports, performs real synthesis in an isolated child and releases on exit. No GPU service modification, fallback model, auto-generated video track or silent timing changes.

All adopted characters receive a voice slot. For 下一站：長洲, Astra authored distinct audition directions for the twelve canonical character/voice entries. The crowd entry is explicitly one representative timbre, not multivoice crowd synthesis; infected/child audition sentences are voice tests, not additions to screenplay dialogue. Radio voices retain clean source audio for later effects. These new live candidates remain unselected for the director's listening decision.

## Crowd references versus individual four-view sheets

Use `Entity.kind=crowd` for collective cast, leaving individual `character` four-view policy intact. This avoids adding a serialized default to every entity and invalidating unrelated approved images. A crowd asset captures member diversity, clothing and shared condition; it is not a one-person turnaround, a fixed roster for indefinite crowds, or universal blocking for every scene. Featured recurring individuals can be independent characters and must not be duplicated as extras. Crowd image approval uses existing general review/human decisions, with no single-person layout gate. Existing representative crowd voice profiles remain available; this does not add multivoice synthesis. Classification changes use normal revision/dependency invalidation; old originals and provenance stay intact.

## Explicitly edited prompt text

A direct user prompt edit is an authoritative manual direction, stored verbatim via prompt_edited on Scene/Shot delivery settings. Automatic speech/composition instructions continue for generated and legacy default prompts; explicit manual text is not silently rewritten. Structural/dialogue/reference validation still reports issues without blocking storage of a draft direction. Browser drafts are separate from saved production settings, isolated by project/Scene/Shot, and conflict checks precede optimistic API saves. Saving one field preserves other effective provider outputs and guidance settings in the Scene.

## English, scoped delivery directions

User correction: person/character names retain their exact canonical spelling and original language. Do not translate or romanize names (e.g. 陳樂言, 昌叔); this is an explicit exception alongside original dialogue to English descriptive prose. Historical prepared names are resolved through canonical entity IDs without rewriting immutable job output. The legacy schema key name_en is retained for compatibility but stores the original name for characters, crowds and voice identities. Language validation permits only the supplied original names, not arbitrary non-English descriptions.

All delivered prompt prose is English except exact original dialogue inside canonical language-tagged `<d>` blocks. The Traditional Chinese interface and source production remain readable in their original language. Do not concatenate `Production.style` into a Shot: it may contain adaptation decisions, future events, shot counts and project bookkeeping. Astra prepares concise reusable Scene appearance/light plus each Shot's own camera, actors, owned objects, timed actions and sound. Every action must identify its actor and object owner; ambiguous source clauses require semantic interpretation, not literal translation.

The `h3_prepare` text capability freezes a Scene source and policy hash, including relevant canon and style as interpretation context only. Preparation can happen before reference images exist; stable Entity tokens resolve to approved Subject/Picture slots later. Opening an unprepared Scene submits its text preparation, with explicit status and retry, independently of manual image generation. Pending mixed-language fallback text cannot be copied as production direction. Validate scope tokens, section order, English script, dialogue words/order/languages; these mechanical checks do not prove semantic fidelity. Preserve explicit manual edits and report invalid language instead of silently translating them. Segment-guidance analysis follows the prepared prompts. Silent mouth-only scripted lines retain articulation windows without becoming audible speech.


## 2026-09-09 — Asset scope and audio-only canon

Public versus chapter Scene is organizational metadata on stable canonical identities, not duplicated assets. Explicit public scope supports the main protagonist from the first chapter; auto scope promotes identities used across adopted chapters, while explicit Scene scope remains local. Scene membership follows its location and Shot entity references.

A voice canon kind describes an identity that never appears visually, including radio broadcasts and the closed-door mother/child in the current adopted script. It preserves sound, timing, dialogue and existing voice profiles while excluding image jobs, visual slots and missing-picture requirements. Visible actors speaking offscreen in some shots remain visual characters. New narrative/storyboard requests must distinguish these cases.

Scope is excluded from visual dependencies and English-preparation source identity, so organization alone never forces regeneration. Prepared output from the scope rollout can be reused only with a verified complete input source and exact equality after removing scope. Actual voice-kind or story changes still invalidate relevant prepared content. Source, canon IDs, media bytes and past job records remain durable.

## 2026-09-09 — Props belong to Shot reference inputs

The user distinguishes asset-library public identities from H3 Scene common parameters. Keep reusable characters/crowds/locations in the Scene input; handheld props and their visual definitions belong to each Shot that actually references them. The existing canonical Shot membership remains authoritative; no inferred story edits or asset deletion. A Scene's prop union must not force a prop into unrelated Shots or block them for a missing prop image.

Director Ref2VA groups support indexed local images merged with common images. Assign shared slots first, then each Shot's local props, never overriding a shared slot. Per-Shot prop definition lines precede summary and continue the single subject_definitions section when concatenated with the Scene global. Prepared Entity tokens resolve against each Shot's actual mapping; no new text or image generation is needed for existing prepared results. Local slot meanings can differ across separate Shots. Clear the previous group's unused local slots when reusing a group. Keep the global and per-Shot prompts separate, with six sections in each complete output.

Refinement validates that the global references only common slots and all attached references are defined in the combined prompt. Local asset approvals participate in refinement dependency hashes. Explicit manual text remains verbatim and reports old global-prop mappings for review. The API/export expose local_references and per-Shot missing_references, and the UI shows the actual assigned slot numbers in each Shot.


## 2026-09-09 — Reviewable per-Shot text regeneration

Use a dedicated h3_shot capability rather than rerunning all Scene directions or the screenplay. Freeze the selected Shot, relevant canon/reference assignments, Scene global and current effective text, with an optional unsaved browser draft as the rewrite starting point. Generate a candidate without mutating production or delivery. Explicit adoption uses existing delivery history and preserves effective sibling/global text. Check current source identity under the mutation lock and protect browser drafts changed after submission. Keep originals, failed jobs and older candidates. Status freshness must use complete internal job hashes, not the API's shortened job input summary. Repeated adoption is idempotent.


## 2026-09-09 — Scene global-only regeneration

Add h3_global as an independent reviewable text capability beside h3_shot. Freeze the Scene common references and every unchanged Shot in its source; candidate completion never applies automatically. Adoption changes only the Scene global and freezes effective Shot text so invalidating an older h3_scene result cannot revert Shots. Preserve original person names, translate location/object labels to English, and keep props local to Shots. Apply source and browser-draft conflict checks. See SCENE_REGENERATION.md.

Global-only regeneration validates that the new global adds no dialogue, rather than rejecting independently edited dialogue in unchanged Shot prompts. Existing Shot validation issues remain visible; h3_shot/full generation retain strict canonical dialogue checks. This avoids making a global appearance revision overwrite or block separate user edits.


## 2026-09-09 — More than five keyframe references

The Astra image tool limits both recent-image selection and explicit path lists to five inputs (confirmed by live attempt 441769ad0a5c415d). Do not reject a valid Shot or discard references. For more than five approved references, retain the first four independently and paste remaining originals at native resolution into a numbered transport board in the job directory. Attach those five inputs and use the proven recent-conversation selector. Explicit local paths hit bwrap permission errors on this host (attempt a00ac24dc6804a27), even inside the job workspace. Original source images, IDs, order and dependency hashes remain intact; the board is not a new canonical asset or H3 reference. The model must use each tile only for its original role and never reproduce the board/panels. One-to-five-input generation keeps its existing route. New storyboard requests no longer impose an artificial five-entity budget; frozen older requests retain their stated budget.


## 2026-09-09 — Guidance analysis independent of English preparation

Remove the all-Scenes-prepared frontend gate. Shot boundaries can be assessed from adopted canonical storyboards before English preparation is complete; source explicitly flags unfinished Scenes and the analyst must avoid placeholder evidence. Only the actual missing/contradictory boundary earns uncertain. Pending means no matching job, not running. Expose queue/running/stale-active/manual/failure separately with start/retry/details controls. Retain strict evidence and freshness checks and manual overrides.

## Explicit frame preparation alongside Ref2VA (2026-09-09)

Superseded navigation boundary: the user approved one unified 影片準備 workspace. The adopted Shot mode controls the material and prompt UI: frame modes use their frame flow; Ref2VA embeds its existing Scene-global/Shot-local handoff. Keep one Scene/Shot selector and original storage boundaries; do not merge or overwrite the distinct prompt formats. Scene globals remain shared across Ref2VA Shots, while each selected Shot retains its own directions. Legacy routes alias the unified page and never change a saved mode merely by navigation.

A new 影片準備 workspace makes conditioning a per-Shot creative decision: default planning with I2VA, optional FL2VA endpoint pair, or the existing Ref2VA workbench. Astra provides source-grounded mode advice, single-moment blueprints and concrete checks. Recommendations do not render or approve images. The application preserves canon, voices, Ref2VA global/Shot edits, images and old routes.

Frame-mode prompt generation inspects the selected current approved images and converts the effective Shot direction into the official three-field contract with exact frame alignment. Candidates require review/adoption; editor drafts, source/frame hashes and optimistic settings revisions prevent accidental replacement. Missing/stale frames block handoff, with no automatic T2VA fallback. A later cross-frame/source conflict is returned separately as Traditional Chinese frame_issues and blocks ready copy/export/adoption, even when individual images were previously approved. Do not paste contradictory constraints into the video prompt. User can repair the images or choose an appropriate different mode and regenerate.

Keep each Shot an independent handoff with previous-video guidance off in this new frame workflow. The existing Ref2VA connection analysis remains intact. Model-family batches are separate; no claimed speed ratios, fixed FL2VA percentage, GPU benchmark, automatic render or direct ComfyUI workflow injection. See FL2VA_WORKFLOW.md.

## Optional image approval notes (2026-09-09)

An explicit user approval establishes adoption even when the user leaves the note empty. Review concerns remain visible and immutable; record a default human-adoption note rather than requiring the user to write a reason. Keep source/reference freshness checks. Use approval-specific copy and optional notes instead of the generic creative-feedback form. This supersedes the earlier mandatory override-note policy.


## 2026-09-09 — Explicit DeepSeek creative authority

User requested a complete DeepSeek alternative in Settings. This explicit choice supersedes Astra-only creative defaults when selected, while Astra remains the unchanged initial setting. Use one transactional profile apply and a persisted default provider for newly added instruction skills; preserve all prior job/provider snapshots and adopted canon. Per-capability edits remain supported and are labelled Custom rather than misrepresenting mixed routing as entirely DeepSeek.

Use the official DeepSeek API: V4 Pro text by default, explicit V4 Flash option, and V4 Flash Vision Exp for any image-bearing request. Never drop images to fit a text-only model, advertise DeepSeek as an image renderer, or fall back to Codex. DeepSeek profile image rendering must be explicitly manual or a configured non-Codex HTTP image service. Credentials remain environment-only. Readiness is a safe /models check; missing keys are visible and actual provider generation is not claimed verified without one. See DEEPSEEK.md and acceptance evidence.

## Complete copyable H3 prompts despite advisory image concerns (2026-09-09)

User explicitly rejected receiving only image-review notes in the video prompt section. Supersede the v2 empty-text/conflict gate: approved-frame jobs must return a structurally valid complete H3 prompt even when image discrepancies remain. Preserve intended storyboard/dialogue and list discrepancies separately; do not invent a corrective transfer or insert conflicting prose into the H3 prompt. Human adoption decides use; image warnings no longer veto it. Missing/unapproved/stale frames, stale candidates, invalid format/reference labels/dialogue and browser drafts remain guarded. Display the complete candidate inline with an explicit adopt-and-copy action. Old empty review-only results are labelled honestly and require regeneration. No source/image/voice mutation or automatic video rendering.

## Locked per-Shot mode and explicit regeneration choice (2026-09-09)

Once a Shot has a saved mode, display the chosen card as locked and grey/disable both alternatives. Changes go through regenerate recommendation, with AUTO selected by default or an explicit I2VA/FL2VA/REF2VA constraint; persist that constraint in the job, include it in request deduplication and reject mismatched outputs. Existing current mode remains until explicit adoption. Show reason inline; details/evidence/blueprints stay in the review modal. Distinguish unadopted candidate from adopted strategy, including staleness. No automatic adoption or generation from card display.

## Asset groups and explicit rejected-file deletion (2026-09-09)

Group review cards by target identity, not generated version; expose versions separately. User requested local deletion of rejected files. Provide explicit rejected-only deletion with reference/active-use checks; preserve approved/pending/stale files, other versions and job audit history. This is not automatic cleanup on rejection.


## 2026-09-09 — Source interpretation and renderer instructions are separate

Production.style is a reusable visual look, never a chapter director notebook. New proposals place per-Shot camera, acting, sound and transitions in their own fields. Historical mixed style remains immutable source context. Every new automatic image job first invokes the provider-switchable image_prepare text capability (Astra by default), validates its bounded visual fields, then freezes the exact renderer prompt and hash before media execution. Text preparation failure never triggers a renderer fallback. Reference roles/layout/fidelity are assembled per target; Codex execution instructions are adapter-only and never sent to an HTTP image endpoint. Canonical dependency hashes remain unchanged so this prompt-policy correction does not revoke approved images.

For location/frame preparation, matching Scene appearance/light and its time override scene-dependent fragments in legacy style. Reviewer attachments retain their roles but get new review indices; never paste the renderer reference map into the reviewer mapping. Manual prompts and historical asset instructions remain unchanged. Unprepared legacy H3 output is explicitly a draft, with copy disabled and a separate export directory; prepared Ref2VA speech maps into the base-mode integrated timeline. See PROMPT_ASSEMBLY.md.

## 2026-09-09 — Selected design governs a proposed image candidate

Supersedes the text-only image-brief preparation decision: input roles alone cannot resolve a visual reference conflict. image_prepare must inspect the same actual image pixels as the renderer. For an entity asset, selecting an uploaded identity/design is authorization to propose that visible design, not automatic canon adoption. Remove the prior same-target approved identity from competing inputs; retain explicit edit targets only with lower visual authority. Explicit changes govern, selected subject pixels outrank legacy appearance, style/layout examples never provide identity, and approved pixels outrank stale appearance prose when no new design is selected. Preserve required layout and shot state/time. Conflicting primary designs require a reported conflict rather than silent blending. Review uses the same authority and prepared brief. No live canon/schema/hash migration.

High-reference preservation is prompt-level emphasis with the current built-in adapter; it is not an undocumented numeric/model parameter. Preserve actual reference source paths, order and SHA-256 snapshots, and do not claim CLI attachment evidence proves the renderer's internal conditioning. Display uploaded inputs in asset provenance so the visible audit does not misleadingly suggest text-only generation.


## 2026-09-09 — H3 Director workflow preservation and integration direction

Preserve the user's exact all-in-one workflow as an immutable-by-convention original, with hash/source metadata, separate from pinned upstream reference code. Treat embedded notes/prompts as data, not execution authority. The user asked to investigate first; archiving does not enable a runtime provider or silently update ComfyUI. Prefer the existing Director pack v1 format as the next delivery integration: one Scene/model-family batch, exact saved prompts and approved original media, stable reference slots and Shot IDs, explicit continuity boundary handling. Retain Studio as creative/canonical authority and ComfyUI as video execution. Keep workflow loading, pack import and Queue as distinct actions; any future direct submission must be tracked with output provenance and existing VRAM Manager coordination. See H3_DIRECTOR_WORKFLOW.md.

## 2026-09-09 — Review reminders respect newer adopted versions

Review eligibility is a projection, not a destructive state transition. Suppress pending/stale candidates whose version creation time is not later than a current approved version of the same target. Keep newer candidates, target isolation, stale-without-approval recovery and every historical version. Reuse this rule for review grouping, sidebar counts and canon-card reminders. Deliberately approving an older version does not silently reject later alternatives. No schema or durable status change.

## 2026-09-09 — Rejection authorizes image disposal

The user's explicit instruction supersedes the earlier preservation/default separate-delete policy for rejected images. A reject decision now authorizes removal of that version's locally stored image and known matching production copies, while keeping text audit. Canonical/stale/superseded versions are not automatically rejected or removed. Uploaded references, shared originals, active jobs and saved settings remain protected; the response must distinguish actual deletion from deferred disposal and explain the dependency. Retry after project work completion/failure/cancellation. Version filenames remain reserved in deletion-event history to prevent old immutable paths from resolving to different pixels. Cleanup of preexisting rejects in this turn is scoped to the active 下一站：長洲 project. Provider result paths are constrained to known generated-image/job roots and must match the rejected original's decoded RGB pixels before removal.

## 2026-09-09 — Recoverable project deletion

作品管理 offers deletion with an explicit impact warning, exact-title confirmation and server-checked production revision. Deletion moves a work to 已刪除作品, with a visible restore flow; it does not purge media or free disk space. Only projects.deleted_at changes, plus deletion/restoration audit events. Chapters, canon, approvals, prompts, histories, settings and files remain intact. Active text/image/manual jobs or voice/import work block deletion under the same submission lock and a SQLite immediate transaction. Deleted work is hidden from active lists and cannot be edited/generated until restored. Current-project and cross-tab refresh state must recover without repeatedly fetching a removed work. No live work should be deleted as feature acceptance.

## 2026-09-09 — Explicit per-Shot H3 video production

User now requests Studio one-click implementation, superseding research-only scope. Submit only on the explicit generation action; no live video or plugin update in this implementation acceptance. Freeze exact approved image bytes, saved prompts, mode and seed; use the original main graph with correct model family. Existing ComfyUI VRAM middleware owns GPU admission. Persist intent and receipts; ambiguous results permit query/recovery only, never automatic resubmission. Separate successful take review/adoption from canon. Independent modes only: continuation-required Ref2VA stays in the existing Director handoff until a real chained-input implementation exists. See H3_ONE_CLICK.md.


## 2026-09-09 — Local image execution is independent of creative authority

Add explicit comfy_local image capability rather than treating Astra/DeepSeek as interchangeable image renderers. Preserve Astra defaults; allow per-job overrides and an independently selected renderer in each creative profile. Archive original canvases unchanged, then build pinned Studio API recipes without upstream sample prompts, input filenames or auxiliary LLM calls. Selection follows target kind/reference structure and explicit operation, with no keyword inference of face transfer/masking/outpaint or provider failure fallback.

Use the existing ComfyUI VRAM admission hook, unique durable submission tokens, exact output-node mapping and recoverable receipts. Never repost uncertain submissions. One target still receives one candidate asset; a four-view sheet uses separate views composed into that candidate after one-pass layout failures. Freeze the global brief and each per-panel actual prompt. Selected references, job lineage and human approval remain authoritative; supported branches and observed visual acceptance are reported separately. See LOCAL_IMAGE_WORKFLOWS.md.


## 2026-09-09 — Superseding character-sheet layout example

The user's newly attached 錢德貴 sheet sets the current layout: front full body → one side full body → rear full body → enlarged front face. It supersedes the old portrait → left → right → rear instruction. Adopt four-view-v2 in new generation/review and local adapter v4, with consistent scale and standing baseline across the first three, a larger portrait at right, seamless white and no panel borders. The example supplies layout only, not its character, name, costume, cup or realism. Save to a new guide filename so frozen historical inputs are never changed in place. Keep existing canon, approvals and assets; no automatic regeneration or reinterpretation of old review results.

## 2026-09-09 — User-selected H3 sampling presets

User supersedes single-pass 20-step defaults with collapsed settings: FL2V Turbo8 at 8 steps, Kitchen attention, 16:9/0.4 MP, generated audio, no other LoRAs, no refine or scale. Selecting an accelerator resets the recommended first-pass steps; manual overrides remain valid. Expose independent refine, scale, aspect/MP, audio and other LoRA controls. Ref2VA must never receive FL2V Turbo; show its none/20-step default and compatible installed choices explicitly. Preserve actual settings with each render. Second-pass base model retains creative LoRAs but not first-pass Turbo. No plugin update or video submission for acceptance.

## 2026-09-09 — LoRA strength is a per-adapter preset

User wants other installed LoRAs, especially motion, with intended adapter strength. Surface creative choices beside acceleration and source known strengths from author model cards, not LoRA rank/alpha or filename. Preserve manual override; reset only when changing adapter. Selecting a LoRA does not authorize rewriting adopted prompts; show any documented trigger and its source. Default remains no creative LoRA.

## 2026-09-09 — Klein/H3 runtime-mode correction and real four-view sample

The installed CLI launchers and opt-in SDPA patch were inspected. The live H3 process lacked --disable-smart-memory; Klein adds it. HERMES_FORCE_SDPA_MATH is unset in both current launchers, so the old SDPA patch is inert. Some historical launcher comments still claim otherwise. No external launcher, kernel patch or GPU service implementation was edited.

Replayed identical Klein v4 model/graph/prompt/seed: H3 mode produced black side/rear panels; switching only the attention node produced black output; the existing VRAM Manager's Klein-mode switch produced a complete 2048×1152 front/side/rear/portrait sheet. Mode switch includes a fresh process, so this is evidence for the working runtime profile, not isolated proof that smart-memory alone is the root cause. The sample has minor costume/framing drift and is not approved canon. Artifacts: data/acceptance/character-sheet-standard/demo-v4-klein-mode/render.png and runtime-investigation.json.

Studio now requests Klein for local image work and H3 for local video work through the existing /vram/comfy/mode endpoint. It respects paused admissions and manager refusal when work is active; no forced stop or blind mode retry. A process-owned ComfyUI-compatible GPU reservation pins the verified mode/PID across preparation and rendering, preventing a switch between check and submission. Recovery uses history only and does not change mode or acquire GPU. Current mode is left in place until another explicitly requested generation needs the other mode.

## 2026-09-09 — Style and acceleration are separate LoRA purposes

Numbered Style LoRA slots contain appearance/style/camera adapters only. Turbo weights belong exclusively to accelerator selection; unknown model-family eligibility must not reclassify an accelerator as style. Correct previously saved browser misclassification with notice while preserving independent acceleration settings.

## 2026-09-09 — Remove synthetic portrait padding

The user identified visible white blocks above/below the rightmost portrait. Studio v4 generated a 704×960 portrait and centered it on a pure-white 704×1152 canvas, adding exactly 96px at both ends. This was an adapter composition defect, not a model or GPU-mode defect. Adapter v5 generates the portrait at the full sheet height and concatenates its decoded pixels directly, removing the white canvas/composite nodes. Front/side/rear framing, reference order, seeds and overall 2048×1152 layout stay the same. Historical samples and receipts remain untouched. Thirty-four focused tests passed; real sample evidence is under data/acceptance/character-sheet-standard/demo-v5-full-height/.

## 2026-09-09 — Selectable H3 base model

Expose installed H3 UNET choices by Shot family with the existing INT8 defaults retained. Save the choice with per-Shot settings and freeze it in the generation request. Both sampling passes use that selected base; model changes preserve LoRAs/steps. Family mismatch and unavailable model are explicit errors, with no fallback. Runtime catalog is local schema metadata only.

## Workflow ownership — verified and required (2026-09-09)

User requires Studio to survive deletion of external ComfyUI workflow JSON. All three complete original workflow copies are regular files under Studio workflows/; image routing/graphs and H3 I2VA/FL2VA/REF2VA graphs are owned Python code. External manifest source paths are provenance only. Added a permanent AGENTS.md contract, workflows/OWNERSHIP.md and 13 offline checks that relocate the owned bundle and make external workflow reads/probes fail. All 9 image recipes and all 3 H3 modes build successfully. The test caught 4 missing core node schemas in Studio's archived snapshot; copied the live definitions into its owned archive. Combined relevant tests: 73 passed. No production logic, services, DB, external files or generated media changed. ComfyUI/models/custom nodes/VRAM Manager remain explicit execution dependencies. Evidence: data/acceptance/workflow-ownership/verification.json.

## 2026-09-09 — Ref2V permits FL2VA base weights

User corrected the prior hard restriction: Ref2V may select a FL2VA base while preserving reference conditioning and shared/Shot prompts. Studio now permits this explicit combination; original Ref2VA default remains. LoRA eligibility follows selected base weights, not the Shot conditioning mode. Changing the base preserves settings, while changing accelerator brings its suggested steps. Official docs describe separate default variants; installed Director conditioning is selected by task and does not gate the checkpoint name. This change verifies graph wiring, not generated reference fidelity. No plugin update or media generation.

## 2026-09-09 — Lock first-pass steps to accelerator

User superseded the earlier manual-override preference: 4-step Turbo means 4 first-pass steps, 8-step means 8, none means 20. Disabled grey field and backend normalization enforce this even with legacy manual values. Previously, the field waited for full project refresh; it now updates synchronously with the summary, with change-event fallback and input/change deduplication. Refine steps remain independent. Trigger-word assembly remains proposed, not implemented.


## Provider-independent mandatory production methods (2026-09-09)

User authorized making Astra's established prompt-writing methods durable and automatically applied to alternatives. Studio owns a hash-pinned core skill bundle, injects its applicable instructions before every provider call, and compiles fixed image constraints in code. Model output supplies bounded fields; provider changes do not choose a different method. Exact matching new image jobs may reuse a validated saved preparation across text providers, including after renderer failure, with byte-bound references and explicit provenance. Optional extensions remain available but cannot remove this mandatory contract. No automatic provider downgrade or automatic media resubmission is introduced. This preserves reproducible instructions, not a claim of identical model judgment. See PRODUCTION_METHODS.md for behavior, legacy limits and acceptance.

## 2026-09-09 — Automatically apply LoRA trigger words

User explicitly requires automatic activation after LoRA selection. Added a shared backend prompt assembler for preview and job creation. Preserve canonical source/hash; freeze prompt_assembly with exact outgoing text/common prompt and LoRA strengths/trigger sources. Worker uses frozen assembly for both graph validations/submission; old jobs retain their original source. Prefix known triggers before Shot text, or Ref2V common text when present; avoid duplicate leading triggers and never rewrite dialogue/body. Unknown trigger metadata stays unverified. UI shows automatic status and provides an escaped preview, with local settings rerender on selection instead of waiting for the slow project API. No generation or plugin update.

## 2026-09-10 — Prompt-based Style LoRA recommendations

Added h3_lora_advice as a routed creative text capability using the existing durable job/provider/mandatory-method pipeline. Evaluate full saved Shot/common prompts against installed Style candidates for the selected base; require one decision per candidate, exact quoted evidence and allow none. No keyword heuristic or provider fallback. UI displays reasons/evidence and only changes selections on explicit apply. Apply revalidates source, model and current catalog, uses preset strengths, preserves independent settings and automatic triggers. Jobs persist across reload; stale/failed/pending advice cannot apply. Recommendation and media generation are separate actions.


## Product version 0.1 (2026-09-10)

User named this baseline Continuity Studio 0.1. Display the product version separately from production revisions, skill versions and image/video adapter versions. VERSION records the product label. No backup schedule was requested or created by this naming change.


## Responsive local UI (2026-09-10)

Closing a modal, page navigation and local Shot/frame selection must not wait for unrelated saves or network refresh. Mutations remain serialized and show progress instead of silently dropping clicks. Reuse decoded history within one read-only project response to remove repeated database/JSON work; never cache production state across requests. Coalesce background refresh and ignore responses for a superseded project.

## 2026-09-10 — Formal director planning and independent coverage QC

User requires dramatic beats and directorial intent as canonical production data before shot design. New proposals store Scene director plans, one primary Shot purpose with concrete visual carrier/cut reasons, and a separate ordered edit plan that can reuse source Shots. Legacy duration remains source-generation time, with explicit generation_duration for new plans; fractional planned in/out points govern screen time. Semantic QC is a distinct provider call and adoption gate, with exact source evidence, honest uncertain outcomes and no CU quotas. New planned scenes need current passing QC before keyframe/H3 execution; legacy scenes remain unplanned history. Review freshness covers source, scene/Shot/canon, edit order/ranges and method version. Studio owns the mandatory rules and export; no runtime dependency on external workflow/skill files. Actual trimming and visual validation of source-video in/out points are not performed by this planning feature. See DIRECTOR_PLANNING.md.


## 2026-09-10 — Reusable location references retain sublocation scope

The reported 逐層聽 opening-frame failure came from requiring the nineteenth-floor target to copy a twelfth-floor sign and unique scrape from a reusable stairwell reference and edit candidate. Shared architecture remains authoritative; explicit target sublocation/time governs floor or room lettering and lighting. Unique marks stay at their established sublocation. Scene-wide appearance notes must be filtered to that same frame scope, and incompatible same-place anchors still produce blocking conflicts. Do not change canon, move the story to another floor or auto-approve/regenerate existing images to resolve this policy error.

Brief policy v5 and mandatory method 1.1.1 apply matching instructions to preparation, rendering roles and review. The compiler permits expressly required in-scene text while forbidding unsolicited captions/labels; this rule does not depend on the model using a keyword. Bundle/provenance changes prevent stale preparation reuse, with canonical dependency hashes unchanged. The shared bundle hash remains global, so method-sensitive preparation/directing reviews may need renewal after a method update; no active live project had formal director plans during this deployment audit. Evidence: data/acceptance/location-reference-scope-20260910/.


## 2026-09-10 — Checkpointed chapter generation

After repeated monolithic chapter timeouts, user authorized staged output and continuation. Freeze the complete creative/source context and original provider, then save chapter writing, generate per-scene dramatic/shot outlines, batches of at most three detailed source shots, and a global edit/source-coverage plan. Existing adopted writing and canon are reused verbatim when no rewrite or candidate revision is requested; new/revised writing remains Astra-owned. The first global-outline approach (v1) remains resumable but is superseded for new work by per-scene v2. Keep completed validated checkpoints with immutable attempt evidence and explicit resume. Reuse valid raw outputs after a crash, reject source drift, and retain the independent directing_qc adoption gate. Do not increase the deadline as a substitute for recoverability or silently downgrade Astra. File-backed Codex stdin also fixes a reproducible slow-reader/partial-pipe deadlock without changing provider settings. Details and limits: CHAPTER_STAGES.md.

Preserve canonical asset scope as application-owned organization when validating generated chapter outlines; do not ask the model to recopy a full chapter solely because it reclassified auto/public/scene. Retain original raw output and checkpoint normalization provenance. The first real v1 attempt returned successfully but entered a slow metadata correction; stage progress must explicitly identify correction, rather than presenting it as an unchanged first request.

## 2026-09-10 — Automatic image LoRA selection

User explicitly wants local Krea2/Klein to add LoRAs according to image needs. Extend the existing routed image-preparation response with evidence-backed optional selection; new local jobs require an explicit decision and automatically apply up to two compatible installed reviewed adapters. Do not add another provider call or keyword heuristics. Freeze catalog and resolved presets, keep functional adapters and canonical brief separate, and record exact graph-local triggers. None is a valid outcome. Blood effects are qualified with a non-graphic film-prop sample; generic NSFW names do not establish blood capability. Scope the tested Krea text-fusion preset to Turbo text-to-image, and keep unqualified files out of automatic choices. See IMAGE_AUTO_LORA.md.


## 2026-09-13 — Editorial trial remains a candidate in the same version chain

Use Production for both scene trial and formal adopted plan. Keep audio placement and state/evidence annotations tied to its hash; do not create another formal Shot authority. The trial only edits one scene, preserves exact original dialogue and canon, and adopts via the existing save/invalidation path. Manual adoption does not fabricate a passed creative review.

Distinguish text planning from actual media evidence: a card player is not a film, a face is not proof of audience identity knowledge, planned source ranges are not verified media selections. Preserve independent sound timing, source reuse and story-state references. Missing references never cause silent generation-mode fallback. Selected DirectorSKILL and Serge Shima visual-skills documents are owned, pinned and attributed; numerical craft recipes remain optional. See EDITORIAL_PILOT.md.


## 2026-09-13 — DeepSeek streaming and incomplete response handling

Use SSE for DeepSeek chat while preserving selected provider/model and existing chapter checkpoints. Keep received content as diagnostic partial evidence; only successful terminal completion can enter schema validation/result recovery. Do not auto-retry or switch providers after transport failure. Support complete JSON responses without an extra request. Save safe transport timing/counters/error classes and show an understandable Chinese message for historical failures. One exact first-stage live acceptance succeeded; this does not establish a guaranteed network fix or whole-chapter creative acceptance. See STATE.md and data/acceptance/deepseek-transport-20260913/.


## 2026-09-13 — Improve acting inside existing Studio methods

Treat the external 文戏技能-表演推理.md as reference data. Retain Studio's production/shot/edit/QC ownership and adopt its useful acting causal chain as a concise mandatory performance reference. Ground objectives in source knowledge; distinguish interpretation from canon, make stimulus/control/action readable, preserve listener timing and residual state at actual edit boundaries. Existing schemas carry the result; no beat-count or facial-expression recipes, new Seedance adapter, 4–30-second contract, forced image interview, or added confirmation workflow. Apply full instructions only to narrative/storyboard, Shot-bearing H3 authoring and text/directing QC. Scene-global-only and image tasks retain their scoped contracts. Global method freshness remains unchanged; old records are preserved, not silently migrated or declared revalidated. Live integration is verified; actual visual improvement awaits generated performance comparison.


## 2026-09-13 — Overview guides the next production decision

User approved the page review. Put saved progress, actionable image decisions and in-flight work before story background. Keep approved content separate from generation attempts; job success alone is not proof that a proposal remains unadopted. Preserve all existing generation/adoption mechanics and historical recovery controls. Collapse outline detail, old chapter attempts and advanced directing/editing material; retain accessible navigation and current expansion on rerender. Stage counters represent saved facts, not a claim that media is ready or the film is complete. Chapter-first layout applies to outline projects; legacy projects retain their original story model.


## 2026-09-13 — Portable Studio production Skill and backup

Expose the established method as continuity-studio, an independently installable full directory under skill-packages/ and the personal skills directory. Keep runtime mandatory methods authoritative and unchanged. Package scoped standalone routing, canon/revision discipline, acting, image/H3 contracts and exported schemas with complete local source snapshots and third-party provenance/licenses. Preserve optional upstream recipes as subordinate references, not new execution authority. Do not include live production data or credentials in the shareable Skill ZIP. Keep a separate private system recovery snapshot with current source, owned workflows, media/jobs and a consistent SQLite backup; exclude older backups and reproducible environment caches. Verify relocated Skill behavior and exact backup bytes, and explicitly retain external model/provider requirements.

## 2026-09-13 — Formal editorial ownership

Production remains the sole formal Shot/edit authority. Per-Scene adopted editorial annotations are version-bound sidecars saved atomically with the normal revision and consumed by review and export. Candidate history stays archival. Scene-local sound and visual ranges are independent; whole-project export supplies the offset and only current selected media identities. Adopting a human edit never fabricates a passing creative review. Formal views derive prompts/images from the current full Production even when an unrelated Scene changed.


## 2026-09-13 — Selectable character voice descriptions

User requested multiple selectable voice descriptors and four language/accent choices: 英文, 粵語（香港）, 國語（台灣）, 中文（大陸）. Keep presets in the character voice editor and retain freeform description support. Compose selected descriptors into the existing description string so saved configuration, generation controls and voice freshness retain one authority. Reopen only exact preset tokens; preserve legacy prose and nonstandard language values, including unchanged-save identity. No provider, schema, generation or adopted-production changes are required.


## 2026-09-13 — Character-based voice prefill

Prefill new voice-description drafts from explicit character evidence. Provide explicit reapply and undo for saved profiles; never silently overwrite existing or adopted voices. Only known age/voice traits map to existing checkbox labels; unknown traits remain open. Keep this deterministic assistance narrow: appearance is not a voice, family facts describe other people, and a one-shot delivery is not stable timbre. Preserve existing language, audition, seed and versioned save/generation contracts.


## 2026-09-13 — Complete default voice first, optional feature customization

User correction supersedes the preselect/prefill interaction. Lead with the full role voice; keep descriptor choices and full-text edits in a closed disclosure until requested. Existing saved voice configuration remains authoritative. For blank profiles, supply known role traits plus an explicit neutral speaking baseline, not just a set of checked tags. Normal saving works without expanding the customization controls. Language and audition remain visible.


## 2026-09-13 — Voice references have explicit generation semantics

User wants attached audio with timbre-only reference or Clone. Use VoxCPM2 reference_wav_path for timbre guidance; use both reference_wav_path and prompt_wav_path with exact prompt_text for continuation-style Clone. Label these honestly: timbre guidance still preserves speaker traits, while Clone aims to carry more reference expression and ignores conflicting text controls. Attachments are durable unselected references, independently stored from profile adoption. Saving selects a source; only explicit generation produces auditions. Freeze source/hash/mode/transcript; preserve old profile hashes when no reference exists. User can detach without deleting original files.


## 2026-09-13 — Voice admission readiness and audition language

GPU admission refusal is not a speech-model failure. Read Manager state in VoxCPM readiness, retain the final lease gate, and explain acquire409 without discarding raw historical evidence. Do not bypass another workload or release its lease. New unsaved voice profiles use an unambiguous canonical speaking language, or unambiguous project dialogue language for a silent role. Only exact system audition templates follow language changes; user-authored sentences remain verbatim. Repair the observed saved Ada English/Cantonese-default mismatch with a versioned edit, preserving the original failed take.


## 2026-09-13 — Semantic role voice design replaces generic defaults

The user's Pip correction supersedes the earlier neutral-baseline and keyword-prefill decisions. A maintenance robot must be understood as a character, not silently mapped to an adult human voice. Use the configured creative provider to design the complete default from frozen role/context, with source-grounded rationale. Cache the proposal by relevant source, preserve existing saved profiles, and require the normal versioned save to apply settings. Failed design exposes retry/manual input; never insert a generic fallback. Voice design is a text job, distinct from audible VoxCPM generation and canon dialogue. One same-provider correction may repair invalid grounding without replacing the provider or disguising a failed attempt.


## 2026-09-13 — Nonverbal sound is a first-class role mode

Pip's robot identity does not imply human-like speech. The user's beep/boop direction establishes nonverbal electronic sounds for Pip. Separate spoken voice from wordless sound identity in profile configuration and semantic design. Nonverbal descriptions define sound texture and expressive patterns, with no language or audition words. Current sound effects are imported as real files and adopted explicitly; do not send written beep/boop to VoxCPM or silently substitute a procedural/audio provider. Preserve existing clips as historical records and keep sound design distinct from canonical dialogue and timeline placement.


## 2026-09-13 — Direct current-voice playback, user-opened histories

Voice candidate/history lists default closed. Playback of the adopted current voice belongs on the role card and in settings. When nothing is adopted, a matching successful candidate may be previewed directly with an explicit unadopted label, never described as already in use. Keep old/failed takes in history; no automatic adoption or stale fallback. Retain manually opened disclosure state and the same audio element during same-project refreshes.

## 2026-09-13 — Frozen model budgets and grounded chapter context

Separate input capacity from reserved output. New jobs freeze provider-specific Studio budgets; exact llama.cpp counting stays behind the existing VRAM Manager gateway. Prefer full context when it fits. Under pressure, use directly sourced, checkpointed scene spans, navigation and verbatim anchors to retrieve current original passages and transitive dependencies, preserving canon, global direction and neighbouring shot state. Do not recursively summarize summaries or trim necessary evidence. Fail explicitly when an indivisible foundation/scene still cannot fit. Preserve legacy job identities and all adoption gates. See docs/MODEL_CONTEXT.md for implemented boundaries and accounting caveats.


## 2026-09-13 — Montage before source-shot production

User requires visual-skills to affect routine automatic directing quality, not only the authored editorial pilot. Load the pinned original dramaturgy chapter plus an explicit Studio montage adaptation into narrative/storyboard and text/directing QC. Preserve author attribution/license/provenance and both workspace-owned method copies. Decide coverage in scene outlines before shot briefs freeze; express the chosen view sequence in existing coverage_strategy, source Shot direction and edit_plan fields. Keep one continuous setup per source and independent screen ranges, with no imposed shot/insert counts or fixed rhythm recipes. Missing coverage must be repaired upstream, not by injecting cuts into still/H3 source generation.

Show saved audience edit order, source reuse, framing, screen duration, purpose and expandable cut reasons in the plan/proposal. Preserve existing productions and assets. New method freshness requires current review; bind completed review records to their frozen method instead of the method installed at completion. Method integration and structural tests do not prove generated media quality. See MONTAGE.md and data/acceptance/montage-integration-20260913/.


## 2026-09-13 — Saving directing content continues into independent review

The user rejects the extra manual review click after saving directing intent. A saved or adopted formal plan whose scene/source/editorial/method basis needs review must automatically enter the existing routed directing review queue. Startup reconciles existing missing or method-stale plans without mutating GET requests. Match immutable source fingerprints, serialize concurrent submissions, and let a newer saved version follow an older in-flight review. Preserve the existing proposal review/adoption gate. A substantive revise/uncertain result or execution failure remains visible and must not trigger repeated same-source calls to obtain pass. Manual routing remains an explicit human handoff.

Show automatic queue/running state beside the saved intent and in production navigation; hide duplicate submission while work is active. Expose results and actionable errors with the same 導演內容審查 name. No automatic production adoption, media generation, provider downgrade or bypass of creative review.


## 2026-09-13 — Explicit Qwen3.8 whole-engine selection

User requested a functional Powered by Qwen3.8 option. Use the existing local_qwen provider and VRAM Manager gateway; preserve the currently selected engine until the user applies the new mode. Cover text, vision, installed skills and future creative capabilities, with an explicit image-renderer boundary. Do not rename another provider, fake generation, add a hidden cloud fallback or change GPU services. Selecting Qwen must not rewrite DeepSeek configuration or credentials. Connection checking is passive metadata, distinct from real generation acceptance.


## 2026-09-13 — Human directing approval is an independent creative decision

User explicitly rejects AI review having an absolute veto. Current formal plans and readable current-revision proposals offer human approval even when AI returns revise/uncertain, fails or has not completed. Preserve the original AI job, verdict and evidence; separately record actor=user, time, source hash, viewed review ID/verdict and optional note. Human approval satisfies creative readiness/adoption without claiming AI passed. Proposal adoption inherits only its actual adopted Scene IDs, including chapter localization. Keep source/schema/reference execution validation intact.

Human decisions follow reviewed scene/source/editorial content; an AI method-only update or a late non-passing AI result cannot revoke them. Changed relevant content invalidates their applicability. Freeze project/revision/source at form opening and recheck on submission. Do not approve a production merely because the user requested the feature. Expose the approval action beside the review status and alongside proposal revision/adoption choices; notes are optional.

## 2026-09-13 — Separate storyboard views from H3 generation groups

User approved native montage execution plus deliberate storyboard/reference preparation. Keep existing source Shot/frame/edit records backward compatible, but let independent generation groups cite consecutive edit uses. One group is one H3 clip with explicit cut headers, cumulative times and role-labelled references; no compulsory image or request per view. The routed director planner compares native grouping with independently generated sources trimmed later. Whole-group selection and planned versus user-observed mappings prevent treating one full clip as several source takes. Precise cut fidelity remains a footage review concern. No contact-sheet timing guarantee, provider downgrade, media regeneration or canon migration. See docs/GENERATION_GROUPS.md.


## 2026-09-13 — Revision suggestions belong in the revision entry point

The current-plan 修訂劇情表達方案 entry must show actual applicable review recommendations immediately and carry them into revision; do not make the user reconstruct a prompt from review output. Separate current adopted-source revision from historical proposal revision. Display problem and specific recommended change, keep extra instructions optional when advice exists, and scope outline projects to a selected real chapter. Missing/pending/stale review must be described honestly without fabricated suggestions. Opening the form is read-only; explicit submission uses existing production generation and adoption paths.


## 2026-09-13 — Grouping cannot prescribe independent-source conditioning

Real planner output repeated the trimmed-source misconception despite an explicit prompt exception. Remove that overlapping decision from the grouping contract: native groups choose conditioning; independent items require null mode and defer to the existing source strategy. Reject concrete modes on independent items instead of silently correcting provider output. Version frozen planning inputs so old advice cannot be newly adopted, while retaining original records and existing source selections. Endpoint timing promises are explicitly disallowed in instructions and explained in review UI; structural validation is not semantic or footage approval.

## 2026-09-13 — File completion is insufficient for generated-image success

A decodable PNG and Comfy execution_success cannot establish a usable image. Reject exact all-black/all-white, fully transparent or unreadable generated output before asset creation, without near-dark heuristics or provider substitution. Preserve failed output and execution evidence; never automatically repost an invalid result. Apply the same guard to approval and reuse of historical generated candidates. Present historical diagnostics read-only instead of rewriting old execution/review records. Human-uploaded design swatches remain outside this generated-output check. Renderer root cause must remain unknown unless logs or a controlled reproduction establish it.


## Workflow dependency and material boundaries (2026-09-13)

Existing adoption/revision/human direction approval is the editorial baseline. Asset readiness never owns generation intent validity. Explicit fingerprints govern editorial cues, review annotations, grouping plans and independent-source strategies; legacy records need proven snapshots before narrowing dependencies.

Freeze exact H3 requests before creating attempts, using immutable request files plus existing settings/video_takes instead of a new table. Recovery uses original receipts. Take success, human disposition, baseline compatibility, source selection and actual edit use are separate. Unknown compatibility invites a version-bound human review and never removes historical media.

Both single-source and native montage clips expose the same Edit Segment material reference. Legacy selections are unverified suggestions; observed montage cuts preserve their source offsets. New bindings retain history and report gaps/overlaps. Final timeline rendering remains a later scope. Idle-gated activation protects ongoing production; static UI feature negotiation preserves old-backend operation until restart.


## 2026-09-13 — Pending creative decisions must have a direct entry

A readiness message must name the outstanding work and lead directly to it. Board review appears in the review room and the relevant H3 scene rather than relying on the user to discover a separate board panel. Continue one image at a time with saved per-image decisions; do not bulk approve, generate missing media, or equate source-asset approval with a current board decision. Collapse the full workflow map outside the overview, preserve a stable update target, and retain all existing source/token checks.

## 2026-09-13 — Complete directing review within frozen context/output budgets

Use Studio-owned scene/beat review plus original-source global reveal and adjacent edit-boundary checks. Plan and measure all required calls before generation; preserve full linked Shots and original narrative, with explicit responsibility per phase. Do not replace originals with rolling model summaries. Small fitting reviews retain the original behavior. Persist checkpoints, separate explicit-resume attempts and a complete aggregate receipt; no partial review can be adopted. A cross-phase revise/uncertain survives aggregation even when every local coverage row passes. Scope-specific missing data must not be confused with data assigned to another mandatory phase. See MODEL_CONTEXT.md and reviews/directing-context-20260913/ for acceptance and limits.


## 2026-09-13 — Studio prepares its own video runtime

Users should not coordinate manual runtime modes. Explicit video-service preparation and new generation use the existing VRAM Manager H3 reservation and honor busy/paused refusals. Service status GET stays passive; the visible prepare button uses POST, verifies readiness, and submits no media. Never bypass the manager or infer permission to regenerate from preparation.


## 2026-09-13 — Compile storyboard image intent into existing generation routes

An approved visual board is not proof of model image conditioning. Reuse group-plan/source-strategy ownership, but require new board-aware generation plans to account for every anchor as image_conditioning or planning_only with rationale. Editorial opening/CUT anchors are strong generation-boundary candidates; a planning-only boundary needs an explicit, visible exception. Keep semantic roles and source/edit times separate from execution uses. Validate promised inputs against supported source endpoints/native endpoints/explicit Ref2VA targets, bind current approved asset/hash, preserve the manifest in frozen requests and verify graph references. Missing decisions cannot become text-only silently. Pixel readiness does not invalidate intent; changed intent does.

Preserve existing production/keyframe JSON, image hashes, approval receipts and legacy jobs/settings. Do not migrate old plans into imaginary usage decisions or force every image into Ref2VA. Existing legacy/manual routes remain identifiable; new contracted plans retain enforcement through later edits and stale source plans. Arbitrary source-interval generation requires additional timing/dialogue/take mapping work and is outside this minimal patch. Do not relabel an interior frame as a full-source endpoint or claim that native references guarantee a timed cut. Show planned versus receipted usage separately, including failed submissions and unknown legacy use. See reviews/storyboard-handoff-20260913/REPORT.md.


## 2026-09-14 — Decide image demand before making storyboard images

Storyboard image count follows executable conditioning need, not beat count. Default continuous source strategy is I2VA opening; add a true source ending only for a concretely justified FL2VA endpoint. Preserve ordinary actions as text notes. Native Ref2VA remains an explicit reference route, never automatic consumption of every storyboard image or timestamped interpolation. New generation-needed board adoption saves the displayed mode and required endpoints through existing video-workflow/settings revisions. Existing approved assets and legacy job/board fingerprints are preserved.

Editorial Shot, Storyboard Frame and Generation Segment are distinct. Never fabricate editorial CUTs to accommodate image count. Full-source endpoint times remain 0 and source duration even when editorial use is trimmed. An authoritative unsupported middle constraint must be surfaced before extra image spending and must block handoff; it cannot be downgraded silently to prose or a generic reference. True internal segmentation remains future execution work requiring per-segment timing/audio/assembly and source mappings, not merely more graph shots. This deliberately bounds the current patch to generation-needed image planning and honest gates. User's latest pasted direction supersedes the earlier impulse to consume all existing middle frames.


## 2026-09-14 — Distinguish Ref2VA recommendation from selected execution inputs

AUTO source strategy can recommend REF2VA but does not select reference slots; the current image-demand board still lacks its Ref2VA branch. Never describe backend capability, an allowed model enum, synthetic routing tests or invalid legacy trim-based suggestions as verified autonomous Ref2VA production. Mode criteria must explain a real reusable identity/object/appearance/environment reference need and why opening conditioning is insufficient, not storyboard quantity or edit trim. Exact intermediate timestamps and unsupported video/audio references remain unresolved.

Preserve canonical role/name/target/subject in frozen reference records and distinguish request freeze/upload from matching graph-and-receipt submission evidence. Full completion needs a shared versioned mode/requirements contract, per-source selected target roles, board reference readiness and regenerated/validated prompt slot mapping; do not simply prune scene-union refs under old shared prompts or add an unexecutable board enum. This review's patch is deliberately bounded to criteria clarity and reference evidence.


## 2026-09-14 — Adapt generation planning within the selected model

Partition complete edit-linked source units against frozen input capacity and an explicit output-sizing hint, preserving original scene direction/methods. Every split must reconcile the full bordering provisional groups so batching does not dictate native versus independent execution. Boundary-only projection is explicit and may omit already-read source keyframe descriptions, never original action, dialogue, timing, board intent or local decisions. Validate against full original source and prove the complete checkpoint tree before success/adoption. Keep old/manual jobs compatible. Native Qwen accounting must use its gateway/tokenizer without bypassing VRAM Manager; no model fallback or hidden source truncation. Only explicit terminal length permits automatic subdivision; ambiguous transport failures wait for explicit resume. A minimum complete unit/boundary can still exceed capacity, in which case retain evidence and stop.


## 2026-09-14 — Shared conditioning decisions and explicit Ref2VA demands

Adopt a single source-level ConditioningDecision contract across h3_strategy and generation-needed image planning. Image-demand planning must reuse an adopted source mode, demands and unresolved requirements. Reference assets fulfil explicit shot intent; neither scene asset unions, timeline image count nor source trims may select the mode or supply a hidden fallback reference set. Required missing/unsupported inputs block execution. Optional demands are omitted; repeated semantic roles share one entity image and stable slot.

Compile new Ref2VA sources into a separately validated per-source six-field prompt with exact role/Picture/Subject definitions and empty global prompt. Do not renumber/prune references under existing Scene-global prompts. Retain old approved artifacts/settings and use the existing frozen-request, byte verification, SQLite revisions and receipt mechanisms. For new demand-based receipts, verify full upload hash, frozen input bytes, graph index and submitted workflow hash before displaying confirmed delivery. This does not imply precise intermediate timing or seamless internal segmentation.

Actual Astra AUTO → 3 demands → approved assets → frozen request → matching ComfyUI/H3 history and successful MP4 is verified in reviews/autonomous-ref2va-20260914/. This supersedes the prior backend/recommendation-only capability statement for newly adopted decisions.


## 2026-09-14 — Canonical state owns shot semantics before Production commit

Use one authored shot-state timeline for entity gaze, pose, position, held props, expression and extensible object facts. Endpoint arrays, interior frozen states and frame prose are compatibility projections, never independent revision authorities. Frame composition belongs to its exact source instant; do not paste global dynamic framing into every still. Semantic revisions edit canonical facts/transitions and compile all dependent descriptions.

All formal writes pass a shared structural and independent selected-provider semantic precommit check. Reject genuine conflicts and prose-only edits before saving revisions. Legacy extraction can reconcile stale frame prose against authoritative states and timed beats, with an explicit record and one bounded structural repair; it cannot rewrite conflicting authored intent to pass. Keep historical sources/media unchanged. The compiler proves projection identity; the semantic model and later pixel review have separate responsibilities. FRAME_MOMENT_SYNC remains defense in depth.

Planner wire context may reference shared complete facts and Shot/canon records, with exact reconstruction checks; persisted source snapshots/hashes remain full. Do not sacrifice source data, mandatory methods or change providers to fit context. User-facing Shot edits expose canonical fields rather than duplicate endpoint/prose boxes. Actual The Smallest Fix conversion and positive/negative checks are in reviews/canonical-shot-state/.
