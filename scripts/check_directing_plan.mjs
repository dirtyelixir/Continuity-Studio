import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const mod=await import('data:text/javascript;base64,'+Buffer.from(readFileSync('static/directing-plan.js','utf8')).toString('base64'));
const esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const shot={id:'S1',title:'Chloe <reaction>',duration:5,shot_purpose:'Recognize 黃太',framing:'CU',direction:{visual_carrier:'Chloe eyes',readability:'Face readable',cut_in_reason:'Recognition starts',cut_out_reason:'Reaction registered',next_shot_relationship:'Then reveal identity'}};
const edit={id:'E1',shot_id:'S1',planned_edit_in:1.8,planned_edit_out:3.4};
const p={scenes:[{id:'scene',title:'Door',director_plan:null}],shots:[shot],edit_plan:[edit,{...edit,id:'E2'}]};
const text=mod.editPlanMarkup(p,esc,true);assert.match(text,/3.20 秒/);assert.equal((text.match(/1.60 秒/g)||[]).length,2);assert.match(text,/5 秒/);assert.ok(!text.includes('<reaction>'));assert.match(text,/再取一段/);
assert.match(mod.shotIntentMarkup(shot,esc),/Recognize 黃太/);assert.match(mod.directorPlanMarkup(p,esc),/這場已有分鏡/);
const blocked=mod.proposalReviewMarkup({required:true,state:'failed',error:'<script>'},'proposal',esc);assert.ok(!blocked.includes('<script>'));assert.match(blocked,/審查此方案/);
const pending=mod.proposalReviewMarkup({required:true,state:'running'},'proposal',esc);assert.ok(!pending.includes('data-action="directing-qc"'));assert.match(pending,/更新審查狀態/);
console.log('Director UI: source reuse, fractional screen duration, purpose, legacy/pending/failure state and HTML escaping passed.');

const candidate=(id,created,revision=9)=>({id,created,capability:'narrative',state:'succeeded',input:{revision},result:{scenes:[{id:'scene',director_plan:{beats:[]}}]}});
const older=candidate('older','2026-09-13T05:01:49Z'),latest=candidate('latest"<','2026-09-13T05:07:50Z');
const review={required:true,state:'succeeded',result:{verdict:'pass'}};
const project={id:'project',revision:9,production:p,jobs:[older,latest],directing:{scenes:[{scene_id:'scene',status:'legacy'}],proposals:{[older.id]:review,[latest.id]:review}}};
let panel=mod.directingPanel(project,esc);
assert.match(panel,/拍攝意圖已生成 · 待採用/);
assert.match(panel,/data-action="proposal" data-id="latest&quot;&lt;"/);
assert(!panel.includes('data-id="older"'));
assert(!panel.includes('尚未補充')&&!panel.includes('建立含拍攝意圖')&&!panel.includes('data-action="develop"'));
assert.match(panel,/目前仍沿用已採用的舊分鏡/);
for(const [state,verdict,label] of [['running',null,'正在審查'],['missing',null,'待審查'],['failed',null,'審查失敗'],['succeeded','revise','需要修訂'],['succeeded','uncertain','審查未能判斷']]){
 const copy=structuredClone(project);copy.directing.proposals[latest.id]={required:true,state,result:verdict?{verdict}:null};
 panel=mod.directingPanel(copy,esc);assert(panel.includes('拍攝意圖已生成 · '+label));assert(!panel.includes('待採用'));
}
for(const change of [j=>j.input.revision=8,j=>j.state='failed',j=>j.capability='image',j=>j.result.scenes[0].director_plan=null,j=>j.result.scenes[0].id='unrelated']){
 const copy=structuredClone(project);copy.jobs=[structuredClone(latest)];change(copy.jobs[0]);
 assert.equal(mod.directingCandidates(copy).size,0);assert.match(mod.directingPanel(copy,esc),/建立含拍攝意圖的方案/);
}
const noFormal=structuredClone(project);noFormal.directing.proposals={};assert.equal(mod.directingCandidates(noFormal).size,0);
const adopted=structuredClone(project);adopted.production.scenes[0].director_plan={reveal_order:[],beats:[]};adopted.directing.scenes[0].status='pass';
assert.equal(mod.directingCandidates(adopted).size,0);assert(!mod.directingPanel(adopted,esc).includes('待採用'));
const serial=structuredClone(project);serial.production.scenes=[{id:'ch__scene',title:'Chapter 1'},{id:'other__scene',title:'Chapter 2'}];serial.production.chapters=[{id:'ch',scene_ids:['ch__scene']},{id:'other',scene_ids:['other__scene']}];
serial.jobs=[{...latest,capability:'storyboard',target_id:'ch',result:{production:latest.result}}];
assert.deepEqual([...mod.directingCandidates(serial).keys()],['ch__scene']);
serial.jobs[0].target_id='missing';assert.equal(mod.directingCandidates(serial).size,0);
console.log('Director candidates: latest current proposal, QC states, stale/failed/unrelated exclusions, adopted authority, chapter scope and escaping passed.');
