// Edit authored state/composition; keep derived frame prose out of the form.
export function shotStateFields(shot){
  if(!shot.canonical_state)return [
    {label:'關鍵幀 · JSON 結構',key:'keyframes',value:JSON.stringify(shot.keyframes,null,2),area:true,rows:8},
    {label:'起始狀態 · JSON 結構',key:'start_state',value:JSON.stringify(shot.start_state,null,2),area:true,rows:5},
    {label:'結束狀態 · JSON 結構',key:'end_state',value:JSON.stringify(shot.end_state,null,2),area:true,rows:5}
  ];
  return [
    {label:'畫面時刻 · JSON 結構',key:'frame_moments',value:JSON.stringify(shot.keyframes.map(f=>({id:f.id,moment:f.moment,...(f.moment==='key'?{source_time:f.source_time}:{})})),null,2),area:true,rows:5},
    {label:'時間狀態與畫面構圖 · JSON 結構',key:'canonical_state',value:JSON.stringify(shot.canonical_state,null,2),area:true,rows:14}
  ];
}

export function applyShotStateFields(shot,values){
  if(!shot.canonical_state){
    for(const k of ['keyframes','start_state','end_state'])shot[k]=JSON.parse(values[k]);
    return;
  }
  const canonical=JSON.parse(values.canonical_state);
  if(!canonical||canonical.version!=='canonical-shot-state-v1')throw Error('請保留時間狀態格式及版本。');
  const frames=JSON.parse(values.frame_moments);
  if(!Array.isArray(frames))throw Error('畫面時刻必須是清單。');
  const old=new Map(shot.keyframes.map(f=>[f.id,f]));
  shot.keyframes=frames.map(f=>{
    if(Object.keys(f).some(k=>!['id','moment','source_time'].includes(k)))throw Error('畫面時刻只填 ID、moment 及 source_time；狀態與構圖請在下方修改。');
    return {id:f.id,moment:f.moment,description:old.get(f.id)?.description||'',
      ...(f.moment==='key'?{source_time:f.source_time,state:old.get(f.id)?.state||[]}:{})};
  });
  shot.canonical_state=canonical;
}
