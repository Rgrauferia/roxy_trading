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
      'No pudimos consultar el catálogo en este momento. Reintenta; tus recetas guardadas siguen en Mi recetario.';
  };

  function setActive(container, active) { renders.get(container)?.activate(Boolean(active)); }

  function render(container, {user, identity = '', api, companion, speech, hidden = false, active = true, isCurrent = () => true,
    browseGroup = 'all', autoLoad = false, preset = null, personalRevision = 0}) {
    if (!container) return;
    const group = ['all', 'food', 'dessert'].includes(browseGroup) ? browseGroup : 'all';
    const personal = browseGroup === 'personal' && preset && typeof preset.query === 'string' && preset.query.length <= 100;
    const signature = JSON.stringify([user, identity, hidden, personalRevision, personal ? [preset.id,preset.query,preset.category] : null]);
    const previous = renders.get(container);
    if (previous?.signature === signature) {
      previous.isCurrent = isCurrent; previous.configure?.(group, Boolean(autoLoad)); previous.activate(active); return;
    }
    previous?.dispose();
    const state = {signature, active:Boolean(active), isCurrent, generation:0, controller:null,
      busy:false, loaded:false, page:1, totalPages:0, canNext:false, deadline:0, expire:null,
      group, autoLoad:Boolean(autoLoad), initialLoadRequested:Boolean(autoLoad), loadAttempted:false,
      category:personal ? preset.category || '' : group === 'food' ? 'Main dish' : group === 'dessert' ? 'Dessert' : '', query:personal ? preset.query : '', selected:null,
      categoryOptions:['Main dish', 'Dessert', 'Beverage', 'Salad', 'Soup', 'Breakfast', 'Bread', 'Side dish']};
    state.activate = () => {}; state.dispose = () => {};
    renders.set(container, state); container.replaceChildren(); container.hidden = hidden;
    if (hidden) return;

    const root = node('section', null, 'myplate-library');
    const heading = node('header', null, 'myplate-heading');
    const introduction = node('div');
    const title = node('h2'); introduction.append(title);
    const total = node('p', 'Originales en inglés · MyPlate.food', 'myplate-total');
    introduction.append(total); heading.append(introduction);
    const intro = node('p', 'Abre una receta para ver sus ingredientes y preparación originales.', 'myplate-intro');
    const language = node('p', 'Originales en inglés · enlace al español cuando existe.', 'myplate-note myplate-language');
    const quota = node('p', '100 fichas completas/día · cupo compartido de Roxy; después, consulta la fuente.', 'myplate-note myplate-quota');
    const explore = button('Explorar recetas', () => void load(1), 'myplate-button myplate-primary');
    const start = node('div', null, 'myplate-start'); start.append(intro, explore);
    const browser = node('div', null, 'myplate-browser'); browser.hidden = true;
    const form = node('form', null, 'myplate-controls');
    const label = node('label'); label.append(node('span', 'Buscar en el catálogo'));
    const search = node('input'); search.type = 'search'; search.maxLength = 100; search.placeholder = 'Ej. pasta, chicken, smoothie';
    search.setAttribute('aria-label', 'Buscar en el catálogo'); label.append(search);
    search.value = state.query;
    const submit = node('button', 'Buscar recetas', 'myplate-button myplate-primary'); submit.type = 'submit'; form.append(label, submit);
    const categories = node('nav', null, 'myplate-categories'); categories.setAttribute('aria-label', 'Categorías del catálogo MyPlate');
    const filterHint = node('p', '', 'myplate-filter-hint');
    const status = node('p', '', 'myplate-status'); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite'); status.tabIndex = -1;
    const personalNotice = node('p', '', 'myplate-note'); personalNotice.hidden = true;
    const retry = button('Reintentar consulta', () => state.selected ? void openRecipe(state.selected) : void load(state.page)); retry.hidden = true;
    const cancel = button('Cancelar consulta', () => { stop(); paused(); }); cancel.hidden = true;
    const grid = node('div', null, 'myplate-grid');
    const pagination = node('nav', null, 'myplate-pagination'); pagination.setAttribute('aria-label', 'Páginas del catálogo MyPlate'); pagination.hidden = true;
    const pageLabel = node('span');
    const prev = button('Página anterior', () => { if (state.page > 1) void load(state.page - 1); });
    const next = button('Página siguiente', () => { if (state.canNext) void load(state.page + 1); });
    pagination.append(prev, pageLabel, next);
    const baseCategory = () => state.group === 'food' ? 'Main dish' : state.group === 'dessert' ? 'Dessert' : '';
    const clear = button('Ver todas', () => { search.value = ''; state.query = ''; state.category = baseCategory(); void load(1); }); clear.hidden = true;
    browser.append(form, categories, filterHint, grid, clear, pagination);
    const detail = node('section', null, 'myplate-detail'); detail.hidden = true;
    const back = button('Volver a las recetas', () => closeDetail());
    const detailBody = node('div', null, 'myplate-detail-body'); detail.append(back, detailBody);
    const information = label => {
      const control = node('details', null, 'myplate-credits myplate-information');
      const summary = node('summary'); summary.setAttribute('aria-label', label); summary.title = label;
      const icon = node('span', 'info', 'material-symbols-rounded'); icon.setAttribute('aria-hidden', 'true'); summary.append(icon);
      const content = node('div', null, 'myplate-information-content'); content.append(node('h4', label));
      const close = button('Cerrar información', () => { control.open = false; summary.focus({preventScroll:true}); });
      content.append(close); control.append(summary, content);
      control.addEventListener('keydown', event => { if (event.key === 'Escape') { event.preventDefault(); control.open = false; summary.focus({preventScroll:true}); } });
      return {control, content};
    };
    const catalogueInfo = information('Información del recetario'), credit = catalogueInfo.control;
    const creditText = node('p', attribution); creditText.lang = 'en';
    catalogueInfo.content.append(creditText, language, quota, node('p', 'MyPlate.food es un archivo independiente, no el sitio oficial del USDA. El catálogo se consulta en directo; no se descarga ni se guarda completo en Roxy.'),
      node('p', 'Conservamos el texto original, sin completar pasos con IA ni adaptar cantidades o alergias. La colección no equivale a recetas ensayadas individualmente por Roxy. Algunas imágenes de la fuente se han ampliado con IA.'),
      node('p', 'La fuente permite hasta 20 consultas por minuto. La disponibilidad puede variar.'));
    sourceLink(catalogueInfo.content, 'Conocer MyPlate.food', 'https://myplate.food/about');
    heading.append(credit);
    root.append(heading, start, status, personalNotice, retry, cancel, browser, detail); container.append(root);

    const current = () => renders.get(container) === state && state.active && !container.hidden && !container.closest?.('[hidden]') && container.isConnected && !document.hidden && state.isCurrent();
    const controls = () => [explore, submit, search, retry, prev, next, clear, ...Array.from(categories.children)];
    const setBusy = value => {
      state.busy = value; root.setAttribute('aria-busy', String(value)); cancel.hidden = !value;
      controls().forEach(control => { control.disabled = value; });
      if (!value) { prev.disabled = state.page <= 1; next.disabled = !state.canNext; }
    };
    const stop = () => { state.generation++; state.controller?.abort(); state.controller = null; state.deadline = 0; state.expire = null; setBusy(false); };
    const paused = () => { status.textContent = 'Consulta interrumpida. Puedes reintentar cuando quieras.'; retry.hidden = false; };
    const purgeDetail = () => { state.guide?.dispose(); state.guide = null; state.selected = null; detailBody.replaceChildren(); detail.hidden = true; heading.hidden = false; credit.open = false; };
    const closeDetail = () => {
      stop(); purgeDetail(); retry.hidden = true; status.textContent = ''; browser.hidden = !state.loaded;
      start.hidden = state.loaded; if (state.loaded) search.focus({preventScroll:true});
    };
    const request = (path, controller) => new Promise((resolve, reject) => {
      let settled = false;
      const finish = (action, value) => {
        if (settled) return; settled = true; clearTimeout(timer); controller.signal.removeEventListener('abort', aborted);
        if (state.controller === controller) { state.deadline = 0; state.expire = null; }
        action(value);
      };
      const aborted = () => finish(reject, Object.assign(new Error('cancelled'), {name:'AbortError'}));
      const expire = () => { finish(reject, Object.assign(new Error('timeout'), {name:'TimeoutError'})); controller.abort(); };
      const timer = setTimeout(expire, 12000);
      state.deadline = Date.now() + 12000; state.expire = expire;
      controller.signal.addEventListener('abort', aborted, {once:true});
      if (controller.signal.aborted) { aborted(); return; }
      Promise.resolve().then(() => {
        if (controller.signal.aborted) throw Object.assign(new Error('cancelled'), {name:'AbortError'});
        return api(path, {method:'GET', signal:controller.signal});
      }).then(value => finish(resolve, value), error => finish(reject, error));
    });
    const categoryLabels = {'Main dish':'Platos principales', Dessert:'Postres', Beverage:'Bebidas', Salad:'Ensaladas', Soup:'Sopas',
      Breakfast:'Desayunos', Bread:'Panes', 'Side dish':'Acompañamientos', Snack:'Meriendas'};
    const nativeOrQuery = (value, query, label) => state.categoryOptions.includes(value) ? {value, label} : {query, label};
    const categoryButtons = () => {
      categories.replaceChildren();
      categories.hidden = state.group === 'all' && state.autoLoad;
      const choices = state.group === 'food' ? [
        nativeOrQuery('Breakfast', 'breakfast', 'Desayunos'), {value:'Main dish', label:'Platos principales'},
        {query:'pasta', label:'Pastas'}, {query:'rice', label:'Arroces'}, {value:'Salad', label:'Ensaladas'},
        {value:'Soup', label:'Sopas'}, nativeOrQuery('Bread', 'bread', 'Panes'),
        nativeOrQuery('Side dish', 'side dish', 'Acompañamientos'),
      ] : state.group === 'dessert' ? [{value:'Dessert', label:'Todos los postres'},
        {value:'Dessert', query:'cake', label:'Pasteles'}, {value:'Dessert', query:'cookie', label:'Galletas'},
        {value:'Dessert', query:'fruit', label:'Frutas'}] :
        [{value:'', label:'Todas'}, ...state.categoryOptions.map(value => ({value, label:categoryLabels[value] || value})),
          {query:'pasta', label:'Pastas'}, ...(state.categoryOptions.includes('Breakfast') ? [] : [{query:'breakfast', label:'Desayunos'}])];
      choices.forEach(({value = '', label:categoryLabel, query = ''}) => {
        const item = button(categoryLabel, () => {
          state.category = value; state.query = query; search.value = query; void load(1);
        }, 'myplate-category');
        if (query) item.title = `Buscar “${query}” en la fuente`;
        item.setAttribute('aria-pressed', String(state.category === value && state.query === query)); categories.append(item);
      });
      filterHint.textContent = state.query ? `“${state.query}”${state.category ? ` · ${categoryLabels[state.category] || state.category}` : ''}` : '';
      filterHint.hidden = !filterHint.textContent;
    };
    const groupHeading = () => {
      title.textContent = personal ? preset.label : state.group === 'food' ? 'Comidas para tu mesa' : state.group === 'dessert' ? 'Un momento dulce' : 'Explora el recetario';
      clear.textContent = state.group === 'food' ? 'Volver a platos principales' : state.group === 'dessert' ? 'Ver todos los postres' : 'Ver todas';
      search.placeholder = state.group === 'dessert' ? 'Ej. chocolate, apple, cake' : state.group === 'food' ? 'Ej. chicken, pasta, rice' : 'Ej. pasta, chicken, smoothie';
    };
    groupHeading(); categoryButtons();
    const card = summary => {
      const article = node('article', null, 'myplate-recipe-card');
      article.append(photo(summary));
      const body = node('div', null, 'myplate-card-body');
      const title = node('h3', summary.title); title.lang = 'en'; title.tabIndex = -1;
      const meta = node('p', summary.category ? `${categoryLabels[summary.category] || summary.category} · EN` : 'Original en inglés', 'myplate-card-meta');
      const open = button('Ver receta', () => { if (!state.busy) void openRecipe(summary); });
      open.setAttribute('aria-label', `Ver receta: ${summary.title}`);
      const prepare = button('Preparar con Roxy', () => { if (!state.busy) void openRecipe(summary, true); }, 'myplate-button myplate-primary');
      prepare.setAttribute('aria-label', `Preparar con Roxy: ${summary.title}`);
      body.append(title, meta, prepare, open); article.append(body); return article;
    };
    async function load(page, {focus = true} = {}) {
      if (!current() || state.busy) return;
      stop(); purgeDetail(); state.page = page; state.loaded = false; state.initialLoadRequested = false; state.loadAttempted = true;
      retry.hidden = true; start.hidden = true; personalNotice.hidden = true; personalNotice.textContent = ''; categoryButtons();
      browser.hidden = false; grid.replaceChildren(); clear.hidden = true; pagination.hidden = true;
      total.textContent = 'Originales en inglés · MyPlate.food';
      const generation = state.generation, controller = new AbortController(); state.controller = controller; setBusy(true);
      status.textContent = 'Consultando las recetas de la fuente…';
      const offset = (page - 1) * 24;
      const params = new URLSearchParams({requested:'true', q:state.query, category:state.category, offset:String(offset), limit:'24'});
      try {
        const data = await request(`/v1/home-food/${encodeURIComponent(user)}/myplate-recipes?${params}`, controller);
        if (generation !== state.generation || controller.signal.aborted) return;
        if (!current()) { paused(); return; }
        if (!data || data.provider !== 'MyPlate.food' || data.live !== true || !Array.isArray(data.recipes) || data.recipes.length > 24 ||
          !data.recipes.every(validSummary) || new Set(data.recipes.map(row => row.slug)).size !== data.recipes.length ||
          !Number.isInteger(data.total) || data.total < 0 || data.offset !== offset || data.limit !== 24 ||
          !(data.next_offset === null || data.next_offset === offset + 24) ||
          !(data.hidden_in_page == null || (Number.isInteger(data.hidden_in_page) && data.hidden_in_page >= 0 && data.hidden_in_page + data.recipes.length <= 24))) throw new Error('invalid_catalog');
        state.totalPages = Math.ceil(data.total / 24); state.canNext = data.next_offset !== null; state.loaded = true;
        grid.replaceChildren(...data.recipes.map(card));
        if (Array.isArray(data.category_options) && data.category_options.length <= 30 && data.category_options.every(value =>
          typeof value === 'string' && value.trim())) { state.categoryOptions = data.category_options; categoryButtons(); }
        const filtered = Number.isInteger(data.hidden_in_page), hiddenCount = data.hidden_in_page || 0;
        total.textContent = `${data.total.toLocaleString('es')} ${filtered ? 'coincidencias en la fuente' : 'recetas'} · originales en inglés`;
        status.textContent = filtered && hiddenCount ? `${hiddenCount} recetas ocultas en esta página por posibles conflictos con tus preferencias.` : data.recipes.length ? '' :
          'No encontramos recetas con estos filtros. Prueba otra palabra en inglés o vuelve a ver todas.';
        if (filtered && !data.recipes.length && hiddenCount) status.textContent += state.canNext ? ' Puedes probar la página siguiente.' : ' Prueba otra selección.';
        if (typeof data.personal_notice === 'string') {personalNotice.textContent = data.personal_notice; personalNotice.hidden = !data.personal_notice;}
        clear.hidden = !state.query && state.category === baseCategory();
        pageLabel.textContent = `Página ${page} de ${Math.max(1, state.totalPages)}`;
        pagination.hidden = state.totalPages <= 1;
        if (focus) {
          const firstCard = grid.firstChild, firstTitle = firstCard?.querySelector('h3');
          if (firstTitle) { firstTitle.focus({preventScroll:true}); firstCard.scrollIntoView({block:'start', behavior:'auto'}); }
          else status.focus({preventScroll:false});
        }
      } catch (error) {
        if (generation !== state.generation) return;
        if (!current() || (controller.signal.aborted && error?.name !== 'TimeoutError')) { paused(); return; }
        status.textContent = errorText(error); retry.hidden = false;
        if (focus) status.focus({preventScroll:false});
      } finally { if (generation === state.generation) { state.controller = null; setBusy(false); } }
    }
    async function openRecipe(summary, prepare = false) {
      if (!current() || state.busy) return;
      stop(); purgeDetail(); state.selected = summary; browser.hidden = true; detail.hidden = false; heading.hidden = true; retry.hidden = true;
      detailBody.append(node('h3', summary.title));
      const generation = state.generation, controller = new AbortController(); state.controller = controller; setBusy(true);
      status.textContent = 'Cargando ingredientes y preparación originales…';
      try {
        const data = await request(`/v1/home-food/${encodeURIComponent(user)}/myplate-recipes/${encodeURIComponent(summary.slug)}?requested=true`, controller);
        if (generation !== state.generation || controller.signal.aborted) return;
        if (!current()) { paused(); return; }
        if (!validDetail(data?.recipe, summary.slug)) throw new Error('invalid_recipe');
        showRecipe(data.recipe, summary, data.companion_version, prepare); status.textContent = '';
      } catch (error) {
        if (generation !== state.generation) return;
        if (!current() || (controller.signal.aborted && error?.name !== 'TimeoutError')) { paused(); return; }
        status.textContent = errorText(error, true); retry.hidden = false;
        sourceLink(detailBody, 'Abrir receta en MyPlate.food', summary.source_url);
        status.focus({preventScroll:false});
      } finally { if (generation === state.generation) { state.controller = null; setBusy(false); } }
    }
    function showRecipe(recipe, summary, companionVersion, prepare = false) {
      detailBody.replaceChildren();
      const title = node('h3', recipe.title, 'myplate-detail-title'); title.lang = 'en'; title.tabIndex = -1;
      const recipeHeading = node('div', null, 'myplate-detail-heading'); recipeHeading.append(title);
      detailBody.append(recipeHeading, node('p', 'Original en inglés · voz en inglés', 'myplate-note'), photo(recipe, true));
      const fit = recipe.personal_fit;
      if (fit && ['conflict','needs_review','unrestricted'].includes(fit.status)) {
        const assessment = node('aside', null, 'myplate-personal-fit'); assessment.setAttribute('role','status');
        assessment.append(node('strong', fit.status === 'conflict' ? 'Esta receta entra en conflicto con tus respuestas' : 'Antes de cocinar'));
        if (Array.isArray(fit.conflicts)) fit.conflicts.forEach(text => { if (typeof text === 'string') assessment.append(node('p',text)); });
        if (typeof fit.caution === 'string') assessment.append(node('p',fit.caution));
        detailBody.append(assessment);
      }
      const recipeBody = node('div'); const guideHost = node('div');
      const sourceSteps = Array.isArray(recipe.source_steps) && recipe.source_steps_language === 'en' &&
        recipe.source_steps.every(step => typeof step === 'string' && step.trim()) && recipe.source_steps.join('') === recipe.directions ? recipe.source_steps : [recipe.directions];
      const beginGuide = () => {
        if (!current() || detail.hidden || !window.RoxyRecipeGuide?.mount) return;
        state.guide?.dispose(); recipeBody.hidden = true; startGuide.hidden = true;
        const guide = window.RoxyRecipeGuide.mount(guideHost, {title:recipe.title, steps:sourceSteps,
          ingredients:recipe.ingredients.map(item => item.note ? `${item.text} (${item.note})` : item.text),
          language:'en', startWithVoice:true, sourceLabel:'MyPlate.food · original en inglés',
          requestSpeech:typeof speech==='function'?params=>speech({...params,source:'myplate',recipe_id:recipe.slug,recipe_version:companionVersion}):undefined,
          askQuestion:typeof companion==='function'&&/^[a-f0-9]{64}$/.test(companionVersion||'')?
            params=>companion({...params,source:'myplate',recipe_id:recipe.slug,recipe_version:companionVersion}):undefined,
          isCurrent:() => current() && !detail.hidden && state.selected?.slug === recipe.slug,
          onClose:() => { if (state.guide !== guide || !current() || detail.hidden || !startGuide.isConnected) return; state.guide = null; recipeBody.hidden = false; startGuide.hidden = false; startGuide.focus({preventScroll:true}); }});
        state.guide = guide;
      };
      const startGuide = button('Paso a paso con Roxy', beginGuide, 'myplate-button myplate-primary');
      if (fit?.status === 'conflict') {startGuide.disabled = true;startGuide.textContent = 'Busca otra receta compatible';}
      if (window.RoxyRecipeGuide?.mount) detailBody.append(startGuide, guideHost);
      detailBody.append(recipeBody);
      const amounts = node('div', null, 'myplate-amounts');
      if (recipe.yield) amounts.append(node('p', `Rendimiento de la fuente: ${recipe.yield}`));
      if (recipe.serving_size) amounts.append(node('p', `Porción de la fuente: ${recipe.serving_size}`));
      if (amounts.children.length) recipeBody.append(amounts);
      recipeBody.append(node('h4', 'Ingredientes'));
      const ingredients = node('ul', null, 'myplate-ingredients'); ingredients.lang = 'en';
      recipe.ingredients.forEach(item => {
        const li = node('li'); li.append(node('span', item.text));
        if (item.note) li.append(node('small', item.note)); ingredients.append(li);
      });
      recipeBody.append(ingredients, node('h4', 'Preparación'));
      const directions = node('div', recipe.directions, 'myplate-directions'); directions.lang = 'en'; recipeBody.append(directions);
      if (recipe.notes) { const notes = node('p', recipe.notes, 'myplate-source-notes'); notes.lang = 'en'; recipeBody.append(node('h4', 'Notas de la receta'), notes); }
      const recipeInfo = information('Información de la receta'), recipeCredits = recipeInfo.content;
      recipeHeading.append(recipeInfo.control);
      if (recipe.description) { const description = node('p', recipe.description); description.lang = 'en'; recipeCredits.append(description); }
      if (recipe.contributor) recipeCredits.append(node('p', `Autor o colaborador: ${recipe.contributor}`, 'myplate-note'));
      const links = node('div', null, 'myplate-source-links');
      sourceLink(links, 'Ver receta en la fuente', recipe.source_url);
      sourceLink(links, 'Leer en español en la fuente', recipe.translation_urls?.es || summary.translation_urls?.es);
      recipeCredits.append(links);
      const originalCredit = node('p', attribution, 'myplate-note'); originalCredit.lang = 'en'; recipeCredits.append(originalCredit,
        node('p', 'La guía conserva las instrucciones originales. No adapta cantidades ni modifica tu plan de comidas o lista de compras.', 'myplate-note'));
      recipeCredits.append(node('p', 'MyPlate.food es un archivo independiente que conserva la colección USDA MyPlate Kitchen. Original en inglés; enlace al español cuando está disponible.', 'myplate-note'),
        node('p', '100 fichas completas al día y 20 consultas por minuto, con cupo compartido de Roxy. El catálogo se consulta en directo. Algunas imágenes de la fuente se han ampliado con IA.', 'myplate-note'));
      detailBody.append(node('p', 'Antes de empezar, revisa ingredientes, alergias y preparación completa.', 'myplate-note'));
      title.focus({preventScroll:false});
      if (prepare && fit?.status !== 'conflict') beginGuide();
    }
    form.addEventListener('submit', event => {
      event.preventDefault(); if (state.busy) return;
      state.query = search.value.trim().slice(0,100); void load(1);
    });
    state.configure = (nextGroup, nextAutoLoad) => {
      if (state.group === nextGroup && state.autoLoad === nextAutoLoad) return;
      if (state.group !== nextGroup) {
        stop(); purgeDetail(); grid.replaceChildren();
        state.group = nextGroup; state.category = baseCategory(); state.query = ''; search.value = '';
        state.page = 1; state.totalPages = 0; state.canNext = false; state.loaded = false; state.loadAttempted = false;
        state.initialLoadRequested = true; status.textContent = ''; retry.hidden = true; pagination.hidden = true;
        clear.hidden = true; browser.hidden = true; start.hidden = false; total.textContent = 'Originales en inglés · MyPlate.food';
      }
      if (nextAutoLoad && !state.autoLoad && !state.loaded && !state.loadAttempted) state.initialLoadRequested = true;
      state.autoLoad = nextAutoLoad; groupHeading(); categoryButtons(); setBusy(state.busy);
    };
    state.activate = value => {
      state.active = Boolean(value);
      if (current()) {
        if (state.busy && state.deadline && Date.now() >= state.deadline) state.expire?.();
        if (state.initialLoadRequested && !state.busy) void load(1, {focus:false}); return;
      }
      const wasBusy = state.busy, hadDetail = Boolean(state.selected); stop(); purgeDetail();
      if (hadDetail) { browser.hidden = !state.loaded; start.hidden = state.loaded; }
      if (wasBusy) paused();
    };
    const visibility = () => state.activate(state.active);
    document.addEventListener('visibilitychange', visibility);
    state.dispose = () => { stop(); purgeDetail(); document.removeEventListener('visibilitychange', visibility); };
    state.activate(active);
  }
  window.RoxyMyPlateRecipes = Object.freeze({render, setActive});
})();
