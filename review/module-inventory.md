# Module inventory (generated)

Flat package `studio/`: **83 modules**, **15305 lines**. Tests: **102 files**, 13565 lines. HTTP routes in `studio/app.py`: **64**. SQLite tables (created in `studio/store.py`): assets, events, jobs, projects, revisions, settings, story_chapters.

`deps` = internal modules it imports; `used by` = internal modules importing it; `test refs` = textual `studio.<module>` references across `tests/`. Docstrings are first-person as written in the source.

| module | LOC | bytes | deps | used by | test refs | purpose (source docstring) |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `engine` | 719 | 63843 | 43 | 15 | 11 | — |
| `skills` | 704 | 24568 | 0 | 2 | 2 | Safe local instruction-skill registry for Continuity Studio. |
| `app` | 675 | 42007 | 51 | 0 | 4 | — |
| `generation_groups` | 583 | 43195 | 14 | 11 | 3 | Storyboard edit uses and native H3 generation are independently addressable. |
| `video_render` | 582 | 32016 | 20 | 6 | 2 | Persistent, explicitly submitted per-Shot video takes and recoverable Comfy jobs. |
| `chapter_pipeline` | 479 | 31147 | 9 | 7 | 1 | Checkpointed chapter proposals. |
| `prompt_writing` | 476 | 23830 | 1 | 3 | 1 | Shared prompt-writing judgment, loaded from the versioned Studio method bundle. |
| `image_prompts` | 450 | 26671 | 10 | 3 | 6 | Separate source interpretation from the exact, single-image rendering brief. |
| `storyboard_board` | 447 | 33959 | 11 | 8 | 5 | Ordered visual storyboard, exact frozen moments and image-bound human review. |
| `models` | 433 | 16860 | 3 | 29 | 4 | — |
| `directing_models` | 413 | 17673 | 0 | 5 | 4 | Pure data contracts for the Scene -> dramatic beats -> shots -> edit ranges pipeline. |
| `postproduction` | 375 | 22369 | 6 | 2 | 4 | Versioned character voices and dialogue takes, independent of visual canon. |
| `shot_state` | 359 | 28169 | 5 | 5 | 2 | Canonical state compiler and mandatory, durable Production pre-commit gate. |
| `editorial` | 354 | 18889 | 9 | 3 | 4 | Scene-scoped, versioned editorial trials using the existing Production contract. |
| `directing_pipeline` | 351 | 23281 | 8 | 4 | 1 | Budgeted directing review over frozen originals; only complete aggregate is a review. |
| `video_workflow` | 345 | 30220 | 15 | 5 | 2 | Explicit, reviewable H3 frame workflow; never infer text-only delivery. |
| `generation_pipeline` | 315 | 16990 | 5 | 3 | 1 | Adaptive generation planning over complete source units, with durable assembly. |
| `delivery` | 272 | 21196 | 9 | 7 | 7 | One global prompt per Scene, with independent Shot prompts. |
| `editorial_records` | 258 | 13261 | 3 | 6 | 2 | Version-bound editorial annotations consumed by review, playback and export. |
| `chapter_context` | 254 | 16203 | 5 | 1 | 1 | Source-grounded context selection for frozen chapter stages. |
| `providers` | 253 | 17714 | 18 | 12 | 7 | — |
| `h3_render_graph` | 245 | 12820 | 4 | 2 | 1 | Deterministic API graph derived from the archived Director's active main chain. |
| `directing` | 226 | 15284 | 10 | 9 | 8 | Formal director planning, evidence-bound semantic review, and source-clip edit decisions. |
| `comfy_video_provider` | 218 | 10905 | 4 | 2 | 1 | ComfyUI transport. |
| `storyboard_usage` | 214 | 12924 | 5 | 5 | 1 | Compile adopted board intent into existing generation routes, without media mutation. |
| `comfy_images` | 208 | 13359 | 5 | 6 | 6 | One managed ComfyUI submission, durable receipt and exact-node output recovery. |
| `local_images` | 207 | 17336 | 3 | 5 | 2 | Pinned local image recipes; selection is structural, never a provider fallback. |
| `editorial_timing` | 193 | 8899 | 0 | 2 | 2 | Pure editorial timeline helper for the UI text-card animatic. |
| `image_loras` | 186 | 9004 | 2 | 4 | 5 | Studio-owned image adapters: semantic choice, frozen presets, strict routing. |
| `provider_profiles` | 163 | 8724 | 2 | 2 | 1 | Explicit workspace-wide creative providers; image rendering is chosen separately. |
| `comfy_recovery` | 156 | 8205 | 4 | 2 | 3 | Studio-owned recovery policy; only VRAM Manager may repair the GPU service. |
| `editorial_pilot` | 152 | 15702 | 3 | 0 | 0 | Authored one-scene pilot, explicitly based on the user's existing screenplay. |
| `serial_story` | 149 | 9248 | 4 | 3 | 2 | Persistent story outlines and chapter-scoped proposals using shared production canon. |
| `prompt_preparation` | 144 | 12701 | 5 | 8 | 5 | Scene-scoped English direction, independent of whether images are approved yet. |
| `context_limits` | 140 | 6830 | 2 | 6 | 4 | Frozen Studio budgets, distinct from advertised model training context. |
| `conditioning` | 139 | 10094 | 5 | 7 | 1 | Shared mode decision and deterministic reference-demand compiler. |
| `deepseek_stream` | 135 | 7294 | 0 | 1 | 0 | DeepSeek chat transport: preserve partial evidence, require complete output. |
| `take_lifecycle` | 135 | 6974 | 8 | 3 | 0 | Take compatibility is editorial evidence, independent of execution readiness. |
| `asset_library` | 133 | 8141 | 1 | 13 | 6 | Human-readable, stable original-image storage; asset IDs remain database identity. |
| `h3_render_settings` | 130 | 6187 | 2 | 5 | 2 | User-facing H3 presets and deterministic resolution/step normalization. |
| `voice_defaults` | 118 | 6888 | 4 | 3 | 0 | Semantic voice proposals, cached against character context, never adopted audio. |
| `image_output_quality` | 117 | 4972 | 0 | 4 | 1 | Deterministic blank-output guard for generated images; Pillow only, no provider or GPU calls. |
| `input_references` | 116 | 5835 | 3 | 2 | 0 | Director-uploaded production inputs; never canonical assets or generation jobs. |
| `continuity` | 114 | 7590 | 5 | 18 | 5 | — |
| `asset_deletion` | 109 | 6295 | 2 | 2 | 1 | Rejected images are discarded; preserve only text audit and in-use originals. |
| `storyboarding` | 106 | 10722 | 5 | 4 | 0 | Source-preserving storyboard adapter; production remains Studio's canonical model. |
| `store` | 105 | 5945 | 0 | 58 | 27 | — |
| `frame_moment_guard` | 102 | 8077 | 4 | 3 | 1 | Bounded, durable text verification before a frozen frame reaches rendering. |
| `edit_segments` | 97 | 5613 | 6 | 3 | 0 | One material mapping for single-source and native montage takes. |
| `directing_auto` | 96 | 4119 | 6 | 4 | 0 | Continue saved directing intent into one independent review per frozen source. |
| `director_styles` | 91 | 8215 | 2 | 3 | 0 | Content-led director recommendations; one explicitly chosen lens per proposal. |
| `folders` | 86 | 4539 | 1 | 2 | 2 | Readable production snapshots, separate from canonical storage. |
| `voxcpm_provider` | 85 | 5372 | 0 | 1 | 3 | Fail-closed local VoxCPM2 adapter. |
| `comfy_runtime` | 83 | 4123 | 0 | 4 | 3 | Select the installed runtime through VRAM Manager and pin it during a job. |
| `h3_lora_advice` | 83 | 5152 | 5 | 3 | 0 | Provider-backed, evidence-checked Style LoRA recommendations. |
| `identity_assets` | 81 | 6033 | 7 | 1 | 0 | Explicit human adoption of existing pixels as a current visual identity. |
| `proposal_progress` | 81 | 3827 | 1 | 1 | 0 | Read-only progress from saved proposal and canonical verification artifacts. |
| `directing_approvals` | 77 | 4343 | 5 | 2 | 0 | Version-bound human directing decisions, independent of AI review verdicts. |
| `identity_from_image` | 75 | 5070 | 3 | 2 | 0 | Source-bound visual identity drafts. |
| `shot_prompts` | 74 | 6275 | 5 | 4 | 0 | Reviewable regeneration of one Shot's effective Ref2VA prompt. |
| `guidance` | 72 | 7329 | 1 | 2 | 0 | Fresh, evidence-backed decisions about incoming Motion Context boundaries. |
| `scene_asset_batch` | 70 | 4819 | 6 | 1 | 1 | Scene-derived image batches with explicit preview and durable deduplication. |
| `scene_prompts` | 70 | 6812 | 4 | 2 | 0 | Reviewable regeneration of Scene common direction, preserving all Shots. |
| `h3` | 69 | 5689 | 3 | 4 | 12 | — |
| `story_import` | 59 | 3340 | 0 | 2 | 1 | Bounded text/DOCX preview. |
| `production_methods` | 55 | 2224 | 0 | 9 | 3 | Studio-owned, mandatory production instructions; no provider or external skill dependency. |
| `speech_direction` | 54 | 4011 | 1 | 4 | 1 | Explicit speech boundaries derived from canonical Shot dialogue. |
| `crowds` | 53 | 3350 | 0 | 4 | 0 | Collective cast references are distinct from individual turnaround sheets. |
| `frame_moments` | 52 | 3525 | 3 | 2 | 0 | Single source for frozen dynamic state; prose alignment remains model work. |
| `shot_state_models` | 49 | 1177 | 0 | 3 | 0 | Authored semantic timeline; endpoint/frame fields are compatibility projections. |
| `job_queue` | 48 | 1948 | 1 | 2 | 0 | Independent bounded lanes; a renderer cannot occupy a text worker. |
| `asset_roles` | 46 | 3119 | 1 | 15 | 1 | Shared identities, scene usage and audio-only cast are independent concepts. |
| `h3_lora_catalog` | 44 | 2318 | 0 | 3 | 3 | Explicit, source-backed display and strength presets; never infer strength from rank. |
| `h3_render_prompt` | 43 | 1980 | 1 | 1 | 1 | Assemble LoRA activation prefixes without editing saved creative prompts. |
| `project_deletion` | 42 | 2649 | 1 | 1 | 0 | Recoverable project deletion; no files or dependent records are removed. |
| `reference_boards` | 37 | 2303 | 0 | 2 | 0 | Lossless transport boards for image tools with five input slots. |
| `saved_proposal` | 36 | 1492 | 1 | 1 | 0 | Read-only preview of retained, unaccepted production output. |
| `comfy_health` | 35 | 1822 | 0 | 2 | 1 | Read-only detection of a dead local ComfyUI executor despite a live HTTP server. |
| `workflow_impact` | 35 | 2392 | 7 | 2 | 0 | Read-only preview of a proposed editorial baseline revision. |
| `comfy_bridge` | 26 | 1693 | 2 | 1 | 1 | Send existing images to the local ComfyUI input library via its upload API. |
| `character_sheets` | 24 | 1671 | 3 | 3 | 1 | Character sheet policy, independent of existing identity approval/provenance. |
| `revision_feedback` | 20 | 1306 | 0 | 1 | 1 | Interpret only Studio's exact historical empty revision templates. |
| `__init__` | 0 | 0 | 0 | 0 | 0 | — |

## Hub modules (most imported)

| module | imported by |
| --- | ---: |
| `store` | 58 |
| `models` | 29 |
| `continuity` | 18 |
| `engine` | 15 |
| `asset_roles` | 15 |
| `asset_library` | 13 |
| `providers` | 12 |
| `generation_groups` | 11 |
| `directing` | 9 |
| `production_methods` | 9 |
| `storyboard_board` | 8 |
| `prompt_preparation` | 8 |
| `chapter_pipeline` | 7 |
| `delivery` | 7 |
| `conditioning` | 7 |

## Modules with no textual test reference

A test may still exercise these through another module's public path; the list marks where the mapping is not explicit.

`editorial_pilot`, `deepseek_stream`, `take_lifecycle`, `voice_defaults`, `input_references`, `storyboarding`, `edit_segments`, `directing_auto`, `director_styles`, `h3_lora_advice`, `identity_assets`, `proposal_progress`, `directing_approvals`, `identity_from_image`, `shot_prompts`, `guidance`, `scene_prompts`, `crowds`, `frame_moments`, `shot_state_models`, `job_queue`, `project_deletion`, `reference_boards`, `saved_proposal`, `workflow_impact`
