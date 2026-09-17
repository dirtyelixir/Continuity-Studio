import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../static/generation-status.js',import.meta.url),'utf8');
const {generationStatus,elapsedLabel,renderGenerationStatus}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const base={id:'p',jobs:[],assets:[]};
const job={id:'j',target_id:'ada',capability:'image',created:'2026-09-08T15:00:00Z',state:'queued'};
const asset={id:'a',target_id:'ada',status:'pending',created:'2026-09-08T15:02:00Z'};
assert.equal(generationStatus(base,'ada'),null);
for(const state of ['queued','running','awaiting_input']){
 const status=generationStatus({...base,jobs:[{...job,state}]},'ada');assert.equal(status.phase,state);assert.equal(status.active,true);
 assert.equal(generationStatus({...base,jobs:[{...job,state}]},'pip'),null);
}
assert.match(generationStatus({...base,jobs:[{...job,state:'awaiting_input'}]},'ada').detail,/沒有自動生成/);
for(const state of ['failed','interrupted','cancelled']){
 const status=generationStatus({...base,jobs:[{...job,state}]},'ada');assert.equal(status.phase,state);assert.equal(status.active,false);
}
const completed={...base,jobs:[{...job,state:'succeeded'}],assets:[asset]};
assert.equal(generationStatus(completed,'ada').phase,'ready');
const review={...job,id:'review',target_id:'a',capability:'image_review',created:'2026-09-08T15:02:01Z',state:'running'};
assert.match(generationStatus({...completed,jobs:[...completed.jobs,review]},'ada').label,/正在審查/);
assert.equal(generationStatus({...completed,jobs:[...completed.jobs,review]},'ada').assetId,'a');
assert.equal(generationStatus({...completed,assets:[{...asset,status:'approved'}]},'ada'),null);
assert.equal(generationStatus({...completed,jobs:[{...job,state:'failed'}],assets:[{...asset,status:'approved'}]},'ada'),null,'Old failure must not override a newer accepted import');
assert.equal(generationStatus({...completed,jobs:[{...job,id:'new',created:'2026-09-08T15:03:00Z',state:'running'},review]},'ada').jobId,'new');
assert.equal(elapsedLabel(job.created,Date.parse('2026-09-08T15:01:03Z')),'已等候 1 分 3 秒');
assert.equal(elapsedLabel('invalid'), '');
assert.equal(elapsedLabel('2030-01-01',0),'已等候 0 秒');
const escape=x=>String(x).replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const markup=renderGenerationStatus({...generationStatus({...base,jobs:[job]},'ada'),error:'<script>bad</script>'},escape);
assert.ok(markup.includes('data-job-since=')&&markup.includes('generation-spinner')&&markup.includes('role="status"'));
assert.ok(!markup.includes('<script>')&&!markup.includes('%'));
assert.ok(!renderGenerationStatus(generationStatus(completed,'ada'),escape).includes('generation-spinner'));
console.log('Generation status checks passed: queue, run, manual, review, completion, failures, target isolation, old-job precedence, elapsed time and rendering.');
const {queueDetail}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const queued={...job,queue:{label:'圖片生成',position:2,running:1,running_projects:['另一作品 <unsafe>']}};
assert.match(queueDetail(queued),/第 2 位/);
assert.match(generationStatus({...base,jobs:[queued]},'ada').detail,/另一作品/);
assert.ok(!renderGenerationStatus(generationStatus({...base,jobs:[queued]},'ada'),escape).includes('<unsafe>'));
assert.equal(queueDetail({...queued,state:'succeeded'}),'');
const cancelling={...job,state:'running',provider:'comfy_local',error:'已要求取消；正在停止本機結果等待'};
assert.match(generationStatus({...base,jobs:[cancelling]},'ada').detail,/停止等待本機結果/);
const {renderLocalRuntime}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
assert.match(renderLocalRuntime({phase:'recovering',message:'Manager 正在核對 <unsafe>'},escape),/正在復原出圖服務/);
assert.ok(!renderLocalRuntime({phase:'blocked',message:'<unsafe>'},escape).includes('<unsafe>'));
assert.equal(renderLocalRuntime({phase:'ready',message:'ready'},escape),'');
