/* Execute the Home voice implementation with synthetic audio, DOM, and network. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../assets/roxy_list.js'), 'utf8');
function section(first, last) {
  const begin = source.indexOf(first), end = source.indexOf(last, begin);
  assert.ok(begin >= 0 && end > begin, `Missing ${first}`);
  return source.slice(begin, end);
}
const executable = section('  let roxyDeviceSpeech=', '  function populateHomeForms(')
  + section('  let roxyVoiceConversation=', '  function renderProductLookup(');
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return {promise, resolve}; };
function harness({provider = true, fetchReply, audioReject = false, speechAvailable = true} = {}) {
  const nodes = new Map(), timers = new Map(), audio = [], spoken = [], requests = [], messages = [], revoked = [];
  let nextTimer = 0, cancellations = 0, automaticTimers = 0, microphoneCalls = 0, companionDisposals = 0;
  function element(id = '') {
    const listeners = new Map();
    return {id, textContent:'', hidden:false, disabled:false, value:'', open:false, children:[], listeners,
      classList:{add() {}, remove() {}, toggle() {}},
      setAttribute() {}, focus() {},
      append(child) { this.children.push(child); child.parentElement = this; if (child.id) nodes.set(child.id, child); },
      addEventListener(name, callback) { if (!listeners.has(name)) listeners.set(name, []); listeners.get(name).push(callback); },
      emit(name, detail = {}) { return Promise.all((listeners.get(name) || []).map(callback => callback({type:name, target:this, ...detail}))); },
    };
  }
  for (const id of ['cookingDialog','speakStepButton','roxyVoicePanel','roxyVoiceLauncher','roxyVoiceStatus','roxyVoiceTranscript','roxyVoiceStart','roxyVoiceEnd','roxyTextMessage','roxyTextSend']) nodes.set(id, element(id));
  nodes.get('cookingDialog').open = true; nodes.get('speakStepButton').parentElement = nodes.get('cookingDialog');
  const document = {...element(), hidden:false, createElement:() => element()};
  const synth = {speaking:false, pending:false, getVoices:() => [{lang:'es-US', localService:true, name:'Synthetic local voice'}],
    speak(utterance) { spoken.push(utterance); }, cancel() { cancellations++; }};
  const browser = {...element(), ...(speechAvailable ? {speechSynthesis:synth, SpeechSynthesisUtterance:class { constructor(text) { this.text = text; } }} : {})};
  const timer = (callback, delay) => { const id = ++nextTimer; timers.set(id, {callback, delay}); return id; };
  const ctx = {window:browser, document, navigator:{mediaDevices:{getUserMedia:async () => { microphoneCalls++; throw new Error('No real microphone in this test'); }}},
    $:id => nodes.get(id) || null, user:'synthetic-home', account:{mode:'member', id:'member-a'},
    collectionIdentity:() => `${ctx.account.mode}:${ctx.account.id}`,
    checkCollectionContext:(owner, identity) => { if (owner !== ctx.user || identity !== ctx.collectionIdentity()) throw new Error('Session changed'); },
    currentCooking:{session:{id:'session-a', status:'ACTIVE'}, step_number:1, current_step:'Mezcla sin omitir el final.'},
    homeFood:{voice_service:{enabled:provider}}, roxyStepAudio:null,
    AbortController, DOMException, Date, console,
    setTimeout:timer, clearTimeout:id => timers.delete(id), setInterval:timer, clearInterval:id => timers.delete(id),
    URL:{createObjectURL:() => 'blob:synthetic', revokeObjectURL:url => revoked.push(url)},
    Audio:class {
      constructor(url) { this.url = url; this.listeners = new Map(); this.playCalls = 0; this.paused = false; audio.push(this); }
      addEventListener(name, callback) { this.listeners.set(name, callback); }
      emit(name) { this.listeners.get(name)?.(); }
      pause() { this.paused = true; }
      async play() { this.playCalls++; if (audioReject) throw new DOMException('Gesture required', 'NotAllowedError'); }
    },
    fetch:async (url, options) => { requests.push({url, options}); return fetchReply ? fetchReply(url, options) : {ok:false}; },
    startSynchronizedStepVideo:async (media, current) => { await Promise.resolve(); if (current()) await media.play(); },
    stopSynchronizedStepVideo() {}, startAutomaticStepTimer:() => { automaticTimers++; }, announce:text => messages.push(text),
    api:async () => { throw new Error('Unexpected backend request'); }, load:async () => {},
    activeItems:() => [], activePersonName:() => 'Synthetic member',
    disposeCookingCompanion:() => { companionDisposals++; },
  };
  vm.createContext(ctx); vm.runInContext(executable, ctx);
  const tick = delay => { for (const [id, value] of [...timers]) if (value.delay === delay && timers.has(id)) value.callback(); };
  return {ctx, nodes, spoken, requests, messages, audio, timers, revoked, document, synth, tick,
    cancellations:() => cancellations, automaticTimers:() => automaticTimers, microphoneCalls:() => microphoneCalls,
    companionDisposals:() => companionDisposals};
}

test('failed official step request reads the full same step on the device without an ElevenLabs conversation', async () => {
  const h = harness(); h.ctx.currentCooking.current_step = 'Texto largo completo. '.repeat(100) + 'FINAL EXACTO.';
  await h.ctx.speakCurrentStep();
  assert.equal(h.requests.length, 1); assert.equal(h.spoken.length, 1);
  assert.equal(h.spoken[0].text, `Paso 1. ${h.ctx.currentCooking.current_step}`);
  assert.equal(h.spoken[0].voice.localService, true);
  assert.doesNotMatch(h.nodes.get('cookingSpeechStatus').textContent, /hablando/);
  h.spoken[0].onstart(); assert.match(h.nodes.get('cookingSpeechStatus').textContent, /dispositivo.*hablando/);
  h.spoken[0].onend(); assert.equal(h.automaticTimers(), 0, 'Narration never starts cooking timers');
  assert.equal(h.nodes.get('speakStepButton').textContent, 'Escuchar paso');
  assert.equal(h.microphoneCalls(), 0);
});

test('unconfigured official TTS uses device speech without making a provider request', async () => {
  const h = harness({provider:false}); await h.ctx.speakCurrentStep();
  assert.equal(h.requests.length, 0); assert.equal(h.spoken.length, 1);
});

test('a cooking MP3 can play without claiming to speak before its playing event', async () => {
  const h = harness({fetchReply:async () => ({ok:true, blob:async () => ({})})});
  await h.ctx.speakCurrentStep(); assert.equal(h.audio[0].playCalls, 1); assert.equal(h.spoken.length, 0);
  assert.doesNotMatch(h.nodes.get('cookingSpeechStatus').textContent, /hablando/);
  h.audio[0].emit('playing'); assert.match(h.nodes.get('cookingSpeechStatus').textContent, /oficial.*hablando/);
  h.audio[0].emit('ended'); assert.equal(h.automaticTimers(), 0, 'Narration is not a timer confirmation'); assert.deepEqual(h.revoked, ['blob:synthetic']);
});

test('autoplay rejection and MP3 errors fall back once and revoke the unused audio URL', async () => {
  const h = harness({audioReject:true, fetchReply:async () => ({ok:true, blob:async () => ({})})});
  await h.ctx.speakCurrentStep(); assert.equal(h.spoken.length, 1); assert.deepEqual(h.revoked, ['blob:synthetic']);
  h.audio[0].emit('error'); assert.equal(h.spoken.length, 1);
});

test('provider timeout falls back and ignores a late successful MP3 response', async () => {
  const pending = deferred(), h = harness({fetchReply:() => pending.promise});
  const reading = h.ctx.speakCurrentStep(); h.tick(12000);
  assert.equal(h.requests[0].options.signal.aborted, true); assert.equal(h.spoken.length, 1);
  pending.resolve({ok:true, blob:async () => ({})}); await reading;
  assert.equal(h.audio.length, 0); assert.equal(h.spoken.length, 1);
});

for (const change of ['step','session','identity','user','closed','hidden']) {
  test(`late speech result is discarded after ${change} changes`, async () => {
    const pending = deferred(), h = harness({fetchReply:() => pending.promise});
    const reading = h.ctx.speakCurrentStep();
    if (change === 'step') h.ctx.currentCooking.step_number++;
    if (change === 'session') h.ctx.currentCooking.session.id = 'session-b';
    if (change === 'identity') h.ctx.account.id = 'member-b';
    if (change === 'user') h.ctx.user = 'different-home';
    if (change === 'closed') h.nodes.get('cookingDialog').open = false;
    if (change === 'hidden') h.document.hidden = true;
    pending.resolve({ok:true, blob:async () => ({})}); await reading; h.tick(250);
    assert.equal(h.spoken.length, 0); assert.equal(h.audio.length, 0); assert.equal(h.automaticTimers(), 0);
    assert.equal(h.requests[0].options.signal.aborted, true);
  });
}

test('closing cooking stops a device utterance and detaches its timer callback', async () => {
  const h = harness({provider:false}); await h.ctx.speakCurrentStep(); const speech = h.spoken[0];
  await h.nodes.get('cookingDialog').emit('close');
  assert.equal(speech.onend, null); assert.equal(h.cancellations(), 1); assert.equal(h.automaticTimers(), 0);
  assert.equal(h.companionDisposals(), 1);
});

test('a device speech start timeout restores a retry button and never starts a cooking timer', async () => {
  const h = harness({provider:false}); await h.ctx.speakCurrentStep(); h.tick(6000);
  assert.match(h.nodes.get('cookingSpeechStatus').textContent, /no inició/);
  assert.equal(h.nodes.get('speakStepButton').textContent, 'Escuchar paso');
  assert.equal(h.automaticTimers(), 0); assert.equal(h.spoken[0].onend, null);
});

test('an end event without a speech start cannot claim completion or start a cooking timer', async () => {
  const h = harness({provider:false}); await h.ctx.speakCurrentStep(); h.spoken[0].onend();
  assert.match(h.nodes.get('cookingSpeechStatus').textContent, /no inició/);
  assert.equal(h.automaticTimers(), 0);
});

test('unsupported device speech reports the limitation while keeping the recipe text', async () => {
  const h = harness({provider:false, speechAvailable:false}); await h.ctx.speakCurrentStep();
  assert.match(h.nodes.get('cookingSpeechStatus').textContent, /texto sigue disponible/);
  assert.equal(h.ctx.currentCooking.current_step, 'Mezcla sin omitir el final.');
  assert.equal(h.nodes.get('speakStepButton').disabled, false);
});

test('text responses remain silent until the user explicitly presses Listen', async () => {
  const h = harness(); h.ctx.roxyVoiceTranscript('Respuesta completa para leer.');
  assert.equal(h.spoken.length, 0); assert.equal(h.requests.length, 0);
  await h.nodes.get('roxyTextListen').emit('click');
  assert.equal(h.spoken.length, 1); assert.equal(h.spoken[0].text, 'Respuesta completa para leer.');
  assert.equal(h.microphoneCalls(), 0);
  await h.nodes.get('roxyTextListen').emit('click'); assert.equal(h.spoken[0].onend, null);
});

test('a response belonging to the previous member cannot be played', async () => {
  const h = harness(); h.ctx.roxyVoiceTranscript('Mensaje del miembro anterior.'); h.ctx.account.id = 'member-b';
  await h.nodes.get('roxyTextListen').emit('click'); assert.equal(h.spoken.length, 0);
});

test('opening the widget does not imply connection, request microphone or call a provider', () => {
  const h = harness(); h.ctx.openRoxyVoice();
  assert.match(h.nodes.get('roxyVoiceStatus').textContent, /Pulsa Iniciar/);
  assert.equal(h.microphoneCalls(), 0); assert.equal(h.requests.length, 0);
});

test('missing Home conversation configuration is checked before microphone access', async () => {
  const h = harness(); h.ctx.api = async () => { throw new Error('Home agent missing'); };
  await h.ctx.startRoxyVoice(); assert.equal(h.microphoneCalls(), 0);
  assert.match(h.nodes.get('roxyVoiceStatus').textContent, /agente exclusivo/);
  assert.equal(h.nodes.get('roxyVoiceStart').disabled, false);
});

test('legacy READY is rejected as unverified configuration before microphone access', async () => {
  const h = harness(); h.ctx.api = async () => ({status:'READY', agent_id:'shared-product-agent'});
  await h.ctx.startRoxyVoice(); assert.equal(h.microphoneCalls(), 0);
  assert.match(h.nodes.get('roxyVoiceStatus').textContent, /agente exclusivo/);
});

test('a configured Home agent proceeds to the microphone permission step only after configuration', async () => {
  const h = harness(); h.ctx.api = async () => ({status:'CONFIGURED', agent_id:'home-agent', provider_health_verified:false});
  await h.ctx.startRoxyVoice(); assert.equal(h.microphoneCalls(), 1);
});

test('billing rejection gives an actionable message without retrying', () => {
  const h = harness(); assert.match(h.ctx.roxyVoiceError(new Error('[payment_issue] unresolved payment'), 'conversación'), /pago pendiente.*administradora/);
  assert.equal(h.requests.length, 0); assert.equal(h.microphoneCalls(), 0);
});

test('resetting Home identity removes the previous transcript and cancels its device audio', async () => {
  const h = harness(); h.ctx.roxyVoiceTranscript('Respuesta privada anterior.');
  await h.nodes.get('roxyTextListen').emit('click'); h.ctx.resetRoxyVoiceContext();
  assert.equal(h.spoken[0].onend, null); assert.equal(h.nodes.get('roxyTextListen').hidden, true);
  assert.doesNotMatch(h.nodes.get('roxyVoiceTranscript').textContent, /privada anterior/);
});

test('an old backend command result cannot populate the new member response or trigger a refresh', async () => {
  const h = harness(), pending = deferred(); let refreshes = 0;
  h.ctx.api = () => pending.promise; h.ctx.load = async () => { refreshes++; };
  const command = h.ctx.sendRoxyHomeCommand({command:'Lista'}); h.ctx.account.id = 'new-member';
  pending.resolve({message:'Dato privado anterior.'}); await assert.rejects(command, /Session changed/);
  assert.equal(refreshes, 0); assert.doesNotMatch(h.nodes.get('roxyVoiceTranscript').textContent, /privado anterior/);
});

test('delayed official speech recovery cannot enter a different conversation', () => {
  const h = harness(), messages = []; h.ctx.testConversation = {sendUserMessage:text => messages.push(text)};
  vm.runInContext('roxyVoiceConversation = testConversation', h.ctx);
  h.ctx.recoverRoxyVoiceSpeech('Resultado de otra conversación', Date.now());
  vm.runInContext('roxyVoiceAttempt++', h.ctx); h.tick(3200); assert.deepEqual(messages, []);
});

test('provider payment error releases microphone, shows billing status, and does not reconnect', async () => {
  const h = harness(); let options, sessions = 0, releases = 0;
  h.ctx.api = async () => ({status:'CONFIGURED', agent_id:'home-only-agent'});
  h.ctx.navigator.mediaDevices.getUserMedia = async () => ({getTracks:() => [{stop:() => { releases++; }}]});
  h.ctx.testStartSession = async config => { options = config; sessions++; config.onConnect(); return {endSession:async () => {}}; };
  vm.runInContext('roxyElevenLabsModule = {Conversation:{startSession:testStartSession}}', h.ctx);
  await h.ctx.startRoxyVoice(); assert.equal(options.agentId, 'home-only-agent'); assert.equal(releases, 1);
  options.onError(new Error('[payment_issue] unresolved payment'));
  await new Promise(setImmediate);
  assert.match(h.nodes.get('roxyVoiceStatus').textContent, /pago pendiente/);
  assert.equal(sessions, 1); assert.equal(h.nodes.get('roxyVoiceStart').disabled, false);
});
