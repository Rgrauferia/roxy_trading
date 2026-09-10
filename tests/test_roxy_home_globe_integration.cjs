/* Run actual main-JS globe lifecycle functions; no WebGL, location or live API. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const root = path.join(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const main = read('assets/roxy_list.js');
function between(startText, endText) {
  const start = main.indexOf(startText), end = main.indexOf(endText, start);
  assert.ok(start >= 0 && end > start, 'Execute the actual shipped function');
  return main.slice(start, end);
}
const functions = between('  async function activateFamilyWeatherGlobe()', '  function familyWeatherMapStyles(')
  + between('  function selectPanel(', '  const calendarCategories=')
  + between('  async function renderFamilyMap()', '  async function refreshFamily(');
const flush = async () => { for (let i = 0; i < 16; i++) await Promise.resolve(); };
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const frames = [{ time: 1000, path: '/v2/radar/one' }, { time: 2000, path: '/v2/radar/two' }];

function fixture(options = {}) {
  const elements = new Map(), timers = new Map(), animationFrames = [];
  const calls = { loader: 0, ensure: 0, radar: 0, install: 0, playback: 0, stop: 0, resize: 0, jump: [], zoom: [], weather: 0, google: 0, googleCreate: 0, mapStyles: 0 };
  let sequence = 0;
  function element() {
    const classes = new Set(), attributes = new Map();
    return { textContent: '', hidden: false, disabled: false, attributes,
      classList: { add: name => classes.add(name), remove: name => classes.delete(name), contains: name => classes.has(name), toggle(name, value) { if (value) classes.add(name); else classes.delete(name); } },
      setAttribute: (name, value) => attributes.set(name, value), scrollTo() {},
    };
  }
  const $ = id => { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); };
  const map = { jumpTo: position => calls.jump.push(position), resize: () => calls.resize++, getCenter: () => ({ lng: -80, lat: 25 }) };
  const context = {
    activePanel: 'family', familyWeatherGlobeActive: false, familyMapTransitioning: false,
    familyWeatherGlobeLoadId: 0, familyWeatherGlobeFrames: [], familyWeatherGlobeFrameIndex: 0,
    familyWeatherGlobePlaying: false, familyWeatherGlobeMap: null,
    homeWeather: { status: 'READY', current: { temperature: 0, condition: 'Nublado' } },
    homeFamily: { map: { provider: 'GOOGLE_MAPS' }, members: [], places: [] },
    account: { mode: 'member' }, location: { hash: '' }, $, console: { warn() {} },
    document: { body: element(), querySelectorAll: () => [] },
    window: { scrollTo() {}, RoxyMapLibre: { load() { calls.loader++; return options.loader ? options.loader(calls.loader) : Promise.resolve({}); } } },
    familyWeatherAtmosphere: () => ({ fresh: true, location: 'Lugar de prueba', validAt: '2026-09-10T12:00:00Z' }),
    familyClock: value => value,
    familyWeatherGlobeCenter: () => [-81, 28],
    familyMap: { getCenter: () => ({ lng: () => -81.5, lat: () => 28.5 }), setZoom: value => calls.zoom.push(value), setCenter() {} },
    ensureFamilyWeatherGlobe() { calls.ensure++; if (options.ensureError) throw options.ensureError; context.familyWeatherGlobeMap = map; return map; },
    loadFamilyRadarMetadata() { calls.radar++; return options.radar ? options.radar(calls.radar) : Promise.resolve({ frames }); },
    installFamilyWeatherGlobeRadar: () => calls.install++,
    syncFamilyWeatherGlobePlayback: () => calls.playback++,
    stopFamilyWeatherGlobePlayback: () => calls.stop++,
    renderFamilyWeatherFx: () => calls.weather++,
    requestAnimationFrame: callback => animationFrames.push(callback),
    setTimeout(callback, ms) { const id = ++sequence; timers.set(id, { callback, ms }); return id; },
    clearTimeout: id => timers.delete(id),
    renderRecipes() {}, mountFitness() {},
    loadFamilyGoogleMaps() { calls.google++; return options.google ? options.google() : Promise.resolve(); },
    familyWeatherMapStyles(styles) { calls.mapStyles++; return styles; },
    google: { maps: { Map() { calls.googleCreate++; throw new Error('Offscreen test must not create a Google map'); } } },
  };
  vm.createContext(context); vm.runInContext(functions, context);
  return { context, calls, elements, $, timers, animationFrames,
    flushAnimations() { animationFrames.splice(0).forEach(callback => callback()); },
  };
}

test('success waits for the renderer before map construction and real radar metadata', async () => {
  const loader = deferred(), radar = deferred(), f = fixture({ loader: () => loader.promise, radar: () => radar.promise });
  const pending = f.context.activateFamilyWeatherGlobe();
  assert.equal(f.calls.loader, 1); assert.equal(f.calls.ensure, 0); assert.equal(f.calls.radar, 0);
  assert.equal(f.$('familyWeatherGlobeStatus').textContent, 'Abriendo el visor…');
  assert.equal(f.$('familyWeatherGlobePanel').attributes.get('aria-hidden'), 'false');
  loader.resolve({}); await flush();
  assert.equal(f.calls.ensure, 1); assert.equal(f.calls.radar, 1); assert.equal(f.calls.install, 0);
  assert.equal(f.calls.jump[0].center[0], -81.5); assert.equal(f.calls.jump[0].center[1], 28.5);
  radar.resolve({ frames }); await pending; f.flushAnimations();
  assert.equal(f.calls.resize, 1); assert.equal(f.calls.install, 1); assert.equal(f.calls.playback, 1);
  assert.equal(f.context.familyWeatherGlobeFrames, frames);
  assert.equal(f.$('familyWeatherGlobeTimeline').disabled, false); assert.equal(f.$('familyWeatherGlobeTimeline').max, '1');
  assert.equal(f.$('familyWeatherGlobeStatus').textContent, 'Radar real · últimas 2 horas');
});

test('renderer download failure does not claim a live globe or blame RainViewer', async () => {
  const f = fixture({ loader: () => Promise.reject(new Error('offline script')) });
  await f.context.activateFamilyWeatherGlobe();
  assert.equal(f.calls.ensure, 0); assert.equal(f.calls.radar, 0); assert.equal(f.calls.install, 0);
  assert.equal(f.$('familyWeatherGlobeStatus').textContent, 'No pude cargar el visor');
  assert.equal(f.$('familyWeatherGlobeTime').textContent, 'Vuelve al mapa para reintentar');
  assert.ok(!f.$('familyWeatherGlobeNotice').textContent.includes('RainViewer'));
  assert.equal(f.$('familyWeatherGlobePlay').disabled, true); assert.equal(f.$('familyWeatherGlobeTimeline').disabled, true);
  assert.equal(f.context.familyMapTransitioning, false);
});

test('construction failure has the viewer fallback, not the radar fallback', async () => {
  const f = fixture({ ensureError: new Error('WebGL unavailable') });
  await f.context.activateFamilyWeatherGlobe();
  assert.equal(f.calls.ensure, 1); assert.equal(f.calls.radar, 0);
  assert.equal(f.$('familyWeatherGlobeStatus').textContent, 'No pude cargar el visor');
  assert.ok(!f.$('familyWeatherGlobeTime').textContent.includes('activo'));
});

test('missing loader is caught with a finite viewer fallback', async () => {
  const f = fixture(); delete f.context.window.RoxyMapLibre;
  await f.context.activateFamilyWeatherGlobe();
  assert.equal(f.calls.ensure, 0); assert.equal(f.calls.radar, 0);
  assert.equal(f.$('familyWeatherGlobeStatus').textContent, 'No pude cargar el visor');
});

test('radar failure keeps the actual globe but clears and disables radar', async () => {
  const f = fixture({ radar: () => Promise.reject(new Error('RainViewer HTTP 503')) });
  await f.context.activateFamilyWeatherGlobe();
  assert.equal(f.calls.ensure, 1); assert.equal(f.calls.radar, 1); assert.equal(f.calls.install, 0);
  assert.equal(f.$('familyWeatherGlobeStatus').textContent, 'Radar temporalmente no disponible');
  assert.equal(f.$('familyWeatherGlobeTime').textContent, 'Globo interactivo activo');
  assert.match(f.$('familyWeatherGlobeNotice').textContent, /RainViewer.*503/);
  assert.equal(f.context.familyWeatherGlobeFrames.length, 0); assert.equal(f.calls.playback, 0);
});

test('successful retry clears the obsolete viewer-error notice', async () => {
  const f = fixture({ loader: index => index === 1 ? Promise.reject(new Error('first attempt offline')) : Promise.resolve({}) });
  await f.context.activateFamilyWeatherGlobe();
  assert.match(f.$('familyWeatherGlobeNotice').textContent, /no se ha cargado un globo/);
  f.context.exitFamilyWeatherGlobe(); await f.context.activateFamilyWeatherGlobe();
  assert.equal(f.calls.install, 1);
  assert.ok(!f.$('familyWeatherGlobeNotice').textContent.includes('no se ha cargado un globo'), 'Old viewer error contradicts the recovered globe');
});

test('successful retry clears the obsolete RainViewer error notice', async () => {
  const f = fixture({ radar: index => index === 1 ? Promise.reject(new Error('first attempt 503')) : Promise.resolve({ frames }) });
  await f.context.activateFamilyWeatherGlobe();
  assert.match(f.$('familyWeatherGlobeNotice').textContent, /RainViewer no respondió/);
  f.context.exitFamilyWeatherGlobe(); await f.context.activateFamilyWeatherGlobe();
  assert.equal(f.calls.install, 1);
  assert.ok(!f.$('familyWeatherGlobeNotice').textContent.includes('RainViewer no respondió'), 'Old radar error contradicts the recovered real data');
});

test('closing while the library loads prevents construction and radar requests', async () => {
  const loader = deferred(), f = fixture({ loader: () => loader.promise });
  const pending = f.context.activateFamilyWeatherGlobe(); const openingId = f.context.familyWeatherGlobeLoadId;
  f.context.exitFamilyWeatherGlobe(); loader.resolve({}); await pending; f.flushAnimations();
  assert.equal(f.calls.ensure, 0); assert.equal(f.calls.radar, 0); assert.equal(f.calls.resize, 0);
  assert.equal(f.context.familyWeatherGlobeActive, false); assert.ok(f.context.familyWeatherGlobeLoadId > openingId);
  assert.equal(f.$('familyWeatherGlobePanel').attributes.get('aria-hidden'), 'true');
  assert.equal(f.context.document.body.classList.contains('family-globe-active'), false);
});

test('changing module through selectPanel cancels a pending globe opening', async () => {
  const loader = deferred(), f = fixture({ loader: () => loader.promise });
  const pending = f.context.activateFamilyWeatherGlobe(); f.context.selectPanel('today');
  loader.resolve({}); await pending;
  assert.equal(f.context.activePanel, 'today'); assert.equal(f.context.location.hash, 'hoy');
  assert.equal(f.context.familyWeatherGlobeActive, false); assert.equal(f.calls.ensure, 0); assert.equal(f.calls.radar, 0);
});

test('offscreen and duplicate active openings do not download twice', async () => {
  const loader = deferred(), f = fixture({ loader: () => loader.promise });
  f.context.activePanel = 'fitness'; await f.context.activateFamilyWeatherGlobe();
  assert.equal(f.calls.loader, 0); assert.equal(f.elements.size, 0);
  f.context.activePanel = 'family'; const pending = f.context.activateFamilyWeatherGlobe();
  await f.context.activateFamilyWeatherGlobe(); assert.equal(f.calls.loader, 1);
  loader.resolve({}); await pending;
});

test('closing during radar fetch prevents stale installation and queued resize', async () => {
  const radar = deferred(), f = fixture({ radar: () => radar.promise });
  const pending = f.context.activateFamilyWeatherGlobe(); await flush();
  assert.equal(f.calls.ensure, 1); assert.equal(f.calls.radar, 1);
  f.context.exitFamilyWeatherGlobe(); radar.resolve({ frames }); await pending; f.flushAnimations();
  assert.equal(f.calls.install, 0); assert.equal(f.calls.playback, 0); assert.equal(f.calls.resize, 0);
  assert.equal(f.context.familyWeatherGlobeFrames.length, 0);
});

test('late renderer failure from A cannot overwrite successful opening B', async () => {
  const first = deferred(), second = deferred();
  const f = fixture({ loader: index => index === 1 ? first.promise : second.promise });
  const a = f.context.activateFamilyWeatherGlobe(); f.context.exitFamilyWeatherGlobe();
  const b = f.context.activateFamilyWeatherGlobe(); second.resolve({}); await b;
  first.reject(new Error('obsolete A')); await a;
  assert.equal(f.calls.ensure, 1); assert.equal(f.calls.radar, 1); assert.equal(f.calls.install, 1);
  assert.equal(f.$('familyWeatherGlobeStatus').textContent, 'Radar real · últimas 2 horas');
  assert.equal(f.$('familyWeatherGlobePlay').disabled, false);
});

test('late radar failure from A cannot clear successful opening B', async () => {
  const first = deferred();
  const f = fixture({ radar: index => index === 1 ? first.promise : Promise.resolve({ frames }) });
  const a = f.context.activateFamilyWeatherGlobe(); await flush(); f.context.exitFamilyWeatherGlobe();
  await f.context.activateFamilyWeatherGlobe(); first.reject(new Error('obsolete radar A')); await a;
  assert.equal(f.calls.install, 1); assert.equal(f.context.familyWeatherGlobeFrames, frames);
  assert.equal(f.$('familyWeatherGlobeStatus').textContent, 'Radar real · últimas 2 horas');
});

test('Google Maps is not loaded while Nexo is hidden', async () => {
  const f = fixture(); f.context.activePanel = 'recipes';
  await f.context.renderFamilyMap(); assert.equal(f.calls.google, 0); assert.equal(f.calls.googleCreate, 0);
});

test('Google Maps is not constructed after the user leaves during its loader', async () => {
  const google = deferred(), f = fixture({ google: () => google.promise });
  const pending = f.context.renderFamilyMap(); assert.equal(f.calls.google, 1);
  f.context.activePanel = 'fitness'; google.resolve(); await pending;
  assert.equal(f.calls.googleCreate, 0); assert.equal(f.calls.mapStyles, 0, 'No hidden map work may resume after its loader');
});

test('HTML loads only the lightweight helper; Docker retains local vendor', () => {
  const html = read('assets/roxy_list.html'), docker = read('Dockerfile.roxy-home');
  const helper = html.indexOf('src="/assets/roxy_maplibre_loader.js?v=1"');
  assert.ok(helper >= 0 && helper < html.indexOf('src="/assets/roxy_list.js?'));
  assert.ok(!/\b(?:src|href)=["'][^"']*vendor\/maplibre-gl/.test(html));
  assert.ok(docker.includes('COPY assets/roxy_maplibre_loader.js ./assets/'));
  assert.ok(docker.includes('COPY assets/vendor/maplibre-gl.js assets/vendor/maplibre-gl.css'));
});

test('recipes and exercise remain adjacent in navigation without CSS reordering', () => {
  const html = read('assets/roxy_list.html'), css = read('assets/roxy_list.css').replace(/\/\*[\s\S]*?\*\//g, '');
  const nav = html.match(/<nav\b[^>]*class="bottom-nav"[^>]*>([\s\S]*?)<\/nav>/)[1];
  const links = [...nav.matchAll(/\bdata-tab-link="([^"]+)"/g)].map(match => match[1]);
  assert.equal(links[links.indexOf('recipes') + 1], 'fitness');
  const rules = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)];
  for (const [, selector, declarations] of rules) {
    if (!selector.includes('bottom-nav') && !selector.includes('fitness-nav') && !selector.includes('roxy-nav')) continue;
    const order = [...declarations.matchAll(/(?:^|;)\s*order\s*:\s*([^;]+)/g)].map(match => match[1].trim());
    assert.ok(order.every(value => /^(?:0|initial|unset|revert)(?:\s*!important)?$/.test(value)), `Legacy navigation order remains in ${selector}: ${order}`);
  }
});
