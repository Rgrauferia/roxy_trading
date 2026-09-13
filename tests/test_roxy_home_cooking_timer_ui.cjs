const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../assets/roxy_list.js'),'utf8');
const part=(a,b)=>source.slice(source.indexOf(a),source.indexOf(b,source.indexOf(a)));
function harness(){
  const nodes={timerMinutes:{value:'99'},startTimerButton:{},timerSuggestion:{}};
  const calls=[],messages=[];
  const ctx={$:id=>nodes[id],currentCooking:{session:{status:'ACTIVE'}},createCookingTimer:async(...args)=>calls.push(args),announce:text=>messages.push(text)};
  vm.createContext(ctx);vm.runInContext(part('  function prepareCookingTimer(', '  function timerRemaining(')+part('  async function startCookingTimer(', '  async function cancelCookingTimer('),ctx);
  return{ctx,nodes,calls,messages};
}
for(const seconds of [0,undefined,null,'300',NaN,-10,86401,1.5])test(`non-exact duration ${seconds} clears old timer instead of reparsing text`,()=>{
  const h=harness();h.ctx.prepareCookingTimer({session:{status:'ACTIVE'},suggested_timer_seconds:seconds,current_step:'Cocina 2–3 minutos y 1–2 minutos más.'});
  assert.equal(h.nodes.timerMinutes.value,'');assert.match(h.nodes.timerSuggestion.textContent,/Elige la duración/);
});
for(const seconds of [1,20,90,300,4500,86400])test(`explicit suggestion ${seconds}s remains accurate and requires confirmation`,async()=>{
  const h=harness();h.ctx.prepareCookingTimer({session:{status:'ACTIVE'},suggested_timer_seconds:seconds});
  assert.equal(h.calls.length,0);assert.equal(Math.round(Number(h.nodes.timerMinutes.value)*60),seconds);
  await h.ctx.startCookingTimer();assert.equal(Math.round(h.calls[0][0]),seconds);
});
for(const value of ['', '0', '-1', 'Infinity', 'NaN', '1441', '0.001'])test(`manual duration ${value} is rejected`,async()=>{
  const h=harness();h.nodes.timerMinutes.value=value;await h.ctx.startCookingTimer();assert.equal(h.calls.length,0);assert.equal(h.messages.length,1);
});
test('completed recipes disable new timers and clear a previous suggestion',async()=>{
  const h=harness();h.ctx.currentCooking.session.status='COMPLETED';h.ctx.prepareCookingTimer({session:{status:'COMPLETED'},suggested_timer_seconds:300});
  assert.equal(h.nodes.timerMinutes.value,'');assert.equal(h.nodes.startTimerButton.disabled,true);await h.ctx.startCookingTimer();assert.equal(h.calls.length,0);
});
test('neither native nor provider audio completion starts timers or invokes a prose fallback',()=>{
  assert.doesNotMatch(source,/startAutomaticStepTimer|stepTimerSeconds/);
  assert.match(part('    const completed=()=>', '    const fallback=()=>'),/no se activa con la voz/);
});
