// A choice stays local until the identity editor's explicit save/adopt action.
export function bindIdentityAssetPicker({form,entity,assets,esc,displayLabel}){
 if(entity.kind==='voice')return {selection:()=>null};
 const choices=assets.filter(a=>a.target_id===entity.id&&a.status!=='rejected');
 form.insertAdjacentHTML('afterbegin',`<section class="identity-asset-picker"><h3>${entity.kind==='character'?'角色圖片':'身份參考圖片'}</h3><p class="muted">可直接選用現有版本或上傳圖片；儲存時採用為目前身份參考。</p><label>圖片來源<select data-identity-asset-mode><option value="keep">保留目前圖片</option>${choices.length?'<option value="existing">選用現有圖片</option>':''}<option value="upload">上傳圖片並採用</option></select></label><div data-existing-identity hidden><label>現有版本<select data-identity-asset-id>${choices.map((a,i)=>`<option value="${esc(a.id)}">版本 ${choices.length-i} · ${esc(displayLabel(a.status))}</option>`).join('')}</select></label><img class="identity-asset-preview" data-existing-preview alt="${esc(entity.name)} · 選用的圖片"></div><div data-upload-identity hidden><label>上傳圖片<input type="file" data-identity-asset-file accept="image/png,image/jpeg,image/webp"></label><img class="identity-asset-preview" data-upload-preview hidden alt="上傳圖片預覽"></div><p data-identity-adoption-note hidden>按「儲存設定並採用圖片」會將所選圖片設為身份參考，保留原有版本及審查紀錄；相關鏡頭可能需要更新。</p></section>`);
 const root=form.querySelector('.identity-asset-picker'),mode=root.querySelector('[data-identity-asset-mode]'),select=root.querySelector('[data-identity-asset-id]'),file=root.querySelector('[data-identity-asset-file]'),submit=form.querySelector('[type=submit]'),oldLabel=submit.textContent;
 let url=null;
 const update=()=>{
  const visual=form.elements.kind?.value!=='voice';root.hidden=!visual;
  root.querySelector('[data-existing-identity]').hidden=mode.value!=='existing';root.querySelector('[data-upload-identity]').hidden=mode.value!=='upload';
  root.querySelector('[data-identity-adoption-note]').hidden=mode.value==='keep';
  if(select?.value)root.querySelector('[data-existing-preview]').src='/api/assets/'+encodeURIComponent(select.value)+'/image';
  submit.textContent=visual&&mode.value!=='keep'?'儲存設定並採用圖片':oldLabel;
 };
 mode.onchange=update;if(select)select.onchange=update;form.elements.kind?.addEventListener('change',update);
 file.onchange=()=>{if(url)URL.revokeObjectURL(url);url=file.files[0]?URL.createObjectURL(file.files[0]):null;const preview=root.querySelector('[data-upload-preview]');preview.hidden=!url;if(url)preview.src=url;};
 const observer=new MutationObserver(()=>{if(!form.isConnected){if(url)URL.revokeObjectURL(url);observer.disconnect();}});observer.observe(document.body,{childList:true,subtree:true});
 update();
 return {selection:()=>{
  if(form.elements.kind?.value==='voice'||mode.value==='keep')return null;
  if(mode.value==='existing'){if(!select.value)throw Error('請選用一張現有圖片。');return {asset_id:select.value};}
  const chosen=file.files[0];if(!chosen)throw Error('請先選擇要上傳的圖片。');if(chosen.size>40000000)throw Error('圖片不可超過 40MB。');return {file:chosen};
 }};
}
