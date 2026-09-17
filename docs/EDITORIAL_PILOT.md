# 剪接與預覽

2026-09-13 後續更新：Visual Skills 的戲劇／montage 章節已接入一般自動故事、分鏡、章節規劃及獨立審查，見 [自動 montage 方法](MONTAGE.md)。下文「只用於試行／未接入所有規劃」保留為當時實作範圍的歷史記錄。

2026-09-13 正式整合：使用者已採用為第 5 版。現已補上正式修改保存、各場景入口、聲音正式匯出、導演審查及舊→新 Shot 對照。現行行為見 [正式流程檢視](EDITORIAL_MAPPING_AUDIT.md)。下文保留最初試行設計與當時驗收狀態；第 4 版／尚未採用等敘述屬歷史。

# 原始一場戲試行紀錄

入口：Studio 頂列及「製作手冊 → 導演規劃與剪接」的「剪接試行與預覽」。
目前作品：下一站：長洲；來源正式版 4；場景「十二樓一隻」。

此試行由 Codex 按既有已採用分鏡人工撰寫，沒有呼叫生成供應商，也沒有批准生成結果。
原版 5 段 / 54 秒；試行 9 個連續來源 Shot / 53.5 秒預定剪接。來源生成時長合計 61 秒，與成片取用時長分開。
19、17、14 樓各自成為獨立來源；13 樓聽聲保留 4 秒。反應近景及最後拾容器全景分開，避免把不同機位藏在同一來源片段內。
「熟人的背影」維持連續 10 秒平搖：先保留樂言兩秒反應，再揭示女人。這也是不切鏡對照；沒有為展示蒙太奇而加手掌特寫。

## 同一份方案

候選與正式方案均使用現有 `Production`、`SceneDirectorPlan`、`ShotDirection`、`EditDecision` 合約。
試行是 `settings` 中的候選快照，並非另一條正式 Shot list。編輯只可改本場景剪接取用及聲音位置；其餘場景、canon、故事、原文對白受保護。
顯式「採用為正式方案」經 `engine.save_plan` 建立正常正式版本，原有資產依既有依賴檢查標示 stale；不刪除或重新生成。
採用不是導演審查通過：正式生成仍受 `directing.require_ready` 管控。
`editorial_applied:<project>` 保存本次已採用聲音時間及狀態註解的來源版本；其他正式修改會令其 `plan_hash` 不再匹配，不能視為已同步。

每次儲存保留上一候選快照、遞增版本，並由同一 Production hash 重新派生 H3 草稿及狀態引用。
正式來源 hash 改變時試行可讀、不可覆寫或採用。此版沒有自動 rebase；需要按新來源重新編寫。
人名與對白保持原語言，其餘 H3 草稿英文。模式未確認時 `execution_mode=null`、`ready=false`，不會因缺圖而偷偷送出 T2VA。
草稿不是已通過素材核對的交接提示詞。正式採用後使用現有 Studio 模式建議、參考圖、英文準備及提示詞採用流程。

## 預覽與證據

可播放、暫停、拖動時間、比較原版、修改入出點、重排、重用同一 Shot、儲存及匯出。
畫面與聲音時間獨立；刮擦聲橋跨入下一畫面。缺少完整原有對白標記會警示並阻止正式採用。
沒有音檔時僅顯示時間標記，不以 TTS 模擬完成聲音。只有仍符合候選依賴 hash 的已批准圖片可作分鏡預覽；沒有圖片則用文字卡。
Media reference 記錄 immutable asset ID、來源 generated/imported、可空 job ID 與 dependency hash。同一 Shot 重用仍讀同一圖片。
真實影片匯入、候選 take 剪接、實際 source in/out 與成片渲染屬後續素材閉環，本試行沒有冒充已完成。

每個 Shot 帶有故事位置、入／出狀態的內容 hash 及原有分鏡事件摘錄。剪接重排或重用舊時刻不改寫故事狀態；省略拾回容器使用原有分鏡的時間省略依據，不為生成缺陷虛構換手。
身份辨認保守評估：普通手掌不能證明具名身份；未建立觀眾身份基礎的露面仍 uncertain；刻意不揭示身份合法。
本場只能計劃表達「樂言認出熟人」，未證明觀眾知道她叫黃太。文字卡未驗證實際構圖、表演、嘴形或觀眾理解。

## 知識適配及來源

Studio-owned `studio/bundled/editorial-knowledge/provenance.json` 記錄逐文件 commit、URL、SHA-256。讀取時驗證本機內容。
選讀 DirectorSKILL 的 editing-and-assembly / sound-and-dialogue，以及 Serge Shima 的 visual-skills dramaturgy。
固定八／十二格裁剪、節奏表、三細節或五錨點配方僅為可選啟發；不成為硬驗證，也不帶入上游模型路由或強制完整工作流程。
本次適配只用於已撰寫的場景試行，沒有宣稱全體後續自動規劃已接入兩套完整 skill。

- DirectorSKILL：wuwangzhang1216，MIT；commit `c65ae0d14457053efb1e354c7e7f7e120d97fad1`。
- Visual Skills：Copyright 2026 Serge Shima，CC BY 4.0；commit `ae26d624edd747e719fa21528d18d39e68c04a0e`。
  作者：https://sergeshima.com / https://aimasters.me / https://t.me/aimastersme
  原作：https://github.com/smixs/visual-skills
  原文、LICENSE、NOTICE 均保留；Studio 適配及試行另寫，沒有改稱原作者的完整工作流程。

## 驗收

31 個 editorial / timing 測試通過，包含完整原對白、英文草稿、無聲口形、版本衝突、stale、顯式採用、外部來源圖片、換手失效、倒敘狀態、同源重用、合法 J/L-cut、漏對白及非有限時間拒絕。
另有 72 個既有 directing / directing-model / speech / workflow-ownership 測試通過；Director UI regression 與 JS syntax 通過。
真實資料備份、試行快照及部署收據：`data/acceptance/editorial-pilot-20260913/`。
正式版仍為 4，沒有生成媒體，沒有代使用者採用候選。

真實 Chrome 驗證：正式頁顯示 9 段 / 53.5 秒；跳到連續發現鏡並播放，時間推進及跨切點刮擦標記正常，無聲口形與身份不確定提示可見。另以臨時資料目錄、4761 端口驗證出點 1.5→1.8、53.8 秒、儲存 v2 及一筆歷史，以及原版 5 段 / 54 秒只讀比較；測試服務已停止。使用者的正式試行未因 UI 測試而修改。
