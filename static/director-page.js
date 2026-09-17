// The handoff guide stores browser-only copy receipts, never creative direction.
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const btn = (label, action, attrs = '', primary = false) => `<button type="button" data-action="${action}" ${attrs} class="${primary ? 'primary' : ''}">${label}</button>`;

export function createHandoffState(storage) {
  const memory = new Map();
  function read(projectId) {
    if (!memory.has(projectId)) {
      let saved;
      try { saved = JSON.parse(storage?.getItem('continuity-handoff-v1:' + projectId)); } catch {}
      memory.set(projectId, saved && typeof saved === 'object' && !Array.isArray(saved) ? saved : {});
    }
    return memory.get(projectId);
  }
  function save(projectId) {
    try { storage?.setItem('continuity-handoff-v1:' + projectId, JSON.stringify(read(projectId))); } catch {}
  }
  return {
    selection(projectId, scenes) {
      const state = read(projectId);
      const scene = scenes.find(s => s.scene_id === state.sceneId) || scenes[0];
      const shot = scene?.chapters.find(c => c.shot_id === state.step);
      return {scene, step: shot ? shot.shot_id : 'shared', shot};
    },
    select(projectId, sceneId, step = 'shared') {
      Object.assign(read(projectId), {sceneId, step}); save(projectId);
    },
    copied(projectId, sceneId, step, text) {
      return read(projectId).copies?.[sceneId]?.[step] === text;
    },
    markCopied(projectId, sceneId, step, text) {
      const state = read(projectId);
      state.copies ??= {}; state.copies[sceneId] ??= {}; state.copies[sceneId][step] = text;
      save(projectId);
    },
  };
}

// Independent failures remain retryable without re-uploading successful images.
export async function transferReferences(references, results, send, onProgress = () => {}) {
  for (const ref of references) {
    if (results[ref.asset_id]?.status === 'sent') continue;
    results[ref.asset_id] = {status: 'sending'}; onProgress();
    try {
      const result = await send(ref.asset_id);
      results[ref.asset_id] = {status: 'sent', result};
    } catch (error) {
      results[ref.asset_id] = {status: 'failed', error: error.message || '傳送失敗，請重試。'};
    }
    onProgress();
  }
}

export function renderHandoff(project, state, transfers = {}, provider = 'Astra', drafts = null, embedded = null) {
  const scenes = project.delivery.scenes;
  if (!scenes.length) return '<div class="panel"><h2>尚未有場景</h2><p>建立場景與鏡頭後，即可在這裡準備導演台內容。</p></div>';
  const selection = state.selection(project.id, scenes);
  const scene = embedded ? scenes.find(s=>s.scene_id===embedded.sceneId) : selection.scene;
  const step = embedded ? (selection.scene?.scene_id===scene.scene_id && selection.step==='shared' ? 'shared' : embedded.shotId) : selection.step;
  const shot = scene.chapters.find(c=>c.shot_id===step);
  const currentShot = embedded && scene.chapters.find(c=>c.shot_id===embedded.shotId);
  const cfg = project.delivery.configuration;
  const review = project.delivery.guidance_review;
  const allGuidance = project.delivery.scenes.flatMap(s=>s.chapters).map(c=>c.guidance.continuityFromPrev);
  const allOff = review?.status==='ready' && allGuidance.every(value=>value===false);
  const guidanceValue = g => g.continuityFromPrev == null ? '暫未能判斷' : g.continuityFromPrev ? '勾選' : '不勾選';
  const reviewMessages={pending:'接續分析尚未啟動；進入此頁會自動開始，也可按下方按鈕。',queued:'接續分析已排隊，完成後會顯示每個 Shot 的勾選建議及原因。',running:'正在按分鏡分析接續方式，完成後會自動顯示每個 Shot 的勾選指示與原因。',waiting:'上一個版本的接續分析仍在處理；完成後會按目前內容重新分析。',awaiting_input:'已選用人工判斷服務，請提交分析結果。'};
  const reviewNotice = review && review.status !== 'ready' ? `<div class="note" role="status">${reviewMessages[review.status]||'接續分析未完成，請查看原因並重試。'}${review.error?`<p>${esc(review.error)}</p>`:''}${review.status==='pending'?btn('開始分析接續','analyze-guidance'):''}${['failed','interrupted','cancelled'].includes(review.status) ? btn('重新分析接續', 'analyze-guidance') : ''}${review.status === 'awaiting_input' ? btn('提交人工判斷', 'manual', `data-id="${esc(review.job_id)}"`) : ''}${review.job_id?btn('查看分析工作','job-detail',`data-id="${esc(review.job_id)}"`):''}</div>` : '';

  const sid = esc(scene.scene_id);
  const prep=scene.preparation;
  const preparationNotice=prep?.required?`<div class="note" role="status">${['queued','running'].includes(prep.status)?'正在整理本 Scene 的英文提示詞：保留原文對白，逐鏡核對動作主體並移除跨場內容。':prep.status==='awaiting_input'?'英文提示詞等待人工提交。':'本 Scene 需要整理英文提示詞，完成後才可複製。'}${['queued','running'].includes(prep.status)?'':prep.status==='awaiting_input'?btn('提交英文提示詞','manual',`data-id="${esc(prep.job_id)}"`):btn('整理英文提示詞','prepare-scene',`data-id="${sid}"`)}</div>`:'';
  const index = shot ? scene.chapters.indexOf(shot) : -1;
  const copied = (key, text) => state.copied(project.id, scene.scene_id, key, text);
  const count = Number(copied('shared', scene.global_prompt)) + scene.chapters.filter(c => copied(c.shot_id, c.shot_prompt)).length;
  const go = (label, key, primary = false) => btn(label, 'director-step', `data-scene="${sid}" data-step="${esc(key)}"`, primary);
  const copy = (key, text, label) => btn(copied(key, text) ? '✓ 已複製 · 再複製' : label, 'director-copy', `data-scene="${sid}" data-step="${esc(key)}"`, true);
  const prompt = (key, text, label) => {
    const draft=drafts?.get(project.id,scene.scene_id,key),dirty=!!draft;
    return `<label class="director-prompt-label" for="director-prompt">${label} · 可直接編輯</label><textarea id="director-prompt" class="director-prompt" data-scene="${sid}" data-step="${esc(key)}" spellcheck="false">${esc(draft?.text??text)}</textarea><div class="actions director-editor-actions">${btn('儲存提示詞','director-save',`data-scene="${sid}" data-step="${esc(key)}" ${dirty?'':'disabled'}`,true)}${btn('放棄修改','director-discard',`data-scene="${sid}" data-step="${esc(key)}" ${dirty?'':'disabled'}`)}<span data-prompt-status role="status">${dirty?'有未儲存修改 · 草稿保留於本瀏覽器':'內容已載入 · 編輯後按儲存'}</span></div><p class="director-copy-note">${dirty?'請先儲存，再複製到導演台。':copied(key,text)?'已複製這份內容；請到導演台貼上。':'儲存後，複製及匯出會使用你的版本。'}</p>`;
  };
  const stepButton = (key, title, sub, text, number) => `<button type="button" data-action="director-step" data-scene="${sid}" data-step="${esc(key)}" class="director-step ${step === key ? 'selected' : ''}" ${step === key ? 'aria-current="step"' : ''}><span class="director-step-number">${number}</span><span><strong>${title}</strong><small>${esc(sub)}</small><small class="director-receipt">${copied(key, text) ? '✓ 提示詞已複製' : '提示詞未複製'}</small></span></button>`;
  const sent = scene.references.filter(r => transfers[r.asset_id]?.status === 'sent').length;
  const sending = scene.references.some(r => transfers[r.asset_id]?.status === 'sending');
  const failed = scene.references.some(r => transfers[r.asset_id]?.status === 'failed');
  const settings = `<div class="director-settings"><div><span>任務類型</span><strong>r2v · 參考主體生影片</strong></div><div><span>公共參數</span><strong>啟用</strong></div><div><span>段間引導</span><strong>${allOff ? '關閉（本作品毋須）' : cfg.continuity_enabled ? '開啟' : '關閉'}</strong></div><div><span>上下文幀數</span><strong>${cfg.context_frames}</strong></div></div><div class="director-setting-note"><span>請在導演台套用以上設定。</span>${btn('調整段間引導', 'delivery-settings')}</div>`;
  const references = `<section class="director-block"><div class="director-block-head"><div><span class="director-destination">公共參數 → 參考圖片</span><h3>① 放入 ${scene.references.length} 張共用圖片</h3></div>${btn(sending ? '正在傳送…' : failed ? '重試未送出圖片' : sent && sent === scene.references.length ? '重新傳送全部圖片' : '全部送到 ComfyUI', 'director-send', `data-scene="${sid}" ${sending || !scene.references.length ? 'disabled' : ''}`, true)}</div><p class="muted">送出後，在導演台按「选已有」→「缩略图」，依圖片編號選取，再按「使用所选文件」。清單已開啟時先按「刷新」。</p><div class="director-images">${scene.references.map((r, i) => {
    const transfer = transfers[r.asset_id];
    return `<article class="director-image"><div class="director-image-label">圖片 ${i + 1} <small>· ${esc(r.label)}</small></div><button type="button" class="director-preview" data-action="lightbox" data-id="${esc(r.asset_id)}" aria-label="查看 ${esc(r.name)} 及圖片操作"><img src="/api/assets/${encodeURIComponent(r.asset_id)}/image" alt="${esc(r.name)}"></button><strong>${esc(r.name)}</strong><div class="director-transfer ${transfer?.status === 'failed' ? 'notice' : ''}">${transfer?.status === 'sent' ? '✓ 已送到素材庫' : transfer?.status === 'sending' ? '正在傳送…' : transfer?.status === 'failed' ? esc(transfer.error) : '按上方按鈕一次送出'}</div>${transfer?.status === 'sent' ? `<details><summary>在素材庫中的檔名</summary><span class="director-filename">${esc(transfer.result.name)}</span></details>` : ''}${btn('複製圖片路徑', 'copy-image-path', `data-id="${esc(r.asset_id)}"`)}</article>`;
  }).join('')}</div><p class="director-copy-note" role="status">${sent ? `${sent} / ${scene.references.length} 張已送到素材庫。仍需在導演台選入圖片槽位。` : '此處放共用人物與場景；道具圖片放在各 Shot。點圖片可放大及開啟原圖資料夾。'}</p>${scene.missing_references.length ? `<p class="notice">尚欠已批准參考圖：${esc(scene.missing_references.join('、'))}。${btn('前往角色與場景', 'navigate', 'data-page="canon"')}</p>` : ''}</section>`;
  const globalRegen=project.scene_prompt_regenerations?.[scene.scene_id];
  const globalRegenerating=globalRegen&&['queued','running','awaiting_input'].includes(globalRegen.state);
  const globalRegenPanel=globalRegen?`<div class="note" role="status">${globalRegen.adopted?'已採用重新生成的版本。':globalRegen.state==='succeeded'?`新版已完成${globalRegen.stale?'，來源已更新，請重新生成':'，待比較及採用'}。 ${btn('比較新版','review-scene-prompt',`data-id="${esc(globalRegen.job_id)}"`)}`:globalRegenerating?`正在重新生成 Scene 全域提示詞，原有文字仍然保留。${globalRegen.state==='awaiting_input'?btn('提交結果','manual',`data-id="${esc(globalRegen.job_id)}"`):''}`:`重新生成未完成，原文仍保留。${esc(globalRegen.error||'可重試。')}`}</div>`:'';
  const shared = `${settings}<p class="director-copy-note director-guidance-summary">${review?.status==='ready' ? (allGuidance.some(value=>value==null) ? '部分鏡頭尚未能確定接續方式，請先查看各 Shot 的原因及修訂說明。' : allGuidance.some(Boolean) ? '部分鏡頭需要連續延長；請開啟總開關，再按每個 Shot 的指示勾選。' : '目前沒有鏡頭需要引用上段，可關閉段間引導總開關。Scene 共用參考圖仍照常使用。') : '總開關是目前保存的設定；各 Shot 是否引用上一段，會按分鏡另行判斷。'}</p>${references}<section class="director-block"><div class="director-block-head"><div><span class="director-destination">公共參數 → 提示詞</span><h3>② 貼上 Scene 全域提示詞</h3></div><div class="actions">${copy('shared', scene.global_prompt, '複製全域提示詞')}${btn(globalRegenerating?'正在重新生成…':'重新生成全域提示詞','regenerate-scene-prompt',`data-id="${sid}" ${globalRegenerating||prep?.required?'disabled':''}`)}${btn('編輯', 'edit-scene-global', `data-id="${sid}"`)}</div></div>${globalRegenPanel}${prompt('shared', scene.global_prompt, '此 Scene 所有 Shot 共用的全域提示詞')}</section>`;
  const regen=project.shot_prompt_regenerations?.[shot?.shot_id];
  const regenerating=regen&&['queued','running','awaiting_input'].includes(regen.state);
  const regenPanel=regen?`<div class="note" role="status">${regen.adopted?'已採用重新生成的版本。':regen.state==='succeeded'?`新版已完成${regen.stale?'，來源已更新，請重新生成':'，待比較及採用'}。 ${btn('比較新版','review-shot-prompt',`data-id="${esc(regen.job_id)}"`)}`:regenerating?`正在重新生成本 Shot，原有文字仍然保留。${regen.state==='awaiting_input'?btn('提交結果','manual',`data-id="${esc(regen.job_id)}"`):''}`:`重新生成未完成，原文仍保留。${esc(regen.error||'可重試。')}`}</div>`:'';
  const localRefs=shot?.local_references??[];
  const localMissing=(shot?.missing_references??[]).filter(name=>!scene.missing_references.includes(name));
  const localPictures=shot?`<section class="director-block director-shot-refs"><div class="director-block-head"><div><span class="director-destination">素材組 ${index+1} → 參考圖片</span><h3>本 Shot 的 ${localRefs.length} 張道具圖片</h3></div></div><p class="muted">按下列 Picture 編號放入本素材組的圖片槽位，保留公共圖片槽位。重用素材組時，清掉上一鏡不再使用的道具圖片。</p><div class="director-images">${localRefs.map(r=>`<article class="director-image"><div class="director-image-label">${esc(r.label)} · 本 Shot</div><button type="button" class="director-preview" data-action="lightbox" data-id="${esc(r.asset_id)}" aria-label="查看 ${esc(r.name)} 及圖片操作"><img src="/api/assets/${encodeURIComponent(r.asset_id)}/image" alt="${esc(r.name)}"></button><strong>${esc(r.name)}</strong><div class="actions">${btn('送到 ComfyUI 素材庫','send-comfy',`data-id="${esc(r.asset_id)}"`)}${btn('複製圖片路徑','copy-image-path',`data-id="${esc(r.asset_id)}"`)}</div></article>`).join('')}</div>${localMissing.length?`<p class="notice">本 Shot 尚欠道具參考圖：${esc(localMissing.join('、'))}。${btn('前往角色與場景','navigate','data-page="canon"')}</p>`:''}<p class="muted">本鏡道具定義已放在下方提示詞開首，請連同 summary 後的內容完整複製。</p></section>`:'';
  const shotContent = shot ? `<div class="director-settings director-shot-settings"><div><span>秒數</span><strong>${shot.duration} 秒</strong></div><div><span>引用上段</span><strong>${guidanceValue(shot.guidance)}</strong></div><div><span>共用圖片</span><strong>Scene 共用 ${scene.references.length} 張 ＋ 本 Shot ${localRefs.length} 張道具</strong></div></div><div class="director-guidance-decision"><strong>${shot.guidance.manual ? '你已手動指定；以下保留自動分析' : shot.guidance.review_provider ? '按分鏡判斷 · ' + esc(shot.guidance.review_provider==='astra'?'Astra':shot.guidance.review_provider==='manual'?'人工分析':shot.guidance.review_provider) : '接續判斷'}</strong><p>${esc(shot.guidance.reason || '第一個 Shot，沒有上一段。')}</p>${shot.guidance.continuityFromPrev && !cfg.continuity_enabled ? '<p class="notice">要套用此接續，請先在「公共參數」開啟段間引導總開關。</p>' : ''}${shot.guidance.decision==='uncertain' ? '<p class="notice">分鏡有未明確之處；請修訂鏡頭說明後重新分析，暫勿依此設定生成。</p>' : ''}${shot.guidance.evidence?.length ? `<details><summary>查看分鏡判斷依據</summary>${shot.guidance.evidence.map(e=>`<blockquote>${esc(e)}</blockquote>`).join('')}</details>` : ''}</div>${localPictures}<section class="director-block"><div class="director-block-head"><div><span class="director-destination">素材組 ${index + 1} → 提示詞</span><h3>貼上此 Shot 的分鏡提示詞</h3></div><div class="actions">${copy(shot.shot_id, shot.shot_prompt, '複製分鏡提示詞')}${btn(regenerating?'正在重新生成…':'重新生成分鏡提示詞','regenerate-shot-prompt',`data-id="${esc(shot.shot_id)}" data-scene="${sid}" ${regenerating||prep?.required?'disabled':''}`)}${btn('鏡頭接續與參考設定', 'edit-chapter-delivery', `data-scene="${sid}" data-id="${esc(shot.shot_id)}"`)}</div></div>${regenPanel}${prompt(shot.shot_id, shot.shot_prompt, '本鏡頭的動作、運鏡、對白與聲音')}${shot.issues.map(issue => `<p class="notice">${esc(issue)}</p>`).join('')}<details><summary>查看接續方向</summary><p class="prose">${esc(shot.guidance.notes)}</p></details></section>` : '';
  if(embedded) return `<div class="director-page director-embedded"><div class="director-scene-bar"><p>Ref2VA · ${esc(scene.title)}：先設定本 Scene 公共參數，再貼入目前 Shot。</p><details class="director-tools"><summary>場景與接續工具</summary>${btn('發展提示詞 · '+esc(provider),'refine-scene',`data-id="${sid}"`)}${btn('段間引導設定','delivery-settings')}${btn('重新分析接續','analyze-guidance')}</details></div>${preparationNotice}${reviewNotice}<nav class="director-inline-tabs" aria-label="目前 Shot 的 Ref2VA 內容">${stepButton('shared','2 · Scene 公共參數','共用參考圖與全域提示詞',scene.global_prompt,'○')}${stepButton(currentShot.shot_id,'3 · 本 Shot 提示詞',currentShot.title,currentShot.shot_prompt,String(currentShot.number))}</nav><article class="director-workspace" aria-labelledby="director-step-heading"><div class="director-workspace-head"><h2 id="director-step-heading" tabindex="-1">${shot?esc(shot.title):'Scene 公共參數'}</h2></div>${shot?shotContent:shared}<footer class="director-footer">${shot?go('← Scene 公共參數','shared'):go('本 Shot 提示詞 →',currentShot.shot_id,true)}</footer></article></div>`;
  return `<div class="director-page"><header class="director-header"><div><div class="eyebrow">H3 / Ref2VA · 導演台交接</div><h1>照次序，複製貼上。</h1><p class="muted">先貼 Scene 公共參數，再逐個 Shot 填入素材組。</p></div>${btn('影片準備 · 首／尾幀', 'navigate', 'data-page="video"')}</header><div class="director-scene-bar"><label for="director-scene">目前 Scene<select id="director-scene" data-director-scene>${scenes.map((s, i) => `<option value="${esc(s.scene_id)}" ${s.scene_id === scene.scene_id ? 'selected' : ''}>${String(i + 1).padStart(2, '0')} · ${esc(s.title)}</option>`).join('')}</select></label><span>${scene.chapters.length} 個 Shot · ${scene.chapters.reduce((sum, c) => sum + c.duration, 0)} 秒</span><details class="director-tools"><summary>場景工具</summary>${btn('發展提示詞 · ' + esc(provider), 'refine-scene', `data-id="${sid}"`)}${btn('段間引導設定', 'delivery-settings')}${btn('重新分析接續', 'analyze-guidance')}</details></div>${scenes.length > 1 ? '<p class="director-copy-note">一次交接一個 Scene。切換 Scene 時，換上該場景的公共參數與素材組內容；全域提示詞只屬於 Scene。</p>' : ''}${preparationNotice}${reviewNotice}<div class="director-layout"><nav class="director-steps" aria-label="貼入導演台的步驟"><div class="director-progress">${count} / ${scene.chapters.length + 1} 份提示詞已複製</div>${stepButton('shared', 'Scene 公共參數', '共用圖片 ＋ 全域提示詞', scene.global_prompt, '○')}${scene.chapters.map((c, i) => stepButton(c.shot_id, `Shot ${String(c.number).padStart(2, '0')} · 素材組 ${i + 1}`, c.title + ' · ' + c.duration + ' 秒 · 引用上段：' + guidanceValue(c.guidance), c.shot_prompt, i + 1)).join('')}<p class="director-copy-note">記錄本瀏覽器的複製進度；不代表已貼入導演台。</p></nav><article class="director-workspace" aria-labelledby="director-step-heading"><div class="director-workspace-head"><div><div class="eyebrow">${shot ? `SHOT ${String(shot.number).padStart(2, '0')} · 素材組 ${index + 1}` : 'SCENE · 只需設定一次'}</div><h2 id="director-step-heading" tabindex="-1">${shot ? esc(shot.title) : '公共參數'}</h2></div><span class="director-step-count">${index + 2} / ${scene.chapters.length + 1}</span></div>${shot ? shotContent : shared}<footer class="director-footer"><div>${shot ? go('← ' + (index ? '上一個 Shot' : '公共參數'), index ? scene.chapters[index - 1].shot_id : 'shared') : ''}</div>${index + 1 < scene.chapters.length ? go('下一步：Shot ' + String(scene.chapters[index + 1].number).padStart(2, '0') + ' →', scene.chapters[index + 1].shot_id, true) : '<span>已到最後一個 Shot · 貼上後可到導演台檢查。</span>'}</footer></article></div></div>`;
}
