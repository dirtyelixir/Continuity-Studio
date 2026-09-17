# Qwen3.8 創作引擎

在「擴充功能與服務商 → 創作引擎」選擇 **Powered by Qwen3.8**，選定圖片生成服務，按「套用整體模式」。故事、劇本、分鏡、導演建議、圖片理解、提示詞、審查及技能的新工作會使用本機 Qwen。圖片生成及配音獨立設定。

執行模型是 `qwen3.8-27b`，透過既有 VRAM Manager 閘道 `http://127.0.0.1:8080/v1`。Studio 製作方法、內容審閱與上下文預算照常適用。新工作保存服務商與容量；切換模式不改動已存在的工作、內容或 DeepSeek 憑證。

「檢查本機 Qwen3.8 連線」只讀模型清單及可用的圖片理解資訊，不啟動生成，也不能保證 GPU 即時可用。忙碌、無法取得 token 計數、輸出截斷或無效結果會明確停止；不會自動改用其他創作引擎。

驗證：52 項 Python 測試、兩份 JavaScript 檢查及語法檢查通過。隔離瀏覽器驗證套用、連線及重新載入；真實文字請求回傳繁體中文鏡頭描述，圖片請求正確辨認測試形狀與顏色。這是小型接線驗收，並非完整作品品質保證。正式設定仍為 DeepSeek + ComfyUI，新增選項已部署。

Evidence: `data/acceptance/qwen-profile-20260913/verification.json` and `live-provider.json`. Backend API: `POST /api/settings/profile` with `mode: "local_qwen"` and explicit `image_provider`; passive check: `POST /api/settings/qwen/check`.
