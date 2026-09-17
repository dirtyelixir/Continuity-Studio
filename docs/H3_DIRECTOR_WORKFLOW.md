# MiniMax H3 導演台工作流：保存、使用與 Studio 接入調查

調查日期：2026-09-09。以下記錄最初保存與調查時的狀態。後續依使用者要求已實作 Studio 一鍵生成，詳見 [H3_ONE_CLICK.md](H3_ONE_CLICK.md)；未更新插件，未提交實際影片生成。

## 已保存的工具

原檔：`/home/navievroom/Downloads/MiniMax+H3+导演台全能工作流 (1).json`。

保存副本：`workflows/minimax-h3-director/original/MiniMax+H3+导演台全能工作流 (1).json`，48,070 bytes，SHA-256 `fa40539a002264b292e6bcb990bc8d2f3788f90f4cadcaf6c67f2a726aa925be`。保留原始位元組，沒有改成另一個工作流、刪除範例或重設採樣參數。此 JSON 是 ComfyUI 畫布格式，不能直接當 `/prompt` API 請求送出。

`workflows/minimax-h3-director/manifest.json` 保存原檔來源、雜湊、外部參考版本和未實測狀態。`upstream-reference/` 是研究用文件及程式碼快照，不是已啟用的節點安裝。原始工作流與插件、模型是不同資產；插件的 Apache-2.0 授權不自動代表工作流內所有模型／LoRA 的授權。

## 調查結論

適合納入 Continuity Studio 作為下游影片工具。Studio 已有角色／場景／道具關係、批准素材、每 Shot 模式、完整 H3 提示詞及交接資料；導演台已有多組素材、採樣、聲畫解碼、續拍、二採和輸出。應沿用兩者分工：Studio 管理創作及版本，ComfyUI 執行影片生成。

目前 Studio 的 `studio/comfy_bridge.py` 只把圖片送入 ComfyUI 素材庫；`studio/video_workflow.py:packet` 和 `studio/delivery.py` 提供人工交接，並未載入整個工作流或提交影片。**保存到專案不等於 Studio 已能一鍵生成。**

最合適的第一個接入功能是「匯出 H3 導演包」，接在現有「影片準備」完成處。插件支援 `.mmxpack.zip`，包含提示詞、素材組、圖片、音訊及時間軸，能減少逐一複製／選圖。其格式不攜帶模型，仍需載入已保存的工作流並選擇正確模型。來源：[導演台 README](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director/blob/f1f68bc9fcc6ae3d965d89ea92fb1e1d8cdee13d/README.md)。

## 原始檔的實際狀態：使用前需修正

- 20 個節點、20 條連線。主鏈為模型／CLIP／雙 VAE → Director → CreateVideo → SaveVideo，另有 report 預覽。
- **模式／模型不配對**：Director 現存值是 `r2v`，啟用中的 UNETLoader 卻選 `minimax_h3_fl2va_pruned_int8_convrot.safetensors`。執行 Ref2VA 前應在工作副本改選 `minimax_h3_ref2va_pruned_int8_convrot.safetensors`；本機有此檔。若做截圖中的 I2VA，保留 fl2va 模型，改成首幀分組並換上該 Shot 的內容。此次原檔不改。
- 原檔仍有 2 段示例（要求 10 秒＋5 秒）、3 張共用參考圖；三張都不在指定 input 路徑，且本機 ComfyUI `/view` 全部回傳 404。JSON 不包含它們的像素。必須換成 Studio 實際批准素材，不能原樣按 Queue。
- 現存參數為 864×480、24 fps、20 steps、CFG 1、seed 666、`res_multistep`／`simple`，段間引導關閉。367 個序列化影格相當於約 15.292 秒，與要求的 15 秒不同；最終長度以生成結果為準。
- 4／8 步 Turbo LoRA、注意力 patch、Refine、放大模型與二採分支均為旁路。原檔內含它們不代表當前已啟用；不得直接把 20 steps 改成 4 steps 卻仍旁路 LoRA。後續若用 Ref2VA 加速，亦須核對相同家族的 LoRA。
- 原檔列出的 7 個不同模型／LoRA／放大檔案均在本機；13 種執行節點由運行中的 `/object_info` 確認存在。這只證明可找到檔案／節點，不證明載入、模式配對或 GPU 執行成功。
- `MarkdownNote` 不在後端節點清單，不能據此判斷前端註解節點缺失；沒有為此安裝任何插件。工作流前端載入及舊 widget 升級尚待驗證。
- 運行中 Director schema 額外列有 `mixed`，而本次磁碟 `task_modes.py` 不含此模式。只能確認節點已載入，尚不能斷言服務目前執行的程式碼正是磁碟 commit。接入前需核對運行版本；此次維持已確認的分家族交接方案，不宣稱 mixed 已可用。

盤點與複核：`data/acceptance/h3-director-research/workflow-inventory.json`、`parent-review.json`。複核已修正初始盤點對秒數、widget 名稱及前端註解節點的推論。

## 使用方式

1. 在 ComfyUI 新工作流頁籤載入保存的原始 JSON；先確認模型、啟用分支、舊素材和示例提示詞。工作流內的範例內容只是資料，不是 Studio 的創作指令。
2. 在 Studio「影片準備」選擇 Shot，完成該模式所需的素材批准及提示詞採用／保存。秒數沿用 Shot；切換模式後需使用對應模式的有效提示詞。
3. I2VA：FL2VA 家族模型，導演台可採 fl2v 分組、只放首幀；清除舊 Ref2VA 公共內容。FL2VA：同家族模型，另放尾幀。每 Shot 一組，完整三欄提示詞貼該組，依 Studio 現行規則不引用上段。
4. Ref2VA：改用 Ref2VA 家族模型、導演台 r2v。Scene 共用圖與全域提示詞放公共參數；Shot 道具／局部圖、秒數與分鏡提示詞放各素材組。圖片編號接續共用槽位；同槽位局部素材會覆蓋公共素材，所以不可把每組第一張道具圖一律重編為 Picture 1。
5. 「引用上段」採用 Studio 的逐鏡判斷。只有意圖連續延長同一鏡才接續；相同角色、同場景或連續聲音不足以判定。不要把所有素材組一律勾選。
6. 檢查畫幅、實際輸出尺寸、採樣設定、首／尾幀、參考槽位和範例是否清除後，由明確的生成操作送入 ComfyUI。成片要核對對白、角色／持物、動作起終點及聲畫同步，再採用版本。

I2VA／FL2VA 與 Ref2VA 使用不同模型和提示詞結構，分批處理。H3 原生聲畫生成與 Studio 的 VoxCPM 後期聲音是兩條流程；此次不自動把試音檔當作 H3 參考音訊，也不以靜音掩蓋不正確的口型。底層模式依據：[ComfyUI 官方 H3 說明](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)。

## 導演包接入契約（待實作）

已閱讀本機 `director/pack.py`。本機與此次上游快照的該檔案位元組完全相同。以下是程式碼核對結果，不是已完成的輸出功能。來源：[固定版本 pack.py](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director/blob/f1f68bc9fcc6ae3d965d89ea92fb1e1d8cdee13d/director/pack.py)。

| Studio 資料 | 導演包位置／欄位 |
|---|---|
| 包類型與版本 | `pack.json`: `format=minimax-h3-director-pack`, `formatVersion=1` |
| 模式／輸出設定 | `pack.json`: `taskType`, `output`, 可選 `widgets` |
| Scene 全域提示詞 | `shared_params/shared_params.json`: `prompt`, `commonEnabled` |
| Scene 共用圖 | `shared_params/PictureN.ext` 與 `refs` |
| Shot 對應素材組 | `asset_groups/01/group.json`，依原鏡頭順序編號 |
| Shot ID／完整有效文字／秒數 | `id`, `prompt`, `durationSec`, `frameCount` |
| Shot 道具圖 | `asset_groups/01/PictureN.ext`，保留 Studio 已分配編號 |
| 首尾幀 | 組內 `start.ext`／`end.ext`，對應 `startImage`／`endImage` |
| 是否接續上一段 | 組內 `continuityFromPrev`，配合總開關 `output.continuityEnabled` |
| 上下文影格 | `output.continuityOverlapFrames` |

轉換器可不寫 `timeline.json`，由插件 `_assemble_timeline` 重建。不能用隨意精簡的舊 timeline，因為只要有 `timeline.json`，匯入會優先採它。導演包匯入覆蓋目前節點時間軸，應在另存的工作流副本中操作。

建議每個 Scene × 模型家族輸出一包，保留原 Shot 順序與 ID。I2VA／FL2VA 共用 fl2v 組；Ref2VA 包只收該 Scene 的 Ref2VA Shots。若中間插入另一模式的鏡頭，不能把原本跨鏡的接續旗標直接套到分批後的新相鄰組；須斷開或顯式提供正確前片。第一組不能引用不存在的前片。

24 fps 下影格依 `17k+5` 向上對齊；例如 10 秒對齊至 243 格，即 10.125 秒。保存「要求秒數」和「實際輸出影格／時長」，不可默默改寫劇本秒數。最新上游另改進接續餘幀保留，因此最終時長需以實際輸出為準。

打包時只取目前有效、已採用提示詞及批准素材；原文、對白、圖片位元組與槽位應可雜湊核對。資料不齊顯示缺項；不能自動退成文字生片、補假圖或將過期提示詞標為完成。包內檔名採 ASCII，中文名稱保留在 metadata。封裝一次不應建立生成 job。

## 版本與實測邊界

本機導演台 commit：`7de4a95243ce1a25fedc634a0eda62672610afd1`；此次上游：`f1f68bc9fcc6ae3d965d89ea92fb1e1d8cdee13d`。本機 git 工作目錄無改動；上游多 5 commits，差異已保存於 `workflows/minimax-h3-director/upstream-comparison.json`。

值得在後續正式接入前驗證的修正：Linux 分段 MP4 輸出對已關閉 stdin 執行 flush 的問題、參考音訊標籤／音色對位、接續餘幀保留。這是版本差異，不代表本次已重現輸出故障。此次沒有更新或重啟 ComfyUI。來源：[版本比較](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director/compare/7de4a95243ce1a25fedc634a0eda62672610afd1...f1f68bc9fcc6ae3d965d89ea92fb1e1d8cdee13d)、[Linux 輸出修正](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director/commit/3cea821640d02f16f24db3a8b61a34fa20d540f6)。

## 後續落地順序與驗收

1. 現階段：保存原始工作流、版本證據、依賴盤點與操作說明。
2. 下一階段：在「影片準備」增加真正可匯入的 `.mmxpack.zip`，繼續保留現有複製及圖片傳送；以暫存素材與隔離工作流驗證匯入後模式、組數、文字、槽位、圖片雜湊、秒數及引導旗標完全相符。
3. 再下一階段：新增影片生成能力及 ComfyUI provider，保留模型／LoRA／採樣參數與工作流雜湊；依既有 VRAM Manager 協調，不自行停用服務。須有送出回條、狀態、明確重試及輸出回收，避免逾時後重複生成。
4. 生成結果以候選影片回到原 Shot，保留 prompt_id、workflow_hash、asset hashes、seed、模型、實際時長、ComfyUI prompt_id 及逐段 report。採用影片不覆蓋圖片 canon。第一個完整驗收使用一鏡真實 I2VA；Ref2VA／FL2VA 再各自驗證，不能以單一模式通過宣稱全能工作流全部可用。

本次未做真實影片生成、速度／顯存測試、工作流 UI 匯入測試或 Studio 生成整合；不據此宣稱可立即一鍵出片。正式測試需使用具體批准素材與明確生成操作。
