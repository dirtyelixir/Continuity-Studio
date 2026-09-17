// Image analysis proposes a draft. Only the existing identity editor saves canon.
export function bindIdentityImageAssistant({form,project,entity,asset,api,esc,providerName,available=true}){
 if(entity.kind==='voice')return;
 form.insertAdjacentHTML('afterbegin',`<section class="identity-image-assistant"><h3>按圖片反推身份設定</h3>${asset?`<div class="identity-image-source"><img src="/api/assets/${encodeURIComponent(asset.id)}/image" alt="${esc(entity.name)} · 本次反推來源"><div><p>以這張圖片修訂外觀描述與固定設定，保留已有的故事資訊。</p><button type="button" data-identity-analyse>按圖片反推</button><p class="muted">${esc(providerName)} · 只產生草稿，儲存後才會修改身份。</p></div></div>`:'<p class="muted">此資產尚未有圖片。先製作參考圖，再使用圖片反推。</p>'}<p data-identity-status role="status" class="muted"></p><div data-identity-candidate hidden></div></section>`);
 if(!asset)return;
 const root=form.querySelector('.identity-image-assistant'),start=root.querySelector('[data-identity-analyse]'),status=root.querySelector('[data-identity-status]'),preview=root.querySelector('[data-identity-candidate]');
 if(!available){start.disabled=true;status.textContent='圖片反推服務正在更新，完成後重新整理即可使用。';return;}
 let currentJob=null,requesting=false,undo=null,candidate=null,timer=null;
 const connected=()=>form.isConnected;
 const fields=()=>({description:form.elements.description.value,facts:form.elements.facts.value});
 const editable=()=>form.elements.kind?.value!=='voice';
 function message(text){status.textContent=text;}
 function showCandidate(job){
  if(job.project_id!==project.id||job.target_id!==entity.id||job.capability!=='identity_from_image'||job.input?.source_asset_id!==asset.id||job.input?.revision!==project.revision){message('這份草稿的圖片或身份版本已變更，請重新反推。');return;}
  candidate=job.result;preview.hidden=false;
  preview.innerHTML=`<h4>圖片反推草稿</h4><p class="prose">${esc(candidate.description)}</p><ul class="facts">${candidate.facts.map(f=>`<li>${esc(f)}</li>`).join('')}</ul>${candidate.uncertainties.length?`<p class="notice">需你確認</p><ul class="facts">${candidate.uncertainties.map(f=>`<li>${esc(f)}</li>`).join('')}</ul>`:''}<p class="muted">先與下方原設定比較。「套用至編輯欄位」會替換描述與固定設定，名稱及資產分類維持原值。</p><div class="actions"><button type="button" data-identity-apply>套用至編輯欄位</button><button type="button" data-identity-undo hidden>復原套用</button></div>`;
  const apply=preview.querySelector('[data-identity-apply]'),restore=preview.querySelector('[data-identity-undo]');
  apply.onclick=()=>{
   if(!editable()){message('聲音資產不使用圖片身份設定。');return;}
   undo=fields();form.elements.description.value=candidate.description;form.elements.facts.value=candidate.facts.join('\n');apply.disabled=true;restore.hidden=false;message('草稿已套用至下方欄位，尚未儲存。你可以繼續修改或復原。');
  };
  restore.onclick=()=>{if(!undo)return;form.elements.description.value=undo.description;form.elements.facts.value=undo.facts;undo=null;apply.disabled=false;restore.hidden=true;message('已復原套用前的編輯內容。');};
  message('草稿已完成。請檢視圖片與原設定，再決定是否套用。');
 }
 async function poll(){
  if(!connected()||!currentJob)return;
  try{
   const job=await api('/jobs/'+currentJob);if(!connected())return;
   if(job.state==='succeeded'){start.disabled=false;showCandidate(job);return;}
   if(['failed','cancelled','interrupted','awaiting_input'].includes(job.state)){
    start.disabled=false;message(job.state==='awaiting_input'?'目前使用人工服務。請到「活動與版本」提交這份工作的結果，再重新開啟身份設定。':job.error||'反推未完成，可以再次按圖片反推。');return;
   }
   message(job.state==='queued'?'圖片反推已排隊，完成後會在這裡顯示草稿。':'正在讀取圖片並整理身份設定…');
   timer=setTimeout(poll,1800);
  }catch(error){if(connected()){start.disabled=false;message('暫時無法取得結果：'+error.message+'。重新按下可接回目前工作。');}}
 }
 start.onclick=async()=>{
  if(requesting||!editable()){if(!editable())message('聲音資產不使用圖片身份設定。');return;}
  requesting=true;start.disabled=true;preview.hidden=true;message('正在建立圖片反推工作…');clearTimeout(timer);
  try{
   const reply=await api('/projects/'+project.id+'/jobs',{capability:'identity_from_image',target_id:entity.id,source_asset_id:asset.id});
   currentJob=reply.job.id;if(connected())await poll();
  }catch(error){if(connected()){start.disabled=false;message(error.message);}}
  finally{requesting=false;}
 };
 // Closing the editor stops local polling, not the durable analysis job.
 const previous=(project.jobs||[]).find(j=>j.capability==='identity_from_image'&&j.target_id===entity.id&&j.input?.source_asset_id===asset.id&&j.input?.revision===project.revision&&['queued','running','succeeded','awaiting_input'].includes(j.state));
 if(previous){currentJob=previous.id;start.disabled=true;poll();}
}
