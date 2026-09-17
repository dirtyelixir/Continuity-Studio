import {shotStateFields,applyShotStateFields} from './shot-state-editor.js';
import {renderTakeLibrary} from './video-render.js';
import {renderStoryboard,installStoryboard} from './storyboard-board.js';
import {boardTask,renderBoardNext} from './storyboard-next.js';
import {jobDetailBody,refreshJobDetail} from './job-detail.js';
import {openCurrentDirectingRevision} from './directing-revision.js';
import {directingApprovalForm} from './directing-approval.js';
import {renderGenerationGroups,installGenerationGroups} from './generation-groups.js';
import {openSceneAssetBatch} from './scene-asset-batch.js';
import {bindIdentityAssetPicker} from './identity-assets.js';
import {renderWorkActivity,renderWorkRow,stageActivity,workAction,workItems,workSummary} from './work-activity.js';
import {proposalGuideMarkup,proposalGuideFooterMarkup,reviewReceiptMarkup,readableProposal} from './proposal-guide.js';
import {watchProposal} from './proposal-watch.js';
import {renderContextSettings,contextLimitsForm,renderContextUsage} from './context-settings.js';
import {bindIdentityImageAssistant} from './identity-image.js';
import {renderStagedProgress,canResumeStages,hasSavedStages,stagedResumeLabel} from './staged-progress.js';
import {directingPanel,directorPlanMarkup,shotIntentMarkup,editPlanMarkup,proposalReviewMarkup,proposalAdoptionState,directingRevisionMarkup} from './directing-plan.js';
import {imageControls,bindImageControls,imageOptions,localImageSettings,imageLoraMarkup} from './local-images.js';
import {groupAssetVersions,needsAssetReview} from './asset-versions.js';
import {renderProviderProfile,profileLabel,supportsProvider,renderProductionMethod} from './provider-profile.js';
import {renderVideoWorkflow,strategyMarkup} from './video-workflow.js';
import {renderAssetGroups} from './asset-groups.js';
import {createPromptDrafts,currentPrompt,promptSaveConfiguration} from './prompt-editor.js';
import {referenceFidelityFeedback} from './reference-fidelity.js';
import {generationStatus,renderGenerationStatus,elapsedLabel,assetRegenerationStatus,imageProgressMarkup,queueDetail,renderLocalRuntime} from './generation-status.js';
import {referenceDropMarkup,bindReferenceDrop} from './reference-drop.js';
import {renderPostproduction,installVoiceUI,captureVoicePlayback,restoreVoicePlayback} from './postproduction.js';
import {installVideoRenderUI} from './video-render.js';
import {renderVisualStylePicker,readVisualStyle} from './visual-style.js';
import {renderProductionGuide,renderProductionDashboard,renderProductionNav} from './production-guide.js';
import {renderStoryOverview,chapterForm} from './story-chapters.js';
import {renderDirectorStyles} from './director-styles.js';
import {createHandoffState, renderHandoff, transferReferences} from './director-page.js';
import {displayLabel,displayError} from './locale-zh.js';
const $=s=>document.querySelector(s), esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const handoff = createHandoffState({getItem: key => localStorage.getItem(key), setItem: (key, value) => localStorage.setItem(key, value)});
const handoffTransfers = {};
const promptDrafts=createPromptDrafts(sessionStorage);
let guidanceRequest=false;
let preparationRequest=false;
let disposeReferenceDrop=null;
let disposeProposalWatch=null;
const imageURL=id=>`/api/assets/${id}/image`;
function routePage(){const raw=location.hash.slice(1),p=['h3','h3-legacy'].includes(raw)?'video':raw;return ['progress','projects','projects-trash','overview','shots','canon','postproduction','review','video','h3','h3-legacy','history','settings'].includes(p)?p:'progress';}
let projectDeletionReady=false;
let projects=[],deletedProjects=[],project=null,page=routePage(),selectedShot=null,selectedFrame=null,settings=null,lastState='',busy=false;
async function previewBaselineImpact(path,body){
 const impact=await api(path.replace(/\/plan$/,'/plan-impact'),body);
 const form=document.querySelector('#edit-form');
 if(!form)return; // Quick actions keep their existing revision protection.
 const signature=JSON.stringify(body);
 if(form.dataset.impactSource===signature)return;
 let panel=form.querySelector('[data-baseline-impact]');
 if(!panel){panel=document.createElement('section');panel.dataset.baselineImpact='';form.querySelector('.modal-footer').before(panel);}
 panel.innerHTML=`<h3>修訂影響預覽</h3><p>${impact.assets_require_review.length} 項圖片需要重新核對 · ${impact.generation_units_change.length} 個生成單位改變 · ${impact.takes_retained_needing_review.length} 個舊 Take 保留並需要兼容性核對。</p><p>${impact.dialogue_audio_unchanged?'對白與剪接聲音依賴維持有效。':'聲音／對白時間依賴已改變，需要核對。'}</p>`;
 form.dataset.impactSource=signature;form.querySelector('[type=submit]').textContent='保存這份修訂';
 panel.scrollIntoView({block:'nearest'});
 throw Object.assign(new Error('已顯示修訂影響，尚未儲存。'),{name:'ImpactPreview'});
}
async function api(path,body,method){if(project?.workflow_contract_version===1&&method==='PUT'&&/\/projects\/[^/]+\/plan$/.test(path)&&document.querySelector('#edit-form'))await previewBaselineImpact(path,body);const r=await fetch('/api'+path,{method:method||(body===undefined?'GET':'POST'),headers:body instanceof FormData?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:body instanceof FormData?body:JSON.stringify(body)});if(!r.ok){let e=await r.json().catch(()=>({detail:r.statusText}));throw Error(typeof e.detail==='string'?e.detail:JSON.stringify(e.detail));}return r.json();}
function toast(text){$('#toast').textContent=text;$('#toast').style.display='block';setTimeout(()=>$('#toast').style.display='none',6500);}
function providerLabel(cap){const id=settings?.routing?.[cap]||settings?.profile?.default_provider||'astra';return providerName(id);}
function providerName(id){return id==='astra'?'Astra':id==='manual'?'人工處理':settings?.providers.find(p=>p.id===id)?.name||id;}
function uiError(text){return /^[\u3400-\u9fff]/u.test(String(text||''))?String(text):displayError(text);}
function badge(x){return `<span class="badge ${esc(x)}">${esc(displayLabel(x))}</span>`;}
function button(label,action,attrs='',cls=''){return `<button type="button" class="${cls}" data-action="${action}" ${attrs}>${label}</button>`;}
function imageTransfer(id,label=targetName(id)){
 const filename=(label||'reference').replace(/[<>:"/\\|?*\x00-\x1f]/g,'-').replace(/\s+/g,'-')+'.png';
 return `${button('送到 ComfyUI 素材庫','send-comfy',`data-id="${id}"`,'small primary')}${button('在資料夾中顯示','reveal-image',`data-id="${id}" title="開啟原圖所在資料夾，並選取這個檔案"`,'small primary')}${button('複製圖片路徑','copy-image-path',`data-id="${id}"`,'small')}${button('複製圖片','copy-image',`data-id="${id}" data-label="${esc(label)}"`,'small')}<a class="small image-download" href="${imageURL(id)}" download="${esc(filename)}">下載 PNG ↓</a>`;
}
function folderFileLabel(name){const stem=name.split('/').pop().split('.')[0],asset=project.assets.find(a=>a.id===stem);return asset?targetName(asset.target_id)+' · '+name:name;}
function assetsFor(id){return (project?.assets||[]).filter(a=>a.target_id===id);}
function approved(id){return assetsFor(id).find(a=>a.status==='approved');}
function latest(id){return approved(id)||assetsFor(id)[0];}
function targetName(id){const job=project?.jobs?.find(j=>j.id===id);if(job)return job.target_id&&job.target_id!==id?targetName(job.target_id):(project.title+' · 製作方案');const p=project?.production;const ch=project?.story_chapters?.find(c=>c.id===id);if(ch)return ch.title;if(!p)return id;const as=project.assets.find(a=>a.id===id);if(as)return targetName(as.target_id);return project.generation_groups?.rows.find(g=>g.id===id)?.title||p.canon.find(e=>e.id===id)?.name||p.scenes.find(s=>s.id===id)?.title||p.shots.find(s=>s.id===id)?.title||p.shots.flatMap(s=>s.keyframes.map(f=>({...f,name:`${s.title} · ${displayLabel(f.moment)}`}))).find(f=>f.id===id)?.name||id;}
function imageStatus(target){return generationStatus(project,target);}
function imageStatusPanel(status){return renderGenerationStatus(status,esc);}
let progressPolling=false;
async function updateVisibleImageProgress(){
 if(progressPolling||refreshing||!project)return;
 progressPolling=true;const pid=project.id,loadVersion=projectLoadVersion;
 try{
  const fresh=await api('/projects/'+pid);if(project?.id!==pid||loadVersion!==projectLoadVersion)return;
  updateWorkSurfaces(fresh);
  document.querySelectorAll('[data-image-progress]').forEach(el=>{const html=renderGenerationStatus(generationStatus(fresh,el.dataset.imageProgress),esc);if(el.innerHTML!==html)el.innerHTML=html;});
  document.querySelectorAll('[data-progress-target]').forEach(el=>{el.disabled=!!generationStatus(fresh,el.dataset.progressTarget)?.active;});
 }catch(error){if(project?.id===pid&&loadVersion===projectLoadVersion)document.querySelectorAll('[data-work-refresh]').forEach(el=>{el.textContent='暫時未能更新進度，以下是上次狀態；會自動重試。';});throw error;}finally{progressPolling=false;}
}
function updateWorkSurfaces(fresh){
 const helpers={esc,button,displayLabel,pendingImages:groupAssetVersions(fresh.assets||[],{reviewOnly:true}).length,targetName:id=>activityTargetName(fresh,id)};
 const patch=(selector,html)=>{document.querySelectorAll(selector).forEach(el=>{if(el._workMarkup===html)return;el._workMarkup=html;const opened=[...el.querySelectorAll('details[open]')].map(d=>d.closest('[data-work-id]')?.dataset.workId||'recent');const focused=el.contains(document.activeElement)?document.activeElement:null;const key=focused?.closest('[data-work-id]')?.dataset.workId;const action=focused?.dataset.action;el.innerHTML=html;el.querySelectorAll('details').forEach(d=>{if(opened.includes(d.closest('[data-work-id]')?.dataset.workId||'recent'))d.open=true;});if(key&&action)[...el.querySelectorAll('[data-action]')].find(b=>b.closest('[data-work-id]')?.dataset.workId===key&&b.dataset.action===action)?.focus({preventScroll:true});});};
 const template=document.createElement('template');template.innerHTML=renderWorkActivity(fresh,helpers);patch('[data-work-activity]',template.content.firstElementChild.innerHTML);
 document.querySelectorAll('[data-work-refresh]').forEach(el=>{el.textContent='進度自動更新；可繼續瀏覽或編輯。';});
 const stages=stageActivity(fresh);
 if(page==='progress'){const cards=document.createElement('template');cards.innerHTML=renderProductionDashboard(fresh,{...helpers,stageActivity:stages,workAction,workActivity:'shared'});patch('.production-stage-grid',cards.content.querySelector('.production-stage-grid').innerHTML);}
 const guide=document.querySelector('[data-production-guide]');
 if(guide){const fragment=document.createElement('template');fragment.innerHTML=renderProductionGuide(fresh,page,{...helpers,stageActivity:stages});for(const selector of ['.production-path','.production-next','.production-guide-foot']){const source=fragment.content.querySelector(selector),target='[data-production-guide] '+selector;patch(target,source?.innerHTML||'');document.querySelectorAll(target).forEach(el=>{el.hidden=!source||source.hidden;});}}
 patch('[data-work-summary]',esc(workSummary(workItems(fresh))));
 const detail=document.querySelector('[data-live-job]');if(detail){const j=fresh.jobs.find(j=>j.id===detail.dataset.liveJob);if(j){patch('[data-live-job]',renderWorkRow({...j,kind:'job'},{...helpers,showAction:false}));const body=document.querySelector('[data-job-detail-body]');if(body)refreshJobDetail(body,j,fresh,jobDetailHelpers());}}
 updateGenerationClocks();
}
function jobDetailHelpers(){return {esc,button,providerName,renderProductionMethod,renderContextUsage,imageLoraMarkup,uiError};}
function activityTargetName(p,id){const job=p.jobs?.find(j=>j.id===id);if(job)return job.target_id&&job.target_id!==id?activityTargetName(p,job.target_id):(p.title+' · 製作方案');const asset=p.assets?.find(a=>a.id===id);if(asset)return activityTargetName(p,asset.target_id);return p.story_chapters?.find(c=>c.id===id)?.title||p.production?.canon?.find(e=>e.id===id)?.name||p.production?.scenes?.find(s=>s.id===id)?.title||p.production?.shots?.find(s=>s.id===id)?.title||p.production?.shots?.flatMap(s=>(s.keyframes||[]).map(f=>({...f,title:s.title+' · '+displayLabel(f.moment)}))).find(f=>f.id===id)?.title||id||p.title;}
function updateGenerationClocks(){document.querySelectorAll('[data-job-since]').forEach(el=>{el.textContent=elapsedLabel(el.dataset.jobSince);});}
function activeJobs(){return [...(project?.jobs||[]),...(project?.postproduction?.takes||[]),...(project?.video_renders?.takes||[])].filter(j=>['queued','preparing','submitting','submitted','running','awaiting_input'].includes(j.state));}
function head(title,sub,actions=''){return `<div class="page-header"><div><div class="eyebrow">${esc(project?.title||'你的製作工作台')}</div><h1>${title}</h1><p class="muted">${sub}</p></div><div class="actions">${actions}</div></div>`;}
function overviewDetailKey(el){
 const labels=[];for(let node=el;node&&node.tagName!=='MAIN';node=node.parentElement){
  if(node.id)labels.push(node.id);
  else if(node.tagName==='DETAILS')labels.push(node.querySelector(':scope > summary')?.textContent||'');
  else if(node.classList.contains('story-chapter'))labels.push(node.getAttribute('data-chapter-id')||node.querySelector('h3')?.textContent||'');
 }
 return JSON.stringify(labels);
}
function progressHelpers(){const helpers={esc,button,pendingImages:groupAssetVersions(project?.assets||[],{reviewOnly:true}).length,targetName,displayLabel};return {...helpers,stageActivity:stageActivity(project),workAction,workActivity:renderWorkActivity(project,helpers)};}
function render(){const root=$('#app'),sameOverview=page==='overview'&&root.dataset.overviewProject===project?.id;
 const frameScope=['video','shots'].includes(page)?page+':'+(project?.id||''):'';
 const expandedFrames=frameScope&&root.dataset.frameScope===frameScope?new Set([...root.querySelectorAll('[data-frame-description][open]')].map(el=>el.dataset.frameDescription)):new Set();
 const expandedBoards=new Set([...root.querySelectorAll('[data-storyboard-scene][open]')].map(el=>el.dataset.storyboardScene));
 const expandedGroups=page==='video'&&root.dataset.videoProject===project?.id?new Set([...root.querySelectorAll('[data-generation-group][open]')].map(el=>el.dataset.generationGroup)):new Set();
 const expandedArrangements=page==='video'&&root.dataset.videoProject===project?.id?new Set([...root.querySelectorAll('[data-generation-arrangement][open]')].map(el=>el.dataset.generationArrangement)):new Set();
 const voicePlayback=captureVoicePlayback(root,page==='postproduction'?project?.id:null);
 const expandedEntities=page==='canon'&&root.dataset.canonProject===project?.id?new Set([...root.querySelectorAll('.entity-details[open]')].map(el=>el.dataset.entity)):new Set();
 const expanded=sameOverview?new Set([...root.querySelectorAll('main details[open]')].map(overviewDetailKey)):new Set();
 const pending=groupAssetVersions(project?.assets||[],{reviewOnly:true}).length;$('#app').innerHTML=`<div class="shell"><aside class="sidebar"><div class="brand"><div class="brand-mark">C</div><b>Continuity<br>Studio 0.1</b></div><div class="eyebrow">工作區</div>${renderProductionNav(page,pending,{esc,button})}<div class="projects"><div class="eyebrow">作品</div>${projects.map(p=>button(esc(p.title),'project',`data-id="${p.id}"`,'project-button '+(project?.id===p.id?'active':''))).join('')}${button('＋ 新增作品','new-project','','project-button')}</div><div class="bottom">${button('擴充功能與服務商','navigate','data-page="settings"',page==='settings'?'active':'')}<div class="connection"><span class="dot"></span>${esc(profileLabel(settings))}<br>作品儲存於本機<br>介面語言：繁體中文</div></div></aside><main class="main"><div class="topbar"><span>工作區 &nbsp; / &nbsp; <strong>${esc(project?.title||'作品')}</strong></span><div class="top-actions">${project?`<span class="muted">已儲存 · 版本 ${project.revision}</span>`:''}<span data-work-summary>${activeJobs().length?esc(workSummary(activeJobs())):''}</span>${button('建立作品／導入故事','new-project','','small')}${project?button('製作資料夾','production-folder','','small'):''}${project?.production?`<a class="small" href="/editorial?project=${encodeURIComponent(project.id)}">剪接與預覽 →</a><a class="small" href="/api/projects/${project.id}/export">匯出製作資料 ↗</a>`:''}</div></div>${project&&!['projects','projects-trash','settings'].includes(page)?renderProductionGuide(project,page,progressHelpers()):''}${['projects','projects-trash'].includes(page)?projectsPage():page==='settings'?settingsPage():!project?landing():page==='progress'?renderProductionDashboard(project,progressHelpers()):page==='overview'?overview():page==='canon'?canon():page==='shots'?shots():page==='review'?review():page==='video'?videoPage():page==='h3-legacy'?h3Legacy():page==='postproduction'?renderPostproduction(project):history()}</main></div>`;
 root.dataset.frameScope=frameScope;
 root.querySelectorAll('[data-frame-description]').forEach(el=>{el.open=expandedFrames.has(el.dataset.frameDescription);});
 root.dataset.videoProject=page==='video'?(project?.id||''):'';
 root.querySelectorAll('[data-storyboard-scene]').forEach(el=>{if(expandedBoards.has(el.dataset.storyboardScene))el.open=true;});
 root.querySelectorAll('[data-generation-group]').forEach(el=>{el.open=el.dataset.groupPrimary==='true'||expandedGroups.has(el.dataset.generationGroup);});
 root.querySelectorAll('[data-generation-arrangement]').forEach(el=>{el.open=expandedArrangements.has(el.dataset.generationArrangement);});
 restoreVoicePlayback(root,page==='postproduction'?project?.id:null,voicePlayback);
 root.dataset.canonProject=page==='canon'?(project?.id||''):'';
 root.querySelectorAll('.entity-details').forEach(el=>{el.open=expandedEntities.has(el.dataset.entity);});
 root.dataset.overviewProject=page==='overview'?(project?.id||''):'';
 if(sameOverview)root.querySelectorAll('main details').forEach(el=>{if(expanded.has(overviewDetailKey(el)))el.open=true;});
}
function projectsPage(){
 if(page==='projects-trash'&&!projectDeletionReady)return head('已刪除作品','作品刪除功能正等待服務更新，請稍後重新整理。',button('返回作品管理','navigate','data-page="projects"'));
 const trash=page==='projects-trash',items=trash?deletedProjects:projects;
 return `<div class="page-header"><div><div class="eyebrow">工作區</div><h1>${trash?'已刪除作品':'作品管理'}</h1><p class="muted">${trash?'作品資料仍保留在本機，可還原後繼續製作；刪除不會釋放磁碟空間。':`共 ${projects.length} 部作品。開啟作品以繼續製作，或建立新作品、導入故事。`}</p></div><div class="actions">${button(trash?'返回作品管理':'已刪除作品','navigate',`data-page="${trash?'projects':'projects-trash'}" ${projectDeletionReady?'':'disabled title="等待服務更新"'}`)}${!trash?button('建立作品／導入故事','new-project','','primary'):''}</div></div>`+
 (items.length?`<div class="grid">${items.map(p=>`<article class="card"><div class="card-body"><div class="meta"><span>作品 · 版本 ${p.revision}</span>${trash?'<span class="badge">已刪除</span>':project?.id===p.id?'<span class="badge approved">目前作品</span>':''}</div><h2>${esc(p.title)}</h2><p class="muted">${esc((p.idea||'').slice(0,160))}</p>${trash?`<p class="muted">刪除時間：${esc(new Date(p.deleted_at).toLocaleString('zh-HK'))}</p>`:''}<div class="actions">${trash?button('還原作品','restore-project',`data-id="${esc(p.id)}"`,'primary small'):button('開啟作品 →','project',`data-id="${esc(p.id)}"`,'primary small')+button('刪除作品','delete-project',`data-id="${esc(p.id)}" ${projectDeletionReady?'':'disabled title="等待服務更新"'}`,'danger small')}</div></div></article>`).join('')}</div>`:`<div class="panel empty"><h2>${trash?'沒有已刪除作品':'尚未建立作品'}</h2><p class="muted">${trash?'刪除的作品會顯示在這裡，可隨時還原。':'建立第一部作品，或導入已有故事開始製作。'}</p></div>`);
}
function clearCurrentProject(){
 const id=project?.id;project=null;selectedShot=null;selectedFrame=null;lastState='';
 if(!id||localStorage.getItem('continuity-project')===id)localStorage.removeItem('continuity-project');
}
async function deleteProjectDialog(id){
 if(!projectDeletionReady)throw Error('作品刪除功能正等待服務更新，請稍後重新整理。');
 const target=await api('/projects/'+id);
 modal('確認刪除作品',`<form id="delete-project-form"><div class="note error" role="alert"><strong>即將刪除「${esc(target.title)}」</strong><p>作品將從工作區及選單移除，無法繼續製作，直到你還原作品。</p><p>故事、章節、分鏡、圖片、配音、提示詞及歷史版本會保留，可在「已刪除作品」還原。這個操作不會釋放磁碟空間。</p></div><p>仍有生成、配音、排隊或待提交工作時，系統會阻止刪除。</p><label>請輸入完整作品名稱以確認：<strong>${esc(target.title)}</strong><input name="confirmation_title" aria-label="確認作品名稱" autocomplete="off" required></label><p id="delete-project-error" class="notice" role="alert"></p><div class="modal-footer">${button('取消','close')}<button type="submit" class="danger" disabled>確認刪除作品</button></div></form>`);
 const form=$('#delete-project-form'),input=form.elements.confirmation_title,submit=form.querySelector('[type="submit"]');
 input.oninput=()=>{submit.disabled=input.value!==target.title;};
 form.onsubmit=e=>{e.preventDefault();if(input.value!==target.title)return;guarded(async()=>{
  submit.disabled=true;$('#delete-project-error').textContent='';
  try{await api('/projects/'+id,{confirmation_title:input.value,revision:target.revision},'DELETE');if(project?.id===id)clearCurrentProject();close();page='projects';window.history.replaceState(null,'','#projects');await refresh(true);toast('作品已刪除，可在「已刪除作品」還原。');}
  catch(error){const errorBox=$('#delete-project-error');if(errorBox)errorBox.textContent=uiError(error.message);else toast(uiError(error.message));}
  finally{if(submit.isConnected)submit.disabled=input.value!==target.title;}
 });};
 input.focus();
}
function landing(){return `<div class="landing"><div class="eyebrow">由一個構思，建立連貫的故事世界</div><h1>讓你的故事<br>逐步成為作品。</h1><p class="lead">與創作引擎發展故事、建立角色、設計分鏡，並在製作過程中沿用已批准的角色與場景參考。</p>${button('開始新作品 →','new-project','','primary')}<div class="landing-rule"></div><div class="grid">${projects.map(p=>`<div class="card welcome-card" data-action="project" data-id="${p.id}"><div class="eyebrow">作品 · 版本 ${p.revision}</div><h2>${esc(p.title)}</h2><p class="muted">${esc(p.idea.slice(0,160))}</p><span>開啟作品 →</span></div>`).join('')}</div></div>`;}
function stats(){const p=project.production;return `<div class="stage-strip"><div class="stage"><strong>${p?'01 · 故事已建立':'01 · 發展故事'}</strong><span>${p?'可編輯的製作方案':'由你的創作目標開始'}</span></div><div class="stage"><strong>${p?p.canon.filter(e=>e.kind!=='voice'&&approved(e.id)).length:0} / ${p?.canon.filter(e=>e.kind!=='voice').length||0} 項視覺資產</strong><span>已批准、可重用的參考素材</span></div><div class="stage"><strong>${p?.shots.length||0} 個鏡頭</strong><span>${p?.edit_plan?.length?`${p.edit_plan.reduce((n,e)=>n+e.planned_edit_out-e.planned_edit_in,0).toFixed(2)} 秒預定成片 · `:''}${p?.shots.reduce((n,s)=>n+s.duration,0)||0} 秒生成素材</span></div><div class="stage"><strong>${p?p.shots.flatMap(s=>s.keyframes).filter(f=>approved(f.id)).length:0} 張關鍵幀已批准</strong><span>可用作 H3 關鍵幀參考</span></div></div>`;}
function jobList(items){return (items.some(j=>j.provider==='comfy_local')?renderLocalRuntime(project?.local_runtime,esc):'')+items.map(j=>j.prompt_id!==undefined?`<div class="job-row"><div class="job-main"><h3>H3 影片 · ${esc(targetName(j.shot_id))}</h3><small>本機 ComfyUI</small><p>${esc(j.state)}</p><button type="button" class="small" data-render-action="detail" data-id="${esc(j.id)}">影片工作記錄</button></div></div>`:`<div class="job-row"><div class="job-main"><h3>${esc(displayLabel(j.capability))} ${j.target_id?'· '+esc(targetName(j.target_id)):''}</h3><small>${esc(providerName(j.provider))} · ${new Date(j.created).toLocaleTimeString('zh-HK')} ${j.state==='running'?'· 處理中，可繼續使用其他頁面':''}</small>${j.error?`<p class="notice overflow">${esc(uiError(j.error))}</p>`:''}${queueDetail(j)?`<p class="muted">${esc(queueDetail(j))}</p>`:''}${renderStagedProgress(j,esc)}${j.state==='succeeded'&&['narrative','storyboard'].includes(j.capability)?button('審閱方案','proposal',`data-id="${j.id}"`,'small primary'):''}${j.state==='succeeded'&&j.capability==='h3_shot'?button('比較新版','review-shot-prompt',`data-id="${j.id}"`,'small primary'):''}${j.state==='succeeded'&&j.capability==='h3_global'?button('比較新版','review-scene-prompt',`data-id="${j.id}"`,'small primary'):''}${j.state==='awaiting_input'?button('提交結果','manual',`data-id="${j.id}"`,'small'):''}${['failed','interrupted'].includes(j.state)?(canResumeStages(j)?button(stagedResumeLabel(j),'resume-stages',`data-id="${j.id}"`,'small primary'):button('恢復已保存結果','recover',`data-id="${j.id}"`,'small'))+(canResumeStages(j)&&hasSavedStages(j)?'':button(j.input?.chapter_pipeline?'從頭建立新方案':j.provider==='comfy_local'?'取回本機結果／重試':'按目前設定重試','retry',`data-id="${j.id}"`,'small')):''}${['queued','running','awaiting_input'].includes(j.state)?button(j.error?.startsWith('已要求取消')?'正在取消…':'取消工作','cancel-job',`data-id="${j.id}" ${j.error?.startsWith('已要求取消')?'disabled':''}`,'small quiet'):''}${button('詳情','job-detail',`data-id="${j.id}"`,'small quiet')}</div>${badge(j.state)}</div>`).join('');}
function newProject(){
 modal('建立作品｜故事大綱與視覺方向',`<form id="new-form"><label>你現在有甚麼？<select name="source_kind"><option value="outline">故事大綱 — 建立持續創作、多章節的作品</option><option value="story">已有劇情／故事 — 保留情節，整理成可拍的分鏡</option><option value="screenplay">完整劇本 — 保留原文與對白，直接設計分鏡</option><option value="idea">只有構思 — 讓創作引擎發展故事</option></select></label><label>作品名稱<input name="title" placeholder="最後一盞燈" required maxlength="150"></label><label id="story-file-label">匯入檔案（或直接在下方貼上）<input id="story-file" type="file" accept=".txt,.md,.docx"></label><p class="muted">支援 TXT、Markdown、Word DOCX，最大 2 MB。文字上限 20,000 字，不限制分行／段落數；整體大綱與各章內容分開保存，可隨時新增章節。DOCX 讀取正文文字與表格，圖片及頁眉頁尾不會匯入；PDF 請先複製文字。</p><label><span id="source-label">故事大綱</span><textarea name="idea" rows="9" required minlength="3" placeholder="寫下故事背景、主角、核心衝突與長線走向；不需要一次寫完所有章節。"></textarea></label><p id="import-status" class="muted" role="status">大綱會獨立保存；建立作品後，再逐章發展劇情與分鏡。</p>${renderVisualStylePicker()}<label class="inline-check"><input type="checkbox" name="start_now" checked> 儲存後先推薦適合的導演風格</label><p class="muted">方案完成後先由你審閱，再接角色、場景參考圖及 H3。這一步只處理文字。</p><div class="modal-footer"><button type="submit" class="primary">保存大綱，建立作品 →</button></div></form>`,true);
 const form=$('#new-form'),input=form.elements.idea,submit=form.querySelector('[type="submit"]'),status=$('#import-status');let filename='',importing=false;
 form.elements.source_kind.onchange=()=>{const kind=form.elements.source_kind.value;$('#story-file-label').hidden=kind==='idea';$('#source-label').textContent={outline:'故事大綱',idea:'故事構思',story:'原文劇情',screenplay:'原文劇本'}[kind];input.placeholder=kind==='outline'?'故事背景、主角、核心衝突與長線走向；之後逐章創作。':'貼上這個短篇的構思、劇情或劇本。';status.textContent=kind==='outline'?'大綱會獨立保存；建立作品後，再逐章發展劇情與分鏡。':'原文獨立保存，方案完成後先審閱。';submit.textContent=kind==='outline'?'保存大綱，建立作品 →':'保存原文，建立作品 →';};
 $('#story-file').onchange=async e=>{
  const file=e.target.files[0];if(!file)return;importing=true;submit.disabled=true;status.textContent='正在讀取檔案…';
  try {if(file.size>2000000)throw Error('檔案超過 2 MB，請分開導入。');const data=new FormData();data.append('file',file);const result=await api('/story-import/preview',data);input.value=result.text;filename=result.filename;if(!form.elements.title.value.trim())form.elements.title.value=filename.replace(/\.[^.]+$/,'').slice(0,150);status.textContent=`已讀取 ${filename}，共 ${Array.from(result.text).length} 字。請檢查下方文字，再保存。`;}
  catch(error){status.textContent=uiError(error.message)+' 原有文字仍保留。';}
  finally{importing=false;submit.disabled=false;}
 };
 form.onsubmit=e=>{e.preventDefault();if(importing)return;guarded(async()=>{
  if(Array.from(input.value).length>20000)throw Error('內容超過 20,000 字，請按單集或場景分開導入；內容尚未保存。');
  submit.disabled=true;
  try {const kind=form.elements.source_kind.value,run=form.elements.start_now.checked;
   const created=await api('/projects',{title:form.elements.title.value,idea:input.value,style:readVisualStyle(form),source_kind:kind,source_filename:kind==='idea'?'':filename});
   project=created;page='overview';updateProjectURL(created.id,'overview');localStorage.setItem('continuity-project',created.id);close();await refresh(true);
   if(run){try{await start('director_style');}finally{await refresh(true);}}
  }finally{submit.disabled=false;}
 });};
}
function overview(){if(project.source_kind==='outline')return head('故事與章節','查看目前進度，繼續章節製作；故事大綱與視覺方向保存在下方。')+renderStoryOverview(project,{esc,button,head,stats,jobList,renderDirectorStyles})+overviewDirecting();const p=project.production,imported=project.source_kind&&project.source_kind!=='idea';return head(p?'故事與章節':imported?'由你的原文，<br>接續建立分鏡。':'每部作品<br>都由一個好構思開始。',p?esc(p.logline):'將創作方向交給所選引擎；先審閱故事、角色、場景和分鏡方案，再開始製作圖片。',button(imported?(p?'由原文修訂分鏡':'由原文建立分鏡 →'):p?'發展修訂方案':'交由以下服務發展：'+esc(providerLabel('narrative'))+' →','develop','','primary'))+`<details class="panel"><summary>導演風格與拍法</summary>${renderDirectorStyles(project,esc,button)}</details>`+overviewDirecting()+`${imported?`<div class="panel"><div class="eyebrow">已保存原文 · ${project.source_kind==='screenplay'?'完整劇本':'已有劇情'}${project.source_filename?' · '+esc(project.source_filename):' · 貼上文字'}</div><p>原文 → 分鏡方案 → 審閱採用 → 角色與場景參考 → 分鏡圖 → H3 / Ref2VA</p><details><summary>閱讀保存的原文</summary><div class="prose">${esc(project.idea)}</div></details><p class="muted">分鏡方法：保留原文、逐段對照及連戲檢查，由 ${esc(providerLabel('storyboard'))} 執行。先審閱文字方案，再進入圖片製作。</p></div>`:''}<div class="two-col"><div>${!p?`<div class="panel"><div class="eyebrow">創作目標</div><p class="story-prose">${esc(project.idea)}</p><div class="eyebrow">視覺風格</div><p>${esc(project.style)}</p></div>`:`<div class="panel"><div class="panel-header"><h2>故事</h2>${button('編輯故事與劇本','edit-writing','','small')}</div><div class="story-prose">${esc(p.story||p.logline)}</div><details><summary>閱讀劇本與對白</summary><div class="prose">${esc(p.screenplay)}</div></details></div><div class="panel"><div class="eyebrow">視覺方向</div><p>${esc(p.style)}</p><div class="actions">${button('建立角色 →','navigate','data-page="canon"','primary')}${button('開啟分鏡板','navigate','data-page="shots"')}</div></div>`}</div><div><div class="panel"><h3>製作動態</h3>${project.jobs.length?jobList(project.jobs.slice(0,7)):'<p class="muted">製作方案和生成工作會顯示在這裡，所有結果均會保存以供審閱。</p>'}</div>${p?`<div class="panel"><h3>連續性檢查</h3>${project.qc.filter(i=>i.level!=='pending').length?project.qc.filter(i=>i.level!=='pending').map(i=>`<div class="note error">${esc(uiError(i.message))}</div>`).join(''):'<p class="muted">未發現同場景中缺乏解釋的狀態變化。</p>'}${button('品質審查 · '+esc(providerLabel('qc')),'qc','','small')}${project.jobs.filter(j=>j.capability==='qc'&&j.result).slice(0,1).map(j=>`<div class="note">${badge(j.result.verdict)} ${esc(j.result.summary)}<ul>${j.result.issues.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`).join('')}</div>`:''}</div></div>`;}
function overviewDirecting(){return project.production?`<details id="overview-directing" class="panel overview-directing"><summary>劇情表達與剪接安排</summary><p class="muted">查看每場戲想表達甚麼，以及鏡頭的先後和取用片段。預定取用的開始與結束時間，仍需在影片生成後看片確認。</p><div class="actions">${button('開啟後製配音','navigate','data-page="postproduction"')}</div>${directingPanel(project,esc)}</details>`:'';}
function missingPlan(){return head('先建立故事','發展並採用製作方案，建立角色設定與分鏡。',button('開啟故事與章節','navigate','data-page="overview"','primary'));}
function isCharacterAsset(a){return project.production?.canon.some(e=>e.id===a?.target_id&&e.kind==='character');}
function sheetVerified(a){return a?.review?.character_sheet==='pass';}
function sheetAccepted(a){return a?.status==='approved'&&a.note?.startsWith('[人工覆核採用]');}
function sheetNotice(a){return isCharacterAsset(a)?`<div class="note">${sheetVerified(a)?'✓ 四視圖審查通過':sheetAccepted(a)?'已人工採用 · 保留審查意見':'四視圖待更新／審查：正面全身 → 側面全身 → 背面全身 → 正面臉部特寫'}</div>`:'';}
function isPublicAsset(entity){return project.asset_groups?.public_ids?.includes(entity.id)??entity.scope==='public';}
function assetScopeStatus(entity){return `<p class="asset-scope muted">${isPublicAsset(entity)?'公共資產':'場景資產 · 按需求自動歸類'}</p>`;}
function voiceAssetCard(e){
 const takes=(project.postproduction?.takes||[]).filter(t=>t.character_id===e.id&&t.kind==='voice'&&t.state==='succeeded'),sample=takes.find(t=>t.selected&&t.current)||takes.find(t=>t.current)||takes[0];
 return `<article class="card voice-asset" data-asset-id="${esc(e.id)}"><div class="card-body"><div class="eyebrow">聲音資產 · 只聞其聲</div><h2>${esc(e.name)}</h2>${assetScopeStatus(e)}<p>${esc(e.description)}</p><ul class="facts">${e.facts.map(f=>`<li>${esc(f)}</li>`).join('')}</ul><p class="note">不出鏡，無需人物圖片或四視圖。分鏡保留此聲音的對白與時間。</p>${sample?.audio_url?`<audio controls preload="none" src="${esc(sample.audio_url)}" aria-label="${esc(e.name)}試音"></audio><p class="muted">${sample.selected?'已採用音色':'已保存試音候選，尚待選用'}</p>`:'<p class="muted">可到後製配音設定聲線或匯入人聲。</p>'}<div class="actions">${button('音色與配音','open-voice',`data-id="${esc(e.id)}"`,'primary small')}${button('編輯資產設定','edit-entity',`data-id="${esc(e.id)}"`,'small')}</div></div></article>`;
}
function entityCard(e){if(e.kind==='voice')return voiceAssetCard(e);const character=e.kind==='character',crowd=e.kind==='crowd',pending=assetsFor(e.id).find(x=>x.status==='pending'&&needsAssetReview(x,assetsFor(e.id))),a=(character||crowd)&&pending?pending:latest(e.id),progress=imageStatus(e.id);return `<article class="card canon-card ${a?.status==='approved'?'asset-approved':''} ${progress?.active?'is-generating':''}">${a?`<img class="card-image ${character||crowd?'character-sheet':'portrait'}" src="${imageURL(a.id)}" alt="${esc(e.name)} ${character?'角色參考圖':'參考圖'}" data-action="lightbox" data-id="${a.id}">`:`<div class="frame-empty"><span>${e.kind==='location'?'⌂':e.kind==='character'?'◌':'◇'}</span>${progress?.active?esc(progress.label):character?'四視圖尚未生成':crowd?'群像參考圖尚未生成':'尚未生成參考圖'}</div>`}<div class="card-body"><div class="canon-card-heading"><div><span class="muted">${esc(displayLabel(e.kind))}</span><h2>${esc(e.name)}</h2></div>${progress?.active?`<span class="badge running">${esc(progress.label)}</span>`:a?badge(a.status):badge('unestablished')}</div>${assetScopeStatus(e)}${imageProgressMarkup(project,e.id,esc)}${character?`<p class="canon-sheet-status ${sheetVerified(a)?'verified':'notice'}">${sheetVerified(a)?'✓ 四視圖審查通過':sheetAccepted(a)?'已人工採用 · 保留審查意見':pending?'新版四視圖候選 · 等待審查':'需要四視圖 · 現有圖片未通過四視圖審查'}</p>`:''}${a&&a.status!=='approved'?button('採用目前圖片','adopt-identity-image',`data-id="${a.id}"`,'small canon-adopt-current'):''}<div class="actions entity-actions">${button(progress?.active?esc(progress.label):a?'製作新版':character?'生成角色四視圖':crowd?'生成群像參考圖':'生成參考圖','generate',`data-target="${e.id}" data-force="${!!a}" ${progress?.active?'disabled':''}`,'primary small')}${button('編輯身份設定','edit-entity',`data-id="${e.id}"`,'small')}${a?button('傳送到 ComfyUI','send-comfy',`data-id="${a.id}"`,'small')+button('在資料夾中顯示','reveal-image',`data-id="${a.id}"`,'small'):''}</div><details class="entity-details" data-entity="${esc(e.id)}"><summary>身份詳情與固定設定</summary><p>${esc(e.description)}</p><ul class="facts">${e.facts.map(f=>`<li>${esc(f)}</li>`).join('')}</ul>${crowd?'<p class="muted">群像參考保留人物差異、衣著及群體特徵；各場人數與位置按分鏡鎖定。</p>':''}${productionReferences(e.id)}</details>${pending?`<div class="note">${character?'新版圖片等待審查及批准。':'已送到審查室。'} ${button('前往審查 →','navigate','data-page="review"','small quiet')}</div>`:''}</div></article>`}
function canon(){
 const p=project.production;if(!p)return missingPlan();
 const grouped=project.asset_groups;
 return head('角色與場景資產','公共身份貫穿作品；章節按 Scene 顯示實際用到的資產。同一身份只保存一份，聲音角色只接配音。',button('上傳共用風格參考','upload-input-reference','','primary'))+
 `<details class="panel"><summary>圖片與聲音的製作方式</summary><p>個別出鏡角色使用四視圖；群眾演員使用群像參考。廣播、旁白及從未露面的聲音角色使用音色／配音，無需人物圖片。圖片與音檔均由你按「生成」才製作。</p><p>在「編輯身份設定」勾選「設為公共資產」，儲存後即可讓作品共用此身份。場景資產由系統按分鏡中的實際需求歸類，無需手動選擇場景；分類不會複製或重製素材。</p></details>${productionReferences('')}`+
 (grouped?renderAssetGroups(grouped,{renderEntity:id=>entityCard(p.canon.find(e=>e.id===id)),esc,nameFor:targetName}):`<div class="grid">${p.canon.map(entityCard).join('')}</div>`);
}
function shots(){const p=project.production;if(!p)return missingPlan();let s=p.shots.find(s=>s.id===selectedShot)||p.shots[0];selectedShot=s.id;const frameTime=k=>k.moment==='start'?0:k.moment==='end'?s.duration:k.source_time,frames=[...s.keyframes].sort((a,b)=>frameTime(a)-frameTime(b));let f=frames.find(f=>f.id===selectedFrame)||frames[0];selectedFrame=f.id;const a=latest(f.id),progress=imageStatus(f.id),scene=p.scenes.find(x=>x.id===s.scene_id),ids=[...new Set([...s.entity_ids,scene.location_id])].filter(id=>p.canon.find(e=>e.id===id)?.kind!=='voice'),missing=ids.filter(id=>!approved(id));return renderStoryboard(project)+head('每個鏡頭，每個細節','以已批准的角色與場景為基礎，規劃每個鏡頭及轉場前後的狀態。',button('修訂導演方向','revise-shot',`data-id="${s.id}"`,'primary')+button('編輯鏡頭','edit-shot',`data-id="${s.id}"`))+`<div class="shot-layout"><div class="shot-list">${p.scenes.map(sc=>`<div class="scene-label">${esc(sc.title)}</div>${p.shots.filter(x=>x.scene_id===sc.id).map(x=>`<button class="shot-button ${x.id===s.id?'selected':''}" data-action="select-shot" data-id="${x.id}"><span class="shot-number">${String(p.shots.indexOf(x)+1).padStart(2,'0')}</span><span><strong>${esc(x.title)}</strong><small>${x.duration} 秒 · ${x.keyframes.length} 張關鍵幀</small></span></button>`).join('')}`).join('')}</div><div><div class="panel"><div class="panel-header"><div><div class="eyebrow">${esc(scene.title)} / ${s.duration} 秒</div><h2>${esc(s.title)}</h2></div>${a?badge(a.status):badge('planned')}</div>${a?.image_output_quality?.valid===false?`<div class="frame-empty" style="aspect-ratio:16/9"><span>!</span><p>生成結果無有效畫面</p><small>${esc(a.image_output_quality.message)}</small></div>`:a?`<img class="hero-frame" src="${imageURL(a.id)}" alt="${esc(f.description)}" data-action="lightbox" data-id="${a.id}">`:`<div class="frame-empty" style="aspect-ratio:16/9"><span>▧</span>${esc(f.description)}</div>`}${imageProgressMarkup(project,f.id,esc)}<div class="keyframe-tabs">${frames.map(k=>button(k.moment==='start'?'起始幀':k.moment==='end'?'結束幀':k.source_time+' 秒關鍵幀','select-frame',`data-id="${k.id}"`,f.id===k.id?'selected':'')).join('')}</div><details class="frame-description" data-frame-description="${esc(f.id)}"><summary>查看構圖與畫面狀態</summary><p class="prose">${esc(f.description)}</p></details><div class="actions">${a?imageTransfer(a.id,s.id+' '+s.title+' '+f.moment):''}${button(progress?.active?esc(progress.label):a?'生成另一版本':'生成關鍵幀','generate',`data-target="${f.id}" data-force="${!!a}" ${missing.length||progress?.active?'disabled':''}`,'primary')}${button('匯入關鍵幀','upload',`data-target="${f.id}" ${missing.length?'disabled':''}`,'small')}${a?.status==='pending'?button('審閱這張關鍵幀 →','navigate','data-page="review"','small'):''}</div>${missing.length?`<div class="note">請先批准：${missing.map(id=>esc(targetName(id))).join(', ')}. ${button('開啟角色與場景','navigate','data-page="canon"','small quiet')}</div>`:''}<div class="eyebrow" style="margin-top:25px">自動連結的參考圖</div><p class="muted reference-help">點選素材，可確認生成或上傳製作參考圖。</p><div class="reference-row">${ids.map(id=>{const r=approved(id),progress=imageStatus(id);return `<button type="button" class="ref ref-action" data-action="generate" data-target="${esc(id)}" data-force="${!!latest(id)}" aria-label="${esc(targetName(id))} · ${progress?.active?esc(progress.label):r?'已批准的參考圖':'待批准'} · 生成或上傳參考圖" title="點選以生成或上傳參考圖">${r?`<img src="${imageURL(r.id)}" alt="">`:''}<span>${esc(targetName(id))}<br>${progress?.active?esc(progress.label):r?'已批准的參考圖':'待批准'}</span><span aria-hidden="true">${progress?.active?'◷':'＋'}</span></button>`}).join('')}</div>${shotIntentMarkup(s,esc)}<div class="shot-info">${[['景別與角度',s.framing+' · '+s.angle],['鏡頭運動',s.camera],['走位與表情',s.blocking+' '+s.expression],['動作',s.action]].map(([l,v])=>`<div><div class="label">${l}</div><p>${esc(v)}</p></div>`).join('')}</div><details><summary>時間節奏、對白與連續性</summary><div class="prose">${s.beats.map(b=>`${b.start}–${b.end}s · ${esc(b.action)}`).join('\n')}\n\n${s.dialogue.map(d=>`${d.start}–${d.end}s · ${esc(targetName(d.entity_id))}: “${esc(d.text)}” (${esc(d.delivery)})`).join('\n')}</div><div class="shot-info"><div><div class="label">起始狀態</div>${s.start_state.map(x=>`<p>${esc(targetName(x.entity_id))} · ${esc(x.key)}: ${esc(x.value)}</p>`).join('')}</div><div><div class="label">結束狀態</div>${s.end_state.map(x=>`<p>${esc(targetName(x.entity_id))} · ${esc(x.key)}: ${esc(x.value)}</p>`).join('')}</div></div>${s.transition_note?`<p>轉場連續性：${esc(s.transition_note)}</p>`:''}</details>${a?`<details><summary>圖片提示詞與參考來源</summary>${imagePromptNote(a)}<pre>${esc(a.prompt)}</pre><p class="muted">服務商：${esc(providerName(a.provider))} · 參考素材：${esc(a.reference_ids.join(', ')||'首次建立身份')}</p></details>`:''}</div></div></div>`;}
function review(){if(!project.production)return missingPlan();let items=groupAssetVersions(project.assets,{reviewOnly:true}).map(g=>g.primary);return renderBoardNext(project)+head('審閱並決定採用版本','只列出待審圖片，每組素材顯示一張。過時圖片不計入待審；可從「查看全部素材」或分鏡頁製作新版，舊圖及審查記錄仍保留。',button('查看全部素材','all-assets'))+(items.length?`<div class="grid">${items.map(assetCard).join('')}</div>`:`<div class="panel empty"><div class="symbol">✓</div><h2>${boardTask(project).scene?'其他素材暫時沒有待審版本':'暫時沒有待審素材'}</h2><p class="muted">${boardTask(project).scene?'分鏡畫面仍有待辦，請由上方「分鏡畫面審閱」繼續。':'新圖片及審查結果會顯示在這裡，方便你決定採用版本。'}</p>${button('開啟鏡頭','navigate','data-page="shots"','primary')}</div>`)+`<div class="section-line"><h2>進行中的工作</h2></div><div class="panel">${activeJobs().length?jobList(activeJobs()):'<p class="muted">目前沒有進行中的工作。</p>'}</div>`;}
function imagePromptNote(a){
 const job=project.jobs.find(j=>j.id===a.job_id);
 const note=a.provider==='manual'?'匯入圖片紀錄':job?.input?.image_prompt_stage==='render'?'已整理並交付生圖的提示詞':'歷史組裝指示：包含當時的原始製作資料，未經新版圖片提示詞整理。';
 return `<p class="muted">${note}</p>`;
}
function imageReferenceEvidence(a){
 const job=project.jobs.find(j=>j.id===a.job_id),input=job?.input||{};
 const ids=[...new Set([...(a.reference_ids||[]),...(input.source_asset_id?[input.source_asset_id]:[])])];
 const uploads=(input.input_reference_ids||[]).map(id=>(project.input_references||[]).find(r=>r.id===id)).filter(Boolean);
 return `<p class="muted">${input.local_image_plan?esc(input.local_image_plan.name+' · '+input.local_image_plan.reason)+'<br>':''}此版本的輸入：${ids.length} 張素材參考、${uploads.length} 張上傳參考${input.layout_reference?'，另附四視圖排版範例':''}。</p>${imageLoraMarkup(input.local_image_plan,esc)}<div class="reference-row">${ids.map(id=>`<img width="80" src="${imageURL(id)}" alt="${id===input.source_asset_id?'修訂來源':'生成時的素材參考'}" data-action="lightbox" data-id="${id}">`).join('')}${uploads.map(r=>`<a href="${inputReferenceURL(r)}" target="_blank"><img width="80" src="${inputReferenceURL(r)}" alt="${esc(r.name)}" title="${esc(r.name)} · ${r.purpose==='style'?'風格參考':'外觀／形狀參考'}"></a>`).join('')}</div>`;
}
function assetCard(a){const regeneration=generationStatus(project,a.target_id);return `<article class="card ${a.status==='approved'?'asset-approved':''}"><img class="card-image ${isCharacterAsset(a)?'character-sheet':''}" src="${imageURL(a.id)}" alt="${esc(targetName(a.target_id))}" data-action="lightbox" data-id="${a.id}"><div class="card-body"><div class="meta"><span>${esc(providerName(a.provider))}</span>${badge(a.status)}</div><h3>${esc(targetName(a.target_id))}</h3><div class="actions">${button('版本清單 · '+project.assets.filter(x=>x.target_id===a.target_id).length+' 張','asset-versions',`data-target="${a.target_id}"`,'small')}${a.status==='rejected'?button('刪除此拒絕版本','delete-rejected-asset',`data-id="${a.id}"`,'small'):''}</div>${imageProgressMarkup(project,a.target_id,esc)}${sheetNotice(a)}${a.review?`<p>${badge(a.review.verdict)} ${esc(a.review.summary)}</p>${a.review.issues.length?`<ul class="facts">${a.review.issues.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}`:'<p class="muted">等待視覺審查；你可以先查看圖片。</p>'}${a.note?`<p class="notice">${esc(a.status==='stale'?displayLabel(a.note):a.note)}</p>`:''}${a.status==='stale'?'<p class="muted">這張圖已過時，不需再次審查。請按「修訂」使用目前參考圖製作新版，再審查新圖。</p>':''}<div class="actions">${a.status!=='stale'?button(isCharacterAsset(a)&&!sheetVerified(a)?'人工確認採用':'批准','approve',`data-id="${a.id}"`,'primary small'):''}${button('拒絕','reject',`data-id="${a.id}"`,'small')}${button('修訂','generate',`data-target="${a.target_id}" data-force="true" data-source-id="${a.id}" data-progress-target="${a.target_id}" ${regeneration?.active?'disabled':''}`,'small')}${a.status==='stale'?'':button('再次審查','review-asset',`data-id="${a.id}"`,'small quiet')}</div><details><summary>參考圖與生成指示</summary>${imageReferenceEvidence(a)}${imagePromptNote(a)}<pre>${esc(a.prompt)}</pre></details></div></article>`;}
function inputReferenceURL(r){return `/api/projects/${project.id}/input-references/${r.id}/image`;}
function productionReferences(target){
 const refs=(project.input_references||[]).filter(r=>r.target_id===target);
 if(!refs.length)return '';
 return `<details class="production-inputs" open><summary>${target?'已上傳的製作參考':'作品共用風格參考'} · ${refs.length} 張</summary><div class="reference-row">${refs.map(r=>`<div class="ref"><a href="${inputReferenceURL(r)}" target="_blank"><img src="${inputReferenceURL(r)}" alt="${esc(r.name)}"></a><span>${esc(r.name)}<br>${r.purpose==='style'?'風格參考':'外觀／形狀參考'} · 原圖已保存${r.original_filename?`<br><small>原檔：${esc(r.original_filename)}</small>`:''}<br>${button('在資料夾中顯示','reveal-input-reference',`data-id="${esc(r.id)}"`,'small quiet')}${button('複製圖片路徑','copy-input-reference-path',`data-id="${esc(r.id)}"`,'small quiet')}</span></div>`).join('')}</div><small class="muted">原圖已存入此作品素材庫，不依賴原本的檔案位置；生成時可再次選用。</small></details>`;
}
function uploadProductionReference(target,onReturn,initialFile){
 const referenceProjectId=project.id;
 modal('上傳製作參考'+(target?' · '+targetName(target):' · 共用風格'),`<form id="production-reference-form"><label>圖片用途<select name="purpose"><option value="style">風格參考 — 畫風、色調、材質、光線</option>${target?'<option value="identity" selected>外觀／形狀參考 — 用這張圖製作所需素材</option>':''}</select></label>${referenceDropMarkup()}<p class="muted">保存後會按作品及素材名稱整理原圖，保留原檔名與版本，不依賴原本檔案位置。保存不會開始生成；之後可重用這張圖。</p><div class="modal-footer">${onReturn?'<button type="button" id="return-to-generation">返回生成設定</button>':button('取消','close')}<button type="submit" class="primary">保存參考圖</button></div></form>`);
 const drop=bindReferenceDrop($('#production-reference-form [data-reference-drop]'),{initialFile});disposeReferenceDrop=drop.dispose;
 $('#production-reference-form').onsubmit=e=>{e.preventDefault();guarded(async()=>{const files=drop.getFiles();if(!files.length)throw Error('請先拖放或選擇參考圖片。');const submit=e.target.querySelector('button[type=submit]'),purpose=new FormData(e.target).get('purpose');submit.disabled=true;let saved=0;try{for(const file of files){submit.textContent=`正在保存 ${saved+1} / ${files.length} 張…`;const data=new FormData();data.set('purpose',purpose);data.set('file',file,file.name);data.set('target_id',target);await api('/projects/'+referenceProjectId+'/input-references',data);saved++;drop.removeFile(file);}close();await refresh(true);toast(`已保存 ${saved} 張參考圖。按「生成」後才會製作圖片。`);if(onReturn)onReturn();}catch(error){throw Error(`已保存 ${saved} 張；未完成的圖片已保留，可再次保存。`+error.message);}finally{if(submit.isConnected){submit.disabled=false;submit.textContent='保存參考圖';}}});};
 if(onReturn)$('#return-to-generation').onclick=()=>onReturn();
}
function generationForm(target,force,source,draft){
 const progress=imageStatus(target);if(progress?.active){modal(targetName(target)+' · '+progress.label,imageProgressMarkup(project,target,esc)+`<p>此素材已有工作處理中，毋須重複生成。</p>${button('上傳製作參考','upload-input-reference',`data-target="${esc(target)}"`)}${button('關閉','close')}`);return;}

 if(project.production.canon.find(e=>e.id===target)?.kind==='voice'){return navigate('postproduction').then(()=>document.getElementById('voice-'+target)?.scrollIntoView({block:'start'}));}
 const entityKind=project.production.canon.find(e=>e.id===target)?.kind,character=entityKind==='character',crowd=entityKind==='crowd';
 const generateLabel=character?'生成四視圖':crowd?'生成群像參考圖':'生成圖片';
 const refs=(project.input_references||[]).filter(r=>!r.target_id||r.target_id===target);
 const feedback=draft?.feedback??(source?(project.assets.find(a=>a.id===source)?.review?.issues||[]).join('\n'):'');
 modal(generateLabel+' · '+targetName(target),`<form id="generation-form">${imageControls(settings,draft,esc)}<label>製作要求（可留空）<textarea name="feedback" rows="4" placeholder="${character?'例如：保留人物外觀，按作品畫風製作四視圖。':crowd?'例如：不同年齡的街坊，保留每個人的衣著與外貌差異。':'例如：保留參考圖外觀與材質，按作品畫風製作。'}">${esc(feedback)}</textarea></label>${referenceDropMarkup()}<h3>選用已保存的製作參考</h3>${refs.length?refs.map(r=>`<label class="generation-reference inline-check"><input type="checkbox" name="references" value="${r.id}" ${!draft||!draft.known.includes(r.id)||draft.selected.includes(r.id)?'checked':''}><img src="${inputReferenceURL(r)}" alt="${esc(r.name)}"><span>${esc(r.name)}<br><small>${r.purpose==='style'?'風格參考':'外觀／形狀參考'}</small></span></label>`).join(''):'<p class="muted">未有上傳製作參考；會按作品設定及已有的正式參考圖製作。</p>'}<label class="inline-check fidelity-option"><input type="checkbox" name="high_reference_fidelity" ${draft?.highFidelity?'checked':''}><span><strong>高度保留參考內容</strong><small>加強保留外觀、細節、材質及配色的指示，並非模型保真度參數。所選外觀參考主導今次候選圖；風格參考只影響畫風。${character?'個別角色仍按四視圖排版製作。':crowd?'群像會保留多人的外貌差異，避免重複同一張臉。':''}</small></span></label><p class="muted">只有按下方「${generateLabel}」才會開始。生成結果會另存，等待你審閱。</p><div class="modal-footer"><button type="button" id="generation-upload">上傳製作參考圖</button>${button('取消','close')}<button type="submit" class="primary">${generateLabel}</button></div></form>`,true);
 bindImageControls($('#generation-form'),settings);
 const openReferenceUpload=file=>{const f=new FormData($('#generation-form'));const saved={feedback:f.get('feedback'),selected:f.getAll('references'),known:refs.map(r=>r.id),highFidelity:f.has('high_reference_fidelity'),imageProvider:f.get('image_provider'),imageOperation:f.get('image_operation')||'auto',imageRegion:f.get('image_region'),imagePadding:f.get('image_padding')};uploadProductionReference(target,()=>generationForm(target,force,source,saved),file);};
 const drop=bindReferenceDrop($('#generation-form [data-reference-drop]'),{onSelect:openReferenceUpload});disposeReferenceDrop=drop.dispose;
 $('#generation-upload').onclick=()=>openReferenceUpload();
 $('#generation-form').onsubmit=e=>{e.preventDefault();guarded(async()=>{const submit=e.target.querySelector('button[type=submit]'),label=submit.textContent;submit.disabled=true;submit.textContent='正在提交生成工作…';try{const f=new FormData(e.target),highFidelity=f.has('high_reference_fidelity');const entity=project.production.canon.find(e=>e.id===target);if(highFidelity&&!f.getAll('references').length&&!source&&entity&&!approved(target))throw Error('請先選用或上傳一張參考圖片，再使用「高度保留參考內容」。');await start('image',target,referenceFidelityFeedback(f.get('feedback'),highFidelity),force,source,f.getAll('references'),imageOptions(f));close();render();await refresh(true);}finally{if(submit.isConnected){submit.disabled=false;submit.textContent=label;}}});};
}
function videoRow(){return project?.video_workflow?.shots.find(r=>r.shot_id===localStorage.getItem('video-shot:'+project.id))||project?.video_workflow?.shots[0];}
function ref2Active(){return page==='video'&&videoRow()?.mode==='REF2VA'&&!videoRow()?.conditioning;}
function videoPage(){
 if(!project.production)return missingPlan();
 return renderGenerationGroups(project,promptDrafts,{planningOnly:true})+renderVideoWorkflow(project,localStorage.getItem('video-group:'+project.id)||videoRow()?.shot_id,imageTransfer,promptDrafts,row=>{
  const scene=project.delivery?.scenes.find(s=>s.scene_id===row.scene_id);
  if(!scene)return '<p>正在載入場景提示詞…</p>';
  if(scene.preparation?.required&&scene.preparation.status==='needed')queueMicrotask(ensurePreparation);
  if(project.delivery.guidance_review?.status==='pending')queueMicrotask(ensureGuidance);
  return renderHandoff(project,handoff,handoffTransfers[project.id]??={},providerLabel('h3_scene'),promptDrafts,{sceneId:row.scene_id,shotId:row.shot_id});
 })+renderTakeLibrary(project);
}
async function ensurePreparation(){
 if(preparationRequest||!ref2Active())return;
 const scene=project.delivery.scenes.find(s=>s.scene_id===videoRow().scene_id);
 if(!scene?.preparation?.required||scene.preparation.status!=='needed')return;
 preparationRequest=true;
 try{await start('h3_prepare',scene.scene_id);await refresh(true);}catch(e){toast(uiError(e.message));}finally{preparationRequest=false;}
}
async function ensureGuidance(){
 if(guidanceRequest||!ref2Active()||project?.delivery?.guidance_review?.status!=='pending')return;
 guidanceRequest=true;
 try{await api('/projects/'+project.id+'/guidance/analyze',{});await refresh();}
 catch(e){toast(uiError(e.message));}
 finally{guidanceRequest=false;}
}
function updateProjectURL(pid,route,shotId=null){
 const url=new URL(location.href);url.searchParams.set('project',pid);
 if(shotId)url.searchParams.set('shot',shotId);else url.searchParams.delete('shot');
 url.hash=route;window.history.replaceState(null,'',url.pathname+url.search+url.hash);
}
function selectVideoShot(id){
 localStorage.removeItem('video-group:'+project.id);
 const r=project.video_workflow.shots.find(r=>r.shot_id===id);if(!r)return;
 if(page==='video')updateProjectURL(project.id,'video',id);
 localStorage.setItem('video-shot:'+project.id,id);handoff.select(project.id,r.scene_id,id);render();
}
function selectDirectorStep(sceneId,step='shared'){
 handoff.select(project.id,sceneId,step);render();
 const heading=$('#director-step-heading');heading?.focus({preventScroll:true});
 heading?.scrollIntoView({block:'nearest'});
}
function regenerateScenePrompt(sid){
 const pid=project.id,scene=project.delivery.scenes.find(s=>s.scene_id===sid),draft=promptDrafts.get(pid,sid,'shared');
 const source=draft?.text??scene.global_prompt;
 modal('重新生成 · '+scene.title,`<form id="regenerate-scene-form"><p>由 ${esc(providerLabel('h3_global'))} 重寫此 Scene 的全域提示詞；保留各 Shot 的文字，完成後比較並採用新版。</p><p class="muted">${draft?'會以你尚未儲存的文字作修改起點；原草稿保留。':'會以目前提示詞及本 Scene 的共用參考設定作修改起點。'}</p><label>修改要求（可留空）<textarea name="feedback" rows="4" placeholder="例如：精簡重複描述，保留人物外觀、場景材質及低照度；不要加入個別 Shot 的道具或動作。"></textarea></label><div class="modal-footer">${button('取消','close')}<button type="submit" class="primary">開始重新生成</button></div></form>`);
 $('#regenerate-scene-form').onsubmit=e=>{e.preventDefault();guarded(async()=>{const f=new FormData(e.target);await api('/projects/'+pid+'/jobs',{capability:'h3_global',target_id:sid,source_prompt:source,feedback:f.get('feedback')});close();await refresh(true);toast('已開始重新生成；完成後可比較新版，原有文字仍保留。');});};
}
async function reviewScenePrompt(jid){
 const pid=project.id,j=await api('/jobs/'+jid),fresh=await api('/projects/'+pid);
 if(j.project_id!==pid||j.capability!=='h3_global'||j.state!=='succeeded')throw Error('這個新版尚未完成。');
 const status=fresh.scene_prompt_regenerations?.[j.target_id],canAdopt=status?.job_id===jid&&!status.stale&&!status.adopted;
 modal('比較重新生成的全域提示詞',`<p>${status?.adopted?'此新版已採用。':canAdopt?'採用後只替換此 Scene 的全域提示詞，各 Shot 的文字保留；原版本留在工作及修訂記錄。':'來源已更新或已有較新方案，此版本仍保留供參考。'}</p><div class="two-col shot-prompt-comparison"><section><h3>修改起點</h3><pre>${esc(j.input.source_prompt)}</pre></section><section><h3>重新生成的版本</h3><pre>${esc(j.result.text)}</pre></section></div><div class="modal-footer">${button('保留目前版本','close')}${canAdopt?button('採用新版','adopt-scene-prompt',`data-id="${esc(jid)}"`,'primary'):''}</div>`,true);
}
function regenerateShotPrompt(sid,id){
 const pid=project.id,scene=project.delivery.scenes.find(s=>s.scene_id===sid),shot=scene.chapters.find(s=>s.shot_id===id),draft=promptDrafts.get(pid,sid,id);
 const source=draft?.text??shot.shot_prompt;
 modal('重新生成 · '+shot.title,`<form id="regenerate-shot-form"><p>由 ${esc(providerLabel('h3_shot'))} 重寫這個 Shot，完成後比較並採用新版。</p><p class="muted">${draft?'會以你尚未儲存的文字作修改起點；原草稿保留。':'會以目前提示詞及已採用分鏡作修改起點。'}</p><label>修改要求（可留空）<textarea name="feedback" rows="4" placeholder="例如：減少重複描述，清楚交代誰拿着甚麼；運鏡更克制。"></textarea></label><div class="modal-footer">${button('取消','close')}<button type="submit" class="primary">開始重新生成</button></div></form>`);
 $('#regenerate-shot-form').onsubmit=e=>{e.preventDefault();guarded(async()=>{const f=new FormData(e.target);await api('/projects/'+pid+'/jobs',{capability:'h3_shot',target_id:id,source_prompt:source,feedback:f.get('feedback')});close();await refresh(true);toast('已開始重新生成；完成後可比較新版，原有文字仍保留。');});};
}
async function reviewShotPrompt(jid){
 const pid=project.id,j=await api('/jobs/'+jid),fresh=await api('/projects/'+pid);
 if(j.project_id!==pid||j.capability!=='h3_shot'||j.state!=='succeeded')throw Error('這個新版尚未完成。');
 const status=fresh.shot_prompt_regenerations?.[j.target_id],canAdopt=status?.job_id===jid&&!status.stale&&!status.adopted;
 modal('比較重新生成的分鏡提示詞',`<p>${status?.adopted?'此新版已採用。':canAdopt?'採用後只替換這個 Shot 的提示詞；原版本留在工作及修訂記錄。':'來源已更新或已有較新方案，此版本仍保留供參考。'}</p><div class="two-col shot-prompt-comparison"><section><h3>修改起點</h3><pre>${esc(j.input.source_prompt)}</pre></section><section><h3>重新生成的版本</h3><pre>${esc(j.result.text)}</pre></section></div><div class="modal-footer">${button('保留目前版本','close')}${canAdopt?button('採用新版','adopt-shot-prompt',`data-id="${esc(jid)}"`,'primary'):''}</div>`,true);
}
function deliveryChapter(id){return project.delivery.scenes.flatMap(s=>s.chapters).find(c=>c.shot_id===id);}
function editableDelivery(sceneId){
 const cfg=structuredClone(project.delivery.configuration);cfg.production_revision=project.revision;
 if(sceneId){const rendered=project.delivery.scenes.find(s=>s.scene_id===sceneId),scene=cfg.scenes[sceneId]??={chapters:{}};
  scene.global_prompt=rendered.global_prompt;scene.chapters??={};
  for(const c of rendered.chapters){const ch=scene.chapters[c.shot_id]??={};ch.shot_prompt=c.shot_prompt;}
 }
 return cfg;
}
async function saveDelivery(cfg){await api('/projects/'+project.id+'/delivery',cfg,'PUT');close();await refresh(true);toast('Scene 與 Shot 提示詞已保存。');}
function h3Legacy(){if(!project.production)return missingPlan();return head('首尾幀模式提示詞','H3 提示詞沿用已批准的導演方向、對白時間與首尾幀參考。匯出資料包含按上傳次序排列的參考圖。')+project.h3.map(h=>`<div class="panel"><div class="panel-header"><div><div class="eyebrow">${esc(h.mode)} · ${h.duration}s · ${h.refined_by?'已由以下服務修訂：'+esc(h.refined_by):h.ready?'已整理導演方向':'未整理草稿 · 請先交由服務商修訂'}</div><h2>${esc(targetName(h.shot_id))}</h2></div><div class="actions">${button('複製提示詞','copy-h3',`data-id="${h.shot_id}" ${h.ready?'':'disabled'}`,'small')}${button('交由服務商修訂','refine-h3',`data-id="${h.shot_id}"`,'small primary')}</div></div>${!h.references.length?'<div class="note">目前為文字生成影片模式；批准關鍵幀後會自動加入圖片參考。</div>':`<p class="muted">「在資料夾中顯示」會開啟原圖所在的本機資料夾，並選取該參考圖。</p><div class="h3-references">${h.references.map(r=>`<article class="h3-reference"><h3>${esc(r.label)} · ${r.moment==='start'?'起始幀':'結束幀'}</h3><img src="${imageURL(r.asset_id)}" alt="${esc(targetName(h.shot_id)+' · '+r.label+' · '+r.moment)}" data-action="lightbox" data-id="${r.asset_id}"><div class="actions">${imageTransfer(r.asset_id,h.shot_id+' '+targetName(h.shot_id)+' '+r.label+' '+r.moment)}</div></article>`).join('')}</div>`}<pre>${esc(h.text)}</pre></div>`).join('');}
function eventText(e){
 const d=String(e.detail||'');
 if(e.kind==='job'){const m=d.match(/^([^:]+): (.*?) → (.+)$/);if(m)return `${displayLabel(m[1])}：${targetName(m[2])||'作品'} → ${displayLabel(m[3])}`;}
 if(e.kind==='asset'&&d.startsWith('Image ready for review: '))return '圖片已送審：'+targetName(d.slice(24));
 if(e.kind==='decision'){const m=d.match(/^([^:]+): (approved|rejected)\s*(.*)$/s);if(m)return `${targetName(m[1])}：${displayLabel(m[2])}${m[3]?' · '+m[3]:''}`;}
 if(e.kind==='revision')return d.replace(/^Revision (\d+): /,'版本 $1：').replace('Adopted Astra proposal','已採用 Astra 方案');
 if(e.kind==='direction')return d.replace(/^Saved Ref2VA scene\/chapter direction revision (\d+)$/,'已儲存 Ref2VA 場景與鏡頭設定（版本 $1）');
 if(e.kind==='review_error')return uiError(d);
 return d;
}
function history(){return head('保留每次創作與決定','版本、審查決定與生成記錄均隨作品保存。還原時會建立新的修訂版本。')+`<div class="two-col"><div class="panel"><h2>生成記錄</h2>${jobList(project.jobs)}</div><div><div class="panel"><h2>作品版本</h2>${project.revisions.map(r=>`<div class="job-row"><div class="job-main"><h3>版本 ${r.number}</h3><small>${esc(r.reason)} · ${new Date(r.created).toLocaleString('zh-HK')}</small></div>${button('還原','restore',`data-number="${r.number}"`,'small')}</div>`).join('')||'<p class="muted">採用製作方案後，即會建立第一個版本。</p>'}</div><div class="panel"><h2>決策記錄</h2>${project.events.map(e=>`<div class="job-row"><div><small class="muted">${new Date(e.created).toLocaleString('zh-HK')}</small><p>${esc(eventText(e))}</p></div></div>`).join('')}</div></div></div>`;}
function settingsPage(){if(!settings)return head('正在載入服務商…','');return head('擴充你的製作工作台','選擇整體創作引擎，或為個別功能指定服務商。技能不會自行更換服務商。')+renderProviderProfile(settings,esc)+renderContextSettings(settings,esc)+localImageSettings()+`<div class="two-col"><div><div class="panel"><div class="panel-header"><h2>功能與服務商</h2>${button('新增 API 服務商','add-provider','','small')}</div>${settings.capabilities.map(c=>`<div class="provider-row"><div><strong>${esc(displayLabel(c))}</strong><div class="muted" style="font-size:11px">${c==='image'?'依選定服務生成圖片，或人工匯入':'此功能可獨立選擇服務商'}</div></div><select aria-label="服務商：${esc(displayLabel(c))}" data-route="${esc(c)}">${settings.providers.filter(p=>supportsProvider(p,c)).map(p=>`<option value="${esc(p.id)}" ${(settings.routing[c]||settings.profile?.default_provider||'astra')===p.id?'selected':''}>${esc(displayLabel(p.name))}</option>`).join('')}</select></div>`).join('')}<p class="muted" style="margin-top:18px">Codex CLI：${settings.codex_installed?'已安裝':'未安裝'}。沿用已登入的帳戶。HTTP 整合需設定 API 位址、模型，以及需要時使用的憑證環境變數。</p></div><div class="panel"><h2>已安裝技能</h2>${settings.skills.length?settings.skills.map(s=>`<div class="job-row"><div class="job-main"><h3>${esc(s.name)} ${badge(s.enabled?'enabled':'disabled')}</h3><small>v${esc(s.version)} · ${esc(s.capabilities.map(displayLabel).join('、'))}</small><p>${esc(s.description)}</p><div class="actions">${button(s.enabled?'停用':'啟用並授予作品讀取權限','toggle-skill',`data-id="${s.id}" data-enabled="${!s.enabled}"`,'small')}${s.enabled?s.capabilities.filter(c=>!providersBuiltIn.includes(c)&&c!=='*').map(c=>button('執行 '+esc(displayLabel(c)),'run-skill',`data-cap="${esc(c)}"`,'small primary')).join(''):''}</div></div></div>`).join(''):'<p class="muted">可在下方安裝指示技能。系統會保存指定版本，並由你決定何時啟用。</p>'}</div></div><div class="panel"><div class="panel-header"><h2>探索本機技能</h2>${button('從路徑安裝','install-path','','small')}</div><p class="muted">支援 SKILL.md 指示與文字參考；目前版本不會執行技能內的程式。</p>${settings.discovered.map(s=>`<div class="job-row"><div class="job-main"><h3>${esc(s.name)}</h3><small>${esc(s.capabilities.map(displayLabel).join('、'))} · ${esc(s.version)}</small></div>${button('安裝','install',`data-source="${esc(s.skill_dir)}"`,'small')}</div>`).join('')}</div></div>`;}
const providersBuiltIn=['director_style','narrative','storyboard','image','image_review','h3','h3_scene','h3_guidance','qc'];
function modal(title,html,wide=false){disposeProposalWatch?.();disposeProposalWatch=null;document.body.classList.add('modal-open');disposeReferenceDrop?.();disposeReferenceDrop=null;$('#modal-root').innerHTML=`<div class="modal-backdrop"><div class="modal ${wide?'wide':''}" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="panel-header"><h2>${esc(title)}</h2>${button('✕','close','aria-label="關閉視窗"','quiet','')}</div>${html}</div></div>`;setTimeout(()=>($('#modal-root [data-initial-focus]')||$('#modal-root input, #modal-root textarea'))?.focus(),0);}
function close(){disposeProposalWatch?.();disposeProposalWatch=null;disposeReferenceDrop?.();disposeReferenceDrop=null; $('#modal-root').innerHTML='';document.body.classList.remove('modal-open'); }
function bindProposalWatch(pid,id,phase='review',initialGuide){
 const root=$('#proposal-guide-top');
 const previous=new Map(initialGuide?[["#proposal-guide-top",proposalGuideMarkup(initialGuide,esc)],["#proposal-guide-footer",proposalGuideFooterMarkup(initialGuide,esc)],["#proposal-review-details",proposalReviewMarkup(initialGuide.status,id,esc)]]:[]);
 const update=(selector,html)=>{const el=$(selector);if(el&&previous.get(selector)!==html){el.innerHTML=html;previous.set(selector,html);}};
 disposeProposalWatch=watchProposal({
  isCurrent:()=>root.isConnected&&project?.id===pid,
  read:async()=>{const [job,current]=await Promise.all([api('/jobs/'+id),api('/projects/'+pid)]);return {job,status:proposalReviewStatus(job,current),currentRevision:current.revision,phase};},
  render:guide=>{update('#proposal-guide-top',proposalGuideMarkup(guide,esc));update('#proposal-guide-footer',proposalGuideFooterMarkup(guide,esc));update('#proposal-review-details',proposalReviewMarkup(guide.status,id,esc));update('#proposal-watch-error','');},
  onError:()=>update('#proposal-watch-error','暫時未能更新進度，會自動再試。已保存的工作仍然保留。')
 });
}
function proposalReviewStatus(job,current){const status=job.directing_review;return status?{...status,queue:current.jobs?.find(j=>j.id===status.job_id)?.queue}:status;}
async function showProposalProgress(pid,id,isCurrent=()=>true){
 const [job,current]=await Promise.all([api('/jobs/'+id),api('/projects/'+pid)]);
 if(project?.id!==pid||!isCurrent())return;
 const guide={job,status:proposalReviewStatus(job,current),currentRevision:current.revision,phase:'progress'};
 modal('方案進度',`<div id="proposal-guide-top">${proposalGuideMarkup(guide,esc)}</div><p role="status" id="proposal-watch-error" class="notice"></p><p class="muted">進度會自動更新。也可以關閉視窗，稍後從「製作總覽」繼續。</p><div class="actions">${button('查看工作記錄','job-detail',`data-id="${esc(id)}"`)}</div><div id="proposal-guide-footer">${proposalGuideFooterMarkup(guide,esc)}</div>`);
 bindProposalWatch(pid,id,'progress',guide);
}
async function submitDirectingReview(id){
 const pid=project.id,dialog=$('#modal-root').firstElementChild,root=$('#proposal-guide-top');
 const isCurrent=()=>project?.id===pid&&$('#modal-root').firstElementChild===dialog;
 const saved=new Map();
 const display=status=>{if(!isCurrent())return;for(const selector of ['#proposal-guide-top','#proposal-guide-footer','#proposal-review-details']){const el=$(selector);if(el){if(!saved.has(selector))saved.set(selector,el.innerHTML);el.innerHTML=selector==='#proposal-review-details'?'':reviewReceiptMarkup(status,esc);}}};
 if(root){disposeProposalWatch?.();disposeProposalWatch=null;display({state:'sending'});}
 toast('正在送出審查…');
 let receipt;
 try{
  receipt=await api('/projects/'+pid+'/jobs',{capability:'directing_qc',target_id:id||''});
 }catch(error){
  if(isCurrent()){for(const [selector,html] of saved){const el=$(selector);if(el)el.innerHTML=html;}if(root)bindProposalWatch(pid,id);}
  throw error;
 }
 if(project?.id!==pid)return;
 if(receipt.job){project.jobs=[receipt.job,...project.jobs.filter(j=>j.id!==receipt.job.id)];updateWorkSurfaces(project);display(receipt.job);}
 // The receipt is already visible; background reads must not resurrect old retry controls.
 try{await refresh(true);if(id&&isCurrent())await showProposalProgress(pid,id,isCurrent);}
 catch(error){if(isCurrent()&&root){const el=$('#proposal-watch-error');if(el)el.textContent='審查已送出，暫時未能更新進度；會自動再試。';bindProposalWatch(pid,id);}throw error;}
 if(isCurrent()||!root)toast(receipt.job?.state==='queued'?'審查已排隊，開始後會自動更新。':receipt.job?.state==='running'?'自動審查中，完成後會顯示結果。':receipt.job?.state==='awaiting_input'?'審查工作已保存，等待人工提交結果。':'審查工作已保存，進度會自動更新。');
}
function approveImageForm(asset){
 const review=asset.review;
 modal('批准圖片 · '+targetName(asset.target_id),`<p>按「批准圖片」即代表你確認採用此圖。備註可留空；系統會記錄你的批准決定，保留原有審查意見。</p>${review?`<div class="note"><strong>圖片審查意見</strong><p>${esc(review.summary)}</p>${review.issues.length?`<ul>${review.issues.map(issue=>`<li>${esc(issue)}</li>`).join('')}</ul>`:''}</div>`:'<p class="muted">目前未有圖片審查結果，請按你對圖片的判斷決定是否採用。</p>'}<form id="image-approval-form"><label>批准備註（選填）<textarea name="note" rows="3" placeholder="可留空，例如：接受這個構圖。"></textarea></label><div class="modal-footer">${button('取消','close')}<button class="primary" type="submit">批准圖片</button></div></form>`);
 $('#image-approval-form').onsubmit=e=>{e.preventDefault();guarded(async()=>{await api('/assets/'+asset.id+'/decision',{status:'approved',note:new FormData(e.target).get('note')||''});close();await refresh(true);toast('已批准圖片，原有審查意見仍然保留。');});};
}
function feedbackModal(title,submit,label='繼續',value=''){modal(title,`<form id="feedback-form"><label>導演方向或修訂要求<textarea name="feedback" rows="5" placeholder="想修改哪些內容？留空可由所選創作引擎決定。">${esc(value)}</textarea></label><div class="modal-footer">${button('取消','close')}<button class="primary" type="submit">${label}</button></div></form>`);$('#feedback-form').onsubmit=async e=>{e.preventDefault();await guarded(async()=>{await submit(new FormData(e.target).get('feedback'));close();await refresh(true);});};}
async function guarded(fn){
 if(busy){toast('上一項操作仍在處理，請稍候；你仍可切換頁面或關閉視窗。');return;}
 busy=true;const trigger=document.activeElement?.closest('button'),wasDisabled=trigger?.disabled;
 if(trigger){trigger.disabled=true;trigger.setAttribute('aria-busy','true');}
 const notice=setTimeout(()=>{let el=document.getElementById('operation-status');if(!el){el=document.createElement('div');el.id='operation-status';el.setAttribute('role','status');document.body.append(el);}el.textContent='正在處理…';},250);
 try{await fn();}catch(e){if(e.name!=='ImpactPreview')toast(uiError(e.message));}finally{clearTimeout(notice);document.getElementById('operation-status')?.remove();if(trigger?.isConnected){trigger.disabled=wasDisabled;trigger.removeAttribute('aria-busy');}busy=false;}
}
async function start(cap,target='',feedback='',force=false,source_asset_id='',input_reference_ids=[],image_options={},source_prompt=null){const r=await api(`/projects/${project.id}/jobs`,{capability:cap,target_id:target,feedback,force,source_asset_id,input_reference_ids,source_prompt,...image_options});if(r.job){project.jobs=[r.job,...project.jobs.filter(j=>j.id!==r.job.id)];}if(r.job)updateWorkSurfaces(project);toast(r.reused_asset?'已沿用批准的參考圖。':r.job?.state==='queued'?'工作已收到並排隊，開始後會自動更新進度。':r.job?.state==='awaiting_input'?'工作已保存，等待你提交結果。':'工作已保存，進度會自動更新。');return r;}
let refreshing=null,projectLoadVersion=0,navigationVersion=0;
async function refresh(force=false){
 if(refreshing){if(force){await refreshing;return refresh(true);}return refreshing;}
 refreshing=refreshState(force);
 try{return await refreshing;}finally{refreshing=null;}
}
async function refreshState(force=false){
 const targetProject=project?.id,loadVersion=projectLoadVersion;
 if(!projectDeletionReady){projectDeletionReady=(await api('/health')).project_deletion===true;if(projectDeletionReady)force=true;}
 const previousList=JSON.stringify([projects,deletedProjects]);projects=await api('/projects');
 if(page==='projects-trash'&&projectDeletionReady)deletedProjects=await api('/projects?deleted=true');
 if(project&&!projects.some(p=>p.id===project.id)){clearCurrentProject();close();page='projects';window.history.replaceState(null,'','#projects');force=true;}
 if(project){
  let next;
  try{next=await api('/projects/'+project.id);}catch(error){
   const available=await api('/projects');if(available.some(p=>p.id===project.id))throw error;
   projects=available;clearCurrentProject();close();page='projects';window.history.replaceState(null,'','#projects');render();return;
  }
  if(project?.id!==targetProject||loadVersion!==projectLoadVersion)return;
  const serialized=JSON.stringify(next);project=next;
  if(serialized!==lastState||force||previousList!==JSON.stringify([projects,deletedProjects])){const editing=['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName),playing=[...document.querySelectorAll('audio,video')].some(a=>!a.paused);if(!$('#modal-root').children.length&&(force||!editing&&!playing&&!busy&&page!=='settings')){lastState=serialized;render();}else updateWorkSurfaces(next);}else updateWorkSurfaces(next);
 }else if(!$('#modal-root').children.length&&(force||previousList!==JSON.stringify([projects,deletedProjects])))render();
}
async function openProject(id){const version=++projectLoadVersion;const next=await api('/projects/'+id);if(version!==projectLoadVersion)return;project=next;page='progress';updateProjectURL(id,'progress');selectedShot=null;selectedFrame=null;localStorage.setItem('continuity-project',id);render();}
function openProgressVideo(id,section){
 if(!project?.production)return;
 const group=project.generation_groups?.rows.find(g=>g.id===id);
 const valid=id&&project.production.shots.some(s=>s.id===id);
 if(group)localStorage.setItem('video-group:'+project.id,id);else localStorage.removeItem('video-group:'+project.id);
 if(valid){localStorage.setItem('video-shot:'+project.id,id);const row=project.video_workflow?.shots.find(r=>r.shot_id===id);if(row)handoff.select(project.id,row.scene_id,id);}
 updateProjectURL(project.id,'video',valid?id:null);
 navigate('video').then(()=>{
  const panel=group?[...document.querySelectorAll('[data-generation-group]')].find(el=>el.dataset.generationGroup===id):null;
  if(panel)panel.open=true;
  const target=panel||(section==='render'?document.querySelector('.video-workspace .video-production'):document.querySelector('.video-content'));
  if(target){target.setAttribute('tabindex','-1');target.focus({preventScroll:true});target.scrollIntoView({block:'start',behavior:'smooth'});}
 }).catch(e=>toast(uiError(e.message)));
}
async function navigate(p){
 if(['h3','h3-legacy'].includes(p))p='video';const version=++navigationVersion;page=p;window.history.replaceState(null,'','#'+p);render();window.scrollTo(0,0);
 if(p==='settings'){const next=await api('/settings');if(version!==navigationVersion)return;settings=next;}
 else if(p==='projects-trash'&&projectDeletionReady){const next=await api('/projects?deleted=true');if(version!==navigationVersion)return;deletedProjects=next;}
 else if(p==='projects'){const next=await api('/projects');if(version!==navigationVersion)return;projects=next;}
 else return;
 if(!$('#modal-root').children.length)render();
}
function editForm(title,fields,submit,note="儲存會建立新版本，並將受影響的已批准圖片標示為待更新。"){modal(title,`<form id="edit-form">${fields.map(f=>f.type==='checkbox'?`<label class="inline-check"><input type="checkbox" name="${esc(f.key)}" ${f.value?'checked':''}>${esc(f.label)}</label>`:`<label>${esc(f.label)}${f.options?`<select name="${f.key}">${f.options.map(o=>`<option value="${esc(o.value)}" ${o.value===f.value?'selected':''}>${esc(o.label)}</option>`).join('')}</select>`:f.area?`<textarea name="${f.key}" rows="${f.rows||4}">${esc(f.value)}</textarea>`:`<input name="${f.key}" value="${esc(f.value)}" ${f.type?`type="${f.type}" ${f.type==='number'?'step="any"':''}`:''}>`}</label>`).join('')}<p class="muted">${esc(note)}</p><div class="modal-footer">${button('取消','close')}<button type="submit" class="primary">儲存修訂版本</button></div></form>`);$('#edit-form').onsubmit=e=>{e.preventDefault();guarded(async()=>{await submit(Object.fromEntries(new FormData(e.target)));close();await refresh(true);});};}
let backdropPointer=false;
document.addEventListener('pointerdown',e=>{backdropPointer=e.target.classList?.contains('modal-backdrop')===true;});
document.addEventListener('click',e=>{
 if(e.target.classList?.contains('modal-backdrop')){if(backdropPointer)close();backdropPointer=false;return;}
 const b=e.target.closest('[data-action]');if(!b)return;
 const action=b.dataset.action;
 if(action==='close'){close();return;}
 if(action==='navigate'){if(b.dataset.closeModal)close();navigate(b.dataset.page).then(()=>{if(b.dataset.section)document.getElementById(b.dataset.section)?.scrollIntoView({block:'start',behavior:'smooth'});}).catch(e=>toast(uiError(e.message)));return;}
 if(action==='overview-section'){if(page!=='overview')navigate('overview');const section=document.getElementById(b.dataset.section);if(section?.tagName==='DETAILS')section.open=true;section?.scrollIntoView({behavior:'smooth',block:'start'});return;}
 if(action==='overview-shot'){selectedShot=b.dataset.id;selectedFrame=project.production?.shots.find(s=>s.id===selectedShot)?.keyframes.find(f=>!approved(f.id))?.id||null;navigate('shots').catch(e=>toast(uiError(e.message)));return;}
 if(action==='progress-editorial'){if(project?.production)location.href='/editorial?project='+encodeURIComponent(project.id);return;}
 if(action==='progress-stage'){
  const stage=Number(b.dataset.stage);
  if(stage===1||stage===2){navigate(stage===1?'overview':'video');return;}
  if(stage===3&&boardTask(project).scene){navigate('shots').then(()=>document.getElementById('visual-storyboard')?.scrollIntoView({block:'start'}));return;}
  if(stage===5){navigate('video').then(()=>document.getElementById('edit-materials')?.scrollIntoView({block:'start'}));return;}
  const rows=project?.video_workflow?.shots||[],takes=project?.video_renders?.takes||[];
  const row=rows.find(r=>!takes.some(t=>t.shot_id===r.shot_id&&t.selected&&t.current&&t.state==='succeeded'))||rows[0];
  openProgressVideo(row?.shot_id,stage===4?'render':'');return;
 }
 if(action==='progress-video'){openProgressVideo(b.dataset.id,b.dataset.section);return;}
 if(action==='select-shot'){selectedShot=b.dataset.id;selectedFrame=null;render();return;}
 if(action==='select-frame'){selectedFrame=b.dataset.id;render();return;}
 if(action==='video-select'){selectVideoShot(b.dataset.id);return;}
 if(action==='director-step'){selectDirectorStep(b.dataset.scene,b.dataset.step);return;}
 guarded(async()=>{const a=b.dataset.action,id=b.dataset.id;
if(a==='prepare-scene'){await start('h3_prepare',id);await refresh(true);return;}
if(a==='analyze-guidance'){await start('h3_guidance');await refresh(true);return;}
if(a==='director-step'){selectDirectorStep(b.dataset.scene,b.dataset.step);return;}
if(a==='regenerate-scene-prompt'){regenerateScenePrompt(id);return;}
if(a==='review-scene-prompt'){await reviewScenePrompt(id);return;}
if(a==='adopt-scene-prompt'){
 const pid=project.id,j=await api('/jobs/'+id),sid=j.target_id,draft=promptDrafts.get(pid,sid,'shared');
 if(draft&&draft.text!==j.input.source_prompt)throw Error('你在生成期間又修改了全域草稿。請先保留這些新修改，再決定採用；目前草稿不會被覆蓋。');
 await api('/projects/'+pid+'/scene-prompts/'+id+'/adopt',{});
 if(draft)promptDrafts.clear(pid,sid,'shared');
 close();await refresh(true);toast('已採用新版全域提示詞，各 Shot 的文字保留。');return;
}
if(a==='regenerate-shot-prompt'){regenerateShotPrompt(b.dataset.scene,id);return;}
if(a==='review-shot-prompt'){await reviewShotPrompt(id);return;}
if(a==='adopt-shot-prompt'){
 const pid=project.id,j=await api('/jobs/'+id),sid=j.input.shot_prompt_source.scene_id,draft=promptDrafts.get(pid,sid,j.target_id);
 if(draft&&draft.text!==j.input.source_prompt)throw Error('你在生成期間又修改了草稿。請先保留這些新修改，再決定採用；目前草稿不會被覆蓋。');
 await api('/projects/'+pid+'/shot-prompts/'+id+'/adopt',{});
 if(draft)promptDrafts.clear(pid,sid,j.target_id);
 close();await refresh(true);toast('已採用新版分鏡提示詞。');return;
}
if(a==='director-discard'){promptDrafts.clear(project.id,b.dataset.scene,b.dataset.step);render();return;}
if(a==='director-save'){
 const pid=project.id,sid=b.dataset.scene,step=b.dataset.step,draft=promptDrafts.get(pid,sid,step);if(!draft)return;
 const field=$('#director-prompt');if(field)field.readOnly=true;
 b.disabled=true;b.textContent='正在儲存…';
 try{const fresh=await api('/projects/'+pid),cfg=promptSaveConfiguration(fresh,sid,step,draft);await api('/projects/'+pid+'/delivery',cfg,'PUT');promptDrafts.clear(pid,sid,step);await refresh(true);toast('提示詞已儲存，複製及匯出會使用此版本。');}
 finally{if(field?.isConnected)field.readOnly=false;if(b.isConnected){b.disabled=false;b.textContent='儲存提示詞';}}return;
}
if(a==='director-copy'){
 const scene=project.delivery.scenes.find(s=>s.scene_id===b.dataset.scene),step=b.dataset.step;
 if(scene.preparation?.required){toast('此場景的英文提示詞未完成，請先整理英文提示詞。');return;}
 if(promptDrafts.get(project.id,scene.scene_id,step)){toast('請先儲存提示詞，再複製到導演台。');$('[data-action=director-save]')?.focus();return;}
 const text=step==='shared'?scene.global_prompt:scene.chapters.find(c=>c.shot_id===step).shot_prompt;
 try{await navigator.clipboard.writeText(text);}
 catch{const field=$('#director-prompt');field?.focus();field?.select();toast('瀏覽器未允許自動複製，已選取完整提示詞。請按 Ctrl+C（Mac：⌘C）。');return;}
 handoff.markCopied(project.id,scene.scene_id,step,text);render();$('#director-prompt')?.closest('section')?.querySelector('[data-action="director-copy"]')?.focus({preventScroll:true});
 toast(step==='shared'?'已複製，請貼到導演台「公共參數 → 提示詞」。':'已複製，請貼到對應「素材組 → 提示詞」。');return;
}
if(a==='video-select'){selectVideoShot(id);return;}
if(a==='video-shot'){selectedShot=id;selectedFrame=null;return navigate('shots');}
if(a==='video-ref'){selectVideoShot(id);return navigate('video');}
if(a==='video-mode'){if(project.video_workflow.shots.find(r=>r.shot_id===id)?.selected)return;await api('/projects/'+project.id+'/video-workflow/'+id,{revision:project.video_workflow.revision,mode:b.dataset.mode},'PUT');await refresh(true);return;}
if(a==='video-analyze'){
 modal('重新生成建議',`<form id="video-strategy-form"><label>這次如何決定做法？<select name="strategy_mode"><option value="AUTO">由創作引擎按劇情建議（預設）</option><option value="I2VA">指定只用首幀 · I2VA</option><option value="FL2VA">指定首尾幀 · FL2VA</option><option value="REF2VA">指定主體參考 · Ref2VA</option></select></label><label>導演方向或修訂要求（可留空）<textarea name="feedback" rows="4" placeholder="例如：希望結尾停在指定構圖。"></textarea></label><p class="muted">先產生建議與藍圖，採用後才鎖定新做法。</p><div class="modal-footer">${button('取消','close')}<button type="submit" class="primary">生成建議與藍圖</button></div></form>`);
 $('#video-strategy-form').onsubmit=e=>{e.preventDefault();const data=new FormData(e.target);guarded(async()=>{await api('/projects/'+project.id+'/jobs',{capability:'h3_strategy',target_id:id,strategy_mode:data.get('strategy_mode'),feedback:data.get('feedback')});close();await refresh(true);});};return;
}
if(a==='video-current-strategy'){const r=project.video_workflow.shots.find(r=>r.shot_id===id);return modal('已採用的建議與藍圖',strategyMarkup(r.strategy.result),true);}

if(a==='video-frame-generate'){
 const r=project.video_workflow.shots.find(r=>r.shot_id===id),f=r.frames.find(f=>f.moment===b.dataset.moment);
 const blueprint=!r.strategy_stale?r.strategy?.result?.[f.moment+'_blueprint']:'';
 const feedback=[blueprint,...(f.asset?.review?.issues||[]),...(!r.jobs.h3_video_prompt?.stale?r.jobs.h3_video_prompt?.result?.frame_issues||[]:[])].filter(Boolean).join('\n');
 return generationForm(f.frame_id,!!f.asset,f.asset?.id||'',{feedback,known:[],selected:[],highFidelity:false});
}
if(a==='video-reference-review'){const asset=project.assets.find(a=>a.id===id);return modal('本鏡參考圖 · '+targetName(asset.target_id),assetCard(asset),true);}
if(a==='video-asset-review'){const asset=project.assets.find(a=>a.id===id);return modal('審閱關鍵幀',assetCard(asset),true);}
if(a==='video-add-frame'){
 const r=project.video_workflow.shots.find(r=>r.shot_id===id),moment=b.dataset.moment;
 return editForm('新增'+(moment==='start'?'首幀':'尾幀')+'描述',[{label:'只描述這一刻的靜止畫面：構圖、站位、左右手及道具狀態',key:'description',value:!r.strategy_stale?r.strategy?.result?.[moment+'_blueprint']||'':'',area:true,rows:8}],v=>api('/projects/'+project.id+'/video-workflow/'+id+'/frame',{revision:project.revision,moment,description:v.description}));
}
if(a==='video-prompt-generate'){
 const r=project.video_workflow.shots.find(r=>r.shot_id===id),draft=promptDrafts.get(project.id,id,r.mode);
 return feedbackModal('生成 '+r.mode+' 影片提示詞',async feedback=>{await api('/projects/'+project.id+'/jobs',{capability:'h3_video_prompt',target_id:id,feedback,source_prompt:draft?.text??r.prompt.text??null});await refresh(true);},'生成可比較的新版');
}
if(a==='video-review'){
 const j=await api('/jobs/'+id),r=project.video_workflow.shots.find(r=>r.shot_id===j.target_id),status=r.jobs[j.capability],pid=project.id,revision=project.video_workflow.revision;
 const draft=promptDrafts.get(pid,r.shot_id,r.mode),isPlan=j.capability==='h3_strategy';
 modal(isPlan?'模式建議與關鍵幀藍圖':'比較影片提示詞',isPlan?strategyMarkup(j.result):`${j.result.frame_issues?.length?`<div class="note"><h3>圖片差異提醒</h3><ul>${j.result.frame_issues.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`:''}<div class="video-compare"><div><h3>目前已保存</h3><pre>${esc(r.prompt.text||'尚未生成')}</pre></div><div><h3>新版 · ${esc(j.input.video_source.mode)}</h3><pre>${esc(j.result.text)}</pre></div></div>`,true);
 const footer=document.createElement('div');footer.className='modal-footer';footer.innerHTML=`${status.stale?'<p>來源已更新，請重新分析／生成。</p>':''}${draft?'<p>此模式有未儲存草稿；請先儲存或放棄草稿再採用。</p>':''}<button type="button" id="video-adopt" class="primary" ${status.stale||draft||status.adopted||(!isPlan&&!j.result.text)?'disabled':''}>${status.adopted?'已採用':isPlan?'採用模式與藍圖':'採用新版提示詞'}</button>`;$('.modal').append(footer);
 $('#video-adopt').onclick=()=>guarded(async()=>{await api('/projects/'+pid+'/video-workflow/adopt/'+id,{revision});close();await refresh(true);});return;
}
if(a==='video-adopt-copy'){
 const r=project.video_workflow.shots.find(r=>r.shot_id===b.dataset.shot);
 if(promptDrafts.get(project.id,r.shot_id,r.mode))throw Error('請先儲存或放棄目前草稿。');
 await api('/projects/'+project.id+'/video-workflow/adopt/'+id,{revision:project.video_workflow.revision});
 const packet=await api('/projects/'+project.id+'/video-workflow/'+r.shot_id+'/packet');
 await refresh(true);
 await navigator.clipboard.writeText(packet.text);toast('已採用並複製完整 H3 提示詞，可貼到對應素材組。');return;
}
if(a==='video-save'){
 const r=project.video_workflow.shots.find(r=>r.shot_id===id),draft=promptDrafts.get(project.id,id,r.mode);if(!draft)return;
 if(draft.base!==(r.prompt.text||''))throw Error('目前提示詞已更新；請備份草稿後重新載入。');
 await api('/projects/'+project.id+'/video-workflow/'+id,{revision:project.video_workflow.revision,text:draft.text,source_hash:draft.source_hash},'PUT');promptDrafts.clear(project.id,id,r.mode);await refresh(true);toast('影片提示詞已儲存。');return;
}
if(a==='video-discard'){const r=project.video_workflow.shots.find(r=>r.shot_id===id);promptDrafts.clear(project.id,id,r.mode);render();return;}
if(a==='video-copy'||a==='video-packet'){
 const r=project.video_workflow.shots.find(r=>r.shot_id===id);if(promptDrafts.get(project.id,id,r.mode))throw Error('請先儲存或放棄草稿，再交接影片提示詞。');
 const packet=await api('/projects/'+project.id+'/video-workflow/'+id+'/packet');
 if(a==='video-copy'){await navigator.clipboard.writeText(packet.text);toast('已複製：貼到首尾幀導演台的本組提示詞。');}
 else{const url=URL.createObjectURL(new Blob([JSON.stringify(packet,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=id+'-'+packet.mode+'-handoff.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}return;
}
if(a==='director-send'){
 const scene=project.delivery.scenes.find(s=>s.scene_id===b.dataset.scene),results=handoffTransfers[project.id]??={};
 if(scene.references.every(r=>results[r.asset_id]?.status==='sent'))for(const r of scene.references)delete results[r.asset_id];
 await transferReferences(scene.references,results,id=>api('/assets/'+id+'/comfy',{}),()=>render());
 const count=scene.references.filter(r=>results[r.asset_id]?.status==='sent').length;
 toast(count===scene.references.length?'全部圖片已送到 ComfyUI 素材庫。請按圖片次序選入參考槽位。':`已送出 ${count} / ${scene.references.length} 張。請查看圖片下方原因，再重試未送出圖片。`);return;
}
if(a==='close')return close();
if(a==='open-voice'){await navigate('postproduction');document.getElementById('voice-'+id)?.scrollIntoView({behavior:'smooth',block:'start'});return;}
if(a==='navigate')return navigate(b.dataset.page);
if(a==='project')return openProject(id);
if(a==='delete-project')return deleteProjectDialog(id);
if(a==='restore-project'){await api('/projects/'+id+'/undelete',{});await refresh(true);toast('作品已還原，可返回作品管理開啟。');return;}
if(a==='production-folder'){
 const folder=await api(`/projects/${project.id}/folder`,{});
 const groups={};for(const f of folder.files){const group=f.name.includes('/')?f.name.split('/')[0]:'製作資料';(groups[group]??=[]).push(f);}
 modal('製作資料夾',`<p>已保存的作品檔案：<strong>${esc(project.title)}</strong>。每份快照包含當時已批准的圖片、劇本與提示詞；較早的快照保留在上層資料夾。</p><label>原始圖片素材庫<input id="asset-library-path" readonly value="${esc(folder.library_path||folder.path)}"></label><div class="actions">${button('開啟原圖素材庫','open-asset-library','','primary')}</div><label style="margin-top:20px">匯出快照路徑<input id="production-folder-path" readonly value="${esc(folder.path)}"></label><div class="actions">${button('在檔案管理員開啟','open-production-folder','','primary')}${button('複製路徑','copy-folder-path')}</div><div class="folder-list">${Object.entries(groups).map(([name,files])=>`<details open><summary>${esc(name)} · ${files.length} 個檔案</summary>${files.map(f=>`<div class="folder-file">${button(esc(folderFileLabel(f.name)),'preview-production-file',`data-url="${esc(f.url)}" data-name="${esc(f.name)}"`,'quiet')}<small class="muted">${f.size<1024?f.size+' B':f.size<1048576?(f.size/1024).toFixed(1)+' KB':(f.size/1048576).toFixed(1)+' MB'}</small></div>`).join('')}</details>`).join('')}</div>`,true);return;
}
if(a==='open-asset-library'){await api(`/projects/${project.id}/library/open`,{});toast('已開啟原圖素材庫，各資料夾均有版本清單。');return;}
if(a==='open-production-folder'){const r=await api(`/projects/${project.id}/folder/open`,{});toast(r.opened?'已在檔案管理員開啟製作資料夾。':'資料夾位置：'+r.path);return;}
if(a==='copy-folder-path'){await navigator.clipboard.writeText($('#production-folder-path').value);toast('已複製資料夾路徑。');return;}
if(a==='preview-production-file'){
 const url=b.dataset.url,name=b.dataset.name;
 const content=/\.(png|jpg|jpeg|webp)$/i.test(name)?`<img src="${esc(url)}" alt="${esc(name)}">`:`<pre>${esc(await (await fetch(url)).text())}</pre>`;
 modal(name,`<div class="actions">${button('← 製作資料夾','production-folder')}<a href="${esc(url)}" download>下載檔案 ↗</a></div>${content}`,true);return;
}

if(a==='new-chapter'||a==='edit-chapter'){
 const ch=a==='edit-chapter'?project.story_chapters.find(c=>c.id===id):null,pid=project.id;
 modal(ch?'編輯章節':'新增章節',chapterForm(ch,esc),true);
 $('#story-chapter-form').onsubmit=e=>{e.preventDefault();guarded(async()=>{const f=e.target.elements;await api('/projects/'+pid+'/chapters'+(ch?'/'+ch.id:''),{title:f.title.value,brief:f.brief.value,source_kind:f.source_kind.value,version:ch?.version||0},ch?'PUT':'POST');close();await refresh(true);toast('章節已保存，可建立本章方案。');});};return;
}
if(a==='edit-outline'){
 const rev=project.brief_revision;
 return editForm('編輯故事大綱',[{label:'整體故事大綱',key:'idea',value:project.idea,area:true,rows:14}],async v=>api('/projects/'+project.id+'/outline',{idea:v.idea,brief_revision:rev},'PUT'));
}
if(a==='develop-chapter'){
 const ch=project.story_chapters.find(c=>c.id===id),cap=ch.source_kind==='idea'?'narrative':'storyboard';
 const adopted=project.production?.chapters?.some(c=>c.id===ch.id);
 feedbackModal((adopted?'修訂劇本與分鏡 · ':'建立劇本與分鏡 · ')+ch.title,f=>start(cap,ch.id,f),'交由 '+providerLabel(cap)+' 建立可審閱方案');
 $('#feedback-form').insertAdjacentHTML('afterbegin','<p class="note">會參考已保存的大綱、本章原文、共用角色設定及已選導演方向，產生劇本與分鏡方案。完成後需審閱採用；目前已採用內容會保留。</p>');return;
}
if(a==='chapter-shots'){
 const ch=project.production.chapters.find(c=>c.id===id);selectedShot=project.production.shots.find(s=>ch.scene_ids.includes(s.scene_id))?.id;selectedFrame=null;return navigate('shots');
}
if(a==='new-project'){newProject();return;}
if(a==='recommend-director'){await start('director_style');await refresh(true);return;}
if(a==='choose-director'){await api('/projects/'+project.id+'/director-style',{job_id:id,style_id:b.dataset.style,revision:project.revision});await refresh(true);if(project.source_kind==='outline'){toast('導演方向已保存，請選擇要發展的章節。');return;}await start(project.source_kind&&project.source_kind!=='idea'?'storyboard':'narrative');await refresh(true);toast('已選定導演方向，正在建立可審閱的分鏡方案。');return;}
if(a==='clear-director'){await api('/projects/'+project.id+'/director-style',{revision:project.revision});await refresh(true);return;}
if(a==='revise-current-directing')return openCurrentDirectingRevision({pid:project.id,chapterId:id||'',getProject:()=>project,api,modal,close,refresh,guarded,toast,esc,providerLabel,showProposalProgress,select:$});
if(a==='develop'){if(project.source_kind==='outline'){document.querySelector('.story-chapter')?.scrollIntoView({behavior:'smooth'});toast('請在章節清單選擇建立或修訂劇本與分鏡，或先新增章節。');return;}const cap=project.source_kind&&project.source_kind!=='idea'?'storyboard':'narrative';return feedbackModal(cap==='storyboard'?'由原文建立分鏡方案':project.production?'發展修訂方案':'發展製作方案',feedback=>start(cap,'',feedback),'交由以下服務處理：'+providerLabel(cap));}
if(a==='proposal'){
 const pid=project.id;await refresh(true);if(project?.id!==pid)return;
 const j=await api('/jobs/'+id);if(project?.id!==pid)return;
 if(j.project_id!==pid)throw Error('這個工作不屬於目前作品。');
 const p=readableProposal(j);
 if(!p){await showProposalProgress(pid,id);return;}
 const directorStatus=proposalReviewStatus(j,project);
 const guide={job:j,status:directorStatus,currentRevision:project.revision};
 const adoptionNotice=`<div id="proposal-guide-top">${proposalGuideMarkup(guide,esc)}</div><p id="proposal-watch-error" class="notice" role="status"></p>`;
 const coverage=j.capability==='storyboard'?`<h3>原文與分鏡對照</h3><p class="muted">段落連結已通過檢查；請核對劇情、對白和揭示次序是否恰當。</p>${j.result.coverage.map(c=>`<details><summary>${esc(c.source_id)} → ${c.shot_ids.map(id=>esc(p.shots.find(s=>s.id===id)?.title||id)).join('、')}</summary><div class="prose">${esc(j.input.source.units.find(u=>u.id===c.source_id)?.text)}</div><p>${esc(c.treatment)}</p></details>`).join('')}<h3>製作推定與改編說明</h3>${j.result.adaptation_notes.length?j.result.adaptation_notes.map(n=>`<p>${esc(n)}</p>`).join(''):'<p class="muted">沒有另列推定。</p>'}`:'';
 modal('審閱製作方案',`${adoptionNotice}<div class="eyebrow">${esc(providerName(j.provider))} · 基於版本 ${j.input.revision}</div>${j.input.director_selection?`<div class="note">導演方向：${esc(j.input.director_selection.name)}<p>${esc(p.style)}</p></div>`:''}<h1>${esc(p.title)}</h1><p>${esc(p.logline)}</p><div class="story-prose">${esc(p.story||p.logline)}</div><h3 style="margin-top:24px">角色與場景</h3>${p.canon.map(e=>`<p><strong>${esc(e.name)}</strong> · ${esc(e.description)}</p>`).join('')}${directorPlanMarkup(p,esc)}<h3>來源鏡頭 · ${p.shots.length} 鏡 · 生成素材 ${p.shots.reduce((n,s)=>n+s.duration,0)} 秒</h3>${p.shots.map(s=>`<div class="note"><strong>${esc(s.title)} · ${s.duration}s</strong>${shotIntentMarkup(s,esc)}<p>${esc(s.action)}</p><small>${esc(s.camera)}</small></div>`).join('')}${editPlanMarkup(p,esc)}<div id="proposal-review-details">${proposalReviewMarkup(directorStatus,id,esc)}</div>${coverage}<details><summary>閱讀完整方案與劇本</summary><pre>${esc(JSON.stringify(j.result,null,2))}</pre></details><div id="proposal-guide-footer">${proposalGuideFooterMarkup(guide,esc)}</div>`,true);bindProposalWatch(pid,id,'review',guide);return;
}
if(a==='human-directing'){
 const pid=project.id;
 await refresh(true);if(project?.id!==pid)return;
 const current=project,job=id?await api('/jobs/'+id):null;
 if(project?.id!==pid)return;
 const review=job?job.directing_review:current.directing.current_review;
 const hash=job?review?.approval_source_hash:current.directing.approval_source_hash;
 if(!hash||job&&(job.project_id!==pid||job.input.revision!==current.revision||!readableProposal(job)))throw Error('方案已更新，請重新查看後批准。');
 modal('人工審批導演方案',directingApprovalForm(review,!!job,esc));
 $('#directing-approval-form').onsubmit=e=>{e.preventDefault();const note=new FormData(e.target).get('note')||'';guarded(async()=>{
  await api('/projects/'+pid+'/directing-approval',{revision:current.revision,source_hash:hash,proposal_id:id||'',note});
  if(job)await api('/jobs/'+id+'/adopt',{revision:current.revision});
  if(project?.id!==pid)return;
  close();await refresh(true);toast(job?'已人工批准並採用方案；AI 意見仍保留。':'已人工批准此方案，可以繼續製作。AI 意見仍保留。');
 });};return;
}
if(a==='resume-directing'){const review=await api('/jobs/'+id);await api('/jobs/'+id+'/resume',{});await refresh(true);if(review.target_id)await showProposalProgress(project.id,review.target_id);return;}
if(a==='directing-qc'){await submitDirectingReview(id);return;}
if(a==='revise-directing'){
 const j=await api('/jobs/'+id),r=j.directing_review?.result;
 const notes=r?[r.summary,...r.coverage.filter(c=>c.verdict!=='pass').map(c=>c.beat_id+': '+c.reason+' '+c.recommendation),...r.issues.map(i=>i.code+': '+i.reason+' '+i.recommendation)].join('\n'):'';
 const pid=project.id;
 modal('修訂導演方案',directingRevisionMarkup(notes,providerLabel(j.capability),esc));
 $('#directing-revision-form').onsubmit=e=>{e.preventDefault();const feedback=new FormData(e.target).get('feedback')||'';guarded(async()=>{const result=await api('/projects/'+pid+'/jobs',{capability:j.capability,target_id:j.input.serial_source?j.target_id:'',proposal_id:j.id,feedback:'保留來源劇情及對白，修正以下導演問題：\n'+notes+'\n補充：'+feedback});close();await refresh(true);if(project?.id===pid&&result.job?.id)await showProposalProgress(pid,result.job.id);toast('修訂工作已建立，完成後會再次進行導演審查。');});};return;
}
if(a==='edit-cut'){
 const plan=structuredClone(project.production),cut=plan.edit_plan.find(e=>e.id===id),rev=project.revision;
 return editForm('修改預定剪接範圍',[{label:'來源素材入點（秒）',key:'planned_edit_in',value:cut.planned_edit_in,type:'number'},{label:'來源素材出點（秒）',key:'planned_edit_out',value:cut.planned_edit_out,type:'number'},...['cut_in_reason','cut_out_reason','continuity_note'].map(k=>({label:({cut_in_reason:'切入原因',cut_out_reason:'切出原因',continuity_note:'剪出位置的連戲說明'})[k],key:k,value:cut[k],area:true,rows:2}))],async v=>{Object.assign(cut,v,{planned_edit_in:Number(v.planned_edit_in),planned_edit_out:Number(v.planned_edit_out)});await api('/projects/'+project.id+'/plan',{revision:rev,production:plan},'PUT');},'儲存後會建立新版本；請重新審查取用範圍及剪出位置的連戲。');
}
if(['reuse-cut','move-cut','remove-cut'].includes(a)){
 const plan=structuredClone(project.production),i=plan.edit_plan.findIndex(e=>e.id===id);
 if(a==='reuse-cut')plan.edit_plan.splice(i+1,0,{...plan.edit_plan[i],id:'edit_'+crypto.randomUUID().replaceAll('-','')});
 if(a==='move-cut'&&i>0)[plan.edit_plan[i-1],plan.edit_plan[i]]=[plan.edit_plan[i],plan.edit_plan[i-1]];
 if(a==='remove-cut')plan.edit_plan.splice(i,1);
 await api('/projects/'+project.id+'/plan',{revision:project.revision,production:plan},'PUT');await refresh(true);toast('預定剪接已更新，請重新審查導演方案。');return;
}
if(a==='adopt'){await api('/jobs/'+id+'/adopt',{revision:project.revision});close();await refresh(true);toast('已採用文字方案。角色、場景及道具圖片要由你按「生成」才會製作。');return;}
if(a==='upload-input-reference'){return uploadProductionReference(b.dataset.target||'');}
if(a==='generate'){return generationForm(b.dataset.target,b.dataset.force==='true',b.dataset.sourceId||'');}
if(a==='select-shot'){selectedShot=id;selectedFrame=null;render();return;}
if(a==='select-frame'){selectedFrame=id;render();return;}
if(a==='lightbox'){const asset=project.assets.find(x=>x.id===id);modal(targetName(asset?.target_id||id),`<div class="actions" style="margin-bottom:16px">${imageTransfer(id)}</div>${asset?imageProgressMarkup(project,asset.target_id,esc)+sheetNotice(asset):''}<img src="${imageURL(id)}" alt="完整圖片"><p class="muted" style="margin-top:15px">${esc(asset?.status==='stale'?displayLabel(asset.note):asset?.note||'')}</p>`,true);return;}
if(a==='scene-asset-batch'){const pid=project.id;await openSceneAssetBatch({pid,sceneId:id,settings,api,modal,close,refresh,guarded,esc,isCurrent:()=>project?.id===pid&&page==='canon'});return;}
if(a==='adopt-identity-image'){
 const asset=project.assets.find(x=>x.id===id),pid=project.id,revision=project.revision;
 if(!asset)return;
 modal('採用目前圖片 · '+targetName(asset.target_id),`<img class="identity-asset-preview" src="${imageURL(id)}" alt="${esc(targetName(asset.target_id))}"><p>採用這張圖片作為目前身份參考。即使原四視圖審查未通過，也可按你的判斷採用；原圖及審查紀錄會保留。</p>${asset.review?`<details><summary>原圖片審查意見</summary><p>${esc(asset.review.summary)}</p><ul>${asset.review.issues.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></details>`:''}<p class="muted">會取代目前參考圖，受影響的鏡頭會標示待更新。</p><form id="adopt-identity-form"><div class="modal-footer">${button('取消','close')}<button class="primary" type="submit">確認採用此圖</button></div></form>`);
 $('#adopt-identity-form').onsubmit=e=>{e.preventDefault();guarded(async()=>{const data=new FormData();data.set('revision',revision);data.set('asset_id',id);await api('/projects/'+pid+'/identity-assets/'+asset.target_id,data);close();await refresh(true);toast('已採用為目前身份參考。');});};return;
}
if(a==='approve'&&isCharacterAsset(project.assets.find(x=>x.id===id))&&!sheetVerified(project.assets.find(x=>x.id===id))){
 const asset=project.assets.find(x=>x.id===id);
 modal('人工確認採用 · '+targetName(asset.target_id),`<p>這張圖片尚未通過四視圖審查。你仍可採用為角色參考圖；原有審查結果會保留，系統會自動記錄你的採用決定。</p>${asset.review?`<p>${esc(asset.review.summary)}</p><ul>${asset.review.issues.map(issue=>`<li>${esc(issue)}</li>`).join('')}</ul>`:'<p>目前沒有四視圖審查結果，請先自行檢查圖片。</p>'}<p class="muted">採用後會取代該角色目前的參考圖，相關分鏡會標示待更新。</p><form id="sheet-accept-form"><div class="modal-footer">${button('取消','close')}<button type="submit" class="primary">確認採用此圖</button></div></form>`);
 $('#sheet-accept-form').onsubmit=e=>{e.preventDefault();guarded(async()=>{await api('/assets/'+id+'/decision',{status:'approved',acknowledge_sheet_issues:true});close();await refresh(true);toast('已記錄人工覆核，並採用為角色參考圖。');});};return;
}
if(a==='approve'&&project.assets.find(x=>x.id===id)?.review?.verdict==='pass'){await api('/assets/'+id+'/decision',{status:'approved',note:''});if($('#modal-root').children.length)close();await refresh(true);toast('已批准，可重用為參考圖。');return;}
if(a==='approve')return approveImageForm(project.assets.find(x=>x.id===id));
if(a==='reject')return feedbackModal('拒絕並刪除此版本的本機圖片',async note=>{const result=await api('/assets/'+id+'/decision',{status:'rejected',note});toast(result.deleted?'已拒絕並刪除此版本的本機圖片。':'已拒絕，暫未能刪除：'+result.deletion_pending_reason);},'拒絕並刪除圖片');
if(a==='review-asset'){await start('image_review',id);await refresh(true);return;}
if(a==='asset-versions'){
 const versions=project.assets.filter(x=>x.target_id===b.dataset.target).sort((a,b)=>b.created.localeCompare(a.created));
 modal('版本清單 · '+targetName(b.dataset.target),`<p>選一個版本檢視及審查。拒絕會刪除本機圖片；仍在使用中的版本會列出刪除限制。</p><div class="asset-version-list">${versions.map(x=>`<button type="button" data-action="asset-version" data-id="${x.id}"><img src="${imageURL(x.id)}" alt="${esc(targetName(x.target_id))}"><span>${badge(x.status)}<br>${esc(new Date(x.created).toLocaleString())}</span></button>`).join('')}</div>`,true);return;
}
if(a==='asset-version'){const asset=project.assets.find(x=>x.id===id);return modal('檢視版本 · '+targetName(asset.target_id),assetCard(asset),true);}
if(a==='delete-rejected-asset'){
 const asset=project.assets.find(x=>x.id===id);if(asset?.status!=='rejected')throw Error('只可刪除已拒絕版本。');
 modal('刪除已拒絕版本',`<p>永久刪除「${esc(targetName(asset.target_id))}」此版本的本機原圖及素材記錄。其他版本會保留；若仍被引用，系統會阻止刪除。</p><div class="actions">${button('取消','close')}${button('永久刪除此版本','confirm-delete-asset',`data-id="${id}"`,'primary')}</div>`);return;
}
if(a==='confirm-delete-asset'){await api('/assets/'+id,undefined,'DELETE');close();await refresh(true);toast('已刪除拒絕版本的本機原圖。');return;}
if(a==='all-assets'){modal('全部視覺素材',`<div class="grid">${groupAssetVersions(project.assets).map(g=>assetCard(g.primary)).join('')}</div>`,true);return;}
if(a==='edit-entity'){const plan=structuredClone(project.production),ent=plan.canon.find(x=>x.id===id),rev=project.revision,pid=project.id,publicBefore=isPublicAsset(ent);let picker;editForm('編輯 '+ent.name,[...(['character','crowd','voice'].includes(ent.kind)?[{label:'素材類型',key:'kind',value:ent.kind,options:[{value:'character',label:'出鏡個別角色 · 四視圖'},{value:'crowd',label:'群眾演員 · 群像參考圖'},{value:'voice',label:'只聞其聲 · 音色與配音，不生圖'}]}]:[]),{label:'設為公共資產',key:'public_asset',value:publicBefore,type:'checkbox'},{label:'名稱',key:'name',value:ent.name},{label:'身份描述',key:'description',value:ent.description,area:true},{label:'固定設定 · 每行一項',key:'facts',value:ent.facts.join('\n'),area:true}],async v=>{const choice=picker?.selection();Object.assign(ent,{...(['character','crowd','voice'].includes(ent.kind)&&['character','crowd','voice'].includes(v.kind)?{kind:v.kind}:{}),scope:(v.public_asset==='on')===publicBefore?(ent.scope||'auto'):(v.public_asset==='on'?'public':'scene'),name:v.name,description:v.description,facts:v.facts.split('\n').filter(Boolean)});if(choice){const data=new FormData();data.set('revision',rev);data.set('entity',JSON.stringify(ent));if(choice.asset_id)data.set('asset_id',choice.asset_id);if(choice.file)data.set('file',choice.file);await api('/projects/'+pid+'/identity-assets/'+id,data);}else await api('/projects/'+pid+'/plan',{revision:rev,production:plan},'PUT');},'未勾選公共資產時，系統按場景需求自動歸類，不需選擇場景。只改分類不會重製圖片；改為聲音資產後保留音色與對白，停止要求人物圖片。身份外觀的修訂仍會標示受影響圖片。');const pending=assetsFor(id).find(x=>x.status==='pending'&&needsAssetReview(x,assetsFor(id))),asset=['character','crowd'].includes(ent.kind)&&pending?pending:latest(id);picker=bindIdentityAssetPicker({form:$('#edit-form'),entity:ent,assets:project.assets,esc,displayLabel});bindIdentityImageAssistant({form:$('#edit-form'),project:structuredClone(project),entity:ent,asset,api,esc,providerName:providerLabel('identity_from_image'),available:settings.capabilities.includes('identity_from_image')});return;}
if(a==='revise-shot'&&project.source_kind==='outline'){const shot=project.production.shots.find(s=>s.id===id),owner=project.production.chapters.find(c=>c.scene_ids.includes(shot.scene_id)),ch=project.story_chapters.find(c=>c.id===owner.id);return feedbackModal('修訂 '+targetName(id),f=>start(ch.source_kind==='idea'?'narrative':'storyboard',ch.id,`Revise shot ${id}: ${f.trim()||'Use your directorial judgment to develop a coherent version from the established story; no additional user constraints were supplied'}. Preserve all other shots in this chapter and all shared canon IDs and facts.`),'建立本章修訂方案');}
if(a==='revise-shot'){return feedbackModal('修訂 '+targetName(id),f=>start(project.source_kind&&project.source_kind!=='idea'?'storyboard':'narrative','',`Director requests a revision to ${id}: ${f.trim()||'Use your directorial judgment to develop a coherent version from the established story; no additional user constraints were supplied'}. Preserve all other shots and canonical identities unless the requested change requires continuity updates. Preserve stable IDs.`),'發展修訂方案');}
if(a==='edit-shot'){const plan=structuredClone(project.production),shot=plan.shots.find(x=>x.id===id),rev=project.revision;editForm('編輯 '+shot.title,[{label:'標題',key:'title',value:shot.title},{label:'生成時長 · 4 至 15 秒',key:'duration',value:shot.duration,type:'number'},...(shot.direction?[{label:'主要鏡頭目的',key:'shot_purpose',value:shot.shot_purpose,area:true,rows:2}]:[]),...['framing','angle','camera','blocking','action','expression'].map(k=>({label:displayLabel(k),key:k,value:shot[k],area:true,rows:2})),{label:'時間節奏 · JSON 結構',key:'beats',value:JSON.stringify(shot.beats,null,2),area:true,rows:8},{label:'對白 · JSON 結構',key:'dialogue',value:JSON.stringify(shot.dialogue,null,2),area:true,rows:8},...shotStateFields(shot),{label:'轉場連續性說明',key:'transition_note',value:shot.transition_note,area:true,rows:2}],async v=>{for(const k of ['title','framing','angle','camera','blocking','action','expression','transition_note'])shot[k]=v[k];if(shot.direction)shot.shot_purpose=v.shot_purpose;shot.duration=Number(v.duration);if(shot.generation_duration!=null)shot.generation_duration=shot.duration;for(const k of ['beats','dialogue'])shot[k]=JSON.parse(v[k]);applyShotStateFields(shot,v);await api('/projects/'+project.id+'/plan',{revision:rev,production:plan},'PUT');});return;}
if(a==='edit-writing'){const plan=structuredClone(project.production),rev=project.revision;editForm('編輯故事與劇本',['title','logline','story','screenplay','style'].map(k=>({label:displayLabel(k),key:k,value:plan[k],area:k!=='title',rows:k==='screenplay'?10:k==='story'?6:3})),async v=>{Object.assign(plan,v);await api('/projects/'+project.id+'/plan',{revision:rev,production:plan},'PUT');});return;}
if(a==='edit-plan'){const rev=project.revision;editForm('編輯製作資料',[{label:'完整製作資料 · JSON 結構',key:'json',value:JSON.stringify(project.production,null,2),area:true,rows:23}],async v=>api('/projects/'+project.id+'/plan',{revision:rev,production:JSON.parse(v.json)},'PUT'));return;}
if(a==='qc'){await start('qc');await refresh(true);return;}
if(a==='refine-h3'){await start('h3',id);await refresh(true);return;}
if(a==='send-comfy'){
 b.disabled=true;b.textContent='正在傳送…';
 try{const r=await api('/assets/'+id+'/comfy',{});modal('已送到 ComfyUI 素材庫',`<img src="${imageURL(id)}" alt="已傳送圖片" style="max-width:100%;max-height:220px;object-fit:contain"><p>在 ComfyUI 參考圖片區按 <strong>「選已有」</strong>，切換「縮略圖」後選取這張圖，再按「使用所选文件」。毋須開啟系統選圖視窗。</p><p>檔名：<strong>${esc(r.name)}</strong></p><p class="muted">如果素材清單已經開住，請按素材清單的「刷新」。原圖仍保存在 Studio。</p><div class="modal-footer">${button('完成','close')}</div>`);}
 finally{b.disabled=false;b.textContent='送到 ComfyUI 素材庫';}
 return;
}
if(a==='copy-image-path'){
 const r=await api('/assets/'+id+'/path');
 try{await navigator.clipboard.writeText(r.path);toast('已複製原圖完整路徑：'+r.path);}
 catch{modal('圖片路徑',`<p>瀏覽器未允許自動複製，請複製下方已選取的路徑。</p><input id="original-image-path" aria-label="原圖完整路徑" readonly value="${esc(r.path)}">`);$('#original-image-path').select();}
 return;
}
if(a==='reveal-input-reference'){const r=await api('/projects/'+project.id+'/input-references/'+id+'/reveal',{});toast('已選取素材庫中的原圖：'+r.path);return;}
if(a==='copy-input-reference-path'){const r=await api('/projects/'+project.id+'/input-references/'+id+'/path');try{await navigator.clipboard.writeText(r.path);toast('已複製素材庫原圖路徑。');}catch{modal('圖片路徑',`<input id="reference-original-path" aria-label="參考圖完整路徑" readonly value="${esc(r.path)}">`);$('#reference-original-path').select();}return;}
if(a==='reveal-image'){const r=await api('/assets/'+id+'/reveal',{});toast('已在檔案管理員選取原圖：'+r.path);return;}
if(a==='copy-image'){
 if(!navigator.clipboard?.write||!window.ClipboardItem)throw Error('此瀏覽器不支援圖片剪貼簿，請使用「下載 PNG」。');
 try{
  const png=fetch(imageURL(id)).then(r=>{if(!r.ok)throw Error('未能載入圖片');return r.blob();});
  await navigator.clipboard.write([new ClipboardItem({'image/png':png})]);
  toast((b.dataset.label||'參考圖')+'已複製為圖片，可貼到 ComfyUI；若圖片控制項只接受檔案，請使用「下載 PNG」。');
 }catch(e){throw Error('未能複製圖片。請保持此分頁開啟並允許剪貼簿存取，或使用「下載 PNG」。');}
 return;
}
if(a==='refine-scene'){return feedbackModal('發展 Ref2VA 場景提示詞',f=>start('h3_scene',id,f),'交由以下服務發展：'+providerLabel('h3_scene'),promptDrafts);}
if(a==='copy-scene-global'){await navigator.clipboard.writeText(project.delivery.scenes.find(s=>s.scene_id===id).global_prompt);toast('已複製場景全域提示詞，請貼到已啟用的公共／全域提示詞欄位。');return;}
if(a==='copy-chapter-shot'||a==='copy-chapter-guidance'){const c=deliveryChapter(id);await navigator.clipboard.writeText(a==='copy-chapter-shot'?c.shot_prompt:JSON.stringify(c.guidance,null,2));toast(a==='copy-chapter-shot'?'已複製分鏡提示詞。':'已複製接續指示。');return;}
if(a==='edit-scene-global'){const cfg=editableDelivery(id);return editForm('場景全域提示詞',[{key:'global_prompt',label:'統一此 Scene 下所有 Shot 的場景設定與連續性',value:cfg.scenes[id].global_prompt,area:true,rows:16}],async v=>{cfg.scenes[id].global_prompt=v.global_prompt;cfg.scenes[id].prompt_edited=true;await saveDelivery(cfg);},"場景方向會獨立保存，現有圖片批准狀態會保留。");}
if(a==='delivery-settings'){
 const cfg=editableDelivery();modal('段間引導設定',`<form id="delivery-settings-form"><label class="inline-check"><input type="checkbox" name="enabled" ${cfg.continuity_enabled?'checked':''}>啟用段間引導</label><label>參考影格數<select name="context">${[5,22,39,56].map(n=>`<option ${n===cfg.context_frames?'selected':''}>${n}</option>`).join('')}</select></label><p class="muted">第一個鏡頭沒有上一段；之後每個鏡頭均可獨立關閉「引用上段」。這裡保存接續設定，實際生成時請在 ComfyUI 套用。</p><button type="submit" class="primary">儲存引導設定</button></form>`);
 $('#delivery-settings-form').onsubmit=e=>{e.preventDefault();guarded(async()=>{const f=new FormData(e.target);cfg.continuity_enabled=f.has('enabled');cfg.context_frames=Number(f.get('context'));await saveDelivery(cfg);});};return;
}
if(a==='edit-chapter-delivery'){
 const cfg=editableDelivery(b.dataset.scene),chapter=cfg.scenes[b.dataset.scene].chapters[id],c=deliveryChapter(id);
 modal('鏡頭 · '+c.title,`<form id="chapter-direction-form"><p class="muted">此 Shot 屬於 ${esc(project.delivery.scenes.find(s=>s.scene_id===b.dataset.scene).title)}。全域提示詞在 Scene 設定；此處只編輯本鏡頭的 Prompt。</p><label>獨立導演／分鏡 Prompt<textarea name="shot" rows="13">${esc(c.shot_prompt)}</textarea></label><label>額外分鏡構圖參考（選填）<select name="reference">${[['none','不加入 · 使用角色與場景參考圖'],['start','起始構圖'],['end','結束構圖'],['both','起始及結束構圖']].map(([value,label])=>`<option value="${value}" ${value===(chapter.reference_frame||'none')?'selected':''}>${label}</option>`).join('')}</select></label><label>引用上段<select name="guide" ${c.guidance.previous_shot_id?'':'disabled'}><option value="auto" ${chapter.guidance_mode!=='manual'?'selected':''}>按分鏡自動判斷（建議）</option><option value="on" ${chapter.guidance_mode==='manual'&&chapter.guide_from_previous?'selected':''}>我指定勾選</option><option value="off" ${chapter.guidance_mode==='manual'&&chapter.guide_from_previous===false?'selected':''}>我指定不勾選</option></select></label><label>接續方向<textarea name="notes" rows="4">${esc(c.guidance.notes)}</textarea></label><div class="modal-footer"><button type="submit" class="primary">儲存鏡頭</button></div></form>`,true);
 $('#chapter-direction-form').onsubmit=e=>{e.preventDefault();guarded(async()=>{const f=new FormData(e.target);Object.assign(chapter,{shot_prompt:f.get('shot'),prompt_edited:true,reference_frame:f.get('reference'),guidance_mode:f.get('guide')==='on'||f.get('guide')==='off'?'manual':'auto',guide_from_previous:f.get('guide')==='auto'?null:f.get('guide')==='on',guidance_notes:f.get('notes')});await saveDelivery(cfg);});};return;
}
if(a==='copy-h3'){const h=project.h3.find(x=>x.shot_id===id);if(!h.ready)throw Error('這是未整理草稿，請先交由服務商修訂。');await navigator.clipboard.writeText(h.text);toast('已複製 H3 提示詞。');return;}
if(a==='restore'){return feedbackModal('還原版本 '+b.dataset.number,()=>api(`/projects/${project.id}/restore/${b.dataset.number}`,{revision:project.revision}),'還原並建立新版本');}
if(a==='cancel-job'){const result=await api('/jobs/'+id+'/cancel',{});await refresh(true);await updateVisibleImageProgress();toast(result.state==='cancelled'?'工作已取消。':'已要求取消；服務商可能仍在結束處理，不會採用結果。');return;}
if(a==='resume-stages'){await api('/jobs/'+id+'/resume',{});await refresh(true);toast('已接續原工作；沿用已保存階段及原服務商。');return;}
if(a==='recover'){const job=project.jobs.find(j=>j.id===id);if(job?.provider==='comfy_local'){await api('/jobs/'+id+'/recover-image',{});await refresh(true);return;}await api('/jobs/'+id+'/recover',{});await refresh(true);toast('已恢復服務商保存的結果，沒有重新生成。');return;}
if(a==='retry'){const j=project.jobs.find(x=>x.id===id);if(j.provider==='comfy_local'){try{await api('/jobs/'+j.id+'/recover-image',{});await refresh(true);return;}catch(error){if(!error.message.includes('沒有待取回'))throw error;}}if(j.capability==='h3_strategy'){await api('/projects/'+project.id+'/jobs',{capability:j.capability,target_id:j.target_id,feedback:j.input.feedback||'',strategy_mode:j.input.strategy_mode||'AUTO',source_prompt:j.input.source_prompt??null,force:true});await refresh(true);return;}await start(j.capability,j.target_id,j.input.feedback,true,j.input.source_asset_id||'',j.input.input_reference_ids||[],{image_provider:j.input.image_provider||'',image_operation:j.input.image_operation||'auto',image_region:j.input.image_region||null,image_padding:j.input.image_padding||null},j.input.source_prompt??null);await refresh(true);return;}
if(a==='job-detail'){
 const pid=project.id,loadVersion=projectLoadVersion;
 const [j,fresh]=await Promise.all([api('/jobs/'+id),api('/projects/'+pid)]);
 if(project?.id!==pid||projectLoadVersion!==loadVersion)return;
 if(j.project_id!==pid)throw Error('這項工作不屬於目前作品。');
 modal('工作記錄',`<div data-live-job="${esc(j.id)}">${renderWorkRow({...j,kind:'job'},{esc,button,displayLabel,targetName:id=>activityTargetName(fresh,id),showAction:false})}</div><div data-job-detail-body>${jobDetailBody(j,fresh,jobDetailHelpers())}</div>`,true);
 const body=document.querySelector('[data-job-detail-body]');body._jobSnapshot=j;body._jobMarkup=jobDetailBody(j,fresh,jobDetailHelpers());
 return;
}
if(a==='manual'){const j=await api('/jobs/'+id);if(j.capability==='image'){toast('請在對應角色或鏡頭使用「匯入圖片」，完成此工作。');return;}modal('提交人工處理結果',`<p>使用下方完整請求交由你選擇的工作流程處理，再提交 JSON 結果；系統會先驗證內容。</p><details><summary>請求</summary><pre>${esc(j.input.prompt)}</pre></details><form id="manual-form"><label>JSON 結果<textarea name="result" rows="14" required>${['director_style','narrative','storyboard','h3_guidance'].includes(j.capability)?'':j.capability==='h3_scene'?esc(JSON.stringify({global_prompt:j.input.compiled.global_prompt,chapters:j.input.compiled.chapters.map(c=>({shot_id:c.shot_id,shot_prompt:c.shot_prompt}))},null,2)):esc(JSON.stringify(j.capability==='image_review'?{verdict:'uncertain',summary:'',issues:[],character_sheet:'uncertain'}:j.capability==='qc'?{verdict:'pass',summary:'',issues:[]}:{text:''},null,2))}</textarea></label><button class="primary" type="submit">提交結果</button></form>`,true);$('#manual-form').onsubmit=e=>{e.preventDefault();guarded(async()=>{await api('/jobs/'+id+'/manual',JSON.parse(new FormData(e.target).get('result')));close();await refresh(true);});};return;}
if(a==='upload'){const target=b.dataset.target;modal('匯入 '+targetName(target),`<form id="upload-form"><label>參考圖片<input type="file" name="file" accept="image/png,image/jpeg,image/webp" required></label><p class="muted">圖片會複製到作品資料夾並安排視覺審查；匯入後仍需批准。</p><button type="submit" class="primary">匯入圖片</button></form>`);$('#upload-form').onsubmit=e=>{e.preventDefault();guarded(async()=>{await api(`/projects/${project.id}/upload/${target}`,new FormData(e.target));close();await refresh(true);});};return;}
if(a==='check-local-images'){const target=$('#local-image-status');target.textContent='正在檢查…';const r=await api('/settings/local-images/check',{});target.textContent=r.message+' '+r.recipes.map(x=>x.name+'：'+(x.ready?'依賴齊備':x.error)).join('；');return;}
if(a==='check-qwen'){const el=$('#qwen-connection-result');el.textContent='正在檢查本機服務…';const result=await api('/settings/qwen/check',{});el.textContent=result.message;return;}
if(a==='check-deepseek'){const el=$('#deepseek-connection-result');el.textContent='正在檢查已儲存設定…';const result=await api('/settings/deepseek/check',{});el.textContent=result.message;return;}
if(a==='context-limits'){const provider=settings.providers.find(p=>p.id===id),policy=settings.context_profiles[id];modal('模型容量設定',contextLimitsForm(provider,policy,esc));$('#context-limits-form').onsubmit=e=>{e.preventDefault();guarded(async()=>{const v=Object.fromEntries(new FormData(e.target));await api('/settings/context-limits',{provider_id:id,context_window:Number(v.context_window),max_output_tokens:Number(v.max_output_tokens),tokenizer:v.tokenizer});close();await navigate('settings');toast('已保存容量設定；新工作使用新預算。');});};return;}
if(a==='add-provider'){modal('新增 API 服務商',`<form id="provider-form"><div class="form-grid"><label>服務商識別碼<input name="id" placeholder="my-provider" pattern="[a-zA-Z0-9_-]+" required></label><label>顯示名稱<input name="name" required></label><label class="full">相容 OpenAI 格式的 API 基礎位址<input name="base_url" placeholder="http://127.0.0.1:8080/v1" required></label><label>模型<input name="model" required></label><label>憑證環境變數<input name="key_env" placeholder="MY_PROVIDER_API_KEY"></label><label class="full">功能識別碼 · 以逗號分隔<input name="capabilities" value="narrative,h3,qc"></label></div><p class="muted">文字使用 chat/completions，圖片使用 images/generations 或 images/edits。新增服務商不會更改預設選項。</p><button class="primary" type="submit">儲存服務商</button></form>`);$('#provider-form').onsubmit=e=>{e.preventDefault();guarded(async()=>{let v=Object.fromEntries(new FormData(e.target));v.kind='http';v.capabilities=v.capabilities.split(',').map(s=>s.trim());await api('/settings/providers',v);close();await navigate('settings');});};return;}
if(a==='install'){await api('/skills/install',{source:b.dataset.source});settings=await api('/settings');render();toast('已安裝指定版本，預設為停用。');return;}
if(a==='install-path'){return feedbackModal('安裝本機指示技能',async source=>{await api('/skills/install',{source});settings=await api('/settings');},'安裝技能');}
if(a==='toggle-skill'){await api('/skills/'+id+'/enable',{enabled:b.dataset.enabled==='true',granted_permissions:b.dataset.enabled==='true'?['project:read']:[]});settings=await api('/settings');render();return;}
if(a==='run-skill'){if(!project)throw Error('請先開啟作品。');return feedbackModal('執行 '+displayLabel(b.dataset.cap),f=>start(b.dataset.cap,'',f),'執行功能');}
});});
document.addEventListener('input',e=>{
 if(e.target.matches('[data-video-prompt]')){const t=e.target,r=project.video_workflow.shots.find(r=>r.shot_id===t.dataset.shot),old=promptDrafts.get(project.id,r.shot_id,r.mode);promptDrafts.set(project.id,r.shot_id,r.mode,{text:t.value,base:old?.base??r.prompt.text??'',source_hash:old?.source_hash??t.dataset.hash});document.querySelectorAll('[data-action=video-save],[data-action=video-discard]').forEach(b=>b.disabled=false);const note=$('[data-video-draft-note]');if(note)note.textContent='有未儲存修改，草稿保留於本瀏覽器。';return;}

 const field=e.target;if(field.id!=='director-prompt')return;
 const sid=field.dataset.scene,step=field.dataset.step,previous=promptDrafts.get(project.id,sid,step),base=previous?.base??currentPrompt(project,sid,step);
 if(field.value===base)promptDrafts.clear(project.id,sid,step);
 else promptDrafts.set(project.id,sid,step,{base,text:field.value,productionRevision:previous?.productionRevision??project.revision});
 const dirty=!!promptDrafts.get(project.id,sid,step);
 for(const action of ['director-save','director-discard'])$('[data-action='+action+']').disabled=!dirty;
 field.closest('section').querySelector('.director-copy-note').textContent=dirty?'請先儲存，再複製到導演台。':'儲存後，複製及匯出會使用你的版本。';
 $('[data-prompt-status]').textContent=dirty?'有未儲存修改 · 草稿保留於本瀏覽器':'內容已載入 · 編輯後按儲存';
});
document.addEventListener('change',e=>{if(e.target.id==='creative-provider-mode'){$('#deepseek-profile-options').hidden=e.target.value!=='deepseek';$('#qwen-profile-options').hidden=e.target.value!=='local_qwen';const choice=$('#provider-profile-form select[name=image_provider]'),old=choice.value;const choices=settings.providers.filter(p=>supportsProvider(p,'image')&&(e.target.value!=='deepseek'||p.kind!=='codex'));choice.innerHTML=choices.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');choice.value=choices.some(p=>p.id===old)?old:(e.target.value==='deepseek'?'manual':'astra');return;}if(e.target.matches('[data-video-scene]')){const r=project.video_workflow.shots.find(r=>r.scene_id===e.target.value);selectVideoShot(r.shot_id);return;}if(e.target.matches('[data-director-scene]')){if(!busy)selectDirectorStep(e.target.value);return;}if(e.target.dataset.route)guarded(async()=>{await api('/settings/routing',{capability:e.target.dataset.route,provider_id:e.target.value});settings=await api('/settings');render();toast('已保存服務商選項。');});});
document.addEventListener('submit',e=>{if(e.target.id!=='provider-profile-form')return;e.preventDefault();guarded(async()=>{const values=Object.fromEntries(new FormData(e.target));if(!['astra','deepseek','local_qwen'].includes(values.mode))throw Error('請選擇 Astra、DeepSeek 或 Qwen3.8 整體模式。');await api('/settings/profile',values);settings=await api('/settings');render();$('#provider-profile-result').textContent=settings.profile.mode==='deepseek'&&!settings.profile.deepseek.credential_configured?' 已儲存；尚需設定 API 憑證。':' 已套用，新工作將使用此模式。';toast('已保存整體模式。');});});
document.addEventListener('keydown',e=>{if(e.key==='Escape')close();});
window.addEventListener('hashchange',()=>guarded(()=>navigate(routePage())));
// Adaptive status polling. A full project read carries every job record (megabytes
// on a long-lived production), so read it frequently only while work is in flight;
// an idle project is polled slowly and recovers to fast polling on real activity.
let pollDueAt=0,pollActiveWork=false;
function pollActive(p){
 if(!p)return false;
 if((p.jobs||[]).some(j=>['queued','running','awaiting_input'].includes(j.state)))return true;
 const phase=p.local_runtime?.phase;
 return !!phase&&phase!=='ready';
}
function pollIntervalMs(){return pollActiveWork?4000:30000;}
async function boot(){try{projectDeletionReady=(await api('/health')).project_deletion===true;if(['#h3','#h3-legacy'].includes(location.hash))window.history.replaceState(null,'','#video');[projects,settings]=await Promise.all([api('/projects'),api('/settings')]);render();const requested=new URLSearchParams(location.search);const remembered=requested.get('project')||localStorage.getItem('continuity-project');if(remembered&&projects.some(p=>p.id===remembered)){try{project=await api('/projects/'+remembered);}catch(error){projects=await api('/projects');if(projects.some(p=>p.id===remembered))throw error;localStorage.removeItem('continuity-project');}}else if(remembered)localStorage.removeItem('continuity-project');if(project){localStorage.setItem('continuity-project',project.id);const sid=requested.get('shot');if(sid&&project.production?.shots.some(s=>s.id===sid)){selectedShot=sid;selectVideoShot(sid);}}if(page==='projects-trash'&&projectDeletionReady)deletedProjects=await api('/projects?deleted=true');render();setInterval(updateGenerationClocks,1000);setInterval(()=>{if(document.visibilityState!=='hidden'&&(busy||$('#modal-root').children.length||['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)||[...document.querySelectorAll('audio,video')].some(a=>!a.paused)))updateVisibleImageProgress().catch(()=>{});},4000);setInterval(()=>{if(document.visibilityState==='hidden'||busy||refreshing||progressPolling||[...document.querySelectorAll('audio,video')].some(a=>!a.paused)||$('#modal-root').children.length||['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName))return;const now=Date.now();if(now<pollDueAt)return;pollDueAt=now+pollIntervalMs();refresh().then(()=>{pollActiveWork=pollActive(project);}).catch(e=>{pollActiveWork=true;pollDueAt=Date.now()+4000;document.querySelectorAll('[data-work-refresh]').forEach(el=>{el.textContent='暫時未能更新進度，以下是上次狀態；會自動重試。';});toast('連線中斷，已保存的作品資料仍然保留。');});},1000);}catch(e){$('#app').innerHTML=`<div class="empty"><h1>暫時未能連接工作台</h1><p>${esc(uiError(e.message))}</p><button onclick="location.reload()">重試</button></div>`;}}
boot();

installVoiceUI({getProject:()=>project,api,modal,close,refresh,guarded,toast});
installVideoRenderUI({getProject:()=>project,drafts:promptDrafts,api,modal,refresh,guarded,toast});
installGenerationGroups({openGroup:id=>openProgressVideo(id),getProject:()=>project,api,modal,close,refresh,guarded,toast});
installStoryboard({getProject:()=>project,getSettings:()=>settings,api,modal,close,refresh,guarded,toast,navigate});
