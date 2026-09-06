(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let config = null, widget = null, token = '', submitting = false;
  const setToken = value => { token = value || ''; $('signupSubmit').disabled = !token || submitting; };
  async function configuration() {
    try {
      const response = await fetch('/v1/home-account/registration', {cache:'no-store', credentials:'same-origin'});
      if (!response.ok) return;
      config = await response.json();
      $('openSignup').hidden = !config.enabled;
    } catch (_) { /* Existing login is still usable without registration. */ }
  }
  async function openSignup() {
    if (!config?.enabled) return;
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
    $('signupPanel').hidden = true; $('loginForm').hidden = false;
    $('openSignup').hidden = !config?.enabled; $('loginUsername').focus();
  });
  $('signupForm').addEventListener('submit', async event => {
    event.preventDefault();
    if (submitting || !token) return;
    if ($('signupPassword').value !== $('signupPasswordRepeat').value) {
      $('signupError').textContent = 'Las contraseñas no coinciden.'; return;
    }
    submitting = true; $('signupSubmit').disabled = true;
    $('signupError').textContent = '';
    try {
      const response = await fetch('/v1/home-account/register', {method:'POST', credentials:'same-origin',
        headers:{'Content-Type':'application/json'}, body:JSON.stringify({
          username:$('signupUsername').value.trim(), display_name:$('signupName').value.trim(),
          password:$('signupPassword').value, verification_token:token,
          acknowledged:$('signupAcknowledged').checked, notice_version:config.notice_version
        })});
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Revisa los datos del registro e inténtalo de nuevo.');
      $('signupForm').reset();
      localStorage.setItem('roxyShoppingUser', result.storage_user_id);
      // A full navigation discards the previous household's in-memory UI.
      location.replace(`${location.pathname}#hoy`);
    } catch (error) {
      $('signupError').textContent = error.message;
      setToken('');
      if (widget !== null) window.turnstile?.reset(widget);
    } finally { submitting = false; $('signupSubmit').disabled = !token; }
  });
  configuration();
})();
