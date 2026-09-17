import {supportsProvider} from './provider-profile.js';
export const localOperations={auto:'自動選擇',new:'全新圖片',reference:'參考圖生成／多圖合成',sheet:'角色四視圖',portrait:'人物写真',face_swap:'換臉（來源圖＋身份參考）',edit:'整張修改',inpaint:'指定範圍修改',outpaint:'擴展畫面'};
export function imageControls(settings,draft,esc){
 const inherited=settings.routing.image||settings.profile.image_provider||settings.profile.default_provider;
 const providers=settings.providers.filter(p=>supportsProvider(p,'image'));
 const requested=draft?.imageProvider||inherited,provider=providers.some(p=>p.id===requested)?requested:'',op=draft?.imageOperation||'auto';
 return `<div class="panel"><label>今次圖片生成服務<select name="image_provider" required>${!provider?'<option value="" selected disabled>請選擇可用的圖片生成服務</option>':''}${providers.map(p=>`<option value="${esc(p.id)}" ${p.id===provider?'selected':''}>${p.id===inherited?'沿用設定：':''}${esc(p.kind==='manual'?'人工匯入圖片（不自動生成）':p.name)}</option>`).join('')}</select></label><p class="muted">Qwen3.8／DeepSeek 負責創作與圖片審查；實際出圖服務在這裡獨立選擇。</p>${!provider?'<p class="notice">之前選擇的服務不能生成圖片。請重新選擇，製作要求與參考圖仍保留。</p>':''}<div data-local-options><label>本機工作方式<select name="image_operation">${Object.entries(localOperations).map(([id,name])=>`<option value="${id}" ${id===op?'selected':''}>${name}</option>`).join('')}</select></label><p class="muted">自動：角色四視圖／多圖參考 → Klein；全新圖／單雙圖修改 → Krea2。完整保留所有參考，超出支援範圍會明確停止。整理畫面時會自動選用相容且用途已核對的 LoRA；沒有合適項目就不加，選用原因與權重會保存在工作記錄。</p><div data-region><label>修改範圍 x,y,寬,高（百分比）<input name="image_region" value="${esc(draft?.imageRegion||'20,20,40,40')}" placeholder="20,20,40,40"></label><small>左上角為 0,0。框外保留縮放後來源圖像素；框內仍需審閱，Turbo 移除物件效果有限。</small></div><div data-padding><label>擴圖 左,上,右,下（像素）<input name="image_padding" value="${esc(draft?.imagePadding||'128,0,128,0')}" placeholder="128,0,128,0"></label><small>每邊 0–512，8 的倍數。使用來源圖約 1MP 的尺寸，再加上邊距。</small></div><small>修改／換臉需從已有版本「修訂」開始；角色四視圖：正面全身 → 側面全身 → 背面全身 → 正面臉部特寫。写真為單張候選；四視圖分四個視角逐張生成再拼接，耗時較長。生成結果不會自動批准。</small></div></div>`;
}
export function bindImageControls(form,settings){
 const update=()=>{const p=form.elements.image_provider.value;const selected=settings.providers.find(x=>x.id===p),valid=!!selected&&supportsProvider(selected,'image');form.elements.image_provider.setCustomValidity(valid?'':'請選擇可用的圖片生成服務。');const local=valid&&p==='comfy_local';form.querySelector('[data-local-options]').hidden=!local;form.elements.image_operation.disabled=!local;form.querySelector('[data-region]').hidden=form.elements.image_operation.value!=='inpaint';form.querySelector('[data-padding]').hidden=form.elements.image_operation.value!=='outpaint';};
 form.elements.image_provider.onchange=update;form.elements.image_operation.onchange=update;update();
}
export function imageOptions(f){
 const op=f.get('image_operation')||'auto';
 const parse=name=>{const v=String(f.get(name)||'').split(',').map(x=>Number(x.trim()));if(v.length!==4||v.some(x=>!Number.isInteger(x)))throw Error('請以逗號分開填寫四個整數。');return v;};
 return {image_provider:f.get('image_provider')||'',image_operation:op,image_region:op==='inpaint'?parse('image_region'):null,image_padding:op==='outpaint'?parse('image_padding'):null};
}
export function localImageSettings(){return `<section class="panel"><h2>本機圖片工作流 · Klein / Krea2</h2><p>已收錄人物資產合集及 Krea2 編輯整合流原檔；Studio 使用獨立適配版本，每個目標產生一張候選圖。創作與圖片理解服務另選，DeepSeek 本身不會生成圖片。</p><p>角色四視圖、写真、換臉、多圖參考；文生圖、單／雙圖編輯、指定範圍修改及擴圖。新工作的生成表單可單次選擇本機服務，或在下方設定為圖片生成服務。</p><button data-action="check-local-images">檢查本機節點與模型</button><p id="local-image-status" role="status">尚未檢查連線。檢查不會生成圖片。</p></section>`;}

export function imageLoraMarkup(plan,esc){
 if(!plan?.lora_selection)return '';
 const rows=plan.creative_loras||[];
 return `<details open class="panel"><summary>自動 LoRA · ${rows.length?`已選 ${rows.length} 個`:'不需額外 LoRA'}</summary><p>${esc(plan.lora_selection.summary)}</p>${rows.map(r=>`<p><strong>${esc(r.name)}</strong> · ${esc(r.strength)}<br>${esc(r.reason)}${r.trigger?`<br>已自動加入觸發詞：${esc(r.trigger)}`:''}</p>`).join('')}<small>功能 LoRA 仍依工作方式保留；本次選配、實際節點提示詞及底模已保存。</small></details>`;
}
