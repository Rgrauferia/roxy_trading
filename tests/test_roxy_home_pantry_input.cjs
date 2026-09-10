const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const test=require('node:test');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../assets/roxy_list.js'),'utf8');
const start=source.indexOf('  function pantryFields('),end=source.indexOf('  async function createRecipe(',start);
assert.ok(start>0&&end>start);
function harness(){
  const input={value:'Arroz; 2; tazas',readOnly:false,attributes:{},setAttribute(k,v){this.attributes[k]=v},removeAttribute(k){delete this.attributes[k]},focus(){this.focused=true}};
  const message={hidden:true,textContent:''},button={disabled:false},requests=[],notices=[];
  const ctx={String,Number,Error,user:'house-a',identity:'member:a',collectionIdentity:()=>ctx.identity,
    $:id=>({pantryItems:input,pantryError:message,pantryForm:{querySelector:()=>button}})[id],
    api:async(url,options)=>{requests.push({url,items:JSON.parse(options.body).items})},announce:msg=>notices.push(msg),load:async()=>{ctx.loads++},loads:0};
  vm.createContext(ctx);vm.runInContext(source.slice(start,end)+'\nthis.parse=parsePantryText;this.format=formatPantryText;this.save=savePantry;',ctx);
  return {ctx,input,message,button,requests,notices,save:()=>ctx.save({preventDefault(){}}),parse:text=>JSON.parse(JSON.stringify(ctx.parse(text)))};
}
test('Spanish decimal commas and decimal points preserve exact amount and unit',()=>{
  assert.deepEqual(harness().parse('Leche; 1,5; litros\nArroz; 0.25; kg'),[{name:'Leche',quantity:1.5,unit:'litros'},{name:'Arroz',quantity:0.25,unit:'kg'}]);
});
test('legacy unambiguous comma rows remain accepted',()=>assert.equal(harness().parse('Arroz, 250, g')[0].quantity,250));
test('legacy CSV quoting preserves comma and semicolon in a product name',()=>assert.equal(harness().parse('"Arroz, integral; QA", 2, tazas')[0].name,'Arroz, integral; QA'));
test('ambiguous fourth comma field is rejected instead of discarded',()=>assert.throws(()=>harness().parse('Leche, 1,5, litros'),/Línea 1/));
test('blank lines are ignored but not invalid nonblank lines',()=>{
  assert.deepEqual(harness().parse('\n \r\n'),[]);
  assert.throws(()=>harness().parse('Arroz; 2; g\n\nHuevos'),/Línea 3/);
});
for(const quantity of ['0','-1','NaN','Infinity','1e3','0x10','1/2','100001','0.00001','1,000.5','']){
  test(`rejects quantity ${JSON.stringify(quantity)} without guessing one`,()=>assert.throws(()=>harness().parse(`Arroz; ${quantity}; g`)));
}
for(const line of [';2;g','Arroz;2;','Arroz;2;5','Arroz;2;g;extra','"Arroz;2;g','Arroz"mal;2;g','"Arroz"extra;2;g']){
  test(`rejects malformed row ${JSON.stringify(line)}`,()=>assert.throws(()=>harness().parse(line)));
}
test('quoted names and delimiters round-trip without changing inventory',()=>{
  const h=harness(),rows=[{name:'Arroz; integral "QA", largo',quantity:2,unit:'tazas'}];
  assert.deepEqual(h.parse(h.ctx.format(rows)),rows);
});
test('field size and count overflow never silently truncates',()=>{
  for(const text of ['x'.repeat(121)+';1;g','Arroz;1;'+'g'.repeat(33),Array(501).fill('Arroz;1;g').join('\n')])assert.throws(()=>harness().parse(text));
});
test('invalid form never sends a replacement and preserves editable text',async()=>{
  const h=harness();h.input.value='Leche, 1,5, litros';await h.save();
  assert.equal(h.requests.length,0);assert.equal(h.message.hidden,false);assert.match(h.message.textContent,/Línea 1/);
  assert.equal(h.input.attributes['aria-invalid'],'true');assert.equal(h.input.focused,true);assert.equal(h.input.value,'Leche, 1,5, litros');
});
test('submission uses owner captured at start, blocks duplicate submits and releases controls',async()=>{
  const h=harness();let finish;h.ctx.api=async(url,options)=>{h.requests.push({url,items:JSON.parse(options.body).items});await new Promise(resolve=>finish=resolve)};
  const pending=h.save();assert.equal(h.button.disabled,true);assert.equal(h.input.readOnly,true);await h.save();assert.equal(h.requests.length,1);
  h.ctx.user='house-b';finish();await pending;assert.match(h.requests[0].url,/house-a/);assert.equal(h.ctx.loads,0);assert.equal(h.notices.length,0);assert.equal(h.button.disabled,false);
});
test('network error keeps the form and does not report success',async()=>{
  const h=harness();h.ctx.api=async()=>{throw new Error('No disponible')};await h.save();
  assert.equal(h.input.value,'Arroz; 2; tazas');assert.equal(h.message.textContent,'No disponible');assert.equal(h.ctx.loads,0);assert.equal(h.input.readOnly,false);
});
test('valid save transmits exact quantities and refreshes once',async()=>{
  const h=harness();h.input.value='Leche; 1,5; litros';await h.save();assert.equal(h.requests[0].items[0].quantity,1.5);assert.equal(h.requests[0].items[0].unit,'litros');assert.equal(h.ctx.loads,1);
});
