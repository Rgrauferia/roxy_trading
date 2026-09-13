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
function harness({tts = true, microphone = true, availableVoices = [esVoice, enVoice], speakThrows = false, recognitionThrows = false} = {}) {
  let now = 0, timerSequence = 0, list = availableVoices;
  const timers = new Map(), calls = [], microphones = [], observers = [], forbidden = [];
  const document = new Target(); document.hidden = false; document.body = new Element('body'); document.body.isRoot = true;
  document.documentElement = document.body; document.createElement = tag => new Element(tag);
  const window = new Target();
  const speech = new Target(); speech.speaking = false; speech.pending = false;
  speech.getVoices = () => list;
  speech.speak = utterance => { calls.push({type:'speak', utterance}); if (speakThrows) throw new Error('device failed'); speech.pending = true; };
  speech.cancel = () => { calls.push({type:'cancel'}); speech.speaking = false; speech.pending = false; };
  if (tts) { window.speechSynthesis = speech; window.SpeechSynthesisUtterance = class { constructor(text) { this.text = text; } }; }
  if (microphone) window.SpeechRecognition = class {
    constructor() { microphones.push(this); }
    start() { this.started = true; if (recognitionThrows) throw new Error('blocked'); }
    abort() { this.aborted = true; }
  };
  window.MutationObserver = class { constructor(callback) { this.callback = callback; this.connected = false; observers.push(this); } observe() { this.connected = true; } disconnect() { this.connected = false; } };
  const deny = name => { forbidden.push(name); throw new Error(`Forbidden ${name}`); };
  vm.runInNewContext(code, {window, document, setTimeout(fn, delay = 0) { const id = ++timerSequence; timers.set(id, {fn, due:now + delay}); return id; }, clearTimeout(id) { timers.delete(id); },
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
  assert.match(response(h.container), /Todavía no responde preguntas abiertas ni propone sustituciones/); assert.equal(progress(h.container), 'Paso 1 de 3'); assert.deepEqual(h.forbidden, []);
});
test('ambiguous compound command is not partially executed', () => {
  const h = harness(); h.mount(); h.command('siguiente y ponlo a 300 grados'); assert.equal(progress(h.container), 'Paso 1 de 3'); assert.match(response(h.container), /no responde preguntas abiertas ni propone sustituciones/);
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
test('microphone begins only after Hablar and remains one-shot', () => {
  const h = harness(); h.mount(); button(h.container, 'Hablar').click(); const mic = h.microphones[0]; assert.equal(mic.continuous, false); assert.equal(mic.interimResults, false); assert.equal(mic.lang, 'es-ES');
  mic.onstart(); h.micResult('listo'); assert.equal(mic.aborted, true); assert.equal(progress(h.container), 'Paso 2 de 3'); h.tick(60000); assert.equal(h.microphones.length, 1); assert.equal(h.calls.length, 0);
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
