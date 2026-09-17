# Continuity Studio
Read docs/STATE.md, docs/DECISIONS.md and docs/USER_BRIEF.md before substantial changes. Astra owns creative/product decisions and defaults. Never substitute fake generation or silently downgrade a provider. Do not modify sibling projects, authentication files, or GPU services. Durable canon is in data/studio.sqlite3; images and jobs in data/. Preserve them. Tests use temporary directories.

Prefer local qwen_execute for self-contained mechanical scopes when verification is cheap; protect other work. Never bypass VRAM Manager. Run .venv/bin/python -m pytest for relevant changes. Start with ./run.sh (127.0.0.1:4760). Keep docs/STATE.md and acceptance evidence current.

Studio must own every production workflow definition and routing rule. Never require external ComfyUI/Downloads workflow JSON files at runtime or link to them instead of keeping complete Studio-owned copies. Source paths in manifests are provenance only. Preserve tests/test_workflow_ownership.py and workflows/OWNERSHIP.md when adding workflows; models, custom nodes, ComfyUI and VRAM Manager remain explicit execution dependencies.
