import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

// Classification is informational on cards; only a submitted identity editor
// can persist a change. Exercise the actual editor handler with two assets.
const source=readFileSync(new URL('../static/app.js',import.meta.url),'utf8');
const helpers=source.slice(source.indexOf('function isPublicAsset('),source.indexOf('function voiceAssetCard('));
const edit=source.slice(source.indexOf("if(a==='edit-entity')"),source.indexOf("if(a==='revise-shot'"));
let form,requests=[];
const saved={id:'test',revision:1,production:{canon:['ada','pip'].map(id=>({id,kind:'character',name:id,description:'Original',facts:['Fact'],scope:'auto'})),scenes:[{id:'room'}],shots:[{id:'shot',entity_ids:['ada','pip']}]},asset_groups:{public_ids:[]}};
const ctx={settings:{capabilities:['identity_from_image']},bindIdentityImageAssistant:()=>{},bindIdentityAssetPicker:()=>({selection:()=>null}),displayLabel:String,$:()=>({}),assetsFor:()=>[],latest:()=>null,providerLabel:()=>'Test',project:structuredClone(saved),structuredClone,esc:String,editForm:(title,fields,submit)=>{form={fields,submit};},api:async(path,body,method)=>{assert.equal(method,'PUT');assert.equal(body.revision,saved.revision);assert.deepEqual(body.production.shots,saved.production.shots);requests.push(body);saved.production=structuredClone(body.production);saved.revision++;saved.asset_groups.public_ids=saved.production.canon.filter(e=>e.scope==='public').map(e=>e.id);ctx.project=structuredClone(saved);}};
vm.createContext(ctx);vm.runInContext(helpers+`\nasync function open(id){const a='edit-entity';${edit}}`,ctx);
for(const ent of ctx.project.production.canon)assert.doesNotMatch(ctx.assetScopeStatus(ent),/<input|<button|data-action|data-public-asset/);
assert.doesNotMatch(source,/changeAssetScope|data-public-asset/);
await ctx.open('ada');assert.equal(requests.length,0,'opening/cancelling editor must not save');
assert.equal(form.fields.find(f=>f.key==='public_asset').type,'checkbox');
assert(!form.fields.some(f=>f.key==='scope'||f.key==='scene_ids'));
async function save(id,makePublic){await ctx.open(id);const ent=ctx.project.production.canon.find(e=>e.id===id);await form.submit({kind:ent.kind,name:ent.name,description:ent.description,facts:ent.facts.join('\n'),...(makePublic?{public_asset:'on'}:{})});}
await save('ada',true);await save('pip',true);assert.deepEqual(saved.asset_groups.public_ids,['ada','pip']);
await save('ada',false);assert.deepEqual(saved.asset_groups.public_ids,['pip']);
ctx.project.production.canon[0].scope='auto';ctx.project.asset_groups.public_ids=['ada','pip'];
await save('ada',true);assert.equal(saved.production.canon[0].scope,'auto','unchanged effective legacy scope is preserved');
console.log('Asset scope: read-only cards, editor-only saving, multiple public assets, independent removal, revision and legacy preservation passed.');
