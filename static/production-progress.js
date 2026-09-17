// A read-only recommendation. Saved approvals and render checks remain authoritative.
const activeStates=new Set(['queued','preparing','submitting','submitted','running','awaiting_input']);
const isStory=j=>['narrative','storyboard'].includes(j.capability);
const newest=items=>[...items].sort((a,b)=>String(b.created||'').localeCompare(String(a.created||'')));
const nav=(title,description,label,page)=>({title,description,label,action:'navigate',page});

export function productionProgress(project,pendingImages=0){
 const p=project.production,shots=p?.shots||[],canon=p?.canon||[],assets=project.assets||[],jobs=newest(project.jobs||[]);
 const rows=project.video_workflow?.shots||[],rowById=new Map(rows.map(r=>[r.shot_id,r]));
 const shotIds=new Set(shots.map(s=>s.id));
 const visualIds=new Set(project.visual_entity_ids??canon.filter(e=>e.kind!=='voice').map(e=>e.id));
 const approved=new Set(assets.filter(a=>a.status==='approved').map(a=>a.target_id));
 const refs=rows.filter(r=>shotIds.has(r.shot_id)).flatMap(r=>r.references||[]);
 const missingRefs=[...visualIds].filter(id=>{const seen=refs.filter(r=>r.target_id===id);return seen.length?seen.some(r=>!r.ready):!approved.has(id);});
 const takes=newest(project.video_renders?.takes||[]),renderChecks=project.video_renders?.shots||{};
 const groups=project.generation_groups?.rows||[],groupIds=new Set(groups.map(g=>g.id));
 const groupChecks=project.video_renders?.groups||{};
 const groupTakes=takes.filter(t=>groupIds.has(t.shot_id));
 const selectedGroups=groupTakes.filter(t=>t.selected&&t.current&&t.review_status!=='rejected'&&t.state==='succeeded');
 const observedEdits=new Set([...selectedGroups.filter(t=>t.mapping?.status==='user_observed').flatMap(t=>t.mapping.boundaries.map(b=>b.edit_id)),...(project.edit_segments?.segments||[]).filter(s=>['current','legacy_observed'].includes(s.status)).map(s=>s.edit_id)]);
 const preparedEdits=new Set(groups.filter(g=>groupChecks[g.id]?.ready).flatMap(g=>g.edit_ids));
 const allEditsCovered=(sid,covered)=>{const edits=(p?.edit_plan||[]).filter(e=>e.shot_id===sid);return edits.length>0&&edits.every(e=>covered.has(e.id));};
 const adopted=new Set(takes.filter(t=>shotIds.has(t.shot_id)&&t.selected&&t.current&&t.review_status!=='rejected'&&t.state==='succeeded').map(t=>t.shot_id));
 for(const s of shots)if(allEditsCovered(s.id,observedEdits))adopted.add(s.id);
 const framesReady=r=>r.mode==='REF2VA'||!!r.frames?.length&&r.frames.every(f=>f.ready);
 const prepared=shots.filter(s=>{const r=rowById.get(s.id);return allEditsCovered(s.id,preparedEdits)||r?.selected&&!r.strategy_stale&&framesReady(r)&&renderChecks[s.id]?.ready;}).length;
 const stage=(number,title,done,total,status)=>({number,title,done,total,status,complete:!!shots.length&&done===total});
 const plannedScenes=new Set((project.generation_groups?.arrangements||[]).filter(a=>a.status==='current').map(a=>a.scene_id));
 const unplanned=(p?.scenes||[]).find(sc=>(p?.edit_plan||[]).some(e=>shots.some(s=>s.id===e.shot_id&&s.scene_id===sc.id))&&!plannedScenes.has(sc.id));
 const stages=[
  stage(1,'故事與剪接基準',shots.length?1:0,1,shots.length?`${shots.length} 鏡已採用`:'待建立並採用方案'),
  stage(2,'生成安排與素材',visualIds.size-missingRefs.length,visualIds.size,p?visualIds.size?`${visualIds.size-missingRefs.length}／${visualIds.size} 項參考已批准`:'本方案無圖片參考需求':'待建立'),
  stage(3,'畫面與提示詞',prepared,shots.length,shots.length?`${prepared}／${shots.length} 鏡已備妥`:'待建立'),
  stage(4,'影片製作',adopted.size,shots.length,shots.length?`${adopted.size}／${shots.length} ${groups.length?'分鏡已覆蓋':'鏡已採用'}${selectedGroups.length?' · '+selectedGroups.length+' 組已採用':''}`:'待建立'),
  {number:5,title:'實際剪接範圍',done:project.edit_segments?.segments?.filter(r=>['current','legacy_observed'].includes(r.status)).length||0,total:p?.edit_plan?.length||null,complete:false,status:project.edit_segments?.complete?'素材範圍已綁定 · 尚未渲染最終成片':'看片後綁定素材範圍 · 配音可並行'},
 ];
 if(unplanned){stages[1].complete=false;stages[1].status+=' · 生成安排待採用';}
 const work=[...jobs.map(j=>({...j,kind:'job'})),...takes.filter(t=>shotIds.has(t.shot_id)||groupIds.has(t.shot_id)).map(t=>({...t,kind:'video'})),...(project.postproduction?.takes||[]).map(t=>({...t,kind:'voice'}))].filter(j=>activeStates.has(j.state)||j.kind==='video'&&['uncertain','recoverable'].includes(j.state));
 const finish=(currentStage,next)=>({stages,currentStage,next,work});
 const jobNext=(j,title,description)=>({title,description,label:'查看進度／處理',action:'job-detail',id:j.id});
 if(pendingImages>0&&p){
  const referencePending=assets.some(a=>a.status==='pending'&&visualIds.has(a.target_id));
  return finish(referencePending?2:3,nav(`${pendingImages} 項圖片待你審閱`,'先查看候選，再決定採用或修改；批准後才會供後續鏡頭沿用。','查看待審圖片','review'));
 }
 const currentStoryJobs=jobs.filter(j=>isStory(j)&&(!shots.length||Number.isInteger(j.input?.revision)&&j.input.revision===project.revision));
 const storyWork=currentStoryJobs.find(j=>activeStates.has(j.state));
 if(storyWork)return finish(1,jobNext(storyWork,storyWork.state==='queued'?'製作方案已排隊，等候開始':storyWork.state==='awaiting_input'?'製作方案等待你處理':'正在建立製作方案','查看已保存進度及待處理事項，毋須重新提交。'+(shots.length?'目前採用版本仍然保留。':'')));
 const latestStory=currentStoryJobs[0];
 if(latestStory&&['failed','interrupted'].includes(latestStory.state))return finish(1,jobNext(latestStory,'上次方案工作需要處理','查看中斷原因與已保存階段，再選擇接續或修訂。'+(shots.length?'目前採用版本仍然保留。':'')));
 // A proposal based on the exact current revision cannot already have been adopted:
 // adoption creates a new production revision. Older successful jobs remain history.
 // Opening review rechecks full source freshness and creative QC before adoption.
 const proposal=currentStoryJobs.find(j=>j.state==='succeeded'&&j.result);
 if(proposal){
  const review=project.directing?.proposals?.[proposal.id],needsRevision=!review?.human_approval&&review?.required&&review?.state==='succeeded'&&review.result?.verdict==='revise';
  if(shots.length)stages[0].status+=needsRevision?' · 新方案待修訂':' · 有方案可審閱';
  return finish(1,{title:needsRevision?'製作方案需要修訂':'有製作方案可以審閱',description:needsRevision?'整體導演審查要求修訂。開啟方案查看原因，再按「按意見修訂方案」處理；目前採用版本仍然保留。':shots.length?'比較新方案，再決定是否採用；審閱時會核對來源與導演審查，目前採用版本仍然保留。':'文字方案已完成。先審閱故事、角色及分鏡，採用後才進入素材製作。',label:needsRevision?'查看方案修訂要求':'審閱製作方案',action:'proposal',id:proposal.id});
 }
 if(!shots.length){
  const storyJobs=jobs.filter(isStory),working=storyJobs.find(j=>activeStates.has(j.state));
  if(working)return finish(1,jobNext(working,working.state==='queued'?'製作方案已排隊，等候開始':working.state==='awaiting_input'?'製作方案等待你處理':'正在建立製作方案','查看已保存進度及待處理事項，毋須重新提交。'));
  const failed=storyJobs[0];
  if(failed&&['failed','interrupted'].includes(failed.state))return finish(1,jobNext(failed,'上次方案工作需要處理','查看中斷原因與已保存階段，再選擇接續或修訂。'));
  if(project.source_kind==='outline')return finish(1,project.story_chapters?.length?{...nav('繼續建立章節方案','選擇章節建立劇本與分鏡，再審閱採用。','前往章節','overview'),section:'overview-chapters'}:{title:'開始第一章',description:'大綱已保存。新增第一章，寫下事件與人物，或貼上已有劇本。',label:'新增第一章',action:'new-chapter'});
  return finish(1,{title:'建立故事與分鏡方案',description:'以已保存的構思或原文設定創作要求，生成後先審閱採用。',label:'設定創作要求',action:'develop'});
 }
 const directingNeedsWork=(project.directing?.scenes||[]).some(s=>!['pass','legacy','human_approved'].includes(s.status));
 if(directingNeedsWork){
  const r=project.directing?.current_review;
  const pending=r&&['queued','running','deferred'].includes(r.state);
  const title=pending?(r.state==='running'?'正在自動審查導演內容':r.state==='deferred'?'最新方案等候自動審查':'導演內容審查已自動排隊'):r?.state==='awaiting_input'?'導演內容審查等待人工處理':r?.state==='succeeded'?'導演內容審查有意見需要處理':'導演內容審查需要處理';
  stages[0].complete=false;stages[0].status+=' · '+title;
  return finish(1,{title,description:pending?'毋須再次提交。完成後會顯示結果；通過後可繼續製作關鍵幀與 H3。':'查看審查結果或執行狀態，修訂後系統會自動審查。',label:'查看導演內容審查',action:'overview-section',section:'overview-directing'});
 }
 if(shots.length&&shots.every(s=>adopted.has(s.id)))return finish(5,nav('核對實際剪接範圍與聲音',project.edit_segments?.complete?'實際素材範圍已綁定；這不代表最終成片已渲染。配音可繼續並行處理。':'各鏡已有可用影片，請看片並綁定實際素材範圍；這不代表整部成片已完成。','查看實際剪接素材','video'));
 if(unplanned){
  const candidate=project.generation_groups?.plans?.find(j=>j.target_id===unplanned.id&&!j.stale);
  if(candidate)return finish(2,candidate.state==='succeeded'?nav('檢視並採用生成安排','先決定獨立來源或分組與所需控制畫面；圖片可以稍後準備。','前往生成安排','video'):jobNext(candidate,'生成安排正在處理','完成後先審閱，再準備所需圖片。'));
  return finish(2,nav('先安排本場如何生成',unplanned.title+'：沿用已採用剪接基準，安排來源、分組和圖片需求。','前往生成安排','video'));
 }
 if(missingRefs.length){
  const working=work.find(j=>j.kind==='job'&&missingRefs.includes(j.target_id)&&['image','image_prepare','image_review'].includes(j.capability));
  if(working)return finish(2,jobNext(working,'正在準備參考素材','查看圖片處理進度；完成後仍需審閱並批准。'));
  const names=missingRefs.slice(0,3).map(id=>canon.find(e=>e.id===id)?.name||id).join('、');
  return finish(2,nav(`還有 ${missingRefs.length} 項參考素材未備妥`,`${names}${missingRefs.length>3?'等':''}。先生成或匯入並審閱，過時圖片需要更新。`,'準備角色與場景參考','canon'));
 }
 const boardScenes=project.storyboard?.scenes||[];
 const boardPending=boardScenes.find(s=>!s.ready);
 if(boardPending){
  stages[2].complete=false;stages[2].status='視覺圖板 '+boardScenes.filter(s=>s.ready).length+'／'+boardScenes.length+' 場已審閱';
  const anchors=(boardPending.panels||[]).flatMap(panel=>panel.anchors||[]),approved=anchors.filter(a=>a.ready&&!boardPending.stale).length,pending=anchors.filter(a=>a.asset&&!a.ready&&!(a.review?.verdict==='revise'&&(!a.review.fingerprint?.asset_id||a.review.fingerprint.asset_id===a.asset.id))).length,missing=anchors.filter(a=>!a.asset).length;
  const canReview=boardPending.adopted&&!boardPending.stale&&pending>0;
  return finish(3,{...nav(canReview?`${pending} 格分鏡畫面等你確認`:boardPending.stale?'分鏡安排已更新，需要重新確認':boardPending.adopted?'完成分鏡畫面':'先確認分鏡畫面安排',boardPending.title+`：已確認 ${approved}／${anchors.length} 格`+(missing?`，欠 ${missing} 張圖`:'')+'。打開後逐格查看，確認會自動保存，可隨時離開再繼續。',canReview?'開始審閱畫面':'查看分鏡畫面','shots'),boardScene:boardPending.scene_id,section:'visual-storyboard'});
 }
 for(const group of groups){
  if(group.edit_ids?.every(id=>observedEdits.has(id)))continue;
  const selected=selectedGroups.find(t=>t.shot_id===group.id);
  if(selected?.mapping?.status==='user_observed')continue;
  const next=(title,description,number=4)=>finish(number,{title,description,label:'處理生成分組',action:'progress-video',page:'video',id:group.id,section:'render'});
  if(selected)return next('整組影片已採用，請核對實際切點','播放 '+group.title+'，確認每個預定分鏡實際出現，再保存你觀察到的切鏡範圍。');
  if(groupTakes.some(t=>t.shot_id===group.id&&t.current&&t.state==='succeeded'))return next('多鏡影片有候選待審閱','檢查 '+group.title+' 的切鏡、表演及參考一致性，再採用整組。');
  if(groupTakes.some(t=>t.shot_id===group.id&&['queued','preparing','submitting','submitted','running','uncertain','recoverable'].includes(t.state)))return next('多鏡影片工作正在處理','查看 '+group.title+' 的原工作與回條，毋須重複生成。');
  return next(groupChecks[group.id]?.ready?'多鏡分組已可生成':'準備多鏡分組的圖片與提示詞',group.title+'：'+(group.reasons||[]).join('；'),groupChecks[group.id]?.ready?4:3);
 }
 const shot=shots.find(s=>!adopted.has(s.id));
 if(!shot&&project.edit_segments&&!project.edit_segments.complete)return finish(5,nav('綁定實際剪接範圍','看片後為每個剪接項目選 Take、素材入出點及時間線位置。配音預覽可同時進行。','設定素材範圍','video'));
 if(!shot)return finish(5,{title:'鏡頭影片已採用，接下來核對剪接與聲音',description:'各鏡素材已有採用版本。按需要處理配音，並對照實際影片確認剪接；這不代表整部成片已完成。',label:'查看實際剪接素材',action:'navigate',page:'video'});
 const row=rowById.get(shot.id),shotTakes=takes.filter(t=>t.shot_id===shot.id);
 const videoNext=(title,description,render=false)=>({title,description,label:render?'查看本鏡影片':'處理這個鏡頭',action:'progress-video',page:'video',id:shot.id,...(render?{section:'render'}:{})});
 if(shotTakes.some(t=>t.current&&t.state==='succeeded'&&!t.selected))return finish(4,videoNext('這一鏡有影片待你採用','播放候選影片，檢查表演、連戲和聲音，再決定採用。',true));
 const videoWork=work.find(t=>t.kind==='video'&&t.shot_id===shot.id);
 if(videoWork)return finish(4,videoNext(['uncertain','recoverable'].includes(videoWork.state)?'影片工作需要確認或回收':'正在製作這一鏡影片','查看原工作的進度及結果，毋須重新生成；取得成片後再審閱採用。',true));
 const requiredIds=new Set([shot.id,...(row?.mode==='REF2VA'?[]:row?.frames||[]).map(f=>f.frame_id)]);
 const frameWork=work.find(j=>j.kind==='job'&&requiredIds.has(j.target_id)&&['image','image_prepare','image_review','h3_strategy','h3_video_prompt'].includes(j.capability));
 if(frameWork)return finish(3,jobNext(frameWork,'這一鏡的素材正在處理','查看進度或待處理事項，結果完成後再審閱採用。'));
 if(!row?.selected||row.strategy_stale)return finish(3,videoNext(row?.strategy_stale?'這一鏡的畫面方案需要更新':'先決定這一鏡的做法','在影片頁檢視並採用做法與畫面藍圖，再準備所選模式需要的素材。'));
 if(!framesReady(row))return finish(3,videoNext('準備這一鏡需要的畫面',row.mode==='FL2VA'?'本鏡採用首尾幀模式，需完成並批准首幀與尾幀。':'本鏡只用首幀，完成並批准首幀便可繼續；毋須為此模式製作尾幀。'));
 const check=renderChecks[shot.id];
 if(!check?.ready)return finish(3,videoNext('核對這一鏡的提示詞與素材',(check?.reasons||[]).slice(0,2).join('；')||'前往影片頁查看最新檢查結果，準備並採用提示詞及所需素材。'));
 return finish(4,videoNext('這一鏡已可進入影片生成','素材與提示詞檢查已通過。核對設定後按生成，完成後再看片並採用。',true));
}
