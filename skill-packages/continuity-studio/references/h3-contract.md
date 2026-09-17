# Frozen Studio H3 handoff

This documents the Studio code contract captured with this package. Preserve an existing selected mode and supplied exact alignment instruction. Consult current official provider/tool documentation if asked to change capabilities or target a different runtime; do not treat this snapshot as proof of present provider limits. Studio's explicit workflow selects I2VA, FL2VA or REF2VA. Legacy formatter support for other shapes does not authorize silent fallback.

## Common

One source Shot is one continuous take with a local [Shot 1] timeline from zero to its adopted duration. Preserve original canonical names; descriptive prose is English. Keep exact dialogue, speaker, language, delivery, timing and audible versus silent-mouth intent. Stable speaker labels (S1), (S2) identify the same people throughout. Dialogue uses `<d>[language] original words</d>`. Do not add lyrics, narration, references, transfers or editing inside the take. Respect the existing total 7000-character handoff limit; if faithful content cannot fit, report the conflict rather than truncate or rewrite dialogue.

Separate review commentary from renderer prose. Describe physically plausible action between frames, not instant morphing or invented transfers to conceal inconsistent images. Approved-frame differences remain separate advisory notes while the current Studio contract still delivers the complete intended prompt. Missing, unapproved or stale required images make an executable handoff unready; do not label a text draft ready or change mode automatically.

## I2VA and FL2VA

I2VA uses only the approved first frame as Picture 1. Its alignment line is:

`For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.`

FL2VA uses Picture 1 for the first frame and Picture 2 for the last. Its alignment line, substituting the actual duration formatted to two decimals, is:

`How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the {duration}-second mark of the target video.`

Follow the line with a blank line and exactly these sections, once each and in order:

```text
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

The integrated timeline contains camera, timed acting/action and all timed dialogue/speaker tags. Soundscape contains ambience, physical and nonverbal sounds, with no dialogue tags. Music follows the adopted choice; use N/A when absent. No Ref2VA subject definitions or retention sections belong here. In a structured Studio task, use [video-prompt-result.schema.json](../schemas/video-prompt-result.schema.json), returning complete text and separate frame_issues.

## REF2VA

Maintain one shared Scene global and separate Shot text. The combined handoff has exactly six sections, once each:

```text
subject_definitions:
...
summary:
[reference generation] ...
retention_analysis:
...
detailed_description:
[Shot 1] ...
overall_soundscape:
...
non_diegetic_music:
...
```

The Scene global supplies reference mappings and reusable visible identity/appearance/light. It does not carry biography, hidden inventories, scene-by-scene action, future events, Shot dialogue or hand ownership. Shared reference slots belong to relevant characters/crowds/locations. Props belong to individual Shots: place local prop definition lines before that Shot's summary so they continue the existing subject_definitions section, without repeating its header. Assign shared slots first and then the Shot's actual local inputs; local slot meanings may differ between separately generated Shots. No placeholder asset claims or unassigned reference labels.

At text-preparation time, unresolved canonical identities can use `<Entity entity_id>` tokens and a subjects record. Resolve only against actual approved attachments for the final handoff; use the original canonical name for an unassigned entity, while reporting unmet reference readiness separately. Voice-only entities stay in sound/dialogue with no visual retention or Picture slot. Each Shot's retention covers only its actual visible/used entities. Preserve the supplied Ref2VA speech placement and validators; do not mechanically impose the frame-mode three-field format.

Keep images, assigned slots, exact final text, selected mode, source identity and review separately recorded. LoRA triggers and graph parameters are execution-adapter concerns derived from an actual selected compatible catalog; a creative prompt writer must not fabricate them.
