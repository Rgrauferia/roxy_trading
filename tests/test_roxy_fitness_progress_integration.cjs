'use strict';
// Synthetic DOM integration: private handoffs, agenda reader and chosen targets.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const planner=require('../assets/roxy_fitness_planner.js');
const clone=value=>JSON.parse(JSON.stringify(value));
const ID='77777777-7777-4777-8777-777777777777';
const OTHER='88888888-8888-4888-8888-888888888888';
const reference={session_id:ID,program_id:'home-dumbbell-foundations',content_version:'home-training-213-v1',logs_version:7};
const targets=[{exercise_id:'dumbbell-curl',sets:[{reps:8,seconds:null,load:{value:10,unit:'lb'}}]}];
const row=()=>({id:ID,program_id:reference.program_id,date:'2026-09-01',time:'09:00',
  content_version:reference.content_version,confirmed_requirements:{equipment:['dumbbells'],capabilities:['free_weights']},
  reserved_minutes:45,travel_minutes:0,training_targets:clone(targets),starts_at:'2026-09-01T13:00:00Z',status:'planned',completed_at:null});
const saved=()=>({version:2,consent:{purpose:'fitness_activity_plan',text_version:'fitness-activity-plan-v1',granted:true},
  plan:{title:'Mi semana',timezone:'America/New_York',sessions:[row()]},progress:{planned:1,completed:0,skipped:0,total:1},updated_at:'2026-09-01T00:00:00Z'});
function parentHarness(){
  let source=fs.readFileSync(require.resolve('./test_roxy_fitness_ui.cjs'),'utf8').split("test('today and week")[0];
  source=source.replace('if(values.root)root=values.root;', 'if(values.moduleActive!==undefined)moduleActive=values.moduleActive;if(values.root)root=values.root;');
  source=source.replace('context.window=context;',`context.RoxyFitnessProgress={mount(node,options){programCalls.push({type:'progress',options});},clear(){programCalls.push({type:'progress-clear'});},setActive(active){programCalls.push({type:'progress-active',active});}};
    context.RoxyFitnessTraining={mount(node,options){programCalls.push({type:'training',options});},clear(){programCalls.push({type:'training-clear'});},setActive(active){programCalls.push({type:'training-active',active});}};context.window=context;`);
  return new Function('require','__dirname',source+'\nreturn harness(true);')(require,__dirname);
}
function readerHarness(intercept){
  let source=fs.readFileSync(require.resolve('./test_roxy_fitness_planner_ui.cjs'),'utf8').split("test('invalid dates/timezones")[0];
  source=source.replace('context.window=context;',`context.RoxyFitnessTrainingSession={mount(node,options){trainingCalls.push(options);},setActive(){},clear(){}};context.window=context;`);
  return new Function('require','initial','intercept','const trainingCalls=[];\n'+source+'\nconst h=harness(initial,intercept);h.trainingCalls=trainingCalls;h.helper={button,field,all};return h;')(require,saved(),intercept);
}
const latest=(h,type)=>h.programCalls.filter(call=>call.type===type).at(-1);

test('parent carries an explicit progress reference to routine selection exactly until consumed',()=>{
  const h=parentHarness();h.api.configure({view:'space',section:'progress'});h.api.render();
  assert.equal(latest(h,'progress').options.identity,'member-a');latest(h,'progress').options.onRepeat(clone(reference));
  assert.equal(h.api.current().section,'training');assert.deepEqual(clone(latest(h,'training').options.repeatSource),reference);
  latest(h,'training').options.onRepeatConsumed();h.api.render();assert.equal(latest(h,'training').options.repeatSource,null);
  assert.equal(h.requests.length,0);
});

test('parent opens a historical record in the agenda and consumes its handoff',()=>{
  const h=parentHarness();h.api.configure({view:'space',section:'progress'});h.api.render();latest(h,'progress').options.onOpenSession(ID);
  assert.equal(h.api.current().section,'week');assert.equal(latest(h,'planner').options.openSessionId,ID);
  latest(h,'planner').options.onSessionConsumed();h.api.render();assert.equal(latest(h,'planner').options.openSessionId,null);
});

test('parent private reset removes progress state and both unconsumed handoffs',()=>{
  const h=parentHarness();h.api.configure({view:'space',section:'progress'});h.api.render();latest(h,'progress').options.onRepeat(clone(reference));
  h.api.configure({section:'progress'});h.api.render();latest(h,'progress').options.onOpenSession(ID);
  h.api.setActive(false);assert.equal(h.root.innerHTML,'');assert.equal(latest(h,'progress-active').active,false);
  h.api.clear();assert.ok(latest(h,'progress-clear'));
  h.api.configure({root:h.root,context:{identity:'member-b'},identity:'member-b',moduleActive:true,view:'space',section:'training'});h.api.render();
  assert.equal(latest(h,'training').options.repeatSource,null);h.api.configure({section:'week'});h.api.render();assert.equal(latest(h,'planner').options.openSessionId,null);
});

test('agenda opens only the stored matching session with goals kept separate in its metadata',async()=>{
  const h=readerHarness();let consumed=0;await h.mount('week',undefined,{openSessionId:ID,onSessionConsumed(){consumed++;}});
  assert.equal(consumed,1);assert.equal(h.trainingCalls.length,1);assert.equal(h.trainingCalls[0].identity,'member-a');
  assert.deepEqual(clone(h.trainingCalls[0].session.training_targets),targets);assert.equal(h.trainingCalls[0].session.id,ID);assert.equal(h.trainingCalls[0].reviewRecord,true);
  assert.equal(h.calls.every(call=>call.method==='GET'),true);
});

test('a missing historical agenda session cannot mount another record',async()=>{
  const h=readerHarness();let consumed=0;await h.mount('week',undefined,{openSessionId:OTHER,onSessionConsumed(){consumed++;}});
  assert.equal(consumed,1);assert.equal(h.trainingCalls.length,0);assert.match(h.root.textContent,/ya no está|no está|no encontr/i);
  assert.equal(h.calls.every(call=>call.method==='GET'),true);
});

test('chosen goals survive append and reschedule with independent copies and no status-derived results',()=>{
  const initial=saved().plan;const newRow={...row(),id:OTHER,date:'2026-09-03'};
  const appended=planner.draftPlan(initial,initial.title,initial.timezone,[newRow]);
  assert.deepEqual(appended.sessions[0].training_targets,targets);assert.deepEqual(appended.sessions[1].training_targets,targets);
  appended.sessions[1].training_targets[0].sets[0].load.value=11;assert.equal(initial.sessions[0].training_targets[0].sets[0].load.value,10);
  const moved=planner.reschedulePlan(initial,{...row(),date:'2026-09-04'});assert.deepEqual(moved.sessions[0].training_targets,targets);
  assert.equal(moved.sessions[0].status,undefined);assert.equal(moved.sessions[0].exercises,undefined);
});

test('invalid chosen target structure cannot become trusted planner metadata',()=>{
  for(const bad of [[],[{exercise_id:'same',sets:[{reps:2}]},{exercise_id:'same',sets:[{reps:3}]}],
    [{exercise_id:'curl',sets:[{reps:8,seconds:10}]}],[{exercise_id:'curl',sets:[{seconds:Infinity}]}],
    [{exercise_id:'curl',sets:[{reps:8,load:{value:NaN,unit:'kg'}}]}]]){
    assert.throws(()=>planner.trainingMetadata({...row(),training_targets:bad}));
  }
  assert.throws(()=>planner.trainingMetadata({program_id:'gentle-strength',training_targets:targets}));
});

for(const route of ['agenda','progress'])test(`entering reader from ${route} clears an earlier save confirmation`,async()=>{
  const h=readerHarness(path=>path.endsWith('/me/profile')?{ok:true,status:200,json:async()=>({version:2})}:undefined);
  const {button,field,all}=h.helper;await h.mount();await button(h.root,'Reprogramar').click();
  const date=field(h.root,'Fecha de actividad 1');date.value='2026-09-03';await date.emit('input');
  await all(h.root,'form')[0].emit('submit');await button(h.root,'Guardar cambio').click();
  assert.match(h.root.textContent,/quedó reprogramada/);
  if(route==='agenda')await button(h.root,'Empezar mi actividad').click();
  else await h.mount('week',undefined,{openSessionId:ID});
  assert.doesNotMatch(h.root.textContent,/quedó reprogramada/);assert.ok(h.trainingCalls.length);
});
