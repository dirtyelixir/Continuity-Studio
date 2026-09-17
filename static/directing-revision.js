// Current adopted sources only. A proposal's advice belongs to its own dialog.
export function directingRevisionData(project,chapterId=''){
 const plan=project.production,chapter=chapterId?(plan?.chapters||[]).find(c=>c.id===chapterId):null;
 if(chapterId&&!chapter)throw Error('找不到目前採用的章節。');
 const sceneIds=new Set(chapter?.scene_ids||(plan?.scenes||[]).map(s=>s.id));
 const shots=(plan?.shots||[]).filter(s=>sceneIds.has(s.scene_id)),shotIds=new Set(shots.map(s=>s.id));
 const records=(project.directing?.scenes||[]).filter(s=>sceneIds.has(s.scene_id)&&s.review);
 const reviews=[...new Map(records.map(s=>[s.review.job_id,s.review.review])).values()];
 const items=[],seen=new Set();
 function add(item){const key=JSON.stringify([item.reason,item.recommendation]);if(!item.recommendation?.trim()||seen.has(key))return;seen.add(key);items.push(item);}
 for(const review of reviews){
  for(const issue of review.issues||[]){
   if(chapterId&&!issue.shot_ids?.length&&(review.coverage||[]).some(c=>!sceneIds.has(c.scene_id)))continue;
   if(issue.shot_ids?.length&&!issue.shot_ids.some(id=>shotIds.has(id)))continue;
   const names=(issue.shot_ids||[]).filter(id=>shotIds.has(id)).map(id=>shots.find(s=>s.id===id)?.title||id);
   add({title:names.join('、')||'整體劇情表達',reason:issue.reason,recommendation:issue.recommendation});
  }
  for(const c of review.coverage||[])if(sceneIds.has(c.scene_id)&&c.verdict!=='pass'){
   const scene=plan.scenes.find(s=>s.id===c.scene_id);
   add({title:(scene?.title||c.scene_id)+' · '+c.beat_id,reason:c.reason,recommendation:c.recommendation});
  }
 }
 const draft=(project.story_chapters||[]).find(c=>c.id===chapterId);
 const kind=chapterId?draft?.source_kind:project.source_kind;
 if(chapterId&&!draft)throw Error('找不到章節來源，請重新載入作品。');
 return {items,chapterId,capability:kind&&kind!=='idea'?'storyboard':'narrative',
  notes:items.map((i,n)=>`${n+1}. ${i.title}\n問題：${i.reason||''}\n建議：${i.recommendation}`).join('\n\n'),
  sourceKey:JSON.stringify([project.revision,project.directing?.approval_source_hash,project.brief_revision,draft||null]),
  reviewState:project.directing?.current_review?.state};
}
export function directingRevisionForm(project,data,label,esc){
 const chapters=project.production?.chapters||[];
 const stateMessage={queued:'審查正在排隊',running:'審查仍在進行',deferred:'最新版本正在等候審查',failed:'審查未能完成',interrupted:'審查已中斷',awaiting_input:'正在等候人工審查'}[data.reviewState]||'目前版本未有具體修訂建議';
 return `<form id="current-directing-revision-form">${project.source_kind==='outline'?`<label>修訂章節<select name="chapter_id">${chapters.map(c=>`<option value="${esc(c.id)}" ${c.id===data.chapterId?'selected':''}>${esc(c.title)}</option>`).join('')}</select></label>`:''}<h3>建議修改哪些內容</h3>${data.items.length?`<p>以下建議來自目前方案的審查，已自動帶入修訂要求。可直接按「按以上建議開始修訂」。</p>${data.items.map((item,i)=>`<div class="note"><strong>${i+1}. ${esc(item.title)}</strong><p><b>問題：</b>${esc(item.reason)}</p><p><b>建議做法：</b>${esc(item.recommendation)}</p></div>`).join('')}`:`<p class="notice">${esc(stateMessage)}，未能列出可套用的修改建議。你可等候審查結果，或在下方填寫想調整的內容。</p>`}<label>補充修訂要求（${data.items.length?'選填':'未有建議時需填寫'}）<textarea name="feedback" rows="3" placeholder="${data.items.length?'可留空，系統會按上面建議修訂。':'想修改哪些內容？'}" ${data.items.length?'':'required'}></textarea></label><p class="muted">由 ${esc(label)} 修訂目前採用方案，保留來源劇情及對白。完成後會自動審查，新方案由你決定是否採用。</p><div class="modal-footer"><button type="button" data-action="close">返回</button><button class="primary" type="submit">${data.items.length?'按以上建議開始修訂':'按補充要求開始修訂'}</button></div></form>`;
}
export async function openCurrentDirectingRevision({pid,chapterId='',getProject,api,modal,close,refresh,guarded,toast,esc,providerLabel,showProposalProgress,select}){
 const frozen=await api('/projects/'+pid);if(getProject()?.id!==pid)return;
 const chapters=frozen.production?.chapters||[];
 if(frozen.source_kind==='outline'&&!chapterId)chapterId=chapters.find(c=>directingRevisionData(frozen,c.id).items.length)?.id||chapters[0]?.id||'';
 if(frozen.source_kind==='outline'&&!chapterId)throw Error('請先建立並採用章節方案。');
 function render(extra=''){
  const data=directingRevisionData(frozen,chapterId);
  modal('修訂劇情表達方案',directingRevisionForm(frozen,data,providerLabel(data.capability),esc));
  const form=select('#current-directing-revision-form');form.elements.feedback.value=extra;
  if(form.elements.chapter_id)form.elements.chapter_id.onchange=e=>{chapterId=e.target.value;render(form.elements.feedback.value);};
  form.onsubmit=e=>{e.preventDefault();const feedback=form.elements.feedback.value||'';guarded(async()=>{
   if(!data.notes&&!feedback.trim())throw Error('目前未有修訂建議，請先填寫想調整的內容。');
   const fresh=await api('/projects/'+pid);
   if(directingRevisionData(fresh,data.chapterId).sourceKey!==data.sourceKey)throw Error('方案或章節來源已更新，請重新開啟修訂，取得最新建議。');
   const result=await api('/projects/'+pid+'/jobs',{capability:data.capability,target_id:data.chapterId,feedback:'修訂目前採用方案。保留來源劇情、對白及未涉及的內容，修正以下導演問題：\n'+data.notes+'\n補充要求：'+feedback});
   if(getProject()?.id!==pid||select('#current-directing-revision-form')!==form)return;
   close();await refresh(true);if(getProject()?.id===pid&&result.job?.id)await showProposalProgress(pid,result.job.id);
   toast('已帶入建議並開始修訂，完成後會自動審查。');
  });};
 }
 render();
}
