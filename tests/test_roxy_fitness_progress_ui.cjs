'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const api=require('../assets/roxy_fitness_progress.js');
const source=fs.readFileSync(require.resolve('../assets/roxy_fitness_progress.js'),'utf8');
const PREFIX='/api/fitness/v1/me/training-progress',VERSION='home-training-213-v1';
const A='11111111-1111-4111-8111-111111111111',B='22222222-2222-4222-8222-222222222222';
const clone=value=>JSON.parse(JSON.stringify(value));
const empty=()=>({format:'roxy-home-training-progress-v1',logs_version:0,content_version:VERSION,updated_at:null,self_reported:true,clinical_approval:false,summary:{recorded_sessions:0,active_days:0,exercise_entries:0,performed_exercise_entries:0,skipped_exercise_entries:0,total_sets:0,first_performed_on:null,last_performed_on:null,duration:{reported_sessions:0,unreported_sessions:0,total_minutes:null}},workouts:[],exercises:[]});
const workout=(extra={})=>({session_id:A,program_id:'home-dumbbell-foundations',program_title:'Fuerza con mancuernas en casa',content_version:VERSION,performed_on:'2026-09-14',timezone:'America/New_York',duration_minutes:25,performed_exercises:1,skipped_exercises:0,set_count:1,can_repeat:true,...extra});
const entry=(extra={})=>({session_id:A,program_id:'home-dumbbell-foundations',program_title:'Fuerza con mancuernas en casa',performed_on:'2026-09-14',timezone:'America/New_York',skipped:false,sets:[{reps:12,seconds:null,load:{value:5,unit:'kg'},load_kg:5}],totals:{sets:1,reps:12,seconds:null},label:'Registro guardado',...extra});
const exercise=(extra={})=>({key:'squat|'+VERSION+'|reps',exercise_id:'squat',name:'Sentadilla con mancuerna',content_version:VERSION,tracking_unit:'reps',per_side:false,current_content_available:true,source_links:[],entry_count:1,performed_count:1,skipped_count:0,latest:entry(),previous:null,latest_day_entry_count:1,previous_day_entry_count:0,comparison_reason:'no_previous_day',comparison:null,history:[entry()],...extra});
function saved({two=false,skipped=false,archived=false}={}){
  const prior=entry({session_id:B,performed_on:'2026-09-10',sets:[{reps:10,seconds:null,load:{value:10,unit:'lb'},load_kg:4.535924}],totals:{sets:1,reps:10,seconds:null}});
  let latest=entry();if(skipped)latest=entry({skipped:true,sets:[],totals:{sets:0,reps:null,seconds:null}});
  const version=archived?'home-training-previous':VERSION;
  const workouts=[workout({content_version:version,can_repeat:!archived,performed_exercises:skipped?0:1,skipped_exercises:skipped?1:0,set_count:skipped?0:1})];if(two)workouts.push(workout({session_id:B,performed_on:'2026-09-10',duration_minutes:null,content_version:version,can_repeat:!archived}));
  const ex=exercise({content_version:version,key:'squat|'+version+'|reps',current_content_available:!archived,latest,previous:two?prior:null,history:two?[latest,prior]:[latest],entry_count:two?2:1,performed_count:(two?2:1)-(skipped?1:0),skipped_count:skipped?1:0,previous_day_entry_count:two?1:0,comparison_reason:two?(skipped?'skipped_entry':'compared'):'no_previous_day',comparison:two&&!skipped?{previous_session_id:B,set_count_delta:0,reps_delta:2,seconds_delta:null,load_kg_deltas:[0.464076],label:'Diferencia entre registros',interpretation:'descriptive_only'}:null});
  return {...empty(),logs_version:7,workouts,exercises:[ex],summary:{recorded_sessions:workouts.length,active_days:workouts.length,exercise_entries:workouts.length,performed_exercise_entries:ex.performed_count,skipped_exercise_entries:ex.skipped_count,total_sets:ex.performed_count,first_performed_on:two?'2026-09-10':'2026-09-14',last_performed_on:'2026-09-14',duration:{reported_sessions:1,unreported_sessions:two?1:0,total_minutes:25}}};
}
const response=(value,status=200)=>({ok:status>=200&&status<300,status,json:async()=>clone(value)});
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
const flush=async()=>{for(let i=0;i<35;i++)await Promise.resolve();};
const descendants=node=>node.children.flatMap(child=>[child,...descendants(child)]);
const all=(node,tag)=>descendants(node).filter(child=>child.tagName===tag.toUpperCase());
const byClass=(node,name)=>descendants(node).filter(child=>(child.className||'').split(' ').includes(name));
const button=(node,label)=>all(node,'button').find(child=>child.textContent===label);
function harness(initial=empty(),intercept){
  const calls=[],events={},timers=new Map();let id=0;
  class Node{
    constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.attrs={};this.events={};this._text='';this.value='';}
    get textContent(){return this._text+this.children.map(n=>n.textContent).join('');}set textContent(value){this._text=String(value);this.replaceChildren();}
    get isConnected(){return this.root||Boolean(this.parent?.isConnected);}
    append(...nodes){nodes.forEach(node=>{node.parent=this;this.children.push(node);});}
    replaceChildren(...nodes){this.children.forEach(node=>node.parent=null);this.children=[];this.append(...nodes);}
    setAttribute(key,value){this.attrs[key]=String(value);}getAttribute(key){return this.attrs[key]??null;}
    addEventListener(key,fn){(this.events[key]||=[]).push(fn);}
    querySelectorAll(selector){return selector.split(',').flatMap(tag=>all(this,tag));}
    async emit(name){for(const fn of this.events[name]||[])fn({target:this,preventDefault(){},stopPropagation(){}});await flush();}
    async click(){if(!this.disabled)await this.emit('click');}
  }
  const body=new Node('body');body.root=true;const root=new Node('div');body.append(root);
  const document={hidden:false,createElement:tag=>new Node(tag),addEventListener:(name,fn)=>events[name]=fn};
  const context={document,Intl,Date,Map,Set,AbortController,
    setTimeout(fn){const token=++id;timers.set(token,fn);return token;},clearTimeout(token){timers.delete(token);},addEventListener:(name,fn)=>events[name]=fn,
    fetch:async(path,options)=>{calls.push({path,...options});assert.equal(path,PREFIX);assert.equal(options.method,'GET');assert.equal(options.credentials,'same-origin');assert.equal(options.cache,'no-store');assert.ok(options.headers['X-Roxy-Fitness-Member']);const override=intercept?.(path,options,calls.length);return override===undefined?response(initial):await override;}};
  context.window=context;vm.runInNewContext(source,context);
  return {api:context.RoxyFitnessProgress,root,body,calls,events,timers,document,newRoot(){const node=new Node('div');body.append(node);return node;},async mount(options={}){context.RoxyFitnessProgress.mount(root,{identity:'member-a',timezone:'America/New_York',...options});await flush();},async visibility(hidden){document.hidden=hidden;events.visibilitychange();await flush();}};
}

test('empty journal presents actual zero records without simulated workouts or comparisons',async()=>{
  const h=harness();await h.mount();assert.match(h.root.textContent,/Mi evolución/);assert.match(h.root.textContent,/Aquí empieza tu historia/);assert.equal(byClass(h.root,'fxev-entry').length,0);assert.equal(byClass(h.root,'fxev-exercise').length,0);assert.equal(button(h.root,'Repetir rutina'),undefined);assert.equal(h.calls.length,1);
});
test('one workout preserves declared loads and says when a later date will enable comparison',async()=>{
  const h=harness(saved());await h.mount();assert.match(h.root.textContent,/25 min registrados/);assert.match(h.root.textContent,/Serie 1 · 12 repeticiones · 5 kg/);assert.match(h.root.textContent,/Cuando registres este ejercicio en otra fecha/);assert.equal(byClass(h.root,'fxev-comparison').length,0);assert.equal(all(h.root,'details')[0].open,undefined);
});
test('two dates show descriptive actual quantities and original units without prescribing progression',async()=>{
  const h=harness(saved({two:true}));await h.mount();assert.match(h.root.textContent,/Diferencia registrada: 0 series · \+2 repeticiones/);assert.match(h.root.textContent,/10 repeticiones · 10 lb/);assert.match(h.root.textContent,/12 repeticiones · 5 kg/);assert.doesNotMatch(h.root.textContent,/0 min registrados|kcal|calorías|puntaje|sube la carga/);assert.equal(byClass(h.root,'fxev-comparison').length,1);
});
test('skipped exercise is shown as omitted and never as zero performance',async()=>{
  const h=harness(saved({two:true,skipped:true}));await h.mount();assert.match(h.root.textContent,/Omitido/);assert.match(h.root.textContent,/Ejercicio omitido en esta sesión/);assert.doesNotMatch(h.root.textContent,/\b0 repeticiones|Diferencia registrada/);assert.match(h.root.textContent,/Uno de estos registros fue omitido/);
});
test('same-day multiple entries suppress a numeric progression claim',async()=>{
  const value=saved({two:true});value.exercises[0].comparison=null;value.exercises[0].comparison_reason='multiple_entries_on_day';value.exercises[0].latest_day_entry_count=2;const h=harness(value);await h.mount();assert.match(h.root.textContent,/Hay varios registros en una de estas fechas/);assert.doesNotMatch(h.root.textContent,/Diferencia registrada/);assert.equal(byClass(h.root,'fxev-comparison').length,0);
});
test('repeat sends stable session, program, content and log version only after explicit click',async()=>{
  const repeats=[],opened=[],h=harness(saved());await h.mount({onRepeat:payload=>repeats.push(clone(payload)),onOpenSession:id=>opened.push(id)});assert.equal(repeats.length,0);await button(h.root,'Repetir rutina').click();assert.deepEqual(repeats,[{session_id:A,program_id:'home-dumbbell-foundations',content_version:VERSION,logs_version:7}]);await button(h.root,'Ver registro').click();assert.deepEqual(opened,[A]);assert.equal(h.calls.length,1);
});
test('archived content remains readable but has no repeat action',async()=>{
  const h=harness(saved({archived:true}));await h.mount({onRepeat:()=>assert.fail('cannot repeat archived'),onOpenSession:()=>{}});assert.equal(button(h.root,'Repetir rutina'),undefined);assert.ok(button(h.root,'Ver registro'));assert.match(h.root.textContent,/versión anterior/);assert.match(h.root.textContent,/5 kg/);
});
test('version filter keeps recorded variants separate and never recalculates comparisons',async()=>{
  const value=saved({two:true});value.workouts[1].content_version='old';value.workouts[1].can_repeat=false;value.exercises[0]=exercise();const historical=exercise({key:'squat|old|reps',content_version:'old',current_content_available:false,latest:entry({session_id:B,performed_on:'2026-09-10'}),history:[entry({session_id:B,performed_on:'2026-09-10'})]});value.exercises.push(historical);const h=harness(value);await h.mount();const select=all(h.root,'select')[0];assert.ok(select);select.value='old';await select.emit('change');assert.equal(byClass(h.root,'fxev-entry').length,1);assert.equal(byClass(h.root,'fxev-exercise').length,1);assert.match(h.root.textContent,/versión anterior/);assert.equal(h.calls.length,1);
});
test('refresh resets a retired version filter when those records were removed elsewhere',async()=>{
  const value=saved({two:true});value.workouts[1].content_version='old';value.workouts[1].can_repeat=false;value.exercises=[];const h=harness(value,(_path,_options,count)=>count===2?response(saved()):undefined);await h.mount();const select=all(h.root,'select')[0];select.value='old';await select.emit('change');await button(h.root,'Actualizar').click();assert.equal(byClass(h.root,'fxev-entry').length,1);assert.match(h.root.textContent,/5 kg/);assert.equal(all(h.root,'select').length,0);
});
test('identity is required before any private request',async()=>{
  const h=harness(saved());await h.mount({identity:''});assert.equal(h.calls.length,0);assert.match(h.root.textContent,/Entra en tu perfil personal/);assert.equal(button(h.root,'Volver a cargar historial'),undefined);
});
test('authorization rejection on refresh removes displayed records and callbacks',async()=>{
  const h=harness(saved(),(_path,_options,count)=>count===2?response({detail:'private server content'},403):undefined);await h.mount({onRepeat:()=>{}});await button(h.root,'Actualizar').click();assert.match(h.root.textContent,/La sesión cambió/);assert.doesNotMatch(h.root.textContent,/5 kg|private server content/);assert.equal(button(h.root,'Repetir rutina'),undefined);
});
test('unavailable storage shows useful recovery without invented history',async()=>{
  const h=harness(empty(),()=>response({detail:'raw postgres internal'},503));await h.mount();assert.match(h.root.textContent,/historial privado todavía no está disponible/);assert.ok(button(h.root,'Volver a cargar historial'));assert.doesNotMatch(h.root.textContent,/raw postgres|sesión registrada/);
});
test('network timeout aborts and late data cannot replace the error state',async()=>{
  const pending=deferred(),h=harness(empty(),()=>pending.promise);h.api.mount(h.root,{identity:'member-a'});await flush();assert.equal(h.timers.size,1);[...h.timers.values()][0]();await flush();assert.equal(h.calls[0].signal.aborted,true);assert.match(h.root.textContent,/La conexión tardó demasiado/);pending.resolve(response(saved()));await flush();assert.doesNotMatch(h.root.textContent,/5 kg/);
});
test('hiding clears private DOM and revalidates on return',async()=>{
  const h=harness(saved());await h.mount();await h.visibility(true);assert.equal(h.root.textContent,'');await h.visibility(false);assert.equal(h.calls.length,2);assert.match(h.root.textContent,/5 kg/);
});
test('late response after hiding cannot repopulate or enable actions',async()=>{
  const pending=deferred(),h=harness(empty(),()=>pending.promise);h.api.mount(h.root,{identity:'member-a'});await flush();await h.visibility(true);pending.resolve(response(saved()));await flush();assert.equal(h.root.textContent,'');assert.equal(h.calls[0].signal.aborted,true);
});
test('switching members cancels the previous request and keeps data isolated',async()=>{
  const pending=deferred(),h=harness(empty(),(_path,options)=>options.headers['X-Roxy-Fitness-Member']==='member-a'?pending.promise:response(empty()));h.api.mount(h.root,{identity:'member-a'});await flush();h.api.mount(h.root,{identity:'member-b'});await flush();pending.resolve(response(saved()));await flush();assert.doesNotMatch(h.root.textContent,/5 kg/);assert.match(h.root.textContent,/Aquí empieza tu historia/);assert.equal(h.calls[0].signal.aborted,true);
});
test('leaving, remounting and pagehide remove the previous panel and invalidate old handlers',async()=>{
  let repeats=0;const h=harness(saved());await h.mount({onRepeat:()=>repeats++});const stale=button(h.root,'Repetir rutina');h.api.setActive(false);assert.equal(h.root.textContent,'');await stale.click();assert.equal(repeats,0);h.api.setActive(true);await flush();const next=h.newRoot();h.api.mount(next,{identity:'member-a'});await flush();assert.equal(h.root.textContent,'');assert.match(next.textContent,/5 kg/);h.events.pagehide();assert.equal(next.textContent,'');
});
test('untrusted payloads with false claims, duplicate sessions, invalid units or same-day comparison fail closed',()=>{
  for(const alter of [p=>p.self_reported=false,p=>p.clinical_approval=true,p=>p.summary.recorded_sessions=99,p=>p.workouts.push(clone(p.workouts[0])),p=>p.workouts[0].timezone='bad/zone',p=>p.exercises[0].latest.sets[0].load.unit='ton',p=>p.exercises[0].previous.performed_on=p.exercises[0].latest.performed_on,p=>p.exercises[0].comparison.interpretation='fitness_score',p=>p.exercises[0].history[0].sets[0].reps=Infinity]){const value=saved({two:true});alter(value);assert.throws(()=>api.snapshot(value));}
});
test('invalid returned payload never renders saved personal values',async()=>{
  const value=saved();value.exercises[0].history[0].sets[0].load.unit='bad';const h=harness(value);await h.mount();assert.match(h.root.textContent,/No pude verificar tu historial/);assert.doesNotMatch(h.root.textContent,/5 kg/);
});
test('reported seconds and per-side amounts remain amounts entered by the member',()=>{
  const timed=exercise({tracking_unit:'seconds',per_side:true}),record=entry({sets:[{reps:null,seconds:20,load:null,load_kg:null}],totals:{sets:1,reps:null,seconds:20}});assert.deepEqual(api.valueText(record,timed),{value:'20',unit:'segundos en total, ambos lados · 1 serie'});assert.equal(api.setText(record.sets[0],0,true),'Serie 1 · 20 segundos en total, ambos lados');assert.equal(api.setText({reps:10,seconds:null,load:null},1,false),'Serie 2 · 10 repeticiones');
});
test('missing reported duration stays null and does not become a zero-minute workout',async()=>{
  const value=saved();value.workouts[0].duration_minutes=null;value.summary.duration={reported_sessions:0,unreported_sessions:1,total_minutes:null};const h=harness(value);await h.mount();assert.match(h.root.textContent,/5 kg/);assert.doesNotMatch(h.root.textContent,/min registrados/);const bad=clone(value);bad.summary.duration.total_minutes=0;assert.throws(()=>api.snapshot(bad));
});
test('unknown historical side metadata remains readable without inventing a side convention',async()=>{
  const value=saved({archived:true});value.exercises[0].per_side=null;const h=harness(value);await h.mount();assert.match(h.root.textContent,/Serie 1 · 12 repeticiones · 5 kg/);assert.doesNotMatch(h.root.textContent,/por lado|ambos lados/);
});
test('historical omitted record with no known unit is readable and never assigned seconds',async()=>{
  const value=saved({skipped:true,archived:true});value.exercises[0].per_side=null;value.exercises[0].tracking_unit=null;const h=harness(value);await h.mount();assert.match(h.root.textContent,/Omitido/);assert.doesNotMatch(h.root.textContent,/0 segundos|No pude verificar/);
});
test('mixed historical units preserve each set without an invented combined performance amount',async()=>{
  const value=saved({two:true,archived:true}),ex=value.exercises[0];ex.tracking_unit=null;ex.per_side=null;ex.comparison_reason='unknown_tracking_unit';ex.comparison=null;for(const item of [ex.latest,ex.previous,...ex.history]){item.sets=[{reps:10,seconds:null,load:null,load_kg:null},{reps:null,seconds:20,load:null,load_kg:null}];item.totals={sets:2,reps:null,seconds:null};}const h=harness(value);await h.mount();assert.match(h.root.textContent,/Serie 1 · 10 repeticiones/);assert.match(h.root.textContent,/Serie 2 · 20 segundos/);assert.match(h.root.textContent,/no permite una comparación con la misma unidad/);assert.doesNotMatch(h.root.textContent,/Diferencia registrada/);
});
test('bilateral comparison labels never halve or double actual quantities',()=>{
  const value=saved({two:true}).exercises[0];value.per_side=true;assert.equal(api.valueText(value.latest,value).value,'12');assert.match(api.valueText(value.latest,value).unit,/en total, ambos lados/);assert.match(api.comparisonNote(value),/\+2 repeticiones en total, ambos lados/);assert.doesNotMatch(api.comparisonNote(value),/por lado/);
});
test('the journal only reads member data and never stores, broadcasts or prescribes it',()=>{
  assert.doesNotMatch(source,/localStorage|sessionStorage|indexedDB|console\.|\/calendar|\/agent|\/speech|speechSynthesis|sendBeacon|method:'(?:PUT|POST|DELETE)'/);assert.match(source,/cache:'no-store'/);assert.match(source,/'X-Roxy-Fitness-Member'/);assert.match(source,/prefers-reduced-motion|fxev-shell/);
});
