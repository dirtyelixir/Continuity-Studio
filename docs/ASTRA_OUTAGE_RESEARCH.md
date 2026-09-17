> Implementation follow-up (2026-09-09): the user subsequently authorized the mandatory shared-method layer. See [PRODUCTION_METHODS.md](PRODUCTION_METHODS.md). Both reproduced image-skill/HTTP-repair gaps are now fixed; real DeepSeek quality and full Astra-free acceptance remain outstanding. The audit below records the earlier observed state.

# Astra 中斷時的功能替代與品質保障調查

調查日期：2026-09-09（Asia/Hong_Kong）。範圍：目前 Continuity Studio、現場只讀設定、既有驗收紀錄與服務商官方文件。本文件是研究及建議，並非已部署的故障接管或品質認證；沒有提交新文字／圖片／影片／語音生成。

## 判斷

Skills 的指引與參考知識通常不是 Astra 專屬，可交給 DeepSeek 或其他模型使用；能否執行工具、看見相同圖片、遵守全部要求及達到同等創作品質，必須另外驗證。換模型並不會把 Astra 的能力一併複製過去。

Studio 已有 DeepSeek 創作 profile 及獨立本機圖片服務，但目前不能宣稱「Astra 不可用時，全部功能已有經品質驗收的後備」。現場 GET /api/settings 顯示 mode/default_provider/image_provider 均為 astra，DeepSeek credential_configured=false。過往 DeepSeek 驗收亦明示沒有真實 DeepSeek generation；通過的是整合／隔離測試。原始證據：[DeepSeek 驗收](../data/acceptance/deepseek-settings/verification.json)、[整合說明](DEEPSEEK.md)。

應保障的是：每項能力有已驗收的獨立執行路徑、沿用相同創作契約及素材、結果經驗收才可視為達標；沒有合格路徑時保留工作並明示未完成。任何模型（包括 Astra）都不能保證每次生成必然優秀。

## Skills 到底能否承接

| 層次 | 能否轉移 | 必要條件 |
| --- | --- | --- |
| 故事、對白、導演方法、分鏡、H3 提示詞等文字指引 | 通常可以 | 實際載入相同版本的指引、必要 references、canon 與例子 |
| 輸出格式及確定性檢查 | 可以 | 由 Studio 執行相同 schema、引用、來源與時序檢查 |
| 看圖與比較角色／場景連續性 | 有條件 | 模型支援圖片輸入，adapter 傳入真實像素及正確 reference roles |
| scripts、MCP、瀏覽器、圖片工具 | 不能只靠複製文字接管 | agent runtime 必須提供相應工具、執行循環、憑證及回傳格式 |
| Codex 專用工具名稱／產品內功能 | 不會自動繼承 | 寫獨立 adapter 或採用等價工具；逐項驗收 |
| Astra 的創作判斷與推理表現 | 不可直接轉移 | 用同一作品測試、盲評與實際修訂成本判定 |

OpenAI 的 skills 文件把 skill 定義為 SKILL.md 加可選 scripts、references 等內容，按需要載入；Agent Skills 也提供跨 agent 的整合規格。因此「知識可攜」成立，但「任何 runtime 已具備全部工具」不成立。[OpenAI skills 文件](https://learn.chatgpt.com/docs/build-skills)、[Agent Skills 整合規格](https://agentskills.io/client-implementation/adding-skills-support)。

還需區分三個來源：此 Codex 對話中可見的技能清單、Studio 內建的固定技能／規則，以及 Studio extension registry。三者不是同一清單。此次讀取 data/skills/registry.json，只看到一個已啟用的 performance-notes（performance_notes capability）；這不包含 Studio 內建方法，也不代表本對話全部 short-drama 等技能都已安裝到 Studio。

## 程式核查與已重現缺口

一般路徑：engine.build_input 先讀取該 capability 的啟用 skill，將內容附到 prompt，再選 provider；DeepSeek HTTP adapter 收到同一 prompt，帶圖時選 vision_model。分鏡的固定 short-drama-storyboard 參考內容，以及已選 DirectorSKILL 的完整方法內容，也在 provider 選擇之前組裝。因此這些已整合的創作指引確實可交給 DeepSeek，並非 Astra 私有能力。

定位：studio/engine.py:41、:233、:249；studio/providers.py:107、:111；studio/storyboarding.py:15、:44；studio/director_styles.py:74。Studio 的 skills 安裝器只複製 SKILL.md 及 references 的 md/txt，沒有 script 執行功能；文字 provider 也沒有通用 tool-calling loop。Codex adapter 的非圖片工作關閉 shell／exec／image generation，不能把此對話的全部工具能力當作 Studio 內建能力。定位：studio/skills.py:14；studio/providers.py:59、:60、:110。

**缺口 A：自動圖片準備沒有取得 image_prepare 專用擴充。** 外層工作 capability 是 image，engine.build_input 只取 image 的 skill；enqueue 選了 image_prepare 的 provider 後，execute 把原 prompt 傳給內部 image_prompts.prepare，未再次載入 image_prepare 的 skills。隔離實驗用一個只屬 image_prepare 的標記指引，直接 build_input(image_prepare) 有標記，build_input(image) 沒有標記。這影響所有 provider，不是 DeepSeek 特有；目前 registry 沒有這類已啟用擴充，因此是已重現的承接缺口，並非證明現有作品已漏掉某個已安裝 skill。定位：studio/engine.py:41、:265、:384；studio/image_prompts.py:150。

**缺口 B：DeepSeek／HTTP 分鏡修訂的回應保存不齊。** storyboarding.run 的一次修訂需要 work/result.json；Codex adapter 產生該檔，http_run 直接驗證並回傳物件，未寫入原始 result.json。隔離 MockTransport 回傳不合 schema 的分鏡，確認只有一次 HTTP 呼叫、沒有原始結果檔及 repair-1，工作直接失敗。這是結構錯誤恢復能力的差異，不是 DeepSeek 真實輸出品質測試。定位：studio/storyboarding.py:59、:64、:67；studio/providers.py:87、:121。

**尚未有自動接管／品質資格機制。** resolve 只選當前 provider；run 只按 kind 分派，engine.execute 的例外將工作標記 failed。圖片整理和渲染各有配置；圖片完成後 enqueue 的 image_review 又按當時 routing 選 provider，並非三步共用一個已凍結的全流程接管配置。切換中途需納入故障演練。定位：studio/providers.py:19、:123；studio/engine.py:265、:362、:401。檢查的通用執行路徑未發現非 Codex provider 失敗後暗中呼叫 Astra 的分支；這是程式核查結論，仍需端到端 outage 演練。

既有結果檢查包含 schema、對白／引用／來源、四視圖審查欄位等；image succeeded 後另排 review，review verdict 及人類 adoption 不是同一狀態。不能用 job succeeded 或綠色採用狀態代表已獨立證明藝術品質。定位：studio/engine.py:322、:331、:359、:361；[既有採用決策](DECISIONS.md)。

隔離重現證據：[ASTRA_OUTAGE_VERIFICATION.json](ASTRA_OUTAGE_VERIFICATION.json)。兩項缺口尚未修改。既有相關回歸測試 108 passed（兩個既有依賴棄用警告）；這證明現有測試通過，不能推翻本次另行重現的缺口，也不代表真實模型品質合格。沒有以本機委派的未完成報告作驗收；以上是主代理直接核查及隔離重現所得。

## 現場功能覆蓋清單

正式服務 127.0.0.1:4760 的 GET /api/settings 列出以下 15 項 built-in capabilities 及 1 項 extension。provider 清單目前只有 astra、deepseek、comfy_local、manual；沒有已配置的 Claude、Gemini 或 BFL provider。

| 功能／capability | Astra 停用時的現有替代路徑 | 品質／覆蓋判斷 |
| --- | --- | --- |
| 作品／章節故事、劇本、對白：narrative | DeepSeek V4 Pro | 已有路由，未有真實 DeepSeek 驗收 |
| 分鏡與鏡頭規劃：storyboard | DeepSeek V4 Pro | 同上，須測原文覆蓋及連續性 |
| 導演方法推薦：director_style | DeepSeek V4 Pro | 同上，推薦有來源不代表藝術判斷相等 |
| 看圖整理圖片 prompt：image_prepare | DeepSeek，帶圖時走 Vision Exp | 真實視覺驗收缺口；本機 renderer 本身不能取代此步 |
| 人物／場景／道具／群眾／關鍵幀生成、修改：image | comfy_local；或另配置外部 image API | 本機有真實樣本但各分支品質不齊；manual 不算等價自動替代 |
| 圖片連續性審查：image_review | DeepSeek Vision Exp | 視覺審查能力待驗收 |
| H3 模式與關鍵幀策略：h3_strategy | DeepSeek | 須驗證理由、模式及來源匹配 |
| 首尾幀對應的影片 prompt：h3_video_prompt | DeepSeek Vision Exp（有圖片） | 必須完整保留首尾幀及對白，不能走純文字假設 |
| H3 基本 prompt／英文化準備：h3、h3_prepare | DeepSeek | 結構可驗，實際 prompt 品質未驗 |
| H3 Scene globals／Shot 文本與再生成：h3_global、h3_shot、h3_scene | DeepSeek | 保留兩級契約、引用、對白及來源新鮮度 |
| 相鄰鏡頭接續判斷：h3_guidance | DeepSeek | 須測 hard cut 與連續延伸的區分 |
| 整體品質檢查：qc | DeepSeek | 同模型生成＋自評不足以作獨立品質保障 |
| 擴充表演筆記：performance_notes | 可經 default provider／skill 路由 | 已啟用擴充不等於有跨模型品質認證 |
| VoxCPM 配音（獨立子系統） | 現有本機 VoxCPM2，已有內容可繼續合成 | 合成不依賴 Astra；新故事／聲音指導的創作仍需可用模型，音色及粵語需聽審 |
| H3 影片渲染（獨立子系統） | 現有本機 H3，使用已採用 prompt／素材 | 渲染不依賴 Astra；新的準備工作需要上述文字／視覺路徑。整 Scene 接續仍有既有範圍限制 |
| 作品保存、canon、版本／採用、匯入／匯出 | 本機應用及資料 | 不因 Astra 模型停用而消失；不代表新創作能繼續生成 |

本機圖像驗收見 [LOCAL_IMAGE_WORKFLOWS.md](LOCAL_IMAGE_WORKFLOWS.md)；VoxCPM 見 [VOXCPM.md](VOXCPM.md)；H3 本機渲染及接續限制見 [H3_ONE_CLICK.md](H3_ONE_CLICK.md)。現場 capability 宣告證明可選路由，不足以證明每個實際生成路徑都已在 outage 下驗收。

## 服務商候選與選型

下表是按官方能力作的候選篩選，不是 Studio 實測排名。新增供應商仍須 adapter、帳戶權限及真實創作驗收；不能只填 base URL 就假定完成。

| 候選 | 適合承接的工作 | 現況／限制 |
| --- | --- | --- |
| DeepSeek V4 Pro：deepseek-v4-pro | 故事、對白、分鏡、文字 prompt、文字 QC | Studio 已有直接整合；當前沒有配置憑證，未完成真實創作品質驗收。官方文字模型不能直接讀圖 |
| DeepSeek V4 Flash Vision Exp：deepseek-v4-flash-vision-exp | 圖片理解、看參考圖整理 prompt、圖片審查、依首尾幀寫 H3 | Studio 已有圖像路由；官方明示實驗模型，不能作唯一未經驗收的視覺保障 |
| Anthropic Claude Opus 5／Fable 5.1 | 高要求文字創作候選、導演判斷、視覺審查 | 官方支援文字及圖片輸入、文字輸出、工具使用；尚未在 Studio 接入及盲評，不能聲稱比 DeepSeek／Astra 更會寫本作品 |
| Google Gemini 3.8 Flash | 多模態理解、獨立文字／視覺複核候選 | 官方穩定模型，支援文字、圖片、影片、音訊、PDF 輸入及文字輸出；Studio 尚待 adapter／驗收。名稱含 Flash 不能代替實測判斷 |
| Google Nano Banana Pro：gemini-3-pro-image | 雲端人物／場景／關鍵幀生成、多參考圖修改 | 官方定位專業資產製作；最多 14 張混合參考圖，另有角色及物件高保真子限額，不能當成 14 個人物身份保證；Studio 尚待整合 |
| BFL FLUX.2 [max]／[pro] | 獨立雲端出圖與多參考圖編輯 | 官方區分高精度 max 與生產規模 pro；編輯文件寫 API 最多 8 張、playground 10 張，需按實際端點確認。不是現有 OpenAI-compatible transport 的直接替換 |
| 本機 ComfyUI Klein／Krea2 | 已有本機人物、場景、道具、關鍵幀／編輯路徑 | 已有真實樣本，但衣著、人數、照明等仍見偏差；分支通過 graph/schema 不等於每個分支視覺合格。與 H3／VoxCPM 共享本機 GPU／VRAM Manager |
| OpenAI GPT Image 直接 API | Codex／Astra 單一路徑故障時的額外圖片通道 | 官方有獨立 Image API；不能算 OpenAI 整體故障時的獨立後備，也未證明本機 Astra 工具內部使用哪個圖片型號 |

官方來源：[DeepSeek API／模型](https://api-docs.deepseek.com/)、[DeepSeek vision 限制](https://api-docs.deepseek.com/guides/vision/)、[Claude 模型與模態](https://platform.claude.com/docs/en/models/overview)、[Gemini 3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)、[Google 圖片生成](https://ai.google.dev/gemini-api/docs/image-generation)、[BFL 多參考圖編輯](https://docs.bfl.ai/flux_2/flux2_image_editing)、[OpenAI 圖片 API](https://developers.openai.com/api/docs/guides/image-generation)。模型／端點是本次查閱所得，帳戶實際可用性另需檢查。

不以單 token 價格排序。適合本作品的比較單位是「每個可採用結果的總成本」：生成、失敗、重試、圖片準備、獨立審查與人工改稿時間全部計入。先品質達標，再比較延遲與成本。

## 建議的品質契約

以下是待實作的建議，不描述目前已存在的保證。

1. **共同創作輸入。** 每次工作凍結 canon、原劇本／粵語對白、導演方法、相關 skill 版本與內容 hash、reference roles、真實圖片 hash 及相鄰鏡頭狀態。換 provider 只改 transport／模型所需格式，不刪除約束，不以舊文字代替真實參考圖片。
2. **前置相容性檢查。** 清楚宣告文字／圖片輸入、圖片輸出、參考圖數量、編輯／遮罩／擴圖、輸出長度及 JSON 能力。載不下必要 skills 或傳不了全部必要圖片就停止，不可截短後仍標示完整套用。未驗收的新技能不可因 wildcard routing 就被稱為已支援。
3. **程式規則與創作品質分開。** JSON 正確、對白逐字、角色／道具 ID、參考圖對應、來源新鮮度與時序可由程式檢查；戲劇張力、自然粵語、具體可拍的運鏡、畫面連續性則要語義／視覺評估。格式通過不是作品合格。
4. **獨立複核。** 文字或圖片交給第二個已驗收模型檢查，輸入相同來源及素材；不能只讓生成者自評。審查模型也可能漏判，須以人工評分校準；Astra 故障時，複核路徑本身也要不依賴 Astra。
5. **明確的結果狀態。** 分開「已生成」「已驗證結構」「創作品質通過」「用戶採用」。保留既有用戶可採用有 advisory notes 結果的權利，但不能把這種採用偽裝成零缺陷認證。低品質候選不自動覆蓋 canon 或已採用版本。
6. **有限修訂與透明停止。** 不合格時列出具體問題，限定修訂次數／時間／成本；仍不合格則保留候選與失敗原因、交由下一個合格後備或待處理。不能為完成率降低要求。

採用任務專屬評測、盲比較與人工校準的方向符合官方評測建議；以下題目與門檻則是本專案的設計建議，不是供應商承諾。[Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)。

## 可執行的接管驗收設計

先從《下一站：長洲》等現有作品挑選使用者認可的樣本，另加入已知失敗案例；分開調整用樣本與保留測試樣本。以相同來源／素材與語義契約比較 Astra、DeepSeek 與選定第三方，隨機化 A/B 次序；不同 renderer 的同 seed 並不等於相同實驗起點。

| 測試組 | 驗收重點 |
| --- | --- |
| 故事／章節／對白 | 人物動機、因果、揭示順序、香港語感、既定對白與 canon 不被改寫 |
| 導演推薦／分鏡 | 有文本證據、動作可拍、鏡頭動機清晰、一幀一時刻、手部／持物／軸線連續 |
| 圖片準備／生成／編輯 | 同一角色身份、服裝、人物數目、左右方位、空間與照明；四視圖順序及比例；指定修改而非重設人物 |
| 多參考圖／首尾幀 | 所有必需圖片確實傳入，角色與場景角色分工不混淆，視覺衝突可指出 |
| Scene／Shot／H3 prompts | 三欄契約、準確對白／聲音、秒數、起止畫面、具體運鏡、不憑空加動作、可直接交給對應 H3 mode |
| QA 與反例 | 以已知錯人、錯服裝、漏道具、錯方向、黑圖、空 prompt 等測漏判及誤殺；單看通過率不足 |
| 語音／影片／輸出 | 保留既定素材與提示詞；實際畫面／表演／粵語發音與音色由聽看驗收，檔案尺寸／時長檢查另計 |

建議初步每項創作維度 1–5 分，4 分表示可直接用或只需小修；任何主要維度低於 4 分不以其他高分抵銷。不可違反的指定對白／引用／來源約束須全部通過。這是待用戶認可樣本校準的起始門檻，不是已取得的測試結果。每種主要任務重跑多次，記錄首次合格率、修訂後合格率、嚴重錯誤、延遲及每個合格結果成本。

在隔離資料及測試環境另做故障演練：禁止 Astra/Codex 呼叫後，完整跑一個多角色、多 Scene、含圖像準備／審查及 H3 的流程。檢查 401／欠額、429、timeout、5xx、視覺模型不可用、圖片服務失敗，以及「服務已收件但本地未收到回條」。未明提交只查詢／回收，不能自動跨 provider 重複生成。恢復後不重跑、不重批、不改 canon。此演練和真實服務商生成尚未在本調查執行。

## 故障範圍與建議組合

| 故障 | 有效保障 |
| --- | --- |
| Codex 配額、登入、CLI 或 Astra 模型路徑不可用 | 獨立憑證的 DeepSeek／Anthropic／Google；OpenAI API 是否也可用須另測 |
| OpenAI 整體服務不可用 | 至少一個非 OpenAI 的創作＋視覺路徑，以及本機／非 OpenAI 圖片路徑 |
| DeepSeek 文字或實驗 vision 單項不可用 | 各能力分開選後備；不能把文字模型當視覺模型用 |
| 本機 GPU 忙碌或故障 | 已驗收的雲端圖片路徑；本機 Klein 與 Krea2 並非硬件上互相獨立 |
| 整機／網絡故障 | 屬更廣泛災備；需資料備份與另一運行環境，不能靠換 API 模型解決 |

建議先保留 Astra 為主用，完成 DeepSeek V4 Pro＋Vision＋本機圖片的真實資格測試；同時準備一個獨立、通過盲評的 Claude 或 Gemini 文字／視覺後備，以及 Nano Banana Pro 或 FLUX.2 的雲端圖片後備。是否把 DeepSeek 排第一必須由作品實測決定，不按低價格或名稱決定。

「所有功能有 alternative」應定義為每項生產能力有可執行且已驗收的後備，或本來就不依賴 Astra。人工匯入可作保留工作進度的出口，但不能計作等價自動創作後備。先建立合格名單與透明切換，再考慮預先授權的自動接管。
