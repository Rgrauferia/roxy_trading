'use strict';
// Synthetic classes exercise the UI contract; these are not clinical recommendations.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../assets/roxy_fitness_discovery.js'),'utf8');
const api=require('../assets/roxy_fitness_discovery.js');
const clone=value=>JSON.parse(JSON.stringify(value));
const fixture=[
  ['chair-yoga','Yoga con silla','yoga',20,'en','class'],
  ['pilates-flow','Pilates de pie','pilates',30,'es','class'],
  ['pushup-demo','Flexiones adaptadas','calisthenics',null,'en','technique'],
  ['easy-mobility','Movilidad suave','mobility',10,'es','class'],
  ['strength-demo','Fuerza general','strength',40,'en','technique'],
  ['dance-cardio','Baile y coordinación','cardio',45,'en','class'],
  ['balance-demo','Equilibrio con apoyo','balance',null,'es','technique'],
].map(([id,title_es,modality,duration_minutes,language,format])=>({id,title_es,description_es:`Recurso general: ${title_es}.`,modality,modalities:[modality],duration_minutes,language,format,
  publisher:'NHS',creator:'InstructorLive',source_url:`https://www.nhs.uk/live-well/exercise/${id}/`,equipment:[{name_es:'Silla estable',requirement:'optional'}],equipment_complete:false,
  media_mode:'external_link',embed_url:null,clinical_approval:false,can_activate_plans:false,duration_note_es:null,source_notes_es:[]}));
const payload=(classes=fixture)=>({status:'external_original_classes',classes:clone(classes),count:classes.length,clinical_approval:false,can_activate_plans:false});
const response=(data=payload(),status=200)=>({ok:status>=200&&status<300,status,json:async()=>clone(data)});
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const settle=async()=>{for(let i=0;i<30;i++)await Promise.resolve();};
function harness(intercept){
  const calls=[],childCalls=[],preferences=[],roots=[];
  class Root {
    constructor(){this._html='';this.events={};this.children=[];roots.push(this);}
    set innerHTML(value){this._html=String(value);this.children=[];this.child=null;}
    get innerHTML(){return this._html;}
    replaceChildren(){this.innerHTML='';}
    addEventListener(name,fn){(this.events[name]||=new Set()).add(fn);}
    removeEventListener(name,fn){this.events[name]?.delete(fn);}
    contains(node){return node?.parent===this;}
    querySelector(selector){
      if(selector==='#fdExisting'&&this.innerHTML.includes('id="fdExisting"'))return this.child||=(new Root());
      if(selector==='h3'||selector==='.fd-result'||selector.startsWith('[data-fd-modality='))return {focus(){},scrollIntoView(){}};
      return null;
    }
    dispatch(name,target){
      const event={target,defaultPrevented:false,propagationStopped:false,preventDefault(){this.defaultPrevented=true;},stopPropagation(){this.propagationStopped=true;}};
      for(const fn of [...(this.events[name]||[])])fn(event);
      return event;
    }
    async click(dataset){
      const target={dataset,parent:this,closest(selector){return selector==='button'?this:null;}};
      const event=this.dispatch('click',target);await settle();return event;
    }
    async submit(values={},id='fdFilters'){
      const target={id,values,parent:this};const event=this.dispatch('submit',target);await settle();return event;
    }
  }
  const context={URL,AbortController,TypeError,FormData:class {constructor(target){this.values=target.values;}get(key){return this.values[key]??null;}},
    fetch:async(path,opts)=>{calls.push({path,...opts});const replacement=intercept?.(calls.length,path,opts);return replacement===undefined?response():await replacement;},
    RoxyFitnessLibrary:{mount:(node)=>childCalls.push({kind:'movements',node}),clear:()=>childCalls.push({kind:'clear-movements'})},
    RoxyFitnessPrograms:{mount:(node,options)=>childCalls.push({kind:'guides',node,options}),clear:()=>childCalls.push({kind:'clear-guides'})},
  };context.window=context;vm.runInNewContext(source,context);
  const root=new Root();
  return {api:context.RoxyFitnessDiscovery,root,calls,childCalls,preferences,roots,newRoot:()=>new Root(),
    async mount(node=root,options={}){context.RoxyFitnessDiscovery.mount(node,{identity:'member-a',timezone:'America/New_York',onPreferences:()=>preferences.push(true),...options});await settle();}};
}

test('verified external source URLs exclude scripts, impostor domains, credentials and tracking',()=>{
  assert.equal(api.safeSource(fixture[0].source_url),fixture[0].source_url);
  assert.equal(api.safeSource('https://www.mayoclinic.org/healthy-lifestyle/fitness/multimedia/squat/vid-20084663'),'https://www.mayoclinic.org/healthy-lifestyle/fitness/multimedia/squat/vid-20084663');
  for(const value of ['javascript:alert(1)','http://www.nhs.uk/live-well/exercise/yoga/','https://www.nhs.uk.evil.test/live-well/exercise/yoga/','https://evil.test/www.nhs.uk/live-well/exercise/','https://user:pass@www.nhs.uk/live-well/exercise/yoga/','https://www.nhs.uk:8443/live-well/exercise/yoga/','https://www.nhs.uk/live-well/exercise/yoga/?token=x','https://www.nhs.uk/live-well/exercise/yoga/#video','https://www.nhs.uk/conditions/','/live-well/exercise/yoga/'])assert.equal(api.safeSource(value),'',value);
});
test('the catalog accepts classes and technique demonstrations without implying active plans',()=>{
  assert.deepEqual(api.validate(payload()),fixture);
  assert.equal(api.validate(payload([])).length,0);
});
for(const [name,mutate] of [
  ['wrong status',p=>p.status='personalized_workout'],['wrong count',p=>p.count++],['duplicate IDs',p=>{p.classes.push(clone(p.classes[0]));p.count++;}],
  ['untrusted source',p=>p.classes[0].source_url='https://evil.test/video'],['unknown modality',p=>p.classes[0].modalities=['combat']],
  ['embedded media',p=>p.classes[0].embed_url='https://video.test/embed'],['autoplay mode',p=>p.classes[0].media_mode='autoplay'],
  ['entry clinical claim',p=>p.classes[0].clinical_approval=true],['entry plan claim',p=>p.classes[0].can_activate_plans=true],
  ['global clinical claim',p=>p.clinical_approval=true],['global plan claim',p=>p.can_activate_plans=true],
  ['missing global flag',p=>delete p.clinical_approval],['unknown video language',p=>p.classes[0].language='unknown'],
  ['invented duration',p=>p.classes[0].duration_minutes=-10],['fractional duration',p=>p.classes[0].duration_minutes=1.5],
  ['missing title',p=>delete p.classes[0].title_es],['invalid equipment item',p=>p.classes[0].equipment=[null]],
  ['unknown equipment requirement',p=>p.classes[0].equipment[0].requirement='maybe'],['non-text description',p=>p.classes[0].description_es={text:'Injected'}],
  ['unknown format',p=>p.classes[0].format='custom_plan'],['non-text duration note',p=>p.classes[0].duration_note_es={}],
  ['invalid source notes',p=>p.classes[0].source_notes_es='Not an array'],['non-text source note',p=>p.classes[0].source_notes_es=[null]],
])test(`invalid discovery metadata fails closed: ${name}`,()=>{const data=payload();mutate(data);assert.throws(()=>api.validate(data));});

test('modality, known duration and video language combine without inventing missing durations',()=>{
  assert.deepEqual(api.select(fixture,{modality:'yoga'}).map(e=>e.id),['chair-yoga']);
  assert.deepEqual(api.select(fixture,{minutes:'20'}).map(e=>e.id),['chair-yoga','easy-mobility']);
  assert.deepEqual(api.select(fixture,{minutes:'30',language:'es'}).map(e=>e.id),['pilates-flow','easy-mobility']);
  assert.deepEqual(api.select(fixture,{modality:'calisthenics',minutes:'60'}),[]);
  assert.equal(api.select(fixture,{modality:'calisthenics'})[0].duration_minutes,null);
});
test('cinematic yoga room initially combines yoga and Pilates without changing the underlying catalogue',async()=>{
  const h=harness();await h.mount(h.root,{initialModalities:['yoga','pilates']});
  assert.equal((h.root.innerHTML.match(/class="fd-class"/g)||[]).length,2);assert.match(h.root.innerHTML,/<h4>Yoga con silla<\/h4>/);assert.match(h.root.innerHTML,/<h4>Pilates de pie<\/h4>/);assert.doesNotMatch(h.root.innerHTML,/<h4>Fuerza general<\/h4>/);
  assert.match(h.root.innerHTML,/data-fd-modality="yoga" aria-pressed="true"/);assert.match(h.root.innerHTML,/data-fd-modality="pilates" aria-pressed="true"/);
  await h.root.submit({minutes:'20',language:'',query:''});assert.equal((h.root.innerHTML.match(/class="fd-class"/g)||[]).length,1);assert.equal(h.calls.length,1);
});
test('selecting a modality replaces the initial room filter and Todas restores access to all resources',async()=>{
  const h=harness();await h.mount(h.root,{initialModalities:['strength','calisthenics','unknown']});assert.equal((h.root.innerHTML.match(/class="fd-class"/g)||[]).length,2);
  await h.root.click({fdModality:'yoga'});assert.equal((h.root.innerHTML.match(/class="fd-class"/g)||[]).length,1);assert.match(h.root.innerHTML,/<h4>Yoga con silla<\/h4>/);
  await h.root.click({fdModality:''});assert.equal((h.root.innerHTML.match(/class="fd-class"/g)||[]).length,6);await h.root.click({fd:'more'});assert.equal((h.root.innerHTML.match(/class="fd-class"/g)||[]).length,7);assert.equal(h.calls.length,1);
});
test('search is accent-insensitive, uses every query word and preserves source order',()=>{
  assert.deepEqual(api.select(fixture,{query:'coordinacion baile'}).map(e=>e.id),['dance-cardio']);
  assert.deepEqual(api.select(fixture,{query:'  YOGA SILLA  '}).map(e=>e.id),['chair-yoga']);
  assert.equal(api.select(fixture,{query:'yoga fuerza'}).length,0);
});
test('cards escape all editorial text and explicitly label source video language and unknown duration',()=>{
  const row={...fixture[2],title_es:'<img src=x onerror=alert(1)>',description_es:'"<script>evil()</script>&',creator:"<b>'unsafe'</b>",equipment:[{name_es:'<iframe src=x>',requirement:'optional'}]};
  const html=api.card(row);
  assert.doesNotMatch(html,/<img|<script|<iframe|<b>/);
  assert.match(html,/&lt;img/);assert.match(html,/&lt;script&gt;/);assert.match(html,/&lt;iframe/);
  assert.match(html,/Duración sin confirmar/);assert.match(html,/Vídeo original en inglés/);assert.match(html,/Ver demostración original/);
  assert.match(html,/target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer"/);
  assert.match(api.card(fixture[1]),/Vídeo en español/);
});
test('duration uncertainty and source limitations remain visible and safely escaped',()=>{
  const row={...fixture[2],duration_note_es:'Duración no confirmada en <script>la fuente</script>.',source_notes_es:['Para quienes ya conocen lo básico <img src=x>.']};
  const html=api.card(row);assert.match(html,/Duración no confirmada en &lt;script&gt;la fuente&lt;\/script&gt;/);assert.match(html,/Para quienes ya conocen lo básico &lt;img src=x&gt;/);assert.doesNotMatch(html,/<script>|<img src=x/);
});
test('opening discovery performs one read with no third-party media requests or automatic tracking',async()=>{
  const h=harness();await h.mount();assert.equal(h.calls.length,1);
  assert.equal(h.calls[0].path,'/api/fitness/v1/classes');assert.equal(h.calls[0].credentials,'same-origin');assert.equal(h.calls[0].cache,'no-store');assert.equal(h.calls[0].headers.Accept,'application/json');
  assert.match(h.root.innerHTML,/Fichas ilustradas/);assert.match(h.root.innerHTML,/Guías paso a paso/);
  assert.doesNotMatch(h.root.innerHTML,/<iframe|<video|autoplay|calorías quemadas|rutina personalizada para ti/);
  assert.match(h.root.innerHTML,/Todavía no evalúa si un ejercicio es adecuado para tu edad, peso, capacidad o limitaciones/);
  assert.equal((h.root.innerHTML.match(/class="fd-class"/g)||[]).length,6);
  await h.root.click({fd:'more'});assert.equal((h.root.innerHTML.match(/class="fd-class"/g)||[]).length,7);assert.equal(h.calls.length,1);
});
test('filters update the collection locally, expose empty results and can be cleared',async()=>{
  const h=harness();await h.mount();await h.root.click({fdModality:'yoga'});
  assert.equal((h.root.innerHTML.match(/class="fd-class"/g)||[]).length,1);
  const e=await h.root.submit({minutes:'10',language:'es',query:''});assert.equal(e.defaultPrevented,true);assert.equal(e.propagationStopped,true);
  assert.match(h.root.innerHTML,/No hay recursos con esta combinación/);
  await h.root.click({fd:'reset'});assert.equal((h.root.innerHTML.match(/class="fd-class"/g)||[]).length,6);assert.equal(h.calls.length,1);
});
test('the search field escapes entered markup and remains a filter without sending profile data',async()=>{
  const h=harness();await h.mount();await h.root.submit({query:'\"><img src=x onerror=alert(1)>',minutes:'',language:''});
  assert.match(h.root.innerHTML,/&lt;img src=x onerror=alert\(1\)&gt;/);assert.doesNotMatch(h.root.innerHTML,/<img src=x/);assert.equal(h.calls.length,1);
});
for(const [name,status,expected] of [['unauthorized',401,/Inicia sesión/],['unavailable',503,/No pude cargar las clases/]])test(`${name} classes still permit existing library and Spanish guides`,async()=>{
  const h=harness(()=>response({},status));await h.mount();assert.match(h.root.innerHTML,expected);assert.match(h.root.innerHTML,/Volver a cargar las clases/);
  await h.root.click({fd:'movements'});assert.equal(h.childCalls.at(-1).kind,'movements');
  await h.root.click({fd:'explore'});assert.match(h.root.innerHTML,expected);
  const scheduleActivity=()=>{};h.api.clear();await h.mount(h.root,{scheduleActivity});await h.root.click({fd:'guides'});
  assert.equal(h.childCalls.at(-1).kind,'guides');assert.equal(h.childCalls.at(-1).options.identity,'member-a');assert.equal(h.childCalls.at(-1).options.timezone,'America/New_York');assert.equal(h.childCalls.at(-1).options.scheduleActivity,scheduleActivity);
});
test('transport errors are Spanish, recoverable and never display raw browser messages',async()=>{
  const h=harness(n=>n===1?Promise.reject(new TypeError('Failed to fetch')):undefined);await h.mount();
  assert.match(h.root.innerHTML,/Revisa tu conexión/);assert.doesNotMatch(h.root.innerHTML,/Failed to fetch/);
  await h.root.click({fd:'retry'});assert.equal(h.calls.length,2);assert.match(h.root.innerHTML,/7 recursos coinciden/);
});
test('invalid payloads cannot expose cards and retain access to existing source material',async()=>{
  const data=payload();data.classes[0].source_url='https://evil.test/';const h=harness(()=>response(data));await h.mount();
  assert.match(h.root.innerHTML,/No pude verificar las clases/);assert.doesNotMatch(h.root.innerHTML,/class="fd-class"/);assert.match(h.root.innerHTML,/Fichas ilustradas/);
});
test('clear aborts the pending read, clears content and prevents late responses restoring it',async()=>{
  const pending=deferred(),h=harness(()=>pending.promise);h.api.mount(h.root);await settle();assert.match(h.root.innerHTML,/Comprobando/);
  h.api.clear();assert.equal(h.calls[0].signal.aborted,true);assert.equal(h.root.innerHTML,'');
  pending.resolve(response());await settle();assert.equal(h.root.innerHTML,'');
  assert.equal(h.root.events.click?.size||0,0);assert.equal(h.root.events.submit?.size||0,0);
});
test('moving to a new root detaches the old listeners and ignores its late read',async()=>{
  const pending=deferred(),h=harness(n=>n===1?pending.promise:undefined);h.api.mount(h.root);await settle();
  const next=h.newRoot();await h.mount(next);assert.equal(h.calls[0].signal.aborted,true);
  assert.equal(h.root.events.click?.size||0,0);assert.equal(h.root.events.submit?.size||0,0);
  pending.resolve(response(payload([fixture[0]])));await settle();assert.match(next.innerHTML,/7 recursos coinciden/);
  await h.root.click({fd:'preferences'});assert.equal(h.preferences.length,0);
});
test('remounting and clearing the same root preserve a single active listener per event',async()=>{
  const h=harness();await h.mount();await h.mount();assert.equal(h.calls.length,1);
  h.api.clear();await h.mount();await h.root.click({fd:'preferences'});assert.equal(h.preferences.length,1);
  assert.equal(h.root.events.click.size,1);assert.equal(h.root.events.submit.size,1);
});
test('nested source forms and unrelated buttons remain owned by their child module',async()=>{
  const h=harness();await h.mount();await h.root.click({fd:'guides'});const before=h.root.innerHTML;
  const event=await h.root.submit({query:'Discard me'},'fxpArrangeForm');assert.equal(event.defaultPrevented,false);assert.equal(event.propagationStopped,false);assert.equal(h.root.innerHTML,before);
  await h.root.click({fxp:'next'});assert.equal(h.root.innerHTML,before);assert.equal(h.preferences.length,0);
});
test('discovery filters have no age/weight inference, persistence, training activation or substituted speech',()=>{
  assert.doesNotMatch(source,/localStorage|sessionStorage|indexedDB|speechSynthesis|\/plans\/preview|method\s*:\s*['"](?:POST|PUT|PATCH|DELETE)/);
  assert.doesNotMatch(source,/filters\.(?:age|weight|bmi|sex)/);
});
