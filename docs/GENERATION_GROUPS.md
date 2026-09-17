# Storyboard views and H3 generation groups

2026-09-13. User approved separating editorial views, reference-image preparation and generation calls. This supersedes the assumption that every storyboard/source Shot must be one independent H3 request.

`Production.shots` preserves existing source direction and single-moment frame records; `edit_plan` defines the ordered views and their screen ranges. A new independently saved generation group cites consecutive **edit IDs**, not just Shot IDs. Repeated uses of one source stay distinct. Each group is one native multi-shot H3 clip. Existing productions, images, source prompts and take selections are not migrated or overwritten.

In **影片製作 → Storyboard → 多鏡生成分組**, use **由導演安排** to obtain a routed `h3_group_plan` proposal for an adopted scene. It decides native grouping versus independent source generation, supplies reasons and concrete review checks, and selects image conditioning. Review/adopt creates multi-shot groups; independent items remain in the existing source workspace, which owns their conditioning strategy; the grouping result must use `mode: null` for those items. Manual creation/editing is also available. Groups can be disabled and restored while retaining all definitions, prompts and takes. Adopting a replacement director arrangement retires its previous generated groups; manual groups remain independent. No paid video request follows from saving a group or adopting its text.

Native groups contain 2–12 consecutive edit uses in one scene, totaling 4–15 seconds; individual views can be shorter than four seconds. These are transport bounds, not creative quotas. New camera views must already exist as storyboard records; a grouping proposal cannot invent coverage, change edit order or alter the screenplay. It can recommend generating existing sources independently and trimming them afterward. A nonzero edit-in does **not** make independent generation impossible.

## Images and dialogue

H3 now displays the saved adopted execution arrangement even when a newer candidate exists. Selecting a member of an active native group opens the group's image, prompt and render controls by default; use the source navigation to reach independent shots. Independent entries distinguish complete source generation from later editorial trims, and current checks enter new Shot prompt sources. Existing source modes and prompts are preserved. Older planner contracts are labelled for replacement rather than applying obsolete conditioning advice. A stale planning analysis does not erase an active saved group; its existing current-source and image/render checks remain authoritative.

- I2VA uses the first view's approved opening frame. Its selected source interval must begin at zero.
- FL2VA also uses the last view's approved ending frame, labelled as final Shot N. Its selected interval must end at that source's duration. Original source endpoints cannot masquerade as trimmed/intermediate frames.
- REF2VA explicitly selects 1–9 related approved identity or storyboard-frame targets. Roles, labels, asset IDs and byte hashes are frozen. Identity pictures constrain appearance; storyboard references suggest composition. Neither guarantees cut times or intermediate state.

Missing pictures are visible with preparation/import actions. Existing reference targets may be reused; there is no compulsory fresh picture for each close-up. Frames remain single-moment images, not multi-panel contact sheets. Planner input distinguishes planned frame descriptions from actual approved-image availability.

Group prompt generation uses the existing `h3_video_prompt` provider, schema and durable job queue. Frozen input includes members, source intervals, cumulative cut starts, canonical speaker IDs, images and current method hash. H3 body contains exact ordered `[Shot N]` headers and `At MM:SS.mmm, the camera cuts to` commands; REF2VA can have a shared reference-role preamble before Shot 1. Frame-mode bodies start at Shot 1. Exact canonical speech clauses preserve group-time ranges, original words/language and speakers; punctuation outside a dialogue clause is free. A partial dialogue line at an internal range boundary is rejected. Grouped production does not pretend to implement a J/L-cut audio bridge.

The group planner deterministically discards only empty `reason_note`/`checks_note` provider annotations. Nonempty annotations and all other unknown fields remain schema errors. Raw provider text/result files remain unchanged. This addresses observed transport formatting, not creative approval.

## Rendering, selection, mapping

`generation_groups.py` stores definitions/prompts/planning receipts in project-scoped settings with optimistic revisions and source hashes. Rendering dispatches the group ID through the existing ComfyUI H3 submission, immutable input-copy, receipt/recovery and adoption mechanisms. The Studio-owned workflow remains unchanged. The graph has **one Director segment**, whose prompt contains multiple shots, rather than one generation segment per view. No external workflow JSON or new GPU service is introduced.

The whole MP4 is selected against the group ID only. It is not selected or duplicated for every constituent source Shot. Frozen provenance retains a `planned` edit-to-group mapping. After viewing, the user can record actual continuous cut boundaries against that exact take, with a note. This is labelled `user_observed`, never automated detection or a guaranteed quality pass. Final aligned model padding can remain outside the last chosen usable boundary. Wrong order, gaps, overlaps and out-of-file timing fail validation.

Progress navigation distinguishes selected groups from verified view coverage. Planned group boundaries do not complete source/view coverage; selected current groups with user-observed boundaries cover their cited edit uses without modifying source take selections. Group cards stay open across ordinary project refresh.

Export includes group definitions, ready group handoff/prompt files, and each selected current successful clip once with immutable provenance plus the separate planned/observed storyboard mapping. This does not automatically assemble a final film or prove native H3 cut execution. The existing editorial previs and independent-source paths remain available.

## Acceptance and limits

Evidence: `data/acceptance/generation-groups-20260913/`.

- Isolated Python protocol tests exercise short views, repeated source uses, global order, cross-scene/duration rejection, partial speech, all image modes, exact endpoints, references/roles, source freshness, real API job/manual-adoption lifecycle, one mocked Comfy submission, whole-group selection and mapping export/observation.
- Node tests exercise escaped storyboard/reference cards, group-aware render settings/actions, source-hash routing, unresolved-request protection, planning/prompt controls, progress coverage and navigation. Related legacy video, rendering, methods, provider and chapter checks pass.
- Browser used an isolated copy of The Smallest Fix. It displayed two views totaling 13 seconds and four role-labelled approved references; saved the real prompt through the form; saved the group; preserved disclosure state; showed the ready grouped-generation control and no page overflow. No render button was pressed.
- Real unchanged DeepSeek `deepseek-flash` text/vision adapter ran on that copy. Initial planning passed structure but its reasoning misinterpreted independent-source trims and assumed described frames were approved. The planning contract was corrected to specify complete-source generation before trimming and explicit pixel availability. The later real plan recommends three independent sources for this particular precision-sensitive scene; its empty surplus note fields now normalize and the complete plan validates. This is a creative choice for review, not a requirement to use montage in every passage.
- An explicitly selected two-view, 13-second REF2VA acceptance group using four actual approved references produced a 5,295-character prompt with the hard cut at 7.8 seconds and exact original speech at 4.8–6.0. Initial failures (harness Path conversion, missing dialogue tags, overstrict punctuation/preamble handling) and outputs are retained. Final validation succeeds. The model separately flags uncertain button details, staging, relative scale, lighting and missing shot-specific keyframes. Those concerns remain; text success is not continuity approval.
- No real H3 video or new image was generated in this task. Native cut fidelity and final film quality remain to be assessed on actual rendered footage. Existing directing AI/human approval gates still apply to media and H3 prompt generation; group planning itself is read-only and can precede that gate.


## Planner contract correction (2026-09-13)

The saved real results 67c582c3b9f041d4 and 83e1c0e164a1461f still incorrectly excluded I2VA/FL2VA from an independent 8-second source because its edit used 0.2–5.4 seconds. The earlier acceptance claim that a prompt exception fixed that misconception was too strong: structure passed while the explanation remained wrong.

Planner contract v2 separates responsibilities. A `separate_source` item must have `mode: null` and no reference targets; a native montage must have a concrete mode and retains its endpoint/reference guards. The per-source strategy workspace chooses conditioning against the full original source. Titles, explanations and summaries are instructed not to make independent-source mode recommendations. Full source generation precedes editorial trimming. Endpoint pictures do not guarantee hold duration, precise camera speed or intermediate action; those remain footage checks.

The frozen source carries `plan_contract_version: 2`, changing freshness and request identity. Older plans remain intact and readable, but new adoption is refused; their original advice is collapsed beneath correction guidance in plan reviews and work records. Current per-source modes, canon, images and video are preserved. These deterministic checks enforce scope, not the truth of all generated prose. Human creative review and actual footage review remain necessary.

Verification: `data/acceptance/generation-plan-contract-20260913/verification.json`.

Live acceptance also showed the limits of instruction-only semantic quality: the first v2 proposal overpromised native-cut continuity and the next misstated the frame count. The supervisor supplied an exact reviewed three-source correction, then rebased its source snapshot as concurrent storyboard work added frame plans. These are explicit text revisions, not automatic adoption or footage acceptance. See the verification receipt for final job identity and source freshness.
