// Read-only task summary. Backend image tokens and scene readiness own approval.
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function boardItems(p,sceneId){
 return (p.storyboard?.scenes||[]).filter(s=>!sceneId||s.scene_id===sceneId).flatMap(scene=>(scene.panels||[]).flatMap(panel=>(panel.anchors||[]).map(anchor=>({scene,panel,anchor}))));
}
export const needsBoardRevision=a=>a.review?.verdict==='revise'&&(!a.review.fingerprint?.asset_id||a.review.fingerprint.asset_id===a.asset?.id);
export function boardTask(p,sceneId){
 const scenes=(p.storyboard?.scenes||[]).filter(s=>!sceneId||s.scene_id===sceneId),items=boardItems(p,sceneId);
 const approved=items.filter(x=>x.anchor.ready&&!x.scene.stale).length;
 const missing=items.filter(x=>!x.anchor.asset).length;
 const revising=items.filter(x=>!x.anchor.ready&&needsBoardRevision(x.anchor)).length;
 const pending=items.filter(x=>!x.scene.stale&&x.scene.adopted&&x.anchor.asset&&!x.anchor.ready&&!needsBoardRevision(x.anchor));
 const needsPlan=scenes.find(s=>s.stale||!s.adopted),next=pending[0];
 const scene=next?.scene||needsPlan||scenes.find(s=>!s.ready),complete=scenes.length>0&&scenes.every(s=>s.ready);
 const unresolved=scenes.find(s=>s.unresolved_constraints?.length),recoverable=scenes.flatMap(s=>(s.candidates||[]).filter(c=>c.usable&&!c.adopted)).length;
 const title=unresolved?'圖板有未解決嘅用圖約束':complete?'分鏡畫面已全部確認':pending.length?`${pending.length} 格畫面等你確認`:needsPlan?'先確認分鏡畫面安排':revising?`${revising} 格畫面需要修改`:missing?`還欠 ${missing} 格畫面`:'分鏡畫面準備中';
 const label=unresolved?'查看約束同可行下一步':next?'開始審閱畫面':needsPlan?'查看畫面安排':revising?'查看需修改畫面':'查看缺少畫面';
 return {items,scenes,approved,missing,revising,pending,next,scene,complete,title,label,unresolved,recoverable};
}
export function renderBoardNext(p,sceneId){
 const t=boardTask(p,sceneId);if(!t.scenes.length||t.complete)return '';
 return `<section class="board-next" aria-label="分鏡畫面待辦"><div><span class="eyebrow">分鏡畫面審閱</span><h2>${esc(t.title)}</h2><p>已確認 ${t.approved}／${t.items.length} 格${t.missing?' · 欠 '+t.missing+' 張圖':''}${t.revising?' · '+t.revising+' 格需修改':''}。${t.unresolved?(t.recoverable?'圖板有一個未有執行策略嘅約束，所以唔會生圖或交去 H3。可行做法：檢視並採用較早嘅成功方案，或重新判斷用圖需要。':'圖板有一個未有執行策略嘅約束，所以唔會生圖或交去 H3。請重新判斷用圖需要，或先修訂來源。'):t.pending.length?'打開圖片，確認人物、動作同連戲；每次只處理一格。':'開啟分鏡畫面，查看目前安排及待處理事項。'}</p></div><button type="button" class="primary" data-board-action="continue" data-scene="${esc(t.scene?.scene_id)}">${esc(t.label)} →</button></section>`;
}
