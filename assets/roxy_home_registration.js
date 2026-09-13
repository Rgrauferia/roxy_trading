(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let config = null, widget = null, token = '', submitting = false, generation = 0, operation = null, accountCreated = false;
  const setToken = value => { token = value || ''; $('signupSubmit').disabled = !token || submitting; };
  const clearPasswords = () => { $('signupPassword').value = ''; $('signupPasswordRepeat').value = ''; };
  const showLogin = message => {
    $('signupPanel').hidden = true; $('loginForm').hidden = false; $('openSignup').hidden = !config?.enabled;
    if ($('loginError')) $('loginError').textContent = message || '';
    $('loginUsername').focus();
  };
  const cancel = () => { generation++; operation?.cancel(); operation = null; clearPasswords(); setToken(''); window.RoxyHomeRecovery?.reset(); };
  async function configuration() {
    try {
      const response = await fetch('/v1/home-account/registration', {cache:'no-store', credentials:'same-origin'});
      if (!response.ok) return;
      config = await response.json();
      $('openSignup').hidden = !config.enabled;
    } catch (_) { /* Existing login is still usable without registration. */ }
  }
  async function openSignup() {
    if (!config?.enabled || submitting) return;
    if (accountCreated) { showLogin('Tu cuenta ya se creó. Inicia sesión con tu contraseña y genera códigos nuevos desde Seguridad si los necesitas.'); return; }
    $('signupPanel').hidden = false;
    $('loginForm').hidden = true;
    $('openSignup').hidden = true;
    $('signupName').focus();
    $('signupError').textContent = '';
    try {
      if (!window.turnstile) await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
        script.async = true;
        script.onload = resolve;
        script.onerror = () => { script.remove(); reject(new Error('No se pudo cargar la comprobación de seguridad. Inténtalo de nuevo.')); };
        document.head.append(script);
      });
      if (widget === null) widget = window.turnstile.render('#signupChallenge', {
        sitekey:config.site_key, action:'home_signup', language:'es',
        callback:setToken, 'expired-callback':() => setToken(''),
        'error-callback':() => { setToken(''); $('signupError').textContent = 'No se pudo verificar el registro. Vuelve a intentarlo.'; }
      });
      else window.turnstile.reset(widget);
    } catch (error) { $('signupError').textContent = error.message; }
  }
  $('openSignup').addEventListener('click', openSignup);
  $('backToLogin').addEventListener('click', () => {
    const uncertain = submitting; cancel();
    showLogin(uncertain ? 'Si el registro llegó a completarse, puedes acceder con el usuario y contraseña que elegiste. Después podrás generar códigos desde Seguridad.' : '');
  });
  $('signupForm').addEventListener('submit', async event => {
    event.preventDefault();
    if (submitting || !token || accountCreated) return;
    if ($('signupPassword').value !== $('signupPasswordRepeat').value) {
      $('signupError').textContent = 'Las contraseñas no coinciden.'; return;
    }
    if ($('signupPassword').value.length < 12 || $('signupPassword').value.length > 128) {
      $('signupError').textContent = 'La contraseña debe tener entre 12 y 128 caracteres.'; return;
    }
    submitting = true; $('signupSubmit').disabled = true;
    $('signupError').textContent = '';
    const ticket = ++generation, username = $('signupUsername').value.trim();
    const payload = {username,display_name:$('signupName').value.trim(),password:$('signupPassword').value,
      verification_token:token,acknowledged:$('signupAcknowledged').checked,notice_version:config.notice_version};
    clearPasswords(); setToken('');
    const controller = new AbortController(); let timer, rejectWait;
    const timeout = new Promise((_,reject) => { rejectWait = reject; timer = setTimeout(() => { controller.abort(); reject(new Error('No pudimos confirmar el registro. Si tu cuenta se creó, puedes iniciar sesión y generar códigos desde Seguridad.')); },12000); });
    const request = {cancel:() => { controller.abort(); clearTimeout(timer); rejectWait(new Error('cancelled')); }}; operation = request;
    let result;
    try {
      result = await Promise.race([fetch('/v1/home-account/register', {method:'POST', credentials:'same-origin',cache:'no-store',signal:controller.signal,
        headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).then(async response => {
        const value = await response.json();
        if (ticket !== generation || controller.signal.aborted) { if (Array.isArray(value?.recovery_codes)) value.recovery_codes.fill(''); return null; }
        if (!response.ok) throw Object.assign(new Error(typeof value.detail === 'string' ? value.detail : 'Revisa los datos del registro e inténtalo de nuevo.'),{registrationRejected:true});
        return value;
      }),timeout]);
      clearTimeout(timer); if (operation === request) operation = null;
      if (ticket !== generation || !result) return;
      accountCreated = true;
      $('signupForm').reset();
      $('loginUsername').value = result.username || username;
      if (!window.RoxyHomeRecovery?.showCodes || !Array.isArray(result.recovery_codes)) {
        showLogin('Tu cuenta se creó, pero no pudimos mostrar sus códigos. Inicia sesión con tu contraseña y genera un juego nuevo desde Seguridad.'); return;
      }
      const confirmed = await window.RoxyHomeRecovery.showCodes({username:result.username || username,recovery_codes:result.recovery_codes});
      if (ticket !== generation) return;
      if (!confirmed) { showLogin('Tu cuenta ya está creada. Inicia sesión con tu contraseña; si no guardaste los códigos, genera otros desde Seguridad.'); return; }
      localStorage.setItem('roxyShoppingUser', result.storage_user_id);
      // A full navigation discards the previous household's in-memory UI.
      history.replaceState(null, '', `${location.pathname}#hoy`);
      location.reload();
    } catch (error) {
      if (ticket !== generation) return;
      $('signupError').textContent = error.registrationRejected ? error.message : 'No pudimos confirmar el registro. Si tu cuenta se creó, puedes iniciar sesión con tu contraseña y generar códigos nuevos desde Seguridad.';
      setToken('');
      if (widget !== null) window.turnstile?.reset(widget);
    } finally {
      clearTimeout(timer); payload.password = payload.verification_token = '';
      if (Array.isArray(result?.recovery_codes)) result.recovery_codes.fill('');
      if (operation === request) operation = null;
      submitting = false; $('signupSubmit').disabled = !token || accountCreated;
    }
  });
  window.addEventListener('pagehide',cancel);
  configuration();
})();
