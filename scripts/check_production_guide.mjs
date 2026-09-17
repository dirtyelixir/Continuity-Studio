import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const url=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64');
const model=url(readFileSync('static/production-progress.js','utf8'));
const source=readFileSync('static/production-guide.js','utf8').replace("'./production-progress.js'",JSON.stringify(model));
const {renderProductionGuide,renderProductionDashboard,renderProductionNav}=await import(url(source));
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const button=(label,action,attrs='',cls='')=>`<button class="${cls}" data-action="${action}" ${attrs}>${label}</button>`;
const helpers={esc,button};
const p={id:'p',title:'Example',production:{canon:[],shots:[{id:'s"',title:'<img src=x>',keyframes:[]}]},assets:[],jobs:[],video_workflow:{shots:[]}};
for(const page of ['progress','overview','canon','shots','video','review','history','postproduction']){
 const html=renderProductionGuide(p,page,helpers);
 assert.equal((html.match(/data-stage=/g)||[]).length,5,'all production pages have a complete route');
 assert.equal((html.match(/aria-current="step"/g)||[]).length,1,'only the recommended production step is marked current');
 assert(html.includes('建議先處理 · 第 '));
 if(page!=='progress')assert(html.includes('正在瀏覽：')&&html.includes('返回製作總覽'));
 assert(!html.includes('<img src=x>'),'shot titles must be escaped');
 assert(!/data-action="(?:generate|retry|adopt|resume-stages)"/.test(html),'guide buttons only navigate or open a review/form');
}
const empty=renderProductionGuide({source_kind:'outline',jobs:[],assets:[]},'progress',helpers);
assert.equal((empty.match(/data-stage="[2-5]" disabled/g)||[]).length,4,'unavailable steps disabled for a blank project');
assert(renderProductionDashboard(p,helpers).includes('文字／圖片預覽不代表成片已完成'));
const nav=renderProductionNav('canon',2,helpers);
assert(nav.indexOf('data-page="canon"')<nav.indexOf('data-page="shots"'),'reference page precedes frame page');
assert.equal((nav.match(/aria-current="page"/g)||[]).length,1);
assert(nav.includes('製作總覽'));

// Execute actual routing code in a DOM-free harness: continuation selects the exact Shot
// and navigates without submitting any backend request.
const app=readFileSync('static/app.js','utf8');
const block=app.slice(app.indexOf('function openProgressVideo('),app.indexOf('async function navigate('));
const writes=[],visits=[],focus=[];
const urls=[];
const ctx={project:{id:'p',production:{shots:[{id:'s'}]}},updateProjectURL:(...args)=>urls.push(args),localStorage:{setItem:(...a)=>writes.push(a),removeItem:()=>{}},navigate:async page=>visits.push(page),document:{querySelector:s=>({setAttribute:()=>{},focus:()=>focus.push(s),scrollIntoView:()=>{}})},toast:e=>{throw Error(e)},uiError:x=>x};
vm.createContext(ctx);vm.runInContext(block,ctx);vm.runInContext("openProgressVideo('s','render')",ctx);await Promise.resolve();
assert.deepEqual(writes,[['video-shot:p','s']]);assert.deepEqual(visits,['video']);assert.deepEqual(focus,['.video-workspace .video-production']);
assert.deepEqual(urls,[['p','video','s']],'reload retains the exact continuation target');
vm.runInContext("openProgressVideo('removed','')",ctx);await Promise.resolve();assert.equal(writes.length,1,'stale target cannot become selected');
const route=app.slice(app.indexOf('function routePage('),app.indexOf('let projectDeletionReady'));
const rc={location:{hash:''}};vm.createContext(rc);vm.runInContext(route,rc);
assert.equal(vm.runInContext('routePage()',rc),'progress');
rc.location.hash='#overview';assert.equal(vm.runInContext('routePage()',rc),'overview','saved story links still work');
rc.location.hash='#h3';assert.equal(vm.runInContext('routePage()',rc),'video','legacy video links still work');
console.log('Production guide: persistent route, page versus step distinction, escaping, navigation-only actions, exact Shot continuation, empty states and legacy routes passed.');
// Contextual board review replaces the generic next card without removing the
// update target that background progress polling patches every four seconds.
const board={...p,storyboard:{scenes:[{scene_id:'scene',title:'Room',adopted:true,ready:false,panels:[{anchors:[{id:'a',asset:{id:'image'},ready:false}]}]}]}};
const reviewGuide=renderProductionGuide(board,'review',helpers);
assert(reviewGuide.includes('class="production-next" hidden'));
assert(renderProductionGuide(board,'progress',helpers).includes('data-board-action="continue"'));
