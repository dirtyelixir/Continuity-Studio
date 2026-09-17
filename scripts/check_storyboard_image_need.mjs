import assert from 'node:assert/strict';
import {imagePlanMarkup} from '../static/storyboard-board.js';
import {boardTask} from '../static/storyboard-next.js';
const panel={image_plan:{mode:'I2VA',reason:'Opening is sufficient',unresolved_constraints:[]},planning_notes:['A gesture <script>']};
const html=imagePlanMarkup(panel);
assert.match(html,/只需來源首幀/);
assert.match(html,/同一 continuous Shot/);
assert.match(html,/不生圖、不需逐張批准/);
assert.match(html,/&lt;script&gt;/);
assert.equal(imagePlanMarkup({}),'');
panel.image_plan.mode='FL2VA';panel.image_plan.unresolved_constraints=['Hard middle state'];
assert.match(imagePlanMarkup(panel),/來源首幀＋尾幀/);
assert.match(imagePlanMarkup(panel),/尚未可執行：Hard middle state/);
const task=boardTask({storyboard:{scenes:[{scene_id:'s',adopted:true,ready:false,panels:[],unresolved_constraints:['Hard middle state']}]}});
assert.equal(task.complete,false);assert.match(task.title,/約束|约束/);assert.equal(task.label,'查看約束同可行下一步');
assert.equal(task.recoverable,0);
// A blocked board must name a real next step, and say so differently when an
// earlier usable plan exists (a later failed retry must not leave the user stuck).
const blocked=boardTask({storyboard:{scenes:[{scene_id:'s',adopted:true,ready:false,panels:[],unresolved_constraints:['Hard middle state'],candidates:[{id:'c1',state:'failed',stale:false,usable:false,adopted:false}]}]}});
assert.equal(blocked.recoverable,0);
const recovering=boardTask({storyboard:{scenes:[{scene_id:'s',adopted:true,ready:false,panels:[],unresolved_constraints:['Hard middle state'],candidates:[{id:'c1',state:'succeeded',stale:false,usable:true,adopted:false}]}]}});
assert.equal(recovering.recoverable,1);
const scene=recovering.scenes[0];
const {renderBoardNext}=await import('../static/storyboard-next.js');
assert.match(renderBoardNext({storyboard:{scenes:[scene]}}),/較早嘅成功方案/);
console.log('Storyboard image demand UI checks passed');
