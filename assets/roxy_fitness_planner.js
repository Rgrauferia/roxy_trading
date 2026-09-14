/* Member-owned activity plans: choices and self-reports, never generated exercise doses. */
((scope) => {
  'use strict';
  const PREFIX='/api/fitness/v1/me/activity-plan';
  const PROGRAMS=['gentle-strength','gentle-balance','gentle-flexibility'];
  const TRAINING=['home-bodyweight-foundations','home-dumbbell-foundations','gym-dumbbell-foundations','gentle-mobility','yoga-gentle-start','core-foundations'];
  const TRAINING_TITLES={'home-bodyweight-foundations':'Tu fuerza empieza en casa','home-dumbbell-foundations':'Mancuernas, a tu ritmo','gym-dumbbell-foundations':'Fuerza en el estudio','gentle-mobility':'Muévete con más espacio','yoga-gentle-start':'Yoga: una pausa que se mueve','core-foundations':'Control del centro'};
  const validProgram=id=>PROGRAMS.includes(id)||TRAINING.includes(id);
  function chosenTargets(value){
    if(value===undefined||value===null)return undefined;
    if(!Array.isArray(value)||!value.length||value.length>100||new Set(value.map(row=>row?.exercise_id)).size!==value.length)throw new Error('No pude verificar los objetivos elegidos para esta sesión.');
    return value.map(row=>{if(!row||typeof row.exercise_id!=='string'||!/^[a-z0-9][a-z0-9_-]{0,99}$/.test(row.exercise_id)||!Array.isArray(row.sets)||!row.sets.length||row.sets.length>20)throw new Error('Revisa los ejercicios y series de tus objetivos.');return {exercise_id:row.exercise_id,sets:row.sets.map(set=>{const reps=set?.reps??null,seconds=set?.seconds??null,load=set?.load??null;
      if(!((Number.isInteger(reps)&&reps>=1&&reps<=10000&&seconds===null)||(reps===null&&typeof seconds==='number'&&Number.isFinite(seconds)&&seconds>0&&seconds<=86400))||(load!==null&&(!load||typeof load.value!=='number'||!Number.isFinite(load.value)||load.value<0||load.value>2500||!['kg','lb'].includes(load.unit))))throw new Error('Revisa las cantidades elegidas como objetivos.');return {reps,seconds,load:copy(load)};})};});
  }
  function trainingMetadata(row){
    if(!TRAINING.includes(row.program_id)){if(row.training_targets!=null)throw new Error('Esta guía no admite objetivos de otra rutina.');return {};}
    const c=row.confirmed_requirements,sets=[['equipment',['bodyweight','chair','wall','dumbbells','bench','mat']],['capabilities',['standing','sit_to_stand','hip_hinge','free_weights','bench_transfer','floor_transfer','kneeling']]];
    if(typeof row.content_version!=='string'||!row.content_version||row.content_version.length>80||!Number.isInteger(row.reserved_minutes)||row.reserved_minutes<5||row.reserved_minutes>180||!Number.isInteger(row.travel_minutes)||row.travel_minutes<0||row.travel_minutes>180||!c||sets.some(([key,allowed])=>!Array.isArray(c[key])||new Set(c[key]).size!==c[key].length||c[key].some(value=>!allowed.includes(value))))throw new Error('Revisa la rutina y sus requisitos antes de continuar.');
    const targets=chosenTargets(row.training_targets);
    return {content_version:row.content_version,confirmed_requirements:copy(c),reserved_minutes:row.reserved_minutes,travel_minutes:row.travel_minutes,...(targets?{training_targets:targets}:{})};
  }
  const sessionInput=row=>({id:row.id,program_id:row.program_id,date:row.date,time:row.time,...trainingMetadata(row)});
  const STATUSES=['planned','completed','skipped'];
  const LABELS={planned:'Pendiente',completed:'Realizada',skipped:'Omitida'};
  const UUID=/^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/i;
  let state=null,active=true;
  const copy=value=>JSON.parse(JSON.stringify(value));
  const zoneOK=value=>{try{return typeof value==='string'&&value.length<=64&&!!new Intl.DateTimeFormat('es',{timeZone:value});}catch(_){return false;}};
  const dateOK=value=>{if(typeof value!=='string'||!/^(?:20\d{2}|2100)-\d{2}-\d{2}$/.test(value))return false;const date=new Date(value+'T12:00:00Z');return Number.isFinite(date.getTime())&&date.toISOString().slice(0,10)===value;};
  const timeOK=value=>typeof value==='string'&&/^([01]\d|2[0-3]):[0-5]\d$/.test(value);
  function localNow(zone,now=new Date()) {
    const parts=new Intl.DateTimeFormat('en-CA',{timeZone:zoneOK(zone)?zone:'UTC',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(now),v=name=>parts.find(part=>part.type===name).value;
    return {date:`${v('year')}-${v('month')}-${v('day')}`,time:`${v('hour')}:${v('minute')}`};
  }
  function counts(sessions=[]) {return {planned:sessions.filter(s=>s.status==='planned').length,completed:sessions.filter(s=>s.status==='completed').length,skipped:sessions.filter(s=>s.status==='skipped').length,total:sessions.length};}
  function snapshot(payload) {
    if(!payload||!Number.isInteger(payload.version)||payload.version<0||JSON.stringify(payload).length>400000)throw new Error('No pude verificar tu plan guardado.');
    const consent=payload.consent;
    if(consent!==null&&(!consent||consent.purpose!=='fitness_activity_plan'||consent.text_version!=='fitness-activity-plan-v1'||typeof consent.granted!=='boolean'))throw new Error('No pude verificar el permiso de guardado.');
    const plan=payload.plan;
    if(plan!==null){
      if(consent?.granted!==true)throw new Error('El plan no tiene un permiso de guardado vigente.');
      if(!plan||typeof plan.title!=='string'||!plan.title.trim()||plan.title.length>100||!zoneOK(plan.timezone)||!Array.isArray(plan.sessions)||plan.sessions.length>366)throw new Error('El plan recibido no es válido.');
      const ids=new Set();
      for(const s of plan.sessions){if(!s||!UUID.test(s.id)||ids.has(s.id)||!validProgram(s.program_id)||!dateOK(s.date)||!timeOK(s.time)||!STATUSES.includes(s.status)||(s.completed_at!==null&&(typeof s.completed_at!=='string'||!Number.isFinite(Date.parse(s.completed_at)))))throw new Error('Una actividad guardada no se pudo verificar.');trainingMetadata(s);ids.add(s.id);}
    }
    const totals=counts(plan?.sessions);if(!payload.progress||Object.keys(totals).some(key=>payload.progress[key]!==totals[key]))throw new Error('El resumen no coincide con tus actividades.');
    return copy(payload);
  }
  function draftPlan(base,title,timezone,rows) {
    if(typeof title!=='string'||!title.trim()||title.trim().length>100)throw new Error('Pon un nombre de hasta 100 caracteres a tu plan.');
    if(!zoneOK(timezone))throw new Error('Revisa tu zona horaria, por ejemplo America/New_York.');
    if(base?.sessions?.length&&timezone!==base.timezone)throw new Error('Conserva la zona horaria de tus actividades guardadas.');
    if(!Array.isArray(rows)||!rows.length)throw new Error('Añade al menos una fecha y una hora.');
    const sessions=(base?.sessions||[]).map(sessionInput);
    for(const row of rows){if(!UUID.test(row.id)||!validProgram(row.program_id)||!dateOK(row.date)||!timeOK(row.time))throw new Error('Completa la guía, fecha y hora de cada actividad.');if(sessions.some(s=>s.date===row.date&&s.time===row.time))throw new Error('Ya hay una actividad a esa fecha y hora. Revisa tu selección.');sessions.push(sessionInput(row));}
    if(sessions.length>366)throw new Error('Tu plan admite hasta 366 actividades.');
    return {title:title.trim(),timezone,sessions:sessions.sort((a,b)=>(a.date+a.time).localeCompare(b.date+b.time))};
  }
  function reschedulePlan(base,row) {
    const original=base?.sessions?.find(session=>session.id===row?.id);
    if(!original||original.status!=='planned')throw new Error('Solo puedes reprogramar una actividad pendiente.');
    if(!validProgram(row.program_id)||!dateOK(row.date)||!timeOK(row.time))throw new Error('Completa la guía, fecha y hora de la actividad.');
    if(TRAINING.includes(original.program_id)&&row.program_id!==original.program_id)throw new Error('Elige la nueva rutina desde Rutinas para confirmar sus requisitos.');
    if(base.sessions.some(s=>s.id!==row.id&&s.date===row.date&&s.time===row.time))throw new Error('Ya hay una actividad a esa fecha y hora.');
    return {title:base.title,timezone:base.timezone,sessions:base.sessions.map(s=>sessionInput(s.id===row.id?row:s)).sort((a,b)=>(a.date+a.time).localeCompare(b.date+b.time))};
  }

  function proposalSnapshot(payload,owner) {
    const proposal=payload?.proposal;
    if(!proposal||JSON.stringify(payload).length>60000||!Number.isInteger(payload.profile_version)||payload.profile_version<0||payload.activity_plan_version!==owner.saved.version)throw new Error('Tu agenda o tus preferencias cambiaron. Vuelve a preparar la propuesta.');
    if(proposal.version!=='fitness-agenda-proposal-212-v1'||!['ready','no_slots'].includes(proposal.status)||proposal.timezone!==(owner.saved.plan?.timezone||owner.timezone)||!zoneOK(proposal.timezone)||!dateOK(proposal.start_date)||!dateOK(proposal.end_date)||proposal.end_date<proposal.start_date||!Number.isInteger(proposal.allocated_minutes)||proposal.allocated_minutes<5||proposal.allocated_minutes>180||!Number.isInteger(proposal.travel_minutes)||proposal.travel_minutes<0||proposal.travel_minutes>180||proposal.source_duration_minutes!==null||proposal.clinical_approval!==false||proposal.can_activate_training!==false||typeof proposal.notice_es!=='string'||proposal.notice_es.length>1200)throw new Error('No pude verificar los horarios propuestos. Revisa tus preferencias y vuelve a intentarlo.');
    if(!Array.isArray(proposal.sessions)||proposal.sessions.length>7||!Array.isArray(proposal.session_details)||proposal.session_details.length!==proposal.sessions.length||!Array.isArray(proposal.excluded_days)||proposal.excluded_days.length>7||(proposal.status==='ready')!==Boolean(proposal.sessions.length))throw new Error('No pude verificar las actividades propuestas.');
    const weekEnd=new Date(proposal.start_date+'T12:00:00Z');weekEnd.setUTCDate(weekEnd.getUTCDate()+6);
    if(proposal.end_date!==weekEnd.toISOString().slice(0,10)||(owner.proposalSetup?.startDate&&proposal.start_date!==owner.proposalSetup.startDate))throw new Error('La propuesta no corresponde a la semana que elegiste.');
    const ids=new Set(),dates=new Set(),existing=owner.saved.plan?.sessions||[],selected=owner.proposalSetup?.programIds||PROGRAMS;
    for(const row of proposal.sessions){
      if(!row||!UUID.test(row.id)||ids.has(row.id)||dates.has(row.date)||existing.some(s=>s.id===row.id||(s.status!=='skipped'&&s.date===row.date))||!PROGRAMS.includes(row.program_id)||!selected.includes(row.program_id)||!dateOK(row.date)||row.date<proposal.start_date||row.date>proposal.end_date||!timeOK(row.time))throw new Error('Una actividad propuesta no se pudo verificar.');
      const detail=proposal.session_details.filter(item=>item?.session_id===row.id);if(detail.length!==1||detail[0].allocated_minutes!==proposal.allocated_minutes||detail[0].travel_minutes!==proposal.travel_minutes||detail[0].source_duration_minutes!==null||!['starts_at','reserved_until'].every(key=>typeof detail[0][key]==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(detail[0][key])&&Number.isFinite(Date.parse(detail[0][key])))||Date.parse(detail[0].reserved_until)-Date.parse(detail[0].starts_at)!==(proposal.allocated_minutes+proposal.travel_minutes)*60000)throw new Error('No pude verificar el tiempo reservado de una actividad.');
      const start=localNow(proposal.timezone,new Date(detail[0].starts_at));if(start.date!==row.date||start.time!==row.time)throw new Error('La hora de la propuesta no coincide con tu zona horaria.');ids.add(row.id);dates.add(row.date);
    }
    for(const row of proposal.excluded_days){if(!row||!dateOK(row.date)||row.date<proposal.start_date||row.date>proposal.end_date||dates.has(row.date)||typeof row.message_es!=='string'||row.message_es.length>500)throw new Error('No pude verificar los días de la propuesta.');dates.add(row.date);}
    if(dates.size!==7)throw new Error('La propuesta no incluye todos los días de la semana elegida.');
    return copy(payload);
  }
  function trainingProposalSnapshot(payload,owner){
    const p=payload?.proposal;
    if(!p||JSON.stringify(payload).length>60000||!Number.isInteger(payload.profile_version)||payload.profile_version<0||payload.activity_plan_version!==owner.saved.version||p.version!=='home-training-proposal-213-v1'||p.status!=='ready'||!TRAINING.includes(p.program_id)||p.clinical_approval!==false||!zoneOK(p.timezone)||p.timezone!==(owner.saved.plan?.timezone||owner.timezone)||typeof p.title!=='string'||p.title.length>200||!dateOK(p.start_date)||!dateOK(p.end_date)||!Array.isArray(p.sessions)||!p.sessions.length||p.sessions.length>7||!Array.isArray(p.excluded_days)||p.excluded_days.length>7||!Array.isArray(p.session_details)||p.session_details.length!==p.sessions.length)throw new Error('La propuesta de rutina cambió. Vuelve a Rutinas para preparar sus fechas.');
    const end=new Date(p.start_date+'T12:00:00Z');end.setUTCDate(end.getUTCDate()+6);if(end.toISOString().slice(0,10)!==p.end_date)throw new Error('No pude verificar la semana de esta rutina.');
    const dates=new Set(),ids=new Set(),existing=owner.saved.plan?.sessions||[];
    for(const row of p.sessions){trainingMetadata(row);if(!UUID.test(row.id)||ids.has(row.id)||dates.has(row.date)||row.program_id!==p.program_id||row.content_version!==p.content_version||!dateOK(row.date)||row.date<p.start_date||row.date>p.end_date||!timeOK(row.time)||row.reserved_minutes!==p.reserved_minutes||row.travel_minutes!==p.travel_minutes||existing.some(s=>s.id===row.id||(s.status!=='skipped'&&s.date===row.date)))throw new Error('Una fecha de la rutina no pudo verificarse.');
      const d=p.session_details.filter(d=>d?.session_id===row.id);if(d.length!==1||!Number.isFinite(Date.parse(d[0].starts_at))||!Number.isFinite(Date.parse(d[0].reserved_until))||Date.parse(d[0].reserved_until)-Date.parse(d[0].starts_at)!==(p.reserved_minutes+p.travel_minutes)*60000)throw new Error('No pude verificar los minutos reservados.');
      const local=localNow(p.timezone,new Date(d[0].starts_at));if(local.date!==row.date||local.time!==row.time)throw new Error('La hora no coincide con tu zona.');dates.add(row.date);ids.add(row.id);
    }
    for(const day of p.excluded_days){if(!dateOK(day.date)||day.date<p.start_date||day.date>p.end_date||dates.has(day.date)||typeof day.message_es!=='string'||day.message_es.length>500)throw new Error('No pude verificar todos los días.');dates.add(day.date);}
    if(dates.size!==7)throw new Error('Faltan días de esta semana.');return copy(payload);
  }
  function consumeTraining(owner){
    if(!owner.pendingTraining||!owner.loaded||!owner.saved||owner.busy||!current(owner))return;
    const pending=owner.pendingTraining;owner.pendingTraining=null;owner.onTrainingConsumed?.();
    try{const result=trainingProposalSnapshot(pending,owner);owner.proposalMeta=result;owner.proposalStale=false;owner.draft={title:owner.saved.plan?.title||'Mi semana de movimiento',timezone:result.proposal.timezone,rows:result.proposal.sessions.map(sessionInput),consent:owner.saved.consent?.granted===true};owner.review=null;owner.error='';}
    catch(error){fail(owner,error);}
  }
  function consumeOpenSession(owner){
    if(!owner.pendingOpenSession||!owner.loaded||!owner.saved||owner.busy||!current(owner))return;
    const id=owner.pendingOpenSession;owner.pendingOpenSession=null;owner.onSessionConsumed?.();
    const session=owner.saved.plan?.sessions.find(row=>row.id===id);
    if(!session){owner.error='La actividad ya no está en tu plan. Vuelve a consultar tu progreso.';return;}
    if(TRAINING.includes(session.program_id)){owner.reader={sessionId:id,training:true,reviewRecord:true};owner.error='';owner.notice='';}
    else owner.error='Abre esta guía desde las actividades de tu plan.';
  }
  const el=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined&&text!==null)node.textContent=text;if(cls)node.className=cls;return node;};
  const btn=(text,fn,cls='fxpl-button')=>{const node=el('button',text,cls);node.type='button';node.addEventListener('click',fn);return node;};
  const current=(owner,revision=owner.revision)=>state===owner&&active&&!document.hidden&&owner.revision===revision&&owner.root?.isConnected!==false;
  function stopVoice(owner){if(owner.voiceOwned||owner.voiceActive)scope.RoxyHomeTour?.stop();owner.voiceOwned=false;owner.voiceActive=false;}
  function cancel(owner){owner.controller?.abort();owner.controller=null;owner.revision++;owner.busy=false;stopVoice(owner);scope.RoxyFitnessTrainingSession?.clear();}
  function focus(owner,selector){const target=owner.root.querySelector(selector);target?.focus({preventScroll:true});(target?.closest?.('.fx-session-cinema')||target)?.scrollIntoView?.({block:'start',behavior:'auto'});}
  function clearPrivate(owner){cancel(owner);owner.saved=null;owner.draft=null;owner.review=null;owner.pendingOpenSession=null;owner.pendingTraining=null;owner.proposalSetup=null;owner.proposalMeta=null;owner.proposalStale=false;owner.reader=null;owner.program=null;owner.confirm=null;owner.error='';owner.notice='';owner.loaded=false;owner.blocked=false;owner.uncertain=false;owner.conflict=false;owner.keys.clear();owner.root.replaceChildren();}
  async function request(owner,path,method='GET',payload) {
    const controller=new AbortController();owner.controller=controller;
    const headers={Accept:'application/json','Content-Type':'application/json','X-Roxy-Fitness-Member':owner.identity};
    if(method!=='GET'){
      headers['X-Roxy-Fitness-Request']='1';const fingerprint=JSON.stringify([path,method,payload]);
      if(!owner.keys.has(fingerprint))owner.keys.set(fingerprint,scope.crypto.randomUUID());headers['Idempotency-Key']=owner.keys.get(fingerprint);
    }
    let timer;
    try{return await Promise.race([(async()=>{
      const response=await fetch(path,{method,headers,credentials:'same-origin',cache:'no-store',signal:controller.signal,body:payload===undefined?undefined:JSON.stringify(payload)});
      const data=await response.json().catch(()=>({}));if(!response.ok){const error=new Error(typeof data.detail==='string'?data.detail:data.detail?.message||'No pude completar esta operación.');error.status=response.status;error.code=data.detail?.code;throw error;}return data;
    })(),new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(new Error('La conexión tardó demasiado. Comprueba el guardado antes de repetir.'));},12000);})]);}
    finally{clearTimeout(timer);if(owner.controller===controller)owner.controller=null;}
  }
  function fail(owner,error){
    owner.error=error.name==='TypeError'?'No pude conectar con tu plan. Revisa la conexión y vuelve a intentarlo.':error.status===503?'El guardado privado de Ejercicio todavía no está disponible. Puedes consultar las guías y volver a comprobarlo.':error.status===409?'Tu plan cambió en otra sesión. Vuelve a cargarlo antes de guardar para conservar esos cambios.':error.message;
    if(error.status===401||error.status===403){owner.saved=null;owner.draft=null;owner.review=null;owner.proposalSetup=null;owner.proposalMeta=null;owner.proposalStale=false;owner.reader=null;owner.program=null;owner.confirm=null;owner.loaded=false;owner.blocked=true;owner.error='La sesión cambió. Vuelve a entrar en tu perfil para consultar tu plan.';}
    if(error.status===409)owner.conflict=true;
  }
  async function load(owner){
    if(!current(owner)||owner.busy)return;cancel(owner);const rev=owner.revision;owner.busy=true;owner.error='';owner.blocked=false;draw(owner);
    try{
      const saved=snapshot(await request(owner,PREFIX));if(!current(owner,rev))return;owner.saved=saved;owner.loaded=true;owner.conflict=false;
      if(!owner.catalog){const data=await request(owner,'/api/fitness/v1/programs');if(!current(owner,rev))return;owner.catalog=scope.RoxyFitnessPrograms.validateCatalog(data);}
    }catch(error){if(current(owner,rev)&&error.name!=='AbortError')fail(owner,error);}
    finally{if(current(owner,rev)){owner.busy=false;consumeTraining(owner);consumeOpenSession(owner);draw(owner);}}
  }
  async function mutate(owner,path,method,payload,onSuccess){
    if(!current(owner)||owner.busy||owner.blocked||owner.conflict||owner.uncertain)return;
    stopVoice(owner);const rev=owner.revision;owner.busy=true;owner.error='';owner.notice='';draw(owner);
    try{const saved=snapshot(await request(owner,path,method,payload));if(!current(owner,rev))return;owner.saved=saved;owner.loaded=true;owner.keys.clear();onSuccess?.();}
    catch(error){if(current(owner,rev)&&error.name!=='AbortError'){fail(owner,error);owner.uncertain=true;}}
    finally{if(current(owner,rev)){owner.busy=false;draw(owner);}}
  }
  function startProposal(owner){
    if(!current(owner)||owner.busy||owner.conflict)return;stopVoice(owner);owner.reader=null;owner.review=null;owner.draft=null;owner.confirm=null;owner.proposalMeta=null;owner.proposalStale=false;owner.error='';owner.notice='';owner.proposalSetup={startDate:localNow(owner.saved.plan?.timezone||owner.timezone).date,programIds:[],result:null};draw(owner);focus(owner,'.fxpl-form-title');
  }
  async function propose(owner){
    if(!current(owner)||owner.busy||!owner.proposalSetup||owner.conflict)return;
    const setup=owner.proposalSetup;
    if(!dateOK(setup.startDate)||setup.startDate<localNow(owner.saved.plan?.timezone||owner.timezone).date||!setup.programIds.length){owner.error='Elige al menos una guía y una fecha de inicio que no esté en el pasado.';draw(owner);return;}
    const rev=owner.revision;owner.busy=true;owner.error='';owner.notice='';draw(owner);
    try{const result=proposalSnapshot(await request(owner,PREFIX+'/proposal','POST',{start_date:setup.startDate,program_ids:setup.programIds,expected_version:owner.saved.version}),owner);if(!current(owner,rev))return;
      if(result.proposal.status==='no_slots'){setup.result=result.proposal;owner.notice=result.proposal.notice_es;return;}
      owner.draft={title:owner.saved.plan?.title||'Mi semana de movimiento',timezone:result.proposal.timezone,rows:result.proposal.sessions.map(({id,program_id,date,time})=>({id,program_id,date,time})),consent:owner.saved.consent?.granted===true};owner.proposalMeta=result;owner.proposalSetup=null;owner.proposalStale=false;
    }catch(error){if(current(owner,rev)&&error.name!=='AbortError')fail(owner,error);}
    finally{if(current(owner,rev)){owner.busy=false;draw(owner);focus(owner,'.fxpl-form-title');}}
  }
  function drawProposal(owner,wrap){
    const setup=owner.proposalSetup,title=el('h3','Haz espacio para moverte','fxpl-form-title');title.tabIndex=-1;wrap.append(title,el('p','Elige las guías que quieres organizar. Roxy buscará horarios dentro de la disponibilidad que guardaste en tus preferencias.'));
    const form=el('form',null,'fxpl-form');form.setAttribute('aria-label','Organizar con mi disponibilidad');const label=el('label','Empezar a partir de'),date=el('input');date.type='date';date.required=true;date.value=setup.startDate;date.min=localNow(owner.saved.plan?.timezone||owner.timezone).date;date.setAttribute('aria-label','Fecha de inicio de la propuesta');date.addEventListener('input',()=>setup.startDate=date.value);label.append(date);form.append(label);
    const guides=el('fieldset',null,'fxpl-review');guides.append(el('legend','Guías que quiero incluir'));
    for(const program of owner.catalog){const label=el('label',null,'fxpl-consent'),check=el('input');check.type='checkbox';check.checked=setup.programIds.includes(program.id);check.setAttribute('aria-label',`Incluir ${program.title_es}`);check.addEventListener('change',()=>{setup.programIds=check.checked?[...new Set([...setup.programIds,program.id])]:setup.programIds.filter(id=>id!==program.id);});label.append(check,el('span',`${program.title_es} · ${program.exercise_count} movimientos`));guides.append(label);}form.append(guides);
    form.append(el('p','Se propone una agenda para los próximos 7 días desde la fecha elegida. Las guías son generales; el tiempo reservado es el que elegiste y la fuente no indica una duración total.','fxpl-caption'));
    if(setup.result){const excluded=el('div',null,'fxpl-empty');for(const day of setup.result.excluded_days)excluded.append(el('p',`${dateLabel(day.date,'').replace(/ · $/,'')}: ${day.message_es}`));form.append(excluded);}
    const submit=el('button','Proponer horarios','fxpl-button fxpl-primary');submit.type='submit';form.append(submit,btn('Cancelar',()=>{owner.proposalSetup=null;owner.error='';owner.notice='';draw(owner);},'fxpl-button fxpl-quiet'));
    if(typeof owner.onPreferences==='function')form.append(btn('Revisar mi disponibilidad',()=>{if(current(owner)&&!owner.busy)owner.onPreferences();},'fxpl-button fxpl-quiet'));
    form.addEventListener('submit',event=>{event.preventDefault();event.stopPropagation();void propose(owner);});wrap.append(form);
  }
  function newDraft(owner){
    if(!current(owner)||owner.busy)return;stopVoice(owner);owner.reader=null;owner.review=null;owner.confirm=null;owner.proposalSetup=null;owner.proposalMeta=null;owner.proposalStale=false;
    owner.draft={title:owner.saved?.plan?.title||'Mi semana de movimiento',timezone:owner.saved?.plan?.timezone||owner.timezone,rows:[{id:scope.crypto.randomUUID(),program_id:'',date:'',time:''}],consent:owner.saved?.consent?.granted===true};owner.error='';draw(owner);focus(owner,'.fxpl-form-title');
  }
  function editSession(owner,session){
    if(!current(owner)||owner.busy||session.status!=='planned')return;stopVoice(owner);owner.reader=null;owner.review=null;owner.confirm=null;owner.proposalSetup=null;owner.proposalMeta=null;owner.proposalStale=false;
    owner.draft={title:owner.saved.plan.title,timezone:owner.saved.plan.timezone,rows:[sessionInput(session)],consent:true,editing:session.id};owner.error='';draw(owner);focus(owner,'.fxpl-form-title');
  }
  async function save(owner){
    if(!current(owner)||owner.busy||!owner.review||owner.conflict||owner.proposalStale||owner.uncertain)return;
    if(!owner.draft.consent){owner.error='Confirma que autorizas guardar este plan en tu perfil personal.';draw(owner);return;}
    const rev=owner.revision;let writeStarted=false;owner.busy=true;owner.error='';draw(owner);
    try{
      if(owner.proposalMeta){const profile=await request(owner,'/api/fitness/v1/me/profile');if(!current(owner,rev))return;if(!Number.isInteger(profile.version)||profile.version!==owner.proposalMeta.profile_version||profile.consent?.granted!==true||profile.consent.purpose!=='fitness_preferences'||profile.consent.text_version!=='fitness-preferences-v1'){owner.proposalStale=true;throw new Error('Tus preferencias cambiaron. Vuelve a organizar los horarios con tu disponibilidad actual antes de guardar.');}}
      let expectedProfile=owner.proposalMeta?.profile_version;
      if(owner.draft.editing&&TRAINING.includes(owner.draft.rows[0].program_id)){const profile=await request(owner,'/api/fitness/v1/me/profile');if(!current(owner,rev))return;expectedProfile=profile.version;}
      writeStarted=true;
      if(owner.saved.consent?.granted!==true){const result=await request(owner,PREFIX+'/consent','POST',{expected_version:owner.saved.version,consent:{purpose:'fitness_activity_plan',text_version:'fitness-activity-plan-v1',granted:true}});if(!current(owner,rev))return;owner.saved=snapshot(result);}
      const result=await request(owner,PREFIX,'PUT',{expected_version:owner.saved.version,plan:owner.review,...(expectedProfile===undefined?{}:{expected_profile_version:expectedProfile})});if(!current(owner,rev))return;
      owner.saved=snapshot(result);const edited=owner.draft.editing;owner.draft=null;owner.review=null;owner.proposalMeta=null;owner.proposalStale=false;owner.keys.clear();owner.notice=edited?'La actividad quedó reprogramada. Si ya tenías un evento en Calendario Home, actualiza ese evento allí para evitar duplicarlo.':'Tu plan quedó guardado en tu perfil. Lo recuperarás al volver a Ejercicio.';
    }catch(error){if(current(owner,rev)&&error.name!=='AbortError'){fail(owner,error);owner.uncertain=writeStarted;}}
    finally{if(current(owner,rev)){owner.busy=false;draw(owner);}}
  }
  async function openReader(owner,session){
    if(current(owner)&&!owner.busy&&TRAINING.includes(session.program_id)){stopVoice(owner);owner.reader={sessionId:session.id,training:true};owner.error='';owner.notice='';draw(owner);return;}
    if(!current(owner)||owner.busy)return;stopVoice(owner);const rev=owner.revision;owner.busy=true;owner.error='';owner.notice='';owner.reader=null;draw(owner);
    try{const result=await request(owner,'/api/fitness/v1/programs/'+encodeURIComponent(session.program_id));if(!current(owner,rev))return;
      owner.program=scope.RoxyFitnessPrograms.validateDetail(result,owner.catalog.find(row=>row.id===session.program_id));owner.reader={sessionId:session.id,movement:0,instruction:0,language:'es'};
    }catch(error){if(current(owner,rev)&&error.name!=='AbortError')fail(owner,error);}
    finally{if(current(owner,rev)){owner.busy=false;draw(owner);focus(owner,'.fxpl-reader-title');}}
  }
  function requestStatus(owner,session,status){
    if(!current(owner)||owner.busy)return;stopVoice(owner);owner.confirm={id:session.id,status};draw(owner);focus(owner,'.fxpl-confirm');
  }
  function dateLabel(date,time){return new Intl.DateTimeFormat('es',{weekday:'long',day:'numeric',month:'short',timeZone:'UTC'}).format(new Date(date+'T12:00:00Z'))+' · '+time;}
  function titleFor(owner,id){return owner.catalog?.find(row=>row.id===id)?.title_es||TRAINING_TITLES[id]||'Guía de movimiento';}
  function rowCard(owner,session){
    const card=el('article',null,'fxpl-session');card.append(el('p',dateLabel(session.date,session.time),'fxpl-date'),el('h4',titleFor(owner,session.program_id)),el('span',LABELS[session.status],'fxpl-badge fxpl-'+session.status));
    const actions=el('div',null,'fxpl-actions');actions.append(btn(session.status==='planned'?'Empezar mi actividad':'Consultar la guía',()=>void openReader(owner,session),'fxpl-button fxpl-primary'));
    const now=localNow(owner.saved.plan.timezone),future=session.date+session.time>now.date+now.time;
    if(session.status!=='completed'){
      const complete=btn('Marcar realizada',()=>requestStatus(owner,session,'completed'));complete.disabled=future;actions.append(complete);
      if(future)card.append(el('p','Podrás registrar que la realizaste cuando llegue la fecha y hora elegidas.','fxpl-caption'));
    }
    if(session.status==='planned'){actions.append(btn('Reprogramar',()=>editSession(owner,session)),btn('Cancelar esta actividad',()=>requestStatus(owner,session,'skipped'),'fxpl-button fxpl-quiet'));}
    else actions.append(btn('Volver a pendiente',()=>requestStatus(owner,session,'planned'),'fxpl-button fxpl-quiet'));
    if(typeof owner.scheduleActivity==='function')actions.append(btn('Añadir al calendario Home',()=>{if(current(owner)){stopVoice(owner);owner.scheduleActivity({date:session.date,time:session.time,timezone:owner.saved.plan.timezone,starts_at:session.starts_at});}},'fxpl-button fxpl-quiet'));
    card.append(actions);return card;
  }
  function drawForm(owner,wrap){
    const draft=owner.draft,title=el('h3',draft.editing?'Reprogramar actividad':owner.saved?.plan?'Añadir actividades a mi plan':'Prepara tu plan','fxpl-form-title');title.tabIndex=-1;wrap.append(title,el('p','Elige una guía y reserva tus propias fechas. Roxy conserva el contenido de la guía; tú decides cómo organizarte.'));
    if(owner.proposalMeta){const proposal=owner.proposalMeta.proposal;wrap.append(el('p',`Origen: tu disponibilidad guardada. ${proposal.allocated_minutes||proposal.reserved_minutes} minutos reservados por actividad${proposal.travel_minutes?` + ${proposal.travel_minutes} minutos de desplazamiento`:''}. ${proposal.version==='home-training-proposal-213-v1'?'La duración es estimada. Revisa las fechas y horas; conservamos los requisitos que confirmaste.':'La fuente no indica la duración total de estas guías. Puedes editar sus fechas, horas y guías antes de guardar.'}`,'fxpl-caption'));if(proposal.excluded_days.length){const excluded=el('details',null,'fxpl-data');excluded.append(el('summary','Días sin una actividad nueva'));for(const day of proposal.excluded_days)excluded.append(el('p',`${dateLabel(day.date,'').replace(/ · $/,'')}: ${day.message_es}`,'fxpl-caption'));wrap.append(excluded);}if(owner.proposalStale){wrap.append(btn('Volver a organizar horarios',()=>startProposal(owner),'fxpl-button fxpl-primary'));return;}}
    if(owner.review){
      const review=el('section',null,'fxpl-review');review.append(el('h4','Revisa antes de guardar'),el('p',owner.review.title),el('p',owner.review.timezone,'fxpl-caption'));
      for(const row of draft.rows){review.append(el('p',`${titleFor(owner,row.program_id)} · ${dateLabel(row.date,row.time)}`));if(row.training_targets?.length)review.append(el('p',`Incluye tus objetivos elegidos para ${row.training_targets.length} ejercicios. Son referencias para la sesión, no resultados realizados ni una recomendación de aumentar el esfuerzo.`,'fxpl-caption'));}
      if(owner.saved?.plan?.sessions.length)review.append(el('p',draft.editing?'Solo cambia esta actividad pendiente. Tus otras actividades y su historial se conservan.':`Conservaremos tus ${owner.saved.plan.sessions.length} actividades anteriores y su historial.`,'fxpl-caption'));
      const label=el('label',null,'fxpl-consent'),check=el('input');check.type='checkbox';check.checked=draft.consent;check.addEventListener('change',()=>draft.consent=check.checked);label.append(check,el('span','Autorizo guardar mi plan y mis registros de actividad solo en mi perfil personal.'));review.append(label,el('p','Puedes descargar o eliminar estos datos desde Mi plan. El calendario del hogar se añade por separado.','fxpl-caption'));
      review.append(btn(draft.editing?'Guardar cambio':'Guardar mi plan',()=>void save(owner),'fxpl-button fxpl-primary'),btn('Volver a editar',()=>{owner.review=null;draw(owner);},'fxpl-button fxpl-quiet'));wrap.append(review);return;
    }
    const form=el('form',null,'fxpl-form');form.setAttribute('aria-label','Mi plan de movimiento');
    const fields=el('div',null,'fxpl-fields');
    function field(label,value,type,onChange){const parent=el('label',label),input=el('input');input.type=type;input.value=value;input.required=true;input.setAttribute('aria-label',label);input.addEventListener('input',()=>onChange(input.value));parent.append(input);return {parent,input};}
    const name=field('Nombre de mi plan',draft.title,'text',value=>draft.title=value);name.input.maxLength=100;name.input.readOnly=!!draft.editing;
    const zone=field('Zona horaria',draft.timezone,'text',value=>draft.timezone=value);zone.input.maxLength=64;zone.input.readOnly=!!owner.saved?.plan?.sessions.length;fields.append(name.parent,zone.parent);form.append(fields);if(zone.input.readOnly)form.append(el('p','Conservamos la zona horaria de este plan para mantener tus fechas y registros anteriores.','fxpl-caption'));
    draft.rows.forEach((row,index)=>{
      const item=el('fieldset',null,'fxpl-draft-row');item.append(el('legend',`Actividad ${index+1}`));
      const label=el('label','Guía'),select=el('select');select.required=true;select.setAttribute('aria-label',`Guía de actividad ${index+1}`);
      const placeholder=el('option','Elige una guía');placeholder.value='';select.append(placeholder);
      (TRAINING.includes(row.program_id)?[{id:row.program_id,title_es:titleFor(owner,row.program_id),exercise_count:null}]:owner.catalog).forEach(program=>{const option=el('option',`${program.title_es}${program.exercise_count?` · ${program.exercise_count} movimientos`:""}`);option.value=program.id;option.selected=row.program_id===program.id;select.append(option);});select.value=row.program_id;select.addEventListener('change',()=>row.program_id=select.value);label.append(select);
      const date=field(`Fecha de actividad ${index+1}`,row.date,'date',value=>row.date=value),time=field(`Hora de actividad ${index+1}`,row.time,'time',value=>row.time=value);
      item.append(label,date.parent,time.parent);if(draft.rows.length>1)item.append(btn(`Quitar actividad ${index+1}`,()=>{draft.rows.splice(index,1);draw(owner);},'fxpl-button fxpl-quiet'));form.append(item);
    });
    if(!draft.editing&&owner.proposalMeta?.proposal.version!=='home-training-proposal-213-v1'&&(owner.saved?.plan?.sessions.length||0)+draft.rows.length<366)form.append(btn('Añadir otra fecha',()=>{draft.rows.push({id:scope.crypto.randomUUID(),program_id:'',date:'',time:''});draw(owner);},'fxpl-button fxpl-quiet'));
    form.append(el('p',draft.rows.some(s=>TRAINING.includes(s.program_id))?'Tus fechas deben caber en la disponibilidad guardada. Puedes repetir o adaptar el ritmo durante la sesión; las cargas las eliges y registras tú.':'Las guías no indican una duración total. Las horas son tu elección de agenda, sin cargas ni progresiones calculadas.','fxpl-caption'));
    const submit=el('button','Revisar mi plan','fxpl-button fxpl-primary');submit.type='submit';form.append(submit);
    form.addEventListener('submit',event=>{event.preventDefault();event.stopPropagation();if(!current(owner)||owner.busy)return;try{owner.review=draft.editing?reschedulePlan(owner.saved.plan,draft.rows[0]):draftPlan(owner.saved.plan,draft.title,draft.timezone,draft.rows);owner.error='';}catch(error){owner.error=error.message;}draw(owner);});
    form.append(btn('Cancelar',()=>{owner.draft=null;owner.review=null;owner.proposalMeta=null;owner.proposalStale=false;owner.error='';draw(owner);},'fxpl-button fxpl-quiet'));wrap.append(form);
  }
  function drawReader(owner,wrap){
    const {program,reader}=owner,session=owner.saved.plan.sessions.find(s=>s.id===reader.sessionId);if(!session)return;
    if(reader.training){const root=el('div',null,'fxpl-training-session');wrap.append(root);scope.RoxyFitnessTrainingSession?.setActive(true);scope.RoxyFitnessTrainingSession?.mount(root,{identity:owner.identity,session,timezone:owner.saved.plan.timezone,reviewRecord:reader.reviewRecord===true,onClose:()=>{if(current(owner)){scope.RoxyFitnessTrainingSession?.clear();owner.reader=null;draw(owner);}},onSaved:()=>{},onComplete:()=>{if(current(owner)){scope.RoxyFitnessTrainingSession?.clear();requestStatus(owner,session,'completed');}}});return;}
    const lang=reader.language,box=el('section',null,'fxpl-reader fx-session-cinema');box.setAttribute('data-fx-reading','true');box.setAttribute('aria-label','Mi actividad con Roxy');
    const setInstruction=index=>{if(!current(owner)||index<0||index>=program.exercises[reader.movement]['instructions_'+reader.language].length)return;stopVoice(owner);reader.instruction=index;draw(owner);focus(owner,'.fx-session-current-instruction');};
    const scene=scope.RoxyFitnessPrograms.renderSessionScene({program,movement:reader.movement,language:lang,instruction:reader.instruction,titleClass:'fxpl-reader-title',instructionsClass:'fxpl-instructions',onInstruction:setInstruction},{element:el,button:btn});box.append(scene.stage);
    const content=el('div',null,'fx-session-support');content.append(el('p','Sigue la guía a tu ritmo. Si sientes dolor, detén el movimiento.','fxpl-caption fx-session-safety'));
    const intro=el('details',null,'fxpl-intro fx-session-intro');intro.lang=lang;intro.append(el('summary','Antes de empezar'));program['intro_'+lang].forEach(line=>intro.append(el('p',line)));intro.open=reader.movement===0&&!reader.instruction;content.append(intro,scene.source);
    const controls=el('div',null,'fxpl-actions fx-session-transport');controls.setAttribute('aria-label','Controles de mi actividad');
    const previous=btn('Anterior',()=>{if(current(owner)&&reader.movement>0){stopVoice(owner);reader.movement--;reader.instruction=0;draw(owner);focus(owner,'.fxpl-reader-title');}},'fxpl-button fx-session-button fx-session-quiet');
    const next=btn('Siguiente movimiento',()=>{if(current(owner)&&reader.movement<program.exercises.length-1){stopVoice(owner);reader.movement++;reader.instruction=0;draw(owner);focus(owner,'.fxpl-reader-title');}},'fxpl-button fx-session-button');previous.disabled=reader.movement===0;next.disabled=reader.movement===program.exercises.length-1;controls.append(previous);
    if(scope.RoxyHomeTour){
      const status=el('p','Voz oficial de Roxy · lectura del movimiento completo en español','fxpl-caption fx-session-voice-status');status.setAttribute('role','status');const host=el('div',null,'fx-session-voice-host');
      const play=()=>{if(!current(owner))return;stopVoice(owner);owner.voiceActive=true;owner.voiceOwned=true;
        void scope.RoxyHomeTour.speak(`fitness:${program.id.replace('gentle-','')}:${reader.movement}`,(phase,message)=>{if(!current(owner)||voice.isConnected===false)return;owner.voiceActive=['loading','playing','ready'].includes(phase);if(['ended','error'].includes(phase))owner.voiceOwned=false;status.textContent=message;voice.textContent=owner.voiceActive?'Pausar voz':'Escuchar a Roxy';},host);};
      const voice=btn('Escuchar a Roxy',()=>{if(!current(owner))return;if(owner.voiceActive){stopVoice(owner);voice.textContent='Escuchar a Roxy';status.textContent='Voz oficial pausada';}else play();},'fxpl-button fx-session-button fx-session-voice');controls.append(voice,btn('Repetir voz',play,'fxpl-button fx-session-button fx-session-quiet'));content.append(status,host);
    }
    controls.append(next);box.append(controls,content);
    const completion=el('div',null,'fx-session-completion');
    const now=localNow(owner.saved.plan.timezone),done=btn('Terminé · registrar realizada',()=>requestStatus(owner,session,'completed'),'fxpl-button fxpl-primary fx-session-button');done.disabled=session.status==='completed'||session.date+session.time>now.date+now.time;completion.append(done,el('p','Leer o escuchar todos los movimientos no registra una actividad. Tú confirmas si la realizaste.','fxpl-caption'));box.append(completion);
    const credit=el('footer',null,'fxpl-credit fx-session-credit');credit.append(btn(lang==='es'?'Ver original en inglés':'Ver adaptación en español',()=>{if(!current(owner))return;stopVoice(owner);reader.language=lang==='es'?'en':'es';draw(owner);},'fxpl-button fx-session-button fx-session-quiet'),el('p',program['attribution_'+lang]),el('p',`Original ${program.source_version} · consultado ${program.checked_on}`));
    for(const [label,url] of [['Open Government Licence v3',program.license_url],['Procedencia del original en inglés',program.source_url],['Condiciones de la fuente',program.terms_url]]){const link=el('a',label);link.href=url;link.target='_blank';link.rel='noopener noreferrer';credit.append(link);}if(lang==='es')program.notes_es.forEach(line=>credit.append(el('p',line)));
    box.append(credit,btn('Volver a mi plan',()=>{if(!current(owner))return;stopVoice(owner);owner.reader=null;draw(owner);},'fxpl-button fx-session-button fx-session-exit'));wrap.append(box);
  }
  async function exportData(owner){
    if(!current(owner)||owner.busy)return;const rev=owner.revision;owner.busy=true;owner.error='';draw(owner);
    try{const data=await request(owner,PREFIX+'/data');if(!current(owner,rev))return;const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),link=el('a');link.href=url;link.download='mi-plan-ejercicio-roxy.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);owner.notice='Descarga preparada con los datos guardados de tu plan.';}catch(error){if(current(owner,rev))fail(owner,error);}finally{if(current(owner,rev)){owner.busy=false;draw(owner);}}
  }
  function draw(owner){
    if(state!==owner||!owner.root)return;stopVoice(owner);if(!owner.reader?.training||owner.confirm||owner.draft)scope.RoxyFitnessTrainingSession?.clear();owner.root.replaceChildren();if(!active||document.hidden)return;
    const wrap=el('section',null,'fxpl-shell');wrap.setAttribute('aria-label','Mi plan privado de Ejercicio');wrap.setAttribute('aria-busy',String(owner.busy));owner.root.append(wrap);
    const heading=el('header',null,'fxpl-heading');heading.append(el('p','ELEGIDO POR TI · GUARDADO EN TU PERFIL','fxpl-eyebrow'),el('h3',owner.view==='progress'?'Tu constancia, día a día':owner.view==='week'?'Mi plan de movimiento':'Hoy me muevo'));wrap.append(heading);
    if(owner.busy){const loading=el('p','Comprobando tu plan…','fxpl-status');loading.setAttribute('role','status');wrap.append(loading);}
    if(owner.error){const error=el('p',owner.error,'fxpl-error');error.setAttribute('role','alert');wrap.append(error,btn(owner.uncertain?'Comprobar guardado':'Volver a cargar mi plan',()=>{owner.draft=null;owner.review=null;owner.proposalSetup=null;owner.proposalMeta=null;owner.proposalStale=false;owner.confirm=null;owner.uncertain=false;owner.loaded=false;owner.saved=null;void load(owner);}));}
    if(owner.notice){const status=el('p',owner.notice,'fxpl-status');status.setAttribute('role','status');wrap.append(status);}
    if(!owner.loaded||!owner.saved||!owner.catalog||owner.blocked)return;
    if(owner.conflict||owner.uncertain)return;
    if(owner.confirm){
      const confirm=el('section',null,'fxpl-confirm');confirm.tabIndex=-1;confirm.setAttribute('role','group');
      if(owner.confirm.delete){confirm.append(el('h4','Eliminar mi plan y sus registros'),el('p','Se borrarán tus actividades de este perfil y se retirará el permiso de guardado. Los eventos que confirmaste en el calendario Home se gestionan allí.'));
        confirm.append(btn('Sí, eliminar mi plan',()=>void mutate(owner,PREFIX+'/data','DELETE',{expected_version:owner.saved.version,confirm_delete:true},()=>{owner.confirm=null;owner.reader=null;owner.notice='Tu plan y sus registros fueron eliminados del perfil.';}),'fxpl-button fxpl-danger'));
      }else{const session=owner.saved.plan.sessions.find(s=>s.id===owner.confirm.id);confirm.append(el('h4',owner.confirm.status==='completed'?'¿Realizaste esta actividad?':owner.confirm.status==='skipped'?'¿Cancelar esta actividad?' :'¿Volver a dejarla pendiente?'),el('p',`${titleFor(owner,session.program_id)} · ${dateLabel(session.date,session.time)}`),el('p',owner.confirm.status==='skipped'?'Quedará como omitida en tu historial. Si tiene un evento en Calendario Home, gestiona ese evento allí.':'Este registro refleja lo que tú declaras. Puedes corregirlo después.'));
        confirm.append(btn(owner.confirm.status==='completed'?'Sí, la realicé':owner.confirm.status==='skipped'?'Sí, cancelar actividad':'Confirmar pendiente',()=>void mutate(owner,PREFIX+'/sessions/'+encodeURIComponent(session.id),'PATCH',{expected_version:owner.saved.version,status:owner.confirm.status},()=>{owner.confirm=null;owner.reader=null;owner.notice='Registro actualizado en tu perfil.';}),'fxpl-button fxpl-primary'));
      }
      confirm.append(btn('Cancelar',()=>{owner.confirm=null;draw(owner);},'fxpl-button fxpl-quiet'));wrap.append(confirm);
    }else if(owner.proposalSetup)drawProposal(owner,wrap);
    else if(owner.draft)drawForm(owner,wrap);
    else if(owner.reader)drawReader(owner,wrap);
    else{
      const sessions=owner.saved.plan?.sessions||[],totals=counts(sessions);
      if(owner.saved.plan)wrap.append(el('p',owner.saved.plan.title,'fxpl-plan-name'),el('p',`Horario de tu plan: ${owner.saved.plan.timezone}`,'fxpl-caption'));
      if(owner.view==='progress'){
        const stats=el('div',null,'fxpl-stats');for(const [key,label] of [['completed','Realizadas'],['planned','Pendientes'],['skipped','Omitidas']]){const cell=el('div');cell.append(el('strong',String(totals[key])),el('span',label));stats.append(cell);}wrap.append(stats,el('p','Conteos de tus propios registros. No calculamos calorías ni interpretamos estos datos como mediciones físicas.','fxpl-caption'));
      }
      const content=owner.view==='progress'?el('details',null,'fxpl-data fxpl-progress-history'):wrap;
      if(owner.view==='progress'){content.append(el('summary',`Historial de actividades (${sessions.length})`));wrap.append(content);}
      let shown=[...sessions].sort((a,b)=>(a.date+a.time).localeCompare(b.date+b.time));
      if(owner.view==='today'){
        const today=localNow(owner.saved.plan?.timezone||owner.timezone).date,todayRows=shown.filter(s=>s.date===today),overdue=shown.filter(s=>s.date<today&&s.status==='planned');
        if(todayRows.length){content.append(el('h4','Para hoy'));shown=todayRows;}
        else{const next=shown.find(s=>s.date>today&&s.status==='planned');shown=next?[next]:[];content.append(el('p',next?'Tu próxima actividad':'Hoy no tienes una actividad programada. Tú eliges cuándo moverte.'));}
        if(overdue.length){const notice=el('p',`Tienes ${overdue.length} ${overdue.length===1?'actividad pendiente anterior':'actividades pendientes anteriores'}. No las reprogramamos automáticamente.`,'fxpl-caption');content.append(notice,btn('Ver todas mis actividades',()=>{owner.view='week';draw(owner);}));}
      }else if(owner.view==='progress')shown.reverse();
      if(!sessions.length)content.append(el('div','Prepara tu primera actividad: elige una guía y una fecha. Al guardarla, aparecerá aquí cada vez que vuelvas.','fxpl-empty'));
      const list=el('div',null,'fxpl-session-list');shown.forEach(session=>list.append(rowCard(owner,session)));content.append(list,btn(sessions.length?'Añadir actividades':'Crear mi plan',()=>newDraft(owner),'fxpl-button fxpl-primary'));
      if(owner.view!=='progress')content.append(btn('Organizar con mi disponibilidad',()=>startProposal(owner),'fxpl-button'));
      if(typeof owner.onTraining==='function'&&owner.view!=='progress')content.append(btn('Elegir una rutina',()=>owner.onTraining(),'fxpl-button fxpl-primary'));content.append(el('p','Tu agenda reúne las guías y rutinas que eliges. Los requisitos de cada rutina se confirman antes de programarla.','fxpl-caption'));
      if(owner.saved.plan){content.append(el('p','«Añadir al calendario Home» abre un borrador genérico. Revisa y confirma su hora y duración; ese calendario es visible para tu hogar.','fxpl-caption'));
        const settings=el('details',null,'fxpl-data');settings.append(el('summary','Mis datos de Ejercicio'),btn('Descargar mi plan y registros',()=>void exportData(owner)),btn('Eliminar plan y registros',()=>{owner.confirm={delete:true};draw(owner);},'fxpl-button fxpl-quiet'));content.append(settings);}
    }
    if(owner.busy)wrap.querySelectorAll('button,input,select').forEach(node=>node.disabled=true);
  }
  function mount(root,options={}){
    if(!root)return;const identity=options.identity||'';
    if(!state||state.identity!==identity){if(state)clearPrivate(state);state={root,identity,revision:0,controller:null,busy:false,loaded:false,saved:null,catalog:null,draft:null,review:null,reader:null,confirm:null,program:null,keys:new Map(),error:'',notice:'',timezone:zoneOK(options.timezone)?options.timezone:'UTC'};}
    const nextView=['today','week','progress'].includes(options.view)?options.view:'today';
    if(state.view!==nextView&&state.reader){stopVoice(state);state.reader=null;}
    state.root=root;state.view=nextView;if(zoneOK(options.timezone))state.timezone=options.timezone;state.scheduleActivity=options.scheduleActivity;state.onPreferences=options.onPreferences;state.onTraining=options.onTraining;state.onTrainingConsumed=options.onTrainingConsumed;if(options.trainingProposal)state.pendingTraining=copy(options.trainingProposal);if(options.openSessionId&&UUID.test(options.openSessionId))state.pendingOpenSession=options.openSessionId;state.onSessionConsumed=options.onSessionConsumed;consumeTraining(state);consumeOpenSession(state);draw(state);if(active&&!state.loaded&&!state.busy&&!state.error)void load(state);
  }
  function setActive(value){const next=value===true;if(next===active)return;active=next;if(state){clearPrivate(state);if(next&&!document.hidden)void load(state);}}
  function clear(){if(state)clearPrivate(state);state=null;}
  scope.RoxyFitnessPlanner={mount,setActive,clear};
  if(typeof document!=='undefined')document.addEventListener('visibilitychange',()=>{if(!state)return;if(document.hidden)clearPrivate(state);else if(active)void load(state);});
  scope.addEventListener?.('pagehide',clear);
  if(typeof module!=='undefined')module.exports={localNow,counts,snapshot,draftPlan,reschedulePlan,proposalSnapshot,trainingProposalSnapshot,trainingMetadata,chosenTargets,sessionInput,dateOK,timeOK,zoneOK};
})(typeof window!=='undefined'?window:globalThis);
