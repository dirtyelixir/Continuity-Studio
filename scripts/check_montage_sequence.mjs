import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const mod=await import('data:text/javascript;base64,'+Buffer.from(readFileSync('static/directing-plan.js','utf8')).toString('base64'));
const esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const shot=(id,scene_id,title)=>({id,scene_id,title,framing:'CU <eyes>',shot_purpose:'read <evidence>'});
const edit=(id,shot_id,start,end)=>({id,shot_id,planned_edit_in:start,planned_edit_out:end,cut_in_reason:'receive <gaze>',cut_out_reason:'after <reaction>',continuity_note:'same <hand>'});
const plan={scenes:[{id:'room',title:'Room',director_plan:{beats:[],reveal_order:[]}},{id:'hall',title:'Hall',director_plan:null}],
 shots:[shot('a','room','Opening'),shot('b','room','Detail'),shot('c','hall','Outside')],
 edit_plan:[edit('e1','b',1,1.8),edit('e2','a',0,2.2),edit('e3','b',3,4.5),edit('e4','c',0,5)]};
const before=JSON.stringify(plan),html=mod.sceneEditSequenceMarkup(plan,'room',esc);
assert.equal((html.match(/<li /g)||[]).length,3);
assert(html.indexOf('Detail')<html.indexOf('Opening'));
assert.equal((html.match(/<strong>Detail/g)||[]).length,2);
assert.match(html,/2 個來源鏡頭 · 3 段剪接取用 · 4.50 秒/);
for(const expected of ['0.80 秒','2.20 秒','1.50 秒','3–4.5 秒','receive &lt;gaze&gt;','after &lt;reaction&gt;','same &lt;hand&gt;','CU &lt;eyes&gt;','read &lt;evidence&gt;','待實際影片核對'])assert(html.includes(expected),expected);
assert(!html.includes('Outside')&&!html.includes('<evidence>'));
assert.match(mod.sceneEditSequenceMarkup(plan,'hall',esc),/1 個來源鏡頭 · 1 段剪接/);
assert.match(mod.sceneEditSequenceMarkup({...plan,edit_plan:[]},'room',esc),/尚未保存/);
assert.match(mod.sceneEditSequenceMarkup({shots:[]},'room',esc),/尚未保存/);
assert.match(mod.directorPlanMarkup(plan,esc),/畫面如何接起來/);
assert.equal(JSON.stringify(plan),before);
console.log('Montage sequence: saved order, source reuse, fractional timing, scene scope, escaping, missing plans, actual plan integration and immutability passed.');
