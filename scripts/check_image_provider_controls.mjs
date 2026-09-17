import assert from 'node:assert/strict';
import {imageControls,bindImageControls,imageOptions} from '../static/local-images.js';
const esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const providers=[{id:'astra',kind:'codex',name:'Astra',capabilities:['*']},{id:'local_qwen',kind:'http',name:'Qwen3.8',capabilities:['*']},{id:'deepseek',kind:'deepseek',name:'DeepSeek',capabilities:['*']},{id:'comfy_local',kind:'comfy',name:'Klein / Krea2',capabilities:['image']},{id:'image-api',kind:'http',name:'Image <API>',capabilities:['image']},{id:'text-api',kind:'http',name:'Text',capabilities:['narrative']}];
const settings={providers,routing:{image:'astra'},profile:{image_provider:'astra',default_provider:'local_qwen'}};
const html=imageControls(settings,null,esc);
assert(!html.includes('value="local_qwen"'));assert(!html.includes('value="deepseek"'));assert(!html.includes('value="text-api"'));
assert(html.includes('value="astra" selected'));assert(html.includes('value="comfy_local"'));assert(html.includes('Image &lt;API>'));assert(html.includes('name="image_provider" required'));
assert(imageControls(settings,{imageProvider:'comfy_local'},esc).includes('value="comfy_local" selected'));
for(const invalid of ['local_qwen','missing']){
 const draft={imageProvider:invalid,feedback:'Preserve me',selected:['ref'],imageRegion:'10,20,30,40'},before=JSON.stringify(draft);
 const markup=imageControls(settings,draft,esc);assert(markup.includes('value="" selected disabled'));assert(!markup.includes('value="astra" selected'),'invalid explicit draft never silently falls back');assert.equal(JSON.stringify(draft),before);
}
const invalidDefault={...settings,routing:{image:'local_qwen'}};assert(imageControls(invalidDefault,null,esc).includes('value="" selected disabled'));
let validity='';const fields={image_provider:{value:'local_qwen',setCustomValidity:x=>validity=x},image_operation:{value:'auto'}},nodes={};
const form={elements:fields,querySelector:s=>nodes[s]??={}};bindImageControls(form,settings);assert(validity);assert(fields.image_operation.disabled);
fields.image_provider.value='comfy_local';fields.image_provider.onchange();assert.equal(validity,'');assert(!nodes['[data-local-options]'].hidden);assert(!fields.image_operation.disabled);
fields.image_provider.value='astra';fields.image_provider.onchange();assert.equal(validity,'');assert(nodes['[data-local-options]'].hidden);
assert.deepEqual(imageOptions(new Map([['image_provider','comfy_local'],['image_operation','auto']])),{image_provider:'comfy_local',image_operation:'auto',image_region:null,image_padding:null});
console.log('Image providers: wildcard Qwen/DeepSeek excluded, valid renderer choices preserved, explicit selection, invalid drafts/defaults require choice, no draft mutation, local controls and request identity passed.');
