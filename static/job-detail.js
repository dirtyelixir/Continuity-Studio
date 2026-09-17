// A completed job is an execution receipt; its creative verdict is separate.
const verdicts={pass:'通過',revise:'需要修訂',uncertain:'未能判斷'};
const list=value=>Array.isArray(value)?value:[];
export function directingJobResult(job,project,{esc,button}){
 const review=job.result;
 if(job.state!=='succeeded'||!review?.verdict){
  const messages={queued:'審查已排隊，尚未有結論。',running:'正在審查，完成後會在這裡自動顯示結論與建議。',awaiting_input:'等待提交人工審查結果，尚未有結論。',failed:'審查未能完成；這不代表方案不通過。請查看上方原因。',interrupted:'審查已中斷，尚未有完成結論。',cancelled:'審查已取消，尚未有完成結論。'};
  return `<section aria-label="導演審查結果"><h3>尚未有審查結論</h3><p>${esc(messages[job.state]||'尚未取得可顯示的審查結論。')}</p></section>`;
 }
 const source=job.input?.directing_source||{},shots=list(source.shots),scenes=list(source.scenes);
 const shotLabel=id=>shots.find(s=>s.id===id)?.title||id;
 const context=item=>list(item.shot_ids).map(shotLabel).join('、')||scenes.find(s=>s.id===item.scene_id)?.title||'整體方案';
 const issueCard=(item,index)=>`<article class="note"><h4>${index+1}. ${esc(context(item))}</h4><p><strong>問題：</strong>${esc(item.reason||'審查未提供問題說明。')}</p><p><strong>建議改法：</strong>${esc(item.recommendation||'這項意見未提供具體改法；可在修訂時補充你的要求。')}</p>${item.evidence?`<details><summary>查看原文依據</summary><blockquote>${esc(item.evidence)}</blockquote></details>`:''}</article>`;
 const issues=list(review.issues),coverage=list(review.coverage);
 // Coverage can contain additional failed beats without a separate issue record.
 const findings=[...issues,...coverage.filter(c=>c.verdict!=='pass'&&!issues.some(i=>list(i.beat_ids).includes(c.beat_id)||(i.reason===c.reason&&i.recommendation===c.recommendation)))];
 const current=project.directing?.current_review?.state==='succeeded'&&project.directing.current_review.job_id===job.id;
 const states=list(project.directing?.scenes).filter(s=>s.status!=='legacy');
 const approved=current&&states.length&&states.every(s=>['pass','human_approved'].includes(s.status))&&states.some(s=>s.status==='human_approved');
 const proposal=list(project.jobs).find(j=>j.id===job.target_id&&['narrative','storyboard'].includes(j.capability));
 let actions='',applicability='';
 if(current){
  applicability=approved?'此方案已由你人工批准；以下 AI 意見仍保留作參考。':'這是目前採用方案的審查結果。';
  if(review.verdict!=='pass'&&!approved){
   actions=button('查看建議並修訂方案','revise-current-directing','','primary');
   if(project.directing?.approval_source_hash)actions+=button('人工批准此方案','human-directing');
  }
 }else if(proposal){
  applicability='這份審查針對候選方案；請在方案頁查看目前可採取的操作。';
  actions=button('查看候選方案與處理意見','proposal',`data-id="${esc(proposal.id)}"`,'primary');
 }else{
  applicability='這是歷史審查記錄；目前方案的狀態請到故事與分鏡查看。';
  actions=button('查看目前方案','navigate','data-page="overview"');
 }
 return `<section aria-label="導演審查結果"><h3>審查結果：${esc(verdicts[review.verdict]||'未能判斷')}</h3><p>${esc(review.summary||'審查未提供摘要。')}</p><p class="muted">${esc(applicability)}</p>${actions?`<div class="actions">${actions}</div>`:''}${findings.length?`<h3>問題與建議 · ${findings.length} 項</h3>${findings.map(issueCard).join('')}`:review.verdict!=='pass'?'<p>審查未提供具體修訂建議。</p>':'<p>審查沒有列出需要修訂的問題。</p>'}${coverage.length?`<details><summary>查看逐項審查 · ${coverage.length} 項</summary>${coverage.map(c=>`<article class="note"><strong>${esc(context(c))} · ${esc(verdicts[c.verdict]||'未能判斷')}</strong><p>要傳達：${esc(c.required_communication)}</p><p>${esc(c.reason)}</p><p>建議：${esc(c.recommendation)}</p>${c.evidence?`<blockquote>${esc(c.evidence)}</blockquote>`:''}</article>`).join('')}</details>`:''}</section>`;
}
export function jobBudgetNotice(job,esc){
 const p=job.input?.provider_config?.context_policy,r=job.budget_usage;
 if(!p||!(r?.finish_reason==='length'||/輸出達到長度上限|output was truncated/.test(job.error||'')))return '';
 const n=v=>Number(v).toLocaleString();
 const input=r?.input_tokens!=null?`輸入${r.count_method==='utf8-byte-upper-bound'?'UTF-8 位元組保守上界（非精確 token 數）':'實際核對 token 數'} ${n(r.input_tokens)}${r.fits===true?'，已通過容量檢查':''}。`:'';
 const usage=r?.usage;
 const output=r?.content_chars!=null?`已收到正式答案 ${n(r.content_chars)} 字元。`:'';
 const accounting=usage?.completion_tokens!=null?`服務商回報輸出 ${n(usage.completion_tokens)} tokens${usage.reasoning_tokens!=null?`，其中推理 ${n(usage.reasoning_tokens)} tokens`:''}。`:r?.reasoning_chars!=null?`已收到推理 ${n(r.reasoning_chars)} 字元；服務商未回報精確 token 用量。`:'這份舊記錄未保存推理用量，無法確認額度分配。';
 return `<section class="notice" aria-label="輸出預算說明"><h3>本次輸出預算與中斷原因</h3><p>本次上下文容量 ${n(p.context_window)} · 輸出上限 ${n(p.max_output_tokens)} tokens。${esc(input)}${esc(output)}</p><p>${esc(accounting)}</p><p>輸出上限亦包含模型推理；預留額度不保證模型能在額度內完成。可到「擴充功能與服務商 → 模型上下文與輸出預算」調整每次輸出預留，再按目前設定重試。舊工作預算不會追溯更改。</p></section>`;
}
export function groupPlanJobResult(job,project,{esc,button}){
 if(job.state!=='succeeded'||!job.result)return '<p>生成安排尚未完成；請查看工作狀態。</p>';
 const source=job.input?.group_plan_source,projection=project.generation_groups?.plans?.find(j=>j.id===job.id);
 const current=source?source.plan_contract_version===3:projection?.contract_current===true;
 const banner=current?'生成安排已保存，仍需檢視後採用。':'這份舊安排可能混用剪接與生成模式規則，需要重新安排。舊模式建議不作為目前依據。';
 const actions=project.id===job.project_id?button('前往影片準備','navigate','data-page="video"'):'';
 return `<section aria-label="生成安排結果"><h3>${current?'生成安排待檢視':'舊版生成安排需要更新'}</h3><p class="${current?'muted':'notice'}">${esc(banner)}</p><p>獨立來源先生成完整影片再剪接；裁切本身不排除首幀或首尾幀模式。生成模式由逐鏡影片準備判斷。</p><p>首尾圖不能保證停頓秒數、運鏡速度或中段動作；實際效果仍須檢查成片。</p>${actions}${current?`<p>${esc(job.result.summary)}</p>`:`<details><summary>查看舊版原始摘要</summary><p>${esc(job.result.summary)}</p></details>`}</section>`;
}
export function momentVerificationNotice(job,esc){
 const record=job.moment_verification||job.input?.image_moment_verification;
 if(!record)return '';
 const accepted=record.state==='accepted',repaired=record.repaired===true,pending=record.state==='attempted';
 const title=accepted?(repaired?'已在生圖前自動修正畫面時刻':'生圖前畫面時刻檢查已通過'):pending?'正在檢查畫面時刻':'生圖前畫面時刻檢查尚未通過';
 const notes=job.input?.image_moment_alignment?.omitted_context||job.input?.image_moment_alignment?.notes||[];
 return `<section class="notice" aria-label="畫面時刻同步"><h3>${esc(title)}</h3><p>${accepted?'已按指定時刻核對視線、姿勢、持物及燈光狀態；實際生成畫面仍須驗收。':pending?'正在核對整理後的提示詞，通過後才會開始生圖。':'圖片渲染前已攔下未解決的文字問題。'}</p>${record.error?`<p>${esc(record.error)}</p>`:''}${notes.length?`<details><summary>查看自動對齊記錄</summary>${notes.map(x=>`<p>${esc(x)}</p>`).join('')}</details>`:''}</section>`;
}
export function jobDetailBody(job,project,helpers){
 const {esc,providerName,renderProductionMethod,renderContextUsage,imageLoraMarkup}=helpers;
 const invalidAsset=(project.assets||[]).find(a=>(a.job_id===job.id||a.id===job.target_id)&&a.image_output_quality?.valid===false);
 const imageNotice=invalidAsset?`<p class="notice"><strong>輸出檔案無有效畫面</strong> ${esc(invalidAsset.image_output_quality.message)} 原執行記錄與圖片保留；服務回報完成不代表圖片有效。</p>`:'';
 let result=job.capability==='directing_qc'?directingJobResult(job,project,helpers):job.capability==='h3_group_plan'?groupPlanJobResult(job,project,helpers):job.result?.text?`<div class="prose">${esc(job.result.text)}</div>`:job.result?.summary?`<p>${esc(job.result.summary)}</p>`:'';
 if(job.result==null&&job.capability!=='directing_qc')result=`<p class="muted">${job.capability==='image'&&job.error==='圖片 LoRA 依據必須引用本次畫面簡報原文。'?'畫面簡報已整理，工作停在 LoRA 依據檢查，尚未送入 ComfyUI。重試時會核對並沿用相同要求與參考圖的簡報。':'尚無完成結果。'}</p>`;
 if(job.result==null&&job.saved_proposal){
  const saved=job.saved_proposal,checks=list(saved.checks),blocked=checks.filter(c=>c.state==='blocked');
  result=`<section aria-label="已保存草案"><h3>草案已保存，尚未成為完成方案</h3><p>${esc(saved.title)} · ${esc(saved.scenes)} 場景 · ${esc(saved.shots)} 鏡頭 · ${esc(saved.canon)} 項角色／場景／道具設定</p><p>已保存的內容可查看；仍需通過檢查及審閱，目前採用版本保留。</p>${checks.length?`<p>鏡頭狀態檢查：${checks.filter(c=>c.state==='accepted').length} 鏡通過${blocked.length?`，${blocked.length} 鏡尚未通過`:''}。</p>`:''}${blocked.map(c=>`<div class="notice"><strong>接續檢查尚未通過 · ${esc(c.shot_id)}</strong><p>${esc(c.error)}</p></div>`).join('')}<details><summary>查看已保存故事與劇本</summary><div class="prose">${esc(saved.story)}</div><pre>${esc(saved.screenplay)}</pre></details></section>`;
 }
 if(job.result!=null&&job.capability!=='directing_qc')result+=`<details><summary>查看結構化結果</summary><pre>${esc(JSON.stringify(job.result,null,2))}</pre></details>`;
 return `${imageNotice}${job.error?`<p class="notice">${esc(helpers.uiError?helpers.uiError(job.error):job.error)}</p>`:''}${jobBudgetNotice(job,esc)}${momentVerificationNotice(job,esc)}${result}<details data-job-technical><summary>技術記錄（製作方法、來源與原始資料）</summary><p class="muted">供追查執行使用，並非審查結論。</p><p>${esc(job.id)} · ${esc(providerName(job.provider))}</p>${renderProductionMethod(job.input,esc)}${renderContextUsage(job,esc)}${job.input?.local_image_plan?`<p><strong>${esc(job.input.local_image_plan.name)}</strong><br>${esc(job.input.local_image_plan.reason)}</p>`:''}${imageLoraMarkup(job.input?.local_image_plan,esc)}${job.capability==='directing_qc'&&job.result!=null?`<details><summary>原始審查結果</summary><pre>${esc(JSON.stringify(job.result,null,2))}</pre></details>`:''}<details><summary>完整請求與來源記錄</summary><pre>${esc(JSON.stringify(job.input,null,2))}</pre></details></details>`;
}
// Refresh only this read-only dialog. Preserve each disclosure independently;
// opening one evidence paragraph must not expand every technical record.
export function refreshJobDetail(element,job,project,helpers){
 const merged={...element._jobSnapshot,...job,input:{...element._jobSnapshot?.input,...job.input}};
 element._jobSnapshot=merged;
 const html=jobDetailBody(merged,project,helpers);
 if(element._jobMarkup===html)return;
 const key=d=>{const path=[];for(let n=d;n&&n!==element;n=n.parentElement){if(n.tagName==='DETAILS')path.push(n.querySelector(':scope > summary')?.textContent);if(n.tagName==='ARTICLE')path.push(n.querySelector('h4')?.textContent);}return JSON.stringify(path);};
 const open=new Set([...element.querySelectorAll('details[open]')].map(key));
 const focus=element.contains(element.ownerDocument.activeElement)?element.ownerDocument.activeElement:null;
 const action=focus?.dataset.action,id=focus?.dataset.id;
 element.innerHTML=html;element._jobMarkup=html;
 element.querySelectorAll('details').forEach(d=>{d.open=open.has(key(d));});
 if(action)[...element.querySelectorAll('[data-action]')].find(b=>b.dataset.action===action&&b.dataset.id===id)?.focus({preventScroll:true});
}
