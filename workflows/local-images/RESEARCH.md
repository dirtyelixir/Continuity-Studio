# Local image workflow collection

The two files in original/ are byte-identical to the named user workflows. inventory.json records their source paths, SHA-256, node/widget data, groups, active/bypassed modes and runtime dependency evidence. runtime-schemas.json is a read-only snapshot, not a plugin installation.

See ../../docs/LOCAL_IMAGE_WORKFLOWS.md for findings, branch selection, exact recipe/model mapping, intentional Studio adaptations, recovery behavior and acceptance boundaries. Runtime API graphs are constructed separately in studio/local_images.py and frozen per job. Do not submit archived canvas JSON directly to /prompt or execute its sample text/LLM branches.
