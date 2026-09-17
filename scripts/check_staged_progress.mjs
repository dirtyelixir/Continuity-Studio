import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

// 以 data URL 匯入原始碼，模擬純 ESM 模組（無外部相依）
const source=await readFile(new URL('../static/staged-progress.js',import.meta.url),'utf8');
const {renderStagedProgress,canResumeStages}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));

const esc=x=>String(x).replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const progress={kind:'chapter_stages',label:'分階段生成',completed:2,total:5,completed_shots:6,total_shots:12,updated:'2026-09-10T10:00:00Z'};

// 1. 無 progress 時回傳 ''
assert.equal(renderStagedProgress({},esc),'');
assert.equal(renderStagedProgress(null,esc),'');
assert.equal(renderStagedProgress({progress:{kind:'other'}},esc),'');
assert.equal(renderStagedProgress({progress:{}},esc),'');
assert.ok(!renderStagedProgress({progress:{kind:'chapter_stages'}},esc).includes('階段 0'),'stage count shown without numbers'); // 數字缺少先不顯示計數

// 2. 數字計數正確顯示（階段與鏡頭）
const running=renderStagedProgress({state:'running',progress},esc);
assert.ok(running.includes('階段 2/5'),'stages count missing');
assert.ok(running.includes('鏡頭 6/12'),'shots count missing');
assert.ok(running.includes('staged-progress-running'));

// 3. 失敗／中斷：保留已保存階段的說明
const failed=renderStagedProgress({state:'failed',progress,error:'逾時'},esc);
assert.ok(failed.includes('已完成的階段仍會保留'),'failure note missing');
const interrupted=renderStagedProgress({state:'interrupted',progress},esc);
assert.ok(interrupted.includes('仍會保留'),'interrupted note missing');

// 4. 成功：階段完成不等於採用
const succeeded=renderStagedProgress({state:'succeeded',progress},esc);
assert.ok(succeeded.includes('再決定是否採用'),'adoption note missing');

// 5. 活動中進度 = 已完成檢查點，而非宣稱模型活動
assert.ok(running.includes('進度以已保存的階段成果為準'),'checkpoint note missing');
assert.ok(!running.includes('正在生成'),'should not claim model activity');

// 6. XSS：label 全部轉義
const xss=renderStagedProgress({state:'running',progress:{...progress,label:'<img src=x onerror=alert(1)>'}},esc);
assert.ok(!xss.includes('<img src=x'),'raw XSS label leaked');
assert.ok(xss.includes('&lt;img src=x'),'escaped label missing');
// 所有注入文字都經過 esc：原始 '<' 不應出現（標籤本身除外，檢查關鍵注入點）
assert.ok(!xss.includes('onerror=alert(1)')||xss.includes('&lt;img'));

// 7. 無按鈕在渲染器內部
for(const html of [running,failed,succeeded]){
 assert.ok(!html.includes('<button'),'button found inside renderer');
}

// 8. canResumeStages：僅 chapter_pipeline 為真 + failed/interrupted + 無取消要求
const base={input:{chapter_pipeline:true},state:'failed',error:'逾時'};
assert.equal(canResumeStages(base),true);
assert.equal(canResumeStages({...base,state:'interrupted'}),true);
assert.equal(canResumeStages({...base,state:'succeeded'}),false,'succeeded not resumable');
assert.equal(canResumeStages({...base,state:'running'}),false,'running not resumable');
assert.equal(canResumeStages({...base,state:'cancelled'}),false,'cancelled not resumable');
assert.equal(canResumeStages({input:{},state:'failed'}),false,'no chapter_pipeline');
assert.equal(canResumeStages({input:null,state:'failed'}),false);
assert.equal(canResumeStages(null),false);
assert.equal(canResumeStages({}),false);
// 取消要求
assert.equal(canResumeStages({...base,cancel_requested:true}),false,'cancel_requested blocks resume');
assert.equal(canResumeStages({...base,error:'已要求取消，等待結束'}),false,'cancel error blocks resume');
assert.equal(canResumeStages({...base,error:'其他錯誤'}),true);
// 數字非整數／負數時不顯示計數（但仍渲染）
const weird=renderStagedProgress({state:'running',progress:{kind:'chapter_stages',label:'x',completed:1.5,total:5,completed_shots:-1,total_shots:12}},esc);
assert.ok(weird.includes('staged-progress'),'weird progress still renders');
assert.ok(!weird.includes('階段 1.5'),'fractional stage count shown');
const cancelled=renderStagedProgress({...base,state:'cancelled',progress},esc);
assert.ok(cancelled.includes('章節工作已取消'));
assert.ok(!cancelled.includes('再決定是否採用'));
assert.ok(!cancelled.includes('可接續'));
const stopping=renderStagedProgress({...base,state:'running',cancel_requested:true,progress},esc);
assert.ok(stopping.includes('正在停止章節工作'));
const cannotResume=renderStagedProgress({...base,cancel_requested:true,progress},esc);
assert.ok(cannotResume.includes('此工作不能接續'));

console.log('Staged progress checks passed: absent progress, numeric counts, failure/success notes, checkpoint wording, XSS escaping, no buttons, resumable states.');

const {hasSavedStages,stagedResumeLabel}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const finalStage={...base,progress:{...progress,completed:22,total:23,completed_shots:40,total_shots:40,finalization:{completed:3,total:10,covered_units:160,total_units:663}}};
assert.equal(hasSavedStages(finalStage),true);
assert.equal(stagedResumeLabel(finalStage),'接續剩餘整理');
assert.equal(stagedResumeLabel({...base,progress}),'從中斷位置繼續');
assert.ok(renderStagedProgress(finalStage,esc).includes('全部鏡頭已保存'));
assert.ok(renderStagedProgress(finalStage,esc).includes('原文對照 160/663 段'));
const app=await readFile(new URL('../static/app.js',import.meta.url),'utf8');
assert.ok(app.includes("canResumeStages(j)&&hasSavedStages(j)?'':button"),'resumable saved work must not offer adjacent start-over action');

const adaptive={input:{generation_pipeline:'generation-stages-v1'},state:'failed',progress:{kind:'generation_stages',label:'<pending>',completed:2,total:null}};
assert(canResumeStages(adaptive));
assert(!canResumeStages({...adaptive,cancel_requested:true}));
const adaptiveHTML=renderStagedProgress(adaptive,esc);
assert(adaptiveHTML.includes('已保存 2 批')&&adaptiveHTML.includes('&lt;pending&gt;'));
assert(!adaptiveHTML.includes('/0')&&!adaptiveHTML.includes('<pending>'));
