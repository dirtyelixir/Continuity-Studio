/* Continuity Studio — Traditional Chinese (Hong Kong) locale layer.
 * displayLabel(key): machine labels (states, entities, capabilities, form fields,
 * standard provider names) -> 繁體中文. Unknown keys pass through unchanged.
 * displayError(text): known application validation errors -> translated with
 * variable detail preserved; unknown errors get a short operation-failed
 * introduction while keeping the original diagnostic.
 * Prompts, creative content, API identifiers, JSON keys, paths and provider
 * model IDs are deliberately NOT translated. */

const LABELS = {
  'storyboard_frames':'視覺圖板安排',
  'key':'中段關鍵幀',
  'voice': '聲音角色',
  'voice_defaults': '角色預設音色設計',
  'director_style': '導演風格推薦',
  'storyboard': '原文分鏡規劃',
  'h3_lora_advice': 'Style LoRA 推薦',
  'h3_group_plan': 'Storyboard 生成分組安排',
  'h3_strategy': '影片模式與關鍵幀藍圖',
  'h3_video_prompt': '首尾幀影片提示詞',
  'h3_global': '重新生成全域提示詞',
  'h3_shot': '重新生成分鏡提示詞',
  'h3_guidance': '分鏡接續判斷',
  'An approved reference was replaced.': '使用的已批准參考圖已被新版取代。',
  'An approved reference was rejected.': '使用的已批准參考圖已被拒絕。',
  // job / asset states and review verdicts
  approved: '已批准',
  pending: '待審查',
  rejected: '已拒絕',
  stale: '待更新',
  superseded: '已取代',
  queued: '排隊中',
  running: '處理中',
  succeeded: '已完成',
  failed: '已失敗',
  interrupted: '已中斷',
  awaiting_input: '待提交結果',
  cancelled: '已取消',
  pass: '通過',
  revise: '需修訂',
  uncertain: '不確定',
  unestablished: '尚未建立',
  planned: '已規劃',
  enabled: '已啟用',
  disabled: '已停用',
  composition: '構圖參考',
  // entity kinds
  character: '角色',
  crowd: '群眾演員',
  location: '場景',
  prop: '道具',
  frame: '關鍵幀',
  entity: '設定項目',
  // capabilities
  directing_qc:'導演內容審查',narrative: '故事與製作方案',
  image: '圖片生成',
  image_prepare: '圖片提示詞整理',
  image_review: '圖片審查',
  identity_from_image: '按圖片反推身份設定',
  h3: '首尾幀提示詞',
  h3_prepare: '整理英文分鏡提示詞',
  h3_scene: 'Ref2VA 場景提示詞',
  qc: '品質審查',
  direction: '導演指示',
  performance_notes: '表演指導',
  // form fields
  title: '標題',
  logline: '故事簡介',
  story: '故事',
  screenplay: '劇本',
  style: '畫風',
  framing: '景別',
  angle: '角度',
  camera: '運鏡',
  blocking: '走位',
  action: '動作',
  expression: '表情',
  start: '起始幀',
  end: '結束幀',
  // standard provider display names
  'Astra · Codex': 'Astra · Codex',
  'Human / manual': '人工處理',
};

const ERRORS = {
  'Provider timed out. Output retained in job directory; inspect before retry.': '服務商逾時，工作已停止。已保留請求及診斷日誌；這不代表已有完整結果，恢復前須先檢查。',
  'peer closed connection without sending complete message body (incomplete chunked read)': '服務商回應尚未接收完整，連線便被關閉。可能是服務商或中途網路設備中斷；此錯誤本身無法確定原因。分階段章節工作可按「接續未完成階段」重試。',
  'Provider timed out after 20 minutes. A result file was retained; validate it before recovery.': '服務商超過 20 分鐘仍未完成，工作已停止。已保留結果檔，可嘗試「恢復已保存結果」；系統仍須驗證內容是否完整有效。',
  'Provider timed out after 20 minutes. No structured result was saved; only the request and diagnostic logs were retained.': '服務商超過 20 分鐘仍未完成，工作已停止。只保留了請求及診斷日誌，沒有可恢復的完整結果。若已有重試工作正在執行，請先等待該工作。',
  // app.py — revisions and proposals
  'Revision not found': '找不到該版本。',
  'Only a completed narrative proposal can be adopted': '只有已完成的製作方案可以採用。',
  'Proposal was created from an earlier revision. Develop a revised proposal to avoid overwriting newer decisions.': '此提案建基於較早的版本。請基於最新版本重新發展，以免覆蓋較新的決定。',
  // app.py — job lifecycle
  'Only queued or manual jobs can be cancelled before execution': '只有排隊中或待提交結果的工作可以在執行前取消。',
  'Only failed or interrupted jobs can be recovered': '只有已失敗或已中斷的工作可以恢復。',
  'No saved provider result exists. Retry is needed.': '沒有已儲存的服務商結果，請重新執行。',
  'Job was already recovered': '該工作已經被恢復。',
  'Job is not awaiting manual output': '該工作目前不是等待手動輸入。',
  'Use image upload for manual image jobs': '手動圖片任務請改用「匯入圖片」。',
  // app.py — assets and import
  'Image not found': '找不到該圖片。',
  'Invalid image path': '圖片路徑無效。',
  'Original image file is missing': '原始圖片檔案不存在。',
  'Adopt a plan before importing a reference': '請先採用製作計劃，再匯入參考。',
  'Approve canonical references before importing a frame': '請先批准正式參考圖，再匯入關鍵幀。',
  'Maximum upload is 40MB': '上傳檔案最大 40MB。',
  'Could not import image: ': '無法匯入圖片：',
  // app.py — providers and routing
  'Built-in providers are protected': '內建服務商受保護，不可修改。',
  'Custom providers currently use the HTTP adapter': '自訂服務商目前使用 HTTP 介接工具。',
  'Use an HTTP(S) base URL without embedded credentials': '請使用不含帳密資訊的 HTTP(S) 基礎位址。',
  'Use an environment variable name, not a key value': '請填寫環境變數名稱，而不是金鑰值。',
  'Provider does not support capability': '該服務商不支援此功能。',
  // app.py — export
  'Adopt a production plan before exporting': '請先採用製作計劃再匯出。',
  // engine.py — plan save
  'Project not found': '找不到該作品。',
  'Project changed. Reload before saving; your older result is retained.': '作品已改變，請重新載入後再儲存；較舊的結果已保留。',
  // engine.py — job build
  'Develop and adopt a production plan first': '請先發展並採用製作計劃。',
  'Approve canonical references before rendering this frame: ': '生成此關鍵幀前請先批准正式參考圖：',
  'Edit source must belong to this project and visual target': '編輯來源必須屬於此作品及同一視覺目標。',
  'Asset not found': '找不到該素材。',
  'Adopt a production plan first': '請先採用製作計劃。',
  'Scene not found': '找不到該場景。',
  'Approve required Scene/Shot references first: ': '請先批准 Scene／Shot 所需參考圖：',
  'Approve this Shot references: ': '本 Shot 尚欠道具參考圖：',
  'Scene and Shot definitions must identify every attached reference before summary': 'Scene 與 Shot 的定義須在 summary 前識別所有參考圖片。',
  'Approve scene references first: ': '請先批准場景參考：',
  'Too many Ref2VA image references; maximum nine per chapter': 'Ref2VA 圖片參考過多；每個鏡頭最多九張。',
  'Shot not found': '找不到該鏡頭。',
  'Enable a skill that supplies this capability first': '請先啟用提供此功能的技能。',
  // engine.py — image results
  'Image provider returned no rendered file': '圖片服務商沒有傳回生成檔案。',
  'Provider output must be inside this job or Codex generated-image storage': '服務商輸出必須位於此工作或 Codex 生成圖片儲存目錄內。',
  'Missing or oversized image output': '圖片輸出缺失或過大。',
  'Rendered output is too small': '生成輸出太小。',
  'Source shot no longer exists': '來源鏡頭已不存在。',
  // engine.py — approval (decide_asset)
  'This image was made from older canon. Regenerate against current production.': '此圖片基於舊版角色與場景設定製作，請按目前製作重新生成。',
  'Character reference must pass the four-view sheet review before approval. Generate or import front close-up, left profile, right profile and rear full-body views in one sheet, then review it.': '角色參考必須先通過四視圖審查才能批准。請在一張圖片內生成或匯入正面面部近鏡、左側面、右側面及背面全身四格，然後審查。',
  'An input reference is no longer approved/current. Regenerate this candidate.': '其中一個輸入參考已不再是已批准的現行版本，請重新生成此候選。',
  'Astra flagged issues. Add an override note to approve, or request a revision.': 'Astra 指出需要修正的地方。請填寫 批准理由後批准，或要求修改。',
  // engine.py / providers — provider issues
  'Selected provider does not support this capability': '所選服務商不支援此功能。',
  'This Astra image adapter supports up to five reference images per job. Configure an image API for larger casts.': '此 Astra 圖片介接工具每項工作最多支援五張參考圖片；陣容較大時請設定圖片 API。',
  'HTTP provider needs a base URL': 'HTTP 服務商需要 API 基礎位址。',
  'Manual provider awaits submitted output': '手動服務商等待提交的結果。',
  // folders.py — snapshot and file manager
  'Invalid project': '作品 ID 無效。',
  'Folder cannot be a symbolic link': '資料夾不能是符號連結。',
  'Invalid snapshot': '快照 ID 無效。',
  'Invalid file path': '檔案路徑無效。',
  'Symbolic links are not served': '符號連結不會被服務。',
  'File not found': '找不到檔案。',
  'Snapshot cannot be a symbolic link': '快照資料夾不能是符號連結。',
  'Invalid package path': '套件內路徑無效。',
  'File manager opener unavailable. Copy the folder path instead.': '檔案管理員打不開，請直接複製資料夾路徑。',
  'Could not confirm the file manager opened. Copy the folder path instead.': '無法確認檔案管理員已開啟，請直接複製資料夾路徑。',
  'File manager could not open this folder. Copy the folder path instead.': '檔案管理員無法開啟此資料夾，請直接複製資料夾路徑。',
  'File selection service unavailable. Original image: ': '檔案選取服務不可用。原始圖片：',
  'Could not reveal the original image: ': '無法顯示原始圖片：',
  'File manager could not select the original image: ': '檔案管理員無法選取原始圖片：',
  // delivery.py — Ref2VA validation
  'Direction changed. Reload before saving.': '方向已改變，請重新載入後再儲存。',
  'Choose 5, 22, 39 or 56 context frames': '參考影格數請選擇 5、22、39 或 56。',
  'Unknown scene': '未知場景。',
  'Chapter must belong to this scene': '鏡頭必須屬於此場景。',
  'Global prompt exceeds 7000 characters': '全域提示詞超過 7000 個字元。',
  'Invalid storyboard reference choice': '分鏡參考選擇無效。',
  'Prompt exceeds 7000 characters': '提示詞超過 7000 個字元。',
  'Ref2VA requires all six sections exactly once in order': 'Ref2VA 需要六個欄位按順序各出現一次。',
  'Ref2VA summary must begin with [reference generation]': 'Ref2VA 的 summary 必須以 [reference generation] 開頭。',
  'Prompt contains an unresolved reference label': '提示詞含有未解析的參考標籤。',
  'No video/audio reference asset is attached; motion guidance is a separate setting': '未附上影片/聲音參考素材；段間引導是另一個設定。',
  'Global definitions must identify every attached reference': '全域定義必須識別所有附上的參考。',
  'Combined prompt exceeds the director UI limit of approximately 7000 characters': '合併提示詞超過導演介面約 7000 個字元的限制。',
  'Prompt omitted or changed canonical dialogue': '提示詞遺漏或改動了已確認對白。',
  'Scene result must include every chapter exactly once': '場景結果必須包含每個鏡頭，且各出現一次。',
  // h3.py
  'H3 output must retain the three required fields in order': 'H3 輸出必須按順序保留三個必填欄位。',
  'H3 output changed the required frame-alignment instruction': 'H3 輸出改動了必填的幀對齊指引。',
  'H3 output contains an unresolved reference label': 'H3 輸出含有未解析的參考標籤。',
  'H3 output changed or omitted canonical dialogue': 'H3 輸出改動或遺漏了已確認對白。',
  // asset_library.py
  'Asset library path escapes storage': '素材庫路徑超出了儲存範圍。',
  'Image verification failed': '圖片驗證失敗。',
  // continuity.py / store.py / models.py
  'Unknown visual target': '未知視覺目標。',
  'Job not found': '找不到該工作。',
  'All entity, scene, shot and frame IDs must be unique': '角色、場景、鏡頭及關鍵幀的識別碼不可重複。',
  'Scene must link a canonical location': '場景必須連結正式場景設定。',
  'Unknown shot entity': '未知鏡頭設定項目。',
  'Duplicate shot entity': '鏡頭設定項目重複。',
  'State entity must belong to shot': '狀態設定項目必須屬於此鏡頭。',
  'Duplicate state key': '狀態欄位重複。',
  'Timing must fit within shot duration': '時間必須在鏡頭時長範圍內。',
  'Dialogue must link a character in the shot': '對白必須連結鏡頭內的角色。',
  'Only one keyframe per moment': '每個起始或結束時刻只能有一張關鍵幀。',
};

export function displayLabel(key) {
  if (key === null || key === undefined) return key;
  const s = String(key).trim();
  if (s === '') return key;
  return Object.prototype.hasOwnProperty.call(LABELS, s) ? LABELS[s] : key;
}

export function displayError(text) {
  if (text === null || text === undefined) return text;
  const original = String(text);
  const t = original.trim();
  if (t === '') return text;
  const hit = ERRORS[t];
  if (hit !== undefined) return hit;
  for (const [prefix, zh] of Object.entries(ERRORS)) {
    if (zh.endsWith('：') && t.startsWith(prefix)) {
      return zh + original.trimStart().slice(prefix.length);
    }
  }
  return '操作失敗：' + original;
}
