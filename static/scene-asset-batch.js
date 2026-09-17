import {supportsProvider} from './provider-profile.js';
const labels={generate:'將製作',approved:'沿用已批准圖片',pending:'已有候選待審',active:'已有工作，先等候／取回結果'};
export async function openSceneAssetBatch({pid,sceneId,settings,api,modal,close,refresh,guarded,esc,isCurrent}){
 const plan=await api('/projects/'+pid+'/scenes/'+sceneId+'/asset-batch');
 if(!isCurrent())return;
 const providers=settings.providers.filter(p=>p.kind!=='manual'&&supportsProvider(p,'image'));
 const preferred=settings.routing.image||settings.profile.default_provider;
 modal('按場景批量製作 · '+plan.scene_title,`<p>依此場景的角色、場地及道具需求，補齊所需圖片。公共資產按需沿用；已批准、已有候選待審或正在製作的項目會略過。</p><div class="scene-batch-items">${plan.items.map(i=>`<div class="scene-batch-row"><strong>${esc(i.name)}</strong><span>${esc(labels[i.state]||i.reason)}</span></div>`).join('')}</div><form id="scene-asset-batch-form"><label>圖片生成服務<select name="image_provider" required>${providers.some(p=>p.id===preferred)?'':'<option value="" selected disabled>請選擇圖片生成服務</option>'}${providers.map(p=>`<option value="${esc(p.id)}" ${p.id===preferred?'selected':''}>${esc(p.name)}</option>`).join('')}</select></label><p class="muted">預計製作 ${plan.generate_count} 項。角色會製作四視圖；各項依序排隊，完成後仍需審閱採用。</p><div class="modal-footer"><button type="button" data-action="close">取消</button><button type="submit" class="primary" ${!plan.generate_count||!providers.length?'disabled':''}>開始製作 ${plan.generate_count} 項資產</button></div><p data-batch-status role="status"></p></form>`);
 const form=document.querySelector('#scene-asset-batch-form');
 form.onsubmit=e=>{e.preventDefault();const provider=form.elements.image_provider.value;const submit=form.querySelector('[type=submit]');submit.disabled=true;form.querySelector('[data-batch-status]').textContent='正在提交批量工作…';guarded(async()=>{
  try{
   const result=await api('/projects/'+pid+'/scenes/'+sceneId+'/asset-batch',{token:plan.token,image_provider:provider});
   if(form.isConnected&&isCurrent()){
    const names={queued:'已排隊',skipped:'已略過',failed:'未能建立工作',submitting:'提交中斷，需核對原工作',planned:'尚未提交'};
    modal(result.state==='complete'?'場景資產製作已提交':'批量提交未完成',`<p>${result.state==='complete'?'已建立的工作會按佇列執行；未能建立的項目可重新開啟清單處理。':'提交曾中斷；已保存各項狀態，請先核對提交中的原工作。'}</p>${result.items.map(i=>`<div class="scene-batch-row"><strong>${esc(i.name)}</strong><span>${esc(names[i.state]||i.state)}${i.error?' · '+esc(i.error):''}</span></div>`).join('')}<div class="modal-footer"><button data-action="close" class="primary">完成</button></div>`);
   }
   await refresh(true);
  }catch(error){if(form.isConnected){submit.disabled=false;form.querySelector('[data-batch-status]').textContent=error.message;}throw error;}
 });};
}
