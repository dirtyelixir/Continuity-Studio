import {productionProgress} from './production-progress.js';

const pageNames={progress:'製作總覽',overview:'故事與章節',canon:'角色與場景',shots:'分鏡畫面與審閱',video:'影片製作',postproduction:'後製配音',review:'審查室',history:'活動與版本'};
const stageHelp=[
 {goal:'決定故事、劇本、每場戲和鏡頭安排。',finish:'審閱並採用製作方案，作品內已有正式鏡頭。',action:'開啟故事與章節',page:'overview'},
 {goal:'先按剪接基準安排獨立來源或分組，再列出素材需求。',finish:'生成安排已採用，再生成及審閱所需角色、場景和控制畫面。',action:'安排生成與素材',page:'video'},
 {goal:'準備分鏡圖片，按故事次序逐格確認，再準備影片提示詞。',finish:'每格圖片可以直接審閱；批准或記錄修改後，自動帶你看下一格。缺圖可在同一頁補齊。',action:'查看畫面與審閱',stage:3},
 {goal:'核對影片提示詞及生成設定，生成後看片並採用。',finish:'每鏡有已採用、符合目前來源的影片。生成成功仍需你決定採用。',action:'查看影片與成片',stage:4},
 {goal:'將已審閱 Take 綁定到實際素材入出點及時間線位置；配音可並行。',finish:'對照實際影片確認節奏、聲畫和取用範圍。文字／圖片預覽不代表成片已完成。',action:'綁定實際剪接範圍',page:'video'},
];

function nextButton(next,{esc,button},cls='primary'){
 if(next.boardScene)return `<button type="button" class="${cls}" data-board-action="continue" data-scene="${esc(next.boardScene)}">${esc(next.label)} →</button>`;
 const attrs=[next.page?`data-page="${esc(next.page)}"`:'',next.id?`data-id="${esc(next.id)}"`:'',next.section?`data-section="${esc(next.section)}"`:''].filter(Boolean).join(' ');
 return button(esc(next.label)+' →',next.action,attrs,cls);
}

export function renderProductionNav(page,pending,{esc,button}){
 const navButton=(id,label)=>button(esc(label)+(id==='review'&&pending?` <span class="badge">${pending}</span>`:''),'navigate',`data-page="${id}" ${page===id?'aria-current="page"':''}`,page===id?'active':'');
 return `<nav aria-label="工作區導覽">${navButton('progress','製作總覽')}<div class="nav-group-label">製作頁面</div>${[['overview','故事與章節'],['canon','角色與場景'],['shots','分鏡畫面與審閱'],['video','影片製作'],['postproduction','後製配音']].map(([id,label])=>navButton(id,label)).join('')}<div class="nav-group-label">審閱與管理</div>${navButton('review','審查室')}${navButton('history','活動與版本')}${navButton('projects','作品管理')}</nav>`;
}

export function renderProductionGuide(project,page,helpers){
 const {esc,button,pendingImages=0}=helpers,s=productionProgress(project,pendingImages),activity=helpers.stageActivity||{};
 for(const stage of s.stages)if(activity[stage.number])stage.status=activity[stage.number].status+' · '+stage.status;
 const shot=project.production?.shots?.find(x=>x.id===s.next.id);
 const showNext=!(s.next.boardScene&&['shots','review','video'].includes(page));
 return `<section class="production-guide" aria-label="製作導航" data-production-guide><div class="production-guide-heading">${page==='progress'?'<h1>製作總覽</h1>':`<span>正在瀏覽：${esc(pageNames[page]||page)}</span>`}${page!=='progress'?button('返回製作總覽','navigate','data-page="progress"','small quiet'):'<span class="muted">按已保存的內容更新</span>'}</div>
 ${helpers.workActivity||''}${page!=='progress'?'<details class="production-path-disclosure"><summary>查看完整製作流程</summary>':''}<nav class="production-path" aria-label="製作流程">${s.stages.map(stage=>button(`<span class="production-step-number">${stage.complete?'✓':stage.number}</span><span><strong>${esc(stage.title)}</strong><small>${esc(stage.status)}</small>${s.currentStage===stage.number?'<em>建議先處理</em>':''}</span>`,'progress-stage',`data-stage="${stage.number}" ${!project.production&&stage.number>1?'disabled':''} ${s.currentStage===stage.number?'aria-current="step"':''}`,`production-step ${stage.complete?'is-complete':''} ${s.currentStage===stage.number?'needs-attention':''}`)).join('')}</nav>${page!=='progress'?'</details>':''}
 <div class="production-next" ${showNext?'':'hidden'}><div><div class="eyebrow">建議先處理 · 第 ${s.currentStage} 步 · ${esc(s.stages.find(x=>x.number===s.currentStage)?.title||'')}</div><h2>${esc(s.next.title)}</h2>${shot?`<p class="production-next-target">第 ${project.production.shots.indexOf(shot)+1} 鏡 · ${esc(shot.title)}</p>`:''}<p>${esc(s.next.description)}</p></div>${nextButton(s.next,helpers)}</div>
 <div class="production-guide-foot"><span>可隨時返回前面修改；每鏡可分開推進。</span>${s.work.length?button(`${s.work.length} 項工作處理中／待處理`,'navigate','data-page="history"','small quiet'):''}</div></section>`;
}

export function renderProductionDashboard(project,helpers){
 const {esc,button,pendingImages=0,displayLabel=x=>x,targetName=x=>x}=helpers,s=productionProgress(project,pendingImages);
 const stageCards=s.stages.map(stage=>{const h=stageHelp[stage.number-1],active=helpers.stageActivity?.[stage.number];return `<article class="production-stage-card ${stage.number===s.currentStage?'recommended':''}"><div class="panel-header"><h3>${stage.number} · ${esc(stage.title)}</h3><span class="badge ${stage.complete?'approved':''}">${active?esc(active.status):stage.number===s.currentStage?'建議先處理':stage.complete?'已備妥':'尚待處理'}</span></div><p data-stage-work="${stage.number}">${esc(stage.status)}</p><p>${h.goal}</p><p class="muted"><strong>這步做到甚麼：</strong>${h.finish}</p><div class="actions">${active&&helpers.workAction?nextButton({...helpers.workAction(active.job),label:'查看本步工作'},helpers,'small primary'):''}${h.editorial?button(h.action,'progress-editorial',!project.production?'disabled':'','small'):h.stage?button(h.action,'progress-stage',`data-stage="${h.stage}" ${!project.production?'disabled':''}`,'small'):button(h.action,'navigate',`data-page="${h.page}" ${!project.production&&stage.number>1?'disabled':''}`,'small')}${stage.number===5?button('配音／匯入聲音','navigate',`data-page="postproduction" ${!project.production?'disabled':''}`,'small'):''}</div></article>`;}).join('');
 const work=s.work.map(j=>`<div class="production-work-row"><div><strong>${esc(j.kind==='video'?'影片生成':j.kind==='voice'?'聲音製作':displayLabel(j.capability))}</strong><p>${esc(targetName(j.target_id||j.shot_id||'')||project.title)} · ${esc(displayLabel(j.state))}</p></div>${j.kind==='job'?button('查看進度／處理','job-detail',`data-id="${esc(j.id)}"`,'small'):button('查看工作',j.kind==='video'?'progress-video':'navigate',j.kind==='video'?`data-id="${esc(j.shot_id)}" data-section="render"`:'data-page="postproduction"','small')}</div>`).join('');
 return `<div class="page-header production-dashboard-header"><div><h2>每一步要做甚麼</h2><p class="muted">先跟上方的下一步繼續；需要了解整個流程時，再看以下各步說明。</p></div></div>${work&&!helpers.workActivity?`<section class="panel"><h2>正在處理的工作</h2><p class="muted">結果會保存到作品。正在處理時可繼續其他部分，毋須重新提交。</p>${work}</section>`:''}<div class="production-stage-grid">${stageCards}</div>`;
}
