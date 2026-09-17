import assert from 'node:assert/strict';
import {renderVideoWorkflow} from '../static/video-workflow.js';
const row={shot_id:'shot',scene_id:'scene',title:'Shot',duration:6,mode:'I2VA',frames:[],prompt:{},jobs:{},reasons:[]};
const scene=id=>({scene_id:id,adopted:true,ready:false,panels:[{anchors:[{id:'a'+id,asset:{id:'image'},ready:false}]}]});
const p={id:'p',production:{scenes:[{id:'scene',title:'Room'}],shots:[{id:'shot',scene_id:'scene',duration:6,title:'Shot',keyframes:[]}]},video_workflow:{shots:[row]},storyboard:{scenes:[scene('other'),scene('scene')]}};
const drafts={get:()=>null};
for(const group of [false,true]){
 if(group)p.generation_groups={rows:[{id:'g',title:'Group',scene_id:'scene',duration:6,mode:'I2VA',members:[{shot_id:'shot',shot:p.production.shots[0],edit:{},edit_id:'e'}],reasons:[],prompt:{}}]};
 const render=()=>renderVideoWorkflow(p,group?'g':'shot',()=>'',drafts);
 let html=render();assert(html.includes('data-board-action="continue" data-scene="scene"'));assert(!html.includes('data-board-action="continue" data-scene="other"'));
 p.storyboard.scenes[1].ready=true;html=render();assert(!html.includes('data-board-action="continue"'),'ready scene does not inherit other scene blocker');
 p.storyboard.scenes[1].ready=false;
}
console.log('H3 board entry: independent/native paths, scene targeting and ready-scene omission passed.');
