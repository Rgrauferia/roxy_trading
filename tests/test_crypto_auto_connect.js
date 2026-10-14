'use strict';
const test=require('node:test'), assert=require('node:assert/strict');
const validation=require('../assets/crypto_pulso/contract-validation.js');
const ui=require('../assets/crypto_pulso/pulso-ui.js');
const NOW=Date.UTC(2026,0,1,12,1), OPEN=Date.UTC(2026,0,1,12), EXPIRY=OPEN+900000;
const SYMBOL='NX.F.OPT.BTC.I.1.1.20260101';
function contract(overrides={}) { return {status:'VALID',symbol:'BTC/USD',instrumentSymbol:SYMBOL,instId:'1',strike:'100.25',operator:'>',durationSeconds:900,
 windowStartTimestampMs:OPEN,windowCloseTimestampMs:EXPIRY,expiryTimestampMs:EXPIRY,tradable:true,warnings:[],underlyingSymbol:'TEST_INDEX',...overrides}; }
const selection=overrides=>({symbol:'BTC/USD',operator:'>',horizonSeconds:900,strike:'100.25',expiryTimestampMs:EXPIRY,...overrides});
test('15m exact match is supported without admitting a 1h instrument as 15m',()=>{
 const cat={status:'VALID',instruments:[contract()],coverage:'PARTIAL'};
 assert.equal(validation.matchSelectedContract(cat,selection(),NOW).status,'MATCHED');
 assert.equal(validation.matchSelectedContract(cat,selection({horizonSeconds:3600}),NOW).status,'NO_MATCH');
 assert.equal(validation.matchSelectedContract(cat,selection({horizonSeconds:60}),NOW).status,'INVALID');
 assert.equal(validation.matchSelectedContract(cat,selection(),EXPIRY).status,'EXPIRED');
});
function ticker(b,k){return {code:0,method:'public/get-tickers',result:{data:[{i:SYMBOL,t:NOW,b,k,a:null}]}};}
const quoteOptions={kind:'TICKER',source:'https://api.crypto.com/fcm/v1/public/get-tickers',expectedInstrumentSymbol:SYMBOL,receivedAtMs:NOW,allowOneSided:true};
test('one-sided native quotes preserve absence and never manufacture a complement',()=>{
 const result=validation.normalizeQuoteSnapshot(ticker(null,'0.09'),quoteOptions,NOW);
 assert.equal(result.status,'VALID');assert.equal(result.bid,null);assert.equal(result.ask,'0.09');assert.equal(result.liquidity,'ONE_SIDED');
 assert.equal(result.mappedYesNo,null);assert.equal(result.execution_allowed,false);
 assert.equal(validation.normalizeQuoteSnapshot(ticker(null,'0.09'),{...quoteOptions,allowOneSided:false},NOW).status,'INVALID');
});
test('one-sided mode still rejects missing, malformed, crossed and entirely absent quotes',()=>{
 for(const payload of [ticker('','0.09'),ticker(null,null),ticker('0.10','0.09'),ticker('-1','0.09')]) assert.equal(validation.normalizeQuoteSnapshot(payload,quoteOptions,NOW).status,'INVALID');
 const missing=ticker(null,'0.09');delete missing.result.data[0].b;
 assert.equal(validation.normalizeQuoteSnapshot(missing,quoteOptions,NOW).status,'INVALID');
});
test('documented book levels accept missing liquidity, not malformed present prices or quantities',()=>{
 const options={...quoteOptions,kind:'BOOK',source:'https://api.crypto.com/fcm/v1/public/get-book'};
 const body={code:0,method:'public/get-book',result:{instrument_name:SYMBOL,data:[{t:NOW,bids:[],asks:[['0.09','2',1]]}]}};
 const result=validation.normalizeQuoteSnapshot(body,options,NOW);assert.equal(result.status,'VALID');assert.equal(result.bid,null);assert.equal(result.ask,'0.09');
 body.result.data[0].asks=[['0.09','0']];assert.equal(validation.normalizeQuoteSnapshot(body,options,NOW).status,'INVALID');
});
class Element{
 constructor(id=''){this.id=id;this.tagName=id.startsWith('chart-')?'CANVAS':'DIV';this.children=[];this.listeners=new Map();this.value='';this.type='submit';}
 set textContent(v){this._text=v;this.children=[];}get textContent(){return this._text;}
 appendChild(v){this.children.push(v);}removeChild(v){this.children.splice(this.children.indexOf(v),1);}
 addEventListener(n,f){this.listeners.set(n,f);}removeEventListener(n){this.listeners.delete(n);}getContext(){return null;}
}
function surface({auto=true,records=[contract()],catalogueReader}={}){
 const nodes=new Map(),doc=new Element(),env=new Element(),calls={catalogue:0,start:0,stop:0};let options,state,now=NOW;
 doc.hidden=false;doc.getElementById=id=>{if(!nodes.has(id))nodes.set(id,new Element(id));return nodes.get(id);};doc.createElement=()=>new Element();
 const catalogue={status:'VALID',instruments:records,coverage:'PARTIAL'};
 Object.assign(env,{document:doc,Date:{now:()=>now},PULSO_NETWORK_ENABLED:true,PULSO_AUTO_CONNECT:auto,PULSO_DEFAULT_HORIZON_SECONDS:900,
  PulsoContractValidation:validation,AbortController,fetch:()=>{throw new Error('No real network in tests');},setInterval:()=>1,clearInterval:()=>{},
  PulsoRestFeed:{createRestClient:()=>({getCatalogue:()=>{calls.catalogue++;return catalogueReader?catalogueReader():Promise.resolve(catalogue);}}),
   createReadController:o=>{options=o;state={selection:o.selection,connection:'DISCONNECTED',following:false,data:null};return {
    getState:()=>state,start:()=>{calls.start++;return Promise.resolve(state);},readOnce:()=>Promise.resolve(state),
    stop:reason=>{calls.stop++;state={...state,data:null,following:false,reason};o.onState(state);},
    setSelection:s=>{state={...state,selection:s};o.onState(state);},setVisible:()=>{},dispose:()=>{}};}}});
 return {env,nodes,calls,setTime:n=>{now=n;},emit:s=>options.onState({...state,...s})};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
test('opening auto mode resolves one exact active 15m contract and starts without copying fields',async()=>{
 const s=surface(),c=ui.mount(s.env);await flush();await flush();
 assert.equal(s.calls.catalogue,1);assert.equal(s.calls.start,1);assert.equal(c.getState().selection.instrumentSymbol,SYMBOL);
 assert.equal(c.getState().selection.horizonSeconds,900);assert.equal(s.nodes.get('strike').value,'100.25');assert.equal(s.nodes.get('strike').readOnly,true);c.dispose();
});
test('auto mode never chooses an ambiguous or not-yet-open contract',async()=>{
 for(const records of [[contract(),contract({instrumentSymbol:SYMBOL+'-OTHER',instId:'2'})],[contract({windowStartTimestampMs:NOW+1000})]]){
  const s=surface({records}),c=ui.mount(s.env);await flush();assert.equal(s.calls.start,0);assert.equal(c.getState().selection.strike,'');c.dispose();
 }
});
test('disposing before queued auto bootstrap prevents all reads',async()=>{
 const s=surface(),c=ui.mount(s.env);c.dispose();await flush();assert.equal(s.calls.catalogue,0);assert.equal(s.calls.start,0);
});
test('duration change during catalogue read cannot auto-start an old or substituted contract',async()=>{
 let resolve;const pending=new Promise(r=>{resolve=r;});const s=surface({catalogueReader:()=>pending}),c=ui.mount(s.env);await flush();
 s.nodes.get('horizon').value='3600';s.nodes.get('horizon').listeners.get('change')();resolve({status:'VALID',instruments:[contract()],coverage:'PARTIAL'});await flush();
 assert.equal(s.calls.start,0);assert.equal(c.getState().selection.horizonSeconds,3600);assert.equal(c.getState().selection.strike,'');c.dispose();
});
test('native quote rendering is ask for buy and bid for sell; absent side stays blank',()=>{
 const s=surface({auto:false}),c=ui.mount(s.env);
 // Load/fix through genuine UI handlers, then feed an explicit normalized snapshot.
 return s.nodes.get('reload-catalogue').listeners.get('click')().then(()=>{
  s.nodes.get('contract-choice').value=SYMBOL;s.nodes.get('contract-choice').listeners.get('change')();s.nodes.get('contract-form').listeners.get('submit')({preventDefault(){}});
  const catalogue={status:'VALID',instruments:[contract()],coverage:'PARTIAL'};
  const quote=validation.normalizeQuoteSnapshot(ticker(null,'0.09'),quoteOptions,NOW);
  s.emit({data:{catalogue,quotes:{ticker:quote},context:{}}});
  assert.equal(s.nodes.get('yes-price').textContent,'$0.09');assert.equal(s.nodes.get('no-price').textContent,'—');
  assert.match(s.nodes.get('quote-provenance').textContent,/Un lado/);c.dispose();
 });
});
const feed=require('../assets/crypto_pulso/rest-feed.js');
test('index lookup is opt-in, fixed to declared CDNA index, and never substitutes spot',async()=>{
 let calls=0,rows=[];
 const client=feed.createRestClient({includeUnderlyingIndex:true,clock:()=>NOW,fetchImpl:async url=>{calls++;return {status:200,url,redirected:false,headers:{get:()=>null},text:async()=>JSON.stringify({code:0,method:'public/get-tickers',result:{data:rows}})};}});
 assert.equal((await client.getIndex({underlyingSymbol:'BTC_USD'})).status,'UNAVAILABLE');assert.equal(calls,0);
 assert.equal((await client.getIndex({underlyingSymbol:'BTCUSD-INDEX@CdnaFunded'})).status,'UNAVAILABLE');
 rows=[{i:'BTCUSD-INDEX@CdnaFunded',a:'82192.32',t:NOW}];
 const value=await client.getIndex({underlyingSymbol:'BTCUSD-INDEX@CdnaFunded'});assert.equal(value.status,'VALID');assert.equal(value.price,82192.32);
 rows[0].t=NOW-60001;assert.equal((await client.getIndex({underlyingSymbol:'BTCUSD-INDEX@CdnaFunded'})).status,'UNAVAILABLE');
 rows=[{i:'BTC_USD',a:'82192.32',t:NOW}];assert.equal((await client.getIndex({underlyingSymbol:'BTCUSD-INDEX@CdnaFunded'})).status,'UNAVAILABLE');
});
test('auto polling retires context at a normal candle boundary and waits for the next validated cycle',async()=>{
 let now=NOW;const frames=new Map(),ticks=new Map();let nextId=1;
 const timers={setTimeout:()=>nextId++,clearTimeout:()=>{},setInterval:(fn,ms)=>{const id=nextId++;ticks.set(id,{fn,ms});return id;},clearInterval:id=>ticks.delete(id)};
 const quoted=kind=>({status:'VALID',kind,instrumentSymbol:SYMBOL,providerTimestampMs:now,validUntilMs:now+60000,bid:'0.10',ask:'0.20'});
 const client={getCatalogue:async()=>({status:'VALID',instruments:[contract()],coverage:'PARTIAL'}),getTicker:async()=>quoted('TICKER'),getBook:async()=>quoted('BOOK'),
  getCandles:async({intervalSeconds})=>{const count=(frames.get(intervalSeconds)||0)+1;frames.set(intervalSeconds,count);return {status:'VALID',purpose:'CONTEXT_ONLY_NOT_SETTLEMENT_INDEX',validUntilMs:intervalSeconds===300 && count===1 ? NOW+1 : now+300000};}};
 const controller=feed.createReadController({client,selection:selection(),clock:()=>now,timers,isVisible:()=>true,refreshContextOnBoundary:true});
 await controller.start({userInitiated:true});assert.equal(controller.getState().following,true);
 now=NOW+2;const waiting=controller.getState();assert.equal(waiting.following,true);assert.equal(waiting.reason,'CONTEXT_REFRESH_PENDING');assert.equal(waiting.data.context.m5,null);assert.equal(waiting.data.context.m15,null);
 assert.equal(frames.get(300),1); // Rechecking time never performs a new network read.
 const poll=Array.from(ticks.values()).find(t=>t.ms===10000);assert.ok(poll);poll.fn();await flush();
 assert.equal(frames.get(300),2);assert.equal(controller.getState().data.context.m5.status,'VALID');controller.dispose();
});
