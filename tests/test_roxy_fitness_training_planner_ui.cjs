'use strict';
// Reuse the existing synthetic DOMs; no live browser, account, timer or database.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const api=require('../assets/roxy_fitness_planner.js');
const clone=value=>JSON.parse(JSON.stringify(value));
const PREFIX='/api/fitness/v1/me/activity-plan';
const ID='77777777-7777-4777-8777-777777777777';
const NEW='88888888-8888-4888-8888-888888888888';
const OLD='99999999-9999-4999-8999-999999999999';
const training=(extra={})=>({id:ID,program_id:'home-dumbbell-foundations',date:'2026-09-01',time:'09:00',
  content_version:'home-training-213-v1',confirmed_requirements:{equipment:['bodyweight','dumbbells','wall'],capabilities:['free_weights','hip_hinge','standing']},
  reserved_minutes:45,travel_minutes:10,starts_at:'2026-09-01T13:00:00Z',status:'planned',completed_at:null,...extra});
const legacy=()=>({id:OLD,program_id:'gentle-flexibility',date:'2026-08-31',time:'10:00',starts_at:'2026-08-31T14:00:00Z',status:'completed',completed_at:'2026-08-31T15:00:00Z'});
const consent={purpose:'fitness_activity_plan',text_version:'fitness-activity-plan-v1',granted:true,recorded_at:'2026-08-01T00:00:00Z'};
const saved=(sessions=[],version=2)=>({version,consent:clone(consent),plan:{title:'Mi historial conservado',timezone:'America/New_York',sessions},progress:api.counts(sessions),updated_at:'2026-09-01T00:00:00Z'});
const empty=()=>({version:0,consent:null,plan:null,progress:api.counts(),updated_at:null});
const profile=(version=4)=>({version,consent:{purpose:'fitness_preferences',text_version:'fitness-preferences-v1',granted:true}});
const response=(value,status=200)=>({ok:status>=200&&status<300,status,json:async()=>clone(value)});
const descendants=node=>node.children.flatMap(child=>[child,...descendants(child)]);
const all=(node,tag)=>descendants(node).filter(child=>child.tagName===tag.toUpperCase());
const button=(node,label)=>all(node,'button').find(child=>child.textContent===label);
const field=(node,label)=>descendants(node).find(child=>child.getAttribute('aria-label')===label);
const flush=async()=>{for(let i=0;i<40;i++)await Promise.resolve();};

const oldHarness=fs.readFileSync(require.resolve('./test_roxy_fitness_planner_ui.cjs'),'utf8').split("test('invalid dates/timezones")[0];
const makePlanner=new Function('require','initial','intercept',oldHarness+'\nreturn harness(initial,intercept);');
const harness=(initial=saved([legacy(),training()]),intercept)=>makePlanner(require,initial,(path,options,index)=>
  intercept?.(path,options,index)??(path.endsWith('/me/profile')?response(profile()):undefined));
function proposal(version=2){
  const row=api.sessionInput(training({id:NEW,date:'2099-09-01'}));
  return {profile_version:4,activity_plan_version:version,proposal:{version:'home-training-proposal-213-v1',status:'ready',
    program_id:row.program_id,title:'Mancuernas, a tu ritmo',content_version:row.content_version,clinical_approval:false,
    timezone:'America/New_York',start_date:'2099-09-01',end_date:'2099-09-07',reserved_minutes:45,travel_minutes:10,
    estimated_minutes:{min:20,max:34,kind:'editorial_estimate'},notice_es:'Tiempo estimado; descansa a tu ritmo.',
    sessions:[row],session_details:[{session_id:NEW,starts_at:'2099-09-01T13:00:00Z',reserved_until:'2099-09-01T13:55:00Z'}],
    excluded_days:Array.from({length:6},(_,index)=>({date:`2099-09-0${index+2}`,message_es:'Sin una nueva actividad.'}))}};
}

function parentHarness(){
  let prefix=fs.readFileSync(require.resolve('./test_roxy_fitness_ui.cjs'),'utf8').split("test('today and week")[0];
  prefix=prefix.replace('context.window=context;',`context.RoxyFitnessTraining={mount(node,options){programCalls.push({type:'training',options});},clear(){programCalls.push({type:'training-clear'});},setActive(active){programCalls.push({type:'training-active',active});}};
    context.RoxyFitnessTrainingSession={clear(){programCalls.push({type:'session-clear'});},setActive(active){programCalls.push({type:'session-active',active});}};context.window=context;`);
  return new Function('require','__dirname',prefix+'\nreturn harness(true);')(require,__dirname);
}

test('training metadata is copied deeply and retained by every input transformation',()=>{
  const row=training(),meta=api.trainingMetadata(row),input=api.sessionInput(row);
  assert.deepEqual(meta.confirmed_requirements,row.confirmed_requirements);
  meta.confirmed_requirements.equipment.push('bench');assert.equal(row.confirmed_requirements.equipment.includes('bench'),false);
  assert.equal(input.content_version,row.content_version);assert.equal(input.reserved_minutes,45);assert.equal(input.travel_minutes,10);
  assert.equal(input.status,undefined);assert.equal(input.completed_at,undefined);assert.equal(input.starts_at,undefined);
  const initial=saved([legacy(),row]).plan,appended=api.draftPlan(initial,initial.title,initial.timezone,[proposal().proposal.sessions[0]]);
  assert.equal(appended.sessions.length,3);assert.deepEqual(appended.sessions.find(s=>s.id===ID),api.sessionInput(row));
  assert.deepEqual(appended.sessions.find(s=>s.id===OLD),api.sessionInput(legacy()));
  assert.deepEqual(initial,saved([legacy(),training()]).plan);
});

test('missing malformed or duplicate requirements never enter a trusted training snapshot',()=>{
  for(const change of [row=>delete row.content_version,row=>delete row.confirmed_requirements,row=>row.reserved_minutes='45',row=>row.reserved_minutes=4,
    row=>row.travel_minutes=-1,row=>row.confirmed_requirements.equipment.push('dumbbells'),row=>row.confirmed_requirements.capabilities=['medical_clearance']]){
    const row=training();change(row);assert.throws(()=>api.trainingMetadata(row));assert.throws(()=>api.snapshot(saved([row])));
  }
});

test('training proposal validates every day, scheduling metadata and current agenda version',()=>{
  const owner={saved:saved([legacy(),training()]),timezone:'America/New_York'};
  assert.deepEqual(api.trainingProposalSnapshot(proposal(),owner),proposal());
  for(const change of [p=>p.activity_plan_version=1,p=>p.profile_version=-1,p=>p.proposal.version='old',p=>p.proposal.clinical_approval=true,
    p=>p.proposal.sessions[0].id=ID,p=>p.proposal.sessions[0].content_version='other',p=>p.proposal.sessions[0].program_id='core-foundations',
    p=>p.proposal.sessions[0].reserved_minutes=30,p=>p.proposal.sessions[0].travel_minutes=0,p=>p.proposal.timezone='UTC',p=>p.proposal.end_date='2099-09-08',
    p=>p.proposal.session_details[0].reserved_until='2099-09-01T13:45:00Z',p=>p.proposal.session_details[0].starts_at='bad',
    p=>p.proposal.excluded_days.pop(),p=>p.proposal.excluded_days[0].date='2099-09-01',p=>p.proposal.sessions.push(p.proposal.sessions[0])]){
    const value=proposal();change(value);assert.throws(()=>api.trainingProposalSnapshot(value,owner));
  }
});

test('pending reschedule keeps requirements and unrelated history; changing routine requires a new selection',()=>{
  const initial=saved([legacy(),training()]).plan;
  const changed=api.reschedulePlan(initial,{...training(),date:'2026-09-03',time:'10:00'});
  assert.deepEqual(changed.sessions.find(row=>row.id===OLD),api.sessionInput(legacy()));
  const row=changed.sessions.find(row=>row.id===ID);
  assert.deepEqual(row.confirmed_requirements,training().confirmed_requirements);assert.equal(row.content_version,training().content_version);
  assert.equal(row.reserved_minutes,45);assert.equal(row.travel_minutes,10);
  assert.throws(()=>api.reschedulePlan(initial,{...training(),program_id:'core-foundations'}));
  assert.throws(()=>api.reschedulePlan(initial,{...legacy(),date:'2026-09-04'}));
});

test('importing a routine makes an explicit review draft and appends only after profile recheck',async()=>{
  let consumed=0;const h=harness();await h.mount('week',undefined,{trainingProposal:proposal(),onTrainingConsumed(){consumed++;}});
  assert.equal(consumed,1);assert.equal(h.calls.filter(call=>call.method!=='GET').length,0);
  assert.match(h.root.textContent,/La duración es estimada/);assert.equal(button(h.root,'Añadir otra fecha'),undefined);
  const guide=field(h.root,'Guía de actividad 1');assert.deepEqual(all(guide,'option').map(o=>o.value),['','home-dumbbell-foundations']);
  await all(h.root,'form')[0].emit('submit');assert.match(h.root.textContent,/Conservaremos tus 2 actividades anteriores/);
  assert.equal(h.calls.filter(call=>call.method==='PUT').length,0);await button(h.root,'Guardar mi plan').click();
  const write=h.calls.find(call=>call.method==='PUT');assert.equal(write.payload.expected_profile_version,4);assert.equal(write.payload.expected_version,2);
  assert.ok(h.calls.findIndex(call=>call.path.endsWith('/me/profile'))<h.calls.indexOf(write));
  assert.equal(write.payload.plan.sessions.length,3);assert.deepEqual(write.payload.plan.sessions.find(row=>row.id===ID),api.sessionInput(training()));
  assert.deepEqual(write.payload.plan.sessions.find(row=>row.id===NEW),proposal().proposal.sessions[0]);
  assert.equal(h.server.plan.sessions.find(row=>row.id===OLD).status,'completed');assert.equal(h.server.progress.completed,1);
});

test('proposal on an empty account never grants agenda consent automatically',async()=>{
  const h=harness(empty());await h.mount('week',undefined,{trainingProposal:proposal(0)});await all(h.root,'form')[0].emit('submit');
  await button(h.root,'Guardar mi plan').click();assert.equal(h.calls.filter(call=>call.method!=='GET').length,0);assert.match(h.root.textContent,/Confirma que autorizas/);
  const check=all(h.root,'input').find(node=>node.type==='checkbox');check.checked=true;await check.emit('change');await button(h.root,'Guardar mi plan').click();
  assert.deepEqual(h.calls.filter(call=>call.method!=='GET').map(call=>call.method),['POST','PUT']);
  assert.equal(h.calls.find(call=>call.method==='PUT').payload.expected_profile_version,4);assert.equal(h.server.plan.sessions.length,1);
});

test('stale profile or agenda discards unsaved proposal without overwriting prior activities',async()=>{
  for(const defect of ['profile','agenda']){
    const h=harness(undefined,path=>defect==='profile'&&path.endsWith('/me/profile')?response(profile(5)):undefined);
    await h.mount('week',undefined,{trainingProposal:proposal(defect==='agenda'?1:2)});
    if(defect==='profile'){await all(h.root,'form')[0].emit('submit');await button(h.root,'Guardar mi plan').click();}
    assert.equal(h.calls.filter(call=>call.method!=='GET').length,0);assert.equal(h.server.plan.sessions.length,2);
    assert.match(h.root.textContent,/cambiaron|cambió/);
  }
});

test('rescheduling training rechecks profile and includes full metadata in reviewed PUT',async()=>{
  const h=harness(saved([training()]));await h.mount('week');await button(h.root,'Reprogramar').click();
  const date=field(h.root,'Fecha de actividad 1');date.value='2026-09-03';await date.emit('input');await all(h.root,'form')[0].emit('submit');
  assert.equal(h.calls.filter(call=>call.method==='PUT').length,0);await button(h.root,'Guardar cambio').click();
  const write=h.calls.find(call=>call.method==='PUT');assert.equal(write.payload.expected_profile_version,4);
  assert.deepEqual(write.payload.plan.sessions[0],api.sessionInput(training({date:'2026-09-03'})));
});

test('server guard for recorded session is shown without replacing saved history',async()=>{
  const h=harness(saved([training()]),(path,options)=>options.method==='PUT'?response({detail:'Esta sesión tiene un registro de entrenamiento. Elimínalo explícitamente antes de moverla.'},422):undefined);
  await h.mount('week');await button(h.root,'Reprogramar').click();const date=field(h.root,'Fecha de actividad 1');date.value='2026-09-03';await date.emit('input');await all(h.root,'form')[0].emit('submit');await button(h.root,'Guardar cambio').click();
  assert.equal(h.server.plan.sessions[0].date,'2026-09-01');assert.doesNotMatch(h.root.textContent,/quedó reprogramada/);
  assert.match(h.root.textContent,/registro de entrenamiento/);
});

test('leaving while profile validation is pending prevents late routine save',async()=>{
  let resolve;const pending=new Promise(done=>resolve=done),h=harness(undefined,path=>path.endsWith('/me/profile')?pending:undefined);
  await h.mount('week',undefined,{trainingProposal:proposal()});await all(h.root,'form')[0].emit('submit');await button(h.root,'Guardar mi plan').click();
  h.api.setActive(false);resolve(response(profile()));await flush();assert.equal(h.root.textContent,'');assert.equal(h.calls.filter(call=>call.method==='PUT').length,0);
});

test('parent hands routine proposal to planner exactly until consumed and returns to routines',()=>{
  const h=parentHarness();h.api.configure({view:'space',section:'training'});h.api.render();
  const selection=h.programCalls.filter(call=>call.type==='training').at(-1);assert.equal(selection.options.identity,'member-a');
  const payload=proposal();selection.options.onSchedule(payload);assert.equal(h.api.current().section,'week');
  let planner=h.programCalls.filter(call=>call.type==='planner').at(-1);assert.deepEqual(clone(planner.options.trainingProposal),payload);
  planner.options.onTrainingConsumed();h.api.render();planner=h.programCalls.filter(call=>call.type==='planner').at(-1);assert.equal(planner.options.trainingProposal,null);
  planner.options.onTraining();assert.equal(h.api.current().section,'training');assert.equal(h.requests.length,0);
});

test('parent exit and identity reset clear unconsumed routine proposals and session details',()=>{
  const h=parentHarness();h.api.configure({view:'space',section:'training'});h.api.render();
  h.programCalls.filter(call=>call.type==='training').at(-1).options.onSchedule(proposal());
  h.api.setActive(false);assert.equal(h.root.innerHTML,'');assert.equal(h.programCalls.filter(call=>call.type==='training-active').at(-1).active,false);
  assert.equal(h.programCalls.filter(call=>call.type==='session-active').at(-1).active,false);
  h.api.clear();assert.ok(h.programCalls.some(call=>call.type==='training-clear'));assert.ok(h.programCalls.some(call=>call.type==='session-clear'));
});
