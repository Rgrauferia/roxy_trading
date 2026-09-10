/* Private weather refresh: actual JS functions, no network or real people. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const main = fs.readFileSync(path.join(__dirname, '../assets/roxy_list.js'), 'utf8');
const source = main.slice(main.indexOf('  let familyWeatherRefreshTimer='), main.indexOf('  function renderFamilyWeatherFx()'));
const flush = async () => { for (let i = 0; i < 16; i++) await Promise.resolve(); };
function deferred() { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; }
function fixture() {
  const requests = [], timers = new Map(), app = { hidden: false }; let sequence = 0;
  const calls = { weather: 0, fx: 0, styles: 0 };
  const context = { user: 'shared-synthetic-home', account: { mode: 'member', id: 'A' }, activePanel: 'family', document: { hidden: false },
    commerce: { profile: { location_enabled: true, latitude: 28, longitude: -81 } }, homeWeather: { status: 'UNAVAILABLE' },
    $: () => app, Date, AbortController, DOMException,
    api(url, options) { const pending = deferred(); requests.push({ ...pending, url, options }); return pending.promise; },
    collectionIdentity: () => `${context.account.mode}:${context.account.id}`,
    renderWeather: () => calls.weather++, renderFamilyWeatherFx: () => calls.fx++,
    familyMap: { setOptions: () => calls.styles++ }, familyWeatherMapStyles: styles => styles,
    setTimeout(callback, ms) { const id = ++sequence; timers.set(id, { callback, ms }); return id; }, clearTimeout: id => timers.delete(id),
  };
  vm.createContext(context); vm.runInContext(source, context);
  vm.runInContext('familyWeatherBaseMapStyles=[]', context);
  return { context, requests, calls, timers, app, pending: () => vm.runInContext('familyWeatherRefreshPending', context) };
}

test('current response renders once; duplicate refreshes are coalesced and throttled', async () => {
  const f = fixture(); const pending = f.context.refreshFamilyWeatherIfNeeded(); await f.context.refreshFamilyWeatherIfNeeded();
  assert.equal(f.requests.length, 1); f.requests[0].resolve({ status: 'READY', marker: 'A' }); await pending;
  assert.equal(f.context.homeWeather.marker, 'A'); assert.deepEqual(f.calls, { weather: 1, fx: 1, styles: 1 });
  assert.equal(f.pending(), false); assert.equal(f.timers.size, 0); await f.context.refreshFamilyWeatherIfNeeded(); assert.equal(f.requests.length, 1);
});

for (const kind of ['success', 'error']) {
  test(`late ${kind} of A cannot render or release B's pending request in the same home`, async () => {
    const f = fixture(); const a = f.context.refreshFamilyWeatherIfNeeded(); f.context.account.id = 'B';
    const b = f.context.refreshFamilyWeatherIfNeeded(); assert.equal(f.requests.length, 2); assert.equal(f.requests[0].options.signal.aborted, true);
    if (kind === 'success') f.requests[0].resolve({ status: 'READY', marker: 'A' }); else f.requests[0].reject(new Error('obsolete A'));
    await a; assert.equal(f.pending(), true); assert.deepEqual(f.calls, { weather: 0, fx: 0, styles: 0 });
    await f.context.refreshFamilyWeatherIfNeeded(); assert.equal(f.requests.length, 2);
    f.requests[1].resolve({ status: 'READY', marker: 'B' }); await b;
    assert.equal(f.context.homeWeather.marker, 'B'); assert.equal(f.pending(), false); assert.equal(f.calls.weather, 1);
  });
}

for (const condition of ['hidden document', 'hidden app', 'leave module', 'consent revoked', 'identity changed', 'house changed', 'location changed', 'signed out']) {
  test(`${condition} cancels and discards pending success without repainting`, async () => {
    const f = fixture(), pending = f.context.refreshFamilyWeatherIfNeeded();
    if (condition === 'hidden document') f.context.document.hidden = true;
    if (condition === 'hidden app') f.app.hidden = true;
    if (condition === 'leave module') f.context.activePanel = 'recipes';
    if (condition === 'consent revoked') f.context.commerce.profile.location_enabled = false;
    if (condition === 'identity changed') f.context.account.id = 'B';
    if (condition === 'house changed') f.context.user = 'second-home';
    if (condition === 'location changed') f.context.commerce.profile.latitude = 31;
    if (condition === 'signed out') f.context.account.mode = 'signed_out';
    f.context.cancelObsoleteFamilyWeatherRefresh(); await pending;
    assert.equal(f.requests[0].options.signal.aborted, true); assert.equal(f.pending(), false); assert.equal(f.timers.size, 0);
    f.requests[0].resolve({ status: 'READY', marker: 'obsolete' }); await flush();
    assert.equal(f.context.homeWeather.marker, undefined); assert.deepEqual(f.calls, { weather: 0, fx: 0, styles: 0 });
  });
}

test('revoking and granting location again cannot revive the old result', async () => {
  const f = fixture(); const a = f.context.refreshFamilyWeatherIfNeeded(); f.context.commerce.profile.location_enabled = false;
  f.context.cancelObsoleteFamilyWeatherRefresh(); f.context.commerce.profile.location_enabled = true;
  const b = f.context.refreshFamilyWeatherIfNeeded(); f.requests[1].resolve({ status: 'READY', marker: 'new-consent' }); await b;
  f.requests[0].resolve({ status: 'READY', marker: 'revoked-consent' }); await a;
  assert.equal(f.context.homeWeather.marker, 'new-consent'); assert.equal(f.calls.weather, 1);
});

test('hidden refresh makes no request and rejected offscreen response cannot reopen UI', async () => {
  const f = fixture(); f.context.document.hidden = true; await f.context.refreshFamilyWeatherIfNeeded(); assert.equal(f.requests.length, 0);
  f.context.document.hidden = false; const pending = f.context.refreshFamilyWeatherIfNeeded(); f.context.document.hidden = true;
  f.requests[0].reject(new Error('offline')); await pending; assert.deepEqual(f.calls, { weather: 0, fx: 0, styles: 0 });
  f.context.document.hidden = false; const next = f.context.refreshFamilyWeatherIfNeeded(); assert.equal(f.requests.length, 2, 'Discarded request must not throttle the return');
  f.requests[1].resolve({ status: 'READY' }); await next;
});

test('model timeout settles even if API ignores cancellation; late data remains ignored', async () => {
  const f = fixture(); const pending = f.context.refreshFamilyWeatherIfNeeded();
  [...f.timers.values()].forEach(row => row.callback()); await pending;
  assert.equal(f.requests[0].options.signal.aborted, true); assert.equal(f.pending(), false); assert.equal(f.timers.size, 0);
  f.requests[0].resolve({ status: 'READY', marker: 'late' }); await flush(); assert.equal(f.context.homeWeather.marker, undefined);
});

test('weather paint checks obsolete model request before globe or scene rendering', () => {
  const render = main.slice(main.indexOf('  function renderFamilyWeatherFx()'), main.indexOf('  const familyGlobeLifecycle='));
  assert.ok(render.indexOf('cancelObsoleteFamilyWeatherRefresh();') < render.indexOf('syncFamilyWeatherGlobeLifecycle();'));
});
