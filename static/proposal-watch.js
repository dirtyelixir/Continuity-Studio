// Only observe the open proposal. Closing/replacing its dialog cancels delivery
// of an in-flight read as well as the next timer; this never submits work.
export function watchProposal({read,render,onError,isCurrent,setTimer=setTimeout,clearTimer=clearTimeout,interval=4000}){
 let stopped=false,timer;
 async function tick(){
  if(stopped||!isCurrent())return;
  try{const value=await read();if(!stopped&&isCurrent())render(value);}
  catch(error){if(!stopped&&isCurrent())onError(error);}
  if(!stopped&&isCurrent())timer=setTimer(tick,interval);
 }
 timer=setTimer(tick,interval);
 return ()=>{stopped=true;clearTimer(timer);};
}
