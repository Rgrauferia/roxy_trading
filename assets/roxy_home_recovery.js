/* Home-only recovery. Secrets live only in this dialog until explicit export/close. */
(function (global) {
  'use strict';
  const BASE = '/v1/home-account/recovery';
  const CODE = /^[0-9a-f]{8}(?:-[0-9a-f]{8}){3}$/i;
  let active = null, sequence = 0;
  const clean = value => typeof value === 'string' ? value.trim() : '';
  const normalizedCode = value => { const hex = clean(value).replace(/[\s-]/g,''); return /^[0-9a-f]{32}$/i.test(hex) ? hex.toUpperCase().match(/.{8}/g).join('-') : ''; };
  const validCodes = value => Array.isArray(value) && value.length === 8 && new Set(value).size === 8 && value.every(code => typeof code === 'string' && CODE.test(code));
  const clearCodes = value => { if (Array.isArray(value)) value.fill(''); };
  function create(kind, member = null, resolver = null) {
    active?.dispose();
    const doc = global.document, previousFocus = doc.activeElement, id = `home-recovery-${++sequence}`;
    let closed = false, pending = null, codes = [], resources = new Map(), continueCallback = null, acknowledged = false, bundleProceed = null;
    const listeners = [];
    const el = (tag, className = '', text = null) => { const node = doc.createElement(tag); node.className = className; if (text != null) node.textContent = text; return node; };
    const on = (target, event, callback) => { target.addEventListener(event,callback); listeners.push(() => target.removeEventListener(event,callback)); };
    const current = () => !closed && active === controller && dialog.isConnected !== false && (!member || typeof member.isCurrent !== 'function' || member.isCurrent());
    const dialog = el('dialog','home-recovery'); dialog.setAttribute('aria-labelledby',`${id}-title`);
    const shell = el('section','hr-shell'), header = el('header','hr-header'), title = el('h2'); title.id = `${id}-title`; title.tabIndex = -1;
    const button = (text, className, action) => { const node = el('button',className,text); node.type = 'button'; node.addEventListener('click',() => { if (current() && !node.disabled) action(); }); return node; };
    const close = button('Cerrar','hr-close',() => dispose(false)); header.append(title,close);
    const content = el('div','hr-content'), status = el('p','hr-status'); status.setAttribute('role','status'); status.setAttribute('aria-live','polite');
    const error = el('p','hr-error'); error.setAttribute('role','alert'); error.tabIndex = -1; error.hidden = true;
    shell.append(el('p','hr-eyebrow','ROXY HOME · SEGURIDAD'),header,content,status,error); dialog.append(shell); doc.body.append(dialog);
    function wipeInputs() { dialog.querySelectorAll('input').forEach(input => { if (input.type !== 'checkbox') input.value = ''; else input.checked = false; }); }
    function clearExport() { resources.forEach(timer => clearTimeout(timer)); resources.forEach((_timer,url) => global.URL.revokeObjectURL(url)); resources.clear(); }
    function wipe() { wipeInputs(); content.querySelectorAll('code').forEach(node => { node.textContent = ''; }); codes.fill(''); codes = []; continueCallback = null; acknowledged = false; bundleProceed = null; clearExport(); content.replaceChildren(); }
    // Switching to a password manager must not destroy this one-time bundle.
    // Hide and clear rendered secrets while retaining only this dialog's memory.
    function syncVisibility() {
      if (!current()) { dispose(false); return; }
      content.hidden = Boolean(doc.hidden); status.hidden = Boolean(doc.hidden);
      if (doc.hidden) { wipeInputs(); acknowledged = false; if (bundleProceed) bundleProceed.disabled = true; clearError(); }
      content.querySelectorAll('code').forEach((node,index) => { node.textContent = doc.hidden ? '' : (codes[index] || ''); });
    }
    function dispose(confirmed = false) {
      if (closed) return; closed = true; pending?.cancel(); pending = null;
      wipe(); listeners.splice(0).forEach(remove => remove()); dialog.close?.(); dialog.remove();
      if (active === controller) active = null;
      if (resolver) { const resolve = resolver; resolver = null; resolve(confirmed); }
      if (previousFocus?.isConnected !== false) previousFocus?.focus?.();
    }
    const controller = {dispose:() => dispose(false)}; active = controller;
    function showError(text) { if (!current()) return; error.hidden = false; error.textContent = text; error.focus?.(); }
    function clearError() { error.hidden = true; error.textContent = ''; }
    function busy(value) { shell.setAttribute('aria-busy',String(value)); content.querySelectorAll('input, button').forEach(node => { node.disabled = value; }); }
    function field(name,label,{password=false,autocomplete='off',max=128,min=0}={}) {
      const row = el('label','hr-field'), input = el('input'); input.name = name; input.id = `${id}-${name}`; input.type = password ? 'password' : 'text'; input.autocomplete = autocomplete;
      input.maxLength = max; if (min) input.minLength = min; input.required = true; input.spellcheck = false; input.autocapitalize = 'none';
      row.append(el('span','',label),input); return {row,input};
    }
    function check(label) { const row = el('label','hr-check'), input = el('input'); input.type = 'checkbox'; row.append(input,el('span','',label)); return {row,input}; }
    async function request(path,method,body) {
      if (!current() || pending) return null;
      const operation = {controller:new AbortController(),timer:null}; pending = operation; busy(true); clearError();
      let rejectDeadline;
      const deadline = new Promise((_,reject) => { rejectDeadline = reject; operation.timer = setTimeout(() => { operation.controller.abort(); reject(Object.assign(new Error('timeout'),{name:'TimeoutError'})); },12000); });
      operation.cancel = () => { operation.controller.abort(); clearTimeout(operation.timer); rejectDeadline(Object.assign(new Error('cancelled'),{name:'AbortError'})); };
      try {
        const response = await Promise.race([Promise.resolve().then(() => {
          if (!current() || operation.controller.signal.aborted) throw Object.assign(new Error('cancelled'),{name:'AbortError'});
          return global.fetch(path,{method,cache:'no-store',credentials:'same-origin',signal:operation.controller.signal,
            headers:{Accept:'application/json',...(body ? {'Content-Type':'application/json'} : {}),...(member ? {'X-Roxy-Member-Id':clean(member.id)} : {})},
            ...(body ? {body:JSON.stringify(body)} : {})});
        }).then(async response => {
          let data = {}; try { data = await response.json(); } catch (_) { /* Treat malformed responses as uncertain. */ }
          if (!current() || pending !== operation) { clearCodes(data?.recovery_codes); return null; }
          if (!response.ok) throw Object.assign(new Error('rejected'),{status:response.status});
          return data;
        }),deadline]);
        return current() && pending === operation ? response : null;
      } finally {
        clearTimeout(operation.timer); if (body) Object.keys(body).forEach(key => { body[key] = ''; });
        if (pending === operation) { pending = null; if (current()) busy(false); }
      }
    }
    function exportText(username) { return `Roxy Home — códigos de recuperación\nUsuario: ${username}\n\n${codes.join('\n')}\n\nGuarda este archivo en un lugar privado. Cada restablecimiento invalida todos los códigos anteriores.\nNo compartas estos códigos. No son una clave de administrador ni de otros productos Roxy.\n`; }
    function showBundle(data,{onContinue}={}) {
      wipe(); clearError(); status.textContent = '';
      if (!validCodes(data.recovery_codes) || !clean(data.username)) { clearCodes(data.recovery_codes); showError('No pudimos mostrar los códigos nuevos. Puedes generar otro juego desde Seguridad con tu contraseña actual.'); return false; }
      codes = [...data.recovery_codes]; clearCodes(data.recovery_codes); continueCallback = onContinue;
      const username = clean(data.username).slice(0,64); title.textContent = 'Guarda tus códigos de recuperación';
      content.append(el('p','hr-intro',`Tu cuenta: ${username}. Estos ocho códigos se muestran una sola vez. Permiten recuperar esta cuenta si olvidas tu contraseña.`));
      const list = el('ol','hr-codes'); list.setAttribute('aria-label','Tus ocho códigos de recuperación'); codes.forEach(value => { const item = el('li'); item.append(el('code','',value)); list.append(item); }); content.append(list);
      content.append(el('p','hr-note','Guárdalos en un lugar privado al que puedas acceder fuera de Roxy Home. No los envíes a otras personas. Un restablecimiento invalida todo este juego.'));
      const actions = el('div','hr-actions');
      const copy = button('Copiar códigos','hr-secondary',async() => {
        if (!global.navigator?.clipboard?.writeText) { showError('La copia no está disponible. Puedes seleccionar los códigos o descargar el archivo.'); return; }
        copy.disabled = true; clearError();
        try { await global.navigator.clipboard.writeText(exportText(username)); if (current()) status.textContent = 'Códigos copiados. Guárdalos en un lugar privado; copiar no confirma que ya los conservaste.'; }
        catch (_) { if (current()) showError('No pudimos copiar. Puedes seleccionar los códigos o descargar el archivo.'); }
        finally { if (current()) copy.disabled = false; }
      });
      const download = button('Descargar TXT','hr-secondary',() => {
        clearError(); try {
          const url = global.URL.createObjectURL(new Blob([exportText(username)],{type:'text/plain;charset=utf-8'}));
          const link = el('a'); link.href = url; link.download = 'roxy-home-recovery-codes.txt'; doc.body.append(link); link.click(); link.remove();
          resources.set(url,setTimeout(() => { global.URL.revokeObjectURL(url); resources.delete(url); },2000));
          status.textContent = 'Descarga solicitada. Comprueba que guardaste el archivo antes de continuar.';
        } catch (_) { showError('No pudimos descargar el archivo. Copia los códigos o guárdalos manualmente.'); }
      }); actions.append(copy,download); content.append(actions);
      const saved = check('Ya guardé mis ocho códigos en un lugar privado.'); saved.input.name = 'codes_saved';
      const proceed = button('Ya los guardé · continuar','hr-primary',() => {
        if (!acknowledged || !saved.input.checked) return;
        const callback = continueCallback; dispose(true); if (typeof callback === 'function') callback();
      }); proceed.disabled = true; bundleProceed = proceed;
      saved.input.addEventListener('change',() => { if (current()) { acknowledged = saved.input.checked; proceed.disabled = !acknowledged; } });
      content.append(saved.row,proceed,el('p','hr-footnote','Si cierras sin guardarlos, accede con tu contraseña y genera un juego nuevo desde Seguridad. Los códigos antiguos no se pueden volver a consultar.'));
      syncVisibility(); title.focus?.(); return true;
    }
    async function showManage() {
      title.textContent = 'Recuperación de tu cuenta'; status.textContent = 'Comprobando tus códigos…';
      try {
        const result = await request(BASE,'GET'); if (!result || !current()) return;
        if (typeof result.enabled !== 'boolean' || !Number.isInteger(result.remaining) || result.remaining < 0 || result.remaining > 8) throw new Error('invalid');
        status.textContent = ''; content.replaceChildren();
        content.append(el('p','hr-intro',result.enabled ? `Tienes ${result.remaining} códigos de recuperación disponibles.` : 'No tienes códigos de recuperación vigentes.'));
        if (result.generated_at) { const date = new Date(result.generated_at); if (Number.isFinite(date.getTime())) content.append(el('p','hr-note',`Último juego creado: ${date.toLocaleString('es')}.`)); }
        content.append(el('p','hr-note','Aquí sólo mostramos el estado. Los códigos anteriores no se pueden leer de nuevo. Para crear otro juego necesitas tu contraseña actual.'));
        const form = el('form'), password = field('current_password','Contraseña actual',{password:true,autocomplete:'current-password',max:128});
        const rotate = check(result.enabled ? 'Entiendo que crear códigos nuevos invalida todos los anteriores.' : 'Quiero crear ocho códigos y guardarlos personalmente.'); rotate.input.name = 'confirm_rotation';
        const submit = el('button','hr-primary',result.enabled ? 'Crear códigos nuevos' : 'Activar recuperación'); submit.type = 'submit';
        form.append(password.row,rotate.row,submit); content.append(form);
        form.addEventListener('submit',async event => {
          event.preventDefault(); if (!current() || pending) return;
          if (!password.input.value || password.input.value.length > 128) { showError('Escribe tu contraseña actual.'); return; }
          if (!rotate.input.checked) { showError('Confirma que quieres crear este juego de códigos.'); return; }
          const body = {current_password:password.input.value}; password.input.value = ''; rotate.input.checked = false;
          status.textContent = 'Creando códigos nuevos…';
          try { const created = await request(`${BASE}/codes`,'POST',body); if (created && current()) { status.textContent = ''; showBundle(created); } }
          catch (failure) { if (current()) { status.textContent = ''; showError(failure.status === 401 || failure.status === 403 ? 'No pudimos verificar tu contraseña o sesión. Vuelve a intentarlo con tu cuenta.' : failure.status === 429 ? 'Se alcanzó el límite de intentos. Espera antes de volver a probar.' : 'No pudimos confirmar la creación de códigos. Puedes generar otro juego con tu contraseña actual; el anterior quedará invalidado.'); } }
        });
      } catch (_) { if (current()) { status.textContent = ''; showError('No pudimos consultar el estado. Cierra y vuelve a abrir Seguridad para reintentar.'); } }
    }
    function showReset() {
      title.textContent = 'Recupera el acceso'; content.append(el('p','hr-intro','Necesitas tu nombre de usuario y uno de los códigos que guardaste previamente. No enviamos códigos por correo ni usamos preguntas personales.'));
      const form = el('form'), username = field('username','Nombre de usuario',{autocomplete:'username',min:3,max:64}), recovery = field('recovery_code','Código de recuperación',{max:64}), password = field('new_password','Nueva contraseña',{password:true,autocomplete:'new-password',min:12,max:128}), repeat = field('password_repeat','Repite la nueva contraseña',{password:true,autocomplete:'new-password',min:12,max:128});
      recovery.input.placeholder = '12345678-12345678-12345678-12345678';
      const submit = el('button','hr-primary','Restablecer contraseña'); submit.type = 'submit';
      form.append(username.row,recovery.row,password.row,repeat.row,el('p','hr-note','Usa entre 12 y 128 caracteres. Al restablecer, se cerrarán las sesiones y todos tus códigos anteriores dejarán de funcionar.'),submit);content.append(form);
      content.append(el('p','hr-footnote','Si no guardaste códigos, esta función no puede recuperar tu cuenta. No tenemos recuperación por correo.'));
      form.addEventListener('submit',async event => {
        event.preventDefault(); if (!current() || pending) return;
        const account = clean(username.input.value), code = normalizedCode(recovery.input.value);
        if (account.length < 3 || account.length > 64 || !code) { showError('Escribe tu usuario de 3 a 64 caracteres y un código completo de los que guardaste.'); return; }
        if (password.input.value.length < 12 || password.input.value.length > 128) { showError('La nueva contraseña debe tener entre 12 y 128 caracteres.'); return; }
        if (password.input.value !== repeat.input.value) { showError('Las contraseñas no coinciden.'); return; }
        const body = {username:account,recovery_code:code,new_password:password.input.value};
        recovery.input.value = password.input.value = repeat.input.value = ''; status.textContent = 'Verificando tu código…';
        try {
          const result = await request(`${BASE}/reset`,'POST',body); if (!result || !current()) return;
          if (result.status !== 'RESET') throw new Error('invalid');
          wipe(); status.textContent = ''; title.textContent = 'Contraseña actualizada';
          content.append(el('p','hr-intro','Inicia sesión manualmente con tu nueva contraseña. Todos tus códigos de recuperación anteriores quedaron invalidados; después de acceder, genera un juego nuevo desde Seguridad.'),button('Volver al acceso','hr-primary',() => dispose(false))); title.focus?.();
        } catch (failure) {
          if (!current()) return; status.textContent = '';
          showError([400,401,403,404,422].includes(failure.status) ? 'No pudimos verificar esos datos. Revisa el usuario y un código válido sin usar.' : failure.status === 429 ? 'Se alcanzó el límite de intentos. Espera antes de volver a probar.' : 'No pudimos confirmar el cambio. Prueba acceder con la nueva contraseña antes de volver a restablecer.');
        }
      });
    }
    on(dialog,'cancel',event => { event.preventDefault(); dispose(false); }); on(dialog,'close',() => dispose(false));
    on(doc,'visibilitychange',syncVisibility); on(global,'pagehide',() => dispose(false));
    if (typeof dialog.showModal === 'function') dialog.showModal(); else dialog.setAttribute('open','');
    if (kind === 'manage') { if (!clean(member?.id)) { dispose(false); return controller; } void showManage(); }
    else if (kind === 'reset') showReset();
    syncVisibility(); title.focus?.(); return {...controller,showBundle};
  }
  function showCodes(options = {}) {
    return new Promise(resolve => { const controller = create('codes',null,resolve); if (!controller.showBundle(options,{onContinue:options.onContinue})) controller.dispose(); });
  }
  const reset = () => active?.dispose();
  global.RoxyHomeRecovery = Object.freeze({openReset:() => create('reset'),openManage:member => create('manage',member),showCodes,reset,dispose:reset});
})(window);
