/* Roxy Home Exercise: private preferences, no clinical prescriptions.
 * Deliberately no localStorage, IndexedDB, telemetry, AI or offline health cache.
 */
((scope) => {
  'use strict';
  let trainingProposal=null,repeatTrainingSource=null,openTrainingSession=null;
  const DAYS = [['mon','Lun'],['tue','Mar'],['wed','Mié'],['thu','Jue'],['fri','Vie'],['sat','Sáb'],['sun','Dom']];
  const GOALS = {
    strength:['fitness_center','Ganar fuerza','Sentirte más fuerte en tu día a día.'],
    muscle_gain:['exercise','Ganar masa muscular','Construir una base de fuerza y constancia.'],
    fat_loss:['directions_walk','Reducir grasa o peso','Con hábitos sostenibles, sin fechas prometidas.'],
    healthy_weight_gain:['nutrition','Aumentar peso de forma saludable','Un objetivo distinto de ganar músculo.'],
    fitness_habit:['favorite','Moverme y sentirme mejor','Más movimiento y un hábito que encaje contigo.']
  };
  const LOCATIONS = {home:'En casa',gym:'Gimnasio',outdoors:'Al aire libre'};
  const EQUIPMENT = {bodyweight:'Sin material',mat:'Colchoneta',bands:'Bandas',dumbbells:'Mancuernas',bench:'Banco',barbell:'Barra',confirmed_gym_machines:'Máquinas confirmadas'};
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const icon = value => `<span class="material-symbols-rounded" aria-hidden="true">${value}</span>`;
  const defaults = () => ({age_band:null,language:'es',weight_unit:'kg',length_unit:'cm',timezone:Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',primary_goal:null,secondary_goal:null,without_weight_or_calories:true,experience:'prefer_not_to_say',locations:[],equipment:[],availability:[],session_minutes:null,travel_minutes:0});
  const clone = value => JSON.parse(JSON.stringify(value));
  const canonical = value => Array.isArray(value) ? value.map(canonical) : value && typeof value==='object' ? Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])) : value;
  const validTimezone = value => {if(typeof value!=='string'||!value.trim())return false;try{new Intl.DateTimeFormat('es',{timeZone:value});return true;}catch(_){return false;}};
  function weekDates(timezone, now=new Date()) {
    const parts = new Intl.DateTimeFormat('en-US',{timeZone:validTimezone(timezone)?timezone:'UTC',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);
    const n=type=>Number(parts.find(p=>p.type===type).value);
    const day=new Date(Date.UTC(n('year'),n('month')-1,n('day'),12));
    day.setUTCDate(day.getUTCDate()-(day.getUTCDay()+6)%7);
    return DAYS.map(([key,label],i)=>{const d=new Date(day);d.setUTCDate(d.getUTCDate()+i);return {key,label,date:d.toISOString().slice(0,10),number:d.getUTCDate()};});
  }
  function validateAvailability(p) {
    if(p.session_minutes!==null && (!Number.isInteger(p.session_minutes)||p.session_minutes<5||p.session_minutes>180))return 'Indica entre 5 y 180 minutos por sesión, o déjalo sin definir.';
    if(!Number.isInteger(p.travel_minutes)||p.travel_minutes<0||p.travel_minutes>180)return 'Indica entre 0 y 180 minutos de desplazamiento.';
    for(const row of p.availability) for(const win of row.windows) {
      if(!/^([01]\d|2[0-3]):[0-5]\d$/.test(win.start)||!/^([01]\d|2[0-3]):[0-5]\d$/.test(win.end)||win.end<=win.start) return 'Revisa las horas: el final debe ser posterior al inicio, en el mismo día.';
      const mins=s=>Number(s.slice(0,2))*60+Number(s.slice(3));
      if(p.session_minutes && p.session_minutes+p.travel_minutes>mins(win.end)-mins(win.start)) return 'El tiempo de sesión y desplazamiento no cabe en una de las ventanas. Amplíala o reduce los minutos.';
    }
    for(const row of p.availability){const sorted=[...row.windows].sort((a,b)=>a.start.localeCompare(b.start));if(sorted.some((win,i)=>i>0&&win.start<sorted[i-1].end))return 'Las ventanas de un mismo día no pueden solaparse. Revisa sus horas.';}
    return '';
  }
  let root, context, identity, abort, generation=0, view='welcome', step=0, section='today', selectedDay='mon';
  let profile=defaults(), snapshot={version:0,profile:null,consent:null}, status=null, saved=false, busy=false, notice='', failure='', ready=false, consentChecked=false, ageOutside=false;
  let remoteUncertain=false, pageSuspended=false, moduleActive=true, checkingIdentity=false, discoveryModalities=[];
  const pendingKeys = new Map();
  const button = (action,label,kind='primary') => `<button type="button" class="fx-button fx-${kind}" data-fx="${action}">${label}</button>`;
  const note = (title,copy) => `<div class="fx-note">${icon('info')}<div><strong>${title}</strong><p>${copy}</p></div></div>`;
  const canSave = () => !!(ready && status?.personal_login && status?.storage?.configured);
  const hasStoredData = () => !!(snapshot.profile || snapshot.consent);
  const hasRemoteState = () => hasStoredData() || remoteUncertain || canSave();
  const dirty = () => !!snapshot.profile && JSON.stringify(canonical(profile))!==JSON.stringify(canonical(snapshot.profile));
  const saveLabel = () => remoteUncertain?'Guardado sin confirmar · comprueba la conexión':saved?(dirty()?'Cambios sin guardar · la versión anterior sigue guardada':'Preferencias personales guardadas'):hasStoredData()?'Preferencias sin guardar · consentimiento registrado':'Preferencias aún no guardadas';
  function acceptSnapshot(state,replaceDraft=false){snapshot=clone(state);saved=!!snapshot.profile;remoteUncertain=false;if(replaceDraft){profile=snapshot.profile?clone(snapshot.profile):defaults();consentChecked=snapshot.consent?.granted===true;}}
  const commonTitle = (title,copy) => `<header class="fx-title"><p class="fx-eyebrow">ROXY HOME · EJERCICIO</p><h2 tabindex="-1">${title}</h2>${copy?`<p>${copy}</p>`:''}</header>`;
  function focusHeading(){root?.querySelector('h2')?.focus({preventScroll:true});root?.scrollIntoView({block:'start',behavior:'auto'});}
  function showFailure(message){failure=message;render();root?.querySelector('[role="alert"]')?.focus({preventScroll:true});}
  function setView(next) {view=next;failure='';notice='';render();focusHeading();}
  function validateDraft(){if(!validTimezone(profile.timezone)){showFailure('Revisa la zona horaria (ej. America/New_York) antes de continuar.');return false;}if(step===2){const error=validateAvailability(profile);if(error){showFailure(error);return false;}}return true;}
  async function request(path, method='GET', payload) {
    const requestGeneration=generation, parentSignal=abort.signal, controller=new AbortController();
    const headers={Accept:'application/json','Content-Type':'application/json'};
    if(path!=='/status')headers['X-Roxy-Fitness-Member']=context.identity;
    if(method!=='GET') {
      headers['X-Roxy-Fitness-Request']='1';
      const fingerprint=JSON.stringify([path,method,payload]);
      if(!pendingKeys.has(fingerprint))pendingKeys.set(fingerprint,crypto.randomUUID());
      headers['Idempotency-Key']=pendingKeys.get(fingerprint);
      // A lost response is not proof that the server did not commit the write.
      remoteUncertain=true;
    }
    let timeout, stop;
    const stopped=()=>{const error=new Error('La consulta se canceló.');error.name='AbortError';return error;};
    const deadline=new Promise((_,reject)=>{
      stop=()=>{controller.abort();reject(stopped());};
      parentSignal.addEventListener('abort',stop,{once:true});
      if(parentSignal.aborted){stop();return;}
      timeout=setTimeout(()=>{controller.abort();reject(new Error('La conexión tardó demasiado. Vuelve a comprobar antes de dar por guardados tus cambios.'));},12000);
    });
    let response,result;
    try{
      ({response,result}=await Promise.race([deadline,(async()=>{
        const response=await fetch('/api/fitness/v1'+path,{credentials:'same-origin',cache:'no-store',method,headers,body:payload===undefined?undefined:JSON.stringify(payload),signal:controller.signal});
        return {response,result:await response.json().catch(()=>({}))};
      })()]));
    }finally{clearTimeout(timeout);parentSignal.removeEventListener('abort',stop);}
    if(requestGeneration!==generation||parentSignal.aborted)throw stopped();
    if(!response.ok){const e=new Error(typeof result.detail==='string'?result.detail:result.detail?.message || 'No pude confirmar la operación. Revisa tu conexión e inténtalo de nuevo.');e.status=response.status;e.code=result.detail?.code;if(e.code==='identity_changed'||e.code==='personal_login_required'||e.status===401){profile=defaults();snapshot={version:0,profile:null,consent:null};saved=false;ready=false;consentChecked=false;remoteUncertain=false;view='welcome';checkingIdentity=true;scope.RoxyFitnessPrograms?.clear();scope.RoxyFitnessPlanner?.clear();scope.RoxyFitnessMeasurements?.clear();}throw e;}
    return result;
  }
  async function load(preserveDraft=false) {
    if(preserveDraft && view==='onboarding')collect();
    const token=generation;busy=true;checkingIdentity=true;failure='';scope.RoxyFitnessPrograms?.setActive(false);scope.RoxyFitnessPlanner?.setActive(false);scope.RoxyFitnessMeasurements?.setActive(false);render();
    try {
      const meta=await request('/status');if(token!==generation)return;
      if(!meta||typeof meta.personal_login!=='boolean'||!meta.storage||typeof meta.storage.configured!=='boolean'||(meta.personal_login&&(typeof meta.member_id!=='string'||!meta.member_id.trim())))throw new Error('No pude verificar quién tiene la sesión abierta. Vuelve a comprobar la conexión.');
      if(meta.personal_login && meta.member_id!==context.identity){profile=defaults();snapshot={version:0,profile:null,consent:null};saved=false;ready=false;consentChecked=false;remoteUncertain=false;view='welcome';throw new Error('Cambió la persona conectada. Recarga Roxy Home para abrir su espacio privado.');}
      // A shared/expired session cannot prove ownership of even an unsaved draft.
      if(!meta.personal_login){profile=defaults();snapshot={version:0,profile:null,consent:null};saved=false;ready=false;consentChecked=false;ageOutside=false;remoteUncertain=false;view='welcome';pendingKeys.clear();scope.RoxyFitnessPrograms?.clear();scope.RoxyFitnessPlanner?.clear();scope.RoxyFitnessMeasurements?.clear();}
      status=meta;ready=false;checkingIdentity=false;
      if(meta.personal_login && meta.storage.configured) {
        const state=await request('/me/profile');if(token!==generation)return;
        acceptSnapshot(state,!preserveDraft);ready=true;
        if(state.profile && !preserveDraft && !scope.RoxyFitnessWorld)view='space';
      }
    } catch(e){if(e.name!=='AbortError'&&token===generation){failure=e.message;if(e.status===401||e.status===403){profile=defaults();snapshot={version:0,profile:null,consent:null};saved=false;ready=false;consentChecked=false;view='welcome';}}}
    finally {if(token===generation){busy=false;if(!checkingIdentity&&moduleActive)scope.RoxyFitnessPrograms?.setActive(true);render();}}
  }
  function welcome() {
    return `<div class="fx-welcome"><figure class="fx-welcome-photo"><img src="/assets/roxy_home/fitness/roxy-fitness-welcome.jpg" alt="Roxy te da la bienvenida a un espacio de ejercicio en casa"/><figcaption>Imagen ilustrativa · no es una demostración técnica</figcaption></figure><div class="fx-welcome-copy"><span class="fx-pill">Un espacio para ti</span>${commonTitle('Haz espacio<br>para moverte.','Explora un programa general, elige tus días y consulta la guía de cada fecha.')}<div class="fx-benefits"><p>${icon('event_available')}Una agenda con fechas que tú eliges</p><p>${icon('menu_book')}Movimientos explicados y procedencia consultable</p><p>${icon('restaurant')}Las recetas de tu hogar, en el mismo lugar</p></div>${button('week',(scope.RoxyFitnessPlanner?'Crear o ver mi plan':'Organizar mis días')+' '+icon('arrow_forward'))}${button('start','Preparar mis preferencias','secondary')}${button('explore','Explorar primero','text')}<p class="fx-caption">${scope.RoxyFitnessPlanner?'Guarda tus actividades, llévalas al calendario cuando lo decidas y registra cómo te fue.':'La selección de días es temporal. Puedes reservar cada actividad en Calendario y confirmarla para conservarla. El entrenamiento personalizado sigue pendiente.'}</p></div></div>`;
  }
  const options = (values,selected) => values.map(([value,label])=>`<option value="${value}" ${value===selected?'selected':''}>${label}</option>`).join('');
  const select = (name,title,values,current) => `<label class="fx-field"><span>${title}</span><select name="${name}">${options(values,current)}</select></label>`;
  const checks = (name,values,selected) => `<div class="fx-choices">${Object.entries(values).map(([key,label])=>`<label class="fx-chip"><input type="checkbox" name="${name}" value="${key}" ${selected.includes(key)?'checked':''}/><span>${label}</span></label>`).join('')}</div>`;
  function onboarding() {
    const titles=['A tu manera','¿Qué quieres conseguir?','Hagamos espacio en tu semana','¿Dónde te gustaría moverte?','Tú decides qué guardar'];
    const descriptions=['Solo lo necesario para empezar. Sin peso, fotos corporales ni fecha de nacimiento.','Elige lo más importante para ti. Puedes cambiarlo después.','Esto es disponibilidad, no una obligación de entrenar todos esos días.','Roxy no dará por hecho que tienes una máquina o un material.','Revisa tus preferencias. No son una evaluación de salud ni un plan de entrenamiento.'];
    let fields='';
    if(step===0) fields=`${select('age_band','Banda de edad',[['','Prefiero no indicarla todavía'],['18_29','18–29 años'],['30_44','30–44 años'],['45_64','45–64 años'],['65_plus','65 años o más'],['under18','Soy menor de 18 años']],ageOutside?'under18':profile.age_band||'')}<p class="fx-caption">Esta primera versión contempla adultos. Explorar no requiere declarar la edad.</p>${select('language','Idioma preferido del contenido',[['es','Español'],['en','English']],profile.language)}<p class="fx-caption">La interfaz actual está en español; esta preferencia no traduce fuentes externas.</p><div class="fx-grid">${select('weight_unit','Unidad de peso',[['kg','Kilogramos'],['lb','Libras']],profile.weight_unit)}${select('length_unit','Unidad de altura',[['cm','Centímetros'],['ft_in','Pies y pulgadas']],profile.length_unit)}</div><label class="fx-field"><span>Zona horaria</span><input name="timezone" value="${esc(profile.timezone)}" required maxlength="64"/><small>Detectada en este dispositivo; puedes corregirla (ej. America/New_York).</small></label>`;
    if(step===1) fields=`<fieldset class="fx-goals"><legend class="fx-sr">Objetivo principal</legend>${Object.entries(GOALS).map(([key,[glyph,title,copy]])=>`<label class="fx-goal"><input type="radio" name="primary_goal" value="${key}" ${profile.primary_goal===key?'checked':''}/>${icon(glyph)}<span><strong>${title}</strong><small>${copy}</small></span></label>`).join('')}</fieldset><label class="fx-check"><input name="without_weight_or_calories" type="checkbox" ${profile.without_weight_or_calories?'checked':''}/><span>Prefiero una experiencia sin peso ni calorías</span></label>`;
    if(step===2) fields=`<fieldset><legend>Días disponibles</legend>${checks('days',Object.fromEntries(DAYS),profile.availability.map(x=>x.day))}</fieldset><div class="fx-grid"><label class="fx-field"><span>Máximo por sesión (min)</span><input name="session_minutes" type="number" min="5" max="180" step="1" value="${profile.session_minutes??''}" placeholder="Sin definir"/></label><label class="fx-field"><span>Desplazamiento total (min)</span><input name="travel_minutes" type="number" min="0" max="180" step="1" value="${profile.travel_minutes}"/></label></div><div id="fxWindows">${windows()}</div><p class="fx-caption">Cada ventana incluye el desplazamiento. Los minutos de viaje no cuentan como ejercicio.</p>`;
    if(step===3) fields=`${select('experience','Experiencia reciente',[['prefer_not_to_say','Todavía no quiero indicarla'],['beginner','Estoy empezando o retomando'],['intermediate','Entreno con regularidad']],profile.experience)}<fieldset><legend>Lugares que sí puedo usar</legend>${checks('locations',LOCATIONS,profile.locations)}</fieldset><fieldset><legend>Material que he confirmado</legend>${checks('equipment',EQUIPMENT,profile.equipment)}</fieldset><p class="fx-caption">Confirmar máquinas indica disponibilidad, no su modelo ni sus ajustes. Eso necesita una ficha específica antes de usarlas.</p>`;
    if(step===4) fields=`${summary()}${ageOutside?note('Alcance para adultos','Puedes consultar información general, pero esta versión no prepara entrenamientos para menores.'):''}${canSave()?`<label class="fx-check"><input type="checkbox" name="consent" ${consentChecked?'checked':''}/><span>Autorizo guardar estas preferencias de Ejercicio en mi perfil personal para organizar este espacio. Puedo retirarlas desde Ajustes de Ejercicio.</span></label><p class="fx-caption">Consentimiento fitness-preferences-v1. No compartimos estas preferencias con otros miembros del hogar ni con afiliados. No incluye historiales médicos, reloj ni fotografías.</p>`:note('Vista previa · sin guardar','Estas selecciones permanecen únicamente mientras esta página está abierta. No se guardan en el hogar ni se envían a proveedores. Se perderán al recargar o cerrar la página.')}<p class="fx-caption">Antes de activar entrenamientos hacen falta contenido autorizado y revisión profesional. No se programará nada en tu calendario.</p>`;
    return `<div class="fx-onboarding"><div class="fx-topline">${button('back',icon('arrow_back')+' Atrás','text')}<span>Paso ${step+1} de 5</span></div><div class="fx-progress" data-progress="${step+1}" role="progressbar" aria-label="Registro de preferencias" aria-valuemin="0" aria-valuemax="5" aria-valuenow="${step+1}"><span></span></div>${commonTitle(titles[step],descriptions[step])}<form id="fxForm">${fields}<div class="fx-form-footer"><button class="fx-button fx-primary" type="submit" ${busy?'disabled':''}>${busy?'Comprobando…':step<4?'Continuar':canSave()?'Guardar mis preferencias':'Ver mi espacio · sin guardar'}${icon('arrow_forward')}</button>${button('skip',step<4?'Explorar sin completar':'Explorar sin guardar cambios','text')}</div></form></div>`;
  }
  function windows() {
    return profile.availability.map(row=>`<fieldset class="fx-window"><legend>${DAYS.find(x=>x[0]===row.day)[1]}</legend>${row.windows.map((win,index)=>`<div class="fx-grid">${['start','end'].map((part,i)=>`<label class="fx-field"><span>${i?'Hasta':'Desde'} · ventana ${index+1}</span><input type="time" data-day="${row.day}" data-window="${index}" data-time="${part}" value="${esc(win[part])}" required/></label>`).join('')}</div>${row.windows.length>1?`<button type="button" class="fx-button fx-text" data-fx-remove-window="${index}" data-day="${row.day}">Quitar ventana ${index+1}</button>`:''}`).join('')}${row.windows.length<4?`<button type="button" class="fx-button fx-text" data-fx-add-window="${row.day}">Añadir otra ventana</button>`:''}</fieldset>`).join('');
  }
  function collect() {
    const form=root.querySelector('#fxForm');if(!form)return;
    const data=new FormData(form), values=name=>data.getAll(name);
    if(step===0){ageOutside=data.get('age_band')==='under18';profile.age_band=ageOutside?null:data.get('age_band')||null;for(const name of ['language','weight_unit','length_unit','timezone'])profile[name]=String(data.get(name)).trim();}
    if(step===1){profile.primary_goal=data.get('primary_goal')||null;profile.without_weight_or_calories=data.has('without_weight_or_calories');}
    if(step===2){profile.session_minutes=data.get('session_minutes')?Number(data.get('session_minutes')):null;profile.travel_minutes=Number(data.get('travel_minutes')||0);profile.availability=values('days').map(day=>{const existing=profile.availability.find(row=>row.day===day);return {day,windows:(existing?.windows||[{start:'18:00',end:'19:00'}]).map((win,index)=>({start:form.querySelector(`[data-day="${day}"][data-window="${index}"][data-time="start"]`)?.value??win.start,end:form.querySelector(`[data-day="${day}"][data-window="${index}"][data-time="end"]`)?.value??win.end}))};});}
    if(step===3){profile.experience=data.get('experience');profile.locations=values('locations');profile.equipment=values('equipment');}
    if(step===4 && canSave())consentChecked=data.has('consent');
  }
  function summary() {
    return `<dl class="fx-summary"><div><dt>Tu objetivo</dt><dd>${GOALS[profile.primary_goal]?.[1]||'Por definir'}</dd></div><div><dt>Tiempo disponible</dt><dd>${profile.availability.length?profile.availability.map(x=>DAYS.find(d=>d[0]===x.day)[1]).join(' · '):'Días por definir'}${profile.session_minutes?' · hasta '+profile.session_minutes+' min':''}</dd></div><div><dt>Tu espacio</dt><dd>${profile.locations.map(x=>LOCATIONS[x]).join(' · ')||'Por definir'}</dd></div><div><dt>Material confirmado</dt><dd>${profile.equipment.map(x=>EQUIPMENT[x]).join(' · ')||'Todavía no indicado'}</dd></div></dl>`;
  }
  function education() {
    const links=status?.education||[];
    return `<div class="fx-education">${links.map(source=>`<a class="fx-resource" href="${esc(source.url)}" target="_blank" rel="noopener noreferrer"><span class="fx-source-name">${esc(source.publisher)}</span><span><strong>${esc(source.title)}</strong><small>${esc(source.summary)} Fuente en inglés · abre otra página.</small></span>${icon('arrow_outward')}</a>`).join('') || '<p>No se pudieron cargar las fuentes. Puedes volver a comprobar la conexión.</p>'}</div>`;
  }
  function week() {
    const timezone=validTimezone(profile.timezone)?profile.timezone:'UTC';
    const dates=weekDates(timezone);const chosen=dates.find(x=>x.key===selectedDay)||dates[0];
    const available=profile.availability.find(x=>x.day===chosen.key);
    return `${timezone!==profile.timezone?note('Revisa tu zona horaria','La zona indicada no es válida. Esta semana se muestra provisionalmente en UTC; no hemos cambiado tu preferencia. Corrígela en Ajustes.'):''}<section class="fx-week"><div class="fx-topline"><h3>Mi semana</h3>${icon('calendar_month')}</div><p class="fx-caption">${esc(dates[0].date)} — ${esc(dates[6].date)} · ${esc(timezone)}</p><div class="fx-days" aria-label="Día de la semana">${dates.map(day=>`<button type="button" data-fx-day="${day.key}" aria-pressed="${day.key===chosen.key}"><small>${day.label}</small><strong>${day.number}</strong><span class="fx-day-dot ${profile.availability.some(x=>x.day===day.key)?'available':''}"></span></button>`).join('')}</div><div class="fx-day-detail"><span class="fx-eyebrow">${available?'DISPONIBILIDAD DECLARADA':'SIN HORARIO DEFINIDO'}</span><h3>${available?available.windows.map(w=>esc(w.start)+'–'+esc(w.end)).join(' · '):'Un día abierto'}</h3><p>${available?'Es tiempo que podrías reservar. Aún no hay una sesión asignada.':'No tienes que llenar todos los días. Puedes añadir disponibilidad cuando la necesites.'}</p></div></section>`;
  }
  let measurementsOpen=false;
  const showMeasurements=()=>!profile.without_weight_or_calories||measurementsOpen;
  function space() {
    const tabs=[['today','Hoy'],['week',scope.RoxyFitnessPlanner?'Mi plan':'Mi semana'],['training','Rutinas'],['library','Ejercicios'],['progress','Progreso'],['food','Alimentación'],['services','Servicios']];
    let content='';
    if(section==='today')content=`${scope.RoxyFitnessPlanner?'<div id="fxPlanner"></div><details class="fxpl-source-guides"><summary>Consultar guías sin guardarlas</summary><div id="fxPrograms"></div></details>':'<div id="fxPrograms"><p role="status">Cargando programas de movimiento…</p></div>'}<details class="fx-preferences-detail"><summary>Mis preferencias de Ejercicio</summary>${summary()}${button('edit','Ajustar mis preferencias','secondary')}${note('Rutinas que encajan contigo','En Rutinas puedes elegir casa o gimnasio, revisar el material y los movimientos, y preparar fechas con tu disponibilidad. La adaptación a lesiones todavía no está disponible.')}</details>`;
    if(section==='week')content=`${scope.RoxyFitnessPlanner?'<div id="fxPlanner"></div><details class="fxpl-source-guides"><summary>Consultar guías sin guardarlas</summary><div id="fxPrograms"></div></details>':'<div id="fxPrograms"><p role="status">Cargando programas de movimiento…</p></div>'}<details class="fx-preferences-detail"><summary>Mi disponibilidad declarada</summary>${week()}${button('edit-time','Cambiar mi disponibilidad','secondary')}${note('Organiza tus próximos días','Usa «Organizar con mi disponibilidad» para proponer fechas a las guías que elijas. Revisa y confirma la agenda antes de guardarla.')}</details>`;
    if(section==='training')content='<div id="fxTraining"></div>';
    if(section==='library')content=`<div id="fxLibrary"><p role="status">Cargando biblioteca de movimientos…</p></div><h3>Conoce las bases</h3>${education()}`;
    if(section==='progress')content=scope.RoxyFitnessPlanner?'<div id="fxTrainingProgress"></div><div id="fxPlanner"></div>'+(showMeasurements()?'<div id="fxMeasurements"></div>':`<section class="fx-empty"><h3>A tu manera</h3><p>Elegiste una experiencia sin peso ni calorías. Puedes mantenerla así o abrir tus mediciones opcionales cuando quieras.</p>${button('show-measurements','Abrir mediciones opcionales','secondary')}</section>`):`<article class="fx-empty">${icon('insights')}<h3>Tu historia empieza contigo</h3><p>Todavía no hay sesiones realizadas ni mediciones. Cuando existan registros, verás su fecha y si son declarados, medidos o estimados.</p>${button('week','Ver mi disponibilidad','secondary')}</article>${note('Sin números de muestra','No hay calorías, peso o porcentajes de progreso inventados. Tampoco hay un reloj conectado.')}`;
    if(section==='food')content=`<article class="fx-food"><span class="fx-eyebrow">UN SOLO RECETARIO</span><h3>Tu movimiento y tu cocina,<br>en la misma casa.</h3><p>Explora las recetas y el plan de comidas que ya tienes en Roxy Home. Tus objetivos personales no cambiarán la alimentación del resto del hogar.</p>${button('recipes','Explorar recetas '+icon('arrow_forward'))}${button('meal-plan','Ver el plan de comidas','secondary')}</article>${note('Tú confirmas los cambios','No calculamos un déficit, prescribimos suplementos ni añadimos ingredientes a Compra desde esta sección. Puedes usarla sin peso ni calorías.')}`;
    if(section==='services')content=`<article class="fx-empty">${icon('storefront')}<h3>Apoyo cuando lo necesites</h3><p>Gimnasios, profesionales y material tendrán su lugar aquí cuando podamos verificar la oferta y los acuerdos.</p><span class="fx-pill">Sin reservas ni afiliados activos</span></article><div class="fx-service-list"><div><strong>Gimnasios y clases</strong><p>Sin disponibilidad ni precios confirmados todavía.</p></div><div><strong>Equipo para tu espacio</strong><p>Se basará en el material que confirmes; no en una comisión.</p></div><div><strong>Alimentación primero</strong><p>No hay recomendación automática ni dosis de suplementos.</p></div></div>`;
    return `<header class="fx-space-head"><div><p class="fx-eyebrow">ROXY HOME · EJERCICIO</p><h2 tabindex="-1">Mi espacio</h2><p>${scope.RoxyFitnessPlanner?'Tu plan y tus registros son personales.':saveLabel()}</p></div><button type="button" data-fx="settings" class="fx-icon-button" aria-label="Ajustes de Ejercicio">${icon('tune')}</button></header><div class="fx-tabs" role="tablist" aria-label="Secciones de Ejercicio">${tabs.map(([key,label])=>`<button type="button" role="tab" id="fx-tab-${key}" aria-controls="fx-content" aria-selected="${section===key}" tabindex="${section===key?'0':'-1'}" data-fx-tab="${key}">${label}</button>`).join('')}</div><div id="fx-content" role="tabpanel" aria-labelledby="fx-tab-${section}" tabindex="0">${content}</div>`;
  }
  function settings() {
    return `<div class="fx-onboarding">${button('space',icon('arrow_back')+' Mi espacio','text')}${commonTitle('Tu espacio, tus decisiones','Lo que compartes aquí no se convierte en el perfil nutricional del hogar.')}<p>${saveLabel()}</p>${summary()}${button('edit','Editar preferencias')}${hasRemoteState()?button('export','Descargar datos guardados','secondary'):''}${button('erase',hasRemoteState()?'Eliminar mis datos de Ejercicio y retirar consentimiento':'Descartar esta vista previa','secondary')}${button('welcome','Ver bienvenida','text')}<p class="fx-caption">${hasRemoteState()?'Comprobaremos el servidor antes de eliminar preferencias, plan, registros, mediciones y consentimiento de Ejercicio. Se conserva una versión técnica para evitar escrituras antiguas; las copias de seguridad siguen la retención de la infraestructura.':'No hay datos de Ejercicio guardados en el servidor. Cerrar o recargar la página descarta esta vista previa.'}</p><div id="fxDeleteConfirm" hidden>${note('¿Quieres continuar?',hasRemoteState()?'Se eliminarán tus preferencias, plan, registros y mediciones de Ejercicio, junto con su consentimiento. No se borran tus mascotas, recetas ni eventos del calendario del hogar.':'Se descartarán las selecciones de esta vista previa.')}${button('erase-confirm','Sí, eliminar','primary')}${button('erase-cancel','Cancelar','secondary')}</div></div>`;
  }
  function render() {
    if(!root)return;
    scope.RoxyFitnessWorld?.update({active:moduleActive,view,section,checking:checkingIdentity});
    if(!moduleActive){root.innerHTML='';return;}
    if(checkingIdentity||view!=='space'||section!=='library')scope.RoxyFitnessDiscovery?.clear();
    // Keep prior-member content out of the DOM until status confirms ownership.
    if(checkingIdentity){root.innerHTML=`<div class="fx-shell" aria-busy="${busy}">${commonTitle('Comprobando tu espacio privado','Verificamos la sesión antes de mostrar tus preferencias o tu agenda.')}<div class="fx-feedback" aria-live="polite">${busy?'<p role="status">Un momento…</p>':''}${failure?`<p role="alert" tabindex="-1" class="fx-error">${esc(failure)}</p>${button('retry','Volver a comprobar','secondary')}`:''}</div></div>`;return;}
    root.innerHTML=`<div class="fx-shell" aria-busy="${busy}">${view==='welcome'?welcome():view==='onboarding'?onboarding():view==='settings'?settings():space()}<div class="fx-feedback" aria-live="polite">${busy?'<p>Comprobando tu espacio privado…</p>':''}${failure?`<p role="alert" tabindex="-1" class="fx-error">${esc(failure)}</p>${button('retry','Volver a comprobar','secondary')}`:''}${notice?`<p>${esc(notice)}</p>`:''}</div>${!canSave()&&!(scope.RoxyFitnessPlanner&&view==='space')?`<p class="fx-storage-note">${icon('lock')}${status?.personal_login?'El guardado privado aún no está disponible.':'Para guardar necesitas un perfil personal y almacenamiento privado disponible.'} ${hasRemoteState()?'Hay un estado guardado o pendiente de confirmar. Revisa Ajustes antes de darlo por eliminado.':'La vista previa no guarda tus selecciones.'}</p>`:''}</div>`;
    scope.RoxyFitnessTraining?.setActive(view==='space'&&section==='training'&&moduleActive&&!checkingIdentity);
    if(view==='space'&&section==='training'&&moduleActive)scope.RoxyFitnessTraining?.mount(root.querySelector('#fxTraining'),{identity:context?.identity||'preview',timezone:profile.timezone,repeatSource:repeatTrainingSource,onRepeatConsumed:()=>{repeatTrainingSource=null;},onSchedule:payload=>{trainingProposal=payload;section='week';setView('space');},onPreferences:()=>{step=0;setView('onboarding');}});
    scope.RoxyFitnessPlanner?.setActive(view==='space'&&['today','week','progress'].includes(section)&&moduleActive&&!checkingIdentity);
    if(view==='space'&&['today','week','progress'].includes(section)&&moduleActive)scope.RoxyFitnessPlanner?.mount(root.querySelector('#fxPlanner'),{identity:context?.identity||'preview',timezone:profile.timezone,view:section,openSessionId:openTrainingSession,onSessionConsumed:()=>{openTrainingSession=null;},trainingProposal,onTrainingConsumed:()=>{trainingProposal=null;},onTraining:()=>{section='training';setView('space');},scheduleActivity:context?.scheduleActivity,onPreferences:()=>{step=2;setView('onboarding');}});
    scope.RoxyFitnessProgress?.setActive(view==='space'&&section==='progress'&&moduleActive&&!checkingIdentity);
    if(view==='space'&&section==='progress'&&moduleActive)scope.RoxyFitnessProgress?.mount(root.querySelector('#fxTrainingProgress'),{identity:context?.identity||'preview',timezone:profile.timezone,onRepeat:source=>{repeatTrainingSource=source;section='training';setView('space');},onOpenSession:sessionId=>{openTrainingSession=sessionId;section='week';setView('space');}});
    scope.RoxyFitnessMeasurements?.setActive(view==='space'&&section==='progress'&&moduleActive&&!checkingIdentity&&showMeasurements());
    if(view==='space'&&section==='progress'&&moduleActive&&showMeasurements())scope.RoxyFitnessMeasurements?.mount(root.querySelector('#fxMeasurements'),{identity:context?.identity||'preview',timezone:profile.timezone,weightUnit:profile.weight_unit,heightUnit:profile.length_unit,onPreferences:()=>{step=0;setView('onboarding');}});
    if(view==='space'&&section==='library'){if(scope.RoxyFitnessDiscovery)scope.RoxyFitnessDiscovery.mount(root.querySelector('#fxLibrary'),{identity:context?.identity||'preview',timezone:profile.timezone,scheduleActivity:context?.scheduleActivity,initialModalities:discoveryModalities,onPreferences:()=>{step=0;setView('onboarding');}});else scope.RoxyFitnessLibrary?.mount(root.querySelector('#fxLibrary'));}
    if(view==='space'&&['today','week'].includes(section)&&moduleActive)scope.RoxyFitnessPrograms?.mount(root.querySelector('#fxPrograms'),{identity:context?.identity||'preview',timezone:profile.timezone,view:section,scheduleActivity:context?.scheduleActivity});
    if(view==='settings'||(view==='onboarding'&&step===4))root.querySelector('.fx-onboarding')?.insertAdjacentHTML?.('beforeend','<p class="fx-caption"><a href="/privacy#ejercicio" target="_blank" rel="noopener noreferrer">Cómo protegemos tus datos de Ejercicio</a></p>');
    if(busy)root.querySelectorAll('button,input,select,textarea').forEach(control=>{control.disabled=true;});
  }
  async function submit(event) {
    if(event.target?.id!=='fxForm')return;
    event.preventDefault();if(busy)return;collect();failure='';notice='';
    if(!validateDraft())return;
    if(step<4){step++;render();focusHeading();return;}
    if(ageOutside&&canSave()){showFailure('Esta versión guarda preferencias solo para adultos. Puedes explorar sin guardarlas.');return;}
    if(!canSave()){setView('space');return;}
    if(!consentChecked){showFailure('Decide si autorizas guardar tus preferencias. También puedes explorar sin guardarlas.');return;}
    const token=generation;let completed=false;busy=true;render();
    try{
      if(remoteUncertain){const current=await request('/me/profile');if(token!==generation)return;acceptSnapshot(current);}
      if(!snapshot.consent?.granted){const state=await request('/me/consents','POST',{expected_version:snapshot.version,consent:{purpose:'fitness_preferences',text_version:'fitness-preferences-v1',granted:true}});if(token!==generation)return;acceptSnapshot(state);}
      const state=await request('/me/profile','PATCH',{expected_version:snapshot.version,profile});if(token!==generation)return;
      acceptSnapshot(state,true);completed=true;setView('space');notice='Tus preferencias quedaron guardadas solo en tu perfil. No se activó un entrenamiento.';
    }catch(e){if(e.name!=='AbortError'&&token===generation)failure=e.message;}
    finally{if(token===generation){busy=false;render();if(completed)focusHeading();else if(failure)root.querySelector('[role="alert"]')?.focus({preventScroll:true});}}
  }
  async function erase() {
    if(busy)return;
    const token=generation,verifyRemote=canSave()||hasRemoteState();let completed=false;busy=true;render();
    try{
      // Reconcile even a consent-only or ambiguous failed save before claiming removal.
      if(verifyRemote){
        const current=await request('/me/profile');if(token!==generation)return;acceptSnapshot(current);
        const state=await request('/me/data','DELETE',{expected_version:snapshot.version,confirm_delete:true});if(token!==generation)return;acceptSnapshot(state);if(hasStoredData())throw new Error('El servidor todavía informa datos activos.');
      }
      profile=defaults();saved=false;consentChecked=false;ageOutside=false;remoteUncertain=false;pendingKeys.clear();completed=true;setView('welcome');notice=verifyRemote?'El servidor confirmó la eliminación de tus datos activos de Ejercicio y su consentimiento. No se modificó el hogar.':'Vista previa descartada. No se modificó el hogar.';
    }catch(e){if(e.name!=='AbortError'&&token===generation)failure='No pude confirmar la retirada. No des tus datos por eliminados todavía. '+e.message;}
    finally{if(token===generation){busy=false;render();if(completed)focusHeading();else if(failure)root.querySelector('[role="alert"]')?.focus({preventScroll:true});}}
  }
  async function exportData() {
    if(busy||!hasRemoteState())return;
    const token=generation;busy=true;render();
    try{const data=await request('/me/data');if(token!==generation)return;const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='mis-datos-ejercicio.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notice='Descarga preparada: contiene tus datos guardados de Ejercicio, no los cambios sin guardar.';}catch(e){if(e.name!=='AbortError'&&token===generation)failure=e.message;}
    finally{if(token===generation){busy=false;render();}}
  }
  function click(event) {
    const target=event.target.closest('button');if(!target||busy)return;
    if(checkingIdentity&&target.dataset.fx!=='retry')return;
    if(target.dataset.fxAddWindow){collect();const row=profile.availability.find(x=>x.day===target.dataset.fxAddWindow);if(row&&row.windows.length<4){row.windows.push({start:'',end:''});root.querySelector('#fxWindows').innerHTML=windows();root.querySelector(`[data-day="${row.day}"][data-window="${row.windows.length-1}"][data-time="start"]`)?.focus();}return;}
    if(target.dataset.fxRemoveWindow!==undefined){collect();const row=profile.availability.find(x=>x.day===target.dataset.day);if(row&&row.windows.length>1){row.windows.splice(Number(target.dataset.fxRemoveWindow),1);root.querySelector('#fxWindows').innerHTML=windows();root.querySelector(`[data-day="${row.day}"][data-window="0"][data-time="start"]`)?.focus();}return;}
    if(target.dataset.fxTab){section=target.dataset.fxTab;render();root.querySelector(`#fx-tab-${section}`)?.focus({preventScroll:true});return;}
    if(target.dataset.fxDay){selectedDay=target.dataset.fxDay;render();root.querySelector(`[data-fx-day="${selectedDay}"]`)?.focus({preventScroll:true});return;}
    switch(target.dataset.fx){
      case 'show-measurements':measurementsOpen=true;render();break;
      case 'start':case 'edit':step=0;setView('onboarding');break;
      case 'edit-time':step=2;setView('onboarding');break;
      case 'back':collect();if(!validateDraft())break;if(step){step--;render();focusHeading();}else setView('welcome');break;
      case 'explore':case 'skip':collect();if(validateDraft())setView('space');break;
      case 'space':setView('space');break;
      case 'welcome':setView('welcome');break;
      case 'settings':setView('settings');break;
      case 'week':section='week';setView('space');break;
      case 'recipes':context.navigate('recipes');break;
      case 'meal-plan':context.navigate('today');break;
      case 'retry':void load(true);break;
      case 'export':void exportData();break;
      case 'erase':root.querySelector('#fxDeleteConfirm').hidden=false;root.querySelector('[data-fx="erase-confirm"]').focus();break;
      case 'erase-cancel':root.querySelector('#fxDeleteConfirm').hidden=true;root.querySelector('[data-fx="erase"]').focus();break;
      case 'erase-confirm':void erase();break;
    }
  }
  function change(event) {
    if(busy)return;
    if(event.target.name==='days'){collect();const node=root.querySelector('#fxWindows');node.innerHTML=windows();}
  }
  function keys(event) {
    if(event.target.getAttribute('role')!=='tab')return;
    const tabs=[...root.querySelectorAll('[role="tab"]')];let i=tabs.indexOf(event.target);
    if(event.key==='ArrowRight')i=(i+1)%tabs.length;else if(event.key==='ArrowLeft')i=(i+tabs.length-1)%tabs.length;else if(event.key==='Home')i=0;else if(event.key==='End')i=tabs.length-1;else return;
    event.preventDefault();tabs[i].click();
  }
  function reset() {
    scope.RoxyFitnessWorld?.reset();discoveryModalities=[];measurementsOpen=false;trainingProposal=null;repeatTrainingSource=null;openTrainingSession=null;scope.RoxyFitnessProgress?.clear();scope.RoxyFitnessTraining?.clear();scope.RoxyFitnessTrainingSession?.clear();
    scope.RoxyFitnessPlanner?.clear();scope.RoxyFitnessMeasurements?.clear();
    abort?.abort();generation++;abort=new AbortController();profile=defaults();snapshot={version:0,profile:null,consent:null};status=null;ready=false;saved=false;busy=false;notice='';failure='';consentChecked=false;ageOutside=false;remoteUncertain=false;checkingIdentity=false;view='welcome';step=0;section='today';selectedDay='mon';pendingKeys.clear();
  }
  function openWorld(next,modalities=[]) {
    if(checkingIdentity||busy)return;
    if(view==='onboarding'){collect();if(!validateDraft())return;}
    if(next==='room'){setView('welcome');return;}
    if(next==='preferences'){step=0;setView('onboarding');return;}
    if(!['today','week','training','library','progress'].includes(next))return;
    discoveryModalities=Array.isArray(modalities)?modalities.filter(v=>['yoga','pilates','strength','calisthenics'].includes(v)):[];
    if(next==='library')scope.RoxyFitnessDiscovery?.clear();
    section=next;setView('space');
  }
  function mount(node,options) {
    node=scope.RoxyFitnessWorld?.mount(node,{identity:options.identity,open:openWorld,exit:panel=>context?.navigate(panel)})||node;
    const changedRoot=root!==node;
    if(root!==node){root?.removeEventListener('click',click);root?.removeEventListener('submit',submit);root?.removeEventListener('change',change);root?.removeEventListener('keydown',keys);root=node;root.addEventListener('click',click);root.addEventListener('submit',submit);root.addEventListener('change',change);root.addEventListener('keydown',keys);}
    context=options;const key=options.identity||'preview';
    scope.RoxyFitnessWorld?.update({active:moduleActive,view,section,checking:checkingIdentity});
    if(identity!==key||!abort){identity=key;reset();void load();}else if(changedRoot)render();
  }
  function setActive(value) {
    const next=value===true;
    if(next===moduleActive)return;
    // Capture the current step while its fields and original save state exist.
    if(!next&&view==='onboarding'&&!busy&&!checkingIdentity)collect();
    moduleActive=next;scope.RoxyFitnessWorld?.setActive(next);
    if(!next){trainingProposal=null;repeatTrainingSource=null;openTrainingSession=null;scope.RoxyFitnessProgress?.setActive(false);scope.RoxyFitnessTraining?.setActive(false);scope.RoxyFitnessTrainingSession?.setActive(false);measurementsOpen=false;scope.RoxyFitnessPrograms?.setActive(false);scope.RoxyFitnessPlanner?.setActive(false);scope.RoxyFitnessMeasurements?.setActive(false);abort?.abort();generation++;busy=false;ready=false;checkingIdentity=true;scope.RoxyFitnessDiscovery?.clear();scope.RoxyFitnessLibrary?.clear();if(root)root.innerHTML='';return;}
    if(root&&context){abort=new AbortController();void load(true);}
  }
  function clear() {identity=null;reset();scope.RoxyFitnessDiscovery?.clear();scope.RoxyFitnessLibrary?.clear();scope.RoxyFitnessPrograms?.clear();scope.RoxyFitnessPlanner?.clear();scope.RoxyFitnessMeasurements?.clear();render();}
  scope.RoxyFitness={mount,clear,setActive};
  if(typeof module!=='undefined')module.exports={weekDates,validateAvailability,defaults,esc,validTimezone};
  scope.addEventListener?.('pagehide',()=>{pageSuspended=!!root;clear();});
  scope.addEventListener?.('pageshow',event=>{if(event.persisted&&pageSuspended&&root&&context){pageSuspended=false;identity=context.identity||'preview';reset();void load();}});
})(typeof window!=='undefined'?window:globalThis);
