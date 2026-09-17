import {referenceDemandMarkup} from './video-workflow.js';
import {boardItems,boardTask,renderBoardNext} from './storyboard-next.js';
import {supportsProvider} from './provider-profile.js';
import {renderAnchorUsage} from './storyboard-usage.js';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const button=(text,action,sid,id='',disabled=false)=>`<button type="button" data-board-action="${action}" data-scene="${esc(sid)}" data-id="${esc(id)}" ${disabled?'disabled':''}>${text}</button>`;
const image=a=>a?`<img loading="lazy" src="/api/assets/${esc(a.id)}/image" alt="分鏡候選畫面">`:'';
export function imagePlanMarkup(panel){
 const p=panel.image_plan;if(!p)return '';
 return `<div class="note" data-image-need-plan><strong>${esc(p.mode)} · ${p.mode==='REF2VA'?'本鏡身份／外觀參考':p.mode==='FL2VA'?'來源首幀＋尾幀':'只需來源首幀'}</strong><p>${esc(p.reason)}</p>${referenceDemandMarkup(panel.reference_demands||p.reference_demands,p)}<p>同一 continuous Shot；圖片數量不代表剪接或 Generation Segment 數量。目前此來源由一段生成。</p>${(p.unresolved_constraints||[]).map(x=>`<p class="notice">尚未可執行：${esc(x)}</p>`).join('')}${panel.planning_notes?.length?`<details><summary>文字演出／規劃 notes · 不生圖、不需逐張批准</summary>${panel.planning_notes.map(x=>`<p>${esc(x)}</p>`).join('')}</details>`:''}</div>`;
}
export function renderStoryboard(p){
 const scenes=p.storyboard?.scenes||[];
 return `<section id="visual-storyboard" class="panel visual-storyboard"><div class="panel-header"><div><h2>分鏡畫面 · 跟剪接次序睇畫面</h2><p>先決定生成需要，再準備必要圖片。普通 continuous shot 預設只需首幀；動作節點保留為文字。</p></div></div>${renderBoardNext(p)}${scenes.map(s=>{
 const j=s.job,active=['queued','running','awaiting_input'].includes(j?.state),anchors=s.panels.flatMap(p=>p.anchors),others=(s.candidates||[]).filter(c=>c.usable&&!c.adopted&&c.id!==j?.id);
 return `<details data-storyboard-scene="${esc(s.scene_id)}" ${scenes.length===1||!s.ready?'open':''}><summary>${esc(s.title)} · ${s.ready?(anchors.length?'圖板已逐格批准':'參考需求已就緒'):s.stale?'分鏡已更新，請重新安排':s.adopted?anchors.filter(a=>a.ready).length+'／'+anchors.length+' 個畫面已審閱':'待安排視覺圖板'}</summary><p>${esc(s.summary)}</p><div class="actions">${button(active?'圖板安排處理中…':s.adopted?'重新判斷用圖需要':'由導演安排所需圖片','plan',s.scene_id,'',active)}${s.adopted&&anchors.length?button('補齊缺少圖片','batch',s.scene_id,'',s.stale||!!s.unresolved_constraints?.length):''}${s.ready?'<button data-action="navigate" data-page="video">安排 H3 生成分組 →</button>':''}</div>
 ${j?`<p>${esc({queued:'圖板安排已排隊',running:'正在安排每格畫面',awaiting_input:'等候人工提供結果',succeeded:j.adopted?'圖板安排已採用':'圖板安排待檢視',failed:'安排失敗',interrupted:'工作中斷'}[j.state]||j.state)}${j.error?' · '+esc(j.error):''}</p><div class="actions">${j.state==='succeeded'&&!j.adopted?button('檢視圖板安排','plan-review',s.scene_id,j.id):''}<button data-action="job-detail" data-id="${esc(j.id)}">工作記錄</button></div>`:''}
 ${others.length?`<p class="notice">另有 ${others.length} 個較早嘅成功方案仍然可用；最新一次失敗唔會蓋過佢，可直接檢視及採用。</p><div class="actions">${others.map(c=>button('檢視較早方案 · '+new Date(c.created).toLocaleString('zh-HK'),'plan-review',s.scene_id,c.id)).join('')}</div>`:''}
 ${s.stale?'<p class="notice">來源已改動，舊圖板及批准紀錄保留作追查。重新安排後再審閱。</p>':''}
 <div class="storyboard-grid">${s.panels.map((panel,i)=>`<article class="storyboard-panel"><div class="eyebrow">${i+1} · 剪接 ${panel.edit?panel.edit.planned_edit_in+'–'+panel.edit.planned_edit_out:'已變更'} 秒</div><h3>${esc(panel.title)}</h3>${imagePlanMarkup(panel)}<details><summary>這次切鏡的原因</summary><p>${esc(panel.reason)}</p></details>${panel.anchors.map(a=>`<div class="storyboard-anchor" data-board-anchor="${esc(a.id)}">${a.asset?image(a.asset):'<div class="storyboard-missing">尚待製作畫面<br><small>構圖計劃已保存</small></div>'}<strong>${a.time} 秒 · ${a.ready?'已逐格批准':a.review?.verdict==='revise'?'需要修訂':a.asset?'待逐格審閱':'待製作畫面'}</strong><p>${esc(a.purpose)}</p>${renderAnchorUsage(a)}<details><summary>畫面描述與凍結狀態</summary><p class="muted">${esc(a.frame?.description||'此畫面已不在目前方案')}</p>${(a.frame?.state||[]).map(x=>`<p>${esc(x.entity_id)} · ${esc(x.key)}：${esc(x.value)}</p>`).join('')}</details><div class="actions">${a.asset?button('檢視／審閱這格','review',s.scene_id,a.id,s.stale):''}${a.frame?`<button data-action="generate" data-target="${esc(a.frame_id)}" data-force="${!!a.asset}">${a.asset?'生成另一版本':'準備此畫面'}</button><button data-action="upload" data-target="${esc(a.frame_id)}">匯入</button>`:''}</div>${a.review?.note?`<p>審閱備註：${esc(a.review.note)}</p>`:''}</div>`).join('')}</article>`).join('')}</div></details>`;
 }).join('')}<p class="muted">每格係一個指定時刻嘅畫面。批准圖板後，H3 仍需實際看片核對切鏡、表演及連戲。匯出製作資料會附上可開啟嘅圖板。</p></section>`;
}
export function renderBoardPlan(p,s,j){
 return `<p>${esc(j.result.summary)}</p><div class="storyboard-grid">${j.result.panels.map((panel,i)=>{const shot=p.production.shots.find(x=>x.id===s.panels.find(x=>x.edit_id===panel.edit_id)?.shot_id)||p.production.shots.find(x=>x.id===p.production.edit_plan?.find(e=>e.id===panel.edit_id)?.shot_id)||p.production.shots.find(x=>'source_'+x.id===panel.edit_id);return `<article><h3>${i+1}. ${esc(shot?.title||panel.edit_id)}</h3><p>${esc(panel.reason)}</p>${imagePlanMarkup(panel)}${panel.anchors.map(a=>`<p><strong>${a.time} 秒 · ${a.reuse_frame_id?'沿用既有分鏡畫面':'新增指定時刻畫面'}</strong></p><p>${esc(a.purpose)}</p><p>${esc(a.description)}</p>`).join('')}</article>`;}).join('')}</div><p>採用會一併保存所示 I2VA／FL2VA／REF2VA 來源模式及必要圖片清單；舊圖及紀錄保留。文字 notes 不會生圖或要求逐格批准。安排本身未生成圖片。</p>${j.stale?'<p class="notice">來源已更新，請重新安排。</p>':''}<button id="board-adopt" class="primary" ${j.stale||j.adopted?'disabled':''}>採用圖板安排</button>`;
}
export function installStoryboard({getProject,getSettings,api,modal,close,refresh,guarded,toast,navigate=async()=>{}}){

 function openReview(p,scene,id){
  const sid=scene.scene_id,base='/projects/'+p.id;
   const panel=scene.panels.find(x=>x.anchors.some(a=>a.id===id)),a=panel?.anchors.find(a=>a.id===id);if(!a?.asset)throw Error('請先準備畫面。');
   const items=boardItems(p,sid),index=items.findIndex(x=>x.anchor.id===id),near=items.slice(Math.max(0,index-1),index+2);
   const task=boardTask(p,sid);
   modal('審閱分鏡畫面 · 第 '+(index+1)+'／'+items.length+' 格',`<p class="board-review-progress" tabindex="-1" data-initial-focus>${esc(scene.title)} · 已確認 ${task.approved}／${items.length} 格</p><div class="storyboard-neighbours">${near.map(x=>`<figure class="${x.anchor.id===id?'is-current':''}">${image(x.anchor.asset)}<figcaption>${esc(x.panel.title)} · ${x.anchor.time} 秒${x.anchor.id===id?'（目前）':''}</figcaption></figure>`).join('')}</div><h3>${esc(panel.title)}</h3><p>${a.time} 秒 · ${esc(a.purpose)}</p><form id="board-review"><label class="${a.candidates.length===1?'board-single-version':''}">圖片版本<select name="asset_id">${a.candidates.map((x,i)=>`<option value="${esc(x.id)}" ${x.id===a.asset.id?'selected':''}>圖片 ${i+1} · ${x.status==='approved'?'素材已批准':'候選待審'}</option>`).join('')}</select></label><div data-board-image></div><details><summary>構圖描述與剪接原因</summary><p>${esc(a.frame.description)}</p><p>${esc(panel.reason)}</p></details><div data-board-findings></div><p>檢查畫面有冇傳達呢一格嘅資訊，以及相鄰鏡頭嘅視線、左右位置、手／道具狀態同揭示次序。</p><label>審閱備註（可留空）<textarea name="note" rows="3">${esc(a.review?.note||'')}</textarea></label><div class="actions board-review-actions"><button type="submit" name="verdict" value="approved" class="primary">批准這格及圖片，繼續下一格</button><button type="submit" name="verdict" value="revise">記錄需修改，繼續下一格</button></div></form>`,true);
   const form=document.querySelector('#board-review');const update=()=>{const asset=p.assets.find(x=>x.id===form.elements.asset_id.value);form.querySelector('[data-board-image]').innerHTML=image(asset);form.querySelector('[data-board-findings]').innerHTML=asset?.review?`<p>圖片審查：${esc({pass:'通過',revise:'建議修改',uncertain:'未能確認'}[asset.review.verdict]||asset.review.verdict)}</p><ul>${(asset.review.issues||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'<p>此版本尚無 AI 圖片審查結果；你的人工判斷會另行保存。</p>';};form.elements.asset_id.onchange=update;update();
   let saving=false;
   form.onsubmit=e=>{e.preventDefault();const verdict=e.submitter?.value;if(!verdict||saving)return;guarded(async()=>{
    if(getProject()?.id!==p.id)throw Error('作品已切換，請重新開啟審閱。');
    const asset=a.candidates.find(x=>x.id===form.elements.asset_id.value);if(!asset)throw Error('圖片版本已更新，請重新開啟審閱。');
    saving=true;const buttons=[...form.querySelectorAll('button[type="submit"]')];buttons.forEach(b=>b.disabled=true);
    try{
     await api(base+'/storyboard/'+sid+'/review/'+id,{revision:p.storyboard.revision,token:asset.token,asset_id:asset.id,verdict,note:form.elements.note.value});
     close();await refresh(true);if(getProject()?.id!==p.id)return;
     const fresh=getProject(),remaining=boardTask(fresh),next=remaining.pending.find(x=>x.anchor.id!==id);
     toast(verdict==='approved'?'此格已確認並保存。':'已保存修改要求，原圖保留。');
     if(next)openReview(fresh,next.scene,next.anchor.id);
     else modal(remaining.complete?'分鏡畫面已全部確認':'今次可審閱的畫面已處理',`<p>${remaining.complete?'可以返回影片製作，繼續準備 H3 影片。':'修改要求及已確認畫面已保存。缺圖或需修改的畫面會留在分鏡頁。'}</p>${remaining.complete?'<button type="button" class="primary" data-action="navigate" data-close-modal="true" data-page="video">繼續影片製作 →</button>':renderBoardNext(fresh)}<button type="button" data-action="close">返回分鏡畫面</button>`);
    }finally{saving=false;buttons.forEach(b=>b.disabled=false);}
   });};

 }
 document.addEventListener('click',e=>{const b=e.target.closest('[data-board-action]');if(!b||b.disabled)return;guarded(async()=>{
  const p=getProject(),sid=b.dataset.scene,id=b.dataset.id,action=b.dataset.boardAction,base='/projects/'+p.id;
  const scene=p.storyboard.scenes.find(s=>s.scene_id===sid);if(!scene)throw Error('場景已更新，請重新開啟。');
  if(action==='continue'){
   close();await navigate('shots');if(getProject()?.id!==p.id)return;
   const fresh=getProject(),task=boardTask(fresh,sid),current=task.scenes[0];
   const node=[...document.querySelectorAll('[data-storyboard-scene]')].find(el=>el.dataset.storyboardScene===sid);
   if(node){node.open=true;node.scrollIntoView({block:'start'});}
   if(task.next)openReview(fresh,task.next.scene,task.next.anchor.id);
   else if(current)toast(task.title+'，請在這場的畫面清單處理。');
   return;
  }
  if(action==='plan'){
   modal('安排視覺圖板 · '+scene.title,`<form id="board-plan"><p>先判斷每鏡嘅生成需要：預設 I2VA 只畫來源首幀；具體尾部構圖需要先選 FL2VA；需要可重用身份／外觀參考可選 REF2VA，沿用本鏡必要嘅已批准資產。普通動作寫入文字 notes。未有執行策略嘅中間硬約束會明示，唔會先叫你生圖。</p><label>補充要求（可留空）<textarea name="feedback" rows="4" placeholder="例如：需要睇清楚門底嘅手，再切返人物反應；留意視線方向。"></textarea></label><button type="submit" class="primary">開始安排圖板</button></form>`);
   const form=document.querySelector('#board-plan');form.onsubmit=e=>{e.preventDefault();guarded(async()=>{const submit=form.querySelector('button');submit.disabled=true;try{await api(base+'/jobs',{capability:'storyboard_frames',target_id:sid,feedback:form.elements.feedback.value});close();await refresh(true);toast('圖板安排已提交。');}catch(error){submit.disabled=false;throw error;}});};return;
  }
  if(action==='plan-review'){
   const attempt=(scene.candidates||[]).find(c=>c.id===id)||(scene.job?.id===id?scene.job:null);
   if(!attempt||attempt.state!=='succeeded')throw Error('請先查看工作記錄。');
   const j={...await api('/jobs/'+id),stale:attempt.stale,adopted:attempt.adopted};
   modal('檢視圖板安排',renderBoardPlan(p,scene,j),true);
   document.querySelector('#board-adopt').onclick=()=>guarded(async()=>{await api(base+'/storyboard/adopt/'+id,{revision:p.storyboard.revision,production_revision:p.revision});close();await refresh(true);toast('已採用視覺圖板，可補齊圖片。');});return;
  }
  if(action==='review'){openReview(p,scene,id);return;}
  if(action==='batch'){
   const plan=await api(base+'/storyboard/'+sid+'/batch'),settings=getSettings();if(getProject()?.id!==p.id)return;
   const providers=settings.providers.filter(x=>x.kind!=='manual'&&supportsProvider(x,'image')),preferred=settings.routing.image||settings.profile.default_provider;
   const labels={approved:'沿用已批准圖片',pending:'已有候選待審',active:'已有工作，等候／取回結果',blocked:'先批准角色／場景參考',generate:'將補圖'};
   modal('補齊圖板圖片',`<p>只提交缺少嘅畫面；每張經過既定圖片提示詞及生成流程，完成後逐格審閱。</p>${plan.items.map(i=>`<p><strong>${esc(i.name)}</strong> · ${esc(labels[i.state])}${i.missing.length?'：'+esc(i.missing.join('、')):''}</p>`).join('')}<form id="board-batch"><label>圖片服務<select name="image_provider" required>${providers.some(x=>x.id===preferred)?'':'<option value="" disabled selected>選擇圖片服務</option>'}${providers.map(x=>`<option value="${esc(x.id)}" ${x.id===preferred?'selected':''}>${esc(x.name)}</option>`).join('')}</select></label><button type="submit" class="primary" ${!plan.generate_count?'disabled':''}>開始補齊 ${plan.generate_count} 張圖片</button></form>`);
   const form=document.querySelector('#board-batch');form.onsubmit=e=>{e.preventDefault();guarded(async()=>{form.querySelector('button').disabled=true;try{const result=await api(base+'/storyboard/'+sid+'/batch',{token:plan.token,image_provider:form.elements.image_provider.value});modal('圖板補圖提交結果',result.items.map(i=>`<p>${esc(i.name)} · ${esc({queued:'已排隊',skipped:'已沿用／略過',failed:'提交失敗',submitting:'提交中斷，須核對原工作',planned:'尚未提交'}[i.state]||i.state)}${i.error?'：'+esc(i.error):''}</p>`).join(''));await refresh(true);}catch(error){form.querySelector('button').disabled=false;throw error;}});};
  }
 });});
}
