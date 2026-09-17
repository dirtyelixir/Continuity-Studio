import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
// Exercise the actual page entry point with an unfinished Scene elsewhere.
const app=readFileSync('static/app.js','utf8'),scheduled=[];
const scenes=[{scene_id:'ready',preparation:{required:false}},{scene_id:'unfinished',preparation:{required:true,status:'needed'}}];
const context={page:'video',localStorage:{getItem:()=>null},imageTransfer:()=>'',renderVideoWorkflow:(p,s,i,d,renderRef)=>renderRef(p.video_workflow.shots[0]),project:{id:'p',production:{},video_workflow:{shots:[{shot_id:'shot',scene_id:'ready',mode:'REF2VA'}]},delivery:{guidance_review:{status:'pending'},scenes}},handoff:{selection:()=>({scene:scenes[0]})},queueMicrotask:f=>scheduled.push(f),ensureGuidance(){},ensurePreparation(){},handoffTransfers:{},providerLabel:()=>'',promptDrafts:{},renderHandoff:()=>'',missingPlan:()=>'',head:()=>''};
vm.createContext(context);vm.runInContext(app.slice(app.indexOf('function videoRow(){'),app.indexOf('async function ensurePreparation(){'))+'\nvideoPage();',context);
assert.deepEqual(scheduled,[context.ensureGuidance]);
const source=readFileSync('static/director-page.js','utf8');
const {renderHandoff,createHandoffState}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const shot={shot_id:'shot',title:'Shot',number:1,duration:10,shot_prompt:'summary: x',references:[],local_references:[],missing_references:[],issues:[],guidance:{continuityFromPrev:null,notes:''}};
const p={id:'p',delivery:{configuration:{context_frames:22},scenes:[{scene_id:'scene',title:'Scene',global_prompt:'subject_definitions:',references:[],missing_references:[],chapters:[shot]}]}};
const state=createHandoffState();state.select('p','scene','shot');
for(const [status,message] of Object.entries({pending:'尚未啟動',queued:'已排隊',running:'正在按分鏡分析',waiting:'上一個版本',failed:'未完成',awaiting_input:'人工判斷'})){
 p.delivery.guidance_review={status,job_id:status==='pending'?null:'job',error:status==='failed'?'<failure>':''};
 const html=renderHandoff(p,state);assert(html.includes(message));
 if(status!=='running')assert(!html.includes('正在按分鏡分析接續方式'));
 if(status==='pending')assert(html.includes('開始分析接續'));
 if(status==='failed')assert(html.includes('&lt;failure&gt;')&&html.includes('重新分析接續'));
 if(status!=='pending')assert(html.includes('查看分析工作'));
}
console.log('Guidance: auto-start despite unfinished Scenes; pending/queue/running/stale-active/manual/failure UI and retry controls passed.');
