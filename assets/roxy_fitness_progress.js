/* A private, descriptive journal of the workouts the member actually recorded. */
((scope) => {
  'use strict';
  const PREFIX='/api/fitness/v1/me/training-progress';
  const FORMAT='roxy-home-training-progress-v1';
  const UUID=/^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/i;
  let state=null,active=true;
  const copy=value=>JSON.parse(JSON.stringify(value));
  const integer=value=>Number.isInteger(value)&&value>=0;
  const finite=value=>typeof value==='number'&&Number.isFinite(value)&&value>=0;
  const textOK=value=>typeof value==='string'&&value.length>0&&value.length<=500;
  const zoneOK=value=>{try{return typeof value==='string'&&value.length<=64&&!!new Intl.DateTimeFormat('es',{timeZone:value});}catch(_){return false;}};
  const dateOK=value=>{if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value))return false;const date=new Date(value+'T12:00:00Z');return Number.isFinite(date.getTime())&&date.toISOString().slice(0,10)===value;};
  const invalid=()=>new Error('No pude verificar tu historial de entrenamientos. Vuelve a cargarlo.');
  function entryOK(entry,unit,workouts){
    if(!entry||!UUID.test(entry.session_id)||!workouts.has(entry.session_id)||!textOK(entry.program_id)||!textOK(entry.program_title)||!dateOK(entry.performed_on)||!zoneOK(entry.timezone)||typeof entry.skipped!=='boolean'||!Array.isArray(entry.sets)||entry.sets.length>20)throw invalid();
    const workout=workouts.get(entry.session_id);
    if(entry.program_id!==workout.program_id||entry.performed_on!==workout.performed_on||entry.timezone!==workout.timezone)throw invalid();
    if(entry.skipped?entry.sets.length!==0:entry.sets.length===0)throw invalid();
    for(const set of entry.sets){
      if(!set)throw invalid();const reps=integer(set.reps)&&set.reps>0&&set.seconds===null,seconds=finite(set.seconds)&&set.seconds>0&&set.reps===null;
      if(!(unit==='reps'?reps:unit==='seconds'?seconds:reps||seconds))throw invalid();
      if(set.load!==null&&(!set.load||!finite(set.load.value)||!['kg','lb'].includes(set.load.unit)))throw invalid();
      if(set.load_kg!==null&&set.load_kg!==undefined&&!finite(set.load_kg))throw invalid();
    }
    if(!entry.totals||entry.totals.sets!==entry.sets.length)throw invalid();
    for(const key of ['reps','seconds'])if(entry.totals[key]!==null&&!finite(entry.totals[key]))throw invalid();
  }
  function snapshot(payload){
    if(!payload||payload.format!==FORMAT||!integer(payload.logs_version)||!textOK(payload.content_version)||payload.self_reported!==true||payload.clinical_approval!==false||!Array.isArray(payload.workouts)||payload.workouts.length>366||!Array.isArray(payload.exercises)||payload.exercises.length>36600||JSON.stringify(payload).length>16000000)throw invalid();
    const summary=payload.summary,workouts=new Map();
    if(!summary||!['recorded_sessions','active_days','exercise_entries','performed_exercise_entries','skipped_exercise_entries','total_sets'].every(key=>integer(summary[key]))||summary.recorded_sessions!==payload.workouts.length)throw invalid();
    if(summary.first_performed_on!==null&&!dateOK(summary.first_performed_on)||summary.last_performed_on!==null&&!dateOK(summary.last_performed_on))throw invalid();
    if(!summary.duration||!integer(summary.duration.reported_sessions)||!integer(summary.duration.unreported_sessions)||(summary.duration.reported_sessions===0?summary.duration.total_minutes!==null:!finite(summary.duration.total_minutes))||summary.duration.reported_sessions+summary.duration.unreported_sessions!==payload.workouts.length)throw invalid();
    for(const row of payload.workouts){
      if(!row||!UUID.test(row.session_id)||workouts.has(row.session_id)||!['program_id','program_title','content_version'].every(key=>textOK(row[key]))||!dateOK(row.performed_on)||!zoneOK(row.timezone)||(row.duration_minutes!==null&&!finite(row.duration_minutes))||!['performed_exercises','skipped_exercises','set_count'].every(key=>integer(row[key]))||typeof row.can_repeat!=='boolean')throw invalid();
      workouts.set(row.session_id,row);
    }
    const keys=new Set();
    for(const exercise of payload.exercises){
      if(!exercise||!['key','exercise_id','name','content_version'].every(key=>textOK(exercise[key]))||keys.has(exercise.key)||!['reps','seconds',null].includes(exercise.tracking_unit)||(exercise.per_side!==null&&typeof exercise.per_side!=='boolean')||typeof exercise.current_content_available!=='boolean'||!['entry_count','performed_count','skipped_count','latest_day_entry_count','previous_day_entry_count'].every(key=>integer(exercise[key]))||!Array.isArray(exercise.history)||exercise.history.length!==exercise.entry_count||exercise.entry_count<1||exercise.entry_count>366||exercise.performed_count+exercise.skipped_count!==exercise.entry_count)throw invalid();
      keys.add(exercise.key);const ids=new Set();
      for(const entry of exercise.history){entryOK(entry,exercise.tracking_unit,workouts);if(ids.has(entry.session_id))throw invalid();ids.add(entry.session_id);}
      if(!exercise.latest||!ids.has(exercise.latest.session_id))throw invalid();entryOK(exercise.latest,exercise.tracking_unit,workouts);
      if(exercise.previous!==null){if(!ids.has(exercise.previous.session_id))throw invalid();entryOK(exercise.previous,exercise.tracking_unit,workouts);if(exercise.previous.performed_on>=exercise.latest.performed_on)throw invalid();}
      if(!['no_previous_day','skipped_entry','multiple_entries_on_day','unknown_tracking_unit','compared'].includes(exercise.comparison_reason))throw invalid();
      if(exercise.comparison!==null){
        const comparison=exercise.comparison;
        if(exercise.comparison_reason!=='compared'||!exercise.previous||exercise.latest.skipped||exercise.previous.skipped||exercise.latest_day_entry_count!==1||exercise.previous_day_entry_count!==1||comparison.previous_session_id!==exercise.previous.session_id||comparison.interpretation!=='descriptive_only'||!Number.isInteger(comparison.set_count_delta)||!Array.isArray(comparison.load_kg_deltas)||comparison.load_kg_deltas.some(value=>value!==null&&(typeof value!=='number'||!Number.isFinite(value))))throw invalid();
        for(const key of ['reps_delta','seconds_delta'])if(comparison[key]!==null&&(typeof comparison[key]!=='number'||!Number.isFinite(comparison[key])))throw invalid();
      }else if(exercise.comparison_reason==='compared')throw invalid();
    }
    return copy(payload);
  }
  const format=value=>new Intl.NumberFormat('es',{maximumFractionDigits:2}).format(value);
  const dateLabel=date=>new Intl.DateTimeFormat('es',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(date+'T12:00:00Z'));
  const count=(value,singular,plural)=>`${format(value)} ${value===1?singular:plural}`;
  const signed=value=>`${value>0?'+':''}${format(value)}`;
  const el=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined&&text!==null)node.textContent=text;if(cls)node.className=cls;return node;};
  const btn=(text,fn,cls='fxev-button')=>{const node=el('button',text,cls);node.type='button';node.addEventListener('click',fn);return node;};
  const current=(owner,revision=owner.revision)=>state===owner&&active&&!document.hidden&&owner.revision===revision&&owner.root?.isConnected!==false;
  function cancel(owner){owner.controller?.abort();owner.controller=null;owner.revision++;owner.busy=false;}
  function clearPrivate(owner){cancel(owner);owner.saved=null;owner.loaded=false;owner.error='';owner.blocked=false;owner.filter='all';owner.visible=4;owner.exerciseVisible=6;owner.root.replaceChildren();}
  async function request(owner){
    const controller=new AbortController();owner.controller=controller;let timer;
    try{return await Promise.race([(async()=>{
      const response=await fetch(PREFIX,{method:'GET',headers:{Accept:'application/json','X-Roxy-Fitness-Member':owner.identity},credentials:'same-origin',cache:'no-store',signal:controller.signal});
      const data=await response.json().catch(()=>({}));
      if(!response.ok){const error=new Error('No pude cargar tu historial. Vuelve a intentarlo.');error.status=response.status;throw error;}return data;
    })(),new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(new Error('La conexión tardó demasiado. Vuelve a cargar tu historial.'));},12000);})]);}
    finally{clearTimeout(timer);if(owner.controller===controller)owner.controller=null;}
  }
  async function load(owner){
    if(!current(owner)||owner.busy)return;
    if(!owner.identity){owner.blocked=true;owner.error='Entra en tu perfil personal para consultar tu evolución.';draw(owner);return;}
    cancel(owner);const revision=owner.revision;owner.busy=true;owner.saved=null;owner.loaded=false;owner.error='';owner.blocked=false;draw(owner);
    try{const saved=snapshot(await request(owner));if(!current(owner,revision))return;if(owner.filter!=='all'&&!saved.workouts.some(row=>row.content_version===owner.filter)){owner.filter='all';owner.visible=4;owner.exerciseVisible=6;}owner.saved=saved;owner.loaded=true;}
    catch(error){if(current(owner,revision)&&error.name!=='AbortError'){
      owner.error=error.status===401||error.status===403?'La sesión cambió. Vuelve a entrar en tu perfil para consultar tu evolución.':error.status===503?'Tu historial privado todavía no está disponible. Vuelve a comprobarlo.':error.name==='TypeError'?'No pude conectar con tu historial. Revisa la conexión y vuelve a intentarlo.':error.message;
      owner.blocked=error.status===401||error.status===403;
    }}finally{if(current(owner,revision)){owner.busy=false;draw(owner);}}
  }
  function repeat(owner,row){if(!current(owner)||owner.busy||!row.can_repeat||typeof owner.onRepeat!=='function')return;owner.onRepeat({session_id:row.session_id,program_id:row.program_id,content_version:row.content_version,logs_version:owner.saved.logs_version});}
  function setText(set,index,perSide){
    const amount=set.reps!==null?`${format(set.reps)} repeticiones${perSide?' en total, ambos lados':''}`:`${format(set.seconds)} segundos${perSide?' en total, ambos lados':''}`;
    return `Serie ${index+1} · ${amount}${set.load?` · ${format(set.load.value)} ${set.load.unit}`:''}`;
  }
  function valueText(entry,exercise){
    if(entry.skipped)return {value:'Omitido',unit:'Lo marcaste como omitido'};
    if(exercise.tracking_unit===null)return {value:count(entry.totals.sets,'serie','series'),unit:'Cantidades conservadas en cada serie'};
    const value=exercise.tracking_unit==='reps'?entry.totals.reps:entry.totals.seconds;
    return {value:value===null?'Sin cantidad':format(value),unit:`${exercise.tracking_unit==='reps'?'repeticiones':'segundos'}${exercise.per_side?' en total, ambos lados':''} · ${count(entry.totals.sets,'serie','series')}`};
  }
  function comparisonNote(exercise){
    if(exercise.comparison_reason==='multiple_entries_on_day')return 'Hay varios registros en una de estas fechas. Puedes ver cada serie en el historial; no los ordenamos como si fueran sesiones consecutivas.';
    if(exercise.comparison_reason==='unknown_tracking_unit')return 'Conservamos las cantidades de cada serie. Este registro no permite una comparación con la misma unidad.';
    if(exercise.comparison_reason==='skipped_entry')return 'Uno de estos registros fue omitido. No cuenta como cero repeticiones ni como una reducción de tu rendimiento.';
    if(exercise.comparison_reason==='no_previous_day')return 'Cuando registres este ejercicio en otra fecha, podrás comparar lo que anotaste en ambas sesiones.';
    const delta=exercise.comparison,amount=exercise.tracking_unit==='reps'?delta.reps_delta:delta.seconds_delta;
    return `Diferencia registrada: ${signed(delta.set_count_delta)} ${Math.abs(delta.set_count_delta)===1?'serie':'series'}${amount===null?'':` · ${signed(amount)} ${exercise.tracking_unit==='reps'?(Math.abs(amount)===1?'repetición':'repeticiones'):(Math.abs(amount)===1?'segundo':'segundos')}${exercise.per_side?' en total, ambos lados':''}`}. Compara también las cargas y las series que anotaste abajo.`;
  }
  function drawExercise(owner,exercise){
    const card=el('article',null,'fxev-exercise');card.append(el('h5',exercise.name));
    if(exercise.comparison_reason==='multiple_entries_on_day')card.append(el('p',`${count(exercise.latest_day_entry_count,'registro','registros')} el ${dateLabel(exercise.latest.performed_on)}. Consulta las series de cada sesión.`,'fxev-single-record'));
    else if(exercise.previous){const comparison=el('div',null,'fxev-comparison');for(const [label,entry] of [['Anterior',exercise.previous],['Último registro',exercise.latest]]){const box=el('div'),value=valueText(entry,exercise);box.append(el('span',`${label} · ${dateLabel(entry.performed_on)}`,'fxev-comparison-label'),el('strong',value.value,'fxev-comparison-value'),el('span',value.unit,'fxev-comparison-unit'),el('span',entry.program_title,'fxev-comparison-program'));comparison.append(box);}card.append(comparison);}
    else{const value=valueText(exercise.latest,exercise);card.append(el('p',`${dateLabel(exercise.latest.performed_on)} · ${value.value} ${value.unit}`,'fxev-single-record'));}
    card.append(el('p',comparisonNote(exercise),'fxev-comparison-note'));
    if(!exercise.current_content_available)card.append(el('p','Este registro corresponde a una versión anterior de la rutina.','fxev-version-note'));
    const details=el('details'),summary=el('summary',`Ver las series · ${count(exercise.entry_count,'registro','registros')}`);details.append(summary);const history=el('ol',null,'fxev-history');let shown=0;
    function appendEntries(){for(const entry of exercise.history.slice(shown,shown+6)){const item=el('li'),date=el('time',dateLabel(entry.performed_on));date.setAttribute('datetime',entry.performed_on);item.append(date,el('span',entry.program_title,'fxev-history-program'));if(entry.skipped)item.append(el('p','Ejercicio omitido en esta sesión.','fxev-skipped'));else entry.sets.forEach((set,index)=>item.append(el('p',setText(set,index,exercise.per_side),'fxev-set')));history.append(item);}shown=Math.min(shown+6,exercise.history.length);}
    appendEntries();details.append(history);if(shown<exercise.history.length){const more=btn('Ver registros anteriores',()=>{if(!current(owner)||owner.busy)return;appendEntries();more.hidden=shown>=exercise.history.length;},'fxev-button fxev-quiet');details.append(more);}card.append(details);return card;
  }
  function filterOptions(saved){const versions=[...new Set(saved.workouts.map(row=>row.content_version))];return versions.map((value,index)=>({value,label:versions.length===1?'Todas las rutinas':value===saved.content_version?'Rutinas actuales':`Versión anterior ${index+1}`}));}
  function drawHistory(owner,body){
    const saved=owner.saved,heading=el('div',null,'fxev-heading');heading.append(el('h4','Tu recorrido'),btn('Actualizar',()=>void load(owner),'fxev-button fxev-quiet'));body.append(heading);
    if(!saved.workouts.length){const empty=el('div',null,'fxev-empty');empty.append(el('p','EL PRIMER PASO QUEDA CONTIGO','fxev-eyebrow'),el('h4','Aquí empieza tu historia.'),el('p','Cuando guardes las series de una rutina, aparecerán aquí. Roxy mostrará las repeticiones, los tiempos y las cargas que tú registres.','fxev-caption'));body.append(empty);return;}
    const options=filterOptions(saved);if(options.length>1){const label=el('label',null,'fxev-filter');label.append(el('span','Ver versión de las rutinas'));const select=el('select');select.setAttribute('aria-label','Ver versión de las rutinas');for(const option of [{value:'all',label:'Todas las versiones'},...options]){const node=el('option',option.label);node.value=option.value;select.append(node);}select.value=owner.filter;select.addEventListener('change',()=>{if(!current(owner)||owner.busy)return;owner.filter=select.value;owner.visible=4;owner.exerciseVisible=6;draw(owner);});label.append(select);body.append(label);}
    const rows=saved.workouts.filter(row=>owner.filter==='all'||row.content_version===owner.filter),timeline=el('ol',null,'fxev-timeline');
    for(const row of rows.slice(0,owner.visible)){
      const item=el('li'),card=el('article',null,'fxev-entry'),date=el('div',null,'fxev-date'),time=el('time',dateLabel(row.performed_on));time.setAttribute('datetime',row.performed_on);date.append(time);if(row.duration_minutes!==null)date.append(el('span',`${format(row.duration_minutes)} min registrados`,'fxev-duration'));
      card.append(date,el('h5',row.program_title),el('p',`${count(row.performed_exercises,'ejercicio registrado','ejercicios registrados')} · ${count(row.set_count,'serie','series')}${row.skipped_exercises?` · ${count(row.skipped_exercises,'omitido','omitidos')}`:''}`,'fxev-entry-stats'));
      if(!row.can_repeat)card.append(el('p','Conservamos tu registro. Esta versión no está disponible para volver a programarla.','fxev-version-note'));
      const actions=el('div',null,'fxev-actions');if(typeof owner.onOpenSession==='function')actions.append(btn('Ver registro',()=>{if(current(owner)&&!owner.busy)owner.onOpenSession(row.session_id);},'fxev-button fxev-quiet'));if(row.can_repeat&&typeof owner.onRepeat==='function')actions.append(btn('Repetir rutina',()=>repeat(owner,row),'fxev-button fxev-primary'));if(actions.children.length)card.append(actions);item.append(card);timeline.append(item);
    }
    body.append(timeline);if(rows.length>owner.visible)body.append(btn(`Ver más sesiones (${rows.length-owner.visible})`,()=>{if(current(owner)&&!owner.busy){owner.visible+=6;draw(owner);}},'fxev-button fxev-load-more'));
    const exercises=saved.exercises.filter(row=>owner.filter==='all'||row.content_version===owner.filter);if(exercises.length){const section=el('section',null,'fxev-comparisons'),title=el('div',null,'fxev-heading');title.append(el('h4','Ejercicio a ejercicio'));section.append(title,el('p','Tus dos fechas más recientes para cada ejercicio y versión. Son datos que tú anotaste; distintas cargas o cantidades no indican por sí solas una mejora.','fxev-caption'));const grid=el('div',null,'fxev-exercise-grid');exercises.slice(0,owner.exerciseVisible).forEach(exercise=>grid.append(drawExercise(owner,exercise)));section.append(grid);if(exercises.length>owner.exerciseVisible)section.append(btn('Ver más ejercicios',()=>{if(current(owner)&&!owner.busy){owner.exerciseVisible+=6;draw(owner);}},'fxev-button fxev-load-more'));body.append(section);}
  }
  function draw(owner){
    if(state!==owner||!owner.root)return;owner.root.replaceChildren();if(!active||document.hidden)return;
    const wrap=el('section',null,'fxev-shell');wrap.setAttribute('aria-label','Mi evolución en Ejercicio');wrap.setAttribute('aria-busy',String(owner.busy));owner.root.append(wrap);
    const hero=el('header',null,'fxev-hero');hero.append(el('p','TU ESTUDIO · TU RECORRIDO','fxev-eyebrow'),el('h3','Mi evolución'),el('p','Cada sesión cuenta una parte de tu historia. Aquí puedes volver a lo que hiciste y decidir tu próximo paso.','fxev-hero-copy'));
    if(owner.loaded&&owner.saved){const summary=owner.saved.summary,stats=el('div',null,'fxev-hero-stats');for(const [value,label] of [[summary.recorded_sessions,summary.recorded_sessions===1?'sesión registrada':'sesiones registradas'],[summary.active_days,summary.active_days===1?'día con registro':'días con registro'],[summary.total_sets,summary.total_sets===1?'serie registrada':'series registradas']]){const stat=el('div',null,'fxev-hero-stat');stat.append(el('strong',format(value)),el('span',label));stats.append(stat);}hero.append(stats);}wrap.append(hero);
    if(owner.busy){const status=el('p','Comprobando tu historial privado…','fxev-status');status.setAttribute('role','status');wrap.append(status);}
    if(owner.error){const error=el('p',owner.error,'fxev-error');error.setAttribute('role','alert');wrap.append(error);if(!owner.blocked)wrap.append(btn('Volver a cargar historial',()=>void load(owner),'fxev-button fxev-retry'));}
    if(owner.loaded&&owner.saved){const body=el('div',null,'fxev-body');drawHistory(owner,body);wrap.append(body);}
    if(owner.busy)wrap.querySelectorAll('button,select').forEach(node=>node.disabled=true);
  }
  function mount(root,options={}){
    if(!root)return;const identity=typeof options.identity==='string'?options.identity:'';
    if(!state||state.identity!==identity){if(state)clearPrivate(state);state={root,identity,revision:0,controller:null,busy:false,loaded:false,saved:null,error:'',blocked:false,filter:'all',visible:4,exerciseVisible:6};}
    else if(state.root!==root)state.root.replaceChildren();
    state.root=root;state.onRepeat=options.onRepeat;state.onOpenSession=options.onOpenSession;state.timezone=zoneOK(options.timezone)?options.timezone:'UTC';draw(state);if(active&&!state.loaded&&!state.busy&&!state.error)void load(state);
  }
  function setActive(value){const next=value===true;if(next===active)return;active=next;if(state){clearPrivate(state);if(next&&!document.hidden)void load(state);}}
  function clear(){if(state)clearPrivate(state);state=null;}
  scope.RoxyFitnessProgress={mount,setActive,clear};
  if(typeof document!=='undefined')document.addEventListener('visibilitychange',()=>{if(!state)return;if(document.hidden)clearPrivate(state);else if(active)void load(state);});
  scope.addEventListener?.('pagehide',clear);
  if(typeof module!=='undefined')module.exports={snapshot,dateOK,zoneOK,setText,valueText,comparisonNote,filterOptions};
})(typeof window!=='undefined'?window:globalThis);
