// Synthetic DOM and fetch only. No production account, cookie, or CAPTCHA call.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../assets/roxy_home_registration.js'), 'utf8');

function harness({ pathname = '/lista', hash = '#hoy', enabled = true, pending = null, failure = null } = {}) {
  const calls = { reload: 0, requests: [], stored: [], replaced: [], challengeResets: 0 };
  const nodes = {};
  for (const id of ['signupSubmit', 'openSignup', 'signupPanel', 'loginForm', 'signupName', 'signupError',
    'backToLogin', 'loginUsername', 'signupForm', 'signupUsername', 'signupPassword', 'signupPasswordRepeat', 'signupAcknowledged']) {
    nodes[id] = { hidden: id === 'openSignup' || id === 'signupPanel', disabled: id === 'signupSubmit',
      value: '', textContent: '', checked: true, handlers: {}, focus() {},
      addEventListener(name, callback) { this.handlers[name] = callback; } };
  }
  Object.assign(nodes.signupName, { value: ' Synthetic ' });
  Object.assign(nodes.signupUsername, { value: ' synthetic.member ' });
  nodes.signupPassword.value = nodes.signupPasswordRepeat.value = 'synthetic-password-123';
  nodes.signupForm.reset = () => {
    nodes.signupName.value = nodes.signupUsername.value = nodes.signupPassword.value = nodes.signupPasswordRepeat.value = '';
  };
  const location = {
    pathname, search: '', hash,
    get href() { return `https://roxy.test${this.pathname}${this.search}${this.hash}`; },
    replace(target) {
      const next = new URL(target, this.href);
      if (next.pathname !== this.pathname || next.search !== this.search) calls.reload++;
      this.pathname = next.pathname; this.search = next.search; this.hash = next.hash;
      calls.replaced.push(target);
    },
    reload() { calls.reload++; },
  };
  let challenge;
  const context = {
    document: { getElementById: id => nodes[id] }, location,
    localStorage: { setItem: (key, value) => calls.stored.push([key, value]) },
    history: { replaceState(_state, _title, target) {
      const next = new URL(target, location.href);
      location.pathname = next.pathname; location.search = next.search; location.hash = next.hash;
      calls.replaced.push(target);
    } },
    window: { turnstile: {
      render(_selector, options) { challenge = options; return 'synthetic-widget'; },
      reset() { calls.challengeResets++; challenge?.callback(''); },
    } },
    async fetch(url, options) {
      if (url.endsWith('/registration')) return { ok: true, json: async () => ({ enabled, site_key: 'synthetic', notice_version: '2026-09-06' }) };
      calls.requests.push({ url, options });
      if (pending) await pending;
      if (failure) return { ok: false, json: async () => ({ detail: failure }) };
      return { ok: true, json: async () => ({ storage_user_id: 'synthetic-household' }) };
    },
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  return { context, nodes, calls, ready: () => new Promise(resolve => setImmediate(resolve)),
    open: () => nodes.openSignup.handlers.click(),
    solve: () => challenge.callback('verified-synthetic-token'),
    submit: () => nodes.signupForm.handlers.submit({ preventDefault() {} }) };
}

for (const pathname of ['/home', '/lista']) {
  for (const hash of ['#hoy', '#recetas']) {
    test(`registration enters a fresh authenticated document from ${pathname}${hash}`, async () => {
      const h = harness({ pathname, hash });
      await h.ready(); await h.open(); h.solve(); await h.submit();
      assert.equal(h.calls.requests.length, 1);
      assert.equal(h.calls.reload, 1, 'Fragment navigation retains the signed-out document');
      assert.equal(h.context.location.pathname, pathname);
      assert.equal(h.context.location.hash, '#hoy');
      assert.equal(h.nodes.signupPassword.value, '');
      assert.deepEqual(h.calls.stored, [['roxyShoppingUser', 'synthetic-household']]);
      assert.ok(h.calls.replaced.every(url => !url.includes('synthetic')));
    });
  }
}

test('closed registration hides its entry and never submits without a challenge', async () => {
  const h = harness({ enabled: false });
  await h.ready(); await h.open(); await h.submit();
  assert.equal(h.nodes.openSignup.hidden, true);
  assert.equal(h.nodes.signupPanel.hidden, true);
  assert.equal(h.calls.requests.length, 0);
});

test('mismatched passwords remain editable before any signup request', async () => {
  const h = harness(); await h.ready(); await h.open(); h.solve();
  h.nodes.signupPasswordRepeat.value = 'different-password';
  await h.submit();
  assert.equal(h.calls.requests.length, 0);
  assert.match(h.nodes.signupError.textContent, /no coinciden/);
  assert.equal(h.calls.reload, 0);
});

test('repeated taps create only one pending registration', async () => {
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  const h = harness({ pending }); await h.ready(); await h.open(); h.solve();
  const first = h.submit(); await h.submit();
  assert.equal(h.calls.requests.length, 1);
  assert.equal(h.nodes.signupSubmit.disabled, true);
  release(); await first;
  assert.equal(h.calls.reload, 1);
});

test('a rejected signup preserves fields and requires a fresh challenge', async () => {
  const h = harness({ failure: 'La demo alcanzó su capacidad de registro.' });
  await h.ready(); await h.open(); h.solve(); await h.submit();
  assert.equal(h.calls.reload, 0);
  assert.equal(h.calls.stored.length, 0);
  assert.match(h.nodes.signupError.textContent, /capacidad/);
  assert.equal(h.nodes.signupPassword.value, 'synthetic-password-123');
  assert.equal(h.nodes.signupSubmit.disabled, true);
  assert.equal(h.calls.challengeResets, 1);
  await h.submit(); assert.equal(h.calls.requests.length, 1);
  h.solve(); await h.submit(); assert.equal(h.calls.requests.length, 2);
});
