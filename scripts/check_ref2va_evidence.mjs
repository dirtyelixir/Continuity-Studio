import assert from 'node:assert/strict';
import {renderFrozenReferences} from '../static/video-render.js';
const t={request:{source:{mode:'REF2VA'}},image_inputs:[{name:'Chloe <identity>',target_id:'chloe',role:'character',label:'Picture 1',sha256:'a'.repeat(64),submission_verified:false}]};
let h=renderFrozenReferences(t);assert.match(h,/角色身份/);assert.match(h,/→ Picture 1/);assert.match(h,/尚未有完整提交證據/);assert.match(h,/&lt;identity&gt;/);
t.image_inputs[0].submission_verified=true;h=renderFrozenReferences(t);assert.match(h,/提交回條吻合/);assert.doesNotMatch(h,/尚未有完整提交證據/);
assert.equal(renderFrozenReferences({}),'');
console.log('Ref2VA frozen role mapping, evidence distinction, legacy fallback and escaping passed');
