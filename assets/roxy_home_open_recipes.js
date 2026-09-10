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
  const translationOf = recipe => {
    const value = recipe.translation;
    if (!value || value.language !== 'es' || value.source_id !== recipe.id ||
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
    card.addEventListener('toggle', () => { if (card.open && !photo.src) photo.src = image.href; });
    card.append(node('p', recipe.photo_scope, 'pet-product-method'), node('p', `Foto: ${recipe.image_author} · ${recipe.image_license}`, 'pet-product-method'));
    link(card, 'Fotografía y créditos · Wikimedia Commons', recipe.image_source_url); link(card, 'Licencia de esta fotografía', recipe.image_license_url);
    if (recipe.image_changes) { const changes = node('p', recipe.image_changes, 'pet-product-method'); changes.lang = 'en'; card.append(changes); }
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
  function recipeCard(recipe) {
    const spanish = translationOf(recipe);
    let useSpanish = Boolean(spanish);
    const original = {title:recipe.title, time:recipe.time_original, ingredients:recipe.ingredients_original,
      steps:recipe.steps_original, equipment:recipe.equipment_original, notes:recipe.notes_original};
    const content = () => useSpanish ? spanish : original;
    const language = () => useSpanish ? 'es' : 'en';
    const card = node('details', null, 'provider-recipe-card'); const title = node('summary'); card.append(title);
    card.append(node('p', [countries[recipe.cuisine] || recipe.cuisine,
      `${recipe.servings_original} ${recipe.servings === 1 ? 'ración' : 'raciones'}`].filter(Boolean).join(' · ')));
    const languageLabel = node('p', null, 'pet-product-method'); card.append(languageLabel);
    const languageButton = button('Ver original en inglés', () => { useSpanish = !useSpanish; showContent(); showStep(); });
    if (spanish) card.append(languageButton);
    const time = node('p'); card.append(time);
    if (spanish?.editorial_notes?.length) {
      const notes = node('aside', null, 'pet-product-method');
      originalList(notes, 'Antes de usar esta fuente · notas de Roxy', spanish.editorial_notes, false, 'es');
      card.append(notes);
    }
    sourcePhoto(card, recipe);
    const body = node('div'); card.append(body);
    const showContent = () => {
      const value = content(); title.textContent = value.title; title.lang = language();
      time.textContent = value.time; time.lang = language(); time.hidden = !value.time;
      languageLabel.textContent = useSpanish ? 'Traducción al español de la revisión enlazada. Sin cambiar cantidades, tiempos ni pasos; no es una adaptación a alergias ni una receta ensayada por Roxy.' : 'Original en inglés de la revisión enlazada. No es una receta ensayada por Roxy.';
      languageButton.textContent = useSpanish ? 'Ver original en inglés' : 'Ver traducción al español';
      body.replaceChildren();
      originalList(body, useSpanish ? 'Ingredientes · medidas de la fuente' : 'Ingredients · medidas originales', value.ingredients, false, language());
      originalList(body, useSpanish ? 'Equipo' : 'Equipment · equipo de la fuente', value.equipment, false, language());
      originalList(body, useSpanish ? 'Preparación · pasos de la fuente' : 'Instructions · pasos originales', value.steps, true, language());
      originalList(body, useSpanish ? 'Notas y variantes de la fuente' : 'Notes · notas originales', value.notes, false, language());
    };
    const reader = node('section', null, 'open-recipe-reader'); reader.hidden = true;
    const progress = node('p'); progress.setAttribute('role', 'status');
    const step = node('p', null, 'provider-original-instructions'); step.lang = 'en'; step.tabIndex = -1;
    let position = 0;
    const showStep = () => { progress.textContent = `Paso ${position + 1} de ${recipe.steps_original.length}`;
      step.textContent = content().steps[position]; step.lang = language(); previous.disabled = position === 0; next.disabled = position === recipe.steps_original.length - 1; };
    const previous = button('Anterior', () => { if (position > 0) { position--; showStep(); } });
    const next = button('Siguiente', () => { if (position < recipe.steps_original.length - 1) { position++; showStep(); } });
    const start = button('Leer paso a paso', () => { position = 0; showStep(); reader.hidden = false; start.hidden = true; step.focus({preventScroll:true}); });
    const end = button('Terminar lectura', () => { reader.hidden = true; start.hidden = false; start.focus({preventScroll:true}); });
    reader.append(progress, step, previous, next, end); card.append(start, reader, button('Descargar original TXT', () => download(recipe)));
    if (spanish) card.append(button('Descargar traducción TXT', () => download(recipe, true)),
      node('p', `${spanish.attribution} · ${spanish.license}`, 'pet-product-method'), node('p', spanish.changes, 'pet-product-method'));
    const rights = recipe.rights || {};
    card.append(node('p', recipe.attribution || rights.attribution));
    link(card, 'Fuente original · Wikibooks', recipe.source_url);
    link(card, `Revisión conservada ${recipe.revid}`, recipe.source_revision_url);
    link(card, rights.license || 'CC BY-SA 4.0', recipe.license_url || rights.license_url);
    (rights.additional_attribution_urls || []).forEach(url => link(card, 'Crédito adicional de la fuente', url));
    if (rights.changes) { const changes = node('p', rights.changes, 'pet-product-method'); changes.lang = 'en'; card.append(changes); }
    card.append(node('p', 'Cantidades originales, sin conversión automática ni adaptación a tus alergias.', 'pet-product-method'));
    showContent();
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
    details.append(node('p', 'Selección gratuita de Wikibooks, con raciones, ingredientes y pasos de la fuente. Traducciones al español cuando están revisadas; el original en inglés permanece disponible para comparar y descargar.'));
    const controls = node('div', null, 'kitchen-form'); controls.hidden = true;
    const cuisineLabel = node('label'); cuisineLabel.append(node('span', 'Cocina de la fuente'));
    const cuisine = node('select'); cuisine.append(node('option', 'Todas las cocinas')); cuisine.firstChild.value = ''; cuisineLabel.append(cuisine);
    const searchLabel = node('label'); searchLabel.append(node('span', 'Buscar en español o inglés'));
    const search = node('input'); search.type = 'search'; search.maxLength = 100; search.placeholder = 'Ej. papas, rice, queso'; searchLabel.append(search);
    const status = node('p'); status.setAttribute('role', 'status');
    const results = node('div', null, 'provider-recipe-results');
    const filter = () => {
      if (!current()) return;
      const query = key(search.value.trim());
      const visible = state.rows.filter(row => {
        const translated = translationOf(row);
        return (!cuisine.value || row.cuisine === cuisine.value) &&
          key([row.title, row.cuisine, ...row.ingredients_original, translated?.title || '', ...(translated?.ingredients || [])].join(' ')).includes(query);
      });
      results.replaceChildren(...visible.map(recipeCard));
      status.textContent = visible.length ? `${visible.length} de ${state.rows.length} originales disponibles.` : 'No hay recetas de esta selección que coincidan. Prueba otra palabra o cocina.';
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
