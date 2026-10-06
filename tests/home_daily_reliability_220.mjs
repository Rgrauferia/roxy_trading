import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
const code=fs.readFileSync(new URL('../assets/roxy_list.js',import.meta.url),'utf8');
const saveCode=code.slice(code.indexOf('  async function saveWeeklyPlanReady('),code.indexOf('  async function createWeeklyPlan('));
function harness({fail=false,changeOwner=false}={}){
  const calls=[],checkbox={checked:true,disabled:false};
  const plan={id:'plan',days:[{ingredients_ready:false}]};
  const context={user:'synthetic',currentWeeklyPlan:plan,homeFood:{weekly_plans:[plan]},
    collectionIdentity:()=>context.user,checkCollectionContext:(owner)=>{if(context.user!==owner)throw new Error('changed');},
    announce:text=>calls.push(['announce',text]),api:async(path,options)=>{
      calls.push([path,JSON.parse(options.body)]);if(changeOwner)context.user='other';
      if(fail)throw new Error('network');return {plan:{...plan,days:[{ingredients_ready:true}]}};
    }};
  vm.createContext(context);vm.runInContext(saveCode,context);return {context,calls,checkbox};
}
test('ready checkbox persists to server and updates current plan',async()=>{
  const h=harness();await h.context.saveWeeklyPlanReady(0,h.checkbox);
  assert.equal(h.calls[0][1].action,'ready');assert.equal(h.context.currentWeeklyPlan.days[0].ingredients_ready,true);
  assert.equal(h.checkbox.disabled,false);
});
test('failed save rolls back checkbox instead of excluding unsaved ingredients',async()=>{
  const h=harness({fail:true});await h.context.saveWeeklyPlanReady(0,h.checkbox);
  assert.equal(h.checkbox.checked,false);assert.equal(h.context.currentWeeklyPlan.days[0].ingredients_ready,false);
  assert.match(h.calls.at(-1)[1],/No pude guardar/);
});
test('late readiness response cannot update another member',async()=>{
  const h=harness({changeOwner:true});await h.context.saveWeeklyPlanReady(0,h.checkbox);
  assert.equal(h.context.currentWeeklyPlan.days[0].ingredients_ready,false);
  assert.equal(h.calls.length,1);
});
test('chat errors explain actionable safe status without leaking raw errors',()=>{
  const context={};vm.createContext(context);vm.runInContext(code.slice(code.indexOf('  function roxyTextError('),code.indexOf('  async function sendRoxyText(')),context);
  assert.match(context.roxyTextError({status:429,message:'sk-secret'}),/límite/);
  assert.doesNotMatch(context.roxyTextError({status:502,message:'sk-secret'}),/sk-secret/);
  assert.match(context.roxyTextError({status:401}),/sesión/);
});
test('readiness no longer exists only in a transient browser set',()=>{
  assert.doesNotMatch(code,/weeklyPlanReadyDays/);
  assert.match(code,/checkbox.checked=Boolean\(day.ingredients_ready\)/);
  assert.match(code,/if\(result.intent!=='general'\)await load\(\{quiet:true\}\)/);
});
test('old meal plans keep their real dates instead of pretending to be this week',()=>{
  assert.doesNotMatch(code,/rebaseDates/);
  assert.match(code,/Este plan corresponde a otra semana/);
  assert.match(code,/const date=new Date\(`\$\{day.date\}T12:00:00`\)/);
});
test('first load and unavailable service have a visible recovery outside the hidden app',()=>{
  const nodes=Object.fromEntries(['homeLoadStatus','homeLoadMessage','homeLoadRetry'].map(id=>[id,{hidden:true,disabled:false,textContent:'',setAttribute(){}}]));
  const context={$:id=>nodes[id]};vm.createContext(context);
  vm.runInContext(code.slice(code.indexOf('  function setHomeLoadStatus('),code.indexOf('  async function api(')),context);
  context.setHomeLoadStatus('Preparando',true);
  assert.equal(nodes.homeLoadStatus.hidden,false);assert.equal(nodes.homeLoadRetry.hidden,true);
  context.setHomeLoadStatus('Reintenta');assert.equal(nodes.homeLoadRetry.hidden,false);assert.equal(nodes.homeLoadRetry.disabled,false);
  context.setHomeLoadStatus();assert.equal(nodes.homeLoadStatus.hidden,true);
  const html=fs.readFileSync(new URL('../assets/roxy_list.html',import.meta.url),'utf8');
  assert.ok(html.indexOf('id="homeLoadStatus"')<html.indexOf('id="app"'));
  assert.match(code,/homeLoadRetry'\).addEventListener\('click',\(\)=>load\(\)\)/);
});
