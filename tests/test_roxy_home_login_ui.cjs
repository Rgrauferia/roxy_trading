// No real account, browser cookie, or network access is used in these regressions.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../assets/roxy_list.js'), 'utf8');
const start = source.indexOf('  async function login(event)');
const end = source.indexOf('  function renderAccount()', start);
assert.ok(start >= 0 && end > start, 'The real login handler must be found');
const loginSource = source.slice(start, end);

function harness({ hash = '#hoy', pathname = '/lista', fail = null, pending = null } = {}) {
  const calls = { login: [], reload: 0, load: 0, replaced: [], stored: [] };
  const button = { disabled: false, textContent: 'Entrar' };
  const nodes = {
    loginUsername: { value: '  synthetic.member  ' },
    loginPassword: { value: 'synthetic-password-123' },
    loginError: { textContent: '' },
    pairDialog: { open: true, close() { this.open = false; } },
    app: { hidden: true },
    loginForm: { querySelector: () => button },
  };
  const location = {
    pathname, search: '', hash,
    get href() { return `https://roxy.test${this.pathname}${this.search}${this.hash}`; },
    replace(target) {
      calls.replaced.push(target);
      // Browsers do not reload when only the fragment differs.
      const resolved = new URL(target, this.href);
      if (resolved.pathname !== this.pathname || resolved.search !== this.search) calls.reload++;
      this.pathname = resolved.pathname; this.search = resolved.search; this.hash = resolved.hash;
    },
    reload() { calls.reload++; },
  };
  const context = {
    $: id => nodes[id], account: { mode: 'signed_out' }, user: 'old-household',
    localStorage: { setItem: (key, value) => calls.stored.push([key, value]) },
    history: { replaceState(_state, _unused, target) {
      calls.replaced.push(target);
      const resolved = new URL(target, location.href);
      location.pathname = resolved.pathname; location.search = resolved.search; location.hash = resolved.hash;
    } },
    location,
    window: { RoxyFitness: { clear() {} } },
    async api(endpoint, options) {
      calls.login.push({ endpoint, options });
      if (pending) await pending;
      if (fail) throw fail;
      return { status: 'AUTHENTICATED', mode: 'member', id: 'synthetic-id', storage_user_id: 'synthetic-household' };
    },
    async load() { calls.load++; },
    selectPanel() {},
  };
  vm.createContext(context);
  vm.runInContext(`${loginSource}\nthis.invokeLogin=login;`, context);
  return { context, nodes, calls, button, invoke: () => context.invokeLogin({ preventDefault() {}, currentTarget: nodes.loginForm, submitter: button }) };
}

for (const hash of ['#hoy', '#mascotas', '#ejercicio']) {
  test(`successful login refreshes the authenticated document from ${hash}`, async () => {
    const h = harness({ hash });
    await h.invoke();
    assert.equal(h.calls.login.length, 1);
    assert.equal(h.context.location.hash, '#hoy');
    assert.equal(h.calls.reload, 1,
      'A fragment-only navigation leaves the sign-in dialog and signed-out data unchanged');
    assert.equal(h.nodes.loginPassword.value, '');
    assert.ok(h.calls.replaced.every(target => !target.includes('password') && !target.includes('synthetic.member')));
  });
}

test('wrong credentials remain on the form without pretending to sign in', async () => {
  const h = harness({ fail: new Error('Usuario o contraseña incorrectos') });
  await h.invoke();
  assert.equal(h.calls.reload, 0);
  assert.equal(h.calls.load, 0);
  assert.equal(h.context.account.mode, 'signed_out');
  assert.equal(h.nodes.loginError.textContent, 'Usuario o contraseña incorrectos');
  assert.equal(h.nodes.pairDialog.open, true);
  assert.equal(h.button.disabled, false);
  assert.equal(h.button.textContent, 'Entrar');
  assert.equal(h.nodes.loginPassword.value, 'synthetic-password-123');
});

test('unavailable storage is shown as unavailable, not invalid credentials', async () => {
  const h = harness({ fail: new Error('No se pudieron leer las cuentas. Conservamos el archivo; inténtalo más tarde.') });
  await h.invoke();
  assert.equal(h.calls.reload, 0);
  assert.match(h.nodes.loginError.textContent, /No se pudieron leer las cuentas/);
  assert.equal(h.context.account.mode, 'signed_out');
  assert.equal(h.button.disabled, false);
  assert.equal(h.button.textContent, 'Entrar');
  assert.equal(h.nodes.loginPassword.value, 'synthetic-password-123');
});

test('home entry preserves its pathname and forces a document refresh', async () => {
  const h = harness({ pathname: '/home', hash: '#hoy' });
  await h.invoke();
  assert.equal(h.context.location.pathname, '/home');
  assert.equal(h.calls.replaced[0], '/home#hoy');
  assert.equal(h.calls.reload, 1);
});

test('repeated taps while signing in produce only one request', async () => {
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  const h = harness({ pending });
  const first = h.invoke();
  assert.equal(h.button.disabled, true);
  assert.equal(h.button.textContent, 'Entrando…');
  await h.invoke();
  assert.equal(h.calls.login.length, 1);
  assert.equal(h.calls.reload, 0);
  release();
  await first;
  assert.equal(h.calls.reload, 1);
  assert.equal(h.button.disabled, true, 'Successful navigation remains protected until reload');
});

test('a rejected attempt can be corrected and submitted again', async () => {
  const h = harness({ fail: new Error('Usuario o contraseña incorrectos') });
  await h.invoke();
  await h.invoke();
  assert.equal(h.calls.login.length, 2);
  assert.equal(h.button.disabled, false);
  assert.equal(h.nodes.loginPassword.value, 'synthetic-password-123');
});
