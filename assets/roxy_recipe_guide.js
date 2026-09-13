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
      audioTimer:null, voiceTimer:null, cancelTimer:null, micTimer:null, scopeTimer:null,
      ownCancellationPending:false,
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
    input.placeholder = 'Repite, ¿cuánto tiempo?, ¿qué ingredientes?'; input.setAttribute('aria-describedby', `${id}-help`);
    const send = node('button', 'Enviar', 'recipe-guide-button'); send.type = 'submit';
    const row = node('div', null, 'recipe-guide-command-row'); row.append(input, send); form.append(label, row);
    const help = node('p', 'Puedes decir o escribir: siguiente, listo, repite, atrás, pausa o «qué hago ahora». También puedes consultar ingredientes, tiempos y temperaturas: mostraré fragmentos originales, sin calcular totales ni verificar seguridad o cocción.', 'recipe-guide-note'); help.id = `${id}-help`;
    const talk = button('Hablar', () => startRecognition());
    const micStatus = node('p', '', 'recipe-guide-status'); micStatus.setAttribute('role', 'status'); micStatus.setAttribute('aria-live', 'polite');
    const response = node('p', '', 'recipe-guide-response'); response.setAttribute('role', 'status'); response.setAttribute('aria-live', 'polite');
    const hearResponse = button('Escuchar respuesta', () => {
      if (!usable() || !response.textContent) return;
      state.voiceEnabled = true; state.paused = false; paint();
      speakText(response.textContent, response.lang || 'es');
    });
    hearResponse.hidden = true; hearResponse.disabled = true;
    const deviceNote = node('p', 'Voz del dispositivo, opcional. «Hablar» pide permiso de micrófono para un solo comando y activa la respuesta hablada; el navegador puede procesar el audio mediante su servicio. Los fragmentos se leen en su idioma original. Puedes usar los botones o escribir.', 'recipe-guide-note recipe-guide-device-note');
    conversation.append(form, help, talk, micStatus, response, hearResponse);
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
      state.speechToken++; state.voiceRequest = null; clearTimer('voiceTimer'); clearTimer('audioTimer'); clearTimer('cancelTimer');
      const utterance = state.utterance; state.utterance = null;
      if (utterance) {
        utterance.onstart = null; utterance.onend = null; utterance.onerror = null;
        try { speech.cancel(); } catch (_) { /* Browser unavailable; textual controls remain usable. */ }
        // Some engines clear speaking/pending after cancel() returns. Remember
        // only cancellation of our own utterance; never cancel another reader.
        state.ownCancellationPending = Boolean(speech.speaking || speech.pending);
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
      stopSpeech(); stopRecognition(); micStatus.textContent = ''; audioStatus.textContent = ''; response.textContent = ''; hearResponse.hidden = true; hearResponse.disabled = true;
      const target = Math.max(0, Math.min(steps.length - 1, state.index + delta));
      if (target === state.index) { reply(delta > 0 ? 'Estás en el último paso. Puedes repetirlo o volver a la receta.' : 'Estás en el primer paso.'); return; }
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
    function chosenVoice(available, spokenLanguage) {
      const matching = available.filter(voice => String(voice.lang || '').toLowerCase().split(/[-_]/)[0] === spokenLanguage.toLowerCase().split('-')[0]);
      return matching.find(voice => String(voice.lang).toLowerCase() === spokenLanguage.toLowerCase()) || matching.find(voice => voice.localService) || matching[0];
    }
    function speakStep() {
      if (!usable() || state.paused || !steps.length) return;
      speakText(steps[state.index], language, 'step');
    }
    function speakText(text, spokenLanguage, kind = 'response') {
      if (!usable() || state.paused || !text) return;
      stopSpeech(); stopRecognition(); micStatus.textContent = '';
      if (!speechAvailable) { audioStatus.textContent = 'Este navegador no ofrece lectura en voz alta. Puedes continuar con los botones o escribir.'; return; }
      state.voiceRequest = {token:state.speechToken, index:state.index, text, language:spokenLanguage, kind, cancelWaits:0};
      audioStatus.textContent = 'Preparando la voz del dispositivo…';
      watchScope();
      prepareVoice();
    }
    function waitForSpeechSlot() {
      const request = state.voiceRequest;
      if (!request) return true;
      if (!speech.speaking && !speech.pending) { state.ownCancellationPending = false; clearTimer('cancelTimer'); return false; }
      if (state.ownCancellationPending && request.cancelWaits < 20) {
        if (state.cancelTimer == null) state.cancelTimer = setTimeout(() => {
          state.cancelTimer = null;
          if (!usable() || state.voiceRequest !== request || request.token !== state.speechToken) return;
          request.cancelWaits++; prepareVoice();
        }, 50);
        return true;
      }
      state.ownCancellationPending = false; state.voiceRequest = null;
      clearTimer('cancelTimer'); clearTimer('voiceTimer');
      audioStatus.textContent = 'Hay otra lectura de voz en curso o la anterior no se detuvo. Vuelve a tocar Escuchar cuando termine.';
      return true;
    }
    function prepareVoice() {
      const request = state.voiceRequest;
      if (!request || !usable() || state.paused || request.token !== state.speechToken || request.index !== state.index || waitForSpeechSlot()) return;
      const available = voices();
      if (available.length) { dispatchVoice(available); return; }
      if (state.voiceTimer != null) return;
      state.voiceTimer = setTimeout(() => {
        state.voiceTimer = null;
        if (!usable() || state.voiceRequest !== request || request.token !== state.speechToken) return;
        const loaded = voices();
        if (loaded.length) dispatchVoice(loaded);
        else { state.voiceRequest = null; audioStatus.textContent = 'El navegador no cargó una voz. Puedes reintentar Escuchar o seguir por texto.'; }
      }, 3000);
    }
    function dispatchVoice(available) {
      const request = state.voiceRequest;
      if (!request || !usable() || state.paused || request.token !== state.speechToken || request.index !== state.index) return;
      if (waitForSpeechSlot()) return;
      clearTimer('voiceTimer'); state.voiceRequest = null;
      const voice = chosenVoice(available, request.language);
      if (!voice) { audioStatus.textContent = `No hay una voz disponible para el idioma de esta lectura (${request.language}). Puedes leer el texto o usar los controles.`; return; }
      let utterance;
      try { utterance = new Speech(request.text); } catch (_) { audioStatus.textContent = 'No se pudo preparar la voz. Puedes seguir por texto.'; return; }
      utterance.lang = request.language; utterance.voice = voice; utterance.rate = 0.95;
      const token = state.speechToken; state.utterance = utterance;
      let started = false;
      const fresh = () => { if (!usable()) return false; return state.speechToken === token && state.utterance === utterance && !state.paused; };
      const fail = message => { if (!fresh()) return; stopSpeech(); audioStatus.textContent = message; };
      utterance.onstart = () => {
        if (!fresh()) return; started = true; clearTimer('audioTimer');
        audioStatus.textContent = request.kind === 'step' ? 'Leyendo este paso…' : 'Leyendo la respuesta…'; hear.setAttribute('aria-pressed', 'true');
        state.audioTimer = setTimeout(() => fail('La lectura tardó demasiado en terminar. El paso se conserva; puedes reintentar Escuchar.'), Math.max(30000, Math.min(1200000, utterance.text.length * 180)));
      };
      utterance.onend = () => {
        if (!fresh()) return;
        if (!started) { fail('La voz no comenzó. Revisa el audio del dispositivo y reintenta Escuchar, o sigue por texto.'); return; }
        clearTimer('audioTimer'); state.utterance = null;
        utterance.onstart = null; utterance.onend = null; utterance.onerror = null;
        hear.setAttribute('aria-pressed', 'false'); audioStatus.textContent = 'Lectura terminada. Avanzamos cuando tú lo indiques.';
      };
      utterance.onerror = event => fail(event?.error === 'not-allowed' ? 'El navegador bloqueó la voz. Toca Escuchar para reintentar; puedes seguir por texto.' : 'No se pudo completar la lectura. El paso se conserva; puedes reintentar Escuchar.');
      state.audioTimer = setTimeout(() => fail('La voz no comenzó. Revisa el audio del dispositivo y reintenta Escuchar, o sigue por texto.'), 6000);
      try { speech.speak(utterance); } catch (_) { fail('No se pudo iniciar la lectura. Puedes reintentar Escuchar o continuar por texto.'); }
    }
    function reply(text, replyLanguage = 'es') {
      response.lang = replyLanguage; response.textContent = text; hearResponse.hidden = !text; hearResponse.disabled = !speechAvailable || !text;
      if (state.voiceEnabled && !state.paused) speakText(text, replyLanguage);
    }
    function sourceAnswer(command) {
      // Retrieval only: do not interpret safety, substitutions, doneness, totals,
      // conversions or compound instructions, even if they mention a quantity.
      if (/\b(?:alerg\w*|allerg\w*|segur\w*|safe\w*|sustitu\w*|reemplaz\w*|replace\w*|substitut\w*|cambiar|cambio|quitar|retirar|sin|without|remove|instead|convert\w*|convertir|equivale\w*|list[oa]s?|done|doneness|cocid[oa]s?|cooked|cru[dt][oa]s?|raw|y|and)\b/.test(command)) return null;
      const time = /^(?:cuanto tiempo|que tiempo|cual es (?:el )?tiempo|cuantos (?:minutos|segundos|horas)|cuanto (?:debe |hay que )?(?:reposar|hornear|cocinar)|tiempo|how long|how much time|how many (?:minutes|hours|seconds)|what (?:is the )?(?:cooking |baking |resting )?time)\b/.test(command);
      const temperature = /^(?:a que temperatura|que temperatura|cual es la temperatura|(?:a )?cuantos grados|temperatura|what (?:oven )?temperature|at what temperature|how hot|how many degrees)\b/.test(command);
      const ingredient = /^(?:ingredientes|ver ingredientes|ingredients|what (?:are the )?ingredients|(?:que|cuales) (?:son los )?ingredientes|lista de ingredientes|cantidades|cuant[oa]s? (?!tiempo\b|minutos\b|segundos\b|horas\b|grados\b|cuesta\b|dinero\b)|how much (?!time\b|does\b)|how many (?!minutes\b|hours\b|seconds\b|degrees\b))/.test(command);
      const english = baseLanguage === 'en';
      if (ingredient && !time && !temperature) {
        ingredientPanel.open = true;
        if (!ingredients.length) return {text:english ? 'This recipe does not include an ingredient list. I cannot supply missing quantities.' : 'Esta ficha no incluye una lista de ingredientes. No puedo completar cantidades ausentes.', language:english ? 'en' : 'es'};
        return {text:(english ? 'Complete original ingredient list. These are source quantities; I do not calculate totals or assign them to a different use:\n\n' : 'Lista original completa de ingredientes. Son cantidades de la fuente; no calculo totales ni las asigno a otro uso:\n\n') + ingredients.join('\n'), language};
      }
      if (!time && !temperature) return null;
      const currentOnly = /\b(?:este paso|paso actual|aqui|this step|current step)\b/.test(command);
      const pattern = time ? /\b(?:minutes?|mins?|minutos?|seconds?|secs?|segundos?|hours?|hrs?|horas?)\b/i : /°|\b(?:fahrenheit|celsius|degrees?|grados?)\b|\b\d{2,3}\s*[fc]\b/i;
      const excerpts = steps.map((text, index) => ({text, index})).filter(row => (!currentOnly || row.index === state.index) && pattern.test(row.text));
      const subject = english ? (time ? 'time' : 'temperature') : (time ? 'tiempo' : 'temperatura');
      if (!excerpts.length) return {text:english ? `No ${subject} with units is specified in ${currentOnly ? 'this step' : 'the recipe steps'}. I cannot supply a missing value or confirm doneness.` : `No encuentro ${subject} con unidades en ${currentOnly ? 'este paso' : 'los pasos de la receta'}. No puedo completar un valor ausente ni verificar la cocción.`, language:english ? 'en' : 'es'};
      const intro = english ? `Original excerpts from ${currentOnly ? 'the current step' : 'the full recipe'}. They may contain different values; I do not calculate totals, assign them to a specific action or confirm doneness:\n\n` : `Fragmentos originales de ${currentOnly ? 'este paso' : 'la receta completa'}. Pueden contener valores distintos; no calculo totales ni asigno valores a una acción concreta. Tampoco verifico la cocción:\n\n`;
      return {text:intro + excerpts.map(row => `${english ? 'Step' : 'Paso'} ${row.index + 1}: ${row.text}`).join('\n\n'), language};
    }
    function executeCommand(value) {
      if (!usable()) return;
      response.lang = 'es';
      const command = normalized(value).replace(/^(?:roxy\s+)?(?:por favor\s+|please\s+)?/, '').replace(/\s+(?:por favor|please)$/, '');
      if (!command) { reply('Escribe un comando, por ejemplo «siguiente» o «qué hago ahora».'); return; }
      if (/^(siguiente|listo|lista|ya|ya esta|ya termine|siguiente paso|next|done)$/.test(command)) { move(1); return; }
      if (/^(atras|anterior|paso anterior|back|previous)$/.test(command)) { move(-1); return; }
      if (/^(repite|repetir|repite el paso|repeat)$/.test(command)) { repeatStep(); return; }
      if (/^(pausa|pausar|para|detente|pause|stop)$/.test(command)) { togglePause(true); return; }
      if (/^(reanudar|continua|continuar|resume)$/.test(command)) { togglePause(false); return; }
      if (/^(que hago ahora|que sigue|en que paso estoy|cual es el paso|what do i do now)$/.test(command)) {
        response.lang = language; response.textContent = steps[state.index] || 'No hay pasos disponibles en esta ficha.';
        if (state.voiceEnabled && !state.paused) speakStep(); return;
      }
      stopSpeech();
      const answer = sourceAnswer(command);
      if (answer) { reply(answer.text, answer.language); return; }
      reply('Puedo leer el paso y mostrar fragmentos originales de ingredientes, tiempos o temperaturas. No puedo responder preguntas abiertas, calcular ajustes, proponer sustituciones ni verificar alergias, seguridad o punto de cocción.');
    }
    function startRecognition() {
      if (!usable()) return;
      if (state.recognition) { stopRecognition(); micStatus.textContent = 'Micrófono detenido.'; return; }
      if (!Recognition) { micStatus.textContent = 'Este navegador no admite comandos de voz. Puedes escribir el comando o usar los botones.'; return; }
      stopSpeech(); audioStatus.textContent = ''; response.textContent = ''; hearResponse.hidden = true; hearResponse.disabled = true; stopRecognition();
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
        // A completed microphone request is explicit permission for a spoken
        // reply. Typed commands remain silent until audio has been selected.
        state.voiceEnabled = true; state.paused = false; paint();
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
