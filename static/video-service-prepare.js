// Only service preparation is retried after a proven pre-admission refusal.
// Never wrap generation, upload, timeout or ambiguous transport errors here.
export async function prepareVideoService(api,{notify=()=>{},wait=ms=>new Promise(resolve=>setTimeout(resolve,ms)),now=Date.now,timeoutMs=180000}={}){
 const deadline=now()+timeoutMs;
 while(true){
  try{return await api('/video-provider/prepare',{});}
  catch(error){
   if(!String(error.message).includes('VRAM Manager 已暫停或正在切換；尚未送出生成。'))throw error;
   const remaining=deadline-now();
   if(remaining<=0)throw Error('VRAM Manager 仍未開放工作；如已暫停，請先恢復接收。尚未開始生成影片。');
   notify('正在等候 VRAM Manager；切換完成後會自動準備 H3。若已手動暫停，需先恢復接收工作。');
   await wait(Math.min(2000,remaining));
  }
 }
}
