# DeepSeek in Continuity Studio

Open http://127.0.0.1:4760/#settings and choose **Powered by DeepSeek**, select its text model and image renderer, then apply. This applies to every new creative task across works. Existing projects, approved references, proposals, jobs and VoxCPM audio remain intact. In-flight jobs finish with their frozen provider. Individual routing overrides display a custom profile; switching back to Astra is explicit.

- Text and Vision: `deepseek-flash` (DeepSeek V4.1 Flash) is the current default and one model handles both text and image input. `deepseek-v4-pro` remains available while the provider supports it. The retired `deepseek-v4-flash` and `deepseek-v4-flash-vision-exp` names remain accepted as compatibility aliases and route to V4.1 Flash.
- Every request carrying images uses the configured Vision model, now `deepseek-flash` for new settings. Original image attachments remain present.
- Studio leaves DeepSeek thinking mode at the provider default (enabled, high effort).
- Image generation is separate: choose a configured OpenAI-compatible HTTP image API or manual import. DeepSeek has no native image-generation endpoint; its profile excludes Astra/Codex rendering and never silently falls back.
- Keys can be supplied through the server process environment, by default `DEEPSEEK_API_KEY`, or entered directly in Settings. Direct entry is stored only in `data/studio-credentials.json` with owner-only permissions; it is never stored in SQLite, job snapshots or the browser. The environment-variable path remains available for service-managed deployments.
- **Check saved DeepSeek connection** uses authenticated `GET https://api.deepseek.com/models`, checks the selected text and Vision models after resolving the retired Flash aliases, and makes no generation request. Save model/environment-name changes before checking. It cannot prove creative output quality or available generation balance.

`POST /api/settings/profile` takes `mode`, `model`, `vision_model`, `key_env`, and `image_provider`. Profile application validates before one SQLite transaction, covers built-ins/installed skills/old route keys, and sets `default_provider` for future capabilities. `GET /api/settings` returns `profile`, including computed mode and a credential-present boolean. `POST /api/settings/deepseek/check` returns a redacted connection status. DeepSeek built-in cannot be overwritten or assigned image rendering. Schema validation rejects missing, invalid, empty or truncated JSON before adoption.

Verification: `data/acceptance/deepseek-settings/verification.json`. Live mode remains Astra and no DeepSeek credential is configured as of deployment; authenticated creative acceptance is pending. HTTP/vision tests use labelled synthetic responses only in isolated tests. No media was produced for acceptance.

Official references checked 2026-09-09:
- https://api-docs.deepseek.com/guides/vision/
- https://api-docs.deepseek.com/guides/json_mode/
- https://api-docs.deepseek.com/api/create-chat-completion/
- https://api-docs.deepseek.com/guides/thinking_mode/
