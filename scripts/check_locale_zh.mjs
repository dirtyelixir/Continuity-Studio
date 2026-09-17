#!/usr/bin/env node
/* Executable checks for static/locale-zh.js. Run: node scripts/check_locale_zh.mjs */
import { displayLabel, displayError } from '../static/locale-zh.js';
import assert from 'node:assert/strict';

let passed = 0;
function check(name, actual, expected) {
  assert.equal(actual, expected, `${name}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  passed += 1;
}

// --- labels: all specified keys translate to Traditional Chinese ---
const labelCases = {
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
  character: '角色',
  location: '場景',
  prop: '道具',
  frame: '關鍵幀',
  entity: '設定項目',
  narrative: '故事與製作方案',
  image: '圖片生成',
  image_review: '圖片審查',
  h3: '首尾幀提示詞',
  h3_scene: 'Ref2VA 場景提示詞',
  qc: '品質審查',
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
  'Astra · Codex': 'Astra · Codex',
  'Human / manual': '人工處理',
};
for (const [key, zh] of Object.entries(labelCases)) {
  check(`displayLabel(${JSON.stringify(key)})`, displayLabel(key), zh);
}

// --- unknown labels pass through unchanged ---
check('unknown label unchanged', displayLabel('some-unknown-state'), 'some-unknown-state');
check('provider model ID unchanged', displayLabel('gpt-6-astra'), 'gpt-6-astra');
check('capability-like unknown unchanged', displayLabel('video_generation'), 'video_generation');
check('creative content unchanged', displayLabel('The robot hums a tune.'), 'The robot hums a tune.');
check('label input with whitespace still matches', displayLabel('  running '), '處理中');
check('empty label safe', displayLabel(''), '');
check('null label safe', displayLabel(null), null);

// --- known errors translate, keeping variable detail ---
check('four-view error',
  displayError('Character reference must pass the four-view sheet review before approval. Generate or import front close-up, left profile, right profile and rear full-body views in one sheet, then review it.'),
  '角色參考必須先通過四視圖審查才能批准。請在一張圖片內生成或匯入正面面部近鏡、左側面、右側面及背面全身四格，然後審查。');
check('approval: older canon',
  displayError('This image was made from older canon. Regenerate against current production.'),
  '此圖片基於舊版角色與場景設定製作，請按目前製作重新生成。');
check('approval: flagged issues',
  displayError('Astra flagged issues. Add an override note to approve, or request a revision.'),
  'Astra 指出需要修正的地方。請填寫 批准理由後批准，或要求修改。');
check('revision conflict',
  displayError('Project changed. Reload before saving; your older result is retained.'),
  '作品已改變，請重新載入後再儲存；較舊的結果已保留。');
check('revision not found',
  displayError('Revision not found'), '找不到該版本。');
check('adopt proposal gate',
  displayError('Only a completed narrative proposal can be adopted'),
  '只有已完成的製作方案可以採用。');
check('adopt stale revision',
  displayError('Proposal was created from an earlier revision. Develop a revised proposal to avoid overwriting newer decisions.'),
  '此提案建基於較早的版本。請基於最新版本重新發展，以免覆蓋較新的決定。');

// --- representative errors from the five inspected modules ---
check('folders: file manager unavailable',
  displayError('File manager opener unavailable. Copy the folder path instead.'),
  '檔案管理員打不開，請直接複製資料夾路徑。');
check('folders: cannot open folder',
  displayError('File manager could not open this folder. Copy the folder path instead.'),
  '檔案管理員無法開啟此資料夾，請直接複製資料夾路徑。');
check('folders: reveal with path suffix',
  displayError('Could not reveal the original image: /home/u/data/assets/char-1.png'),
  '無法顯示原始圖片：/home/u/data/assets/char-1.png');
check('app: upload too large',
  displayError('Maximum upload is 40MB'), '上傳檔案最大 40MB。');
check('app: import failure with nested diagnostic',
  displayError('Could not import image: Provider output must be inside this job or Codex generated-image storage'),
  '無法匯入圖片：Provider output must be inside this job or Codex generated-image storage');
check('engine: approve frame refs with missing list',
  displayError('Approve canonical references before rendering this frame: Ada, 機房走廊'),
  '生成此關鍵幀前請先批准正式參考圖：Ada, 機房走廊');
check('engine: scene refs with missing list',
  displayError('Approve scene references first: Ada'),
  '請先批准場景參考：Ada');
check('delivery: prompt too long',
  displayError('Prompt exceeds 7000 characters'), '提示詞超過 7000 個字元。');
check('delivery: Ref2VA sections',
  displayError('Ref2VA requires all six sections exactly once in order'),
  'Ref2VA 需要六個欄位按順序各出現一次。');
check('h3: fields order',
  displayError('H3 output must retain the three required fields in order'),
  'H3 輸出必須按順序保留三個必填欄位。');
check('models: timing',
  displayError('Timing must fit within shot duration'), '時間必須在鏡頭時長範圍內。');
check('asset_library: verification',
  displayError('Image verification failed'), '圖片驗證失敗。');
check('continuity: unknown target',
  displayError('Unknown visual target'), '未知視覺目標。');
check('store: job not found',
  displayError('Job not found'), '找不到該工作。');
check('providers: capability',
  displayError('Selected provider does not support this capability'),
  '所選服務商不支援此功能。');

// --- unknown errors: operation-failed introduction + original diagnostic preserved ---
check('unknown error keeps original',
  displayError('Boom: /tmp/worker segfaulted (code 139)'),
  '操作失敗：Boom: /tmp/worker segfaulted (code 139)');
check('unknown error, JSON-ish diagnostic',
  displayError('ValidationError: chapters: field required'),
  '操作失敗：ValidationError: chapters: field required');
check('unknown error with path',
  displayError('Permission denied: data/jobs/abc/result.json'),
  '操作失敗：Permission denied: data/jobs/abc/result.json');
check('empty error safe', displayError(''), '');
check('null error safe', displayError(null), null);
check('whitespace error safe', displayError('   '), '   ');

// --- path / target suffixes are preserved (not translated) ---
check('reveal path suffix',
  displayError('File selection service unavailable. Original image: data/productions/p1/2a3b4c5d/ref.png'),
  '檔案選取服務不可用。原始圖片：data/productions/p1/2a3b4c5d/ref.png');
check('select original image path suffix',
  displayError('File manager could not select the original image: /home/u/data/assets/prop-9.png'),
  '檔案管理員無法選取原始圖片：/home/u/data/assets/prop-9.png');
check('frame target list suffix',
  displayError('Approve canonical references before rendering this frame: frame_shot1_start, Ada'),
  '生成此關鍵幀前請先批准正式參考圖：frame_shot1_start, Ada');
check('import image nested diagnostic suffix',
  displayError('Could not import image: Asset not found'),
  '無法匯入圖片：Asset not found');


check('double spaces in original path remain intact', displayError('Could not reveal the original image: /tmp/My  Reference.png'), '無法顯示原始圖片：/tmp/My  Reference.png');
check('new enable state', displayLabel('enabled'), '已啟用');
check('new disable state', displayLabel('disabled'), '已停用');

console.log(`locale-zh checks passed: ${passed}`);
