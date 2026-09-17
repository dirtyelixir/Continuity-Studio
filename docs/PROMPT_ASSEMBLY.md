# 提示詞組裝調查與修正 — 2026-09-09

本次修正從製作方案、圖片文字整理、圖片服務商、參考圖傳輸、審圖，到 Ref2VA／首尾幀交付。問題不是單純字數過多：原始創作資料與執行指令混在一起，且缺少明確的輸出邊界。

## 查明及修正

| 路徑 | 問題 | 修正 |
| --- | --- | --- |
| 導演方法 → Production.style | 指令要求把拍攝方法寫入 style，導致全章表演、聲音、改編決策污染畫風欄 | 新提案的 style 僅容納畫面媒介、比例、色彩、材質及通用光感；運鏡、表演、聲音等回到各 Shot 欄位 |
| continuity.image_prompt | style 直接拼接兩遍；整個 canon facts／批准備註被當成圖片指令 | 分成明確的解讀來源及結構化單張圖片結果；來源只出現一次，批准備註只作解讀證據 |
| engine image → provider | 上游資料、工具操作要求及原始 JSON 直接交給圖片 API；頁面保存的不是整理後內容 | 先由 image_prepare 產生受長度限制的 visual_style／appearance／composition／lighting／requested_changes，再組合目標格式與參考角色；執行前保存該生成指令及 hash |
| 高度保留參考 | 生場景也加入角色四視圖、人臉及群像模板 | 前端只保存選項；後端依 location／prop／character／crowd／frame 生成適用規則，兼容舊標記並保留使用者修改要求 |
| 圖片種類 | 場景要求展示整個地點；道具要求 readable face | 場景改成單一連貫視角建立固定空間；道具只描述物件形狀及細節；人物四視圖及群像保留各自格式 |
| 關鍵幀來源 | 所有狀態、後續動作及聲音一起進入靜態圖 | 只取該幀、對應 start/end 狀態、構圖、站位及本場視覺設定；聲音身份不出鏡 |
| 跨場光線 | 全章「夜間」筆記可把較後場次火光帶進 04:17 走廊 | 加入已有的本 Scene 外觀／光線及時間作優先來源；舊筆記必須同時符合地點與時間 |
| 修改原圖／多參考 | 正式參考兼作修改目標時重複附圖；超額時曾刪掉構圖參考 | 相同資產只附一次並列明雙重用途；保留所有參考，沿用無損傳輸板；傳輸編號說明也納入保存及交付的生成指令 |
| image_review | 缺少使用者上傳的外觀／風格參考，且重讀整份混雜設定 | 新圖片按同次整理的視覺要求審查；加入上傳參考及修改原圖，重新分配審圖編號，避免沿用生圖編號造成衝突 |
| h3_scene | 一個 Scene 修訂收到全作品 story／screenplay／其他場次及大量重複 combined prompt | 只交本 Scene、相關 canon、Shots、必要 reference／guidance；完整原資料仍保存在工作中供版本驗證 |
| 個別 Shot／Scene／影片模式 | 相鄰完整鏡頭、備註／路徑及重複起始文本增加混入風險 | 模型輸入收窄鄰鏡至構圖及端點連續性；移除路徑與審閱備註；起始文本只提供一次。保存的 hash 來源保持兼容 |
| 舊 h3.compile_shot | 未整理草稿直接塞入人物 facts／身世／隱藏物；Ref2VA 對白可落在首尾幀的 soundscape | 移除 raw canon 拼接；未整理內容標為草稿，停用複製並匯出至 h3/drafts/。Ref2VA 對白段完整移到 integrated timeline，保留原文及時間 |
| 工作重用與恢復 | 相同目標但不同修改要求可能回傳舊工作 | 比較完整圖片整理要求；不同要求不再靜默重用。恢復只接受原來源及原請求，不覆蓋舊證據 |

## 執行及紀錄

點擊生成仍是唯一媒體啟動操作。新流程先顯示「正在整理圖片提示詞」，成功後才顯示「正在生成圖片」。文字整理預設 Astra，可透過 image_prepare 更換服務商；保持已明確設定的 provider routing，沒有自動替換服務商。整理失敗或回報不可解的設定衝突時停止，圖片 API 不會被呼叫。

Codex renderer 收到已完成的 render prompt 和圖片操作包裝；要求以原文傳入 image_gen。HTTP 圖片 API 只收到 render prompt，不會收到 Codex 工具執行要求。超過五張參考的傳輸板說明亦包含在 render prompt。這是可驗證的服務商交付指令；不能藉此保證生成模型一定呈現全部細節。

每個新圖片工作保留 `image_source`、`image_preparation`、原始 `prompt`、整理後 `image_prompt`、`image_prompt_stage`、`render_prompt_hash` 及原有 reference provenance。檔案包括 `preparation/source.json`、`preparation/request.txt`、`preparation/result.json`、`preparation/render-prompt.txt`，以及根目錄 `render-prompt.txt`（包含必要傳輸說明）。資產 prompt、側錄文字及匯出圖片 prompt 使用交付文字。舊圖的 prompt 原樣保留，介面標示為歷史組裝指示。

image_prepare 可獨立作文字／人工能力使用。若自動生圖搭配人工 image_prepare，會清楚要求選擇可執行文字服務或人工圖片匯入；不會悄悄替換人工設定。

## 驗證與界限

- 隔離測試涵蓋從 API 工作建立、文字整理、失敗不生圖、render 前保存、圖片保存／審查／匯出、參考數量／編號、重用衝突及恢復。
- 用 Astra 真實整理住宅消防樓梯、樂言手機、陳樂言及第一張起始關鍵幀；逐項審閱輸出。另以 04:17 走廊重現跨場火光問題，最後結果只使用凌晨天光，明確排除火光。
- 自動結構檢查不是語意正確性的證明。第一次走廊結果仍借用了後場火光，經本次人工驗收發現並補上場次優先邏輯。關鍵場次／生成圖仍需內容審阅。
- Qwen 僅協助有範圍的 H3 調查。其「prepared.visual_setting 等同 whole Production.style」判斷不成立，沒有據此刪除正確的場景設定。手動提示詞及手動 guidance 是使用者指示，也沒有按其建議刪除。
- 本次未由此 task 啟動任何圖片／影片／聲音生成或修改 live canon。工作期間另有 live 生成、審查及拒絕操作，會一併保留；不可把資料列變動誤判為本次測試寫入，亦不可還原覆蓋。
- 既有混雜 style、原分鏡、手動 prompt 和歷史媒體不作批次改寫。修正作用於新請求及衍生草稿，不能追溯改變已生成圖片。

測試、真實文字輸出及部署檢查位於 `data/acceptance/prompt-assembly/`。部署備份位於 `data/backups/prompt-assembly-20260909/`。

## Follow-up correction: actual reference pixels and priority (v3)

The earlier v2 text-only preparation design was insufficient. Live c_leyan job a252992c263641bf attached the upload but made the prior approved identity authoritative, so both the written brief and output retained the old slim gray-shirt man. v3 uses vision preparation and explicit primary design roles for selected entity uploads. The old target identity no longer competes with the selected new candidate design; unchanged live canon and manual approval remain separate. Reference input snapshots include order/source/path/SHA-256 and are shared by preparation and rendering. Review respects the candidate brief and selected design. The UI shows uploaded reference provenance and identifies high preservation as prompt guidance. See STATE.md and data/acceptance/reference-design-fix/ for validation and the untested final-render limitation.
