export function directingApprovalForm(review,proposal,esc){
 const result=review?.result;
 return `<p>你可以接受目前方案並繼續製作。人工決定會獨立記錄，AI 原有意見會保留。</p>${result?`<details open><summary>AI 審查：${esc(({pass:'通過',revise:'需要修訂',uncertain:'未能判斷'})[result.verdict]||result.verdict)}</summary><p>${esc(result.summary)}</p>${(result.issues||[]).map(i=>`<p>${esc(i.reason)}<br>${esc(i.recommendation)}</p>`).join('')}</details>`:'<p>目前未有完整 AI 審查結果；你仍可自行判斷並批准。</p>'}<form id="directing-approval-form"><label>批准備註（選填）<textarea name="note" rows="3" placeholder="可留空，例如：接受這個鏡頭安排。"></textarea></label><div class="modal-footer"><button type="button" data-action="close">返回</button><button class="primary" type="submit">${proposal?'人工批准並採用':'人工批准，繼續製作'}</button></div></form>`;
}
