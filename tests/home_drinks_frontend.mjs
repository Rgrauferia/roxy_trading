import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

// Synthetic contracts only. These fixtures are not beverage recipes or editorial evidence.
const code = fs.readFileSync(new URL('../assets/roxy_home_drinks.js', import.meta.url), 'utf8');
const revision = 'f446f0e9356b9b43155d207b4f7c5214d9da91ab';
const categories = ['coffee_tea', 'juice', 'smoothie', 'mocktail', 'cocktail'];
const bases = ['gin', 'vodka', 'rum', 'agave', 'whisky', 'wine', 'other'];
const rows = Array.from({length:60}, (_, index) => ({id:`synthetic-${index}`, title:`Synthetic drink ${index}`, title_es:`Bebida sintética ${index}`,
  category:categories[index % 5], alcoholic:index % 5 === 4,
  spirit_bases:index % 5 === 4 ? [bases[Math.floor(index / 5) % bases.length]] : [],
  image_url:`https://raw.githubusercontent.com/alfg/opendrinks/${revision}/src/assets/recipes/synthetic-${index}.jpg`,
  image_credit:'Synthetic photographer', ingredients:['1/2 cup synthetic A', '1.5 oz synthetic B'], steps:['Synthetic exact first step.', 'Synthetic exact second step.'],
  ingredients_es:['1/2 taza de A sintético', '1.5 oz de B sintético'], steps_es:['Primer paso sintético exacto.', 'Segundo paso sintético exacto.'],
  source_url:`https://github.com/alfg/opendrinks/blob/${revision}/src/recipes/synthetic-${index}.json`, contributor:'Synthetic author', notes_es:['Nota sintética.'], source_sha256:'a'.repeat(64)}));
// Actual manifest rows do not store server-derived base metadata. This fixture
// only supplies an explicit synthetic bucket; server classifier tests are separate.
const withBases = row => Object.hasOwn(row, 'spirit_bases') ? row : {...row, spirit_bases:row.alcoholic ? ['other'] : []};
const summaries = drinks => drinks.map(withBases).map(row => ({...Object.fromEntries(['id','title','title_es','category','alcoholic','image_url','source_sha256','spirit_bases'].map(key => [key,row[key]])),
  ingredient_count:row.ingredients.length, step_count:row.steps.length}));
const fixtureBodies = new WeakMap();
const payload = (drinks = rows) => {
  const value = {drinks:summaries(drinks), total:drinks.length, counts:Object.fromEntries(categories.map(key => [key, drinks.filter(row => row.category === key).length])),
    source:{name:'Open Drinks', revision, license:'MIT', license_url:'/assets/open-drinks-license.txt'}};
  fixtureBodies.set(value, structuredClone(drinks)); return value;
};
const fullResponse = row => ({drink:structuredClone(Object.fromEntries(Object.entries(withBases(row)).filter(([key]) => key !== 'raw_source'))),
  source:{name:'Open Drinks', revision, license:'MIT', license_url:'/assets/open-drinks-license.txt'}, audience:'human', can_scale:false, can_add_to_shopping:false});
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => { resolve = a; reject = b; }); return {promise, resolve, reject}; };
const settle = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
const descendants = el => el.children.flatMap(child => [child, ...descendants(child)]);
const all = (el, tag) => descendants(el).filter(child => child.tagName === tag.toUpperCase());
const byClass = (el, name) => descendants(el).filter(child => String(child.className || '').split(/\s+/).includes(name));
const button = (el, text) => all(el, 'button').find(child => child.textContent === text);
const category = (el, key) => byClass(el, 'drinks-categories')[0].children[categories.indexOf(key) + 1];
function harness({voice = true} = {}) {
  let activeElement, now = 0, timerId = 0; const timers = new Map(), listeners = {}, speechCalls = [], storageWrites = [];
  class Element {
    constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this._text = ''; this.listeners = {}; this.hidden = false; this.value = ''; this.parent = null; }
    get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
    set textContent(value) { this._text = String(value); this.children.forEach(child => { child.parent = null; }); this.children = []; }
    get isConnected() { return this.root || Boolean(this.parent?.isConnected); }
    get firstChild() { return this.children[0]; }
    append(...children) { children.forEach(child => { child.parent = this; this.children.push(child); }); }
    replaceChildren(...children) { this.children.forEach(child => { child.parent = null; }); this.children = []; this._text = ''; this.append(...children); }
    remove() { if (this.parent) { this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null; } }
    setAttribute(key, value) { this[key] = String(value); }
    getAttribute(key) { return this[key] ?? null; }
    addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
    removeEventListener(name, fn) { this.listeners[name] = (this.listeners[name] || []).filter(value => value !== fn); }
    async emit(name, values = {}) { for (const fn of [...(this.listeners[name] || [])]) fn({target:this, preventDefault() {}, ...values}); await settle(); }
    click() { return this.disabled ? Promise.resolve() : this.emit('click'); }
    focus(options) { activeElement = this; this.focusOptions = options; }
    showModal() { this.open = true; }
    close() { this.open = false; }
  }
  const document = {hidden:false, createElement:tag => new Element(tag), body:new Element('body'),
    addEventListener(name, fn) { (listeners[name] ||= []).push(fn); }, removeEventListener(name, fn) { listeners[name] = (listeners[name] || []).filter(value => value !== fn); }};
  document.body.root = true;
  const speechSynthesis = {speaking:false, pending:false, speak(utterance) { this.speaking = true; speechCalls.push({type:'speak', utterance}); }, cancel() { this.speaking = false; speechCalls.push({type:'cancel'}); }};
  const window = voice ? {speechSynthesis, SpeechSynthesisUtterance:class { constructor(text) { this.text = text; } }} : {};
  const forbidden = value => { storageWrites.push(value); throw new Error(`Unexpected ${value}`); };
  const sandbox = {window, document, AbortController, URL,
    setTimeout(fn, delay = 0) { const id = ++timerId; timers.set(id, {fn, due:now + delay}); return id; }, clearTimeout(id) { timers.delete(id); },
    fetch() { forbidden('fetch'); }, localStorage:{setItem() { forbidden('localStorage'); }, getItem() { forbidden('localStorage read'); }},
    sessionStorage:{setItem() { forbidden('sessionStorage'); }, getItem() { forbidden('sessionStorage read'); }}, indexedDB:{open() { forbidden('indexedDB'); }}};
  vm.runInNewContext(code, sandbox);
  const container = () => { const el = new Element('div'); document.body.append(el); return el; };
  const tick = async ms => { const until = now + ms; for (;;) { const entry = [...timers].filter(([, value]) => value.due <= until).sort((a,b) => a[1].due - b[1].due)[0]; if (!entry) break; const [id, value] = entry; timers.delete(id); now = value.due; value.fn(); await settle(); } now = until; await settle(); };
  const visibility = async value => { document.hidden = value; for (const fn of [...(listeners.visibilitychange || [])]) fn(); await settle(); };
  return {...window.RoxyDrinks, container, tick, visibility, speechCalls, speechSynthesis, storageWrites, get activeElement() { return activeElement; }};
}
function server(data = payload(), intercept) {
  const calls = [], fullRows = fixtureBodies.get(data) || rows;
  return {calls, api:async (path, options) => {
    const url = new URL(path, 'https://home.invalid');
    assert.match(url.pathname, /^\/v1\/home-food\/household%2Fa\/drinks(?:\/[a-z0-9_-]+)?$/); assert.equal(options.method, 'GET'); assert.ok(options.signal instanceof AbortSignal);
    assert.equal(url.search, '?include_spirit_bases=true', 'new metadata is negotiated without breaking previous clients');
    const call = {path, url, options}; calls.push(call); const override = intercept?.(calls.length, call); if (override !== undefined) return await override;
    if (url.pathname.endsWith('/drinks/summaries')) return structuredClone(data);
    const row = fullRows.find(item => item.id === url.pathname.split('/').at(-1)); assert.ok(row, `Unknown synthetic detail ${path}`); return fullResponse(row);
  }};
}
async function start(h, panel, mock, options = {}) {
  h.render(panel, {user:'household/a', identity:'member-a', api:mock.api, ...options}); await button(panel, 'Explorar bebidas').click();
}
const dialog = panel => all(panel, 'dialog')[0];

test('bounded local gallery loads explicitly once and defaults to nonalcoholic photos and Spanish titles', async () => {
  const h = harness(), panel = h.container(), mock = server(); h.render(panel, {user:'household/a', api:mock.api}); await h.tick(60000); assert.equal(mock.calls.length, 0);
  await button(panel, 'Explorar bebidas').click(); assert.equal(mock.calls.length, 1); assert.equal(byClass(panel, 'drinks-card').length, 24);
  const titles = all(byClass(panel, 'drinks-grid')[0], 'h3').map(el => el.textContent); assert.ok(titles.includes(rows[0].title_es)); assert.ok(!titles.includes(rows[4].title_es));
  assert.ok(all(panel, 'img').every(img => img.loading === 'lazy' && img.referrerPolicy === 'no-referrer'));
  assert.ok(panel.textContent.includes('60 bebidas en esta colección: 48 sin licores y 12 cócteles con alcohol')); assert.deepEqual(h.storageWrites, []); assert.equal(h.speechCalls.length, 0);
});

test('card counts use singular Spanish for one ingredient or step', async () => {
  const one = structuredClone(rows[0]);
  one.ingredients = one.ingredients.slice(0, 1); one.ingredients_es = one.ingredients_es.slice(0, 1);
  one.steps = one.steps.slice(0, 1); one.steps_es = one.steps_es.slice(0, 1);
  const h = harness(), panel = h.container(), mock = server(payload([one]));
  await start(h, panel, mock);
  assert.equal(byClass(panel, 'drinks-card-meta')[0].textContent, '1 ingrediente · 1 paso');
});

test('pagination and bilingual searches remain local and replace pages of at most 24', async () => {
  const h = harness(), panel = h.container(), mock = server(); await start(h, panel, mock); await button(panel, 'Más bebidas').click();
  assert.equal(byClass(panel, 'drinks-card').length, 24); assert.equal(button(panel, 'Más bebidas').disabled, true); assert.equal(mock.calls.length, 1);
  await button(panel, 'Bebidas anteriores').click(); const search = all(panel, 'input')[0]; search.value = 'sintética 58'; await all(panel, 'form')[0].emit('submit');
  assert.equal(byClass(panel, 'drinks-card').length, 1); assert.ok(byClass(panel, 'drinks-card')[0].textContent.includes(rows[58].title_es));
  assert.ok(panel.textContent.includes('1–1 de 1 bebida.')); assert.ok(!panel.textContent.includes('1–1 de 1 bebidas.'));
  search.value = 'Synthetic drink 0'; await all(panel, 'form')[0].emit('submit'); assert.equal(byClass(panel, 'drinks-card').length, 1);
  await button(panel, 'Quitar filtros de bebidas').click(); assert.equal(byClass(panel, 'drinks-card').length, 24); assert.equal(mock.calls.length, 1);
});

test('alcohol is excluded from search until explicit cocktail selection and checked adult choice', async () => {
  const h = harness(), panel = h.container(), mock = server(); await start(h, panel, mock);
  const search = all(panel, 'input')[0]; search.value = rows[59].title; await all(panel, 'form')[0].emit('submit'); assert.equal(byClass(panel, 'drinks-card').length, 0);
  await button(panel, 'Quitar filtros de bebidas').click(); await category(panel, 'cocktail').click(); assert.equal(dialog(panel).open, true);
  const confirm = button(dialog(panel), 'Ver cócteles con alcohol'); assert.equal(confirm.disabled, true); await confirm.click(); assert.ok(!all(byClass(panel, 'drinks-grid')[0], 'h3').some(el => el.textContent === rows[4].title_es));
  const check = all(dialog(panel), 'input')[0]; check.checked = true; await check.emit('change'); await confirm.click();
  assert.equal(dialog(panel).open, false); assert.equal(byClass(panel, 'drinks-card').length, 12); assert.ok(byClass(panel, 'drinks-card')[0].textContent.includes(rows[4].title_es));
  await byClass(panel, 'drinks-categories')[0].children[0].click(); assert.equal(byClass(panel, 'drinks-card').length, 24); assert.ok(!all(byClass(panel, 'drinks-grid')[0], 'h3').some(el => el.textContent === rows[4].title_es));
  assert.deepEqual(h.storageWrites, []); assert.equal(mock.calls.length, 1);
});

test('dialog retains exact quantities, full ordered steps, credits and reversible original language', async () => {
  const h = harness(), panel = h.container(), mock = server(payload(rows.slice(0,1))); await start(h, panel, mock); const opener = button(panel, 'Preparar bebida'); await opener.click();
  const d = dialog(panel); assert.equal(d.open, true); assert.ok(d.getAttribute('aria-labelledby')); assert.equal(d.getAttribute('aria-modal'), 'true');
  assert.deepEqual(byClass(d, 'drinks-ingredients')[0].children.map(el => el.textContent), rows[0].ingredients_es);
  assert.deepEqual(byClass(d, 'drinks-steps')[0].children.map(el => el.textContent), rows[0].steps_es);
  await button(d, 'Ver original en inglés').click(); assert.deepEqual(byClass(d, 'drinks-ingredients')[0].children.map(el => el.textContent), rows[0].ingredients);
  assert.deepEqual(byClass(d, 'drinks-steps')[0].children.map(el => el.textContent), rows[0].steps); assert.equal(byClass(d, 'drinks-steps')[0].lang, 'en');
  const credits = byClass(d, 'drinks-credits')[0]; assert.ok(credits); assert.ok(!credits.open);
  assert.ok(credits.textContent.includes(rows[0].image_credit)); assert.ok(credits.textContent.includes(rows[0].contributor)); assert.ok(all(credits, 'a').some(a => a.href === rows[0].source_url));
  assert.ok(all(credits, 'a').some(a => a.href === '/assets/open-drinks-license.txt'));
  assert.ok(!button(d, 'Agregar ingredientes')); await button(d, 'Cerrar bebida').click(); assert.equal(d.open, false); assert.equal(d.children[0].children.length, 0); assert.equal(h.activeElement, opener);
});

test('reader is bounded and optional device speech reads the exact displayed step, never starts automatically', async () => {
  const h = harness(), panel = h.container(), mock = server(payload(rows.slice(0,1))); await start(h, panel, mock); await button(panel, 'Preparar bebida').click(); const d = dialog(panel);
  await button(d, 'Leer paso a paso').click(); assert.equal(h.speechCalls.length, 0); assert.equal(button(d, 'Paso anterior').disabled, true);
  await button(d, 'Escuchar este paso').click(); assert.equal(h.speechCalls[0].utterance.text, rows[0].steps_es[0]); assert.equal(h.speechCalls[0].utterance.lang, 'es-US');
  await button(d, 'Paso siguiente').click(); assert.equal(h.speechCalls.at(-1).type, 'cancel'); assert.equal(button(d, 'Paso siguiente').disabled, true);
  assert.equal(byClass(d, 'drinks-reader-step')[0].textContent, rows[0].steps_es[1]);
  await button(d, 'Ver original en inglés').click(); await button(d, 'Escuchar este paso').click(); assert.equal(h.speechCalls.at(-1).utterance.text, rows[0].steps[1]);
  await button(d, 'Detener voz').click(); assert.equal(h.speechCalls.at(-1).type, 'cancel'); await button(d, 'Ver preparación completa').click(); assert.equal(byClass(d, 'drinks-reader')[0].hidden, true);
});

test('device without speech keeps a complete usable text reader', async () => {
  const h = harness({voice:false}), panel = h.container(), mock = server(payload(rows.slice(0,1))); await start(h, panel, mock); await button(panel, 'Preparar bebida').click();
  await button(panel, 'Leer paso a paso').click(); assert.equal(button(panel, 'Escuchar este paso'), undefined); assert.equal(byClass(panel, 'drinks-reader-step')[0].textContent, rows[0].steps_es[0]);
});

for (const mode of ['inactive', 'hidden', 'identity', 'document']) test(`pending response is aborted and ignored on ${mode}`, async () => {
  const pending = deferred(), h = harness(), panel = h.container(), mock = server(payload(), () => pending.promise); await start(h, panel, mock);
  if (mode === 'inactive') h.setActive(panel, false);
  if (mode === 'hidden') h.render(panel, {user:'household/a', identity:'member-a', api:mock.api, hidden:true});
  if (mode === 'identity') h.render(panel, {user:'household/a', identity:'member-b', api:mock.api});
  if (mode === 'document') await h.visibility(true);
  assert.equal(mock.calls[0].options.signal.aborted, true); pending.resolve(payload()); await settle(); assert.equal(byClass(panel, 'drinks-card').length, 0);
});

test('leaving the module closes detail, stops its speech and purges recipes and transient adult choice', async () => {
  const h = harness(), panel = h.container(), mock = server(); await start(h, panel, mock); await category(panel, 'cocktail').click();
  const check = all(dialog(panel), 'input')[0]; check.checked = true; await check.emit('change'); await button(panel, 'Ver cócteles con alcohol').click(); await button(panel, 'Preparar bebida').click();
  await button(panel, 'Leer paso a paso').click(); await button(panel, 'Escuchar este paso').click(); h.setActive(panel, false);
  assert.equal(h.speechCalls.at(-1).type, 'cancel'); assert.equal(dialog(panel).open, false); assert.equal(byClass(panel, 'drinks-steps').length, 0); assert.equal(byClass(panel, 'drinks-card').length, 0);
  h.setActive(panel, true); await button(panel, 'Explorar bebidas').click(); await category(panel, 'cocktail').click(); assert.ok(button(panel, 'Ver cócteles con alcohol').disabled); assert.deepEqual(h.storageWrites, []);
});

test('returning to drinks clears an old search instead of making the catalogue appear empty', async () => {
  const h = harness(), panel = h.container(), mock = server(); await start(h, panel, mock);
  const search = all(panel, 'input')[0]; search.value = 'no matching drink'; await all(panel, 'form')[0].emit('submit');
  assert.equal(byClass(panel, 'drinks-card').length, 0);
  h.setActive(panel, false); h.setActive(panel, true); await button(panel, 'Explorar bebidas').click();
  assert.equal(search.value, ''); assert.equal(byClass(panel, 'drinks-card').length, 24);
});

test('Escape closes native dialog, purges its body and restores the invoking card focus', async () => {
  const h = harness(), panel = h.container(), mock = server(payload(rows.slice(0,1))); await start(h, panel, mock); const opener = button(panel, 'Preparar bebida'); await opener.click();
  await dialog(panel).emit('cancel'); assert.equal(dialog(panel).open, false); assert.equal(byClass(panel, 'drinks-steps').length, 0); assert.equal(h.activeElement, opener);
});

for (const bad of [
  `https://raw.githubusercontent.com/alfg/opendrinks/main/src/assets/recipes/test.jpg`,
  `https://raw.githubusercontent.com.evil.test/alfg/opendrinks/${revision}/src/assets/recipes/test.jpg`,
  `https://raw.githubusercontent.com/alfg/opendrinks/${revision}/src/assets/recipes/test.svg`,
  `https://raw.githubusercontent.com/alfg/opendrinks/${revision}/src/assets/recipes/test.jpg?track=1`,
  'javascript:alert(1)'
]) test(`untrusted or unpinned image is never loaded: ${bad}`, async () => {
  const row = {...rows[0], image_url:bad}, h = harness(), panel = h.container(), mock = server(payload([row])); await start(h, panel, mock); assert.equal(all(panel, 'img').length, 0); assert.equal(byClass(panel, 'drinks-card').length, 1);
});

test('a failed exact photo displays an honest message without generic fallback or extra requests', async () => {
  const h = harness(), panel = h.container(), mock = server(payload(rows.slice(0,1))); await start(h, panel, mock); await all(panel, 'img')[0].emit('error');
  assert.equal(all(panel, 'img').length, 0); assert.ok(panel.textContent.includes('No se pudo cargar la foto de esta bebida.')); assert.equal(mock.calls.length, 1);
});

for (const mutation of [
  data => { data.source.revision = 'main'; }, data => { data.source.license = 'unknown'; }, data => { data.total = 500; },
  data => { data.counts.juice = 500; }, data => { data.drinks[0].steps = []; }, data => { data.drinks[0].source_url = 'https://evil.test'; },
  data => { data.drinks.push(data.drinks[0]); data.total++; }
]) test(`invalid catalogue fails closed without showing substitute recipes: ${mutation.toString()}`, async () => {
  const data = payload(); mutation(data); const h = harness(), panel = h.container(), mock = server(data); await start(h, panel, mock);
  assert.equal(byClass(panel, 'drinks-card').length, 0); assert.equal(button(panel, 'Reintentar bebidas').hidden, false);
});

test('partial Spanish translation fails closed instead of claiming a complete bilingual detail', async () => {
  const row = {...rows[0], steps_es:['Only one translated step']}, h = harness(), panel = h.container(), mock = server(payload([row])); await start(h, panel, mock); await button(panel, 'Preparar bebida').click();
  assert.equal(byClass(panel, 'drinks-steps').length, 0); assert.equal(button(panel, 'Reintentar esta bebida').hidden, false); assert.equal(button(panel, 'Ver original en inglés'), undefined);
});

test('12 second timeout settles even if the API ignores abort; stale late data never paints', async () => {
  const pending = deferred(), h = harness(), panel = h.container(), mock = server(payload(), () => pending.promise); await start(h, panel, mock); await h.tick(12000);
  assert.equal(mock.calls[0].options.signal.aborted, true); assert.ok(panel.textContent.includes('La carga tardó demasiado')); pending.resolve(payload()); await settle(); assert.equal(byClass(panel, 'drinks-card').length, 0);
});

test('published selection renders each Spanish and original source line without omissions (not a culinary review)', async () => {
  const actual = JSON.parse(fs.readFileSync(new URL('../data/home_open_drinks.json', import.meta.url), 'utf8')).drinks;
  for (const row of actual) {
    const h = harness({voice:false}), panel = h.container(), mock = server(payload([row])); await start(h, panel, mock);
    if (row.alcoholic) {
      await category(panel, 'cocktail').click(); const check = all(dialog(panel), 'input')[0]; check.checked = true; await check.emit('change'); await button(panel, 'Ver cócteles con alcohol').click();
    }
    assert.equal(byClass(panel, 'drinks-card').length, 1, row.id); await button(panel, 'Preparar bebida').click();
    assert.deepEqual(byClass(panel, 'drinks-ingredients')[0].children.map(el => el.textContent), row.ingredients_es, row.id);
    assert.deepEqual(byClass(panel, 'drinks-steps')[0].children.map(el => el.textContent), row.steps_es, row.id);
    await button(panel, 'Ver original en inglés').click();
    assert.deepEqual(byClass(panel, 'drinks-ingredients')[0].children.map(el => el.textContent), row.ingredients, row.id);
    assert.deepEqual(byClass(panel, 'drinks-steps')[0].children.map(el => el.textContent), row.steps, row.id);
    assert.equal(all(dialog(panel), 'img')[0].src, row.image_url, row.id);
  }
});

test('200 lightweight summaries need only one list request, 24 DOM cards, and no hidden detail bodies', async () => {
  const large = Array.from({length:200}, (_, index) => ({...rows[index % rows.length], id:`large-${index}`, title:`Large ${index}`, title_es:`Grande ${index}`,
    source_url:`https://github.com/alfg/opendrinks/blob/${revision}/src/recipes/large-${index}.json`}));
  const data = payload(large), h = harness(), panel = h.container(), mock = server(data); await start(h, panel, mock);
  assert.ok(Buffer.byteLength(JSON.stringify(data), 'utf8') < 150 * 1024);
  assert.ok(data.drinks.every(row => !('ingredients' in row) && !('steps' in row) && !('raw_source' in row)));
  assert.equal(mock.calls.length, 1); assert.equal(mock.calls[0].path, '/v1/home-food/household%2Fa/drinks/summaries?include_spirit_bases=true');
  assert.equal(byClass(panel, 'drinks-card').length, 24); assert.equal(byClass(panel, 'drinks-steps').length, 0);
  await button(panel, 'Más bebidas').click(); assert.equal(mock.calls.length, 1);
  const search = all(panel, 'input')[0]; search.value = 'Grande 198'; await all(panel, 'form')[0].emit('submit');
  assert.equal(byClass(panel, 'drinks-card').length, 1); await button(panel, 'Preparar bebida').click();
  assert.equal(mock.calls.length, 2); assert.equal(mock.calls[1].path, '/v1/home-food/household%2Fa/drinks/large-198?include_spirit_bases=true');
});

test('selecting a category clears an old title query so its visible count matches its cards', async () => {
  const h = harness(), panel = h.container(), mock = server(); await start(h, panel, mock);
  const search = all(panel, 'input')[0]; search.value = 'no title exists'; await all(panel, 'form')[0].emit('submit');
  assert.equal(byClass(panel, 'drinks-card').length, 0); await category(panel, 'juice').click();
  assert.equal(search.value, ''); assert.equal(byClass(panel, 'drinks-card').length, 12); assert.equal(mock.calls.length, 1);
});

test('only the selected detail loads; duplicate opening is coalesced and close removes its body', async () => {
  const pending = deferred(), h = harness(), panel = h.container(), mock = server(payload(), (n) => n === 2 ? pending.promise : undefined);
  await start(h, panel, mock); const opener = button(panel, 'Preparar bebida'); await opener.click(); await opener.click();
  assert.equal(mock.calls.length, 2); assert.equal(dialog(panel).getAttribute('aria-busy'), 'true'); assert.equal(byClass(panel, 'drinks-steps').length, 0);
  pending.resolve(fullResponse(rows[0])); await settle(); assert.equal(byClass(panel, 'drinks-steps').length, 1); assert.equal(dialog(panel).getAttribute('aria-busy'), 'false');
  await button(panel, 'Cerrar bebida').click(); assert.equal(byClass(panel, 'drinks-steps').length, 0);
  await opener.click(); assert.equal(mock.calls.length, 3, 'a later opening re-requests the detail, not a retained body cache');
});

test('detail failure keeps a retryable dialog without fabricating a preparation', async () => {
  const h = harness(), panel = h.container(), mock = server(payload(), n => n === 2 ? Promise.reject(new Error('unavailable')) : undefined);
  await start(h, panel, mock); await button(panel, 'Preparar bebida').click(); assert.equal(dialog(panel).open, true);
  assert.equal(byClass(panel, 'drinks-steps').length, 0); assert.equal(button(panel, 'Reintentar esta bebida').hidden, false);
  await button(panel, 'Reintentar esta bebida').click(); assert.equal(mock.calls.length, 3); assert.deepEqual(byClass(panel, 'drinks-steps')[0].children.map(el => el.textContent), rows[0].steps_es);
});

test('a 12 second detail timeout ignores a late result and allows deliberate retry', async () => {
  const pending = deferred(), h = harness(), panel = h.container(), mock = server(payload(), n => n === 2 ? pending.promise : undefined);
  await start(h, panel, mock); await button(panel, 'Preparar bebida').click(); await h.tick(12000);
  assert.equal(mock.calls[1].options.signal.aborted, true); assert.ok(dialog(panel).textContent.includes('Esta bebida tardó demasiado'));
  pending.resolve(fullResponse(rows[0])); await settle(); assert.equal(byClass(panel, 'drinks-steps').length, 0);
  await button(panel, 'Reintentar esta bebida').click(); assert.equal(byClass(panel, 'drinks-steps').length, 1);
});

for (const mode of ['close', 'query', 'page', 'category', 'inactive', 'hidden', 'identity', 'document', 'isCurrent']) test(`late detail cannot paint after ${mode}`, async () => {
  let identityIsCurrent = true;
  const pending = deferred(), h = harness(), panel = h.container(), mock = server(payload(), n => n === 2 ? pending.promise : undefined);
  await start(h, panel, mock, {isCurrent:() => identityIsCurrent}); await button(panel, 'Preparar bebida').click();
  if (mode === 'close') await button(panel, 'Cerrar bebida').click();
  if (mode === 'query') { all(panel, 'input')[0].value = 'drink 58'; await all(panel, 'form')[0].emit('submit'); }
  if (mode === 'page') await button(panel, 'Más bebidas').click();
  if (mode === 'category') await category(panel, 'smoothie').click();
  if (mode === 'inactive') h.setActive(panel, false);
  if (mode === 'hidden') h.render(panel, {user:'household/a', identity:'member-a', api:mock.api, hidden:true});
  if (mode === 'identity') h.render(panel, {user:'household/a', identity:'member-b', api:mock.api});
  if (mode === 'document') await h.visibility(true);
  if (mode === 'isCurrent') { identityIsCurrent = false; h.setActive(panel, true); }
  assert.equal(mock.calls[1].options.signal.aborted, true); pending.resolve(fullResponse(rows[0])); await settle();
  assert.equal(byClass(panel, 'drinks-steps').length, 0); assert.equal(dialog(panel)?.open || false, false);
});

for (const mutation of [
  value => { value.drink.id = 'other'; }, value => { value.drink.source_sha256 = 'b'.repeat(64); },
  value => { value.source.revision = 'main'; }, value => { value.drink.steps.pop(); }, value => { value.drink.ingredients.pop(); },
  value => { value.drink.source_url = `https://github.com/alfg/opendrinks/blob/${revision}/src/recipes/synthetic-1.json`; },
  value => { value.drink.category = 'cocktail'; value.drink.alcoholic = true; }, value => { value.can_scale = true; },
  value => { value.can_add_to_shopping = true; }, value => { value.audience = 'pet'; }, value => { value.drink.raw_source = '{}'; }
]) test(`detail is tied to summary and allowed actions: ${mutation.toString()}`, async () => {
  const value = fullResponse(rows[0]); mutation(value); const h = harness(), panel = h.container(), mock = server(payload(), n => n === 2 ? value : undefined);
  await start(h, panel, mock); await button(panel, 'Preparar bebida').click(); assert.equal(byClass(panel, 'drinks-steps').length, 0); assert.equal(button(panel, 'Reintentar esta bebida').hidden, false);
});

const baseSelect = panel => all(byClass(panel, 'drinks-spirit-filter')[0], 'select')[0];
async function acceptCocktails(panel) {
  await category(panel, 'cocktail').click();
  const check = all(dialog(panel), 'input')[0];
  if (check) { check.checked = true; await check.emit('change'); await button(panel, 'Ver cócteles con alcohol').click(); }
}
const mixedCocktails = () => [rows[0], ...Array.from({length:64}, (_, index) => ({...rows[4], id:`base-${index}`,
  title:`Mix ${index}`, title_es:`Mezcla ${index}`, spirit_bases:index % 2 ? ['gin','vodka'] : ['rum'],
  source_url:`https://github.com/alfg/opendrinks/blob/${revision}/src/recipes/base-${index}.json`}))];

test('base names and controls appear only after explicit adult cocktail choice', async () => {
  const h = harness(), panel = h.container(), mock = server(); await start(h, panel, mock);
  assert.equal(byClass(panel, 'drinks-spirit-filter')[0].hidden, true); assert.equal(all(panel, 'select').length, 0);
  await category(panel, 'cocktail').click(); assert.equal(all(panel, 'select').length, 0);
  await button(panel, 'Seguir sin licores').click(); assert.equal(all(panel, 'select').length, 0);
  await acceptCocktails(panel); const select = baseSelect(panel); assert.ok(select); assert.equal(select.value, '');
  assert.equal(select.children.length, 8); assert.ok(select.children.some(option => option.textContent === 'Ginebra (2)'));
  assert.ok(select.children.some(option => option.textContent === 'Vino, vermut y espumoso (1)'));
  assert.ok(select.children.some(option => option.textContent === 'Otras bases (1)'));
  await category(panel, 'juice').click(); assert.equal(all(panel, 'select').length, 0);
});

test('multi-base counts, title search, pagination and clear intersect without more API calls', async () => {
  const h = harness(), panel = h.container(), mock = server(payload(mixedCocktails())); await start(h, panel, mock); await acceptCocktails(panel);
  let select = baseSelect(panel); assert.ok(select.children.some(option => option.textContent === 'Todas las bases (64)'));
  assert.ok(select.children.some(option => option.textContent === 'Ginebra (32)')); assert.ok(select.children.some(option => option.textContent === 'Vodka (32)'));
  select.value = 'gin'; await select.emit('change'); assert.equal(byClass(panel, 'drinks-card').length, 24);
  await button(panel, 'Más bebidas').click(); assert.equal(byClass(panel, 'drinks-card').length, 8);
  select = baseSelect(panel); select.value = 'rum'; await select.emit('change'); assert.equal(byClass(panel, 'drinks-card').length, 24); assert.equal(button(panel, 'Bebidas anteriores').disabled, true);
  const search = all(panel, 'input')[0]; search.value = 'Mezcla 3'; await all(panel, 'form')[0].emit('submit'); assert.equal(byClass(panel, 'drinks-card').length, 5);
  select = baseSelect(panel); assert.equal(select.value, 'rum'); assert.ok(select.children.some(option => option.textContent === 'Todas las bases (11)'));
  assert.ok(select.children.some(option => option.textContent === 'Ginebra (6)'));
  select.value = 'gin'; await select.emit('change'); assert.equal(search.value, 'Mezcla 3'); assert.equal(byClass(panel, 'drinks-card').length, 6);
  await button(panel, 'Quitar filtros de bebidas').click(); assert.equal(search.value, ''); assert.equal(all(panel, 'select').length, 0); assert.equal(byClass(panel, 'drinks-card').length, 1);
  await acceptCocktails(panel); assert.equal(baseSelect(panel).value, ''); assert.equal(mock.calls.length, 1);
});

test('leaving the module clears selected base, query, adult choice and base labels', async () => {
  const h = harness(), panel = h.container(), mock = server(); await start(h, panel, mock); await acceptCocktails(panel);
  const oldSelect = baseSelect(panel); oldSelect.value = 'gin'; await oldSelect.emit('change'); h.setActive(panel, false);
  assert.equal(all(panel, 'select').length, 0); assert.equal(byClass(panel, 'drinks-spirit-filter')[0].hidden, true);
  h.setActive(panel, true); await button(panel, 'Explorar bebidas').click(); assert.equal(all(panel, 'select').length, 0);
  await category(panel, 'cocktail').click(); assert.equal(button(panel, 'Ver cócteles con alcohol').disabled, true);
  await button(panel, 'Seguir sin licores').click(); oldSelect.value = 'vodka'; await oldSelect.emit('change'); assert.equal(all(panel, 'select').length, 0);
});

test('changing base cancels a pending detail and ignores its stale result', async () => {
  const pending = deferred(), h = harness(), panel = h.container(), data = payload(mixedCocktails()), mock = server(data, n => n === 2 ? pending.promise : undefined);
  await start(h, panel, mock); await acceptCocktails(panel); await button(panel, 'Preparar bebida').click();
  const select = baseSelect(panel); select.value = 'gin'; await select.emit('change'); assert.equal(mock.calls[1].options.signal.aborted, true);
  pending.resolve(fullResponse(mixedCocktails()[1])); await settle(); assert.equal(dialog(panel).open, false); assert.equal(byClass(panel, 'drinks-steps').length, 0);
});

for (const bad of [undefined, null, 'gin', [], ['unknown'], ['gin','gin'], [true], ['gin','vodka','rum','agave','whisky','wine','other','gin']]) test(`malformed cocktail summary bases fail closed: ${JSON.stringify(bad)}`, async () => {
  const data = payload([rows[4]]); if (bad === undefined) delete data.drinks[0].spirit_bases; else data.drinks[0].spirit_bases = bad;
  const h = harness(), panel = h.container(), mock = server(data); await start(h, panel, mock);
  assert.equal(button(panel, 'Reintentar bebidas').hidden, false); assert.equal(byClass(panel, 'drinks-card').length, 0); assert.equal(all(panel, 'select').length, 0);
});

test('a nonalcoholic summary cannot be assigned an alcoholic base', async () => {
  const data = payload([rows[0]]); data.drinks[0].spirit_bases = ['gin'];
  const h = harness(), panel = h.container(), mock = server(data); await start(h, panel, mock); assert.equal(button(panel, 'Reintentar bebidas').hidden, false);
});

for (const bad of [undefined, null, 'gin', [], ['rum'], ['gin','gin'], ['unknown'], [1]]) test(`detail cannot change or omit its summary base metadata: ${JSON.stringify(bad)}`, async () => {
  const row = rows[4], value = fullResponse(row); if (bad === undefined) delete value.drink.spirit_bases; else value.drink.spirit_bases = bad;
  const h = harness(), panel = h.container(), mock = server(payload([row]), n => n === 2 ? value : undefined);
  await start(h, panel, mock); await acceptCocktails(panel); await button(panel, 'Preparar bebida').click();
  assert.equal(byClass(panel, 'drinks-steps').length, 0); assert.equal(button(panel, 'Reintentar esta bebida').hidden, false);
});

test('multi-base detail accepts the same canonical set in a different order, never inventing ABV', async () => {
  const row = {...rows[4], spirit_bases:['gin','vodka']}, value = fullResponse(row); value.drink.spirit_bases = ['vodka','gin'];
  const h = harness(), panel = h.container(), mock = server(payload([row]), n => n === 2 ? value : undefined);
  await start(h, panel, mock); await acceptCocktails(panel); await button(panel, 'Preparar bebida').click();
  assert.equal(byClass(panel, 'drinks-steps').length, 1); assert.ok(panel.textContent.includes('no indica su graduación alcohólica'));
});
