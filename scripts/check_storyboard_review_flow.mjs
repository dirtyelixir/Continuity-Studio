import assert from 'node:assert/strict';
import {boardTask,renderBoardNext} from '../static/storyboard-next.js';
import {installStoryboard} from '../static/storyboard-board.js';
const anchor=(id,extras={})=>({id,frame_id:'f'+id,time:0,purpose:'Action '+id,frame:{description:'Still '+id},asset:{id:'a'+id},candidates:[{id:'a'+id,token:'token-'+id,status:'pending'}],ready:false,...extras});
const scene=(id,anchors,extras={})=>({scene_id:id,title:'Scene '+id,adopted:true,stale:false,ready:false,panels:[{title:'View '+id,anchors}],...extras});
const fixture=()=>({id:'p',revision:7,storyboard:{revision:4,scenes:[scene('s1',[anchor('done',{ready:true}),anchor('1'),anchor('2'),anchor('missing',{asset:null}),anchor('fix',{review:{verdict:'revise'}})]),scene('s2',[anchor('3')])]},assets:['done','1','2','3','fix'].map(id=>({id:'a'+id}))});
let p=fixture(),task=boardTask(p,'s1');
assert.equal(task.approved,1);assert.equal(task.missing,1);assert.equal(task.revising,1);assert.equal(task.pending.length,2);assert.equal(task.next.anchor.id,'1');
assert.equal(boardTask(p,'s2').next.anchor.id,'3');
const replacement=fixture();replacement.storyboard.scenes[0].panels[0].anchors[1].review={verdict:'revise',fingerprint:{asset_id:'old-image'}};assert.equal(boardTask(replacement,'s1').next.anchor.id,'1','old revision note cannot hide a replacement image');
assert(renderBoardNext(p,'s1').includes('2 格畫面等你確認'));
p.storyboard.scenes[0].stale=true;assert.equal(boardTask(p,'s1').pending.length,0);assert(!renderBoardNext(p,'s1').includes('開始審閱'));
p.storyboard.scenes[0].ready=true;assert.equal(renderBoardNext(p,'s1'),'');
p=fixture();
const handlers={},calls=[],navigations=[],modals=[];let form,pending,fail=false,release;
const nodes=['s1','s2'].map(id=>({dataset:{storyboardScene:id},open:false,scrollIntoView(){}}));
globalThis.document={addEventListener:(t,fn)=>handlers[t]=fn,querySelector:()=>form,querySelectorAll:()=>nodes};
function modal(title,html){
 modals.push({title,html});
 if(html.includes('id="board-review"')){
  const assetId=html.match(/<option value="([^"]+)" selected/)[1],buttons=[{disabled:false},{disabled:false}];
  form={elements:{asset_id:{value:assetId},note:{value:'Viewed'}},buttons,querySelector:()=>({innerHTML:''}),querySelectorAll:()=>buttons};
 }
}
installStoryboard({getProject:()=>p,getSettings:()=>({}),modal,close(){},toast(){},navigate:async page=>navigations.push(page),guarded:fn=>pending=fn(),refresh:async()=>{},api:async(path,body)=>{
 calls.push({path,body});if(fail)throw Error('version conflict');if(release)await new Promise(r=>release=r);
 const item=p.storyboard.scenes.flatMap(s=>s.panels.flatMap(x=>x.anchors)).find(a=>path.endsWith('/'+a.id));
 item.ready=body.verdict==='approved';item.review={verdict:body.verdict};p.storyboard.revision++;
}});
const click=async(action,sid='s1',id='')=>{handlers.click({target:{closest:()=>({dataset:{boardAction:action,scene:sid,id}})}});await pending;};
const submit=async verdict=>{form.onsubmit({preventDefault(){},submitter:{value:verdict}});await pending;};
await click('continue');assert.deepEqual(navigations,['shots']);assert.equal(calls.length,0,'opening never approves or generates');assert(nodes[0].open);assert.match(modals.at(-1).title,/第 2／5 格/);
assert(modals.at(-1).html.includes('/api/assets/adone/image'),'previous frame visible');
await submit('approved');assert.equal(calls.length,1);assert.equal(calls[0].body.token,'token-1');assert.equal(calls[0].body.revision,4);assert.match(modals.at(-1).title,/第 3／5 格/);
await submit('revise');assert.equal(calls[1].body.verdict,'revise');assert.equal(calls[1].body.revision,5);assert.match(modals.at(-1).title,/第 1／1 格/,'continues to next scene; missing/revise are retained');
await submit('approved');assert.equal(calls.length,3);assert.match(modals.at(-1).title,/今次可審閱/);assert(!modals.at(-1).html.includes('繼續影片製作'),'remaining repair cannot be shown as complete');
p=fixture();await click('continue');fail=true;const failedForm=form;await assert.rejects(()=>submit('approved'),/version conflict/);assert.equal(form,failedForm);assert(form.buttons.every(b=>!b.disabled));fail=false;
// A second click while the same immutable token is being saved cannot post twice.
release=true;const n=calls.length;form.onsubmit({preventDefault(){},submitter:{value:'approved'}});const saving=pending;form.onsubmit({preventDefault(){},submitter:{value:'approved'}});assert.equal(calls.length,n+1);release();release=null;await saving;
p=fixture();await click('continue');p={...p,id:'other'};const before=calls.length;await assert.rejects(()=>submit('approved'),/作品已切換/);assert.equal(calls.length,before);
console.log('Storyboard review flow: counts, scoped entry, neighbour images, token/revision saves, next scene, revise/missing retention, conflict retry, duplicate-submit and switched-project guards passed.');
