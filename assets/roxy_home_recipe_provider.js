(() => {
  'use strict';
  const renders = new WeakMap();
  const node = (tag, text, className) => {
    const el = document.createElement(tag);
    if (text) el.textContent = text;
    if (className) el.className = className;
    return el;
  };
  const safeURL = value => {
    try { const u=new URL(value); return u.protocol==='https:'&&!u.username&&!u.password&&!u.port ? u : null; }
    catch (_) { return null; }
  };
  const areaNames = {American:'Estados Unidos', British:'Reino Unido', Canadian:'Canadá', Chinese:'China', Croatian:'Croacia',
    Dutch:'Países Bajos', Egyptian:'Egipto', Filipino:'Filipinas', French:'Francia', Greek:'Grecia', Indian:'India', Irish:'Irlanda',
    Italian:'Italia', Jamaican:'Jamaica', Japanese:'Japón', Kenyan:'Kenia', Malaysian:'Malasia', Mexican:'México', Moroccan:'Marruecos',
    Polish:'Polonia', Portuguese:'Portugal', Russian:'Rusia', Spanish:'España', Thai:'Tailandia', Tunisian:'Túnez', Turkish:'Turquía',
    Ukrainian:'Ucrania', Vietnamese:'Vietnam', Algerian:'Argelia', Saudi:'Arabia Saudita', Unknown:'Origen no indicado'};
  function recipeCard(recipe) {
    const card=node('details',null,'provider-recipe-card');const title=node('summary',recipe.title);title.lang='en';card.append(title);
    const original=recipe.provider_original||{};
    const imageURL=safeURL(recipe.image_url);
    if(imageURL&&['www.themealdb.com','themealdb.com'].includes(imageURL.hostname)&&imageURL.pathname.startsWith('/images/media/meals/')){
      const image=node('img');image.src=imageURL.href;image.alt=`Fotografía del proveedor: ${recipe.title}`;image.loading='lazy';image.referrerPolicy='no-referrer';
      image.addEventListener('error',()=>{image.replaceWith(node('p','La fotografía del proveedor no está disponible.'))},{once:true});card.append(image);
    }
    if(original.area)card.append(node('p',`Cocina de la fuente: ${areaNames[original.area]||original.area}`));
    card.append(node('p','Original en inglés · porciones no indicadas. No se ha comprobado la correspondencia de la fotografía ni adaptado a tus alergias.'));
    card.append(node('h4','Ingredients · medidas originales'));
    const ingredients=node('ul');ingredients.lang='en';(recipe.ingredients||[]).forEach(item=>ingredients.append(node('li',`${item.measure||''} ${item.name||''}`.trim())));card.append(ingredients);
    card.append(node('h4','Instructions · texto original'));
    const instructions=node('p',original.instructions||(recipe.steps||[]).join('\n'),'provider-original-instructions');instructions.lang='en';card.append(instructions);
    (recipe.sources||[]).forEach(source=>{const url=safeURL(source.url);if(!url)return;const link=node('a',source.title||'Fuente');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';card.append(link);});
    card.append(node('p','Pendiente de revisión de porciones, ingredientes y traducción antes de incorporar a tu recetario. No se ha guardado ni enviado a Compra.','pet-product-method'));
    return card;
  }
  function render(container, {user, service={}, api, hidden=false}) {
    if (!container) return;
    const signature=JSON.stringify([user,service,hidden]);
    if (renders.get(container)?.signature===signature) return;
    const state={signature,requestToken:0,areaToken:0};renders.set(container,state);
    container.replaceChildren();container.hidden=hidden;
    if (hidden) return;
    const current=()=>renders.get(container)===state&&container.isConnected&&!container.hidden;
    const details=node('details',null,'card kitchen-tools');
    details.append(node('summary','Recetas de fuentes externas'));
    details.append(node('p','TheMealDB · ingredientes, pasos y fotografía del proveedor. Los originales están en inglés; Roxy no inventa porciones ni los presenta como revisados.'));
    if (!service.access_allowed) {
      details.append(node('p',service.access_status==='not_included_in_demo'
        ? 'Esta conexión todavía no está incluida en la demo.'
        : 'Conexión pendiente: falta confirmar la licencia comercial y configurar el acceso. El recetario de Roxy sigue disponible.','pet-product-method'));
      container.append(details);return;
    }
    const form=node('form',null,'kitchen-form');const label=node('label');
    label.append(node('span','Buscar en TheMealDB (en inglés)'));
    const input=node('input');input.type='search';input.required=true;input.minLength=2;input.maxLength=100;
    input.placeholder='Ej. chicken, rice, eggs';label.append(input);
    const submit=node('button','Consultar TheMealDB','secondary full');submit.type='submit';
    const status=node('p');status.setAttribute('role','status');
    const results=node('div',null,'provider-recipe-results');
    form.append(label,node('small','Sólo se envía tu búsqueda al proveedor, no tu hogar, despensa ni perfil. No incluyas datos personales.'),submit);
    const loadAreas=node('button','Cargar países y regiones','secondary full');loadAreas.type='button';
    const areaStatus=node('p');areaStatus.setAttribute('role','status');
    const browseForm=node('form',null,'kitchen-form');browseForm.hidden=true;
    const areaLabel=node('label');areaLabel.append(node('span','País o región de la fuente'));
    const area=node('select');area.required=true;areaLabel.append(area);
    const browseSubmit=node('button','Consultar este país o región','secondary full');browseSubmit.type='submit';browseSubmit.disabled=true;
    browseForm.append(areaLabel,node('small','Consulta hasta cuatro recetas completas del país o región que elijas, con los derechos y datos requeridos.'),browseSubmit);
    details.append(form,loadAreas,areaStatus,browseForm,status,results);container.append(details);
    const base=`/v1/home-food/${encodeURIComponent(user)}/providers/recipes`;
    const latest=token=>current()&&token===state.requestToken;
    const resetButtons=()=>{submit.disabled=false;browseSubmit.disabled=!area.value;};
    const consult=async(path,sourceButton,limit)=>{
      const token=++state.requestToken;resetButtons();sourceButton.disabled=true;
      status.textContent='Consultando el proveedor…';results.replaceChildren();
      try {
        const data=await api(base+path);
        if(!latest(token))return;
        if(!Array.isArray(data.recipes))throw new Error('invalid_provider_response');
        const rows=data.recipes.slice(0,limit);
        status.textContent=rows.length?`${rows.length} resultados del proveedor · pendientes de revisión.`:'No hay resultados utilizables con los derechos y datos requeridos. Prueba otra búsqueda.';
        results.replaceChildren(...rows.map(recipeCard));
      } catch (_) { if(latest(token))status.textContent='No se pudo consultar TheMealDB. El recetario local sigue disponible; no se ha guardado nada.'; }
      finally { if(latest(token))resetButtons(); }
    };
    form.addEventListener('submit',async event=>{
      event.preventDefault();if(!current()||!form.reportValidity())return;
      const query=input.value.trim();if(query.length<2)return;
      await consult(`/search?q=${encodeURIComponent(query)}&limit=12&requested=true`,submit,12);
    });
    browseForm.addEventListener('submit',async event=>{
      event.preventDefault();if(!current()||!browseForm.reportValidity()||!area.value)return;
      await consult(`/browse?area=${encodeURIComponent(area.value)}&requested=true`,browseSubmit,4);
    });
    const invalidate=()=>{if(!current())return;state.requestToken++;resetButtons();results.replaceChildren();status.textContent='Pulsa Consultar para ver los resultados de tu selección.';};
    input.addEventListener('input',invalidate);area.addEventListener('change',invalidate);
    loadAreas.addEventListener('click',async()=>{
      if(!current()||loadAreas.disabled)return;
      const token=++state.areaToken;loadAreas.disabled=true;areaStatus.textContent='Consultando países y regiones…';
      try {
        const data=await api(`${base}/areas?requested=true`);
        if(!current()||token!==state.areaToken)return;
        if(!Array.isArray(data.areas))throw new Error('invalid_provider_areas');
        const values=[...new Set(data.areas.filter(value=>typeof value==='string'&&value.trim()&&value.length<=80))].slice(0,200);
        area.replaceChildren();const placeholder=node('option','Selecciona un país o región');placeholder.value='';area.append(placeholder);
        values.forEach(value=>{const option=node('option',areaNames[value]||value);option.value=value;area.append(option);});
        browseForm.hidden=!values.length;browseSubmit.disabled=true;
        areaStatus.textContent=values.length?`${values.length} países y regiones de TheMealDB. Elige uno para consultar sus recetas.`:'El proveedor no devolvió países o regiones disponibles.';
        loadAreas.textContent='Volver a cargar países y regiones';
      } catch (_) { if(current()&&token===state.areaToken)areaStatus.textContent='No se pudieron cargar los países y regiones. Puedes volver a intentarlo.'; }
      finally { if(current()&&token===state.areaToken)loadAreas.disabled=false; }
    });
  }
  window.RoxyRecipeProvider=Object.freeze({render});
})();
