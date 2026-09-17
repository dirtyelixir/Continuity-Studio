# Scene 公共參數與 Shot 道具

Scene 公共參數保留共用人物、場景身份與場景光線。道具圖片、外觀定義和持物／動作安排放在實際使用的 Shot。

在 H3 / Ref2VA 頁面，先把共用圖片放到公共參數，再到各 Shot 把本鏡道具放入該素材組標示的 Picture 槽位；不要覆蓋共用槽位。若重用同一個素材組，清掉上一鏡不再使用的道具圖片。完整複製該 Shot 提示詞，包含 summary 前的本鏡道具定義。

Scene 02 的例子：五公升膠水樽、昌叔兩個膠桶、長身螺絲批不再列入公共圖片或公共主體定義。「折返」的 canonical Shot 沒有膠桶，故不附膠桶參考；其他有列入膠桶的 Shot 照常使用同一張原圖。此改動不改劇本、持物安排、既有圖片或配音。

匯出每個 Shot 的 references-and-guidance.json 同時提供完整 references、本鏡 local_references 和本鏡 missing_references。完整六段提示詞由 Scene global.txt 加該 Shot shot.txt 組成；道具定義延續唯一的 subject_definitions 區塊，沒有第二個全域設定。

驗證包含：本鏡道具隔離、不同 Shot 圖片編號解析、缺圖只影響相關 Shot、公共參數不得定義本鏡道具、構圖圖片與道具槽位不衝突、每鏡九張上限、匯出圖片與提示詞對應、原有手動文字保留並標示舊全域道具問題。部署前完整 Python suite 210 passed，另補手動文字保護案例後六項 focused tests passed。

已安全部署並在真實瀏覽器驗證 Scene 02 公共參數、Shot 02 三件道具、Shot 05 兩件道具與編號、複製成功狀態及排版。API／ZIP 相符，三個作品、22 筆圖片及 12 份原始試音不變。證據：data/acceptance/shot-references/。Qwen 未完成所派介面工作，由主代理補完並驗證。
