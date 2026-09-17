import assert from 'node:assert/strict';
import {bindReferenceDrop,validateReferenceFiles,referenceDropMarkup} from '../static/reference-drop.js';
const file=(name='ref.png',type='image/png',size=10)=>({name,type,size,lastModified:1});
for(const files of [[],[file('bad','text/plain')],[file('empty.png','image/png',0)],[file('big.png','image/png',41*1024*1024)]])assert.throws(()=>validateReferenceFiles(files));
assert.equal(validateReferenceFiles([file(),file('next.webp','image/webp')]).length,2);
assert(referenceDropMarkup().includes('multiple'));
const element=()=>({children:[],append(...nodes){this.children.push(...nodes);},replaceChildren(){this.children=[];},setAttribute(){}});
const oldDoc=globalThis.document,create=URL.createObjectURL,revoke=URL.revokeObjectURL;
const released=[];globalThis.document={createElement:element};URL.createObjectURL=()=>`blob:${Math.random()}`;URL.revokeObjectURL=u=>released.push(u);
try{
 const listeners=new Map(),modal={addEventListener:(n,h)=>listeners.set(n,h),removeEventListener:n=>listeners.delete(n)};
 const input={files:[]},preview=element(),status={};
 const root={closest:()=>modal,querySelector:s=>({'input':input,'[role="status"]':status,'.reference-drop-preview':preview})[s],classList:{add(){},remove(){}}};
 const a=file('a.png'),b=file('b.webp','image/webp'),c=file('c.jpg','image/jpeg');let picked;
 const control=bindReferenceDrop(root,{initialFile:[a,b],onSelect:files=>picked=files});
 assert.equal(control.getFiles().length,2);assert.equal(picked,undefined);
 input.files=[a,c];input.onchange();assert.equal(control.getFiles().length,3);assert.equal(picked.length,3);
 assert.equal(preview.children.length,3);preview.children[0].children[2].onclick();assert.deepEqual(control.getFiles(),[b,c]);
 input.files=[file('bad','text/plain')];input.onchange();assert.deepEqual(control.getFiles(),[b,c]);assert(status.textContent.includes('仍然保留'));
 control.removeFile(b);assert.deepEqual(control.getFiles(),[c]);
 control.dispose();assert.equal(listeners.size,0);assert(released.length>0);
}finally{globalThis.document=oldDoc;URL.createObjectURL=create;URL.revokeObjectURL=revoke;}
console.log('Multi-reference selection, append/dedup, removal, partial-save retention, validation and URL cleanup passed.');
