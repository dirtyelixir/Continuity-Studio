/**
 * visual-style.js — 自包含的視覺風格選擇器（Visual Style Picker）。
 *
 * 由父模組（parent）導入本模組與 visual-style.css 使用：
 *   import {renderVisualStylePicker, readVisualStyle} from './visual-style.js';
 *
 * 本模組不依賴任何外部資源（無圖片、無 icon 字型、無第三方函式庫），
 * 也不修改 DOM（renderVisualStylePicker 只回傳 HTML 字串）。
 */

/* 預設的八個視覺方向。描述的是「媒介／風格」，不是故事類型（genre）。 */
const PRESETS = [
  {value: 'realistic_cinema',   label: '寫實電影',   note: '自然膚色、真實攝影與光線'},
  {value: 'animation_2d',       label: '2D 動畫',    note: '清晰線稿與賽璐璐上色'},
  {value: 'animation_3d',       label: '3D 動畫',    note: '風格化 3D 圓潤造型'},
  {value: 'stop_motion',        label: '定格動畫',   note: '可觸感的微縮黏土與布料'},
  {value: 'watercolor',         label: '水彩繪本',   note: '紙張水彩、柔和邊緣'},
  {value: 'black_white_comic',  label: '黑白漫畫',   note: '高對比墨線與網點'},
  {value: 'auto',               label: '交由 創作引擎 建議', note: '由 創作引擎 依故事內容決定風格'},
  {value: 'custom',             label: '自訂方向',   note: '在下方自行描述視覺方向'},
];

/* 畫幅比例選項（順序即顯示順序）。 */
const ASPECTS = ['16:9', '9:16', '1:1', '2.39:1'];

/* 自訂方向的文字上限（字元數）。 */
const NOTES_LIMIT = 2400;

/* 把 HTML 特殊字元轉義，避免任何動態值注入時破壞結構。 */
const esc = value => String(value ?? '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');

/**
 * 回傳視覺風格選擇器的可存取的 HTML 字串。
 *
 * 包含一個 <fieldset>，內有：
 *  - 名稱為 visual_preset 的 8 個 radio（auto 預設 selected），
 *    以 grid 卡片呈現；選中狀態透過 CSS :has() 顯示（見 visual-style.css）。
 *  - 名稱為 aspect_ratio 的 select，選項為 16:9、9:16、1:1、2.39:1。
 *  - 名稱為 style_notes 的 textarea（maxLength 2400），供自訂方向使用。
 *
 * @returns {string} 可直接嵌入 <form> 的 HTML 字串。
 */
export function renderVisualStylePicker() {
  const radios = PRESETS.map(p => `
      <label class="visual-style-card${p.value === 'auto' ? ' is-default' : ''}">
        <input type="radio" name="visual_preset" value="${esc(p.value)}"${p.value === 'auto' ? ' checked' : ''}>
        <span class="visual-style-card__title">${esc(p.label)}</span>
        <span class="visual-style-card__note">${esc(p.note)}</span>
      </label>`).join('');

  const options = ASPECTS.map(a => `        <option value="${esc(a)}">${esc(a)}</option>`).join('\n');

  return `
  <fieldset class="visual-style-picker" id="visual-style-picker">
    <legend class="visual-style-picker__legend">視覺風格</legend>
    <p class="visual-style-picker__hint">選擇影像的媒介風格（非故事類型）；選「自訂方向」時請在下方描述。</p>
    <div class="visual-style-picker__cards" role="radiogroup" aria-label="視覺風格">
${radios}
    </div>
    <div class="visual-style-picker__fields">
      <label class="visual-style-picker__field">
        <span class="visual-style-picker__label">畫幅比例</span>
        <select name="aspect_ratio">
${options}
        </select>
      </label>
      <label class="visual-style-picker__field visual-style-picker__notes-field">
        <span class="visual-style-picker__label">補充說明（選填）</span>
        <textarea name="style_notes" rows="4" maxlength="${NOTES_LIMIT}" placeholder="若選「自訂方向」，請在此描述你想要的視覺風格（例如色彩、鏡頭感、材質）。"></textarea>
        <span class="visual-style-picker__count" id="visual-style-notes-count">最多 ${NOTES_LIMIT} 字</span>
      </label>
    </div>
  </fieldset>`;
}

/* 取表單中 name 對應的元素（相容 form.elements 與直接元素物件）。 */
function field(form, name) {
  const el = form?.elements?.[name];
  return el || (form?.[name] ?? null);
}

/* 取 visual_preset radio 中 selected 的值；找不到時回傳 null。 */
function checkedPreset(form) {
  const group = field(form, 'visual_preset');
  if (group && group.value !== undefined) {
    const v = group.value;
    return v === '' ? null : v;
  }
  if (form?.querySelector) {
    const el = form.querySelector('input[name="visual_preset"]:checked');
    return el ? el.value : null;
  }
  return null;
}

/**
 * 讀取表單中已選的視覺風格，回傳單一繁體中文風格字串。
 *
 * 字串包含：
 *  - 已選定的預設風格（寫實電影／2D 動畫／3D 動畫／定格動畫／水彩繪本／
 *    黑白漫畫／交由 創作引擎 建議／自訂方向）；
 *  - 畫幅比例（16:9、9:16、1:1、2.39:1）；
 *  - 自訂方向的補充說明（若自訂方向或任何附註存在）。
 *
 * 若選「自訂方向」但 style_notes 為空白（純空白），會拋出使用者可讀的
 * Error（中文訊息）。
 *
 * @param {object} form 表單物件（需有 elements 或 querySelector 可取
 *   visual_preset、aspect_ratio、style_notes）。
 * @returns {string} 單一繁體中文風格描述字串。
 * @throws {Error} 自訂方向但補充說明為空白時。
 */
export function readVisualStyle(form) {
  const presetValue = checkedPreset(form);
  const preset = PRESETS.find(p => p.value === presetValue) || null;
  const aspect = (field(form, 'aspect_ratio')?.value || '').trim() || '16:9';
  const notes = (field(form, 'style_notes')?.value || '').trim();

  let styleLine;
  if (!preset) {
    styleLine = '視覺方向待選定';
  } else if (preset.value === 'auto') {
    styleLine = '視覺方向交由 創作引擎 建議（依故事內容決定風格）';
  } else if (preset.value === 'custom') {
    if (!notes) {
      throw new Error('你選擇了「自訂方向」，但尚未在下方描述視覺風格——請補上補充說明，或改選其他方向。');
    }
    styleLine = `自訂方向：${notes}`;
  } else {
    styleLine = `視覺風格為「${preset.label}」（${preset.note}）`;
  }

  const parts = [styleLine, `畫幅比例 ${aspect}`];
  if (notes && preset?.value !== 'custom') parts.push(`補充說明：${notes}`);
  return parts.join('；');
}
