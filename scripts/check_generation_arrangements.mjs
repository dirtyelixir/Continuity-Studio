import assert from 'node:assert/strict';
import {renderAdoptedArrangements,renderShotArrangement} from '../static/generation-arrangements.js';
import {installGenerationGroups} from '../static/generation-groups.js';
import {renderVideoWorkflow} from '../static/video-workflow.js';
import {createPromptDrafts} from '../static/prompt-editor.js';
const gid='mg_aaaaaaaaaaaaaaaa';
const member={edit_id:'e1',shot_id:'s1',title:'Close <script>',source_in:.2,source_out:5.4,duration:8};
const independent={edit_ids:['e1'],title:'Evidence',execution:'separate_source',mode:null,reason:'Readable switch',checks:['Hands < switch'],members:[member],group_id:''};
const native={...independent,title:'Native',execution:'native_montage',mode:'REF2VA',group_id:gid};
const a={scene_id:'scene',title:'Workshop',job_id:'adopted',status:'current',reason:'Saved',items:[independent,native]};
const p={id:'p',generation_groups:{rows:[{id:gid}],arrangements:[a]}};
let html=renderAdoptedArrangements(p,'scene');
assert(html.includes('生成完整 8 秒，再剪用 0.2–5.4 秒'));
assert(html.includes('data-action="progress-video" data-id="s1"'));
assert(html.includes(`data-group-action="open" data-id="${gid}"`));
assert(html.includes('Hands &lt; switch')&&!html.includes('<script>')&&!html.includes('undefined'));
assert(renderShotArrangement(p,'s1').includes('檢查要求會帶入新生成的 H3 提示詞'));
assert.equal(renderShotArrangement(p,'unrelated'),'');
native.group_id='';assert(!renderShotArrangement(p,'s1').includes('合成一段影片'));
assert(renderAdoptedArrangements(p,'scene').includes('此分組已停用'));
for(const status of ['legacy','stale']){
 a.status=status;html=renderAdoptedArrangements(p,'scene');
 assert(html.includes('重新安排生成分組')&&!html.includes('data-action="progress-video"')&&!html.includes('data-group-action="open"'));
 assert.equal(renderShotArrangement(p,'s1'),'');
}
const listeners={},panel={dataset:{generationGroup:gid},open:false,setAttribute(){},focus(){this.focused=true;},scrollIntoView(){this.scrolled=true;}};
let pending,calls=0;
globalThis.document={addEventListener:(event,fn)=>listeners[event]=fn,querySelectorAll:()=>[panel]};
installGenerationGroups({getProject:()=>p,api:()=>{calls++;},guarded:fn=>pending=fn()});
listeners.click({target:{closest:()=>({dataset:{groupAction:'open',id:gid}})}});await pending;
assert(panel.open&&panel.focused&&panel.scrolled);assert.equal(calls,0);
// Selecting either member of an adopted group opens its complete H3 workspace.
a.status='current';native.group_id=gid;native.members=[member,{...member,shot_id:'s2',edit_id:'e2'}];
p.production={scenes:[{id:'scene',title:'Workshop'}]};
p.video_workflow={shots:[{shot_id:'s1'},{shot_id:'s2'}]};
p.generation_groups.rows=[{id:gid,shot_id:gid,scene_id:'scene',kind:'generation_group',title:'Combined',duration:13,mode:'I2VA',
 reason:'One clip',members:native.members.map(m=>({...m,start:0,end:6,shot:{scene_id:'scene',keyframes:[]},edit:{}})),
 reference_requirements:[],references:[],reasons:[],prompt:{},checks:[]}];
for(const selected of ['s1','s2',gid]){
 html=renderVideoWorkflow(p,selected,()=>'',createPromptDrafts());
 assert(html.includes('按已保存分組製作影片')&&html.includes('13 秒 · I2VA'));
 assert(html.includes('生成整組 H3 提示詞')&&html.includes('data-group-primary="true"'));
 assert(!html.includes('本鏡 · 選擇做法'));
 assert.equal((html.match(/data-generation-group=/g)||[]).length,1);
}
a.status='stale';assert(renderVideoWorkflow(p,'s1',()=>'',createPromptDrafts()).includes('13 秒 · I2VA'));
console.log('Adopted H3 arrangements: exact source ranges, independent/native navigation, scoped checks, escaping, stale/legacy exclusion, archived routing and read-only group focus passed.');
