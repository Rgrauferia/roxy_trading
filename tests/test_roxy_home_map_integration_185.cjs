/* Real map lifecycle functions + real readiness helper, no external APIs. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');
const main=fs.readFileSync(path.join(__dirname,'../assets/roxy_list.js'),'utf8');
const helper=fs.readFileSync(path.join(__dirname,'../assets/roxy_home_map_readiness.js'),'utf8');
function between(start,end){const from=main.indexOf(start),to=main.indexOf(end,from);assert.ok(from>=0&&to>from);return main.slice(from,to)}
const functions=between('  function cancelFamilyHistory(', '  const familyFriendlyDate=')
  +between('  function resetFamilyBaseMap(', '  function loadFamilyGoogleMaps(')
  +between('  async function renderFamilyMap(){','  async function refreshFamily()');
function fixture(){
  const timers=new Map(),constructed=[],calls={clear:0,removed:0,trafficDetached:0,gps:0,writes:0,load:0,readyAttachments:0};let sequence=0;
  const notice={hidden:true},app={hidden:false},root={children:[],replaceChildren(){calls.clear++;this.children=[]},querySelector(){return {addEventListener(){}}},firstElementChild:{append(){}},innerHTML:''};
  const historyElements=new Map();for(const id of ['familyHistoryPanel','familyHistoryList','familyHistorySummary','familyHistoryButton'])historyElements.set(id,{hidden:true,textContent:'',innerHTML:'',replaceChildren(){this.innerHTML='';this.textContent=''},setAttribute(){}});
  function makeMap(options={}){
    const events=new Map();let center=options.center||{lat:42,lng:17},zoom=options.zoom??13,type=options.mapTypeId||'satellite';
    const map={events,options,addListener(name,callback){if(name==='tilesloaded')calls.readyAttachments++;events.set(name,callback);return {remove(){calls.removed++;events.delete(name)}}},
      getCenter:()=>({lat:()=>center.lat,lng:()=>center.lng}),getZoom:()=>zoom,getMapTypeId:()=>type,
      setCenter(value){center=value},setZoom(value){zoom=value},setMapTypeId(value){type=value},setOptions(){},fitBounds(){},fire(name='tilesloaded'){events.get(name)?.()}};
    return map;
  }
  const window={setTimeout(callback,ms){const id=++sequence;timers.set(id,{callback,ms});return id},clearTimeout:id=>timers.delete(id)};
  const context={window,document:{hidden:false},user:'home-A',account:{mode:'member',id:'A'},activePanel:'family',AbortController,
    $:id=>id==='familyMap'?root:id==='familyMapLoadNotice'?notice:id==='app'?app:historyElements.get(id)||null,
    collectionIdentity:()=>`${context.account.mode}:${context.account.id}`,
    familyMap:null,familyMapReadiness:null,familyMapReadinessScope:'',familyMapRetryView:null,familyMapRetryScope:'',familyMapRetryAttempt:null,
    familyMapZoomListener:null,familyMapMarkers:[],familyMapViewportInitialized:false,familyTrafficLayer:{setMap(value){assert.equal(value,null);calls.trafficDetached++}},
    familyMapStyle:'roadmap',familySelectedPlaceId:'',familySelectedMemberId:'',familyMapTransitioning:false,familyWeatherGlobeActive:false,
    familyHistoryOpen:false,familyHistoryPoints:[],familyHistoryGeneration:0,familyHistoryRequest:null,familyHistoryScope:'',homeFamily:{map:{provider:'GOOGLE_MAPS'},members:[],places:[]},
    loadFamilyGoogleMaps:async()=>{calls.load++},familyWeatherMapStyles:styles=>styles,
    google:{maps:{Map:class{constructor(element,options){const map=makeMap(options);constructed.push(map);return map}},LatLngBounds:class{extend(){}getCenter(){return{lat:0,lng:0}}},Circle:class{setMap(){}}}},
    clearFamilyRoutes(){},syncFamilyTraffic(){},familySelectedMember:()=>null,renderFamilyRouteCard:async()=>{},renderFamilyHistoryPanel(){},
    createFamilyMapPlace:()=>({setMap(){}}),createFamilyMapPerson:()=>({setMap(){}}),activateFamilyWeatherGlobe:async()=>{},
    api:async()=>{calls.writes++;throw new Error('No API allowed')},navigator:{geolocation:{getCurrentPosition(){calls.gps++;throw new Error('No GPS allowed')}}},
    escapeHtml:value=>String(value),makeButton:()=>({}),announce(){},
  };
  vm.createContext(context);vm.runInContext(helper,context);vm.runInContext(functions,context);
  const expire=()=>{for(const[id,{callback}]of [...timers]){timers.delete(id);callback()}};
  return {context,timers,constructed,calls,notice,root,app,makeMap,expire};
}
test('constructor immediately attaches tiles listener; only tiles set ready',async()=>{
  const f=fixture();await f.context.renderFamilyMap();assert.equal(f.constructed.length,1);assert.equal(f.calls.readyAttachments,1);
  assert.equal(f.context.familyMapReadiness.getState().phase,'loading');assert.equal(f.notice.hidden,true);
  f.context.familyMap.fire();assert.equal(f.context.familyMapReadiness.getState().phase,'ready');assert.equal(f.timers.size,0);
});
test('delayed notice does not recurse, request GPS, mutate API or rebuild automatically',async()=>{
  const f=fixture();await f.context.renderFamilyMap();f.expire();
  assert.equal(f.notice.hidden,false);assert.equal(f.constructed.length,1);assert.equal(f.timers.size,0);
  assert.equal(f.calls.gps,0);assert.equal(f.calls.writes,0);f.context.syncFamilyMapReadiness();assert.equal(f.timers.size,0);
  f.context.familyMap.fire();assert.equal(f.notice.hidden,true);
});
test('reset removes listeners, markers and DOM while discarding view by default',async()=>{
  const f=fixture();await f.context.renderFamilyMap();let markers=0;f.context.familyMapMarkers=[{setMap(value){assert.equal(value,null);markers++}}];
  const map=f.context.familyMap;f.context.resetFamilyBaseMap();
  assert.equal(f.context.familyMap,null);assert.equal(f.context.familyMapReadiness,null);assert.equal(f.context.familyMapReadinessScope,'');
  assert.equal(f.context.familyMapRetryView,null);assert.equal(f.context.familyMapViewportInitialized,false);assert.equal(markers,1);
  assert.equal(map.events.size,0);assert.equal(f.timers.size,0);assert.equal(f.notice.hidden,true);assert.equal(f.calls.trafficDetached,1);
});
test('manual retry preserves exact in-memory center zoom and satellite type without GPS or writes',async()=>{
  const f=fixture();await f.context.renderFamilyMap();f.context.familyMap.setCenter({lat:42,lng:17});f.context.familyMap.setZoom(11);f.context.familyMap.setMapTypeId('satellite');
  const old=f.context.familyMap;await f.context.retryFamilyBaseMap();const next=f.context.familyMap;
  assert.notEqual(next,old);assert.equal(old.events.size,0);assert.equal(next.getCenter().lat(),42);assert.equal(next.getCenter().lng(),17);
  assert.equal(next.getZoom(),11);assert.equal(next.getMapTypeId(),'satellite');assert.equal(f.context.familyMapViewportInitialized,true);
  assert.equal(f.context.familyMapRetryView,null);assert.equal(f.constructed.length,2);assert.equal(f.calls.gps,0);assert.equal(f.calls.writes,0);
});
for(const reason of ['hidden','other-panel','globe','signed-out'])test(`manual retry is unavailable for ${reason}`,async()=>{
  const f=fixture();await f.context.renderFamilyMap();
  if(reason==='hidden')f.context.document.hidden=true;if(reason==='other-panel')f.context.activePanel='recipes';
  if(reason==='globe')f.context.familyWeatherGlobeActive=true;if(reason==='signed-out')f.context.account.mode='signed_out';
  await f.context.retryFamilyBaseMap();assert.equal(f.constructed.length,1);assert.equal(f.calls.load,1);
});
for(const reason of ['identity','household','signed-out'])test(`${reason} change clears old private map`,async()=>{
  const f=fixture();await f.context.renderFamilyMap();const map=f.context.familyMap;
  if(reason==='identity')f.context.account.id='B';if(reason==='household')f.context.user='home-B';if(reason==='signed-out')f.context.account.mode='signed_out';
  f.context.syncFamilyMapReadiness();assert.equal(f.context.familyMap,null);assert.equal(map.events.size,0);assert.equal(f.timers.size,0);
  assert.equal(f.context.familyMapRetryView,null);assert.equal(f.notice.hidden,true);
});
for(const reason of ['hidden','other-panel','globe','hidden-app'])test(`${reason} pauses pending tiles without destroying map`,async()=>{
  const f=fixture();await f.context.renderFamilyMap();const map=f.context.familyMap;
  if(reason==='hidden')f.context.document.hidden=true;if(reason==='other-panel')f.context.activePanel='recipes';
  if(reason==='globe')f.context.familyWeatherGlobeActive=true;if(reason==='hidden-app')f.app.hidden=true;
  f.context.syncFamilyMapReadiness();assert.equal(f.timers.size,0);assert.equal(f.context.familyMap,map);assert.equal(f.notice.hidden,true);
  f.context.document.hidden=false;f.context.activePanel='family';f.context.familyWeatherGlobeActive=false;f.app.hidden=false;
  f.context.syncFamilyMapReadiness();assert.equal(f.timers.size,1);map.fire();assert.equal(f.timers.size,0);
});
test('identity change during library wait does not construct old map',async()=>{
  const f=fixture();let release;f.context.loadFamilyGoogleMaps=()=>new Promise(resolve=>release=resolve);
  const pending=f.context.renderFamilyMap();f.context.account.id='B';release();await pending;assert.equal(f.constructed.length,0);
});
test('post-construction error clears detached instance so a subsequent render rebuilds',async()=>{
  const f=fixture();f.context.syncFamilyTraffic=()=>{throw new Error('synthetic post-construction failure')};await f.context.renderFamilyMap();
  assert.equal(f.constructed.length,1);assert.equal(f.context.familyMap,null);assert.equal(f.timers.size,0);assert.match(f.root.innerHTML,/No pude abrir el mapa/);
  f.context.syncFamilyTraffic=()=>{};await f.context.renderFamilyMap();assert.equal(f.constructed.length,2);assert.notEqual(f.context.familyMap,null);
});
test('stale library rejection cannot clear a newer identity map',async()=>{
  const f=fixture();let reject;f.context.loadFamilyGoogleMaps=()=>new Promise((_,no)=>reject=no);const pending=f.context.renderFamilyMap();
  f.context.account.id='B';f.context.loadFamilyGoogleMaps=async()=>{};await f.context.renderFamilyMap();const newer=f.context.familyMap;
  reject(new Error('late A error'));await pending;assert.equal(f.context.familyMap,newer);assert.equal(f.constructed.length,1);
});
test('retry view cannot leak from A to B while library reload is pending',async()=>{
  const f=fixture();await f.context.renderFamilyMap();f.context.familyMap.setCenter({lat:42,lng:17});
  let release;f.context.loadFamilyGoogleMaps=()=>new Promise(resolve=>release=resolve);const pending=f.context.retryFamilyBaseMap();
  f.context.account.id='B';f.context.syncFamilyMapReadiness();release();await pending;f.context.loadFamilyGoogleMaps=async()=>{};
  await f.context.renderFamilyMap();assert.notEqual(f.context.familyMap.getCenter().lat(),42,'New member must not inherit prior member center');
});
test('provider removal disposes old map before replacing its DOM',async()=>{
  const f=fixture();await f.context.renderFamilyMap();const old=f.context.familyMap;f.context.homeFamily.map.provider='NONE';
  await f.context.renderFamilyMap();assert.equal(f.context.familyMap,null);assert.equal(old.events.size,0);assert.equal(f.timers.size,0);
  f.context.homeFamily.map.provider='GOOGLE_MAPS';await f.context.renderFamilyMap();assert.equal(f.constructed.length,2);
});
for(const reason of ['provider-removed','hidden-app','hidden-document'])test(`${reason} during library wait never constructs a new hidden/unavailable map`,async()=>{
  const f=fixture();let release;f.context.loadFamilyGoogleMaps=()=>new Promise(resolve=>release=resolve);const pending=f.context.renderFamilyMap();
  if(reason==='provider-removed')f.context.homeFamily.map.provider='NONE';if(reason==='hidden-app')f.app.hidden=true;if(reason==='hidden-document')f.context.document.hidden=true;
  release();await pending;assert.equal(f.constructed.length,0);
});
test('a duplicate manual retry while library loading does not discard the captured view',async()=>{
  const f=fixture();await f.context.renderFamilyMap();f.context.familyMap.setCenter({lat:42,lng:17});f.context.familyMap.setZoom(11);
  let release;const wait=new Promise(resolve=>release=resolve);f.context.loadFamilyGoogleMaps=()=>wait;
  const first=f.context.retryFamilyBaseMap(),second=f.context.retryFamilyBaseMap();release();await Promise.all([first,second]);
  assert.equal(f.constructed.length,2);assert.equal(f.context.familyMap.getCenter().lat(),42);assert.equal(f.context.familyMap.getZoom(),11);
});
test('resume after hidden library completion constructs missing visible map once and never recurses',async()=>{
  const f=fixture();let release;f.context.loadFamilyGoogleMaps=()=>new Promise(resolve=>release=resolve);const pending=f.context.renderFamilyMap();
  f.context.document.hidden=true;release();await pending;assert.equal(f.constructed.length,0);
  f.context.loadFamilyGoogleMaps=async()=>{f.calls.load++};f.context.resumeFamilyBaseMap();assert.equal(f.calls.load,0);
  f.context.document.hidden=false;f.context.resumeFamilyBaseMap();for(let index=0;index<8;index++)await Promise.resolve();
  assert.equal(f.constructed.length,1);assert.equal(f.calls.load,1);f.context.familyMap.fire();f.context.resumeFamilyBaseMap();
  assert.equal(f.constructed.length,1);assert.equal(f.calls.load,1);assert.equal(f.context.familyMapReadiness.getState().phase,'ready');
});
for(const reason of ['identity','history-closed','leave-panel','sharing-revoked','member-removed','selection-changed'])test(`late history after ${reason} cannot write points or repaint`,async()=>{
  const f=fixture();const person={id:'synthetic-A-member',sharing_enabled:true,location:{latitude:42,longitude:17}};
  f.context.homeFamily.members=[person,{id:'synthetic-B-member',sharing_enabled:true,location:{latitude:12,longitude:34}}];
  f.context.familySelectedMemberId=person.id;f.context.familySelectedMember=()=>f.context.homeFamily.members.find(row=>row.id===f.context.familySelectedMemberId);
  f.context.familyHistoryOpen=true;let release,painted=0,routes=0;f.context.api=()=>new Promise(resolve=>release=resolve);f.context.renderFamilyHistoryPanel=()=>painted++;f.context.renderFamilyRouteCard=async()=>routes++;
  const pending=f.context.renderFamilyMap();for(let i=0;i<8;i++)await Promise.resolve();assert.equal(typeof release,'function');
  if(reason==='identity'){f.context.account.id='B';f.context.syncFamilyMapReadiness()}
  if(reason==='history-closed')f.context.familyHistoryOpen=false;
  if(reason==='leave-panel')f.context.activePanel='recipes';
  if(reason==='sharing-revoked')person.sharing_enabled=false;
  if(reason==='member-removed')f.context.homeFamily.members=[];
  if(reason==='selection-changed')f.context.familySelectedMemberId='synthetic-B-member';
  release({points:[{synthetic_owner:'A'}]});await pending;
  assert.equal(f.context.familyHistoryPoints.length,0,'Stale history must not be retained');assert.equal(painted,0,'Stale history must not repaint');
  if(reason!=='history-closed')assert.equal(routes,0,'Stale map render must not invalidate a newer route');
});
function historyFixture(){
  const f=fixture(),requests=[],paints=[];
  const person={id:'synthetic-A-member',sharing_enabled:true,location:{latitude:42,longitude:17}};
  f.context.homeFamily.members=[person];f.context.familySelectedMemberId=person.id;
  f.context.familySelectedMember=()=>f.context.homeFamily.members.find(row=>row.id===f.context.familySelectedMemberId);
  f.context.api=(url,options)=>new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}));
  f.context.renderFamilyHistoryPanel=points=>paints.push(points);
  return {...f,requests,paints,person};
}
test('direct history loader accepts only the current request and uses an abort signal',async()=>{
  const f=historyFixture(),pending=f.context.loadFamilyHistoryPanel(true);
  assert.equal(f.requests.length,1);assert.ok(f.requests[0].options.signal instanceof AbortSignal);
  f.requests[0].resolve({points:[{synthetic_owner:'current'}]});await pending;
  assert.equal(f.context.familyHistoryPoints[0].synthetic_owner,'current');assert.equal(f.paints.length,1);assert.equal(f.context.familyHistoryRequest,null);
});
test('closing history aborts pending work and never fetches new data',async()=>{
  const f=historyFixture(),pending=f.context.loadFamilyHistoryPanel(true);
  await f.context.loadFamilyHistoryPanel(false);assert.equal(f.requests.length,1);assert.equal(f.requests[0].options.signal.aborted,true);
  assert.equal(f.context.familyHistoryOpen,false);assert.equal(f.context.$('familyHistoryPanel').hidden,true);
  f.requests[0].resolve({points:[{synthetic_owner:'old'}]});await pending;assert.equal(f.paints.length,0);assert.equal(f.context.familyHistoryPoints.length,0);
});
test('close and reopen ABA cannot revive old history or release the new request',async()=>{
  const f=historyFixture(),first=f.context.loadFamilyHistoryPanel(true);f.context.cancelFamilyHistory({close:true});
  const second=f.context.loadFamilyHistoryPanel(true);const newer=f.context.familyHistoryRequest;
  f.requests[0].resolve({points:[{synthetic_owner:'old'}]});await first;
  assert.equal(f.context.familyHistoryRequest,newer);assert.equal(f.paints.length,0);
  f.requests[1].resolve({points:[{synthetic_owner:'new'}]});await second;
  assert.equal(f.context.familyHistoryPoints[0].synthetic_owner,'new');assert.equal(f.paints.length,1);
});
test('identity A to B to A with reset cannot restore the first A history',async()=>{
  const f=historyFixture();await f.context.renderFamilyMap();const first=f.context.loadFamilyHistoryPanel(true);
  f.context.account.id='B';f.context.syncFamilyMapReadiness();f.context.account.id='A';const second=f.context.loadFamilyHistoryPanel(true);
  f.requests[0].resolve({points:[{synthetic_owner:'old-A'}]});await first;assert.equal(f.paints.length,0);
  f.requests[1].resolve({points:[{synthetic_owner:'new-A'}]});await second;assert.equal(f.context.familyHistoryPoints[0].synthetic_owner,'new-A');
});
test('leaving and returning ABA invalidates pending history even under the same identity',async()=>{
  const f=historyFixture(),first=f.context.loadFamilyHistoryPanel(true);
  f.context.activePanel='recipes';f.context.syncFamilyMapReadiness();assert.equal(f.requests[0].options.signal.aborted,true);
  f.context.activePanel='family';const second=f.context.loadFamilyHistoryPanel(true);
  f.requests[0].resolve({points:[{synthetic_owner:'old'}]});await first;assert.equal(f.paints.length,0);
  f.requests[1].resolve({points:[{synthetic_owner:'new'}]});await second;assert.equal(f.paints.length,1);
});
test('direct history loader without sharing closes and performs no request',async()=>{
  const f=historyFixture();f.person.sharing_enabled=false;await f.context.loadFamilyHistoryPanel(true);
  assert.equal(f.requests.length,0);assert.equal(f.context.familyHistoryOpen,false);assert.equal(f.context.familyHistoryPoints.length,0);
});
test('a stale history rejection cannot clear a newer completed request',async()=>{
  const f=historyFixture(),first=f.context.loadFamilyHistoryPanel(true),second=f.context.loadFamilyHistoryPanel(true);
  f.requests[1].resolve({points:[{synthetic_owner:'new'}]});await second;f.requests[0].reject(new Error('old response failed'));await first;
  assert.equal(f.context.familyHistoryPoints[0].synthetic_owner,'new');assert.equal(f.paints.length,1);
});
test('completed history from A is cleared on identity change even if Google map never constructed',async()=>{
  const f=historyFixture(),pending=f.context.loadFamilyHistoryPanel(true);f.requests[0].resolve({points:[{synthetic_owner:'A'}]});await pending;
  assert.equal(f.context.familyMap,null);assert.equal(f.context.familyMapReadinessScope,'');assert.equal(f.context.familyHistoryRequest,null);
  f.context.$('familyHistoryList').innerHTML='Synthetic A history';f.context.account.id='B';f.context.syncFamilyMapReadiness();
  assert.equal(f.context.familyHistoryPoints.length,0);assert.equal(f.context.familyHistoryScope,'');assert.equal(f.context.familyHistoryOpen,false);
  assert.equal(f.context.$('familyHistoryPanel').hidden,true);assert.equal(f.context.$('familyHistoryList').innerHTML,'');
});
