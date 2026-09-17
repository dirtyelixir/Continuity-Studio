export function referenceDropMarkup() {
 return `<div class="reference-drop" data-reference-drop>
 <strong>拖放多張參考圖片到這裡</strong><span>PNG、JPG、WebP · 可多選，每張最多 40 MB</span>
 <label class="reference-file-picker">或點此選擇圖片<input type="file" multiple accept="image/png,image/jpeg,image/webp" aria-label="選擇參考圖片"></label>
 <div class="reference-drop-preview" hidden></div>
 <p class="reference-drop-status" role="status" aria-live="polite"></p></div>`;
}
export function validateReferenceFiles(files) {
 if (!files.length) throw Error('請選擇至少一張參考圖片。');
 for (const file of files) {
  if (!['image/png','image/jpeg','image/webp'].includes(file.type) && !(file.type === '' && /\.(png|jpe?g|webp)$/i.test(file.name))) throw Error(file.name+'：請選擇 PNG、JPG 或 WebP 圖片。');
  if (!file.size) throw Error(file.name+'：檔案是空白。');
  if (file.size > 40*1024*1024) throw Error(file.name+'：圖片超過 40 MB。');
 }
 return [...files];
}
export function bindReferenceDrop(root,{initialFile,onSelect}={}) {
 const modal=root.closest('.modal'),input=root.querySelector('input'),status=root.querySelector('[role="status"]'),preview=root.querySelector('.reference-drop-preview');
 let selected=[],urls=[],depth=0;
 const release=()=>{urls.forEach(u=>URL.revokeObjectURL(u));urls=[];};
 const render=()=>{
  release();preview.replaceChildren();preview.hidden=!selected.length;
  for(const file of selected){
   const item=document.createElement('div'),img=document.createElement('img'),name=document.createElement('span'),remove=document.createElement('button');
   const url=URL.createObjectURL(file);urls.push(url);img.src=url;img.alt=file.name+' 預覽';
   name.textContent=file.name;remove.type='button';remove.textContent='移除';remove.setAttribute('aria-label','移除 '+file.name);
   remove.onclick=()=>{selected=selected.filter(f=>f!==file);render();};
   item.append(img,name,remove);preview.append(item);
  }
  status.textContent=selected.length?`已選取 ${selected.length} 張；按「保存參考圖」後才會上傳。`:'尚未選取圖片。';
 };
 const choose=(files,notify=true)=>{
  let valid;try{valid=validateReferenceFiles(files);}catch(e){status.textContent=e.message+(selected.length?' 原本選取的圖片仍然保留。':'');return;}
  for(const f of valid)if(!selected.some(x=>x.name===f.name&&x.size===f.size&&x.lastModified===f.lastModified))selected.push(f);
  render();input.value='';if(notify)onSelect?.([...selected]);
 };
 input.onchange=()=>{if(input.files.length)choose([...input.files]);};
 const events={dragenter:e=>{e.preventDefault();depth++;root.classList.add('drag-over');},dragover:e=>{e.preventDefault();if(e.dataTransfer)e.dataTransfer.dropEffect='copy';},dragleave:e=>{e.preventDefault();if(--depth<=0){depth=0;root.classList.remove('drag-over');}},drop:e=>{e.preventDefault();e.stopPropagation();depth=0;root.classList.remove('drag-over');choose([...e.dataTransfer.files]);}};
 for(const [n,h] of Object.entries(events))modal.addEventListener(n,h);
 if(initialFile)choose(Array.isArray(initialFile)?initialFile:[initialFile],false);
 return {getFiles:()=>[...selected],getFile:()=>selected[0]||null,removeFile:file=>{selected=selected.filter(f=>f!==file);render();},dispose:()=>{release();for(const [n,h] of Object.entries(events))modal.removeEventListener(n,h);}};
}
