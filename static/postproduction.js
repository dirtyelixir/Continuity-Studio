const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const action=(label,a,attrs='',primary=false)=>`<button type="button" data-voice-action="${a}" ${attrs} class="small ${primary?'primary':''}">${label}</button>`;
const status={queued:'等待生成',running:'VoxCPM2 正在配音',succeeded:'可試聽',failed:'生成失敗',interrupted:'工作中斷',importing:'匯入中'};
export const voicePresetGroups=[
 ['聲線',['女聲','男聲','中性聲線']],
 ['年齡感',['童聲','少年感','年輕成年','成熟','年長']],
 ['音高',['低沉','中低音','中音','中高音','高音']],
 ['質感',['溫暖','清亮','柔和','渾厚','沙啞','氣聲','鼻音']],
 ['語氣',['親切','沉穩','活潑','冷淡','嚴肅']],
 ['節奏',['緩慢','從容','自然','輕快','急促']],
];
export const voiceLanguages=['英文','粵語（香港）','國語（台灣）','中文（大陸）'];
export const auditionTexts={
 '英文':"Hello, I'm here. Let's tell this story together.",
 '粵語（香港）':'你好，我喺度。等我哋一齊將呢個故事講落去。',
 '國語（台灣）':'你好，我在這裡。讓我們一起把這個故事說下去。',
 '中文（大陸）':'你好，我在这里。让我们一起把这个故事说下去。',
};
export function languageAudition(language,current){
 const aliases={en:'英文',english:'英文','yue-hk':'粵語（香港）',yue:'粵語（香港）',cantonese:'粵語（香港）','zh-tw':'國語（台灣）','zh-cn':'中文（大陸）',zh:'中文（大陸）',mandarin:'中文（大陸）'};
 return Object.values(auditionTexts).includes(current)?auditionTexts[aliases[language.toLowerCase()]||language]||current:current;
}
export function voiceErrorMessage(error){
 if(/HTTP Error 409/.test(error)&&/vram\/gpu\/acquire/.test(error))return 'GPU 資源申請被拒絕，配音尚未開始。請待其他 GPU 工作完成或本機服務復原後再生成。';
 const known=error.match(/RuntimeError: (GPU 資源未就緒[^\n]*)/);
 return known?known[1]:error;
}
export const nonverbalPresetGroups=[['音型',['電子短音','雙音回應','脈衝音','滑音']],['質感',['柔和','清亮','金屬感','數碼感']],['節奏',['緩慢','從容','輕快','急促']]];
const voicePresets=[...new Set([...voicePresetGroups,...nonverbalPresetGroups].flatMap(([,values])=>values))];
export function splitVoiceDescription(description=''){
 const parts=description.split('；');
 return {selected:voicePresets.filter(v=>parts.includes(v)),custom:parts.filter(v=>!voicePresets.includes(v)).join('；')};
}
export function composeVoiceDescription(original,selected,custom){
 const initial=splitVoiceDescription(original),chosen=voicePresets.filter(v=>selected.includes(v));
 if(custom===initial.custom&&JSON.stringify(chosen)===JSON.stringify(initial.selected))return original;
 return [...chosen,...(custom.trim()?[custom]:[])].join('；');
}
export function roleVoiceProfile(v){
 return v.description.trim()?v:{...v,description:v.default_voice?.description||'',...(v.default_voice?.sound_mode?{sound_mode:v.default_voice.sound_mode}:{})};
}
// Background text design releases the main UI action guard. Closing the dialog
// leaves its durable job running but never reopens it or replaces another form.
export function prepareRoleVoice({v,ent,base,cid,api,modal,openEditor}){
 modal('角色音色 · '+ent.name,`<section id="voice-default-loading"><p class="muted">${esc(ent.description)}</p><h3>按角色設定設計預設音色</h3><p role="status" id="voice-default-status">正在讀取角色描述、固定設定與分鏡表現…</p><p class="muted">完成後會保存這套設計，之後可直接沿用。你可以關閉視窗，稍後再回來。</p><button type="button" id="voice-default-retry" hidden>重試設計</button><button type="button" id="voice-default-manual">自行填寫音色</button></section>`);
 const panel=document.querySelector('#voice-default-loading'),status=panel.querySelector('#voice-default-status'),retry=panel.querySelector('#voice-default-retry');
 panel.querySelector('#voice-default-manual').onclick=()=>openEditor(v);
 const run=async(retryFailed=false)=>{
  retry.hidden=true;status.textContent='正在根據完整角色設定設計音色…';
  try{
   let response=await api(base+'/voices/'+cid+'/default',{version:v.version,retry:retryFailed});
   if(!panel.isConnected)return;
   if(response.job){
    let job=response.job;
    while(['queued','running'].includes(job.state)){
     status.textContent=job.state==='queued'?'音色設計已排隊；完成後會顯示角色專屬設定。':'正在根據完整角色設定設計音色…';
     await new Promise(resolve=>setTimeout(resolve,1500));if(!panel.isConnected)return;
     job=await api('/jobs/'+job.id);if(!panel.isConnected)return;
    }
    if(job.state!=='succeeded')throw new Error(job.state==='awaiting_input'?'目前使用人工創作服務，請先提交設計結果，或自行填寫音色。':job.error||'音色設計未完成。');
    response=await api(base+'/voices/'+cid+'/default');if(!panel.isConnected)return;
   }
   if(!roleVoiceProfile(response.profile).description)throw new Error('角色設定已變更，請重新設計音色。');
   openEditor(response.profile);
  }catch(error){if(panel.isConnected){status.textContent='未能建立角色預設音色：'+error.message;retry.hidden=false;}}
 };
 retry.onclick=()=>run(true);
 return run();
}
export function voiceDescriptionFields(v){
 const {selected,custom}=splitVoiceDescription(v.description);
 const nonverbal=v.sound_mode==='nonverbal',groups=nonverbal?nonverbalPresetGroups:voicePresetGroups;
 const languages=voiceLanguages.includes(v.language)?voiceLanguages:[...voiceLanguages,v.language];
 return `<details id="voice-custom-options"><summary>自訂音色特色（可多選）</summary><div class="voice-description-fields"><p class="muted">需要特別的聲音特色時才調整。可多選，並修改下方的完整音色描述。</p>${groups.map(([group,values])=>`<fieldset class="voice-preset-group"><legend>${group}</legend><div class="voice-preset-options">${values.map(value=>`<label><input type="checkbox" name="voice_preset" value="${value}" ${selected.includes(value)?'checked':''}>${value}</label>`).join('')}</div></fieldset>`).join('')}<label>完整音色描述<textarea name="custom_description" rows="3" maxlength="1200" placeholder="補充聲音質感、音高或節奏；也可只用自訂描述。">${esc(custom)}</textarea></label><p class="muted">所選音色與自訂描述合共最多 1200 字。</p></div></details><div ${nonverbal?'hidden':''}><label for="voice-language">語言與口音</label><select id="voice-language" name="language" ${nonverbal?'disabled':'required'}>${languages.map(value=>`<option value="${esc(value)}" ${value===v.language?'selected':''}>${esc(value)}</option>`).join('')}</select></div>`;
}
export function voiceReferenceFields(v,takes){
 const nonverbal=v.sound_mode==='nonverbal';
 const refs=takes.filter(t=>t.character_id===v.character_id&&t.state==='succeeded'&&t.request?.provider==='uploaded');
 return `<section class="panel tight voice-reference"><h3>參考聲音（選填）</h3><p class="muted">附上 ${nonverbal?'0.1–30 秒的角色音效':'2–30 秒的人聲'}，16-bit PCM WAV，最多 20 MB。附件先儲存供試聽，按「儲存音色設定」後才套用；上傳不會生成配音。</p><label for="voice-reference-file">附加參考音訊</label><input id="voice-reference-file" type="file" accept="audio/wav,.wav"><button type="button" id="voice-attach" class="small">上傳附件</button><p id="voice-attach-status" class="muted" role="status"></p><label for="voice-reference-select">使用的參考音訊</label><select id="voice-reference-select" name="reference_take_id"><option value="">不使用附件 · 使用角色預設音色</option>${refs.map(t=>`<option value="${esc(t.id)}" ${v.reference_take_id===t.id?'selected':''}>${esc(t.request.filename||'參考人聲')} · ${new Date(t.created).toLocaleString('zh-HK')}</option>`).join('')}</select><audio id="voice-reference-audio" controls preload="none" hidden></audio><div id="voice-reference-settings" hidden data-nonverbal="${nonverbal}"><label for="voice-reference-mode">參考方式</label><select id="voice-reference-mode" name="reference_mode"><option value="timbre" ${v.reference_mode!=='clone'?'selected':''}>只參考音色</option><option value="clone" ${v.reference_mode==='clone'?'selected':''}>Clone · 貼近原聲表現</option></select><p id="voice-reference-help" class="muted"></p><div id="voice-reference-transcript" hidden><label for="voice-reference-text">附件逐字稿</label><textarea id="voice-reference-text" name="reference_text" rows="3" maxlength="2000" placeholder="逐字填寫附件內的人聲內容，不是下方的試音對白。">${esc(v.reference_text||'')}</textarea></div></div></section>`;
}
export function voiceReferencePayload(form,soundMode){
 const f=new FormData(form),id=f.get('reference_take_id');
 if(id===null)return {};
 if((soundMode??f.get('sound_mode'))==='nonverbal')return {reference_take_id:id||null,reference_mode:'timbre',reference_text:''};
 return {reference_take_id:id||null,reference_mode:f.get('reference_mode')||'timbre',reference_text:id?f.get('reference_text')||'':''};
}
export function installVoiceReferences(form,{v,takes,base,cid,api,guarded}){
 const select=form.querySelector('#voice-reference-select');if(!select)return;
 const refs=[...takes],file=form.querySelector('#voice-reference-file'),attach=form.querySelector('#voice-attach'),status=form.querySelector('#voice-attach-status'),audio=form.querySelector('#voice-reference-audio'),mode=form.querySelector('#voice-reference-mode'),transcript=form.querySelector('#voice-reference-text');
 const update=()=>{
  const nonverbal=v.sound_mode==='nonverbal';
  const ref=refs.find(t=>t.id===select.value),clone=!nonverbal&&mode.value==='clone';
  if(nonverbal){mode.value='timbre';mode.disabled=true;}
  form.querySelector('#voice-reference-settings').hidden=!select.value||nonverbal;
  form.querySelector('#voice-reference-transcript').hidden=!clone;
  transcript.required=!!select.value&&clone;
  transcript.setCustomValidity(transcript.required&&!transcript.value.trim()?'請填寫附件內的人聲逐字稿。':'');
  form.querySelector('#voice-reference-help').textContent=clone?'沿用附件的音色、節奏及表情。此模式以原聲為準，不套用文字音色或表演指令；新對白仍使用你設定的文字。':'主要沿用附件音色，語氣及節奏可按角色設定調整。這仍會保留說話者的聲音特徵。';
  audio.hidden=!ref;
  if(ref){const src=base.replace('/projects/','/api/projects/')+'/voice-takes/'+ref.id+'/audio';if(audio.getAttribute('src')!==src)audio.src=src;}else{audio.pause();audio.removeAttribute('src');}
 };
 select.onchange=update;mode.onchange=update;transcript.oninput=update;update();
 attach.onclick=()=>{
  const chosen=file.files?.[0];if(!chosen){status.textContent='請先選擇 WAV 音訊檔。';return;}
  if(chosen.size>20*1024*1024){status.textContent='音檔上限為 20 MB。';return;}
  attach.disabled=true;status.textContent='正在上傳參考音訊…';
  guarded(async()=>{try{
   const body=new FormData();body.set('file',chosen);body.set('version',String(v.version));body.set('attachment','true');body.set('reference_sound_mode',v.sound_mode||'speech');
   const ref=await api(base+'/voices/'+cid+'/upload',body);refs.push(ref);takes.push(ref);
   const option=document.createElement('option');option.value=ref.id;option.textContent=ref.request.filename||chosen.name;select.append(option);select.value=ref.id;file.value='';
   status.textContent='已附加，可先試聽。儲存音色設定後套用。';update();
  }catch(error){status.textContent='上傳失敗：'+error.message;throw error;}finally{attach.disabled=false;}});
 };
}
function takeCard(t,profile){return `<div class="panel voice-take"><div class="meta"><b>${t.selected?'✓ 已採用':status[t.state]||t.state}</b><small>${new Date(t.created).toLocaleString('zh-HK')}</small></div>${!t.current?'<p class="notice">來源設定已更新，此版本保留作記錄。</p>':''}${t.result?`<audio controls preload="none" data-voice-audio="${esc(t.id)}" aria-label="試聽角色聲音" src="${esc(t.audio_url)}"></audio><p class="muted">${t.result.duration.toFixed(2)} 秒 · ${t.result.sample_rate} Hz${t.result.overrun?' · 超出對白時段，剪接時需調整':''}</p>`:''}${t.error?`<p class="notice overflow">${esc(voiceErrorMessage(t.error))}</p>${voiceErrorMessage(t.error)!==t.error?`<details><summary>技術錯誤記錄</summary><pre>${esc(t.error)}</pre></details>`:''}`:''}<div class="actions">${t.state==='succeeded'&&t.current&&!t.selected?action(t.kind==='voice'?(profile.sound_mode==='nonverbal'?'採用此角色音效':'採用此角色音色'):'採用此句配音','adopt',`data-id="${t.id}" data-version="${profile.version}"`,true):''}${t.audio_url?`<a href="${t.audio_url}" download="${esc(t.character_id)}-${t.id}.wav" class="small">下載 WAV</a>${action('在資料夾中顯示','reveal',`data-id="${t.id}"`)}`:''}</div><details><summary>音色與來源記錄</summary><pre>${esc(JSON.stringify({request:t.request,result:t.result},null,2))}</pre></details></div>`;}
export function voicePreview(v,takes=[]){
 const playable=takes.filter(t=>t.character_id===v.character_id&&t.kind==='voice'&&t.state==='succeeded'&&t.current&&t.audio_url);
 return playable.find(t=>t.id===v.selected_take_id)||playable[0]||null;
}
export function voicePlaybackPanel(v,takes=[],compact=false){
 const t=voicePreview(v,takes),selected=t?.id===v.selected_take_id;
 if(!t)return `<p class="muted">${v.sound_mode==='nonverbal'?'目前設定未有可試聽的音效，匯入後即可試聽。':'目前設定未有可試聽的音檔，生成或匯入後即可試聽。'}</p>`;
 return `<section class="voice-playback"><h3>${selected?'現使用的聲音':'目前設定的試聽候選'}</h3>${selected?'':'<p class="muted">尚未採用；試聽後可選作角色聲音。</p>'}${compact?`<div class="voice-take"><audio controls preload="none" aria-label="試聽角色聲音" src="${esc(t.audio_url)}"></audio></div>`:takeCard(t,v)}</section>`;
}
export function captureVoicePlayback(root,pid){
 if(!pid||root.dataset.voiceProject!==pid)return null;
 return {expanded:new Set([...root.querySelectorAll('details[data-voice-history][open]')].map(el=>el.dataset.voiceHistory)),audio:new Map([...root.querySelectorAll('audio[data-voice-audio]')].map(el=>[el.dataset.voiceAudio,el]))};
}
export function restoreVoicePlayback(root,pid,saved){
 root.dataset.voiceProject=pid||'';if(!saved)return;
 root.querySelectorAll('details[data-voice-history]').forEach(el=>{el.open=saved.expanded.has(el.dataset.voiceHistory);});
 root.querySelectorAll('audio[data-voice-audio]').forEach(el=>{const old=saved.audio.get(el.dataset.voiceAudio);if(old&&old.getAttribute('src')===el.getAttribute('src'))el.replaceWith(old);});
}
export function renderPostproduction(project){
 const plan=project.production,p=project.postproduction;
 if(!plan)return '<h1>後製配音</h1><p>先在製作手冊採用故事與分鏡，便可為每個角色建立音色。</p>';
 if(!p)return '<h1>後製配音正在更新</h1><p>現有工作完成後會啟用新介面，已保存的製作資料仍然保留。</p>';
 const chars=plan.canon.filter(e=>['character','crowd','voice'].includes(e.kind)),takes=p.takes;
 return `<div class="page-header"><div><div class="eyebrow">${esc(project.title)} · 後製</div><h1>角色音色與配音</h1><p class="muted">角色可使用人聲對白或非語言音效，試聽後採用。</p></div>${action('檢查 VoxCPM2','status')}</div><div class="note">人聲以 VoxCPM2 生成；非語言聲音可匯入 WAV 音效。聲音設定與附件不會自動生成或加入分鏡。配音保留原長度，供後製剪接；不會自動替換影片聲軌。</div><h2>角色音色</h2><div class="grid">${chars.map(e=>{const v=p.profiles.find(x=>x.character_id===e.id),nonverbal=roleVoiceProfile(v).sound_mode==='nonverbal',all=takes.filter(t=>t.character_id===e.id&&t.kind==='voice'),selected=all.find(t=>t.id===v.selected_take_id&&t.current),preview=voicePreview(v,all),pending=all.filter(t=>['queued','running'].includes(t.state));return `<article class="card" id="voice-${esc(e.id)}"><div class="card-body">${e.kind==='voice'?'<div class="note">只聞其聲 · 聲音資產，不建立人物圖片</div>':''}<div class="eyebrow">${selected?'已建立可重用音色':all.some(t=>t.state==='succeeded'&&t.current)?'音色候選待試聽':'待建立音色'}</div><h2>${esc(e.name)}</h2><p>${esc(v.description||v.default_voice?.description||'開啟音色設定，會按完整角色設定設計一套預設音色。')}</p><p class="muted">${nonverbal?'非語言聲音 · 無人聲／無對白':esc(v.language)}</p>${v.reference_take_id?`<p class="note">已附加參考聲音 · ${v.reference_mode==='clone'?'Clone：貼近原聲表現':'只參考音色'}</p>`:''}<div class="actions">${action('音色設定','edit',`data-character="${e.id}"`,!v.description)}${v.description?nonverbal?action('匯入角色音效','sound-upload',`data-character="${e.id}" data-version="${v.version}"`,true):action('生成音色候選','design',`data-character="${e.id}" data-version="${v.version}"`,true)+action('匯入參考人聲','upload',`data-character="${e.id}" data-version="${v.version}"`):''}</div>${pending.map(t=>takeCard(t,v)).join('')}${voicePlaybackPanel(v,all)}${all.filter(t=>!pending.includes(t)&&t!==preview).length?`<details data-voice-history="${esc(e.id)}"><summary>試聽候選與歷史版本（${all.filter(t=>!pending.includes(t)&&t!==preview).length}）</summary>${all.filter(t=>!pending.includes(t)&&t!==preview).map(t=>takeCard(t,v)).join('')}</details>`:''}</div></article>`;}).join('')}</div><h2 style="margin-top:32px">分鏡對白配音</h2>${plan.shots.map(s=>`<section class="panel"><h3>${esc(s.title)} <small class="muted">${s.duration} 秒</small></h3>${s.dialogue.length?s.dialogue.map((d,i)=>{const v=p.profiles.find(x=>x.character_id===d.entity_id),name=chars.find(x=>x.id===d.entity_id)?.name||d.entity_id,items=takes.filter(t=>t.kind==='line'&&t.request.source.shot_id===s.id&&t.request.source.dialogue_index===i);return `<div class="voice-line"><div class="meta"><b>${esc(name)}</b><span>${d.start}–${d.end} 秒 · ${esc(d.language)}</span></div><p class="story-prose">${esc(d.text)}</p><p class="muted">${esc(d.delivery)}</p>${p.silent_lines?.includes(s.id+':'+i)?'<p class="muted">無聲口形 · 保留分鏡原意，不生成配音。</p>':v?.sound_mode==='nonverbal'?'<p class="notice">此角色使用非語言聲音，不生成對白人聲；請在剪接中安排角色音效。</p>':v?.selected_take_id?action('以角色音色生成這句','line',`data-shot="${s.id}" data-index="${i}"`,true):'<p class="notice">先採用此角色的音色，才可配音。</p>'}${items.length?`<details data-voice-history="line-${esc(s.id)}-${i}"><summary>配音版本（${items.length}）</summary>${items.map(t=>takeCard(t,v||{version:0})).join('')}</details>`:''}</div>`;}).join(''):'<p class="muted">這個鏡頭沒有對白。</p>'}</section>`).join('')}`;
}
export function installVoiceUI({getProject,api,modal,close,refresh,guarded,toast}){
 document.addEventListener('click',e=>{const b=e.target.closest('[data-voice-action]');if(!b)return;guarded(async()=>{
 const p=getProject(),base='/projects/'+p.id,a=b.dataset.voiceAction,cid=b.dataset.character;
 if(a==='status'){const s=await api('/voxcpm/status');toast(s.ready?'本機 VoxCPM2 已就緒；生成時由 VRAM Manager 安排運算。':s.error||'VoxCPM2 尚未就緒');return;}
 if(a==='design'){await api(base+'/voices/'+cid+'/generate',{version:Number(b.dataset.version)});toast('已排入音色生成；完成後可試聽。');await refresh(true);return;}
 if(a==='line'){await api(base+'/voice-lines/generate',{shot_id:b.dataset.shot,dialogue_index:Number(b.dataset.index)});toast('已排入對白配音。');await refresh(true);return;}
 if(a==='adopt'){await api(base+'/voice-takes/'+b.dataset.id+'/adopt',{version:Number(b.dataset.version)});await refresh(true);toast('已採用此版本。');return;}
 if(a==='reveal'){await api(base+'/voice-takes/'+b.dataset.id+'/reveal',{});return;}
 if(a==='sound-upload'){
 modal('匯入角色音效',`<form id="voice-effect-upload"><p>匯入無人聲的 beep／boop 或其他角色音效。完成後先試聽，再採用。</p><p class="muted">0.1–30 秒、16-bit PCM WAV，最多 20 MB。保留原音檔；不會經過人聲生成或 Clone。</p><input type="file" name="file" accept="audio/wav,.wav" required><button type="submit" class="primary">匯入音效</button></form>`);
 document.querySelector('#voice-effect-upload').onsubmit=e=>{e.preventDefault();const body=new FormData(e.target);body.set('version',b.dataset.version);guarded(async()=>{await api(base+'/voices/'+cid+'/upload',body);close();await refresh(true);});};return;
 }
 if(a==='edit'||a==='upload'){
 const v=p.postproduction.profiles.find(x=>x.character_id===cid),ent=p.production.canon.find(x=>x.id===cid);
 const modeDrafts=new Map();
 const openEditor=v=>{
 const draft={...roleVoiceProfile(v,ent),sample_text:languageAudition(v.language,v.sample_text)},nonverbal=draft.sound_mode==='nonverbal';
 modal('角色音色 · '+ent.name,`<form id="voice-profile-form"><label>發聲方式<select name="sound_mode" id="voice-sound-mode"><option value="speech" ${!nonverbal?'selected':''}>人聲對白</option><option value="nonverbal" ${nonverbal?'selected':''}>非語言聲音 · beep／boop 等</option></select></label>${nonverbal?'<p class="note">純音效，不含人聲或可辨識字詞。以音高、長短與停頓表達；可儲存設定及匯入角色音效，沒有語言、口音或試音對白。</p>':''}<p class="muted">${esc(ent.description)}</p><section class="panel tight"><h3>角色預設音色</h3><p id="voice-current-description" class="prose">${esc(draft.description||'請展開下方選單，填寫你想要的音色。')}</p>${v.default_voice?`<details><summary>角色設計依據</summary><p>${esc(v.default_voice.rationale)}</p>${v.default_voice.evidence.map(quote=>`<blockquote>${esc(quote)}</blockquote>`).join('')}</details>`:''}<p class="muted">平時直接沿用這套音色；需要特別的聲音特色時，再展開下方選單調整。</p></section>${voicePlaybackPanel(v,p.postproduction.takes||[],true)}${voiceDescriptionFields(draft)}${p.postproduction.reference_modes?voiceReferenceFields(draft,p.postproduction.takes):''}<div ${nonverbal?'hidden':''}><label>試音對白<textarea name="sample_text" rows="3" maxlength="600" ${nonverbal?'disabled':'required'}>${esc(draft.sample_text)}</textarea></label></div><details ${nonverbal?'hidden':''}><summary>生成設定</summary><label>首個候選種子<input type="number" name="seed" min="0" max="2147483647" value="${v.seed}" required></label></details><p class="muted">${nonverbal?'儲存設定後，可匯入音效並試聽採用。音效不經過人聲生成。':'儲存設定後，可生成多個候選並試聽；後續候選會使用下一個種子，確切設定保存在音檔記錄。'} 修改設定會解除舊聲音的採用狀態，音檔仍然保留。</p><button type="submit" class="primary">儲存音色設定</button></form>`);
 const form=document.querySelector('#voice-profile-form'),custom=form.elements.custom_description;
 if(!draft.description)form.querySelector('#voice-custom-options').open=true;
 const validate=()=>{
  const f=new FormData(form),description=composeVoiceDescription(draft.description,f.getAll('voice_preset'),f.get('custom_description'));
  form.querySelector('#voice-current-description').textContent=description||'請保留一套音色描述。';
  custom.setCustomValidity(!description.trim()?'請選擇至少一個音色特徵，或填寫自訂描述。':[...description].length>1200?'音色描述合共不能超過 1200 字。':'');
  return description;
 };
 const language=form.querySelector('#voice-language'),sample=form.querySelector('[name="sample_text"]');
 if(language&&sample)language.addEventListener('change',()=>{sample.value=languageAudition(language.value,sample.value);});
 const mode=form.querySelector('#voice-sound-mode');
 if(mode)mode.onchange=()=>{
  const f=new FormData(form),oldMode=draft.sound_mode||'speech';
  modeDrafts.set(oldMode,{...v,description:validate(),language:f.get('language')||'',sample_text:f.get('sample_text')||'',seed:Number(f.get('seed')),sound_mode:oldMode,...voiceReferencePayload(form,oldMode)});
  const next=modeDrafts.get(mode.value)||{...v,default_voice:null,description:'',sound_mode:mode.value,language:voiceLanguages[0],sample_text:auditionTexts[voiceLanguages[0]],reference_take_id:null,reference_mode:'timbre',reference_text:''};
  openEditor(next);
 };
 installVoiceReferences(form,{v:draft,takes:p.postproduction.takes||[],base,cid,api,guarded});
 form.addEventListener('input',validate);
 form.addEventListener('change',validate);
 form.onsubmit=event=>{event.preventDefault();const description=validate();if(custom.validationMessage)form.querySelector('#voice-custom-options').open=true;if(!form.reportValidity())return;const f=new FormData(form);guarded(async()=>{await api(base+'/voices/'+cid,{description,language:f.get('language')||'',sample_text:f.get('sample_text')||'',seed:Number(f.get('seed')),version:v.version,...(f.get('sound_mode')?{sound_mode:f.get('sound_mode')}:{}),...voiceReferencePayload(form)},'PUT');close();await refresh(true);});};
 };
 if(roleVoiceProfile(v).description)openEditor(v);
 else void prepareRoleVoice({v,ent,base,cid,api,modal,openEditor});
 return;
 }

 });});
}
