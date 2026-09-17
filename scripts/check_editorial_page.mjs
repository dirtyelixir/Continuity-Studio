import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync('static/editorial.js','utf8');
const shot={id:'shot',scene_id:'scene',title:'測試鏡頭',duration:4,beats:[],start_state:[],end_state:[],action:'站立',transition_note:''};
const plan={scenes:[{id:'scene',title:'測試場景'}],shots:[shot],edit_plan:[{id:'edit',shot_id:'shot',planned_edit_in:0,planned_edit_out:4}]};
const trial={id:'trial',scene_id:'scene',title:'測試場景 · 剪接方案',version:1,status:'adopted',production_revision:2,base_revision:1,stale:false,plan,
 baseline:{...plan,edit_plan:[{...plan.edit_plan[0],planned_edit_out:2}]},baseline_timeline:{duration:2,audio:[]},audio_cues:[],notes:{},images:{},artifacts:{prompts:[]},provenance:{limitations:[]}};
const listing={project_id:'project',title:'測試作品',production_revision:2,scenes:plan.scenes,trials:[trial]};
async function boot(payload,{code=source,ok=true,detail='資料讀取失敗'}={}){
 const nodes=new Map(),calls=[];
 function element(id){
  return {dataset:{},style:{},hidden:false,disabled:false,textContent:'',value:'',classList:{toggle(){}},select(){},
   get innerHTML(){return this.html||''},set innerHTML(html){this.html=html;if(id==='app'){
    for(const key of nodes.keys())if(!['app','status','return-video','return-progress'].includes(key))nodes.delete(key);
    for(const m of html.matchAll(/\bid="([^"]+)"/g))nodes.set(m[1],element(m[1]));
   }}};
 }
 for(const id of ['app','status','return-video','return-progress'])nodes.set(id,element(id));
 const context={document:{querySelector:s=>nodes.get(s.slice(1))||null,querySelectorAll:()=>[]},location:{search:'?project=project'},URLSearchParams,
 window:{addEventListener(){}},performance:{now:()=>0},requestAnimationFrame:()=>1,cancelAnimationFrame(){},setTimeout:()=>1,clearTimeout(){},
 fetch:async(path,options={})=>{calls.push({path,options});return {ok,json:async()=>ok?structuredClone(options.method==='POST'?trial:payload):{detail}}}};
 vm.createContext(context);
 await vm.runInContext('(async()=>{'+code+'})()',context);
 return {nodes,calls,html:()=>nodes.get('app').innerHTML};
}
const live=await boot(listing);
assert.match(live.html(),/正式剪接 · 1 段 · 4.0 秒/);
for(const id of ['scene-choice','open-scene','play','scrub','compare','screen'])assert(live.nodes.has(id),id);
assert.match(live.nodes.get('screen').innerHTML,/測試鏡頭/);
assert.equal(live.nodes.get('return-video').href,'/?project=project#video');
live.nodes.get('compare').onclick();
assert.match(live.html(),/原有方案 · 1 段 · 2.0 秒/);
assert.match(live.html(),/返回目前剪接/);
live.nodes.get('compare').onclick();
assert.match(live.html(),/正式剪接 · 1 段 · 4.0 秒/);
live.nodes.get('scene-choice').value='scene';
await live.nodes.get('open-scene').onclick();
assert.equal(live.calls.at(-1).path,'/api/projects/project/editorial/open');
assert.deepEqual(JSON.parse(live.calls.at(-1).options.body),{scene_id:'scene',production_revision:2});
assert.match(live.html(),/正式剪接 · 1 段 · 4.0 秒/);
const empty=await boot({...listing,trials:[]});
assert.match(empty.html(),/選擇場景/);assert(empty.nodes.has('open-scene'));assert(!empty.nodes.has('play'));
const legacy={...listing};delete legacy.scenes;
const missing=await boot(legacy);
assert.match(missing.html(),/已保存的方案仍然保留/);
assert.doesNotMatch(missing.html(),/undefined|reading 'map'/);
// Prove this exact old/new API mismatch triggered the original crash without the guard.
const oldCode=source.replace(/if\(!Array\.isArray\(projectInfo\.scenes\)\)throw Error\('[^']*'\);/,'');
assert.notEqual(oldCode,source);
assert.match((await boot(legacy,{code:oldCode})).html(),/Cannot read properties of undefined.*map/);
const failure=await boot(null,{ok:false,detail:'資料庫 <暫停>'});
assert.match(failure.html(),/資料庫 &lt;暫停&gt;/);
console.log('Editorial page: actual bootstrap/render, preview controls, comparison, scene-open request, empty trials, legacy API crash reproduction/guard and escaped API errors passed.');

const queued=structuredClone(listing);queued.trials[0].directing_status='unreviewed';queued.trials[0].directing_review={state:'queued'};assert.match((await boot(queued)).html(),/導演內容審查：已自動排隊/);
