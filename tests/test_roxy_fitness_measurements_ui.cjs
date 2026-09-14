'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),{webcrypto}=require('node:crypto');
const api=require('../assets/roxy_fitness_measurements.js');
const source=fs.readFileSync(require.resolve('../assets/roxy_fitness_measurements.js'),'utf8');
const PREFIX='/api/fitness/v1/me/measurements';
const A='11111111-1111-4111-8111-111111111111',B='22222222-2222-4222-8222-222222222222';
const clone=x=>JSON.parse(JSON.stringify(x));
const consent={purpose:'fitness_measurements',text_version:'fitness-measurements-v1',granted:true,recorded_at:'2026-09-01T00:00:00Z'};
const row=(extra={})=>{const value={id:A,date:'2026-09-01',timezone:'America/New_York',weight:{value:75,unit:'kg'},height:{value:175,unit:'cm'},recorded_at:'2026-09-01T00:00:00Z',updated_at:'2026-09-01T00:00:00Z',...extra};return {...value,...api.normalized(value)};};
const empty=()=>({version:0,consent:null,measurements:[],updated_at:null,eligible:true,eligibility_reason:null});
const saved=(measurements=[row()],version=1)=>({...empty(),version,consent:clone(consent),measurements,updated_at:'2026-09-01T00:00:00Z'});
const response=(data,status=200)=>({ok:status>=200&&status<300,status,json:async()=>clone(data)});
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
const flush=async()=>{for(let i=0;i<35;i++)await Promise.resolve();};
const descendants=node=>node.children.flatMap(child=>[child,...descendants(child)]);
const all=(node,tag)=>descendants(node).filter(child=>child.tagName===tag.toUpperCase());
const byClass=(node,name)=>descendants(node).filter(child=>(child.className||'').split(' ').includes(name));
const button=(node,label)=>all(node,'button').find(child=>child.textContent===label);
const field=(node,label)=>descendants(node).find(child=>child.getAttribute('aria-label')===label);
function harness(initial=empty(),intercept){
  let server=clone(initial),id=0;const calls=[],events={},downloads=[],timers=new Map(),revoked=[];
  class Node{
    constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.attrs={};this.events={};this._text='';this.value='';}
    get textContent(){return this._text+this.children.map(n=>n.textContent).join('');}set textContent(v){this._text=String(v);this.replaceChildren();}
    get isConnected(){return this.root||Boolean(this.parent?.isConnected);}
    append(...nodes){nodes.forEach(n=>{n.parent=this;this.children.push(n);});}
    replaceChildren(...nodes){this.children.forEach(n=>n.parent=null);this.children=[];this.append(...nodes);}
    setAttribute(k,v){this.attrs[k]=String(v);}getAttribute(k){return this.attrs[k]??null;}
    addEventListener(k,fn){(this.events[k]||=[]).push(fn);}
    querySelector(selector){return selector.startsWith('.')?byClass(this,selector.slice(1))[0]:all(this,selector)[0];}
    querySelectorAll(selector){return selector.split(',').flatMap(tag=>all(this,tag));}
    focus(){this.focused=true;}
    async emit(name){for(const fn of this.events[name]||[])fn({target:this,preventDefault(){},stopPropagation(){}});await flush();}
    async click(){if(this.disabled)return;if(this.tagName==='A'){downloads.push(this);return;}await this.emit('click');}
  }
  const body=new Node('body');body.root=true;const root=new Node('div');body.append(root);
  const doc={hidden:false,createElement:tag=>new Node(tag),addEventListener:(name,fn)=>events[name]=fn};
  const context={document:doc,Intl,Date,Map,Set,AbortController,Blob,crypto:webcrypto,
    URL:{createObjectURL:()=> 'blob:measurements',revokeObjectURL:url=>revoked.push(url)},
    setTimeout(fn){const token=++id;timers.set(token,fn);return token;},clearTimeout(token){timers.delete(token);},addEventListener:(name,fn)=>events[name]=fn,
    fetch:async(path,options)=>{
      calls.push({path,...options,payload:options.body?JSON.parse(options.body):undefined});
      assert.equal(options.credentials,'same-origin');assert.equal(options.cache,'no-store');assert.ok(options.headers['X-Roxy-Fitness-Member']);
      const override=intercept?.(path,options,calls.length);if(override!==undefined)return await override;
      if(path===PREFIX+'/export')return response({format:'roxy-home-fitness-measurements-v1',scope:'authenticated_member_only',exported_at:'2026-09-14T00:00:00Z',data:server});
      if(options.method==='GET')return response(server);
      assert.equal(options.headers['X-Roxy-Fitness-Request'],'1');assert.match(options.headers['Idempotency-Key'],/^[a-f\d-]{36}$/i);
      const data=JSON.parse(options.body);assert.equal(data.expected_version,server.version);
      if(path.endsWith('/consent'))server={...server,version:server.version+1,consent:clone(consent)};
      else if(options.method==='PUT'){const value=row(data.measurement),rows=server.measurements.filter(item=>item.id!==value.id);rows.push(value);server={...server,version:server.version+1,measurements:rows};}
      else if(options.method==='DELETE'&&path!==PREFIX){assert.equal(data.confirm_delete,true);server={...server,version:server.version+1,measurements:server.measurements.filter(item=>!path.endsWith('/'+item.id))};}
      else if(options.method==='DELETE'){assert.equal(data.confirm_delete,true);server={...empty(),version:server.version+1};}
      return response(server);
    }};context.window=context;vm.runInNewContext(source,context);
  return {api:context.RoxyFitnessMeasurements,root,body,calls,events,downloads,timers,revoked,document:doc,get server(){return clone(server);},newRoot(){const node=new Node('div');body.append(node);return node;},async mount(options={}){context.RoxyFitnessMeasurements.mount(root,{identity:'member-a',timezone:'America/New_York',...options});await flush();},async visibility(hidden){doc.hidden=hidden;events.visibilitychange();await flush();}};
}
async function change(h,label,value,event='input'){const node=field(h.root,label);assert.ok(node,label);node.value=value;await node.emit(event);}
async function fill(h,values={weight:'76.3',cm:'175'}){await button(h.root,'Añadir medición').click();await change(h,'Fecha de medición','2026-09-05');if(values.weight!==undefined)await change(h,'Peso',values.weight);if(values.cm!==undefined)await change(h,'Estatura en centímetros',values.cm);await all(h.root,'form')[0].emit('submit');}
async function approve(h){const check=all(h.root,'input').find(node=>node.type==='checkbox');check.checked=true;await check.emit('change');}
const draft=(extra={})=>({id:A,date:'2026-09-01',timezone:'America/New_York',weight:'75',weightUnit:'kg',heightUnit:'cm',cm:'175',feet:'',inches:'',...extra});

test('conversion preserves declared measurements and finite canonical units',()=>{
  assert.deepEqual(api.normalized(row({weight:{value:165,unit:'lb'},height:{unit:'ft_in',feet:5,inches:9}})),{weight_kg:74.842741,height_cm:175.26});
  for(const value of [NaN,Infinity,true,'75',-3,0,1001])assert.throws(()=>api.normalized({...row(),weight:{value,unit:'kg'}}));
  assert.throws(()=>api.normalized({...row(),height:{unit:'ft_in',feet:5,inches:12}}));
  assert.throws(()=>api.normalized({...row(),height:{unit:'ft_in',feet:5.5,inches:0}}));
});
test('date, timezone, future and duplicate-date guards work in the selected timezone',()=>{
  assert.equal(api.dateOK('2026-02-29'),false);assert.equal(api.dateOK('2028-02-29'),true);assert.equal(api.zoneOK('fake/zone'),false);
  assert.equal(api.today('America/New_York',new Date('2026-09-14T02:00:00Z')),'2026-09-13');
  assert.throws(()=>api.draftMeasurement(draft({date:'2026-09-14'}),[],new Date('2026-09-14T02:00:00Z')),/futuro/);
  assert.throws(()=>api.draftMeasurement(draft({id:B}),[row()]),/Ya tienes/);
  assert.equal(api.draftMeasurement(draft(),[row()]).id,A);
});
test('weight and height are individually optional, never default to invented amounts',()=>{
  assert.equal(api.draftMeasurement(draft({weight:''})).weight,null);
  assert.equal(api.draftMeasurement(draft({cm:''})).height,null);
  assert.throws(()=>api.draftMeasurement(draft({weight:' ',cm:''})),/Añade el peso/);
  assert.throws(()=>api.draftMeasurement(draft({heightUnit:'ft_in',feet:'5',inches:''})),/Completa pies/);
  assert.deepEqual(api.draftMeasurement(draft({heightUnit:'ft_in',feet:'5',inches:'0'})).height,{unit:'ft_in',feet:5,inches:0});
});
test('difference uses preceding weight record across units and skips height-only dates',()=>{
  const previous=row({weight:{value:100,unit:'kg'}}),heightOnly=row({id:B,date:'2026-09-03',weight:null}),last=row({id:'33333333-3333-4333-8333-333333333333',date:'2026-09-05',weight:{value:220.462262,unit:'lb'}});
  assert.equal(api.weightDelta(previous,[previous,heightOnly,last]),null);assert.equal(api.weightDelta(heightOnly,[previous,heightOnly,last]),null);
  assert.deepEqual(api.weightDelta(last,[previous,heightOnly,last]),{value:0,unit:'lb',previous_date:'2026-09-01',label:'0 lb'});
});
test('untrusted saved payloads cannot display inconsistent canonical data or permissions',()=>{
  for(const alter of [p=>p.measurements[0].weight_kg=12,p=>p.measurements[0].height_cm=2,p=>p.measurements.push(row()),p=>p.measurements[0].date='2026-99-99',p=>p.measurements[0].recorded_at='bad',p=>p.consent.granted=false,p=>p.consent.purpose='household',p=>p.version=-1,p=>delete p.eligible,p=>p.eligibility_reason='adult_profile_required']){const data=saved();alter(data);assert.throws(()=>api.snapshot(data));}
});
test('empty state has no simulated measurements and opening the form never writes',async()=>{
  const h=harness();await h.mount();assert.match(h.root.textContent,/El primer registro lo eliges tú/);assert.equal(byClass(h.root,'fxm-stat').length,0);
  await button(h.root,'Añadir medición').click();assert.equal(field(h.root,'Peso').value,'');assert.equal(field(h.root,'Estatura en centímetros').value,'');assert.equal(field(h.root,'Zona horaria de la medición').readOnly,true);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
});
test('saving requires review and explicit private consent and waits for confirmed versions',async()=>{
  const h=harness();await h.mount();await fill(h);assert.match(h.root.textContent,/Revisa antes de guardar/);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
  await button(h.root,'Guardar medición').click();assert.match(h.root.textContent,/Confirma que autorizas/);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
  await approve(h);await button(h.root,'Guardar medición').click();const writes=h.calls.filter(c=>c.method!=='GET');assert.deepEqual(writes.map(c=>c.method),['POST','PUT']);assert.deepEqual(writes.map(c=>c.payload.expected_version),[0,1]);assert.equal(writes[0].payload.consent.purpose,'fitness_measurements');assert.equal(writes[1].payload.measurement.weight.value,76.3);assert.equal(h.server.measurements.length,1);assert.match(h.root.textContent,/quedó guardada/);
});
test('height-only save and unit choice work with no weight field or derived health metric',async()=>{
  const h=harness();await h.mount({weightUnit:'lb',heightUnit:'ft_in'});await button(h.root,'Añadir medición').click();await change(h,'Fecha de medición','2026-09-05');assert.equal(field(h.root,'Unidad de peso').value,'lb');await change(h,'Pies','5');await change(h,'Pulgadas','9');await all(h.root,'form')[0].emit('submit');await approve(h);await button(h.root,'Guardar medición').click();assert.equal(h.server.measurements[0].weight,null);assert.equal(h.server.measurements[0].height_cm,175.26);assert.match(h.root.textContent,/5 pies · 9 pulg/);assert.doesNotMatch(h.root.textContent,/IMC|kcal|calorías|diagnóstico/);
});
test('correction preserves identity and unrounded declared values and requires consent again',async()=>{
  const h=harness(saved([row({weight:{value:165.123456,unit:'lb'},height:{unit:'ft_in',feet:5,inches:9.234}})]));await h.mount();await button(h.root,'Corregir').click();assert.equal(field(h.root,'Peso').value,165.123456);assert.equal(field(h.root,'Pulgadas').value,9.234);await change(h,'Peso','165.5');await all(h.root,'form')[0].emit('submit');assert.equal(all(h.root,'input').find(n=>n.type==='checkbox').checked,false);await approve(h);await button(h.root,'Guardar corrección').click();const writes=h.calls.filter(c=>c.method!=='GET');assert.equal(writes.length,1);assert.equal(writes[0].payload.measurement.id,A);assert.equal(writes[0].payload.measurement.height.inches,9.234);assert.equal(h.server.measurements.length,1);assert.match(h.root.textContent,/quedó corregida/);
});
test('ineligible profile reads history and can manage records but cannot add or correct',async()=>{
  const start={...saved(),eligible:false,eligibility_reason:'adult_profile_required'},h=harness(start);let opened=0;await h.mount({onPreferences:()=>opened++});assert.match(h.root.textContent,/75 kg/);assert.match(h.root.textContent,/18 años o más/);assert.equal(button(h.root,'Añadir medición'),undefined);assert.equal(button(h.root,'Corregir').disabled,true);await button(h.root,'Configurar mis preferencias').click();assert.equal(opened,1);assert.ok(button(h.root,'Descargar mis mediciones'));assert.ok(button(h.root,'Retirar permiso y borrar mediciones'));assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
});
test('deleting one measurement requires explicit local confirmation and preserves other rows',async()=>{
  const h=harness(saved([row(),row({id:B,date:'2026-09-02'})]));await h.mount();await button(h.root,'Eliminar').click();assert.equal(h.calls.filter(c=>c.method==='DELETE').length,0);await button(h.root,'Conservar mis mediciones').click();assert.equal(h.calls.filter(c=>c.method==='DELETE').length,0);await button(h.root,'Eliminar').click();await button(h.root,'Sí, eliminar medición').click();assert.equal(h.server.measurements.length,1);assert.equal(h.server.measurements[0].id,A);assert.equal(h.server.consent.granted,true);assert.match(h.root.textContent,/medición fue eliminada/);
});
test('withdrawing consent and all records requires a separate confirmation',async()=>{
  const h=harness(saved());await h.mount();await button(h.root,'Retirar permiso y borrar mediciones').click();assert.equal(h.calls.filter(c=>c.method==='DELETE').length,0);assert.match(h.root.textContent,/Tu plan y tus actividades se conservan/);await button(h.root,'Sí, retirar y borrar').click();assert.equal(h.server.measurements.length,0);assert.equal(h.server.consent,null);assert.match(h.root.textContent,/permiso de guardado fue retirado/);
});
test('export downloads only a verified member export after an explicit click',async()=>{
  const h=harness(saved());await h.mount();assert.equal(h.downloads.length,0);await button(h.root,'Descargar mis mediciones').click();assert.equal(h.downloads.length,1);assert.equal(h.downloads[0].download,'mis-mediciones-roxy.json');assert.equal(h.calls.at(-1).path,PREFIX+'/export');assert.equal(h.calls.at(-1).method,'GET');assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
});
test('incorrect export scope is rejected and never triggers a download',async()=>{
  const h=harness(saved(),path=>path.endsWith('/export')?response({format:'roxy-home-fitness-measurements-v1',scope:'household',data:saved()}):undefined);await h.mount();await button(h.root,'Descargar mis mediciones').click();assert.equal(h.downloads.length,0);assert.match(h.root.textContent,/No pude verificar la exportación/);
});
test('pending save disables controls and never shows an optimistic saved value',async()=>{
  const pending=deferred(),h=harness(saved(),(path,options)=>options.method==='PUT'?pending.promise:undefined);await h.mount();await fill(h,{weight:'99',cm:''});await approve(h);await button(h.root,'Guardar medición').click();assert.equal(button(h.root,'Guardar medición').disabled,true);assert.doesNotMatch(h.root.textContent,/quedó guardada/);assert.equal(h.server.measurements.length,1);pending.resolve(response(saved([row(),row({id:B,date:'2026-09-05',weight:{value:99,unit:'kg'},height:null})],2)));await flush();assert.match(h.root.textContent,/quedó guardada/);assert.match(h.root.textContent,/99 kg/);
});
test('conflict does not overwrite server data and forces reload before another write',async()=>{
  const h=harness(saved(),(path,options)=>options.method==='PUT'?response({detail:{message:'conflict'}},409):undefined);await h.mount();await fill(h);await approve(h);await button(h.root,'Guardar medición').click();assert.match(h.root.textContent,/cambiaron en otra sesión/);assert.equal(button(h.root,'Guardar medición'),undefined);assert.equal(h.server.measurements.length,1);await button(h.root,'Volver a cargar mediciones').click();assert.match(h.root.textContent,/75 kg/);
});
test('ambiguous write requires checking committed state before trying again',async()=>{
  let failed=false;const h=harness(saved(),(path,options)=>{if(options.method==='PUT'&&!failed){failed=true;throw new TypeError('Failed to fetch');}});await h.mount();await fill(h);await approve(h);await button(h.root,'Guardar medición').click();assert.match(h.root.textContent,/No pude conectar/);assert.ok(button(h.root,'Comprobar guardado'));assert.equal(button(h.root,'Guardar medición'),undefined);assert.doesNotMatch(h.root.textContent,/Failed to fetch/);await button(h.root,'Comprobar guardado').click();assert.ok(button(h.root,'Añadir medición'));assert.equal(h.server.measurements.length,1);
});
test('expired authorization clears health values from the DOM immediately after rejection',async()=>{
  const h=harness(saved(),(path,options)=>options.method==='DELETE'?response({detail:{message:'expired'}},403):undefined);await h.mount();await button(h.root,'Eliminar').click();await button(h.root,'Sí, eliminar medición').click();assert.doesNotMatch(h.root.textContent,/75 kg|175 cm/);assert.match(h.root.textContent,/La sesión cambió/);
});
test('no authenticated identity means no request and no writable measurement form',async()=>{
  const h=harness();await h.mount({identity:''});assert.equal(h.calls.length,0);assert.match(h.root.textContent,/Entra en tu perfil personal/);assert.equal(button(h.root,'Añadir medición'),undefined);
});
test('late GET or export response after leaving cannot restore or download private data',async()=>{
  const pending=deferred(),h=harness(empty(),()=>pending.promise);h.api.mount(h.root,{identity:'member-a',timezone:'UTC'});await flush();h.api.setActive(false);pending.resolve(response(saved()));await flush();assert.equal(h.root.textContent,'');
  const exportPending=deferred(),e=harness(saved(),path=>path.endsWith('/export')?exportPending.promise:undefined);await e.mount();await button(e.root,'Descargar mis mediciones').click();e.api.setActive(false);exportPending.resolve(response({format:'roxy-home-fitness-measurements-v1',scope:'authenticated_member_only',data:saved()}));await flush();assert.equal(e.downloads.length,0);assert.equal(e.root.textContent,'');
});
test('hidden tab clears measurements and revalidates the server on return',async()=>{
  const h=harness(saved());await h.mount();await h.visibility(true);assert.equal(h.root.textContent,'');await h.visibility(false);assert.equal(h.calls.filter(c=>c.method==='GET').length,2);assert.match(h.root.textContent,/75 kg/);
});
test('identity switch cancels previous responses and never exposes previous member values',async()=>{
  const pending=deferred(),h=harness(empty(),(path,options)=>options.headers['X-Roxy-Fitness-Member']==='member-a'?pending.promise:response(empty()));h.api.mount(h.root,{identity:'member-a',timezone:'UTC'});await flush();h.api.mount(h.root,{identity:'member-b',timezone:'UTC'});await flush();pending.resolve(response(saved()));await flush();assert.doesNotMatch(h.root.textContent,/75 kg|175 cm/);assert.match(h.root.textContent,/El primer registro/);assert.equal(h.calls[0].signal.aborted,true);
});
test('remounting into a new root removes private values from the previous detached panel',async()=>{
  const h=harness(saved());await h.mount();const next=h.newRoot();h.api.mount(next,{identity:'member-a',timezone:'UTC'});await flush();assert.equal(h.root.textContent,'');assert.match(next.textContent,/75 kg/);
});
test('private measurements never use browser databases, analytics, AI or shared calendar endpoints',()=>{
  assert.doesNotMatch(source,/localStorage|sessionStorage|indexedDB|console\.|\/calendar|\/agent|\/speech|speechSynthesis|sendBeacon/);
  assert.match(source,/cache:'no-store'/);assert.match(source,/'X-Roxy-Fitness-Member'/);assert.match(source,/'X-Roxy-Fitness-Request'/);assert.match(source,/'Idempotency-Key'/);
});

test('unavailable private storage shows recovery without a form or simulated records',async()=>{
  const h=harness(empty(),()=>response({detail:{message:'unavailable'}},503));await h.mount();assert.match(h.root.textContent,/guardado privado de mediciones todavía no está disponible/);assert.ok(button(h.root,'Volver a cargar mediciones'));assert.equal(button(h.root,'Añadir medición'),undefined);assert.equal(byClass(h.root,'fxm-stat').length,0);
});
test('duplicate dates and invalid blank form never issue a mutation',async()=>{
  const h=harness(saved());await h.mount();await button(h.root,'Añadir medición').click();await all(h.root,'form')[0].emit('submit');assert.match(h.root.textContent,/Añade el peso/);await change(h,'Fecha de medición','2026-09-01');await change(h,'Peso','76');await all(h.root,'form')[0].emit('submit');assert.match(h.root.textContent,/Ya tienes una medición/);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
});
test('pending writes do not return health data to a hidden panel even when the server commits',async()=>{
  const pending=deferred(),h=harness(saved(),(path,options)=>options.method==='PUT'?pending.promise:undefined);await h.mount();await fill(h);await approve(h);await button(h.root,'Guardar medición').click();const call=h.calls.find(c=>c.method==='PUT');await h.visibility(true);assert.equal(h.root.textContent,'');assert.equal(call.signal.aborted,true);pending.resolve(response(saved([row(),row({id:B,date:'2026-09-05',weight:{value:76.3,unit:'kg'}})],2)));await flush();assert.equal(h.root.textContent,'');
});
test('write timeout removes save controls until server state is checked',async()=>{
  const pending=deferred(),h=harness(saved(),(path,options)=>options.method==='PUT'?pending.promise:undefined);await h.mount();await fill(h);await approve(h);await button(h.root,'Guardar medición').click();assert.equal(h.timers.size,1);[...h.timers.values()][0]();await flush();assert.match(h.root.textContent,/La conexión tardó demasiado/);assert.ok(button(h.root,'Comprobar guardado'));assert.equal(button(h.root,'Guardar medición'),undefined);assert.equal(h.calls.find(c=>c.method==='PUT').signal.aborted,true);
});
