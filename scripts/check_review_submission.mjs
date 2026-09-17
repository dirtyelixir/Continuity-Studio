import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const url=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64');
const guide=await import(url(readFileSync('static/proposal-guide.js','utf8')));
const directing=await import(url(readFileSync('static/directing-plan.js','utf8')));
const esc=x=>String(x??'').replaceAll('<','&lt;').replaceAll('>','&gt;');
const job={id:'proposal',state:'succeeded',result:{canon:[],scenes:[],shots:[]},input:{revision:2}};
for(const phase of ['review','progress'])for(const state of ['sending','queued','running']){
 const args={job,phase,currentRevision:2,status:{required:true,state,queue:{position:2,running:1,running_projects:['<other>']}}};
 const html=guide.proposalGuideMarkup(args,esc)+guide.proposalGuideFooterMarkup(args,esc);
 assert(!html.includes('data-action="directing-qc"'));
 assert(html.includes({sending:'正在送出審查',queued:'審查已排隊',running:'自動審查中'}[state]));
 if(state==='queued'){assert(html.includes('第 2 位'));assert(html.includes('&lt;other&gt;'));}
}
for(const state of ['queued','running']){
 const html=directing.proposalReviewMarkup({required:true,state,result:{verdict:'pass'}},'proposal',esc);
 assert(!html.includes('data-action="directing-qc"'));assert(!html.includes('data-action="revise-directing"'));
}
const failed=guide.proposalGuideMarkup({job,currentRevision:2,status:{required:true,state:'failed',error:'<failure>'}},esc);
assert(failed.includes('自動審查失敗'));assert(failed.includes('並非仍在處理'));assert(failed.includes('&lt;failure&gt;'));
const source=readFileSync('static/app.js','utf8');
const fn=source.slice(source.indexOf('async function submitDirectingReview('),source.indexOf('function approveImageForm('));
function harness(){
 const dialog={},els=Object.fromEntries(['#proposal-guide-top','#proposal-guide-footer','#proposal-review-details','#proposal-watch-error'].map(s=>[s,{innerHTML:'old retry',textContent:''}]));
 els['#modal-root']={firstElementChild:dialog};
 let resolvePost,resolveRefresh,cancelled=0;
 const calls=[],opened=[];
 const ctx={project:{id:'p',jobs:[]},$:s=>els[s],disposeProposalWatch:()=>cancelled++,reviewReceiptMarkup:guide.reviewReceiptMarkup,esc,toast:()=>{},api:(path,body)=>{calls.push({path,body});return new Promise(r=>resolvePost=r);},updateWorkSurfaces:()=>{},refresh:()=>new Promise(r=>resolveRefresh=r),showProposalProgress:async(...args)=>opened.push(args.slice(0,2)),bindProposalWatch:()=>{}};
 vm.createContext(ctx);vm.runInContext(fn,ctx);
 return {ctx,els,calls,opened,run:()=>vm.runInContext("submitDirectingReview('proposal')",ctx),post:value=>resolvePost(value),refresh:()=>resolveRefresh(),cancelled:()=>cancelled};
}
const h=harness(),pending=h.run();
assert(h.els['#proposal-guide-top'].innerHTML.includes('正在送出審查'),'synchronous feedback before POST resolves');
assert.equal(h.cancelled(),1,'old watcher stopped before submitting');assert.equal(h.els['#proposal-review-details'].innerHTML,'');
assert.equal(h.calls[0].path,'/projects/p/jobs');assert.equal(h.calls[0].body.target_id,'proposal');
h.post({job:{id:'review',state:'queued'}});await new Promise(setImmediate);
assert(h.els['#proposal-guide-top'].innerHTML.includes('審查已排隊'),'receipt visible before refresh completes');
h.refresh();await pending;assert.deepEqual(h.opened,[['p','proposal']]);
const closed=harness(),late=closed.run();closed.els['#modal-root'].firstElementChild=null;closed.post({job:{id:'review',state:'running'}});await new Promise(setImmediate);closed.refresh();await late;assert.equal(closed.opened.length,0,'late submission cannot reopen a closed dialog');
const switched=harness(),old=switched.run();switched.ctx.project={id:'other',jobs:[]};switched.post({job:{id:'review',state:'running'}});await old;assert.equal(switched.opened.length,0);assert.deepEqual(switched.ctx.project.jobs,[],'cannot write receipt into another project');
console.log('Review submission: immediate sending, queued receipt before refresh, explicit running state, no retry/revise controls while pending, stale watcher disposal, close and project-switch safety passed.');
