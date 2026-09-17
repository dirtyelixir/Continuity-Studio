import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const {renderHandoff,createHandoffState}=await import('data:text/javascript;base64,'+Buffer.from(readFileSync('static/director-page.js','utf8')).toString('base64'));
const shot={shot_id:'shot',title:'Shot',number:1,duration:10,shot_prompt:'summary: [reference generation]',references:[],local_references:[],missing_references:[],issues:[],guidance:{continuityFromPrev:false,notes:''}};
const project={id:'project',delivery:{configuration:{context_frames:22},scenes:[{scene_id:'scene',title:'Scene',global_prompt:'subject_definitions:',references:[],missing_references:[],chapters:[shot]}]}};
const state=createHandoffState();state.select('project','scene','shot');
assert(renderHandoff(project,state).includes('重新生成分鏡提示詞'));
for(const status of ['queued','running','awaiting_input']){
 project.shot_prompt_regenerations={shot:{job_id:'job',state:status}};
 const html=renderHandoff(project,state);assert(html.includes('正在重新生成…')&&/data-action="regenerate-shot-prompt"[^>]*disabled/.test(html));
}
project.shot_prompt_regenerations.shot={job_id:'job',state:'succeeded',stale:false};
assert(renderHandoff(project,state).includes('比較新版'));
project.shot_prompt_regenerations.shot.adopted=true;assert(renderHandoff(project,state).includes('已採用重新生成的版本'));
project.shot_prompt_regenerations.shot={job_id:'job',state:'failed',error:'<bad>'};
const html=renderHandoff(project,state);assert(html.includes('原文仍保留')&&html.includes('&lt;bad&gt;'));
console.log('Shot regeneration controls: generate, pending/manual states, review/adopt status, failure and escaping passed.');
