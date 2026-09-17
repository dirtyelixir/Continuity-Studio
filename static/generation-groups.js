import {renderVideoProduction} from './video-render.js';
import {renderFrameUses} from './storyboard-usage.js';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const button=(text,action,id='')=>`<button type="button" data-group-action="${action}" data-id="${esc(id)}">${text}</button>`;
const modes={I2VA:'只用整組首幀',FL2VA:'整組首尾幀',REF2VA:'多張身份／構圖參考'};
export function renderGroupPlanReview(p,j){
 const legacy=j.contract_current!==true;
 const result=j.result||{},groups=result.groups||[];
 const body=`<p>${esc(result.summary)}</p>${groups.map(g=>`<article><h3>${esc(g.title)} · ${g.execution==='native_montage'?'一段 H3 多鏡片':'獨立來源生成後剪接'}</h3><p>${esc(g.reason)}</p><p>${g.execution==='separate_source'?'生成模式由逐鏡影片準備判斷':esc(modes[g.mode])} · ${g.edit_ids.length} 個剪接項目</p><ul>${g.checks.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>${renderFrameUses(p,g.frame_uses)}</article>`).join('')}`;
 const sourceIds=[...new Set(groups.filter(g=>g.execution==='separate_source').flatMap(g=>g.edit_ids).map(id=>p.production.edit_plan?.find(e=>e.id===id)?.shot_id).filter(Boolean))];
 return `${legacy?'<p class="notice">這份舊安排未包含逐張用圖契約，或可能混用剪接與生成模式規則，需要重新安排。原始建議保留供追查，不作為目前模式依據。</p>':j.stale?'<p class="notice">分鏡或製作方法已更新，請重新安排。</p>':''}<p>獨立來源先生成完整影片，再按剪接範圍取用；裁切本身不排除首幀或首尾幀模式。首尾圖不能保證停頓秒數、運鏡速度或中段動作，仍須檢查成片。</p>${legacy?`<details><summary>查看舊版原始建議</summary>${body}</details>`:body}<div class="actions"><button id="group-plan-adopt" class="primary" ${legacy||j.stale||j.adopted||j.state!=='succeeded'?'disabled':''}>${j.adopted?'已採用':'採用生成安排'}</button>${legacy||j.stale?button('重新安排此場景','plan',j.target_id):''}${sourceIds.map(id=>`<button type="button" data-action="video-ref" data-id="${esc(id)}">準備：${esc(p.production.shots?.find(s=>s.id===id)?.title||id)}</button>`).join('')}</div><p>獨立來源沿用逐鏡工作台；採用安排不會替你選定模式、批准圖片或開始生片。</p>`;
}

function memberPicture(p,m){
 const a=p.storyboard?.scenes?.flatMap(s=>s.panels).find(x=>x.edit_id===m.edit_id)?.anchors?.[0];
 if(a)return `${a.asset?`<img loading="lazy" src="/api/assets/${esc(a.asset.id)}/image" alt="${esc(m.title)} 的圖板畫面">`:`<p class="muted">${esc(a.frame?.description||'圖板畫面待更新')}</p>`}<small>剪接開場：來源 ${a.time} 秒 · ${a.ready?'已逐格批准':'待製作／審閱'}</small>`;
 if(m.source_in)return '<p class="muted">此段由來源 '+m.source_in+' 秒開始，請在視覺圖板準備對應時刻的畫面。</p>';
 const f=m.shot.keyframes.find(f=>f.moment==='start'),asset=f&&p.assets?.find(x=>x.target_id===f.id&&x.status==='approved');
 return asset?`<img loading="lazy" src="/api/assets/${esc(asset.id)}/image" alt="${esc(m.title)} 的來源首幀"><small>來源首幀預覽</small>`:`<p class="muted">${esc(f?.description||'尚未準備分鏡畫面')}</p>`;
}

export function renderGenerationGroups(p,drafts,{preparationOnly=false,planningOnly=false,groupId=null}={}){
 const rows=(p.generation_groups?.rows||[]).filter(r=>!groupId||r.id===groupId);
 const content=rows.map(r=>`<details data-generation-group="${esc(r.id)}" ${preparationOnly?'open data-group-primary="true"':''}><summary>${esc(r.title)} · ${r.members.length} 個分鏡 · ${r.duration} 秒 · ${esc(modes[r.mode])}</summary><p>${esc(r.reason)}</p><div class="actions">${button('調整分組與參考','edit',r.id)}${button('停用分組（保留影片）','archive',r.id)}</div>
 <div class="video-reference-grid">${r.members.map((m,i)=>`<article><h3>${i+1}. ${esc(m.title)}</h3><p><strong>${m.start}–${m.end} 秒</strong> · ${esc(m.shot.framing)} · ${esc(m.shot.angle)}</p><p>${esc(m.shot.direction?.visual_carrier||m.shot.shot_purpose||m.shot.action)}</p><p>${esc(m.edit.cut_in_reason||'')}</p>${memberPicture(p,m)}</article>`).join('')}</div>
 ${r.checks?.length?`<h3>看片要核對</h3><ul>${r.checks.map(c=>`<li>${esc(c)}</li>`).join('')}</ul>`:''}<h3>本次附圖用途</h3><p>${r.reference_requirements?.length||0} 張圖片 · ${esc(modes[r.mode])}。中間切點需檢視成片確認。</p><div class="video-reference-grid">${(r.reference_requirements||[]).map((ref,i)=>`<article>${ref.asset?`<img loading="lazy" src="/api/assets/${esc(ref.asset.id)}/image" alt="Picture ${i+1}">`:''}<p>Picture ${i+1} · ${esc({character:'角色身份',location:'場景身份',prop:'道具身份',crowd:'群像身份',storyboard:'分鏡構圖'}[ref.role]||ref.role)} · ${ref.ready?'已準備':'待準備'}</p><p>${esc(ref.title)}</p>${!ref.ready&&!ref.target_id?`<p>先在視覺圖板安排來源 ${ref.source_time} 秒的畫面，再製作及審閱。</p><button data-action="navigate" data-page="shots">前往視覺圖板</button>`:''}${!ref.ready&&ref.target_id?`<div class="actions"><button type="button" data-action="generate" data-target="${esc(ref.target_id)}">準備此參考圖</button><button type="button" data-action="upload" data-target="${esc(ref.target_id)}">匯入圖片</button></div>`:''}</article>`).join('')}</div>
 ${r.reasons.map(x=>`<p class="note">${esc(x)}</p>`).join('')}
 <div class="actions"><button type="button" data-group-action="generate-prompt" data-id="${esc(r.id)}" ${!r.source_hash||['queued','running','awaiting_input'].includes(r.job?.state)?'disabled':''}>${['queued','running','awaiting_input'].includes(r.job?.state)?'提示詞處理中…':'生成整組 H3 提示詞'}</button>${r.prompt.text?button('檢視／修改已保存提示詞','prompt',r.id):''}</div>
 ${r.job?`<p>提示詞工作：${esc(({queued:'已排隊',running:'正在生成',succeeded:'完成，請檢視',failed:'失敗',awaiting_input:'等待人工結果'})[r.job.state]||r.job.state)}${r.job.stale?' · 來源已更新':''}</p>${r.job.error?`<p class="note">${esc(r.job.error)}</p>`:''}<div class="actions">${r.job.state==='succeeded'?button('檢視並採用新版提示詞','review',r.id):''}<button type="button" data-action="job-detail" data-id="${esc(r.job.id)}">工作記錄</button></div>`:''}
 ${renderVideoProduction(p,r,drafts)}
 ${(p.video_renders?.takes||[]).filter(t=>t.shot_id===r.id&&t.state==='succeeded').map(t=>`<p>${t.selected?'已採用版本':'候選版本'} ${esc(t.id)}：${t.mapping?.status==='user_observed'?'已保存人工觀察的切點':'只有預定切點，尚未核對實際畫面'} ${button('播放後記錄實際切點','boundaries',t.id)}</p>`).join('')}
 </details>`).join('');
 if(preparationOnly)return `<section class="panel montage-groups">${content}</section>`;
 const plans=p.generation_groups?.plans||[];
 const planActions=`<div class="actions">${p.production.scenes.map(s=>button('由導演安排：'+esc(s.title),'plan',s.id)).join('')}${button('建立多鏡分組','new')}</div>`;
 return `<section class="panel montage-groups"><div class="panel-header"><h2>生成安排</h2></div>
 ${plans.map(j=>`<div class="group-plan-status${j.state==='succeeded'&&j.adopted?' is-adopted':''}"><div class="group-plan-status-row"><strong>${esc(j.title)}</strong><span class="badge ${j.state==='succeeded'?(j.adopted?'approved':'pending'):esc(j.state)}">${esc({queued:'已排隊',running:'安排中',succeeded:j.adopted?'已採用':'待檢視',failed:'安排失敗',awaiting_input:'等待人工結果'}[j.state]||j.state)}</span>${j.state==='succeeded'?button('檢視生成安排','plan-review',j.id):''}${j.resumable?`<button type="button" data-action="resume-stages" data-id="${esc(j.id)}">接續安排</button>`:''}</div>${j.progress&&j.state!=='succeeded'?`<p class="muted">${esc(j.progress.label)}${j.progress.completed?' · 已保存 '+esc(j.progress.completed)+' 批':''}</p>`:''}${j.error?`<p class="notice">${esc(j.error)}</p>`:''}${j.contract_current!==true?'<p class="notice">舊版安排，請重新規劃。</p>':j.stale?'<p class="notice">分鏡已更新，請重新安排。</p>':''}</div>`).join('')}
 ${!rows.length?`<p class="muted">${(p.generation_groups?.arrangements||[]).some(a=>a.status==='current')?'到下方 H3 繼續製作。':p.generation_groups?.arrangements?.length?'生成安排需要更新。':plans.length?'':'先由導演安排影片生成方式。'}</p>`:''}
 ${!plans.length?planActions:''}
 ${planningOnly?rows.map(r=>`<p>${button('準備：'+esc(r.title),'open',r.id)}</p>`).join(''):content}
 ${plans.length||p.generation_groups?.archived?.length?`<details class="group-plan-options"><summary>更多選項</summary>${plans.length?planActions:''}${plans.map(j=>`<p>${esc(j.title)} <button type="button" data-action="job-detail" data-id="${esc(j.id)}">工作記錄</button></p>`).join('')}${p.generation_groups?.archived?.length?`<details><summary>已停用分組 · ${p.generation_groups.archived.length}</summary>${p.generation_groups.archived.map(g=>`<p>${esc(g.title)} ${button('恢復分組','restore',g.id)}</p>`).join('')}</details>`:''}</details>`:''}</section>`;
}
export function installGenerationGroups({getProject,api,modal,close,refresh,guarded,toast,openGroup}){
 document.addEventListener('click',e=>{const b=e.target.closest('[data-group-action]');if(!b||b.disabled)return;
 guarded(async()=>{
  const p=getProject(),pid=p.id,id=b.dataset.id,action=b.dataset.groupAction,base='/projects/'+pid;
  const r=p.generation_groups?.rows.find(r=>r.id===id);
  if(action==='open'){
   if(openGroup){openGroup(id);return;}
   const panel=[...document.querySelectorAll('[data-generation-group]')].find(el=>el.dataset.generationGroup===id);
   if(!r||!panel)throw Error('此分組已更新或停用，請重新載入生成安排。');
   panel.open=true;panel.setAttribute('tabindex','-1');panel.focus({preventScroll:true});panel.scrollIntoView({block:'start',behavior:'smooth'});return;
  }
  if(action==='archive'||action==='restore'){await api(base+'/generation-groups/'+id+'/archive',{revision:p.generation_groups.revision,archived:action==='archive'});await refresh(true);toast(action==='archive'?'已停用分組，工作與影片保留。':'已恢復分組。');return;}
  if(action==='plan'){
   b.disabled=true;b.textContent='正在提交安排…';
   try{await api(base+'/jobs',{capability:'h3_group_plan',target_id:id});b.textContent='安排已提交';await refresh(true);toast('導演會按已採用分鏡安排分組，完成後先檢視。');}catch(error){b.disabled=false;b.textContent='由導演安排';throw error;}return;
  }
  if(action==='plan-review'){
   const j=p.generation_groups.plans.find(j=>j.id===id);
   if(!j?.result||j.state!=='succeeded')throw Error('生成安排尚未完成，請先查看工作記錄。');
   modal('檢視導演生成安排',renderGroupPlanReview(p,j),true);
   document.querySelector('#group-plan-adopt').onclick=()=>guarded(async()=>{if(j.contract_current!==true||j.stale||j.adopted)return;await api(base+'/generation-groups/plan-adopt/'+id,{revision:p.generation_groups.revision});close();await refresh(true);toast('已採用生成安排；H3 · 影片準備已更新。');document.querySelector('[data-adopted-arrangements]')?.scrollIntoView({block:'start',behavior:'smooth'});});return;
  }
  if(action==='new'||action==='edit'){
   const edits=p.production.edit_plan||[];
   if(!edits.length)throw Error('請先建立並採用包含剪接次序的導演方案。');
   const gid=r?.id||'mg_'+crypto.randomUUID().replaceAll('-','').slice(0,16);
   const targets=[...p.production.canon.filter(x=>x.kind!=='voice').map(x=>({id:x.id,label:x.name,role:x.kind})),...p.production.shots.flatMap(s=>s.keyframes.map(f=>({id:f.id,label:s.title+' · '+(f.moment==='key'?f.source_time+' 秒關鍵幀':f.moment),role:'storyboard'})))];
   modal(r?'調整生成分組':'建立生成分組',`<form id="generation-group-form"><label>分組名稱<input name="title" required value="${esc(r?.title||'')}" maxlength="160"></label><label>點解呢幾個畫面適合一段片？<textarea name="reason" required>${esc(r?.reason||'')}</textarea></label><h3>依剪接表選取連續分鏡</h3><p>保留每個分鏡嘅觀看時間，合共須為 4–15 秒。</p>${edits.map(edit=>{const s=p.production.shots.find(s=>s.id===edit.shot_id);return `<label class="reference-check"><input type="checkbox" name="edit_ids" value="${esc(edit.id)}" data-seconds="${edit.planned_edit_out-edit.planned_edit_in}" ${r?.edit_ids.includes(edit.id)?'checked':''}><span>${esc(s.title)} · ${esc(s.framing)} · ${Number(edit.planned_edit_out-edit.planned_edit_in).toFixed(2)} 秒</span></label>`;}).join('')}<p data-group-total role="status"></p><label>圖片做法<select name="mode">${Object.entries(modes).map(([mode,label])=>`<option value="${mode}" ${mode===(r?.mode||'I2VA')?'selected':''}>${label}</option>`).join('')}</select></label><p>首幀用第一個分鏡嘅開場圖；首尾幀再加最後分鏡嘅結尾圖。若剪接端點已修短，可先保存安排；對應時刻嘅關鍵幀會列為待準備條件，送出前須完成審閱。</p><fieldset data-group-refs><legend>Ref2VA 參考圖（1–9 張，須屬組內分鏡或相關身份）</legend><p>身份圖固定外觀；分鏡圖提供構圖參考，唔代表鎖定每次切鏡。</p>${targets.map(t=>`<label class="reference-check"><input type="checkbox" name="reference_targets" value="${esc(t.id)}" ${r?.reference_targets.includes(t.id)?'checked':''}><span>${esc(t.label)} · ${esc(t.role)}</span></label>`).join('')}</fieldset><div class="actions"><button type="submit" class="primary">儲存分組</button></div><p>儲存只更新分組，之後先生成提示詞及影片。</p></form>`,true);
   const form=document.querySelector('#generation-group-form');
   const update=()=>{form.querySelector('[data-group-total]').textContent='已選 '+form.querySelectorAll('[name=edit_ids]:checked').length+' 個分鏡 · '+[...form.querySelectorAll('[name=edit_ids]:checked')].reduce((a,x)=>a+Number(x.dataset.seconds),0).toFixed(2)+' 秒';form.querySelector('[data-group-refs]').disabled=form.elements.mode.value!=='REF2VA';};form.addEventListener('change',update);update();
   form.onsubmit=e=>{e.preventDefault();guarded(async()=>{const f=new FormData(form);await api(base+'/generation-groups',{revision:p.generation_groups.revision,production_revision:p.revision,group:{id:gid,title:f.get('title'),reason:f.get('reason'),edit_ids:f.getAll('edit_ids'),mode:f.get('mode'),reference_targets:f.getAll('reference_targets')}},'PUT');close();await refresh(true);toast('已保存生成分組。');});};return;
  }
  if(action==='generate-prompt'){
   b.disabled=true;b.textContent='正在提交提示詞工作…';
   try{await api(base+'/jobs',{capability:'h3_video_prompt',target_id:id});await refresh(true);toast('整組提示詞已提交，會沿用已設定的創作引擎。');}catch(error){b.disabled=false;b.textContent='生成整組 H3 提示詞';throw error;}return;
  }
  if(action==='review'||action==='prompt'){
   const candidate=action==='review',value=candidate?r.job.result:r.prompt;
   modal(candidate?'檢視新版整組提示詞':'修改整組提示詞',`<p>檢查每個 [Shot]、切鏡時間、對白及圖片用途。切點標記係目標，仍需看片確認。</p>${(value.frame_issues||[]).map(x=>`<p class="note">${esc(x)}</p>`).join('')}<form id="group-prompt-form"><textarea name="text" rows="18" ${candidate?'readonly':''}>${esc(value.text)}</textarea><button type="submit" class="primary" ${candidate&&r.job.stale?'disabled':''}>${candidate?'採用整組提示詞':'儲存提示詞'}</button></form>`,true);
   const form=document.querySelector('#group-prompt-form');form.onsubmit=e=>{e.preventDefault();guarded(async()=>{if(candidate)await api(base+'/generation-groups/adopt/'+r.job.id,{revision:p.generation_groups.revision});else await api(base+'/generation-groups/'+id+'/prompt',{revision:p.generation_groups.revision,source_hash:r.source_hash,text:form.elements.text.value},'PUT');close();await refresh(true);toast('已保存整組提示詞。');});};return;
  }
  if(action==='boundaries'){
   const t=p.video_renders.takes.find(t=>t.id===id),rows=t.mapping.boundaries;
   modal('核對成片實際切點',`<video controls preload="metadata" src="${esc(t.video_url)}" style="width:100%;max-height:380px"></video><p>逐次看片核對新畫面出現嘅時間。下方初值係${t.mapping.status==='planned'?'預定切點，未經驗證':'上次人工紀錄'}。若少咗鏡或錯序，應重新生成或逐鏡剪接，唔好確認虛構切點。</p><form id="group-boundaries-form">${rows.map((x,i)=>`<label>${i+1}. ${esc(x.edit_id)} · 結束秒數<input type="number" name="end" step="0.001" min="0.001" max="${t.result.duration}" value="${x.end}" required></label>`).join('')}<label>實際畫面與連續性觀察<textarea name="note" required></textarea></label><button class="primary" type="submit">保存我觀察到嘅切點</button></form>`,true);
   const form=document.querySelector('#group-boundaries-form');form.onsubmit=e=>{e.preventDefault();guarded(async()=>{const f=new FormData(form);let start=0;const boundaries=f.getAll('end').map((value,i)=>{const end=Number(value),entry={edit_id:rows[i].edit_id,start,end};start=end;return entry;});await api(base+'/generation-groups/takes/'+id+'/boundaries',{source_hash:t.source_hash,boundaries,note:f.get('note')});close();await refresh(true);toast('已保存人工切點觀察；匯出會保留呢份紀錄。');});};
  }
 });});
}
