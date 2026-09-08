'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../assets/roxy_fitness_catalog.js'),'utf8');
const api=require('../assets/roxy_fitness_catalog.js');
const data=require('../data/home_fitness_catalog.json');
const payload={clinical_approval:false,can_activate_training:false,entries:data.entries};
const clone=x=>JSON.parse(JSON.stringify(x));
const flush=()=>new Promise(resolve=>setImmediate(resolve));

test('all eight originals and sixteen exact-source illustrations render',()=>{
  const entries=api.validatedEntries(payload);
  assert.equal(entries.length,8);assert.equal(entries.flatMap(x=>x.images).length,16);
  for(const e of entries){const html=api.detail(e);assert.match(html,/Indicaciones originales/);assert.match(html,/Revisión profesional de Roxy: pendiente/);assert.match(html,/Everkinetic/);assert.match(html,/CC-BY-SA/);assert.match(html,/no-referrer/);assert.doesNotMatch(html,/Comenzar entrenamiento|FDA approved/);assert.equal((html.match(/<img /g)||[]).length,e.images.length);assert.ok(html.includes(e.source_url));}
});
test('unavailable or purported clinical approvals never enter educational UI',()=>{
  assert.throws(()=>api.validatedEntries({...payload,status:'catalogue_unavailable'}));
  assert.throws(()=>api.validatedEntries({...payload,clinical_approval:true}));
  assert.throws(()=>api.validatedEntries({...payload,can_activate_training:true}));
  const altered=clone(payload);altered.entries[0].can_activate_training=true;
  assert.equal(api.validatedEntries(altered).length,7);
});
test('unsafe sources, media, missing prose, duplicates and missing attribution are rejected',()=>{
  for(const mutate of [e=>e.images[0].url='https://evil.example/a.png',e=>e.source_url='javascript:alert(1)',e=>e.attribution.license_url='https://example.org/license',e=>e.instructions=[],e=>e.images=[],e=>e.images[0].author='']){
    const altered=clone(payload);mutate(altered.entries[0]);assert.equal(api.validatedEntries(altered).length,7);
  }
  assert.equal(api.validatedEntries({...payload,entries:[...data.entries,data.entries[0]]}).length,8);
  for(const url of ['javascript:alert(1)','http://wger.de/x','https://wger.de.evil.test/x','https://wger.de@evil.test/x'])assert.equal(api.safeLink(url),'');
  for(const url of ['https://wger.de/media/a.svg','https://evil.test/media/x.jpg','https://wger.de/media/a.png?redirect=evil'])assert.equal(api.safeImage(url),'');
});
test('filters accept accents, translated groups and equipment without inventing results',()=>{
  assert.equal(api.selectEntries(data.entries,{query:'biceps'}).length,2);
  assert.equal(api.selectEntries(data.entries,{query:'piernas'}).length,2);
  assert.equal(api.selectEntries(data.entries,{query:'mancuerna'}).length,3);
  assert.equal(api.selectEntries(data.entries,{category:'Arms',equipment:'1'}).length,1);
  assert.equal(api.selectEntries(data.entries,{query:'dragones'}).length,0);
});
test('all source text is escaped rather than interpreted as provider HTML',()=>{
  const e=clone(data.entries[0]);e.name='<img src=x onerror=alert(1)>';e.instructions=['<script>alert(1)</script>'];e.attribution.authors=['<b>author</b>'];
  const html=api.detail(e);assert.doesNotMatch(html,/<script>|<b>author|<img src=x/);assert.match(html,/&lt;script&gt;/);assert.match(html,/&lt;b&gt;author/);
});

function harness(){
  const queue=[],requests=[];
  const context={AbortController,console,FormData:class{constructor(target){this.values=target.values;}get(k){return this.values[k];}},fetch:async(url,opts)=>{requests.push({url,opts});const item=queue.shift();if(item instanceof Error)throw item;return await item;}};
  context.window=context;vm.createContext(context);vm.runInContext(source,context);
  const events={};let html='';const root={get innerHTML(){return html;},set innerHTML(v){html=v;},addEventListener:(k,v)=>events[k]=v,querySelectorAll:()=>[],querySelector:()=>({focus(){}}),scrollIntoView(){}};
  return {api:context.RoxyFitnessLibrary,root,events,queue,requests};
}
const response=(body,status=200)=>({ok:status===200,status,json:async()=>clone(body)});
test('mount uses one same-origin no-store read; filters never post preferences',async()=>{
  const h=harness();h.queue.push(response(payload));h.api.mount(h.root);await flush();
  assert.equal(h.requests.length,1);assert.equal(h.requests[0].url,'/api/fitness/v1/exercises');assert.equal(h.requests[0].opts.cache,'no-store');assert.equal(h.requests[0].opts.credentials,'same-origin');assert.equal(h.requests[0].opts.body,undefined);
  let stopped=false;h.events.submit({preventDefault(){},stopPropagation(){stopped=true;},target:{values:{query:'zzzz',category:'',equipment:''}}});
  assert.equal(stopped,true);assert.match(h.root.innerHTML,/No hay coincidencias/);assert.equal(h.requests.length,1);
});
test('late response after clear cannot repopulate a prior screen',async()=>{
  const h=harness();let resolve;h.queue.push(new Promise(r=>resolve=r));h.api.mount(h.root);const pending=h.root.innerHTML;h.api.clear();resolve(response(payload));await flush();assert.equal(h.root.innerHTML,pending);assert.equal(h.requests[0].opts.signal.aborted,true);
});
test('network/auth failures provide a retry rather than fabricated exercises',async()=>{
  for(const value of [new Error('Sin conexión'),response({},401),response({},503)]){
    const h=harness();h.queue.push(value);h.api.mount(h.root);await flush();assert.match(h.root.innerHTML,/role="alert"/);assert.match(h.root.innerHTML,/Volver a cargar/);assert.doesNotMatch(h.root.innerHTML,/data-exercise-id/);
  }
});
