# Continuity Studio 工作流所有權

Studio 生成時不得讀取 ComfyUI 收藏、使用者工作流目錄或 Downloads 裡的原始工作流 JSON。那些檔案可以移動或刪除。manifest 裡的外部 `source`／`source_path` 只記錄來源，不是執行位置。

| Studio 自有內容 | 保存位置 |
|---|---|
| Klein、Krea2 完整原檔副本與 SHA-256 | `local-images/original/`、`local-images/manifest.json` |
| H3 導演台完整原檔副本與 SHA-256 | `minimax-h3-director/original/`、其 `manifest.json` |
| 圖片用途選擇、模型／節點／參數及完整 API 節點圖組裝 | `../studio/local_images.py` |
| I2VA、FL2VA、REF2VA 節點图組裝與設定 | `../studio/h3_render_graph.py`、`h3_render_settings.py` |
| 圖片／影片送出、回條、原工作取回 | `../studio/comfy_images.py`、`comfy_video_provider.py`、`video_render.py` |
| Klein／H3 模式要求與管理器預約 | `../studio/comfy_runtime.py` |
| 人物排版範例與節點規格快照 | `local-images/reference/`、`runtime-schemas.json` |
| 每次工作的確切提示詞、節點圖、參考素材、種子、結果與回條 | `../data/jobs/`、`../data/video/`，以實際工作資料夾為準 |

Studio 把完整 API 節點圖提交到 ComfyUI `/prompt`，不要求使用者先在 ComfyUI 開啟或保存任何工作流。原始 UI 工作流中的範例圖片、外部增強器和舊 prompt 不會成為隱含生產依賴。工作流副本是普通實體檔案，不是指向外部的符號連結。

ComfyUI 引擎、已安裝的模型權重／VAE／文字編碼器／LoRA、節點插件及 VRAM Manager 仍是運算依賴。刪除工作流 JSON 與移除這些運算元件是不同操作；Studio 會在缺少運算依賴時回報，不會偷偷換模型。

完整備份應包含 Studio 程式、`workflows/` 和 `data/`。只備份資料庫或單一作品匯出包，不包含完整可執行的 Studio。原檔副本必須保留在 Studio 自己的資料夾內。

`tests/test_workflow_ownership.py` 把外部工作流位置模擬為不存在，將 Studio 工作流包搬到臨時位置，核對副本／雜湊，再檢查 9 條圖片流程及 3 種 H3 流程可正常組裝。測試不刪除實際外部檔案，也不啟動 GPU 生成。後續新增或修改流程必須維持這個契約。

## Local image LoRA ownership (2026-09-10)

`local-images/loras.json` owns the complete reviewed image adapter catalog, recipe eligibility, presets, triggers and provenance. `studio/image_loras.py` owns semantic-selection instructions and validation; `studio/local_images.py` owns every resulting graph connection. Model-card URLs and acceptance paths are provenance only, never runtime reads. Existing complete original workflow archives and their checks remain intact.
