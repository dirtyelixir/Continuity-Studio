// Presentation only: queue positions and progress come from saved server state.
const moving=new Set(['queued','preparing','submitting','submitted','running']);
const attention=new Set(['awaiting_input','uncertain','recoverable']);
const terminal=new Set(['succeeded','failed','interrupted','cancelled']);
const states={queued:'排隊中',preparing:'準備中',submitting:'正在提交',submitted:'已提交，等候結果',running:'處理中',awaiting_input:'等待你提交',uncertain:'需要確認',recoverable:'有結果待取回',succeeded:'已完成',failed:'失敗，需處理',interrupted:'已中斷，需處理',cancelled:'已取消'};
const stories=new Set(['narrative','storyboard','director_style','directing_qc']);
export function workItems(project){
 const all=[...(project.jobs||[]).map(j=>({...j,kind:'job'})),...(project.video_renders?.takes||[]).map(j=>({...j,kind:'video'})),...(project.postproduction?.takes||[]).map(j=>({...j,kind:'voice'}))];
 return all.filter(j=>!j.project_id||j.project_id===project.id).sort((a,b)=>String(b.updated||b.created||'').localeCompare(String(a.updated||a.created||'')));
}
export function workStage(project,j){
 if(j.kind==='video')return 4;
 if(j.kind==='voice'||j.capability==='voice_defaults')return 5;
 if(stories.has(j.capability))return 1;
 if(j.capability?.startsWith('h3'))return 3;
 const target=(project.assets||[]).find(a=>a.id===j.target_id)?.target_id||j.target_id;
 if((project.production?.canon||[]).some(e=>e.id===target))return 2;
 if((project.production?.shots||[]).some(s=>s.id===target||(s.keyframes||[]).some(f=>f.id===target)))return 3;
 return null;
}
export function workState(j){return (moving.has(j.state)&&(j.cancel_requested||j.error?.startsWith('已要求取消')))?'正在取消':states[j.state]||j.state;}
export function workSummary(items){
 const count=predicate=>items.filter(predicate).length;
 return [[count(j=>moving.has(j.state)&&j.state!=='queued'),'處理中'],[count(j=>j.state==='queued'),'排隊中'],[count(j=>attention.has(j.state)),'等你處理']].filter(([n])=>n).map(([n,label])=>`${n} 項${label}`).join(' · ')||'目前沒有工作排隊或處理中';
}
export function stageActivity(project){
 const all=workItems(project).filter(j=>moving.has(j.state)||attention.has(j.state));
 return Object.fromEntries([1,2,3,4,5].map(stage=>{const items=all.filter(j=>workStage(project,j)===stage);return [stage,items.length?{status:workSummary(items),job:items[0]}:null];}));
}
export function workAction(j){return j.kind==='video'?{action:'progress-video',id:j.shot_id,section:'render'}:j.kind==='voice'?{action:'navigate',page:'postproduction'}:{action:'job-detail',id:j.id};}
export function workDetail(j){
 if(workState(j)==='正在取消')return '取消要求已收到，正在等執行端結束。';
 if(j.state==='queued'){
  if(j.kind==='video')return j.error||'影片已排隊，等候 GPU／影片服務；輪到會自動開始。';
  const q=j.queue;
  return q&&Number.isInteger(q.position)&&q.position>0?`${q.label||'工作'}佇列第 ${q.position} 位；${q.running?`等候 ${q.running} 項工作完成${q.running_projects?.length?'（'+q.running_projects.join('、')+'）':''}`:'正在安排開始'}。`:'工作已收到，等候可用的執行服務；尚未開始。';
 }
 if(j.state==='awaiting_input')return '需要你提交結果，系統目前沒有自動生成。';
 if(j.state==='succeeded'&&j.capability==='directing_qc')return '審查已完成'+({pass:'：通過。',revise:'：需要修訂。',uncertain:'：未能判斷。'}[j.result?.verdict]||'；請查看審查結論。');
 if(j.state==='succeeded')return '結果已保存；完成狀態不代表已採用。';
 if(j.state==='cancelled')return '工作已停止，原有資料仍然保留。';
 if(['failed','interrupted'].includes(j.state))return '查看原因及已保存成果，再決定如何接續。';
 if(j.state==='uncertain'||j.state==='recoverable')return '查看原工作以確認或取回結果。';
 if(j.progress?.label)return j.progress.label;
 if(j.state==='running'&&j.capability==='directing_qc')return '正在審查劇情、鏡頭安排與連戲；審查結論尚未返回。';
 if(j.state==='running'&&j.capability==='storyboard_frames')return '正在判斷每鏡所需圖片及沿用素材；安排結果尚未返回。';
 if(j.capability==='image'&&j.input?.image_prompt_stage==='source')return '正在整理畫面與圖片提示詞，尚未開始出圖。';
 return '正在處理，完成後會自動更新；毋須重新提交。';
}
export function renderWorkRow(j,helpers){
 const {esc,button,displayLabel=x=>x,targetName=x=>x}=helpers,a=workAction(j);
 const label=j.kind==='video'?'影片生成':j.kind==='voice'?'聲音製作':displayLabel(j.capability);
 const name=targetName(j.target_id||j.shot_id||j.entity_id||'')||helpers.projectTitle||'作品';
 const progress=j.progress,counts=progress?.kind==='chapter_stages'?[['階段',progress.completed,progress.total],['鏡頭',progress.completed_shots,progress.total_shots]].filter(([,n,t])=>Number.isInteger(n)&&Number.isInteger(t)&&t>0).map(([s,n,t])=>`${s} ${n}／${t}`).join(' · '):'';
 const attrs=`${a.id?`data-id="${esc(a.id)}"`:''} ${a.page?`data-page="${a.page}"`:''} ${a.section?'data-section="render"':''}`;
 return `<article class="work-activity-row ${esc(j.state)}" data-work-id="${esc(j.kind+':'+j.id)}"><div><div class="work-activity-title">${moving.has(j.state)?'<span class="generation-spinner" aria-hidden="true"></span>':''}<strong>${esc(label)} · ${esc(name)}</strong><span class="badge ${esc(j.state)}">${esc(workState(j))}</span></div><p>${esc(workDetail(j))}</p>${counts?`<p>${esc(counts)}</p>`:''}${moving.has(j.state)&&j.created?`<small data-job-since="${esc(j.created)}"></small>`:''}${j.error&&!moving.has(j.state)?`<details><summary>查看原因</summary><p>${esc(j.error)}</p></details>`:''}</div>${helpers.showAction===false?'':button(terminal.has(j.state)?'查看結果／記錄':'查看進度／處理',a.action,attrs,'small')}</article>`;
}
export function renderWorkActivity(project,helpers){
 const active=workItems(project).filter(j=>moving.has(j.state)||attention.has(j.state));
 return `<div data-work-activity><section class="work-activity" aria-label="即時工作狀態"><div class="work-activity-heading"><h2>工作狀態</h2><strong role="status" aria-live="polite">${helpers.esc(workSummary(active))}</strong></div><p class="work-refresh-note" data-work-refresh>進度自動更新；可繼續瀏覽或編輯。</p>${active.map(j=>renderWorkRow(j,{...helpers,projectTitle:project.title})).join('')}</section></div>`;
}
