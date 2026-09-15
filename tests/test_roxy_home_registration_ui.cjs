// Synthetic DOM and fetch only. No production account, cookie, or CAPTCHA call.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../assets/roxy_home_registration.js'), 'utf8');

const recoveryCodes = () => Array.from({length:8},(_,i)=>`${String(i+1).padStart(8,'0')}-AAAAAAAA-BBBBBBBB-CCCCCCCC`);
function harness({ pathname = '/lista', hash = '#hoy', enabled = true, pending = null, failure = null, codeConfirmation = true, missingRecovery = false, networkFailure = false, missingTurnstile = false, manualTimers = false } = {}) {
  const calls = { reload: 0, requests: [], stored: [], replaced: [], challengeResets: 0, challengeRemovals: 0, codeViews: [], recoveryResets: 0, responses: [], focused: [], scrolled: [], scripts: [], timers: new Map(), challenges: [] };
  const nodes = {};
  for (const id of ['signupSubmit', 'openSignup', 'signupPanel', 'loginForm', 'signupName', 'signupError',
    'backToLogin', 'loginUsername', 'loginError', 'loginForgotButton', 'signupStatus', 'signupRetryChallenge', 'signupForm', 'signupUsername', 'signupPassword', 'signupPasswordRepeat', 'signupAcknowledged']) {
    nodes[id] = { hidden: id === 'openSignup' || id === 'signupPanel', disabled: id === 'signupSubmit',
      value: '', textContent: '', checked: true, handlers: {}, attributes: {},
      focus() { calls.focused.push(id); }, scrollIntoView() { calls.scrolled.push(id); },
      setAttribute(name, value) { this.attributes[name] = String(value); },
      removeAttribute(name) { delete this.attributes[name]; },
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
  let challenge, timerSequence = 0;
  const turnstile = {
    render(_selector, options) { challenge = options; calls.challenges.push(options); return 'synthetic-widget'; },
    reset() { calls.challengeResets++; challenge?.callback(''); },
    remove() { calls.challengeRemovals++; },
  };
  const context = {
    document: { getElementById: id => nodes[id],
      createElement() { return {removed:false, remove() { this.removed = true; }}; },
      head: {append(script) { calls.scripts.push(script); }} }, location, AbortController,
    setTimeout(callback, delay) {
      const id = manualTimers ? ++timerSequence : setTimeout(() => { calls.timers.delete(id); callback(); }, delay);
      calls.timers.set(id, {callback, delay}); return id;
    },
    clearTimeout(id) { calls.timers.delete(id); if (!manualTimers) clearTimeout(id); },
    localStorage: { setItem: (key, value) => calls.stored.push([key, value]) },
    history: { replaceState(_state, _title, target) {
      const next = new URL(target, location.href);
      location.pathname = next.pathname; location.search = next.search; location.hash = next.hash;
      calls.replaced.push(target);
    } },
    window: { handlers:{}, addEventListener(name,fn) { this.handlers[name]=fn; }, ...(missingTurnstile ? {} : {turnstile}) },
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
    challenge: () => challenge,
    retry: () => nodes.signupRetryChallenge.handlers.click(),
    loadChallenge: () => { context.window.turnstile = turnstile; calls.scripts.at(-1).onload(); },
    fireTimer: delay => { const found = [...calls.timers.entries()].find(([, timer]) => timer.delay === delay); assert.ok(found, `No ${delay}ms timer`); calls.timers.delete(found[0]); found[1].callback(); },
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
  assert.equal(h.nodes.signupSubmit.disabled, false);
  assert.equal(h.nodes.signupRetryChallenge.hidden, false);
  assert.equal(h.calls.challengeResets, 0);
  await h.submit(); assert.equal(h.calls.requests.length, 1);
  h.nodes.signupPassword.value=h.nodes.signupPasswordRepeat.value='synthetic-password-123';
  h.retry(); await h.ready();
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

for (const [field,value,message] of [
  ['signupName','   ',/nombre/], ['signupName','x'.repeat(65),/nombre/],
  ['signupUsername','ab',/usuario/], ['signupUsername','x'.repeat(65),/usuario/],
  ['signupUsername','Mi usuario',/sin espacios/], ['signupUsername','válido',/sin espacios/],
  ['signupPassword','short',/12 y 128/], ['signupPassword','x'.repeat(129),/12 y 128/],
  ['signupPasswordRepeat','different-password',/no coinciden/],
]) {
  test(`invalid ${field} is explained and focused without dispatch or erasing input (${value.length} characters)`,async()=>{
    const h=harness();await h.ready();await h.open();h.nodes[field].value=value;
    await h.submit();
    assert.equal(h.calls.requests.length,0);assert.equal(h.nodes.signupSubmit.disabled,false);
    assert.match(h.nodes.signupError.textContent,message);assert.equal(h.nodes[field].value,value);
    assert.equal(h.calls.focused.at(-1),field);assert.equal(h.nodes[field].attributes['aria-invalid'],'true');
    assert.equal(h.calls.scrolled.at(-1),'signupError');
  });
}

test('consent is explicitly required before CAPTCHA or registration dispatch',async()=>{
  const h=harness();await h.ready();await h.open();h.nodes.signupAcknowledged.checked=false;
  await h.submit();assert.equal(h.calls.requests.length,0);assert.match(h.nodes.signupError.textContent,/Confirma que tienes al menos 18/);
  assert.equal(h.calls.focused.at(-1),'signupAcknowledged');assert.equal(h.nodes.signupSubmit.disabled,false);
});

test('pressing create before CAPTCHA explains that no account exists and exposes retry',async()=>{
  const h=harness();await h.ready();await h.open();
  assert.equal(h.nodes.signupSubmit.disabled,false);assert.equal(h.nodes.loginForgotButton.hidden,true);
  await h.submit();assert.equal(h.calls.requests.length,0);assert.match(h.nodes.signupError.textContent,/Todavía no se ha creado tu cuenta/);
  assert.equal(h.nodes.signupRetryChallenge.hidden,false);assert.equal(h.nodes.signupPassword.value,'synthetic-password-123');
  h.solve();assert.equal(h.nodes.signupError.textContent,'');assert.match(h.nodes.signupStatus.textContent,/Comprobación lista/);
  assert.equal(h.nodes.signupRetryChallenge.hidden,true);
});

test('submission has visible progress and created confirmation while codes are pending',async()=>{
  let release,confirm;const h=harness({pending:new Promise(resolve=>release=resolve),codeConfirmation:new Promise(resolve=>confirm=resolve)});
  await h.ready();await h.open();h.solve();const submit=h.submit();
  assert.equal(h.nodes.signupSubmit.disabled,true);assert.equal(h.nodes.signupSubmit.textContent,'Creando tu hogar…');
  assert.equal(h.nodes.signupForm.attributes['aria-busy'],'true');assert.match(h.nodes.signupStatus.textContent,/Creando tu hogar privado/);
  release();await h.ready();assert.equal(h.nodes.signupSubmit.textContent,'Cuenta creada');assert.match(h.nodes.signupStatus.textContent,/Tu cuenta ya está creada/);
  assert.equal(h.calls.reload,0);confirm(true);await submit;assert.equal(h.calls.reload,1);
  assert.equal(h.nodes.signupForm.attributes['aria-busy'],'false');
});

test('password reaches signup byte for byte without trimming and identity fields are trimmed',async()=>{
  const h=harness();await h.ready();await h.open();h.solve();
  const password='  exact password 123  ';h.nodes.signupPassword.value=h.nodes.signupPasswordRepeat.value=password;
  await h.submit();const sent=JSON.parse(h.calls.requests[0].options.body);
  assert.equal(sent.password,password);assert.equal(sent.username,'synthetic.member');assert.equal(sent.display_name,'Synthetic');
});

for (const callback of ['expired-callback','error-callback','timeout-callback']) {
  test(`${callback} gives actionable feedback without preventing a create-button explanation`,async()=>{
    const h=harness();await h.ready();await h.open();h.solve();h.challenge()[callback]();
    assert.equal(h.nodes.signupSubmit.disabled,false);assert.equal(h.nodes.signupRetryChallenge.hidden,false);
    assert.ok(h.nodes.signupError.textContent.length>0);await h.submit();assert.equal(h.calls.requests.length,0);
  });
}

test('retry renders a fresh challenge and ignores callbacks from the removed widget',async()=>{
  const h=harness();await h.ready();await h.open();const old=h.challenge();h.retry();await h.ready();
  assert.equal(h.calls.challengeRemovals,1);assert.equal(h.calls.challenges.length,2);
  old.callback('stale-token');old['error-callback']();await h.submit();assert.equal(h.calls.requests.length,0);
  h.solve();await h.submit();assert.equal(h.calls.requests.length,1);
});

test('returning to login ignores late challenge callbacks and restores recovery access',async()=>{
  const h=harness();await h.ready();await h.open();const old=h.challenge();h.nodes.backToLogin.handlers.click();
  const message=h.nodes.signupStatus.textContent;old.callback('late-token');old['expired-callback']();
  assert.equal(h.nodes.signupStatus.textContent,message);assert.equal(h.nodes.loginForgotButton.hidden,false);
  assert.equal(h.nodes.loginForm.hidden,false);assert.equal(h.nodes.signupPanel.hidden,true);
  await h.open();h.nodes.signupPassword.value=h.nodes.signupPasswordRepeat.value='synthetic-password-123';
  await h.submit();assert.equal(h.calls.requests.length,0);
});

test('a stalled challenge script has a deadline and can be retried without losing fields',async()=>{
  const h=harness({missingTurnstile:true,manualTimers:true});await h.ready();const opening=h.open();
  assert.equal(h.nodes.signupSubmit.disabled,false);assert.match(h.nodes.signupStatus.textContent,/Cargando/);
  h.fireTimer(12000);await opening;assert.equal(h.calls.scripts[0].removed,true);
  assert.match(h.nodes.signupError.textContent,/tardando demasiado/);assert.equal(h.nodes.signupRetryChallenge.hidden,false);
  assert.equal(h.nodes.signupName.value,' Synthetic ');h.retry();h.loadChallenge();await h.ready();
  assert.equal(h.calls.scripts.length,2);assert.match(h.nodes.signupStatus.textContent,/Completa la comprobación/);
  h.solve();await h.submit();assert.equal(h.calls.requests.length,1);assert.equal(h.calls.timers.size,0);
});

test('challenge script failure remains retryable and a late load after close cannot reopen it',async()=>{
  const h=harness({missingTurnstile:true,manualTimers:true});await h.ready();const opening=h.open();
  h.calls.scripts[0].onerror();await opening;assert.match(h.nodes.signupError.textContent,/No se pudo cargar/);
  h.retry();const script=h.calls.scripts.at(-1),lateLoad=script.onload;
  h.nodes.backToLogin.handlers.click();lateLoad();await h.ready();
  assert.equal(script.removed,true);assert.equal(h.calls.challenges.length,0);assert.equal(h.nodes.signupPanel.hidden,true);
  assert.equal(h.calls.timers.size,0);
});

test('registration waits thirty seconds then reports uncertainty without automatically creating again',async()=>{
  let release;const h=harness({manualTimers:true,pending:new Promise(resolve=>release=resolve)});
  await h.ready();await h.open();h.solve();const submit=h.submit();
  assert.ok([...h.calls.timers.values()].some(timer=>timer.delay===30000));h.fireTimer(30000);await submit;
  assert.equal(h.calls.requests.length,1);assert.equal(h.calls.requests[0].options.signal.aborted,true);
  assert.match(h.nodes.signupError.textContent,/No pudimos confirmar/);assert.equal(h.nodes.signupSubmit.disabled,false);
  assert.equal(h.nodes.signupRetryChallenge.hidden,false);release();await h.ready();
  assert.equal(h.calls.reload,0);assert.equal(h.calls.codeViews.length,0);assert.ok(h.calls.responses[0].recovery_codes.every(value=>value===''));
});
