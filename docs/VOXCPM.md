# VoxCPM2 character voices — postproduction

User request: use VoxCPM to establish each character's timbre as part of Continuity Studio postproduction.

The new 後製配音 workspace lists every adopted canonical character and the exact dialogue in each shot. Configure a voice description, language/dialect, audition sentence and initial seed. Generate a candidate, listen, then adopt. Further design candidates advance the seed without deleting earlier audio. Alternatively upload a clear 2–30 second 16-bit PCM WAV voice reference, audition and adopt. A selected reference is reused via VoxCPM2 `reference_wav_path` for each canonical line; seed alone is not treated as voice identity.

Profiles, candidate jobs, references and selected dialogue takes live in SQLite, independently of image approvals and production revisions. Profile writes use optimistic versions. Frozen requests record exact dialogue, delivery, shot timing, selected voice ID and SHA-256. Editing a profile clears its selection; replacing a voice or changing a line/timing makes old dialogue takes stale. Audio remains recoverable. Only selected current audio is included in production ZIP/folder exports, with timing/provenance JSON. Natural audio duration is retained; an overrun flag identifies dialogue exceeding its slot. No automatic waveform stretching, clipping, video muxing or lip-sync is performed.

Runtime uses the existing local installation and weights read-only. An isolated process obtains its own existing VRAM Manager lease before model imports, uses VoxCPM2 without a denoiser, and exits after generation. No service changes, model downloads, substitute providers or simulated production audio. Failures remain visible; starting a new candidate/line is explicit. Restarted in-flight voice jobs are marked interrupted and never automatically regenerated.

Upstream API verified against https://github.com/OpenBMB/VoxCPM and the installed `/home/navievroom/VoxCPM/src/voxcpm/core.py`. VoxCPM2 supports natural-language voice design and reference-only cloning; upstream lists Cantonese among supported Chinese dialects. Model quality, pronunciation and timbre still require listening, especially for short utterances.

Acceptance results will be recorded below after real execution and browser checks.

## Verified integration

177 Python tests passed (two existing upstream warnings), including eleven initial audio/profile/lease tests. A subsequent explicit-silent-dialogue fix passes all twelve focused tests. 85 locale assertions and Director regression checks pass. Isolated real API/browser workflow generated two distinct 48 kHz audition WAVs (5.44s, 2.72s), adopted their references, then generated exact canonical Cantonese lines (1.76s, 0.80s). Browser exercised play, voice adoption, dialogue generation and line adoption; the export contains all four selected current WAVs and their request/source metadata. These isolated selections are functional acceptance, not a claim of human approval of accent or acting quality.

Evidence: `data/acceptance/voxcpm/isolated-state.json`, `production-package.zip`, and copied original WAVs plus request/result/log files in `audio/`. Live service restarted only after all existing jobs finished. Before/after comparison confirms all existing titles, source, style, production revisions and assets preserved. Backup path is recorded in `data/acceptance/voxcpm/backup-path.txt`.

Local Qwen exhausted its bounded iteration budget during investigation without writing adapter files. Parent completed the implementation and verification. No worker verification was claimed.

Explicit silent-delivery markers (`無聲`, `只有口形，無聲`, `silent`, `inaudible`, `mouths silently`) suppress the synthesis action and are rejected server-side. This honors declared silence; it does not claim to infer all semantic variants of performance instructions.

Final live acceptance: all 12 下一站：長洲 auditions succeeded at 48 kHz, 2.24–7.84 seconds, with 12 distinct verified SHA-256 hashes. Saved settings/audio survived final restart; source and visual assets were unchanged. Browser verified all 12 players and the explicit silent line. Candidates are unselected and ready for user listening. `verification.json` PASS and `character-auditions.zip` are in the evidence directory. No live voice job remains unfinished.


## Optional attachments and reference modes (2026-09-13)

The role voice editor now supports uploading reference attachments before or after the first profile save, previewing them, reusing an uploaded file, and detaching it without deletion. Supported upload: 2–30 seconds, 16-bit PCM WAV, maximum 20 MB. Attachments are `kind=reference`, cannot be adopted as generated auditions, and never trigger synthesis by upload alone. The original standalone voice-import API remains compatible.

- **只參考音色**: `reference_wav_path`, with role text controls for audition and canonical language/delivery for lines. This still preserves the reference speaker's voice traits.
- **Clone · 貼近原聲表現**: both `reference_wav_path` and `prompt_wav_path`, plus required exact `prompt_text`. Text voice/delivery controls are omitted so they do not compete with the reference expression. Output text remains the requested audition or exact canonical dialogue. Adopted generated Clone auditions provide their own audio and exact audition text to subsequent line cloning.

Reference profile fields are optional; profiles without attachments keep old config hashes. Save validates project/character/source scope and original audio hash. Generation freezes attachment identity, mode and transcript; execution verifies original bytes again. Export includes attached source audio plus metadata. Mode changes invalidate prior adoption through existing config freshness; no automatic retry or provider downgrade.

Acceptance: 76 relevant offline Python tests, frontend serialization checks and isolated browser upload/save/reopen passed. The actual worker argument builder is checked against the installed VoxCPM2 signature and [official examples](https://github.com/OpenBMB/VoxCPM). Synthetic audio was used solely as an upload fixture; no new GPU synthesis or actual voice-similarity assessment was performed. See data/acceptance/voice-references-20260913/.


### Character-aware default design

Blank voice profiles now prepare a durable `voice_defaults` job through the configured creative routing. The input includes the complete character, its relevant shots and story context. The result is a complete voice instruction plus rationale and verified quotes, cached only while the source matches. `/api/projects/{pid}/voices/{cid}/default` starts/reads the proposal; explicit retry is supported after failure. This does not synthesize speech, save a voice profile, adopt a take or add canonical dialogue. Existing profiles remain authoritative. Settings display the complete proposal before the closed optional feature controls; source grounding can be expanded independently.


### Nonverbal sound mode

Profiles may choose `sound_mode: nonverbal` for robot beeps, chirps or other wordless sounds. Save clears language/audition fields, and generation/line APIs reject this mode before any VoxCPM queue or GPU call. Human Clone is not supported for nonverbal references. Import a finished 0.1–30-second PCM16 WAV as a character sound, audition and adopt it; export retains the real source bytes. Optional reference attachments are distinct from finished effects and can be added before first profile save. No automatic effect generation or timeline insertion is claimed. Legacy profiles omit `sound_mode` and retain existing speech hashes; explicitly selecting speech normalizes to that same representation.
