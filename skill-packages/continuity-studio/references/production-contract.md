# Production contract and portable state

This package freezes Continuity Studio 0.1 methods, including mandatory method 1.5.0 and its visual storyboard workflow. The package version is independent of application and production revisions. provenance.json records file digests and the original method manifest. A method snapshot is not a current claim about a provider's product limits.

## Source and persistent state

In an existing Studio project, SQLite and its immutable revisions own canon; data/ owns images, jobs and generated originals. Read the actual project and current selected references through the application. Do not use a stale conversation as a substitute or write competing canon beside its database.

For a standalone multi-stage production, use the user's chosen output directory. Keep a source snapshot, an adopted production record and versioned candidates with a small current-state note. Record what was requested, what was adopted, open issues and the next stage. Use readable Markdown unless JSON is requested. Do not create an elaborate project tree for a single short prompt. Original media, reference role, identity, file/hash, approval and source revision belong in a reference ledger rather than being repeated as lengthy prose in every prompt.

The logical production contains:

- Canonical entities: stable ID, kind (character/crowd/voice/location/prop), original name, reusable description and established facts. Public/scene scope organizes reuse; it does not create duplicate identities. Voice-only people do not acquire visible bodies or image requirements.
- Scenes: canonical location, time, event summary and dramatic beats. Each beat records audience knowledge before/after, emotional target, visual priority, reveal and coverage strategy. Character knowledge and audience knowledge are separate.
- Source Shots: primary purpose, linked beats/subjects, readable visual carrier, framing, camera, blocking, action/acting, timed dialogue, sound, source endpoints and incoming/outgoing relationship.
- Keyframes: source start/end moments and justified interior keys (up to eight total) per source Shot, with precise frozen pose, camera, visible people and hand/prop state. Do not depict a later emotional result at time zero.
- Edit decisions: ordered source ID, selected in/out points, cut reasons and continuity at those points. A repeated use references the same source; it does not conjure an ungenerated setup. Mark proposed ranges planned/unverified until real footage is inspected.

## Application-compatible export

Use [production.schema.json](../schemas/production.schema.json) for a Studio-shaped Production. New plans fill director_plan, generation_duration, shot_purpose, direction and edit_plan even though legacy compatibility allows empty fields. The current application uses 4–15 seconds per source Shot and at most 40 per chapter/proposal; these are Studio constraints, not universal video-model limits. Split an overloaded plan by meaningful events without deleting source material. Downstream rewriting preserves the already adopted duration and speech windows.

JSON Schema is necessary but not sufficient. Check unique global entity/scene/shot/frame IDs, valid local references and canonical location kinds. States reference entities present in that Shot or its location, with one value per entity/key. Dialogue speakers must be character/crowd/voice entities in scope. Every beat/dialogue interval satisfies 0 ≤ start < end ≤ source duration. Every scene's reveal_order is a permutation of its beat IDs; direction links local beats and valid subjects. Every source Shot has at least one edit use; selected ranges lie inside its source. generation_duration equals duration. Chapters, when present, uniquely own scenes. Apply current Studio validators when importing into the app; a standalone schema does not claim to replicate all Python semantic checks.

## Revision boundaries

Changing one Shot does not authorize rewriting its Scene global, screenplay, neighboring Shots or canonical identity. Use neighboring state as continuity context only. A new visual candidate preserves its original inputs and requested differences; acceptance updates canon explicitly. Changed source/reference pixels or method versions can make prior preparation/review stale. Preserve old results as history rather than relabeling them current. Failures preserve evidence and completed work; they do not authorize automatic spending, provider downgrades or changed story retries.

## Still-image handoff

Use [prepared-image.schema.json](../schemas/prepared-image.schema.json) for the bounded preparation fields. In standalone work, local_lora_selection may be omitted unless an actual compatible installed catalog is supplied. It must not invent an adapter or strength. Include explicit target format, assigned attachment roles, the validated visual fields and applicable common/target rules from [render-rules.json](methods/references/render-rules.json) in the final renderer instruction. For individual characters, add the four-view layout. Keep omitted_context and conflicts in review notes, outside renderer prose; resolve blocking conflicts before treating the brief as executable. Only supplied actual reference images get indices.

## Review

Use [directing-review.schema.json](../schemas/directing-review.schema.json) only when structured directing QC is requested. Link issues to literal evidence, relevant beats/Shots and a concrete repair; the existing codes include OTHER for supported concerns outside named classes. Do not invent a pass because the text parses. Text can establish planned readability and causal acting; still images cannot prove a temporal performance. Approved real video plus inspection is needed to assess actual timing, reaction and edit usability.


## Visual storyboard extension

Source Shots may hold up to eight frozen frames: start/end plus interior `key` frames with exact `source_time` and explicit entity/key/value `state`. Interior keys are not automatic H3 endpoints. See [visual storyboard production](methods/references/storyboard.md). An adopted ordered visual board is separate from the source Shot list; each edit has its own opening anchor and justified additional states. Review is bound to actual images before H3 handoff.


## Canonical semantic shot state (v1)

New or revised Studio Productions pass the shared canonical compiler before formal commit. Each Shot's `canonical_state` owns atomic entity facts at exact source moments and timed transitions. Gaze target, pose, position, held props, expression, power and custom dynamic facts have one authority. JSON null means unspecified at this moment, not physical absence or a blocking contradiction. Composition records own the corresponding frame's camera/layout/lighting detail.

`start_state`, `end_state`, interior frame `state` and every frame `description` are read-only compatibility projections. Revise canonical moments/transitions and the affected beat/action prose, or revise canonical compositions for framing. Studio regenerates projections and independently verifies all duplicated natural-language claims before inserting a Production revision. A schema-valid candidate is insufficient; use the application precommit path. Removing canonical_state to regain prose authority is rejected. Legacy records remain readable, and explicit adoption/restoration migrates them through the same checked path. Rendering-time moment synchronization remains a safety net.

Canonical timeline samples do not request pictures, editorial cuts or generation segments. An I2VA source still needs only its source opening image unless its conditioning decision explicitly changes.
