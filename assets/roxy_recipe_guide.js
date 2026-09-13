(() => {
  'use strict';
  const mounts = new WeakMap();
  let sequence = 0;
  const node = (tag, text, className) => {
    const el = document.createElement(tag);
    if (text != null) el.textContent = text;
    if (className) el.className = className;
    return el;
  };
  const normalized = value => String(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    .replace(/[¿?¡!.,;:]/g, '').replace(/\s+/g, ' ').trim();
  const linesValid = value => Array.isArray(value) && value.length > 0 && value.every(line => typeof line === 'string' && line.trim());

  /**
   * mount(container, {title, steps: string[], ingredients: string[], language='es',
   *   sourceLabel, isCurrent=()=>true, onClose, initialStep=0, onStepChange})
   * returns {dispose(), setActive(boolean)}. Step indices are zero-based.
   * Supply intact, already validated source/translation lines and their actual
   * language. No fetching, translation, storage or recipe completion occurs here.
   * On language/recipe changes dispose and mount with the corresponding lines;
   * initialStep/onStepChange allow language switches to retain the same position.
   * isCurrent must include the parent identity/dialog scope. Call setActive(false)
   * on navigation and dispose before removing/replacing a recipe or closing it.
   */
  function mount(container, options = {}) {
    if (!container || typeof container.append !== 'function') throw new TypeError('Recipe guide needs a container.');
    mounts.get(container)?.dispose();
    const {title = '', sourceLabel = '', isCurrent = () => true, onClose, onStepChange} = options;
    const steps = linesValid(options.steps) ? options.steps.slice() : [];
    const ingredients = linesValid(options.ingredients) ? options.ingredients.slice() : [];
    const suppliedLanguage = typeof options.language === 'string' ? options.language : 'es';
    const language = /^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$/i.test(suppliedLanguage) ? suppliedLanguage : 'es';
    const baseLanguage = language.toLowerCase().split('-')[0];
    const speech = window.speechSynthesis;
    const Speech = window.SpeechSynthesisUtterance;
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const speechAvailable = Boolean(speech && Speech && typeof speech.speak === 'function' && typeof speech.getVoices === 'function');
    const id = `recipe-guide-${++sequence}`;
    const state = {
      active:true, disposed:false, paused:false, voiceEnabled:false,
      index:Number.isInteger(options.initialStep) ? Math.max(0, Math.min(options.initialStep, steps.length - 1)) : 0,
      speechToken:0, utterance:null, voiceRequest:null, recognition:null, micToken:0,
      audioTimer:null, voiceTimer:null, micTimer:null, scopeTimer:null,
    };
    const cleanups = [];
    const root = node('section', null, 'recipe-guide'); root.setAttribute('aria-labelledby', `${id}-heading`);
    const head = node('div', null, 'recipe-guide-heading');
    const heading = node('h4', 'Vamos paso a paso'); heading.id = `${id}-heading`;
    const subtitle = node('p', title, 'recipe-guide-title'); subtitle.lang = language;
    const listen = (el, type, fn) => { el.addEventListener(type, fn); cleanups.push(() => el.removeEventListener(type, fn)); };
    const button = (text, action, className = '') => {
      const el = node('button', text, `recipe-guide-button ${className}`.trim()); el.type = 'button';
      listen(el, 'click', action); return el;
    };
    const close = button('Volver a la receta', () => { if (!usable()) return; dispose(); if (typeof onClose === 'function') onClose(); });
    head.append(heading, close);
    const source = node('p', sourceLabel ? `Pasos de ${sourceLabel}.` : 'Los pasos conservan el texto de la receta.', 'recipe-guide-note');
    const progress = node('p', '', 'recipe-guide-progress');
    const meter = node('progress', null, 'recipe-guide-meter'); meter.max = Math.max(1, steps.length); meter.setAttribute('aria-label', 'Paso actual de la receta');
    const step = node('p', '', 'recipe-guide-step'); step.lang = language; step.tabIndex = -1;
    const guidance = node('p', '', 'recipe-guide-guidance'); guidance.setAttribute('role', 'status'); guidance.setAttribute('aria-live', 'polite');
    const nav = node('div', null, 'recipe-guide-navigation'); nav.setAttribute('aria-label', 'Pasos de la receta');
    const previous = button('Anterior', () => move(-1));
    const next = button('Listo, siguiente', () => move(1), 'recipe-guide-primary');
    nav.append(previous, next);
    const controls = node('div', null, 'recipe-guide-controls');
    const hear = button('Escuchar este paso', () => { if (!usable() || !steps.length) return; state.paused = false; state.voiceEnabled = true; paint(); speakStep(); });
    const repeat = button('Repetir', () => repeatStep());
    const pause = button('Pausar', () => togglePause());
    controls.append(hear, repeat, pause);
    const audioStatus = node('p', '', 'recipe-guide-status'); audioStatus.setAttribute('role', 'status'); audioStatus.setAttribute('aria-live', 'polite');
    const ingredientPanel = node('details', null, 'recipe-guide-ingredients');
    const ingredientSummary = node('summary', `Ingredientes${ingredients.length ? ` (${ingredients.length})` : ''}`);
    const ingredientList = node('ul'); ingredientList.lang = language;
    ingredients.forEach(line => ingredientList.append(node('li', line)));
    ingredientPanel.append(ingredientSummary, ingredients.length ? ingredientList : node('p', 'No hay una lista de ingredientes disponible en esta ficha.'));
    const conversation = node('div', null, 'recipe-guide-conversation');
    const form = node('form', null, 'recipe-guide-command-form');
    const label = node('label', 'Dime cómo seguimos'); label.htmlFor = `${id}-command`;
    const input = node('input'); input.id = `${id}-command`; input.type = 'text'; input.maxLength = 300; input.autocomplete = 'off';
    input.placeholder = 'Siguiente, repite, ¿qué hago ahora?'; input.setAttribute('aria-describedby', `${id}-help`);
    const send = node('button', 'Enviar', 'recipe-guide-button'); send.type = 'submit';
    const row = node('div', null, 'recipe-guide-command-row'); row.append(input, send); form.append(label, row);
    const help = node('p', 'Puedes decir o escribir: siguiente, listo, repite, atrás, pausa, ingredientes o «qué hago ahora».', 'recipe-guide-note'); help.id = `${id}-help`;
    const talk = button('Hablar', () => startRecognition());
    const micStatus = node('p', '', 'recipe-guide-status'); micStatus.setAttribute('role', 'status'); micStatus.setAttribute('aria-live', 'polite');
    const response = node('p', '', 'recipe-guide-response'); response.setAttribute('role', 'status'); response.setAttribute('aria-live', 'polite');
    const deviceNote = node('p', 'Voz del dispositivo, opcional. «Hablar» pide permiso de micrófono para un solo comando; el navegador puede procesar el audio mediante su servicio. Puedes usar los botones o escribir.', 'recipe-guide-note recipe-guide-device-note');
    conversation.append(form, help, talk, micStatus, response);
    root.append(head, subtitle, source, progress, meter, step, guidance, nav, controls, audioStatus, ingredientPanel, conversation, deviceNote);
    container.append(root);

    const clearTimer = name => { if (state[name] != null) clearTimeout(state[name]); state[name] = null; };
    function scopeValid() {
      try {
        return !state.disposed && state.active && root.isConnected && !document.hidden && !root.closest?.('[hidden]') && isCurrent() === true;
      } catch (_) { return false; }
    }
    function usable() { if (scopeValid()) return true; suspend(); return false; }
    function watchScope() {
      if (state.scopeTimer != null || state.disposed) return;
      state.scopeTimer = setTimeout(() => {
        state.scopeTimer = null;
        if (!scopeValid()) { suspend(); return; }
        if (state.utterance || state.voiceRequest || state.recognition) watchScope();
      }, 200);
    }
    function stopSpeech() {
      state.speechToken++; state.voiceRequest = null; clearTimer('voiceTimer'); clearTimer('audioTimer');
      const utterance = state.utterance; state.utterance = null;
      if (utterance) {
        utterance.onstart = null; utterance.onend = null; utterance.onerror = null;
        try { speech.cancel(); } catch (_) { /* Browser unavailable; textual controls remain usable. */ }
      }
      hear.setAttribute('aria-pressed', 'false');
    }
    function stopRecognition() {
      state.micToken++; clearTimer('micTimer');
      const recognition = state.recognition; state.recognition = null;
      if (recognition) {
        recognition.onstart = null; recognition.onresult = null; recognition.onerror = null; recognition.onend = null;
        try { recognition.abort(); } catch (_) { /* It may already have stopped. */ }
      }
      talk.textContent = 'Hablar'; talk.setAttribute('aria-pressed', 'false');
    }
    function suspend() {
      if (state.disposed) return;
      const hadMedia = Boolean(state.utterance || state.voiceRequest || state.recognition);
      stopSpeech(); stopRecognition(); clearTimer('scopeTimer');
      if (hadMedia) { state.paused = true; audioStatus.textContent = 'Guía pausada. Puedes continuar desde este paso.'; micStatus.textContent = ''; paint(); }
    }
    function paint() {
      progress.textContent = steps.length ? `Paso ${state.index + 1} de ${steps.length}` : 'Pasos no disponibles';
      meter.value = steps.length ? state.index + 1 : 0;
      step.textContent = steps[state.index] || 'Esta ficha no contiene una secuencia completa de pasos legibles.';
      guidance.textContent = !steps.length ? 'Vuelve a la receta para revisar la fuente.' : state.paused ? 'En pausa. Conservamos tu paso.' :
        state.index === steps.length - 1 ? 'Este es el último paso de la fuente. Puedes repetirlo o volver a la receta.' : 'Cuando termines este paso, dime «listo» o toca Siguiente.';
      previous.disabled = !steps.length || state.index === 0; next.disabled = !steps.length || state.index === steps.length - 1;
      next.textContent = steps.length && state.index === steps.length - 1 ? 'Último paso' : 'Listo, siguiente';
      hear.disabled = !steps.length || !speechAvailable; repeat.disabled = !steps.length; pause.disabled = !steps.length;
      pause.textContent = state.paused ? 'Reanudar' : 'Pausar'; pause.setAttribute('aria-pressed', String(state.paused));
    }
    function move(delta) {
      if (!usable() || !steps.length) return;
      stopSpeech(); stopRecognition(); micStatus.textContent = ''; audioStatus.textContent = ''; response.textContent = '';
      const target = Math.max(0, Math.min(steps.length - 1, state.index + delta));
      if (target === state.index) { response.textContent = delta > 0 ? 'Estás en el último paso. Puedes repetirlo o volver a la receta.' : 'Estás en el primer paso.'; return; }
      state.index = target; paint();
      if (typeof onStepChange === 'function') onStepChange(state.index);
      if (!usable()) return;
      step.focus({preventScroll:false});
      if (state.voiceEnabled && !state.paused) speakStep();
    }
    function repeatStep() {
      if (!usable() || !steps.length) return;
      response.lang = language; response.textContent = steps[state.index];
      state.paused = false; paint();
      // Repetir repeats text immediately. Once listening is selected, it also reads it.
      if (state.voiceEnabled) speakStep();
    }
    function togglePause(force) {
      if (!usable() || !steps.length) return;
      state.paused = typeof force === 'boolean' ? force : !state.paused;
      stopSpeech(); stopRecognition(); micStatus.textContent = '';
      audioStatus.textContent = state.paused ? 'Voz detenida. El paso se conserva.' : '';
      paint(); if (!state.paused && state.voiceEnabled) speakStep();
    }
    function voices() { try { return Array.from(speech.getVoices() || []); } catch (_) { return []; } }
    function chosenVoice(available) {
      const matching = available.filter(voice => String(voice.lang || '').toLowerCase().split(/[-_]/)[0] === baseLanguage);
      return matching.find(voice => String(voice.lang).toLowerCase() === language.toLowerCase()) || matching.find(voice => voice.localService) || matching[0];
    }
    function speakStep() {
      if (!usable() || state.paused || !steps.length) return;
      stopSpeech(); stopRecognition(); micStatus.textContent = '';
      if (!speechAvailable) { audioStatus.textContent = 'Este navegador no ofrece lectura en voz alta. Puedes continuar con los botones o escribir.'; return; }
      if (speech.speaking || speech.pending) { audioStatus.textContent = 'Hay otra lectura de voz en curso. Detén esa lectura y vuelve a tocar Escuchar.'; return; }
      const token = state.speechToken;
      state.voiceRequest = {token, index:state.index};
      audioStatus.textContent = 'Preparando la voz del dispositivo…';
      watchScope();
      const available = voices();
      if (available.length) { dispatchVoice(available); return; }
      state.voiceTimer = setTimeout(() => {
        state.voiceTimer = null;
        if (!usable() || !state.voiceRequest || token !== state.speechToken) return;
        const loaded = voices();
        if (loaded.length) dispatchVoice(loaded);
        else { state.voiceRequest = null; audioStatus.textContent = 'El navegador no cargó una voz. Puedes reintentar Escuchar o seguir por texto.'; }
      }, 3000);
    }
    function dispatchVoice(available) {
      const request = state.voiceRequest;
      if (!request || !usable() || state.paused || request.token !== state.speechToken || request.index !== state.index) return;
      clearTimer('voiceTimer'); state.voiceRequest = null;
      const voice = chosenVoice(available);
      if (!voice) { audioStatus.textContent = `No hay una voz disponible para el idioma de estos pasos (${language}). Puedes leerlos o usar los controles.`; return; }
      if (speech.speaking || speech.pending) { audioStatus.textContent = 'Hay otra lectura de voz en curso. Vuelve a tocar Escuchar cuando termine.'; return; }
      let utterance;
      try { utterance = new Speech(steps[state.index]); } catch (_) { audioStatus.textContent = 'No se pudo preparar la voz. Puedes seguir por texto.'; return; }
      utterance.lang = language; utterance.voice = voice; utterance.rate = 0.95;
      const token = state.speechToken; state.utterance = utterance;
      const fresh = () => { if (!usable()) return false; return state.speechToken === token && state.utterance === utterance && !state.paused; };
      const fail = message => { if (!fresh()) return; stopSpeech(); audioStatus.textContent = message; };
      utterance.onstart = () => {
        if (!fresh()) return; clearTimer('audioTimer');
        audioStatus.textContent = 'Leyendo este paso…'; hear.setAttribute('aria-pressed', 'true');
        state.audioTimer = setTimeout(() => fail('La lectura tardó demasiado en terminar. El paso se conserva; puedes reintentar Escuchar.'), Math.max(30000, Math.min(1200000, utterance.text.length * 180)));
      };
      utterance.onend = () => {
        if (!fresh()) return; clearTimer('audioTimer'); state.utterance = null;
        utterance.onstart = null; utterance.onend = null; utterance.onerror = null;
        hear.setAttribute('aria-pressed', 'false'); audioStatus.textContent = 'Lectura terminada. Avanzamos cuando tú lo indiques.';
      };
      utterance.onerror = event => fail(event?.error === 'not-allowed' ? 'El navegador bloqueó la voz. Toca Escuchar para reintentar; puedes seguir por texto.' : 'No se pudo completar la lectura. El paso se conserva; puedes reintentar Escuchar.');
      state.audioTimer = setTimeout(() => fail('La voz no comenzó. Revisa el audio del dispositivo y reintenta Escuchar, o sigue por texto.'), 6000);
      try { speech.speak(utterance); } catch (_) { fail('No se pudo iniciar la lectura. Puedes reintentar Escuchar o continuar por texto.'); }
    }
    function executeCommand(value) {
      if (!usable()) return;
      response.lang = 'es';
      const command = normalized(value);
      if (!command) { response.textContent = 'Escribe un comando, por ejemplo «siguiente» o «qué hago ahora».'; return; }
      if (/^(siguiente|listo|lista|ya|ya esta|ya termine|siguiente paso|next|done)$/.test(command)) { move(1); return; }
      if (/^(atras|anterior|paso anterior|back|previous)$/.test(command)) { move(-1); return; }
      if (/^(repite|repetir|repite el paso|repeat)$/.test(command)) { repeatStep(); return; }
      if (/^(pausa|pausar|para|detente|pause|stop)$/.test(command)) { togglePause(true); return; }
      if (/^(reanudar|continua|continuar|resume)$/.test(command)) { togglePause(false); return; }
      if (/^(ingredientes|ver ingredientes|ingredients)$/.test(command)) {
        stopSpeech(); ingredientPanel.open = true; ingredientSummary.focus({preventScroll:true});
        response.textContent = ingredients.length ? 'Aquí tienes los ingredientes de esta receta, con sus cantidades originales.' : 'Esta ficha no incluye una lista de ingredientes disponible.'; return;
      }
      if (/^(que hago ahora|que sigue|en que paso estoy|cual es el paso|what do i do now)$/.test(command)) {
        response.lang = language; response.textContent = steps[state.index] || 'No hay pasos disponibles en esta ficha.';
        if (state.voiceEnabled && !state.paused) speakStep(); return;
      }
      response.textContent = 'En esta guía puedo leer o repetir el paso, avanzar, volver atrás y mostrar ingredientes. Todavía no responde preguntas abiertas ni propone sustituciones.';
    }
    function startRecognition() {
      if (!usable()) return;
      if (state.recognition) { stopRecognition(); micStatus.textContent = 'Micrófono detenido.'; return; }
      if (!Recognition) { micStatus.textContent = 'Este navegador no admite comandos de voz. Puedes escribir el comando o usar los botones.'; return; }
      stopSpeech(); audioStatus.textContent = ''; response.textContent = ''; stopRecognition();
      const token = state.micToken;
      let recognition;
      try { recognition = new Recognition(); } catch (_) { micStatus.textContent = 'No se pudo abrir el micrófono. Puedes escribir el comando.'; return; }
      state.recognition = recognition;
      recognition.lang = 'es-ES'; recognition.continuous = false; recognition.interimResults = false; recognition.maxAlternatives = 1;
      const fresh = () => { if (!usable()) return false; return token === state.micToken && state.recognition === recognition; };
      talk.textContent = 'Detener micrófono'; talk.setAttribute('aria-pressed', 'false');
      micStatus.textContent = 'Esperando permiso de micrófono…';
      recognition.onstart = () => { if (!fresh()) return; micStatus.textContent = 'Te escucho para un comando…'; talk.setAttribute('aria-pressed', 'true'); };
      recognition.onresult = event => {
        if (!fresh()) return;
        const result = event.results?.[event.resultIndex || 0];
        if (!result || result.isFinal === false) return;
        const transcript = result[0]?.transcript;
        stopRecognition();
        if (typeof transcript !== 'string' || !transcript.trim()) { micStatus.textContent = 'No entendí el comando. Puedes repetirlo con Hablar o escribirlo.'; return; }
        micStatus.textContent = `Escuché: «${transcript}».`; executeCommand(transcript);
      };
      recognition.onerror = event => {
        if (!fresh()) return; stopRecognition();
        micStatus.textContent = ['not-allowed', 'service-not-allowed'].includes(event?.error) ? 'Permiso de micrófono denegado. Puedes usar los botones o escribir.' :
          event?.error === 'no-speech' ? 'No se detectó un comando. Toca Hablar para reintentar o escribe.' : 'El reconocimiento de voz no estuvo disponible. Puedes escribir el comando o reintentar Hablar.';
      };
      recognition.onend = () => { if (!fresh()) return; stopRecognition(); micStatus.textContent = 'Micrófono cerrado. Toca Hablar cuando quieras dar otro comando.'; };
      state.micTimer = setTimeout(() => { if (!fresh()) return; stopRecognition(); micStatus.textContent = 'Se agotó la espera del micrófono. Puedes reintentar Hablar o escribir.'; }, 15000);
      watchScope();
      try { recognition.start(); } catch (_) { if (fresh()) { stopRecognition(); micStatus.textContent = 'No se pudo iniciar el micrófono. Puedes escribir el comando.'; } }
    }
    listen(form, 'submit', event => { event.preventDefault(); if (!usable()) return; stopRecognition(); executeCommand(input.value); input.value = ''; });
    listen(document, 'visibilitychange', () => { if (document.hidden) suspend(); });
    if (typeof window.addEventListener === 'function') listen(window, 'pagehide', () => suspend());
    if (speechAvailable && typeof speech.addEventListener === 'function') listen(speech, 'voiceschanged', () => {
      if (state.voiceRequest && usable()) { const loaded = voices(); if (loaded.length) dispatchVoice(loaded); }
    });
    const Observer = window.MutationObserver;
    const observer = Observer ? new Observer(() => { if (!scopeValid()) suspend(); }) : null;
    observer?.observe(document.documentElement || document.body, {subtree:true, childList:true, attributes:true, attributeFilter:['hidden', 'open', 'style', 'class']});
    function dispose() {
      if (state.disposed) return;
      stopSpeech(); stopRecognition(); clearTimer('scopeTimer'); state.disposed = true;
      observer?.disconnect(); cleanups.splice(0).forEach(cleanup => cleanup()); root.remove();
      if (mounts.get(container) === controller) mounts.delete(container);
    }
    const controller = {
      dispose,
      setActive(active) {
        if (state.disposed) return;
        state.active = active === true;
        if (!state.active) suspend();
        root.hidden = !state.active;
        if (state.active && !scopeValid()) suspend();
      },
    };
    mounts.set(container, controller); paint();
    if (!speechAvailable) audioStatus.textContent = 'Este navegador no ofrece lectura en voz alta. Puedes continuar con los botones o escribir.';
    if (!Recognition) { talk.disabled = true; micStatus.textContent = 'Comandos de voz no disponibles en este navegador. Puedes escribir.'; }
    if (!scopeValid()) suspend();
    else step.focus({preventScroll:false});
    return controller;
  }
  window.RoxyRecipeGuide = Object.freeze({mount});
})();
