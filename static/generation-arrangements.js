import {renderFrameUses} from './storyboard-usage.js';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const action=(text,kind,id)=>`<button type="button" class="small" data-group-action="${kind}" data-id="${esc(id)}">${text}</button>`;

function preparationRow(title,meta,control){
 return `<div class="arrangement-preparation-row"><strong>${esc(title)}</strong><span class="muted">${esc(meta)}</span>${control}</div>`;
}

export function renderAdoptedArrangements(p,sceneId){
 const saved=(p.generation_groups?.arrangements||[]).filter(a=>a.scene_id===sceneId);
 if(!saved.length)return '';
 return `<section class="panel" data-adopted-arrangements><h2>已採用的生成安排</h2>${saved.map(a=>{
  const current=a.status==='current';
  const rows=current?a.items.map(item=>item.execution==='native_montage'
   ?preparationRow(item.title,`${item.members.length} 個分鏡 · 整組生成`,item.group_id?action('準備整組','open',item.group_id):'<span class="notice">此分組已停用</span>')
   :[...new Map(item.members.map(m=>[m.shot_id,m])).values()].map(m=>preparationRow(m.title,`生成 ${m.duration} 秒`,`<button type="button" class="small" data-action="progress-video" data-id="${esc(m.shot_id)}" aria-label="準備 ${esc(m.title)}">準備</button>`)).join('')).join(''):'';
  return `<article class="adopted-arrangement"><div class="arrangement-heading"><h3>${esc(a.title)}</h3><span class="badge ${current?'approved':'stale'}">${current?'已採用':'需更新'}</span></div>${current?`<div class="arrangement-preparation-list">${rows}</div>`:`<p class="notice">${a.status==='legacy'?'舊版安排需要更新。':'分鏡已更新，請重新安排。'}</p>${action('重新安排生成分組','plan',a.scene_id)}`}
  <details class="arrangement-details" data-generation-arrangement="${esc(a.job_id+':details')}"><summary>查看安排詳情</summary><p>${esc(a.reason)}</p>${a.items.map(item=>`<article class="arrangement-detail-item"><h4>${esc(item.title)} · ${item.execution==='native_montage'?'整組生成 · '+esc(item.mode):'獨立來源生成'}</h4>${item.members.map(m=>`<p>${esc(m.title)}：${item.execution==='separate_source'?`生成完整 ${m.duration} 秒，再剪用 ${m.source_in}–${m.source_out} 秒`:`組內取用 ${m.source_in}–${m.source_out} 秒`}</p>`).join('')}<p>${esc(item.reason)}</p><ul>${item.checks.map(c=>`<li>${esc(c)}</li>`).join('')}</ul>${renderFrameUses(p,item.frame_uses)}</article>`).join('')}<button type="button" class="small" data-action="job-detail" data-id="${esc(a.job_id)}">查看原始記錄</button></details></article>`;
 }).join('')}</section>`;
}

export function renderShotArrangement(p,sid){
 const items=(p.generation_groups?.arrangements||[]).filter(a=>a.status==='current').flatMap(a=>a.items).filter(i=>(i.execution==='separate_source'||i.group_id)&&i.members.some(m=>m.shot_id===sid));
 if(!items.length)return '';
 return `<section class="panel" data-shot-arrangement><h3>本鏡的生成安排</h3>${items.map(i=>`<p>${i.execution==='native_montage'?'此鏡按已採用安排，與其他分鏡合成一段影片。':'此鏡獨立生成完整來源；剪接範圍與檢查要求會帶入新生成的 H3 提示詞。'}</p>${i.group_id?action('前往整組製作','open',i.group_id):''}<ul>${i.checks.map(c=>`<li>${esc(c)}</li>`).join('')}</ul>`).join('')}</section>`;
}
