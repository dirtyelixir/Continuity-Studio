# Continuity Studio 0.1

> **Review snapshot.** This tree is a read-only code-and-docs snapshot prepared for an external
> architecture review. Start with **[REVIEW_BRIEF.md](REVIEW_BRIEF.md)** (what to review and the
> questions asked) and **[ARCHITECTURE.md](ARCHITECTURE.md)** (measured module map). See
> **[SNAPSHOT.md](SNAPSHOT.md)** for provenance, what was deliberately excluded (database,
> generated media, runtime services) and how to reproduce every figure.
> The README below is the application's own product documentation, unchanged.

A working local narrative-production application: idea → Astra production proposal → canonical identities → shot/keyframe plan → real images and visual review → H3 prompt package.

Open **http://127.0.0.1:4760**. The installed user service `continuity-studio.service` starts it automatically on login. The sample production **The Smallest Fix** is saved in the local database. See [docs/STATE.md](docs/STATE.md) for current live acceptance status.

The interface defaults to **繁體中文**. Existing stories, prompts and generated content keep their original language. See [interface language](docs/INTERFACE_LANGUAGE.md).

## Use it

已有故事或劇本：按右上角 **建立作品／導入故事**，貼文字或匯入 TXT、Markdown、DOCX。選「已有劇情」或「完整劇本」，Astra 會保留原文並提出可審閱的分鏡方案；採用後接以下角色、場景、分鏡及 H3 流程。見 [操作方法及 skill 比較](docs/STORY_IMPORT.md)。

製作手冊的 **按劇情推薦導演** 會比較 DirectorSKILL 的 20 套方法，提出三個有劇情依據的方向。選一個後，用該方向建立可審閱的分鏡；大綱作品則逐章繼續。見 [導演風格推薦](docs/DIRECTOR_STYLES.md)。

1. Create a production with an idea and visual direction. **Develop with Astra** produces a reviewable story, screenplay, cast, scenes and shots.
2. **Review proposal → Adopt** establishes the production book. Request a revised proposal or edit writing/canonical facts when needed.
3. In **Cast & locations**, characters require a four-view sheet: front close-up, left-facing full-body profile, right-facing full-body profile, and rear full body. **製作新版四視圖** uses the current approved identity and the saved layout example. New approvals require a passing four-view check or **人工確認採用** with an automatically saved acceptance record; older portraits are visibly marked for update. See [character sheet requirements](docs/CHARACTER_SHEETS.md). Generate other missing references normally. In **Review room**, inspect the images and Astra’s visual assessment, then approve, reject or revise. A revision uses the candidate as an explicit edit source; it does not grant canonical approval.
4. In **Shots & storyboards**, choose a shot and generate its frozen keyframe. Approved characters, location and props are attached automatically. End frames also use an approved opening frame when available.
5. **H3 / Ref2VA 提示詞** defaults to **Ref2VA**. **Develop scene prompts · Astra** writes one scene-wide global prompt and an independent director/storyboard prompt for each Shot. Only the Scene owns a global prompt. Each Shot has its own director/storyboard prompt and cannot define or override a global prompt. **Guidance settings** records segment guidance and context frames; each Shot also controls reference to the previous segment, including scene boundaries. **Export package** includes split prompts, complete prompts, ordered image references and guidance notes. **Keyframe-mode prompts** retains the earlier I2VA/FL2VA workflow. See [the Ref2VA guide](docs/REF2VA.md).
6. **Extensions & providers** can register instruction skills, enable them with explicit permissions, add API providers and route individual capabilities. Installing a skill never changes Astra defaults.

Use **Show in folder** below a reference or in its full-size preview to open the original `data/assets/` directory and select that exact existing image in the desktop file manager. This action creates no copy or download.

In **H3 / Ref2VA 提示詞**, the handoff guide shows one Scene at a time: shared parameters first, then one Shot per Director material group. Every copy button names its destination; Shot seconds and reference-previous settings are visible beside the prompt. **全部送到 ComfyUI** sends the Scene's original images to the local library in one batch, with per-image results and partial-failure retry. Select them in the existing Director picker in Picture order. Copy receipts and the current step persist in this browser; they do not claim content has been pasted in ComfyUI. The guide does not alter the Director workflow or start generation.

Use **Production folder** in the top bar to browse saved files, preview images/text, copy the folder path or **Open in Files**. The app creates reusable snapshots under `data/productions/PROJECT_ID/SNAPSHOT/`, containing approved images, screenplay, image prompts and H3 files. Opening an unchanged production reuses its snapshot; older snapshots and any notes you add are preserved. Ideas can be viewed before a plan is adopted. These are output snapshots; edits there do not change the production book.

Astra image review is advisory. Approving a flagged result requires a director note. Approved images are persistent identity references, not an assertion that image generation is perfectly consistent. Replacing or rejecting a reference invalidates dependent work; nothing is deleted. Old proposals cannot overwrite a newer production revision.

## Run and maintain

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock.txt
./run.sh
```

Requires Python 3.12+ and authenticated `codex` on PATH (`codex login`). Default model is `gpt-6-astra`; its creative jobs and built-in image rendering use your Codex account and usage limits. No API key is needed for the tested default path. Image jobs freeze approved references in their own job directory and attach them in order. Up to five references use the established conversation-input path. Larger sets retain the first four images independently and pack remaining originals at native resolution into a labelled transport board, keeping the image tool within five inputs without dropping canonical references. HTTP providers use separate configured credentials; no silent fallback or local-model downgrade.

```bash
systemctl --user status continuity-studio
systemctl --user restart continuity-studio
systemctl --user stop continuity-studio
journalctl --user -u continuity-studio -n 60
.venv/bin/python -m pytest -q
```

Only one server may own a data directory. Bind to loopback; this is a single-user local application, not a network service. `STUDIO_DATA` overrides storage, `STUDIO_PORT` overrides port for manual launches. The user service is installed at `~/.config/systemd/user/continuity-studio.service`.

Original images now use readable folders and version names:

```text
data/assets/The Smallest Fix/
  Characters/Ada/Ada-reference-v002.png
  Characters/Pip/Pip-reference-v001.png
  Locations/Tiny lighthouse workshop/
  Props/Brass lantern/
  Scenes/S01-A quiet repair/
    SH01-The diagnosis/Opening-v001.png
    SH02-The switch/Opening-v003.png
    SH02-The switch/Ending-v001.png
    SH03-Her kind of thank-you/
```

**Production folder → Open asset library** opens this original-image library. **Show in folder** selects the exact image inside it. `Asset library.md` lists all images; each image folder has `Versions.md` with approval status. Images have adjacent prompt text and JSON provenance files. These indexes refresh after image creation/review/approval and production edits. All versions remain; choose the entry marked **approved**. Folder names stay stable after initial organization, even if a production title is later edited, so existing file links keep working. Duplicate project/character names receive a readable numeric suffix.

The existing production was backed up before migration and all 13 original images were verified byte-for-byte. Historical ID-based paths remain compatibility links for saved job inputs. Future images are saved directly with readable version names. `scripts/organize_assets.py PROJECT_ID --apply` supports backed-up migration of legacy assets only while the studio service is stopped.

All production state lives in **data/**: SQLite in `studio.sqlite3`, immutable images in `assets/`, request/result/evidence directories in `jobs/`, pinned skills in `skills/`. Back up the whole data directory while the service is stopped, or use a SQLite online backup plus the immutable assets/jobs/skills. Git intentionally excludes runtime data. Export packages contain a portable production snapshot; they are not a substitute for a full editable-workspace backup.

Interrupted jobs are marked explicitly at startup. **Recover saved result** ingests an already-written result without another generation. If no result exists, retry explicitly; the studio does not automatically spend again after an uncertain interruption.

Studio owns its image and H3 workflow definitions under **workflows/** and **studio/**. External ComfyUI/Downloads workflow JSON files are provenance only and may be removed without losing Studio's generation logic. Keep the application code and workflows directory alongside data in a full backup. ComfyUI, installed models/custom nodes and VRAM Manager remain execution dependencies. See [workflow ownership](workflows/OWNERSHIP.md).

## Scope and evidence

- [Product decisions](docs/DECISIONS.md), [research](docs/RESEARCH.md), [extension contract](docs/EXTENSIONS.md), [current state](docs/STATE.md), [acceptance evidence](docs/ACCEPTANCE.md).
- VoxCPM2 character voice design, WAV reference import and per-line postproduction speech are available in 後製配音; see docs/VOXCPM.md. Per-Shot MiniMax H3 video submission, recovery and adoption are available in 影片準備; see docs/H3_ONE_CLICK.md. No automatic multi-Shot edit or separate voice/music assembly, multiplayer collaboration or unrestricted executable plugin runtime.
- HTTP adapter contract is tested with a local test server; external paid API accounts are not configured or claimed tested.
- `scripts/verify_project.py PROJECT_ID --output data/acceptance` checks the actual live project, reference reuse, real distinct image bytes, visual-review records, H3 anchors and ZIP contents. It never generates or approves work.

### H3 影片準備

側欄「影片準備」可逐 Scene／Shot 選擇首幀 I2VA、首尾幀 FL2VA 或 Ref2VA，請 Astra 按劇情建議模式和關鍵幀藍圖。先修準並批准圖片，再生成、比較、採用及編輯對應影片提示詞。未完成圖片或發現首尾幀衝突會阻止交接；現有 Ref2VA 全域／分鏡提示詞仍在原工作台。詳見 [FL2VA_WORKFLOW.md](docs/FL2VA_WORKFLOW.md)。
