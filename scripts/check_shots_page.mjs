import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {renderStoryboard} from '../static/storyboard-board.js';
const source=readFileSync('static/app.js','utf8');
const {imageLoraMarkup}=await import('../static/local-images.js');
const block=source.slice(source.indexOf('function shots(){'),source.indexOf('function review(){'));
const evidence=source.slice(source.indexOf('function imageReferenceEvidence('),source.indexOf('function assetCard('));
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const frame={id:'start',moment:'start',description:'A still frame.'};
const shot={id:'shot',scene_id:'scene',title:'First shot',duration:4,keyframes:[frame],entity_ids:['person'],framing:'Medium',angle:'Eye level',camera:'Locked',blocking:'At left',expression:'Neutral',action:'Standing',beats:[],dialogue:[],start_state:[],end_state:[],transition_note:''};
let asset=null,reference=null;
const ctx={project:{id:'p',production:{shots:[shot],scenes:[{id:'scene',title:'Scene',location_id:'room'}],canon:[{id:'person',kind:'character'},{id:'room',kind:'location'}]},jobs:[],input_references:[]},selectedShot:null,selectedFrame:null,
 renderStoryboard,latest:()=>asset,approved:()=>reference,imageStatus:()=>null,esc,imageLoraMarkup,
 head:(title,description,actions)=>`<h1>${title}</h1>${description}${actions}`,button:(title,action,attrs='')=>`<button data-action="${action}" ${attrs}>${title}</button>`,badge:s=>`<span>${s}</span>`,imageURL:id=>`/api/assets/${id}/image`,imageProgressMarkup:()=>'',imageTransfer:()=>'',shotIntentMarkup:()=>'',targetName:id=>id,imagePromptNote:()=>'',providerName:id=>id,missingPlan:()=>'<p>Missing plan</p>'};
vm.createContext(ctx);vm.runInContext(block+evidence,ctx);
// Execute the actual rendering function with no accidental global `input`.
for(const status of [null,'pending','approved']){
 asset=status?{id:'asset',status,prompt:'Saved brief',provider:'comfy_local',reference_ids:[]}:null;
 reference=status==='approved'?{id:'reference'}:null;
 const html=vm.runInContext('shots()',ctx);
 assert(html.includes('First shot'));
 assert(html.includes('data-action="select-shot"'));
 assert(html.includes('data-action="generate"'));
 assert(html.includes('data-target="person"'));
 assert.equal(html.includes('請先批准'),!reference);
}
// LoRA provenance still renders where its job input is in scope.
ctx.project.jobs=[{id:'job',input:{local_image_plan:{lora_selection:{summary:'選用寫實'},creative_loras:[{name:'sample.safetensors',strength:1,reason:'材質',trigger:''}]}}}];
ctx.asset={id:'asset',job_id:'job',reference_ids:[]};
assert(vm.runInContext('imageReferenceEvidence(asset)',ctx).includes('sample.safetensors'));
ctx.project.production=null;
assert.equal(vm.runInContext('shots()',ctx),'<p>Missing plan</p>');
console.log('Shots render: empty/pending/approved frame, reference actions, missing plan and LoRA provenance passed.');
