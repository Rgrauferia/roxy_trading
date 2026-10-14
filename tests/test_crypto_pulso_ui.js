const test = require('node:test');
const assert = require('node:assert/strict');
const ui = require('../assets/crypto_pulso/pulso-ui.js');
test('technical summary reports observed prices and no forecast probability', () => {
  const candles = Array.from({length:30}, (_,i) => ({open:100+i,high:102+i,low:99+i,close:101+i}));
  const result = ui.technicalReading(candles, '125');
  assert.equal(result.available,true); assert.equal(result.high,131); assert.equal(result.low,117);
  assert.ok(result.ema9 > result.ema21); assert.match(result.detail,/describe el pasado/);
  assert.equal(Object.hasOwn(result,'probability'),false);
  assert.equal(ui.technicalReading(candles,'').available,false);
});
test('catalogue choice fills required form fields before native submit validation', () => {
  class Element {
    constructor(id='') { this.id=id; this.tagName=id.startsWith('chart-')?'CANVAS':'DIV'; this.children=[]; this.listeners=new Map(); this.value=''; this.type='submit'; }
    set textContent(v) {this._text=v;this.children=[];} get textContent(){return this._text;}
    appendChild(v){this.children.push(v);} removeChild(v){this.children.splice(this.children.indexOf(v),1);}
    addEventListener(n,f){this.listeners.set(n,f);} removeEventListener(n){this.listeners.delete(n);}
    getContext(){return null;}
  }
  const nodes=new Map(), doc=new Element(); doc.hidden=false;
  doc.getElementById=id=>{if(!nodes.has(id))nodes.set(id,new Element(id));return nodes.get(id);};doc.createElement=()=>new Element();
  const now=Date.UTC(2026,0,1,12,1), contract={status:'VALID',instrumentSymbol:'TEST_ONLY',strike:'100.25',operator:'>',durationSeconds:3600,expiryTimestampMs:now+3500000};
  const env=new Element();Object.assign(env,{document:doc,Date:{now:()=>now},PULSO_NETWORK_ENABLED:true,PULSO_BOOTSTRAP_CATALOGUE:'SYNTHETIC',
    PulsoContractValidation:{decodeCatalogue:()=>({status:'VALID',instruments:[contract]}),matchSelectedContract:()=>({status:'NO_MATCH'})},
    setInterval:()=>1,clearInterval:()=>{}});
  const controller=ui.mount(env);
  nodes.get('contract-choice').value='TEST_ONLY';nodes.get('contract-choice').listeners.get('change')();
  assert.equal(nodes.get('strike').value,'100.25');
  assert.equal(nodes.get('expiry').value,new Date(contract.expiryTimestampMs).toISOString());
  assert.equal(controller.getState().selection.strike,''); // Draft only, no selection or network.
  controller.dispose();
});
