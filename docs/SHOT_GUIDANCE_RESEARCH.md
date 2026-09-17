# 分鏡與段間引導研究 — 2026-09-08

## 結論與適用範圍

切鏡不需要自動延續上一段畫面。針對本機 AIMixer MiniMax H3 Director，只有需要同一鏡頭不中斷延長、延續運鏡／動作時，才建議下一段啟用「引用上段」。同一 Scene、同一人物、道具狀態相連，都不足以單獨構成啟用理由。

本次是來源、程式與現有 UI／production 的研究，沒有修改 ComfyUI、工作流、生成設定或 canon，沒有提交／取消生成，沒有做開關 A/B 渲染。下列品質風險屬於機制推論，不是本次實測成片結論。

## 已核對的事實

- 本機安裝：`/home/navievroom/comfy/ComfyUI/custom_nodes/ComfyUI_MiniMaxH3_Director/`。
- Chrome 的實際導演台正在執行 r2v，三組提示詞。觀察時總開關「段间引导」開啟、上下文 5 幀、方式為「引导」。本次沒有打開其他組改動設定，故不宣稱已核對第二／第三組的實際開關。
- 本機 UI 提示直接寫明：「同镜头、同画布、上下文 22 帧；换镜请关『引用上段』」。一般引導以先前 AV 作 Guide；「引导+重绘」改用先前內容作運動初值重畫接縫，亦不是一般硬切模式。
- 上游 README 說明段間引導把上一段末尾運動及生成音頻釘入下一段采樣，再裁去前綴。可選 5／22／39／56；上游總開關預設關，推薦接續窗口 22。本機執行設定與上游預設應分開看。
- 5 幀仍然會接續前段畫面，並不是角色一致性專用開關。以 UI 24 fps 換算，5／22／39／56 幀約為 0.21／0.92／1.63／2.33 秒；實際采樣另受 H3 幀格對齊影響。音頻窗口在實作中可獨立指定，不能將此換算當成音頻引導長度。
- H3 官方 Ref2VA 指南區分可重用 Subject、構圖 Picture、影片延續及 Audio 引用。共用人物參考可以跨切鏡使用；不需要把前段畫面鎖為下段開頭。
- 官方格式允許單次生成內有多個 Shot，後續 Shot 以時間戳標示切點。生成段落與攝影 Shot 是不同概念；目前 Studio 的一 Shot 一生成組是產品交接選擇。

## 建議判斷

本機程式證據：`director/segment_continuity.py:169` 解析總開關，`:187` 解析每段引用上一段，`:329` 的 `is_continuity_active` 同時要求兩者開啟並排除第一段；關閉時回到官方 conditioning 路徑，不加 Motion Context pin／patch／trim。`director/h3_motion_context.py:429` 將前段畫面加入 keyframe context；`:460` 起可再加入前段音頻。這條路徑先建立視覺 context，再選擇是否延續音頻，不能把它視為只延續音頻的功能。`web/js/minimax_i18n.js:103` 保存上述換鏡提示。

調查執行：本地 Qwen 委派因 GPU 正被使用而回傳 503，沒有完成調查或驗證；未重試、未搶佔渲染。上述必要程式查閱由主代理直接以只讀文字方式完成。

| 下一段與上一段的關係 | 下一段「引用上段」 | 仍要管理的連續性 |
| --- | --- | --- |
| 同一鏡頭因長度限制拆開，動作／運鏡繼續 | 開 | 結尾速度、方向、人物動作及音頻 |
| 正反打、遠景切特寫、插入鏡頭 | 關 | 身份、視線、軸線、持物、動作階段 |
| 換地點、時間跳躍、蒙太奇 | 關 | 敘事關係及需要保留的 canon |
| 畫面硬切，但旁白／環境聲／音樂要延續 | 不應為聲音而硬鎖畫面 | 分開處理聲音參考或剪接音軌 |

依硬鎖前綴的机制推論，要求立即硬切卻沿用前一構圖，可能造成換鏡延遲、意外推拉／變形或新構圖受牽制。文字寫「cut」不能視為解除 sampler 引導的保證。

若混合連續延長與切鏡，可以保留總開關，再逐段決定是否引用上一段。若全片段落邊界都屬硬切，總開關可以關閉。關閉接續不等於停用 Scene 公共參數或 Ref2VA 參考图。關掉進入 B 的引用，也不代表禁止後續 C 再從 B 接續。

## 實際 production：The Smallest Fix

只讀 API：`GET /api/projects/91b816c3ac9549a2`。

| 邊界 | production 的切鏡設計 | 建議 |
| --- | --- | --- |
| shot_01 → shot_02 | Straight cut to a tighter view on the same side of the bench axis. | shot_02 關閉引用上段 |
| shot_02 → shot_03 | Straight cut back to the original wider composition, retaining the new amber illumination. | shot_03 關閉引用上段 |

保持 Ada／Pip／工房／燈的共用參考。Shot 2 開始時燈仍關閉；Shot 3 開始時燈已亮，琥珀照明要延續。這些狀態應保留在各 Shot 的開場指令和審查中。

Studio API 當前卻輸出 shot_02、shot_03 `guidance.enabled=true`、`continuityFromPrev=true`、22 幀。`studio/delivery.py` 預設所有有前段的 Shot 引用上段；`studio/engine.py` 的提示亦要求預期使用者開啟接續。這是已確認的預設策略問題，尚未在本研究中修改或部署。Studio 的 handoff 不會自動修改 ComfyUI，所以不能據此推斷正在執行的第二／第三組開關。

## 後續產品方向（建議，尚未實作）

由 Astra 判斷每個 Shot 邊界是「連續延長」還是「切鏡」，並記錄原因。只有前者自動建議 Motion Context；切鏡保留 canon／狀態，但不預設引用上一段 AV。聲音是否跨切鏡延續應有獨立的創作決策，不能用視覺接續開關代替。不要把同場景、相同人物或幀數較少等同連續延長，也不要只靠英文關鍵字推斷全部電影語法。

## 來源

- [實際使用的 AIMixer Director 上游說明](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director#功能介绍)
- [H3 官方 Ref2VA 提示詞指南](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/ref-en.txt)：參考角色與影片延續的區別、段內多 Shot、聲音跨切鏡。
- [H3 官方案例](https://github.com/MiniMax-AI/MiniMax-H3)：T2VA 示例在 4.5 秒由中遠景切到臉部特寫。
- [Motion Context 原始專案](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context)：用作機制背景，並非本機 Director 所有細節的替代證據。
