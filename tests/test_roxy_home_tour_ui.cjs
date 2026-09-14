'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../assets/roxy_home_tour.js'),'utf8');
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return{promise,resolve};};
const settle=async()=>{for(let i=0;i<20;i++)await Promise.resolve();};
function harness({fetcher,denyPlay=false}={}){
  const listeners={},nodes=[],calls=[],revoked=[],statuses=[],timers=new Map();let id=0;
  class Node {
    constructor(tag){this.tag=tag;this.events={};this.children=[];this.attrs={};this.paused=true;this.isConnected=false;nodes.push(this);}
    setAttribute(k,v){this.attrs[k]=v;} removeAttribute(k){delete this.attrs[k];}
    append(n){this.children.push(n);n.parent=this;n.isConnected=true;}
    addEventListener(k,fn){this.events[k]=fn;}
    pause(){this.paused=true;this.events.pause?.();} load(){}
    remove(){this.isConnected=false;if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);}
    async play(){if(denyPlay){const error=new Error('User gesture needed');error.name='NotAllowedError';throw error;}this.paused=false;this.events.playing?.();}
  }
  const document={hidden:false,body:new Node('body'),createElement:tag=>new Node(tag),addEventListener:(k,fn)=>listeners[k]=fn};
  const window={speechSynthesis:{speak(){throw new Error('Forbidden device fallback');}}};window.window=window;window.document=document;
  const response=(status=200)=>({ok:status===200,status,blob:async()=>new Blob([new Uint8Array(2048)],{type:'audio/mpeg'}),json:async()=>({detail:{message:'Voz oficial no disponible'}})});
  vm.runInNewContext(source,{window,document,AbortController,Blob,URL:{createObjectURL:()=> 'blob:synthetic',revokeObjectURL:url=>revoked.push(url)},setTimeout:(fn,ms)=>{timers.set(++id,{fn,ms});return id;},clearTimeout:i=>timers.delete(i),fetch:async(path,options)=>{calls.push({path,options});return fetcher?fetcher(path,options):response();}});
  const api=window.RoxyHomeTour,ctx={identity:'member-a',version:2,isCurrent:()=>true};api.bind(ctx);
  const speak=chapter=>api.speak(chapter,(state,message)=>statuses.push({state,message}));
  return{api,ctx,document,nodes,calls,revoked,statuses,timers,speak,response,hide:()=>{document.hidden=true;listeners.visibilitychange();}};
}
test('only explicit playback calls official fixed-script route, with member/session and no personal text',async()=>{
  const h=harness();assert.equal(h.calls.length,0);await h.speak('welcome');
  const call=h.calls[0];assert.equal(call.path,'/v1/home-tour/speech');assert.equal(call.options.method,'POST');assert.deepEqual(JSON.parse(call.options.body),{chapter:'welcome'});assert.equal(call.options.headers['X-Roxy-Member-Id'],'member-a');assert.equal(call.options.headers['X-Roxy-Session-Version'],'2');assert.equal(call.options.credentials,'same-origin');assert.equal(call.options.cache,'no-store');assert.ok(h.statuses.some(s=>s.state==='playing'));h.api.stop();
});
test('stopping cancels transport, removes the audio and revokes blob URLs',async()=>{
  const h=harness();await h.speak('plants');h.api.stop();assert.equal(h.calls[0].options.signal.aborted,true);assert.deepEqual(h.revoked,['blob:synthetic']);assert.equal(h.document.body.children.length,0);assert.equal(h.timers.size,0);
});
for(const change of ['identity','version','hidden','close'])test(`late transport cannot play after ${change}`,async()=>{
  const pending=deferred(),h=harness({fetcher:()=>pending.promise});const job=h.speak('welcome');
  if(change==='identity')h.api.bind({...h.ctx,identity:'member-b'});
  if(change==='version')h.api.bind({...h.ctx,version:3});
  if(change==='hidden')h.hide();if(change==='close')h.api.stop();
  pending.resolve(h.response());await job;assert.equal(h.nodes.some(n=>n.tag==='audio'),false);assert.equal(h.api.isPlaying(),false);
});
test('quiet same-member binding keeps an in-flight narration valid',async()=>{
  const pending=deferred(),h=harness({fetcher:()=>pending.promise});const job=h.speak('welcome');h.api.bind({...h.ctx});pending.resolve(h.response());await job;assert.ok(h.statuses.some(s=>s.state==='playing'));h.api.stop();
});
test('autoplay rejection retains a visible audio control and never claims speaking',async()=>{
  const h=harness({denyPlay:true});await h.api.speak('calendar',(state,message)=>h.statuses.push({state,message}),h.document.body);assert.ok(h.statuses.some(s=>s.state==='ready'));assert.equal(h.statuses.some(s=>s.state==='playing'),false);const audio=h.document.body.children[0];assert.equal(audio.controls,true);assert.notEqual(audio.hidden,true);assert.equal(h.timers.size,0);h.api.stop();
});
test('a background announcement blocked by autoplay ends instead of offering hidden controls',async()=>{
  const h=harness({denyPlay:true});await h.speak('timer-finished');assert.equal(h.statuses.at(-1).state,'error');assert.equal(h.api.isPlaying(),false);assert.equal(h.document.body.children.length,0);
});
test('provider error remains an error and never invokes device speech',async()=>{
  const h=harness({fetcher:async()=>({ok:false,status:503,json:async()=>({detail:{message:'Voz oficial no disponible'}})})});await h.speak('welcome');assert.equal(h.statuses.at(-1).state,'error');assert.equal(h.nodes.some(n=>n.tag==='audio'),false);assert.equal(h.api.isPlaying(),false);
});
test('deadline cancels a stalled provider and ignores its late audio',async()=>{
  const pending=deferred(),h=harness({fetcher:()=>pending.promise});const job=h.speak('welcome');[...h.timers.values()][0].fn();assert.equal(h.calls[0].options.signal.aborted,true);pending.resolve(h.response());await job;assert.equal(h.statuses.at(-1).state,'error');assert.equal(h.nodes.some(n=>n.tag==='audio'),false);
});
