/* Roxy Home: sourced classes and existing movement libraries. No profile inference. */
((scope) => {
  'use strict';
  const MODALITIES = {yoga:['self_improvement','Yoga'],pilates:['accessibility_new','Pilates'],cardio:['directions_run','Cardio y baile'],strength:['fitness_center','Fuerza'],calisthenics:['exercise','Calistenia'],mobility:['accessibility','Movilidad'],balance:['balance','Equilibrio']};
  const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const icon = name => `<span class="material-symbols-rounded" aria-hidden="true">${name}</span>`;
  const fold = v => String(v??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  function safeSource(value) {
    try {const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password&&!u.port&&!u.search&&!u.hash&&((u.hostname==='www.nhs.uk'&&u.pathname.startsWith('/live-well/exercise/'))||(u.hostname==='www.mayoclinic.org'&&u.pathname.startsWith('/healthy-lifestyle/fitness/')))?u.href:'';} catch (_) {return '';}
  }
  const textOK=(v,max=2000)=>typeof v==='string'&&v.trim().length>0&&v.length<=max;
  function validate(payload) {
    if(payload?.clinical_approval!==false||payload?.can_activate_plans!==false||payload?.status!=='external_original_classes'||!Array.isArray(payload.classes)||payload.count!==payload.classes.length||payload.classes.length>100)throw new Error('No pude verificar las clases. Intenta cargar otra vez.');
    const ids=new Set();
    for(const e of payload.classes) {
      if(!e||typeof e.id!=='string'||!/^[a-z0-9-]{3,90}$/.test(e.id)||ids.has(e.id)||!e.title_es||!e.description_es||!safeSource(e.source_url)||!Array.isArray(e.modalities)||!e.modalities.length||e.modalities.some(m=>!MODALITIES[m])||!['en','es'].includes(e.language)||e.media_mode!=='external_link'||e.embed_url!==null||e.clinical_approval!==false||e.can_activate_plans!==false||!Array.isArray(e.equipment)||(e.duration_minutes!==null&&(!Number.isInteger(e.duration_minutes)||e.duration_minutes<=0||e.duration_minutes>180)))throw new Error('No pude verificar las clases. Intenta cargar otra vez.');
      if(!['class','technique'].includes(e.format)||!['title_es','description_es','creator','publisher'].every(key=>textOK(e[key]))||!MODALITIES[e.modality]||!e.modalities.includes(e.modality)||e.equipment.some(x=>!x||!textOK(x.name_es,200)||!['required','optional'].includes(x.requirement))||(e.duration_note_es!=null&&!textOK(e.duration_note_es))||(e.source_notes_es!==undefined&&(!Array.isArray(e.source_notes_es)||e.source_notes_es.some(x=>!textOK(x)))))throw new Error('No pude verificar las clases. Intenta cargar otra vez.');
      ids.add(e.id);
    }
    return payload.classes;
  }
  function select(entries, filters={}) {
    const words=fold(filters.query).trim().split(/\s+/).filter(Boolean),limit=Number(filters.minutes)||0;
    return entries.filter(e=>(!filters.modality||e.modalities.includes(filters.modality))&&(!filters.modalities?.length||filters.modalities.some(m=>e.modalities.includes(m)))&&(!filters.language||e.language===filters.language)&&(!limit||(Number.isInteger(e.duration_minutes)&&e.duration_minutes<=limit))&&words.every(w=>fold([e.title_es,e.description_es,...e.modalities.map(m=>MODALITIES[m][1])].join(' ')).includes(w)));
  }
  function card(e) {
    const kind=e.format==='class'?'Clase completa':'Demostración';
    return `<article class="fd-class"><div class="fd-card-top">${icon(MODALITIES[e.modality]?.[0]||'play_circle')}<span>${esc(kind)} · ${e.duration_minutes===null?'Duración sin confirmar':`${e.duration_minutes} min`}</span></div><h4>${esc(e.title_es)}</h4><p>${esc(e.description_es)}</p>${e.level==='basic_fitness'?'<p class="fd-level">La fuente requiere una base de condición física.</p>':e.level==='basic_experience'?'<p class="fd-level">Requiere experiencia básica en esta disciplina.</p>':e.level==='beginner'?'<p class="fd-level">La fuente la presenta para principiantes.</p>':''}<div class="fd-facts"><span>${e.language==='es'?'Vídeo en español':'Vídeo original en inglés'}</span><span>${esc(e.creator||e.publisher)}</span></div>${e.equipment.length?`<p class="fd-equipment">Material mencionado: ${e.equipment.map(x=>`${esc(x.name_es)}${x.requirement==='optional'?' (opcional)':''}`).join(' · ')}</p>`:'<p class="fd-equipment">Revisa el material en la fuente antes de empezar.</p>'}${e.duration_note_es?`<p class="fd-equipment">${esc(e.duration_note_es)}</p>`:''}${e.source_notes_es?.length?`<details class="fd-source-notes"><summary>Antes de empezar</summary>${e.source_notes_es.map(n=>`<p>${esc(n)}</p>`).join('')}</details>`:''}<a class="fx-button fx-secondary" href="${esc(safeSource(e.source_url))}" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">${e.format==='class'?'Abrir clase original':'Ver demostración original'} ${icon('open_in_new')}</a></article>`;
  }
  let root=null,options={},controller=null,generation=0,entries=null,error='',loading=false,view='explore',limit=6;
  let filters={modality:'',minutes:'',language:'',query:''};
  function releaseChildren(){scope.RoxyFitnessLibrary?.clear();scope.RoxyFitnessPrograms?.clear();}
  function render() {
    if(!root)return;
    if(view==='movements'||view==='guides') {
      root.innerHTML=`<button type="button" class="fx-button fx-text" data-fd="explore">${icon('arrow_back')} Todas las modalidades</button><div id="fdExisting"></div>`;
      const node=root.querySelector('#fdExisting');
      if(view==='movements')scope.RoxyFitnessLibrary?.mount(node);
      else scope.RoxyFitnessPrograms?.mount(node,{identity:options.identity||'preview',timezone:options.timezone,view:'today',scheduleActivity:options.scheduleActivity});
      return;
    }
    const result=select(entries||[],filters),counts=Object.fromEntries(Object.keys(MODALITIES).map(m=>[m,(entries||[]).filter(e=>e.modalities.includes(m)).length]));
    root.innerHTML=`<div class="fd-discovery"><header class="fd-intro"><div><p class="fx-eyebrow">TU BIBLIOTECA DE MOVIMIENTO</p><h3>Elige cómo quieres moverte.</h3><p>Clases, demostraciones y guías para descubrir a tu ritmo.</p></div><img src="/assets/roxy_home/fitness/roxy-fitness-welcome.jpg" alt="Roxy en tu espacio de ejercicio" /></header><div class="fd-originals"><button type="button" data-fd="movements">${icon('fitness_center')}<span><strong>Fichas ilustradas</strong><small>Fuerza y variantes · indicaciones dentro de Roxy</small></span>${icon('arrow_forward')}</button><button type="button" data-fd="guides">${icon('route')}<span><strong>Guías paso a paso</strong><small>Fuerza suave, flexibilidad y equilibrio · español</small></span>${icon('arrow_forward')}</button></div><div class="fd-heading"><div><p class="fx-eyebrow">INSTRUCTORES Y FUENTES ORIGINALES</p><h3>Explora otras formas de entrenar</h3></div></div>${loading?'<p role="status">Comprobando las clases disponibles…</p>':error?`<p class="fx-error" role="alert">${esc(error)}</p><button type="button" class="fx-button fx-secondary" data-fd="retry">Volver a cargar las clases</button>`:`<div class="fd-modalities" aria-label="Modalidades"><button type="button" data-fd-modality="" aria-pressed="${!filters.modality&&!filters.modalities?.length}">Todas</button>${Object.entries(MODALITIES).filter(([key])=>counts[key]>0).map(([key,[symbol,title]])=>`<button type="button" data-fd-modality="${key}" aria-pressed="${filters.modality===key||filters.modalities?.includes(key)||false}">${icon(symbol)} ${title}<small>${counts[key]}</small></button>`).join('')}</div><form id="fdFilters"><label class="fx-field"><span>Buscar una clase o movimiento</span><input type="search" name="query" maxlength="100" placeholder="Yoga, silla, baile…" value="${esc(filters.query)}" /></label><div class="fx-grid"><label class="fx-field"><span>Tiempo que tienes</span><select name="minutes"><option value="">Cualquier duración</option>${[10,20,30,45,60].map(v=>`<option value="${v}" ${String(v)===filters.minutes?'selected':''}>Hasta ${v} minutos</option>`).join('')}</select></label><label class="fx-field"><span>Idioma del vídeo</span><select name="language"><option value="">Todos los idiomas</option><option value="es" ${filters.language==='es'?'selected':''}>Español</option><option value="en" ${filters.language==='en'?'selected':''}>Inglés</option></select></label></div><button type="submit" class="fx-button fx-primary">Aplicar mis filtros</button></form><p class="fd-result" role="status">${result.length} ${result.length===1?'recurso coincide':'recursos coinciden'} con tus filtros · ${entries.filter(e=>e.format==='class').length} clases y ${entries.filter(e=>e.format!=='class').length} demostraciones en esta colección</p><div class="fd-classes">${result.slice(0,limit).map(card).join('')}</div>${result.length>limit?'<button type="button" class="fx-button fx-secondary fd-more" data-fd="more">Ver más recursos</button>':''}${!result.length?'<div class="fx-empty"><h4>No hay recursos con esta combinación.</h4><p>Prueba otra duración o idioma. Las guías paso a paso de Roxy sí están en español.</p><button type="button" class="fx-button fx-secondary" data-fd="reset">Quitar filtros</button></div>':''}`}<details class="fd-details"><summary>Cómo elegir y qué está personalizado</summary><p>Esta biblioteca responde a tus filtros. Todavía no evalúa si un ejercicio es adecuado para tu edad, peso, capacidad o limitaciones. No asigna una rutina individual.</p><p>Las clases externas se abren en la página original; conservan su instructor, idioma y condiciones. Las fichas de Roxy mantienen sus fuentes y no se reemplazan por estos enlaces.</p><button type="button" class="fx-button fx-secondary" data-fd="preferences">Revisar mis preferencias</button></details></div>`;
  }
  async function load(){
    const token=++generation;controller?.abort();controller=new AbortController();loading=true;error='';render();
    try{const r=await fetch('/api/fitness/v1/classes',{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'},signal:controller.signal});if(!r.ok)throw new Error(r.status===401?'Inicia sesión para consultar las clases.':'No pude cargar las clases. Puedes seguir usando las fichas y guías.');const payload=await r.json();if(token!==generation)return;entries=validate(payload);}
    catch(e){if(token===generation&&e.name!=='AbortError')error=e instanceof TypeError?'No pude conectar. Revisa tu conexión y vuelve a intentarlo.':e.message;}
    finally{if(token===generation){loading=false;render();}}
  }
  function click(event){const b=event.target.closest('button');if(!b||!root?.contains(b))return;
    if(b.dataset.fdModality!==undefined){filters.modality=b.dataset.fdModality;filters.modalities=[];limit=6;render();root.querySelector(`[data-fd-modality="${filters.modality}"]`)?.focus();return;}
    if(['explore','movements','guides'].includes(b.dataset.fd)){releaseChildren();view=b.dataset.fd;render();root.querySelector('h3')?.focus();}
    else if(b.dataset.fd==='retry')void load();
    else if(b.dataset.fd==='more'){limit+=6;render();}
    else if(b.dataset.fd==='reset'){filters={modality:'',minutes:'',language:'',query:''};limit=6;render();}
    else if(b.dataset.fd==='preferences')options.onPreferences?.();
  }
  function submit(event){if(event.target.id!=='fdFilters')return;event.preventDefault();event.stopPropagation();const data=new FormData(event.target);filters={...filters,query:String(data.get('query')||'').slice(0,100),minutes:String(data.get('minutes')||''),language:String(data.get('language')||'')};limit=6;render();root.querySelector('.fd-result')?.scrollIntoView({block:'nearest'});}
  function mount(node,opts={}){if(!node||node===root)return;controller?.abort();generation++;if(root){root.removeEventListener('click',click);root.removeEventListener('submit',submit);root.replaceChildren();}root=node;options=opts;if(Array.isArray(opts.initialModalities))filters={...filters,modalities:opts.initialModalities.filter(m=>MODALITIES[m])};root.addEventListener('click',click);root.addEventListener('submit',submit);if(entries)render();else void load();}
  function clear(){controller?.abort();generation++;if(root){root.removeEventListener('click',click);root.removeEventListener('submit',submit);releaseChildren();root.replaceChildren();}root=null;options={};entries=null;loading=false;error='';view='explore';limit=6;filters={modality:'',minutes:'',language:'',query:''};}
  scope.RoxyFitnessDiscovery={mount,clear};
  if(typeof module!=='undefined')module.exports={safeSource,validate,select,card,MODALITIES};
})(typeof window!=='undefined'?window:globalThis);
