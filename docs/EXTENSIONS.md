# Extension and provider contract

Install a local directory from Extensions & providers. Studio discovers direct children of ~/.agents/skills, ~/.codex/skills and ./extensions. A SKILL.md with YAML name/description is enough; without a manifest it registers a `direction` capability. Optional studio.json:

```json
{"id":"performance-notes","version":"1.0.0","api_version":1,"capabilities":["performance_notes"],"permissions":["project:read"]}
```

Skill text and safe text references are copied to data/skills with a SHA256 content fingerprint. Executable scripts and symlinks are not supported. Each installed version has a distinct installation ID and starts disabled. Enable explicitly, granting project:read. Enabled instructions augment the selected capability provider. Any new text capability appears automatically in routing and the extension's Run button. Several instruction skills can compose by matching the same capability. Failed skills/jobs surface errors; provider defaults never change during install/enable. Integrity is checked before invoking installed content. This is an instruction-compatible subset of Codex Skills, not an arbitrary Codex plugin runtime.

Add an HTTP provider with an OpenAI-compatible base URL, model, capability list and an environment variable NAME for its key (not the key itself). Select it explicitly for a capability. Text adapters call /chat/completions with JSON output; image adapters call /images/generations or multipart /images/edits when references exist, requiring base64 image output. Providers with another protocol need a new adapter, not a new production model. API requests may send the selected production context/reference images to the configured endpoint. No automatic fallback. Manual text mode exposes the request and validates submitted JSON; manual image mode uses Import image. Built-in Astra uses saved Codex login and gpt-6-astra, with model/provider information persisted per job.

Stored jobs pin provider configuration, skill metadata/hash, input revision, prompt, reference IDs and any explicit edit source. Skills cannot authorize external messages, shell execution or additional rendering. The current local single-user application trusts the operator to configure provider URLs; do not expose its port to a network.
