(() => {
  'use strict';
  const renders = new WeakMap();
  const revision = 'f446f0e9356b9b43155d207b4f7c5214d9da91ab';
  const imagePrefix = `https://raw.githubusercontent.com/alfg/opendrinks/${revision}/src/assets/recipes/`;
  const sourcePrefix = `https://github.com/alfg/opendrinks/blob/${revision}/src/recipes/`;
  const categories = {all:'Sin licores', coffee_tea:'Café y té', juice:'Jugos', smoothie:'Batidos', mocktail:'Refrescantes', cocktail:'Cócteles · 21+'};
  let dialogSequence = 0;
  const node = (tag, text, className) => { const el = document.createElement(tag); if (text != null) el.textContent = text; if (className) el.className = className; return el; };
  const button = (text, action, className = 'drinks-button') => { const el = node('button', text, className); el.type = 'button'; el.addEventListener('click', action); return el; };
  const normalize = value => String(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const validLines = value => Array.isArray(value) && value.length > 0 && value.length <= 128 && value.every(line => typeof line === 'string' && line.trim() && line.length < 8192);
  const safeImage = value => typeof value === 'string' && value.startsWith(imagePrefix) && /^[a-z0-9_-]+\.(?:jpe?g|png|webp)$/i.test(value.slice(imagePrefix.length));
  const safeSource = value => typeof value === 'string' && value.startsWith(sourcePrefix) && /^[a-z0-9_-]+\.json$/i.test(value.slice(sourcePrefix.length));
  const translated = row => typeof row.title_es === 'string' && row.title_es.trim() && validLines(row.ingredients_es) && validLines(row.steps_es) &&
    row.ingredients_es.length === row.ingredients.length && row.steps_es.length === row.steps.length;
  const validBase = row => row && typeof row.id === 'string' && /^[a-z0-9_-]{1,140}$/i.test(row.id) && typeof row.title === 'string' && row.title.trim() && row.title.length <= 300 &&
    typeof row.title_es === 'string' && row.title_es.trim() && row.title_es.length <= 300 &&
    Object.hasOwn(categories, row.category) && row.category !== 'all' && typeof row.alcoholic === 'boolean' &&
    row.alcoholic === (row.category === 'cocktail') &&
    typeof row.source_sha256 === 'string' && /^[a-f0-9]{64}$/.test(row.source_sha256);
  const validSummary = row => validBase(row) && Number.isInteger(row.ingredient_count) && row.ingredient_count > 0 && row.ingredient_count <= 128 &&
    Number.isInteger(row.step_count) && row.step_count > 0 && row.step_count <= 128 &&
    (row.source_url === undefined || row.source_url === `${sourcePrefix}${row.id}.json`) &&
    Object.keys(row).every(key => ['id','title','title_es','category','alcoholic','image_url','image_credit','source_url','source_sha256','ingredient_count','step_count'].includes(key));
  const validDetail = (row, summary) => validBase(row) &&
    ['id','title','title_es','category','alcoholic','image_url','source_sha256'].every(key => row[key] === summary[key]) &&
    validLines(row.ingredients) && validLines(row.steps) && translated(row) && row.source_url === `${sourcePrefix}${summary.id}.json` &&
    row.ingredients.length === summary.ingredient_count && row.steps.length === summary.step_count && !Object.hasOwn(row, 'raw_source');
  const validSource = source => source?.name === 'Open Drinks' && source.revision === revision && source.license === 'MIT';
  function photo(row, large = false) {
    const figure = node('figure', null, `drinks-photo${large ? ' drinks-photo-large' : ''}`);
    const empty = node('span', 'La fuente no tiene una foto disponible.', 'drinks-photo-empty'); figure.append(empty);
    if (!safeImage(row.image_url)) return figure;
    const img = node('img'); img.alt = `${row.title_es || row.title} · imagen de la fuente`;
    img.width = 600; img.height = 600; img.loading = 'lazy'; img.decoding = 'async'; img.referrerPolicy = 'no-referrer';
    empty.hidden = true; img.addEventListener('error', () => { img.remove(); empty.textContent = 'No se pudo cargar la foto de esta bebida.'; empty.hidden = false; });
    img.src = row.image_url; figure.append(img); return figure;
  }
  const sourceLink = (parent, row) => { if (!safeSource(row.source_url)) return; const a = node('a', 'Ver receta y autoría en la fuente'); a.href = row.source_url; a.target = '_blank'; a.rel = 'noopener noreferrer'; parent.append(a); };
  function setActive(container, active) { renders.get(container)?.activate(Boolean(active)); }
  function render(container, {user, identity = '', api, hidden = false, active = true, isCurrent = () => true}) {
    if (!container) return;
    const signature = JSON.stringify([user, identity, hidden]); const previous = renders.get(container);
    if (previous?.signature === signature) { previous.isCurrent = isCurrent; previous.activate(active); return; }
    previous?.dispose(); container.replaceChildren(); container.hidden = hidden;
    const state = {signature, active:Boolean(active), isCurrent, rows:[], counts:{}, page:1, category:'all', query:'',
      loaded:false, busy:false, adult:false, generation:0, controller:null, detailGeneration:0, detailController:null, detailId:'',
      utterance:null, speechToken:0, returnFocus:null};
    state.activate = () => {}; state.dispose = () => {}; renders.set(container, state); if (hidden) return;
    const root = node('section', null, 'drinks-library');
    const header = node('header', null, 'drinks-heading'); header.append(node('p', 'LA PAUSA TAMBIÉN TIENE SU RECETA', 'drinks-eyebrow'), node('h2', 'Bebidas para cada momento'));
    const summary = node('p', 'Café, té, jugos, batidos y refrescantes. Ingredientes y pasos de una fuente comunitaria, con su versión en español.', 'drinks-intro');
    const status = node('p', '', 'drinks-status'); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite'); status.tabIndex = -1;
    const explore = button('Explorar bebidas', () => void load(), 'drinks-button drinks-primary');
    const retry = button('Reintentar bebidas', () => void load()); retry.hidden = true;
    const browser = node('div', null, 'drinks-browser'); browser.hidden = true;
    const form = node('form', null, 'drinks-search'); const label = node('label'); label.append(node('span', 'Busca una bebida por nombre'));
    const search = node('input'); search.type = 'search'; search.maxLength = 100; search.placeholder = 'Café, limonada, coffee…'; label.append(search);
    const submit = node('button', 'Buscar bebidas', 'drinks-button'); submit.type = 'submit'; form.append(label, submit);
    const tabs = node('nav', null, 'drinks-categories'); tabs.setAttribute('aria-label', 'Categorías de bebidas');
    const grid = node('div', null, 'drinks-grid');
    const pager = node('nav', null, 'drinks-pagination'); pager.setAttribute('aria-label', 'Páginas de bebidas');
    const pageLabel = node('span');
    const prev = button('Bebidas anteriores', () => { if (state.page > 1) { state.page--; showPage(true); } });
    const next = button('Más bebidas', () => { if (state.page * 24 < filtered().length) { state.page++; showPage(true); } }); pager.append(prev, pageLabel, next);
    const clear = button('Quitar filtros de bebidas', () => { search.value = ''; state.query = ''; state.category = 'all'; state.page = 1; showPage(true); }); clear.hidden = true;
    browser.append(form, tabs, grid, clear, pager);
    const note = node('p', 'Recetas de Open Drinks: comunidad, no cocina de prueba de Roxy. Conservamos las cantidades del lote original; no calculamos porciones ni nutrición.', 'drinks-note');
    const license = node('a', 'Créditos y licencia de Open Drinks', 'drinks-license'); license.href = '/assets/open-drinks-license.txt'; license.target = '_blank'; license.rel = 'noopener noreferrer';
    const dialog = node('dialog', null, 'drinks-dialog'); dialog.setAttribute('aria-modal', 'true');
    const dialogInner = node('div', null, 'drinks-dialog-inner'); dialog.append(dialogInner);
    root.append(header, summary, explore, status, retry, browser, note, license, dialog); container.append(root);
    const current = () => renders.get(container) === state && container.isConnected && !container.hidden && !document.hidden && state.active && state.isCurrent();
    const stopSpeech = () => {
      state.speechToken++;
      if (state.utterance) { state.utterance.onend = null; state.utterance.onerror = null; state.utterance = null; window.speechSynthesis?.cancel(); }
    };
    const cancelDetail = () => {
      state.detailGeneration++; state.detailController?.abort(); state.detailController = null; state.detailId = ''; dialog.setAttribute('aria-busy', 'false');
    };
    const closeDialog = (restore = true) => {
      cancelDetail(); stopSpeech(); if (dialog.open) dialog.close(); dialogInner.replaceChildren();
      if (restore && current() && state.returnFocus?.isConnected) state.returnFocus.focus({preventScroll:true}); state.returnFocus = null;
    };
    dialog.addEventListener('cancel', event => { event.preventDefault(); closeDialog(); });
    dialog.addEventListener('click', event => { if (event.target === dialog) closeDialog(); });
    const openDialog = (title, opener) => {
      closeDialog(false); state.returnFocus = opener; const id = `roxy-drink-dialog-${++dialogSequence}`;
      const head = node('div', null, 'drinks-dialog-heading'); const heading = node('h3', title); heading.id = id; heading.tabIndex = -1;
      head.append(heading, button('Cerrar bebida', () => closeDialog())); dialog.setAttribute('aria-labelledby', id); dialogInner.append(head);
      dialog.showModal(); heading.focus({preventScroll:false}); return heading;
    };
    const filtered = () => state.rows.filter(row => (!row.alcoholic || (state.adult && state.category === 'cocktail')) &&
      (state.category === 'all' || row.category === state.category) && normalize(`${row.title} ${row.title_es}`).includes(state.query));
    function chooseCategory(key, opener) {
      if (!current()) return;
      if (key !== 'cocktail' || state.adult) { state.category = key; state.query = ''; search.value = ''; state.page = 1; showPage(true); return; }
      openDialog('Contenido con alcohol', opener);
      dialogInner.append(node('p', 'Esta sección es opcional. Para verla, confirma que tienes 21 años o más. Es una elección de contenido, no una verificación de edad.', 'drinks-age-copy'));
      const ageLabel = node('label', null, 'drinks-age-check'); const check = node('input'); check.type = 'checkbox'; ageLabel.append(check, node('span', 'Confirmo que tengo 21 años o más.'));
      const confirm = button('Ver cócteles con alcohol', () => {
        if (!current() || !check.checked) return; state.adult = true; state.category = 'cocktail'; state.query = ''; search.value = ''; state.page = 1; closeDialog(false); showPage(true);
      }, 'drinks-button drinks-primary'); confirm.disabled = true;
      check.addEventListener('change', () => { confirm.disabled = !check.checked; });
      dialogInner.append(ageLabel, node('p', 'No guardamos esta confirmación. Evita el alcohol si vas a conducir; las recetas no son recomendaciones de salud.', 'drinks-note'), confirm,
        button('Seguir sin licores', () => closeDialog()));
    }
    function showPage(focus = false) {
      if (!current() || !state.loaded) return;
      closeDialog(false);
      const matches = filtered(), pages = Math.max(1, Math.ceil(matches.length / 24)); state.page = Math.min(state.page, pages);
      tabs.replaceChildren();
      Object.entries(categories).forEach(([key, name]) => {
        const count = key === 'all' ? state.rows.filter(row => !row.alcoholic).length : state.counts[key];
        const tab = button(`${name}${Number.isInteger(count) ? ` (${count})` : ''}`, () => chooseCategory(key, tab), 'drinks-category');
        tab.setAttribute('aria-pressed', String(key === state.category)); tabs.append(tab);
      });
      grid.replaceChildren(...matches.slice((state.page - 1) * 24, state.page * 24).map(row => {
        const card = node('article', null, 'drinks-card'); card.append(photo(row)); const body = node('div', null, 'drinks-card-body');
        const title = node('h3', row.title_es); title.lang = 'es';
        const open = button('Preparar bebida', () => { if (current()) void openRecipe(row, open); }); open.setAttribute('aria-label', `Preparar bebida: ${title.textContent}`);
        body.append(title, node('p', `${row.ingredient_count} ${row.ingredient_count === 1 ? 'ingrediente' : 'ingredientes'} · ${row.step_count} ${row.step_count === 1 ? 'paso' : 'pasos'}${row.alcoholic ? ' · Con alcohol' : ''}`, 'drinks-card-meta'), open); card.append(body); return card;
      }));
      summary.textContent = `${state.rows.length} bebidas en esta colección: ${state.rows.filter(row => !row.alcoholic).length} sin licores y ${state.rows.filter(row => row.alcoholic).length} cócteles con alcohol en una sección opcional para mayores de 21 años.`;
      status.textContent = matches.length ? `${(state.page - 1) * 24 + 1}–${Math.min(state.page * 24, matches.length)} de ${matches.length} bebidas. Abre una ficha para ver sus ingredientes y pasos.` : 'No hay bebidas con esos filtros. Prueba otro nombre en español o inglés, o quita los filtros.';
      pageLabel.textContent = `Página ${state.page} de ${pages}`; prev.disabled = state.page === 1; next.disabled = state.page === pages; pager.hidden = pages <= 1;
      clear.hidden = !state.query && state.category === 'all'; if (focus) status.focus({preventScroll:false});
    }
    async function openRecipe(summary, opener) {
      if (!current() || !state.loaded || state.busy || (summary.alcoholic && (!state.adult || state.category !== 'cocktail'))) return;
      if (state.detailController && state.detailId === summary.id) return;
      openDialog(summary.title_es, opener);
      const loading = node('p', 'Cargando los ingredientes y pasos de esta bebida…', 'drinks-detail-status'); loading.setAttribute('role', 'status');
      const retryDetail = button('Reintentar esta bebida', () => void openRecipe(summary, opener)); retryDetail.hidden = true; dialogInner.append(loading, retryDetail);
      const generation = state.generation, detailGeneration = state.detailGeneration, controller = new AbortController();
      state.detailController = controller; state.detailId = summary.id; dialog.setAttribute('aria-busy', 'true');
      const fresh = () => current() && state.generation === generation && state.detailGeneration === detailGeneration &&
        state.detailController === controller && dialog.open && loading.isConnected;
      try {
        const data = await request(`/v1/home-food/${encodeURIComponent(user)}/drinks/${encodeURIComponent(summary.id)}`, controller);
        if (!fresh() || controller.signal.aborted) return;
        if (!validSource(data.source) || data.audience !== 'human' || data.can_scale !== false || data.can_add_to_shopping !== false ||
          !validDetail(data.drink, summary)) throw new Error('invalid_detail');
        state.detailController = null; showRecipe(data.drink, opener);
      } catch (error) {
        if (!fresh() || (controller.signal.aborted && error?.name !== 'TimeoutError')) return;
        loading.textContent = error?.name === 'TimeoutError' ? 'Esta bebida tardó demasiado en cargar. Puedes reintentar.' :
          'No pudimos cargar esta bebida completa. Reintenta; no hemos sustituido sus ingredientes ni pasos.';
        retryDetail.hidden = false;
      } finally { if (state.detailGeneration === detailGeneration && state.detailController === controller) { state.detailController = null; dialog.setAttribute('aria-busy', 'false'); } }
    }
    function showRecipe(row, opener) {
      let spanish = translated(row), position = 0, reading = false;
      const title = openDialog(spanish ? row.title_es : row.title, opener);
      const lang = () => spanish ? 'es' : 'en'; const ingredientLines = () => spanish ? row.ingredients_es : row.ingredients; const stepLines = () => spanish ? row.steps_es : row.steps;
      const languageLabel = node('p', '', 'drinks-note');
      const toggle = button('Ver original en inglés', () => { stopSpeech(); spanish = !spanish; paint(); });
      dialogInner.append(languageLabel); if (translated(row)) dialogInner.append(toggle);
      dialogInner.append(photo(row, true));
      if (row.alcoholic) dialogInner.append(node('p', 'Contiene alcohol · contenido opcional para mayores de 21 años.', 'drinks-alcohol-note'));
      const body = node('div', null, 'drinks-recipe-body'); const reader = node('section', null, 'drinks-reader'); reader.hidden = true;
      const progress = node('p', '', 'drinks-reader-progress'); progress.setAttribute('role', 'status');
      const step = node('p', '', 'drinks-reader-step'); step.tabIndex = -1;
      const speechStatus = node('p', '', 'drinks-note'); speechStatus.setAttribute('role', 'status');
      const speechAvailable = Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance);
      const speak = button('Escuchar este paso', () => {
        if (!current() || !dialog.open || !reading || !speechAvailable) return;
        const replacingOwnSpeech = Boolean(state.utterance);
        stopSpeech();
        if (!replacingOwnSpeech && (window.speechSynthesis.speaking || window.speechSynthesis.pending)) { speechStatus.textContent = 'El dispositivo ya está reproduciendo audio. Espera a que termine.'; return; }
        const utterance = new window.SpeechSynthesisUtterance(stepLines()[position]); const token = ++state.speechToken;
        utterance.lang = spanish ? 'es-US' : 'en-US'; state.utterance = utterance;
        utterance.onend = () => { if (state.utterance === utterance && state.speechToken === token) { state.utterance = null; speechStatus.textContent = 'Lectura terminada.'; } };
        utterance.onerror = () => { if (state.utterance === utterance && state.speechToken === token) { state.utterance = null; speechStatus.textContent = 'No se pudo reproducir la voz del dispositivo. El paso sigue disponible en pantalla.'; } };
        speechStatus.textContent = 'Voz del dispositivo · leyendo el texto de este paso.';
        try { window.speechSynthesis.speak(utterance); } catch (_) { stopSpeech(); speechStatus.textContent = 'La voz del dispositivo no está disponible.'; }
      });
      const pause = button('Detener voz', () => { stopSpeech(); speechStatus.textContent = 'Voz detenida.'; });
      const previousStep = button('Paso anterior', () => { if (position > 0) { stopSpeech(); position--; paint(); step.focus({preventScroll:false}); } });
      const nextStep = button('Paso siguiente', () => { if (position < row.steps.length - 1) { stopSpeech(); position++; paint(); step.focus({preventScroll:false}); } });
      const start = button('Leer paso a paso', () => { reading = true; position = 0; paint(); step.focus({preventScroll:false}); }, 'drinks-button drinks-primary');
      const finish = button('Ver preparación completa', () => { stopSpeech(); reading = false; paint(); start.focus({preventScroll:false}); });
      reader.append(progress, step, previousStep, nextStep);
      if (speechAvailable) reader.append(node('p', 'Voz del dispositivo · reproducción opcional', 'drinks-note'), speak, pause, speechStatus);
      reader.append(finish); dialogInner.append(start, reader, body);
      const notes = Array.isArray(row.notes_es) ? row.notes_es : typeof row.notes_es === 'string' && row.notes_es ? [row.notes_es] : [];
      if (notes.length) { const box = node('aside', null, 'drinks-editorial-notes'); box.append(node('h4', 'Notas de Roxy')); notes.forEach(text => box.append(node('p', text))); dialogInner.append(box); }
      const credits = node('details', null, 'drinks-credits'); credits.append(node('summary', 'Fuente y créditos'));
      if (row.image_credit) credits.append(node('p', `Foto: ${row.image_credit}`, 'drinks-note'));
      if (row.contributor) credits.append(node('p', `Autoría de la fuente: ${row.contributor}`, 'drinks-note')); sourceLink(credits, row);
      const licenseLink = node('a', 'Leer la licencia MIT completa de Open Drinks'); licenseLink.href = '/assets/open-drinks-license.txt'; licenseLink.target = '_blank'; licenseLink.rel = 'noopener noreferrer'; credits.append(licenseLink);
      dialogInner.append(credits);
      dialogInner.append(node('p', 'Cantidades originales, sin escalado ni cálculo de porciones. Comprueba ingredientes y alergias; no adaptamos automáticamente estas recetas.', 'drinks-note'));
      function paint() {
        title.textContent = spanish ? row.title_es : row.title; title.lang = lang(); toggle.textContent = spanish ? 'Ver original en inglés' : 'Ver traducción al español';
        languageLabel.textContent = spanish ? 'Traducción al español; puedes comparar el original de Open Drinks.' : 'Original de Open Drinks en inglés, sin alterar medidas ni pasos.';
        body.replaceChildren(node('h4', spanish ? 'Ingredientes' : 'Ingredients'));
        const ingredients = node('ul', null, 'drinks-ingredients'); ingredients.lang = lang(); ingredientLines().forEach(line => ingredients.append(node('li', line)));
        const steps = node('ol', null, 'drinks-steps'); steps.lang = lang(); stepLines().forEach(line => steps.append(node('li', line)));
        body.append(ingredients, node('h4', spanish ? 'Preparación' : 'Directions'), steps);
        progress.textContent = `Paso ${position + 1} de ${row.steps.length}`; step.textContent = stepLines()[position]; step.lang = lang();
        previousStep.disabled = position === 0; nextStep.disabled = position === row.steps.length - 1;
        reader.hidden = !reading; body.hidden = reading; start.hidden = reading; speechStatus.textContent = '';
      }
      paint();
    }
    const stop = () => { state.generation++; state.controller?.abort(); state.controller = null; state.busy = false; explore.disabled = false; root.setAttribute('aria-busy', 'false'); };
    const request = (path, controller) => new Promise((resolve, reject) => {
      let settled = false;
      const finish = (action, value) => { if (settled) return; settled = true; clearTimeout(timer); controller.signal.removeEventListener('abort', aborted); action(value); };
      const aborted = () => finish(reject, Object.assign(new Error('cancelled'), {name:'AbortError'}));
      const timer = setTimeout(() => { finish(reject, Object.assign(new Error('timeout'), {name:'TimeoutError'})); controller.abort(); }, 12000);
      controller.signal.addEventListener('abort', aborted, {once:true});
      Promise.resolve().then(() => { if (controller.signal.aborted) throw Object.assign(new Error('cancelled'), {name:'AbortError'}); return api(path, {method:'GET', signal:controller.signal}); })
        .then(value => finish(resolve, value), error => finish(reject, error));
    });
    async function load() {
      if (!current() || state.busy) return;
      stop(); closeDialog(false); state.loaded = false; state.rows = []; grid.replaceChildren(); browser.hidden = true; retry.hidden = true;
      state.busy = true; explore.disabled = true; root.setAttribute('aria-busy', 'true'); status.textContent = 'Cargando el recetario de bebidas…';
      const generation = state.generation, controller = new AbortController(); state.controller = controller;
      try {
        const data = await request(`/v1/home-food/${encodeURIComponent(user)}/drinks/summaries`, controller);
        if (!current() || controller.signal.aborted || generation !== state.generation) return;
        if (!Array.isArray(data.drinks) || data.drinks.length > 200 || !data.drinks.every(validSummary) || data.total !== data.drinks.length ||
          new Set(data.drinks.map(row => row.id)).size !== data.drinks.length || !data.counts ||
          !validSource(data.source)) throw new Error('invalid_catalog');
        for (const key of Object.keys(categories).filter(key => key !== 'all')) {
          if (data.counts[key] !== data.drinks.filter(row => row.category === key).length) throw new Error('invalid_count');
        }
        state.rows = data.drinks; state.counts = data.counts; state.loaded = true; state.page = 1; browser.hidden = false; explore.hidden = true; showPage(true);
      } catch (error) {
        if (!current() || generation !== state.generation || (controller.signal.aborted && error?.name !== 'TimeoutError')) return;
        status.textContent = error?.name === 'TimeoutError' ? 'La carga tardó demasiado. Puedes reintentar sin perder tus recetas guardadas.' : 'No pudimos cargar las bebidas. Reintenta; no se han generado recetas de reemplazo.'; retry.hidden = false;
      } finally { if (generation === state.generation) { state.controller = null; state.busy = false; explore.disabled = false; root.setAttribute('aria-busy', 'false'); } }
    }
    form.addEventListener('submit', event => { event.preventDefault(); state.query = normalize(search.value.trim().slice(0,100)); state.page = 1; showPage(true); });
    const visibility = () => state.activate(state.active);
    state.activate = value => {
      state.active = Boolean(value); if (current()) return;
      stop(); closeDialog(false); state.adult = false; state.category = 'all'; state.loaded = false; state.rows = []; state.counts = {};
      state.query = ''; search.value = ''; state.page = 1;
      grid.replaceChildren(); tabs.replaceChildren(); browser.hidden = true; explore.hidden = false; retry.hidden = true; status.textContent = '';
    };
    state.dispose = () => { stop(); closeDialog(false); state.rows = []; document.removeEventListener('visibilitychange', visibility); };
    document.addEventListener('visibilitychange', visibility);
  }
  window.RoxyDrinks = Object.freeze({render, setActive});
})();
