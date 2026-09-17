# Studio 一鍵生成 MiniMax H3 影片

2026-09-09。影片準備的第 4 區已接入本機 ComfyUI；本次驗收沒有送出真實影片工作，也沒有更新插件。原始收藏 JSON 保持不變。

## 使用

1. 選作品、Scene 與 Shot，採用本鏡做法。I2VA 使用批准首幀；FL2VA 使用批准首尾幀；Ref2VA 使用批准角色／場景／道具與已保存的 Scene、Shot 提示詞。
2. 完成並儲存目前素材對應的影片提示詞。過期來源或未保存草稿會停用生成。圖片差異提醒本身不阻止已採用提示詞。
3. 可按「檢查服務連線」。VRAM Manager 須開放 H3 模式，ComfyUI 須保有現有 GPU 保護。Studio 不切換或重啟 GPU 服務。
4. 展開影片設定可調尺寸、加速 LoRA 及種子；預設 16:9／0.4 MP（864×480）、FL2V Turbo 8-step LoRA／8 步、Comfy Kitchen Attention、聲畫一起生成，不二採、不放大，新種子；固定 24 fps。按「一鍵生成本鏡影片」才保存及送出此鏡；這個按鈕即是本次生成操作，不會先再開確認視窗。
5. 等待真實工作狀態；完成後在本鏡播放、下載 MP4，或明確「採用此成片」。採用不改寫圖片批准或分鏡。
6. 連線或回條不明時按「重新查詢原工作」；檔案回收失敗按「重新回收成片」。兩者只尋找原工作，不重新 POST 生成。確認失敗才可另外生成。

## 範圍

獨立 I2VA／FL2VA 使用 FL2VA 底模；Ref2V 預設 Ref2VA 底模，也容許選 FL2VA 底模。需要上一段影片引導的 Ref2VA 會明確轉介既有導演台接續流程，目前不能一鍵連續整個 Scene。沒有靜默關閉接續、改成純文字模式；所選底模共用於一採、二採。

沿用原工作流的主要採樣、聲畫解碼及 MP4 輸出鏈，編譯成已核對節點 schema 的 API graph；不是把整個含示例的畫布 JSON 直接送入 API。已提供加速／其他 LoRA、attention、二採與放大選擇；詳細預設及分支在下方。影格數向上對齊 17k+5，實際時長可能略長（10 秒 → 243 幀 → 10.125 秒）。聲畫模式輸出必須含音軌，靜音模式輸出不可含音軌；經 ffprobe 檢查實際放大後尺寸、時長及格式才記為完成；實際畫面、表演與音訊品質仍待首支影片驗收。

目前安裝插件磁碟版本保留 7de4a95243ce1a25fedc634a0eda62672610afd1；運行服務 schema 是執行契約，不宣稱它必定等於磁碟版本。不使用未核對的 mixed 模式。來源：[上游倉庫](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director)。

## 保存與恢復

SQLite 的 video_takes 保存每次工作及明確請求編號，video_selections 保存成片採用。data/video/<工作編號>/ 保存實際輸入像素、來源與參數、graph、素材上傳雜湊證據、回條、遠端 history 與 MP4。對同一未結工作重按不會另開生成。來源更新後舊成片仍保留但不能採用為目前版本。尚有未結影片工作時禁止刪除作品。

重啟後已知送出工作只查詢／回收；尚未送出的工作標記失敗，絕不自動重新提交。無法證明是否入隊的工作維持不明狀態，避免重複生成；若遠端歷史已永久清除，需人工查清後處理，沒有自動解除不明狀態的功能。

製作 ZIP 的 video/takes.json 記錄所有工作；只納入目前來源已採用的成功 MP4 及 provenance。完整可恢復備份仍須保存整個 data/。

## 驗證

337 個完整 Python 測試通過；後續補上刪除保護與 UI 展開狀態，再跑相關測試。協定測試使用明確的測試替身，不會連真實 ComfyUI，也不把測試字節視為影片。涵蓋三模式模型／素材／提示詞映射、重按去重、失去回條、重啟、回收失敗、過期來源、不相符遠端工作、輸出路徑限制、採用和 ZIP。另以本機真實只讀 schema 檢查 graph，隔離 Studio 瀏覽器檢查入口與阻擋原因。證據在 data/acceptance/h3-one-click/。


## 可收合的影片設定（2026-09-09）

未展開設定也按預設送出。每作品／Shot／模式的自訂值保存在此瀏覽器；每次生成另將完整有效設定凍結於 request.json，不會改寫歷史工作。展開時只讀取本機可用 LoRA／attention／放大模型，不提交生成、不下載或安裝模型。

| 選項 | 預設與操作 |
| --- | --- |
| 二採 | 不開；可開啟一次 Refine，另調二採步數（3）及去噪（0.25） |
| 加速 LoRA | I2VA／FL2VA：minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors，強度 1 |
| 一採步數 | 選 8-step 帶入 8，選 4-step 帶入 4，沒有加速帶入 20；灰色不可修改，前後端都固定按加速 LoRA 決定 |
| 其他 LoRA | 沒有；選單列本機 H3 LoRA，可依序選取並修改各自強度 |
| 聲音 | 聲畫一起生成；可選靜音影片，略過音訊解碼並不接入 MP4 音軌，底層仍採樣 AV latent |
| 比例／解析度 | 16:9／0.4 MP；另有 9:16、1:1、4:3、3:4、3:2、2:3、21:9 與自訂尺寸；0.2–2 MP |
| 放大 | 不放大（1×）；另有 1.5×、2×、4× |
| Attention | Comfy Kitchen Attention；可選 ComfyUI 預設、Sage 或 H3 Memory Efficient Sage |
| fps | 固定 24，不提供誤導性的可調控制 |

解析度沿用 Director 的 MP×1024² 與 32 對齊計算，所以 16:9／0.4 MP 為 864×480，對齊後比例略有偏差。未二採時，放大以 ImageScaleBy／Lanczos 在影片像素上執行；二採且放大時，使用 DirectorRefine 的 upscale（lanczos，可選本機 4x-UltraSharp 或 RealESRGAN_x2plus），尺寸也對齊 32。只開二採而不放大則同尺寸 refine。二採使用底模＋其他 LoRA，排除一採 Turbo；scheduler beta、sampler euler、passes 1，skip_fl2v=false，所以使用者選擇二採時 I2VA／FL2VA 也真正精修。介面提醒首尾幀可能被改動。不自動採用二採成片。

LoRA 家族以實際底模判斷：Ref2V 選 FL2VA 底模時可選 FL2V Turbo；選 Ref2VA 底模時提供 Ref2V Turbo。Ref2V 原有預設保留 Ref2VA／沒有加速／20 步。切換底模保留已選 LoRA 和步數，若不匹配須重新選擇。加速建議步數根據選定 4／8-step 版本及本次使用者指定的 8-step 預設，並非由任意 LoRA 數学推算最優步數。其他 LoRA 的風格與相容性仍須實際生成驗收。

Kitchen 使用 ComfyUI 核心 ModelAttentionBackend 的 `comfy kitchen attention`；該 runtime 選項只在 Kitchen INT8 可用時出現，送出前必須通過 enum 驗證。沒有用會無條件展示後默默 fallback 的第三方 Kitchen wrapper。原始工作流和已安裝插件保持不變。

驗證：383 項 Python 測試通過；設定、生成、影片工作流與統一頁面 JS 驗證通過；以運行中只讀 schema 編譯 12 組三模式／二採／放大／靜音組合。隔離瀏覽器驗證 8→4 步自動帶入、手動 6 步、直式 0.4 MP、二採、2×、靜音和其他 LoRA。沒有上傳測試素材或 POST /prompt，沒有實際成片品質驗收。證據：data/acceptance/h3-settings/。

本鏡時長固定取自 canonical Shot.duration，在「4 · 生成影片」以灰色停用欄位顯示，24 fps 亦停用。即使設定收合也可看到秒數及 H3 對齊影格／預計時長。API 不接受 duration/frame_rate/frame_count 覆寫；輸入快照、Director.total_frames、timeline.durationSec 均來自相同 Shot。追加協定測試驗證擅改秒數回應 422，合法送出保留原秒數。

其他 LoRA 已移至加速 LoRA／步數下方。運鏡選「運鏡 · Camera Motion」；作者建議0.8–1.0，選取預設1.0。人物寫實預設1.0。每項顯示作者來源、完整檔名及 trigger 提醒；選取不會修改已保存提示詞。換另一 LoRA 帶入其預設，手動強度在重新載入／同一選擇時保留。來源：https://huggingface.co/Jojocodex/minimax-h3-Camera-Motion-lora 及 https://huggingface.co/fal/MiniMax-H3-Realism-People-LoRA 。

選定 LoRA 後，其選單正下方會顯示簡短用途說明；加速及其他 LoRA 都支援。用途說明僅為提示，不會修改已保存提示詞、強度或生成参数。

Style LoRA（風格／運鏡）選單只提供人物寫實、Camera Motion 等非加速權重，所有 Turbo 均排除。加速權重只在上方獨立選單使用；Style 欄保留各項用途、建議強度與觸發詞。

## 模型選擇

「4 · 生成影片 → 影片設定」最上方可選本機 H3 底模。未修改時，I2VA／FL2VA 沿用 `minimax_h3_fl2va_pruned_int8_convrot.safetensors`；Ref2VA 沿用 `minimax_h3_ref2va_pruned_int8_convrot.safetensors`。選單由本機 ComfyUI UNETLoader 清單取得，Ref2V 清單包含 Ref2VA 及 FL2VA，目前 FL2VA 有 INT8 與 FP8 scaled 可選。

修改按瀏覽器／專案／Shot／模式保存，生成時完整凍結到任務設定；一採、二採共用所選底模。切換底模不重設 LoRA；一採步數固定跟隨加速 LoRA。已移除的模型保留顯示「目前找不到」，生成前驗證失敗，不靜默換回預設。這是底模選擇，與 Attention、加速 LoRA 及放大模型分開。

2026-09-09 更新：一採步數改為固定且不可編輯，覆蓋早期手動步數設定。選擇 LoRA 後立即更新欄位及摘要，不等待專案 API；二採步數仍按既有獨立設定處理。

## LoRA 觸發詞自動組裝

選取已核對觸發詞的 LoRA 後，Studio 自動將觸發詞加在本次送出提示詞開頭；Camera Motion 是 `camera motion`，Realism People 是 `r34l1sm`。兩個同選會合併，已在開頭的觸發詞不再重複加。取消選取後不再自動加入；第 3 步原提示詞及手動文字不被修改。未知觸發詞不猜測。

「查看本次生成提示詞」顯示同一後端組裝器的結果，不建立生成任務。I2VA／FL2VA 加在本鏡文字之前；Ref2V 有共用提示詞時加在共用文字之前，維持共用參考與本鏡參考的關係。對白、聲音描述及原圖片指令不改寫。導演台仍會按本身流程添加條件指令。

正式生成時把原來源、所選 LoRA／強度／觸發詞／來源及組裝後文字一併凍結在 request.json／工作紀錄。執行採用凍結文字；日後 registry 變更不會改寫已保存任務。歷史無 prompt_assembly 的任務維持原文字。

## 按提示詞推薦 Style LoRA

在影片設定按「依提示詞推薦」。使用目前路由的創作引擎（預設 Astra），讀取本鏡已保存提示詞與 Ref2V 共用提示詞，逐一評估本機相容的 Style LoRA。這是文字分析，不會啟動影片或修改提示詞。每項顯示建議使用／不使用、簡短原因與可展開的原文依據。可建議全部不用，不以關鍵字機械匹配。

「套用建議」才取代目前 Style LoRA，並帶入本機目錄的預設強度；加速 LoRA、步數、底模及其他設定保留，觸發詞接既有自動組裝。可以繼續手動更改。

分析工作持久保存在一般 jobs，包含提示詞、候選、底模、創作引擎及製作規格。來源或底模改動後舊建議失效；套用前再次核對來源與本機候選及強度預設。失敗、未完成或過期結果不可套用。未知用途保守判斷，模型必須引用已保存提示詞原文；不允許推薦清單外的模型或加速 LoRA。
