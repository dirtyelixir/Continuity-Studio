// Drafts survive navigation/reload; only an explicit Save writes production direction.
export function createPromptDrafts(storage) {
 const memory=new Map(), key=(pid,sid,step)=>'continuity-prompt-draft:'+JSON.stringify([pid,sid,step]);
 return {
  get(pid,sid,step){const k=key(pid,sid,step);if(!memory.has(k)){try{memory.set(k,JSON.parse(storage?.getItem(k)||'null'));}catch{memory.set(k,null);}}return memory.get(k);},
  set(pid,sid,step,draft){const k=key(pid,sid,step);memory.set(k,draft);try{storage?.setItem(k,JSON.stringify(draft));}catch{}},
  clear(pid,sid,step){const k=key(pid,sid,step);memory.delete(k);try{storage?.removeItem(k);}catch{}},
 };
}
export function currentPrompt(project,sid,step){
 const scene=project.delivery.scenes.find(s=>s.scene_id===sid);
 return step==='shared'?scene?.global_prompt:scene?.chapters.find(c=>c.shot_id===step)?.shot_prompt;
}
export function promptSaveConfiguration(project,sid,step,draft){
 if(project.revision!==draft.productionRevision||currentPrompt(project,sid,step)!==draft.base)throw Error('此提示詞或分鏡已在其他地方更新。你的草稿仍然保留；請先複製草稿作備份，再放棄修改以載入最新版本。');
 if(!draft.text.trim())throw Error('提示詞不可留空；請輸入內容後再儲存。');
 const cfg=structuredClone(project.delivery.configuration);cfg.production_revision=project.revision;
 const rendered=project.delivery.scenes.find(s=>s.scene_id===sid),scene=cfg.scenes[sid]??={chapters:{}};
 // Preserve effective provider output for the rest of this scene when its hash changes.
 scene.global_prompt=rendered.global_prompt;scene.chapters??={};
 for(const shot of rendered.chapters){const ch=scene.chapters[shot.shot_id]??={};ch.shot_prompt=shot.shot_prompt;}
 const owner=step==='shared'?scene:scene.chapters[step];
 owner[step==='shared'?'global_prompt':'shot_prompt']=draft.text;owner.prompt_edited=true;
 return cfg;
}
