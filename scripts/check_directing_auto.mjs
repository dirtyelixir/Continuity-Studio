import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const load=async path=>import('data:text/javascript;base64,'+Buffer.from(readFileSync(path,'utf8')).toString('base64'));
const {directingPanel}=await load('static/directing-plan.js');
const {productionProgress}=await load('static/production-progress.js');
const esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const p={id:'test',revision:2,jobs:[],production:{canon:[],scenes:[{id:'scene',title:'Workshop',director_plan:{reveal_order:[],beats:[]}}],shots:[{id:'shot',scene_id:'scene',keyframes:[]}],edit_plan:[]},directing:{scenes:[{scene_id:'scene',status:'unreviewed'}],current_review:{state:'queued',job_id:'review'}}};
for(const [state,label] of [['queued','審查已排隊'],['running','正在自動審查'],['deferred','等待自動審查最新方案'],['awaiting_input','等待人工審查']]){
 p.directing.current_review.state=state;
 const html=directingPanel(p,esc);
 assert(html.includes(label));assert(!html.includes('data-action="directing-qc"'));assert(html.includes('data-id="review"'));
 const progress=productionProgress(p);
 assert.equal(progress.currentStage,1);assert.equal(progress.next.action,'overview-section');assert.equal(progress.next.section,'overview-directing');assert.equal(progress.stages[0].complete,false);
}
p.directing.current_review={state:'failed',job_id:'bad"<',error:'<script>bad</script>'};
let html=directingPanel(p,esc);assert(html.includes('重試導演內容審查'));assert(!html.includes('<script>'));assert(html.includes('bad&quot;&lt;'));
p.directing.scenes[0].status='revise';p.directing.current_review={state:'succeeded',result:{verdict:'revise'}};
assert(productionProgress(p).next.title.includes('有意見'));assert(directingPanel(p,esc).includes('需要修訂方案'));
p.directing.scenes[0].status='pass';p.directing.current_review.result.verdict='pass';assert.notEqual(productionProgress(p).currentStage,1);
console.log('Automatic directing UI: queued/running/deferred/manual, duplicate controls, gate-aware navigation, failure escaping and substantive verdicts passed.');
