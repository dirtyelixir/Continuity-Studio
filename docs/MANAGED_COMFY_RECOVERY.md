# Managed ComfyUI recovery

Studio owns this production recovery policy. VRAM Manager is the only component allowed to stop/start the GPU service. User authorization on 2026-09-13 covers this specific integration and its real fault-recovery acceptance; it does not authorize arbitrary GPU-service changes.

1. Studio observes local-image receipts every 15 seconds while they remain unresolved. Image preflight also checks the renderer before paid preparation. Positive `prompt_worker` death produces a scoped Manager request with PID/start identity and Studio-owned prompt IDs.
2. Manager independently verifies the journal evidence, service ownership and exact current process. A live HTTP listener alone is insufficient. It fences all admissions, including repeated acquisition of an existing Comfy token. Other granted compute blocks recovery; pending requests remain intact and wait behind the fence.
3. The complete affected queue must match the supplied Studio job receipts. Unknown/external work or an in-flight submission prevents recovery. Manager saves queue/history, rereads the queue and process identity, and persists the operation before stopping anything.
4. Manager stops only the identified `comfyui-run.service` and its children, retains leases until exit is verified, and starts the same configured mode. It verifies the new PID, service identity, empty queue, arbiter monitor and HTTP readiness. Studio verifies the live renderer again.
5. Studio reconciles the original receipts with the saved operation. Unsent Studio work may proceed. Submitted graphs are never automatically replayed: completed archived history remains recoverable; interrupted/lost prompts are clearly marked and offer a new explicit retry. Cancelled work stays cancelled.

`POST /vram/comfy/recover` accepts `expected_pid`, `expected_identity` and `owned_prompts` (prompt ID → Studio job ID). The PID/start identity determines one durable operation. Duplicate requests return its outcome, including after a lost HTTP response. The manager exposes the record under `comfy_recovery` in `/vram/status`; Studio exposes its local status at `GET /api/settings/local-images/recovery` and in project job views. GET status calls do not trigger recovery.

| Condition | Behavior |
| --- | --- |
| No positive fatal-thread evidence | Do not restart; ordinary bounded transport/job deadlines apply. |
| Other active computation or granted reservation | Defer; preserve its lease and do not signal it. |
| Pending LLM/GPU request | Keep it pending; it may start after the recovery fence clears. |
| Unknown ComfyUI prompt / changed queue / submission in progress | Refuse and preserve the scene for inspection. |
| Same incident reported again | Return the original durable outcome; no second restart. |
| New verified crash within five minutes | Latch that incident against automatic recovery, including after the cooldown expires. |
| Stop, start or readiness cannot be verified | Persist failure, pause admissions, retain unresolved ownership and stop retrying. |
| Manager restarts during recovery | Persist a failed outcome and pause; no blind repeat of the service operation. |
| Studio loses the response or restarts | Read Manager's durable outcome and reconcile the same receipts. |
| Service was externally restarted and the original prompt is absent | End polling, preserve the receipt, require explicit new generation. |

Studio files: `studio/comfy_recovery.py`, `studio/comfy_health.py`, `studio/comfy_images.py`. Manager files: `/home/navievroom/toonflow-app/scripts/global_vram_manager.py` and `vram_comfy_recovery.py`. No authentication, launch configuration, ComfyUI custom node, model, production workflow or unrelated project implementation was changed. The scoped endpoint uses the existing Manager termination helper with an explicit ComfyUI-only target list; it never invokes `/vram/release-now`.

The real incident was restored in 30.55 seconds, and all nine image recipe dependencies passed readiness. This validates service recovery, not the absence of future HIP errors or the visual quality of newly generated images. Full evidence and the original remote queue snapshot are under `data/acceptance/managed-comfy-recovery-20260913/`.
