import {renderLoraAdvice} from './style-lora-advice.js';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const saved=new Map(), corrected=new Set(), pendingStyleSlot=new Set();let catalog=null;
const isAcceleration=x=>x?.purpose==='acceleration'||x?.turbo===true||/turbo/i.test(x?.name||'');
const storageKey=(p,row)=>`continuity-h3-settings-v2:${p.id}:${row.shot_id}:${row.mode}`;
export function suggestedSteps(name){const low=String(name||'').toLowerCase(),m=low.match(/(?:^|_)(4|8)step(?:_|\.)/);return m&&low.includes('turbo')?Number(m[1]):20;}
export function settingsValues(p,row){
 const k=storageKey(p,row),defaults=p.video_renders.defaults_by_mode?.[row.mode]||p.video_renders.defaults;
 if(!saved.has(k)){try{const raw=JSON.parse(globalThis.localStorage?.getItem(k)||'null');if(raw)saved.set(k,raw);}catch{}}
 const v={...defaults,...(saved.get(k)||{}),other_loras:saved.get(k)?.other_loras||defaults.other_loras||[]};
 v.steps=suggestedSteps(v.acceleration_lora);
 const clean=v.other_loras.filter(x=>!isAcceleration(x));
 if(clean.length!==v.other_loras.length){v.other_loras=clean;corrected.add(k);storeSettings(p,row,v);}
 return v;
}
export function storeSettings(p,row,v){saved.set(storageKey(p,row),v);try{globalThis.localStorage?.setItem(storageKey(p,row),JSON.stringify(v));}catch{}}
export function clearStyleLoraSlot(p,row){pendingStyleSlot.delete(storageKey(p,row));}
export function addStyleLoraSlot(p,row){if(settingsValues(p,row).other_loras.length<4)pendingStyleSlot.add(storageKey(p,row));}
export function removeStyleLoraSlot(p,row,index){
 const v=settingsValues(p,row);v.other_loras=v.other_loras.filter((_,i)=>i!==index);
 clearStyleLoraSlot(p,row);storeSettings(p,row,v);
}
export function setSettingsCatalog(value){catalog=value;}
export function settingsCatalogLoaded(){return !!catalog;}
export function canvasSize(v){if(!v.aspect_ratio||v.aspect_ratio==='custom')return [v.width,v.height];const [a,b]=v.aspect_ratio.split(':').map(Number),s=Math.sqrt(v.megapixels*1024*1024/(a*b));return [Math.max(256,Math.round(a*s/32)*32),Math.max(256,Math.round(b*s/32)*32)];}
function select(name,label,choices,value,disabled=false){return `<label>${label}<select data-render-setting="${name}" ${disabled?'disabled':''}>${choices.map(c=>`<option value="${esc(c.value)}" ${c.value===value?'selected':''} ${c.disabled?'disabled':''}>${esc(c.label)}</option>`).join('')}</select></label>`;}
const opt=(value,label=value)=>({value,label});
function models(p,row,v){
 const family=row.mode==='REF2VA'?'REF2VA':'FL2VA';
 const preferred=(p.video_renders.defaults_by_mode?.[row.mode]||p.video_renders.defaults).model;
 const rows=(catalog?.models||[]).filter(x=>x.family===family||(row.mode==='REF2VA'&&x.family==='FL2VA'));
 if(v.model&&!rows.some(x=>x.name===v.model))rows.unshift({name:v.model,missing:!!catalog});
 return rows.map(x=>opt(x.name,x.name+(x.name===preferred?'（預設）':'')+(x.missing?'（目前找不到）':'')));
}
function loras(v,row,acceleration){
 const family=catalog?.models?.find(x=>x.name===v.model)?.family||(/minimax_h3_fl2va_/i.test(v.model||'')?'FL2VA':/minimax_h3_ref2va_/i.test(v.model||'')?'REF2VA':row.mode==='REF2VA'?'REF2VA':'FL2VA');
 const rows=(catalog?.loras||[]).filter(x=>(!x.family||x.family===family)&&(acceleration?x.turbo:!isAcceleration(x)));
 const selected=acceleration?[v.acceleration_lora]:v.other_loras.map(x=>x.name);
 for(const name of selected)if(name&&(acceleration||!isAcceleration({name}))&&!rows.some(x=>x.name===name))rows.push({name,missing:!!catalog});
 return [opt('','沒有'),...rows.map(x=>opt(x.name,(acceleration?(x.label&&x.label!==x.name?x.label+' — ':'')+x.name:x.label||x.name)+(x.missing?'（目前找不到）':'')))];
}
export function renderSettings(p,row,v,working,open){
 const choices=loras(v,row,true),other=loras(v,row,false),wh=canvasSize(v),scale=v.scale??1;
 const target=wh.map(x=>v.second_pass?Math.round(x*scale/32)*32:Math.round(x*scale));
 const number=(name,label,min,max,step,value=v[name])=>`<label>${label}<input type="number" data-render-setting="${name}" min="${min}" max="${max}" step="${step}" value="${esc(value??'')}" ${working||name==='steps'?'disabled':''}></label>`;
 const available=catalog?.attention||[];
 const attention=[opt('kitchen','Comfy Kitchen Attention'),opt('default','ComfyUI 預設 attention'),opt('sage','Sage Attention'),opt('memory_sage','H3 Memory Efficient Sage Attention')].map(x=>({...x,label:x.label+(catalog&&!available.includes(x.value)?'（目前不可用）':'')}));
 return `<details data-render-settings ${open?'open':''}><summary>影片設定 · ${wh.join('×')} · ${v.steps??suggestedSteps(v.acceleration_lora)} 步 · ${v.second_pass?'開啟二採':'不開二採'}</summary>
 <p class="muted">未展開也會使用以下預設；修改會記住在此瀏覽器的本鏡設定。</p>
 ${select('model','模型選擇',models(p,row,v),v.model,working)}
 <p class="muted">列出本機已安裝、符合本鏡 ${row.mode==='REF2VA'?'Ref2VA':'I2VA／FL2VA'} 模式的 H3 底模。一採與二採共用所選模型；一採步數固定跟隨加速 LoRA。</p>
 <div class="form-grid">
 <div>${select('acceleration_lora','加速 LoRA',choices,v.acceleration_lora||'',working)}${loraDescription(v.acceleration_lora)}</div>
 ${number('steps','一採步數（跟隨加速 LoRA，固定）',1,100,1)}
 </div>
 ${corrected.has(storageKey(p,row))?'<p class="note">先前誤放在 Style LoRA 欄的加速權重已移除；上方加速 LoRA 設定保留。</p>':''}
 ${renderLoraAdvice(p,row,v,working)}
 ${renderOtherLoras(p,row,v,other,working)}
 <div class="form-grid">
 ${select('audio_mode','聲音輸出',[opt('generate','聲畫一起生成'),opt('mute','靜音影片（無音軌）')],v.audio_mode||'generate',working)}
 ${select('attention','Attention 運算方式',attention,v.attention||'kitchen',working)}
 ${select('aspect_ratio','畫面比例',['16:9','9:16','1:1','4:3','3:4','3:2','2:3','21:9','custom'].map(x=>opt(x,x==='custom'?'自訂尺寸':x)),v.aspect_ratio||'custom',working)}
 ${select('megapixels','一採解析度',[0.2,0.3,0.4,0.5,0.6,0.8,1,1.5,2].map(x=>opt(String(x),x+' MP')),String(v.megapixels??0.4),working||v.aspect_ratio==='custom')}
 ${v.aspect_ratio==='custom'?number('width','寬度',256,4096,32)+number('height','高度',256,4096,32):''}
 ${select('scale','放大倍數',[opt('1','不放大（1×）'),opt('1.5','1.5×'),opt('2','2×'),opt('4','4×')],String(scale),working)}
 ${select('second_pass','二採',[opt('false','不開二採'),opt('true','開啟二採')],String(!!v.second_pass),working)}
 ${number('seed','Seed（留空使用新種子）',0,4294967295,1)}
 </div>
 <p class="muted">一採步數固定跟隨加速 LoRA：4-step 為 4 步、8-step 為 8 步，未使用加速 LoRA 時為 20 步。固定 24 fps。輸出約 ${target.join('×')}；H3 一採／二採尺寸對齊 32，影格對齊後時長可能略長。</p>
 ${row.mode==='REF2VA'?'<p class="note">Ref2V 可選 Ref2VA 或 FL2VA 底模，仍沿用主體參考圖流程。LoRA 清單依所選底模篩選；切換底模後請核對已選 LoRA。預設仍為 Ref2VA、不掛加速 LoRA、20 步。</p>':''}

 ${v.second_pass?`<h3>二採設定</h3><div class="form-grid">${number('refine_steps','二採步數',1,100,1)}${number('refine_denoise','二採去噪強度',0.01,1,0.01)}${scale!==1?select('upscale_model','放大模型',[opt('','Lanczos 插值'),...(catalog?.upscale_models||[]).map(x=>opt(x))],v.upscale_model||'',working):''}</div><p class="muted">使用底模及其他 LoRA，不沿用一採 Turbo。二採會重新處理首尾幀；固定 euler／beta，一次精修。${scale!==1?'先放大再二採。':'保持一採尺寸。'}</p>`:scale!==1?'<p class="muted">未開二採時，以 Lanczos 放大成片，不增加採樣。</p>':''}
 ${v.audio_mode==='mute'?'<p class="muted">靜音會略過聲音解碼並輸出無音軌影片；H3 底層仍為聲畫聯合採樣。</p>':''}
 <button type="button" class="small" data-render-action="options">${catalog?'重新讀取本機選單':'讀取本機模型／LoRA／Attention 選單'}</button>
 </details>`;
}
export function editSettings(p,row,target){
 const v=settingsValues(p,row),name=target.dataset.renderSetting;
 if(name==='steps')return false;
 if(name){
  if(name==='second_pass')v[name]=target.value==='true';
  else if(['model','acceleration_lora','attention','audio_mode','aspect_ratio','upscale_model'].includes(name))v[name]=target.value;
  else v[name]=target.value===''?null:Number(target.value);
  if(name==='acceleration_lora')v.steps=suggestedSteps(v[name]);
  if(name==='second_pass'&&!v.second_pass||name==='scale'&&v.scale===1)v.upscale_model='';
 }else if(target.dataset.renderLoraIndex!==undefined){
  clearStyleLoraSlot(p,row);
  const i=Number(target.dataset.renderLoraIndex),list=v.other_loras.map(x=>({...x}));
  const chosen=catalog?.loras?.find(x=>x.name===target.value);
  list[i]={name:target.value,strength:list[i]?.name===target.value?list[i].strength:(chosen?.default_strength??1)};v.other_loras=list.filter(x=>x?.name);
 }else if(target.dataset.renderLoraStrength!==undefined){
  const i=Number(target.dataset.renderLoraStrength);v.other_loras=v.other_loras.map((x,n)=>n===i?{...x,strength:Number(target.value)}:x);
 }else return false;
 [v.width,v.height]=canvasSize(v);storeSettings(p,row,v);return true;
}

function renderOtherLoras(p,row,v,other,working){
 const pending=pendingStyleSlot.has(storageKey(p,row)),count=Math.min(4,v.other_loras.length+(pending?1:0));
 const add=`<div class="actions"><button type="button" class="small" data-render-action="add-style-lora" data-id="${esc(row.shot_id)}" ${working||pending||count>=4?'disabled':''}>加入 Style LoRA</button>${pending?'<span class="muted">請先選擇下方 LoRA，或移除此欄。</span>':''}</div>`;
 if(!count)return add;
 return add+ `<section class="h3-other-loras"><h3>Style LoRA（風格／運鏡）</h3><p class="muted">只顯示已加入的 LoRA，可各自調整強度或移除。</p>
 ${Array.from({length:count},(_,i)=>{
  const x=v.other_loras[i]||{name:'',strength:1},meta=catalog?.loras?.find(m=>m.name===x.name);
  const range=meta?.recommended_strength;
  const advice=range?`建議 ${range[0]===range[1]?range[0].toFixed(1):range.map(n=>n.toFixed(1)).join('–')} · 預設 ${(meta.default_strength??1).toFixed(1)}`:'暫用 1.0；作者建議尚未確認。';
  const source=meta?.source_url?.startsWith('https://huggingface.co/')?`<a href="${esc(meta.source_url)}" target="_blank" rel="noopener noreferrer">查看作者說明 ↗</a>`:'';
  const purpose=meta?.description||(catalog?'用途尚未確認。':'正在讀取本機說明…');
  return `<div class="h3-lora-card"><div class="actions"><button type="button" class="small" data-render-action="remove-style-lora" data-id="${esc(row.shot_id)}" data-lora-index="${i}" aria-label="移除 Style LoRA ${i+1}" ${working?'disabled':''}>移除</button></div><div class="h3-lora-controls"><label>Style LoRA ${i+1}<select data-render-lora-index="${i}" ${working?'disabled':''}>${other.map(c=>`<option value="${esc(c.value)}" ${c.value===x.name?'selected':''}>${esc(c.label)}</option>`).join('')}</select></label><div><label>強度<input type="number" aria-label="Style LoRA ${i+1} 強度" data-render-lora-strength="${i}" min="-2" max="2" step="0.05" value="${esc(x.strength)}" ${working||!x.name?'disabled':''}></label>${x.name?`<p class="muted h3-lora-strength-hint">${advice}</p>`:''}</div></div>
  ${x.name?`<p class="lora-description"><strong>用途</strong> ${esc(purpose)}</p>
  ${meta?.trigger?`<div class="h3-lora-trigger"><strong>自動加入觸發詞</strong><code>${esc(meta.trigger)}</code><p>生成時自動加到提示詞開頭；取消此 LoRA 就不加入。第 3 步的原提示詞保留。</p></div>`:catalog?'<p class="muted">觸發詞尚未確認，請查看作者說明。</p>':''}
  <details class="h3-lora-details"><summary>檔案與來源</summary><p class="overflow">${esc(x.name)}</p>${source}</details>`:''}</div>`;
 }).join('')}
 <p class="muted">所選 LoRA 也會用於二採。${catalog?'':'選單與說明來自本機，尚未出現時可用下方按鈕重新讀取。'}</p></section>`;
}

function loraDescription(name){
 if(!name)return '';
 const info=catalog?.loras?.find(x=>x.name===name);
 return `<p class="muted lora-description">${esc(info?.description||(catalog?'尚未有已核對的用途說明；請參閱作者文件。':'正在讀取用途說明…'))}</p>`;
}
