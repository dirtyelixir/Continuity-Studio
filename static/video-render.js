import {prepareVideoService} from './video-service-prepare.js';
import {settingsValues,storeSettings,renderSettings,editSettings,setSettingsCatalog,settingsCatalogLoaded,addStyleLoraSlot,removeStyleLoraSlot,clearStyleLoraSlot} from './video-render-settings.js';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function renderFrozenReferences(t){
 const refs=t.image_inputs||[];if(!refs.length)return '';
 const roles={character_identity:'角色身份',object_identity:'物件身份',environment_reference:'環境參考',appearance_consistency:'外觀一致',reusable_visual_reference:'可重用視覺參考',character:'角色身份',prop:'物件身份',location:'環境',crowd:'群像身份',composition:'構圖參考',storyboard:'分鏡參考'};
 return `<section data-frozen-references><h3>${esc(t.request?.source?.mode||'H3')} · 凍結用圖</h3>${refs.map(r=>`<p><strong>${esc(r.name||r.description||r.target_id||'既有圖片')} · ${esc(roles[r.role]||r.role||({start:'首幀',end:'尾幀'}[r.moment])||'原紀錄未標示角色')} → ${esc(r.label)}</strong><br>${r.submission_verified?'✓ 圖片 hash、上傳路徑、graph 綁定及提交回條吻合':'尚未有完整提交證據；凍結或上傳不等於 H3 已收到'}${(t.request?.source?.reference_demands||[]).filter(d=>d.asset_id===r.asset_id).map(d=>`<br>${esc(roles[d.role]||d.role)}：${esc(d.reason)}`).join('')}<br><small>SHA-256 ${esc(r.sha256)}</small></p>`).join('')}<p class="muted">參考圖不保證指定時間命中構圖；生成效果仍須看片。</p></section>`;
}
const rowsFor=p=>[...(p?.video_workflow?.shots||[]),...(p?.generation_groups?.rows||[])];
const readyFor=(p,id)=>p.video_renders?.groups?.[id]||p.video_renders?.shots?.[id];
const active=new Set(['queued','preparing','submitting','submitted','running','uncertain','recoverable']);
const labels={queued:'排隊中 · 等候 GPU／影片服務',preparing:'正在核對及傳送素材',submitting:'等待 VRAM Manager／送出回條',submitted:'已排入 ComfyUI',running:'ComfyUI 正在生成',uncertain:'送出狀態待確認',recoverable:'等待回收成片',failed:'生成失敗',succeeded:'成片待審閱'};
const requests=new Map(), expanded=new Set();
const signature=value=>JSON.stringify(value,(_k,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b))):v);
const key=(p,s)=>p+':'+s;
const button=(text,a,id,disabled=false)=>`<button type="button" class="small ${a==='generate'?'primary':''}" data-render-action="${a}" data-id="${esc(id)}" ${disabled?'disabled':''}>${text}</button>`;
export function renderDraftPending(p,row,drafts){
 return row.kind!=='generation_group'&&row.mode==='REF2VA'&&!row.conditioning?!!(drafts.get(p.id,row.scene_id,'shared')||drafts.get(p.id,row.scene_id,row.shot_id)):!!drafts.get(p.id,row.shot_id,row.mode);
}
export function renderVideoProduction(p,row,drafts){
 const state=p.video_renders;if(!state)return '';
 const splitWorkflow=p.workflow_contract_version===1;
 const ready=readyFor(p,row.shot_id)||{ready:false,reasons:['請重新載入目前分鏡。']},dirty=renderDraftPending(p,row,drafts);
 const takes=state.takes.filter(t=>t.shot_id===row.shot_id),working=takes.find(t=>active.has(t.state));
 const values=settingsValues(p,row);
 const saved=state.frozen_requests?.find(f=>f.unit_id===row.shot_id&&f.source_hash===ready.source_hash&&signature(f.requested_settings)===signature(values));
 if(saved&&!requests.has(key(p.id,row.shot_id)))requests.set(key(p.id,row.shot_id),{frozen_id:saved.id,source_hash:saved.source_hash,settings:saved.requested_settings,request_key:crypto.randomUUID()});
 const frozen=requests.get(key(p.id,row.shot_id)),frozenReady=!!frozen?.frozen_id&&frozen.source_hash===ready.source_hash&&signature(frozen.settings)===signature(values);
 const timing=ready.timing,seconds=timing?.duration??row.duration;
 const markup = `<section class="panel video-production" data-render-shot="${esc(row.shot_id)}"><div class="panel-header"><h2>本鏡 · 生成與審閱影片</h2>${button('準備影片服務（自動切換 H3）','status',row.shot_id)}</div><p>MiniMax H3 · 本機 ComfyUI。生成前會自動向 VRAM Manager 申請切換 H3。按下生成會帶入本鏡已儲存的提示詞與批准圖片，完成後自動保存到 Studio，可在這裡播放。「下載 MP4」另存一份；「採用此成片」選為本鏡使用的版本。</p>
 <div class="form-grid video-locked-timing"><label>本鏡時長（依分鏡，固定）<input value="${esc(seconds)} 秒" disabled></label><label>影格率（固定）<input value="24 fps" disabled></label></div>
 <p class="muted">沿用本 Shot 的分鏡秒數，此處不可修改。${timing?`H3 對齊為 ${timing.frame_count} 幀，預計 ${Number(timing.aligned_duration).toFixed(3)} 秒。`:''}</p>
 ${renderSettings(p,row,values,!!working,expanded.has(key(p.id,row.shot_id)))}
 <div class="actions">${button('查看本次生成提示詞','prompt-preview',row.shot_id,!ready.ready||dirty||!!working)}${splitWorkflow?button(frozenReady?'本次請求已凍結':'凍結本次 H3 請求','freeze',row.shot_id,!ready.ready||dirty||!!working||frozenReady):''}${frozenReady?'<span>精確素材與參數已保存，尚未送出。</span>':''}</div>
 ${!ready.ready?`<div class="note">${ready.reasons.map(r=>`<p>${esc(r)}</p>`).join('')}</div>`:''}<p class="muted" data-render-draft-note>${dirty?'有未儲存提示詞，請先儲存或放棄草稿。':''}</p>
 <div class="actions">${button(working?labels[working.state]:'一鍵生成本鏡影片','generate',row.shot_id,!ready.ready||dirty||!!working||splitWorkflow&&!frozenReady)}</div>
 ${takes.map(t=>`<article class="video-take"><div class="panel-header"><h3>${t.selected?'✓ 已採用':esc(labels[t.state]||t.state)}</h3><small>${esc(new Date(t.created).toLocaleString('zh-HK'))}</small></div>${active.has(t.state)&&!['uncertain','recoverable'].includes(t.state)?`<p role="status">${esc(labels[t.state])} · <span data-job-since="${esc(t.created)}"></span></p>`:''}<p>執行：${esc(labels[t.state]||t.state)} · 人工審閱：${esc({accepted:'接受',rejected:'拒絕',unreviewed:'未審閱'}[t.review_status]||'未審閱')} · ${t.current?'與現版兼容':'需要兼容性核對'} · ${t.used_in_edit?'已引用於剪接':'未綁定剪接'}</p>${!t.current?'<p class="note">原影片及記錄仍然保留；可看片確認是否適用於現版。</p>':''}${t.error?`<p class="note overflow">${esc(t.error)}</p>`:''}${t.video_url?`<p class="muted">已保存到 Studio${t.selected?' · 本鏡已採用':''}</p><video controls preload="none" src="${esc(t.video_url)}" style="width:100%;max-height:600px;background:#151712"></video><p>${Number(t.result.duration).toFixed(3)} 秒 · ${t.result.width}×${t.result.height} · ${t.result.audio_channels?t.result.audio_channels+' 聲道':'無音軌'}</p>`:''}<div class="actions">${t.state==='succeeded'&&t.current&&!t.selected?button('採用此成片','adopt',t.id):''}${['uncertain','recoverable','submitted','running'].includes(t.state)?button(t.state==='recoverable'?'重新回收成片':'重新查詢原工作','recover',t.id):''}${t.video_url?`<a class="small" href="${esc(t.video_url)}" download="${esc(row.title)}-${t.id}.mp4">下載 MP4</a>`:''}${t.state==='succeeded'?reviewButtons(t):''}${button('工作記錄','detail',t.id)}</div></article>`).join('')}</section>`;
 return row.kind==='generation_group'?markup.replaceAll('本鏡','本組').replace('沿用本 Shot 的分鏡秒數','沿用組內分鏡的合計秒數').replace('採用此成片','採用整組成片').replace('本組使用的版本。','本組使用的版本。整組只保存一次；採用不等於已核對切點。'):markup;
}
export function installVideoRenderUI({getProject,drafts,api,modal,refresh,guarded,toast}){
 let loading=false;
 async function loadOptions(){if(loading)return;loading=true;try{setSettingsCatalog(await api('/video-provider/options'));await refresh(true);}catch(error){toast('未能讀取本機選單：'+error.message);}finally{loading=false;}}
 document.addEventListener('toggle',e=>{
  if(!e.target.matches?.('[data-render-settings]')||!e.target.isConnected)return;
  const p=getProject(),section=e.target.closest('[data-render-shot]');if(!p||!section)return;
  const k=key(p.id,section.dataset.renderShot);if(e.target.open){expanded.add(k);if(!settingsCatalogLoaded())loadOptions();}else expanded.delete(k);
 },true);
 const selectedValues=new WeakMap();
 function onSettingsInput(e){
  if(e.target.tagName==='SELECT'){
   if(selectedValues.get(e.target)===e.target.value)return;
   selectedValues.set(e.target,e.target.value);
  }
  const p=getProject(),section=e.target.closest('[data-render-shot]');
  if(section){
   const row=rowsFor(p).find(r=>r.shot_id===section.dataset.renderShot);
   if(row&&editSettings(p,row,e.target)&&e.target.tagName==='SELECT'){
    const values=settingsValues(p,row),steps=section.querySelector('[data-render-setting="steps"]'),summary=section.querySelector('[data-render-settings] summary');
    if(steps){steps.value=values.steps;steps.disabled=true;}
    if(summary)summary.textContent=summary.textContent.replace(/· \d+ 步 ·/,`· ${values.steps} 步 ·`);
    const details=section.querySelector('[data-render-settings]');
    if(details){
     const working=p.video_renders.takes.some(t=>t.shot_id===row.shot_id&&active.has(t.state));
     details.outerHTML=renderSettings(p,row,values,working,details.open);
    }else refresh(true).catch(error=>toast(error.message));
   }
  }
  // A new unsaved prompt must disable generation immediately, before any rerender.
  for(const panel of document.querySelectorAll('[data-render-shot]')){
   const row=rowsFor(p).find(r=>r.shot_id===panel.dataset.renderShot);if(!row)continue;
   const dirty=renderDraftPending(p,row,drafts),b=panel.querySelector('[data-render-action="generate"]');
   const waiting=p.video_renders.takes.some(t=>t.shot_id===row.shot_id&&active.has(t.state));
   const frozen=requests.get(key(p.id,row.shot_id)),valid=!!frozen?.frozen_id&&frozen.source_hash===readyFor(p,row.shot_id)?.source_hash&&signature(frozen.settings)===signature(settingsValues(p,row));
   if(b)b.disabled=dirty||waiting||!readyFor(p,row.shot_id)?.ready||p.workflow_contract_version===1&&!valid;
   const freeze=panel.querySelector('[data-render-action="freeze"]');if(freeze){freeze.disabled=dirty||waiting||!readyFor(p,row.shot_id)?.ready||valid;freeze.textContent=valid?'本次請求已凍結':'凍結本次 H3 請求';}
   panel.querySelector('[data-render-draft-note]').textContent=dirty?'有未儲存提示詞，請先儲存或放棄草稿。':'';
  }
 }
 document.addEventListener('input',onSettingsInput);
 document.addEventListener('change',e=>{if(e.target.tagName==='SELECT')onSettingsInput(e);});
 document.addEventListener('click',e=>{const b=e.target.closest('[data-render-action]');if(!b||b.disabled)return;
  guarded(async()=>{
   const p=getProject(),id=b.dataset.id,a=b.dataset.renderAction,base='/projects/'+p.id;
   if(a==='options'){await loadOptions();return;}
   if(a==='status'){const label=b.textContent;b.disabled=true;b.textContent='正在準備 H3…';toast('正在向 VRAM Manager 申請 H3，切換完成後會通知你。');try{const s=await prepareVideoService(api,{notify:toast});toast(s.message);}finally{b.disabled=false;b.textContent=label;}return;}
   if(a==='add-style-lora'||a==='remove-style-lora'){
    const row=rowsFor(p).find(r=>r.shot_id===id);if(!row)return;
    if(p.video_renders.takes.some(t=>t.shot_id===id&&active.has(t.state)))throw Error('影片工作進行中，請完成後再修改 LoRA。');
    if(a==='add-style-lora')addStyleLoraSlot(p,row);else removeStyleLoraSlot(p,row,Number(b.dataset.loraIndex));
    const details=b.closest('[data-render-shot]')?.querySelector('[data-render-settings]');
    if(details)details.outerHTML=renderSettings(p,row,settingsValues(p,row),false,true);
    return;
   }
   if(a==='recommend-loras'||a==='apply-lora-advice'){
    const row=rowsFor(p).find(r=>r.shot_id===id),v=settingsValues(p,row),ready=readyFor(p,id);
    if(renderDraftPending(p,row,drafts))throw Error('請先儲存或放棄提示詞草稿，再推薦或套用 LoRA。');
    if(!ready?.ready)throw Error('請先完成本鏡素材與影片提示詞。');
    if(p.video_renders.takes.some(t=>t.shot_id===id&&active.has(t.state)))throw Error('影片工作進行中，請完成後再修改 LoRA。');
    const originalLabel=b.textContent;b.disabled=true;b.textContent=a==='recommend-loras'?'正在建立推薦…':'正在核對並套用…';
    try{
     if(a==='recommend-loras'){
      const response=await api(base+'/jobs',{capability:'h3_lora_advice',target_id:id,video_model:v.model});
      const job=response.job;
      ready.style_lora_advice??={};ready.style_lora_advice[v.model]={id:job.id,state:job.state,provider:job.provider,error:job.error,result:job.result,source_hash:job.input.lora_source.source_hash,candidates:job.input.lora_source.candidates};
      toast('已建立 Style LoRA 推薦，完成後會顯示理由；目前選擇保留。');
     }else{
      const advice=ready.style_lora_advice?.[v.model];
      if(!advice||advice.state!=='succeeded'||advice.source_hash!==ready.source_hash)throw Error('建議已過期，請重新推薦。');
      const response=await api(base+'/video-workflow/'+id+'/lora-advice-selection',{job_id:advice.id,model:v.model});
      if(renderDraftPending(p,row,drafts))throw Error('提示詞草稿已更改，請先儲存後重新推薦。');
      const latest=settingsValues(p,row);
      if(latest.model!==v.model||JSON.stringify(latest.other_loras)!==JSON.stringify(v.other_loras))throw Error('設定已更改，請重新套用建議。');
      latest.other_loras=response.other_loras;clearStyleLoraSlot(p,row);storeSettings(p,row,latest);
      toast(response.other_loras.length?'已套用建議及各 LoRA 的預設強度，觸發詞會自動加入。':'已套用建議：不使用 Style LoRA。');
     }
     const section=b.closest('[data-render-shot]'),details=section?.querySelector('[data-render-settings]');
     if(details)details.outerHTML=renderSettings(p,row,settingsValues(p,row),false,true);
    }catch(error){b.disabled=false;b.textContent=originalLabel;throw error;}
    return;
   }
   if(a==='prompt-preview'){
    const row=rowsFor(p).find(r=>r.shot_id===id);
    if(renderDraftPending(p,row,drafts))throw Error('請先儲存或放棄提示詞草稿。');
    const preview=await api(base+'/video-workflow/'+id+'/prompt-preview',settingsValues(p,row));
    modal('本次生成提示詞',`<p>${preview.triggers.length?'自動套用觸發詞：'+preview.triggers.map(esc).join('、'):'所選 LoRA 沒有已核對的觸發詞。'} 原提示詞保留。此預覽不會啟動生成。</p>${preview.global_prompt?`<h3>Scene 共用提示詞</h3><pre>${esc(preview.global_prompt)}</pre>`:''}<h3>本鏡提示詞</h3><pre>${esc(preview.text)}</pre>`,true);return;
   }
   if(a==='freeze'){
    const row=rowsFor(p).find(r=>r.shot_id===id),src=readyFor(p,id);
    if(!src?.ready||renderDraftPending(p,row,drafts))throw Error('請先完成並儲存提示詞與素材。');
    const req={source_hash:src.source_hash,request_key:crypto.randomUUID(),settings:settingsValues(p,row)};
    const frozen=await api(base+'/video-workflow/'+id+'/freeze',req);
    requests.set(key(p.id,id),{...req,frozen_id:frozen.id});await refresh(true);
    toast('已凍結圖片、提示詞、模型、種子及時間映射；按生成才會送出。');return;
   }
   if(a==='generate'){
    const row=rowsFor(p).find(r=>r.shot_id===id);
    if(renderDraftPending(p,row,drafts))throw Error('請先儲存或放棄提示詞草稿。');
    const src=readyFor(p,id);if(!src?.ready)throw Error('本鏡尚未準備好。');
    const k=key(p.id,id),values=settingsValues(p,row);
    let req=requests.get(k);
    if(p.workflow_contract_version!==1&&(!req||req.source_hash!==src.source_hash||signature(req.settings)!==signature(values))){req={source_hash:src.source_hash,request_key:crypto.randomUUID(),settings:values};requests.set(k,req);}
    if(p.workflow_contract_version===1&&(!req?.frozen_id||req.source_hash!==src.source_hash||signature(req.settings)!==signature(values)))throw Error('素材或設定已更新，請先凍結本次請求。');
    b.disabled=true;b.textContent='正在保存生成工作…';
    let take;try{take=await api(base+'/video-workflow/'+id+'/generate',req);}catch(error){b.disabled=false;b.textContent='重試保存生成工作';throw error;}
    requests.delete(k);await refresh(true);toast(take.state==='failed'?'工作未送出，請查看失敗原因。':'已保存影片工作，進度會顯示在本鏡下方。');return;
   }
   if(a==='accept'||a==='reject'){
    const t=p.video_renders.takes.find(t=>t.id===id);
    await api(base+'/video-renders/'+id+'/review',{decision:a==='accept'?'accepted':'rejected',compatibility_hash:t.compatibility.current_hash});
    await refresh(true);toast(a==='accept'?'已保存人工接受與兼容性核對；可選用或綁定素材。':'已保存拒絕紀錄，原影片保留。');return;
   }
   if(a==='bind'){
    const t=p.video_renders.takes.find(t=>t.id===id);
    const edits=(p.edit_segments?.segments||[]).filter(e=>e.shot_id===t.shot_id||(t.mapping?.boundaries||[]).some(b=>b.edit_id===e.edit_id&&b.shot_id===e.shot_id));
    if(!edits.length)throw Error('原剪接項目已移除，影片仍可播放及下載。');
    modal('綁定實際剪接範圍',`<video controls src="${esc(t.video_url)}" style="width:100%;max-height:340px"></video><p>看片後輸入實際範圍。初值只是剪接計劃；保存後才會引用此 Take。</p><form id="take-binding"><label>剪接項目<select name="edit_id">${edits.map(e=>`<option value="${esc(e.edit_id)}">${esc(e.title)} · ${esc(e.edit_id)}</option>`).join('')}</select></label><label>素材入點<input type="number" name="source_in" min="0" step="0.001" required></label><label>素材出點<input type="number" name="source_out" min="0.001" max="${t.result.duration}" step="0.001" required></label><label>時間線入點<input type="number" name="timeline_in" min="0" step="0.001" required></label><label>看片紀錄<textarea name="note" required></textarea></label><button type="submit">保存實際素材範圍</button></form>`,true);
    const form=document.querySelector('#take-binding');
    const fill=()=>{const e=edits.find(e=>e.edit_id===form.elements.edit_id.value),m=t.mapping?.boundaries?.find(b=>b.edit_id===e.edit_id);form.elements.source_in.value=m?.start??e.planned.planned_edit_in;form.elements.source_out.value=m?.end??e.planned.planned_edit_out;form.elements.timeline_in.value=e.material?.timeline_in??e.planned.timeline_in;};
    form.elements.edit_id.onchange=fill;fill();
    form.onsubmit=e=>{e.preventDefault();guarded(async()=>{const f=new FormData(form);await api(base+'/edit-segments',{version:p.edit_segments.version,production_revision:p.revision,take_id:id,edit_id:f.get('edit_id'),source_in:Number(f.get('source_in')),source_out:Number(f.get('source_out')),timeline_in:Number(f.get('timeline_in')),note:f.get('note')},'PUT');await refresh(true);toast('已保存實際剪接素材範圍。');form.querySelector('[type=submit]').disabled=true;});};return;
   }
   if(a==='recover'){await api(base+'/video-renders/'+id+'/recover',{});await refresh(true);toast('正在查詢／回收原工作，沒有重新生成。');return;}
   if(a==='adopt'){const t=p.video_renders.takes.find(t=>t.id===id);await api(base+'/video-renders/'+id+'/adopt',{source_hash:t.source_hash});await refresh(true);toast('已採用此成片。');return;}
   if(a==='detail'){const t=await api(base+'/video-renders/'+id);modal('影片工作記錄',`<p>此記錄保存生成時的素材、模式與參數；成片採用不會更改圖片 canon。</p>${renderFrozenReferences(t)}<details><summary>完整工作／回條資料</summary><pre>${esc(JSON.stringify(t,null,2))}</pre></details>`,true);}
  });
 });
}

function reviewButtons(t){if(!t.compatibility)return '';if(t.media_available===false)return '<p>原工作已成功，但本機成片檔案需要找回；歷史記錄保留。</p>';return `${button(t.current?'看片後接受候選':'看片確認與現版兼容','accept',t.id)}${button('拒絕候選','reject',t.id)}${t.current&&t.review_status==='accepted'?button('綁定實際剪接範圍','bind',t.id):''}`;}
export function renderTakeLibrary(p){
 if(!p.edit_segments)return '';
 const takes=p.video_renders?.takes||[],segments=p.edit_segments?.segments||[];
 return `<section class="panel" id="edit-materials"><h2>實際剪接素材</h2><p>每個項目都引用 Take、素材入出點及時間線位置。聲音可並行準備；這裡尚未渲染最終成片。</p>${segments.map(e=>`<p><strong>${esc(e.title)} · ${esc(e.edit_id)}</strong> · ${esc({unassigned:'未綁定',planned_unverified:'預定範圍，待看片',current:'已綁定',legacy_observed:'已沿用人工切點',needs_review:'原綁定需核對'}[e.status])}${e.material?` · ${esc(e.material.take_id)}：素材 ${e.material.source_in}–${e.material.source_out} 秒 → 時間線 ${e.material.timeline_in}–${e.material.timeline_out} 秒`:''}</p>`).join('')}${p.edit_segments?.warnings?.length?'<p class="note">實際時間線有空隙或重疊，請核對素材位置。</p>':''}<details><summary>全部影片與歷史工作 · ${takes.length}</summary>${takes.map(t=>`<article><h3>${esc(t.shot_id)} · ${esc(t.id)}</h3><p>${esc(labels[t.state]||t.state)} · ${esc(t.review_status)} · ${t.current?'兼容':'待兼容性核對'} · ${t.used_in_edit?'已用於剪接':'未綁定剪接'}</p>${t.video_url?`<video controls preload="none" src="${esc(t.video_url)}" style="width:100%;max-height:380px"></video>`:''}<div class="actions">${t.state==='succeeded'?reviewButtons(t):''}${button('工作記錄','detail',t.id)}</div></article>`).join('')}</details></section>`;
}
