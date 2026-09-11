'use strict';
// Synthetic in-memory DOM/network only. No accounts, browser data or live APIs.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const filename = path.join(__dirname,'../assets/roxy_fitness.js');
const source = fs.readFileSync(filename,'utf8');
const {weekDates,validateAvailability,defaults,validTimezone} = require(filename);
const deep = value=>JSON.parse(JSON.stringify(value));
const consent = {purpose:'fitness_preferences',text_version:'fitness-preferences-v1',granted:true};
const stored = (profile=null,version=1)=>({version,profile,consent:deep(consent)});
const empty = version=>({version,profile:null,consent:null});
const activeStatus = {personal_login:true,member_id:'member-a',storage:{configured:true},education:[]};
const response = (body,status=200)=>({ok:status>=200&&status<300,status,json:async()=>deep(body)});
const deferred = ()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
const flush = ()=>new Promise(resolve=>setImmediate(resolve));

function harness() {
  const requests=[],queue=[],events=new Map(),downloads=[],programCalls=[],deadlines=new Map();
  const form={values:new Map(),times:new Map(),querySelector(selector){const day=selector.match(/data-day="([^"]+)"/)?.[1],index=selector.match(/data-window="([^"]+)"/)?.[1],part=selector.match(/data-time="([^"]+)"/)?.[1];return this.times.get(`${day}:${index}:${part}`)||null;}};
  const controls=[{disabled:false},{disabled:false},{disabled:false}];
  let html='',renderCount=0,focus='';
  const heading={focus:()=>{focus='heading';}},alert={focus:()=>{focus='alert';}},windows={innerHTML:''};
  const root={
    set innerHTML(value){html=value;renderCount++;controls.forEach(c=>{c.disabled=false;});},get innerHTML(){return html;},
    querySelector(selector){if(selector==='#fxForm')return html.includes('id="fxForm"')?form:null;if(selector==='h2')return heading;if(selector==='[role="alert"]')return alert;if(selector==='#fxWindows')return windows;return form.querySelector(selector)||{hidden:false,focus:()=>{focus=selector;}};},
    querySelectorAll(selector){if(selector==='button,input,select,textarea')return controls;if(selector==='[role="tab"]')return tabs;return [];},
    addEventListener(){},removeEventListener(){},scrollIntoView(){}
  };
  const tabs=['today','week','library','progress','food','services'].map(key=>({dataset:{fxTab:key},getAttribute:()=> 'tab',click:()=> api.click({target:{closest:()=>tabs.find(x=>x.dataset.fxTab===key)}})}));
  const context={console,Intl,Date,Map,AbortController,Blob,crypto:webcrypto,
    setTimeout(fn,ms){const timer=setTimeout(fn,ms);if(ms===12000)deadlines.set(timer,fn);return timer;},
    clearTimeout(timer){deadlines.delete(timer);clearTimeout(timer);},
    RoxyFitnessPrograms:{mount(node,options){programCalls.push({type:'mount',options});},clear(){programCalls.push({type:'clear'});},setActive(active){programCalls.push({type:'active',active});}},
    URL:{createObjectURL:()=> 'blob:synthetic',revokeObjectURL(){}},
    document:{createElement:()=>({click(){downloads.push(this.download);}})},
    FormData:class {constructor(node){this.node=node;}get(name){const value=this.node.values.get(name);return Array.isArray(value)?value[0]??null:value??null;}getAll(name){const value=this.node.values.get(name);return value===undefined?[]:Array.isArray(value)?value:[value];}has(name){return this.node.values.has(name);}},
    addEventListener:(name,callback)=>events.set(name,callback),
    fetch:async(url,options)=>{requests.push({url,...options,payload:options.body?JSON.parse(options.body):undefined});if(!queue.length)throw new Error('Unexpected synthetic request '+url);const next=queue.shift();if(next instanceof Error)throw next;return typeof next==='function'?await next(url,options):next;}
  };
  context.window=context;
  vm.createContext(context);
  const instrumented=source.replace('scope.RoxyFitness={mount,clear,setActive};',`scope.RoxyFitness={mount,clear,setActive};scope.__test={mount,clear,setActive,load,collect,submit,erase,exportData,click,keys,render,space,settings,onboarding,windows,week,acceptSnapshot,saveLabel,dirty,
    configure(values){if(values.root)root=values.root;if(values.context)context=values.context;if(values.identity!==undefined)identity=values.identity;if(values.profile)profile=clone(values.profile);if(values.snapshot)acceptSnapshot(values.snapshot,!!values.replaceDraft);if(values.status!==undefined)status=values.status;if(values.ready!==undefined)ready=values.ready;if(values.view)view=values.view;if(values.step!==undefined)step=values.step;if(values.consentChecked!==undefined)consentChecked=values.consentChecked;if(values.remoteUncertain!==undefined)remoteUncertain=values.remoteUncertain;if(values.section)section=values.section;},
    current(){return clone({profile,snapshot,saved,busy,notice,failure,ready,view,step,section,remoteUncertain,identity,generation,checkingIdentity});}};`);
  vm.runInContext(instrumented,context,{filename});
  const api=context.__test;
  api.clear();api.configure({root,context:{identity:'member-a',navigate(){}},identity:'member-a'});
  return {api,root,form,controls,queue,requests,events,downloads,tabs,programCalls,deadlines,get renderCount(){return renderCount;},get focus(){return focus;},action(key){api.click({target:{closest:()=>({dataset:{fx:key}})}});}};
}

test('today and week mount the same program component without turning availability into a prescription',()=>{
  const h=harness();h.api.configure({view:'space',section:'today'});h.api.render();
  assert.equal(h.programCalls.at(-1).options.view,'today');
  assert.equal(h.programCalls.at(-1).options.identity,'member-a');
  h.api.configure({section:'week'});h.api.render();
  assert.equal(h.programCalls.at(-1).options.view,'week');
  assert.match(h.root.innerHTML,/Mi disponibilidad declarada/);
  assert.match(h.root.innerHTML,/no asignan ejercicios/);
});

test('welcome offers a source agenda directly without requiring health preferences',()=>{
  const h=harness();h.api.render();assert.match(h.root.innerHTML,/Organizar mis días/);
  h.action('week');assert.equal(h.api.current().view,'space');assert.equal(h.api.current().section,'week');
  assert.equal(h.requests.length,0);assert.equal(h.api.current().saved,false);
});

test('leaving exercise cancels a request and removes visible personal content',async()=>{
  const h=harness(),pending=deferred();h.queue.push(pending.promise);const loading=h.api.load();
  await flush();h.api.setActive(false);assert.equal(h.requests[0].signal.aborted,true);
  pending.resolve(response(activeStatus));await loading;assert.equal(h.root.innerHTML,'');
  assert.deepEqual(h.programCalls.at(-1),{type:'active',active:false});assert.equal(h.deadlines.size,0);
});

test('returning to exercise revalidates the member before loading a profile',async()=>{
  const h=harness();h.api.setActive(false);h.queue.push(response(activeStatus),response(stored({...defaults(),primary_goal:'strength'})));
  h.api.setActive(true);await flush();
  assert.deepEqual(h.requests.map(r=>r.url),['/api/fitness/v1/status','/api/fitness/v1/me/profile']);
  assert.equal(h.api.current().ready,true);assert.equal(h.deadlines.size,0);
});

test('a resumed module masks old preferences until the same member is confirmed',async()=>{
  const h=harness(),pending=deferred(),profile={...defaults(),primary_goal:'fat_loss'};
  h.api.configure({view:'space',section:'today',status:activeStatus,ready:true,snapshot:stored(profile),replaceDraft:true});h.api.render();
  h.api.setActive(false);h.queue.push(pending.promise,response(stored(profile)));h.api.setActive(true);
  assert.equal(h.api.current().checkingIdentity,true);assert.equal(h.api.current().busy,true);
  assert.match(h.root.innerHTML,/Comprobando tu espacio privado/);
  assert.doesNotMatch(h.root.innerHTML,/Reducir grasa o peso|Mis preferencias|fxPrograms|Preferencias personales guardadas/);
  pending.resolve(response(activeStatus));await flush();
  assert.equal(h.api.current().checkingIdentity,false);assert.match(h.root.innerHTML,/Reducir grasa o peso/);
});

test('failed revalidation keeps the mask and retry until identity is actually confirmed',async()=>{
  const h=harness(),profile={...defaults(),primary_goal:'fat_loss'};
  h.api.configure({view:'space',status:activeStatus,ready:true,snapshot:stored(profile),replaceDraft:true});h.api.render();
  h.api.setActive(false);h.queue.push(new TypeError('offline'));h.api.setActive(true);await flush();
  assert.equal(h.api.current().checkingIdentity,true);assert.equal(h.api.current().busy,false);
  assert.match(h.root.innerHTML,/Volver a comprobar/);assert.doesNotMatch(h.root.innerHTML,/Reducir grasa o peso|fxPrograms/);
  h.action('week');assert.equal(h.api.current().section,'today');
  h.queue.push(response(activeStatus),response(stored(profile)));h.action('retry');await flush();
  assert.equal(h.api.current().checkingIdentity,false);assert.match(h.root.innerHTML,/Reducir grasa o peso/);
});

for(const malformed of [{},{personal_login:true,storage:{configured:false}},{personal_login:false,storage:{}},{personal_login:'true',member_id:'member-a',storage:{configured:false}}])test(`malformed status cannot unmask a draft: ${JSON.stringify(malformed)}`,async()=>{
  const h=harness();h.api.configure({view:'space',profile:{...defaults(),primary_goal:'fat_loss'}});
  h.queue.push(response(malformed));await h.api.load(true);
  assert.equal(h.api.current().checkingIdentity,true);assert.match(h.root.innerHTML,/Volver a comprobar/);
  assert.doesNotMatch(h.root.innerHTML,/Reducir grasa o peso|fxPrograms/);assert.equal(h.requests.length,1);
});

test('leaving captures the unsubmitted current step and restores it only for the same member',async()=>{
  const h=harness();h.api.configure({view:'onboarding',step:1,status:activeStatus,ready:true});h.api.render();
  h.form.values.set('primary_goal','strength');h.form.values.set('without_weight_or_calories','on');
  h.api.setActive(false);assert.equal(h.api.current().profile.primary_goal,'strength');assert.equal(h.root.innerHTML,'');
  h.queue.push(response(activeStatus),response(empty(0)));h.api.setActive(true);await flush();
  assert.equal(h.api.current().profile.primary_goal,'strength');assert.match(h.root.innerHTML,/value="strength" checked/);
});

test('leaving captures the consent checkbox before disabling original save eligibility',()=>{
  const h=harness();h.api.configure({view:'onboarding',step:4,status:activeStatus,ready:true});h.api.render();h.form.values.set('consent','on');
  h.api.setActive(false);assert.equal(h.api.current().ready,false);
  // Returning without storage cannot silently reuse it; with storage the choice
  // remains a draft until the user explicitly submits the form.
  h.queue.push(response(activeStatus),response(empty(0)));
  h.api.setActive(true);
  return flush().then(()=>{assert.match(h.root.innerHTML,/name="consent"[^>]*checked/);assert.equal(h.requests.filter(r=>r.method!=='GET').length,0);});
});

test('a shared-session downgrade discards an unsaved personal draft too',async()=>{
  const h=harness();h.api.configure({view:'space',profile:{...defaults(),primary_goal:'fat_loss'},status:activeStatus,ready:true});
  h.queue.push(response({personal_login:false,member_id:null,storage:{configured:false},education:[]}));await h.api.load(true);
  assert.equal(h.api.current().profile.primary_goal,null);assert.equal(h.api.current().view,'welcome');
  assert.equal(h.api.current().checkingIdentity,false);assert.doesNotMatch(h.root.innerHTML,/Reducir grasa o peso/);
});

test('a late unauthorized response from the previous identity cannot erase the current profile',async()=>{
  const h=harness(),pending=deferred();h.queue.push(pending.promise);const old=h.api.load();await flush();
  h.api.clear();h.api.configure({identity:'member-b',context:{identity:'member-b'},snapshot:stored({...defaults(),primary_goal:'muscle_gain'}),replaceDraft:true});
  pending.resolve(response({detail:{code:'identity_changed'}},401));await old;
  assert.equal(h.api.current().profile.primary_goal,'muscle_gain');assert.equal(h.api.current().identity,'member-b');
});

test('a stalled connection has a bounded deadline with a useful error and no false save',async()=>{
  const h=harness(),pending=deferred();h.queue.push(pending.promise);const loading=h.api.load();await flush();
  assert.equal(h.deadlines.size,1);[...h.deadlines.values()][0]();await loading;
  assert.match(h.api.current().failure,/tardó demasiado/);assert.equal(h.api.current().saved,false);
  assert.equal(h.api.current().busy,false);assert.equal(h.deadlines.size,0);pending.resolve(response(activeStatus));
});

test('week follows the declared timezone and falls back safely for an invalid preview',()=>{
  assert.equal(validTimezone('America/New_York'),true);assert.equal(validTimezone('not/a/timezone'),false);
  const date=new Date('2026-09-07T02:00:00Z');
  assert.equal(weekDates('America/New_York',date)[0].date,'2026-08-31');
  assert.equal(weekDates('UTC',date)[0].date,'2026-09-07');
  assert.deepEqual(weekDates('not/a/timezone',date),weekDates('UTC',date));
});

test('duration, travel, every window and overlaps are validated',()=>{
  const p={...defaults(),session_minutes:30,travel_minutes:10,availability:[{day:'mon',windows:[{start:'08:00',end:'09:00'},{start:'18:00',end:'19:00'}]}]};
  assert.equal(validateAvailability(p),'');
  assert.match(validateAvailability({...p,session_minutes:NaN}),/5 y 180/);
  assert.match(validateAvailability({...p,travel_minutes:-1}),/0 y 180/);
  p.availability[0].windows[1].end='18:20';assert.match(validateAvailability(p),/no cabe/);
  p.availability[0].windows[1]={start:'08:30',end:'09:30'};assert.match(validateAvailability(p),/solaparse/);
});

test('editing a saved profile keeps its snapshot immutable and labels unsaved changes',()=>{
  const h=harness(),old={...defaults(),primary_goal:'strength'};
  const input=stored(old,2);h.api.configure({snapshot:input,replaceDraft:true,view:'onboarding',step:1});h.api.render();
  h.form.values.set('primary_goal','muscle_gain');h.form.values.set('without_weight_or_calories','on');h.api.collect();
  assert.equal(h.api.current().snapshot.profile.primary_goal,'strength');assert.equal(input.profile.primary_goal,'strength');
  assert.equal(h.api.current().profile.primary_goal,'muscle_gain');assert.equal(h.api.dirty(),true);
  h.action('skip');assert.match(h.root.innerHTML,/Cambios sin guardar/);assert.doesNotMatch(h.root.innerHTML,/Preferencias personales guardadas/);
});

test('canonical comparison does not mark an equivalent key order dirty',()=>{
  const h=harness(),p={...defaults(),primary_goal:'strength'};h.api.configure({snapshot:stored(p),replaceDraft:true});
  h.api.configure({profile:Object.fromEntries(Object.entries(p).reverse())});assert.equal(h.api.dirty(),false);
});

test('all windows remain editable and survive collection without truncation',()=>{
  const h=harness(),p={...defaults(),availability:[{day:'mon',windows:[{start:'08:00',end:'09:00'},{start:'18:00',end:'20:00'}]}]};
  h.api.configure({profile:p,view:'onboarding',step:2});h.api.render();
  assert.match(h.root.innerHTML,/data-window="1"/);
  h.form.values.set('days',['mon']);h.form.values.set('session_minutes','30');h.form.values.set('travel_minutes','10');
  h.form.times.set('mon:0:start',{value:'08:15'});h.form.times.set('mon:1:end',{value:'20:30'});h.api.collect();
  assert.deepEqual(deep(h.api.current().profile.availability[0].windows),[{start:'08:15',end:'09:00'},{start:'18:00',end:'20:30'}]);
});

test('a cleared time is not silently restored from an old value',()=>{
  const h=harness();h.api.configure({profile:{...defaults(),availability:[{day:'mon',windows:[{start:'08:00',end:'09:00'}]}]},view:'onboarding',step:2});h.api.render();
  h.form.values.set('days',['mon']);h.form.times.set('mon:0:start',{value:''});h.api.collect();
  assert.equal(h.api.current().profile.availability[0].windows[0].start,'');assert.match(validateAvailability(h.api.current().profile),/Revisa las horas/);
});

test('skip and back do not let an invalid timezone enter the week',()=>{
  for(const action of ['skip','back']){
    const h=harness();h.api.configure({view:'onboarding',step:0});h.api.render();
    for(const [name,value] of Object.entries({timezone:'not/a/timezone',language:'es',weight_unit:'kg',length_unit:'cm'}))h.form.values.set(name,value);
    h.action(action);assert.equal(h.api.current().view,'onboarding');assert.match(h.api.current().failure,/zona horaria/);assert.equal(h.focus,'alert');
  }
  const h=harness();h.api.configure({profile:{...defaults(),timezone:'bad'},section:'week'});assert.match(h.api.space(),/provisionalmente en UTC/);
});

test('final step includes explicit exploration without giving consent',()=>{
  const h=harness();h.api.configure({status:activeStatus,ready:true,view:'onboarding',step:4});h.api.render();
  assert.match(h.root.innerHTML,/Explorar sin guardar cambios/);h.action('skip');
  assert.equal(h.api.current().view,'space');assert.equal(h.requests.length,0);assert.match(h.root.innerHTML,/nada guardado/);
});

test('same identity/root mount preserves live uncollected form input',()=>{
  const h=harness();h.api.configure({view:'onboarding',step:1});h.api.render();h.form.values.set('primary_goal','muscle_gain');
  const count=h.renderCount;h.api.mount(h.root,{identity:'member-a',navigate(){}});
  assert.equal(h.renderCount,count);assert.equal(h.form.values.get('primary_goal'),'muscle_gain');assert.equal(h.requests.length,0);
});

test('back restores keyboard focus and tabs have one tab stop',()=>{
  const h=harness();h.api.configure({view:'onboarding',step:1});h.api.render();h.action('back');assert.equal(h.api.current().step,0);assert.equal(h.focus,'heading');
  const markup=h.api.space();assert.equal((markup.match(/role="tab"[^>]*tabindex="0"/g)||[]).length,1);assert.equal((markup.match(/role="tab"[^>]*tabindex="-1"/g)||[]).length,5);
  h.api.keys({target:h.tabs[0],key:'ArrowRight',preventDefault(){}});assert.equal(h.api.current().section,'week');
});

test('consent succeeds, profile fails, and removal still deletes consent-only state',async()=>{
  const h=harness();h.api.configure({status:activeStatus,ready:true,view:'onboarding',step:4});h.api.render();h.form.values.set('consent','on');
  h.queue.push(response(stored(null,1)),response({detail:'Perfil no válido'},422));
  await h.api.submit({preventDefault(){}});assert.equal(h.api.current().saved,false);assert.equal(h.api.current().snapshot.consent.granted,true);
  assert.match(h.api.settings(),/Descargar datos guardados/);
  h.queue.push(response(stored(null,1)),response(empty(2)));await h.api.erase();
  assert.deepEqual(h.requests.map(r=>[r.method,r.url]),[['POST','/api/fitness/v1/me/consents'],['PATCH','/api/fitness/v1/me/profile'],['GET','/api/fitness/v1/me/profile'],['DELETE','/api/fitness/v1/me/data']]);
  assert.equal(h.requests[3].payload.expected_version,1);assert.equal(h.api.current().snapshot.consent,null);assert.match(h.api.current().notice,/El servidor confirmó/);
});

test('lost consent response is reconciled before claiming removal',async()=>{
  const h=harness();h.api.configure({status:activeStatus,ready:true,view:'onboarding',step:4});h.api.render();h.form.values.set('consent','on');h.queue.push(new TypeError('connection lost'));
  await h.api.submit({preventDefault(){}});assert.equal(h.api.current().remoteUncertain,true);assert.match(h.api.settings(),/Eliminar mis preferencias/);
  h.queue.push(response(stored(null,1)),response(empty(2)));await h.api.erase();
  assert.equal(h.requests[1].method,'GET');assert.equal(h.requests[2].method,'DELETE');assert.equal(h.api.current().remoteUncertain,false);
});

test('failed reconciliation never claims ambiguous data was removed',async()=>{
  const h=harness();h.api.configure({status:activeStatus,ready:true,remoteUncertain:true});h.queue.push(new TypeError('offline'));
  await h.api.erase();assert.equal(h.requests.length,1);assert.equal(h.api.current().remoteUncertain,true);assert.equal(h.api.current().notice,'');assert.match(h.api.current().failure,/No des tus datos por eliminados/);
});

test('successful empty reconciliation can discard the local draft without a delete',async()=>{
  const h=harness();h.api.configure({status:activeStatus,ready:true,remoteUncertain:true,profile:{...defaults(),primary_goal:'strength'}});h.queue.push(response(empty(0)));
  await h.api.erase();assert.equal(h.requests.length,1);assert.equal(h.api.current().profile.primary_goal,null);assert.equal(h.api.current().remoteUncertain,false);
});

test('busy operations disable actual controls and do not allow concurrent deletion/export',async()=>{
  const h=harness(),waiting=deferred();h.api.configure({snapshot:stored(null,1),status:activeStatus,ready:true});h.queue.push(()=>waiting.promise);
  const pending=h.api.exportData();assert.equal(h.api.current().busy,true);assert.ok(h.controls.every(control=>control.disabled));
  await h.api.erase();await h.api.exportData();assert.equal(h.requests.length,1);
  waiting.resolve(response({state:stored(null,1)}));await pending;assert.equal(h.api.current().busy,false);assert.deepEqual(h.downloads,['mis-preferencias-ejercicio.json']);assert.ok(h.controls.every(control=>!control.disabled));
});

test('reloading snapshots uses independent draft copies',async()=>{
  const h=harness(),p={...defaults(),primary_goal:'strength'};h.queue.push(response(activeStatus),response(stored(p,2)));
  await h.api.load();h.api.configure({view:'onboarding',step:1});h.api.render();h.form.values.set('primary_goal','muscle_gain');h.form.values.set('without_weight_or_calories','on');h.api.collect();
  assert.equal(h.api.current().snapshot.profile.primary_goal,'strength');assert.equal(h.api.current().profile.primary_goal,'muscle_gain');
});

test('late export response after identity change cannot download the previous member data',async()=>{
  const h=harness(),waiting=deferred();h.api.configure({snapshot:stored({...defaults(),primary_goal:'strength'},2),replaceDraft:true});h.queue.push(()=>waiting.promise);
  const pending=h.api.exportData();h.queue.push(response({personal_login:false,storage:{configured:false},education:[]}));h.api.mount(h.root,{identity:'member-b',navigate(){}});
  waiting.resolve(response({state:stored({...defaults(),primary_goal:'strength'},2)}));await pending;await flush();
  assert.equal(h.downloads.length,0);assert.equal(h.api.current().identity,'member-b');assert.equal(h.api.current().profile.primary_goal,null);
});

test('bfcache pagehide clears private memory and pageshow reauthenticates',async()=>{
  const h=harness();h.api.configure({snapshot:stored({...defaults(),primary_goal:'strength'},2),replaceDraft:true,view:'space'});h.api.render();
  h.events.get('pagehide')({persisted:true});assert.equal(h.api.current().profile.primary_goal,null);assert.equal(h.api.current().snapshot.profile,null);assert.doesNotMatch(h.root.innerHTML,/Preferencias personales guardadas/);
  h.queue.push(response(activeStatus),response(stored({...defaults(),primary_goal:'fitness_habit'},3)));h.events.get('pageshow')({persisted:true});await flush();
  assert.deepEqual(h.requests.map(r=>r.url),['/api/fitness/v1/status','/api/fitness/v1/me/profile']);assert.equal(h.api.current().profile.primary_goal,'fitness_habit');
});

test('expired authentication on reload does not leave a private old profile displayed',async()=>{
  const h=harness();h.api.configure({snapshot:stored({...defaults(),primary_goal:'strength'},2),replaceDraft:true,view:'space'});h.queue.push(response({detail:'Sesión vencida'},401));
  await h.api.load(true);assert.equal(h.api.current().profile.primary_goal,null);assert.equal(h.api.current().snapshot.profile,null);assert.equal(h.api.current().view,'welcome');
});

test('requests retain same-origin, no-store, explicit mutation intent and idempotency',async()=>{
  const h=harness();h.api.configure({status:activeStatus,ready:true,view:'onboarding',step:4});h.api.render();h.form.values.set('consent','on');h.queue.push(response(stored(null,1)),response(stored(defaults(),2)));
  await h.api.submit({preventDefault(){}});assert.equal(h.api.current().failure,'');assert.equal(h.api.current().saved,true);
  for(const r of h.requests){assert.equal(r.credentials,'same-origin');assert.equal(r.cache,'no-store');assert.equal(r.headers['X-Roxy-Fitness-Request'],'1');assert.equal(r.headers['X-Roxy-Fitness-Member'],'member-a');assert.match(r.headers['Idempotency-Key'],/^[a-f0-9-]{36}$/);assert.ok(r.signal);}
});

test('status identity change cannot load another member or retain the old draft',async()=>{
  const h=harness();h.api.configure({snapshot:stored({...defaults(),primary_goal:'strength'},2),replaceDraft:true,view:'space'});
  h.queue.push(response({...activeStatus,member_id:'member-b'}));await h.api.load(true);
  assert.equal(h.requests.length,1);assert.equal(h.api.current().profile.primary_goal,null);assert.equal(h.api.current().snapshot.profile,null);assert.match(h.api.current().failure,/Cambió la persona/);
});

test('HTTP200 downgraded personal login clears previously loaded preferences',async()=>{
  const h=harness();h.api.configure({snapshot:stored({...defaults(),primary_goal:'strength'},2),replaceDraft:true,view:'space'});
  h.queue.push(response({personal_login:false,member_id:null,storage:{configured:false},education:[]}));await h.api.load(true);
  assert.equal(h.api.current().profile.primary_goal,null);assert.equal(h.api.current().snapshot.profile,null);assert.equal(h.api.current().view,'welcome');
});

for(const operation of ['exportData','erase'])test(`shared-login rejection during ${operation} clears the previous member data`,async()=>{
  const h=harness();h.api.configure({status:activeStatus,ready:true,snapshot:stored({...defaults(),primary_goal:'fat_loss'},2),replaceDraft:true,view:'space'});
  h.queue.push(response({detail:{code:'personal_login_required',message:'Inicia sesión con tu cuenta personal.'}},403));
  await h.api[operation]();
  assert.equal(h.api.current().profile.primary_goal,null);assert.equal(h.api.current().snapshot.profile,null);
  assert.equal(h.api.current().ready,false);assert.equal(h.api.current().view,'welcome');assert.doesNotMatch(h.root.innerHTML,/Reducir grasa o peso/);
});

test('progress uses CSP-compatible state classes, not blocked inline styles',()=>{
  const h=harness();h.api.configure({view:'onboarding',step:1});h.api.render();
  assert.match(h.root.innerHTML,/data-progress="2"/);assert.match(h.root.innerHTML,/aria-valuenow="2"/);assert.doesNotMatch(h.root.innerHTML,/style="width:/);
});
