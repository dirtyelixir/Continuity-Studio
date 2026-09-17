# 本機圖片工作流 — 2026-09-09

> **最新人物標準（2026-09-09 使用者修正）**：正面全身 → 向左側面全身 → 背面全身 → 正面臉部特寫。前三欄等寬、人物尺度／頭高／腳底線一致，最右特寫較大，連續白底無分隔線。適配器已更新為 `studio-local-images-v4`、規格 `four-view-v2`；輸出 2048×1152，前三欄各 448px，特寫欄 704px。後三個視角均引用當次生成的正面全身圖。新範例保存在 `reference/character-four-view-v2.jpg`（只取排版，不取人物與文字）。以下 v1–v3 的舊排版及出圖觀察是歷史紀錄，已被這次標準取代。新規格已通過程式與本機 schema 檢查，這次沒有重跑圖片。

## 原檔與調查

來源是本機 `/home/navievroom/comfy/workflows/Shared/local-or-toonflow/`，兩份原檔完整收錄於 `workflows/local-images/original/`，不是重新下載的近似版本：

| 原檔 | SHA-256 | 節點 |
|---|---|---:|
| Toon-flow-Local-Klein_true_V3人物资产制作合集（写真套图+换脸+角色定版图）By+像素幻想Lab.json | `5ef3c363fe7a0f7dd2263a4abfed0e867dd10205c20f614ce9ca7bedc8137b3d` | 129 |
| ▶Local-krea2-图像编辑-整合流.json | `1c329c4d5e0b1b05308d89b2a86b8300a07aac6883f01219ef38a65554ac1a46` | 96 |

`inventory.json` 記錄群組、節點、旁路、原 widget、模型選項及執行節點存在證據；`runtime-schemas.json` 是調查時的服務 schema。原檔是畫布格式，不能直接送 `/prompt`。

Klein 群組：模型載入、換臉、写真、人物定版圖。換臉及写真主要節點目前旁路；定版主鏈啟用，但保存的是動物肖像／三視圖提示詞，同時有未連接的人物文字。原檔中的 `JZL_MiniMaxPromptEnhancerNoOp` 不在運行節點表。照片批次會讀取原本範例與外部提示詞增強鏈，不能當成 Studio 的創作來源。

Krea 群組：雙圖編輯、單圖編輯、擴圖、局部重繪／移除；現存單圖分支啟用，其餘大部分旁路。雙圖分支的 Windows 模型路徑不存在；可確認本機根目錄有同名 Turbo 模型。Windows LoRA 名稱也不等於現存檔名。单圖原檔選用 Muse V2.5 模型，其他分支用 Krea2 Turbo；還有額外風格 LoRA 與舊範例修改要求。原檔沒有獨立文生圖分支。

以上只證明依賴和配置，不能證明「已包括所有圖片需求」。Krea2 編輯是 VAE 外觀參考加 Qwen3-VL 視覺文字編碼，單／雙圖的訓練次序是來源／場景在前、人物參考在後。上游指出 Turbo CFG 1 對移除顯著物件較弱，並建議 ≤2MP。[插件說明](https://github.com/lbouaraba/comfyui-krea2edit/blob/86f886dac23013d88996e3a2e99093ba44d322fb/README.md)。Krea2 本體支援文生圖：[官方模型資料](https://huggingface.co/krea/Krea-2-Turbo)。

## Studio 的調用邏輯

新增 `comfy_local`，只提供圖片渲染。Astra 仍為初始創作／圖片整理／審查設定；DeepSeek 的文字或圖片理解服務與本機渲染分開選擇，DeepSeek 不提供圖片生成。套用 Astra 或 DeepSeek 創作模式時，可明確搭配本機圖片服務。每次生成表單亦可單次選服務，不改全域設定。沒有跨服務商失敗回退。

| 明確需求／結構 | 調用 |
|---|---|
| 角色資產、四視圖 | Klein True V3，分別生成正面肖像、左全身、右全身、背全身，再拼成一張 2048×1024 候選 |
| 无參考的新地點／道具／群像 | Krea2 Turbo 文生圖補充適配圖 |
| 一張外觀／風格參考，或單圖修訂 | Krea2 Muse + identity edit LoRA |
| 来源圖＋一張參考的修訂 | Krea2 Turbo 雙圖編輯；來源先於新參考 |
| 其他兩圖、3–8 圖，或明確「參考圖生成」 | Klein ReferenceLatent，按完整的圖片編號保留全部參考 |
| 明確写真 | Klein 單張写真候選；角色 canon 的既有四視圖要求仍有效 |
| 明確換臉 | Klein + 原工作流 head LoRA；需要來源與一張已選身份參考，可另附角色排版圖 |
| 明確範圍修改 | Krea2 Turbo，唯一來源圖＋百分比矩形；生成後把框外的縮放來源像素合回 |
| 明確擴圖 | Krea2 Turbo，唯一來源圖＋左上右下像素邊距；原中心像素合回 |

自動路由只用目標類型、來源是否存在、參考數量與用途，不靠「換臉」等自然語言關鍵字猜意圖。創作模型處理具體畫面和修改內容。換臉／指定區域／擴圖要選明確操作；缺來源、錯範圍或超出容量會停止。角色的範圍修改不另附排版範例，來源四視圖本身提供排版；使用者選的參考不會被丟棄。需要多張 canon 圖的鏡頭目前不能直接使用 Krea 範圍／擴圖分支，可用多圖參考修改；沒有假稱能在 Krea 雙圖接口塞進任意多圖。

角色写真不會覆蓋 canon 四視圖；写真套圖在 Studio 是多個有明確目標的候選，不會一次執行原檔九條範例。自動選擇不代表生成品質保證，候選仍需審閱。

## 適配與原檔差異

執行版本是 `studio/local_images.py` 的 `studio-local-images-v3`，不是原畫布逐位元執行。只建所選分支，保留明确模型、VAE、CLIP、採樣家族；移除舊圖片、示例文案、無關 LoRA、外部提示詞增強、批次 loop 與預覽節點。Klein 採 True V3 bf16、原 CLIP、flux2 VAE、Turbo LoRA 0.2、一般分支 8 steps/euler/CFG 1；四視圖分支依實測提高至每個視角 16 steps。換臉另加原 head LoRA 0.75。Krea 採原對應 Muse／Turbo 模型、Qwen3-VL 4B、Qwen Image VAE、identity edit LoRA 1.0，10 steps/euler/simple/CFG 1；其來源 patch 以原分支 ref_boost 4、ref_boost_a 1 配置。UI 的「高度保留」仍為提示詞指示，不假稱是這些數值的開關。

第一版 Klein 一次生成整張四視圖的實測出現左右面重複。v2 改成四個獨立視角，但首次實測背面出現噪點。v3 保留相同 seed 再驗：每個視角提高至 16 steps；正面以方形肖像生成並置於白底首欄，兩個側面以該肖像作身份參考，背面則參考剛生成的全身側面以保持服装輪廓。最後只輸出一張組合候選。v3 已正確顯示四個視角，仍可觀察到局部服装細節差異，不宣稱已完全符合 canon。這仍不是數學保證，需要既有四視圖審查。完整原始渲染簡報保留在 `render-prompt.txt`，每個 panel 實際文字另存於 `comfy-graph.json`，不可把整張簡報稱為每個 CLIP 節點的完全相同輸入。

所有 recipe、來源雜湊、選擇原因、尺寸、seed 在 Studio job 入列時保存；實際 API 圖、每張輸入 SHA-256、ComfyUI prompt_id 與 history 在 job 資料夾保存。生成圖只從指定 `save` 節點取回一張，核對資料夾、job 前綴、尺寸與可解碼性，進入既有資產候選、審查及採用流程。四視圖是一個工作，內含四次採樣，耗時高於普通單張。

GPU admission 由已安裝的 `global_vram_arbiter` 在 `/prompt` 和執行階段接管；先讀 `/vram/status` 確認監控有效。Studio 不自行搶佔 GPU、停止服務、直接載入 Torch 或繞過 VRAM Manager。

送出前先保存唯一 submission token。逾時或回應遺失不重新送出；「取回本機結果」依 queue/history token 找回同一 prompt_id。確認執行錯誤後才可新建工作；未知送出狀態會阻擋同目標重複生成。Studio 重新啟動亦可取回同一圖。恢復只取回該工作結果，不改 canon，也不自動批准。

## 驗收紀錄

證據位於 `data/acceptance/local-images/`。所有真實測試以隔離作品／測試輸出執行，没有修改正式作品設定、內容或批准結果。最終測試結果和部署狀態見 `docs/STATE.md` 本項及 `verification.json`。


實測：Krea2 Turbo 文生圖成功；瀏覽器提交的 Krea2 Muse 單圖編輯成功把茶壺改藍，Astra 視覺審查通過、候選仍 pending，準備與渲染來源雜湊一致。Klein v3 真實四視角輸出已人工檢視。以相同回條取回 Krea 結果亦保持原 prompt_id/token，沒有再次生成。最終 Python 全套 348 passed；前端語法及 provider／prompt／參考圖／上傳回歸通過。

雙圖 Krea、換臉、局部修改和擴圖已通過程式圖、服務 schema 和回歸驗證，尚未逐分支做真實視覺驗收。不能把這些依賴檢查等同於全部效果已驗證。正式 4760 已回傳 v3 與本機 provider，靜態檔與磁碟相同；原全域圖片服務仍是 Astra。本任務沒有重啟正式服務或修改正式作品；檢查時已有使用者工作執行中，保持其運作。

## 2026-09-09 — Klein/H3 runtime-mode correction and real four-view sample

The installed CLI launchers and opt-in SDPA patch were inspected. The live H3 process lacked --disable-smart-memory; Klein adds it. HERMES_FORCE_SDPA_MATH is unset in both current launchers, so the old SDPA patch is inert. Some historical launcher comments still claim otherwise. No external launcher, kernel patch or GPU service implementation was edited.

Replayed identical Klein v4 model/graph/prompt/seed: H3 mode produced black side/rear panels; switching only the attention node produced black output; the existing VRAM Manager's Klein-mode switch produced a complete 2048×1152 front/side/rear/portrait sheet. Mode switch includes a fresh process, so this is evidence for the working runtime profile, not isolated proof that smart-memory alone is the root cause. The sample has minor costume/framing drift and is not approved canon. Artifacts: data/acceptance/character-sheet-standard/demo-v4-klein-mode/render.png and runtime-investigation.json.

Studio now requests Klein for local image work and H3 for local video work through the existing /vram/comfy/mode endpoint. It respects paused admissions and manager refusal when work is active; no forced stop or blind mode retry. A process-owned ComfyUI-compatible GPU reservation pins the verified mode/PID across preparation and rendering, preventing a switch between check and submission. Recovery uses history only and does not change mode or acquire GPU. Current mode is left in place until another explicitly requested generation needs the other mode.

## 2026-09-09 — Remove synthetic portrait padding

The user identified visible white blocks above/below the rightmost portrait. Studio v4 generated a 704×960 portrait and centered it on a pure-white 704×1152 canvas, adding exactly 96px at both ends. This was an adapter composition defect, not a model or GPU-mode defect. Adapter v5 generates the portrait at the full sheet height and concatenates its decoded pixels directly, removing the white canvas/composite nodes. Front/side/rear framing, reference order, seeds and overall 2048×1152 layout stay the same. Historical samples and receipts remain untouched. Thirty-four focused tests passed; real sample evidence is under data/acceptance/character-sheet-standard/demo-v5-full-height/.
