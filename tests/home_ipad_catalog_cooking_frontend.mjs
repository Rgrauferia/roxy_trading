import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const code=fs.readFileSync(new URL('../assets/roxy_list.js',import.meta.url),'utf8');
const fn=code.slice(code.indexOf('  async function openCatalogRecipe('),code.indexOf('  function resolveMealRecipe('));
function harness(fail=false){
  const calls=[];
  const context={user:'synthetic',announce:value=>calls.push(['announce',value]),
    api:async(path,options)=>{calls.push(['save',path,JSON.parse(options.body)]);if(fail)throw new Error('No se pudo guardar');return {recipe:{id:'saved-exact',title:'Exacta'}}},
    load:async()=>calls.push(['load']),openRecipe:recipe=>calls.push(['open',recipe.id]),
    startCooking:async id=>calls.push(['cook',id]),selectedPetProfile:()=>null};
  vm.createContext(context);vm.runInContext(fn,context);
  return {calls,run:context.openCatalogRecipe};
}
test('explicit save-and-cook uses the server recipe id, never a title or a draft',async()=>{
  const h=harness();await h.run({title:'Exacta',catalog_key:'exacta'},{cook:true});
  assert.deepEqual(h.calls.filter(row=>row[0]!=='announce').map(row=>row.slice(0,2)),[
    ['save','/v1/home-food/synthetic/recipes'],['load'],['cook','saved-exact']]);
  assert.equal(h.calls[1][2].catalog_key,'exacta');
});
test('ordinary save still opens the recipe without starting a session',async()=>{
  const h=harness();await h.run({title:'Exacta',catalog_key:'exacta'});
  assert.equal(h.calls.some(row=>row[0]==='cook'),false);
  assert.equal(h.calls.find(row=>row[0]==='open')[1],'saved-exact');
});
test('failed save cannot start cooking or pretend success',async()=>{
  const h=harness(true);await h.run({title:'Exacta'},{cook:true});
  assert.equal(h.calls.some(row=>['cook','load','open'].includes(row[0])),false);
  assert.deepEqual(h.calls.at(-1),['announce','No se pudo guardar']);
});
