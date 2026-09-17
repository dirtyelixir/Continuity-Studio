import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const load=async path=>import('data:text/javascript;base64,'+Buffer.from(readFileSync(path,'utf8')).toString('base64'));
const {directingRevisionData:data,directingRevisionForm:markup,openCurrentDirectingRevision:open}=await load('static/directing-revision.js');
const {directingPanel}=await load('static/directing-plan.js');
const esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const review={verdict:'revise',summary:'Summary',issues:[{shot_ids:['s1'],reason:'Small switch',recommendation:'Show switch closer <script>'},{shot_ids:['s2'],reason:'Different scene',recommendation:'Hold listener reaction'}],coverage:[{scene_id:'a',shot_ids:['s1'],beat_id:'B1',verdict:'revise',reason:'Cause unclear',recommendation:'Keep causal order'},{scene_id:'b',shot_ids:['s2'],beat_id:'B1',verdict:'revise',reason:'Listener unreadable',recommendation:'Use closer framing'}]};
const project={id:'p',revision:11,source_kind:'idea',production:{canon:[],scenes:[{id:'a',title:'A',director_plan:{beats:[],reveal_order:[]}},{id:'b',title:'B',director_plan:{beats:[],reveal_order:[]}}],shots:[{id:'s1',title:'Switch',scene_id:'a'},{id:'s2',title:'Listener',scene_id:'b'}]},directing:{approval_source_hash:'hash',current_review:{state:'succeeded',result:review},scenes:['a','b'].map(scene_id=>({scene_id,status:'revise',review:{job_id:'r',review}}))}};
let result=data(project);assert.equal(result.items.length,4,'Deduplicate full review shared across scenes');
assert(result.notes.includes('Show switch closer'));assert(directingPanel(project,esc).includes('data-action="revise-current-directing"'));
let html=markup(project,result,'DeepSeek',esc);assert(html.includes('建議做法'));assert(!html.includes('<script>'));assert(html.includes('按以上建議開始修訂'));assert(!html.includes(' required'));
const serial=structuredClone(project);serial.source_kind='outline';serial.production.chapters=[{id:'c1',title:'One',scene_ids:['a']},{id:'c2',title:'Two',scene_ids:['b']}];serial.story_chapters=[{id:'c1',source_kind:'idea',version:1},{id:'c2',source_kind:'screenplay',version:2}];
const scoped=data(serial,'c1');assert.equal(scoped.items.length,2);assert(!scoped.notes.includes('Listener'));assert.equal(scoped.capability,'narrative');assert.equal(data(serial,'c2').capability,'storyboard');
const missing=structuredClone(project);missing.directing.scenes.forEach(s=>s.review=null);missing.directing.current_review={state:'running',result:review};assert.equal(data(missing).items.length,0,'Never reuse an unrelated or stale review result');assert(markup(missing,data(missing),'P',esc).includes('審查仍在進行'));assert(markup(missing,data(missing),'P',esc).includes(' required'));
async function harness(p){
 let current=p,server=structuredClone(p),form,html='',pending,closed=0;const calls=[],progress=[];
 const deps={pid:p.id,getProject:()=>current,api:async(path,body)=>{calls.push({path,body});return body?{job:{id:'new-job'}}:structuredClone(server)},modal:(title,value)=>{html=value;form={elements:{feedback:{value:''},...(p.source_kind==='outline'?{chapter_id:{}}:{})}}},select:()=>form,close:()=>closed++,refresh:async()=>{},guarded:fn=>pending=fn(),toast(){},esc,providerLabel:()=> 'DeepSeek',showProposalProgress:async(pid,id)=>progress.push({pid,id})};
 await open(deps);
 return {get form(){return form},get html(){return html},calls,progress,get closed(){return closed},server,submit:async()=>{form.onsubmit({preventDefault(){}});await pending},switchProject:()=>current={id:'other'}};
}
let h=await harness(project);assert.equal(h.calls.length,1,'Opening suggestions is read-only');await h.submit();const submitted=h.calls.find(c=>c.body);assert.equal(submitted.path,'/projects/p/jobs');assert.equal(submitted.body.capability,'narrative');assert.equal(submitted.body.target_id,'');assert(!submitted.body.proposal_id);assert(submitted.body.feedback.includes('Show switch closer'));assert.deepEqual(h.progress,[{pid:'p',id:'new-job'}]);
h=await harness(project);h.server.revision++;await assert.rejects(h.submit(),/已更新/);assert(!h.calls.some(c=>c.body));
h=await harness(project);h.switchProject();await h.submit();assert.equal(h.calls.find(c=>c.body).path,'/projects/p/jobs');assert.equal(h.closed,0);assert.equal(h.progress.length,0);
h=await harness(serial);h.form.elements.chapter_id.onchange({target:{value:'c2'}});assert(h.html.includes('Hold listener reaction'));assert(!h.html.includes('Show switch closer'));await h.submit();assert.equal(h.calls.find(c=>c.body).body.target_id,'c2');assert.equal(h.calls.find(c=>c.body).body.capability,'storyboard');
h=await harness(missing);await assert.rejects(h.submit(),/未有修訂建議/);assert(!h.calls.some(c=>c.body));
console.log('Current directing revision: visible grounded suggestions, deduplication, chapter/capability scope, escaped copy, automatic feedback, empty-input submission, stale-source guard and pinned project passed.');
