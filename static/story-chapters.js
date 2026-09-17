export function renderStoryOverview(project, {esc,button,head,stats,jobList,renderDirectorStyles}) {
 const chapters=project.story_chapters||[],adopted=project.production?.chapters||[];
 const chapterList=`<section id="overview-chapters" class="panel"><div class="panel-header"><div><h2>章節 · ${chapters.length}</h2><p class="muted">選擇章節繼續製作，或建立下一章。</p></div>${button('＋ 新增章節','new-chapter','','small')}</div>${chapters.length?chapters.map(ch=>{
  const current=adopted.find(x=>x.id===ch.id),sceneIds=new Set(current?.scene_ids||[]);
  const shotCount=(project.production?.shots||[]).filter(s=>sceneIds.has(s.scene_id)).length;
  const jobs=(project.jobs||[]).filter(j=>j.target_id===ch.id&&['narrative','storyboard'].includes(j.capability)).sort((a,b)=>String(b.created||'').localeCompare(String(a.created||'')));
  const running=jobs.some(j=>['queued','running','awaiting_input'].includes(j.state));
  const olderActive=jobs.slice(1).filter(j=>['queued','running','awaiting_input'].includes(j.state)).length;
  const attrs=`data-id="${esc(ch.id)}"`;
  return `<article class="story-chapter" data-chapter-id="${esc(ch.id)}"><div class="panel-header"><div><div class="eyebrow">第 ${esc(ch.number)} 章</div><h3>${esc(ch.title)}</h3></div>${button(ch.source_kind==='idea'?'編輯章節方向':'編輯章節原文','edit-chapter',attrs,'small')}</div>
  ${current?`<div class="chapter-current"><div class="panel-header"><div><strong>目前採用版本 · ${shotCount} 個鏡頭</strong><p class="muted">這是本章目前用於製作的內容。</p></div>${button('繼續本章製作 →','chapter-shots',attrs,'primary')}</div><details><summary>閱讀已採用劇情與劇本</summary><div class="prose">${esc(current.story)}</div><h4>劇本</h4><div class="prose">${esc(current.screenplay)}</div></details></div>`:'<p class="muted">章節原文已保存，尚未採用製作方案。</p>'}
  <details><summary>本章${ch.source_kind==='screenplay'?'原文劇本':ch.source_kind==='story'?'原文劇情':'創作方向'}</summary><div class="prose">${esc(ch.brief)}</div></details>
  <div class="chapter-work"><div class="panel-header"><h4>${current?'建立修訂方案':'建立製作方案'}</h4>${button(running?'方案工作處理中':current?'讓 AI 修訂劇本與分鏡':'讓 AI 建立劇本與分鏡','develop-chapter',`${attrs} ${running?'disabled':''}`,current?'small':'small primary')}</div><p class="muted">以已保存的大綱、本章內容及角色設定建立方案；完成後需審閱採用。${current?'新方案採用前，目前版本仍會保留。':''}</p>
  ${jobs.length?`<strong>最近一次方案工作</strong><p class="muted">以下是生成工作紀錄；目前採用內容以上方版本為準。</p>${jobList(jobs.slice(0,1))}`:''}
  ${jobs.length>1?`<details><summary>修訂紀錄 · ${jobs.length-1} 次過往工作${olderActive?` · ${olderActive} 項仍在處理`:''}</summary>${jobList(jobs.slice(1))}</details>`:''}</div></article>`;
 }).join(''):'<p class="story-prose">大綱已保存。新增第一章，寫下這一章的事件與人物，或貼上已有劇本。</p>'}</section>`;
 const idea=String(project.idea||''),excerpt=idea.length>160?idea.slice(0,160)+'…':idea;
 return chapterList+`<div class="overview-background"><div class="two-col"><section class="panel"><div class="panel-header"><h2>故事大綱</h2>${button('編輯大綱','edit-outline','','small')}</div><p class="story-prose">${esc(excerpt)}</p><details><summary>閱讀完整故事大綱</summary><div class="prose">${esc(idea)}</div></details><p class="muted">更新大綱會供之後的章節參考，已採用章節會保留。</p></section><section class="panel"><h2>視覺方向</h2><p>${esc(project.style)}</p><p class="muted">各章沿用作品的視覺風格與角色設定。</p>${project.production?button('查看共用角色與場景','navigate','data-page="canon"','small'):''}</section></div><details class="panel overview-directing"><summary>導演風格與拍法${project.director_styles?.selected?.name?' · '+esc(project.director_styles.selected.name):''}</summary>${renderDirectorStyles(project,esc,button)}</details></div>`;
}

export function chapterForm(ch,esc) {
 return `<form id="story-chapter-form"><label>章節名稱<input name="title" value="${esc(ch?.title||'')}" placeholder="第一章：天水圍" required maxlength="150"></label><label>本章已有甚麼？<select name="source_kind">${[['idea','本章大綱／創作方向 — 讓 創作引擎 發展'],['story','已有本章劇情 — 保留情節設計分鏡'],['screenplay','已有本章劇本 — 保留原文與對白']].map(([v,t])=>`<option value="${v}" ${ch?.source_kind===v?'selected':''}>${t}</option>`).join('')}</select></label><label>本章內容<textarea name="brief" rows="9" required minlength="3" maxlength="20000" placeholder="這章的事件、人物衝突、開始與結束狀態。可先寫大綱，亦可貼上完整本章劇情或劇本。">${esc(ch?.brief||'')}</textarea></label><p class="muted">建立方案時會讀取整體故事大綱、已有章節與共用角色設定。每章文字上限 20,000 字、方案最多 40 個鏡頭。</p><div class="modal-footer"><button type="submit" class="primary">保存章節</button></div></form>`;
}
