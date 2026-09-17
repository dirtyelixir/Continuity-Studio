const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function renderLoraAdvice(p,row,v,working){
 const ready=(p.video_renders.groups?.[row.shot_id]||p.video_renders.shots?.[row.shot_id]),a=ready?.style_lora_advice?.[v.model];
 const pending=a&&['queued','running'].includes(a.state),current=a&&a.source_hash===ready?.source_hash;
 const button=(label,action,disabled)=>`<button type="button" class="small" data-render-action="${action}" data-id="${esc(row.shot_id)}" ${disabled?'disabled':''}>${label}</button>`;
 const labels={queued:'已排隊，正在等待創作引擎。',running:'正在閱讀提示詞並評估 LoRA。',awaiting_input:'等待人工服務提交建議，可在「活動與版本」處理。',failed:'推薦失敗，可重新分析。',cancelled:'推薦已取消。',interrupted:'推薦中斷，可重新分析。'};
 return `<section class="h3-lora-advice"><div class="panel-header"><h3>Style LoRA 建議</h3>${button(a?'重新推薦':'依提示詞推薦','recommend-loras',working||!ready?.ready||pending)}</div><p class="muted">由目前創作引擎閱讀已保存的提示詞，建議有需要才加 LoRA。套用後只顯示建議使用的欄位，並取代目前選擇；也可按下方「加入 Style LoRA」自行選擇。</p>
 ${!ready?.ready?'<p class="muted">請先完成本鏡素材與影片提示詞。</p>':''}
 ${a?`<p class="muted">${esc(a.provider==='astra'?'Astra':a.provider==='deepseek'?'DeepSeek':a.provider)}</p>${!current?'<p class="note">提示詞或素材已更新，請重新推薦。</p>':''}${a.state==='succeeded'&&current?`<p><strong>${esc(a.result.summary)}</strong></p>${a.result.decisions.map(d=>{const c=a.candidates.find(x=>x.name===d.name);return `<div class="h3-lora-advice-item"><strong>${d.use?'建議使用':'不建議使用'} · ${esc(c?.label||d.name)}</strong><p>${esc(d.reason)}</p><details><summary>提示詞依據</summary>${d.evidence.map(q=>`<blockquote>${esc(q)}</blockquote>`).join('')}</details></div>`;}).join('')}${button(a.result.decisions.some(d=>d.use)?'套用建議（取代目前 Style LoRA）':'套用建議（不使用 Style LoRA）','apply-lora-advice',working)}`:`<p>${esc(labels[a.state]||a.state)}</p>${a.error?`<p class="note">${esc(a.error)}</p>`:''}`}`:''}
 </section>`;
}
