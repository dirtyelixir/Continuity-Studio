export function renderContextSettings(settings,esc){
 const entries=Object.entries(settings.context_profiles||{});
 if(!entries.length)return '';
 return `<section class="panel"><h2>模型上下文與輸出預算</h2><p class="muted">新工作會保存所選模型的容量。放得下時使用完整背景；章節場景與鏡頭可按原文索引取回相關背景。必要資料仍放不下時會停止並保留成果。設定不會切換服務商。</p>${entries.map(([id,p])=>`<div class="provider-row"><div><strong>${esc(settings.providers.find(x=>x.id===id)?.name||id)}</strong><div class="muted">上下文 ${Number(p.context_window).toLocaleString()} · 預留輸出 ${Number(p.max_output_tokens).toLocaleString()} tokens<br>${p.tokenizer==='llama_cpp'?'經 VRAM Manager／所選接口核對實際 token 數':'以 UTF-8 位元組作保守上界，並非精確 token 數'}</div></div><button type="button" class="small" data-action="context-limits" data-id="${esc(id)}">容量設定</button></div>`).join('')}<p class="muted">預設值是 Studio 工作預算；實際容量以服務商及本機啟動設定為準。輸出預留也是每次回覆上限，推理模型的思考亦會使用輸出額度；放得下輸入不保證能在額度內完成。舊工作保持原有模型與預算。</p></section>`;
}

export function contextLimitsForm(provider,policy,esc){
 return `<form id="context-limits-form"><p>${esc(provider.name)} · ${esc(provider.model)}</p><div class="form-grid"><label>上下文容量（tokens）<input name="context_window" type="number" min="4096" max="2097152" value="${Number(policy.context_window)}" required></label><label>每次輸出預留（tokens）<input name="max_output_tokens" type="number" min="256" max="393216" value="${Number(policy.max_output_tokens)}" required></label><label class="full">計數方式<select name="tokenizer"><option value="estimate" ${policy.tokenizer==='estimate'?'selected':''}>UTF-8 保守上界</option>${provider.kind==='http'?`<option value="llama_cpp" ${policy.tokenizer==='llama_cpp'?'selected':''}>llama.cpp 實際 tokenizer</option>`:''}</select></label></div><p class="muted">另保留 1,024 tokens 安全空間。本機 tokenizer 透過所選接口遵守 VRAM 排隊，不會直連 GPU 服務。上下文容量與輸出上限分開設定；增大上下文不會自動增加輸出。輸出可能包含模型推理，並非全數用於正式答案。變更只影響新工作。</p><button class="primary" type="submit">儲存容量設定</button></form>`;
}

export function renderContextUsage(job,esc){
 const p=job.input?.provider_config?.context_policy;
 if(!p)return '';
 const names={full:'完整背景',scoped:'原文索引與相關背景','deduplicated-foundation':'完整原文，移除重複副本'};
 const method=p.tokenizer==='llama_cpp'?'實際核對 token 數':'UTF-8 位元組保守上界（非精確 token 數）';
 return `<details><summary>上下文使用紀錄</summary><p>容量 ${Number(p.context_window).toLocaleString()} · 預留輸出 ${Number(p.max_output_tokens).toLocaleString()} tokens · ${p.tokenizer==='llama_cpp'?'實際 tokenizer':'UTF-8 保守上界'}</p>${(job.context_usage||[]).map(r=>`<p><strong>${esc(r.attempt)}</strong> · ${esc(names[r.mode]||r.mode)}<br>輸入${method} ${Number(r.input_tokens).toLocaleString()}（完整請求 ${method} ${Number(r.full_input_tokens).toLocaleString()}）${r.mode==='scoped'?` · 原文 ${Number(r.selected_units)} 段／另 ${Number(r.omitted_units)} 段保留於原始資料與索引`:''}</p>`).join('')}</details>`;
}
