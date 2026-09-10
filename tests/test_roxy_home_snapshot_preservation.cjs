const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const test=require('node:test');
const source=fs.readFileSync(require('node:path').join(__dirname,'../assets/roxy_list.js'),'utf8');
const start=source.indexOf('  const collectionRecovery=');
const end=source.indexOf('  function renderCollectionNotice(',start);
assert.ok(start>0&&end>start);
function harness(kind='plants'){
  const field=kind==='plants'?'plants':'projects',identity='member:person-a',key=`home-${kind}:house-a`+(kind==='design'?`:identity:${identity}`:''),recovery=key+'-recovery';
  const db=new Map(),writes=[];
  const ctx={user:'house-a',account:{mode:'member',id:'person-a'},homePlants:{plants:[]},homeDesign:{projects:[]},Date,Error,Array,encodeURIComponent,api:async()=>({}),
    dbGet:async k=>db.get(k),dbSet:async(k,v)=>{writes.push(k);db.set(k,structuredClone(v));}};
  vm.createContext(ctx);vm.runInContext(source.slice(start,end)+'\nthis.save=preserveCollectionSnapshot;this.forget=forgetDeletedCollection;this.recovery=collectionRecovery;',ctx);
  return {ctx,db,writes,field,key,recovery,save:(next,old=null,options={})=>ctx.save(kind,next,old,'house-a',{...options,identity}),forget:id=>ctx.forget(kind,id,'house-a',identity)};
}
for(const kind of ['plants','design']){
  test(`${kind}: archives a nonempty device copy before accepting an empty server list`,async()=>{
    const h=harness(kind),old={[h.field]:[{id:'synthetic'}]};h.db.set(h.key,old);
    await h.save({[h.field]:[],storage_status:'NEW'});
    assert.deepEqual(h.db.get(h.recovery).snapshot,old);assert.equal(h.db.get(h.key)[h.field].length,0);
    assert.ok(h.writes.indexOf(h.recovery)<h.writes.indexOf(h.key));
    assert.equal(h.ctx.recovery[kind].owner,'house-a');
  });
  test(`${kind}: repeated empty loads retain the recovery copy`,async()=>{
    const h=harness(kind);h.db.set(h.key,{[h.field]:[{id:'synthetic'}]});await h.save({[h.field]:[]});await h.save({[h.field]:[]});
    assert.equal(h.db.get(h.recovery).snapshot[h.field][0].id,'synthetic');
  });
  test(`${kind}: confirmed deletion removes only that record from recovery`,async()=>{
    const h=harness(kind);h.db.set(h.key,{[h.field]:[{id:'synthetic'}]});h.db.set(h.recovery,{snapshot:{[h.field]:[{id:'synthetic'},{id:'older'}]}});
    await h.forget('synthetic');await h.save({[h.field]:[]},null,{intentionalDelete:true});assert.equal(h.db.get(h.recovery).snapshot[h.field][0].id,'older');
    assert.equal(h.db.get(h.key)[h.field].length,0);
  });
  test(`${kind}: failed archive leaves the current cache intact`,async()=>{
    const h=harness(kind),old={[h.field]:[{id:'synthetic'}]};h.db.set(h.key,old);h.ctx.dbSet=async()=>{throw new Error('quota')};
    await assert.rejects(h.save({[h.field]:[]}),/quota/);assert.deepEqual(h.db.get(h.key),old);
  });
  test(`${kind}: malformed payload does not replace the previous list`,async()=>{
    const h=harness(kind),old={[h.field]:[{id:'synthetic'}]};h.db.set(h.key,old);
    await assert.rejects(h.save({status:'READY'}),/lista válida/);assert.deepEqual(h.db.get(h.key),old);
  });
  test(`${kind}: a response for a prior household cannot expose its recovery notice`,async()=>{
    const h=harness(kind);h.db.set(h.key,{[h.field]:[{id:'synthetic'}]});h.ctx.user='house-b';
    await assert.rejects(h.save({[h.field]:[]}),/sesión cambió/);assert.equal(h.ctx.recovery[kind],undefined);assert.equal(h.db.has(`home-${kind}:house-b`),false);
  });
  test(`${kind}: new empty households do not get a fabricated recovery copy`,async()=>{
    const h=harness(kind);await h.save({[h.field]:[]});assert.equal(h.db.has(h.recovery),false);
  });
  test(`${kind}: a later disappearance does not overwrite unrelated recovery records`,async()=>{
    const h=harness(kind);h.db.set(h.recovery,{snapshot:{[h.field]:[{id:'earlier'}]}});h.db.set(h.key,{[h.field]:[{id:'later'}]});
    await h.save({[h.field]:[]});assert.deepEqual(h.db.get(h.recovery).snapshot[h.field].map(row=>row.id),['earlier','later']);
  });
  test(`${kind}: changed member in the same household cannot cache a stale response`,async()=>{
    const h=harness(kind);h.ctx.account={mode:'member',id:'person-b'};
    await assert.rejects(h.save({[h.field]:[]}),/sesión cambió/);assert.equal(h.writes.length,0);
  });
}
test('Renueva never attributes the unscoped legacy cache to a signed-in member',async()=>{
  const h=harness('design');h.db.set('home-design:house-a',{projects:[{id:'unattributed'}]});
  await h.save({projects:[]});assert.equal(h.db.has(h.recovery),false);
});
test('new frontend identifies its cache-preserving collection protocol',()=>{
  assert.match(source,/X-Roxy-Snapshot-Version':'2'/);
  assert.match(source,/refreshPlants\(\{intentionalDelete:true\}\)/);
  assert.match(source,/refreshDesignProjects\(\{intentionalDelete:true\}\)/);
});
