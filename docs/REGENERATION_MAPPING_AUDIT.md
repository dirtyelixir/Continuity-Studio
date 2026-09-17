# 重新生成與版本對應調查 — 2026-09-09

範圍：可重複執行的生成、修訂、重試、重新分析入口；檢查請求目標、結果歸屬、採用、生效內容與交接。包含合併後「影片準備」。調查後已修正兩個應用程式缺口；沒有批准正式素材或啟動媒體生成。

## 結論

主要 ID mapping 存在。調查確認兩個功能缺口，現已修正並加入回歸測試：

1. **新關鍵幀藍圖未納入下游版本依賴（較高優先）**：已在 `video_workflow.adopt` 保存變更藍圖對應的現有 approved asset id。`state` 及 `prompt_source` 會將尚未替換的首／尾幀標為待重新生成，阻止舊提示詞和 packet 繼續交接；批准新 asset 後才解除該端點的阻擋，之後按新圖片 hash 重新生成影片提示詞。
2. **失敗工作重試遺漏提示詞草稿（中優先）**：`static/app.js` 的通用 retry 現在完整傳回 `source_prompt`，連同 capability、target、feedback、source assets 和圖片設定，保留使用者原本的修改基底。

兩項均已隔離重現，並以回歸測試驗證修正後的阻擋及重試資料保留行為。

## 入口追蹤

| 位置／按鈕 | 對應方式 | 完成後生效 | 調查結果 |
|---|---|---|---|
| 角色、群眾、場景、道具：製作新版／重新生成參考圖 | entity target_id → job → asset.target_id；修訂另記 source_asset_id | 批准新版才替換；舊版 superseded，依賴舊圖的下游標 stale | 目標與替換鏈已接通 |
| 鏡頭與分鏡：生成另一版本；影片準備：修正／重新生成首尾幀 | Shot + moment 找 frame_id → image job → asset | 批准後以新 asset_id 建立影片提示詞依賴 | 圖片替換及藍圖變更阻擋已接通 |
| 審查室：修訂／再次審查 | 修訂用原圖 target_id；再次審查以 asset_id 為目標 | 審查結果只寫回該 asset.review，不自動批准 | 已接通 |
| Scene：重新生成全域提示詞 | scene_id + source_prompt + source hash | 比較／採用後只換該 Scene 全域，各 Shot 保存；匯出取生效內容 | 已接通；失敗重試保留 source_prompt |
| Shot：重新生成分鏡提示詞 | shot_id + scene context + source hash | 採用只換該 Shot；Scene 與其他 Shot 保留；複製／匯出取生效內容 | 已接通；失敗重試保留 source_prompt |
| 影片準備：重新生成建議 | shot_id + strategy_mode + video_source hash | 採用 mode/strategy 後更新該 Shot 設定；藍圖變更會標記端點重新生成 | 已接通；回歸測試覆蓋 |
| 影片準備：重新生成 I2VA／FL2VA 提示詞 | shot_id + 所選模式 + 已批准首尾幀 ID + source hash | 採用後保存 prompt；packet 與 ZIP 同源；模式、圖片、分鏡或藍圖變更會阻止過期交接 | 已接通；回歸測試覆蓋 |
| Ref2VA：英文整理／舊整場提示詞發展 | scene_id、來源 hash；結果按 Scene／Shot ID 配回 | 符合當前來源的成功結果參與 delivery；已編輯文字有保存規則 | 已接通；舊整場發展不是新版全域／單鏡「比較後採用」流程 |
| 引用上段：重新分析 | 全部 shot_id + previous_shot_id + 原文依據 | 當前來源的成功判斷自動映射到每鏡；人工選項保留 | 已接通；驗證拒絕漏鏡、重複或錯誤上一鏡 |
| 劇情／分鏡提案重新生成、修訂；導演建議 | project/chapter target、revision、選擇來源 | 先採用方案／導演選擇；舊來源不能覆寫新版本 | 現有採用與跨章保護測試通過；修訂 Shot 的提案入口可能重寫其所屬章節，並非直接替換一鏡 |
| 後製配音：再生成音色／對白 | character_id；對白另凍結 shot_id + dialogue_index + voice_take_id | 試聽後採用；過期音色／對白來源不能採用，匯出取已選 take | 已接通 |
| 活動與版本：按目前設定重試／恢復已保存結果 | 重試建立新 job；恢復沿原 job finish | 恢復保留原 input mapping；重試重新建 input（包括 source_prompt） | 已接通；Node retry 檢查覆蓋 |

「生成完成」與「已採用」為不同狀態。新圖片或新提示詞待採用時，仍顯示舊生效版本並不代表漏 mapping。

## 證據與限制

- 正式 SQLite 以 `mode=ro` 查詢：34 個成功 image jobs 均有保留的 asset，project_id、target_id、job_id 全部一致；錯配 0。此為查詢當下資料快照，並非視覺內容審查。
- 第一批 Python：scene_prompts、shot_prompts、video_workflow、production、guidance、delivery、postproduction、asset_library、asset_roles：72 passed / 1 failed。
- 第二批：director_styles、storyboarding、serial_story、prompt_preparation、preparation_scope、shot_references、asset_deletion：54 passed。
- 唯一失敗 `test_new_images_get_versioned_original_names_and_metadata`：拒絕圖片後仍預期 sidecar 保留，但目前 `decide_asset` 已呼叫拒絕版本清理，檔案不存在。新 asset_deletion 測試通過。這是舊測試預期與目前清理行為的衝突，不作為 mapping 正確的證據，亦未擅改測試。
- JS 四組通過：`check_scene_regeneration.mjs`、`check_shot_regeneration.mjs`、`check_video_workflow.mjs`、`check_unified_video.mjs`。這些為渲染／控制與程式碼驗證，本次沒有逐按所有正式瀏覽器按鈕。
- 缺口 1 的回歸測試現在確認：採用不同 I2VA 首幀藍圖後，該 Shot 不再 ready，packet 被拒絕；新 approved asset 取代基準後才可繼續，且舊 prompt hash 會要求重建。
- 缺口 2 的 Node 檢查現在確認：通用 retry 對 h3_global、h3_shot、h3_video_prompt 及 h3_strategy 都保留 source_prompt。
- 測試使用臨時目錄及人工 fixture 結果，只验证關聯與狀態，不代表真正模型生成品質驗收。

## 修正後驗證（2026-09-11）

- `.venv/bin/python -m pytest -q`：556 passed，2 個既有依賴棄用警告。
- 全部 `scripts/check_*.mjs`：25 個通過；全部 `static/*.js` `node --check` 通過。
- `git diff --check` 通過；本機服務重啟後 `/api/health` 回應 200。沒有啟動生成、批准圖片或修改正式作品資料。

## 全專案健康檢查新增發現

- `pytest.ini` 現在將正式測試根目錄固定為 `tests/` 並排除 backups，根目錄測試不再收集備份副本。
- `scripts/check_image_reference_evidence.mjs` 現在為抽取測試注入與瀏覽器相同的無作用 helper 參數，不再因模組依賴而中斷。
- 全部 26 個 `scripts/check_*.mjs` 通過；所有 static JavaScript `node --check` 通過。
- 逐頁瀏覽器 smoke check 時，Studio 服務曾經是 inactive/dead（上一輪 idle-only 停止後未自動啟動），因此 tab 顯示的是舊畫面而非可重新請求的 live backend。已在本次檢查最後重新啟動 `continuity-studio.service`，`/api/health` 回應 200；未啟動任何生成或改動作品資料。
