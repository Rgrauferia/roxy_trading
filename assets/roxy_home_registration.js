(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let config = null, widget = null, token = '', submitting = false, generation = 0, operation = null, accountCreated = false;
  let challengeGeneration = 0, challengeLoad = null, challengeError = false;
  const fields = ['signupName', 'signupUsername', 'signupPassword', 'signupPasswordRepeat', 'signupAcknowledged'];
  const status = message => { $('signupStatus').textContent = message; };
  const renderBusy = () => {
    $('signupSubmit').disabled = submitting || accountCreated;
    $('signupSubmit').textContent = accountCreated ? 'Cuenta creada' : submitting ? 'Creando tu hogar…' : 'Crear mi hogar privado';
    $('signupForm').setAttribute('aria-busy', String(submitting));
  };
  const showError = (message, field = null, isChallenge = false) => {
    challengeError = isChallenge;
    $('signupError').textContent = message;
    if (field) { $(field).setAttribute('aria-invalid', 'true'); $(field).focus(); }
    else $('signupError').focus();
    $('signupError').scrollIntoView?.({block:'nearest'});
  };
  const clearError = () => {
    challengeError = false; $('signupError').textContent = '';
    fields.forEach(id => $(id).removeAttribute('aria-invalid'));
  };
  const setToken = value => { token = typeof value === 'string' ? value : ''; renderBusy(); };
  const clearPasswords = () => { $('signupPassword').value = ''; $('signupPasswordRepeat').value = ''; };
  function stopChallenge() {
    challengeGeneration++; challengeLoad?.cancel(); challengeLoad = null;
    if (widget !== null) window.turnstile?.remove?.(widget);
    widget = null; setToken('');
  }
  const showLogin = message => {
    stopChallenge();
    $('signupPanel').hidden = true; $('loginForm').hidden = false; $('openSignup').hidden = !config?.enabled;
    $('loginForgotButton').hidden = false;
    if ($('loginError')) $('loginError').textContent = message || '';
    $('loginUsername').focus();
  };
  const cancel = () => {
    generation++; operation?.cancel(); operation = null; stopChallenge(); clearPasswords();
    window.RoxyHomeRecovery?.reset();
  };
  async function configuration() {
    try {
      const response = await fetch('/v1/home-account/registration', {cache:'no-store', credentials:'same-origin'});
      if (!response.ok) return;
      config = await response.json();
      $('openSignup').hidden = !config.enabled;
    } catch (_) { /* Existing login is still usable without registration. */ }
  }
  async function refreshChallenge() {
    stopChallenge();
    const ticket = challengeGeneration;
    const current = () => ticket === challengeGeneration && !$('signupPanel').hidden && !accountCreated;
    $('signupRetryChallenge').hidden = true; clearError();
    status('Cargando la comprobación de seguridad… Puedes ir completando tus datos.');
    try {
      if (!window.turnstile) await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        let settled = false, timer;
        const finish = error => {
          if (settled) return; settled = true; clearTimeout(timer);
          script.onload = script.onerror = null;
          if (error) script.remove();
          if (challengeLoad === loading) challengeLoad = null;
          if (error) reject(error); else resolve();
        };
        const loading = {cancel:() => finish(new Error('cancelled'))}; challengeLoad = loading;
        script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
        script.async = true;
        script.onload = () => finish(window.turnstile?.render ? null : new Error('No se pudo iniciar la comprobación de seguridad. Pulsa «Reintentar comprobación».'));
        script.onerror = () => finish(new Error('No se pudo cargar la comprobación de seguridad. Revisa tu conexión y pulsa «Reintentar comprobación».'));
        timer = setTimeout(() => finish(new Error('La comprobación de seguridad está tardando demasiado. Pulsa «Reintentar comprobación».')), 12000);
        document.head.append(script);
      });
      if (!current()) return;
      status('Completa la comprobación de seguridad para crear tu hogar.');
      widget = window.turnstile.render('#signupChallenge', {
        sitekey:config.site_key, action:'home_signup', language:'es',
        callback:value => {
          if (!current()) return;
          setToken(value);
          if (token) {
            if (challengeError) clearError();
            $('signupRetryChallenge').hidden = true;
            if (!submitting) status('Comprobación lista. Revisa tus datos y pulsa «Crear mi hogar privado».');
          }
        },
        'expired-callback':() => {
          if (!current()) return;
          setToken(''); $('signupRetryChallenge').hidden = false;
          if (!submitting) { status('La comprobación de seguridad caducó.'); showError('Repite la comprobación de seguridad antes de crear tu hogar.', null, true); }
        },
        'error-callback':() => {
          if (!current()) return;
          setToken(''); $('signupRetryChallenge').hidden = false;
          if (!submitting) { status('La comprobación de seguridad no se completó.'); showError('No se pudo verificar el registro. Pulsa «Reintentar comprobación».', null, true); }
        },
        'timeout-callback':() => {
          if (!current()) return;
          setToken(''); $('signupRetryChallenge').hidden = false;
          if (!submitting) { status('La comprobación de seguridad necesita otro intento.'); showError('Se agotó el tiempo de la comprobación. Pulsa «Reintentar comprobación».', null, true); }
        }
      });
    } catch (error) {
      if (!current()) return;
      status('La comprobación de seguridad no está lista.'); $('signupRetryChallenge').hidden = false;
      showError(error.message, null, true);
    }
  }
  async function openSignup() {
    if (!config?.enabled || submitting) return;
    if (accountCreated) { showLogin('Tu cuenta ya se creó. Inicia sesión con tu contraseña y genera códigos nuevos desde Seguridad si los necesitas.'); return; }
    $('signupPanel').hidden = false; $('loginForm').hidden = true; $('openSignup').hidden = true;
    $('loginForgotButton').hidden = true;
    $('signupName').focus(); renderBusy();
    await refreshChallenge();
  }
  $('openSignup').addEventListener('click', openSignup);
  $('signupRetryChallenge').addEventListener('click', () => { if (!submitting && !accountCreated) void refreshChallenge(); });
  $('backToLogin').addEventListener('click', () => {
    const uncertain = submitting; cancel();
    showLogin(uncertain ? 'Si el registro llegó a completarse, puedes acceder con el usuario y contraseña que elegiste. Después podrás generar códigos desde Seguridad.' : '');
  });
  $('signupForm').addEventListener('submit', async event => {
    event.preventDefault();
    if (submitting || accountCreated) return;
    clearError();
    if (!config?.enabled) { showError('El registro no está disponible ahora. Recarga la página para volver a comprobarlo.'); return; }
    const username = $('signupUsername').value.trim(), displayName = $('signupName').value.trim();
    let password = $('signupPassword').value;
    if (displayName.length < 1 || displayName.length > 64) { showError('Escribe tu nombre, entre 1 y 64 caracteres.', 'signupName'); return; }
    if (!/^[a-zA-Z0-9_.@-]{3,64}$/.test(username)) { showError('Elige un usuario de 3 a 64 caracteres: letras, números, punto, guion, guion bajo o @, sin espacios.', 'signupUsername'); return; }
    if (password.length < 12 || password.length > 128) { showError('La contraseña debe tener entre 12 y 128 caracteres.', 'signupPassword'); return; }
    if (password !== $('signupPasswordRepeat').value) { showError('Las contraseñas no coinciden. Repite exactamente la misma contraseña.', 'signupPasswordRepeat'); return; }
    if (!$('signupAcknowledged').checked) { showError('Confirma que tienes al menos 18 años y que has leído la privacidad y los límites de la demo.', 'signupAcknowledged'); return; }
    if (!token) {
      showError('Todavía no se ha creado tu cuenta. Completa la comprobación de seguridad; si no aparece, pulsa «Reintentar comprobación».', null, true);
      $('signupRetryChallenge').hidden = false; return;
    }
    submitting = true; renderBusy();
    status('Creando tu hogar privado… Espera la confirmación antes de salir.');
    const ticket = ++generation;
    const payload = {username,display_name:displayName,password,
      verification_token:token,acknowledged:true,notice_version:config.notice_version};
    password = '';
    clearPasswords(); setToken('');
    const controller = new AbortController(); let timer, rejectWait;
    const timeout = new Promise((_,reject) => { rejectWait = reject; timer = setTimeout(() => { controller.abort(); reject(new Error('registration-timeout')); },30000); });
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
      accountCreated = true; renderBusy(); status('Tu cuenta ya está creada. Guarda tus códigos de recuperación para continuar.');
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
      if (accountCreated) {
        showLogin('Tu cuenta ya está creada. Inicia sesión con tu contraseña; puedes generar códigos nuevos desde Seguridad.');
      } else {
        status(error.registrationRejected ? 'El registro no se completó. Revisa el mensaje y vuelve a intentarlo.' : 'No recibimos la confirmación del registro.');
        showError(error.registrationRejected ? error.message : 'No pudimos confirmar el registro. Si tu cuenta se creó, puedes iniciar sesión con tu contraseña y generar códigos nuevos desde Seguridad.');
        // A rejected or uncertain POST never retries automatically.
        setToken(''); $('signupRetryChallenge').hidden = false;
      }
    } finally {
      clearTimeout(timer); payload.password = payload.verification_token = '';
      if (Array.isArray(result?.recovery_codes)) result.recovery_codes.fill('');
      if (operation === request) operation = null;
      submitting = false; renderBusy();
    }
  });
  window.addEventListener('pagehide',cancel);
  renderBusy(); configuration();
})();
