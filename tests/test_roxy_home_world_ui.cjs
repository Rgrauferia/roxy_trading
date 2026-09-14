'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const source=fs.readFileSync(require.resolve('../assets/roxy_home_world.js'),'utf8');
const settle=async()=>{for(let i=0;i<45;i++)await Promise.resolve();};
function harness({pending=false}={}){
  const events={},calls=[],starts=[],nodes=[],timers=new Map();let timerId=0,resolveSpeech;
  const waiting=new Promise(r=>resolveSpeech=r);
  class Element {
    constructor(tag){this.tag=tag;this.children=[];this.events={};this.attrs={};this.dataset={};this.style={};this.isConnected=true;this._text='';this.classList={toggle(){},add(){},remove(){}};nodes.push(this);}
    get textContent(){return this._text+this.children.map(n=>n.textContent||'').join('');}set textContent(v){this._text=String(v);}
    append(...items){this.children.push(...items);items.forEach(item=>item.parent=this);}
    replaceChildren(...items){this.children=[];this._text='';this.append(...items);}
    setAttribute(k,v){this.attrs[k]=String(v);}removeAttribute(k){delete this.attrs[k];}
    addEventListener(k,fn){this.events[k]=fn;}focus(){document.activeElement=this;}showModal(){this.open=true;}close(){this.open=false;}
    remove(){this.isConnected=false;if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);}
    querySelectorAll(selector){const all=[];const visit=n=>{for(const child of n.children){if(selector.split(',').includes(child.tag))all.push(child);visit(child);}};visit(this);return all;}
    querySelector(selector){return this.querySelectorAll(selector)[0]||null;}pause(){}load(){}
  }
  const document={hidden:false,createElement:tag=>new Element(tag),body:new Element('body'),addEventListener:(k,fn)=>events[k]=fn};
  class AudioContext {
    constructor(){this.state='suspended';this.destination={};}resume(){this.state='running';return Promise.resolve();}close(){this.state='closed';return Promise.resolve();}
    createGain(){return{connect(){},gain:{value:1}};}decodeAudioData(){return Promise.resolve({duration:4});}
    createBufferSource(){return{connect(){},disconnect(){},start(){starts.push(this);},stop(){this.stopped=true;}};}
  }
  const preferences={theme:'classic',avatar:'home',response_style:'balanced',background:'plant',text_scale:'standard'};
  const envelope={member_id:'member-a',version:1,revision:0,progress:null,personalization:{display_name:'Example',preferences},chapters:[],world:{version:1,entry_image:'/entry.png',speech:{'world-name':'Your name?','world-theme':'Choose a colour.'},films:{}}};
  const response={ok:true,blob:async()=>new Blob([new Uint8Array(2048)],{type:'audio/mpeg'})};
  const window={document,AudioContext,matchMedia:()=>({matches:false}),addEventListener:(k,fn)=>events[k]=fn};
  const fetcher=async(path,options)=>{calls.push({path,options});if(path.endsWith('/speech'))return pending?waiting:response;return{ok:true,json:async()=>JSON.parse(JSON.stringify(envelope))};};
  vm.runInNewContext(source,{window,document,fetch:fetcher,AbortController,Blob,setTimeout:(fn,ms)=>{timers.set(++timerId,{fn,ms});return timerId;},clearTimeout:id=>timers.delete(id)});
  const api=window.RoxyHomeWorld,owner={identity:'member-a',version:2,isCurrent:()=>true};api.bind(owner);
  const dialog=()=>nodes.findLast(n=>n.tag==='dialog'&&n.open);
  const click=async text=>{const button=dialog().querySelectorAll('button').find(n=>n.textContent===text);assert.ok(button,`Button ${text}`);button.events.click();await settle();};
  return{api,owner,calls,starts,events,document,dialog,click,timers,resolveSpeech:()=>resolveSpeech(response)};
}
test('entering unlocks one audio context and starts exactly one fixed-script request',async()=>{
  const h=harness();await h.api.open();assert.equal(h.calls.filter(c=>c.path.endsWith('/speech')).length,0);
  await h.click('Entrar con Roxy  ↗');const speech=h.calls.filter(c=>c.path.endsWith('/speech'));
  assert.equal(speech.length,1);assert.deepEqual(JSON.parse(speech[0].options.body),{chapter:'world-name'});
  assert.equal(speech[0].options.headers['X-Roxy-Member-Id'],'member-a');assert.equal(h.starts.length,1);
  const form=h.dialog().querySelector('form');form.querySelector('input').value='Changed locally';form.events.submit({preventDefault(){}});await settle();
  assert.equal(h.starts.length,2);assert.equal(h.starts[0].stopped,true);
  assert.deepEqual(JSON.parse(h.calls.filter(c=>c.path.endsWith('/speech'))[1].options.body),{chapter:'world-theme'});
  assert.equal(h.calls.some(c=>c.path.endsWith('/personalization')),false);h.api.close();
});
for(const change of ['close','member','hidden','mute'])test(`late audio cannot play after ${change}`,async()=>{
  const h=harness({pending:true});await h.api.open();await h.click('Entrar con Roxy  ↗');
  if(change==='close')h.api.close();if(change==='member')h.api.bind({...h.owner,identity:'member-b'});
  if(change==='hidden'){h.document.hidden=true;h.events.visibilitychange();}if(change==='mute')await h.click('Silenciar');
  h.resolveSpeech();await settle();assert.equal(h.starts.length,0);
  assert.equal(h.calls.find(c=>c.path.endsWith('/speech')).options.signal.aborted,true);h.api.close();
});
test('silent entry never contacts the voice service and can still configure',async()=>{
  const h=harness();await h.api.open();await h.click('Entrar sin sonido');assert.equal(h.starts.length,0);
  assert.equal(h.calls.some(c=>c.path.endsWith('/speech')),false);assert.ok(h.dialog().querySelector('form'));h.api.close();
});
test('overall audio deadline prevents late decode or provider output from starting',async()=>{
  const h=harness({pending:true});await h.api.open();await h.click('Entrar con Roxy  ↗');
  [...h.timers.values()].find(t=>t.ms===35000).fn();h.resolveSpeech();await settle();assert.equal(h.starts.length,0);h.api.close();
});
