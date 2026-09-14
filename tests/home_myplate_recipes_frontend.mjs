import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

// Synthetic DOM/API contracts only: these are not real recipes or editorial evidence.
const code = fs.readFileSync(new URL('../assets/roxy_home_myplate_recipes.js', import.meta.url), 'utf8');
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return {promise, resolve, reject}; };
const settle = async () => { for (let i = 0; i < 24; i++) await Promise.resolve(); };
const descendants = parent => parent.children.flatMap(child => [child, ...descendants(child)]);
const all = (parent, tag) => descendants(parent).filter(el => el.tagName === tag.toUpperCase());
const byClass = (parent, name) => descendants(parent).filter(el => String(el.className || '').split(/\s+/).includes(name));
const button = (parent, title) => all(parent, 'button').find(el => el.textContent === title);
const rows = Array.from({length: 51}, (_, index) => ({
  slug: `synthetic-${String(index).padStart(3, '0')}`, title: `Synthetic source ${index}`, description: 'Test fixture, not food advice',
  category: index % 2 ? 'Beverage' : 'Dessert', language: 'en',
  image_url: `https://storage.googleapis.com/peppermint-cdn/myplate.food-recipe-images/synthetic-${index}.jpg`,
  source_url: `https://myplate.food/recipes/synthetic-${String(index).padStart(3, '0')}`, translation_urls: {},
}));
const detail = row => ({...structuredClone(row),
  ingredients: [{text: '1/2 cup synthetic A', note: 'Test note, not an instruction'}, {text: '1.5 tablespoons synthetic B', note: null}],
  directions: 'Synthetic step A: keep 1.5 and 1/2 exactly.\nSynthetic step B: preserve this full paragraph.\nFinal synthetic test line.',
  yield: '2 synthetic portions', serving_size: '1/2 test portion', notes: 'Synthetic note, not a recipe',
  source: 'Synthetic source only', contributor: 'Synthetic contributor',
  original_source_url: `https://www.myplate.gov/recipes/${row.slug}`, can_cook: false, can_add_to_shopping: false,
});

function harness({guide = false} = {}) {
  const timers = new Map(), documentListeners = {}, storageWrites = [], guideMounts = [];
  let activeElement, now = 0, timerId = 0;
  class Element {
    constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.listeners = {}; this._text = ''; this.value = ''; this.hidden = false; this.parent = null; this.dataset = {}; this.className = ''; }
    get textContent() { return this._text + this.children.map(el => el.textContent).join(''); }
    set textContent(value) { this._text = String(value); this.children.forEach(el => { el.parent = null; }); this.children = []; }
    get isConnected() { return this.root || Boolean(this.parent?.isConnected); }
    get firstChild() { return this.children[0]; }
    get parentNode() { return this.parent; }
    append(...elements) { elements.forEach(el => { el.parent = this; this.children.push(el); }); }
    appendChild(el) { this.append(el); return el; }
    insertBefore(el, before) { el.parent=this; const index=this.children.indexOf(before); if(index<0)this.children.push(el);else this.children.splice(index,0,el);return el; }
    after(el) { this.parent?.insertBefore(el,this.parent.children[this.parent.children.indexOf(this)+1]); }
    replaceChildren(...elements) { this.children.forEach(el => { el.parent = null; }); this.children = []; this._text = ''; this.append(...elements); }
    remove() { if (this.parent) { this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null; } }
    contains(el) { return this === el || this.children.some(child => child.contains(el)); }
    closest(selector) { return selector === '[hidden]' ? (this.hidden ? this : this.parent?.closest(selector) || null) : null; }
    setAttribute(name, value) { this[name] = String(value); }
    getAttribute(name) { return this[name] ?? null; }
    removeAttribute(name) { delete this[name]; }
    addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
    removeEventListener(name, callback) { this.listeners[name] = (this.listeners[name] || []).filter(el => el !== callback); }
    async emit(name) { for (const fn of [...(this.listeners[name] || [])]) fn({target:this, currentTarget:this, preventDefault() {}}); await settle(); }
    click() { return this.disabled ? Promise.resolve() : this.emit('click'); }
    focus(options = {}) {
      if (this.closest('[hidden]') || (this.classList.contains('myplate-status') && !this.textContent)) return;
      activeElement = this; this.lastFocusOptions = options;
    }
    scrollIntoView(options = {}) { this.lastScrollOptions = options; }
    querySelectorAll(selector) { return selector.startsWith('.') ? byClass(this, selector.slice(1)) : all(this, selector); }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    get classList() { return {add: name => { this.className += ` ${name}`; }, remove: name => { this.className = this.className.split(/\s+/).filter(value => value !== name).join(' '); }, contains: name => this.className.split(/\s+/).includes(name)}; }
  }
  const document = {hidden:false, createElement:tag => new Element(tag), body:new Element('body'),
    addEventListener(name, fn) { (documentListeners[name] ||= []).push(fn); },
    removeEventListener(name, fn) { documentListeners[name] = (documentListeners[name] || []).filter(value => value !== fn); }};
  document.body.root = true;
  const forbidden = action => { storageWrites.push(action); throw new Error(`Forbidden external/storage operation: ${action}`); };
  const sandbox = {window:{}, document, URL, URLSearchParams, AbortController, Date:class extends Date {static now() {return now;}},
    setTimeout(fn, delay = 0) { const id = ++timerId; timers.set(id, {fn, due:now + delay}); return id; }, clearTimeout(id) { timers.delete(id); },
    fetch() { return forbidden('browser fetch'); }, localStorage:{setItem() { forbidden('localStorage'); }, getItem() { forbidden('localStorage read'); }},
    sessionStorage:{setItem() { forbidden('sessionStorage'); }, getItem() { forbidden('sessionStorage read'); }}, indexedDB:{open() { forbidden('indexedDB'); }}};
  if (guide) sandbox.window.RoxyRecipeGuide = {mount(host, options) {
    const call = {host, options, disposals:0, activations:[]};
    call.controller = {dispose() { call.disposals++; }, setActive(value) { call.activations.push(value); }};
    guideMounts.push(call); return call.controller;
  }};
  vm.runInNewContext(code, sandbox);
  const container = () => { const el = new Element('div'); document.body.append(el); return el; };
  const tick = async duration => { const until = now + duration;
    for (;;) { const item = [...timers].filter(([, value]) => value.due <= until).sort((a,b) => a[1].due - b[1].due)[0]; if (!item) break;
      const [id, value] = item; timers.delete(id); now = value.due; value.fn(); await settle(); }
    now = until; await settle(); };
  const visibility = async hidden => { document.hidden = hidden; for (const fn of [...(documentListeners.visibilitychange || [])]) fn(); await settle(); };
  return {...sandbox.window.RoxyMyPlateRecipes, container, tick, visibility, storageWrites, guideMounts, suspend:duration => {now += duration;},
    get activeElement() { return activeElement; }, get timers() { return timers; }};
}

function server({items = rows, intercept, detailMutation} = {}) {
  const requests = [];
  const api = async (path, options = {}) => {
    const url = new URL(path, 'https://home.invalid');
    assert.equal(url.origin, 'https://home.invalid'); assert.equal(options.method || 'GET', 'GET');
    assert.equal(url.searchParams.get('requested'), 'true'); assert.ok(options.signal instanceof AbortSignal);
    const call = {path, url, options}; requests.push(call); const override = intercept?.(call, requests.length);
    if (override !== undefined) return await override;
    if (url.pathname.endsWith('/myplate-recipes')) {
      const q = (url.searchParams.get('q') || '').toLowerCase(), category = url.searchParams.get('category') || '';
      const offset = Number(url.searchParams.get('offset') || 0), limit = Number(url.searchParams.get('limit') || 24);
      assert.equal(limit, 24); const filtered = items.filter(row => row.title.toLowerCase().includes(q) && (!category || row.category === category));
      return {recipes:structuredClone(filtered.slice(offset, offset + limit)), total:filtered.length, offset, limit,
        next_offset:offset + limit < filtered.length ? offset + limit : null,
        category_options:['Main dish', 'Dessert', 'Beverage', 'Salad', 'Soup', 'Breakfast', 'Bread', 'Side dish'], source:'Synthetic original source', provider:'MyPlate.food', live:true, audience:'human'};
    }
    assert.match(url.pathname, /\/myplate-recipes\/[a-z0-9-]+$/);
    const slug = url.pathname.split('/').at(-1), item = items.find(row => row.slug === slug); assert.ok(item, `Unknown synthetic slug ${slug}`);
    return {recipe:{...detail(item), ...detailMutation}};
  };
  return {api, requests};
}

const start = async (h, panel, mock, extra = {}) => {
  h.render(panel, {user:'household/a', identity:'member-a', api:mock.api, ...extra});
  assert.equal(mock.requests.length, 0, 'render must not call a live source');
  assert.ok(button(panel, 'Explorar recetas')); await button(panel, 'Explorar recetas').click(); await settle();
};

test('no autoquery: explicit exploration loads only 24 safe cards, not ingredients or provider storage', async () => {
  const h = harness(), panel = h.container(), mock = server();
  h.render(panel, {user:'household/a', identity:'member-a', api:mock.api}); await h.tick(60000);
  assert.equal(mock.requests.length, 0); assert.equal(byClass(panel, 'myplate-recipe-card').length, 0);
  await button(panel, 'Explorar recetas').click();
  assert.equal(mock.requests.length, 1); assert.equal(mock.requests[0].url.pathname, '/v1/home-food/household%2Fa/myplate-recipes');
  assert.equal(mock.requests[0].url.searchParams.get('offset'), '0'); assert.equal(byClass(panel, 'myplate-recipe-card').length, 24);
  assert.equal(byClass(panel, 'myplate-directions').length, 0); assert.equal(byClass(panel, 'myplate-ingredients').length, 0);
  assert.equal(all(panel, 'img').length, 24); assert.ok(all(panel, 'img').every(image => image.referrerPolicy === 'no-referrer' && image.loading === 'lazy'));
  assert.deepEqual(h.storageWrites, []); assert.ok(panel.textContent.includes('51'));
});

test('pagination replaces 24 cards instead of accumulating or fetching hidden detail', async () => {
  const h = harness(), panel = h.container(), mock = server(); await start(h, panel, mock);
  await button(panel, 'Página siguiente').click();
  assert.equal(mock.requests.length, 2); assert.equal(mock.requests.at(-1).url.searchParams.get('offset'), '24');
  assert.equal(byClass(panel, 'myplate-recipe-card').length, 24);
  assert.equal(byClass(panel, 'myplate-recipe-card')[0].textContent.includes(rows[24].title), true);
  assert.equal(all(byClass(panel, 'myplate-grid')[0], 'h3').some(title => title.textContent === rows[0].title), false);
  await button(panel, 'Página siguiente').click();
  assert.equal(byClass(panel, 'myplate-recipe-card').length, 3); assert.equal(button(panel, 'Página siguiente').disabled, true);
  await button(panel, 'Página anterior').click();
  assert.equal(byClass(panel, 'myplate-recipe-card').length, 24); assert.equal(mock.requests.at(-1).url.searchParams.get('offset'), '24');
  assert.ok(mock.requests.every(call => call.url.pathname.endsWith('/myplate-recipes')));
});

test('bottom pagination focuses the first new recipe and scrolls its card into view when the empty status is hidden', async () => {
  const h = harness(), panel = h.container(), mock = server(); await start(h, panel, mock);
  const oldFirst = byClass(panel, 'myplate-recipe-card')[0];
  await button(panel, 'Página siguiente').click();
  const first = byClass(panel, 'myplate-recipe-card')[0], heading = all(first, 'h3')[0];
  assert.notEqual(first, oldFirst); assert.equal(oldFirst.isConnected, false);
  assert.equal(byClass(panel, 'myplate-status')[0].textContent, '');
  assert.equal(h.activeElement, heading); assert.equal(heading.tabIndex, -1);
  assert.equal(heading.textContent, rows[24].title); assert.equal(heading.lastFocusOptions.preventScroll, true);
  assert.equal(first.lastScrollOptions.block, 'start'); assert.equal(first.lastScrollOptions.behavior, 'auto');
});

test('an explicit search with no results focuses its visible empty message', async () => {
  const h = harness(), panel = h.container(), mock = server(); await start(h, panel, mock);
  all(panel, 'input')[0].value = 'no-synthetic-matches'; await all(panel, 'form')[0].emit('submit');
  const status = byClass(panel, 'myplate-status')[0];
  assert.equal(h.activeElement, status); assert.match(status.textContent, /No encontramos/);
  assert.equal(status.lastFocusOptions.preventScroll, false);
});

for (const target of ['catalog', 'detail']) test(`an explicit ${target} failure focuses the visible error and preserves retry`, async () => {
  const h = harness(), panel = h.container();
  const mock = server({intercept:(_call, n) => n === 2 ? Promise.reject(new Error('synthetic transport failure')) : undefined});
  await start(h, panel, mock);
  await button(panel, target === 'catalog' ? 'Página siguiente' : 'Ver receta').click();
  const status = byClass(panel, 'myplate-status')[0];
  assert.equal(h.activeElement, status); assert.match(status.textContent, /No pudimos/);
  assert.equal(status.lastFocusOptions.preventScroll, false); assert.equal(button(panel, 'Reintentar consulta').hidden, false);
});

test('search and category changes are explicit, reset page, and preserve query text without household data', async () => {
  const h = harness(), panel = h.container(), mock = server(); await start(h, panel, mock); await button(panel, 'Página siguiente').click();
  const search = all(panel, 'input')[0]; search.value = 'source 50'; await search.emit('input'); await h.tick(1000);
  assert.equal(mock.requests.length, 2, 'typing does not consume a provider call');
  await all(panel, 'form')[0].emit('submit');
  assert.equal(mock.requests.length, 3); assert.equal(mock.requests.at(-1).url.searchParams.get('offset'), '0');
  assert.equal(mock.requests.at(-1).url.searchParams.get('q'), 'source 50'); assert.equal(byClass(panel, 'myplate-recipe-card').length, 1);
  await button(panel, 'Ver todas').click(); assert.equal(byClass(panel, 'myplate-recipe-card').length, 24);
  const category = byClass(panel, 'myplate-categories')[0].children.find(el => el.textContent === 'Bebidas');
  assert.ok(category); await category.click(); assert.equal(mock.requests.at(-1).url.searchParams.get('category'), 'Beverage');
  assert.equal(mock.requests.at(-1).url.searchParams.get('offset'), '0');
  assert.ok(mock.requests.every(call => !call.url.search.includes('member-a') && !call.url.search.includes('household')));
});

test('detail preserves every ingredient measure, note, yield, paragraph and line without fabricated steps', async () => {
  const one = [{...rows[0], translation_urls:{es:'https://myplate.food/es/recipes/fuente-sintetica'}}];
  const h = harness(), panel = h.container(), mock = server({items:one}); await start(h, panel, mock);
  await button(panel, 'Ver receta').click();
  assert.equal(mock.requests.length, 2); assert.ok(mock.requests.at(-1).url.pathname.endsWith('/synthetic-000'));
  const body = byClass(panel, 'myplate-detail-body')[0], expected = detail(one[0]);
  assert.equal(byClass(body, 'myplate-directions')[0].textContent, expected.directions);
  assert.equal(byClass(body, 'myplate-directions')[0].lang, 'en');
  assert.deepEqual(byClass(body, 'myplate-ingredients')[0].children.map(el => all(el, 'span')[0].textContent), expected.ingredients.map(item => item.text));
  for (const exact of [expected.ingredients[0].note, expected.yield, expected.serving_size, expected.notes, expected.contributor]) assert.ok(body.textContent.includes(exact));
  assert.equal(all(body, 'ol').length, 0, 'string source directions must not become invented numbered steps');
  assert.ok(all(body, 'a').some(link => link.href === one[0].translation_urls.es));
  assert.ok(all(body, 'a').every(link => link.rel === 'noopener noreferrer' && link.href.startsWith('https://myplate.food/')));
  assert.ok(!button(panel, 'Agregar ingredientes') && !button(panel, 'Cocinar paso a paso') && !button(panel, 'Guardar receta'));
  await button(panel, 'Volver a las recetas').click(); assert.equal(byClass(panel, 'myplate-directions').length, 0);
  assert.equal(mock.requests.length, 2); assert.equal(byClass(panel, 'myplate-recipe-card').length, 1); assert.deepEqual(h.storageWrites, []);
  await button(panel, 'Ver receta').click(); assert.equal(mock.requests.length, 3, 'a later opening re-queries live, without a persisted detail cache');
});

test('no photo fallback or browser fetch when the exact source image fails', async () => {
  const h = harness(), panel = h.container(), mock = server({items:rows.slice(0,1)}); await start(h, panel, mock);
  const image = all(panel, 'img')[0]; assert.ok(image); await image.emit('error');
  assert.equal(all(panel, 'img').length, 0); assert.ok(byClass(panel, 'myplate-photo-empty').some(el => !el.hidden));
  assert.equal(mock.requests.length, 1); assert.deepEqual(h.storageWrites, []);
});

for (const image_url of [
  'https://storage.googleapis.com.evil.test/peppermint-cdn/myplate.food-recipe-images/x.jpg',
  'https://storage.googleapis.com/other-bucket/x.jpg', 'https://myplate.food.evil.test/x.jpg',
  'https://user:secret@storage.googleapis.com/peppermint-cdn/myplate.food-recipe-images/x.jpg',
  'https://storage.googleapis.com:444/peppermint-cdn/myplate.food-recipe-images/x.jpg',
  'https://storage.googleapis.com/peppermint-cdn/myplate.food-recipe-images/x.svg',
  'https://storage.googleapis.com/peppermint-cdn/myplate.food-recipe-images/x.jpg?track=1',
  'javascript:alert(1)', 'data:image/svg+xml,<svg onload=alert(1)>',
]) test(`unapproved image URL is never rendered: ${image_url}`, async () => {
  const h = harness(), panel = h.container(), mock = server({items:[{...rows[0], image_url}]}); await start(h, panel, mock);
  assert.equal(byClass(panel, 'myplate-recipe-card').length, 1); assert.equal(all(panel, 'img').length, 0); assert.deepEqual(h.storageWrites, []);
});

for (const mutation of [{slug:'synthetic-wrong'}, {ingredients:[]}, {ingredients:[{text:'', note:null}]}, {directions:''}, {can_cook:true}, {can_add_to_shopping:true}]) {
  test(`invalid detail fails closed without replacement: ${JSON.stringify(mutation)}`, async () => {
    const h = harness(), panel = h.container(), mock = server({items:rows.slice(0,1), detailMutation:mutation}); await start(h, panel, mock);
    await button(panel, 'Ver receta').click(); assert.equal(byClass(panel, 'myplate-directions').length, 0);
    assert.equal(button(panel, 'Reintentar consulta').hidden, false); assert.ok(all(panel, 'a').some(link => link.href === rows[0].source_url));
    assert.deepEqual(h.storageWrites, []);
  });
}

test('source timeout expires at 12 seconds even when transport ignores abort; late data cannot paint', async () => {
  const pending = deferred(), h = harness(), panel = h.container(), mock = server({intercept:(call, number) => number === 1 ? pending.promise : undefined});
  await start(h, panel, mock); await h.tick(11999); assert.equal(mock.requests[0].options.signal.aborted, false);
  await h.tick(1); assert.equal(mock.requests[0].options.signal.aborted, true); assert.equal(button(panel, 'Reintentar consulta').hidden, false);
  assert.ok(byClass(panel, 'myplate-status')[0].textContent.includes('tardando'));
  await button(panel, 'Reintentar consulta').click(); assert.equal(mock.requests.length, 2); assert.equal(byClass(panel, 'myplate-recipe-card').length, 24);
  pending.resolve({recipes:[], provider:'MyPlate.food', live:true, total:0, offset:0, limit:24, next_offset:null}); await settle();
  assert.equal(byClass(panel, 'myplate-recipe-card').length, 24); assert.equal(h.timers.size, 0);
});

for (const interruptedBy of ['scope', 'ancestor']) for (const outcome of ['response', 'timeout']) {
  test(`an unnoticed ${interruptedBy} change during ${outcome} leaves a recoverable query instead of a loading label`, async () => {
    const pending = deferred(), h = harness(), outer = h.container(), panel = h.container(); outer.append(panel);
    let matches = true;
    const mock = server({intercept:(_call, number) => number === 1 ? pending.promise : undefined});
    await start(h, panel, mock, {isCurrent:() => matches});
    if (interruptedBy === 'scope') matches = false; else outer.hidden = true;
    if (outcome === 'timeout') await h.tick(12000);
    else {pending.resolve({recipes:[],provider:'MyPlate.food',live:true,total:0,offset:0,limit:24,next_offset:null}); await settle();}
    assert.equal(byClass(panel, 'myplate-library')[0].getAttribute('aria-busy'), 'false');
    assert.equal(button(panel, 'Reintentar consulta').hidden, false);
    assert.doesNotMatch(byClass(panel, 'myplate-status')[0].textContent, /Consultando/);
    assert.equal(byClass(panel, 'myplate-recipe-card').length, 0);
    matches = true; outer.hidden = false; h.setActive(panel, true); await settle();
    assert.equal(mock.requests.length, 1, 'resuming does not spend another provider request automatically');
    await button(panel, 'Reintentar consulta').click();
    assert.equal(mock.requests.length, 2); assert.equal(byClass(panel, 'myplate-recipe-card').length, 24);
    assert.equal(h.timers.size, 0);
  });
}

test('a suspended timer expires immediately on activation and does not require its delayed callback', async () => {
  const pending = deferred(), h = harness(), panel = h.container(), mock = server({intercept:() => pending.promise});
  await start(h, panel, mock); h.suspend(15000); h.setActive(panel, true); await settle();
  assert.equal(mock.requests[0].options.signal.aborted, true); assert.equal(h.timers.size, 0);
  assert.equal(button(panel, 'Reintentar consulta').hidden, false); assert.equal(button(panel, 'Buscar recetas').disabled, false);
  assert.match(byClass(panel, 'myplate-status')[0].textContent, /tardando/); assert.equal(mock.requests.length, 1);
});

for (const target of ['catalog', 'detail']) test(`cancel remains available during ${target} loading and retry ignores the late cancelled response`, async () => {
  const pending = deferred(), h = harness(), panel = h.container();
  const mock = server({intercept:(_call, n) => n === (target === 'catalog' ? 1 : 2) ? pending.promise : undefined});
  await start(h, panel, mock); if (target === 'detail') await button(panel, 'Ver receta').click();
  const count = mock.requests.length, cancel = button(panel, 'Cancelar consulta');
  assert.equal(cancel.hidden, false); assert.ok(!cancel.disabled); await cancel.click();
  assert.equal(mock.requests[count - 1].options.signal.aborted, true); assert.equal(cancel.hidden, true);
  assert.equal(button(panel, 'Reintentar consulta').hidden, false); assert.equal(h.timers.size, 0);
  await button(panel, 'Reintentar consulta').click(); assert.equal(mock.requests.length, count + 1);
  const view = target === 'catalog' ? 'myplate-grid' : 'myplate-detail-body', visible = byClass(panel, view)[0].textContent;
  pending.resolve(null); await settle(); assert.equal(byClass(panel, view)[0].textContent, visible);
  assert.equal(button(panel, 'Reintentar consulta').hidden, true); assert.equal(h.timers.size, 0);
});

test('catalogue information stays in the heading and closes without provider requests', async () => {
  const h = harness(), panel = h.container(), mock = server(); await start(h, panel, mock);
  assert.equal(byClass(panel, 'myplate-status')[0].textContent, '');
  assert.equal(byClass(panel, 'myplate-pagination').length, 1);
  assert.equal(byClass(panel, 'myplate-total')[0].textContent, '51 recetas · originales en inglés');
  const credits = byClass(panel, 'myplate-credits')[0]; assert.equal(credits.tagName, 'DETAILS'); assert.ok(!credits.open);
  assert.ok(credits.contains(byClass(panel, 'myplate-quota')[0])); assert.ok(credits.contains(byClass(panel, 'myplate-language')[0]));
  assert.match(credits.textContent, /USDA MyPlate Kitchen/); assert.match(credits.textContent, /20 consultas por minuto/);
  assert.equal(credits.parentNode,byClass(panel,'myplate-heading')[0]);
  const summary=all(credits,'summary')[0];assert.equal(summary.getAttribute('aria-label'),'Información del recetario');
  const calls=mock.requests.length;credits.open=true;await button(credits,'Cerrar información').click();
  assert.equal(credits.open,false);assert.equal(mock.requests.length,calls);
});

for (const exit of ['inactive', 'hidden', 'identity', 'document']) test(`pending list is cancelled and ignored on ${exit}`, async () => {
  const pending = deferred(), h = harness(), panel = h.container(), mock = server({intercept:() => pending.promise}); await start(h, panel, mock);
  if (exit === 'inactive') h.setActive(panel, false);
  if (exit === 'hidden') h.render(panel, {user:'household/a', identity:'member-a', api:mock.api, hidden:true});
  if (exit === 'identity') h.render(panel, {user:'household/a', identity:'member-b', api:mock.api});
  if (exit === 'document') await h.visibility(true);
  assert.equal(mock.requests[0].options.signal.aborted, true);
  pending.resolve({recipes:[rows[0]], provider:'MyPlate.food', live:true, total:1, offset:0, limit:24, next_offset:null}); await settle();
  assert.equal(byClass(panel, 'myplate-recipe-card').length, 0); assert.equal(h.timers.size, 0);
  if (exit === 'identity') assert.ok(button(panel, 'Explorar recetas'));
});

test('back cancels pending detail, keeps catalogue and discards late source response', async () => {
  const pending = deferred(), h = harness(), panel = h.container(), mock = server({items:rows.slice(0,1), intercept:call => call.url.pathname.endsWith('/synthetic-000') ? pending.promise : undefined});
  await start(h, panel, mock); await button(panel, 'Ver receta').click(); assert.equal(mock.requests.length, 2);
  await button(panel, 'Volver a las recetas').click(); assert.equal(mock.requests[1].options.signal.aborted, true);
  pending.resolve({recipe:detail(rows[0])}); await settle(); assert.equal(byClass(panel, 'myplate-directions').length, 0);
  assert.equal(byClass(panel, 'myplate-recipe-card').length, 1); assert.equal(h.timers.size, 0);
});

test('429 reports provider limit and permits deliberate retry without pretending catalogue is empty', async () => {
  const h = harness(), panel = h.container(), mock = server({intercept:(call, number) => number === 1 ? Promise.reject(Object.assign(new Error('private upstream'), {status:429})) : undefined});
  await start(h, panel, mock); assert.equal(button(panel, 'Reintentar consulta').hidden, false);
  assert.ok(byClass(panel, 'myplate-status')[0].textContent.includes('límite')); assert.ok(!panel.textContent.includes('private upstream'));
  assert.ok(!panel.textContent.includes('0 recetas')); await button(panel, 'Reintentar consulta').click();
  assert.equal(byClass(panel, 'myplate-recipe-card').length, 24); assert.equal(mock.requests.length, 2);
});

test('inactive rendering and duplicate explore clicks cannot issue hidden or parallel calls', async () => {
  const pending = deferred(), h = harness(), panel = h.container(), mock = server({intercept:() => pending.promise});
  h.render(panel, {user:'household/a', identity:'member-a', api:mock.api, active:false});
  await button(panel, 'Explorar recetas').click(); assert.equal(mock.requests.length, 0);
  h.setActive(panel, true); await button(panel, 'Explorar recetas').click(); await button(panel, 'Explorar recetas').click();
  assert.equal(mock.requests.length, 1); h.setActive(panel, false); assert.equal(mock.requests[0].options.signal.aborted, true);
});

test('changing identities clears an already loaded source detail without sharing or refetching it', async () => {
  const h = harness(), panel = h.container(), mock = server({items:rows.slice(0,1)}); await start(h, panel, mock);
  await button(panel, 'Ver receta').click(); assert.equal(byClass(panel, 'myplate-directions').length, 1);
  h.render(panel, {user:'household/a', identity:'member-b', api:mock.api});
  assert.equal(byClass(panel, 'myplate-directions').length, 0); assert.equal(byClass(panel, 'myplate-recipe-card').length, 0);
  assert.equal(mock.requests.length, 2); assert.ok(button(panel, 'Explorar recetas'));
});

for (const mutation of [{provider:'InventedSource'}, {live:false}, {recipes:[rows[0], rows[0]]}, {offset:24}, {limit:100}, {next_offset:50}]) {
  test(`malformed page fails before rendering cards: ${JSON.stringify(mutation)}`, async () => {
    const payload = {recipes:[rows[0]],total:51,offset:0,limit:24,next_offset:24,source:'Synthetic source',provider:'MyPlate.food',live:true,audience:'human',...mutation};
    const h = harness(), panel = h.container(), mock = server({intercept:() => Promise.resolve(payload)}); await start(h, panel, mock);
    assert.equal(byClass(panel, 'myplate-recipe-card').length, 0); assert.equal(button(panel, 'Reintentar consulta').hidden, false);
    assert.deepEqual(h.storageWrites, []);
  });
}

test('unified explore auto-loads one summary page without focus, details, duplicate requests or a redundant flat menu', async () => {
  const h = harness(), panel = h.container(), mock = server();
  const options = {user:'household/a', identity:'member-a', api:mock.api, browseGroup:'all', autoLoad:true};
  h.render(panel, options); await settle();
  assert.equal(mock.requests.length, 1); assert.equal(byClass(panel, 'myplate-recipe-card').length, 24);
  assert.equal(byClass(panel, 'myplate-start')[0].hidden, true);
  assert.equal(byClass(panel, 'myplate-categories')[0].hidden, true); assert.equal(h.activeElement, undefined);
  assert.equal(byClass(panel, 'myplate-directions').length, 0);
  assert.ok(byClass(panel, 'myplate-quota')[0].textContent.includes('100 fichas completas/día'));
  assert.ok(!byClass(panel, 'myplate-quota')[0].hidden);
  h.render(panel, options); h.setActive(panel, true); await settle();
  assert.equal(mock.requests.length, 1);
  await button(panel, 'Página siguiente').click(); assert.equal(mock.requests.length, 2);
  assert.equal(h.activeElement, all(byClass(panel, 'myplate-recipe-card')[0], 'h3')[0]);
  h.render(panel, options); await settle();
  assert.equal(mock.requests.length, 2); assert.equal(mock.requests.at(-1).url.searchParams.get('offset'), '24');
});

test('auto-load waits for active visibility and identity, then executes only once', async () => {
  const h = harness(), panel = h.container(), mock = server(); let ownerMatches = false;
  const options = {user:'household/a', identity:'member-a', api:mock.api, autoLoad:true, active:false, isCurrent:() => ownerMatches};
  h.render(panel, options); await settle(); assert.equal(mock.requests.length, 0);
  h.setActive(panel, true); await settle(); assert.equal(mock.requests.length, 0);
  ownerMatches = true; await h.visibility(true); h.setActive(panel, true); await settle(); assert.equal(mock.requests.length, 0);
  await h.visibility(false); assert.equal(mock.requests.length, 1); assert.equal(h.activeElement, undefined);
  await h.visibility(true); await h.visibility(false); h.render(panel, {...options, active:true}); await settle();
  assert.equal(mock.requests.length, 1);
});

test('hidden pet container never auto-loads and rendering human context starts exactly one page', async () => {
  const h = harness(), panel = h.container(), mock = server();
  const options = {user:'household/a', identity:'member-a', api:mock.api, autoLoad:true};
  h.render(panel, {...options, hidden:true}); await settle(); assert.equal(mock.requests.length, 0);
  assert.equal(panel.children.length, 0); h.render(panel, options); await settle(); assert.equal(mock.requests.length, 1);
});

test('food subcategories use verified native categories while pasta and rice remain explicit source searches', async () => {
  const h = harness(), panel = h.container(), mock = server();
  const options = {user:'household/a', identity:'member-a', api:mock.api, browseGroup:'food', autoLoad:true};
  h.render(panel, options); await settle();
  assert.equal(mock.requests[0].url.searchParams.get('category'), 'Main dish');
  assert.equal(mock.requests[0].url.searchParams.get('q'), '');
  assert.equal(button(panel, 'Platos principales').getAttribute('aria-pressed'), 'true');
  assert.equal(byClass(panel, 'myplate-categories')[0].hidden, false);
  for (const [label, category] of [['Desayunos','Breakfast'], ['Panes','Bread'], ['Acompañamientos','Side dish'], ['Ensaladas','Salad'], ['Sopas','Soup']]) {
    await button(panel, label).click();
    assert.equal(mock.requests.at(-1).url.searchParams.get('category'), category);
    assert.equal(mock.requests.at(-1).url.searchParams.get('q'), '');
    assert.equal(mock.requests.at(-1).url.searchParams.get('offset'), '0');
  }
  for (const [label, q] of [['Pastas','pasta'], ['Arroces','rice']]) {
    await button(panel, label).click();
    assert.equal(mock.requests.at(-1).url.searchParams.get('category'), '');
    assert.equal(mock.requests.at(-1).url.searchParams.get('q'), q);
    assert.equal(byClass(panel, 'myplate-filter-hint')[0].textContent, `“${q}”`);
  }
  await button(panel, 'Volver a platos principales').click();
  assert.equal(mock.requests.at(-1).url.searchParams.get('category'), 'Main dish');
  assert.equal(mock.requests.at(-1).url.searchParams.get('q'), '');
  assert.ok(mock.requests.every(call => call.url.pathname.endsWith('/myplate-recipes')));
});

test('dessert search, subcategories and clearing remain scoped to Dessert', async () => {
  const h = harness(), panel = h.container(), mock = server();
  h.render(panel, {user:'household/a', identity:'member-a', api:mock.api, browseGroup:'dessert', autoLoad:true}); await settle();
  assert.equal(mock.requests.length, 1); assert.equal(mock.requests[0].url.searchParams.get('category'), 'Dessert');
  await button(panel, 'Página siguiente').click(); assert.equal(mock.requests.at(-1).url.searchParams.get('offset'), '24');
  for (const [label, q] of [['Pasteles','cake'], ['Galletas','cookie'], ['Frutas','fruit']]) {
    await button(panel, label).click(); assert.equal(mock.requests.at(-1).url.searchParams.get('q'), q);
    assert.equal(mock.requests.at(-1).url.searchParams.get('offset'), '0');
  }
  all(panel, 'input')[0].value = 'chocolate'; await all(panel, 'form')[0].emit('submit');
  assert.equal(mock.requests.at(-1).url.searchParams.get('q'), 'chocolate');
  await button(panel, 'Ver todos los postres').click(); assert.equal(mock.requests.at(-1).url.searchParams.get('q'), '');
  assert.ok(mock.requests.every(call => call.url.searchParams.get('category') === 'Dessert'));
});

test('changing group cancels an in-flight list and ignores its late response without duplicate automatic loads', async () => {
  const pending = deferred(), h = harness(), panel = h.container();
  const mock = server({intercept:(call, number) => number === 1 ? pending.promise : undefined});
  const options = {user:'household/a', identity:'member-a', api:mock.api, autoLoad:true};
  h.render(panel, {...options, browseGroup:'all'}); await settle(); assert.equal(mock.requests.length, 1);
  h.render(panel, {...options, browseGroup:'dessert'}); h.render(panel, {...options, browseGroup:'dessert'}); await settle();
  assert.equal(mock.requests.length, 2); assert.equal(mock.requests[0].options.signal.aborted, true);
  assert.equal(mock.requests[1].url.searchParams.get('category'), 'Dessert'); assert.equal(h.activeElement, undefined);
  const visible = byClass(panel, 'myplate-grid')[0].textContent;
  pending.resolve({recipes:[], provider:'MyPlate.food', live:true, total:0, offset:0, limit:24, next_offset:null}); await settle();
  assert.equal(byClass(panel, 'myplate-grid')[0].textContent, visible); assert.equal(h.timers.size, 0);
});

test('changing group clears pending source detail and loads only the selected summary page', async () => {
  const pending = deferred(), h = harness(), panel = h.container();
  const mock = server({intercept:call => call.url.pathname.endsWith('/synthetic-000') ? pending.promise : undefined});
  const options = {user:'household/a', identity:'member-a', api:mock.api, autoLoad:true};
  h.render(panel, options); await settle(); await button(panel, 'Ver receta').click();
  assert.equal(mock.requests.length, 2);
  h.render(panel, {...options, browseGroup:'dessert'}); await settle();
  assert.equal(mock.requests[1].options.signal.aborted, true); assert.equal(mock.requests.length, 3);
  assert.equal(byClass(panel, 'myplate-detail')[0].hidden, true);
  pending.resolve({recipe:detail(rows[0])}); await settle(); assert.equal(byClass(panel, 'myplate-directions').length, 0);
  assert.equal(byClass(panel, 'myplate-recipe-card').length, 24);
});

test('group changes while inactive defer their single automatic query until activation', async () => {
  const h = harness(), panel = h.container(), mock = server();
  const options = {user:'household/a', identity:'member-a', api:mock.api, autoLoad:true};
  h.render(panel, options); await settle();
  h.render(panel, {...options, browseGroup:'food', active:false}); await settle(); assert.equal(mock.requests.length, 1);
  assert.equal(byClass(panel, 'myplate-recipe-card').length, 0);
  h.render(panel, {...options, browseGroup:'dessert', active:false}); await settle(); assert.equal(mock.requests.length, 1);
  h.setActive(panel, true); await settle(); assert.equal(mock.requests.length, 2);
  assert.equal(mock.requests[1].url.searchParams.get('category'), 'Dessert'); assert.equal(h.activeElement, undefined);
});

test('automatic request failure does not retry on rerender or visibility; explicit retry is required', async () => {
  const h = harness(), panel = h.container();
  const mock = server({intercept:(call, number) => number === 1 ? Promise.reject(Object.assign(new Error('quota'), {status:429})) : undefined});
  const options = {user:'household/a', identity:'member-a', api:mock.api, autoLoad:true};
  h.render(panel, options); await settle(); assert.equal(mock.requests.length, 1);
  h.render(panel, options); h.setActive(panel, false); h.setActive(panel, true); await h.visibility(true); await h.visibility(false);
  assert.equal(mock.requests.length, 1); assert.equal(button(panel, 'Reintentar consulta').hidden, false);
  await button(panel, 'Reintentar consulta').click(); assert.equal(mock.requests.length, 2);
});

test('changing identity with auto-load aborts the old response and requests only new-owner summaries', async () => {
  const pending = deferred(), h = harness(), panel = h.container();
  const mock = server({intercept:(call, number) => number === 1 ? pending.promise : undefined});
  const options = {user:'household/a', identity:'member-a', api:mock.api, autoLoad:true};
  h.render(panel, options); await settle();
  h.render(panel, {...options, user:'household/b', identity:'member-b'}); await settle();
  assert.equal(mock.requests.length, 2); assert.equal(mock.requests[0].options.signal.aborted, true);
  assert.equal(mock.requests[1].url.pathname, '/v1/home-food/household%2Fb/myplate-recipes');
  pending.resolve({recipes:[], provider:'MyPlate.food', live:true, total:0, offset:0, limit:24, next_offset:null}); await settle();
  assert.equal(byClass(panel, 'myplate-recipe-card').length, 24); assert.deepEqual(h.storageWrites, []);
});

test('a single pager follows the cards and preserves page bounds and source-only requests', async () => {
  const h = harness(), panel = h.container(), mock = server(); await start(h, panel, mock);
  const browser = byClass(panel, 'myplate-browser')[0], pagers = byClass(panel, 'myplate-pagination'), pager = pagers[0];
  assert.equal(pagers.length, 1); assert.ok(browser.children.indexOf(pager) > browser.children.indexOf(byClass(panel, 'myplate-grid')[0]));
  assert.equal(pager.hidden, false); assert.equal(button(pager, 'Página anterior').disabled, true); assert.equal(button(pager, 'Página siguiente').disabled, false);
  assert.ok(pagers.every(pager => all(pager, 'span')[0].textContent === 'Página 1 de 3'));
  await button(pager, 'Página siguiente').click(); assert.equal(mock.requests.at(-1).url.searchParams.get('offset'), '24');
  assert.ok(pagers.every(pager => all(pager, 'span')[0].textContent === 'Página 2 de 3'));
  await button(panel, 'Página siguiente').click(); assert.ok(pagers.every(pager => all(pager, 'span')[0].textContent === 'Página 3 de 3'));
  assert.equal(button(panel, 'Página siguiente').disabled, true);
  await button(pager, 'Página anterior').click(); assert.equal(mock.requests.at(-1).url.searchParams.get('offset'), '24');
  assert.equal(button(panel, 'Página siguiente').disabled, false); assert.ok(mock.requests.every(call => call.url.pathname.endsWith('/myplate-recipes')));
});

test('pager is disabled while a page request is in flight', async () => {
  const pending = deferred(), h = harness(), panel = h.container(), mock = server({intercept:(call, n) => n === 2 ? pending.promise : undefined});
  await start(h, panel, mock); await button(panel, 'Página siguiente').click();
  for (const control of [button(panel, 'Página anterior'), button(panel, 'Página siguiente')]) assert.equal(control.disabled, true);
  await button(panel, 'Página siguiente').click(); assert.equal(mock.requests.length, 2);
  pending.resolve({recipes:rows.slice(24,48), total:51, offset:24, limit:24, next_offset:48, provider:'MyPlate.food', live:true}); await settle();
  assert.equal(button(panel, 'Página anterior').disabled, false); assert.equal(button(panel, 'Página siguiente').disabled, false);
});

for (const size of [0,1,24]) test(`pager stays hidden for a single page or no rows (${size})`, async () => {
  const h = harness(), panel = h.container(), mock = server({items:rows.slice(0,size)}); await start(h, panel, mock);
  assert.ok(byClass(panel, 'myplate-pagination').every(pager => pager.hidden));
});

test('pager retains search and category scope and resets on clear', async () => {
  const h = harness(), panel = h.container(), mock = server(); await start(h, panel, mock);
  await button(byClass(panel, 'myplate-categories')[0], 'Postres').click();
  const input = all(panel, 'input')[0]; input.value = 'Synthetic'; await all(panel, 'form')[0].emit('submit');
  await button(panel, 'Página siguiente').click();
  const query = mock.requests.at(-1).url.searchParams; assert.equal(query.get('category'), 'Dessert'); assert.equal(query.get('q'), 'Synthetic'); assert.equal(query.get('offset'), '24');
  await button(panel, 'Ver todas').click(); assert.ok(byClass(panel, 'myplate-pagination').every(pager => all(pager, 'span')[0].textContent === 'Página 1 de 3'));
});

test('pager cannot issue a stale request after the collection is inactive', async () => {
  const h = harness(), panel = h.container(), mock = server(); await start(h, panel, mock); const next = button(panel, 'Página siguiente');
  h.setActive(panel, false); await next.click(); assert.equal(mock.requests.length, 1);
});

test('guide mounts only on explicit request with intact English source steps, notes and ingredients', async () => {
  const sourceSteps = ['Synthetic step A: keep 1.5 and 1/2 exactly.\n', 'Synthetic step B: preserve this full paragraph.\n', 'Final synthetic test line.'];
  const h = harness({guide:true}), panel = h.container(), mock = server({items:rows.slice(0,1), detailMutation:{source_steps:sourceSteps, source_steps_language:'en'}});
  await start(h, panel, mock); assert.equal(h.guideMounts.length, 0); await button(panel, 'Ver receta').click(); assert.equal(h.guideMounts.length, 0);
  const original = byClass(panel, 'myplate-directions')[0], opener = button(panel, 'Paso a paso con Roxy'); assert.ok(opener); assert.equal(original.parentNode.hidden, false);
  await opener.click(); const call = h.guideMounts[0]; assert.equal(h.guideMounts.length, 1); assert.equal(call.options.title, rows[0].title);
  assert.deepEqual(Array.from(call.options.steps), sourceSteps); assert.equal(call.options.steps.join(''), detail(rows[0]).directions); assert.equal(call.options.language, 'en');
  assert.deepEqual(Array.from(call.options.ingredients), ['1/2 cup synthetic A (Test note, not an instruction)', '1.5 tablespoons synthetic B']);
  assert.match(call.options.sourceLabel, /MyPlate.food.*inglés/); assert.equal(call.options.isCurrent(), true); assert.equal(call.host.isConnected, true);
  assert.equal(original.parentNode.hidden, true); assert.equal(opener.hidden, true); assert.equal(mock.requests.length, 2); assert.deepEqual(h.storageWrites, []);
});

const invalidSourceSteps = [
  {label:'missing field', fields:{}},
  {label:'empty array', fields:{source_steps:[], source_steps_language:'en'}},
  {label:'not an array', fields:{source_steps:'Synthetic step', source_steps_language:'en'}},
  {label:'blank step', fields:{source_steps:[''], source_steps_language:'en'}},
  {label:'non-string step', fields:{source_steps:[null], source_steps_language:'en'}},
  {label:'unconfirmed language', fields:{source_steps:[detail(rows[0]).directions], source_steps_language:'es'}},
  {label:'truncated source', fields:{source_steps:['Synthetic step A: keep 1.5 and 1/2 exactly.'], source_steps_language:'en'}},
  {label:'different whitespace', fields:{source_steps:detail(rows[0]).directions.split('\n'), source_steps_language:'en'}},
  {label:'fabricated extra step', fields:{source_steps:[detail(rows[0]).directions, 'Invented extra instruction.'], source_steps_language:'en'}},
];
for (const {label, fields} of invalidSourceSteps) test(`guide falls back to the full source paragraph when steps are invalid: ${label}`, async () => {
  const h = harness({guide:true}), panel = h.container(), mock = server({items:rows.slice(0,1), detailMutation:fields}); await start(h, panel, mock); await button(panel, 'Ver receta').click();
  await button(panel, 'Paso a paso con Roxy').click(); assert.deepEqual(Array.from(h.guideMounts[0].options.steps), [detail(rows[0]).directions]);
  assert.equal(h.guideMounts[0].options.language, 'en'); assert.equal(byClass(panel, 'myplate-directions')[0].textContent, detail(rows[0]).directions);
});

test('guide unavailable leaves the complete source readable without a broken start action', async () => {
  const h = harness(), panel = h.container(), mock = server({items:rows.slice(0,1)}); await start(h, panel, mock); await button(panel, 'Ver receta').click();
  assert.equal(button(panel, 'Paso a paso con Roxy'), undefined); assert.equal(byClass(panel, 'myplate-directions')[0].textContent, detail(rows[0]).directions); assert.equal(byClass(panel, 'myplate-directions')[0].parentNode.hidden, false);
});

test('guide close restores original instructions and focus without refetching or changing catalog page', async () => {
  const h = harness({guide:true}), panel = h.container(), mock = server(); await start(h, panel, mock); await button(panel, 'Página siguiente').click(); await button(panel, 'Ver receta').click();
  const opener = button(panel, 'Paso a paso con Roxy'); await opener.click(); const call = h.guideMounts[0]; call.controller.dispose(); call.options.onClose();
  assert.equal(opener.hidden, false); assert.equal(byClass(panel, 'myplate-directions')[0].parentNode.hidden, false); assert.equal(h.activeElement, opener); assert.equal(mock.requests.length, 3);
  await button(panel, 'Volver a las recetas').click(); assert.equal(mock.requests.length, 3); assert.ok(byClass(panel, 'myplate-pagination').every(pager => all(pager, 'span')[0].textContent === 'Página 2 de 3'));
});

for (const exit of ['inactive', 'hidden', 'identity', 'document', 'group', 'back']) test(`active source guide is disposed and its scope becomes stale on ${exit}`, async () => {
  const h = harness({guide:true}), panel = h.container(), mock = server({items:rows.slice(0,1)}); await start(h, panel, mock); await button(panel, 'Ver receta').click(); await button(panel, 'Paso a paso con Roxy').click(); const call = h.guideMounts[0];
  if (exit === 'inactive') h.setActive(panel, false);
  if (exit === 'hidden') h.render(panel, {user:'household/a', identity:'member-a', api:mock.api, hidden:true});
  if (exit === 'identity') h.render(panel, {user:'household/b', identity:'member-b', api:mock.api});
  if (exit === 'document') await h.visibility(true);
  if (exit === 'group') { h.render(panel, {user:'household/a', identity:'member-a', api:mock.api, browseGroup:'food'}); await settle(); }
  if (exit === 'back') await button(panel, 'Volver a las recetas').click();
  assert.equal(call.disposals, 1); assert.equal(call.options.isCurrent(), false); assert.equal(call.host.isConnected, false); assert.deepEqual(h.storageWrites, []);
});

test('source guide current callback respects outer identity revocation before a rerender', async () => {
  let current = true; const h = harness({guide:true}), panel = h.container(), mock = server({items:rows.slice(0,1)}); await start(h, panel, mock, {isCurrent:() => current});
  await button(panel, 'Ver receta').click(); await button(panel, 'Paso a paso con Roxy').click(); current = false; assert.equal(h.guideMounts[0].options.isCurrent(), false);
});

test('source guide current callback rejects a hidden ancestor even before parent rerender', async () => {
  const h = harness({guide:true}), outer = h.container(), panel = h.container(), mock = server({items:rows.slice(0,1)}); outer.append(panel); await start(h, panel, mock);
  await button(panel, 'Ver receta').click(); await button(panel, 'Paso a paso con Roxy').click(); outer.hidden = true;
  assert.equal(h.guideMounts[0].options.isCurrent(), false);
});

test('a stale guide close callback cannot clear or focus over the newly mounted guide', async () => {
  const h = harness({guide:true}), panel = h.container(), mock = server({items:rows.slice(0,2)}); await start(h, panel, mock);
  await button(panel, 'Ver receta').click(); await button(panel, 'Paso a paso con Roxy').click(); const first = h.guideMounts[0];
  await button(panel, 'Volver a las recetas').click(); await button(panel, 'Ver receta').click(); const nextOpener = button(panel, 'Paso a paso con Roxy'); await nextOpener.click(); const second = h.guideMounts[1], focused = h.activeElement;
  first.options.onClose(); assert.equal(h.activeElement, focused); assert.equal(nextOpener.hidden, true);
  await button(panel, 'Volver a las recetas').click(); assert.equal(second.disposals, 1);
});

const personalOptions = (mock, extra = {}) => ({
  user:'household/a', identity:'member-a', api:mock.api, browseGroup:'personal', personalRevision:1, autoLoad:true,
  preset:{id:'synthetic-tastes', label:'Sabores que elegiste', query:'Synthetic', category:'Dessert'}, ...extra,
});

test('personal selection forwards only the exact source query and category and retains them through pagination', async () => {
  const h = harness(), panel = h.container(), mock = server(), options = personalOptions(mock);
  h.render(panel, options); await settle();
  assert.equal(mock.requests.length, 1); assert.equal(all(panel,'input')[0].value, 'Synthetic');
  assert.equal(all(panel,'h2')[0].textContent, options.preset.label);
  assert.equal(mock.requests[0].url.searchParams.get('q'), 'Synthetic');
  assert.equal(mock.requests[0].url.searchParams.get('category'), 'Dessert');
  assert.equal(mock.requests[0].url.searchParams.get('offset'), '0');
  assert.equal(byClass(panel,'myplate-recipe-card').length, 24);
  assert.match(byClass(panel,'myplate-filter-hint')[0].textContent, /Synthetic.*Postres/);
  await button(panel,'Página siguiente').click();
  assert.equal(mock.requests.at(-1).url.searchParams.get('q'), 'Synthetic');
  assert.equal(mock.requests.at(-1).url.searchParams.get('category'), 'Dessert');
  assert.equal(mock.requests.at(-1).url.searchParams.get('offset'), '24');
  assert.ok(mock.requests.every(call => [...call.url.searchParams.keys()].sort().join(',') === 'category,limit,offset,q,requested'));
  assert.deepEqual(h.storageWrites, []);
});

test('personal selection remains explicit unless autoLoad is enabled and waits for a visible current scope', async () => {
  const h = harness(), panel = h.container(), mock = server(), options = personalOptions(mock,{autoLoad:false});
  h.render(panel, options); await h.tick(60000); assert.equal(mock.requests.length, 0);
  await button(panel,'Explorar recetas').click(); assert.equal(mock.requests.length, 1);
  h.render(panel, personalOptions(mock,{personalRevision:2,active:false})); await settle(); assert.equal(mock.requests.length, 1);
  h.setActive(panel,true); await settle(); assert.equal(mock.requests.length, 2);
  assert.equal(mock.requests.at(-1).url.searchParams.get('category'), 'Dessert');
});

test('identical personalized renders do not reset a user search, refetch, or close an open guide', async () => {
  const h = harness({guide:true}), panel = h.container(), mock = server(), options = personalOptions(mock);
  h.render(panel, options); await settle(); all(panel,'input')[0].value = 'source 0'; await all(panel,'form')[0].emit('submit');
  await button(panel,'Ver receta').click(); await button(panel,'Paso a paso con Roxy').click(); const call = h.guideMounts[0], count = mock.requests.length;
  h.render(panel,{...options,preset:{...options.preset}}); await settle();
  assert.equal(mock.requests.length,count); assert.equal(all(panel,'input')[0].value,'source 0');
  assert.equal(call.disposals,0); assert.equal(call.options.isCurrent(),true);
});

test('clearing a personal selection restores the full catalogue and does not silently reapply it on rerender', async () => {
  const h = harness(), panel = h.container(), mock = server(), options = personalOptions(mock);
  h.render(panel,options); await settle(); await button(panel,'Ver todas').click();
  assert.equal(mock.requests.at(-1).url.searchParams.get('q'),'');assert.equal(mock.requests.at(-1).url.searchParams.get('category'),'');
  h.render(panel,options);await settle();assert.equal(mock.requests.length,2);assert.equal(all(panel,'input')[0].value,'');
  assert.match(byClass(panel,'myplate-total')[0].textContent,/51 recetas · originales en inglés/);
});

for (const change of ['revision','member','preset-id','query','category','leave-personal']) test(`personal ${change} invalidates open source details and guide callbacks`,async()=>{
  const h=harness({guide:true}),panel=h.container(),mock=server(),options=personalOptions(mock);
  h.render(panel,options);await settle();await button(panel,'Ver receta').click();await button(panel,'Paso a paso con Roxy').click();
  const old=h.guideMounts[0],oldOpen=button(panel,'Paso a paso con Roxy');
  const next={...options,preset:{...options.preset}};
  if(change==='revision')next.personalRevision=2;
  if(change==='member')next.identity='member-b';
  if(change==='preset-id')next.preset.id='another-selection';
  if(change==='query')next.preset.query='source 4';
  if(change==='category')next.preset.category='Beverage';
  if(change==='leave-personal')next.browseGroup='all';
  h.render(panel,next);await settle();
  assert.equal(old.disposals,1);assert.equal(old.options.isCurrent(),false);assert.equal(old.host.isConnected,false);
  assert.equal(byClass(panel,'myplate-directions').length,0);assert.equal(byClass(panel,'myplate-detail')[0].hidden,true);
  const focused=h.activeElement;old.options.onClose();await oldOpen.click();assert.equal(h.activeElement,focused);assert.equal(h.guideMounts.length,1);
  assert.equal(mock.requests.length,3);assert.equal(mock.requests.at(-1).url.searchParams.get('offset'),'0');assert.deepEqual(h.storageWrites,[]);
});

for (const change of ['revision','member','query']) test(`late personal detail is aborted and ignored after ${change} changes`,async()=>{
  const pending=deferred(),h=harness({guide:true}),panel=h.container();
  const mock=server({intercept:call=>call.url.pathname.endsWith('/synthetic-000')?pending.promise:undefined}),options=personalOptions(mock);
  h.render(panel,options);await settle();await button(panel,'Ver receta').click();const old=mock.requests[1];
  const next={...options,preset:{...options.preset}};
  if(change==='revision')next.personalRevision=2;if(change==='member')next.identity='member-b';if(change==='query')next.preset.query='source 4';
  h.render(panel,next);await settle();assert.equal(old.options.signal.aborted,true);assert.equal(mock.requests.length,3);
  const visible=byClass(panel,'myplate-grid')[0].textContent;
  pending.resolve({recipe:{...detail(rows[0]),personal_fit:{status:'unrestricted',conflicts:[],caution:'Late profile A'}}});await settle();
  assert.equal(byClass(panel,'myplate-grid')[0].textContent,visible);assert.equal(byClass(panel,'myplate-directions').length,0);
  assert.equal(panel.textContent.includes('Late profile A'),false);assert.equal(h.guideMounts.length,0);assert.equal(h.timers.size,0);
});

test('late personal list cannot replace a newer profile selection even when the transport ignores abort',async()=>{
  const pending=deferred(),h=harness(),panel=h.container(),mock=server({intercept:(call,n)=>n===1?pending.promise:undefined});
  const options=personalOptions(mock);h.render(panel,options);await settle();
  h.render(panel,{...options,personalRevision:2,preset:{id:'new',label:'Tu nueva selección',query:'source 4',category:'Dessert'}});await settle();
  assert.equal(mock.requests[0].options.signal.aborted,true);assert.equal(mock.requests.length,2);
  const visible=byClass(panel,'myplate-grid')[0].textContent;
  pending.resolve({recipes:rows.slice(0,24),provider:'MyPlate.food',live:true,total:51,offset:0,limit:24,next_offset:24});await settle();
  assert.equal(byClass(panel,'myplate-grid')[0].textContent,visible);assert.equal(all(panel,'h2')[0].textContent,'Tu nueva selección');assert.equal(h.timers.size,0);
});

test('a personal conflict shows exact reasons, keeps source readable and disables starting the Roxy guide',async()=>{
  const fit={status:'conflict',conflicts:['Contiene leche según tu respuesta.','Incluye un ingrediente que prefieres evitar.'],caution:'Revisa siempre etiquetas y contaminación cruzada.'};
  const h=harness({guide:true}),panel=h.container(),mock=server({items:rows.slice(0,1),detailMutation:{personal_fit:fit}});
  h.render(panel,personalOptions(mock));await settle();await button(panel,'Ver receta').click();
  const assessment=byClass(panel,'myplate-personal-fit')[0];assert.equal(assessment.getAttribute('role'),'status');
  for(const value of [...fit.conflicts,fit.caution])assert.ok(assessment.textContent.includes(value));
  assert.match(assessment.textContent,/entra en conflicto/);const blocked=button(panel,'Busca otra receta compatible');assert.equal(blocked.disabled,true);
  await blocked.click();assert.equal(h.guideMounts.length,0);assert.equal(button(panel,'Paso a paso con Roxy'),undefined);
  assert.equal(byClass(panel,'myplate-directions')[0].textContent,detail(rows[0]).directions);assert.equal(byClass(panel,'myplate-directions')[0].parentNode.hidden,false);
  assert.equal(mock.requests.length,2);assert.deepEqual(h.storageWrites,[]);
});

for(const status of ['needs_review','unrestricted'])test(`personal ${status} allows deliberate source guidance and retains the caution outside the hidden source body`,async()=>{
  const fit={status,conflicts:[],caution:'La ausencia de coincidencias no certifica que esta receta sea apta.'};
  const h=harness({guide:true}),panel=h.container(),mock=server({items:rows.slice(0,1),detailMutation:{personal_fit:fit}});
  h.render(panel,personalOptions(mock));await settle();await button(panel,'Ver receta').click();
  const assessment=byClass(panel,'myplate-personal-fit')[0],opener=button(panel,'Paso a paso con Roxy');
  assert.ok(opener);assert.notEqual(opener.disabled,true);assert.equal(h.guideMounts.length,0);assert.match(assessment.textContent,/Antes de cocinar/);
  await opener.click();assert.equal(h.guideMounts.length,1);assert.equal(h.guideMounts[0].options.language,'en');
  assert.equal(assessment.hidden,false);assert.equal(assessment.parentNode.hidden,false);assert.equal(byClass(panel,'myplate-directions')[0].parentNode.hidden,true);
  assert.ok(assessment.textContent.includes(fit.caution));assert.equal(mock.requests.length,2);assert.deepEqual(h.storageWrites,[]);
});

test('personal fit text is displayed literally without interpreting markup or nonstring conflicts',async()=>{
  const fit={status:'conflict',conflicts:['<script>synthetic</script>',null,{message:'not source text'}],caution:'<img src=x onerror=synthetic>'};
  const h=harness({guide:true}),panel=h.container(),mock=server({items:rows.slice(0,1),detailMutation:{personal_fit:fit}});
  h.render(panel,personalOptions(mock));await settle();await button(panel,'Ver receta').click();
  const assessment=byClass(panel,'myplate-personal-fit')[0];assert.ok(assessment.textContent.includes(fit.conflicts[0]));assert.ok(assessment.textContent.includes(fit.caution));
  assert.equal(all(assessment,'script').length,0);assert.equal(all(assessment,'img').length,0);assert.equal(assessment.textContent.includes('[object Object]'),false);
});

const filteredPage = (items, {offset=0,total=51,hidden=24-items.length,next=offset+24<total?offset+24:null,notice='Cribado orientativo de esta página; revisa los ingredientes completos.'}={}) => ({
  recipes:structuredClone(items),provider:'MyPlate.food',live:true,total,offset,limit:24,next_offset:next,
  hidden_in_page:hidden,personal_notice:notice,
});

test('a screened page separates source total from visible rows and does not fetch hidden details',async()=>{
  const visible=rows.slice(0,12),notice='Cribado sintético: los resultados visibles todavía necesitan revisión.';
  const h=harness(),panel=h.container(),mock=server({intercept:(_call,n)=>n===1?filteredPage(visible,{hidden:12,notice}):undefined});
  h.render(panel,personalOptions(mock,{preset:{id:'all-food',label:'Tus sabores',query:'Synthetic',category:''}}));await settle();
  assert.equal(byClass(panel,'myplate-recipe-card').length,12);assert.equal(byClass(panel,'myplate-total')[0].textContent,'51 coincidencias en la fuente · originales en inglés');
  assert.match(byClass(panel,'myplate-status')[0].textContent,/12 recetas ocultas/);
  assert.ok(all(panel,'p').some(node=>node.textContent===notice&&!node.hidden));assert.equal(mock.requests.length,1);
  assert.ok(byClass(panel,'myplate-pagination').every(pager=>!pager.hidden));
  await button(panel,'Página siguiente').click();assert.equal(mock.requests[1].url.searchParams.get('offset'),'24');
  assert.equal(byClass(panel,'myplate-recipe-card').length,24);assert.ok(mock.requests.every(call=>call.url.pathname.endsWith('/myplate-recipes')));
  assert.equal(all(panel,'p').some(node=>node.textContent===notice&&!node.hidden),false,'A notice from the previous response must not survive an unfiltered response');
});

test('a fully screened first page still exposes next control and can reach the next source page',async()=>{
  const h=harness(),panel=h.container(),mock=server({intercept:(_call,n)=>n===1?filteredPage([],{hidden:24}):undefined});
  h.render(panel,personalOptions(mock,{preset:{id:'all-food',label:'Tus sabores',query:'Synthetic',category:''}}));await settle();
  assert.equal(byClass(panel,'myplate-recipe-card').length,0);assert.equal(byClass(panel,'myplate-total')[0].textContent,'51 coincidencias en la fuente · originales en inglés');
  assert.match(byClass(panel,'myplate-status')[0].textContent,/24 recetas ocultas.*página siguiente/);
  assert.equal(byClass(panel,'myplate-pagination')[0].hidden,false);assert.equal(button(panel,'Página siguiente').disabled,false);
  assert.equal(button(panel,'Página anterior').disabled,true);assert.ok(byClass(panel,'myplate-pagination').every(pager=>all(pager,'span')[0].textContent==='Página 1 de 3'));
  await button(panel,'Página siguiente').click();assert.equal(mock.requests[1].url.searchParams.get('offset'),'24');assert.equal(byClass(panel,'myplate-recipe-card').length,24);
  assert.ok(byClass(panel,'myplate-pagination').every(pager=>all(pager,'span')[0].textContent==='Página 2 de 3'));assert.deepEqual(h.storageWrites,[]);
});

test('a fully screened final page keeps previous navigation without inventing another page or a zero source total',async()=>{
  const h=harness(),panel=h.container(),mock=server({intercept:(_call,n)=>n===3?filteredPage([],{offset:48,total:51,hidden:3,next:null}):undefined});
  h.render(panel,personalOptions(mock,{preset:{id:'all-food',label:'Tus sabores',query:'Synthetic',category:''}}));await settle();
  await button(panel,'Página siguiente').click();await button(panel,'Página siguiente').click();
  assert.equal(byClass(panel,'myplate-recipe-card').length,0);assert.equal(byClass(panel,'myplate-total')[0].textContent,'51 coincidencias en la fuente · originales en inglés');
  assert.match(byClass(panel,'myplate-status')[0].textContent,/3 recetas ocultas.*otra selección/);
  assert.ok(byClass(panel,'myplate-pagination').every(pager=>!pager.hidden&&all(pager,'span')[0].textContent==='Página 3 de 3'));
  assert.equal(button(panel,'Página siguiente').disabled,true);assert.equal(button(panel,'Página anterior').disabled,false);
  await button(panel,'Página anterior').click();assert.equal(mock.requests.at(-1).url.searchParams.get('offset'),'24');assert.equal(byClass(panel,'myplate-recipe-card').length,24);
});

test('zero screened exclusions still disclose that the total counts source matches, without a compatibility claim',async()=>{
  const h=harness(),panel=h.container(),mock=server({intercept:()=>filteredPage(rows.slice(0,24),{hidden:0})});
  h.render(panel,personalOptions(mock));await settle();assert.equal(byClass(panel,'myplate-total')[0].textContent,'51 coincidencias en la fuente · originales en inglés');
  assert.equal(byClass(panel,'myplate-recipe-card').length,24);assert.ok(panel.textContent.includes('revisa los ingredientes completos'));
  assert.equal(byClass(panel,'myplate-status')[0].textContent.includes('compatibles'),false);
});

for(const hidden of [-1,25,true,'1',1.5])test(`invalid screened count fails closed before showing cards: ${JSON.stringify(hidden)}`,async()=>{
  const h=harness(),panel=h.container(),mock=server({intercept:()=>filteredPage([],{hidden})});
  h.render(panel,personalOptions(mock));await settle();assert.equal(byClass(panel,'myplate-recipe-card').length,0);
  assert.equal(button(panel,'Reintentar consulta').hidden,false);assert.ok(byClass(panel,'myplate-pagination').every(pager=>pager.hidden));
});

test('screened plus visible rows cannot exceed the source page size',async()=>{
  const h=harness(),panel=h.container(),mock=server({intercept:()=>filteredPage(rows.slice(0,24),{hidden:1})});
  h.render(panel,personalOptions(mock));await settle();assert.equal(byClass(panel,'myplate-recipe-card').length,0);assert.equal(button(panel,'Reintentar consulta').hidden,false);
});

test('food card preparation opens the voice guide directly and binds the authoritative recipe version', async () => {
  const h=harness({guide:true}), panel=h.container(), spoken=[], version='b'.repeat(64);
  const mock=server({intercept:call => call.url.pathname.endsWith('/synthetic-000') ? {recipe:detail(rows[0]),companion_version:version} : undefined});
  await start(h,panel,mock,{speech:params=>{spoken.push(params);}});
  await button(panel,'Ver receta').click(); assert.equal(h.guideMounts.length,0); assert.equal(spoken.length,0);
  await button(panel,'Volver a las recetas').click(); await button(panel,'Preparar con Roxy').click();
  assert.equal(h.guideMounts.length,1); const opts=h.guideMounts[0].options;
  assert.equal(opts.startWithVoice,true); const controller=new AbortController();
  await opts.requestSpeech({kind:'step',text:'',step_index:0,language:'en',signal:controller.signal});
  assert.equal(spoken[0].recipe_version,version); assert.equal(spoken[0].source,'myplate');
  assert.equal(spoken[0].recipe_id,rows[0].slug); assert.equal(spoken[0].signal,controller.signal);
  assert.deepEqual(h.storageWrites,[]);
});

test('Spanish reading is requested once, preserves position across original toggle and binds voice to the signed translation',async()=>{
  const h=harness({guide:true}),panel=h.container(),calls=[],spoken=[],version='d'.repeat(64);
  const mock=server({intercept:call=>call.url.pathname.endsWith('/synthetic-000')?{recipe:detail(rows[0]),companion_version:version}:undefined});
  const translation={title:'Ficha sintética en español',ingredients:['1/2 taza sintética A','1.5 cucharadas sintéticas B'],steps:['Paso sintético completo en español.']};
  await start(h,panel,mock,{translate:params=>{calls.push(params);return{translation,translation_token:'signed-test-only'};},speech:params=>spoken.push(params)});
  await button(panel,'Preparar con Roxy').click();assert.equal(calls.length,1);assert.equal(calls[0].language,'en');assert.equal(calls[0].recipe_version,version);
  let opts=h.guideMounts.at(-1).options;assert.equal(opts.language,'es');assert.equal(opts.title,translation.title);
  await opts.requestSpeech({language:'es',step_index:0,kind:'step',text:''});assert.equal(spoken[0].translation_token,'signed-test-only');
  assert.equal(byClass(panel,'myplate-directions')[0].textContent,translation.steps[0]);
  await button(panel,'Ver original en inglés').click();opts=h.guideMounts.at(-1).options;assert.equal(opts.language,'en');
  assert.equal(byClass(panel,'myplate-directions')[0].textContent,detail(rows[0]).directions);
  await button(panel,'Volver al español').click();assert.equal(h.guideMounts.at(-1).options.language,'es');assert.equal(calls.length,1);assert.deepEqual(h.storageWrites,[]);
});

test('closing a pending translation cancels it and does not start a late spoken guide',async()=>{
  const h=harness({guide:true}),panel=h.container(),pending=deferred(),calls=[];
  const mock=server({intercept:call=>call.url.pathname.endsWith('/synthetic-000')?{recipe:detail(rows[0]),companion_version:'e'.repeat(64)}:undefined});
  await start(h,panel,mock,{translate:params=>{calls.push(params);return pending.promise;}});
  await button(panel,'Preparar con Roxy').click();assert.equal(h.guideMounts.length,0);
  await button(panel,'Volver a las recetas').click();assert.equal(calls[0].signal.aborted,true);
  pending.resolve({translation:{title:'Late',ingredients:['a','b'],steps:['late']},translation_token:'late'});await settle();assert.equal(h.guideMounts.length,0);assert.doesNotMatch(panel.textContent,/Late/);
});
