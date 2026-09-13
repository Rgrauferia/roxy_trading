import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const code = fs.readFileSync(new URL('../assets/roxy_recipe_onboarding.js', import.meta.url),'utf8');
class Target {
  constructor() { this.listeners = new Map(); }
  addEventListener(key,fn) { if (!this.listeners.has(key)) this.listeners.set(key,new Set()); this.listeners.get(key).add(fn); }
  removeEventListener(key,fn) { this.listeners.get(key)?.delete(fn); }
  fire(key,event={}) { for (const fn of [...this.listeners.get(key) || []]) fn({target:this,preventDefault(){},...event}); }
}
class Element extends Target {
  constructor(tag,doc) { super(); this.tagName=tag; this.ownerDocument=doc; this.children=[]; this.parentNode=null; this.attributes={}; this.value=''; this.checked=false; this.disabled=false; this.hidden=false; this._text=''; }
  append(...nodes) { nodes.forEach(node => { node.remove(); node.parentNode=this; this.children.push(node); }); }
  replaceChildren(...nodes) { this.children.forEach(node => { node.parentNode=null; }); this.children=[]; this._text=''; this.append(...nodes); }
  remove() { if (this.parentNode) this.parentNode.children=this.parentNode.children.filter(node=>node!==this); this.parentNode=null; }
  get textContent() { return this._text+this.children.map(node=>node.textContent).join(''); }
  set textContent(value) { this.replaceChildren(); this._text=String(value); }
  setAttribute(key,value) { this.attributes[key]=String(value); }
  getAttribute(key) { return this.attributes[key]; }
  get isConnected() { return this.isRoot || Boolean(this.parentNode?.isConnected); }
  closest(selector) { if (selector==='[hidden]') return this.hidden?this:this.parentNode?.closest(selector); }
  querySelectorAll(selector) { const tags=selector.split(',').map(value=>value.trim()); return descendants(this).filter(node=>tags.includes(node.tagName)); }
  focus() { this.ownerDocument.activeElement=this; }
  click() { if (!this.disabled) this.fire('click'); }
}
function descendants(node) { return node.children.flatMap(child=>[child,...descendants(child)]); }
function find(root,tag,value) { const node=descendants(root).find(item=>item.tagName===tag&&item.textContent===value); assert.ok(node,`Missing ${tag} ${value}`); return node; }
const field=(root,name)=>descendants(root).find(node=>node.tagName==='input'&&(node.name===name||node.name.endsWith(`-${name}`)));
const error=root=>descendants(root).find(node=>node.className==='rco-error');
const choose=(root,key,value,checked=true)=>{ const node=descendants(root).find(item=>item.tagName==='input'&&item.name.endsWith(`-${key}`)&&item.value===value); assert.ok(node,`Missing choice ${key} ${value}`); node.checked=checked; node.fire('change'); return node; };
const input=(root,name,value)=>{ const node=field(root,name); assert.ok(node,`Missing input ${name}`); node.value=value; node.fire('input'); };
const settle=async()=>{ for(let index=0;index<12;index++) await Promise.resolve(); };
const deferred=()=>{ let resolve,reject; const promise=new Promise((a,b)=>{resolve=a;reject=b;}); return {promise,resolve,reject}; };
const baseProfile=()=>({schema_version:1,completed:true,consent:true,language:'es',country_of_origin:'Perú',cuisine_mode:'selected',cuisines:['peruvian'],diet:'omnivore',favorite_foods:['rice'],allergy_status:'listed',allergies:['milk'],other_allergies:'',dislikes:['cilantro'],max_minutes:30,skill:'beginner'});
const envelope=profile=>({member_id:'member-a',revision:0,required:true,profile:profile||null,options:{}});
function harness() {
  let now=0,timerId=0; const timers=new Map(),observers=[],speechCalls=[],forbidden=[];
  const document=new Target(); document.hidden=false; document.createElement=tag=>new Element(tag,document); document.body=document.createElement('body'); document.body.isRoot=true; document.documentElement=document.body;
  const window=new Target(); window.document=document;
  window.MutationObserver=class {constructor(fn){this.fn=fn;this.active=false;observers.push(this);}observe(){this.active=true;}disconnect(){this.active=false;}};
  window.SpeechSynthesisUtterance=class {constructor(text){this.text=text;}};
  const voices=[{name:'Local Spanish',lang:'es-US',localService:true},{name:'Local English',lang:'en-GB',localService:true}];
  window.speechSynthesis={getVoices:()=>voices,speak:utterance=>speechCalls.push({type:'speak',utterance}),cancel:()=>speechCalls.push({type:'cancel'})};
  const deny=name=>{forbidden.push(name);throw new Error(`Unexpected ${name}`);};
  vm.runInNewContext(code,{window,AbortController,setTimeout(fn,delay){const id=++timerId;timers.set(id,{fn,due:now+delay});return id;},clearTimeout(id){timers.delete(id);},fetch(){deny('fetch');},localStorage:{getItem(){deny('storage');},setItem(){deny('storage');}},sessionStorage:{getItem(){deny('session');},setItem(){deny('session');}},indexedDB:{open(){deny('database');}}});
  const container=document.createElement('div'); document.body.append(container);
  const calls=[],saved=[],cancelled=[];
  const defaults={profile:envelope(),identity:'household-a:member-a',isCurrent:()=>true,required:true,displayName:'Alex',api:async(path,options)=>{calls.push({path,options});const body=options.body?JSON.parse(options.body):{};return {...envelope(body.profile),revision:options.method==='PUT'?body.expected_revision+1:0};},onSaved:value=>saved.push(value),onCancel:()=>cancelled.push(true)};
  const mount=options=>window.RoxyRecipeOnboarding.render(container,{...defaults,...options});
  const tick=async(ms)=>{const until=now+ms; for(;;){const next=[...timers].filter(([,v])=>v.due<=until).sort((a,b)=>a[1].due-b[1].due)[0];if(!next)break;const[id,item]=next;timers.delete(id);now=item.due;item.fn();await settle();}now=until;await settle();};
  return {container,document,window,calls,saved,cancelled,forbidden,speechCalls,voices,timers,mount,tick,defaults,mutation:()=>observers.filter(item=>item.active).forEach(item=>item.fn())};
}
function complete(h,{language='es',consent=true}={}) {
  const root=h.container,next=language==='es'?'Continuar':'Continue'; choose(root,'language',language);choose(root,'cuisine_mode','mixed');find(root,'button',next).click();
  choose(root,'diet','undisclosed');choose(root,'allergy_status','undisclosed');find(root,'button',next).click();choose(root,'skill','undisclosed');find(root,'button',next).click();
  if(consent){field(root,'consent').checked=true;field(root,'consent').fire('change');}
}

test('first account starts with unanswered choices, no automatic API, storage or voice',async()=>{
  const h=harness();h.mount();await h.tick(60000);
  assert.equal(h.calls.length,0);assert.deepEqual(h.speechCalls,[]);assert.deepEqual(h.forbidden,[]);
  assert.equal(descendants(h.container).filter(node=>node.tagName==='input'&&node.checked).length,0);
  assert.ok(h.container.textContent.includes('Hola, Alex.'));assert.equal(descendants(h.container).some(node=>node.textContent==='Cancelar'),false);
  find(h.container,'button','Continuar').click();assert.match(error(h.container).textContent,/español o inglés/);
});
test('country does not select a cuisine or language; origin requires explicit country',()=>{
  const h=harness();h.mount();input(h.container,'country_of_origin','Japón');find(h.container,'button','Continuar').click();assert.match(error(h.container).textContent,/español o inglés/);
  choose(h.container,'language','es');find(h.container,'button','Continuar').click();assert.match(error(h.container).textContent,/explorar/);
  input(h.container,'country_of_origin','');choose(h.container,'cuisine_mode','origin');find(h.container,'button','Continuar').click();assert.match(error(h.container).textContent,/país o región/);
  choose(h.container,'cuisine_mode','selected');find(h.container,'button','Continuar').click();assert.match(error(h.container).textContent,/al menos una cocina/);
});
test('English retexts all four steps, review, consent and API without changing global app language',async()=>{
  const h=harness();h.mount();complete(h,{language:'en'});
  assert.match(h.container.textContent,/Your starting point/);assert.match(h.container.textContent,/Prefer not to say/);assert.equal(h.document.documentElement.lang,undefined);
  find(h.container,'button','Save and discover recipes').click();await settle();
  assert.equal(h.calls.length,1);assert.equal(h.calls[0].path,'/v1/home-account/recipe-profile');const request=h.calls[0].options;
  assert.equal(request.method,'PUT');assert.ok(request.signal instanceof AbortSignal);assert.equal(typeof request.body,'string');const body=JSON.parse(request.body);assert.equal(body.member_id,'member-a');assert.equal(body.expected_revision,0);
  assert.equal(body.profile.language,'en');assert.equal(body.profile.allergy_status,'undisclosed');assert.deepEqual([...body.profile.allergies],[]);assert.equal(body.profile.diet,'undisclosed');assert.equal(body.profile.skill,'undisclosed');assert.equal(body.profile.max_minutes,null);assert.equal(body.profile.completed,true);assert.equal(h.saved.length,1);assert.equal(h.container.children.length,0);
});
test('privacy consent is unchecked and required even when editing a previously consented profile',async()=>{
  const h=harness();h.mount({profile:envelope(baseProfile()),required:false});find(h.container,'button','Continuar').click();find(h.container,'button','Continuar').click();find(h.container,'button','Continuar').click();
  assert.equal(field(h.container,'consent').checked,false);find(h.container,'button','Guardar cambios').click();await settle();assert.equal(h.calls.length,0);assert.match(error(h.container).textContent,/Confirma/);
});
test('back navigation and changing language preserve every entered answer',()=>{
  const h=harness();h.mount();choose(h.container,'language','es');input(h.container,'country_of_origin','México');choose(h.container,'cuisine_mode','selected');choose(h.container,'cuisines','mexican');find(h.container,'button','Continuar').click();choose(h.container,'diet','vegan');input(h.container,'dislikes','cilantro');choose(h.container,'allergy_status','listed');choose(h.container,'allergies','other');input(h.container,'other_allergies','Aguacate');find(h.container,'button','Atrás').click();
  assert.equal(field(h.container,'country_of_origin').value,'México');choose(h.container,'language','en');find(h.container,'button','Continue').click();assert.equal(field(h.container,'dislikes').value,'cilantro');assert.equal(field(h.container,'other_allergies').value,'Aguacate');assert.equal(choose(h.container,'diet','vegan').checked,true);
});
test('allergies never default to none; listed and other require details',()=>{
  const h=harness();h.mount();choose(h.container,'language','es');choose(h.container,'cuisine_mode','mixed');find(h.container,'button','Continuar').click();choose(h.container,'diet','omnivore');find(h.container,'button','Continuar').click();assert.match(error(h.container).textContent,/alergias/);
  choose(h.container,'allergy_status','listed');find(h.container,'button','Continuar').click();assert.match(error(h.container).textContent,/al menos una alergia/);choose(h.container,'allergies','other');find(h.container,'button','Continuar').click();assert.match(error(h.container).textContent,/otra alergia/);
});
test('undisclosed removes formerly listed allergies from the saved body and review',async()=>{
  const h=harness();h.mount({profile:envelope(baseProfile())});find(h.container,'button','Continuar').click();choose(h.container,'allergy_status','undisclosed');find(h.container,'button','Continuar').click();find(h.container,'button','Continuar').click();
  assert.equal(h.container.textContent.includes('Leche'),false);field(h.container,'consent').checked=true;field(h.container,'consent').fire('change');find(h.container,'button','Guardar cambios').click();await settle();const body=JSON.parse(h.calls[0].options.body);assert.deepEqual(body.profile.allergies,[]);assert.equal(body.profile.other_allergies,'');
});
test('cancel editing makes no mutation and preserves the supplied profile byte-for-byte',()=>{
  const h=harness(),source=envelope(baseProfile()),before=JSON.stringify(source);h.mount({profile:source,required:false});input(h.container,'country_of_origin','Cuba');find(h.container,'button','Cancelar').click();assert.equal(JSON.stringify(source),before);assert.equal(h.calls.length,0);assert.equal(h.cancelled.length,1);assert.equal(h.container.children.length,0);
});
test('time and dislike validation do not silently truncate or coerce data',()=>{
  const h=harness();h.mount({profile:envelope(baseProfile())});find(h.container,'button','Continuar').click();input(h.container,'dislikes','a'.repeat(61));find(h.container,'button','Continuar').click();assert.match(error(h.container).textContent,/60 caracteres/);input(h.container,'dislikes','');find(h.container,'button','Continuar').click();input(h.container,'max_minutes','4');find(h.container,'button','Continuar').click();assert.match(error(h.container).textContent,/5 y 240/);input(h.container,'max_minutes','30.5');find(h.container,'button','Continuar').click();assert.match(error(h.container).textContent,/5 y 240/);
});
test('double submit sends only one PUT and disables editing during save',async()=>{
  const h=harness(),pending=deferred();let count=0;h.mount({api:()=>{count++;return pending.promise;}});complete(h);const save=find(h.container,'button','Guardar y descubrir recetas');save.click();save.click();await settle();assert.equal(count,1);assert.equal(field(h.container,'consent').disabled,true);pending.resolve({...envelope(baseProfile()),revision:1});await settle();assert.equal(h.saved.length,1);
});
for(const change of ['dispose','identity','ancestor','detach','remount'])test(`late save cannot affect another account or closed view after ${change}`,async()=>{
  const h=harness(),pending=deferred();let current=true,signal;const controller=h.mount({isCurrent:()=>current,api:(path,options)=>{signal=options.signal;return pending.promise;}});complete(h);find(h.container,'button','Guardar y descubrir recetas').click();await settle();
  if(change==='dispose')controller.dispose();if(change==='identity')current=false;if(change==='ancestor')h.container.hidden=true;if(change==='detach')h.container.remove();if(change==='remount')h.mount({profile:{...envelope(),member_id:'member-b'},identity:'household-a:member-b'});h.mutation();
  assert.equal(signal.aborted,true);pending.resolve({...envelope(baseProfile()),revision:1});await settle();assert.equal(h.saved.length,0);assert.equal(h.cancelled.length,0);
});
test('dispose before request dispatch prevents even the injected API call',async()=>{
  const h=harness(),controller=h.mount();complete(h);find(h.container,'button','Guardar y descubrir recetas').click();controller.dispose();await settle();assert.equal(h.calls.length,0);assert.equal(h.saved.length,0);
});
test('timeout aborts and reports uncertain save; late success never claims completion',async()=>{
  const h=harness(),pending=deferred();let signal;h.mount({api:(path,options)=>{signal=options.signal;return pending.promise;}});complete(h);find(h.container,'button','Guardar y descubrir recetas').click();await settle();await h.tick(12000);assert.equal(signal.aborted,true);assert.match(error(h.container).textContent,/confirmar el guardado/);assert.equal(field(h.container,'consent').checked,true);assert.ok(find(h.container,'button','Descartar cambios y cargar el perfil guardado'));
  pending.resolve({...envelope(baseProfile()),revision:1});await settle();assert.equal(h.saved.length,0);
});
for(const mode of ['other-member','unchanged-revision','incomplete'])test(`save response validation rejects ${mode}`,async()=>{
  const h=harness();const response={...envelope(baseProfile()),revision:1};if(mode==='other-member')response.member_id='member-b';if(mode==='unchanged-revision')response.revision=0;if(mode==='incomplete')response.profile.completed=false;
  h.mount({api:async()=>response});complete(h);find(h.container,'button','Guardar y descubrir recetas').click();await settle();assert.equal(h.saved.length,0);assert.match(error(h.container).textContent,/sesión cambió/);
});
test('409 offers explicit reload; no background overwrite and retry uses returned revision',async()=>{
  const h=harness(),calls=[];h.mount({api:async(path,options)=>{calls.push(options);if(calls.length===1){const error=new Error('conflict');error.status=409;throw error;}if(options.method==='GET')return{...envelope(baseProfile()),revision:3};return{...envelope(JSON.parse(options.body).profile),revision:4};}});complete(h);find(h.container,'button','Guardar y descubrir recetas').click();await settle();assert.equal(calls.length,1);assert.match(error(h.container).textContent,/otra sesión/);
  find(h.container,'button','Descartar cambios y cargar el perfil guardado').click();await settle();assert.equal(calls[1].method,'GET');assert.equal(field(h.container,'country_of_origin').value,'Perú');find(h.container,'button','Continuar').click();find(h.container,'button','Continuar').click();find(h.container,'button','Continuar').click();assert.equal(field(h.container,'consent').checked,false);field(h.container,'consent').checked=true;field(h.container,'consent').fire('change');find(h.container,'button','Guardar cambios').click();await settle();assert.equal(JSON.parse(calls[2].body).expected_revision,3);assert.equal(h.saved.length,1);
});
test('voice is explicit, local, language-matched and cancelled on navigation/language/disposal',()=>{
  const h=harness(),controller=h.mount();choose(h.container,'language','es');find(h.container,'button','Escuchar a Roxy').click();assert.equal(h.speechCalls[0].utterance.lang,'es');assert.equal(h.speechCalls[0].utterance.voice.localService,true);choose(h.container,'language','en');assert.equal(h.speechCalls.at(-1).type,'cancel');assert.equal(h.speechCalls.filter(call=>call.type==='speak').length,1);find(h.container,'button','Listen to Roxy').click();assert.equal(h.speechCalls.at(-1).utterance.lang,'en');controller.dispose();assert.equal(h.speechCalls.at(-1).type,'cancel');assert.equal(h.timers.size,0);
});
test('a remote or wrong-language voice is never used as a fallback',()=>{
  const h=harness();h.voices.splice(0,h.voices.length,{lang:'es-US',localService:false},{lang:'en-US',localService:true});h.mount();choose(h.container,'language','es');find(h.container,'button','Escuchar a Roxy').click();assert.equal(h.speechCalls.length,0);assert.match(h.container.textContent,/no hay una voz local/);
});
test('document hiding cancels owned speech and aborts pending save without claiming success',async()=>{
  const h=harness(),pending=deferred();let signal;h.mount({api:(path,options)=>{signal=options.signal;return pending.promise;}});complete(h);find(h.container,'button','Guardar y descubrir recetas').click();await settle();h.document.hidden=true;h.document.fire('visibilitychange');await settle();assert.equal(signal.aborted,true);pending.resolve({...envelope(baseProfile()),revision:1});await settle();assert.equal(h.saved.length,0);
});
test('profile text is rendered as text, without HTML injection',()=>{
  const h=harness(),profile=baseProfile();profile.country_of_origin='<img src=x>';h.mount({profile:envelope(profile),displayName:'<script>hi</script>'});assert.equal(descendants(h.container).some(node=>node.tagName==='script'),false);assert.ok(h.container.textContent.includes('<script>hi</script>'));
});
