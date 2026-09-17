> 2026-09-13 更新：分鏡畫面與 H3 生成次數已拆開。多個有序 edit uses 可以成為一個 native multi-shot 生成分組；詳見 [GENERATION_GROUPS.md](GENERATION_GROUPS.md)。下文的「單一來源 writer」只適用於原有逐鏡模式。

# 自動分鏡中的 Visual Skills 與 montage

Studio 的新故事、分鏡及章節方案會在決定來源鏡頭前規劃觀眾的觀看次序：場面關係、細節證據、人物反應、揭示與停頓。每次切到另一個機位，建立相應 Shot 及關鍵幀，再以 edit_plan 排列實際預定取用時段。連續鏡頭仍可用於有具體戲劇理由的段落；節省生成張數不是把不相容畫面塞在同一鏡的理由。

## 接入位置

Studio-owned production-method bundle v1.4.0 的 narrative、storyboard、qc、directing_qc 路由會載入完整的固定版本 visual-skills `Dramaturgy, detail, montage` 原文，接著載入 `references/montage.md` 的 Studio 適配。原文、LICENSE、NOTICE、來源 commit 與 SHA-256 都保存在 bundle，並由既有完整性檢查及工作快照保存。匯出用 skill-packages 內的方法副本同步更新；不依賴外置 skill 或網路檔案。

章節的正常請求與縮小上下文請求都保存同一方法。chapter_scene／舊 chapter_outline 在 shot briefs 凍結前決定畫面 succession；chapter_shots 完成各來源的具體機位、動作與關鍵幀；chapter_edit／chapter_edit_order 決定取用及節奏。已凍結的最後剪接階段不能憑空補一個沒有來源的特寫。

沿用現有欄位：beat.intent.coverage_strategy 記錄所選畫面次序及切／留理由，Shot.direction 記錄承載內容、可讀性與切點關係，Production.edit_plan 記錄有序的來源引用及取用時段。沒有第二套正式分鏡資料庫。既有 40 來源鏡頭範圍限制仍在；遇到不夠用的範圍應明示需要修訂，不得以隱藏切鏡或刪除原文應付。

## 品質要求

特寫必須能看清真正證據，反應要有接收刺激及評估的表演時間，揭示次序與切點的手／物件／視線狀態要成立。依內容使用短鏡、停頓與長段，生成素材的 4–15 秒限制不是成片每鏡的最低長度。可重用同來源的不同時段，但不能假裝它包含另一個未生成機位，也不能重播不可逆動作。

獨立 directing_qc 檢查實際 edit_plan，會對藏在單一來源內的不相容機位、不可讀的细節／反應、被剪掉的必要表演、無依據的節奏與提前揭示提出具體修訂。原作對白、說話者與無聲口形保留。聲音橋需有對應聲音時間安排；沒有獨立音軌時不能剪掉說話內容後宣稱 J/L-cut 已完成。

不使用鏡頭數、特寫數、固定節拍梯度或「有 montage 字眼」作為通過標準。上游的數值權重、三細節及五錨點配方屬可選參考。文字審查仍不能證明生成影片的表演與成片品質。

## 介面與現有作品

「故事與章節 → 劇情表達與剪接安排」及候選方案的每場戲先展示「畫面如何接起來」：依保存次序列出來源鏡頭、景別、停留時間及觀眾要看見的內容；切點理由與連續性可展開查看。重用同來源會各自顯示不同時段，不按來源列表的順序猜測剪接。

一個來源 Shot 通常仍只有一張起始幀；多個來源鏡頭接在一起才構成多鏡段落。圖片與 H3 writer 執行已採用的單一來源，不收到上游 montage 切鏡指令。

原有正式方案、素材、工作紀錄及採用狀態保留。建立或修訂方案才套用新方法；不會自動改寫舊故事。新方法 hash 使舊導演審查不再代表目前方法的審查，原結果仍作歷史保留。審查保存使用工作啟動時凍結的 method hash，避免舊工作在方法更新後完成時被誤標為已按新方法審查。

## 來源

Serge Shima，Visual Skills，CC BY 4.0。原作：https://github.com/smixs/visual-skills ，固定 commit `ae26d624edd747e719fa21528d18d39e68c04a0e`。作者：https://sergeshima.com / https://aimasters.me / https://t.me/aimastersme 。原文未改寫，Studio 適配另存。接入的是此處列明的戲劇／montage 章節，沒有宣稱移植整套上游工具與工作流程。

验收證據：`data/acceptance/montage-integration-20260913/`。方法／資料關係測試、實際文字生成和視覺成片驗收各自記錄，不混作同一品質結論。
