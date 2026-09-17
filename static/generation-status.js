const active = new Set(['queued','running','awaiting_input']);
const failed = new Set(['failed','interrupted','cancelled']);

export function renderLocalRuntime(runtime,escape){
 if(!runtime||!['recovering','waiting','blocked'].includes(runtime.phase))return '';
 return `<div class="note" role="status"><strong>${runtime.phase==='recovering'?'正在復原出圖服務':'出圖服務需要處理'}</strong><p>${escape(runtime.message)}</p></div>`;
}

export function queueDetail(job){
 const q=job.queue;
 if(job.state!=='queued'||!q)return '';
 const waiting=q.running?`正在等候 ${q.running} 個工作完成${q.running_projects?.length?'（'+q.running_projects.join('、')+'）':''}。`:'正在安排開始。';
 return `${q.label}佇列第 ${q.position} 位；${waiting}`;
}

export function generationStatus(project, target) {
 const assets=(project.assets||[]).filter(a=>a.target_id===target).sort((a,b)=>b.created.localeCompare(a.created));
 const jobs=(project.jobs||[]).filter(j=>j.capability==='image'&&j.target_id===target)
  .sort((a,b)=>b.created.localeCompare(a.created));
 const job=jobs.find(j=>active.has(j.state))||jobs[0];
 if(job&&active.has(job.state)){const status=fromJob(job,false);if(assets.length&&!status.cancelling){status.label={queued:'新版已排隊',running:'正在重新生成',awaiting_input:'新版等待人工提交'}[job.state];status.detail='目前顯示的是原有版本。'+status.detail;}return status;}
 const asset=assets[0];
 if(job&&failed.has(job.state)&&(!asset||job.created>asset.created))return fromJob(job,false);
 if(asset){
  if(asset.image_output_quality?.valid===false)return {phase:'failed',label:'生成結果無有效畫面',detail:asset.image_output_quality.message+' 原檔與工作記錄已保留，未自動重試。',active:false,jobId:asset.job_id};
  const review=(project.jobs||[]).filter(j=>j.capability==='image_review'&&j.target_id===asset.id)
   .sort((a,b)=>b.created.localeCompare(a.created))[0];
  if(review&&(active.has(review.state)||failed.has(review.state)))return {...fromJob(review,true),assetId:asset.id};
  if(asset.status==='pending')return {phase:'ready',label:'圖片已生成 · 等待你審閱',detail:'原圖已保存，審閱後可決定是否採用。',active:false,assetId:asset.id};
 }
 return null;
}

function fromJob(job,review){
 const preparing=!review&&job.state==='running'&&job.input?.image_prompt_stage==='source';
 const phases={queued:review?'圖片已生成 · 等待審查':'排隊中',running:review?'圖片已生成 · 正在審查':'正在生成圖片',awaiting_input:'等待人工處理',failed:review?'圖片已保存 · 審查失敗':'生成失敗',interrupted:review?'圖片已保存 · 審查中斷':'生成已中斷',cancelled:review?'審查已取消':'生成已取消'};
 const details={queued:queueDetail(job)||'工作已收到，等候服務商開始處理。',running:review?'正在檢查圖片與角色／場景設定是否一致。':'正在製作圖片，完成後會自動顯示。你可以繼續處理其他素材。',awaiting_input:'目前使用人工服務商，需要提交結果；沒有自動生成中的工作。'};
 if(job.error?.startsWith('已要求取消'))return {phase:job.state,label:'正在取消…',detail:job.provider==='comfy_local'?'正在停止等待本機結果；不會採用輸出，也不會中斷其他 GPU 工作。':'已送出取消要求，等待執行端結束。即使返回結果，也不會加入素材。',active:true,cancelling:true,jobId:job.id,since:job.created};
 return {phase:job.state,label:preparing?'正在整理圖片提示詞':phases[job.state],detail:preparing?'正在整理此張圖的外觀、構圖與光線；完成後才開始生圖。':details[job.state]||'請查看工作記錄了解原因，再決定是否重試。',error:job.error||'',active:active.has(job.state),jobId:job.id,since:job.created};
}

export function elapsedLabel(since,now=Date.now()){
 const ms=now-Date.parse(since);if(!Number.isFinite(ms))return '';
 const seconds=Math.max(0,Math.floor(ms/1000));
 return seconds<60?`已等候 ${seconds} 秒`:`已等候 ${Math.floor(seconds/60)} 分 ${seconds%60} 秒`;
}

export function renderGenerationStatus(status,escape){
 if(!status)return '';
 const moving=['queued','running'].includes(status.phase);
 return `<div class="generation-status ${escape(status.phase)}" role="status" aria-live="polite">
 <div class="generation-status-heading">${moving?'<span class="generation-spinner" aria-hidden="true"></span>':`<span aria-hidden="true">${status.phase==='ready'?'✓':'!'}</span>`}<strong>${escape(status.label)}</strong></div>
 <p>${escape(status.detail)}</p>
 ${status.active&&status.since?`<small data-job-since="${escape(status.since)}">${elapsedLabel(status.since)}</small>`:''}
 ${status.error?`<details><summary>查看原因</summary><p>${escape(status.error)}</p></details>`:''}
 <div class="actions">${status.active&&status.jobId?`<button type="button" class="small" data-action="cancel-job" data-id="${escape(status.jobId)}" ${status.cancelling?'disabled':''}>${status.cancelling?'正在取消…':'取消工作'}</button>`:''}${status.jobId?`<button type="button" class="small" data-action="job-detail" data-id="${escape(status.jobId)}">查看工作進度</button>`:''}${status.assetId?`<button type="button" class="small" data-action="navigate" data-page="review">審閱圖片</button>`:''}</div>
 </div>`;
}

export function assetRegenerationStatus(project,asset){
 const jobs=(project.jobs||[]).filter(j=>j.capability==='image'&&j.target_id===asset.target_id);
 const status=generationStatus({assets:[asset],jobs},asset.target_id);
 if(!status?.jobId)return null;
 const labels={queued:'新版已排隊',running:'正在重新生成',awaiting_input:'新版等待人工提交'};
 return {...status,label:labels[status.phase]||status.label,detail:status.active?'目前顯示的是原有版本。'+status.detail:status.detail};
}

export function imageProgressMarkup(project,target,escape){
 return `<div data-image-progress="${escape(target)}">${renderGenerationStatus(generationStatus(project,target),escape)}</div>`;
}
