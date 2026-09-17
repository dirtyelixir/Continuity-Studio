import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync('static/app.js','utf8');
// Exercise the actual adaptive-polling decision, not a string match.
const block=source.slice(source.indexOf('let pollDueAt='),source.indexOf('async function boot(){'));
const ctx={};vm.createContext(ctx);vm.runInContext(block,ctx);
const active=j=>vm.runInContext(`pollActive(${JSON.stringify(j)})`,ctx);
assert.equal(active(null),false,'no project is not active work');
assert.equal(active({jobs:[{state:'succeeded'},{state:'failed'},{state:'cancelled'}]}),false,'terminal work alone is idle');
assert.equal(active({jobs:[],local_runtime:{phase:'ready'}}),false,'a ready local runtime is idle');
for(const state of ['queued','running','awaiting_input'])assert.equal(active({jobs:[{state:'succeeded'},{state}]}),true,state+' must poll fast');
assert.equal(active({jobs:[],local_runtime:{phase:'recovering'}}),true,'an active runtime phase must poll fast');
assert.equal(active({jobs:[],local_runtime:{phase:'maintenance'}}),true,'maintenance must poll fast');
vm.runInContext('pollActiveWork=false',ctx);assert.equal(vm.runInContext('pollIntervalMs()',ctx),30000,'an idle project reads slowly');
vm.runInContext('pollActiveWork=true',ctx);assert.equal(vm.runInContext('pollIntervalMs()',ctx),4000,'in-flight work keeps the fast cadence');
// Idle interval must be materially slower than the old unconditional 4-second read.
const idle=vm.runInContext('(pollActiveWork=false,pollIntervalMs())',ctx);
assert(idle>=30000,'an idle project must not read the full project every 4 seconds');
// The interval must still be guarded by the same visibility/edit/playback/dialog rules.
const tick=source.slice(source.indexOf("setInterval(()=>{if(document.visibilityState==='hidden'"),source.indexOf('},1000);}catch(e)'));
for(const guard of ["document.visibilityState==='hidden'",'busy','refreshing','progressPolling','$(\'#modal-root\').children.length',"'INPUT','TEXTAREA','SELECT'"])
 assert(tick.includes(guard),'adaptive polling must keep the '+guard+' guard');
assert(tick.includes('refresh().then'),'a completed read updates the cadence from real returned state');
assert(tick.includes('pollActiveWork=true;pollDueAt=Date.now()+4000'),'a failed read retries promptly instead of staying slow');
// The status-only image progress poll keeps its own unconditional cadence during work.
assert(source.includes("busy||$('#modal-root').children.length"),'status polling remains active during requests and dialogs');
console.log('Status polling: idle projects back off to 30s, queued/running work keeps 4s, failure retries promptly, and every visibility/edit/dialog guard is preserved.');
