import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../static/postproduction.js',import.meta.url),'utf8');
const {splitVoiceDescription:split,composeVoiceDescription:compose,voiceDescriptionFields:fields,installVoiceUI,voiceLanguages,roleVoiceProfile,voiceReferenceFields,voiceReferencePayload,languageAudition,auditionTexts,voiceErrorMessage}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
assert.deepEqual(voiceLanguages,['英文','粵語（香港）','國語（台灣）','中文（大陸）']);
const legacy='二十出頭香港青年男聲；疲憊時略帶氣聲，避免英雄式播音腔。';
for(const text of [legacy,'男聲；低沉；句尾收住','低沉；男聲；男聲；  自訂；描述  ','<script>bad</script>']){
 const p=split(text); assert.equal(compose(text,p.selected,p.custom),text);
}
assert.deepEqual(split('男聲；低沉；句尾收住'),{selected:['男聲','低沉'],custom:'句尾收住'});
assert.equal(compose('男聲；低沉；句尾收住',['男聲'],'句尾收住'),'男聲；句尾收住');
const html=fields({description:'男聲；<script>bad</script>',language:'English'});
assert.match(html,/value="男聲" checked/);assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);
assert.match(html,/value="English" selected/);
assert.equal((html.match(/type="checkbox"/g)||[]).length,30);
for(const language of voiceLanguages)assert.ok(html.includes(`value="${language}"`));

let click,form,markup,requests=[],pending=[];
let entity={id:'ada',name:'Ada',description:'Keeper'};
globalThis.document={addEventListener:(_,fn)=>{click=fn;},querySelector:()=>form};
globalThis.FormData=class{constructor(f){this.data=f.data;}get(k){return this.data[k]??null;}getAll(k){return this.data[k]??[];}};
const profile={character_id:'ada',description:legacy,language:'English',sample_text:'Hello',seed:42,version:2};
installVoiceUI({getProject:()=>({id:'test',postproduction:{profiles:[profile]},production:{canon:[entity]}}),
 api:async(...args)=>requests.push(args),modal:(_,html)=>{markup=html;form={data:{voice_preset:[...html.matchAll(/name="voice_preset" value="([^"]+)" checked/g)].map(m=>m[1]),custom_description:split(roleVoiceProfile(profile,entity).description).custom,language:profile.language,sample_text:profile.sample_text,seed:String(profile.seed)},elements:{custom_description:{get value(){return form.data.custom_description;},set value(v){form.data.custom_description=v;},get validationMessage(){return this.error;},setCustomValidity(message){this.error=message;}}},nodes:{preview:{},details:{open:false}},querySelector(selector){return selector==='#voice-current-description'?this.nodes.preview:selector==='#voice-custom-options'?this.nodes.details:null;},listeners:{},addEventListener(k,fn){this.listeners[k]=fn;},reportValidity(){return !this.elements.custom_description.error;}};},close:()=>{},refresh:async()=>{},guarded:fn=>{pending.push(fn());},toast:()=>{}});
async function open(){click({target:{closest:()=>({dataset:{voiceAction:'edit',character:'ada'}})}});await Promise.all(pending);pending=[];}
async function save(){form.onsubmit({preventDefault(){},target:form});await Promise.all(pending);pending=[];}
await open();assert.match(markup,/角色預設音色/);assert.match(markup,/<details id="voice-custom-options"><summary>自訂音色特色（可多選）/);assert.doesNotMatch(markup,/按角色設定預填|復原預填/);await save();
assert.deepEqual(requests.pop(),['/projects/test/voices/ada',{description:legacy,language:'English',sample_text:'Hello',seed:42,version:2},'PUT']);
await open();form.data.voice_preset=['男聲','溫暖','低沉'];form.data.custom_description='';form.data.language='國語（台灣）';await save();
let payload=requests.pop()[1];assert.equal(payload.description,'男聲；低沉；溫暖');assert.equal(payload.language,'國語（台灣）');
Object.assign(profile,payload);await open();assert.deepEqual(form.data.voice_preset,['男聲','低沉','溫暖']);
form.data.voice_preset=['男聲','溫暖'];await save();assert.equal(requests.pop()[1].description,'男聲；溫暖');
form.data.voice_preset=[];form.data.custom_description='自訂聲音；保持自然';await save();assert.equal(requests.pop()[1].description,'自訂聲音；保持自然');
form.data.custom_description='  ';await save();assert.equal(requests.length,0);assert.match(form.elements.custom_description.error,/至少/);
form.data.custom_description='聲'.repeat(1200);form.data.voice_preset=['男聲'];await save();assert.equal(requests.length,0);assert.match(form.elements.custom_description.error,/1200/);
form.data.custom_description='恢復';form.listeners.input();await save();assert.equal(requests.pop()[1].description,'男聲；恢復');
console.log('Voice profile checks passed: actual edit/submit handlers, multiselect roundtrip, checkbox/custom only, legacy no-op identity, validation recovery, escaping and four languages.');

entity={id:'ada',name:'Ada',description:'A maintenance robot.'};
Object.assign(profile,{description:'',version:0,default_voice:{description:'小型維修機械人的中性合成聲線，輕微金屬共鳴；咬字準確，短句停頓俐落。',rationale:'維修機械人的工作導向與小型機體形成這套聲音設計。',evidence:['maintenance robot']}});
await open();assert.match(markup,/維修機械人/);assert.match(markup,/角色設計依據/);await save();assert.equal(requests.pop()[1].description,profile.default_voice.description);assert.equal(form.nodes.details.open,false);
assert.equal(roleVoiceProfile({description:''}).description,'');
Object.assign(profile,{description:legacy,version:2});await open();assert.equal(form.data.custom_description,legacy);assert.equal(form.nodes.details.open,false);await save();assert.equal(requests.pop()[1].description,legacy);
form.data.voice_preset=['溫暖'];form.listeners.change();assert.equal(form.nodes.preview.textContent,'溫暖；'+legacy);await save();assert.equal(requests.pop()[1].description,'溫暖；'+legacy);
form.data.voice_preset=[];form.data.custom_description='';await save();assert.equal(form.nodes.details.open,true);assert.equal(requests.length,0);
console.log('Complete default voice checks passed: semantic cached role design, existing voice retained, optional controls initially collapsed, save without expansion, preview updates and invalid-field disclosure.');

const referenceHtml=voiceReferenceFields({character_id:'ada',reference_take_id:'ref',reference_mode:'clone',reference_text:'Original <words>'},[{id:'ref',character_id:'ada',state:'succeeded',request:{provider:'uploaded',filename:'a<script>.wav'},created:'2026-09-13'}]);
assert.match(referenceHtml,/value="ref" selected/);assert.match(referenceHtml,/value="clone" selected/);assert.match(referenceHtml,/只參考音色/);assert.match(referenceHtml,/Original &lt;words&gt;/);assert.doesNotMatch(referenceHtml,/<script>/);
assert.deepEqual(voiceReferencePayload({data:{reference_take_id:'ref',reference_mode:'clone',reference_text:'Original'}}),{reference_take_id:'ref',reference_mode:'clone',reference_text:'Original'});
assert.deepEqual(voiceReferencePayload({data:{reference_take_id:'',reference_mode:'clone',reference_text:'old'}}),{reference_take_id:null,reference_mode:'clone',reference_text:''});
assert.deepEqual(voiceReferencePayload({data:{}}),{});
console.log('Reference form checks passed: selectable modes, attached selection, transcript escaping, detach payload and legacy-server compatibility.');

for(const language of Object.keys(auditionTexts))assert.equal(languageAudition(language,auditionTexts['粵語（香港）']),auditionTexts[language]);
assert.equal(languageAudition('English',auditionTexts['粵語（香港）']),auditionTexts['英文']);
assert.equal(languageAudition('英文','我自己寫的句子。'),'我自己寫的句子。');
assert.match(voiceErrorMessage('Traceback /vram/gpu/acquire HTTP Error 409: Conflict'),/配音尚未開始/);
assert.equal(voiceErrorMessage('different error'),'different error');
console.log('Voice language/admission checks passed: default sentence switching, custom text preservation and legacy HTTP 409 explanation.');

const {prepareRoleVoice}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
let loading,opened,defaultRequests=[],responseQueue=[];
const realTimer=globalThis.setTimeout;
globalThis.setTimeout=fn=>{fn();};
const prepareOptions={v:{description:'',version:0},ent:{name:'Pip',description:'A maintenance robot'},base:'/projects/test',cid:'pip',api:async(...args)=>{defaultRequests.push(args);const r=responseQueue.shift();if(r instanceof Error)throw r;return r;},modal:()=>{loading={isConnected:true,nodes:{'#voice-default-status':{},'#voice-default-retry':{},'#voice-default-manual':{}},querySelector(k){return this.nodes[k];}};},openEditor:v=>{opened=v;loading.isConnected=false;}};
globalThis.document.querySelector=()=>loading;
const designed={description:'',version:0,default_voice:{description:'維修機械人的合成聲線'}};
responseQueue=[{profile:prepareOptions.v,job:{id:'job',state:'queued'}},{id:'job',state:'running'},{id:'job',state:'succeeded'},{profile:designed}];
await prepareRoleVoice(prepareOptions);
assert.equal(opened,designed);assert.equal(defaultRequests.length,4);assert.equal(defaultRequests.at(-1)[0],'/projects/test/voices/pip/default');
opened=null;defaultRequests=[];responseQueue=[{profile:prepareOptions.v,job:{id:'failed',state:'failed',error:'Service unavailable'}}];
await prepareRoleVoice(prepareOptions);assert.equal(opened,null);assert.match(loading.nodes['#voice-default-status'].textContent,/Service unavailable/);assert.equal(loading.nodes['#voice-default-retry'].hidden,false);assert.equal(defaultRequests.length,1);
responseQueue=[{profile:designed}];await loading.nodes['#voice-default-retry'].onclick();assert.equal(defaultRequests.at(-1)[1].retry,true);assert.equal(opened,designed);
opened=null;
await prepareRoleVoice({...prepareOptions,api:async()=>{loading.isConnected=false;return {profile:designed};}});assert.equal(opened,null);
responseQueue=[new Error('offline')];await prepareRoleVoice(prepareOptions);loading.nodes['#voice-default-manual'].onclick();assert.equal(opened,prepareOptions.v);assert.equal(opened.description,'');
globalThis.setTimeout=realTimer;
console.log('Semantic design lifecycle passed: queued/running/completed, failure without fallback, explicit retry, close protection and manual editing.');

const {renderPostproduction}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const robotVoice={character_id:'pip',version:1,sound_mode:'nonverbal',description:'純電子 beep／boop，無人聲。',language:'',sample_text:'',seed:42};
assert.equal(roleVoiceProfile({description:'',default_voice:{sound_mode:'nonverbal',description:'電子短音'}}).sound_mode,'nonverbal');
const effectFields=fields(robotVoice);assert.match(effectFields,/電子短音/);assert.doesNotMatch(effectFields,/女聲|童聲|男聲/);assert.match(effectFields,/name="language" disabled/);assert.match(effectFields,/<details id="voice-custom-options"><summary>/);
const effectPage=renderPostproduction({title:'Test',production:{canon:[{id:'pip',kind:'character',name:'Pip'}],shots:[]},postproduction:{profiles:[robotVoice],takes:[]}});
assert.match(effectPage,/匯入角色音效/);assert.doesNotMatch(effectPage,/data-voice-action="design"|匯入參考人聲/);assert.match(effectPage,/無人聲／無對白/);
assert.deepEqual(voiceReferencePayload({data:{sound_mode:'nonverbal',reference_take_id:'ref',reference_mode:'clone',reference_text:'old speech'}}),{reference_take_id:'ref',reference_mode:'timbre',reference_text:''});
console.log('Nonverbal controls passed: role mode, effect-only presets, hidden/disabled language, import-only production and no Clone payload.');
assert.deepEqual(voiceReferencePayload({data:{sound_mode:'nonverbal',reference_take_id:'ref',reference_mode:'clone',reference_text:'original'}},'speech'),{reference_take_id:'ref',reference_mode:'clone',reference_text:'original'});

const {voicePreview,voicePlaybackPanel,captureVoicePlayback,restoreVoicePlayback}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const previewVoice={...robotVoice,sound_mode:'speech',selected_take_id:null};
const takeFixture={id:'current',character_id:'pip',kind:'voice',state:'succeeded',current:true,selected:false,audio_url:'/audio/current.wav',result:{duration:4,sample_rate:48000},request:{},created:'2026-09-13'};
const stale={...takeFixture,id:'stale',current:false,audio_url:'/audio/stale.wav'},failure={...takeFixture,id:'failure',state:'failed',result:null,audio_url:null};
assert.equal(voicePreview(previewVoice,[failure,stale,takeFixture]),takeFixture);
assert.equal(voicePreview(previewVoice,[failure,stale]),null);
const chosen={...takeFixture,id:'chosen',selected:true,audio_url:'/audio/chosen.wav'};
assert.equal(voicePreview({...previewVoice,selected_take_id:'chosen'},[takeFixture,chosen]),chosen);
assert.match(voicePlaybackPanel(previewVoice,[takeFixture]),/目前設定的試聽候選/);assert.match(voicePlaybackPanel({...previewVoice,selected_take_id:'chosen'},[takeFixture,chosen]),/現使用的聲音/);
assert.doesNotMatch(voicePlaybackPanel(previewVoice,[stale]),/<audio/);
const playbackPage=renderPostproduction({title:'Test',production:{canon:[{id:'pip',kind:'character',name:'Pip'}],shots:[]},postproduction:{profiles:[previewVoice],takes:[failure,stale,takeFixture]}});
assert.match(playbackPage,/<details data-voice-history="pip"><summary>試聽候選與歷史版本（2）/);
assert.ok(playbackPage.indexOf('data-voice-audio="current"')<playbackPage.indexOf('data-voice-history="pip"'));
assert.equal(playbackPage.match(/data-voice-audio="current"/g).length,1);
assert.doesNotMatch(playbackPage,/<details[^>]*\bopen\b/);
const oldAudio={dataset:{voiceAudio:'current'},getAttribute:()=>'/audio/current.wav'},historyNode={dataset:{voiceHistory:'pip'},open:true};
const playbackRoot={dataset:{voiceProject:'test'},querySelectorAll:selector=>selector.startsWith('details')?[historyNode]:[oldAudio]};
const captured=captureVoicePlayback(playbackRoot,'test');assert.equal(captureVoicePlayback(playbackRoot,'other'),null);
let replacement;const freshAudio={...oldAudio,replaceWith:old=>{replacement=old;}};
const newHistory={dataset:{voiceHistory:'pip'},open:false};
restoreVoicePlayback({dataset:{},querySelectorAll:selector=>selector.startsWith('details')?[newHistory]:[freshAudio]},'test',captured);
assert.equal(newHistory.open,true);assert.equal(replacement,oldAudio);
console.log('Voice playback checks passed: closed history, visible current candidate/selected audio, no stale fallback, no duplicate preview, user expansion and audio element retained on refresh.');
