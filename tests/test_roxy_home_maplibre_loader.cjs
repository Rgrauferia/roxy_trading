/* Exercise the shipped loader in a DOM/network double; no vendor download. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../assets/roxy_maplibre_loader.js'), 'utf8');
const STYLE = '/assets/vendor/maplibre-gl.css?v=1';
const SCRIPT = '/assets/vendor/maplibre-gl.js?v=1';
const flush = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
const library = () => ({ Map() {}, NavigationControl() {}, AttributionControl() {} });

function fixture() {
  const nodes = [], timers = new Map();
  let sequence = 0, created = 0;
  function element(tag) {
    created++;
    const events = new Map();
    return {
      tag, isConnected: false, disabled: false, sheet: null, events,
      setAttribute() {},
      addEventListener(name, callback) { if (!events.has(name)) events.set(name, new Set()); events.get(name).add(callback); },
      removeEventListener(name, callback) { events.get(name)?.delete(callback); },
      emit(name) { [...(events.get(name) || [])].forEach(callback => callback()); },
      remove() { this.isConnected = false; },
    };
  }
  const document = {
    baseURI: 'https://roxy.test/lista#nexo',
    createElement: element,
    head: { appendChild(node) { nodes.push(node); node.isConnected = true; } },
    querySelectorAll(selector) { return nodes.filter(node => node.isConnected && (selector.startsWith('link') ? node.tag === 'link' && node.rel === 'stylesheet' : node.tag === 'script' && node.src)); },
  };
  const window = {
    document,
    setTimeout(callback, ms) { const id = ++sequence; timers.set(id, { callback, ms }); return id; },
    clearTimeout(id) { timers.delete(id); },
  };
  vm.runInNewContext(source, { window, URL, WeakSet });
  const active = tag => nodes.filter(node => node.isConnected && node.tag === tag);
  return { window, document, nodes, timers, active, get created() { return created; },
    insert(tag, attributes) { const node = Object.assign(element(tag), attributes); document.head.appendChild(node); return node; },
    expire() { const pending = [...timers]; assert.equal(pending.length, 1); assert.equal(pending[0][1].ms, 15000); timers.delete(pending[0][0]); pending[0][1].callback(); },
    readyScript(node = active('script').at(-1)) { window.maplibregl = library(); node.emit('load'); },
    readyStyle(node = active('link').at(-1)) { node.sheet = {}; node.emit('load'); },
    noListeners() { nodes.forEach(node => node.events.forEach(callbacks => assert.equal(callbacks.size, 0))); },
  };
}

test('loading the helper does not create tags, timers or network work', () => {
  const f = fixture();
  assert.equal(typeof f.window.RoxyMapLibre.load, 'function');
  assert.equal(f.created, 0);
  assert.equal(f.nodes.length, 0);
  assert.equal(f.timers.size, 0);
});

test('concurrent calls share one promise and await both local CSS and JS', async () => {
  const f = fixture(), first = f.window.RoxyMapLibre.load();
  assert.equal(f.window.RoxyMapLibre.load(), first);
  assert.equal(f.active('link')[0].href, STYLE);
  assert.equal(f.active('script')[0].src, SCRIPT);
  assert.equal(f.active('script')[0].async, true);
  let settled = false; first.then(() => settled = true);
  f.readyScript(); await flush(); assert.equal(settled, false);
  f.readyStyle(); const api = await first;
  assert.equal(api, f.window.maplibregl);
  assert.equal(f.window.RoxyMapLibre.load(), first);
  assert.equal(f.created, 2); assert.equal(f.timers.size, 0); f.noListeners();
});

test('CSS first does not bypass script readiness', async () => {
  const f = fixture(), pending = f.window.RoxyMapLibre.load();
  let settled = false; pending.then(() => settled = true);
  f.readyStyle(); await flush(); assert.equal(settled, false);
  f.readyScript(); await pending; f.noListeners();
});

test('valid pre-existing vendor and CSS are reused without DOM mutation', async () => {
  const f = fixture(); f.window.maplibregl = library();
  const style = f.insert('link', { rel: 'stylesheet', href: 'https://roxy.test' + STYLE, sheet: {} });
  const script = f.insert('script', { src: SCRIPT });
  const created = f.created, api = await f.window.RoxyMapLibre.load();
  assert.equal(api, f.window.maplibregl); assert.equal(f.created, created);
  assert.equal(style.isConnected, true); assert.equal(script.isConnected, true); f.noListeners();
});

test('existing valid global without CSS loads only the stylesheet', async () => {
  const f = fixture(); f.window.maplibregl = library();
  const pending = f.window.RoxyMapLibre.load();
  assert.equal(f.active('script').length, 0); f.readyStyle(); await pending;
  assert.equal(f.created, 1);
});

test('existing pending vendor tags are observed rather than duplicated', async () => {
  const f = fixture();
  const style = f.insert('link', { rel: 'stylesheet', href: STYLE });
  const script = f.insert('script', { src: SCRIPT });
  const pending = f.window.RoxyMapLibre.load(); assert.equal(f.created, 2);
  f.readyStyle(style); f.readyScript(script); await pending; f.noListeners();
});

test('script load must expose all three constructors used by the globe', async () => {
  const f = fixture(), pending = f.window.RoxyMapLibre.load();
  const rejected = assert.rejects(pending, { code: 'MAPLIBRE_INVALID_GLOBAL' });
  f.window.maplibregl = { Map() {} }; f.readyStyle(); f.active('script')[0].emit('load');
  await rejected; assert.equal(f.active('script').length, 0); assert.equal(f.active('link').length, 1);
  const retry = f.window.RoxyMapLibre.load(); f.readyScript(); await retry;
  assert.equal(f.created, 3); f.noListeners();
});

test('script error is finite; retry keeps successfully loaded CSS', async () => {
  const f = fixture(), pending = f.window.RoxyMapLibre.load();
  const rejected = assert.rejects(pending, { code: 'MAPLIBRE_SCRIPT_ERROR' });
  f.readyStyle(); f.active('script')[0].emit('error'); await rejected;
  assert.equal(f.timers.size, 0); f.noListeners();
  const retry = f.window.RoxyMapLibre.load(); assert.notEqual(retry, pending);
  assert.equal(f.active('link').length, 1); f.readyScript(); await retry;
  assert.equal(f.created, 3);
});

test('CSS error is finite; retry preserves successfully initialized JS', async () => {
  const f = fixture(), pending = f.window.RoxyMapLibre.load();
  const rejected = assert.rejects(pending, { code: 'MAPLIBRE_STYLE_ERROR' });
  f.readyScript(); f.active('link')[0].emit('error'); await rejected;
  const retry = f.window.RoxyMapLibre.load();
  assert.equal(f.active('script').length, 1); f.readyStyle(); await retry;
  assert.equal(f.created, 3); f.noListeners();
});

test('timeout removes only unfinished owned tags and allows a clean retry', async () => {
  const f = fixture(), pending = f.window.RoxyMapLibre.load();
  const rejected = assert.rejects(pending, { code: 'MAPLIBRE_LOAD_TIMEOUT' });
  f.expire(); await rejected;
  assert.equal(f.active('script').length, 0); assert.equal(f.active('link').length, 0); f.noListeners();
  const retry = f.window.RoxyMapLibre.load(); f.readyStyle(); f.readyScript(); await retry;
  assert.equal(f.created, 4); assert.equal(f.timers.size, 0);
});

test('timeout preserves a loaded style and does not fetch it again on retry', async () => {
  const f = fixture(), pending = f.window.RoxyMapLibre.load();
  const rejected = assert.rejects(pending, { code: 'MAPLIBRE_LOAD_TIMEOUT' });
  f.readyStyle(); f.expire(); await rejected;
  assert.equal(f.active('link').length, 1); assert.equal(f.active('script').length, 0);
  const retry = f.window.RoxyMapLibre.load(); f.readyScript(); await retry;
  assert.equal(f.created, 3); f.noListeners();
});

test('timeout preserves initialized vendor while missing CSS is retried', async () => {
  const f = fixture(), pending = f.window.RoxyMapLibre.load();
  const rejected = assert.rejects(pending, { code: 'MAPLIBRE_LOAD_TIMEOUT' });
  f.readyScript(); f.expire(); await rejected;
  assert.equal(f.active('script').length, 1); assert.equal(f.active('link').length, 0);
  const retry = f.window.RoxyMapLibre.load(); f.readyStyle(); await retry;
  assert.equal(f.created, 3); f.noListeners();
});

test('timed-out foreign tags stay intact but are not reused on retry', async () => {
  const f = fixture();
  const style = f.insert('link', { rel: 'stylesheet', href: STYLE });
  const script = f.insert('script', { src: SCRIPT });
  const pending = f.window.RoxyMapLibre.load();
  const rejected = assert.rejects(pending, { code: 'MAPLIBRE_LOAD_TIMEOUT' }); f.expire(); await rejected;
  assert.equal(style.isConnected, true); assert.equal(script.isConnected, true);
  const retry = f.window.RoxyMapLibre.load(); assert.equal(f.created, 4);
  f.readyStyle(f.active('link').at(-1)); f.readyScript(f.active('script').at(-1)); await retry; f.noListeners();
});

test('late callbacks from timed-out A cannot resolve or reject in-flight B', async () => {
  const f = fixture(), first = f.window.RoxyMapLibre.load();
  const callbacks = f.nodes.flatMap(node => [...node.events.values()].flatMap(set => [...set]));
  const rejected = assert.rejects(first, { code: 'MAPLIBRE_LOAD_TIMEOUT' }); f.expire(); await rejected;
  const second = f.window.RoxyMapLibre.load(); let settled = false; second.then(() => settled = true);
  callbacks.forEach(callback => callback()); await flush();
  assert.equal(settled, false); assert.equal(f.window.RoxyMapLibre.load(), second);
  f.readyStyle(); await flush(); assert.equal(settled, false);
  f.readyScript(); await second; assert.equal(f.timers.size, 0); f.noListeners();
});

test('a removed stylesheet after success is reloaded without another script', async () => {
  const f = fixture(), first = f.window.RoxyMapLibre.load();
  f.readyStyle(); f.readyScript(); await first; f.active('link')[0].remove();
  const second = f.window.RoxyMapLibre.load(); assert.notEqual(second, first);
  f.readyStyle(); await second; assert.equal(f.created, 3);
});

test('a disabled old stylesheet is preserved but cannot satisfy renderer readiness', async () => {
  const f = fixture(); f.window.maplibregl = library();
  const style = f.insert('link', { rel: 'stylesheet', href: STYLE, sheet: {}, disabled: true });
  const pending = f.window.RoxyMapLibre.load();
  assert.equal(f.created, 2); assert.equal(style.disabled, true);
  f.readyStyle(); await pending; assert.equal(style.isConnected, true);
});

test('library is revalidated when CSS finishes after script load', async () => {
  const f = fixture(), pending = f.window.RoxyMapLibre.load();
  const rejected = assert.rejects(pending, { code: 'MAPLIBRE_INVALID_GLOBAL' });
  f.readyScript(); f.window.maplibregl = null; f.readyStyle(); await rejected;
  assert.equal(f.timers.size, 0); f.noListeners();
});

test('unrelated remote vendor URL cannot satisfy the local resource match', async () => {
  const f = fixture();
  f.insert('link', { rel: 'stylesheet', href: 'https://other.test' + STYLE, sheet: {} });
  f.insert('script', { src: 'https://other.test' + SCRIPT });
  const pending = f.window.RoxyMapLibre.load(); assert.equal(f.created, 4);
  f.readyStyle(); f.readyScript(); await pending;
});

test('missing DOM rejects without unresolved promise or timeout work', async () => {
  const f = fixture(); f.document.head = null;
  await assert.rejects(f.window.RoxyMapLibre.load(), { code: 'MAPLIBRE_DOM_UNAVAILABLE' });
  assert.equal(f.timers.size, 0); assert.equal(f.created, 0);
});
