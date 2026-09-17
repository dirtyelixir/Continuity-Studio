# 關鍵幀超過五張參考圖

Scene 01 起始幀引用兩個人物、一個場景及四項道具，共七張已批准原圖。原本 Astra adapter 在啟動前以五張上限拒絕，對應失敗工作 c44b833cf36942ef。

實測確認上游 image_gen 的 recent-image selector 及 referenced_image_paths 都限制五張；本機的 path 讀取另有 bwrap 權限錯誤。因此最後方案使用原有可行的 conversation attachments 通道，不修改 sandbox 或 GPU 服務：

- 一至五張維持原流程。
- 超過五張，前四張保持獨立，餘下原圖按原始編號排成一張 transport board。
- 參考板逐張原尺寸貼入，另加編號邊框；不重畫、裁切或刪除原圖。
- 五個圖片輸入直接附到 Astra，使用 num_last_images_to_include=5。提示詞交代各 tile 對應的原始 Image 編號及角色，禁止把拼板／標籤帶入生成結果。
- reference-transport.json 保存原圖、矩形及送入清單。原始素材、dependency/reference IDs、H3 公共／Shot 圖片關係保持分開，參考板僅屬工作內部傳輸檔。

新分鏡規劃不再為此傳輸限制刪減必要人物／道具。歷史 frozen request 的 reference_limit 仍被尊重。大量圖片仍可能受供應商的尺寸或內容限制；七圖是本次真實驗收範圍。

測試：227 full-suite passed；最終附件傳輸調整後 24 focused tests passed。案例涵蓋 0/1/5/6/7 張、空白路徑、原始檔案順序／位元組、參考板逐像素相等、新規劃不設五實體限制。兩項既有套件 deprecation warnings。

真實驗收：最終工作 5cad19b25f7d4363 成功生成 1672×941 PNG，素材 ae41ccbe954d4ed9 已出現在 Shot 01 分鏡頁。HTTP 下載與原檔位元組一致，七個 canonical reference IDs 全部保留；22 張舊素材、三個作品、音色及試音不變。Astra 審查 8e7fe117e5684e83 已完成，提出「樂言改用左手提樽」「昌叔退回門內」兩項內容修訂；圖片保持 pending，沒有自動批准或再生成。傳輸錯誤已修復，內容審查與傳輸驗收分開記錄。

證據：data/acceptance/keyframe-reference-fix/verification.json。備份：data/backups/keyframe-reference-fix-20260909-013524/。
