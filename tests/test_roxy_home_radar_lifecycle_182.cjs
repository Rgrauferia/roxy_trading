/* Actual Nexo radar functions with synthetic identities, clocks and map doubles. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const main = fs.readFileSync(path.join(__dirname, '../assets/roxy_list.js'), 'utf8');
const source = main.slice(main.indexOf('  const familyGlobeLifecycle='), main.indexOf('  function familyWeatherMapStyles('));
const flush = async () => { for (let i = 0; i < 24; i++) await Promise.resolve(); };
function deferred() { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; }

function fixture(options = {}) {
  let now = Date.parse('2026-09-10T16:00:00Z'), sequence = 0;
  const elements = new Map(), maps = [], intervals = new Map(), timers = new Map(), rafs = new Map(), requests = [], observers = [];
  const calls = { loader: 0, tiles: 0, remove: 0, stop: 0, resize: 0, projection: 0, fetch: 0, zoom: [] };
  const eventTarget = target => Object.assign(target, { listeners: new Map(), addEventListener(name, fn) { if (!this.listeners.has(name)) this.listeners.set(name, new Set()); this.listeners.get(name).add(fn); }, removeEventListener(name, fn) { this.listeners.get(name)?.delete(fn); }, dispatch(name) { [...(this.listeners.get(name) || [])].forEach(fn => fn()); } });
  function element() { const classes = new Set(), children = new Map(); return { hidden: false, disabled: false, textContent: '', attributes: new Map(), classList: { add: n => classes.add(n), remove: n => classes.delete(n), contains: n => classes.has(n) }, setAttribute(k, v) { this.attributes.set(k, v); }, querySelector(key) { if (!children.has(key)) children.set(key, { textContent: '' }); return children.get(key); } }; }
  const $ = id => { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); };
  const metadata = () => ({ host: 'https://tilecache.rainviewer.com', radar: { past: [{ time: Math.floor(now / 1000) - 900, path: '/v2/radar/past' }, { time: Math.floor(now / 1000) - 300, path: '/v2/radar/latest' }] } });
  const lib = { Map: class { constructor(opts) { this.center = opts.center; this.zoom = opts.zoom; this.events = new Map(); this.sources = new Map(); this.removed = false; maps.push(this); } addControl() {} on(name, fn) { this.events.set(name, fn); } emit(name, event) { this.events.get(name)?.(event); } setProjection() { calls.projection++; } getCenter() { return { lng: this.center[0], lat: this.center[1] }; } getZoom() { return this.zoom; } jumpTo(view) { this.center = view.center; this.zoom = view.zoom; } resize() { calls.resize++; } stop() { calls.stop++; } remove() { this.removed = true; calls.remove++; } isStyleLoaded() { return true; } getSource(id) { return this.sources.get(id); } addSource(id, data) { calls.tiles++; this.sources.set(id, { ...data, setTiles: value => { calls.tiles++; this.sources.get(id).tiles = value; } }); } addLayer() {} }, NavigationControl: class {}, AttributionControl: class {} };
  const context = {
    user: 'synthetic-home', account: { mode: 'member', id: 'A' }, commerce: { profile: { location_enabled: true } },
    homeFamily: { members: [{ id: 'A', is_viewer: true, sharing_enabled: true, location: { latitude: 28, longitude: -81 } }] },
    homeWeather: { status: 'READY', current: { temperature: 22, condition: 'Nublado' }, location: { label: 'Synthetic place', latitude: 29, longitude: -82 } },
    activePanel: 'family', familyWeatherGlobeMap: null, familyWeatherGlobeTimer: null, familyWeatherGlobeFrames: [], familyWeatherGlobeFrameIndex: 0, familyWeatherGlobePlaying: true, familyWeatherGlobeLoadId: 0, familyRadarMetadata: null, familyRadarFetchedAt: 0, familyWeatherGlobeActive: false, familyMapTransitioning: false,
    familyMap: { getCenter: () => ({ lat: () => 88, lng: () => 99 }), setZoom: z => calls.zoom.push(z), setCenter() {} },
    Date: class extends Date { static now() { return now; } }, Intl, DOMException, AbortController, $, console: { warn() {} },
    document: eventTarget({ hidden: false, body: element() }),
    window: eventTarget({ maplibregl: lib, RoxyMapLibre: { load() { calls.loader++; return options.loader ? options.loader(calls.loader) : Promise.resolve(lib); } } }), maplibregl: lib,
    MutationObserver: class { constructor(callback) { this.callback = callback; this.disconnected = false; observers.push(this); } observe() {} disconnect() { this.disconnected = true; } },
    setInterval(callback, ms) { const id = ++sequence; intervals.set(id, { callback, ms }); return id; }, clearInterval: id => intervals.delete(id),
    setTimeout(callback, ms) { const id = ++sequence; timers.set(id, { callback, ms }); return id; }, clearTimeout: id => timers.delete(id),
    requestAnimationFrame(callback) { const id = ++sequence; rafs.set(id, callback); return id; }, cancelAnimationFrame: id => rafs.delete(id),
    familyWeatherAtmosphere: () => ({ fresh: true, location: 'Synthetic place', validAt: now }), familyClock: () => '12:00',
    renderFamilyWeatherFx() { context.syncFamilyWeatherGlobeLifecycle(); },
    fetch(url, init) { calls.fetch++; requests.push({ url, init }); return options.fetch ? options.fetch(calls.fetch, init) : Promise.resolve({ ok: true, json: async () => metadata() }); },
  };
  vm.createContext(context); vm.runInContext(source, context);
  return { context, calls, $, maps, intervals, timers, rafs, requests, observers, metadata, elements,
    state: () => vm.runInContext('familyGlobeLifecycle', context),
    hide(value = true) { context.document.hidden = value; context.document.dispatch('visibilitychange'); },
    mutate() { observers.filter(o => !o.disconnected).forEach(o => o.callback()); },
    advance(ms) { now += ms; },
    tick() { [...intervals.values()].forEach(row => row.callback()); },
    runTimers(ms) { [...timers.entries()].filter(([, row]) => row.ms === ms).forEach(([id, row]) => { timers.delete(id); row.callback(); }); },
  };
}

test('no map, listener, network or timer before an explicit visible opening', async () => {
  const f = fixture(); f.context.syncFamilyWeatherGlobeLifecycle();
  assert.equal(f.calls.fetch, 0); assert.equal(f.calls.loader, 0); assert.equal(f.observers.length, 0);
  f.context.document.hidden = true; await f.context.activateFamilyWeatherGlobe();
  assert.equal(f.calls.loader, 0); assert.equal(f.intervals.size, 0);
});

test('hide removes renderer and requests, retains view and resumes once', async () => {
  const f = fixture(); await f.context.activateFamilyWeatherGlobe();
  f.maps[0].jumpTo({ center: [-77, 31], zoom: 3 }); assert.equal(f.intervals.size, 1);
  f.hide(); assert.equal(f.intervals.size, 0); assert.equal(f.calls.remove, 1); assert.equal(f.context.familyWeatherGlobeMap, null);
  assert.equal(f.rafs.size, 0); assert.equal(f.timers.size, 0); assert.equal(f.state().suspended, true);
  f.hide(false); f.context.document.dispatch('visibilitychange'); await flush();
  assert.equal(f.maps.length, 2); assert.equal(f.intervals.size, 1); assert.equal(f.calls.fetch, 1, 'Fresh public metadata can be reused');
  assert.deepEqual(Array.from(f.maps[1].center), [-77, 31]); assert.equal(f.maps[1].zoom, 3);
  assert.equal(f.context.document.listeners.get('visibilitychange').size, 1);
});

test('manual pause and selected observation survive hide/resume', async () => {
  const f = fixture(); await f.context.activateFamilyWeatherGlobe();
  f.context.familyWeatherGlobePlaying = false; f.context.setFamilyWeatherGlobeFrame(0); f.context.syncFamilyWeatherGlobePlayback();
  f.hide(); f.hide(false); await flush();
  assert.equal(f.context.familyWeatherGlobePlaying, false); assert.equal(f.context.familyWeatherGlobeFrameIndex, 0); assert.equal(f.intervals.size, 0);
  assert.equal(f.$('familyWeatherGlobePlay').querySelector('b').textContent, 'Reproducir');
});

test('leave while suspended closes permanently and removes lifecycle listeners', async () => {
  const f = fixture(); await f.context.activateFamilyWeatherGlobe(); f.hide();
  f.context.activePanel = 'recipes'; f.context.exitFamilyWeatherGlobe(); f.hide(false); await flush();
  assert.equal(f.context.familyWeatherGlobeActive, false); assert.equal(f.maps.length, 1); assert.equal(f.intervals.size, 0);
  assert.equal(f.context.document.listeners.get('visibilitychange').size, 0); assert.equal(f.observers[0].disconnected, true);
  assert.equal(f.state().view, null); assert.equal(f.$('familyWeatherGlobeCurrent').textContent, '');
});

test('identity change with the same home cannot retain private globe context', async () => {
  const f = fixture(); await f.context.activateFamilyWeatherGlobe();
  f.context.account.id = 'B'; f.$('app').hidden = true; f.mutate();
  assert.equal(f.context.familyWeatherGlobeActive, false); assert.equal(f.calls.remove, 1); assert.equal(f.intervals.size, 0);
  assert.equal(f.state().view, null); assert.equal(f.$('familyWeatherGlobeCurrent').textContent, '');
  assert.equal(f.calls.zoom.length, 0, 'No old center/zoom handed to the next member');
});

for (const change of ['user', 'signed_out', 'viewer consent', 'weather consent', 'other member consent', 'member removed']) {
  test(`${change} invalidates and clears an active globe`, async () => {
    const f = fixture(); f.context.homeFamily.members.push({ id: 'C', sharing_enabled: true }); await f.context.activateFamilyWeatherGlobe();
    if (change === 'user') f.context.user = 'another-home';
    if (change === 'signed_out') f.context.account.mode = 'signed_out';
    if (change === 'viewer consent') f.context.homeFamily.members[0].sharing_enabled = false;
    if (change === 'weather consent') f.context.commerce.profile.location_enabled = false;
    if (change === 'other member consent') f.context.homeFamily.members[1].sharing_enabled = false;
    if (change === 'member removed') f.context.homeFamily.members.pop();
    f.context.syncFamilyWeatherGlobeLifecycle();
    assert.equal(f.calls.remove, 1); assert.equal(f.context.familyWeatherGlobeActive, false); assert.equal(f.intervals.size, 0);
    f.hide(false); await flush(); assert.equal(f.maps.length, 1);
  });
}

test('ordinary coordinate updates do not reconstruct the renderer', async () => {
  const f = fixture(); await f.context.activateFamilyWeatherGlobe(); f.context.homeFamily.members[0].location.latitude = 28.001;
  f.context.syncFamilyWeatherGlobeLifecycle(); assert.equal(f.maps.length, 1); assert.equal(f.calls.remove, 0); assert.equal(f.intervals.size, 1);
});

test('private, invalid and missing coordinates never use stale viewer/weather locations', () => {
  const f = fixture(); f.context.homeFamily.members[0].sharing_enabled = false; f.context.commerce.profile.location_enabled = false;
  assert.deepEqual(Array.from(f.context.familyWeatherGlobeCenter()), [-81.3792, 28.5383]);
  f.context.commerce.profile.location_enabled = true;
  assert.deepEqual(Array.from(f.context.familyWeatherGlobeCenter()), [-82, 29]);
  for (const value of [null, '', false, 180, NaN]) { f.context.homeWeather.location.latitude = value; assert.deepEqual(Array.from(f.context.familyWeatherGlobeCenter()), [-81.3792, 28.5383]); }
  f.context.homeWeather.location = { latitude: 0, longitude: 0 };
  assert.deepEqual(Array.from(f.context.familyWeatherGlobeCenter()), [0, 0]);
});

test('old Google viewport is not reused as the next globe location', async () => {
  const f = fixture(); await f.context.activateFamilyWeatherGlobe();
  assert.deepEqual(Array.from(f.maps[0].center), [-81, 28]);
  assert.ok(!f.$('familyWeatherGlobeCurrent').textContent.includes('88'));
});

test('hide during library loading prevents map creation; visible retry creates only once', async () => {
  const loader = deferred(), f = fixture({ loader: () => loader.promise }); const first = f.context.activateFamilyWeatherGlobe();
  f.hide(); loader.resolve({}); await first; assert.equal(f.maps.length, 0); assert.equal(f.calls.fetch, 0);
  f.hide(false); await flush(); assert.equal(f.maps.length, 1); assert.equal(f.calls.fetch, 1); assert.equal(f.intervals.size, 1);
});

test('cancellation settles an uncooperative metadata fetch and ignores its late response', async () => {
  const response = deferred(), f = fixture({ fetch: () => response.promise }); const pending = f.context.activateFamilyWeatherGlobe(); await flush();
  assert.equal(f.requests.length, 1); f.hide(); await pending;
  assert.equal(f.requests[0].init.signal.aborted, true); assert.equal(f.state().request, null); assert.equal(f.timers.size, 0);
  response.resolve({ ok: true, json: async () => f.metadata() }); await flush();
  assert.equal(f.context.familyRadarMetadata, null); assert.equal(f.calls.tiles, 0); assert.equal(f.intervals.size, 0);
});

test('identity change before a pending library resolves clears the old overlay even without a DOM notification', async () => {
  const loader = deferred(), f = fixture({ loader: () => loader.promise }); const pending = f.context.activateFamilyWeatherGlobe();
  f.context.account.id = 'B'; loader.resolve({}); await pending;
  assert.equal(f.context.familyWeatherGlobeActive, false); assert.equal(f.maps.length, 0); assert.equal(f.calls.fetch, 0);
  assert.equal(f.$('familyWeatherGlobeCurrent').textContent, '');
});

test('consent revocation during a response body cannot update metadata or keep the old renderer', async () => {
  const body = deferred(), f = fixture({ fetch: () => Promise.resolve({ ok: true, json: () => body.promise }) });
  const pending = f.context.activateFamilyWeatherGlobe(); await flush(); f.context.homeFamily.members[0].sharing_enabled = false;
  body.resolve(f.metadata()); await pending;
  assert.equal(f.context.familyRadarMetadata, null); assert.equal(f.context.familyWeatherGlobeActive, false);
  assert.equal(f.calls.remove, 1); assert.equal(f.calls.tiles, 0); assert.equal(f.intervals.size, 0);
});

test('cancelled response body cannot overwrite a newer successful opening', async () => {
  const body = deferred(); let f;
  f = fixture({ fetch: index => Promise.resolve({ ok: true, json: () => index === 1 ? body.promise : Promise.resolve(f.metadata()) }) });
  const a = f.context.activateFamilyWeatherGlobe(); await flush(); f.hide(); await a; f.hide(false); await flush();
  const valid = f.context.familyRadarMetadata; const installed = f.calls.tiles;
  body.resolve({ host: 'https://bad.invalid', radar: { past: [] } }); await flush();
  assert.equal(f.context.familyRadarMetadata, valid); assert.equal(f.calls.tiles, installed); assert.equal(f.intervals.size, 1);
  assert.equal(f.$('familyWeatherGlobeStatus').textContent, 'Radar real · últimas 2 horas');
});

test('timeout is finite even when response body ignores abort', async () => {
  const body = deferred(), f = fixture({ fetch: () => Promise.resolve({ ok: true, json: () => body.promise }) });
  const pending = f.context.activateFamilyWeatherGlobe(); await flush(); f.runTimers(10000); await pending;
  assert.equal(f.requests[0].init.signal.aborted, true); assert.equal(f.$('familyWeatherGlobeStatus').textContent, 'Radar temporalmente no disponible');
  assert.equal(f.intervals.size, 0); assert.equal(f.state().request, null);
});

test('expired cached radar is revalidated on resume, never replayed as recent', async () => {
  const f = fixture(); await f.context.activateFamilyWeatherGlobe(); f.hide(); f.advance(31 * 60000); f.hide(false); await flush();
  assert.equal(f.calls.fetch, 2); assert.equal(f.intervals.size, 1);
  assert.ok(f.context.familyWeatherGlobeFrames.at(-1).time * 1000 >= f.context.Date.now() - 300000);
});

test('visible frame loop refreshes an expired observation instead of looping forever', async () => {
  const f = fixture(); await f.context.activateFamilyWeatherGlobe(); f.advance(31 * 60000); f.tick(); await flush();
  assert.equal(f.calls.fetch, 2); assert.equal(f.calls.remove, 1); assert.equal(f.intervals.size, 1);
});

test('manually paused radar also refreshes stale observations without enabling playback', async () => {
  const f = fixture(); await f.context.activateFamilyWeatherGlobe();
  f.context.familyWeatherGlobePlaying = false; f.context.syncFamilyWeatherGlobePlayback(); f.advance(31 * 60000);
  f.context.syncFamilyWeatherGlobeLifecycle(); await flush();
  assert.equal(f.calls.fetch, 2); assert.equal(f.maps.length, 2); assert.equal(f.intervals.size, 0);
  assert.equal(f.context.familyWeatherGlobePlaying, false);
});

test('cancelled transition, animation and interval callbacks cannot mutate the resumed instance', async () => {
  const f = fixture(); await f.context.activateFamilyWeatherGlobe();
  const transition = f.timers.get(f.state().transition).callback, resize = f.rafs.get(f.state().resize), tick = [...f.intervals.values()][0].callback;
  f.hide(); f.hide(false); await flush();
  const currentTransition = f.state().transition, currentResize = f.state().resize, tiles = f.calls.tiles, index = f.context.familyWeatherGlobeFrameIndex;
  transition(); resize(); tick();
  assert.equal(f.state().transition, currentTransition); assert.equal(f.state().resize, currentResize);
  assert.equal(f.calls.tiles, tiles); assert.equal(f.context.familyWeatherGlobeFrameIndex, index); assert.equal(f.calls.resize, 0);
});

test('explicit close cancels the renderer and reopening replaces, rather than orphans, its transition timer', async () => {
  const f = fixture(); await f.context.activateFamilyWeatherGlobe(); f.context.exitFamilyWeatherGlobe();
  assert.equal(f.context.familyWeatherGlobeMap, null); assert.equal(f.intervals.size, 0); assert.equal(f.rafs.size, 0);
  const oldId = f.state().transition, old = f.timers.get(oldId).callback; await f.context.activateFamilyWeatherGlobe();
  const latest = f.state().transition; assert.ok(!f.timers.has(oldId)); old();
  assert.equal(f.state().transition, latest); assert.equal(f.intervals.size, 1);
});

test('late MapLibre events from removed map cannot touch the replacement', async () => {
  const f = fixture(); await f.context.activateFamilyWeatherGlobe(); const old = f.maps[0]; f.hide(); f.hide(false); await flush();
  const tiles = f.calls.tiles, notice = f.$('familyWeatherGlobeNotice').textContent;
  old.emit('load'); old.zoom = 9; old.emit('zoomend'); old.emit('error', { error: { message: 'openstreetmap failed' } });
  assert.equal(f.calls.tiles, tiles); assert.equal(f.calls.projection, 0); assert.equal(f.$('familyWeatherGlobeNotice').textContent, notice);
  assert.equal(f.context.familyWeatherGlobeActive, true); assert.equal(f.calls.remove, 1);
});

test('repeated play sync and bfcache hide/show never leave duplicate frame timers', async () => {
  const f = fixture(); await f.context.activateFamilyWeatherGlobe();
  for (let i = 0; i < 8; i++) f.context.syncFamilyWeatherGlobePlayback(); assert.equal(f.intervals.size, 1);
  f.context.window.dispatch('pagehide'); assert.equal(f.intervals.size, 0); assert.equal(f.calls.remove, 1);
  f.context.window.dispatch('pageshow'); f.context.window.dispatch('pageshow'); await flush();
  assert.equal(f.maps.length, 2); assert.equal(f.intervals.size, 1);
});

test('render hook rechecks globe identity and consent before painting weather', () => {
  const render = main.slice(main.indexOf('  function renderFamilyWeatherFx()'), main.indexOf('  const familyGlobeLifecycle='));
  assert.ok(render.indexOf('syncFamilyWeatherGlobeLifecycle();') < render.indexOf('familyWeatherAtmosphere()'));
});
