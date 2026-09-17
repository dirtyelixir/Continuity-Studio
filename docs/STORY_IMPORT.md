# 劇情導入與分鏡選型 — 2026-09-08

Continuity Studio 已加入「貼上／導入劇情」。選擇已有劇情或完整劇本，保存後可直接交給 Astra 建立角色、場景、鏡頭及關鍵幀文字方案。審閱並採用後，沿用現有參考圖、圖片審查、分鏡圖及 H3 / Ref2VA 流程。

## 給使用者

1. 按右上角「貼上／導入劇情」。
2. 選「已有劇情／故事」或「完整劇本」，貼文字，或選 TXT、Markdown、Word DOCX。
3. 檢查文字，填作品名稱；視覺方向可留空。勾選導演推薦，即會先比較適合此內容的三個導演方向；也可建立作品後在製作手冊啟動。
4. 選導演方向後建立文字方案（也可直接用原有方向）。工作完成後按「審閱方案」，檢查故事、角色、分鏡、原文對應，以及 AI 推定的外觀／空間安排。
5. 按「採用此方案」，再到「角色與場景」建立參考素材，接「鏡頭與分鏡」及 H3。

原文獨立保存。完整劇本的 screenplay 必須逐字相同；劇情模式的 story 必須逐字相同，另行整理可拍的 screenplay。方案不會自動覆蓋正式製作，也不會在導入時開始圖片／影片生成。「只有構思」保留原有故事發展入口。

目前針對單集／短篇：檔案最大 2 MB、文字最多 20,000 字、40 個 Shot；不限制非空行／段落數。非空行只作來源定位，不是「一行一鏡」。超限會拒絕並請分開導入，沒有截斷。DOCX 讀取正文及表格內的文字，不保留排版、圖片、頁眉頁尾；掃描 PDF／OCR、整本小說分集及匯入到既有製作的合併留待後續。

## 比較與決定

這是閱讀實際 skill、參考檔案、資料契約及授權後的系統適配評估，不是五套使用同一劇本的生成品質盲測。只有選定適配器進行本次 Studio 實際生成驗收。

| 候選 | 查核所得 | 在本系統的取捨 |
|---|---|---|
| [DirectorSKILL / cinematic-director](https://github.com/wuwangzhang1216/DirectorSKILL) | 現版是完整電影製作指令流程，含 blocking、coverage、剪接、聲音及 20 個導演方法 overlay；不只是風格提示。MIT。 | **已接入內容導向的推薦與風格層。** Astra 比較 20 套方法，提供三個有劇情依據的方向；用戶選一個後，才載入完整模組作分鏡。不以整套上游 pipeline 取代既有 canon/H3。見 DIRECTOR_STYLES.md。 |
| [hosnye/directing-cinematic-storyboards](https://github.com/hosnye/directing-cinematic-storyboards/tree/main/.claude/skills/directing-cinematic-storyboards) | 強項是場景地理、軸線、coverage、靜態分鏡與運動分離，也有 Python validators 和示例。檢查到的完整 repository tree 沒有 LICENSE。 | 作研究參考；本次沒有複製或安裝其內容。若日後要納入程式分發，先釐清作者授權。不能直接把它的 Markdown validators 當作 Studio JSON 驗證。 |
| [shuohao-skills / novel-storyboard](https://github.com/eternityspring/shuohao-skills/tree/main/skills/novel-storyboard) | 所讀 SKILL 1.3.0，硬前提 script.json；段 → 段內 2–5 秒 cut → 每切關鍵幀，17 道門（含可選配方門），H3 I2VA 投產輸出。Apache-2.0。 | 借鑑來源認領／時長／對白對帳的設計思路。不能直接接現有 Ref2VA：Studio Shot 為 4–15 秒連續鏡頭且 Scene 獨有 global。整套替換會改變使用者剛確立的語義與匯出。 |
| [cajias/agentic-video-skills](https://github.com/cajias/agentic-video-skills) | Marketplace 集合，director 的上游確為 DirectorSKILL。實際 vendored tree 只見 14 個導演檔，與上游 20 個不同；各組件授權不同。 | 方便尋找工具，但不是第五種導演方法。需要某一項時應選清楚版本及上游，避免全包重複及授權混淆。 |
| [short-drama-storyboard / drama-skills](https://github.com/zenstory-ai/drama-skills/tree/main/skills/short-drama-storyboard) | 本機已安裝；原文到鏡頭的職責、方向／視線／持物、起止狀態與冻结關鍵幀，風格可變。MIT。 | **選為本次核心。** 對應 Studio 已有的 scene/shot/start/end/keyframes 最直接，無需切換現有 H3 模式。 |

這次的整合是「Astra 使用選定 skill 的分鏡知識，輸出 Studio 的結構」，不是讓另一套工具接管工程。沒有修改全域 provider 選項，也沒有自動降級成弱模型。

## 實作與持續維護

- 新增 storyboard capability，預設 Astra，可在服務商設定獨立切換 HTTP／人工，既有 instruction extensions 可用 storyboard capability 補充。
- `studio/bundled/short-drama-storyboard` 保存 SKILL.md、shot-craft.md、keyframe-craft.md 及原 MIT LICENSE。固定本機版本 commit `3ab6b8550bbccef71001d2187e2b2ac9a74ab917`，每檔 SHA-256 在 provenance.json；執行前核对，工作記錄固定來源、雜湊和適配器版本。這是內建知識適配，不是在全域 registry 默默啟用全部 skills。未執行任何上游 scripts。
- 新的 projects.source_kind / source_filename 為加欄 migration；舊作品預設 idea。原文字串保存在現有 idea 欄位，之後修改製作方案不改原文。
- 工作凍結 source_text 及 P001… 的非空行，回傳 Production、coverage、adaptation_notes。驗證來源完整、無重複、順序正確、鏡頭存在且都有來源，以及原文逐字保留。
- 分鏡也按當時圖片服務商檢查參考數量：Astra 最多五張，若有尾幀須預留首幀參考的位置。已知相關角色／道具不能以刪除身份資料來規避限制。
- Astra/Codex 保存的文字候選若不通過 schema／來源／參考數量檢查，最多進行一次修正；原候選及修正请求／結果分開保留。網路／登入／模型不可用不會自動換服務商或重試。人工輸入的錯誤會直接回報。這個修正只限文字，沒有圖片重抽。
- 連結檢查證明結構可追溯，**不證明每個動作／對白已正確表達**。Astra 的內容審查及使用者審閱仍然必要；不能把「全部行都有引用」當成創意品質保證。
- 採用沿用 revision conflict、canon、dependent asset invalidation。修改後不再匹配舊 Production 的 coverage 不會當成当前匯出；原工作記錄保留。
- 匯出含 source/original.txt、來源資訊，以及在目前方案匹配時的原文分鏡對照和 skill provenance。DOCX 的原始二進位不另存，保存的是使用者檢查後提交的文字。
- 檔案預覽端點不建立作品或工作；不解壓到磁碟、不執行巨集，拒絕壞檔、加密、XML DTD/entities、控制字元及大小超限。失敗時表單原有文字保留。

## 來源版本

研究時 GitHub API 所見：DirectorSKILL `c65ae0d14457053efb1e354c7e7f7e120d97fad1`；hosnye `a09cf34b762d7a8c12dd08311be0be37e460361a`；cajias master `204cefd08bbb87fd4681f1f2b0dccbc444a978c1`。版本差異解釋為何 marketplace 描述不能代替實際上游檔案查核。

驗收記錄見 STATE.md 與 data/acceptance/story-import/。
