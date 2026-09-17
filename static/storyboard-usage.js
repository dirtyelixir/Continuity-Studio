const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const roles={shot_opening:'來源首幀約束',endpoint:'來源尾幀約束',opening:'Opening',cut_opening:'CUT 後開場／新視圖',intermediate_keyframe:'鏡內關鍵狀態',final_frame:'來源尾幀',unknown:'角色待確認'};
export function renderAnchorUsage(a){
 const u=a.generation_usage;if(!u)return '';
 const plan=u.planned,submitted=u.submitted||[];
 const intended=!plan?'尚未有逐張用圖安排；實際提交情況見下方':!plan.route_active?'安排所屬分組已停用':plan.use==='image_conditioning'?'計劃作影像約束 · 提交時核對':'⚠ Planning only · 此安排不要求將圖片傳入 H3';
 return `<div class="note" data-storyboard-usage><strong>${esc(roles[u.role]||u.role)}</strong>${u.scene_time!=null?`<p>場景剪接時間 ${esc(u.scene_time)} 秒 · 來源 ${esc(a.time)} 秒</p>`:''}<p>${esc(intended)}</p>${plan?`<p>${esc(plan.reason)}</p>${plan.boundary_exception?`<p>開場／切鏡例外：${esc(plan.boundary_exception)}</p>`:''}`:''}${submitted.length?submitted.map(s=>`<p>✓ 此版本已提交 ${esc(s.mode)} · ${esc(s.roles.map(r=>({startImage:'首幀',endImage:'尾幀',reference:'參考圖'}[r]||r)).join('、'))} <small>（${esc(s.state==='succeeded'?'生成完成，效果仍須看片':s.state==='failed'?'生成失敗，仍保留提交證據':s.state)}）</small></p>`).join(''):'<p>未有此版本圖片傳入 H3 的提交證據。</p>'}</div>`;
}
export function renderFrameUses(p,uses){
 if(!uses?.length)return '';
 const anchors=(p.storyboard?.scenes||[]).flatMap(s=>s.panels.flatMap(panel=>panel.anchors.map(a=>({...a,title:panel.title}))));
 return `<div data-planned-frame-uses><h4>每張分鏡嘅生成用途</h4>${uses.map(u=>{const a=anchors.find(a=>a.id===u.anchor_id);return `<p><strong>${esc(a?.title||'分鏡')} · ${esc(a?.time??'?')} 秒</strong>：${u.use==='image_conditioning'?'計劃作影像約束（提交時核對）':'⚠ Planning only（此安排不要求傳圖）'}</p><p>${esc(u.reason)}</p>${u.boundary_exception?`<p>開場／CUT 例外：${esc(u.boundary_exception)}</p>`:''}`;}).join('')}</div>`;
}
