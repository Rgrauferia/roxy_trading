import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const code = fs.readFileSync(new URL('../assets/roxy_recipe_guide.js', import.meta.url), 'utf8');
class Target {
  constructor() { this.listeners = new Map(); }
  addEventListener(type, callback) { if (!this.listeners.has(type)) this.listeners.set(type, new Set()); this.listeners.get(type).add(callback); }
  removeEventListener(type, callback) { this.listeners.get(type)?.delete(callback); }
  fire(type, properties = {}) { const event = {type, target:this, preventDefault() { this.defaultPrevented = true; }, ...properties}; for (const fn of [...this.listeners.get(type) || []]) fn(event); return event; }
  listenerCount() { return [...this.listeners.values()].reduce((n, value) => n + value.size, 0); }
}
class Element extends Target {
  constructor(tag) { super(); this.tagName = tag; this.children = []; this.parentNode = null; this.attributes = {}; this.hidden = false; this.disabled = false; this._text = ''; this.value = ''; }
  append(...nodes) { nodes.forEach(node => { node.remove(); node.parentNode = this; this.children.push(node); }); }
  remove() { if (this.parentNode) { this.parentNode.children = this.parentNode.children.filter(el => el !== this); this.parentNode = null; } }
  get textContent() { return this._text + this.children.map(el => el.textContent).join(''); }
  set textContent(value) { this._text = String(value); this.children.forEach(el => { el.parentNode = null; }); this.children = []; }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  getAttribute(key) { return this.attributes[key]; }
  get isConnected() { return this.isRoot === true || Boolean(this.parentNode?.isConnected); }
  closest(selector) { if (selector === '[hidden]') return this.hidden ? this : this.parentNode?.closest(selector) || null; return null; }
  focus() { this.focused = true; }
  click() { if (!this.disabled) this.fire('click'); }
}
function descendants(parent) { return parent.children.flatMap(el => [el, ...descendants(el)]); }
const byClass = (parent, name) => descendants(parent).find(el => el.className?.split(' ').includes(name));
const byTag = (parent, tag) => descendants(parent).filter(el => el.tagName === tag);
const button = (parent, name) => { const found = byTag(parent, 'button').find(el => el.textContent === name); assert.ok(found, `Missing button ${name}`); return found; };
const stepText = parent => byClass(parent, 'recipe-guide-step').textContent;
const status = parent => byClass(parent, 'recipe-guide-status').textContent;
const response = parent => byClass(parent, 'recipe-guide-response').textContent;
const progress = parent => byClass(parent, 'recipe-guide-progress').textContent;
const esVoice = {lang:'es-ES', name:'Spanish device', localService:true};
const enVoice = {lang:'en-US', name:'English device', localService:true};
function harness({tts = true, microphone = true, availableVoices = [esVoice, enVoice], speakThrows = false, recognitionThrows = false, deferredCancel = false} = {}) {
  let now = 0, timerSequence = 0, list = availableVoices;
  const timers = new Map(), calls = [], microphones = [], observers = [], forbidden = [];
  const document = new Target(); document.hidden = false; document.body = new Element('body'); document.body.isRoot = true;
  document.documentElement = document.body; document.createElement = tag => new Element(tag);
  const window = new Target();
  const speech = new Target(); speech.speaking = false; speech.pending = false;
  speech.getVoices = () => list;
  speech.speak = utterance => { calls.push({type:'speak', utterance}); if (speakThrows) throw new Error('device failed'); speech.pending = true; };
  speech.cancel = () => { calls.push({type:'cancel'}); if (!deferredCancel) { speech.speaking = false; speech.pending = false; } };
  if (tts) { window.speechSynthesis = speech; window.SpeechSynthesisUtterance = class { constructor(text) { this.text = text; } }; }
  if (microphone) window.SpeechRecognition = class {
    constructor() { microphones.push(this); }
    start() { this.started = true; if (recognitionThrows) throw new Error('blocked'); }
    abort() { this.aborted = true; }
  };
  window.MutationObserver = class { constructor(callback) { this.callback = callback; this.connected = false; observers.push(this); } observe() { this.connected = true; } disconnect() { this.connected = false; } };
  const deny = name => { forbidden.push(name); throw new Error(`Forbidden ${name}`); };
  vm.runInNewContext(code, {window, document, AbortController, setTimeout(fn, delay = 0) { const id = ++timerSequence; timers.set(id, {fn, due:now + delay}); return id; }, clearTimeout(id) { timers.delete(id); },
    fetch() { deny('fetch'); }, localStorage:{getItem() { deny('read localStorage'); }, setItem() { deny('write localStorage'); }}, sessionStorage:{getItem() { deny('read sessionStorage'); }, setItem() { deny('write sessionStorage'); }}, indexedDB:{open() { deny('indexedDB'); }}});
  const container = new Element('div'); document.body.append(container);
  const mount = (options = {}) => window.RoxyRecipeGuide.mount(container, {title:'Arroz de la fuente', steps:['Lava el arroz.', 'Cocina durante 15 minutos.', 'Deja reposar.'], ingredients:['1 taza de arroz', '2 tazas de agua'], sourceLabel:'Fuente de prueba', ...options});
  function tick(ms) {
    const until = now + ms; let loops = 0;
    for (;;) { const entry = [...timers].filter(([, timer]) => timer.due <= until).sort((a,b) => a[1].due - b[1].due)[0]; if (!entry) break;
      if (++loops > 20000) throw new Error('timer loop'); const [id, timer] = entry; timers.delete(id); now = timer.due; timer.fn(); }
    now = until;
  }
  const command = text => { byTag(container, 'input')[0].value = text; byTag(container, 'form')[0].fire('submit'); };
  const latestUtterance = () => calls.filter(call => call.type === 'speak').at(-1)?.utterance;
  const startAudio = () => { speech.pending = false; speech.speaking = true; latestUtterance().onstart?.(); };
  const endAudio = () => { speech.pending = false; speech.speaking = false; latestUtterance().onend?.(); };
  const micResult = (text, {final = true, index = 0} = {}) => { const result = [{transcript:text}]; result.isFinal = final; const results = []; results[index] = result; microphones.at(-1).onresult?.({resultIndex:index, results}); };
  const mutation = () => observers.forEach(observer => { if (observer.connected) observer.callback([]); });
  return {mount, container, document, window, speech, calls, microphones, observers, forbidden, timers, tick, command, latestUtterance, startAudio, endAudio, micResult, mutation,
    setVoices(value) { list = value; speech.fire('voiceschanged'); }, visibility(value) { document.hidden = value; document.fire('visibilitychange'); }};
}

test('mount reads no audio, microphone, network or storage automatically', () => {
  const h = harness(); h.mount(); h.tick(60000);
  assert.equal(progress(h.container), 'Paso 1 de 3'); assert.deepEqual(h.calls, []); assert.deepEqual(h.microphones, []); assert.deepEqual(h.forbidden, []); assert.equal(h.timers.size, 0);
});
test('source text, whitespace, duplicates and HTML-like text are preserved without interpretation', () => {
  const h = harness(); const original = '  Mezcla <b>sin HTML</b>.\n Repite: mezcla.  ';
  h.mount({steps:[original, original], ingredients:['  ½ taza\n de agua  ']});
  assert.equal(stepText(h.container), original); assert.equal(byTag(h.container, 'li')[0].textContent, '  ½ taza\n de agua  '); assert.equal(byTag(h.container, 'b').length, 0);
  button(h.container, 'Listo, siguiente').click(); assert.equal(stepText(h.container), original); assert.equal(progress(h.container), 'Paso 2 de 2');
});
test('navigation updates exact source steps and progress and never auto-advances', () => {
  const h = harness(); const positions = []; h.mount({onStepChange:index => positions.push(index)});
  button(h.container, 'Listo, siguiente').click(); assert.equal(stepText(h.container), 'Cocina durante 15 minutos.');
  h.tick(120000); assert.equal(progress(h.container), 'Paso 2 de 3'); button(h.container, 'Anterior').click(); assert.equal(progress(h.container), 'Paso 1 de 3'); assert.deepEqual(positions, [1,0]);
});
test('last step remains readable and cannot advance or delete the guide', () => {
  const h = harness(); h.mount({initialStep:2}); button(h.container, 'Último paso').click(); h.command('listo');
  assert.equal(progress(h.container), 'Paso 3 de 3'); assert.equal(stepText(h.container), 'Deja reposar.'); assert.match(response(h.container), /último paso/); assert.equal(byClass(h.container, 'recipe-guide').isConnected, true);
});
test('first step cannot move backwards through typed commands', () => {
  const h = harness(); h.mount(); h.command('atrás'); assert.equal(progress(h.container), 'Paso 1 de 3'); assert.match(response(h.container), /primer paso/);
});
test('pause keeps the step and timers cannot move it; explicit resume keeps position', () => {
  const h = harness(); h.mount({initialStep:1}); button(h.container, 'Pausar').click(); h.tick(100000); assert.equal(progress(h.container), 'Paso 2 de 3');
  assert.match(byClass(h.container, 'recipe-guide-guidance').textContent, /En pausa/); button(h.container, 'Reanudar').click(); assert.equal(progress(h.container), 'Paso 2 de 3'); assert.deepEqual(h.calls, []);
});
test('navigation during pause is explicit and keeps audio paused', () => {
  const h = harness(); h.mount(); button(h.container, 'Escuchar este paso').click(); button(h.container, 'Pausar').click(); button(h.container, 'Listo, siguiente').click();
  assert.equal(progress(h.container), 'Paso 2 de 3'); assert.equal(h.calls.filter(call => call.type === 'speak').length, 1); assert.ok(button(h.container, 'Reanudar'));
});
test('repeat provides the intact step before any audio opt-in', () => {
  const h = harness(); h.mount(); button(h.container, 'Repetir').click(); assert.equal(response(h.container), 'Lava el arroz.'); assert.deepEqual(h.calls, []);
});
test('initial index is clamped and language remount can retain it', () => {
  const h = harness(); h.mount({initialStep:1}); h.mount({initialStep:1, language:'en', steps:['Wash rice.', 'Cook for 15 minutes.', 'Rest.']});
  assert.equal(progress(h.container), 'Paso 2 de 3'); assert.equal(stepText(h.container), 'Cook for 15 minutes.'); assert.equal(byClass(h.container, 'recipe-guide-step').lang, 'en');
  h.mount({initialStep:99}); assert.equal(progress(h.container), 'Paso 3 de 3'); h.mount({initialStep:-8}); assert.equal(progress(h.container), 'Paso 1 de 3');
});
test('incomplete steps are rejected as a whole rather than silently shortened', () => {
  const h = harness(); h.mount({steps:['Paso válido', null, 'Otro paso']}); assert.equal(progress(h.container), 'Pasos no disponibles'); assert.ok(button(h.container, 'Listo, siguiente').disabled); assert.equal(h.calls.length, 0);
});
test('missing ingredient list is explained without inventing quantities', () => {
  const h = harness(); h.mount({ingredients:[]}); h.command('ingredientes'); assert.equal(byTag(h.container, 'details')[0].open, true); assert.match(response(h.container), /no incluye/); assert.equal(byTag(h.container, 'li').length, 0);
});
test('ingredients are collapsible and reveal the full original list on command', () => {
  const h = harness(); h.mount(); const panel = byTag(h.container, 'details')[0]; assert.ok(!panel.open); h.command('ingredientes'); assert.equal(panel.open, true); assert.equal(byTag(panel, 'li').length, 2); assert.equal(h.calls.length, 0);
});
test('what do I do now returns only the existing current instruction', () => {
  const h = harness(); h.mount({initialStep:1}); h.command('¿Qué hago ahora?'); assert.equal(response(h.container), 'Cocina durante 15 minutos.'); assert.equal(progress(h.container), 'Paso 2 de 3'); assert.equal(h.calls.length, 0);
});
test('cooking questions outside commands do not invent answers or advance', () => {
  const h = harness(); h.mount(); h.command('¿Puedo sustituir el arroz por carne y cocinar 2 minutos?');
  assert.match(response(h.container), /No puedo responder preguntas abiertas/); assert.equal(progress(h.container), 'Paso 1 de 3'); assert.deepEqual(h.forbidden, []);
});
test('ambiguous compound command is not partially executed', () => {
  const h = harness(); h.mount(); h.command('siguiente y ponlo a 300 grados'); assert.equal(progress(h.container), 'Paso 1 de 3'); assert.match(response(h.container), /No puedo responder preguntas abiertas/);
});
test('typed command variants handle accents, punctuation and whitespace', () => {
  const h = harness(); h.mount(); h.command('  ¡LISTO!  '); assert.equal(progress(h.container), 'Paso 2 de 3'); h.command('ATRÁS'); assert.equal(progress(h.container), 'Paso 1 de 3'); h.command('repite'); assert.equal(response(h.container), 'Lava el arroz.'); h.command('pausa'); assert.ok(button(h.container, 'Reanudar'));
});
test('empty text gives a useful prompt and form submit clears the input', () => {
  const h = harness(); h.mount(); h.command('  '); assert.match(response(h.container), /Escribe un comando/); assert.equal(byTag(h.container, 'input')[0].value, '');
});
test('unsupported audio leaves manual and text recipe guidance working', () => {
  const h = harness({tts:false, microphone:false}); h.mount(); assert.equal(button(h.container, 'Escuchar este paso').disabled, true); assert.equal(button(h.container, 'Hablar').disabled, true);
  assert.match(status(h.container), /no ofrece lectura/); h.command('listo'); assert.equal(progress(h.container), 'Paso 2 de 3'); button(h.container, 'Repetir').click(); assert.equal(response(h.container), 'Cocina durante 15 minutos.');
});
test('voice is pending until actual onstart, then ends without advancing', () => {
  const h = harness(); h.mount(); button(h.container, 'Escuchar este paso').click(); assert.match(status(h.container), /Preparando/); assert.doesNotMatch(status(h.container), /Leyendo/);
  h.startAudio(); assert.equal(status(h.container), 'Leyendo este paso…'); h.endAudio(); assert.match(status(h.container), /Lectura terminada/); assert.equal(progress(h.container), 'Paso 1 de 3');
});
test('English original is read with an English voice and no Spanish prefix', () => {
  const h = harness(); h.mount({language:'en', steps:['Mix 1 cup flour.']}); button(h.container, 'Escuchar este paso').click();
  const utterance = h.latestUtterance(); assert.equal(utterance.text, 'Mix 1 cup flour.'); assert.equal(utterance.lang, 'en'); assert.equal(utterance.voice, enVoice);
});
test('Spanish regional voice selection honors the actual language', () => {
  const mexican = {lang:'es-MX', name:'Spanish Mexico', localService:true}; const h = harness({availableVoices:[esVoice, mexican, enVoice]}); h.mount({language:'es-MX'});
  button(h.container, 'Escuchar este paso').click(); assert.equal(h.latestUtterance().voice, mexican); assert.equal(h.latestUtterance().lang, 'es-MX');
});
test('missing language voice never reads English through Spanish fallback', () => {
  const h = harness({availableVoices:[esVoice]}); h.mount({language:'en', steps:['Boil water.']}); button(h.container, 'Escuchar este paso').click(); assert.equal(h.calls.length, 0); assert.match(status(h.container), /No hay una voz.*\(en\)/);
});
test('voiceschanged resolves delayed voice loading only after explicit listening', () => {
  const h = harness({availableVoices:[]}); h.mount(); h.setVoices([esVoice]); assert.equal(h.calls.length, 0); h.setVoices([]);
  button(h.container, 'Escuchar este paso').click(); assert.equal(h.calls.length, 0); h.setVoices([esVoice]); assert.equal(h.calls.filter(call => call.type === 'speak').length, 1); h.setVoices([esVoice]); assert.equal(h.calls.filter(call => call.type === 'speak').length, 1);
});
test('voice load timeout is visible and later voice changes never auto-start', () => {
  const h = harness({availableVoices:[]}); h.mount(); button(h.container, 'Escuchar este paso').click(); h.tick(3000); assert.match(status(h.container), /no cargó una voz/); h.setVoices([esVoice]); assert.equal(h.calls.length, 0);
  button(h.container, 'Escuchar este paso').click(); assert.equal(h.calls.filter(call => call.type === 'speak').length, 1);
});
test('pending voice request is discarded when source step changes', () => {
  const h = harness({availableVoices:[]}); h.mount(); button(h.container, 'Escuchar este paso').click(); button(h.container, 'Listo, siguiente').click(); h.setVoices([esVoice]); assert.equal(h.latestUtterance().text, 'Cocina durante 15 minutos.'); assert.equal(h.calls.filter(call => call.type === 'speak').length, 1);
});
test('audio start timeout cancels only this utterance and permits retry', () => {
  const h = harness(); h.mount(); button(h.container, 'Escuchar este paso').click(); const oldStart = h.latestUtterance().onstart; h.tick(6000);
  assert.match(status(h.container), /voz no comenzó/); assert.equal(h.calls.at(-1).type, 'cancel'); oldStart(); assert.match(status(h.container), /voz no comenzó/);
  button(h.container, 'Escuchar este paso').click(); h.startAudio(); assert.match(status(h.container), /Leyendo/);
});
test('audio finish timeout is visible and preserves step', () => {
  const h = harness(); h.mount(); button(h.container, 'Escuchar este paso').click(); h.startAudio(); h.tick(30000); assert.match(status(h.container), /tardó demasiado/); assert.equal(progress(h.container), 'Paso 1 de 3');
});
test('audio error is visible, clears pending resources and allows manual next', () => {
  const h = harness(); h.mount(); button(h.container, 'Escuchar este paso').click(); h.latestUtterance().onerror({error:'not-allowed'}); assert.match(status(h.container), /bloqueó la voz/);
  button(h.container, 'Pausar').click(); button(h.container, 'Listo, siguiente').click(); assert.equal(progress(h.container), 'Paso 2 de 3');
});
test('synchronous speech failure gives a textual fallback', () => {
  const h = harness({speakThrows:true}); h.mount(); button(h.container, 'Escuchar este paso').click(); assert.match(status(h.container), /No se pudo iniciar/); assert.equal(progress(h.container), 'Paso 1 de 3');
});
test('existing unrelated browser speech is not cancelled when mounting, listening or disposing', () => {
  const h = harness(); h.speech.speaking = true; const guide = h.mount(); button(h.container, 'Escuchar este paso').click(); assert.match(status(h.container), /otra lectura/); guide.dispose(); assert.deepEqual(h.calls, []);
});
test('after listening, next and repeat read their exact source step', () => {
  const h = harness(); h.mount(); button(h.container, 'Escuchar este paso').click(); h.startAudio(); button(h.container, 'Listo, siguiente').click(); assert.equal(h.latestUtterance().text, 'Cocina durante 15 minutos.');
  button(h.container, 'Repetir').click(); assert.equal(h.latestUtterance().text, 'Cocina durante 15 minutos.'); assert.equal(progress(h.container), 'Paso 2 de 3');
});
test('late speech callbacks cannot change a newer reading state', () => {
  const h = harness(); h.mount(); button(h.container, 'Escuchar este paso').click(); const old = h.latestUtterance(); const staleEnd = old.onend, staleStart = old.onstart, staleError = old.onerror;
  button(h.container, 'Listo, siguiente').click(); h.startAudio(); staleEnd(); staleStart(); staleError({error:'device'}); assert.equal(status(h.container), 'Leyendo este paso…'); assert.equal(progress(h.container), 'Paso 2 de 3');
});
test('microphone begins only after Hablar, replies aloud and remains one-shot', () => {
  const h = harness(); h.mount(); button(h.container, 'Hablar').click(); const mic = h.microphones[0]; assert.equal(mic.continuous, false); assert.equal(mic.interimResults, false); assert.equal(mic.lang, 'es-ES');
  mic.onstart(); h.micResult('listo'); assert.equal(mic.aborted, true); assert.equal(progress(h.container), 'Paso 2 de 3'); assert.equal(h.latestUtterance().text, 'Cocina durante 15 minutos.'); h.tick(60000); assert.equal(h.microphones.length, 1); assert.equal(h.calls.filter(call => call.type === 'speak').length, 1);
});
test('recognition ignores interim transcript and handles final resultIndex', () => {
  const h = harness(); h.mount(); button(h.container, 'Hablar').click(); h.micResult('listo', {final:false}); assert.equal(progress(h.container), 'Paso 1 de 3'); h.micResult('listo', {index:2}); assert.equal(progress(h.container), 'Paso 2 de 3');
});
test('mic permission denial is visible and does not retry automatically', () => {
  const h = harness(); h.mount(); button(h.container, 'Hablar').click(); h.microphones[0].onerror({error:'not-allowed'}); assert.match(h.container.textContent, /Permiso de micrófono denegado/); h.tick(60000); assert.equal(h.microphones.length, 1); h.command('listo'); assert.equal(progress(h.container), 'Paso 2 de 3');
});
test('mic timeout aborts request and stale recognition result cannot advance', () => {
  const h = harness(); h.mount(); button(h.container, 'Hablar').click(); const mic = h.microphones[0], lateResult = mic.onresult; h.tick(15000); assert.match(h.container.textContent, /agotó la espera/); assert.equal(mic.aborted, true);
  lateResult({results:[[{transcript:'listo'}]]}); assert.equal(progress(h.container), 'Paso 1 de 3');
});
test('mic end, no-speech and synchronous failure all leave text controls usable', () => {
  const h = harness(); h.mount(); button(h.container, 'Hablar').click(); h.microphones[0].onend(); assert.match(h.container.textContent, /Micrófono cerrado/);
  button(h.container, 'Hablar').click(); h.microphones[1].onerror({error:'no-speech'}); assert.match(h.container.textContent, /No se detectó/);
  const broken = harness({recognitionThrows:true}); broken.mount(); button(broken.container, 'Hablar').click(); assert.match(broken.container.textContent, /No se pudo iniciar el micrófono/); broken.command('listo'); assert.equal(progress(broken.container), 'Paso 2 de 3');
});
test('mic stop button cancels listening without starting a second request', () => {
  const h = harness(); h.mount(); button(h.container, 'Hablar').click(); button(h.container, 'Detener micrófono').click(); assert.equal(h.microphones.length, 1); assert.equal(h.microphones[0].aborted, true); assert.match(h.container.textContent, /Micrófono detenido/);
});
test('starting microphone cancels own audio and starting audio aborts mic', () => {
  const h = harness(); h.mount(); button(h.container, 'Escuchar este paso').click(); button(h.container, 'Hablar').click(); assert.equal(h.calls.at(-1).type, 'cancel');
  button(h.container, 'Escuchar este paso').click(); assert.equal(h.microphones[0].aborted, true); assert.equal(h.calls.at(-1).type, 'speak');
});
test('hidden document cancels media and restoration never auto-resumes', () => {
  const h = harness(); h.mount(); button(h.container, 'Escuchar este paso').click(); h.visibility(true); assert.equal(h.calls.at(-1).type, 'cancel'); h.visibility(false); h.tick(60000); assert.equal(h.calls.filter(call => call.type === 'speak').length, 1); assert.ok(button(h.container, 'Reanudar'));
});
test('hidden ancestor mutation immediately cancels microphone', () => {
  const h = harness(); h.mount(); button(h.container, 'Hablar').click(); h.container.hidden = true; h.mutation(); assert.equal(h.microphones[0].aborted, true); h.tick(20000); assert.equal(h.microphones.length, 1);
});
test('identity loss is detected during media even without a DOM mutation', () => {
  const h = harness(); let current = true; h.mount({isCurrent:() => current}); button(h.container, 'Escuchar este paso').click(); current = false; h.tick(200); assert.equal(h.calls.at(-1).type, 'cancel');
  const previous = progress(h.container); h.command('listo'); assert.equal(progress(h.container), previous);
});
test('identity callback throwing fails closed without leaving microphone active', () => {
  const h = harness(); let broken = false; h.mount({isCurrent:() => { if (broken) throw new Error('signed out'); return true; }}); button(h.container, 'Hablar').click(); broken = true; h.tick(200); assert.equal(h.microphones[0].aborted, true);
});
test('detachment is observed and cancels owned audio', () => {
  const h = harness(); h.mount(); button(h.container, 'Escuchar este paso').click(); h.container.remove(); h.mutation(); assert.equal(h.calls.at(-1).type, 'cancel');
});
test('setActive(false) stops media and setActive(true) preserves step silently', () => {
  const h = harness(); const guide = h.mount({initialStep:1}); button(h.container, 'Escuchar este paso').click(); guide.setActive(false); assert.equal(byClass(h.container, 'recipe-guide').hidden, true); assert.equal(h.calls.at(-1).type, 'cancel');
  guide.setActive(true); assert.equal(progress(h.container), 'Paso 2 de 3'); assert.equal(byClass(h.container, 'recipe-guide').hidden, false); assert.equal(h.calls.filter(call => call.type === 'speak').length, 1);
});
test('dispose clears own DOM, media, all listeners, observer and timers; late callbacks do nothing', () => {
  const h = harness(); const guide = h.mount(); button(h.container, 'Hablar').click(); const late = h.microphones[0].onresult; guide.dispose(); guide.dispose(); guide.setActive(true);
  late({results:[[{transcript:'listo'}]]}); h.setVoices([esVoice]); h.tick(60000); assert.equal(h.container.children.length, 0); assert.equal(h.microphones[0].aborted, true); assert.equal(h.timers.size, 0);
  assert.equal(h.document.listenerCount(), 0); assert.equal(h.window.listenerCount(), 0); assert.equal(h.speech.listenerCount(), 0); assert.ok(h.observers.every(observer => !observer.connected));
});
test('remount on same container disposes earlier source and pending audio', () => {
  const h = harness({availableVoices:[]}); h.mount(); button(h.container, 'Escuchar este paso').click(); h.mount({title:'Otra receta', steps:['Paso de otra fuente.']}); h.setVoices([esVoice]); h.tick(60000); assert.equal(h.calls.length, 0); assert.equal(stepText(h.container), 'Paso de otra fuente.'); assert.equal(descendants(h.container).filter(el => el.className === 'recipe-guide').length, 1);
});
test('close disposes before notifying parent exactly once', () => {
  const h = harness(); let closed = 0; h.mount({onClose:() => { closed++; assert.equal(h.container.children.length, 0); }}); const close = button(h.container, 'Volver a la receta'); close.click(); close.click(); assert.equal(closed, 1);
});
test('pagehide cancels media without automatic reconnect', () => {
  const h = harness(); h.mount(); button(h.container, 'Hablar').click(); h.window.fire('pagehide'); h.tick(60000); assert.equal(h.microphones[0].aborted, true); assert.equal(h.microphones.length, 1);
});
test('parent onStepChange can unmount synchronously with no stale audio or focus work', () => {
  const h = harness(); let guide; guide = h.mount({onStepChange:() => guide.dispose()}); button(h.container, 'Escuchar este paso').click(); button(h.container, 'Listo, siguiente').click(); assert.equal(h.container.children.length, 0); assert.equal(h.calls.filter(call => call.type === 'speak').length, 1);
});

for (const command of ['listo', 'repite', '¿Qué hago ahora?', 'Roxy, repite por favor']) {
  test(`a first microphone command opts into its spoken reply: ${command}`, () => {
    const h = harness(); h.mount(); button(h.container, 'Hablar').click(); h.micResult(command);
    assert.equal(h.calls.filter(call => call.type === 'speak').length, 1);
    assert.equal(h.latestUtterance().text, command === 'listo' ? 'Cocina durante 15 minutos.' : 'Lava el arroz.');
    assert.equal(h.latestUtterance().voice, esVoice); assert.equal(h.microphones.length, 1);
  });
}
test('voice opt-in occurs after a final transcript, not merely microphone permission', () => {
  const h = harness(); h.mount(); button(h.container, 'Hablar').click(); h.microphones[0].onstart();
  h.micResult('repite', {final:false}); assert.equal(h.calls.length, 0);
  h.micResult('  '); h.command('repite'); assert.equal(h.calls.length, 0);
});
test('spoken pause stops media without replying over the requested silence', () => {
  const h = harness(); h.mount(); button(h.container, 'Hablar').click(); h.micResult('pausa');
  assert.equal(h.calls.length, 0); assert.ok(button(h.container, 'Reanudar'));
});
test('English source step remains English after a Spanish microphone command', () => {
  const h = harness(); h.mount({language:'en', steps:['Bake for 10 minutes at 350 °F.']});
  button(h.container, 'Hablar').click(); h.micResult('repite');
  assert.equal(h.latestUtterance().text, 'Bake for 10 minutes at 350 °F.'); assert.equal(h.latestUtterance().lang, 'en'); assert.equal(h.latestUtterance().voice, enVoice);
});
test('a spoken unsupported question receives a spoken limit, never a recipe invention', () => {
  const h = harness(); h.mount({language:'en', steps:['Wash rice.']});
  button(h.container, 'Hablar').click(); h.micResult('¿Puedo sustituir arroz por carne?');
  assert.match(response(h.container), /No puedo responder preguntas abiertas/);
  assert.equal(h.latestUtterance().text, response(h.container)); assert.equal(h.latestUtterance().lang, 'es'); assert.equal(h.latestUtterance().voice, esVoice);
  assert.equal(progress(h.container), 'Paso 1 de 1'); assert.deepEqual(h.forbidden, []);
});
test('a spoken boundary command answers without advancing past the final step', () => {
  const h = harness(); h.mount({initialStep:2}); button(h.container, 'Hablar').click(); h.micResult('listo');
  assert.match(h.latestUtterance().text, /último paso/); assert.equal(progress(h.container), 'Paso 3 de 3');
});
test('onend without actual onstart reports no audio instead of claiming completion', () => {
  const h = harness(); h.mount(); button(h.container, 'Escuchar este paso').click(); h.endAudio();
  assert.match(status(h.container), /voz no comenzó/); assert.doesNotMatch(status(h.container), /Lectura terminada/);
});
for (const action of ['Listo, siguiente', 'Repetir', 'Escuchar este paso']) {
  test(`own deferred cancel retries the current requested reading once: ${action}`, () => {
    const h = harness({deferredCancel:true}); h.mount(); button(h.container, 'Escuchar este paso').click(); h.startAudio();
    const staleEnd = h.latestUtterance().onend;
    button(h.container, action).click(); h.tick(150); assert.equal(h.calls.filter(call => call.type === 'speak').length, 1);
    h.speech.speaking = false; h.speech.pending = false; h.tick(50);
    assert.equal(h.calls.filter(call => call.type === 'speak').length, 2);
    assert.equal(h.latestUtterance().text, action === 'Listo, siguiente' ? 'Cocina durante 15 minutos.' : 'Lava el arroz.');
    h.startAudio(); staleEnd(); assert.equal(status(h.container), 'Leyendo este paso…');
    h.tick(1000); assert.equal(h.calls.filter(call => call.type === 'speak').length, 2);
    assert.equal(h.calls.filter(call => call.type === 'cancel').length, 1);
  });
}
test('multiple changes during a deferred cancel read only the newest step', () => {
  const h = harness({deferredCancel:true}); h.mount(); button(h.container, 'Escuchar este paso').click(); h.startAudio();
  button(h.container, 'Listo, siguiente').click(); h.tick(50); button(h.container, 'Listo, siguiente').click();
  h.speech.speaking = false; h.speech.pending = false; h.tick(50);
  assert.equal(h.latestUtterance().text, 'Deja reposar.'); assert.equal(h.calls.filter(call => call.type === 'speak').length, 2);
});
test('deferred cancellation wait is bounded and does not restart after timeout', () => {
  const h = harness({deferredCancel:true}); h.mount(); button(h.container, 'Escuchar este paso').click(); h.startAudio();
  button(h.container, 'Listo, siguiente').click(); h.tick(1000); assert.match(status(h.container), /anterior no se detuvo/);
  h.speech.speaking = false; h.speech.pending = false; h.setVoices([esVoice]); h.tick(60000);
  assert.equal(h.calls.filter(call => call.type === 'speak').length, 1); assert.equal(h.calls.filter(call => call.type === 'cancel').length, 1); assert.equal(h.timers.size, 0);
});
for (const endScope of ['close', 'dispose', 'member', 'hide', 'remount']) {
  test(`deferred cancel cannot resume after scope loss: ${endScope}`, () => {
    const h = harness({deferredCancel:true}); let current = true; const guide = h.mount({isCurrent:() => current});
    button(h.container, 'Escuchar este paso').click(); h.startAudio(); button(h.container, 'Listo, siguiente').click();
    if (endScope === 'close') button(h.container, 'Volver a la receta').click();
    if (endScope === 'dispose') guide.dispose();
    if (endScope === 'member') current = false;
    if (endScope === 'hide') h.visibility(true);
    if (endScope === 'remount') h.mount({steps:['Different recipe.'], language:'en'});
    h.speech.speaking = false; h.speech.pending = false; h.tick(60000); h.setVoices([esVoice, enVoice]);
    assert.equal(h.calls.filter(call => call.type === 'speak').length, 1); assert.equal(h.timers.size, 0);
  });
}
test('deferred own cancellation does not repeatedly cancel speech that remains busy', () => {
  const h = harness({deferredCancel:true}); const guide = h.mount(); button(h.container, 'Escuchar este paso').click(); h.startAudio();
  button(h.container, 'Listo, siguiente').click(); h.tick(2000); guide.dispose();
  assert.equal(h.calls.filter(call => call.type === 'cancel').length, 1); assert.equal(h.calls.filter(call => call.type === 'speak').length, 1);
});

const sourceFixtures = {
  es:{
    ingredients:['100 g de azúcar para el relleno.', '50 g de azúcar para la salsa.', '200 ml de leche.', '180 g de harina.', '20 g de cacahuetes.'],
    steps:['Usa un molde de 20 cm. Precalienta el horno a 200 °C; baja a 180 °C al introducir el molde.', 'Hornea 20 minutos; gira el molde y hornea otros 10 minutos.', 'Deja reposar 15 minutos.'],
  },
  en:{
    ingredients:['100 g sugar for the filling.', '50 g sugar for the sauce.', '200 ml milk.', '180 g flour.', '20 g peanuts.'],
    steps:['Use a 20 cm tin. Preheat the oven to 200 °C; reduce to 180 °C when inserting the tin.', 'Bake for 20 minutes; turn the tin and bake for another 10 minutes.', 'Leave to rest for 15 minutes.'],
  },
};
for (const language of ['es', 'en']) {
  for (const query of language === 'es' ? ['¿Cuánta leche lleva?', '¿Cuánto azúcar?', '¿Cuánto azúcar en total?', '¿Qué ingredientes?'] : ['How much milk?', 'How much sugar in total?', 'What ingredients?']) {
    test(`ingredient quantities are complete original excerpts, never inferred totals: ${language} ${query}`, () => {
      const h = harness(); const fixture = sourceFixtures[language]; h.mount({...fixture, language}); h.command(query);
      const text = response(h.container); assert.match(text, language === 'es' ? /Lista original completa/ : /Complete original ingredient list/);
      for (const line of fixture.ingredients) assert.ok(text.includes(line));
      assert.equal(text.endsWith(fixture.ingredients.join('\n')), true); assert.doesNotMatch(text, /150 g/);
      assert.equal(byClass(h.container, 'recipe-guide-response').lang, language);
      assert.equal(progress(h.container), 'Paso 1 de 3'); assert.equal(h.calls.length, 0); assert.deepEqual(h.forbidden, []);
    });
  }
  test(`temperature query preserves both competing values and conditions: ${language}`, () => {
    const h = harness(); const fixture = sourceFixtures[language]; h.mount({...fixture, language}); h.command(language === 'es' ? '¿A qué temperatura va el horno?' : 'What oven temperature?');
    const text = response(h.container); assert.match(text, language === 'es' ? /Fragmentos originales/ : /Original excerpts/);
    assert.ok(text.endsWith(fixture.steps[0])); assert.ok(text.includes('200 °C')); assert.ok(text.includes('180 °C'));
    assert.equal(text.includes(fixture.steps[1]), false); assert.equal(text.includes(fixture.ingredients[3]), false);
    assert.equal(h.calls.length, 0); assert.equal(progress(h.container), 'Paso 1 de 3');
  });
  test(`general time query returns all competing step times without adding a total: ${language}`, () => {
    const h = harness(); const fixture = sourceFixtures[language]; h.mount({...fixture, language}); h.command(language === 'es' ? '¿Cuánto tiempo tarda toda la receta?' : 'How long does the whole recipe take?');
    const text = response(h.container); assert.ok(text.includes(fixture.steps[1])); assert.ok(text.includes(fixture.steps[2])); assert.equal(text.includes(fixture.steps[0]), false);
    assert.doesNotMatch(text, /45 (?:minutes|minutos)|30 (?:minutes|minutos)/); assert.match(text, language === 'es' ? /no calculo totales/ : /do not calculate totals/);
  });
  test(`explicit current step restricts source retrieval without rewriting its two durations: ${language}`, () => {
    const h = harness(); const fixture = sourceFixtures[language]; h.mount({...fixture, language, initialStep:1}); h.command(language === 'es' ? '¿Cuánto tiempo en este paso?' : 'How long in this step?');
    const text = response(h.container); assert.ok(text.endsWith(fixture.steps[1])); assert.equal(text.includes(fixture.steps[2]), false); assert.equal(progress(h.container), 'Paso 2 de 3');
  });
  test(`source question through microphone speaks intact excerpts in source language: ${language}`, () => {
    const h = harness(); const fixture = sourceFixtures[language]; h.mount({...fixture, language}); button(h.container, 'Hablar').click(); h.micResult('¿A qué temperatura va el horno?');
    assert.equal(h.latestUtterance().text, response(h.container)); assert.ok(h.latestUtterance().text.endsWith(fixture.steps[0]));
    assert.equal(h.latestUtterance().lang, language); assert.equal(h.latestUtterance().voice, language === 'es' ? esVoice : enVoice);
  });
  test(`missing source quantities and missing time or temperature units remain explicit: ${language}`, () => {
    const h = harness(); h.mount({language, ingredients:[], steps:[language === 'es' ? 'Mezcla y hornea. Usa un molde de 20 cm.' : 'Mix and bake. Use a 20 cm tin.']});
    for (const query of ['ingredientes', '¿Cuánto tiempo?', '¿A qué temperatura?']) {
      h.command(query); assert.match(response(h.container), language === 'es' ? /no incluye|No encuentro/ : /does not include|No .* with units/);
      assert.doesNotMatch(response(h.container), /20 cm|180|350/); assert.equal(progress(h.container), 'Paso 1 de 1');
    }
  });
}
test('English Fahrenheit and abbreviation durations are preserved, not converted', () => {
  const h = harness(); h.mount({language:'en', steps:['Bake at 350°F for 20 min. Rest 10 mins.']}); h.command('What temperature?');
  assert.ok(response(h.container).endsWith('Bake at 350°F for 20 min. Rest 10 mins.')); assert.doesNotMatch(response(h.container), /°C/);
  h.command('How long?'); assert.ok(response(h.container).endsWith('Bake at 350°F for 20 min. Rest 10 mins.'));
});
test('Spanish action duration is not mistaken for an ingredient quantity query', () => {
  const h = harness(); h.mount(sourceFixtures.es);
  for (const query of ['¿Cuánto debe reposar?', '¿Cuánto hornear?']) {
    h.command(query); assert.match(response(h.container), /Fragmentos originales/); assert.doesNotMatch(response(h.container), /Lista original completa/);
    assert.ok(response(h.container).includes(sourceFixtures.es.steps[1])); assert.ok(response(h.container).includes(sourceFixtures.es.steps[2]));
    assert.match(response(h.container), /ni asigno valores a una acción concreta/);
  }
});
for (const query of ['¿Cuántos grados?', 'How many degrees?', 'How many minutes?', 'How many hours?', 'How many seconds?']) {
  test(`common unit questions retrieve source excerpts, never ingredients: ${query}`, () => {
    const h = harness(); h.mount(sourceFixtures.es); h.command(query);
    assert.match(response(h.container), /Fragmentos originales/); assert.doesNotMatch(response(h.container), /Lista original completa|No puedo responder preguntas abiertas/);
    assert.ok(response(h.container).includes(sourceFixtures.es.steps[/grados|degrees/.test(query) ? 0 : 1]));
  });
}
test('typed source answer offers an explicit listening button for the answer, not the current step', () => {
  const h = harness(); h.mount({...sourceFixtures.en, language:'en'}); assert.equal(button(h.container, 'Escuchar respuesta').hidden, true);
  assert.equal(button(h.container, 'Escuchar respuesta').disabled, true);
  h.command('How much milk?'); const originalAnswer = response(h.container); assert.equal(h.calls.length, 0);
  assert.equal(button(h.container, 'Escuchar respuesta').hidden, false); assert.equal(button(h.container, 'Escuchar respuesta').disabled, false); button(h.container, 'Escuchar respuesta').click();
  assert.equal(h.latestUtterance().text, originalAnswer); assert.equal(h.latestUtterance().voice, enVoice);
  h.latestUtterance().onerror({error:'not-allowed'}); button(h.container, 'Escuchar respuesta').click();
  assert.equal(h.latestUtterance().text, originalAnswer); assert.equal(h.calls.filter(call => call.type === 'speak').length, 2);
  button(h.container, 'Listo, siguiente').click(); assert.equal(button(h.container, 'Escuchar respuesta').hidden, true);
  assert.equal(button(h.container, 'Escuchar respuesta').disabled, true);
});
test('answer listening remains disabled without device speech', () => {
  const h = harness({tts:false}); h.mount(); h.command('¿Cuánto tiempo?'); assert.equal(button(h.container, 'Escuchar respuesta').disabled, true);
});
test('source whitespace and HTML-like text survive retrieval without DOM interpretation', () => {
  const original = '  Hornea <b>20 minutos</b>.\n Luego espera 10 minutos.  ';
  const h = harness(); h.mount({steps:[original]}); h.command('¿Cuánto tiempo?');
  assert.ok(response(h.container).endsWith(original)); assert.equal(byTag(h.container, 'b').length, 0);
});
for (const question of [
  'Soy alérgico a los cacahuetes, ¿puedo comerla si los retiro?',
  '¿Cuánto tiempo para que sea segura?', '¿A qué temperatura sé que está cocido?',
  '¿Cuánto tiempo si cambio la leche por agua?', '¿Cuánto tiempo sin cacahuetes?',
  'How much milk is safe with an allergy?', 'How long until it is done?',
  'It is still runny after 10 minutes. Is it safe to eat?', 'What temperature for raw meat?',
  'Next, and can I replace the peanuts with almonds?',
  'Siguiente y dime cuánto azúcar puedo quitar sin afectar la receta',
  '¿Cuánto tiempo y a qué temperatura?', 'How much sugar and how many minutes?',
  '¿Cuánta harina equivale a una taza?',
]) {
  test(`safety, adjustment and compound requests abstain with no partial execution: ${question}`, () => {
    const h = harness(); h.mount(sourceFixtures.es); h.command(question);
    assert.match(response(h.container), /No puedo responder preguntas abiertas/);
    assert.doesNotMatch(response(h.container), /Fragmentos originales|Lista original completa/);
    assert.equal(progress(h.container), 'Paso 1 de 3'); assert.deepEqual(h.calls, []); assert.deepEqual(h.forbidden, []);
  });
}
test('source answer waiting for a voice is discarded on a member switch', () => {
  const h = harness({availableVoices:[]}); let current = true; h.mount({...sourceFixtures.en, language:'en', isCurrent:() => current});
  button(h.container, 'Hablar').click(); h.micResult('How long?'); current = false; h.setVoices([esVoice, enVoice]); h.tick(60000);
  assert.equal(h.calls.length, 0); assert.equal(h.timers.size, 0);
});

const settleCompanion = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
const deferredCompanion = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return {promise, resolve, reject}; };
const companionAnswer = (answer = 'Batir consiste en mezclar con movimientos rápidos.', supporting_steps = [1]) => ({answer, supporting_steps, needs_clarification:false});
const aiText = h => byClass(h.container, 'recipe-guide-explanation-answer').textContent;
const preferences = h => byTag(h.container, 'input').find(el => el.type === 'checkbox');
const ask = (h, question = '¿Qué significa batir?') => { h.command(question); return settleCompanion(); };

test('companion is explicit, starts without a profile or history and preserves original source text', async () => {
  const calls = []; const h = harness(); h.mount({askQuestion:params => { calls.push(params); return companionAnswer(); }});
  assert.equal(preferences(h).checked, false); h.tick(10000); assert.equal(calls.length, 0);
  await ask(h); assert.equal(calls.length, 1);
  const request = calls[0]; assert.equal(request.question, '¿Qué significa batir?'); assert.equal(request.step_index, 0); assert.equal(request.language, 'es');
  assert.equal(request.include_preferences, false); assert.equal(request.history.length, 0); assert.ok(request.signal instanceof AbortSignal);
  assert.equal(aiText(h), companionAnswer().answer); assert.match(h.container.textContent, /Explicación de Roxy · IA/);
  assert.match(h.container.textContent, /Referencia en la receta: paso 1/); assert.equal(stepText(h.container), 'Lava el arroz.');
  assert.equal(response(h.container), ''); assert.equal(h.calls.length, 0); assert.deepEqual(h.forbidden, []);
});

test('literal commands and source queries remain local even with a companion', async () => {
  const calls = []; const h = harness(); h.mount({askQuestion:params => { calls.push(params); return companionAnswer(); }});
  for (const query of ['listo', 'atrás', 'repite', 'pausa', 'reanudar', 'qué hago ahora', 'ingredientes', 'cuánto tiempo', 'a qué temperatura']) await ask(h, query);
  assert.equal(calls.length, 0); assert.equal(progress(h.container), 'Paso 1 de 3');
});

test('busy companion never duplicates submissions and only retries after a deliberate click', async () => {
  const pending = deferredCompanion(), calls = []; const h = harness();
  h.mount({askQuestion:params => { calls.push(params); return calls.length === 1 ? pending.promise : companionAnswer(); }});
  await ask(h); assert.equal(button(h.container, 'Enviar').disabled, true); assert.equal(button(h.container, 'Hablar').disabled, true);
  await ask(h); assert.equal(calls.length, 1);
  pending.reject(new Error('sensitive backend internals')); await settleCompanion();
  assert.match(h.container.textContent, /No pude responder ahora/); assert.doesNotMatch(h.container.textContent, /sensitive backend internals/);
  h.tick(60000); await settleCompanion(); assert.equal(calls.length, 1);
  button(h.container, 'Reintentar pregunta').click(); await settleCompanion(); assert.equal(calls.length, 2);
  assert.equal(calls[1].question, calls[0].question); assert.equal(calls[1].history.length, 0); assert.equal(aiText(h), companionAnswer().answer);
});

test('a never-settling companion is aborted at 30 seconds and late completion stays ignored', async () => {
  const pending = deferredCompanion(), calls = []; const h = harness(); h.mount({askQuestion:params => { calls.push(params); return pending.promise; }});
  await ask(h); h.tick(29999); assert.equal(calls[0].signal.aborted, false); h.tick(1);
  assert.equal(calls[0].signal.aborted, true); assert.match(h.container.textContent, /respuesta tardó demasiado/);
  pending.resolve(companionAnswer('Respuesta tardía')); await settleCompanion(); assert.equal(aiText(h), '');
  assert.equal(button(h.container, 'Enviar').disabled, false); assert.equal(h.timers.size, 0);
});

test('explicit cancellation neither retries nor retains a late answer', async () => {
  const pending = deferredCompanion(), calls = []; const h = harness(); h.mount({askQuestion:params => { calls.push(params); return pending.promise; }});
  await ask(h); button(h.container, 'Cancelar pregunta').click(); assert.equal(calls[0].signal.aborted, true);
  pending.resolve(companionAnswer('No debe aparecer')); await settleCompanion(); h.tick(60000);
  assert.equal(aiText(h), ''); assert.equal(calls.length, 1); assert.equal(button(h.container, 'Reintentar pregunta').hidden, true);
});

for (const endScope of ['next', 'pause', 'close', 'dispose', 'member', 'hidden', 'inactive', 'detached', 'remount']) {
  test(`companion aborts and ignores a late response on ${endScope}`, async () => {
    const pending = deferredCompanion(), calls = []; const h = harness(); let current = true;
    const guide = h.mount({isCurrent:() => current, askQuestion:params => { calls.push(params); return pending.promise; }});
    await ask(h);
    if (endScope === 'next') button(h.container, 'Listo, siguiente').click();
    if (endScope === 'pause') button(h.container, 'Pausar').click();
    if (endScope === 'close') button(h.container, 'Volver a la receta').click();
    if (endScope === 'dispose') guide.dispose();
    if (endScope === 'member') { current = false; h.tick(200); }
    if (endScope === 'hidden') h.visibility(true);
    if (endScope === 'inactive') guide.setActive(false);
    if (endScope === 'detached') { h.container.remove(); h.mutation(); }
    if (endScope === 'remount') h.mount({steps:['Otra receta.']});
    assert.equal(calls[0].signal.aborted, true);
    pending.resolve(companionAnswer('Respuesta privada tardía')); await settleCompanion(); h.tick(60000);
    assert.doesNotMatch(h.container.textContent, /Respuesta privada tardía/); assert.equal(h.calls.length, 0); assert.equal(h.timers.size, 0);
  });
}

test('history contains only four completed question/answer pairs and cannot be mutated by the callback', async () => {
  const requests = []; const h = harness();
  h.mount({askQuestion:params => { requests.push(params); return companionAnswer(`Respuesta ${requests.length}`); }});
  for (let i = 1; i <= 6; i++) await ask(h, `Explica la técnica ${i}`);
  const history = requests[5].history;
  assert.equal(history.length, 8); assert.equal(history[0].content, 'Explica la técnica 2'); assert.equal(history[7].content, 'Respuesta 5');
  assert.equal(history.filter(entry => entry.role === 'user').length, 4); assert.equal(history.filter(entry => entry.role === 'assistant').length, 4);
  history[6].content = 'Alterado desde fuera'; await ask(h, 'Otra técnica');
  assert.equal(requests[6].history.some(entry => entry.content === 'Alterado desde fuera'), false); assert.deepEqual(h.forbidden, []);
});

test('profile opt-in and withdrawal reset history, abort pending requests and stay private to this mount', async () => {
  const pending = deferredCompanion(), calls = []; const h = harness();
  const options = {askQuestion:params => { calls.push(params); return calls.length === 2 ? pending.promise : companionAnswer(); }};
  h.mount(options); await ask(h);
  preferences(h).checked = true; preferences(h).fire('change'); await ask(h, 'Explica mi técnica');
  assert.equal(calls[1].include_preferences, true); assert.equal(calls[1].history.length, 0);
  preferences(h).checked = false; preferences(h).fire('change'); assert.equal(calls[1].signal.aborted, true);
  pending.resolve(companionAnswer('Preferencia privada')); await settleCompanion(); await ask(h, 'Explica otra técnica');
  assert.equal(calls[2].include_preferences, false); assert.equal(calls[2].history.length, 0); assert.doesNotMatch(h.container.textContent, /Preferencia privada/);
  h.mount(options); assert.equal(preferences(h).checked, false); await ask(h); assert.equal(calls[3].history.length, 0);
});

test('idle completed conversation is cleared when identity is lost', async () => {
  const calls = []; const h = harness(); let current = true;
  h.mount({isCurrent:() => current, askQuestion:params => { calls.push(params); return companionAnswer(); }});
  preferences(h).checked = true; preferences(h).fire('change'); await ask(h);
  current = false; h.tick(200); assert.equal(aiText(h), ''); assert.equal(preferences(h).checked, false);
  current = true; await ask(h); assert.equal(calls[1].history.length, 0); assert.equal(calls[1].include_preferences, false);
});

for (const mode of ['typed', 'microphone', 'listening']) {
  test(`companion speech respects the user's audio selection: ${mode}`, async () => {
    const h = harness(); h.mount({askQuestion:() => companionAnswer()});
    if (mode === 'listening') { button(h.container, 'Escuchar este paso').click(); h.startAudio(); h.endAudio(); }
    if (mode === 'microphone') { button(h.container, 'Hablar').click(); h.micResult('¿Qué significa batir?'); await settleCompanion(); }
    else await ask(h);
    if (mode === 'typed') assert.equal(h.calls.length, 0);
    else assert.equal(h.latestUtterance().text, companionAnswer().answer);
    if (mode === 'typed') { button(h.container, 'Escuchar explicación').click(); assert.equal(h.latestUtterance().text, aiText(h)); }
  });
}

for (const invalid of [{}, {answer:'', supporting_steps:[], needs_clarification:false}, companionAnswer('Texto', [0]), companionAnswer('Texto', [4]), {...companionAnswer(), needs_clarification:'yes'}]) {
  test(`invalid companion output is rejected without displaying an unsupported answer: ${JSON.stringify(invalid)}`, async () => {
    const h = harness(); h.mount({askQuestion:() => invalid}); await ask(h);
    assert.equal(aiText(h), ''); assert.match(h.container.textContent, /No recibí una respuesta completa/); assert.equal(stepText(h.container), 'Lava el arroz.');
  });
}

test('AI output is plain text, carries one-based source references, and can request clarification', async () => {
  const h = harness(); h.mount({askQuestion:() => ({answer:'<img src=x onerror=alert(1)> ¿Usas varillas?', supporting_steps:[1,3,1], needs_clarification:true})}); await ask(h);
  assert.equal(byTag(h.container, 'img').length, 0); assert.match(aiText(h), /^<img/);
  assert.match(h.container.textContent, /pasos 1, 3/); assert.match(h.container.textContent, /necesita un detalle más/); assert.equal(progress(h.container), 'Paso 1 de 3');
});

test('conversationOnly delegates commands without duplicating source navigation or mutating the step', async () => {
  const commands = [], questions = []; const h = harness(); h.mount({conversationOnly:true, initialStep:1,
    onCommand:command => commands.push(command), askQuestion:params => { questions.push(params); return companionAnswer(); }});
  for (const name of ['recipe-guide-heading', 'recipe-guide-title', 'recipe-guide-progress', 'recipe-guide-step', 'recipe-guide-navigation', 'recipe-guide-controls', 'recipe-guide-ingredients']) assert.equal(byClass(h.container, name).hidden, true);
  for (const command of ['siguiente', 'atrás', 'pausa', 'reanudar', 'repite']) await ask(h, command);
  assert.deepEqual(commands, ['next','previous','pause','resume','repeat']); assert.equal(progress(h.container), 'Paso 2 de 3'); assert.equal(questions.length, 0);
  await ask(h); assert.equal(questions[0].step_index, 1); assert.equal(progress(h.container), 'Paso 2 de 3');
});

test('conversationOnly without external command support explains how to use existing recipe controls', async () => {
  const h = harness(); h.mount({conversationOnly:true}); h.command('siguiente');
  assert.match(response(h.container), /Usa los botones de la receta/); assert.equal(progress(h.container), 'Paso 1 de 3');
});

test('parent audio hook runs before recognition and speech and a disposed scope never starts audio', () => {
  const events = []; const h = harness(); let guide;
  guide = h.mount({onBeforeMedia:() => events.push('before')}); button(h.container, 'Hablar').click(); assert.deepEqual(events, ['before']);
  h.micResult('repite'); assert.deepEqual(events, ['before','before']); assert.equal(h.calls.filter(call => call.type === 'speak').length, 1);
  guide.dispose(); guide = h.mount({onBeforeMedia:() => guide.dispose()}); button(h.container, 'Escuchar este paso').click();
  assert.equal(h.container.children.length, 0); assert.equal(h.calls.filter(call => call.type === 'speak').length, 1);
});

test('deterministic safety notices are not presented as an AI explanation', async () => {
  const h = harness(); h.mount({askQuestion:() => ({...companionAnswer('No puedo confirmar que sea compatible con tu alergia.', []), mode:'safety_notice', needs_clarification:true})});
  await ask(h, '¿Puedo tomarlo con alergia?');
  const panel = byClass(h.container, 'recipe-guide-explanation'); assert.match(panel.textContent, /Aviso de seguridad de Roxy/);
  assert.doesNotMatch(panel.textContent, /Explicación de Roxy · IA|necesita un detalle más/); assert.ok(button(h.container, 'Escuchar aviso'));
});

test('question and response lengths match the companion API before any retry is offered', async () => {
  const requests = []; const h = harness(); h.mount({askQuestion:params => { requests.push(params); return companionAnswer(); }});
  assert.equal(byTag(h.container, 'input')[0].maxLength, 600); await ask(h, 'x'.repeat(601));
  assert.equal(requests.length, 0); assert.match(h.container.textContent, /hasta 600 caracteres/); assert.equal(button(h.container, 'Reintentar pregunta').hidden, true);
  await ask(h, 'x'.repeat(600)); assert.equal(requests.length, 1);
  h.mount({askQuestion:() => companionAnswer('x'.repeat(1601))}); await ask(h);
  assert.equal(aiText(h), ''); assert.match(h.container.textContent, /No recibí una respuesta completa/);
});

for (const replyLanguage of [undefined, 'es', 'en', 'fr']) {
  test(`AI response uses its declared language or Spanish UI fallback, independently from an English source: ${replyLanguage}`, async () => {
    const h = harness(); h.mount({language:'en', steps:['Whisk the eggs.'], askQuestion:() => ({...companionAnswer('Explicación de la técnica'), language:replyLanguage})});
    button(h.container, 'Hablar').click(); h.micResult('¿Qué significa batir?'); await settleCompanion();
    const expected = replyLanguage === 'en' ? 'en' : 'es';
    assert.equal(h.latestUtterance().lang, expected); assert.equal(byClass(h.container, 'recipe-guide-explanation-answer').lang, expected);
    assert.equal(stepText(h.container), 'Whisk the eggs.'); assert.equal(byClass(h.container, 'recipe-guide-step').lang, 'en');
    h.startAudio(); h.endAudio(); button(h.container, 'Escuchar explicación').click(); assert.equal(h.latestUtterance().lang, expected);
  });
}

for (const [statusCode, detail, expected, retryable] of [
  [409, 'Esta versión ya no está disponible.', /Esta versión ya no está disponible.*Vuelve a abrir la receta/, false],
  [422, 'Completa tus gustos de recetas para poder incluirlos.', /Completa tus gustos de recetas.*Revisa tu pregunta o tus gustos/, false],
  [422, '[object Object],[object Object]', /Falta revisar la pregunta o tu perfil/, false],
  [422, '[{"loc":["body","question"],"input":"privado"}]', /Falta revisar la pregunta o tu perfil/, false],
  [503, 'El acompañamiento de Roxy no está habilitado.', /El acompañamiento de Roxy no está habilitado.*Puedes continuar/, true],
  [503, 'HTTP 503', /La conversación de Roxy no está disponible ahora/, true],
  [429, 'quota internals', /La conversación alcanzó su límite/, true],
]) {
  test(`companion errors offer a specific recovery and retry only when useful: ${statusCode} ${detail}`, async () => {
    let calls = 0; const h = harness(); h.mount({askQuestion:() => { calls++; throw Object.assign(new Error(detail), {status:statusCode}); }});
    await ask(h); assert.match(h.container.textContent, expected); assert.equal(button(h.container, 'Reintentar pregunta').hidden, !retryable);
    assert.doesNotMatch(h.container.textContent, /\[object Object\]|quota internals|"loc"|"input"/); assert.equal(button(h.container, 'Enviar').disabled, false);
    h.tick(60000); await settleCompanion(); assert.equal(calls, 1); assert.equal(stepText(h.container), 'Lava el arroz.');
  });
}

test('compact companion keeps OpenAI disclosure and opt-in visible while longer explanations stay in closed privacy details', async () => {
  const h = harness(); h.mount({askQuestion:() => companionAnswer()});
  const privacy = byClass(h.container, 'recipe-guide-privacy'), disclosure = byClass(h.container, 'recipe-guide-disclosure');
  const preference = preferences(h), note = descendants(privacy).find(el => el.id === preference.getAttribute('aria-describedby'));
  assert.equal(privacy.open, false); assert.equal(byTag(privacy, 'summary')[0].textContent, 'Voz y privacidad');
  assert.equal(privacy.textContent.includes('Las preguntas abiertas se envían a OpenAI'), true);
  assert.equal(privacy.textContent.includes('«Hablar» pide permiso de micrófono'), true);
  assert.ok(note); assert.match(note.textContent, /tus cocinas, alergias, alimentos que evitas y experiencia/);
  assert.equal(preference.getAttribute('aria-details'), privacy.id); assert.equal(preference.checked, false);
  assert.equal(descendants(privacy).includes(preference), false); assert.equal(descendants(privacy).includes(disclosure), false);
  assert.equal(disclosure.hidden, false); assert.match(disclosure.textContent, /Preguntas a OpenAI · voz opcional del dispositivo/);
  assert.equal(disclosure.parentNode, byTag(h.container, 'form')[0]); assert.equal(byTag(privacy, 'a')[0].href, '/privacy#guia-ia');
  const conversation = byClass(h.container, 'recipe-guide-conversation'), explanation = byClass(h.container, 'recipe-guide-explanation');
  assert.ok(conversation.children.indexOf(explanation) < conversation.children.indexOf(privacy));
  assert.equal(byClass(h.container, 'recipe-guide-step').hidden, false); assert.equal(byClass(h.container, 'recipe-guide-navigation').hidden, false);
  await ask(h); assert.equal(explanation.hidden, false); assert.equal(privacy.open, false); assert.equal(aiText(h), companionAnswer().answer);
});

test('literal-only guide has compact voice help without claiming it sends questions to OpenAI', () => {
  const h = harness(); h.mount(); const privacy = byClass(h.container, 'recipe-guide-privacy');
  assert.equal(privacy.open, false); assert.match(privacy.textContent, /siguiente, listo, repite/);
  assert.equal(byClass(h.container, 'recipe-guide-disclosure').textContent, 'Voz opcional del dispositivo.');
  assert.equal(byTag(h.container, 'input').filter(el => el.type === 'checkbox').length, 0);
});

test('focusActiveQuestion focuses the recipe chat without microphone, network or an automatic question', () => {
  const h = harness(); let asked = 0; const guide = h.mount({askQuestion:() => { asked++; return companionAnswer(); }});
  const input = byTag(h.container, 'input')[0]; assert.equal(h.window.RoxyRecipeGuide.focusActiveQuestion(), true); assert.equal(input.focused, true);
  assert.equal(asked, 0); assert.equal(h.microphones.length, 0); assert.deepEqual(h.calls, []); assert.deepEqual(h.forbidden, []);
  guide.dispose(); input.focused = false; assert.equal(h.window.RoxyRecipeGuide.focusActiveQuestion(), false);
  assert.equal(input.focused, false); assert.equal(h.container.children.length, 0);
});

for (const invalid of ['inactive', 'hidden', 'document', 'identity', 'detached']) {
  test(`focusActiveQuestion cannot focus or reopen an unavailable guide: ${invalid}`, () => {
    const h = harness(); let current = true; const guide = h.mount({isCurrent:() => current, askQuestion:() => companionAnswer()});
    const input = byTag(h.container, 'input')[0]; input.focused = false;
    if (invalid === 'inactive') guide.setActive(false);
    if (invalid === 'hidden') h.container.hidden = true;
    if (invalid === 'document') h.visibility(true);
    if (invalid === 'identity') current = false;
    if (invalid === 'detached') h.container.remove();
    assert.equal(h.window.RoxyRecipeGuide.focusActiveQuestion(), false); assert.equal(input.focused, false);
    if (invalid === 'inactive') assert.equal(byClass(h.container, 'recipe-guide').hidden, true);
    if (invalid === 'hidden') assert.equal(h.container.hidden, true);
    assert.equal(h.microphones.length, 0); assert.deepEqual(h.calls, []); assert.deepEqual(h.forbidden, []);
  });
}

test('focusActiveQuestion chooses the most recently mounted usable chat and skips literal-only guides', () => {
  const h = harness(); h.mount({askQuestion:() => companionAnswer()}); const firstInput = byTag(h.container, 'input')[0];
  const other = h.document.createElement('div'); h.document.body.append(other);
  const newer = h.window.RoxyRecipeGuide.mount(other, {steps:['Otro paso.'], askQuestion:() => companionAnswer()});
  const secondInput = byTag(other, 'input')[0]; assert.equal(h.window.RoxyRecipeGuide.focusActiveQuestion(), true); assert.equal(secondInput.focused, true); assert.notEqual(firstInput.focused, true);
  newer.setActive(false); firstInput.focused = false; assert.equal(h.window.RoxyRecipeGuide.focusActiveQuestion(), true); assert.equal(firstInput.focused, true);
  h.mount(); assert.equal(h.window.RoxyRecipeGuide.focusActiveQuestion(), false); newer.dispose(); assert.equal(h.window.RoxyRecipeGuide.focusActiveQuestion(), false);
});
