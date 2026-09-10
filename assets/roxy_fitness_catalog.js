/* Licensed educational originals only. No personal profile, prescriptions or AI. */
((scope)=>{
  'use strict';
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeLink=v=>/^https:\/\/(?:wger\.de|creativecommons\.org)(?:\/|$)/.test(String(v||''))?String(v):'';
  const safeImage=v=>/^https:\/\/wger\.de\/media\/[A-Za-z0-9_./%-]+\.(?:png|jpg|jpeg|webp)$/i.test(String(v||''))?String(v):'';
  const display=v=>({Arms:'Brazos',Chest:'Pecho',Legs:'Piernas',Back:'Espalda',Abs:'Abdominales',Shoulders:'Hombros',Barbell:'Barra',Dumbbell:'Mancuerna',Bench:'Banco','Incline bench':'Banco inclinado','Pull-up bar':'Barra de dominadas','SZ-Bar':'Barra EZ','Cable machine':'Máquina de poleas'}[v]||v);
  const fold=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const icon=v=>`<span class="material-symbols-rounded" aria-hidden="true">${v}</span>`;
  const link=(url,text)=>safeLink(url)?`<a href="${esc(safeLink(url))}" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">${esc(text)} ${icon('arrow_outward')}</a>`:esc(text);
  function selectEntries(entries,{query='',category='',equipment=''}={}){
    const words=fold(query).trim().split(/\s+/).filter(Boolean);
    return entries.filter(e=>(!category||e.category===category)&&(!equipment||e.equipment.some(x=>String(x.id)===equipment))&&words.every(word=>fold([e.name,e.category,display(e.category),...e.equipment.flatMap(x=>[x.name,display(x.name)])].join(' ')).includes(word)));
  }
  function validatedEntries(payload){
    if(payload?.status==='catalogue_unavailable'||payload?.clinical_approval!==false||payload?.can_activate_training!==false||!Array.isArray(payload?.entries))throw new Error('El catálogo no tiene un estado verificable.');
    const seen=new Set();
    return payload.entries.filter(e=>{
      if(!e||typeof e.id!=='string'||!/^wger-[A-Za-z0-9-]+$/.test(e.id)||seen.has(e.id)||!e.name||!Array.isArray(e.instructions)||!e.instructions.length||e.instructions.some(p=>typeof p!=='string'||!p.trim())||!Array.isArray(e.equipment)||!Array.isArray(e.images)||!e.images.length||!safeLink(e.source_url)||!safeLink(e.attribution?.license_url)||e.clinical_approval!==false||e.can_activate_training!==false)return false;
      if(e.images.some(img=>!safeImage(img.url)||!safeLink(img.license_url)||!img.author))return false;
      seen.add(e.id);return true;
    });
  }
  let root=null,controller=null,generation=0,entries=null,loadError='',loading=false,selected='',filters={query:'',category:'',equipment:''};
  function media(img,name){return `<figure class="fx-exercise-media"><img src="${esc(safeImage(img.url))}" alt="${esc(name)} · ${img.kind==='photo'?'fotografía original':'ilustración original'}" loading="lazy" decoding="async" referrerpolicy="no-referrer"/><figcaption>${img.kind==='photo'?'Fotografía original':'Ilustración original'} · ${esc(img.author)} · ${link(img.license_url,img.license)}<span class="fx-media-error" hidden>La imagen no está disponible. Consulta la fuente original; no la sustituimos por otra variante.</span></figcaption></figure>`;}
  function detail(e){
    return `<button type="button" class="fx-button fx-text" data-fc="back">${icon('arrow_back')} Biblioteca de ejercicios</button><header class="fx-title"><p class="fx-eyebrow">FICHA ORIGINAL · ${e.language==='es'?'ESPAÑOL':'INGLÉS'}</p><h3 tabindex="-1">${esc(e.name)}</h3><p>${esc(display(e.category))} · ${esc(e.equipment.map(x=>display(x.name)).join(' · ')||'Material sin confirmar en la fuente')}</p></header><div class="fx-exercise-images">${e.images.map(img=>media(img,e.name)).join('')}</div><section class="fx-exercise-instructions"><h3>Indicaciones originales</h3>${e.instructions.map(p=>`<p>${esc(p)}</p>`).join('')}</section><aside class="fx-note"><div><strong>Información educativa, no un entrenamiento asignado</strong><p>Esta ficha no evalúa tus lesiones, restricciones ni técnica. Roxy no indica aquí una carga, series o repeticiones para ti. No continúes un movimiento que cause dolor.</p></div></aside><section class="fx-exercise-source"><h3>Origen y permiso de uso</h3><p>${link(e.source_url,'Ver ficha original en wger')}</p><p>Texto: ${esc(Array.isArray(e.attribution.authors)?e.attribution.authors.join(', '):e.attribution.authors)} · ${link(e.attribution.license_url,e.attribution.license)}</p><p>${esc(e.attribution.changes)} Los nombres de grupos y materiales se muestran traducidos.</p><p>Metadatos de la ficha: ${esc(e.base_attribution?.author||'wger')} · ${link(e.base_attribution?.license_url,e.base_attribution?.license||'Ver fuente')}</p><p>Revisión profesional de Roxy: pendiente. Las indicaciones del proveedor no equivalen a una autorización médica.</p></section>`;
  }
  function render(){
    if(!root)return;
    if(loading){root.innerHTML='<p role="status">Cargando fichas originales…</p>';return;}
    if(loadError){root.innerHTML=`<p role="alert" class="fx-error">${esc(loadError)}</p><button type="button" class="fx-button fx-secondary" data-fc="retry">Volver a cargar la biblioteca</button>`;return;}
    if(!entries)return;
    const chosen=entries.find(e=>e.id===selected);
    if(chosen){root.innerHTML=detail(chosen);bindImageErrors();return;}
    const categories=[...new Set(entries.map(e=>e.category))].sort();
    const equipment=[...new Map(entries.flatMap(e=>e.equipment.map(x=>[String(x.id),x.name]))).entries()].sort((a,b)=>a[1].localeCompare(b[1]));
    const result=selectEntries(entries,filters);
    root.innerHTML=`<header class="fx-title"><p class="fx-eyebrow">APRENDE CON UNA FUENTE REAL</p><h3>Biblioteca de movimientos</h3><p>Instrucciones e imágenes originales con autor y licencia. Puedes explorar sin guardar preferencias; no son recomendaciones personalizadas.</p></header><form id="fxCatalogSearch"><label class="fx-field"><span>Buscar un ejercicio</span><input name="query" type="search" maxlength="100" value="${esc(filters.query)}" placeholder="Nombre, grupo o material"/></label><div class="fx-grid"><label class="fx-field"><span>Grupo</span><select name="category"><option value="">Todos</option>${categories.map(x=>`<option ${filters.category===x?'selected':''} value="${esc(x)}">${esc(display(x))}</option>`).join('')}</select></label><label class="fx-field"><span>Material</span><select name="equipment"><option value="">Todos</option>${equipment.map(([id,name])=>`<option ${filters.equipment===id?'selected':''} value="${esc(id)}">${esc(display(name))}</option>`).join('')}</select></label></div><button type="submit" class="fx-button fx-primary">${icon('search')} Buscar</button></form><p class="fx-caption" role="status">${result.length} de ${entries.length} fichas originales · revisión profesional pendiente</p><div class="fx-exercise-grid">${result.map(e=>`<article class="fx-exercise-card">${media(e.images[0],e.name)}<div><p class="fx-eyebrow">${e.language==='es'?'ESPAÑOL':'ORIGINAL EN INGLÉS'} · ${esc(display(e.category))}</p><h3>${esc(e.name)}</h3><p>${esc(e.equipment.map(x=>display(x.name)).join(' · ')||'Material sin confirmar en la fuente')}</p><button type="button" class="fx-button fx-secondary" data-exercise-id="${esc(e.id)}" aria-label="Abrir ${esc(e.name)}">Ver indicaciones ${icon('arrow_forward')}</button></div></article>`).join('')}</div>${result.length?'':`<div class="fx-empty"><h3>No hay coincidencias</h3><p>Prueba otro nombre o quita los filtros. No generamos una ficha para rellenar la búsqueda.</p><button type="button" class="fx-button fx-secondary" data-fc="clear">Ver todas</button></div>`}`;
    bindImageErrors();
  }
  function bindImageErrors(){root.querySelectorAll('.fx-exercise-media img').forEach(img=>{img.addEventListener('error',()=>{img.hidden=true;const fallback=img.parentElement.querySelector('.fx-media-error');if(fallback)fallback.hidden=false;},{once:true});});}
  async function load(){
    const token=generation;loading=true;loadError='';render();
    try{const response=await fetch('/api/fitness/v1/exercises',{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'},signal:controller.signal});if(!response.ok)throw new Error(response.status===401?'Inicia sesión en Roxy Home para abrir la biblioteca.':'No pude cargar las fichas originales. Inténtalo de nuevo.');const payload=await response.json();if(token!==generation)return;entries=validatedEntries(payload);}
    catch(e){if(token===generation&&e.name!=='AbortError')loadError=e.message;}
    finally{if(token===generation){loading=false;render();}}
  }
  function click(event){const button=event.target.closest('button');if(!button||loading)return;
    if(button.dataset.exerciseId){selected=button.dataset.exerciseId;render();root.querySelector('h3')?.focus({preventScroll:true});root.scrollIntoView({block:'start'});}
    else if(button.dataset.fc==='back'){const old=selected;selected='';render();root.querySelector(`[data-exercise-id="${old}"]`)?.focus();}
    else if(button.dataset.fc==='clear'){filters={query:'',category:'',equipment:''};render();root.querySelector('input')?.focus();}
    else if(button.dataset.fc==='retry')void load();
  }
  function submit(event){event.preventDefault();event.stopPropagation();if(loading)return;const data=new FormData(event.target);filters={query:String(data.get('query')||'').slice(0,100),category:String(data.get('category')||''),equipment:String(data.get('equipment')||'')};render();root.querySelector('input')?.focus();}
  function mount(node){if(!node||root===node)return;controller?.abort();generation++;root=node;controller=new AbortController();root.addEventListener('click',click);root.addEventListener('submit',submit);if(entries)render();else void load();}
  function clear(){controller?.abort();generation++;root=null;entries=null;loadError='';loading=false;selected='';filters={query:'',category:'',equipment:''};}
  scope.RoxyFitnessLibrary={mount,clear};
  if(typeof module!=='undefined')module.exports={safeLink,safeImage,selectEntries,validatedEntries,detail,media};
})(typeof window!=='undefined'?window:globalThis);
