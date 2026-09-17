import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const guide=await import('data:text/javascript;base64,'+Buffer.from(readFileSync('static/proposal-guide.js')).toString('base64'));
const plan={title:'Plan',canon:[],scenes:[],shots:[]};
const base={id:'proposal',project_id:'p',capability:'narrative',state:'succeeded',input:{revision:2},result:plan};
assert.equal(guide.readableProposal(base),plan);
assert.equal(guide.readableProposal({...base,capability:'storyboard',result:{production:plan}}),plan);
const source=readFileSync('static/app.js','utf8');
const branch=source.slice(source.indexOf("if(a==='proposal'){"),source.indexOf("if(a==='directing-qc'){"));
for(const state of ['queued','running','awaiting_input','failed','interrupted','cancelled','succeeded']){
 const job={...base,state,result:null},opened=[];
 assert.equal(guide.readableProposal(job),null);
 for(const phase of ['progress','review']){
  const next=guide.proposalNextAction({job,currentRevision:2,phase});
  assert(!['adopt','proposal'].includes(next.action),'missing result never offers open/adopt');
 }
 const ctx={a:'proposal',id:job.id,project:{id:'p',revision:2},refresh:async()=>{},api:async()=>job,readableProposal:guide.readableProposal,showProposalProgress:async(...args)=>opened.push(args)};
 vm.createContext(ctx);await vm.runInContext('(async()=>{'+branch+'})()',ctx);
 assert.deepEqual(opened,[['p','proposal']],'actual handler opens progress without dereferencing null');
}
for(const result of [{},{production:null},{production:{canon:null,scenes:[],shots:[]}},'invalid'])assert.equal(guide.readableProposal({...base,result}),null);
for(const state of ['running','succeeded']){
 const review={...base,capability:'directing_qc',state,result:state==='running'?null:{verdict:'pass'}};
 assert.equal(guide.readableProposal(review),null);
 assert.equal(guide.proposalNextAction({job:review,currentRevision:2}).action,'job-detail','review receipt never becomes a production proposal');
}
for(const state of ['queued','running']){
 const next=guide.proposalNextAction({job:base,status:{required:true,state},currentRevision:2,phase:'progress'});
 assert.equal(next.step,2);assert.equal(next.action,undefined,'pending review stays at step 2 without a premature open button');
}
const foreign={a:'proposal',id:'other',project:{id:'p'},refresh:async()=>{},api:async()=>({...base,project_id:'foreign'}),readableProposal:()=>{throw Error('must not read foreign result');}};
vm.createContext(foreign);await assert.rejects(vm.runInContext('(async()=>{'+branch+'})()',foreign),/不屬於目前作品/);
console.log('Proposal opening: actual handler handles null in every state, rejects wrong job types and project ownership, validates direct/wrapped plans, and keeps pending review at step 2.');
