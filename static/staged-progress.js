// 分階段章節生成進度（純前端模組）
// 讀取 job.progress（kind==='chapter_stages'）並渲染簡潔進度；
// 可恢復判斷由 canResumeStages(job) 提供，供父層掛按鈕使用。

function num(value){
 const n=Number(value);
 return Number.isFinite(n)&&Number.isInteger(n)&&n>=0?n:null;
}

export function hasSavedStages(job){return num(job?.progress?.completed)>0;}
function shotsComplete(job){
 return num(job?.progress?.total_shots)>0&&num(job?.progress?.completed_shots)===num(job?.progress?.total_shots);
}
export function stagedResumeLabel(job){
 return shotsComplete(job)?'接續剩餘整理':'從中斷位置繼續';
}

export function renderStagedProgress(job,esc){
 const progress=job?.progress;
 if(progress?.kind==='generation_stages'){
  const complete=job.state==='succeeded',failed=['failed','interrupted'].includes(job.state);
  const label=job.cancel_requested?'正在停止安排':job.state==='cancelled'?'安排已取消':complete?'生成安排已完成':(failed?'停在：':'')+progress.label;
  return `<div class="staged-progress" role="status" aria-live="polite"><strong>${esc(label)}</strong><span class="staged-count">已保存 ${num(progress.completed)??0} 批</span>${failed&&canResumeStages(job)?'<p class="staged-note">接續時會沿用已完成批次。</p>':''}</div>`;
 }
 if(progress?.kind==='directing_stages'){
  const complete=job.state==='succeeded',failed=['failed','interrupted'].includes(job.state);
  return `<div class="staged-progress" role="status" aria-live="polite"><strong>${esc(complete?'全部審查已完成':job.state==='cancelled'?'審查已取消':(failed?'停在：':'')+progress.label)}</strong><p>已保存 ${num(progress.completed)??0}／${num(progress.total)??0} 批</p><p>${complete?'請查看整體結論及修訂意見。':'全部節拍及跨場核對完成後，才會產生整體結果；已保存批次可接續。'}</p></div>`;
 }
 if(!progress||progress.kind!=='chapter_stages')return '';
 const stages=num(progress.completed);
 const stagesTotal=num(progress.total);
 const shots=num(progress.completed_shots);
 const shotsTotal=num(progress.total_shots);
 const active=(job?.state==='running'||job?.state==='queued');
 const failed=(job?.state==='failed'||job?.state==='interrupted');
 const cancelled=job?.state==='cancelled';
 const stopping=active&&job?.cancel_requested;
 const rawLabel=String(progress.label??'分階段生成');
 const label=esc(cancelled?'章節工作已取消':stopping?'正在停止章節工作':job?.state==='succeeded'?'章節方案已組合':failed?'停在：'+rawLabel.replace(/^正在/,''):rawLabel);
 const state=esc(job?.state||'');
 const parts=[
  `<div class="staged-progress staged-progress-${state}" data-staged-progress role="status" aria-live="polite">`,
  `<div class="staged-progress-heading"><strong>${label}</strong>`,
  stages!==null&&stagesTotal>0?`<span class="staged-count">階段 ${stages}/${stagesTotal}</span>`:'',
  shots!==null&&shotsTotal>0?`<span class="shot-count">鏡頭 ${shots}/${shotsTotal}</span>`:'',
  `</div>`,
  progress.finalization?`<p class="staged-note">最後整理 ${num(progress.finalization.completed)??0}/${num(progress.finalization.total)??0} 批${num(progress.finalization.total_units)>0?` · 原文對照 ${num(progress.finalization.covered_units)??0}/${num(progress.finalization.total_units)} 段`:''}</p>`:'',
  `<p class="staged-note">${
   cancelled
    ?'已保存的階段檔案仍會保留；此工作不會繼續生成。'
    :stopping
     ?'已收到取消要求，正在結束目前階段。'
    :active
    ?'進度以已保存的階段成果為準；完成後會繼續下一階段。'
    :failed
     ?canResumeStages(job)?shotsComplete(job)?'全部鏡頭已保存；接續只補剩餘整理，已完成的原文對照批次亦會沿用。':'已完成的階段仍會保留，可接續未完成的部分。':'已完成的階段仍會保留；此工作不能接續。'
     :job?.state==='succeeded'?'階段成果已保存；請審閱方案及導演意見，再決定是否採用。':'已保存的階段可在工作紀錄檢視。'
  }</p>`,
  `</div>`
 ];
 return parts.filter(Boolean).join('\n');
}

export function canResumeStages(job){
 if(!job)return false;
 if(!job.input?.chapter_pipeline&&!job.input?.directing_pipeline&&!job.input?.generation_pipeline)return false;
 if(job.state!=='failed'&&job.state!=='interrupted')return false;
 if(job.cancel_requested)return false;
 if(job.error&&String(job.error).startsWith('已要求取消'))return false;
 return true;
}
