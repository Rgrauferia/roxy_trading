/* First basemap readiness only. Never fetches, retries or changes a map view. */
(function(root){
  'use strict';
  function create(options={}){
    const onState=typeof options.onState==='function'?options.onState:()=>{};
    const isCurrent=typeof options.isCurrent==='function'?options.isCurrent:()=>true;
    const delay=Number.isFinite(options.timeoutMs)?Math.max(1000,Math.min(30000,options.timeoutMs)):12000;
    let map=null,listener=null,timer=null,generation=0,phase='idle',active=true,disposed=false;
    const snapshot=()=>Object.freeze({phase,active,canRetry:phase==='delayed'});
    function clearTimer(){if(timer!==null){root.clearTimeout(timer);timer=null}}
    function clearListener(){if(listener){listener.remove?.();listener=null}}
    function current(){
      if(disposed)return false;
      if(isCurrent())return true;
      dispose();return false;
    }
    function notify(){if(active&&current())onState(snapshot())}
    function arm(){
      clearTimer();
      if(!active||phase!=='loading'||!map||!current())return;
      const expected=generation;
      const scheduled=root.setTimeout(()=>{
        if(expected!==generation||timer!==scheduled)return;
        timer=null;
        if(!active||!current()||phase!=='loading')return;
        // No tile event is evidence of delay, not proof of network/auth failure.
        phase='delayed';notify();
      },delay);
      timer=scheduled;
    }
    function attach(nextMap){
      if(!current())return snapshot();
      if(nextMap===map)return snapshot();
      if(!nextMap||typeof nextMap.addListener!=='function')throw new TypeError('A map event source is required');
      clearTimer();clearListener();generation++;map=nextMap;phase='loading';
      const expected=generation;
      listener=map.addListener('tilesloaded',()=>{
        if(expected!==generation||!current())return;
        phase='ready';clearTimer();clearListener();notify();
      });
      notify();arm();return snapshot();
    }
    function setActive(value){
      if(!current())return snapshot();
      const next=Boolean(value);
      if(next===active)return snapshot();
      active=next;
      if(active){notify();arm()}else clearTimer();
      return snapshot();
    }
    function dispose(){
      if(disposed)return;
      disposed=true;generation++;clearTimer();clearListener();map=null;phase='idle';active=false;
    }
    return Object.freeze({attach,setActive,getState:snapshot,dispose});
  }
  root.RoxyMapReadiness=Object.freeze({create});
})(typeof window!=='undefined'?window:globalThis);
