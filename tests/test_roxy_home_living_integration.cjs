'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

const source=fs.readFileSync(require.resolve('../assets/roxy_list.js'),'utf8');
const livingSource=fs.readFileSync(require.resolve('../assets/roxy_home_living.js'),'utf8');
// Execute the production functions with their services stubbed; keep route and
// recovery decisions in the application rather than duplicating them here.
function functionBlock(start,end){
  const from=source.indexOf(start),to=source.indexOf(end,from);
  assert.ok(from>=0&&to>from,`Production boundary: ${start}`);
  return source.slice(from,to);
}
const functions=[
  functionBlock('  async function load(', '  async function queueMutation('),
  functionBlock('  function bindHomeTour(', '  function addModuleHelp('),
  functionBlock('  function selectPanel(', '  const calendarCategories='),
  functionBlock('  const initialPanels=', '  window.addEventListener(\'hashchange\''),
].join('\n');

function harness({mode='member',failureStatus=0,failIdentity=false,fitnessWorld=false}={}){
  const noop=()=>{},bindings=[],opened=[],shown=[],cacheReads=[],forms=[],requests=[],nodes=new Map();
  const node=id=>{
    if(!nodes.has(id))nodes.set(id,{hidden:true,dataset:{},classList:{toggle:noop},showModal(){this.open=true},scrollIntoView:noop,scrollTo:noop,click:()=>forms.push({name:id})});
    return nodes.get(id);
  };
  const panels=['house','today','recipes','shopping','calendar','plants','fitness','design','family','pantry','more'].map(panel=>({...node(panel),dataset:{panel}}));
  const member={mode:'member',id:'member-a',session_version:2,storage_user_id:'home-a',home_tour_completed:false};
  const failure=()=>Object.assign(new Error('Simulated endpoint failure'),{status:failureStatus});
  // Use the real room contract so route tests cover the integration rather than
  // a duplicated map that could agree with a broken application by accident.
  const cinematic=fitnessWorld?{mount:noop}:undefined;
  const livingContext={window:{RoxyFitnessWorld:cinematic},document:{addEventListener:noop}};
  vm.runInNewContext(livingSource,livingContext);
  const living=livingContext.window.RoxyHomeLiving;
  const context={
    account:mode==='member'?{...member}:{mode},user:'home-a',activePanel:'house',tourPromptedIdentity:'',appearance:{},
    familyWeatherGlobeActive:false,recipeAudience:'human',priceRecommendations:null,priceRecommendationsLoading:false,
    collectionRecovery:{},collectionLoadErrors:{},snapshot:{},homeFood:{},homeFoodReady:false,homeFoodLoadFailed:false,
    commerce:{},homeCalendar:{},homeDaily:null,homeDesign:{},homePlants:{},homeFamily:{},homeWeather:{},
    $:node,document:{body:{classList:{toggle:noop}},querySelector:()=>null,querySelectorAll:selector=>selector==='[data-panel]'?panels:[]},
    location:{hash:''},localStorage:{setItem:noop},sessionStorage:{getItem:()=>null,setItem:noop},
    window:{scrollTo:noop,RoxyFitnessWorld:cinematic,RoxyHomeTour:{stop:noop,bind:value=>bindings.push(value),home:noop,open:(chapter,options)=>opened.push({chapter,options})},RoxyHomeLiving:{...living,show:panel=>shown.push(panel),enter:noop}},
    requestAnimationFrame:fn=>fn(),
    api:async(path,options)=>{requests.push({path,options});if(path==='/v1/home-account/me'&&!failIdentity)return {...member};throw failure()},
    collectionApi:async()=>null,
    dbGet:async key=>{cacheReads.push(key);return key==='snapshot:home-a'?{items:[{id:'saved-item',name:'Arroz'}]}:null},
    collectionCacheKey:(kind,owner,identity)=>`${kind}:${owner}:${identity}`,
    safeAppearance:value=>value,prepareRecipePreferences:async isCurrent=>isCurrent(),
  };
  context.collectionIdentity=()=>`${context.account.mode}:${context.account.id||''}`;
  for(const name of ['stopCookingSpeech','resetRoxyVoiceContext','setBusy','syncFamilyMapReadiness','clearRecipePreferences','applyAppearance','setConnection','populateHomeForms','render','activateRecipeSources','renderRecipes','addModuleHelp','openRoxyVoice','renderAccount','renderHomeMoment','mountFitness','renderFamily'])context[name]=noop;
  for(const name of ['refreshDesignProjects','refreshPlants','refreshFamily','loadPriceRecommendations'])context[name]=async()=>{};
  for(const name of ['openPlantForm','openPetProfile','openCalendarEvent','openPersonalization'])context[name]=(...args)=>{forms.push({name,args});return `opened:${name}`};
  vm.createContext(context);
  vm.runInContext(`'use strict';\n${functions}`,context);
  return {context,bindings,opened,shown,cacheReads,node,panels,forms,requests,living,initialPanel:hash=>vm.runInContext(`initialPanels[${JSON.stringify(hash)}]`,context)};
}

for(const mode of ['checking','unknown'])test(`pending ${mode} identity preserves the requested room until authentication resolves`,()=>{
  const h=harness({mode});h.context.selectPanel('house');
  assert.equal(h.context.activePanel,'house');assert.equal(h.context.location.hash,'hoy');
  h.context.selectPanel('kitchen');assert.equal(h.context.activePanel,'kitchen');
});

test('legacy navigation consistently opens the existing day and recipe tools',()=>{
  const h=harness({mode:'legacy'});
  for(let repeat=0;repeat<2;repeat++){
    h.context.selectPanel('house');assert.equal(h.context.activePanel,'today');
    assert.equal(h.panels.find(p=>p.dataset.panel==='today').hidden,false);
    h.context.selectPanel('kitchen');assert.equal(h.context.activePanel,'recipes');
    assert.equal(h.panels.find(p=>p.dataset.panel==='recipes').hidden,false);
  }
  assert.deepEqual(h.shown,['today','recipes','today','recipes']);
});

test('member rooms retain their routes and use the same existing tool panels',()=>{
  const h=harness();h.context.selectPanel('kitchen');
  assert.equal(h.context.activePanel,'kitchen');assert.equal(h.context.location.hash,'cocina');
  assert.equal(h.panels.find(p=>p.dataset.panel==='house').hidden,false);
  h.context.selectPanel('recipes');assert.equal(h.context.location.hash,'recetas');
  assert.equal(h.panels.find(p=>p.dataset.panel==='recipes').hidden,false);
});

test('verified member with a failed data request can enter rooms from preserved cache without an automatic tour',async()=>{
  const h=harness({mode:'checking'});await h.context.load();
  assert.equal(h.context.account.id,'member-a');assert.equal(h.node('app').hidden,false);
  assert.equal(h.context.snapshot.items[0].id,'saved-item');
  const owner=h.bindings.at(-1);assert.equal(owner?.identity,'member-a');assert.equal(owner?.version,2);assert.equal(owner?.isCurrent(),true);
  assert.equal(h.opened.length,0);assert.equal(h.context.tourPromptedIdentity,'');
  // Suppressing an offline prompt must not suppress the next normal welcome.
  h.context.bindHomeTour();assert.equal(h.opened.length,1);assert.equal(h.opened[0].options.automatic,true);
});

test('rejected session never rebinds rooms or reads cached household data',async()=>{
  const h=harness({failureStatus:401});await h.context.load();
  assert.equal(h.context.account.mode,'signed_out');assert.equal(h.node('app').hidden,true);
  assert.equal(h.bindings.at(-1),null);assert.equal(h.cacheReads.length,0);assert.equal(h.opened.length,0);
});

test('unverified new session cannot open rooms by recovering private cache',async()=>{
  const h=harness({mode:'checking',failIdentity:true});await h.context.load();
  assert.equal(h.node('app').hidden,true);assert.equal(h.cacheReads.length,0);
  assert.equal(h.bindings.some(Boolean),false);assert.equal(h.opened.length,0);
});

const rooms=[
  ['house','hoy','today'],['kitchen','cocina','recipes'],['garden','patio','plants'],
  ['wellness','bienestar','fitness'],['companions','companeros','pets'],['atelier','estudio','design'],
  ['connection','encuentro','family'],['agenda','agenda','calendar'],
];

for(const mode of ['checking','unknown','member'])test(`${mode} routes every immersive entrance to the shared house panel`,()=>{
  const h=harness({mode});
  for(const [room,hash] of rooms){
    h.context.selectPanel(room);assert.equal(h.context.activePanel,room);assert.equal(h.context.location.hash,hash);
    assert.equal(h.initialPanel(hash),room);assert.equal(h.panels.filter(p=>!p.hidden).length,1);
    assert.equal(h.panels.find(p=>p.dataset.panel==='house').hidden,false);
  }
});

test('legacy accounts consistently fall back to existing module tools for all room links',()=>{
  const h=harness({mode:'legacy'});
  for(const [room,,tool] of rooms){
    h.context.selectPanel(room);assert.equal(h.context.activePanel,tool);
    assert.equal(h.panels.find(p=>p.dataset.panel===(tool==='pets'?'recipes':tool)).hidden,false);
  }
});

test('existing bookmarked tool routes keep their original panels and direct food-tool entry points',()=>{
  const h=harness();
  const tools=[['dia','today','house'],['recetas','recipes','kitchen'],['despensa','pantry','kitchen'],['compra','shopping','kitchen'],['jardin','plants','garden'],['ejercicio','fitness','wellness'],['mascotas','pets','companions'],['renueva','design','atelier'],['nexo','family','connection'],['calendario','calendar','agenda']];
  for(const [hash,tool,room] of tools){
    assert.equal(h.initialPanel(hash),tool);h.context.selectPanel(tool);assert.equal(h.context.location.hash,hash);
    assert.equal(h.panels.find(p=>p.dataset.panel===(tool==='pets'?'recipes':tool)).hidden,false);
    assert.equal(h.living.entryFor(tool),['recipes','pantry','shopping'].includes(tool)?tool:room);
  }
});

test('primary and More navigation enter rooms while links inside a task keep opening the exact tool',()=>{
  const h=harness(),links=[],entrances={fitness:'wellness',plants:'garden',pets:'companions',design:'atelier',family:'connection',calendar:'agenda',recipes:'recipes',pantry:'pantry',shopping:'shopping'};
  for(const location of ['primary','more','task'])for(const target of Object.keys(entrances)){
    const link={dataset:{tabLink:target},location,closest:selector=>{assert.equal(selector,'.bottom-nav,.more-shortcuts');return location==='task'?null:{}},addEventListener:(event,handler)=>{assert.equal(event,'click');link.click=handler}};
    links.push(link);
  }
  const query=h.context.document.querySelectorAll;
  h.context.document.querySelectorAll=selector=>selector==='[data-tab-link]'?links:query(selector);
  vm.runInContext(functionBlock("    document.querySelectorAll('[data-tab-link]').forEach", "    document.querySelectorAll('[data-open-custom]')"),h.context);
  for(const link of links){
    let prevented=false;link.click({preventDefault:()=>prevented=true});assert.equal(prevented,true);
    assert.equal(h.context.activePanel,link.location==='task'?link.dataset.tabLink:entrances[link.dataset.tabLink]);
  }
});

test('cinematic exercise opens directly from primary navigation without visiting the old room',()=>{
  const h=harness({fitnessWorld:true}),links=[];let mounts=0;
  h.context.mountFitness=()=>mounts++;
  for(const location of ['primary','more','task']){
    const link={dataset:{tabLink:'fitness'},closest:()=>location==='task'?null:{},addEventListener:(event,handler)=>link.click=handler};links.push(link);
  }
  const query=h.context.document.querySelectorAll;
  h.context.document.querySelectorAll=selector=>selector==='[data-tab-link]'?links:query(selector);
  vm.runInContext(functionBlock("    document.querySelectorAll('[data-tab-link]').forEach", "    document.querySelectorAll('[data-open-custom]')"),h.context);
  links.forEach(link=>link.click({preventDefault(){}}));
  assert.equal(h.living.entryFor('fitness'),'fitness');
  assert.deepEqual(h.shown,['fitness','fitness','fitness']);assert.equal(mounts,3);
  assert.equal(h.context.location.hash,'ejercicio');assert.equal(h.panels.find(p=>p.dataset.panel==='fitness').hidden,false);
  assert.equal(h.requests.length,0);assert.equal(h.opened.length,0);
});

test('house exercise entrance and legacy wellbeing bookmark open the cinematic module and return to Casa',()=>{
  const h=harness({fitnessWorld:true});let mounts=0;h.context.mountFitness=()=>mounts++;
  h.context.bindHomeTour({prompt:false});const owner=h.bindings.at(-1);
  owner.navigate('wellness');
  assert.equal(h.context.activePanel,'fitness');assert.equal(h.context.location.hash,'ejercicio');
  assert.equal(h.panels.find(p=>p.dataset.panel==='fitness').hidden,false);assert.equal(mounts,1);
  owner.navigate('house');assert.equal(h.context.activePanel,'house');assert.equal(h.context.location.hash,'hoy');
  assert.equal(h.panels.find(p=>p.dataset.panel==='house').hidden,false);
  h.context.selectPanel(h.initialPanel('bienestar'));
  assert.equal(h.context.activePanel,'fitness');assert.equal(mounts,2);
  assert.equal(h.requests.length,0);assert.equal(h.opened.length,0);
});

test('cinematic exercise keeps other room destinations and authentication recovery unchanged',async()=>{
  const h=harness({fitnessWorld:true});
  for(const [room,hash] of rooms.filter(([room])=>room!=='wellness')){
    h.context.selectPanel(room);assert.equal(h.context.activePanel,room);assert.equal(h.context.location.hash,hash);
  }
  assert.equal(h.living.entryFor('plants'),'garden');assert.equal(h.living.entryFor('calendar'),'agenda');
  const rejected=harness({fitnessWorld:true,failureStatus:401});await rejected.context.load();
  assert.equal(rejected.node('app').hidden,true);assert.equal(rejected.bindings.at(-1),null);assert.equal(rejected.cacheReads.length,0);
});

test('authorized room actions open the current forms without writing household data',()=>{
  const h=harness();h.context.bindHomeTour({prompt:false});const owner=h.bindings.at(-1),flow={isCurrent:()=>true};
  assert.equal(owner.openForm('plant-new',flow),'opened:openPlantForm');
  owner.openForm('pet-new');owner.openForm('calendar-new');owner.openForm('design-new');owner.openForm('family-privacy');
  assert.deepEqual(h.forms.map(form=>form.name),['openPlantForm','openPetProfile','openCalendarEvent','designUploadButton']);
  assert.equal(h.forms[0].args[0],null);assert.equal(h.forms[0].args[1],flow);
  assert.equal(h.context.activePanel,'family');assert.equal(h.node('familySettings').open,true);
  assert.equal(h.requests.length,0);assert.equal(h.opened.length,0);
});

test('unknown actions are ignored by the Home form bridge',()=>{
  const h=harness();h.context.bindHomeTour({prompt:false});h.bindings.at(-1).openForm('delete-home');
  assert.equal(h.forms.length,0);assert.equal(h.requests.length,0);
});

for(const change of ['member','version','signed-out'])test(`retained form bridge cannot act after ${change} context changes`,()=>{
  const h=harness();h.context.bindHomeTour({prompt:false});const owner=h.bindings.at(-1);
  if(change==='member')h.context.account.id='member-b';
  else if(change==='version')h.context.account.session_version++;
  else h.context.account.mode='signed_out';
  assert.equal(owner.isCurrent(),false);
  for(const destination of ['plant-new','pet-new','calendar-new','design-new','family-privacy'])owner.openForm(destination);
  assert.equal(h.forms.length,0);assert.notEqual(h.context.activePanel,'family');assert.equal(h.requests.length,0);
});
