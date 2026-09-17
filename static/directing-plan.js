const labels={human_approved:'已人工批准',pass:'通過',revise:'需要修訂',uncertain:'未能判斷',legacy:'已有分鏡 · 尚未補充拍攝意圖',unreviewed:'拍攝意圖已保存 · 待審查',missing:'待審查',queued:'等待審查',running:'正在審查',awaiting_input:'等待人工審查',failed:'審查失敗',interrupted:'審查中斷',cancelled:'審查已取消'};
export function directingReviewMarkup(review,esc){
 if(!review)return '';
 return `<div class="note"><strong>導演內容審查 · ${esc(labels[review.verdict]||review.verdict)}</strong><p>${esc(review.summary)}</p>${review.coverage.map(c=>`<details><summary>${esc(c.scene_id)} / ${esc(c.beat_id)} · ${esc(labels[c.verdict])}</summary><p>要傳達：${esc(c.required_communication)}</p><p>承載鏡頭：${c.shot_ids.map(esc).join('、')}</p><blockquote>${esc(c.evidence)}</blockquote><p>${esc(c.reason)}</p><p>${esc(c.recommendation)}</p></details>`).join('')}${review.issues.map(i=>`<div class="note"><strong>${esc(i.code)}</strong><p>${esc(i.reason)}</p><blockquote>${esc(i.evidence)}</blockquote><p>${esc(i.recommendation)}</p></div>`).join('')}</div>`;
}
export function shotIntentMarkup(s,esc){
 if(!s.direction)return '<p class="muted">已有分鏡 · 尚未補充拍攝意圖</p>';
 return `<div class="note"><strong>鏡頭目的：${esc(s.shot_purpose)}</strong><p>${esc(s.framing)} · ${esc(s.direction.visual_carrier)}</p><p>可讀性：${esc(s.direction.readability)}</p><p>切入：${esc(s.direction.cut_in_reason)}<br>切出：${esc(s.direction.cut_out_reason)}</p><p>接下一鏡：${esc(s.direction.next_shot_relationship)}</p></div>`;
}
export function sceneEditSequenceMarkup(plan,sceneId,esc){
 const shots=new Map((plan.shots||[]).filter(s=>s.scene_id===sceneId).map(s=>[s.id,s]));
 const edits=(plan.edit_plan||[]).filter(e=>shots.has(e.shot_id));
 if(!edits.length)return '<p class="muted">尚未保存這場戲的剪接次序；起始幀只代表各來源鏡頭，未能展示切鏡安排。</p>';
 const sourceCount=new Set(edits.map(e=>e.shot_id)).size;
 return `<div class="scene-edit-sequence"><h3>畫面如何接起來</h3><p>${sourceCount} 個來源鏡頭 · ${edits.length} 段剪接取用 · ${edits.reduce((n,e)=>n+e.planned_edit_out-e.planned_edit_in,0).toFixed(2)} 秒預定畫面</p><p class="muted">按觀眾觀看次序排列。同一鏡頭可取用多段；每張起始幀供該來源鏡頭生成使用。以下時間與切點仍待實際影片核對。</p><ol>${edits.map(e=>{const s=shots.get(e.shot_id);return `<li class="note"><strong>${esc(s.title)} · ${esc(s.framing)}</strong><p>畫面停留 ${(e.planned_edit_out-e.planned_edit_in).toFixed(2)} 秒 · 取用來源 ${esc(e.planned_edit_in)}–${esc(e.planned_edit_out)} 秒</p><p>觀眾要看見：${esc(s.shot_purpose||s.action||'尚未記錄')}</p><details><summary>切點理由與連續性</summary><p>切入：${esc(e.cut_in_reason)}<br>切出／接下一畫面：${esc(e.cut_out_reason)}</p><p>切點連續性：${esc(e.continuity_note)}</p></details></li>`}).join('')}</ol></div>`;
}
export function directorPlanMarkup(plan,esc,candidates=new Map()){
 if(candidates.size)return plan.scenes.map(sc=>candidates.has(sc.id)?`<details class="note" ${plan.scenes.length===1?'open':''}><summary>${esc(sc.title)} · 劇情節拍與拍攝意圖</summary><p>${esc(candidateLabel(candidates.get(sc.id)))}</p><p>新方案已記錄這場戲的拍攝意圖。目前仍沿用已採用的舊分鏡；審閱並採用新方案後，這裡會顯示新版內容。</p><button data-action="proposal" data-id="${esc(candidates.get(sc.id).job.id)}">審閱已生成方案</button></details>`:directorPlanMarkup({...plan,scenes:[sc]},esc)).join('');
 return plan.scenes.map(sc=>`<details class="note" ${plan.scenes.length===1?'open':''}><summary>${esc(sc.title)} · 劇情節拍與拍攝意圖</summary>${sceneEditSequenceMarkup(plan,sc.id,esc)}${sc.director_plan?`<p>揭示次序：${sc.director_plan.reveal_order.map(esc).join(' → ')}</p>${sc.director_plan.beats.map(b=>`<div class="note"><strong>${esc(b.id)} · ${esc(b.event)}</strong><p>之前知道：${esc(b.intent.audience_knowledge_before)}</p><p>必須明白：${esc(b.intent.audience_must_learn)}</p><p>情緒：${esc(b.intent.emotional_target)}</p><p>視覺焦點：${esc(b.intent.visual_priority)}</p><p>揭示安排：${esc(b.intent.reveal_strategy)}</p><p>畫面安排：${esc(b.intent.coverage_strategy)}</p></div>`).join('')}`:'<p>這場已有分鏡，但舊方案未另外記錄觀眾要明白甚麼、感受到甚麼，以及用哪些畫面表達。原有分鏡仍保留；建立並採用修訂方案後可補充這些資料。</p>'}</details>`).join('');
}
export function editPlanMarkup(plan,esc,editable=false){
 const edits=plan.edit_plan||[];if(!edits.length)return '';
 const total=edits.reduce((n,e)=>n+e.planned_edit_out-e.planned_edit_in,0);
 return `<h3>預定剪接 · ${total.toFixed(2)} 秒</h3><p class="muted">入出點按來源素材時間計算，生成後需看片確認。此表尚未裁剪影片。</p><div style="overflow-x:auto"><table><thead><tr><th>段落／來源鏡頭</th><th>生成時長</th><th>預定取用範圍</th><th>成片時長</th>${editable?'<th>調整</th>':''}</tr></thead><tbody>${edits.map((e,i)=>{const s=plan.shots.find(s=>s.id===e.shot_id);return `<tr><td>${i+1}. ${esc(s?.title||e.shot_id)}</td><td>${esc(s?.duration)} 秒</td><td>${esc(e.planned_edit_in)}–${esc(e.planned_edit_out)} 秒</td><td>${(e.planned_edit_out-e.planned_edit_in).toFixed(2)} 秒</td>${editable?`<td><button data-action="edit-cut" data-id="${esc(e.id)}">修改</button> <button data-action="reuse-cut" data-id="${esc(e.id)}">再取一段</button> ${i?`<button data-action="move-cut" data-id="${esc(e.id)}">上移</button>`:''} <button data-action="remove-cut" data-id="${esc(e.id)}">移除</button></td>`:''}</tr>`}).join('')}</tbody></table></div>`;
}
export function currentDirectingReviewMarkup(p,esc){
 const r=p.directing?.current_review;
 if(!r)return '';
 const approved=(p.directing?.scenes||[]).filter(s=>s.status!=='legacy').every(s=>s.status==='human_approved'||s.status==='pass')&&(p.directing?.scenes||[]).some(s=>s.status==='human_approved');
 const human=approved?'<p><strong>已人工批准此方案，可以繼續製作。AI 審查意見仍保留。</strong></p>':'';
 const messages={queued:'導演內容審查已自動排隊，毋須再次提交。',running:'正在自動審查導演內容，完成後會顯示結果。',deferred:'正等待上一版本審查結束，之後會自動審查最新方案。',awaiting_input:'審查服務目前設為人工處理，工作已保存；請提交人工審查結果或在服務商設定選擇自動服務。',failed:'導演內容審查未能完成，請查看原因後重試。',interrupted:'導演內容審查已中斷，請查看原工作後重試。',cancelled:'導演內容審查已取消，可在需要時重新審查。',missing:'拍攝意圖已保存，尚未有審查工作。'};
 const text=approved?'AI 審查意見會保留作參考；你的人工批准已生效。':messages[r.state]||(r.result?.verdict==='pass'?'導演內容審查已通過。':r.result?.verdict==='revise'?'導演內容審查完成：需要修訂方案。':'導演內容審查完成：需要判斷。');
 return `<div class="notice" role="status">${human}<strong>${esc(text)}</strong>${r.progress?`<p>${esc(r.progress.label)} · 已保存 ${Number(r.progress.completed)||0}／${Number(r.progress.total)||0} 批</p>`:''}${r.error?`<p>${esc(r.error)}</p>`:''}<div class="actions">${humanDirectingAction(p)}</div>${r.job_id?`<p><button data-action="job-detail" data-id="${esc(r.job_id)}">查看審查進度與結果</button></p>`:''}</div>`;
}
function humanDirectingAction(p){
 const human=p.directing?.approval_source_hash&&(p.directing?.scenes||[]).some(s=>!['pass','legacy','human_approved'].includes(s.status))?'<button data-action="human-directing" class="primary">人工批准此方案</button>':'';
 return human;
}
function currentDirectingReviewAction(p,esc){

 const state=p.directing?.current_review?.state;
 if(p.directing?.current_review?.resumable)return `<button data-action="resume-directing" data-id="${esc(p.directing.current_review.job_id)}">接續導演內容審查</button>`;
 if(['queued','running','deferred','awaiting_input'].includes(state))return '';
 return `<button data-action="directing-qc">${['failed','interrupted','cancelled'].includes(state)?'重試導演內容審查':state==='succeeded'?'重新審查導演內容':'審查劇情表達'}</button>`;
}
function directingSceneLabel(s,p){
 if(s.status==='unreviewed'){
  const state=p.directing?.current_review?.state;
  return '拍攝意圖已保存 · '+({queued:'審查已排隊',running:'正在自動審查',deferred:'等待自動審查最新方案',awaiting_input:'等待人工審查',failed:'審查失敗',interrupted:'審查中斷',cancelled:'審查已取消'}[state]||'待審查');
 }
 return labels[s.status]||s.status;
}
export function directingPanel(p,esc){
 if(!p.production)return '';
 const states=p.directing?.scenes||[],hasPlan=states.some(s=>s.status!=='legacy');
 const reviews=[...new Map(states.filter(s=>s.review).map(s=>[s.review.job_id,s.review.review])).values()];
 const candidates=directingCandidates(p);
 if(candidates.size){
  const uncovered=p.production.scenes.some(sc=>!sc.director_plan&&!candidates.has(sc.id));
  return `<section class="panel"><h2>各場戲的拍攝意圖</h2>${currentDirectingReviewMarkup(p,esc)}<p class="muted">已生成的新方案與目前採用的分鏡分開保存。先審閱方案，再決定採用；生成完成不會自動替換現有分鏡。</p><p><a class="button" href="/editorial?project=${encodeURIComponent(p.id)}">開啟剪接與預覽 →</a></p><ul class="directing-scene-states">${states.map(s=>`<li><strong>${esc(p.production.scenes.find(sc=>sc.id===s.scene_id)?.title||s.scene_id)}</strong><span>${esc(candidates.has(s.scene_id)?candidateLabel(candidates.get(s.scene_id)):directingSceneLabel(s,p))}</span></li>`).join('')}</ul>${directorPlanMarkup(p.production,esc,candidates)}${editPlanMarkup(p.production,esc,true)}${reviews.map(r=>directingReviewMarkup(r,esc)).join('')}<div class="actions">${hasPlan?currentDirectingReviewAction(p,esc):''}${uncovered?'<button data-action="develop">建立其餘場戲的拍攝意圖方案</button>':''}</div></section>`;
 }
 return `<section class="panel"><h2>各場戲的拍攝意圖</h2>${currentDirectingReviewMarkup(p,esc)}<p class="muted">拍攝意圖記錄每場戲想讓觀眾明白甚麼、感受到甚麼，以及鏡頭如何表達。「尚未補充」表示舊分鏡未記錄這層資料，並非分鏡遺失或生成失敗。</p><p><a class="button" href="/editorial?project=${encodeURIComponent(p.id)}">開啟剪接與預覽 →</a></p><ul class="directing-scene-states">${states.map(s=>`<li><strong>${esc(p.production.scenes.find(sc=>sc.id===s.scene_id)?.title||s.scene_id)}</strong><span>${esc(directingSceneLabel(s,p))}</span></li>`).join('')}</ul>${directorPlanMarkup(p.production,esc)}${editPlanMarkup(p.production,esc,true)}${reviews.map(r=>directingReviewMarkup(r,esc)).join('')}<div class="actions">${hasPlan?currentDirectingReviewAction(p,esc):''}<button data-action="${hasPlan?'revise-current-directing':'develop'}">${hasPlan?'修訂劇情表達方案':p.source_kind==='outline'?'前往章節修訂方案':'建立含拍攝意圖的方案'}</button></div></section>`;
}
// Only current-revision formal proposals can explain missing adopted intent.
// Chapter IDs are localized at adoption; never apply a chapter candidate elsewhere.
export function directingCandidates(p){
 const candidates=new Map(),scenes=p.production?.scenes||[];
 const jobs=[...(p.jobs||[])].filter(j=>['narrative','storyboard'].includes(j.capability)&&j.state==='succeeded'&&j.input?.revision===p.revision&&p.directing?.proposals?.[j.id]?.required)
  .sort((a,b)=>String(b.created||'').localeCompare(String(a.created||''))||String(b.id).localeCompare(String(a.id)));
 for(const job of jobs){
  const plan=job.result?.production||job.result;
  const chapter=job.target_id?(p.production?.chapters||[]).find(c=>c.id===job.target_id):null;
  if(job.target_id&&!chapter)continue;
  for(const scene of plan?.scenes||[]){
   const id=chapter&&!scene.id.startsWith(chapter.id+'__')?chapter.id+'__'+scene.id:scene.id;
   if(chapter&&!chapter.scene_ids.includes(id))continue;
   if(!scene.director_plan||candidates.has(id)||!scenes.some(sc=>sc.id===id&&!sc.director_plan))continue;
   candidates.set(id,{job,review:p.directing.proposals[job.id]});
  }
 }
 return candidates;
}
function candidateLabel({review}){
 if(review.human_approval)return '拍攝意圖已人工批准 · 待採用';
 if(review.state==='succeeded'&&review.result?.verdict==='pass')return '拍攝意圖已生成 · 待採用';
 if(review.state==='succeeded'&&review.result?.verdict==='revise')return '拍攝意圖已生成 · 需要修訂';
 if(review.state==='succeeded'&&review.result?.verdict==='uncertain')return '拍攝意圖已生成 · 審查未能判斷';
 return '拍攝意圖已生成 · '+(labels[review.state]||'待審查');
}
export function proposalReviewMarkup(status,id,esc){
 if(!status?.required)return '';
 const pending=['queued','running','awaiting_input'].includes(status.state);
 return `<details><summary>查看完整導演審查與其他操作</summary><h3>導演內容審查</h3>${status.state==='succeeded'&&status.result?directingReviewMarkup(status.result,esc):`<p>${esc(labels[status.state]||status.state)}${status.error?' · '+esc(status.error):''}</p>`}<div class="actions">${!pending?`<button data-action="directing-qc" data-id="${esc(id)}">${status.result?'重新審查':'審查此方案'}</button>`:''}<button data-action="proposal" data-id="${esc(id)}">更新審查狀態</button>${!pending&&status.result?.verdict!=='pass'?`<button data-action="revise-directing" data-id="${esc(id)}">按意見修訂方案</button>`:''}</div><p class="muted">重新審查只會再評估原方案；要修改內容，請使用上方的下一步。</p></details>`;
}
export function proposalAdoptionState(status,sourceRevision,currentRevision){
 if(sourceRevision!==currentRevision)return {allowed:false,reason:'目前作品已更新；此方案基於較早版本，請先建立修訂方案，避免覆蓋新決定。'};
 if(status?.human_approval)return {allowed:true,reason:'已人工批准，可以採用此方案；AI 意見仍保留。'};
 if(!status?.required)return {allowed:true,reason:''};
 if(status.state==='succeeded'&&status.result?.verdict==='pass')return {allowed:true,reason:'導演內容審查已通過，可以採用此方案。'};
 if(status.result?.verdict==='revise')return {allowed:false,reason:'暫未能採用：整體導演審查要求修訂。個別節拍「通過」不代表整份方案通過；請按「按意見修訂方案」，修訂後會再審查。'};
 return {allowed:false,reason:'暫未能採用：導演內容審查尚未通過（'+(labels[status.result?.verdict||status.state]||'待審查')+'）。請先完成審查或修訂方案。'};
}
export function directingRevisionMarkup(notes,label,esc){
 return `<div class="proposal-guide"><p class="eyebrow">第 1 步／共 3 步 · 修訂方案</p><h3>審查意見已整理好，按下方「開始修訂」即可</h3><p>接下來系統會修訂方案並自動審查。完成後會帶你開啟新方案，再由你決定採用。</p></div><p>已自動帶入原方案及以下審查意見。補充要求可留空，直接按「開始修訂」即可。</p><details open><summary>查看已帶入的審查意見與修改建議</summary><pre>${esc(notes||'目前沒有審查意見，請補充修訂要求。')}</pre></details><form id="directing-revision-form"><label>補充修訂要求（選填）<textarea name="feedback" rows="3" placeholder="可留空，系統會按上述審查意見修訂。"></textarea></label><p class="muted">交由 ${esc(label)} 修訂；新方案完成後會再次審查，目前採用版本仍會保留。</p><div class="modal-footer"><button type="button" data-action="close">取消</button><button class="primary" type="submit">開始修訂</button></div></form>`;
}
