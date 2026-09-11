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

function harness() {
  const timers = new Map(), documentListeners = {}, storageWrites = [];
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
    replaceChildren(...elements) { this.children.forEach(el => { el.parent = null; }); this.children = []; this._text = ''; this.append(...elements); }
    remove() { if (this.parent) { this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null; } }
    contains(el) { return this === el || this.children.some(child => child.contains(el)); }
    setAttribute(name, value) { this[name] = String(value); }
    getAttribute(name) { return this[name] ?? null; }
    removeAttribute(name) { delete this[name]; }
    addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
    removeEventListener(name, callback) { this.listeners[name] = (this.listeners[name] || []).filter(el => el !== callback); }
    async emit(name) { for (const fn of [...(this.listeners[name] || [])]) fn({target:this, currentTarget:this, preventDefault() {}}); await settle(); }
    click() { return this.disabled ? Promise.resolve() : this.emit('click'); }
    focus() { activeElement = this; }
    scrollIntoView() {}
    querySelectorAll(selector) { return selector.startsWith('.') ? byClass(this, selector.slice(1)) : all(this, selector); }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    get classList() { return {add: name => { this.className += ` ${name}`; }, remove: name => { this.className = this.className.split(/\s+/).filter(value => value !== name).join(' '); }, contains: name => this.className.split(/\s+/).includes(name)}; }
  }
  const document = {hidden:false, createElement:tag => new Element(tag), body:new Element('body'),
    addEventListener(name, fn) { (documentListeners[name] ||= []).push(fn); },
    removeEventListener(name, fn) { documentListeners[name] = (documentListeners[name] || []).filter(value => value !== fn); }};
  document.body.root = true;
  const forbidden = action => { storageWrites.push(action); throw new Error(`Forbidden external/storage operation: ${action}`); };
  const sandbox = {window:{}, document, URL, URLSearchParams, AbortController,
    setTimeout(fn, delay = 0) { const id = ++timerId; timers.set(id, {fn, due:now + delay}); return id; }, clearTimeout(id) { timers.delete(id); },
    fetch() { return forbidden('browser fetch'); }, localStorage:{setItem() { forbidden('localStorage'); }, getItem() { forbidden('localStorage read'); }},
    sessionStorage:{setItem() { forbidden('sessionStorage'); }, getItem() { forbidden('sessionStorage read'); }}, indexedDB:{open() { forbidden('indexedDB'); }}};
  vm.runInNewContext(code, sandbox);
  const container = () => { const el = new Element('div'); document.body.append(el); return el; };
  const tick = async duration => { const until = now + duration;
    for (;;) { const item = [...timers].filter(([, value]) => value.due <= until).sort((a,b) => a[1].due - b[1].due)[0]; if (!item) break;
      const [id, value] = item; timers.delete(id); now = value.due; value.fn(); await settle(); }
    now = until; await settle(); };
  const visibility = async hidden => { document.hidden = hidden; for (const fn of [...(documentListeners.visibilitychange || [])]) fn(); await settle(); };
  return {...sandbox.window.RoxyMyPlateRecipes, container, tick, visibility, storageWrites,
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
        category_options:['Main dish', 'Dessert', 'Beverage', 'Salad', 'Soup'], source:'Synthetic original source', provider:'MyPlate.food', live:true, audience:'human'};
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
