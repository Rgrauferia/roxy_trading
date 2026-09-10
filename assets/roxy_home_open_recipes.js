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
  const key = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const button = (text, action) => {
    const el = node('button', text, 'secondary'); el.type = 'button'; el.addEventListener('click', action); return el;
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
    card.addEventListener('toggle', () => { if (card.open && !photo.src) photo.src = image.href; });
    card.append(node('p', recipe.photo_scope, 'pet-product-method'), node('p', `Foto: ${recipe.image_author} · ${recipe.image_license}`, 'pet-product-method'));
    link(card, 'Fotografía y créditos · Wikimedia Commons', recipe.image_source_url); link(card, 'Licencia de esta fotografía', recipe.image_license_url);
    if (recipe.image_changes) { const changes = node('p', recipe.image_changes, 'pet-product-method'); changes.lang = 'en'; card.append(changes); }
  };
  const originalList = (parent, title, values, ordered = false) => {
    if (!values.length) return;
    parent.append(node('h4', title)); const list = node(ordered ? 'ol' : 'ul'); list.lang = 'en';
    values.forEach(value => list.append(node('li', value))); parent.append(list);
  };
  function download(recipe) {
    const rights = recipe.rights || {};
    const sections = [recipe.title, `Original language: ${recipe.language}`, `Servings: ${recipe.servings_original}`, recipe.time_original,
      '\nIngredients', ...recipe.ingredients_original, '\nInstructions', ...recipe.steps_original.map((text, i) => `${i + 1}. ${text}`)];
    if (recipe.equipment_original.length) sections.push('\nEquipment', ...recipe.equipment_original);
    if (recipe.notes_original.length) sections.push('\nNotes, tips, and variations', ...recipe.notes_original);
    sections.push('\nSource and rights', recipe.attribution || rights.attribution, recipe.source_url, recipe.source_revision_url,
      `License: ${rights.license}`, recipe.license_url || rights.license_url, ...(rights.additional_attribution_urls || []), rights.changes);
    if (recipe.image_url && recipe.image_author && recipe.image_license) sections.push('\nSource photograph (reference only)',
      recipe.image_author, recipe.image_license, recipe.image_source_url, recipe.image_license_url, recipe.image_changes);
    const url = URL.createObjectURL(new Blob([sections.filter(value => value !== undefined).join('\n')], {type:'text/plain;charset=utf-8'}));
    const anchor = node('a'); anchor.href = url; anchor.download = `roxy-original-${String(recipe.id).replace(/[^a-z0-9-]/gi, '')}.txt`;
    document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function recipeCard(recipe) {
    const card = node('details', null, 'provider-recipe-card'); const title = node('summary', recipe.title); title.lang = 'en'; card.append(title);
    card.append(node('p', `${countries[recipe.cuisine] || recipe.cuisine} · ${recipe.servings_original} ${recipe.servings === 1 ? 'ración' : 'raciones'} · original en inglés.`));
    if (recipe.time_original) { const time = node('p', recipe.time_original); time.lang = 'en'; card.append(time); }
    sourcePhoto(card, recipe);
    originalList(card, 'Ingredients · medidas originales', recipe.ingredients_original);
    originalList(card, 'Equipment · equipo de la fuente', recipe.equipment_original);
    originalList(card, 'Instructions · pasos originales', recipe.steps_original, true);
    originalList(card, 'Notes · notas originales', recipe.notes_original);
    const reader = node('section', null, 'open-recipe-reader'); reader.hidden = true;
    const progress = node('p'); progress.setAttribute('role', 'status');
    const step = node('p', null, 'provider-original-instructions'); step.lang = 'en'; step.tabIndex = -1;
    let position = 0;
    const showStep = () => { progress.textContent = `Paso ${position + 1} de ${recipe.steps_original.length}`;
      step.textContent = recipe.steps_original[position]; previous.disabled = position === 0; next.disabled = position === recipe.steps_original.length - 1; };
    const previous = button('Anterior', () => { if (position > 0) { position--; showStep(); } });
    const next = button('Siguiente', () => { if (position < recipe.steps_original.length - 1) { position++; showStep(); } });
    const start = button('Leer paso a paso', () => { position = 0; showStep(); reader.hidden = false; start.hidden = true; step.focus({preventScroll:true}); });
    const end = button('Terminar lectura', () => { reader.hidden = true; start.hidden = false; start.focus({preventScroll:true}); });
    reader.append(progress, step, previous, next, end); card.append(start, reader, button('Descargar original TXT', () => download(recipe)));
    const rights = recipe.rights || {};
    card.append(node('p', recipe.attribution || rights.attribution));
    link(card, 'Fuente original · Wikibooks', recipe.source_url);
    link(card, `Revisión conservada ${recipe.revid}`, recipe.source_revision_url);
    link(card, rights.license || 'CC BY-SA 4.0', recipe.license_url || rights.license_url);
    (rights.additional_attribution_urls || []).forEach(url => link(card, 'Crédito adicional de la fuente', url));
    if (rights.changes) { const changes = node('p', rights.changes, 'pet-product-method'); changes.lang = 'en'; card.append(changes); }
    card.append(node('p', 'Cantidades originales, sin conversión automática ni adaptación a tus alergias.', 'pet-product-method'));
    return card;
  }
  function render(container, {user, api, hidden = false}) {
    if (!container) return;
    const signature = JSON.stringify([user, hidden]);
    if (renders.get(container)?.signature === signature) return;
    const state = {signature, rows:[], loaded:false, pending:false}; renders.set(container, state);
    container.replaceChildren(); container.hidden = hidden; if (hidden) return;
    const current = () => renders.get(container) === state && container.isConnected && !container.hidden;
    const details = node('details', null, 'card kitchen-tools');
    details.append(node('summary', 'Recetas del mundo · fuentes originales'));
    details.append(node('p', 'Selección gratuita de Wikibooks, con raciones, ingredientes y pasos de la fuente. Originales en inglés para consultar, leer y descargar.'));
    const controls = node('div', null, 'kitchen-form'); controls.hidden = true;
    const cuisineLabel = node('label'); cuisineLabel.append(node('span', 'Cocina de la fuente'));
    const cuisine = node('select'); cuisine.append(node('option', 'Todas las cocinas')); cuisine.firstChild.value = ''; cuisineLabel.append(cuisine);
    const searchLabel = node('label'); searchLabel.append(node('span', 'Buscar en los originales (inglés)'));
    const search = node('input'); search.type = 'search'; search.maxLength = 100; search.placeholder = 'Ej. potato, rice, cheese'; searchLabel.append(search);
    const status = node('p'); status.setAttribute('role', 'status');
    const results = node('div', null, 'provider-recipe-results');
    const filter = () => {
      if (!current()) return;
      const query = key(search.value.trim());
      const visible = state.rows.filter(row => (!cuisine.value || row.cuisine === cuisine.value) &&
        key([row.title, row.cuisine, ...row.ingredients_original].join(' ')).includes(query));
      results.replaceChildren(...visible.map(recipeCard));
      status.textContent = visible.length ? `${visible.length} de ${state.rows.length} originales disponibles.` : 'No hay recetas de esta selección que coincidan. Prueba otro término en inglés.';
    };
    search.addEventListener('input', filter); cuisine.addEventListener('change', filter);
    controls.append(cuisineLabel, searchLabel); details.append(controls, status, results); container.append(details);
    details.addEventListener('toggle', async () => {
      if (!details.open || state.loaded || state.pending || !current()) return;
      state.pending = true; status.textContent = 'Cargando la selección de recetas…';
      try {
        const data = await api(`/v1/home-food/${encodeURIComponent(user)}/open-recipes`);
        if (!current()) return;
        if (data.status !== 'READY' || !Array.isArray(data.recipes)) throw new Error('catalog_unavailable');
        state.rows = data.recipes.slice(0, 24).filter(row => row && row.title && row.servings_original &&
          ['ingredients_original','steps_original','equipment_original','notes_original'].every(field => Array.isArray(row[field]) && row[field].every(value => typeof value === 'string')) &&
          row.ingredients_original.length && row.steps_original.length);
        [...new Set(state.rows.map(row => row.cuisine))].filter(Boolean).sort().forEach(value => {
          const option = node('option', countries[value] || value); option.value = value; cuisine.append(option);
        });
        state.loaded = true; controls.hidden = false; filter();
      } catch (_) { if (current()) status.textContent = 'No se pudo cargar la selección. Cierra y vuelve a abrir para intentarlo de nuevo.'; }
      finally { state.pending = false; }
    });
  }
  window.RoxyOpenRecipes = Object.freeze({render});
})();
