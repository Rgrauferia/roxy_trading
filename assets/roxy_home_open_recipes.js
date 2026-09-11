(() => {
  'use strict';
  const renders = new WeakMap();
  const countries = {Spanish:'España', French:'Francia', Japanese:'Japón', Greek:'Grecia', Indian:'India', Italian:'Italia',British:'Reino Unido',American:'Estados Unidos','North American':'Norteamérica',Mexican:'México'};
  const node = (tag, text, className) => {
    const el = document.createElement(tag);
    if (text) el.textContent = text;
    if (className) el.className = className;
    return el;
  };
  const button = (text, action) => {
    const el = node('button', text, 'secondary'); el.type = 'button'; el.addEventListener('click', action); return el;
  };
  const translationOf = recipe => {
    const value = recipe.translation;
    if (recipe.language !== 'en' || !value || value.language !== 'es' || value.source_id !== recipe.id ||
      value.source_revid !== recipe.revid || value.source_sha256 !== recipe.source_sha256 ||
      value.license !== 'CC BY-SA 4.0' || value.license_url !== 'https://creativecommons.org/licenses/by-sa/4.0/' ||
      ['title','attribution','changes'].some(field => typeof value[field] !== 'string' || !value[field].trim()) ||
      typeof value.time !== 'string' || !Array.isArray(value.editorial_notes || []) ||
      (value.editorial_notes || []).some(note => typeof note !== 'string' || !note.trim())) return null;
    for (const [field, source] of [['ingredients','ingredients_original'],['steps','steps_original'],
      ['equipment','equipment_original'],['notes','notes_original']]) {
      if (!Array.isArray(value[field]) || value[field].length !== recipe[source]?.length ||
        value[field].some(item => typeof item !== 'string' || !item.trim())) return null;
    }
    return value;
  };
  const safeURL = value => {
    try {
      const url = new URL(value);
      return url.protocol === 'https:' && !url.username && !url.password && !url.port ? url : null;
    } catch (_) { return null; }
  };
  const link = (parent, label, value) => {
    const url = safeURL(value);
    if (!url || !(url.hostname === 'creativecommons.org' || /^(?:[a-z-]+\.)?wikibooks\.org$/.test(url.hostname) ||
      (url.hostname === 'commons.wikimedia.org' && url.pathname.startsWith('/wiki/File:')))) return;
    const el = node('a', label); el.href = url.href; el.target = '_blank'; el.rel = 'noopener noreferrer'; parent.append(el);
  };
  function sourcePhoto(card, recipe) {
    const image = safeURL(recipe.image_url), source = safeURL(recipe.image_source_url), license = safeURL(recipe.image_license_url);
    const fallback = node('p', 'No hay una fotografía de la fuente disponible para esta receta.', 'pet-product-method'); card.append(fallback);
    if (!image || image.hostname !== 'upload.wikimedia.org' || image.search || image.hash || recipe.image_mime !== 'image/jpeg' ||
      !/^\/wikipedia\/commons\/[a-f0-9]\/[a-f0-9]{2}\/[^/]+\.jpe?g$/i.test(image.pathname) || !recipe.image_author ||
      !source || source.hostname !== 'commons.wikimedia.org' || !source.pathname.startsWith('/wiki/File:') ||
      !license || license.hostname !== 'creativecommons.org' || !/^\/licenses\/by-sa\/(?:2\.0|2\.5|3\.0|4\.0)\/$/.test(license.pathname) ||
      recipe.image_license !== `CC BY-SA ${license.pathname.split('/')[3]}` || typeof recipe.image_author !== 'string' || !recipe.image_author.trim() ||
      recipe.image_commercial_use_permitted !== true || recipe.image_status !== 'source_linked_individual_license_checked') return;
    const photo = node('img'); photo.alt = `${recipe.title} · fotografía publicada por la fuente`; photo.loading = 'lazy'; photo.referrerPolicy = 'no-referrer';
    const size = recipe.image_dimensions || {}; if (Number.isInteger(size.width) && Number.isInteger(size.height) && size.width > 0 && size.height > 0) { photo.width = size.width; photo.height = size.height; }
    fallback.hidden = true; card.append(photo);
    photo.addEventListener('error', () => { photo.remove(); fallback.textContent = 'La fotografía original no se pudo cargar; puedes consultar su fuente.'; fallback.hidden = false; });
    const load = () => { if (card.open && !photo.src) photo.src = image.href; };
    card.addEventListener('toggle', load); load();
    card.append(node('p', recipe.photo_scope, 'pet-product-method'), node('p', `Foto: ${recipe.image_author} · ${recipe.image_license}`, 'pet-product-method'));
    const credits = node('details', null, 'open-recipe-credits'); credits.append(node('summary', 'Licencia y procedencia de la foto'));
    link(credits, 'Fotografía y créditos · Wikimedia Commons', recipe.image_source_url); link(credits, 'Licencia de esta fotografía', recipe.image_license_url);
    if (recipe.image_changes) { const changes = node('p', recipe.image_changes, 'pet-product-method'); changes.lang = 'en'; credits.append(changes); }
    card.append(credits);
  };
  const originalList = (parent, title, values, ordered = false, language = 'en') => {
    if (!values.length) return;
    parent.append(node('h4', title)); const list = node(ordered ? 'ol' : 'ul'); list.lang = language;
    values.forEach(value => list.append(node('li', value))); parent.append(list);
  };
  function download(recipe, translated = false) {
    const rights = recipe.rights || {};
    const spanish = translated && translationOf(recipe);
    const content = spanish || {title:recipe.title, time:recipe.time_original, ingredients:recipe.ingredients_original,
      steps:recipe.steps_original, equipment:recipe.equipment_original, notes:recipe.notes_original};
    const sections = [content.title, spanish ? 'Traducción al español del original en inglés; no es una adaptación ni una receta ensayada por Roxy.' : `Original language: ${recipe.language}`,
      `Servings (source): ${recipe.servings_original}`, content.time, '\nIngredients / Ingredientes', ...content.ingredients,
      '\nInstructions / Preparación', ...content.steps.map((text, i) => `${i + 1}. ${text}`)];
    if (content.equipment.length) sections.push('\nEquipment / Equipo', ...content.equipment);
    if (content.notes.length) sections.push('\nNotes / Notas', ...content.notes);
    if (spanish) sections.push('\nTranslation / Traducción', spanish.attribution, spanish.license, spanish.license_url, spanish.changes);
    if (spanish?.editorial_notes?.length) sections.push('\nNotas editoriales de Roxy (no son pasos del original)', ...spanish.editorial_notes);
    sections.push('\nSource and rights', recipe.attribution || rights.attribution, recipe.source_url, recipe.source_revision_url,
      `License: ${rights.license}`, recipe.license_url || rights.license_url, ...(rights.additional_attribution_urls || []), rights.changes);
    if (recipe.image_url && recipe.image_author && recipe.image_license) sections.push('\nSource photograph (reference only)',
      recipe.image_author, recipe.image_license, recipe.image_source_url, recipe.image_license_url, recipe.image_changes);
    const url = URL.createObjectURL(new Blob([sections.filter(value => value !== undefined).join('\n')], {type:'text/plain;charset=utf-8'}));
    const anchor = node('a'); anchor.href = url; anchor.download = `roxy-${spanish ? 'es' : 'original'}-${String(recipe.id).replace(/[^a-z0-9-]/gi, '')}.txt`;
    document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function recipeCard(recipe, card = node('details', null, 'provider-recipe-card')) {
    const spanish = translationOf(recipe);
    let useSpanish = Boolean(spanish);
    const original = {title:recipe.title, time:recipe.time_original, ingredients:recipe.ingredients_original,
      steps:recipe.steps_original, equipment:recipe.equipment_original, notes:recipe.notes_original};
    const content = () => useSpanish ? spanish : original;
    const language = () => useSpanish ? 'es' : recipe.language;
    card.replaceChildren(); const title = node('summary'); card.append(title);
    card.append(node('p', [countries[recipe.cuisine] || recipe.cuisine,
      `${recipe.servings_original} ${recipe.servings === 1 ? 'ración' : 'raciones'}`].filter(Boolean).join(' · ')));
    const time = node('p'); card.append(time);
    sourcePhoto(card, recipe);
    const languageLabel = node('p', null, 'pet-product-method'); card.append(languageLabel);
    const languageButton = button('Ver original en inglés', () => { useSpanish = !useSpanish; showContent(); showStep(); });
    if (spanish) card.append(languageButton);
    if (spanish?.editorial_notes?.length) {
      const notes = node('aside', null, 'pet-product-method');
      originalList(notes, 'Antes de usar esta fuente · notas de Roxy', spanish.editorial_notes, false, 'es');
      card.append(notes);
    }
    const body = node('div');
    const showContent = () => {
      const value = content(); title.textContent = value.title; title.lang = language();
      time.textContent = value.time; time.lang = language(); time.hidden = !value.time;
      languageLabel.textContent = useSpanish ? 'Traducción al español de la revisión enlazada. Sin cambiar cantidades, tiempos ni pasos; no es una adaptación a alergias ni una receta ensayada por Roxy.' : `Original en ${recipe.language === 'es' ? 'español' : 'inglés'} de la revisión enlazada. No es una receta ensayada por Roxy.`;
      languageButton.textContent = useSpanish ? 'Ver original en inglés' : 'Ver traducción al español';
      body.replaceChildren();
      originalList(body, language() === 'es' ? 'Ingredientes · medidas de la fuente' : 'Ingredients · medidas originales', value.ingredients, false, language());
      originalList(body, language() === 'es' ? 'Equipo' : 'Equipment · equipo de la fuente', value.equipment, false, language());
      originalList(body, language() === 'es' ? 'Preparación · pasos de la fuente' : 'Instructions · pasos originales', value.steps, true, language());
      originalList(body, language() === 'es' ? 'Notas y variantes de la fuente' : 'Notes · notas originales', value.notes, false, language());
    };
    const reader = node('section', null, 'open-recipe-reader'); reader.hidden = true;
    const progress = node('p'); progress.setAttribute('role', 'status');
    const step = node('p', null, 'provider-original-instructions'); step.lang = 'en'; step.tabIndex = -1;
    let position = 0;
    const showStep = () => { progress.textContent = `Paso ${position + 1} de ${recipe.steps_original.length}`;
      step.textContent = content().steps[position]; step.lang = language(); previous.disabled = position === 0; next.disabled = position === recipe.steps_original.length - 1; };
    const previous = button('Anterior', () => { if (position > 0) { position--; showStep(); } });
    const next = button('Siguiente', () => { if (position < recipe.steps_original.length - 1) { position++; showStep(); } });
    const start = button('Leer paso a paso', () => { position = 0; showStep(); reader.hidden = false; start.hidden = true; body.hidden = true; step.focus({preventScroll:true}); });
    const end = button('Terminar lectura', () => { reader.hidden = true; start.hidden = false; body.hidden = false; start.focus({preventScroll:true}); });
    reader.append(progress, step, previous, next, end); card.append(start, reader, body, button('Descargar original TXT', () => download(recipe)));
    if (spanish) card.append(button('Descargar traducción TXT', () => download(recipe, true)),
      node('p', `${spanish.attribution} · ${spanish.license}`, 'pet-product-method'));
    const rights = recipe.rights || {};
    card.append(node('p', recipe.attribution || rights.attribution));
    const credits = node('details', null, 'open-recipe-credits'); credits.append(node('summary', 'Fuentes, licencia y cambios editoriales'));
    link(credits, 'Fuente original · Wikibooks', recipe.source_url);
    link(credits, `Revisión conservada ${recipe.revid}`, recipe.source_revision_url);
    link(credits, rights.license || 'CC BY-SA 4.0', recipe.license_url || rights.license_url);
    (rights.additional_attribution_urls || []).forEach(url => link(credits, 'Crédito adicional de la fuente', url));
    if (rights.changes) { const changes = node('p', rights.changes, 'pet-product-method'); changes.lang = 'en'; credits.append(changes); }
    if (spanish) { const changes = node('p', spanish.changes, 'pet-product-method'); changes.lang = 'en'; credits.append(changes); }
    card.append(credits);
    card.append(node('p', 'Cantidades originales, sin conversión automática ni adaptación a tus alergias.', 'pet-product-method'));
    showContent();
    return card;
  }
  function setActive(container, active) {
    const state = renders.get(container);
    if (state) state.activate(Boolean(active));
  }
  function render(container, {user, identity = '', api, hidden = false, active = true, isCurrent = () => true}) {
    if (!container) return;
    const signature = JSON.stringify([user, identity, hidden]);
    const previousState = renders.get(container);
    if (previousState?.signature === signature) { previousState.activate(active); return; }
    previousState?.dispose();
    const state = {signature, active:Boolean(active), loaded:false, version:'', pages:[''], next:'',
      generation:0, controller:null, detailRequests:new Map(), cache:new Map(), timer:null};
    state.activate = () => {}; state.dispose = () => {};
    renders.set(container, state);
    container.replaceChildren(); container.hidden = hidden; if (hidden) return;
    const details = node('details', null, 'card kitchen-tools');
    details.append(node('summary', 'Recetas del mundo · fuentes originales'));
    details.append(node('p', 'Explora por cocina, idioma o ingrediente. Cada ficha conserva las cantidades y todos los pasos de su fuente; puedes comparar el original y leer paso a paso.'));
    details.append(node('p', 'Esta colección es de consulta: no equivale a recetas ensayadas por Roxy ni se adapta automáticamente a alergias.', 'pet-product-method'));
    const current = () => renders.get(container) === state && container.isConnected && !container.hidden &&
      state.active && details.open && !document.hidden && isCurrent();
    // Bound both HTTP and body decoding, including mocks/transports that do not
    // settle after abort. Lifecycle cancellation must not look like a failure.
    const request = (path, controller) => new Promise((resolve, reject) => {
      let settled = false;
      const finish = (action, value) => {
        if (settled) return; settled = true; clearTimeout(timer);
        controller.signal.removeEventListener('abort', aborted); action(value);
      };
      const aborted = () => finish(reject, Object.assign(new Error('cancelled'), {name:'AbortError'}));
      const timer = setTimeout(() => {
        finish(reject, Object.assign(new Error('request_timeout'), {name:'TimeoutError'})); controller.abort();
      }, 12000);
      controller.signal.addEventListener('abort', aborted, {once:true});
      if (controller.signal.aborted) { aborted(); return; }
      Promise.resolve().then(() => {
        if (controller.signal.aborted) throw Object.assign(new Error('cancelled'), {name:'AbortError'});
        return api(path, {signal:controller.signal});
      }).then(value => finish(resolve, value), error => finish(reject, error));
    });
    const controls = node('div', null, 'kitchen-form');
    const cuisineLabel = node('label'); cuisineLabel.append(node('span', 'Cocina de la fuente'));
    const cuisine = node('select'); cuisine.setAttribute('aria-label', 'Cocina de la fuente'); cuisine.append(node('option', 'Todas las cocinas')); cuisine.firstChild.value = ''; cuisineLabel.append(cuisine);
    const languageLabel = node('label'); languageLabel.append(node('span', 'Idioma disponible'));
    const language = node('select'); language.setAttribute('aria-label', 'Idioma disponible');
    [['all','Todos los idiomas'],['es','Español · original o traducción'],['en','Original en inglés']].forEach(([value, label]) => {
      const option = node('option', label); option.value = value; language.append(option);
    });
    language.value = 'all'; languageLabel.append(language);
    const searchLabel = node('label'); searchLabel.append(node('span', 'Buscar en español o inglés'));
    const search = node('input'); search.type = 'search'; search.maxLength = 100; search.placeholder = 'Ej. papas, rice, queso'; searchLabel.append(search);
    const status = node('p'); status.setAttribute('role', 'status');
    const results = node('div', null, 'provider-recipe-results');
    const pagination = node('nav', null, 'open-recipe-pagination'); pagination.setAttribute('aria-label', 'Páginas de recetas originales'); pagination.hidden = true;
    const pageLabel = node('span');
    const prev = button('Página anterior', () => { if (state.pages.length > 1) void load(state.pages.slice(0, -1)); });
    const next = button('Página siguiente', () => { if (state.next) void load([...state.pages, state.next]); });
    pagination.append(prev, pageLabel, next);
    const retry = button('Reintentar', () => void load(state.pages)); retry.hidden = true;
    const clear = button('Limpiar filtros', () => { search.value = ''; cuisine.value = ''; language.value = 'all'; filter(false); });
    controls.append(searchLabel, cuisineLabel, languageLabel, clear);
    details.append(controls, status, retry, results, pagination); container.append(details);
    const cancelDetails = () => {
      for (const pending of state.detailRequests.values()) {
        pending.controller.abort(); pending.cancel();
      }
      state.detailRequests.clear();
    };
    const stop = () => {
      clearTimeout(state.timer); state.timer = null; state.generation++;
      if (state.controller) { state.controller.abort(); state.controller = null; }
      cancelDetails(); results.setAttribute('aria-busy', 'false');
    };
    const versionChanged = () => {
      stop(); state.cache.clear(); state.version = ''; state.pages = ['']; state.next = ''; state.loaded = false;
      results.replaceChildren(); pagination.hidden = true; retry.hidden = false;
      status.textContent = 'La selección se actualizó. Pulsa Reintentar para leer la nueva edición sin mezclar pasos de versiones distintas.';
    };
    const validDetail = (recipe, summary) => recipe && recipe.id === summary.id && recipe.title && recipe.servings_original &&
      recipe.revid === summary.revid && recipe.source_sha256 === summary.source_sha256 && recipe.language === summary.language &&
      ['en','es'].includes(recipe.language) && recipe.can_cook_with_roxy === false && recipe.can_add_to_shopping === false &&
      ['ingredients_original','steps_original','equipment_original','notes_original'].every(field => Array.isArray(recipe[field]) &&
        recipe[field].every(value => typeof value === 'string' && value.trim())) && recipe.ingredients_original.length && recipe.steps_original.length;
    const summaryCard = summary => {
      const card = node('details', null, 'provider-recipe-card');
      const title = node('summary', summary.title_es || summary.title); title.lang = summary.title_es ? 'es' : summary.language;
      const meta = node('p', [countries[summary.cuisine] || summary.cuisine,
        `${summary.ingredient_count} ingredientes`, `${summary.step_count} pasos`].filter(Boolean).join(' · '));
      const label = node('p', summary.has_source_photo ? 'Incluye fotografía de la fuente' : 'Sin fotografía de la fuente', 'pet-product-method');
      const detailStatus = node('p'); detailStatus.setAttribute('role', 'status');
      const again = button('Reintentar receta', () => void open()); again.hidden = true;
      card.append(title, meta, label, detailStatus, again);
      let loaded = false;
      const open = async () => {
        if (!card.open || loaded || state.detailRequests.has(card) || !current() || !card.isConnected) return;
        const version = state.version, generation = state.generation;
        const cacheKey = `${version}:${summary.id}`;
        const cached = state.cache.get(cacheKey);
        if (cached) { loaded = true; recipeCard(cached, card); return; }
        const controller = new AbortController();
        const pending = {controller, cancel:() => { detailStatus.textContent = 'Carga pausada. Vuelve a abrir la receta o pulsa Reintentar receta.'; again.hidden = false; }};
        state.detailRequests.set(card, pending); again.hidden = true; detailStatus.textContent = 'Cargando ingredientes y pasos originales…';
        try {
          const data = await request(`/v1/home-food/${encodeURIComponent(user)}/open-recipes/detail/${encodeURIComponent(summary.id)}?catalog_version=${encodeURIComponent(version)}`, controller);
          if (controller.signal.aborted || generation !== state.generation || !current() || !card.open || !card.isConnected || state.detailRequests.get(card) !== pending) return;
          if (data.catalog_version !== version) { versionChanged(); return; }
          if (!validDetail(data.recipe, summary)) throw new Error('invalid_detail');
          state.cache.set(cacheKey, data.recipe);
          while (state.cache.size > 12) state.cache.delete(state.cache.keys().next().value);
          loaded = true; recipeCard(data.recipe, card);
        } catch (error) {
          if ((controller.signal.aborted && error?.name !== 'TimeoutError') || generation !== state.generation || !current() || !card.isConnected) return;
          if (error?.status === 409) { versionChanged(); return; }
          detailStatus.textContent = 'No se pudieron cargar los pasos. No se han sustituido por instrucciones generadas.'; again.hidden = false;
        } finally { if (state.detailRequests.get(card) === pending) state.detailRequests.delete(card); }
      };
      card.addEventListener('toggle', () => {
        if (card.open) void open();
        else { const pending = state.detailRequests.get(card); if (pending) { pending.controller.abort(); pending.cancel(); state.detailRequests.delete(card); } }
      });
      return card;
    };
    async function load(pages = ['']) {
      if (!current()) return;
      stop(); state.pages = pages; state.loaded = false; retry.hidden = true; pagination.hidden = true; results.replaceChildren();
      const generation = state.generation, controller = new AbortController(); state.controller = controller;
      status.textContent = 'Cargando la selección de recetas…'; results.setAttribute('aria-busy', 'true');
      const params = new URLSearchParams({q:search.value.trim().slice(0,100), cuisine:cuisine.value, language:language.value, limit:'24', cursor:pages.at(-1) || ''});
      try {
        const data = await request(`/v1/home-food/${encodeURIComponent(user)}/open-recipes/summaries?${params}`, controller);
        if (controller.signal.aborted || generation !== state.generation || !current()) return;
        if (data.status !== 'READY' || !data.catalog_version || !Array.isArray(data.recipes) || data.recipes.length > 24 ||
          !Number.isInteger(data.matched_total) || !Number.isInteger(data.catalog_total) ||
          data.recipes.some(row => !row?.id || !row.title || !['en','es'].includes(row.language))) throw new Error('catalog_unavailable');
        if (state.version && state.version !== data.catalog_version && pages.length > 1) { versionChanged(); return; }
        if (state.version !== data.catalog_version) state.cache.clear();
        state.version = data.catalog_version; state.pages = pages; state.next = typeof data.next_cursor === 'string' ? data.next_cursor : '';
        const selectedCuisine = cuisine.value;
        cuisine.replaceChildren(node('option', 'Todas las cocinas')); cuisine.firstChild.value = '';
        (Array.isArray(data.cuisines) ? data.cuisines : []).filter(value => typeof value === 'string' && value).forEach(value => {
          const option = node('option', countries[value] || value); option.value = value; cuisine.append(option);
        });
        cuisine.value = selectedCuisine;
        results.replaceChildren(...data.recipes.map(summaryCard)); state.loaded = true;
        const offset = (pages.length - 1) * 24;
        const matches = data.matched_total === 1 ? '1 coincidencia' : `${offset + 1}–${offset + data.recipes.length} de ${data.matched_total} coincidencias`;
        status.textContent = data.recipes.length ? `${matches} · ${data.catalog_total} originales disponibles.` : 'No hay coincidencias. Prueba otra palabra, cocina o idioma, o limpia los filtros.';
        pagination.hidden = !data.recipes.length || (pages.length === 1 && !state.next);
        pageLabel.textContent = `Página ${pages.length}`; prev.disabled = pages.length <= 1; next.disabled = !state.next;
      } catch (error) {
        if ((controller.signal.aborted && error?.name !== 'TimeoutError') || generation !== state.generation || !current()) return;
        if (error?.status === 409) { versionChanged(); return; }
        status.textContent = 'No se pudo cargar esta selección. Puedes reintentar; tus recetas guardadas no se han cambiado.'; retry.hidden = false;
      } finally {
        if (generation === state.generation) { state.controller = null; results.setAttribute('aria-busy', 'false'); }
      }
    }
    function filter(debounce) {
      stop(); state.pages = ['']; state.next = ''; state.loaded = false; results.replaceChildren(); pagination.hidden = true; retry.hidden = true;
      status.textContent = 'Buscando en toda la colección…';
      if (debounce) state.timer = setTimeout(() => void load(), 300); else void load();
    }
    search.addEventListener('input', () => filter(true)); cuisine.addEventListener('change', () => filter(false)); language.addEventListener('change', () => filter(false));
    state.activate = value => {
      state.active = Boolean(value);
      if (!current()) stop(); else if (!state.loaded && !state.controller) void load(state.pages);
    };
    const visibility = () => state.activate(state.active);
    document.addEventListener('visibilitychange', visibility);
    state.dispose = () => { stop(); state.cache.clear(); document.removeEventListener('visibilitychange', visibility); };
    details.addEventListener('toggle', () => {
      if (!details.open) stop(); else if (!state.loaded && !state.controller) void load(state.pages);
    });
  }
  window.RoxyOpenRecipes = Object.freeze({render, setActive});
})();
