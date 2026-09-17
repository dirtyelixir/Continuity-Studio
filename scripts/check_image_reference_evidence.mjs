import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const app=await readFile(new URL('../static/app.js',import.meta.url),'utf8');
const code=app.slice(app.indexOf('function imageReferenceEvidence('),app.indexOf('function assetCard('));
// The browser imports this helper from local-images.js.  This focused source
// check extracts imageReferenceEvidence on its own, so provide the same
// no-op fallback for plans without LoRA advice instead of relying on module
// imports or a browser bundler.
const imageLoraMarkup=()=>'';
const project={jobs:[{id:'job',input:{source_asset_id:'old',input_reference_ids:['uploaded'],layout_reference:'layout.png'}}],input_references:[{id:'uploaded',name:'<new design>',purpose:'identity'}]};
const render=new Function('project','imageURL','inputReferenceURL','esc','imageLoraMarkup',code+';return imageReferenceEvidence;')(project,id=>'/assets/'+id,r=>'/uploads/'+r.id,s=>s.replaceAll('<','&lt;').replaceAll('>','&gt;'),imageLoraMarkup);
const html=render({job_id:'job',reference_ids:['old']});
assert.ok(html.includes('1 張素材參考、1 張上傳參考，另附四視圖排版範例'));
assert.equal((html.match(/src="\/assets\/old"/g)||[]).length,1);
assert.ok(html.includes('/uploads/uploaded')&&html.includes('&lt;new design&gt;'));
const imported=render({reference_ids:[],provider:'manual'});
assert.ok(!imported.includes('另附四視圖排版範例'));
console.log('Image reference evidence: saved upload shown, edit source deduplicated, labels escaped, layout provenance respected.');
