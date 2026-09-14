'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),{webcrypto}=require('node:crypto');
const api=require('../assets/roxy_fitness_training.js');
const source=fs.readFileSync(require.resolve('../assets/roxy_fitness_training.js'),'utf8');
const PREFIX='/api/fitness/v1/me/training-logs',CATALOG='/api/fitness/v1/training/programs';
const A='11111111-1111-4111-8111-111111111111',B='22222222-2222-4222-8222-222222222222';
const clone=x=>JSON.parse(JSON.stringify(x));
const consent={purpose:'fitness_training_logs',text_version:'fitness-training-logs-v1',granted:true,recorded_at:'2026-09-01T00:00:00Z'};
const exercise=(extra={})=>({id:'chair-sit-stand',name:'Levántate de la silla',phase:'work',instructions:['Apoya los pies.','Levántate con control.','Vuelve despacio.'],cue:'Controla la bajada.',dose:{label:'1 serie · 5 repeticiones',basis:'source',note:''},tracking_unit:'reps',equipment:['chair'],capabilities:['standing'],source_links:[],rest:{mode:'manual',suggested_seconds:null,label:'Descansa a tu ritmo.'},load:null,load_recordable:false,...extra});
const program=()=>({id:'home-bodyweight-foundations',title:'Fuerza en casa',summary:'Una sesión de movimientos con apoyo.',modality:'strength',level:'beginner',locations:['home'],requirements:{equipment:['chair'],capabilities:['standing'],equipment_complete:true},estimated_minutes:{min:20,max:30,kind:'editorial_estimate',assumptions:['Los descansos son manuales.']},exercise_count:2,content_version:'home-training-213-v1',scope:'Iniciación con apoyo.',source_links:[{title:'Ejercicios de fuerza',url:'https://www.nhs.uk/live-well/exercise/strength-exercises/'}],before_start:['Revisa tu espacio.'],exercises:[exercise({id:'walking-warmup',name:'Entra en movimiento',phase:'warmup',tracking_unit:'seconds'}),exercise(),exercise({id:'dumbbell-curl',name:'Curl con mancuerna',load_recordable:true}),exercise({id:'walking-cooldown',name:'Baja el ritmo',phase:'cooldown',tracking_unit:'seconds'})]});
const catalogue=()=>({content_version:'home-training-213-v1',content_digest:'a'.repeat(64),editorial_source_audit:true,clinical_approval:false,programs:[program()]});
const session=(extra={})=>({id:A,program_id:program().id,date:'2026-09-01',time:'08:00',starts_at:'2026-09-01T12:00:00Z',status:'planned',content_version:program().content_version,...extra});
const proposed=(status='ready')=>({profile_version:2,activity_plan_version:3,proposal:{status,program_id:program().id,title:program().title,content_version:program().content_version,timezone:'America/New_York',sessions:status==='ready'?[session()]:[],excluded_days:[{date:'2026-09-02',message_es:'Ya tienes una actividad en ese horario.'}],notice_es:status==='ready'?'Encontré un espacio.':'No hay espacio en esta semana.'}});
const log=(extra={})=>({session_id:A,program_id:program().id,content_version:program().content_version,performed_on:'2026-09-01',timezone:'America/New_York',duration_minutes:null,exercises:[{exercise_id:'chair-sit-stand',skipped:false,sets:[{reps:5,seconds:null,load:null}]},{exercise_id:'dumbbell-curl',skipped:true,sets:[]}],...extra});
const stored=value=>({...clone(value),exercises:value.exercises.map(ex=>({...clone(ex),sets:ex.sets.map(set=>({...clone(set),load_kg:set.load?Number((set.load.value*(set.load.unit==='lb'?.45359237:1)).toFixed(6)):null}))})),scheduled_date:'2026-09-01',scheduled_time:'08:00',scheduled_timezone:'America/New_York',recorded_at:'2026-09-01T13:00:00Z',updated_at:'2026-09-01T13:00:00Z'});
const empty=()=>({version:0,logs:[],consent:null,updated_at:null,eligible:true,eligibility_reason:null});
const saved=(logs=[stored(log())],version=1)=>({...empty(),version,consent:clone(consent),logs,updated_at:'2026-09-01T13:00:00Z'});
const response=(data,status=200)=>({ok:status>=200&&status<300,status,json:async()=>clone(data)});
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
const flush=async()=>{for(let i=0;i<50;i++)await Promise.resolve();};
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
    URL:class extends URL{static createObjectURL(){return 'blob:training';}static revokeObjectURL(url){revoked.push(url);}},
    setTimeout(fn){const token=++id;timers.set(token,fn);return token;},clearTimeout(token){timers.delete(token);},addEventListener:(name,fn)=>events[name]=fn,
    fetch:async(path,options)=>{
      calls.push({path,...options,payload:options.body?JSON.parse(options.body):undefined});
      assert.equal(options.credentials,'same-origin');assert.equal(options.cache,'no-store');assert.ok(options.headers['X-Roxy-Fitness-Member']);
      const override=intercept?.(path,options,calls.length);if(override!==undefined)return await override;
      if(path===CATALOG)return response(catalogue());
      if(path.startsWith(CATALOG+'/'))return response(program());
      if(path==='/api/fitness/v1/me/training/preview')return response(proposed());
      if(path===PREFIX+'/export')return response({format:'roxy-home-fitness-training-logs-v1',scope:'authenticated_member_only',exported_at:'2026-09-01T00:00:00Z',data:server});
      if(options.method==='GET')return response(server);
      assert.equal(options.headers['X-Roxy-Fitness-Request'],'1');assert.match(options.headers['Idempotency-Key'],/^[a-f\d-]{36}$/i);
      const data=JSON.parse(options.body);assert.equal(data.expected_version,server.version);
      if(path.endsWith('/consent'))server={...server,version:server.version+1,consent:clone(consent)};
      else if(options.method==='PUT'){const value=stored(data.log);server={...server,version:server.version+1,logs:[...server.logs.filter(item=>item.session_id!==value.session_id),value]};}
      else if(options.method==='DELETE'&&path!==PREFIX){assert.equal(data.confirm_delete,true);server={...server,version:server.version+1,logs:server.logs.filter(item=>!path.endsWith('/'+item.session_id))};}
      else if(options.method==='DELETE'){assert.equal(data.confirm_delete,true);server={...empty(),version:server.version+1};}
      return response(server);
    }};context.window=context;vm.runInNewContext(source,context);
  return {api:context.RoxyFitnessTrainingSession,browse:context.RoxyFitnessTraining,root,body,calls,events,downloads,timers,revoked,document:doc,get server(){return clone(server);},newRoot(){const node=new Node('div');body.append(node);return node;},async mount(options={}){context.RoxyFitnessTrainingSession.mount(root,{identity:'member-a',timezone:'America/New_York',session:session(),...options});await flush();},async mountBrowse(options={}){context.RoxyFitnessTraining.mount(root,{identity:'member-a',timezone:'America/New_York',...options});await flush();},async visibility(hidden){doc.hidden=hidden;events.visibilitychange();await flush();}};
}
async function change(h,label,value,event='input'){const node=field(h.root,label);assert.ok(node,label);node.value=value;await node.emit(event);}
async function check(h,label,value=true){const node=field(h.root,label);assert.ok(node,label);node.checked=value;await node.emit('change');}
async function openWork(h){await button(h.root,'Siguiente movimiento →').click();}
async function fillSession(h){await openWork(h);await change(h,'Repeticiones · serie 1','5');await button(h.root,'Siguiente movimiento →').click();await check(h,'Omití Curl con mancuerna');await button(h.root,'Revisar y guardar sesión').click();}
async function approve(h){await check(h,'Autorizo guardar mis registros de entrenamiento');}

test('catalog and complete detail accept work counts separate from warmup and reject missing steps or clinical claims',()=>{
  assert.equal(api.catalog(catalogue()).length,1);assert.equal(api.detail(program(),program().id).exercises.length,4);
  const bad=catalogue();bad.clinical_approval=true;assert.throws(()=>api.catalog(bad));
  for(const alter of [p=>p.exercises.splice(1,1),p=>p.exercises[1].instructions=[],p=>p.exercises[1].tracking_unit='calories',p=>p.requirements.equipment_complete=false,p=>p.source_links[0].url='javascript:alert(1)']){const p=program();alter(p);assert.throws(()=>api.detail(p,p.id));}
});
test('requirements stay explicit and proposal supports no slots without inventing a schedule',()=>{
  assert.throws(()=>api.confirmedRequirements(program(),{equipment:[],capabilities:[]}),/Confirma/);
  assert.deepEqual(api.confirmedRequirements(program(),{equipment:['chair'],capabilities:['standing']}),{equipment:['chair'],capabilities:['standing']});
  assert.equal(api.proposal(proposed(),program()).proposal.sessions.length,1);
  assert.equal(api.proposal(proposed('no_slots'),program()).proposal.sessions.length,0);
  const invalid=proposed();invalid.proposal.sessions[0].program_id='another-program';assert.throws(()=>api.proposal(invalid,program()));
});
test('drafts never turn suggested doses into performed sets and omit warmup/cooldown from logs',()=>{
  const draft=api.makeDraft(program(),session(),'America/New_York');assert.equal(draft.exercises.length,2);assert.equal(draft.exercises[0].sets[0].value,'');assert.equal(draft.exercises[0].sets[0].load,'');assert.equal(draft.consent,false);assert.throws(()=>api.draftLog(program(),session(),draft),/Registra lo que hiciste/);
  draft.exercises.forEach(ex=>ex.skipped=true);assert.throws(()=>api.draftLog(program(),session(),draft),/al menos una serie/);
  draft.exercises[0].skipped=false;draft.exercises[0].sets[0].value='4';assert.equal(api.draftLog(program(),session(),draft).exercises[0].sets[0].reps,4);
});
test('per-exercise units, technical bounds and explicit skipped results match backend',()=>{
  const draft=api.makeDraft(program(),session(),'America/New_York');draft.exercises[0].sets[0].value='10000';draft.exercises[1].skipped=true;assert.equal(api.draftLog(program(),session(),draft).exercises[0].sets[0].reps,10000);
  for(const bad of ['1.5','0','10001','NaN','Infinity']){draft.exercises[0].sets[0].value=bad;assert.throws(()=>api.draftLog(program(),session(),draft));}
  draft.exercises[0].sets[0].value='5';draft.exercises[0].sets[0].load='2';assert.throws(()=>api.draftLog(program(),session(),draft));draft.exercises[0].sets[0].load='';
  draft.exercises[0].sets=Array.from({length:21},()=>({value:'5',load:'',unit:'kg'}));assert.throws(()=>api.draftLog(program(),session(),draft));
  assert.equal(api.validSet({reps:null,seconds:.5,load:{value:2500,unit:'lb'}}),true);assert.equal(api.validSet({reps:1,seconds:1,load:null}),false);
  assert.equal(api.dateOK('2100-12-31'),true);assert.equal(api.dateOK('2101-01-01'),false);assert.equal(api.dateOK('2100-02-29'),false);
});
test('performed date respects local day, scheduled date, and optional actual duration',()=>{
  const p=program(),d=api.makeDraft(p,session(),'America/New_York',log());d.performed_on='2026-09-14';assert.throws(()=>api.draftLog(p,session(),d,new Date('2026-09-14T02:00:00Z')),/futuro/);d.performed_on='2026-08-31';assert.throws(()=>api.draftLog(p,session(),d),/anterior/);d.performed_on='2026-09-01';d.duration_minutes='';assert.equal(api.draftLog(p,session(),d).duration_minutes,null);d.duration_minutes='1441';assert.throws(()=>api.draftLog(p,session(),d),/duración/);
});
test('snapshots reject missing eligibility, duplicate session ids, mismatched consent and all-skipped logs',()=>{
  for(const alter of [p=>delete p.eligible,p=>p.consent.granted=false,p=>p.logs.push(p.logs[0]),p=>p.logs[0].exercises.forEach(ex=>{ex.skipped=true;ex.sets=[];}),p=>p.version=-1]){const data=saved();alter(data);assert.throws(()=>api.logsSnapshot(data));}
  assert.equal(api.sameExercises(stored(log()).exercises,log().exercises),true);
});
test('browse is read-only until preview and review handoff preserves version assertions',async()=>{
  const h=harness();let handed=null;await h.mountBrowse({onSchedule:value=>handed=value});assert.match(h.root.textContent,/Elige cómo te quieres mover/);await button(h.root,'Explorar rutina').click();assert.match(h.root.textContent,/Así será tu sesión/);await button(h.root,'Buscar un horario para mí').click();assert.match(h.root.textContent,/Confirma el material/);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
  await check(h,'Silla estable, sin ruedas ni brazos');await check(h,'Puedo permanecer de pie y caminar con control');await change(h,'Semana a partir del','2026-10-01');await button(h.root,'Buscar un horario para mí').click();assert.match(h.root.textContent,/Tu próximo paso ya tiene espacio/);assert.equal(handed,null);assert.equal(h.calls.at(-1).payload.start_date,'2026-10-01');await button(h.root,'Revisar en mi plan').click();assert.equal(handed.profile_version,2);assert.equal(handed.activity_plan_version,3);assert.equal(h.calls.filter(c=>c.method==='PUT').length,0);
});
test('no slots explains excluded dates and never offers a false save',async()=>{
  const h=harness(empty(),path=>path.endsWith('/training/preview')?response(proposed('no_slots')):undefined);await h.mountBrowse();await button(h.root,'Explorar rutina').click();await check(h,'Silla estable, sin ruedas ni brazos');await check(h,'Puedo permanecer de pie y caminar con control');await button(h.root,'Buscar un horario para mí').click();assert.match(h.root.textContent,/Busquemos otra semana/);assert.match(h.root.textContent,/Ya tienes una actividad/);assert.equal(button(h.root,'Revisar en mi plan'),undefined);
});
test('changing a requirement invalidates a proposal before it can be handed off',async()=>{
  const h=harness();await h.mountBrowse();await button(h.root,'Explorar rutina').click();await check(h,'Silla estable, sin ruedas ni brazos');await check(h,'Puedo permanecer de pie y caminar con control');await button(h.root,'Buscar un horario para mí').click();assert.ok(button(h.root,'Revisar en mi plan'));await check(h,'Puedo permanecer de pie y caminar con control',false);assert.equal(button(h.root,'Revisar en mi plan'),undefined);
});
test('reader shows actual instructions with manual steps and empty work fields; browsing cannot write',async()=>{
  const h=harness();await h.mount();assert.match(h.root.textContent,/Entra en movimiento/);assert.equal(field(h.root,'Repeticiones · serie 1'),undefined);await openWork(h);assert.equal(field(h.root,'Repeticiones · serie 1').value,'');assert.equal(field(h.root,'Carga opcional · serie 1'),undefined);assert.match(h.root.textContent,/Apoya los pies/);await button(h.root,'Siguiente paso').click();assert.match(h.root.textContent,/Levántate con control/);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
});
test('saving requires a complete review, separate consent, and confirmed response before completion',async()=>{
  const h=harness();let savedCount=0,completed=0;await h.mount({onSaved:()=>savedCount++,onComplete:()=>completed++});await fillSession(h);assert.match(h.root.textContent,/Así quedó tu entrenamiento/);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);await button(h.root,'Guardar mi registro').click();assert.match(h.root.textContent,/Confirma el permiso/);await approve(h);await button(h.root,'Guardar mi registro').click();const writes=h.calls.filter(c=>c.method!=='GET');assert.deepEqual(writes.map(c=>c.method),['POST','PUT']);assert.deepEqual(writes.map(c=>c.payload.expected_version),[0,1]);assert.equal(h.server.logs[0].exercises[0].sets[0].reps,5);assert.equal(savedCount,1);assert.equal(completed,0);assert.match(h.root.textContent,/quedó guardado/);await button(h.root,'Marcar actividad completada').click();assert.equal(completed,1);
});
test('optional loads remain declared units and saving accepts server canonical load_kg fields',async()=>{
  const h=harness();await h.mount();await openWork(h);await check(h,'Omití Levántate de la silla');await button(h.root,'Siguiente movimiento →').click();await change(h,'Repeticiones · serie 1','12');await change(h,'Carga opcional · serie 1','10');await change(h,'Unidad de carga · serie 1','lb','change');await button(h.root,'Revisar y guardar sesión').click();await approve(h);await button(h.root,'Guardar mi registro').click();assert.match(h.root.textContent,/quedó guardado/);assert.equal(h.server.logs[0].exercises[1].sets[0].load.value,10);assert.equal(h.server.logs[0].exercises[1].sets[0].load.unit,'lb');assert.equal(h.server.logs[0].exercises[1].sets[0].load_kg,4.535924);
});
test('existing logs restore actual sets without granting a new consent checkbox',async()=>{
  const h=harness(saved());await h.mount();await openWork(h);assert.equal(field(h.root,'Repeticiones · serie 1').value,5);await button(h.root,'Revisar mi registro').click();assert.equal(field(h.root,'Autorizo guardar mis registros de entrenamiento').checked,false);await button(h.root,'Volver a la sesión').click();await change(h,'Repeticiones · serie 1','7');assert.equal(button(h.root,'Marcar actividad completada'),undefined);
});
test('future and skipped activities remain readable with saving disabled',async()=>{
  for(const entry of [session({date:'2099-09-01',starts_at:'2099-09-01T12:00:00Z'}),session({status:'skipped'}),session({status:'cancelled'}),session({status:'unknown'})]){const h=harness();await h.mount({session:entry});assert.match(h.root.textContent,/Entra en movimiento/);assert.equal(button(h.root,'Revisar y guardar sesión').disabled,true);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);}
});
test('private eligibility prevents writes while preserving a readable session',async()=>{
  const h=harness({...empty(),eligible:false,eligibility_reason:'adult_profile_required'});await h.mount();assert.match(h.root.textContent,/18 años o más/);assert.equal(button(h.root,'Revisar y guardar sesión').disabled,true);
});
test('rest is manual, does not advance exercises and is cancelled when leaving',async()=>{
  const h=harness();await h.mount();await openWork(h);await button(h.root,'Iniciar descanso').click();assert.ok(button(h.root,'Pausar descanso'));assert.equal(h.timers.size,1);[...h.timers.values()][0]();assert.match(h.root.textContent,/Levántate de la silla/);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);h.api.setActive(false);assert.equal(h.root.textContent,'');
});
test('version conflict prevents a second write until private data is reloaded',async()=>{
  const h=harness(empty(),(path,options)=>options.method==='PUT'?response({detail:'Changed'},409):undefined);await h.mount();await fillSession(h);await approve(h);await button(h.root,'Guardar mi registro').click();assert.match(h.root.textContent,/cambiaron en otra sesión/);assert.equal(button(h.root,'Guardar mi registro'),undefined);assert.ok(button(h.root,'Volver a cargar sesión'));assert.equal(h.server.logs.length,0);
});
test('ambiguous write requires checking server state without pretending that it saved',async()=>{
  const h=harness(empty(),(path,options)=>options.method==='PUT'?Promise.reject(new TypeError('offline')):undefined);await h.mount();await fillSession(h);await approve(h);await button(h.root,'Guardar mi registro').click();assert.ok(button(h.root,'Comprobar guardado'));assert.equal(button(h.root,'Guardar mi registro'),undefined);assert.equal(button(h.root,'Marcar actividad completada'),undefined);assert.doesNotMatch(h.root.textContent,/quedó guardado/);
});
test('in-flight writes disable controls and delayed response cannot restore a hidden session',async()=>{
  const pending=deferred(),h=harness(empty(),(path,options)=>options.method==='PUT'?pending.promise:undefined);await h.mount();await fillSession(h);await approve(h);await button(h.root,'Guardar mi registro').click();assert.equal(button(h.root,'Guardar mi registro').disabled,true);await h.visibility(true);assert.equal(h.root.textContent,'');assert.equal(h.calls.find(c=>c.method==='PUT').signal.aborted,true);pending.resolve(response(saved()));await flush();assert.equal(h.root.textContent,'');
});
test('identity changes and hidden tabs purge private drafts, then revalidate on return',async()=>{
  const h=harness(saved());await h.mount();await openWork(h);await change(h,'Repeticiones · serie 1','777');await h.visibility(true);assert.equal(h.root.textContent,'');await h.visibility(false);await openWork(h);assert.equal(field(h.root,'Repeticiones · serie 1').value,5);const next=h.newRoot();h.api.mount(next,{identity:'member-b',session:session(),timezone:'UTC'});await flush();assert.equal(h.root.textContent,'');assert.equal(h.calls.at(-1).headers['X-Roxy-Fitness-Member'],'member-b');
});
test('no identity or no saved session means no data request or writable form',async()=>{
  for(const options of [{identity:''},{session:{}}]){const h=harness();await h.mount(options);assert.equal(h.calls.length,0);assert.equal(field(h.root,'Repeticiones · serie 1'),undefined);}
});
test('delete one record uses an explicit confirmation and preserves activity state',async()=>{
  const h=harness(saved());await h.mount();await button(h.root,'Eliminar registro de esta sesión').click();assert.equal(h.calls.filter(c=>c.method==='DELETE').length,0);assert.match(h.root.textContent,/estados se conservan/);await button(h.root,'Conservar mis registros').click();assert.equal(h.server.logs.length,1);await button(h.root,'Eliminar registro de esta sesión').click();await button(h.root,'Sí, eliminar este registro').click();assert.equal(h.server.logs.length,0);assert.equal(h.server.consent.granted,true);assert.match(h.root.textContent,/fue eliminado/);
});
test('withdraw and export are explicit scoped actions',async()=>{
  const h=harness(saved());await h.mount();assert.equal(h.downloads.length,0);await button(h.root,'Descargar mis registros').click();assert.equal(h.downloads.length,1);assert.equal(h.downloads[0].download,'mis-entrenamientos-roxy.json');await button(h.root,'Retirar permiso y borrar todos mis registros').click();assert.equal(h.calls.filter(c=>c.method==='DELETE').length,0);await button(h.root,'Sí, retirar permiso y borrar').click();assert.equal(h.server.logs.length,0);assert.equal(h.server.consent,null);
});
test('authorization failure immediately clears displayed private results',async()=>{
  const h=harness(saved(),(path,options)=>options.method==='DELETE'?response({detail:'Expired'},403):undefined);await h.mount();await button(h.root,'Eliminar registro de esta sesión').click();await button(h.root,'Sí, eliminar este registro').click();assert.match(h.root.textContent,/Vuelve a entrar/);assert.equal(field(h.root,'Repeticiones · serie 1'),undefined);assert.equal(button(h.root,'Marcar actividad completada'),undefined);
});
test('training UI has no browser database, provider speech, calendar write, telemetry or simulated completion',()=>{
  assert.doesNotMatch(source,/localStorage|sessionStorage|indexedDB|speechSynthesis|sendBeacon|console\.|\/calendar|\/agent|\/speech/);assert.match(source,/cache:'no-store'/);assert.match(source,/'X-Roxy-Fitness-Member'/);assert.match(source,/'X-Roxy-Fitness-Request'/);assert.match(source,/'Idempotency-Key'/);const css=fs.readFileSync(require.resolve('../assets/roxy_fitness_training.css'),'utf8');assert.match(css,/prefers-reduced-motion:reduce/);assert.match(css,/min-height:48px/);
});
