// Synthetic DOM and fetch only. No production account, cookie, or CAPTCHA call.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../assets/roxy_home_registration.js'), 'utf8');

const recoveryCodes = () => Array.from({length:8},(_,i)=>`${String(i+1).padStart(8,'0')}-AAAAAAAA-BBBBBBBB-CCCCCCCC`);
function harness({ pathname = '/lista', hash = '#hoy', enabled = true, pending = null, failure = null, codeConfirmation = true, missingRecovery = false, networkFailure = false } = {}) {
  const calls = { reload: 0, requests: [], stored: [], replaced: [], challengeResets: 0, codeViews: [], recoveryResets: 0, responses: [] };
  const nodes = {};
  for (const id of ['signupSubmit', 'openSignup', 'signupPanel', 'loginForm', 'signupName', 'signupError',
    'backToLogin', 'loginUsername', 'loginError', 'signupForm', 'signupUsername', 'signupPassword', 'signupPasswordRepeat', 'signupAcknowledged']) {
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
    document: { getElementById: id => nodes[id] }, location, AbortController, setTimeout, clearTimeout,
    localStorage: { setItem: (key, value) => calls.stored.push([key, value]) },
    history: { replaceState(_state, _title, target) {
      const next = new URL(target, location.href);
      location.pathname = next.pathname; location.search = next.search; location.hash = next.hash;
      calls.replaced.push(target);
    } },
    window: { handlers:{}, addEventListener(name,fn) { this.handlers[name]=fn; }, turnstile: {
      render(_selector, options) { challenge = options; return 'synthetic-widget'; },
      reset() { calls.challengeResets++; challenge?.callback(''); },
    } },
    async fetch(url, options) {
      if (url.endsWith('/registration')) return { ok: true, json: async () => ({ enabled, site_key: 'synthetic', notice_version: '2026-09-06' }) };
      calls.requests.push({ url, options });
      if (pending) await pending;
      if (networkFailure) throw new TypeError('Network error');
      if (failure) return { ok: false, json: async () => ({ detail: failure }) };
      const response={storage_user_id:'synthetic-household',username:'synthetic.member',recovery_codes:recoveryCodes()}; calls.responses.push(response);
      return { ok: true, json: async () => response };
    },
  };
  // The controller itself is covered by test_home_recovery_ui; this collaborator
  // models the user's explicit confirmation and can remain unresolved here.
  if (!missingRecovery) context.window.RoxyHomeRecovery={
    showCodes(options){calls.codeViews.push(options);return Promise.resolve(codeConfirmation);},reset(){calls.recoveryResets++;},
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
      assert.equal(h.calls.codeViews.length,1);
      assert.ok(h.calls.responses[0].recovery_codes.every(value=>value===''));
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

test('a rejected signup preserves identity fields, clears passwords and requires a fresh challenge', async () => {
  const h = harness({ failure: 'La demo alcanzó su capacidad de registro.' });
  await h.ready(); await h.open(); h.solve(); await h.submit();
  assert.equal(h.calls.reload, 0);
  assert.equal(h.calls.stored.length, 0);
  assert.match(h.nodes.signupError.textContent, /capacidad/);
  assert.equal(h.nodes.signupPassword.value, '');
  assert.equal(h.nodes.signupPasswordRepeat.value, '');
  assert.equal(h.nodes.signupUsername.value, ' synthetic.member ');
  assert.equal(h.nodes.signupSubmit.disabled, true);
  assert.equal(h.calls.challengeResets, 1);
  await h.submit(); assert.equal(h.calls.requests.length, 1);
  h.nodes.signupPassword.value=h.nodes.signupPasswordRepeat.value='synthetic-password-123';
  h.solve(); await h.submit(); assert.equal(h.calls.requests.length, 2);
});

test('registration cannot reload, persist its household or post again while recovery confirmation is pending',async()=>{
  let resolve;const confirmation=new Promise(value=>resolve=value);const h=harness({codeConfirmation:confirmation});
  await h.ready();await h.open();h.solve();const submit=h.submit();await h.ready();
  assert.equal(h.calls.codeViews.length,1);assert.equal(h.calls.reload,0);assert.equal(h.calls.stored.length,0);assert.equal(h.nodes.signupPassword.value,'');
  await h.submit();assert.equal(h.calls.requests.length,1);assert.equal(h.nodes.signupSubmit.disabled,true);
  resolve(true);await submit;assert.equal(h.calls.reload,1);assert.equal(h.calls.stored.length,1);
  assert.ok(h.calls.responses[0].recovery_codes.every(value=>value===''));
});

test('closing the code interstitial leaves login guidance for the created account without a second register request',async()=>{
  const h=harness({codeConfirmation:false});await h.ready();await h.open();h.solve();await h.submit();
  assert.equal(h.calls.reload,0);assert.equal(h.calls.stored.length,0);assert.equal(h.nodes.loginForm.hidden,false);
  assert.match(h.nodes.loginError.textContent,/cuenta ya está creada/);assert.match(h.nodes.loginError.textContent,/Seguridad/);
  assert.equal(h.nodes.loginUsername.value,'synthetic.member');await h.open();h.solve();await h.submit();assert.equal(h.calls.requests.length,1);
  assert.ok(h.calls.responses[0].recovery_codes.every(value=>value===''));
});

test('missing recovery UI does not discard the created account behind an automatic reload',async()=>{
  const h=harness({missingRecovery:true});await h.ready();await h.open();h.solve();await h.submit();
  assert.equal(h.calls.reload,0);assert.equal(h.calls.stored.length,0);assert.match(h.nodes.loginError.textContent,/cuenta se creó/);
  assert.match(h.nodes.loginError.textContent,/códigos/);assert.ok(h.calls.responses[0].recovery_codes.every(value=>value===''));
});

test('registration passwords clear on submission while an unresolved response can still be cancelled',async()=>{
  let resolve;const pending=new Promise(value=>resolve=value),h=harness({pending});await h.ready();await h.open();h.solve();const submit=h.submit();
  assert.equal(h.nodes.signupPassword.value,'');assert.equal(h.nodes.signupPasswordRepeat.value,'');
  h.nodes.backToLogin.handlers.click();await submit;assert.equal(h.calls.requests[0].options.signal.aborted,true);
  resolve();await h.ready();assert.equal(h.calls.reload,0);assert.equal(h.calls.codeViews.length,0);assert.equal(h.calls.stored.length,0);
  assert.ok(h.calls.responses[0].recovery_codes.every(value=>value===''));assert.match(h.nodes.loginError.textContent,/Si el registro llegó a completarse/);
});

test('lost signup response explains manual login and password-based code generation without retrying automatically',async()=>{
  const h=harness({networkFailure:true});await h.ready();await h.open();h.solve();await h.submit();
  assert.equal(h.calls.requests.length,1);assert.match(h.nodes.signupError.textContent,/Si tu cuenta se creó/);assert.match(h.nodes.signupError.textContent,/Seguridad/);
  assert.equal(h.nodes.signupPassword.value,'');assert.equal(h.calls.reload,0);assert.equal(h.calls.codeViews.length,0);
});

test('leaving the document during code confirmation suppresses a late continue',async()=>{
  let resolve;const confirmation=new Promise(value=>resolve=value),h=harness({codeConfirmation:confirmation});await h.ready();await h.open();h.solve();const submit=h.submit();await h.ready();
  h.context.window.handlers.pagehide();resolve(true);await submit;assert.equal(h.calls.reload,0);assert.equal(h.calls.stored.length,0);assert.equal(h.calls.recoveryResets,1);assert.ok(h.calls.responses[0].recovery_codes.every(value=>value===''));
});

test('registration rejects a too-short or oversized password before dispatch',async()=>{
  const h=harness();await h.ready();await h.open();h.solve();
  for(const password of ['short','x'.repeat(129)]){h.nodes.signupPassword.value=h.nodes.signupPasswordRepeat.value=password;await h.submit();assert.match(h.nodes.signupError.textContent,/12 y 128/);}
  assert.equal(h.calls.requests.length,0);
});
