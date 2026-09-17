# Ref2VA｜全域與分鏡提示詞

一個 Scene（場景）包含多個 Shot（鏡頭）。全域提示詞只屬於 Scene，用於統一場景設定與連續性。每個 Shot 只有自己的導演／分鏡 Prompt，描述動作、運鏡、對白與聲音；沒有 Shot 全域提示詞或全域覆寫。

## 照次序貼入導演台

打開 **H3 / Ref2VA 提示詞**，新版標題為「照次序，複製貼上。」上方選擇 Scene，步驟列依次為 **Scene 公共參數 → Shot 01 → Shot 02…**。一次只顯示目前一步，窄視窗可橫向捲動步驟列。

1. **Scene 公共參數**：按畫面設定導演台的 r2v 模式、公共參數、段間引導及上下文幀數。
2. 按 **全部送到 ComfyUI**，一次傳送該 Scene 的共用圖片。每張分別顯示傳送結果；部分失敗可按 **重試未送出圖片**，已成功的圖片不重傳。
3. 在導演台 **公共參數 → 參考圖片** 按 **选已有 → 缩略图**，按 Studio 圖片 1、2、3… 的順序，逐張選取並按 **使用所选文件**。清單已開啟時先按 **刷新**。上傳到素材庫不等於已選入圖片槽位。點 Studio 圖片可放大、開啟原圖資料夾或使用其他圖片操作；**複製圖片路徑** 仍直接可用。
4. 按 **複製全域提示詞**，貼到導演台 **公共參數 → 提示詞**。全域只需在這個 Scene 設定一次。
5. 按 **下一步：Shot 01**，依顯示的 **秒數** 和 **引用上段** 設定對應素材組，再按 **複製分鏡提示詞**，貼到 **素材組 1 → 提示詞**。接著處理下一個 Shot。每個 Scene 的素材組從 1 開始。

切換 Scene 時，換上該場景的公共參數及素材組內容。不同 Scene 的全域不能同時套用在同一份公共參數上；跨場景接續時需在導演台保留或載入上一段影片。段間引導目前顯示 Studio 已保存的設定，不會自動修改 ComfyUI。

複製成功後顯示 **已複製**，本瀏覽器會記住停留的 Scene／Shot 和複製進度。這只記錄複製操作，不代表已在導演台貼上。提示詞改動後，舊的複製記錄不會套用到新內容。瀏覽器拒絕自動複製時，會選取文字供 Ctrl+C／⌘C 複製。

## 「引用上段」由分鏡判斷

開啟此頁時，若目前作品沒有有效判斷，Studio 會自動交由 **分鏡接續判斷** 服務分析（預設 Astra）。會比較前後 Shot 的構圖、角度、運鏡、動作、起終狀態、Scene／時間及上一鏡頭的轉場說明，也會讀取目前實際交接的 Prompt。

每個 Shot 顯示 **勾選／不勾選＋繁體中文原因**，並可展開原文依據。同一連續鏡頭的延長才使用 Motion Context；直接切鏡、正反打或改景別通常不使用。角色、道具狀態或聲音要連續，不能單獨作為開啟理由。第一段固定不引用上段。

判斷跟作品及有效 Prompt 的版本綁定。修改後舊結果保留，但不再作為目前指示；此頁會重新分析。分析中、失敗或分鏡有衝突時，顯示 **暫未能判斷**，不會用預設勾選冒充分析。失敗可重試；不確定時需修訂說明，或在鏡頭編輯中明確手動指定。手動選項會清楚標示，仍保留 AI 原因作對照。若服務被改為人工處理，需提交人工結果，系統不會偷偷換回 Astra。

Scene 公共參數中的 **段間引導** 是總開關。若所有 Shot 均判斷不需要引用，頁面提示關閉總開關；若某個 Shot 需要接續而已保存的總開關關閉，該 Shot 會提醒先開啟。ComfyUI 的實際設定仍由使用者按頁面指示套用。

現有 The Smallest Fix 已由 Astra 分析：Shot 1 無上段；Shot 2 為中景切緊景；Shot 3 切回闊景，三者均不勾選。

## 修改內容

**場景工具 → 發展提示詞 · Astra** 一次撰寫 Scene 全域與各 Shot 分鏡。全域旁的 **編輯** 只修改 Scene；Shot 的 **編輯鏡頭** 可修改獨立分鏡 Prompt、構圖參考、引用上段和接續方向。**調整段間引導** 保存總開關及 5／22／39／56 個參考影格。

圖片沿用已批准版本（包括人工確認採用的角色四視圖），依原有規則決定可用性。傳送透過本機 ComfyUI（8188）的原有上傳介面加入 input 素材庫，沒有修改導演台程式或 workflow，也不啟動生成。

## 提示詞與保存

Scene 全域：`subject_definitions`，包含參考圖定義、身份、環境與風格。Shot 分鏡：依序為 `summary`、`retention_analysis`、`detailed_description`、`overall_soundscape`、`non_diegetic_music`。Scene 全域加上一個 Shot Prompt 為完整六段 Ref2VA，保留原對白和圖片編號。每段 4–15 秒；合併文字上限 7000 字元，每個 Scene 最多九個參考圖槽位。

方向單獨保存修訂與歷史，修改不撤銷已批准圖片。過往保存的 Shot 全域覆寫保留在原始設定／歷史記錄中，但不再套用。原有分鏡文字、Astra 生成記錄及素材保留。

**製作資料夾** 和 **匯出製作資料** 包含：

```text
ref2/handoff.json
ref2/scenes/SCENE/global.txt
ref2/scenes/SCENE/scene.json
ref2/scenes/SCENE/chapters/SHOT/shot.txt
ref2/scenes/SCENE/chapters/SHOT/complete.txt
ref2/scenes/SCENE/chapters/SHOT/references-and-guidance.json
```

`global.txt` 只在 Scene 層。`complete.txt` 是為需要單段完整文字的外部工具，衍生合併「Scene 全域＋Shot 分鏡」，不是 Shot 的全域設定。舊快照原樣保留。

`chapters` 技術欄位／目錄維持既有相容性，每筆由 `shot_id` 對應 Shot，介面不設 Chapter 層級。handoff 是人工交接清單，並非可直接匯入 ComfyUI 的 workflow。首尾幀模式及舊 Astra 提示詞在 **首尾幀模式提示詞** 和 `h3/` 保留。

## 本機依據

Ref2VA 六欄位依 `/home/navievroom/.agents/skills/h3-prompt-writing/references/ref-en.txt`。導演台安裝於 `/home/navievroom/comfy/ComfyUI/custom_nodes/ComfyUI_MiniMaxH3_Director/`，本次沒有修改其安裝或工作。
