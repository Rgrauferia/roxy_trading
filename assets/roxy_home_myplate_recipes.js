(() => {
  'use strict';
  const renders = new WeakMap();
  const attribution = 'Recipes from the USDA MyPlate Kitchen collection, preserved at MyPlate.food';
  const node = (tag, text, className) => {
    const el = document.createElement(tag);
    if (text !== undefined && text !== null) el.textContent = text;
    if (className) el.className = className;
    return el;
  };
  const button = (text, action, className = 'myplate-button') => {
    const el = node('button', text, className); el.type = 'button'; el.addEventListener('click', action); return el;
  };
  const safeURL = (value, image = false) => {
    try {
      const url = new URL(value);
      if (url.protocol !== 'https:' || url.username || url.password || url.port || url.hash) return null;
      if (image) {
        if (url.hostname !== 'storage.googleapis.com' || !/^\/peppermint-cdn\/myplate\.food-recipe-images\/[a-z0-9][a-z0-9_-]*\.(?:webp|png|jpe?g)$/i.test(url.pathname) || url.search) return null;
      } else if (url.hostname !== 'myplate.food') return null;
      return url.href;
    } catch (_) { return null; }
  };
  const sourceLink = (parent, text, value) => {
    const url = safeURL(value); if (!url) return;
    const anchor = node('a', text); anchor.href = url; anchor.target = '_blank'; anchor.rel = 'noopener noreferrer';
    parent.append(anchor);
  };
  const photo = (recipe, large = false) => {
    const box = node('div', null, `myplate-photo${large ? ' myplate-photo-large' : ''}`);
    const empty = node('span', 'Fotografía no disponible en la fuente', 'myplate-photo-empty'); box.append(empty);
    const url = safeURL(recipe.image_url, true); if (!url) return box;
    const image = node('img'); image.alt = `${recipe.title} · imagen de MyPlate.food`;
    image.loading = 'lazy'; image.decoding = 'async'; image.referrerPolicy = 'no-referrer';
    image.width = 640; image.height = 440;
    empty.hidden = true; image.addEventListener('error', () => { image.remove(); empty.hidden = false; });
    image.src = url; box.append(image); return box;
  };
  const validSummary = row => row && typeof row.slug === 'string' && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(row.slug) &&
    typeof row.title === 'string' && row.title.trim() && row.language === 'en' && safeURL(row.source_url);
  const validDetail = (row, slug) => validSummary(row) && row.slug === slug &&
    row.can_cook === false && row.can_add_to_shopping === false &&
    Array.isArray(row.ingredients) && row.ingredients.length > 0 && row.ingredients.length <= 256 &&
    row.ingredients.every(item => item && typeof item.text === 'string' && item.text.trim() &&
      (item.note == null || typeof item.note === 'string')) &&
    typeof row.directions === 'string' && row.directions.trim();
  const errorText = (error, detail = false) => {
    if (Number(error?.status || error?.status_code) === 429) return 'La fuente alcanzó su límite de consultas. Inténtalo más tarde o abre la receta directamente en MyPlate.food. No se han generado instrucciones de reemplazo.';
    if (error?.name === 'TimeoutError') return 'La fuente está tardando demasiado. Puedes reintentar esta consulta; tus recetas guardadas no han cambiado.';
    return detail ? 'No pudimos cargar los ingredientes y la preparación originales. Reintenta o consulta la fuente.' :
      'No pudimos consultar el catálogo en este momento. Reintenta; tus recetas guardadas siguen disponibles más abajo.';
  };

  function setActive(container, active) { renders.get(container)?.activate(Boolean(active)); }

  function render(container, {user, identity = '', api, hidden = false, active = true, isCurrent = () => true}) {
    if (!container) return;
    const signature = JSON.stringify([user, identity, hidden]);
    const previous = renders.get(container);
    if (previous?.signature === signature) { previous.isCurrent = isCurrent; previous.activate(active); return; }
    previous?.dispose();
    const state = {signature, active:Boolean(active), isCurrent, generation:0, controller:null,
      busy:false, loaded:false, page:1, totalPages:0, canNext:false, category:'', query:'', selected:null};
    state.activate = () => {}; state.dispose = () => {};
    renders.set(container, state); container.replaceChildren(); container.hidden = hidden;
    if (hidden) return;

    const root = node('section', null, 'myplate-library');
    const heading = node('header', null, 'myplate-heading');
    const introduction = node('div'); introduction.append(node('p', 'UN RECETARIO PARA EXPLORAR', 'myplate-eyebrow'),
      node('h2', 'Más ideas para tu mesa'));
    const total = node('p', 'Catálogo en directo · MyPlate.food', 'myplate-total');
    introduction.append(total); heading.append(introduction);
    const intro = node('p', 'Comidas, bebidas, postres y más. Abre cada receta para consultar sus ingredientes y preparación originales.', 'myplate-intro');
    const language = node('p', 'Originales en inglés · enlace al español cuando la fuente lo ofrece.', 'myplate-note');
    const quota = node('p', 'Hasta 100 fichas completas al día en esta conexión compartida de Roxy; después puedes consultar la fuente.', 'myplate-note');
    const explore = button('Explorar recetas', () => void load(1), 'myplate-button myplate-primary');
    const start = node('div', null, 'myplate-start'); start.append(intro, explore);
    const browser = node('div', null, 'myplate-browser'); browser.hidden = true;
    const form = node('form', null, 'myplate-controls');
    const label = node('label'); label.append(node('span', 'Buscar en el catálogo'));
    const search = node('input'); search.type = 'search'; search.maxLength = 100; search.placeholder = 'Ej. pasta, chicken, smoothie';
    search.setAttribute('aria-label', 'Buscar en el catálogo'); label.append(search);
    const submit = node('button', 'Buscar recetas', 'myplate-button myplate-primary'); submit.type = 'submit'; form.append(label, submit);
    const categories = node('nav', null, 'myplate-categories'); categories.setAttribute('aria-label', 'Categorías del catálogo MyPlate');
    const status = node('p', '', 'myplate-status'); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite'); status.tabIndex = -1;
    const retry = button('Reintentar consulta', () => state.selected ? void openRecipe(state.selected) : void load(state.page)); retry.hidden = true;
    const grid = node('div', null, 'myplate-grid');
    const pagination = node('nav', null, 'myplate-pagination'); pagination.setAttribute('aria-label', 'Páginas del catálogo MyPlate'); pagination.hidden = true;
    const pageLabel = node('span');
    const prev = button('Página anterior', () => { if (state.page > 1) void load(state.page - 1); });
    const next = button('Página siguiente', () => { if (state.canNext) void load(state.page + 1); });
    pagination.append(prev, pageLabel, next);
    const clear = button('Ver todas', () => { search.value = ''; state.query = ''; state.category = ''; void load(1); }); clear.hidden = true;
    browser.append(form, categories, grid, clear, pagination);
    const detail = node('section', null, 'myplate-detail'); detail.hidden = true;
    const back = button('Volver a las recetas', () => closeDetail());
    const detailBody = node('div', null, 'myplate-detail-body'); detail.append(back, detailBody);
    const credit = node('details', null, 'myplate-credits'); credit.append(node('summary', 'Fuente, idioma y uso de estas recetas'));
    const creditText = node('p', attribution); creditText.lang = 'en';
    credit.append(creditText, node('p', 'MyPlate.food es un archivo independiente, no el sitio oficial del USDA. El catálogo se consulta en directo; no se descarga ni se guarda completo en Roxy.'),
      node('p', 'Conservamos el texto original, sin completar pasos con IA ni adaptar cantidades o alergias. La colección no equivale a recetas ensayadas individualmente por Roxy. Algunas imágenes de la fuente se han ampliado con IA.'),
      node('p', 'La fuente limita las consultas, incluido el número de fichas completas por día. La disponibilidad puede variar.'));
    sourceLink(credit, 'Conocer MyPlate.food', 'https://myplate.food/about');
    root.append(heading, language, quota, start, status, retry, browser, detail, credit); container.append(root);

    const current = () => renders.get(container) === state && state.active && !container.hidden && container.isConnected && !document.hidden && state.isCurrent();
    const controls = () => [explore, submit, search, prev, next, clear, ...Array.from(categories.children)];
    const setBusy = value => {
      state.busy = value; root.setAttribute('aria-busy', String(value));
      controls().forEach(control => { control.disabled = value; });
      if (!value) { prev.disabled = state.page <= 1; next.disabled = !state.canNext; }
    };
    const stop = () => { state.generation++; state.controller?.abort(); state.controller = null; setBusy(false); };
    const purgeDetail = () => { state.selected = null; detailBody.replaceChildren(); detail.hidden = true; };
    const closeDetail = () => {
      stop(); purgeDetail(); retry.hidden = true; status.textContent = ''; browser.hidden = !state.loaded;
      start.hidden = state.loaded; if (state.loaded) search.focus({preventScroll:true});
    };
    const request = (path, controller) => new Promise((resolve, reject) => {
      let settled = false;
      const finish = (action, value) => {
        if (settled) return; settled = true; clearTimeout(timer); controller.signal.removeEventListener('abort', aborted); action(value);
      };
      const aborted = () => finish(reject, Object.assign(new Error('cancelled'), {name:'AbortError'}));
      const timer = setTimeout(() => { finish(reject, Object.assign(new Error('timeout'), {name:'TimeoutError'})); controller.abort(); }, 12000);
      controller.signal.addEventListener('abort', aborted, {once:true});
      if (controller.signal.aborted) { aborted(); return; }
      Promise.resolve().then(() => {
        if (controller.signal.aborted) throw Object.assign(new Error('cancelled'), {name:'AbortError'});
        return api(path, {method:'GET', signal:controller.signal});
      }).then(value => finish(resolve, value), error => finish(reject, error));
    });
    const categoryLabels = {'Main dish':'Comidas', Dessert:'Postres', Beverage:'Bebidas', Salad:'Ensaladas', Soup:'Sopas'};
    const categoryButtons = values => {
      categories.replaceChildren();
      const choices = [{value:'', label:'Todas'}, ...values.map(value => ({value, label:categoryLabels[value] || value})),
        {query:'pasta', label:'Pastas'}, {query:'breakfast', label:'Desayunos'}];
      choices.forEach(({value = '', label:categoryLabel, query = ''}) => {
        const item = button(categoryLabel, () => {
          state.category = value; state.query = query; search.value = query; void load(1);
        }, 'myplate-category');
        if (query) item.title = `Buscar “${query}” en la fuente`;
        item.setAttribute('aria-pressed', String(state.category === value && state.query === query)); categories.append(item);
      });
    };
    categoryButtons(['Main dish', 'Dessert', 'Beverage', 'Salad', 'Soup']);
    const card = summary => {
      const article = node('article', null, 'myplate-recipe-card');
      article.append(photo(summary));
      const body = node('div', null, 'myplate-card-body');
      const title = node('h3', summary.title); title.lang = 'en';
      const meta = node('p', summary.category ? `${summary.category} · EN` : 'Original en inglés', 'myplate-card-meta');
      const open = button('Ver receta', () => { if (!state.busy) void openRecipe(summary); });
      open.setAttribute('aria-label', `Ver receta: ${summary.title}`); body.append(title, meta, open); article.append(body); return article;
    };
    async function load(page) {
      if (!current() || state.busy) return;
      stop(); purgeDetail(); state.page = page; state.loaded = false; retry.hidden = true; start.hidden = true;
      browser.hidden = false; grid.replaceChildren(); clear.hidden = true; pagination.hidden = true;
      const generation = state.generation, controller = new AbortController(); state.controller = controller; setBusy(true);
      status.textContent = 'Consultando las recetas de la fuente…';
      const offset = (page - 1) * 24;
      const params = new URLSearchParams({requested:'true', q:state.query, category:state.category, offset:String(offset), limit:'24'});
      try {
        const data = await request(`/v1/home-food/${encodeURIComponent(user)}/myplate-recipes?${params}`, controller);
        if (!current() || generation !== state.generation || controller.signal.aborted) return;
        if (data.provider !== 'MyPlate.food' || data.live !== true || !Array.isArray(data.recipes) || data.recipes.length > 24 ||
          !data.recipes.every(validSummary) || new Set(data.recipes.map(row => row.slug)).size !== data.recipes.length ||
          !Number.isInteger(data.total) || data.total < 0 || data.offset !== offset || data.limit !== 24 ||
          !(data.next_offset === null || data.next_offset === offset + 24)) throw new Error('invalid_catalog');
        state.totalPages = Math.ceil(data.total / 24); state.canNext = data.next_offset !== null; state.loaded = true;
        grid.replaceChildren(...data.recipes.map(card));
        if (Array.isArray(data.category_options) && data.category_options.length <= 30 && data.category_options.every(value =>
          typeof value === 'string' && value.trim())) categoryButtons(data.category_options);
        total.textContent = `${data.total.toLocaleString('es')} recetas${state.query || state.category ? ' en esta selección' : ' en el catálogo'} · consulta en directo`;
        status.textContent = data.recipes.length ? `${offset + 1}–${offset + data.recipes.length} de ${data.total} · ingredientes y preparación al abrir cada ficha.` :
          'No encontramos recetas con estos filtros. Prueba otra palabra en inglés o vuelve a ver todas.';
        clear.hidden = !state.query && !state.category;
        pageLabel.textContent = `Página ${page} de ${Math.max(1, state.totalPages)}`;
        pagination.hidden = !data.recipes.length || state.totalPages <= 1;
        status.focus({preventScroll:false});
      } catch (error) {
        if (!current() || generation !== state.generation || (controller.signal.aborted && error?.name !== 'TimeoutError')) return;
        status.textContent = errorText(error); retry.hidden = false;
      } finally { if (generation === state.generation) { state.controller = null; setBusy(false); } }
    }
    async function openRecipe(summary) {
      if (!current() || state.busy) return;
      stop(); purgeDetail(); state.selected = summary; browser.hidden = true; detail.hidden = false; retry.hidden = true;
      detailBody.append(node('h3', summary.title));
      const generation = state.generation, controller = new AbortController(); state.controller = controller; setBusy(true);
      status.textContent = 'Cargando ingredientes y preparación originales…';
      try {
        const data = await request(`/v1/home-food/${encodeURIComponent(user)}/myplate-recipes/${encodeURIComponent(summary.slug)}?requested=true`, controller);
        if (!current() || generation !== state.generation || controller.signal.aborted) return;
        if (!validDetail(data.recipe, summary.slug)) throw new Error('invalid_recipe');
        showRecipe(data.recipe, summary); status.textContent = 'Ficha original cargada. No se han generado ni sustituido instrucciones.';
      } catch (error) {
        if (!current() || generation !== state.generation || (controller.signal.aborted && error?.name !== 'TimeoutError')) return;
        status.textContent = errorText(error, true); retry.hidden = false;
        sourceLink(detailBody, 'Abrir receta en MyPlate.food', summary.source_url);
      } finally { if (generation === state.generation) { state.controller = null; setBusy(false); } }
    }
    function showRecipe(recipe, summary) {
      detailBody.replaceChildren();
      const title = node('h3', recipe.title, 'myplate-detail-title'); title.lang = 'en'; title.tabIndex = -1;
      detailBody.append(title, node('p', 'Texto original en inglés · sin adaptar ingredientes ni cantidades', 'myplate-note'), photo(recipe, true));
      if (recipe.description) { const description = node('p', recipe.description); description.lang = 'en'; detailBody.append(description); }
      const amounts = node('div', null, 'myplate-amounts');
      if (recipe.yield) amounts.append(node('p', `Rendimiento de la fuente: ${recipe.yield}`));
      if (recipe.serving_size) amounts.append(node('p', `Porción de la fuente: ${recipe.serving_size}`));
      if (amounts.children.length) detailBody.append(amounts);
      detailBody.append(node('h4', 'Ingredients · ingredientes originales'));
      const ingredients = node('ul', null, 'myplate-ingredients'); ingredients.lang = 'en';
      recipe.ingredients.forEach(item => {
        const li = node('li'); li.append(node('span', item.text));
        if (item.note) li.append(node('small', item.note)); ingredients.append(li);
      });
      detailBody.append(ingredients, node('h4', 'Directions · preparación original'));
      const directions = node('div', recipe.directions, 'myplate-directions'); directions.lang = 'en'; detailBody.append(directions);
      if (recipe.notes) { const notes = node('p', recipe.notes, 'myplate-source-notes'); notes.lang = 'en'; detailBody.append(node('h4', 'Notes · notas de la fuente'), notes); }
      if (recipe.contributor) detailBody.append(node('p', `Autor o colaborador de la fuente: ${recipe.contributor}`, 'myplate-note'));
      const links = node('div', null, 'myplate-source-links');
      sourceLink(links, 'Ver receta en la fuente', recipe.source_url);
      sourceLink(links, 'Leer en español en la fuente', recipe.translation_urls?.es || summary.translation_urls?.es);
      detailBody.append(links);
      const originalCredit = node('p', attribution, 'myplate-note'); originalCredit.lang = 'en'; detailBody.append(originalCredit,
        node('p', 'Revisa los ingredientes por alergias y consulta la preparación completa antes de empezar. Esta lectura no modifica tu plan de comidas ni tu lista de compras.', 'myplate-note'));
      title.focus({preventScroll:false});
    }
    form.addEventListener('submit', event => {
      event.preventDefault(); if (state.busy) return;
      state.query = search.value.trim().slice(0,100); void load(1);
    });
    state.activate = value => {
      state.active = Boolean(value);
      if (current()) return;
      const wasBusy = state.busy, hadDetail = Boolean(state.selected); stop(); purgeDetail();
      if (hadDetail) { browser.hidden = !state.loaded; start.hidden = state.loaded; }
      if (wasBusy) { status.textContent = 'Consulta pausada. Pulsa Reintentar consulta para continuar.'; retry.hidden = false; }
    };
    const visibility = () => state.activate(state.active);
    document.addEventListener('visibilitychange', visibility);
    state.dispose = () => { stop(); purgeDetail(); document.removeEventListener('visibilitychange', visibility); };
  }
  window.RoxyMyPlateRecipes = Object.freeze({render, setActive});
})();
