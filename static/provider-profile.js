export function supportsProvider(provider, capability) {
  return !((provider.kind === 'deepseek' || provider.id === 'local_qwen') && capability === 'image') && (provider.capabilities.includes(capability) || provider.capabilities.includes('*'));
}

export function profileLabel(settings) {
  const mode = settings?.profile?.mode || 'astra';
  return mode === 'custom' ? '自訂服務商組合' : `Powered by ${mode === 'local_qwen' ? 'Qwen3.8' : mode === 'deepseek' ? 'DeepSeek' : 'Astra'}`;
}

export function renderProviderProfile(settings, esc) {
  const p = settings.profile || {mode:'astra', deepseek:{model:'deepseek-flash', vision_model:'deepseek-flash', key_env:'DEEPSEEK_API_KEY'}};
  const d = p.deepseek;
  const renderers = settings.providers.filter(x => ['codex','http','manual','comfy'].includes(x.kind) && (p.mode!=='deepseek'||x.kind!=='codex') && supportsProvider(x,'image'));
  const image = renderers.some(x => x.id === p.image_provider) ? p.image_provider : 'astra';
  return `<section class="panel provider-profile"><div class="panel-header"><div><div class="eyebrow">創作引擎</div><h2>${esc(profileLabel(settings))}</h2></div></div>
  <p>一次切換故事、劇本、分鏡、導演建議、提示詞、連戲與品質審查。套用至所有作品的新工作；既有內容與進行中的工作保留原服務商記錄。</p>
  ${settings.production_methods?.mandatory?`<p class="notice" data-production-method="${esc(settings.production_methods.version)}"><strong>Studio 既定製作方法 · 已強制套用</strong><br>故事、分鏡、圖片及 H3 沿用同一套製作規格，切換模型仍會載入。圖片的要求、規格與參考圖完全相同時，沿用已保存的提示詞；改動內容才重新整理。生成結果仍須審閱。</p>`:''}
  <form id="provider-profile-form"><label>整體模式<select name="mode" id="creative-provider-mode">
    ${p.mode==='custom'?'<option value="custom" selected disabled>自訂服務商組合（逐項設定）</option>':''}
    <option value="astra" ${p.mode==='astra'?'selected':''}>Powered by Astra</option>
    <option value="deepseek" ${p.mode==='deepseek'?'selected':''}>Powered by DeepSeek</option>
    <option value="local_qwen" ${p.mode==='local_qwen'?'selected':''}>Powered by Qwen3.8</option>
  </select></label>
  <div id="qwen-profile-options" ${p.mode!=='local_qwen'?'hidden':''}>
    <p class="notice">由本機 Qwen3.8 處理文字創作、圖片理解與審查，沿用 Studio 製作方法與上下文設定。圖片生成請在下方獨立選擇。</p>
    <p class="muted">模型：qwen3.8-27b · 經 VRAM Manager 執行。資源忙碌或生成失敗時會顯示原因，可稍後重試；不會自動切換至其他創作引擎。</p>
    <button type="button" data-action="check-qwen" class="small">檢查本機 Qwen3.8 連線</button><p id="qwen-connection-result" role="status"></p>
  </div>
  <div id="deepseek-profile-options" ${p.mode!=='deepseek'?'hidden':''}>
    <div class="form-grid"><label>文字與創作模型<select name="model"><option value="deepseek-flash" ${d.model==='deepseek-flash'?'selected':''}>DeepSeek V4.1 Flash（帳戶可用）</option><option value="deepseek-v4-pro" ${d.model==='deepseek-v4-pro'?'selected':''}>DeepSeek V4 Pro（舊版）</option></select></label>
    <label>圖片理解與審查模型<select name="vision_model"><option value="deepseek-flash">DeepSeek V4.1 Flash（文字＋Vision）</option></select></label>
    <label class="full">DeepSeek API Key（直接貼上）<input name="api_key" type="password" placeholder="留空則保留現有 Key" autocomplete="new-password" spellcheck="false"></label><input type="hidden" name="key_env" value="${esc(d.key_env||'DEEPSEEK_API_KEY')}">
    </div>
    <p class="notice">DeepSeek 模式的創作與視覺審查均由 DeepSeek 處理，不會回退至 Astra。DeepSeek 不提供圖片生成；請另選本機 ComfyUI、圖片 API，或使用人工匯入。可在下方新增圖片 API 服務商。</p>
    <p class="muted">API 位址：https://api.deepseek.com。${d.credential_configured?'本機 Key 已設定（尚需檢查連線）':'尚未設定 Key'}。Key 只保存於本機權限受限檔案，不會保存於作品、SQLite 工作記錄或瀏覽器；環境變數方式仍然支援。</p>
    <button type="button" data-action="check-deepseek" class="small">檢查已儲存的 DeepSeek 連線</button><p id="deepseek-connection-result" role="status"></p>
  </div>
  <label>圖片實際生成（獨立選擇）<select name="image_provider">${renderers.map(x=>`<option value="${esc(x.id)}" ${x.id===image?'selected':''}>${esc(x.kind==='manual'?'人工匯入圖片（不自動生成）':x.name)}</option>`).join('')}</select></label>
  <p class="muted">圖片與配音是獨立的製作服務；現有 VoxCPM 配音設定繼續沿用。下方仍可逐項調整，調整後會顯示為自訂服務商組合。</p>
  <button type="submit" class="primary">套用整體模式</button><span id="provider-profile-result" role="status"></span></form></section>`;
}

export function renderProductionMethod(input, esc) {
  const method=input?.production_method;
  if(!method?.mandatory)return '';
  const origin=input.image_preparation_origin;
  return `<section class="panel" data-production-method="${esc(method.version)}"><strong>Studio 既定製作方法 · 已套用</strong>
  ${origin?`<p>${origin.mode==='reused'?'沿用相同要求及參考圖的已保存提示詞，沒有重新交給模型改寫。':'已按既定製作規格整理並保存圖片提示詞。'}</p>`:''}
  ${input.image_prompt_stage==='render'?`<details><summary>查看最終圖片提示詞</summary><pre>${esc(input.image_prompt)}</pre></details>`:''}
  <details><summary>製作方法與沿用記錄</summary><pre>${esc(JSON.stringify({method,origin,render_prompt_hash:input.render_prompt_hash},null,2))}</pre></details></section>`;
}
