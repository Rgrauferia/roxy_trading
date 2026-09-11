'use strict';
// Synthetic DOM/network contracts, not clinical validation or user data.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const api = require('../assets/roxy_fitness_programs.js');
const source = fs.readFileSync(require.resolve('../assets/roxy_fitness_programs.js'), 'utf8');
const clone = value => JSON.parse(JSON.stringify(value));
const flags = {status:'education_only', active_training:false, can_activate_plans:false, clinical_approval:false, can_persist:false};
const full = ['strength','balance','flexibility'].map((name, index) => ({id:`gentle-${name}`, title_en:`Source ${name}`, title_es:`Guía ${name}`, exercise_count:2,
  source_version:'2026-09-01', checked_on:'2026-09-11', source_sha256:String(index + 1).repeat(64), frequency_en:'Original frequency.', frequency_es:'Frecuencia original.', duration_seconds:null,
  source_url:`https://www.nhs.uk/live-well/exercise/${name}-exercises/`, terms_url:'https://www.nhs.uk/our-policies/terms-and-conditions/', license_url:'https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/',
  intro_en:['Original introduction.', 'Original safety note.'], intro_es:['Introducción adaptada.', 'Aviso de la fuente adaptado.'], notes_es:['Nota de la adaptación.'], attribution_en:'NHS, source accessed 2026-09-11.', attribution_es:'Adaptación de Roxy, OGL3.',
  exercises:[{id:'first-movement',name_en:'First source movement',name_es:'Primer movimiento',instructions_en:['A. Exact source instruction.', 'Attempt 3 sets of 5 to 10 repetitions.'],instructions_es:['A. Instrucción de fuente adaptada.', 'Intenta 3 series de 5 a 10 repeticiones.']},{id:'second-movement',name_en:'Second source movement',name_es:'Segundo movimiento',instructions_en:['Keep the exact second movement.'],instructions_es:['Conserva el segundo movimiento exacto.']}]}));
const summaryKeys = ['id','title_en','title_es','exercise_count','source_version','checked_on','source_sha256','frequency_en','frequency_es','duration_seconds','source_url','terms_url','license_url'];
const summaries = programs => programs.map(row => Object.fromEntries(summaryKeys.map(key => [key, row[key]])));
const catalog = programs => ({...flags, programs:summaries(programs), total:programs.length});
const detail = program => ({...flags, program});
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => { resolve=a; reject=b; }); return {promise,resolve,reject}; };
const settle = async () => { for (let i=0;i<25;i++) await Promise.resolve(); };
const descendants = el => el.children.flatMap(child => [child,...descendants(child)]);
const all = (el, tag) => descendants(el).filter(child => child.tagName===tag.toUpperCase());
const classes = (el,name) => descendants(el).filter(child => String(child.className||'').split(/\s+/).includes(name));
const button = (el,label) => all(el,'button').find(child => child.textContent===label);
const attr = (el,name,value) => descendants(el).find(child => child.getAttribute(name)===value);
function harness(intercept) {
  const calls=[],listeners={},windowEvents={},downloads=[],blobs=[],writes=[],timers=new Map(); let timerId=0,now=0;
  class Element {
    constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.listeners={};this.attrs={};this.parent=null;this._text='';this.value='';}
    get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
    set textContent(value){this._text=String(value);this.children.forEach(child=>child.parent=null);this.children=[];}
    get isConnected(){return this.root||Boolean(this.parent?.isConnected);}
    append(...children){for(const child of children){child.parent=this;this.children.push(child);}}
    replaceChildren(...children){this.children.forEach(child=>child.parent=null);this.children=[];this._text='';this.append(...children);}
    setAttribute(key,value){this.attrs[key]=String(value);}
    getAttribute(key){return this.attrs[key]??null;}
    addEventListener(name,fn){(this.listeners[name]||=[]).push(fn);}
    querySelector(selector){return selector.startsWith('.')?classes(this,selector.slice(1))[0]:all(this,selector)[0];}
    async emit(name){for(const fn of this.listeners[name]||[])fn({target:this,preventDefault(){},stopPropagation(){}});await settle();}
    async click(){if(this.tagName==='A'){downloads.push({filename:this.download,href:this.href});return;}if(!this.disabled)await this.emit('click');}
    focus(){this.focused=true;}
    scrollIntoView(){}
  }
  const body=new Element('body');body.root=true;
  const document={hidden:false,createElement:tag=>new Element(tag),addEventListener:(name,fn)=>listeners[name]=fn};
  const NativeURL=URL; class TestURL extends NativeURL {static createObjectURL(blob){blobs.push(blob);return `blob:test-${blobs.length}`;}static revokeObjectURL(){}}
  const forbidden = name => {writes.push(name);throw new Error(name);};
  const context={document,URL:TestURL,Blob,Intl,Date,AbortController,Map,Set,crypto:{randomUUID:()=> '11111111-1111-4111-8111-111111111111'},
    setTimeout(fn,delay){const id=++timerId;timers.set(id,{fn,due:now+delay});return id;},clearTimeout:id=>timers.delete(id),
    localStorage:{getItem:()=>forbidden('local read'),setItem:()=>forbidden('local write')},sessionStorage:{getItem:()=>forbidden('session read'),setItem:()=>forbidden('session write')},indexedDB:{open:()=>forbidden('indexedDB')},
    addEventListener:(name,fn)=>windowEvents[name]=fn,
    fetch:async(path,options)=>{calls.push({path,options});assert.equal(options.credentials,'same-origin');assert.equal(options.cache,'no-store');assert.equal(options.method,undefined);assert.equal(options.body,undefined);assert.ok(options.signal instanceof AbortSignal);
      const overridden=intercept?.(calls.length,path,options);if(overridden!==undefined)return await overridden;
      if(path==='/api/fitness/v1/status')return {ok:true,status:200,json:async()=>({personal_login:true,member_id:'member-a'})};
      const program=full.find(row=>path.endsWith('/'+row.id));const payload=path==='/api/fitness/v1/programs'?catalog(full):detail(program);return {ok:true,status:200,json:async()=>clone(payload)};
    }};context.window=context;vm.runInNewContext(source,context);
  const container=()=>{const el=new Element('div');body.append(el);return el;};
  const root=container();
  const tick=async ms=>{const end=now+ms;for(;;){const entry=[...timers].filter(([,row])=>row.due<=end).sort((a,b)=>a[1].due-b[1].due)[0];if(!entry)break;const [id,row]=entry;timers.delete(id);now=row.due;row.fn();await settle();}now=end;await settle();};
  const visibility=async hidden=>{document.hidden=hidden;listeners.visibilitychange();await settle();};
  return {...context.RoxyFitnessPrograms,root,container,body,calls,downloads,blobs,writes,windowEvents,tick,visibility};
}
async function mounted(h,view='week'){h.mount(h.root,{identity:'member-a',timezone:'America/New_York',view});await settle();}
async function choose(h,index=0){await attr(h.root,'aria-label',`Ver programa: ${full[index].title_es}`).click();}
async function arrange(h,{start=api.todayInZone('America/New_York'),days=['fri']}={}){
  const date=attr(h.root,'aria-label','Fecha inicial');date.value=start;await date.emit('change');
  for(const key of days){const input=all(h.root,'input').find(node=>node.name==='agenda_day'&&node.value===key);input.checked=true;await input.emit('change');}
  await all(h.root,'form')[0].emit('submit');
}

test('dates respect timezone, DST, leap day and month boundaries without assigning defaults',()=>{
  assert.equal(api.todayInZone('America/New_York',new Date('2026-09-07T02:00:00Z')),'2026-09-06');
  assert.equal(api.todayInZone('Asia/Tokyo',new Date('2026-09-06T23:00:00Z')),'2026-09-07');
  const week=api.agendaDates('2028-02-28',['mon','wed']);assert.equal(week.length,7);assert.equal(week[1].date,'2028-02-29');assert.equal(week[6].date,'2028-03-05');assert.deepEqual(week.filter(d=>d.chosen).map(d=>d.key),['mon','wed']);
  assert.equal(api.agendaDates('2026-03-08',['sun']).at(-1).date,'2026-03-14');
  for(const [date,days] of [['2026-02-29',['mon']],['2026-09-31',['mon']],['2026-09-11',[]],['2026-09-11',['mon','mon']],['2026-09-11',['Friday']]])assert.throws(()=>api.agendaDates(date,days));
});
test('all-day ICS contains only chosen dates and generic private events, no health, alarm or calendar writes',()=>{
  const text=api.calendarText(api.agendaDates('2026-09-11',['fri','mon']),new Date('2026-09-11T12:00:00Z'),()=> 'synthetic-id');
  assert.equal((text.match(/BEGIN:VEVENT/g)||[]).length,2);assert.match(text,/DTSTART;VALUE=DATE:20260911\r\nDTEND;VALUE=DATE:20260912/);assert.match(text,/SUMMARY:Actividad personal/);assert.match(text,/CLASS:PRIVATE/);
  assert.doesNotMatch(text,/VALARM|ATTENDEE|LOCATION|DESCRIPTION|TZID|NHS|strength|calorie|weight|member-a/i);
  const bad=api.agendaDates('2026-09-11',['fri']);bad[1].date=bad[0].date;assert.throws(()=>api.calendarText(bad));
});
test('source catalogue and parallel complete EN/ES detail validate without changing source doses',()=>{
  const list=api.validateCatalog(catalog(full));const value=api.validateDetail(detail(full[0]),list[0]);assert.equal(value.exercises[0].instructions_en[1],'Attempt 3 sets of 5 to 10 repetitions.');
  const text=api.guideText(value,'en');assert.match(text,/Attempt 3 sets of 5 to 10 repetitions\./);assert.match(text,/NHS, source accessed/);assert.doesNotMatch(text,/Adaptación de Roxy/);assert.match(text,/open-government-licence/);assert.match(text,/Original safety note/);
  const es=api.guideText(value,'es');assert.match(es,/Adaptación de Roxy/);assert.doesNotMatch(es,/NHS, source accessed|Fuente: NHS/);assert.match(es,/Procedencia del original en inglés \(no autoría ni aval/);
});
for(const mutate of [p=>p.can_activate_plans=true,p=>p.clinical_approval=true,p=>p.active_training=true,p=>p.can_persist=true,p=>p.total=500,p=>p.programs.push(p.programs[0]),p=>p.programs[0].duration_seconds=1200,p=>p.programs[0].source_sha256='bad',p=>p.programs[0].license_url='https://evil.test/license',p=>p.programs[0].source_url='https://www.nhs.uk.evil.test/x'])test(`invalid catalogue fails closed: ${mutate}`,()=>{const payload=clone(catalog(full));mutate(payload);assert.throws(()=>api.validateCatalog(payload));});
for(const mutate of [p=>p.program.id='wrong-id',p=>p.program.source_sha256='f'.repeat(64),p=>p.program.exercises.pop(),p=>p.program.exercises[0].instructions_es.pop(),p=>p.program.intro_es=[],p=>p.program.exercises[0].instructions_en=['<script>bad</script>'],p=>p.program.source_url=full[1].source_url,p=>p.program.exercises[1].id=p.program.exercises[0].id,p=>p.program.attribution_es='',p=>p.can_activate_plans=true])test(`incomplete or mismatched details never organize: ${mutate}`,()=>{const payload=clone(detail(full[0]));mutate(payload);assert.throws(()=>api.validateDetail(payload,summaries(full)[0]));});
test('checked source data contract matches frontend and contains no fabricated media or durations',()=>{
  const data=JSON.parse(fs.readFileSync(require.resolve('../data/home_fitness_source_programs_192.json'),'utf8'));
  const programs=data.programs.map(row=>({...row,exercise_count:row.exercises.length}));const list=api.validateCatalog(catalog(programs));
  assert.equal(list.length,3);assert.equal(programs.reduce((count,p)=>count+p.exercise_count,0),16);
  for(let i=0;i<programs.length;i++)assert.ok(api.validateDetail(detail(programs[i]),list[i]));
});
test('gallery loads metadata only, details are explicit, days start unselected and no workout actions exist',async()=>{
  const h=harness();await mounted(h);assert.equal(h.calls.length,1);assert.equal(classes(h.root,'fxp-program-card').length,3);assert.equal(all(h.root,'form').length,0);
  await choose(h);assert.equal(h.calls.length,2);assert.equal(all(h.root,'input').filter(i=>i.name==='agenda_day'&&i.checked).length,0);assert.equal(classes(h.root,'fxp-date').length,0);
  assert.equal(attr(h.root,'aria-label','Fecha inicial').value,api.todayInZone('America/New_York'));assert.match(h.root.textContent,/Duración total no indicada/);assert.doesNotMatch(h.root.textContent,/Comenzar entrenamiento|Marcar como completado|calorías quemadas/);assert.equal(all(h.root,'img').length,0);assert.deepEqual(h.writes,[]);
});
test('the source guide is readable before choosing dates and language preserves current movement',async()=>{
  const h=harness();await mounted(h);await choose(h);await button(h.root,'Ver movimientos de la guía').click();assert.match(h.root.textContent,/Intenta 3 series de 5 a 10/);
  await button(h.root,'Movimiento siguiente').click();assert.match(h.root.textContent,/Movimiento 2 de 2/);await button(h.root,'Ver original en inglés').click();assert.match(h.root.textContent,/Movimiento 2 de 2/);assert.match(h.root.textContent,/Keep the exact second movement/);assert.match(h.root.textContent,/Original safety note/);assert.equal(h.calls.length,2);
});
test('Spanish cards and source attribution are separated from original English authorship in every reader view',async()=>{
  const h=harness();await mounted(h);assert.doesNotMatch(h.root.textContent,/fuente NHS/);await choose(h);await button(h.root,'Ver movimientos de la guía').click();
  let reader=classes(h.root,'fxp-reader')[0];assert.match(reader.textContent,/Adaptación de Roxy/);assert.doesNotMatch(reader.textContent,/NHS, source accessed/);assert.ok(all(reader,'a').some(a=>a.href===full[0].license_url));assert.match(reader.textContent,/2026-09-11/);
  await button(reader,'Movimiento siguiente').click();reader=classes(h.root,'fxp-reader')[0];assert.match(reader.textContent,/Adaptación de Roxy/);await button(reader,'Ver original en inglés').click();reader=classes(h.root,'fxp-reader')[0];assert.match(reader.textContent,/NHS, source accessed/);assert.doesNotMatch(reader.textContent,/Adaptación de Roxy/);assert.ok(all(reader,'a').some(a=>a.href===full[0].source_url));
});
test('organized agenda precedes collapsed configuration and introduction instead of hiding the day below forms',async()=>{
  const h=harness();await mounted(h);await choose(h);await arrange(h,{start:'2026-09-11',days:['fri']});const shell=classes(h.root,'fxp-shell')[0],agenda=classes(h.root,'fxp-agenda-root')[0],config=classes(h.root,'fxp-configuration')[0];
  assert.ok(shell.children.indexOf(agenda)<shell.children.indexOf(config));assert.notEqual(config.open,true);assert.notEqual(classes(config,'fxp-source-intro')[0].open,true);assert.match(agenda.textContent,/Si sientes dolor, detén el movimiento/);
});
test('explicit user dates create all seven days, including free days, without assuming dose, duration or progress',async()=>{
  const h=harness();await mounted(h);await choose(h);await arrange(h,{start:'2026-09-11',days:['fri','mon']});const dates=classes(h.root,'fxp-date');assert.equal(dates.length,7);
  assert.ok(attr(h.root,'aria-label','2026-09-12: sin actividad reservada'));assert.match(h.root.textContent,/Elegido por ti/);await dates[1].click();assert.match(h.root.textContent,/No reservaste una actividad/);
  await dates[0].click();await button(h.root,'Ver guía del día').click();assert.match(h.root.textContent,/Intenta 3 series de 5 a 10 repeticiones/);assert.equal(h.calls.length,2);assert.deepEqual(h.writes,[]);
});
test('empty selections and invalid timezone/date cannot produce agenda',async()=>{
  const h=harness();await mounted(h);await choose(h);await all(h.root,'form')[0].emit('submit');assert.equal(classes(h.root,'fxp-date').length,0);assert.match(h.root.textContent,/al menos un día/);
  const zone=attr(h.root,'aria-label','Zona horaria');zone.value='bad-zone';await zone.emit('input');await arrange(h);assert.equal(classes(h.root,'fxp-date').length,0);assert.match(h.root.textContent,/Revisa la zona horaria/);
});
test('changing form invalidates dated agenda and open guide, with no automatic regeneration',async()=>{
  const h=harness();await mounted(h);await choose(h);await arrange(h,{start:'2026-09-11',days:['fri']});await button(h.root,'Ver guía del día').click();const input=all(h.root,'input').find(row=>row.name==='agenda_day'&&row.value==='mon');input.checked=true;await input.emit('change');
  assert.equal(classes(h.root,'fxp-date').length,0);assert.equal(classes(h.root,'fxp-reader').length,0);assert.match(h.root.textContent,/Organiza de nuevo/);assert.equal(h.calls.length,2);
});
test('same identity transfers agenda across Hoy/Mi semana and Hoy selects today even when free',async()=>{
  const h=harness();await mounted(h);await choose(h);const today=api.todayInZone('America/New_York');const chosen=api.agendaDates(today,['mon']).find(day=>day.date!==today).key;await arrange(h,{start:today,days:[chosen]});
  const newRoot=h.container();h.mount(newRoot,{identity:'member-a',timezone:'America/New_York',view:'today'});assert.equal(classes(newRoot,'fxp-date').length,7);assert.match(classes(newRoot,'fxp-day-title')[0].textContent,new RegExp(today));assert.match(newRoot.textContent,/No reservaste una actividad/);assert.equal(h.calls.length,2);
});
test('same-view parent rerender preserves selected date and open reader position',async()=>{
  const h=harness();await mounted(h,'today');await choose(h);await arrange(h,{start:'2026-09-11',days:['fri']});await button(h.root,'Ver guía del día').click();await button(h.root,'Movimiento siguiente').click();
  const next=h.container();h.mount(next,{identity:'member-a',timezone:'America/New_York',view:'today'});assert.match(next.textContent,/Movimiento 2 de 2/);assert.equal(classes(next,'fxp-date').length,7);assert.equal(h.calls.length,2);
});
test('a read resolving between internal fitness tabs remains usable when the agenda root returns',async()=>{
  const pending=deferred(),h=harness(n=>n===2?pending.promise:undefined);await mounted(h);await choose(h);h.body.replaceChildren();
  pending.resolve({ok:true,json:async()=>detail(full[0])});await settle();const next=h.container();h.mount(next,{identity:'member-a',timezone:'America/New_York',view:'week'});assert.equal(all(next,'form').length,1);assert.equal(classes(next,'fxp-program-title')[0].textContent,full[0].title_es);assert.equal(h.calls.length,2);
});
test('downloads are explicit local files and TXT retains complete source with attribution',async()=>{
  const h=harness();await mounted(h);await choose(h);await arrange(h,{start:'2026-09-11',days:['fri','mon']});assert.equal(h.downloads.length,0);
  await button(h.root,'Descargar agenda .ics').click();await button(h.root,'Descargar guía TXT').click();assert.equal(h.downloads.length,2);assert.equal(h.calls.length,2);
  assert.match(await h.blobs[0].text(),/SUMMARY:Actividad personal/);const txt=await h.blobs[1].text();assert.match(txt,/Primer movimiento/);assert.match(txt,/Segundo movimiento/);assert.match(txt,/Adaptación de Roxy/);assert.match(txt,/open-government-licence/);assert.deepEqual(h.writes,[]);
});
test('rejected detail offers retry without hiding catalogue choices or creating agenda',async()=>{
  const h=harness(n=>n===2?{ok:false,status:503}:undefined);await mounted(h);await choose(h);assert.ok(button(h.root,'Reintentar esta guía'));assert.equal(classes(h.root,'fxp-program-card').length,3);assert.equal(all(h.root,'form').length,0);await button(h.root,'Reintentar esta guía').click();assert.equal(all(h.root,'form').length,1);
});
test('a source switch aborts old detail and ignores a transport that resolves late',async()=>{
  const pending=deferred(),h=harness(n=>n===2?pending.promise:undefined);await mounted(h);await choose(h);await choose(h,1);assert.equal(h.calls[1].options.signal.aborted,true);
  pending.resolve({ok:true,json:async()=>detail(full[0])});await settle();assert.equal(classes(h.root,'fxp-program-title')[0].textContent,full[1].title_es);assert.equal(h.calls.length,3);
});
for(const mode of ['exit','identity','clear'])test(`late detail cannot repopulate after ${mode}`,async()=>{
  const pending=deferred(),h=harness(n=>n===2?pending.promise:undefined);await mounted(h);await choose(h);
  if(mode==='exit')h.setActive(false);if(mode==='identity')h.mount(h.root,{identity:'member-b',timezone:'UTC'});if(mode==='clear')h.clear();await settle();
  pending.resolve({ok:true,json:async()=>detail(full[0])});await settle();assert.equal(h.calls[1].options.signal.aborted,true);assert.equal(classes(h.root,'fxp-program-title').length,0);assert.equal(classes(h.root,'fxp-date').length,0);
});
test('12-second timeout exposes retry and ignores late ignored-abort detail',async()=>{
  const pending=deferred(),h=harness(n=>n===2?pending.promise:undefined);await mounted(h);await choose(h);await h.tick(12000);assert.ok(button(h.root,'Reintentar esta guía'));assert.match(h.root.textContent,/tardó demasiado/);pending.resolve({ok:true,json:async()=>detail(full[0])});await settle();assert.equal(all(h.root,'form').length,0);
});
test('temporary hidden tab retains agenda but hides it until same-member revalidation',async()=>{
  const check=deferred(),h=harness((n,path)=>path.endsWith('/status')?check.promise:undefined);await mounted(h);await choose(h);await arrange(h,{start:'2026-09-11',days:['fri']});await h.visibility(true);assert.equal(h.root.textContent,'');await h.visibility(false);assert.equal(classes(h.root,'fxp-date').length,0);assert.match(h.root.textContent,/Comprobando la sesión/);
  check.resolve({ok:true,json:async()=>({personal_login:true,member_id:'member-a'})});await settle();assert.equal(classes(h.root,'fxp-date').length,7);assert.equal(h.calls.length,3);
});
test('hidden-tab identity mismatch purges agenda instead of showing previous choices',async()=>{
  const h=harness((n,path)=>path.endsWith('/status')?{ok:true,json:async()=>({personal_login:true,member_id:'member-b'})}:undefined);await mounted(h);await choose(h);await arrange(h);await h.visibility(true);await h.visibility(false);assert.equal(classes(h.root,'fxp-date').length,0);assert.match(h.root.textContent,/Cambió la persona/);
});
test('shared access can read guides but cannot restore an unbound hidden agenda',async()=>{
  const h=harness((n,path)=>path.endsWith('/status')?{ok:true,json:async()=>({personal_login:false,member_id:null})}:undefined);await mounted(h);await choose(h);await arrange(h);await h.visibility(true);await h.visibility(false);assert.equal(classes(h.root,'fxp-date').length,0);assert.equal(classes(h.root,'fxp-program-card').length,3);assert.equal(h.calls.length,4);
});
test('module exit and pagehide discard agenda; remount does not inherit previous day choices',async()=>{
  const h=harness();await mounted(h);await choose(h);await arrange(h);h.setActive(false);assert.equal(h.root.textContent,'');h.setActive(true);await settle();await choose(h);assert.equal(all(h.root,'input').filter(i=>i.name==='agenda_day'&&i.checked).length,0);h.windowEvents.pagehide();assert.equal(h.root.textContent,'');
});
