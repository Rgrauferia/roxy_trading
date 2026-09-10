/* Actual load() + collection helpers, isolated storage/HTTP and synthetic members. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../assets/roxy_list.js'), 'utf8');
function section(first, last) {
  const start = source.indexOf(first), end = source.indexOf(last, start);
  assert.ok(start >= 0 && end > start);
  return source.slice(start, end);
}
const executable = section('  const collectionRecovery=', '  function renderCollectionNotice(')
  + section('  async function load({quiet=false}', '  async function queueMutation(')
  + '\nthis.recovery=collectionRecovery;this.errors=collectionLoadErrors;';
const copy = value => value === undefined ? undefined : structuredClone(value);
const flush = async () => { for (let i = 0; i < 40; i++) await Promise.resolve(); };
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const member = (id = 'a', household = 'house-a') => ({ mode: 'member', id, storage_user_id: household, display_name: 'Synthetic ' + id });
const fault = status => Object.assign(new Error('Synthetic unavailable'), { status });

function harness(options = {}) {
  const db = new Map(), reads = [], writes = [], calls = [], busy = [], renders = [], elements = new Map();
  let requestGeneration = 0;
  const $ = id => {
    if (!elements.has(id)) elements.set(id, { hidden: id === 'shoppingPanel', textContent: '', showModal() { this.open = true; } });
    return elements.get(id);
  };
  const ctx = {
    account: member(), user: 'house-a', activePanel: 'today', $, Date, Error, Array, encodeURIComponent,
    snapshot: { scope: 'unattributed-old-memory', items: [] }, homeFood: { scope: 'unattributed-old-memory' }, homeFoodReady: true, homeFoodLoadFailed: false,
    homePlants: { plants: [{ id: 'old-unattributed' }] }, homeDesign: { projects: [{ id: 'old-unattributed' }] },
    commerce: { scope: 'unattributed-old-memory' }, homeCalendar: {}, homeDaily: null, homeFamily: {}, homeWeather: {},
    window: { RoxyFitness: { clear() {} } }, document: { querySelectorAll: () => [] },
    localStorage: { setItem() {} }, sessionStorage: { getItem: () => null, setItem() {} },
    appearance: {}, safeAppearance: value => value, applyAppearance() {}, mountFitness() {},
    setBusy: value => busy.push(value), setConnection() {}, announce() {},
    populateHomeForms() {}, render() { renders.push({ user: ctx.user, identity: ctx.collectionIdentity(), hiddenDuringRender: $('app').hidden, snapshot: copy(ctx.snapshot), plants: copy(ctx.homePlants), design: copy(ctx.homeDesign) }); },
    renderAccount() {}, renderHomeMoment() {}, renderRecipes() {}, openAccountDialog() {},
    // Actual map lifecycle is covered separately by map_integration_185.
    syncFamilyMapReadiness() {}, resumeFamilyBaseMap() {},
    redeemNexoInvitationFromUrl() {}, resumeFamilyLocationIfEnabled() {}, autoSyncGoogleCalendar() {}, loadPriceRecommendations() {},
    flushQueue: async () => {},
    dbGet: async key => { reads.push(key); if (options.read) return options.read(key, () => copy(db.get(key)), ctx); return copy(db.get(key)); },
    dbSet: async (key, value) => {
      writes.push({ key, value: copy(value), ownerAtStart: ctx.user, identityAtStart: ctx.collectionIdentity() });
      if (options.write) await options.write(key, value, ctx);
      db.set(key, copy(value));
    },
    api: async (url, settings = {}) => {
      if (url === '/v1/home-account/me') requestGeneration++;
      const scope = { owner: ctx.user, identity: `${ctx.account.mode}:${ctx.account.id || ''}`, generation: requestGeneration };
      let value;
      if (url === '/v1/home-account/me') value = copy(ctx.account);
      else if (url.startsWith('/v1/home-plants/')) value = { plants: [{ id: `${scope.owner}:${scope.identity}:${scope.generation}` }], scope, storage_status: 'READY' };
      else if (url.startsWith('/v1/home-design/')) value = { projects: [{ id: `${scope.owner}:${scope.identity}:${scope.generation}` }], scope, storage_status: 'READY' };
      else value = { scope, items: [], profile: {}, events: [], members: [], daily: [] };
      calls.push({ url, settings, scope });
      return options.api ? options.api(url, value, scope, ctx) : value;
    },
  };
  vm.createContext(ctx); vm.runInContext(executable, ctx);
  return { ctx, db, reads, writes, calls, busy, renders, $, setMember(id, household) { ctx.account = member(id, household); ctx.user = household; },
    key(kind, id = ctx.account.id, household = ctx.user) { return ctx.collectionCacheKey(kind, household, 'member:' + id); },
  };
}

test('successful load uses fixed household/member keys and passes snapshot protocol', async () => {
  const h = harness(); await h.ctx.load();
  assert.equal(h.ctx.snapshot.scope.owner, 'house-a'); assert.equal(h.ctx.homeDesign.scope.identity, 'member:a');
  assert.ok(h.db.has(h.key('design'))); assert.ok(h.db.has(h.key('plants')));
  for (const kind of ['commerce', 'calendar', 'daily', 'family', 'weather']) {
    assert.ok(h.db.has(h.key(kind))); assert.ok(!h.db.has(`home-${kind}:house-a`));
  }
  assert.ok(!h.reads.includes('home-design:house-a')); assert.ok(!h.db.has('home-design:house-a'));
  for (const request of h.calls.filter(row => /\/home-(?:plants|design)\//.test(row.url))) assert.equal(request.settings.headers['X-Roxy-Snapshot-Version'], '2');
  assert.equal(h.busy.at(-1), false); assert.equal(h.renders.length, 1);
});

test('another member of the same household cannot read the unattributed legacy design cache', async () => {
  const h = harness({ api: (url, value) => url.startsWith('/v1/home-design/') ? Promise.reject(fault(503)) : value });
  h.setMember('b', 'house-a');
  h.db.set('home-design:house-a', { projects: [{ id: 'private-member-a' }] });
  h.db.set('home-design:house-a-recovery', { snapshot: { projects: [{ id: 'private-recovery-a' }] } });
  await h.ctx.load();
  assert.equal(h.ctx.homeDesign.projects.length, 0); assert.equal(h.ctx.recovery.design.value, undefined);
  assert.ok(!h.reads.includes('home-design:house-a')); assert.ok(!h.reads.includes('home-design:house-a-recovery'));
});

test('private fallback never reads household-only commerce, calendar, daily, Nexo or weather caches', async () => {
  const h = harness({ api: (url, value) => url.startsWith('/v1/shopping/') ? Promise.reject(fault(503)) : value });
  h.setMember('b', 'house-a');
  for (const kind of ['commerce', 'calendar', 'daily', 'family', 'weather']) {
    h.db.set(`home-${kind}:house-a`, { privateData: 'member-a' });
    h.db.set(h.key(kind, 'b'), { scope: 'member-b' });
  }
  await h.ctx.load();
  for (const kind of ['commerce', 'calendar', 'daily', 'family', 'weather']) assert.ok(!h.reads.includes(`home-${kind}:house-a`));
  for (const value of [h.ctx.commerce, h.ctx.homeCalendar, h.ctx.homeDaily, h.ctx.homeFamily, h.ctx.homeWeather]) assert.equal(value.scope, 'member-b');
});

test('changing identity hides old rendered content until B data is assigned and rendered', async () => {
  const pending = deferred();
  const h = harness({ api: (url, value, scope) => url.startsWith('/v1/shopping/') && scope.identity === 'member:b' ? pending.promise : value });
  await h.ctx.load(); assert.equal(h.$('app').hidden, false);
  h.setMember('b', 'house-a'); const b = h.ctx.load();
  assert.equal(h.$('app').hidden, true); await flush(); assert.equal(h.$('app').hidden, true);
  assert.equal(h.renders.length, 1, 'A remains hidden while B waits for HTTP');
  pending.resolve({ items: [], scope: { identity: 'member:b' } }); await b;
  assert.equal(h.renders.at(-1).identity, 'member:b'); assert.equal(h.renders.at(-1).hiddenDuringRender, true);
  assert.equal(h.$('app').hidden, false);
});

test('a same-identity background refresh does not unnecessarily hide already scoped content', async () => {
  const pending = deferred();
  const h = harness({ api: (url, value, scope) => url.startsWith('/v1/shopping/') && scope.generation === 2 ? pending.promise : value });
  await h.ctx.load(); const second = h.ctx.load({ quiet: true }); await flush();
  assert.equal(h.$('app').hidden, false); pending.resolve({ items: [] }); await second;
});

test('failed B request reveals only B fallback after it has been rendered', async () => {
  const h = harness({ api: (url, value, scope) => url.startsWith('/v1/shopping/') && scope.identity === 'member:b' ? Promise.reject(fault(503)) : value });
  await h.ctx.load(); h.setMember('b', 'house-b');
  h.db.set(h.key('design'), { projects: [{ id: 'b-scoped-copy' }] });
  await h.ctx.load();
  assert.equal(h.renders.at(-1).identity, 'member:b'); assert.equal(h.renders.at(-1).hiddenDuringRender, true);
  assert.equal(h.ctx.homeDesign.projects[0].id, 'b-scoped-copy'); assert.equal(h.$('app').hidden, false);
});

test('queue synchronization completes before final assignments and preserves a newer shopping snapshot', async () => {
  const h = harness(); h.ctx.flushQueue = async () => { h.ctx.snapshot = { items: [], queueFresh: true }; };
  await h.ctx.load(); assert.equal(h.ctx.snapshot.queueFresh, true); assert.equal(h.renders.at(-1).snapshot.queueFresh, true);
});

test('partial collection failure loads both current scoped cache and recovery copy', async () => {
  const h = harness({ api: (url, value) => /\/home-(?:plants|design)\//.test(url) ? Promise.reject(fault(503)) : value });
  for (const kind of ['plants', 'design']) {
    const field = kind === 'plants' ? 'plants' : 'projects';
    h.db.set(h.key(kind), { [field]: [{ id: kind + '-saved' }] });
    h.db.set(h.key(kind) + '-recovery', { snapshot: { [field]: [{ id: kind + '-recovery' }] } });
  }
  await h.ctx.load();
  assert.equal(h.ctx.homePlants.plants[0].id, 'plants-saved'); assert.equal(h.ctx.homeDesign.projects[0].id, 'design-saved');
  for (const kind of ['plants', 'design']) {
    assert.equal(h.ctx.recovery[kind].owner, 'house-a'); assert.equal(h.ctx.recovery[kind].identity, 'member:a');
    assert.ok(h.ctx.recovery[kind].value.snapshot); assert.equal(h.ctx.errors[kind], true);
  }
});

test('full load failure still exposes only the authenticated scope recovery', async () => {
  const h = harness({ api: (url, value) => url.startsWith('/v1/shopping/') ? Promise.reject(fault(503)) : value });
  const saved = { snapshot: { projects: [{ id: 'own-recovery' }] } };
  h.db.set(h.key('design') + '-recovery', saved);
  await h.ctx.load();
  assert.deepEqual(h.ctx.recovery.design.value, saved); assert.equal(h.ctx.recovery.design.identity, 'member:a');
  assert.equal(h.renders.length, 1); assert.equal(h.ctx.homePlants.plants.length, 0); assert.equal(h.ctx.homeDesign.projects.length, 0);
  assert.ok(!h.ctx.snapshot.scope); assert.ok(!h.ctx.homeFood.scope, 'Do not reuse unlabelled old household memory');
});

test('a delayed /me response cannot restore the previous account after B loads', async () => {
  const old = deferred(); let first = true;
  const h = harness({ api: (url, value) => { if (url === '/v1/home-account/me' && first) { first = false; return old.promise; } return value; } });
  const a = h.ctx.load(); h.setMember('b', 'house-b'); await h.ctx.load();
  old.resolve(member('a', 'house-a')); await a;
  assert.equal(h.ctx.account.id, 'b'); assert.equal(h.ctx.user, 'house-b'); assert.equal(h.ctx.snapshot.scope.owner, 'house-b');
  assert.equal(h.calls.filter(row => row.scope.owner === 'house-a').length, 1);
});

test('A network results arriving after household B cannot alter globals or B caches', async () => {
  const old = deferred();
  const h = harness({ api: (url, value, scope) => url.startsWith('/v1/shopping/') && scope.owner === 'house-a' ? old.promise : value });
  const a = h.ctx.load(); await flush(); h.setMember('b', 'house-b'); await h.ctx.load();
  const before = copy([...h.db]); old.resolve({ scope: { owner: 'house-a' }, items: [] }); await a;
  assert.equal(h.ctx.snapshot.scope.owner, 'house-b'); assert.deepEqual([...h.db], before);
  assert.ok(h.writes.every(row => !row.key.includes('house-a')));
});

test('same-household member switch invalidates A even though the user namespace is unchanged', async () => {
  const old = deferred();
  const h = harness({ api: (url, value, scope) => url.startsWith('/v1/shopping/') && scope.identity === 'member:a' ? old.promise : value });
  const a = h.ctx.load(); await flush(); h.setMember('b', 'house-a'); await h.ctx.load();
  const before = copy([...h.db]); old.resolve({ scope: { identity: 'member:a' }, items: [] }); await a;
  assert.equal(h.ctx.homeDesign.scope.identity, 'member:b'); assert.deepEqual([...h.db], before);
  assert.ok(!h.db.has(h.key('design', 'a')));
});

test('two loads for the same member keep only the newest response', async () => {
  const old = deferred();
  const h = harness({ api: (url, value, scope) => url.startsWith('/v1/shopping/') && scope.generation === 1 ? old.promise : value });
  const a = h.ctx.load(); await flush(); await h.ctx.load();
  old.resolve({ scope: { owner: 'house-a', generation: 1 }, items: [] }); await a;
  assert.equal(h.ctx.snapshot.scope.generation, 2); assert.equal(h.ctx.homeDesign.scope.generation, 2);
});

test('same-member supersession during collection preservation cannot overwrite the newer cache', async () => {
  const old = deferred(); let designReads = 0;
  const h = harness({ read: (key, normal) => {
    if (key === 'home-design:house-a:identity:member:a' && ++designReads === 2) return old.promise;
    return normal();
  } });
  const a = h.ctx.load(); await flush(); assert.equal(designReads, 2);
  await h.ctx.load(); assert.equal(h.db.get(h.key('design')).scope.generation, 2);
  old.resolve(null); await a;
  assert.equal(h.db.get(h.key('design')).scope.generation, 2, 'Obsolete load must not rewrite the current identity cache');
});

test('switch during IndexedDB reads stops all later writes and renders from A', async () => {
  const old = deferred(); let held = false;
  const h = harness({ read: (key, normal, ctx) => { if (!held && key.includes('home-design:house-a') && ctx.user === 'house-a') { held = true; return old.promise; } return normal(); } });
  const a = h.ctx.load(); await flush(); assert.equal(held, true);
  h.setMember('b', 'house-b'); await h.ctx.load(); const before = copy([...h.db]);
  old.resolve({ projects: [{ id: 'old-a' }] }); await a;
  assert.deepEqual([...h.db], before); assert.equal(h.ctx.homeDesign.scope.owner, 'house-b');
});

test('an already-started A cache write remains scoped to A and cannot trigger later B writes', async () => {
  const old = deferred(); let held = false;
  const h = harness({ write: (key, _value, ctx) => { if (!held && key.startsWith('home-design:house-a') && ctx.user === 'house-a') { held = true; return old.promise; } } });
  const a = h.ctx.load(); await flush(); assert.equal(held, true);
  h.setMember('b', 'house-b'); await h.ctx.load(); const bCopy = copy(h.db.get(h.key('design')));
  old.resolve(); await a;
  assert.deepEqual(h.db.get(h.key('design')), bCopy); assert.equal(h.ctx.homeDesign.scope.owner, 'house-b');
  assert.equal(h.writes.filter(row => row.ownerAtStart === 'house-a').length, 1);
});

test('obsolete A authentication failure cannot close B session', async () => {
  const old = deferred();
  const h = harness({ api: (url, value, scope) => url.startsWith('/v1/shopping/') && scope.owner === 'house-a' ? old.promise : value });
  const a = h.ctx.load(); await flush(); h.setMember('b', 'house-b'); await h.ctx.load();
  old.reject(fault(401)); await a;
  assert.equal(h.ctx.account.id, 'b'); assert.equal(h.$('app').hidden, false); assert.ok(!h.$('pairDialog').open);
});

test('current authentication failure hides the app without reading offline snapshots', async () => {
  const h = harness({ api: url => { if (url === '/v1/home-account/me') throw fault(401); } });
  await h.ctx.load(); assert.equal(h.reads.length, 0); assert.equal(h.$('app').hidden, true); assert.equal(h.$('pairDialog').open, true);
});

test('fresh unverified session with a failed /me cannot open remembered household caches', async () => {
  const h = harness({ api: () => Promise.reject(fault(503)) }); h.ctx.account = { mode: 'checking' };
  await h.ctx.load(); assert.equal(h.reads.length, 0); assert.equal(h.renders.length, 0);
});

test('switch during failure fallback reads cannot expose A recovery to B', async () => {
  const old = deferred();
  const h = harness({ api: (url, value, scope) => url.startsWith('/v1/shopping/') && scope.owner === 'house-a' ? Promise.reject(fault(503)) : value,
    read: (key, normal) => key.startsWith('home-design:house-a') && key.endsWith('-recovery') ? old.promise : normal() });
  const a = h.ctx.load(); await flush(); h.setMember('b', 'house-b'); await h.ctx.load();
  old.resolve({ snapshot: { projects: [{ id: 'private-a' }] } }); await a;
  assert.equal(h.ctx.homeDesign.scope.owner, 'house-b');
  assert.ok(!h.ctx.recovery.design?.value?.snapshot?.projects?.some(row => row.id === 'private-a'));
});

test('newer quiet load retains busy ownership until it finishes', async () => {
  const old = deferred(), newer = deferred();
  const h = harness({ api: (url, value, scope) => url.startsWith('/v1/shopping/') ? (scope.generation === 1 ? old.promise : newer.promise) : value });
  const a = h.ctx.load(); await flush(); const b = h.ctx.load({ quiet: true }); await flush();
  old.resolve({ items: [] }); await a; assert.equal(h.busy.at(-1), true);
  newer.resolve({ items: [] }); await b; assert.equal(h.busy.at(-1), false);
});

test('malformed collection response restores the scoped cache instead of replacing it', async () => {
  const h = harness({ api: (url, value) => url.startsWith('/v1/home-design/') ? { status: 'READY' } : value });
  const saved = { projects: [{ id: 'valid-own-copy' }] }; h.db.set(h.key('design'), saved);
  await h.ctx.load(); assert.deepEqual(h.ctx.homeDesign, saved); assert.deepEqual(h.db.get(h.key('design')), saved);
});
