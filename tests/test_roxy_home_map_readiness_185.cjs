/* Deterministic first-tile lifecycle tests; no Google calls or real locations. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const source=fs.readFileSync(path.join(__dirname,'../assets/roxy_home_map_readiness.js'),'utf8');
function fixture(timeoutMs){
  const timers=new Map(),states=[];let seq=0,current=true;
  const root={setTimeout(callback,ms){const id=++seq;timers.set(id,{callback,ms});return id},clearTimeout(id){timers.delete(id)}};
  vm.runInNewContext(source,{window:root});
  const controller=root.RoxyMapReadiness.create({onState:s=>states.push({...s}),isCurrent:()=>current,timeoutMs});
  const makeMap=()=>{
    const events=new Map(),removed=[];
    return {events,removed,addListener(name,callback){events.set(name,callback);return{remove(){removed.push(name);events.delete(name)}}},
      fire(name='tilesloaded'){events.get(name)?.()}};
  };
  const map=makeMap();
  function expire(){const queued=[...timers.entries()];for(const [id,{callback}]of queued){timers.delete(id);callback()}}
  return {controller,map,makeMap,timers,states,expire,changeIdentity(){current=false}};
}
test('constructor/library presence does not mark basemap ready',()=>{
  const f=fixture();f.controller.attach(f.map);
  assert.equal(f.controller.getState().phase,'loading');assert.equal(f.timers.size,1);
  assert.deepEqual([...f.map.events.keys()],['tilesloaded']);
  assert.equal([...f.timers.values()][0].ms,12000);
});
test('first tilesloaded marks ready, clears timer and listener',()=>{
  const f=fixture();f.controller.attach(f.map);f.map.fire();
  assert.equal(f.controller.getState().phase,'ready');assert.equal(f.timers.size,0);assert.equal(f.map.events.size,0);
  assert.equal(f.states.at(-1).canRetry,false);f.expire();assert.equal(f.controller.getState().phase,'ready');
});
test('timeout only reports delayed and offers retry; it makes no map mutation or repeated timer',()=>{
  const f=fixture();f.controller.attach(f.map);f.expire();
  assert.equal(f.controller.getState().phase,'delayed');assert.equal(f.controller.getState().canRetry,true);
  assert.equal(f.timers.size,0);f.expire();assert.equal(f.states.length,2);
});
test('tiles that arrive after timeout clear delayed state',()=>{
  const f=fixture();f.controller.attach(f.map);f.expire();f.map.fire();
  assert.equal(f.states.at(-1).phase,'ready');assert.equal(f.map.events.size,0);
});
test('repeated attach of same map preserves ready state without timers',()=>{
  const f=fixture();f.controller.attach(f.map);f.map.fire();const count=f.states.length;f.controller.attach(f.map);
  assert.equal(f.controller.getState().phase,'ready');assert.equal(f.timers.size,0);assert.equal(f.map.events.size,0);
  assert.equal(f.states.length,count);
});
test('repeated attach does not extend the pending timeout',()=>{
  const f=fixture();f.controller.attach(f.map);const timer=[...f.timers.keys()][0];f.controller.attach(f.map);
  assert.deepEqual([...f.timers.keys()],[timer]);
});
test('old map events and queued timeout cannot affect replacement map',()=>{
  const f=fixture();f.controller.attach(f.map);const oldEvent=f.map.events.get('tilesloaded'),oldTimer=[...f.timers.values()][0].callback;
  const next=f.makeMap();f.controller.attach(next);oldEvent();oldTimer();
  assert.equal(f.controller.getState().phase,'loading');assert.equal(f.map.events.size,0);
  next.fire();assert.equal(f.controller.getState().phase,'ready');assert.equal(f.timers.size,0);
});
test('hidden state cancels timeout; returning re-arms only an unresolved loading state',()=>{
  const f=fixture();f.controller.attach(f.map);f.controller.setActive(false);assert.equal(f.timers.size,0);
  f.controller.setActive(true);assert.equal(f.timers.size,1);f.map.fire();f.controller.setActive(false);f.controller.setActive(true);
  assert.equal(f.timers.size,0);assert.equal(f.controller.getState().phase,'ready');
});
test('tiles loaded while hidden are remembered without painting hidden UI',()=>{
  const f=fixture();f.controller.attach(f.map);f.controller.setActive(false);const n=f.states.length;f.map.fire();
  assert.equal(f.states.length,n);assert.equal(f.controller.getState().phase,'ready');
  f.controller.setActive(true);assert.equal(f.states.at(-1).phase,'ready');assert.equal(f.timers.size,0);
});
test('returning to delayed state does not start an automatic retry',()=>{
  const f=fixture();f.controller.attach(f.map);f.expire();f.controller.setActive(false);f.controller.setActive(true);
  assert.equal(f.timers.size,0);assert.equal(f.states.at(-1).phase,'delayed');
});
for(const trigger of ['timer','tiles'])test(`identity loss suppresses ${trigger} callback and disposes listeners`,()=>{
  const f=fixture();f.controller.attach(f.map);const n=f.states.length;f.changeIdentity();
  if(trigger==='timer')f.expire();else f.map.fire();
  assert.equal(f.states.length,n);assert.equal(f.timers.size,0);assert.equal(f.map.events.size,0);
  assert.equal(f.controller.getState().phase,'idle');
});
test('dispose is idempotent and late callbacks cannot revive the controller',()=>{
  const f=fixture();f.controller.attach(f.map);const old=f.map.events.get('tilesloaded');f.controller.dispose();f.controller.dispose();old();
  f.controller.attach(f.makeMap());f.controller.setActive(true);
  assert.equal(f.controller.getState().phase,'idle');assert.equal(f.timers.size,0);assert.equal(f.states.length,1);
});
test('timer configuration stays bounded and invalid map rejected without discarding existing map',()=>{
  for(const [input,wanted]of [[0,1000],[Infinity,12000],[999999,30000]]){
    const f=fixture(input);f.controller.attach(f.map);assert.equal([...f.timers.values()][0].ms,wanted);
    assert.throws(()=>f.controller.attach({}),/event source/);f.map.fire();assert.equal(f.controller.getState().phase,'ready');
  }
});
