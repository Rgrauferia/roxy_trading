// Focused 214 controller tests. Fixtures keep the 213 reader contract unchanged.
'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),{webcrypto}=require('node:crypto');
const api=require('../assets/roxy_fitness_training.js');
const source=fs.readFileSync(require.resolve('../assets/roxy_fitness_training.js'),'utf8');
const PREFIX='/api/fitness/v1/me/training-logs',CATALOG='/api/fitness/v1/training/programs';
const A='11111111-1111-4111-8111-111111111111',B='22222222-2222-4222-8222-222222222222';
const clone=x=>JSON.parse(JSON.stringify(x));
const consent={purpose:'fitness_training_logs',text_version:'fitness-training-logs-v1',granted:true,recorded_at:'2026-09-01T00:00:00Z'};
const exercise=(extra={})=>({id:'chair-sit-stand',name:'Levántate de la silla',phase:'work',instructions:['Apoya los pies.','Levántate con control.','Vuelve despacio.'],cue:'Controla la bajada.',dose:{label:'1 serie · 5 repeticiones',basis:'source',note:''},tracking_unit:'reps',equipment:['chair'],capabilities:['standing'],source_links:[],rest:{mode:'manual',suggested_seconds:null,label:'Descansa a tu ritmo.'},load:null,load_recordable:false,...extra});
const program=()=>({id:'home-bodyweight-foundations',title:'Fuerza en casa',summary:'Una sesión de movimientos con apoyo.',modality:'strength',level:'beginner',locations:['home'],requirements:{equipment:['chair'],capabilities:['standing'],equipment_complete:true},estimated_minutes:{min:20,max:30,kind:'editorial_estimate',assumptions:['Los descansos son manuales.']},exercise_count:2,content_version:'home-training-213-v1',scope:'Iniciación con apoyo.',source_links:[{title:'Ejercicios de fuerza',url:'https://www.nhs.uk/live-well/exercise/strength-exercises/'}],before_start:['Revisa tu espacio.'],exercises:[exercise({id:'walking-warmup',name:'Entra en movimiento',phase:'warmup',tracking_unit:'seconds'}),exercise(),exercise({id:'dumbbell-curl',name:'Curl con mancuerna',load_recordable:true}),exercise({id:'walking-cooldown',name:'Baja el ritmo',phase:'cooldown',tracking_unit:'seconds'})]});
const catalogue=()=>({content_version:'home-training-213-v1',content_digest:'a'.repeat(64),editorial_source_audit:true,clinical_approval:false,programs:[program()]});
const session=(extra={})=>({id:A,program_id:program().id,date:'2026-09-01',time:'08:00',starts_at:'2026-09-01T12:00:00Z',status:'planned',content_version:program().content_version,...extra});
const proposed=(status='ready')=>({profile_version:2,activity_plan_version:3,proposal:{status,program_id:program().id,title:program().title,content_version:program().content_version,timezone:'America/New_York',sessions:status==='ready'?[session()]:[],excluded_days:[{date:'2026-09-02',message_es:'Ya tienes una actividad en ese horario.'}],notice_es:status==='ready'?'Encontré un espacio.':'No hay espacio en esta semana.'}});
const log=(extra={})=>({session_id:A,program_id:program().id,content_version:program().content_version,performed_on:'2026-09-01',timezone:'America/New_York',duration_minutes:null,exercises:[{exercise_id:'chair-sit-stand',skipped:false,sets:[{reps:5,seconds:null,load:null}]},{exercise_id:'dumbbell-curl',skipped:true,sets:[]}],...extra});
const stored=value=>({...clone(value),exercises:value.exercises.map(ex=>({...clone(ex),sets:ex.sets.map(set=>({...clone(set),load_kg:set.load?Number((set.load.value*(set.load.unit==='lb'?.45359237:1)).toFixed(6)):null}))})),scheduled_date:'2026-09-01',scheduled_time:'08:00',scheduled_timezone:'America/New_York',recorded_at:'2026-09-01T13:00:00Z',updated_at:'2026-09-01T13:00:00Z'});
const empty=()=>({version:0,logs:[],consent:null,updated_at:null,eligible:true,eligibility_reason:null});
const saved=(logs=[stored(log())],version=1)=>({...empty(),version,consent:clone(consent),logs,updated_at:'2026-09-01T13:00:00Z'});
const response=(data,status=200)=>({ok:status>=200&&status<300,status,json:async()=>clone(data)});
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
const flush=async()=>{for(let i=0;i<50;i++)await Promise.resolve();};
const descendants=node=>node.children.flatMap(child=>[child,...descendants(child)]);
const all=(node,tag)=>descendants(node).filter(child=>child.tagName===tag.toUpperCase());
const byClass=(node,name)=>descendants(node).filter(child=>(child.className||'').split(' ').includes(name));
const button=(node,label)=>all(node,'button').find(child=>child.textContent===label);
const field=(node,label)=>descendants(node).find(child=>child.getAttribute('aria-label')===label);
function harness(initial=empty(),intercept){
  let server=clone(initial),id=0;const calls=[],events={},downloads=[],timers=new Map(),revoked=[];
  class Node{
    constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.attrs={};this.events={};this._text='';this.value='';}
    get textContent(){return this._text+this.children.map(n=>n.textContent).join('');}set textContent(v){this._text=String(v);this.replaceChildren();}
    get isConnected(){return this.root||Boolean(this.parent?.isConnected);}
    append(...nodes){nodes.forEach(n=>{n.parent=this;this.children.push(n);});}
    replaceChildren(...nodes){this.children.forEach(n=>n.parent=null);this.children=[];this.append(...nodes);}
    setAttribute(k,v){this.attrs[k]=String(v);}getAttribute(k){return this.attrs[k]??null;}
    addEventListener(k,fn){(this.events[k]||=[]).push(fn);}
    querySelector(selector){return selector.startsWith('.')?byClass(this,selector.slice(1))[0]:all(this,selector)[0];}
    querySelectorAll(selector){return selector.split(',').flatMap(tag=>all(this,tag));}
    focus(){this.focused=true;}
    async emit(name){for(const fn of this.events[name]||[])fn({target:this,preventDefault(){},stopPropagation(){}});await flush();}
    async click(){if(this.disabled)return;if(this.tagName==='A'){downloads.push(this);return;}await this.emit('click');}
  }
  const body=new Node('body');body.root=true;const root=new Node('div');body.append(root);
  const doc={hidden:false,createElement:tag=>new Node(tag),addEventListener:(name,fn)=>events[name]=fn};
  const context={document:doc,Intl,Date,Map,Set,AbortController,Blob,crypto:webcrypto,
    URL:class extends URL{static createObjectURL(){return 'blob:training';}static revokeObjectURL(url){revoked.push(url);}},
    setTimeout(fn){const token=++id;timers.set(token,fn);return token;},clearTimeout(token){timers.delete(token);},addEventListener:(name,fn)=>events[name]=fn,
    fetch:async(path,options)=>{
      calls.push({path,...options,payload:options.body?JSON.parse(options.body):undefined});
      assert.equal(options.credentials,'same-origin');assert.equal(options.cache,'no-store');assert.ok(options.headers['X-Roxy-Fitness-Member']);
      const override=intercept?.(path,options,calls.length);if(override!==undefined)return await override;
      if(path===CATALOG)return response(catalogue());
      if(path.startsWith(CATALOG+'/'))return response(program());
      if(path==='/api/fitness/v1/me/training/preview')return response(proposed());
      if(path===PREFIX+'/export')return response({format:'roxy-home-fitness-training-logs-v1',scope:'authenticated_member_only',exported_at:'2026-09-01T00:00:00Z',data:server});
      if(options.method==='GET')return response(server);
      assert.equal(options.headers['X-Roxy-Fitness-Request'],'1');assert.match(options.headers['Idempotency-Key'],/^[a-f\d-]{36}$/i);
      const data=JSON.parse(options.body);assert.equal(data.expected_version,server.version);
      if(path.endsWith('/consent'))server={...server,version:server.version+1,consent:clone(consent)};
      else if(options.method==='PUT'){const value=stored(data.log);server={...server,version:server.version+1,logs:[...server.logs.filter(item=>item.session_id!==value.session_id),value]};}
      else if(options.method==='DELETE'&&path!==PREFIX){assert.equal(data.confirm_delete,true);server={...server,version:server.version+1,logs:server.logs.filter(item=>!path.endsWith('/'+item.session_id))};}
      else if(options.method==='DELETE'){assert.equal(data.confirm_delete,true);server={...empty(),version:server.version+1};}
      return response(server);
    }};context.window=context;vm.runInNewContext(source,context);
  return {api:context.RoxyFitnessTrainingSession,browse:context.RoxyFitnessTraining,root,body,calls,events,downloads,timers,revoked,document:doc,get server(){return clone(server);},newRoot(){const node=new Node('div');body.append(node);return node;},async mount(options={}){context.RoxyFitnessTrainingSession.mount(root,{identity:'member-a',timezone:'America/New_York',session:session(),...options});await flush();},async mountBrowse(options={}){context.RoxyFitnessTraining.mount(root,{identity:'member-a',timezone:'America/New_York',...options});await flush();},async visibility(hidden){doc.hidden=hidden;events.visibilitychange();await flush();}};
}
async function change(h,label,value,event='input'){const node=field(h.root,label);assert.ok(node,label);node.value=value;await node.emit(event);}
async function check(h,label,value=true){const node=field(h.root,label);assert.ok(node,label);node.checked=value;await node.emit('change');}
async function openWork(h){await button(h.root,'Siguiente movimiento →').click();}
async function fillSession(h){await openWork(h);await change(h,'Repeticiones · serie 1','5');await button(h.root,'Siguiente movimiento →').click();await check(h,'Omití Curl con mancuerna');await button(h.root,'Revisar y guardar sesión').click();}
async function approve(h){await check(h,'Autorizo guardar mis registros de entrenamiento');}

const reference=(extra={})=>({session_id:A,program_id:program().id,content_version:program().content_version,logs_version:1,...extra});
const COPY='Usar este registro como punto de partida';
const CHAIR_TARGET='Objetivo de repeticiones · Levántate de la silla · serie 1';
function previewEcho(path,options){if(!path.endsWith('/training/preview'))return undefined;const data=JSON.parse(options.body),out=proposed();if(data.training_targets)out.proposal.sessions.forEach(row=>row.training_targets=clone(data.training_targets));return response(out);}
async function requirements(h){await check(h,'Silla estable, sin ruedas ni brazos');await check(h,'Puedo permanecer de pie y caminar con control');}

test('target normalization accepts omitted nullable fields and preserves content order and units',()=>{
  const targets=api.trainingTargets(program(),[{exercise_id:'dumbbell-curl',sets:[{reps:7,load:{value:10,unit:'lb'}}]},{exercise_id:'chair-sit-stand',sets:[{reps:5}]}]);
  assert.deepEqual(targets,[{exercise_id:'chair-sit-stand',sets:[{reps:5,seconds:null,load:null}]},{exercise_id:'dumbbell-curl',sets:[{reps:7,seconds:null,load:{value:10,unit:'lb'}}]}]);
  assert.equal(api.trainingTargets(program(),undefined),null);assert.equal(api.trainingTargets(program(),null),null);
  for(const bad of [[],[{exercise_id:'walking-warmup',sets:[{seconds:10}]}],[{exercise_id:'chair-sit-stand',sets:[{seconds:10}]}],[{exercise_id:'chair-sit-stand',sets:[{reps:5,load:{value:1,unit:'kg'}}]}],[{exercise_id:'chair-sit-stand',sets:[{reps:5,load_kg:1}]}],[{exercise_id:'chair-sit-stand',sets:Array(21).fill({reps:5})}]])assert.throws(()=>api.trainingTargets(program(),bad));
});
test('projecting records excludes skipped movements and never copies normalized loads or mutates the record',()=>{
  const saved=stored(log({exercises:[{exercise_id:'chair-sit-stand',skipped:true,sets:[]},{exercise_id:'dumbbell-curl',skipped:false,sets:[{reps:9,seconds:null,load:{value:11,unit:'lb'}}]}]})),before=clone(saved),targets=api.targetsFromLog(program(),saved);
  assert.deepEqual(targets,[{exercise_id:'dumbbell-curl',sets:[{reps:9,seconds:null,load:{value:11,unit:'lb'}}]}]);assert.deepEqual(saved,before);
  assert.throws(()=>api.targetsFromLog(program(),{...saved,content_version:'older-v0'}));
  const bad=clone(saved);bad.exercises[1].exercise_id='not-in-program';assert.throws(()=>api.targetsFromLog(program(),bad));
});
test('targets draft starts empty unless a person explicitly supplies a saved reference',()=>{
  const p=program(),draft=api.makeTargetsDraft(p);assert.equal(draft.every(ex=>!ex.enabled&&ex.sets[0].value===''&&ex.sets[0].load===''),true);assert.throws(()=>api.draftTargets(p,draft));
  const copied=api.makeTargetsDraft(p,api.targetsFromLog(p,stored(log())));assert.equal(copied[0].sets[0].value,'5');assert.equal(copied[1].enabled,false);assert.equal(copied[1].sets[0].value,'');copied[0].sets[0].value='6';assert.equal(api.draftTargets(p,copied)[0].sets[0].reps,6);
});
test('repeat opens the authorized record without selecting targets or confirming equipment',async()=>{
  const h=harness(saved());let consumed=0;await h.mountBrowse({repeatSource:reference(),onRepeatConsumed:()=>consumed++});assert.equal(consumed,1);assert.match(h.root.textContent,/Tu siguiente capítulo/);assert.match(h.root.textContent,/Serie 1: 5 repeticiones/);assert.equal(field(h.root,COPY).checked,false);assert.equal(field(h.root,CHAIR_TARGET),undefined);assert.equal(field(h.root,'Silla estable, sin ruedas ni brazos').checked,false);assert.equal(h.calls.filter(c=>c.path===PREFIX).length,1);assert.equal(h.calls.every(c=>c.method==='GET'),true);
  await button(h.root,'Buscar un horario para mí').click();assert.match(h.root.textContent,/Confirma el material/);assert.equal(h.calls.every(c=>c.method==='GET'),true);
});
test('a repeat without the copy choice schedules without objectives and asserts the exact source version',async()=>{
  const h=harness(saved(),previewEcho);let result=null;await h.mountBrowse({repeatSource:reference(),onSchedule:value=>result=value});await requirements(h);await button(h.root,'Buscar un horario para mí').click();const call=h.calls.at(-1);assert.equal(call.payload.source_session_id,A);assert.equal(call.payload.expected_logs_version,1);assert.equal(call.payload.training_targets,undefined);assert.equal(h.calls.filter(c=>c.method==='PUT').length,0);await button(h.root,'Revisar en mi plan').click();assert.equal(result.proposal.sessions[0].training_targets,undefined);
});
test('copying and editing changes chosen targets only, with blank extra sets and explicit skipped movements',async()=>{
  const h=harness(saved(),previewEcho);await h.mountBrowse({repeatSource:reference()});await check(h,COPY);assert.equal(field(h.root,CHAIR_TARGET).value,'5');assert.equal(field(h.root,'Elegir objetivo · Curl con mancuerna').checked,false);assert.equal(field(h.root,'Carga elegida · Curl con mancuerna · serie 1'),undefined);
  await change(h,CHAIR_TARGET,'6');await field(h.root,'Añadir objetivo · Levántate de la silla').click();assert.equal(field(h.root,'Objetivo de repeticiones · Levántate de la silla · serie 2').value,'');await change(h,'Objetivo de repeticiones · Levántate de la silla · serie 2','4');await requirements(h);await button(h.root,'Buscar un horario para mí').click();assert.deepEqual(h.calls.at(-1).payload.training_targets,[{exercise_id:'chair-sit-stand',sets:[{reps:6,seconds:null,load:null},{reps:4,seconds:null,load:null}]}]);assert.equal(h.server.logs[0].exercises[0].sets[0].reps,5);assert.equal(h.calls.filter(c=>c.method==='PUT').length,0);
});
test('target change after preview removes the handoff and requires a new preview',async()=>{
  const h=harness(saved(),previewEcho);await h.mountBrowse({repeatSource:reference()});await check(h,COPY);await requirements(h);await button(h.root,'Buscar un horario para mí').click();assert.ok(button(h.root,'Revisar en mi plan'));await change(h,CHAIR_TARGET,'7');assert.equal(button(h.root,'Revisar en mi plan'),undefined);await button(h.root,'Buscar un horario para mí').click();assert.equal(h.calls.at(-1).payload.training_targets[0].sets[0].reps,7);assert.ok(button(h.root,'Revisar en mi plan'));await check(h,COPY,false);assert.equal(field(h.root,CHAIR_TARGET),undefined);assert.equal(button(h.root,'Revisar en mi plan'),undefined);await button(h.root,'Buscar un horario para mí').click();assert.equal(h.calls.at(-1).payload.training_targets,undefined);
});
test('invalid, empty, or omitted objective inputs block a preview without writing',async()=>{
  const h=harness(saved(),previewEcho);await h.mountBrowse({repeatSource:reference()});await check(h,COPY);await requirements(h);
  for(const value of ['','0','1.5','Infinity','10001']){await change(h,CHAIR_TARGET,value);await button(h.root,'Buscar un horario para mí').click();assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);}
  await change(h,CHAIR_TARGET,'5');await check(h,'Elegir objetivo · Levántate de la silla',false);await button(h.root,'Buscar un horario para mí').click();assert.match(h.root.textContent,/Elige al menos un ejercicio/);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
});
test('missing server objectives cannot be passed off as a saved or verified proposal',async()=>{
  const h=harness(saved());await h.mountBrowse({repeatSource:reference()});await check(h,COPY);await requirements(h);await button(h.root,'Buscar un horario para mí').click();assert.match(h.root.textContent,/No pude confirmar tus objetivos/);assert.equal(button(h.root,'Revisar en mi plan'),undefined);
});
test('stale, unavailable, or mismatched source records never display the private reference',async()=>{
  for(const [snapshot,ref] of [[saved([],2),reference()],[saved(),reference({logs_version:2})],[saved(),reference({session_id:B})],[saved(),reference({content_version:'old-v0'})],[saved([stored(log({program_id:'another-program'}))]),reference()]]){const h=harness(snapshot);await h.mountBrowse({repeatSource:ref});assert.equal(field(h.root,COPY),undefined);assert.equal(field(h.root,CHAIR_TARGET),undefined);assert.doesNotMatch(h.root.textContent,/Tu registro del/);assert.equal(h.calls.every(c=>c.method==='GET'),true);assert.ok(button(h.root,'Volver a cargar rutinas'));}
});
test('malformed handoffs are consumed without requesting member data',async()=>{
  for(const ref of [reference({session_id:'bad'}),reference({logs_version:-1}),reference({logs_version:1.5}),reference({logs_version:Number.MAX_SAFE_INTEGER+1})]){const h=harness(saved());let count=0;await h.mountBrowse({repeatSource:ref,onRepeatConsumed:()=>count++});assert.equal(count,1);assert.equal(h.calls.length,0);assert.match(h.root.textContent,/Vuelve a elegir/);}
});
test('hidden tabs and identity changes clear both reference and edited targets',async()=>{
  const h=harness(saved(),previewEcho);await h.mountBrowse({repeatSource:reference()});await check(h,COPY);await change(h,CHAIR_TARGET,'777');await h.visibility(true);assert.equal(h.root.textContent,'');await h.visibility(false);assert.equal(field(h.root,COPY),undefined);assert.equal(field(h.root,CHAIR_TARGET),undefined);assert.doesNotMatch(h.root.textContent,/777/);assert.equal(h.calls.filter(c=>c.path===PREFIX).length,1);
  await h.mountBrowse({repeatSource:reference()});await check(h,COPY);const next=h.newRoot();h.browse.mount(next,{identity:'member-b',timezone:'UTC'});await flush();assert.equal(h.root.textContent,'');assert.equal(field(next,COPY),undefined);assert.equal(h.calls.at(-1).headers['X-Roxy-Fitness-Member'],'member-b');
});
test('an in-flight previous record cannot restore a hidden repeat workflow',async()=>{
  const waiting=deferred(),h=harness(saved(),path=>path===PREFIX?waiting.promise:undefined);await h.mountBrowse({repeatSource:reference()});assert.equal(h.calls.filter(c=>c.path===PREFIX).length,1);await h.visibility(true);waiting.resolve(response(saved()));await flush();assert.equal(h.root.textContent,'');assert.equal(h.calls.find(c=>c.path===PREFIX).signal.aborted,true);await h.visibility(false);assert.equal(field(h.root,COPY),undefined);assert.equal(h.calls.filter(c=>c.path===PREFIX).length,1);
});
test('conflicting preview discards old reference and forces fresh selection',async()=>{
  const h=harness(saved(),path=>path.endsWith('/training/preview')?response({detail:'changed'},409):undefined);await h.mountBrowse({repeatSource:reference()});await check(h,COPY);await requirements(h);await button(h.root,'Buscar un horario para mí').click();assert.match(h.root.textContent,/cambiaron en otra sesión/);assert.equal(field(h.root,COPY),undefined);assert.equal(field(h.root,CHAIR_TARGET),undefined);assert.ok(button(h.root,'Volver a cargar rutinas'));assert.equal(button(h.root,'Revisar en mi plan'),undefined);
});
test('a new routine can use explicit manual objectives without reading previous logs',async()=>{
  const h=harness(empty(),previewEcho);await h.mountBrowse();await button(h.root,'Explorar rutina').click();const label='Elegir mis objetivos para esta sesión';assert.equal(field(h.root,label).checked,false);await check(h,label);assert.equal(field(h.root,'Elegir objetivo · Levántate de la silla').checked,false);await check(h,'Elegir objetivo · Levántate de la silla');assert.equal(field(h.root,CHAIR_TARGET).value,'');await change(h,CHAIR_TARGET,'3');await requirements(h);await button(h.root,'Buscar un horario para mí').click();assert.equal(h.calls.at(-1).payload.training_targets[0].sets[0].reps,3);assert.equal(h.calls.at(-1).payload.source_session_id,undefined);assert.equal(h.calls.filter(c=>c.path===PREFIX).length,0);
});
test('reader shows chosen references separately while actual series still start empty',async()=>{
  const targets=[{exercise_id:'chair-sit-stand',sets:[{reps:8}]}],h=harness();await h.mount({session:session({training_targets:targets})});await openWork(h);assert.match(h.root.textContent,/Tu objetivo elegido/);assert.match(h.root.textContent,/Serie 1: 8 repeticiones/);assert.equal(field(h.root,'Repeticiones · serie 1').value,'');assert.equal(h.calls.every(c=>c.method==='GET'),true);await change(h,'Repeticiones · serie 1','4');assert.match(h.root.textContent,/Serie 1: 8 repeticiones/);assert.equal(h.server.logs.length,0);
});
test('changed chosen references remount independently from the actual record draft',async()=>{
  const h=harness();await h.mount({session:session({training_targets:[{exercise_id:'chair-sit-stand',sets:[{reps:8}]}]})});await openWork(h);await change(h,'Repeticiones · serie 1','777');await h.mount({session:session({training_targets:[{exercise_id:'chair-sit-stand',sets:[{reps:6}]}]})});await openWork(h);assert.match(h.root.textContent,/Serie 1: 6 repeticiones/);assert.equal(field(h.root,'Repeticiones · serie 1').value,'');
});
test('reader rejects invalid target metadata without filling actual result fields',async()=>{
  const h=harness();await h.mount({session:session({training_targets:[{exercise_id:'walking-warmup',sets:[{seconds:30}]}]})});assert.match(h.root.textContent,/Revisa los ejercicios/);assert.equal(field(h.root,'Repeticiones · serie 1'),undefined);assert.equal(button(h.root,'Marcar actividad completada'),undefined);
});
