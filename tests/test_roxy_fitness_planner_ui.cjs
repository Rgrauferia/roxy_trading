'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {webcrypto}=require('node:crypto');
const api=require('../assets/roxy_fitness_planner.js');
const source=fs.readFileSync(require.resolve('../assets/roxy_fitness_planner.js'),'utf8');
const programAPI=require('../assets/roxy_fitness_programs.js');
const fixture=JSON.parse(fs.readFileSync(require.resolve('../data/home_fitness_source_programs_192.json'),'utf8'));
const programs=fixture.programs.map(row=>({...row,exercise_count:row.exercises.length}));
const flags={status:'education_only',active_training:false,can_activate_plans:false,clinical_approval:false,can_persist:false};
const clone=x=>JSON.parse(JSON.stringify(x));
const UUID='11111111-1111-4111-8111-111111111111';
const session=(extra={})=>({id:UUID,program_id:'gentle-strength',date:'2026-09-01',time:'09:00',starts_at:'2026-09-01T13:00:00+00:00',status:'planned',completed_at:null,...extra});
const consent={purpose:'fitness_activity_plan',text_version:'fitness-activity-plan-v1',granted:true,recorded_at:'2026-09-01T00:00:00Z'};
const saved=(sessions=[],version=1)=>({version,consent:clone(consent),plan:{title:'Mi plan de prueba',timezone:'America/New_York',sessions},progress:api.counts(sessions),updated_at:'2026-09-01T00:00:00Z'});
const empty=()=>({version:0,consent:null,plan:null,progress:api.counts(),updated_at:null});
const response=(data,status=200)=>({ok:status>=200&&status<300,status,json:async()=>clone(data)});
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
const flush=async()=>{for(let i=0;i<40;i++)await Promise.resolve();};
const descendants=node=>node.children.flatMap(child=>[child,...descendants(child)]);
const all=(node,tag)=>descendants(node).filter(child=>child.tagName===tag.toUpperCase());
const byClass=(node,name)=>descendants(node).filter(child=>(child.className||'').split(' ').includes(name));
const button=(node,label)=>all(node,'button').find(child=>child.textContent===label);
const field=(node,label)=>descendants(node).find(child=>child.getAttribute('aria-label')===label);
function harness(initial=empty(),intercept){
  let server=clone(initial),id=0,stopped=0,expectedIdentity='member-a';const calls=[],events={},downloads=[],voices=[],timers=new Map();
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
    focus(){this.focused=true;}scrollIntoView(){}
    async emit(name){for(const fn of this.events[name]||[])fn({target:this,preventDefault(){},stopPropagation(){}});await flush();}
    async click(){if(this.disabled)return;if(this.tagName==='A'){downloads.push(this);return;}await this.emit('click');}
  }
  const body=new Node('body');body.root=true;const root=new Node('div');body.append(root);
  const doc={hidden:false,createElement:tag=>new Node(tag),addEventListener:(name,fn)=>events[name]=fn};
  const context={document:doc,Intl,Date,Map,Set,AbortController,Blob,crypto:webcrypto,RoxyFitnessPrograms:programAPI,
    RoxyHomeTour:{stop(){stopped++;},speak:async(key,cb)=>{voices.push(key);cb('playing','Roxy está hablando.');}},
    URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},
    setTimeout(fn){const token=++id;timers.set(token,fn);return token;},clearTimeout(token){timers.delete(token);},addEventListener:(name,fn)=>events[name]=fn,
    fetch:async(path,options)=>{
      calls.push({path,...options,payload:options.body?JSON.parse(options.body):undefined});
      assert.equal(options.credentials,'same-origin');assert.equal(options.cache,'no-store');assert.equal(options.headers['X-Roxy-Fitness-Member'],expectedIdentity);
      const override=intercept?.(path,options,calls.length);if(override!==undefined)return await override;
      if(path==='/api/fitness/v1/programs')return response({...flags,programs,total:programs.length});
      if(path.startsWith('/api/fitness/v1/programs/'))return response({...flags,program:programs.find(row=>path.endsWith('/'+row.id))});
      if(options.method==='GET')return response(server);
      assert.equal(options.headers['X-Roxy-Fitness-Request'],'1');assert.ok(options.headers['Idempotency-Key']);
      const data=JSON.parse(options.body);assert.equal(data.expected_version,server.version);
      if(path.endsWith('/consent'))server={...server,version:server.version+1,consent:clone(consent)};
      else if(options.method==='PUT'){server=saved(data.plan.sessions.map(row=>{const old=server.plan?.sessions.find(item=>['id','program_id','date','time'].every(key=>item[key]===row[key]));return {...row,starts_at:old?.starts_at||row.date+'T13:00:00Z',status:old?.status||'planned',completed_at:old?.completed_at||null};}),server.version+1);server.plan.title=data.plan.title;server.plan.timezone=data.plan.timezone;}
      else if(options.method==='PATCH'){server=clone(server);server.version++;const row=server.plan.sessions.find(row=>path.endsWith('/'+row.id));row.status=data.status;row.completed_at=data.status==='completed'?'2026-09-14T16:00:00Z':null;server.progress=api.counts(server.plan.sessions);}
      else if(options.method==='DELETE')server={...empty(),version:server.version+1};
      return response(server);
    }};context.window=context;vm.runInNewContext(source,context);
  return {api:context.RoxyFitnessPlanner,root,body,calls,events,downloads,voices,timers,document:doc,get server(){return clone(server);},get stopped(){return stopped;},newRoot(){const node=new Node('div');body.append(node);return node;},async mount(view='week',scheduleActivity,options={}){expectedIdentity=options.identity||'member-a';context.RoxyFitnessPlanner.mount(root,{identity:expectedIdentity,timezone:'America/New_York',view,scheduleActivity,...options});await flush();},async visibility(hidden){doc.hidden=hidden;events.visibilitychange();await flush();}};
}
async function fillDraft(h){await button(h.root,'Crear mi plan').click();const guide=field(h.root,'Guía de actividad 1');guide.value='gentle-strength';await guide.emit('change');for(const [name,value] of [['Fecha de actividad 1','2026-09-01'],['Hora de actividad 1','09:00']]){const node=field(h.root,name);node.value=value;await node.emit('input');}await all(h.root,'form')[0].emit('submit');}

test('invalid dates/timezones are rejected and progress counts only real supplied statuses',()=>{
  assert.equal(api.dateOK('2026-99-99'),false);assert.equal(api.dateOK('2026-02-29'),false);assert.equal(api.dateOK('2028-02-29'),true);assert.equal(api.timeOK('24:00'),false);assert.equal(api.zoneOK('Bad/Zone'),false);
  assert.deepEqual(api.counts([session(),session({status:'completed'}),session({status:'skipped'})]),{planned:1,completed:1,skipped:1,total:3});
  assert.deepEqual(api.localNow('America/New_York',new Date('2026-09-14T02:00:00Z')),{date:'2026-09-13',time:'22:00'});
});
test('new dates preserve every existing activity and IDs without copying status into writes',()=>{
  const old=session({status:'completed',completed_at:'2026-09-01T15:00:00Z'}),row=session({id:'22222222-2222-4222-8222-222222222222',date:'2026-09-03'});
  const value=api.draftPlan({sessions:[old],timezone:'America/New_York'},' Mi plan ','America/New_York',[row]);assert.equal(value.title,'Mi plan');assert.equal(value.sessions.length,2);assert.equal(value.sessions[0].id,old.id);assert.equal(value.sessions[0].status,undefined);assert.equal(old.status,'completed');
  assert.throws(()=>api.draftPlan({sessions:[old],timezone:'America/New_York'},'Plan','UTC',[row,{...row,id:'33333333-3333-4333-8333-333333333333'}]));
});
test('inconsistent summary, session or permission never becomes a trusted snapshot',()=>{
  for(const mutate of [p=>p.progress.completed=20,p=>p.plan.sessions[0].status='approved',p=>p.plan.sessions[0].date='2026-99-99',p=>p.plan.sessions.push(p.plan.sessions[0]),p=>p.consent.purpose='other',p=>p.plan.timezone='bad']){const p=saved([session()]);mutate(p);assert.throws(()=>api.snapshot(p));}
});
test('creation requires review and explicit consent; reload restores saved activities',async()=>{
  const h=harness();await h.mount();await fillDraft(h);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);await button(h.root,'Guardar mi plan').click();assert.match(h.root.textContent,/Confirma que autorizas/);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
  const check=all(h.root,'input').find(n=>n.type==='checkbox');check.checked=true;await check.emit('change');await button(h.root,'Guardar mi plan').click();
  assert.deepEqual(h.calls.filter(c=>c.method!=='GET').map(c=>c.method),['POST','PUT']);assert.equal(h.server.plan.sessions.length,1);assert.match(h.root.textContent,/quedó guardado/);
  h.api.setActive(false);assert.equal(h.root.textContent,'');h.api.setActive(true);await flush();assert.equal(byClass(h.root,'fxpl-session').length,1);assert.match(h.root.textContent,/Mi semana de movimiento/);
});
test('opening/advancing the guide never marks a session complete; voice uses original fixed keys',async()=>{
  const h=harness(saved([session()]));await h.mount();await button(h.root,'Empezar mi actividad').click();assert.match(h.root.textContent,/Movimiento 1 de 7/);await button(h.root,'Escuchar a Roxy').click();assert.deepEqual(h.voices,['fitness:strength:0']);await button(h.root,'Siguiente movimiento').click();assert.match(h.root.textContent,/Movimiento 2 de 7/);assert.ok(h.stopped>0);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
  await button(h.root,'Terminé · registrar realizada').click();assert.match(h.root.textContent,/¿Realizaste/);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);await button(h.root,'Sí, la realicé').click();assert.equal(h.server.progress.completed,1);assert.match(h.root.textContent,/Realizada/);
});
test('future activities cannot be self-reported as already completed',async()=>{
  const h=harness(saved([session({date:'2099-09-01',starts_at:'2099-09-01T13:00:00Z'})]));await h.mount();assert.equal(button(h.root,'Marcar realizada').disabled,true);await button(h.root,'Marcar realizada').click();assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
});
test('omitted and pending corrections update persisted progress only after confirmation',async()=>{
  const h=harness(saved([session()]));await h.mount('progress');await button(h.root,'Cancelar esta actividad').click();await button(h.root,'Sí, cancelar actividad').click();assert.equal(h.server.progress.skipped,1);await button(h.root,'Volver a pendiente').click();await button(h.root,'Confirmar pendiente').click();assert.equal(h.server.progress.skipped,0);assert.equal(h.server.progress.planned,1);
});
test('calendar handoff is explicit and carries only scheduling fields, never program/member data',async()=>{
  const calls=[],h=harness(saved([session()]));await h.mount('week',value=>calls.push(value));assert.equal(calls.length,0);await button(h.root,'Añadir al calendario Home').click();assert.equal(calls.length,1);assert.deepEqual(JSON.parse(JSON.stringify(calls[0])),{date:'2026-09-01',time:'09:00',timezone:'America/New_York',starts_at:'2026-09-01T13:00:00+00:00'});assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
});
test('mutation conflict does not overwrite newer server data',async()=>{
  const h=harness(saved([session()]),(path,options)=>options.method==='PATCH'?response({detail:{message:'Conflict'}},409):undefined);await h.mount();await button(h.root,'Cancelar esta actividad').click();await button(h.root,'Sí, cancelar actividad').click();assert.match(h.root.textContent,/cambió en otra sesión/);assert.equal(button(h.root,'Sí, cancelar actividad'),undefined);assert.equal(h.server.progress.planned,1);await button(h.root,'Comprobar guardado').click();assert.equal(byClass(h.root,'fxpl-session').length,1);
});
test('unavailable private storage has retry and no fake plan or active save button',async()=>{
  const h=harness(empty(),()=>response({detail:{message:'Unavailable'}},503));await h.mount();assert.match(h.root.textContent,/guardado privado.*no está disponible/);assert.equal(button(h.root,'Crear mi plan'),undefined);assert.ok(button(h.root,'Volver a cargar mi plan'));
});
test('expired member authorization erases loaded activity details after a failed write',async()=>{
  const h=harness(saved([session()]),(path,options)=>options.method==='PATCH'?response({detail:{message:'Session expired'}},403):undefined);await h.mount();await button(h.root,'Cancelar esta actividad').click();await button(h.root,'Sí, cancelar actividad').click();assert.doesNotMatch(h.root.textContent,/Mi plan de prueba|Fuerza/);assert.match(h.root.textContent,/La sesión cambió/);
});
test('late responses after leaving cannot restore private data',async()=>{
  const pending=deferred(),h=harness(empty(),(path,options,n)=>n===1?pending.promise:undefined);h.api.mount(h.root,{identity:'member-a',timezone:'UTC'});await flush();h.api.setActive(false);pending.resolve(response(saved([session()])));await flush();assert.equal(h.root.textContent,'');
});
test('tab hiding clears data and rechecks the server before showing it again',async()=>{
  const h=harness(saved([session()]));await h.mount();const reads=h.calls.filter(c=>c.path.endsWith('activity-plan')).length;await h.visibility(true);assert.equal(h.root.textContent,'');await h.visibility(false);assert.ok(h.calls.filter(c=>c.path.endsWith('activity-plan')).length>reads);assert.match(h.root.textContent,/Mi plan de prueba/);
});
test('delete requires confirmation and reports empty state from the server',async()=>{
  const h=harness(saved([session()]));await h.mount();await button(h.root,'Eliminar plan y registros').click();assert.equal(h.calls.filter(c=>c.method==='DELETE').length,0);await button(h.root,'Sí, eliminar mi plan').click();assert.equal(h.server.plan,null);assert.equal(h.server.progress.total,0);assert.match(h.root.textContent,/fueron eliminados/);
});
test('source reader and activity persistence use no browser databases or generated training endpoints',()=>{
  assert.doesNotMatch(source,/localStorage|sessionStorage|indexedDB|\/plans\/preview|can_activate_plans\s*[:=]\s*true|speechSynthesis/);
});


test('rescheduling preserves existing IDs and every completed activity and rejects changes to completed history',()=>{
  const pending=session(),complete=session({id:'22222222-2222-4222-8222-222222222222',status:'completed',completed_at:'2026-09-02T00:00:00Z',date:'2026-09-02'}),base=saved([pending,complete]).plan;
  const plan=api.reschedulePlan(base,{...pending,date:'2026-09-03',time:'10:30'});assert.equal(plan.sessions.length,2);assert.equal(plan.sessions.find(s=>s.id===pending.id).date,'2026-09-03');assert.equal(plan.sessions.find(s=>s.id===complete.id).date,complete.date);assert.equal(plan.timezone,base.timezone);
  assert.throws(()=>api.reschedulePlan(base,{...complete,date:'2026-09-05'}));assert.throws(()=>api.draftPlan(base,'Changed','UTC',[{...pending,id:'33333333-3333-4333-8333-333333333333',date:'2026-09-05'}]));
});
test('saved timezone is read-only and a pending reschedule requires review before the PUT',async()=>{
  const h=harness(saved([session()]));await h.mount();await button(h.root,'Reprogramar').click();assert.equal(field(h.root,'Zona horaria').readOnly,true);const date=field(h.root,'Fecha de actividad 1');date.value='2026-09-03';await date.emit('input');await all(h.root,'form')[0].emit('submit');assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);assert.match(h.root.textContent,/Solo cambia esta actividad pendiente/);await button(h.root,'Guardar cambio').click();const write=h.calls.find(c=>c.method==='PUT');assert.equal(write.payload.plan.sessions[0].id,UUID);assert.equal(write.payload.plan.sessions[0].date,'2026-09-03');assert.match(h.root.textContent,/quedó reprogramada/);
});


test('transport failures show a Spanish recovery message instead of raw browser errors',async()=>{
  const h=harness(empty(),()=>{throw new TypeError('Failed to fetch');});await h.mount();assert.match(h.root.textContent,/No pude conectar con tu plan. Revisa la conexión y vuelve a intentarlo/);assert.doesNotMatch(h.root.textContent,/Failed to fetch/);assert.ok(button(h.root,'Volver a cargar mi plan'));
});


test('private cinematic reader changes source indications without writes or automatic voice and preserves source attribution',async()=>{
  const h=harness(saved([session()]));await h.mount();await button(h.root,'Empezar mi actividad').click();
  let reader=byClass(h.root,'fx-session-cinema')[0];assert.equal(reader.getAttribute('data-fx-reading'),'true');assert.deepEqual(h.voices,[]);
  const exercise=programs[0].exercises[0];assert.equal(byClass(reader,'fx-session-current-instruction')[0].textContent,exercise.instructions_es[0]);
  assert.deepEqual(all(byClass(reader,'fxpl-instructions')[0],'p').map(p=>p.textContent),exercise.instructions_es);
  await button(reader,'Siguiente indicación').click();reader=byClass(h.root,'fx-session-cinema')[0];assert.equal(byClass(reader,'fx-session-current-instruction')[0].textContent,exercise.instructions_es[1]);
  await button(reader,'Ver original en inglés').click();reader=byClass(h.root,'fx-session-cinema')[0];assert.equal(byClass(reader,'fx-session-current-instruction')[0].textContent,exercise.instructions_en[1]);assert.match(reader.textContent,new RegExp(programs[0].checked_on));
  await button(reader,'Repetir voz').click();assert.equal(h.voices.at(-1),'fitness:strength:0');const stops=h.stopped;await button(h.root,'Siguiente movimiento').click();assert.equal(h.stopped,stops+1);assert.match(h.root.textContent,/Indicación 1 de/);
  assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);await button(h.root,'Volver a mi plan').click();assert.equal(byClass(h.root,'fx-session-cinema').length,0);assert.equal(h.server.progress.completed,0);
});
test('cinematic completion waits for confirmed successful PATCH before showing completed progress',async()=>{
  const pending=deferred(),h=harness(saved([session()]),(path,options)=>options.method==='PATCH'?pending.promise:undefined);
  await h.mount();await button(h.root,'Empezar mi actividad').click();await button(h.root,'Terminé · registrar realizada').click();
  assert.equal(h.calls.filter(c=>c.method==='PATCH').length,0);assert.equal(byClass(h.root,'fx-session-cinema').length,0);
  await button(h.root,'Sí, la realicé').click();assert.equal(h.calls.filter(c=>c.method==='PATCH').length,1);assert.equal(byClass(h.root,'fxpl-completed').length,0);assert.doesNotMatch(h.root.textContent,/Registro actualizado/);
  pending.resolve(response(saved([session({status:'completed',completed_at:'2026-09-14T16:00:00Z'})],2)));await flush();assert.equal(byClass(h.root,'fxpl-completed').length,1);assert.match(h.root.textContent,/Registro actualizado en tu perfil/);
});

test('switching from an open cinematic reader to progress closes the reader and shows saved counts without a write',async()=>{
  const h=harness(saved([session()]));await h.mount('week');await button(h.root,'Empezar mi actividad').click();await button(h.root,'Escuchar a Roxy').click();
  assert.equal(byClass(h.root,'fx-session-cinema').length,1);const stopped=h.stopped;
  await h.mount('progress');assert.equal(byClass(h.root,'fx-session-cinema').length,0);assert.ok(h.stopped>stopped);assert.match(h.root.textContent,/Tu constancia, día a día/);
  const stats=byClass(h.root,'fxpl-stats')[0];assert.ok(stats);assert.deepEqual(all(stats,'strong').map(n=>n.textContent),['0','1','0']);
  assert.equal(h.calls.filter(call=>call.method!=='GET').length,0);assert.equal(h.server.progress.completed,0);
});

const PROPOSAL_ID='22222222-2222-4222-8222-222222222222';
const profileSnapshot=(version=4)=>({version,consent:{purpose:'fitness_preferences',text_version:'fitness-preferences-v1',granted:true}});
function proposalPayload(planVersion=0){
  return {profile_version:4,activity_plan_version:planVersion,proposal:{version:'fitness-agenda-proposal-212-v1',status:'ready',timezone:'America/New_York',start_date:'2099-09-01',end_date:'2099-09-07',allocated_minutes:20,travel_minutes:10,source_duration_minutes:null,clinical_approval:false,can_activate_training:false,notice_es:'La fuente no indica una duración total.',sessions:[{id:PROPOSAL_ID,program_id:'gentle-strength',date:'2099-09-01',time:'09:00'}],session_details:[{session_id:PROPOSAL_ID,allocated_minutes:20,travel_minutes:10,source_duration_minutes:null,starts_at:'2099-09-01T13:00:00+00:00',reserved_until:'2099-09-01T13:30:00+00:00'}],excluded_days:Array.from({length:6},(_,i)=>({date:`2099-09-0${i+2}`,message_es:'No indicaste disponibilidad para ese día.'}))}};
}
async function chooseProposal(h){
  await button(h.root,'Organizar con mi disponibilidad').click();
  const date=field(h.root,'Fecha de inicio de la propuesta');date.value='2099-09-01';await date.emit('input');
  const check=field(h.root,`Incluir ${programs[0].title_es}`);check.checked=true;await check.emit('change');
}
async function prepareProposal(h){await chooseProposal(h);await all(h.root,'form')[0].emit('submit');}
const proposalIntercept=(version=0,profile=profileSnapshot())=>(path)=>path.endsWith('/proposal')?response(proposalPayload(version)):path.endsWith('/me/profile')?response(profile):undefined;

test('proposal validation rejects stale versions, mismatched weeks, doses, timestamps and unselected or occupied activities',()=>{
  const owner={saved:saved([session()],2),timezone:'America/New_York',proposalSetup:{startDate:'2099-09-01',programIds:['gentle-strength']}};
  assert.deepEqual(api.proposalSnapshot(proposalPayload(2),owner),proposalPayload(2));
  for(const modify of [
    p=>p.activity_plan_version=1,p=>p.profile_version=-1,p=>p.proposal.version='unknown',
    p=>p.proposal.start_date='2099-09-02',p=>p.proposal.end_date='2099-09-08',p=>p.proposal.timezone='UTC',
    p=>p.proposal.source_duration_minutes=20,p=>p.proposal.clinical_approval=true,p=>p.proposal.can_activate_training=true,
    p=>p.proposal.sessions[0].program_id='gentle-balance',p=>p.proposal.sessions[0].id=UUID,
    p=>p.proposal.sessions[0]=null,p=>p.proposal.session_details[0]=null,
    p=>p.proposal.session_details[0].reserved_until='2099-09-01T13:20:00Z',
    p=>{p.proposal.session_details[0].starts_at='2099-09-01T14:00:00Z';p.proposal.session_details[0].reserved_until='2099-09-01T14:30:00Z';},
    p=>p.proposal.session_details[0].starts_at='September 1 2099',
    p=>p.proposal.excluded_days[0]=null,p=>p.proposal.excluded_days.pop(),
    p=>p.proposal.excluded_days[0].date='2099-09-01',p=>p.proposal.excluded_days[0].date='2099-09-08'
  ]){const payload=proposalPayload(2);modify(payload);assert.throws(()=>api.proposalSnapshot(payload,owner));}
  const occupied={...owner,saved:saved([session({date:'2099-09-01'})],2)};assert.throws(()=>api.proposalSnapshot(proposalPayload(2),occupied));
});

test('proposal only posts explicit selected guides and date, then creates an editable draft without saving',async()=>{
  const h=harness(empty(),proposalIntercept());await h.mount();await button(h.root,'Organizar con mi disponibilidad').click();
  await all(h.root,'form')[0].emit('submit');assert.match(h.root.textContent,/Elige al menos una guía/);assert.equal(h.calls.filter(c=>c.method==='POST').length,0);
  await button(h.root,'Cancelar').click();await prepareProposal(h);
  const call=h.calls.find(c=>c.path.endsWith('/proposal'));assert.equal(call.method,'POST');assert.equal(call.headers['X-Roxy-Fitness-Request'],'1');assert.ok(call.headers['Idempotency-Key']);
  assert.deepEqual(call.payload,{start_date:'2099-09-01',program_ids:['gentle-strength'],expected_version:0});
  assert.ok(field(h.root,'Hora de actividad 1'));assert.match(h.root.textContent,/fuente no indica la duración total/);assert.equal(h.server.plan,null);assert.equal(h.calls.filter(c=>c.method==='PUT'||c.path.endsWith('/consent')).length,0);
});

test('reviewed proposal preserves completed history and saves edited choices only after rechecking preferences',async()=>{
  const old=session({status:'completed',completed_at:'2026-09-01T15:00:00Z'}),h=harness(saved([old],2),proposalIntercept(2));await h.mount();await prepareProposal(h);
  const time=field(h.root,'Hora de actividad 1');time.value='10:30';await time.emit('input');await all(h.root,'form')[0].emit('submit');
  assert.match(h.root.textContent,/Conservaremos tus 1 actividades anteriores/);assert.equal(h.calls.filter(c=>c.method==='PUT').length,0);await button(h.root,'Guardar mi plan').click();
  const write=h.calls.find(c=>c.method==='PUT'),check=h.calls.findIndex(c=>c.path.endsWith('/me/profile'));assert.ok(check>=0&&check<h.calls.indexOf(write));assert.equal(write.payload.expected_version,2);
  assert.equal(write.payload.plan.sessions.length,2);assert.deepEqual(write.payload.plan.sessions[0],{id:old.id,program_id:old.program_id,date:old.date,time:old.time});assert.equal(write.payload.plan.sessions[1].time,'10:30');assert.equal(write.payload.plan.sessions[1].status,undefined);
  assert.equal(h.server.plan.sessions[0].status,'completed');assert.equal(h.server.progress.completed,1);assert.equal(h.server.plan.sessions[1].status,'planned');
});

test('proposal on empty agenda still requires explicit consent before any persistence',async()=>{
  const h=harness(empty(),proposalIntercept());await h.mount();await prepareProposal(h);await all(h.root,'form')[0].emit('submit');await button(h.root,'Guardar mi plan').click();
  assert.match(h.root.textContent,/Confirma que autorizas/);assert.equal(h.calls.filter(c=>c.path.endsWith('/consent')||c.method==='PUT').length,0);
  const consentCheck=all(h.root,'input').find(n=>n.type==='checkbox');consentCheck.checked=true;await consentCheck.emit('change');await button(h.root,'Guardar mi plan').click();
  assert.deepEqual(h.calls.filter(c=>c.method!=='GET').map(c=>c.path.split('/').at(-1)),['proposal','consent','activity-plan']);assert.equal(h.server.plan.sessions.length,1);
});

test('missing preferences keep proposal choices and offer the real preferences callback without writes',async()=>{
  let opened=0;const h=harness(empty(),path=>path.endsWith('/proposal')?response({detail:{code:'missing_preferences',message:'Primero guarda tus preferencias de Ejercicio.'}},422):undefined);
  await h.mount('week',undefined,{onPreferences:()=>opened++});await prepareProposal(h);assert.match(h.root.textContent,/Primero guarda tus preferencias/);assert.equal(field(h.root,`Incluir ${programs[0].title_es}`).checked,true);
  await button(h.root,'Revisar mi disponibilidad').click();assert.equal(opened,1);assert.equal(h.calls.filter(c=>c.method==='PUT').length,0);
});

test('no matching slots reports excluded days without making a draft or claiming a personalized workout',async()=>{
  const payload=proposalPayload();payload.proposal.status='no_slots';payload.proposal.sessions=[];payload.proposal.session_details=[];payload.proposal.excluded_days.unshift({date:'2099-09-01',message_es:'Ninguna ventana permite reservar tus minutos.'});
  const h=harness(empty(),path=>path.endsWith('/proposal')?response(payload):undefined);await h.mount();await prepareProposal(h);assert.match(h.root.textContent,/Ninguna ventana permite/);assert.ok(button(h.root,'Proponer horarios'));assert.equal(button(h.root,'Revisar mi plan'),undefined);assert.equal(h.server.plan,null);
});

test('changed profile version blocks proposal persistence and offers a fresh proposal',async()=>{
  const h=harness(saved([session()],2),proposalIntercept(2,profileSnapshot(5)));await h.mount();await prepareProposal(h);await all(h.root,'form')[0].emit('submit');await button(h.root,'Guardar mi plan').click();
  assert.match(h.root.textContent,/Tus preferencias cambiaron/);assert.equal(button(h.root,'Guardar mi plan'),undefined);assert.equal(button(h.root,'Comprobar guardado'),undefined);assert.ok(button(h.root,'Volver a organizar horarios'));assert.equal(h.calls.filter(c=>c.method==='PUT').length,0);
  await button(h.root,'Volver a organizar horarios').click();assert.ok(button(h.root,'Proponer horarios'));
});

test('withdrawn or unverifiable preference consent blocks proposal persistence even if its version matches',async()=>{
  for(const modify of [p=>p.consent.granted=false,p=>p.consent.purpose='other',p=>p.consent.text_version='unknown']){
    const profile=profileSnapshot();modify(profile);const h=harness(saved([session()],2),proposalIntercept(2,profile));await h.mount();await prepareProposal(h);await all(h.root,'form')[0].emit('submit');await button(h.root,'Guardar mi plan').click();assert.match(h.root.textContent,/Tus preferencias cambiaron/);assert.equal(h.calls.filter(c=>c.method==='PUT'||c.path.endsWith('/consent')).length,0);
  }
});

test('unknown save outcome blocks repeated submission until a fresh server read',async()=>{
  const h=harness(saved([session()],2),(path,options)=>options.method==='PUT'?Promise.reject(new TypeError('Failed to fetch')):proposalIntercept(2)(path));await h.mount();await prepareProposal(h);await all(h.root,'form')[0].emit('submit');await button(h.root,'Guardar mi plan').click();
  assert.ok(button(h.root,'Comprobar guardado'));assert.equal(button(h.root,'Guardar mi plan'),undefined);assert.equal(button(h.root,'Organizar con mi disponibilidad'),undefined);assert.equal(h.calls.filter(c=>c.method==='PUT').length,1);
  await button(h.root,'Comprobar guardado').click();assert.ok(button(h.root,'Organizar con mi disponibilidad'));assert.equal(h.server.plan.sessions.length,1);
});

test('an unknown save is rechecked when returning from a hidden tab',async()=>{
  const h=harness(saved([session()],2),(path,options)=>options.method==='PUT'?Promise.reject(new TypeError('Failed to fetch')):proposalIntercept(2)(path));await h.mount();await prepareProposal(h);await all(h.root,'form')[0].emit('submit');await button(h.root,'Guardar mi plan').click();await h.visibility(true);assert.equal(h.root.textContent,'');await h.visibility(false);assert.ok(button(h.root,'Organizar con mi disponibilidad'));assert.equal(h.calls.filter(c=>c.method==='PUT').length,1);
});

test('late proposal response after member change cannot restore private proposal choices',async()=>{
  const pending=deferred(),h=harness(empty(),path=>path.endsWith('/proposal')?pending.promise:undefined);await h.mount();await prepareProposal(h);await h.mount('week',undefined,{identity:'member-b'});pending.resolve(response(proposalPayload()));await flush();
  assert.equal(field(h.root,'Hora de actividad 1'),undefined);assert.equal(button(h.root,'Revisar mi plan'),undefined);assert.equal(h.calls.filter(c=>c.method==='PUT').length,0);assert.equal(h.calls.at(-1).headers['X-Roxy-Fitness-Member'],'member-b');
});

test('progress history is collapsed by default while real counts stay visible',async()=>{
  const h=harness(saved([session()]));await h.mount('progress');const history=byClass(h.root,'fxpl-progress-history')[0];assert.ok(history);assert.notEqual(history.open,true);assert.equal(all(history,'summary')[0].textContent,'Historial de actividades (1)');assert.ok(byClass(h.root,'fxpl-stats')[0]);assert.equal(button(h.root,'Organizar con mi disponibilidad'),undefined);
});
