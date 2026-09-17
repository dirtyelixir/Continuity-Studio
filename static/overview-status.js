// Read-only guidance from saved production state; opening this panel never queues work.
export function overviewState(project, pendingImages = 0) {
 const p=project.production, shots=p?.shots||[], canon=(p?.canon||[]).filter(e=>e.kind!=='voice');
 const approved=new Set((project.assets||[]).filter(a=>a.status==='approved').map(a=>a.target_id));
 const frames=shots.flatMap(s=>s.keyframes||[]);
 const references=canon.filter(e=>approved.has(e.id)).length;
 const approvedFrames=frames.filter(f=>approved.has(f.id)).length;
 const videoTakes=project.video_renders?.takes||[];
 const adoptedVideos=new Set(videoTakes.filter(t=>t.selected&&t.current&&t.state==='succeeded'&&shots.some(s=>s.id===t.shot_id)).map(t=>t.shot_id)).size;
 const activeStates=['queued','preparing','submitting','submitted','running','awaiting_input'];
 const work=[...(project.jobs||[]).map(j=>({...j,kind:'job'})),...(project.video_renders?.takes||[]).map(j=>({...j,kind:'video'})),...(project.postproduction?.takes||[]).map(j=>({...j,kind:'voice'}))]
  .filter(j=>activeStates.includes(j.state)||j.kind==='video'&&['uncertain','recoverable'].includes(j.state));
 let next;
 if(pendingImages) next={title:`${pendingImages} 項圖片待你審閱`,description:'查看候選圖片，再決定採用或修改；已批准的參考圖會供後續鏡頭沿用。',label:'查看待審圖片',action:'navigate',page:'review'};
 else if(!p) next=project.source_kind==='outline'
  ? (project.story_chapters?.length?{title:'繼續建立章節方案',description:'在下方章節查看方案工作，或交由 AI 發展劇本與分鏡。',label:'前往章節',action:'overview-section',section:'overview-chapters'}:{title:'開始第一章',description:'大綱已保存。寫下第一章的事件與人物，或貼上已有劇本。',label:'新增第一章',action:'new-chapter'})
  :{title:'建立故事與分鏡方案',description:'以已保存的構思或原文建立方案，審閱採用後再製作圖片。',label:'設定創作要求',action:'develop'};
 else if(references<canon.length) next={title:`還有 ${canon.length-references} 項參考素材未批准`,description:'先確立角色、場景與道具外觀，讓分鏡沿用同一套參考。',label:'準備角色與場景參考',action:'navigate',page:'canon'};
 else if(approvedFrames<frames.length) next={title:'繼續製作分鏡與關鍵幀',description:'參考素材已備妥。逐鏡查看畫面、生成進度與審閱結果。',label:'繼續鏡頭製作',action:'overview-shot',id:shots.find(s=>(s.keyframes||[]).some(f=>!approved.has(f.id)))?.id};
 else next={title:'查看影片製作準備',description:'按每鏡所選模式核對提示詞與素材；是否可生成以影片頁的檢查結果為準。',label:'開啟影片製作',action:'navigate',page:'video'};
 return {shots:shots.length,references,referenceTotal:canon.length,approvedFrames,frameTotal:frames.length,adoptedVideos,work,next,pendingImages};
}

export function renderOverviewStatus(project,{esc,button,pendingImages=0,targetName=id=>id,displayLabel=x=>x}) {
 const s=overviewState(project,pendingImages),n=s.next;
 const attrs=n.page?`data-page="${n.page}"`:n.section?`data-section="${n.section}"`:n.id?`data-id="${esc(n.id)}"`:'';
 const stages=[
  ['故事與劇本',project.production?`${s.shots} 個已採用鏡頭`:'待建立方案','overview'],
  ['角色與場景',`${s.references}／${s.referenceTotal} 項參考已批准`,'canon'],
  ['分鏡與關鍵幀',`${s.approvedFrames}／${s.frameTotal} 張已批准`,'shots'],
  ['影片製作',`${s.adoptedVideos}／${s.shots} 鏡影片已採用`,'video'],
 ];
 return `<section class="panel overview-status" aria-label="製作進度與下一步"><div class="overview-next"><div><div class="eyebrow">下一步</div><h2>${esc(n.title)}</h2><p class="muted">${esc(n.description)}</p></div>${button(esc(n.label)+' →',n.action,attrs,'primary')}</div>
 <nav class="overview-path" aria-label="製作流程">${stages.map(([title,status,page],i)=>button(`<span class="path-number">${i+1}</span><span><strong>${title}</strong><small>${status}</small></span>`,'navigate',`data-page="${page}" ${page==='overview'?'aria-current="page"':''} ${!project.production&&page!=='overview'?'disabled':''}`,'path-step')).join('')}${button('<span class="path-number">5</span><span><strong>剪接與配音</strong><small>預定剪接 · 配音入口</small></span>','overview-section',`data-section="overview-directing" ${!project.production?'disabled':''}`,'path-step')}</nav>
 ${s.work.length?`<div class="overview-work"><strong>${s.work.length} 項工作處理中／待處理</strong>${s.work.slice(0,3).map(j=>`<div class="overview-work-row"><span>${esc(j.kind==='video'?'影片生成':j.kind==='voice'?'配音製作':displayLabel(j.capability))} · ${esc(targetName(j.target_id||j.shot_id||''))}<small>${esc(displayLabel(j.state))}</small></span>${j.kind==='job'?button('查看進度','job-detail',`data-id="${esc(j.id)}"`,'small'):button('查看工作','navigate',`data-page="${j.kind==='video'?'video':'postproduction'}"`,'small')}</div>`).join('')}</div>`:''}
 <div class="overview-footer"><span>生成完成後仍需審閱採用。你可隨時返回任何製作階段。</span>${button('全部工作與版本','navigate','data-page="history"','small quiet')}</div></section>`;
}
