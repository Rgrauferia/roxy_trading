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
    try { const u=new URL(value); return u.protocol==='https:'&&!u.username&&!u.password ? u : null; }
    catch (_) { return null; }
  };
  function render(container, {user, service={}, api, hidden=false}) {
    if (!container) return;
    const signature=JSON.stringify([user,service,hidden]);
    if (renders.get(container)?.signature===signature) return;
    const state={signature};renders.set(container,state);
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
    details.append(form,status,results);container.append(details);
    form.addEventListener('submit',async event=>{
      event.preventDefault();if (!form.reportValidity()) return;
      const query=input.value.trim();if(query.length<2)return;
      submit.disabled=true;status.textContent='Consultando el proveedor…';results.replaceChildren();
      try {
        const data=await api(`/v1/home-food/${encodeURIComponent(user)}/providers/recipes/search?q=${encodeURIComponent(query)}&limit=12&requested=true`);
        if(!current())return;
        const rows=data.recipes||[];
        status.textContent=rows.length?`${rows.length} resultados del proveedor · pendientes de revisión.`:'No hay resultados utilizables con los derechos y datos requeridos. Prueba otra búsqueda.';
        rows.forEach(recipe=>{
          const card=node('details',null,'provider-recipe-card');card.append(node('summary',recipe.title));
          const original=recipe.provider_original||{};
          const imageURL=safeURL(recipe.image_url);
          if(imageURL&&['www.themealdb.com','themealdb.com'].includes(imageURL.hostname)&&imageURL.pathname.startsWith('/images/media/meals/')){
            const image=node('img');image.src=imageURL.href;image.alt=`Fotografía del proveedor: ${recipe.title}`;image.loading='lazy';image.referrerPolicy='no-referrer';
            image.addEventListener('error',()=>{image.replaceWith(node('p','La fotografía del proveedor no está disponible.'))},{once:true});card.append(image);
          }
          card.append(node('p','Original en inglés · porciones no indicadas. No se ha comprobado la correspondencia de la fotografía ni adaptado a tus alergias.'));
          card.append(node('h4','Ingredients · medidas originales'));
          const ingredients=node('ul');(recipe.ingredients||[]).forEach(item=>ingredients.append(node('li',`${item.measure||''} ${item.name||''}`.trim())));card.append(ingredients);
          card.append(node('h4','Instructions · texto original'));
          const instructions=node('p',original.instructions||(recipe.steps||[]).join('\n'),'provider-original-instructions');instructions.lang='en';card.append(instructions);
          (recipe.sources||[]).forEach(source=>{const url=safeURL(source.url);if(!url)return;const link=node('a',source.title||'Fuente');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';card.append(link);});
          card.append(node('p','Pendiente de revisión de porciones, ingredientes y traducción antes de incorporar a tu recetario. No se ha guardado ni enviado a Compra.','pet-product-method'));results.append(card);
        });
      } catch (_) { if(current())status.textContent='No se pudo consultar TheMealDB. El recetario local sigue disponible; no se ha guardado nada.'; }
      finally { if(current())submit.disabled=false; }
    });
  }
  window.RoxyRecipeProvider=Object.freeze({render});
})();
