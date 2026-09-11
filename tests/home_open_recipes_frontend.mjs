import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

// Synthetic DOM/API contracts; production browser layout is checked separately.
const catalog = JSON.parse(fs.readFileSync(new URL('../data/home_open_recipes.json', import.meta.url), 'utf8'));
catalog.recipes = catalog.recipes.filter(row => row.audit?.publishable !== false);
const translations = JSON.parse(fs.readFileSync(new URL('../data/home_open_recipes_es.json', import.meta.url), 'utf8')).translations;
const code = fs.readFileSync(new URL('../assets/roxy_home_open_recipes.js', import.meta.url), 'utf8');
const fullRows = (spanish = false) => structuredClone(catalog.recipes).map(row => ({...row,
  attribution:row.rights.attribution, license_url:row.rights.license_url, can_cook_with_roxy:false, can_add_to_shopping:false,
  ...(spanish ? {translation:structuredClone(translations.find(value => value.source_id === row.id))} : {})}));
const normalize = value => String(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return {promise, resolve, reject}; };
const settle = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
const all = (parent, tag) => parent.children.flatMap(child => [...(child.tagName === tag.toUpperCase() ? [child] : []), ...all(child, tag)]);
const cards = parent => all(parent, 'details').filter(el => el.className === 'provider-recipe-card');
const findButton = (parent, text) => all(parent, 'button').find(el => el.textContent === text);
const control = (parent, label, tag) => {
  const found = all(parent, 'label').find(el => el.textContent.includes(label)); assert.ok(found, `Missing label: ${label}`);
  const input = all(found, tag)[0]; assert.ok(input, `Missing ${tag}: ${label}`); return input;
};

function harness() {
  const downloads = [], blobs = [], revoked = [], timers = new Map(), documentListeners = {};
  let activeElement, nextTimer = 1, now = 0;
  class Element {
    constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.listeners = {}; this._text = ''; this.value = ''; this.hidden = false; this.parent = null; this.dataset = {}; }
    get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
    set textContent(text) { this._text = String(text); this.children.forEach(child => { child.parent = null; }); this.children = []; }
    get firstChild() { return this.children[0]; }
    get isConnected() { return this.root || Boolean(this.parent?.isConnected); }
    append(...children) { children.forEach(child => { child.parent = this; this.children.push(child); }); }
    replaceChildren(...children) { this.children.forEach(child => { child.parent = null; }); this.children = []; this._text = ''; this.append(...children); }
    remove() { if (this.parent) { this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null; } }
    contains(child) { return child === this || this.children.some(value => value.contains(child)); }
    setAttribute(name, value) { this[name] = String(value); }
    removeAttribute(name) { delete this[name]; }
    addEventListener(name, action) { (this.listeners[name] ||= []).push(action); }
    removeEventListener(name, action) { this.listeners[name] = (this.listeners[name] || []).filter(value => value !== action); }
    async emit(name) { for (const action of [...(this.listeners[name] || [])]) await action({target:this, preventDefault() {}}); await settle(); }
    click() { if (this.disabled) return Promise.resolve(); if (this.tagName === 'A') { downloads.push({href:this.href, filename:this.download}); return Promise.resolve(); } return this.emit('click'); }
    focus() { activeElement = this; }
  }
  const document = {hidden:false, createElement:tag => new Element(tag), body:new Element('body'),
    addEventListener(name, action) { (documentListeners[name] ||= []).push(action); },
    removeEventListener(name, action) { documentListeners[name] = (documentListeners[name] || []).filter(value => value !== action); }};
  document.body.root = true;
  class TestURL extends URL {
    static createObjectURL(blob) { blobs.push(blob); return `blob:original-${blobs.length}`; }
    static revokeObjectURL(url) { revoked.push(url); }
  }
  const sandbox = {window:{}, document, URL:TestURL, URLSearchParams, Blob, AbortController,
    setTimeout:(fn, delay = 0) => { const id = nextTimer++; timers.set(id, {fn, due:now + delay}); return id; }, clearTimeout:id => timers.delete(id),
    fetch() { throw new Error('No frontend external/network/AI fetch is allowed'); }};
  vm.runInNewContext(code, sandbox);
  const container = () => { const el = new Element('div'); document.body.append(el); return el; };
  const open = async details => { details.open = true; await details.emit('toggle'); };
  const close = async details => { details.open = false; await details.emit('toggle'); };
  const tick = async delay => {
    const end = now + delay;
    while (true) {
      const pending = [...timers].filter(([, timer]) => timer.due <= end).sort((a, b) => a[1].due - b[1].due)[0]; if (!pending) break;
      const [id, timer] = pending; timers.delete(id); now = timer.due; timer.fn(); await settle();
    }
    now = end; await settle();
  };
  const visibility = async hidden => { document.hidden = hidden; for (const action of [...(documentListeners.visibilitychange || [])]) await action(); await settle(); };
  return {...sandbox.window.RoxyOpenRecipes, container, open, close, tick, visibility, downloads, blobs, revoked,
    get activeElement() { return activeElement; }};
}

// Server fixture filters the entire catalog and never includes full bodies or image URLs in summaries.
function server(rows = fullRows(), {version = 'fixture-v1', intercept} = {}) {
  const requests = [];
  const api = async (path, options = {}) => {
    const url = new URL(path, 'https://home.invalid');
    assert.equal(options.method || 'GET', 'GET', 'source browsing cannot mutate Home state');
    assert.ok(options.signal instanceof AbortSignal, 'requests must be cancellable'); assert.equal(url.origin, 'https://home.invalid');
    const request = {path, options, url}; requests.push(request); const override = intercept?.(request, requests.length);
    if (override !== undefined) return await override;
    if (url.pathname.endsWith('/open-recipes/summaries')) {
      const query = normalize(url.searchParams.get('q') || ''), cuisine = url.searchParams.get('cuisine') || '', language = url.searchParams.get('language') || 'all';
      const limit = Number(url.searchParams.get('limit')); assert.equal(limit, 24); assert.ok(['all','es','en'].includes(language));
      const filtered = rows.filter(row => (!cuisine || row.cuisine === cuisine) &&
        (language === 'all' || row.language === language || row.translation?.language === language) &&
        normalize([row.title, row.cuisine, ...row.ingredients_original, row.translation?.title || '', ...(row.translation?.ingredients || [])].join(' ')).includes(query));
      const offset = Number((url.searchParams.get('cursor') || 'offset:0').split(':').at(-1)), page = filtered.slice(offset, offset + limit);
      return {schema_version:2, catalog_version:version, status:'READY', recipes:page.map(row => ({
        id:row.id, title:row.title, title_es:row.translation?.title || (row.language === 'es' ? row.title : ''), language:row.language,
        revid:row.revid, source_sha256:row.source_sha256,
        cuisine:row.cuisine, servings:row.servings, servings_original:row.servings_original,
        step_count:row.steps_original.length, ingredient_count:row.ingredients_original.length, has_source_photo:Boolean(row.image_url)})),
      count:page.length, matched_total:filtered.length, catalog_total:rows.length, next_cursor:offset + limit < filtered.length ? `offset:${offset + limit}` : null,
      cuisines:[...new Set(rows.map(row => row.cuisine))].sort(), languages:[...new Set(rows.flatMap(row => [row.language, ...(row.translation ? ['es'] : [])]))].sort()};
    }
    assert.match(url.pathname, /\/open-recipes\/detail\/[^/]+$/, 'only explicit source detail and summary GETs are allowed');
    assert.equal(url.searchParams.get('catalog_version'), version, 'detail must be bound to the displayed catalog');
    const id = decodeURIComponent(url.pathname.split('/').at(-1)), recipe = rows.find(row => row.id === id); assert.ok(recipe, `Unknown detail ${id}`);
    return {schema_version:2, catalog_version:version, recipe:structuredClone(recipe)};
  };
  return {api, requests};
}
const searchFor = async (h, panel, query) => { const search = control(panel, 'Buscar en español o inglés', 'input'); search.value = query; await search.emit('input'); await h.tick(300); };

test('same-origin summaries defer detail and licensed photos until card opening; originals remain exact', async () => {
  const h = harness(), panel = h.container(), mock = server(); h.render(panel, {user:'household/a', identity:'member-a', api:mock.api});
  assert.equal(mock.requests.length, 0); const initialDetails = panel.firstChild; await h.open(initialDetails);
  assert.equal(mock.requests.length, 1); assert.equal(mock.requests[0].url.pathname, '/v1/home-food/household%2Fa/open-recipes/summaries');
  assert.equal(cards(panel).length, 7); assert.equal(all(panel, 'ol').length, 0); assert.equal(all(panel, 'img').length, 0);
  const firstPhotoCard = cards(panel)[0];
  for (const [i, card] of cards(panel).entries()) {
    await h.open(card); assert.equal(cards(panel)[i], card, 'detail preserves the open details node');
    assert.deepEqual(all(card, 'ul')[0].children.map(el => el.textContent), catalog.recipes[i].ingredients_original);
    assert.deepEqual(all(card, 'ol')[0].children.map(el => el.textContent), catalog.recipes[i].steps_original);
    assert.equal(all(card, 'ol')[0].lang, 'en'); assert.ok(card.textContent.includes(catalog.recipes[i].rights.attribution));
  }
  assert.equal(mock.requests.length, 8, 'one list and one detail per explicit opening');
  assert.equal(all(panel, 'ol').reduce((count, list) => count + list.children.length, 0), 38);
  const sourceImages = all(panel, 'img'), photographed = catalog.recipes.filter(row => row.image_url); assert.equal(sourceImages.length, 3);
  assert.deepEqual(photographed.map(row => row.id), ['wikibooks-150880', 'wikibooks-219286', 'wikibooks-en-83396']);
  photographed.forEach(row => {
    const filename = decodeURIComponent(new URL(row.image_url).pathname.split('/').pop()).replaceAll('_', ' ');
    assert.ok(['Image', 'File'].some(namespace => row.original_wikitext.includes(`${namespace}:${filename}`)));
    assert.equal(row.image_mime, 'image/jpeg'); assert.equal(row.image_commercial_use_permitted, true);
    assert.ok(row.image_dimensions.width > 0 && row.image_dimensions.height > 0);
    assert.ok(row.photo_scope.startsWith('Fotografía publicada con ')); assert.ok(row.photo_scope.endsWith('no verifica cantidades ni resultado'));
    assert.ok(row.image_author && row.image_source_revision); assert.equal(row.photo_verified, undefined);
  });
  assert.equal(sourceImages[0].src, photographed[0].image_url); assert.equal(sourceImages[0].referrerPolicy, 'no-referrer'); assert.equal(sourceImages[0].width, photographed[0].image_dimensions.width);
  assert.ok(firstPhotoCard.textContent.includes(photographed[0].image_author));
  assert.ok(all(firstPhotoCard, 'a').some(anchor => anchor.href === photographed[0].image_license_url));
  assert.ok(all(firstPhotoCard, 'a').some(anchor => anchor.href === photographed[0].image_source_url));
  await sourceImages[0].emit('error'); assert.equal(all(firstPhotoCard, 'img').length, 0); assert.ok(firstPhotoCard.textContent.includes('La fotografía original no se pudo cargar'));
  await h.close(firstPhotoCard); await h.open(firstPhotoCard); assert.equal(mock.requests.length, 8);
  h.render(panel, {user:'household/a', identity:'member-a', api:mock.api}); assert.equal(panel.firstChild, initialDetails);
  await h.close(initialDetails); await h.open(initialDetails); assert.equal(mock.requests.length, 8);
  h.render(panel, {user:'household/a', identity:'member-a', api:mock.api, hidden:true}); assert.equal(panel.hidden, true); assert.equal(panel.children.length, 0); assert.equal(mock.requests.length, 8);
});

test('bounded reader focuses the step and downloads attributed original TXT without mutations', async () => {
  const h = harness(), panel = h.container(), mock = server(); h.render(panel, {user:'reader', api:mock.api}); await h.open(panel.firstChild);
  const cuisine = control(panel, 'Cocina de la fuente', 'select'); assert.ok(cuisine.children.some(option => option.textContent === 'Francia'));
  await searchFor(h, panel, 'lentil'); assert.equal(cards(panel).length, 1); assert.equal(cards(panel)[0].firstChild.textContent, 'Red Lentil Soup');
  await searchFor(h, panel, ''); cuisine.value = 'French'; await cuisine.emit('change'); assert.equal(cards(panel).length, 1);
  const card = cards(panel)[0]; assert.equal(card.firstChild.textContent, 'Potatoes Anna'); await h.open(card); const reader = all(card, 'section')[0];
  const body = all(card, 'div').find(el => all(el, 'ol').length), start = findButton(card, 'Leer paso a paso');
  const sourceIngredients = all(body, 'ul')[0].children.map(el => el.textContent), sourceSteps = all(body, 'ol')[0].children.map(el => el.textContent);
  assert.equal(body.hidden, false); assert.ok(card.children.indexOf(start) < card.children.indexOf(body)); assert.ok(card.children.indexOf(reader) < card.children.indexOf(body));
  await findButton(card, 'Leer paso a paso').click(); assert.equal(reader.hidden, false); assert.equal(reader.children[0].textContent, 'Paso 1 de 5');
  assert.equal(body.hidden, true, 'the full source body is hidden during focused reading');
  assert.deepEqual(all(body, 'ul')[0].children.map(el => el.textContent), sourceIngredients); assert.deepEqual(all(body, 'ol')[0].children.map(el => el.textContent), sourceSteps);
  assert.equal(reader.children[1].textContent, catalog.recipes[0].steps_original[0]); assert.equal(h.activeElement, reader.children[1]); assert.equal(findButton(card, 'Anterior').disabled, true);
  for (let i = 0; i < 10; i++) await findButton(card, 'Siguiente').click(); assert.equal(reader.children[0].textContent, 'Paso 5 de 5'); assert.equal(findButton(card, 'Siguiente').disabled, true);
  await findButton(card, 'Anterior').click(); assert.equal(reader.children[0].textContent, 'Paso 4 de 5'); await findButton(card, 'Terminar lectura').click(); assert.equal(reader.hidden, true); assert.equal(h.downloads.length, 0);
  assert.equal(body.hidden, false); assert.equal(start.hidden, false); assert.equal(h.activeElement, start);
  assert.deepEqual(all(body, 'ul')[0].children.map(el => el.textContent), catalog.recipes[0].ingredients_original);
  assert.deepEqual(all(body, 'ol')[0].children.map(el => el.textContent), catalog.recipes[0].steps_original);
  await findButton(card, 'Descargar original TXT').click(); const text = await h.blobs[0].text(); assert.equal(h.downloads[0].filename, 'roxy-original-wikibooks-150880.txt');
  for (const original of [...catalog.recipes[0].ingredients_original, ...catalog.recipes[0].steps_original, catalog.recipes[0].source_url,
    catalog.recipes[0].source_revision_url, catalog.recipes[0].rights.license_url, catalog.recipes[0].rights.attribution,
    ...catalog.recipes[0].rights.additional_attribution_urls, catalog.recipes[0].rights.changes]) assert.ok(text.includes(original));
  for (const field of ['image_author', 'image_license', 'image_source_url', 'image_license_url']) assert.ok(text.includes(catalog.recipes[0][field]));
  await h.tick(1000); assert.deepEqual(h.revoked, ['blob:original-1']); assert.ok(mock.requests.every(value => value.url.pathname.includes('/open-recipes/')));
});

test('unsafe links and unverified or mismatched photograph metadata cannot display remote photos', async () => {
  const h = harness(), unsafePanel = h.container(), unsafe = fullRows().slice(0, 1); unsafe[0].source_url = 'javascript:alert(1)';
  h.render(unsafePanel, {user:'unsafe-source', api:server(unsafe).api}); await h.open(unsafePanel.firstChild); await h.open(cards(unsafePanel)[0]);
  assert.ok(all(unsafePanel, 'a').every(anchor => anchor.href.startsWith('https://'))); assert.equal(all(unsafePanel, 'a').some(anchor => anchor.textContent === 'Fuente original · Wikibooks'), false);
  for (const mutation of [
    {image_url:'https://upload.wikimedia.org.evil.test/wikipedia/commons/4/41/Tortilla_patatas.jpg'},
    {image_url:'https://upload.wikimedia.org:444/wikipedia/commons/4/41/Tortilla_patatas.jpg'},
    {image_url:'https://user@upload.wikimedia.org/wikipedia/commons/4/41/Tortilla_patatas.jpg'},
    {image_url:'https://upload.wikimedia.org/wikipedia/commons/4/41/Tortilla_patatas.svg'},
    {image_url:'https://upload.wikimedia.org/wikipedia/commons/4/41/Tortilla_patatas.jpg?tracking=1'},
    {image_mime:'image/svg+xml'}, {image_source_url:'https://example.com/wiki/File:photo.jpg'},
    {image_license_url:'https://creativecommons.org/licenses/by-nc/4.0/'}, {image_commercial_use_permitted:false},
    {image_status:'unverified'}, {image_author:''}, {image_license:'CC BY-NC 4.0'}
  ]) {
    const rows = [{...fullRows()[0], ...mutation}], panel = h.container(); h.render(panel, {user:'bad-photo', api:server(rows).api}); await h.open(panel.firstChild); await h.open(cards(panel)[0]);
    assert.equal(all(panel, 'img').length, 0, JSON.stringify(mutation)); assert.ok(panel.textContent.includes('No hay una fotografía de la fuente disponible'));
  }
});

test('seven Spanish translations retain steps, attributed downloads, editorial notes, Pohe photo and serving range', async () => {
  const h = harness(), panel = h.container(), mock = server(fullRows(true)); h.render(panel, {user:'spanish-test', api:mock.api}); await h.open(panel.firstChild); assert.equal(cards(panel).length, 7);
  for (const [index, card] of cards(panel).entries()) {
    const translation = translations.find(value => value.source_id === catalog.recipes[index].id);
    assert.equal(card.firstChild.textContent, translation.title); assert.equal(all(card, 'ol').length, 0); await h.open(card); assert.equal(card.firstChild.lang, 'es');
    assert.deepEqual(all(card, 'ol')[0].children.map(el => el.textContent), translation.steps); assert.equal(all(card, 'ol')[0].lang, 'es');
    assert.ok(card.textContent.includes('no es una adaptación a alergias ni una receta ensayada')); assert.ok(!findButton(card, 'Agregar ingredientes') && !findButton(card, 'Cocinar paso a paso'));
  }
  const esCard = cards(panel)[0], esReader = all(esCard, 'section')[0]; await findButton(esCard, 'Leer paso a paso').click(); await findButton(esCard, 'Siguiente').click();
  assert.equal(esReader.children[0].textContent, 'Paso 2 de 5'); assert.equal(esReader.children[1].textContent, translations[0].steps[1]);
  await findButton(esCard, 'Ver original en inglés').click(); assert.equal(esCard.firstChild.textContent, catalog.recipes[0].title); assert.equal(esReader.children[0].textContent, 'Paso 2 de 5');
  assert.equal(esReader.children[1].textContent, catalog.recipes[0].steps_original[1]); assert.equal(esReader.children[1].lang, 'en');
  await findButton(esCard, 'Ver traducción al español').click(); assert.equal(esReader.children[1].textContent, translations[0].steps[1]);
  await findButton(esCard, 'Descargar traducción TXT').click(); assert.equal(h.downloads.length, 1); assert.equal(h.downloads[0].filename, 'roxy-es-wikibooks-150880.txt'); const spanishText = await h.blobs[0].text();
  for (const field of [...translations[0].ingredients, ...translations[0].steps, translations[0].attribution, translations[0].license_url, catalog.recipes[0].source_revision_url]) assert.ok(spanishText.includes(field));
  await findButton(esCard, 'Descargar original TXT').click(); assert.ok((await h.blobs.at(-1).text()).includes(catalog.recipes[0].steps_original[0]));
  await searchFor(h, panel, 'lentejas'); assert.equal(cards(panel).length, 1); assert.equal(cards(panel)[0].firstChild.textContent, 'Sopa de lentejas rojas'); await searchFor(h, panel, 'lentil'); assert.equal(cards(panel).length, 1);
  await searchFor(h, panel, 'tomato'); const pastaCard = cards(panel)[0]; await h.open(pastaCard); assert.ok(pastaCard.textContent.includes('Esa expresión es ambigua')); assert.equal(all(pastaCard, 'ol')[0].children.length, 4);
  await findButton(pastaCard, 'Descargar traducción TXT').click(); assert.ok((await h.blobs.at(-1).text()).includes('Notas editoriales de Roxy (no son pasos del original)'));
  await searchFor(h, panel, 'copos'); assert.equal(cards(panel).length, 1); const poheCard = cards(panel)[0], pohe = catalog.recipes.find(row => row.id === 'wikibooks-en-83396');
  assert.equal(all(poheCard, 'img').length, 0); await h.open(poheCard); assert.ok(poheCard.textContent.includes('1–2 raciones')); assert.equal(all(poheCard, 'ol')[0].children.length, 11);
  assert.equal(all(poheCard, 'img')[0].src, pohe.image_url); assert.ok(poheCard.textContent.includes('Nizil Shah'));
  await findButton(poheCard, 'Descargar traducción TXT').click(); const poheText = await h.blobs.at(-1).text(); assert.ok(poheText.includes('Servings (source): 1–2')); assert.ok(poheText.includes('fry pay') && poheText.includes('2 cucharadas de aceite'));
  await findButton(poheCard, 'Leer paso a paso').click(); for (let i = 0; i < 8; i++) await findButton(poheCard, 'Siguiente').click(); const poheReader = all(poheCard, 'section')[0];
  assert.equal(poheReader.children[0].textContent, 'Paso 9 de 11'); assert.ok(poheReader.children[1].textContent.includes('5 minutos'));
  await findButton(poheCard, 'Ver original en inglés').click(); assert.equal(poheReader.children[0].textContent, 'Paso 9 de 11'); assert.equal(poheReader.children[1].textContent, pohe.steps_original[8]);
  assert.ok(!findButton(poheCard, 'Agregar ingredientes') && !findButton(poheCard, 'Cocinar paso a paso'));
});

test('invalid translations fall back to the original without granting new actions', async () => {
  const h = harness();
  for (const mutation of [{source_id:'wrong'}, {source_revid:1}, {source_sha256:'changed'}, {title:''}, {steps:['incomplete']},
    {language:'fr'}, {license:'CC BY-NC 4.0'}, {ingredients:[]}, {editorial_notes:'bad'}, {editorial_notes:[null]}]) {
    const rows = fullRows(true).slice(0, 1); Object.assign(rows[0].translation, mutation); const panel = h.container();
    h.render(panel, {user:'invalid-translation', api:server(rows).api}); await h.open(panel.firstChild); await h.open(cards(panel)[0]);
    assert.equal(cards(panel)[0].firstChild.textContent, 'Potatoes Anna', JSON.stringify(mutation)); assert.equal(findButton(panel, 'Ver original en inglés'), undefined); assert.equal(findButton(panel, 'Descargar traducción TXT'), undefined);
  }
});

function largeCatalog() {
  const base = fullRows()[0];
  return Array.from({length:510}, (_, index) => {
    const row = structuredClone(base); row.id = `synthetic-${index}`; row.title = `Recipe ${index}`; row.cuisine = index === 509 ? 'Mexican' : index % 2 ? 'French' : 'Indian';
    if (index === 509) { row.title = 'Beyondfirstpage lentil special'; row.ingredients_original = ['2 cups uniqueingredient']; } return row;
  });
}

test('510 summaries page within bounds and search globally beyond row 24; filters reset paging', async () => {
  const h = harness(), panel = h.container(), mock = server(largeCatalog()); h.render(panel, {user:'large', api:mock.api}); await h.open(panel.firstChild);
  assert.equal(cards(panel).length, 24); assert.ok(panel.textContent.includes('510')); assert.equal(mock.requests.length, 1); assert.equal(all(panel, 'img').length, 0); assert.equal(all(panel, 'ol').length, 0);
  assert.equal(findButton(panel, 'Página anterior').disabled, true); assert.equal(findButton(panel, 'Página siguiente').disabled, false);
  const cuisine = control(panel, 'Cocina de la fuente', 'select'); assert.ok(cuisine.children.some(option => option.value === 'Mexican'), 'facets cover the whole catalog');
  await findButton(panel, 'Página siguiente').click(); assert.equal(cards(panel).length, 24); assert.equal(cards(panel)[0].firstChild.textContent, 'Recipe 24'); assert.equal(mock.requests.at(-1).url.searchParams.get('cursor'), 'offset:24');
  await findButton(panel, 'Página anterior').click(); assert.equal(cards(panel)[0].firstChild.textContent, 'Recipe 0');
  const search = control(panel, 'Buscar en español o inglés', 'input'), beforeSearch = mock.requests.length;
  search.value = 'Beyond'; await search.emit('input'); await h.tick(100); search.value = 'Beyondfirstpage'; await search.emit('input'); await h.tick(299); assert.equal(mock.requests.length, beforeSearch);
  await h.tick(1); assert.equal(mock.requests.length, beforeSearch + 1); assert.equal(cards(panel).length, 1); assert.equal(cards(panel)[0].firstChild.textContent, 'Beyondfirstpage lentil special');
  assert.ok(!mock.requests.at(-1).url.searchParams.get('cursor')); assert.equal(findButton(panel, 'Página siguiente').disabled, true); assert.equal(all(panel, 'ol').length, 0);
  await h.open(cards(panel)[0]); assert.equal(mock.requests.at(-1).url.pathname, '/v1/home-food/large/open-recipes/detail/synthetic-509'); assert.deepEqual(all(cards(panel)[0], 'ul')[0].children.map(el => el.textContent), ['2 cups uniqueingredient']);
  await findButton(panel, 'Limpiar filtros').click(); assert.equal(search.value, ''); assert.equal(cards(panel).length, 24);
  cuisine.value = 'Mexican'; await cuisine.emit('change'); assert.equal(cards(panel).length, 1); assert.equal(mock.requests.at(-1).url.searchParams.get('cuisine'), 'Mexican'); assert.ok(!mock.requests.at(-1).url.searchParams.get('cursor')); assert.equal(all(panel, 'ol').length, 0);
  await findButton(panel, 'Limpiar filtros').click(); assert.equal(cuisine.value, ''); assert.equal(cards(panel).length, 24);
  assert.ok(mock.requests.length <= 9, 'only requested bounded pages plus one detail'); assert.equal(mock.requests.filter(value => value.url.pathname.includes('/detail/')).length, 1);
});

test('language filter searches the server by original or translated availability', async () => {
  const h = harness(), rows = fullRows(), panel = h.container(); rows[0].translation = structuredClone(translations[0]); const mock = server(rows);
  h.render(panel, {user:'languages', api:mock.api}); await h.open(panel.firstChild); const language = control(panel, 'Idioma disponible', 'select'); assert.ok(language.children.some(option => option.value === 'es'));
  language.value = 'es'; await language.emit('change'); assert.equal(cards(panel).length, 1); assert.equal(mock.requests.at(-1).url.searchParams.get('language'), 'es'); assert.equal(cards(panel)[0].firstChild.textContent, translations[0].title);
  language.value = 'en'; await language.emit('change'); assert.equal(cards(panel).length, 7); await findButton(panel, 'Limpiar filtros').click(); assert.equal(language.value, 'all');
});

test('list and detail failures expose manual retry without automatic retry storms', async () => {
  const h = harness(), panel = h.container(); let attempts = 0; const mock = server(fullRows(), {intercept:() => { if (++attempts === 1) throw new Error('offline'); }});
  h.render(panel, {user:'retry-user', api:mock.api}); await h.open(panel.firstChild); assert.equal(cards(panel).length, 0); assert.ok(panel.textContent.includes('No se pudo cargar')); assert.equal(findButton(panel, 'Reintentar').hidden, false);
  await h.tick(60000); assert.equal(mock.requests.length, 1); await findButton(panel, 'Reintentar').click(); assert.equal(cards(panel).length, 7); assert.equal(mock.requests.length, 2);
  let detailAttempts = 0; const detailPanel = h.container(), detailMock = server(fullRows(), {intercept:req => { if (req.url.pathname.includes('/detail/') && ++detailAttempts === 1) throw new Error('detail offline'); }});
  h.render(detailPanel, {user:'retry-detail', api:detailMock.api}); await h.open(detailPanel.firstChild); await h.open(cards(detailPanel)[0]); assert.equal(all(cards(detailPanel)[0], 'ol').length, 0);
  await h.tick(60000); assert.equal(detailAttempts, 1); await findButton(cards(detailPanel)[0], 'Reintentar receta').click(); assert.equal(all(cards(detailPanel)[0], 'ol').length, 1); assert.equal(detailAttempts, 2);
});

test('409 catalog conflict discards old detail and returns to first page on manual retry', async () => {
  const h = harness(), panel = h.container(); let conflict = true;
  const mock = server(largeCatalog(), {intercept:req => { if (conflict && req.url.pathname.includes('/detail/')) { conflict = false; throw Object.assign(new Error('catalog changed'), {status:409}); } }});
  h.render(panel, {user:'conflict', api:mock.api}); await h.open(panel.firstChild); await findButton(panel, 'Página siguiente').click(); await h.open(cards(panel)[0]);
  assert.equal(all(panel, 'ol').length, 0); assert.equal(cards(panel).length, 0); assert.equal(findButton(panel, 'Reintentar').hidden, false);
  const count = mock.requests.length; await h.tick(60000); assert.equal(mock.requests.length, count); await findButton(panel, 'Reintentar').click();
  assert.equal(cards(panel)[0].firstChild.textContent, 'Recipe 0'); assert.ok(!mock.requests.at(-1).url.searchParams.get('cursor')); assert.equal(mock.requests.at(-1).url.pathname, '/v1/home-food/conflict/open-recipes/summaries');
});

test('filter changes abort list/detail requests and discard late replies before debounce expires', async () => {
  const h = harness(), panel = h.container(), oldList = deferred(), oldDetail = deferred();
  const mock = server(fullRows(), {intercept:req => { if (req.url.searchParams.get('q') === 'lentil') return oldList.promise; if (req.url.pathname.includes('/detail/')) return oldDetail.promise; }});
  h.render(panel, {user:'filter-race', api:mock.api}); await h.open(panel.firstChild); const card = cards(panel)[0]; await h.open(card); const detailRequest = mock.requests.at(-1);
  const search = control(panel, 'Buscar en español o inglés', 'input'); search.value = 'lentil'; await search.emit('input'); await h.tick(300); assert.equal(detailRequest.options.signal.aborted, true);
  const listRequest = mock.requests.at(-1); search.value = 'tomato'; await search.emit('input'); assert.equal(listRequest.options.signal.aborted, true); await h.tick(300);
  assert.equal(cards(panel).length, 1); assert.equal(cards(panel)[0].firstChild.textContent, 'Tomato Pasta');
  const helper = server(), stalePage = await helper.api('/v1/home-food/filter-race/open-recipes/summaries?q=lentil&language=all&limit=24', {signal:new AbortController().signal});
  oldList.resolve(stalePage); oldDetail.resolve({schema_version:2, catalog_version:'fixture-v1', recipe:fullRows()[0]}); await settle();
  assert.equal(cards(panel).length, 1); assert.equal(cards(panel)[0].firstChild.textContent, 'Tomato Pasta'); assert.equal(all(panel, 'ol').length, 0); assert.equal(all(card, 'img').length, 0);
});

test('member changes within one household abort and discard late list/detail responses', async () => {
  const h = harness(), panel = h.container(), oldList = deferred(), old = server(fullRows(), {intercept:() => oldList.promise}), fresh = server([fullRows()[5]]);
  h.render(panel, {user:'same-household', identity:'member-a', api:old.api}); await h.open(panel.firstChild);
  h.render(panel, {user:'same-household', identity:'member-b', api:fresh.api}); assert.equal(old.requests[0].options.signal.aborted, true); await h.open(panel.firstChild);
  oldList.resolve({schema_version:2, catalog_version:'fixture-v1', status:'READY', recipes:[], count:0, matched_total:0, catalog_total:0, next_cursor:null, cuisines:[], languages:[]}); await settle();
  assert.equal(cards(panel).length, 1); assert.equal(cards(panel)[0].firstChild.textContent, 'Tomato Pasta');
  const detail = deferred(), detailsMock = server(fullRows(), {intercept:req => req.url.pathname.includes('/detail/') ? detail.promise : undefined});
  h.render(panel, {user:'same-household', identity:'member-c', api:detailsMock.api}); await h.open(panel.firstChild); const oldCard = cards(panel)[0]; await h.open(oldCard);
  h.render(panel, {user:'same-household', identity:'member-d', api:fresh.api}); assert.equal(detailsMock.requests.at(-1).options.signal.aborted, true); await h.open(panel.firstChild);
  detail.resolve({schema_version:2, catalog_version:'fixture-v1', recipe:fullRows()[0]}); await settle();
  assert.equal(cards(panel)[0].firstChild.textContent, 'Tomato Pasta'); assert.equal(all(panel, 'img').length, 0); assert.equal(all(oldCard, 'img').length, 0);
});

test('inactive views and document hiding cancel requests/timers; invalid identity cannot resume', async () => {
  const h = harness(), panel = h.container(), mock = server(); h.render(panel, {user:'inactive', api:mock.api, active:false});
  await h.open(panel.firstChild); assert.equal(mock.requests.length, 0); h.setActive(panel, true); await settle(); assert.equal(mock.requests.length, 1); assert.equal(cards(panel).length, 7);
  const search = control(panel, 'Buscar en español o inglés', 'input'); search.value = 'lentil'; await search.emit('input'); h.setActive(panel, false); await h.tick(300); assert.equal(mock.requests.length, 1);
  const waiting = deferred(), pendingPanel = h.container(), pendingMock = server(fullRows(), {intercept:() => waiting.promise});
  h.render(pendingPanel, {user:'background', api:pendingMock.api}); await h.open(pendingPanel.firstChild); await h.visibility(true); assert.equal(pendingMock.requests[0].options.signal.aborted, true);
  waiting.resolve({schema_version:2, catalog_version:'fixture-v1', status:'READY', recipes:[], count:0, matched_total:0, catalog_total:0, next_cursor:null, cuisines:[], languages:[]}); await settle();
  assert.equal(cards(pendingPanel).length, 0); const count = pendingMock.requests.length; await h.tick(60000); assert.equal(pendingMock.requests.length, count);
  const currentPanel = h.container(), currentMock = server(); h.render(currentPanel, {user:'expired', api:currentMock.api, isCurrent:() => false});
  await h.open(currentPanel.firstChild); assert.equal(currentMock.requests.length, 0); await h.visibility(false); assert.equal(currentMock.requests.length, 0);
});

test('all 510 summaries remain reachable with 24 cards maximum and no implicit detail or photograph requests', async () => {
  const h = harness(), panel = h.container(), mock = server(largeCatalog()), seen = [];
  h.render(panel, {user:'all-pages', api:mock.api}); await h.open(panel.firstChild);
  for (let page = 0; page < 22; page++) {
    assert.equal(cards(panel).length, page === 21 ? 6 : 24);
    seen.push(...cards(panel).map(card => card.firstChild.textContent));
    assert.equal(all(panel, 'ol').length, 0); assert.equal(all(panel, 'img').length, 0);
    if (page < 21) await findButton(panel, 'Página siguiente').click();
  }
  assert.equal(seen.length, 510); assert.equal(new Set(seen).size, 510);
  assert.equal(findButton(panel, 'Página siguiente').disabled, true); assert.equal(mock.requests.length, 22);
  assert.ok(mock.requests.every(request => request.url.pathname.endsWith('/summaries')));
  await findButton(panel, 'Página anterior').click(); assert.equal(cards(panel)[0].firstChild.textContent, 'Recipe 480');
  assert.equal(mock.requests.at(-1).url.searchParams.get('cursor'), 'offset:480');
});

test('Spanish title and original ingredient search reach the end of a 510-entry catalog', async () => {
  const h = harness(), panel = h.container(), rows = largeCatalog();
  rows[508].translation = {...structuredClone(translations[0]), source_id:rows[508].id, title:'Hallazgo lejano quinientos'};
  const mock = server(rows); h.render(panel, {user:'global-spanish', api:mock.api}); await h.open(panel.firstChild);
  await searchFor(h, panel, 'hallazgo lejano'); assert.equal(cards(panel).length, 1); assert.equal(cards(panel)[0].firstChild.textContent, 'Hallazgo lejano quinientos');
  await searchFor(h, panel, 'uniqueingredient'); assert.equal(cards(panel).length, 1); assert.equal(cards(panel)[0].firstChild.textContent, 'Beyondfirstpage lentil special');
  await searchFor(h, panel, 'this-source-does-not-exist'); assert.equal(cards(panel).length, 0); assert.ok(panel.textContent.includes('No hay coincidencias'));
  assert.equal(mock.requests.length, 4); assert.equal(all(panel, 'img').length, 0);
});

test('closing and reopening a pending card aborts and discards the old result without duplicate requests', async () => {
  const h = harness(), panel = h.container(), first = deferred(), second = deferred(); let details = 0;
  const mock = server(fullRows(), {intercept:request => {
    if (request.url.pathname.includes('/detail/')) return (++details === 1 ? first : second).promise;
  }});
  h.render(panel, {user:'close-reopen', api:mock.api}); await h.open(panel.firstChild); const card = cards(panel)[0];
  await h.open(card); await card.emit('toggle'); assert.equal(details, 1, 'duplicate toggle cannot duplicate an in-flight detail');
  await h.close(card); assert.equal(mock.requests.at(-1).options.signal.aborted, true); await h.open(card); assert.equal(details, 2);
  const oldRecipe = fullRows()[0]; oldRecipe.title = 'Obsolete late detail';
  first.resolve({schema_version:2, catalog_version:'fixture-v1', recipe:oldRecipe}); await settle();
  assert.equal(all(card, 'ol').length, 0); assert.equal(all(card, 'img').length, 0); assert.equal(card.firstChild.textContent, 'Potatoes Anna');
  second.resolve({schema_version:2, catalog_version:'fixture-v1', recipe:fullRows()[0]}); await settle();
  assert.equal(cards(panel)[0], card); assert.equal(all(card, 'ol').length, 1); assert.equal(card.firstChild.textContent, 'Potatoes Anna');
});

test('hiding a panel or leaving recipes aborts pending details and prevents late image hydration', async () => {
  for (const action of ['hidden', 'inactive', 'document', 'outer-close']) {
    const h = harness(), panel = h.container(), pending = deferred();
    const mock = server(fullRows(), {intercept:request => request.url.pathname.includes('/detail/') ? pending.promise : undefined});
    h.render(panel, {user:'leave-detail', api:mock.api}); await h.open(panel.firstChild); const card = cards(panel)[0]; await h.open(card); const request = mock.requests.at(-1);
    if (action === 'hidden') h.render(panel, {user:'leave-detail', api:mock.api, hidden:true});
    if (action === 'inactive') h.setActive(panel, false);
    if (action === 'document') await h.visibility(true);
    if (action === 'outer-close') await h.close(panel.firstChild);
    assert.equal(request.options.signal.aborted, true, action);
    pending.resolve({schema_version:2, catalog_version:'fixture-v1', recipe:fullRows()[0]}); await settle(); await h.tick(1000);
    assert.equal(all(card, 'ol').length, 0, action); assert.equal(all(card, 'img').length, 0, action); assert.equal(mock.requests.length, 2, action);
  }
});

test('a different catalog version in list or detail cannot mix source editions', async () => {
  for (const phase of ['list', 'detail']) {
    const h = harness(), panel = h.container(), rows = largeCatalog(), changed = server(rows, {version:'fixture-v2'});
    const mock = server(rows, {intercept:request => {
      if (phase === 'list' && request.url.searchParams.get('cursor')) return changed.api(request.path, request.options);
      if (phase === 'detail' && request.url.pathname.includes('/detail/')) return {schema_version:2, catalog_version:'fixture-v2', recipe:rows[0]};
    }});
    h.render(panel, {user:'different-version', api:mock.api}); await h.open(panel.firstChild);
    if (phase === 'list') await findButton(panel, 'Página siguiente').click(); else await h.open(cards(panel)[0]);
    assert.equal(cards(panel).length, 0, phase); assert.equal(all(panel, 'img').length, 0, phase);
    assert.equal(findButton(panel, 'Reintentar').hidden, false, phase); assert.ok(panel.textContent.includes('se actualizó'));
    await h.tick(60000); assert.equal(mock.requests.length, 2, 'a version mismatch cannot auto-loop');
    await findButton(panel, 'Reintentar').click(); assert.equal(cards(panel)[0].firstChild.textContent, 'Recipe 0'); assert.ok(!mock.requests.at(-1).url.searchParams.get('cursor'));
  }
});

test('list and detail deadlines recover even when transport ignores AbortSignal and never settles', async () => {
  for (const phase of ['list', 'detail']) {
    const h = harness(), panel = h.container(), stuck = deferred(); let failed = false;
    const mock = server(fullRows(), {intercept:request => {
      if (!failed && (phase === 'list' || request.url.pathname.includes('/detail/'))) { failed = true; return stuck.promise; }
    }});
    h.render(panel, {user:'deadline', api:mock.api}); await h.open(panel.firstChild);
    let card; if (phase === 'detail') { card = cards(panel)[0]; await h.open(card); }
    const request = mock.requests.at(-1); await h.tick(11999); assert.equal(request.options.signal.aborted, false, phase);
    await h.tick(1); assert.equal(request.options.signal.aborted, true, phase);
    const retry = findButton(card || panel, phase === 'detail' ? 'Reintentar receta' : 'Reintentar'); assert.equal(retry.hidden, false, phase);
    const count = mock.requests.length; await h.tick(60000); assert.equal(mock.requests.length, count, 'timeout must not create an automatic retry loop');
    await retry.click(); assert.equal(mock.requests.length, count + 1, phase);
    if (phase === 'list') assert.equal(cards(panel).length, 7); else assert.equal(all(card, 'ol').length, 1);
    const afterRetry = panel.textContent;
    stuck.resolve({schema_version:2, catalog_version:'unrelated-old-version', recipe:fullRows()[0]}); await settle();
    assert.equal(panel.textContent, afterRetry, 'a timed-out transport cannot overwrite the successful retry');
  }
});

test('retrying a failed next page preserves that requested cursor', async () => {
  const h = harness(), panel = h.container(); let failed = false;
  const mock = server(largeCatalog(), {intercept:request => {
    if (!failed && request.url.searchParams.get('cursor') === 'offset:24') { failed = true; throw new Error('page unavailable'); }
  }});
  h.render(panel, {user:'page-retry', api:mock.api}); await h.open(panel.firstChild); await findButton(panel, 'Página siguiente').click();
  assert.equal(cards(panel).length, 0); assert.equal(findButton(panel, 'Reintentar').hidden, false); await findButton(panel, 'Reintentar').click();
  assert.equal(mock.requests.at(-1).url.searchParams.get('cursor'), 'offset:24'); assert.equal(cards(panel)[0].firstChild.textContent, 'Recipe 24');
  assert.equal(findButton(panel, 'Página anterior').disabled, false); await findButton(panel, 'Página anterior').click(); assert.equal(cards(panel)[0].firstChild.textContent, 'Recipe 0');
});

test('detail identity, revision, hash, language, and action gates must match the summary', async () => {
  for (const mutation of [{id:'different-recipe'}, {revid:1}, {source_sha256:'wrong'}, {language:'es'},
    {can_cook_with_roxy:true}, {can_add_to_shopping:true}, {ingredients_original:[]}, {steps_original:['']}]) {
    const h = harness(), panel = h.container();
    const mock = server(fullRows(), {intercept:request => request.url.pathname.includes('/detail/') ?
      {schema_version:2, catalog_version:'fixture-v1', recipe:{...fullRows()[0], ...mutation}} : undefined});
    h.render(panel, {user:'invalid-detail', api:mock.api}); await h.open(panel.firstChild); const card = cards(panel)[0]; await h.open(card);
    assert.equal(all(card, 'ol').length, 0, JSON.stringify(mutation)); assert.equal(all(card, 'img').length, 0, JSON.stringify(mutation));
    assert.equal(findButton(card, 'Reintentar receta').hidden, false); assert.equal(findButton(card, 'Descargar original TXT'), undefined);
  }
});
