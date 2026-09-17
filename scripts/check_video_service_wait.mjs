import assert from 'node:assert/strict';
import {prepareVideoService} from '../static/video-service-prepare.js';
const error=()=>Error('操作失敗：VRAM Manager 已暫停或正在切換；尚未送出生成。');
let clock=0;const calls=[],messages=[],options={now:()=>clock,wait:async ms=>clock+=ms,notify:x=>messages.push(x),timeoutMs:4000};
const reply=await prepareVideoService(async(path,body)=>{calls.push({path,body});if(calls.length<3)throw error();return {ready:true};},options);
assert(reply.ready);assert.equal(clock,4000);assert.equal(messages.length,2);assert(calls.every(x=>x.path==='/video-provider/prepare'));assert.equal(calls.length,3);
clock=0;let n=0;await assert.rejects(()=>prepareVideoService(async()=>{n++;throw error();},options),/仍未開放工作/);assert.equal(n,3);assert.equal(clock,4000);
for(const message of ['VRAM Manager 已暫停接收工作','GPU busy','Network timeout','missing nodes']){
 n=0;await assert.rejects(()=>prepareVideoService(async()=>{n++;throw Error(message);},options),new RegExp(message));assert.equal(n,1,'unknown/refused work cannot be retried');
}
console.log('Video service wait: only proven legacy pre-admission refusal retries; explicit prepare only, bounded timeout, current pause and ambiguous/network errors stop without retry.');
