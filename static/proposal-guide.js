// Pure guidance: actions share the existing application routes and review gate.
const steps=['修訂方案','自動審查','審閱並採用'];
export function readableProposal(job){
 if(job?.state!=='succeeded'||job.capability&&!['narrative','storyboard'].includes(job.capability))return null;
 const plan=job.result?.production??job.result;
 return plan&&['canon','scenes','shots'].every(key=>Array.isArray(plan[key]))?plan:null;
}
export function reviewProgress(status){
 const state=status?.state;
 if(state==='sending')return {title:'正在送出審查…',note:'正在提交審查要求，請稍候。'};
 if(state==='queued'){
  const q=status.queue,position=Number.isInteger(q?.position)&&q.position>0?`目前排第 ${q.position} 位。`:'';
  return {title:'審查已排隊，等候開始',note:position+(q?.running?`等候 ${q.running} 項工作完成${q.running_projects?.length?'（'+q.running_projects.join('、')+'）':''}。`:'審查工作已收到，等候可用的執行服務。')+'開始後會自動更新，毋須重新送出。'};
 }
 if(state==='running'&&status.progress?.kind==='directing_stages')return {title:'自動審查中',note:`${status.progress.label}。已保存 ${status.progress.completed}／${status.progress.total} 批；全部節拍及跨場核對完成後才會顯示整體結果。`};
 if(state==='running')return {title:'自動審查中',note:'正在檢查劇情表達、鏡頭安排與連戲。完成後會自動顯示結果，毋須重新送出。'};
 if(state==='awaiting_input')return {title:'等待人工審查結果',note:'目前使用人工審查服務，需要提交結果。'};
 return null;
}
export function reviewReceiptMarkup(status,esc){
 const progress=reviewProgress(status);
 return progress?`<section class="proposal-guide" role="status" aria-live="polite"><h3>${esc(progress.title)}</h3><p>${esc(progress.note)}</p><button disabled aria-busy="${status.state==='sending'}">${esc(progress.title)}</button></section>`:'';
}
export function proposalNextAction({job,status,currentRevision,phase='review'}){
 const id=job.id;
 if(job.capability&&!['narrative','storyboard'].includes(job.capability))return {step:2,label:'查看工作進度',action:'job-detail',id,title:'這是審查或製作工作',note:'這份工作記錄不是故事方案；請查看其進度及結果。'};
 if(job.input?.revision!==currentRevision)return {step:1,label:'下一步：按目前版本建立方案',action:job.input?.serial_source?'develop-chapter':'develop',id:job.input?.serial_source?job.target_id:'',note:'作品已更新，這份方案來自較早版本。請以目前內容建立新方案。'};
 if(job.state!=='succeeded'){
  if(['queued','running'].includes(job.state))return {step:1,note:job.state==='queued'?'修訂工作已保存，正在等候處理。完成後系統會自動審查。':'正在修訂方案，完成後系統會自動審查。'};
  if(job.state==='awaiting_input')return {step:1,label:'下一步：提交人工結果',action:'manual',id,note:'目前選用人工處理，請提交方案結果，再繼續審查。'};
  return {step:1,label:'下一步：查看工作記錄',action:'job-detail',id,note:'修訂未完成。請開啟工作記錄查看原因；可從「版本與記錄」找回工作並恢復或重試。'};
 }
 if(!readableProposal(job))return {step:1,label:'查看工作記錄',action:'job-detail',id,title:'方案結果暫未可讀',note:'未取得完整的方案內容，暫時不能開啟或採用。請查看工作記錄；原有作品仍然保留。'};
 let next;
 if(status?.human_approval)next={step:3,label:'採用此方案 →',action:'adopt',id,note:'你已人工批准此方案；AI 審查意見仍保留。'};
 else if(!status?.required)next={step:3,label:'採用此方案 →',action:'adopt',id,note:'方案已準備好，請核對內容後決定採用。'};
 else if(['sending','queued','running'].includes(status.state))next={step:2,...reviewProgress(status)};
 else if(status.state==='awaiting_input')next={step:2,label:'下一步：提交人工審查',action:'manual',id:status.job_id,note:'目前審查服務採用人工處理。提交審查結果後，才能繼續。'};
 else if(status.state==='succeeded'&&status.result?.verdict==='pass')next={step:3,label:'採用此方案 →',action:'adopt',id,note:'整體導演審查已通過。請核對新方案，按「採用此方案」後進入素材準備。'};
 else if(status.state==='succeeded'&&['revise','uncertain'].includes(status.result?.verdict))next={step:1,label:'下一步：按意見修訂方案',action:'revise-directing',id,note:'這份方案需要修訂。按下一步，系統會自動帶入原方案及審查意見；補充要求可留空，再按「開始修訂」。',summary:status.result.summary};
 else if(status.resumable)next={step:2,label:'下一步：接續審查',action:'resume-directing',id:status.job_id,title:'自動審查已停止',note:'已完成批次保留；接續會沿用原服務商及預算，只處理未完成部分。',summary:status.error};
 else next={step:2,label:!status.state||status.state==='missing'?'下一步：開始審查':'下一步：重試審查',action:'directing-qc',id,title:({failed:'自動審查失敗',interrupted:'自動審查已中斷',cancelled:'自動審查已取消'})[status.state]||'尚未開始自動審查',note:!status.state||status.state==='missing'?'方案已保存，尚未有審查工作。送出審查後會顯示排隊及執行狀態。':'這次審查已停止，並非仍在處理。你可以查看原因，再重新送出審查。',summary:status.error};
 // A completed revision must first be opened and read; never adopt from receipt.
 if(phase==='progress'&&next.action&&next.action!=='manual'&&next.action!=='directing-qc'&&next.action!=='resume-directing')return {...next,label:'開啟新方案',action:'proposal',id};
 return next;
}
function humanAction(args,esc){
 const {job,status,currentRevision,phase}=args;
 if(phase==='progress'||!readableProposal(job)||job.input?.revision!==currentRevision||!status?.approval_source_hash||status.human_approval||status.result?.verdict==='pass')return '';
 return `<button data-action="human-directing" data-id="${esc(job.id)}">人工批准並採用此方案</button>`;
}
function actionMarkup(next,esc){return next.action?`<button class="primary" data-action="${esc(next.action)}"${next.id?` data-id="${esc(next.id)}"`:''}>${esc(next.label)}</button>`:'';}
export function proposalGuideMarkup(args,esc){
 const next=proposalNextAction(args);
 return `<section class="proposal-guide" aria-label="方案處理流程"><ol class="proposal-steps">${steps.map((s,i)=>`<li${i+1===next.step?' aria-current="step"':''}>${s}</li>`).join('')}</ol><h3 role="status" aria-live="polite">${esc(next.title||`目前：第 ${next.step} 步 · ${steps[next.step-1]}`)}</h3><p>${esc(next.note)}</p>${next.summary?`<details><summary>${next.step===2?'查看審查停止原因':'查看今次需要修訂的原因'}</summary><p>${esc(next.summary)}</p></details>`:''}<div class="proposal-next">${actionMarkup(next,esc)}${humanAction(args,esc)}</div></section>`;
}
export function proposalGuideFooterMarkup(args,esc){
 const next=proposalNextAction(args);
 return `<div class="proposal-footer"><p>${esc(next.title||`第 ${next.step} 步 · ${steps[next.step-1]}`)}${next.action?'':'，進度會自動更新。'}</p><button data-action="close">留待稍後處理</button>${actionMarkup(next,esc)}${humanAction(args,esc)}</div>`;
}
