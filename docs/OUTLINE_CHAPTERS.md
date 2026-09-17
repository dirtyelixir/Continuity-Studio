# 故事大綱與持續章節創作

建立作品預設選「故事大綱」，輸入整體背景、主角、衝突及長線走向。選視覺風格、畫幅及補充說明後保存；可選擇先讓 Astra 推薦導演方法。

在製作手冊新增章節，選本章大綱、已有劇情或完整劇本，保存後按「建立本章方案」。方案完成後先審閱採用，再使用角色、場景、分鏡與 H3 流程。下次可續加章節，或修訂指定章節。每章可使用已有共用角色與場景參考。

整體故事大綱與本章原文各自保存。大綱或章節修改後，舊輸入產生的方案不能覆蓋新內容；原方案仍在工作記錄。修改大綱不會自動改寫已採用章節。

視覺方向選項：寫實電影、2D 動畫、3D 動畫、定格動畫、水彩繪本、黑白漫畫、交由 Astra 建議、自訂。畫幅：16:9、9:16、1:1、2.39:1。選定文字會保存並進入實際生成請求。導演方法是另一個全作品選擇，供各章分鏡運用。

## Acceptance

Final checks: 162 Python tests passed (two existing upstream deprecation warnings); 85 locale checks, JavaScript syntax, Director UI regression and diff checks passed.

- Browser: outline-default dialog, 8 accessible radio choices, 2D/9:16/notes persisted; chapter 1 and 2 created through UI and both survived reload. Storage isolated at /tmp/continuity-outline-ui-20260908.
- Regression: independent chapter adoption and revision; unchanged other-chapter shots; canonical reference and original-frame dependency hashes retained on append; rejection of changed canon and stale sources; exact imported chapter screenplay; immutable revision restore; original outline and chapter writing in ZIP.
- Aggregate 42-shot story verified as two 21-shot chapters.
- Live service restart: no running/queued jobs, online backup made first. Existing project title/idea/style/revision/production and asset ID/target/path/status/reference/prompt records unchanged; SQLite integrity ok.
- No image/video generation performed. Synthetic production fixtures exist only in temporary test storage. Existing live works were not converted or rewritten.

## Limits

20,000 characters per outline/chapter input, 40 shots per chapter proposal. Ongoing chapter count is not restricted by a 40-shot whole-story limit. Very long serial works still pass prior adopted writing to the text provider and may eventually encounter its context limit; hierarchical story summaries are not implemented. Chapter input supports pasted text; the main outline/legacy import form retains TXT/Markdown/DOCX preview. Visual presets are text choices, not generated preview images.
