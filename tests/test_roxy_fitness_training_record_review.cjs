'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const prefix=fs.readFileSync(require.resolve('./test_roxy_fitness_training_targets_ui.cjs'),'utf8').split('const reference=')[0];
const make=new Function('require',prefix+'\nreturn {harness,saved,empty,session,stored,log,response,field,button,byClass,deferred,flush};');
const {harness,saved,empty,session,stored,log,response,field,button,byClass,deferred,flush}=make(require);

test('opening a saved progress record starts at actual results rather than warmup',async()=>{
  const h=harness(saved());await h.mount({reviewRecord:true});
  assert.match(h.root.textContent,/Así quedó tu entrenamiento/);assert.match(h.root.textContent,/Serie 1: 5 repeticiones/);
  assert.match(h.root.textContent,/Omitido por ti/);assert.equal(byClass(h.root,'fxt-movement-title').length,0);
  assert.equal(field(h.root,'Autorizo guardar mis registros de entrenamiento').checked,false);
  assert.equal(h.calls.every(call=>call.method==='GET'),true);assert.equal(h.server.logs[0].exercises[0].sets[0].reps,5);
});

test('normal session entry remains on warmup even when previous results exist',async()=>{
  const h=harness(saved());await h.mount();assert.match(h.root.textContent,/Entra en movimiento/);
  assert.equal(byClass(h.root,'fxt-review-title').length,0);assert.equal(h.calls.every(call=>call.method==='GET'),true);
});

test('progress entry with no remaining record does not invent an actual review',async()=>{
  const h=harness(empty());await h.mount({reviewRecord:true});assert.match(h.root.textContent,/ya no está guardado/);
  assert.equal(byClass(h.root,'fxt-review-title').length,0);await button(h.root,'Siguiente movimiento →').click();
  assert.equal(field(h.root,'Repeticiones · serie 1').value,'');assert.equal(h.calls.every(call=>call.method==='GET'),true);
});

test('switching from normal entry to record review reloads saved values without carrying unsaved edits',async()=>{
  const h=harness(saved());await h.mount();await button(h.root,'Siguiente movimiento →').click();
  const input=field(h.root,'Repeticiones · serie 1');input.value='777';await input.emit('input');
  await h.mount({reviewRecord:true});assert.match(h.root.textContent,/Serie 1: 5 repeticiones/);assert.doesNotMatch(h.root.textContent,/777/);
  assert.equal(h.calls.filter(call=>call.method==='PUT').length,0);
});

test('retained history opens for reading even when new results cannot be saved',async()=>{
  const h=harness({...saved(),eligible:false,eligibility_reason:'adult_profile_required'});await h.mount({reviewRecord:true,session:session({status:'skipped'})});
  assert.match(h.root.textContent,/Serie 1: 5 repeticiones/);await button(h.root,'Guardar mi registro').click();
  assert.equal(h.calls.every(call=>call.method==='GET'),true);
});

test('hidden progress entry cannot display a late record response',async()=>{
  const pending=deferred(),h=harness(saved(),path=>path.endsWith('/training-logs')?pending.promise:undefined);
  await h.mount({reviewRecord:true});await h.visibility(true);pending.resolve(response(saved()));await flush();
  assert.equal(h.root.textContent,'');assert.equal(h.calls.every(call=>call.method==='GET'),true);
});
