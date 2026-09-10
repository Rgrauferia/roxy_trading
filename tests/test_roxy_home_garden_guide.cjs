// Synthetic DOM and profiles only: no real household, provider, or microphone.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../assets/roxy_garden_guide.js'), 'utf8');
const species = [
  { key: 'unknown', common_name: 'Por identificar' },
  { key: 'pothos', common_name: 'Pothos', scientific_name: 'Epipremnum aureum', light: 'Luz indirecta media a brillante', soil_rule: 'Comprueba la tierra antes de regar.', toxicity: 'No dejar que las mascotas la mastiquen.' },
  { key: 'aloe', common_name: 'Aloe vera', scientific_name: 'Aloe vera', light: 'Luz brillante', soil_rule: 'Espera a que el sustrato esté seco.' },
];
const photo = 'data:image/jpeg;base64,/9j/2Q==';
class Node {
  constructor(tag, doc) { this.tagName = tag; this.doc = doc; this.children = []; this.attributes = {}; this.dataset = {}; this.listeners = {}; this.value = ''; this.hidden = false; this.disabled = false; this.isConnected = true; this._text = ''; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(' '); }
  set innerHTML(_) { throw new Error('Untrusted text must never enter innerHTML.'); }
  append(...nodes) { nodes.forEach(node => { this.children.push(node); node.parent = this; }); }
  replaceChildren(...nodes) { this.children = []; this._text = ''; this.append(...nodes); }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  removeAttribute(key) { delete this.attributes[key]; }
  addEventListener(event, fn) { (this.listeners[event] ||= []).push(fn); }
  async emit(event) { for (const fn of this.listeners[event] || []) await fn({ preventDefault() {}, target: this }); }
  async click() { if (!this.disabled) await this.emit('click'); }
  querySelector(selector) { return all(this).find(node => node.tagName === selector) || null; }
  focus() { this.doc.activeElement = this; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  remove() { this.isConnected = false; if (this.parent) this.parent.children = this.parent.children.filter(node => node !== this); }
  scrollIntoView() {}
}
function all(node) { return [node, ...node.children.flatMap(all)]; }
function setup({ voice = true } = {}) {
  const document = { createElement(tag) { return new Node(tag, document); } };
  document.body = new Node('body', document);
  document.activeElement = new Node('button', document);
  const spoken = [], cancelled = [];
  const window = { document };
  if (voice) {
    window.SpeechSynthesisUtterance = class { constructor(text) { this.text = text; } };
    window.speechSynthesis = { speak(item) { spoken.push(item); item.onstart(); }, cancel() { cancelled.push(true); } };
  }
  vm.runInNewContext(source, { window });
  return { api: window.RoxyGardenGuide, document, spoken, cancelled, nodes: () => all(document.body), find: text => all(document.body).find(node => node.tagName === 'button' && node.textContent === text) };
}
const plain = value => JSON.parse(JSON.stringify(value));

test('greeting uses supplied member and chosen species, never a guessed identity', () => {
  const { api } = setup(); const model = api.model.create({ memberName: 'Robert', species });
  model.values.species_key = 'pothos';
  assert.match(api.model.narration(model), /Hola, Robert.*añadiendo Pothos/);
  const anonymous = api.model.create({ species });
  assert.doesNotMatch(api.model.narration(anonymous), /Robert|Roberto/);
});

test('unsupported mango stays unknown without borrowing Pothos care', () => {
  const { api } = setup(); const model = api.model.create({ species, plant: { id: 'test', species_key: 'mango', display_name: 'Mango del balcón' } });
  assert.equal(model.values.species_key, 'unknown');
  assert.match(api.model.narration(model), /no voy a inventarla/i);
  assert.equal(api.model.summary(model).care.length, 0);
  assert.ok(api.model.summary(model).pending.some(text => /Confirmar la especie/.test(text)));
});

test('unknown drainage and medium remain unknown, not false or soil', () => {
  const { api } = setup(); const model = api.model.create({ species, plant: { id: 'old', species_key: 'pothos' } });
  const saved = api.model.payload(model);
  assert.equal(saved.drainage, null); assert.equal(saved.growing_medium, 'unknown');
  assert.ok(api.model.summary(model).pending.some(text => /tierra\/sustrato/.test(text)));
  assert.ok(!api.model.summary(model).care.some(row => row[0] === 'Antes de regar'));
});

test('water profile never displays soil watering or missing drainage warning', () => {
  const { api } = setup(); const model = api.model.create({ species });
  Object.assign(model.values, { species_key: 'pothos', growing_medium: 'water', drainage: false }); model.step = 2;
  const result = api.model.summary(model);
  assert.ok(result.care.some(row => /agua, raíces/.test(row[1])));
  assert.ok(!result.care.some(row => /Comprueba la tierra|no tiene drenaje/.test(row[1])));
  assert.ok(!result.facts.some(row => row[0] === 'Drenaje'));
  assert.match(api.model.narration(model), /No le aplicaré una instrucción de regar tierra/);
});

test('soil profile uses exact supplied species rule and explicit no-drainage condition', () => {
  const { api } = setup(); const model = api.model.create({ species });
  Object.assign(model.values, { species_key: 'aloe', growing_medium: 'soil', drainage: false });
  const result = api.model.summary(model);
  assert.ok(result.care.some(row => row[1] === species[2].soil_rule));
  assert.ok(result.care.some(row => /Confirmaste que no tiene drenaje/.test(row[1])));
  assert.ok(!result.care.some(row => row[1] === species[1].soil_rule));
});

test('editing does not overwrite photo, id, journal or silently confirm a visual proposal', () => {
  const { api } = setup(); const model = api.model.create({ species, plant: { id: 'old', species_key: 'pothos', photo_url: '/private-photo', journal: [{ id: 'entry' }], identification: { status: 'PROPOSED' }, notes: 'Conservar nota' } });
  assert.equal(api.model.validate(model), '');
  const result = api.model.payload(model);
  for (const key of ['id', 'photo_url', 'photo_data_url', 'journal', 'identification', 'species_key']) assert.ok(!(key in result), key);
  assert.equal(result.notes, 'Conservar nota');
  const summary = api.model.summary(model);
  assert.ok(summary.facts.some(row => row[0] === 'Especie' && row[1].startsWith('Propuesta sin confirmar')));
  assert.ok(!summary.care.some(row => row[1] === species[1].light));
});

test('new plant requires actual photo data and rejects script/svg values', () => {
  const { api } = setup(); const model = api.model.create({ species });
  for (const value of ['', 'https://example.test/photo.jpg', 'data:image/svg+xml;base64,AAAA', 'javascript:alert(1)']) {
    model.values.photo_data_url = value; assert.notEqual(api.model.validate(model), '');
  }
  model.values.photo_data_url = photo; assert.equal(api.model.validate(model), '');
});

test('payload keeps only plant fields and normalizes bogus enum values', () => {
  const { api } = setup(); const model = api.model.create({ species, memberName: 'Private member' });
  Object.assign(model.values, { placement: 'mars', light_exposure: 'laser', growing_medium: 'unknown-code', pot_type: 'x', drainage: 'false', owner_id: 'attack', secret: 'attack' });
  const result = plain(api.model.payload(model));
  assert.equal(result.placement, 'indoor'); assert.equal(result.drainage, null); assert.equal(result.growing_medium, 'unknown');
  assert.ok(!JSON.stringify(result).includes('attack')); assert.ok(!JSON.stringify(result).includes('Private member'));
});

test('dialog is fully written, no audio or save until explicit gestures', async () => {
  const h = setup(); let saves = 0;
  h.api.open({ species, memberName: 'Robert', onSave: async () => { saves++; } });
  assert.equal(h.spoken.length, 0); assert.equal(saves, 0);
  assert.ok(h.document.body.textContent.includes('Voz del dispositivo'));
  await h.find('Continuar').click();
  assert.ok(h.document.body.textContent.includes('Añade una foto actual'));
  assert.equal(saves, 0);
  await h.find('Cerrar').click(); assert.equal(h.document.body.children.length, 0);
});

test('device narration starts by tap, updates on navigation, and stops on close', async () => {
  const h = setup(); h.api.open({ species, plant: { id: 'p', species_key: 'pothos' }, onSave: async () => {} });
  await h.find('Escuchar a Roxy').click(); assert.equal(h.spoken.length, 1);
  await h.find('Continuar').click(); assert.equal(h.cancelled.length, 1); assert.equal(h.spoken.length, 1, 'No automatic narration on next step');
  await h.find('Escuchar a Roxy').click();
  await h.find('Cerrar').click(); assert.equal(h.cancelled.length, 2);
});

test('without speech support guide stays usable and says voice is unavailable', async () => {
  const h = setup({ voice: false }); h.api.open({ species, plant: { id: 'p' }, onSave: async () => {} });
  assert.equal(h.find('Escuchar a Roxy').disabled, true);
  assert.match(h.document.body.textContent, /Todo está por escrito/);
  await h.find('Continuar').click(); assert.match(h.document.body.textContent, /Cada rincón/);
});

test('failed save retains inputs and is not reported as success', async () => {
  const h = setup(); const calls = [], reasons = [];
  h.api.open({ species, plant: { id: 'p', display_name: 'Pothos de prueba', notes: 'Conservar' }, onSave: async (value, context) => { calls.push({ value, context }); throw new Error('Servicio temporalmente no disponible'); }, onClose: reason => reasons.push(reason) });
  for (let i = 0; i < 3; i++) await h.find('Continuar').click();
  await h.find('Guardar cambios').click();
  assert.equal(calls.length, 1); assert.match(h.document.body.textContent, /Servicio temporalmente no disponible/);
  assert.match(h.document.body.textContent, /Pothos de prueba/); assert.deepEqual(reasons, []);
  assert.equal(h.find('Guardar cambios').disabled, false);
  assert.equal(calls[0].value.notes, 'Conservar'); assert.equal(calls[0].context.plantId, 'p');
});

test('pending save prevents duplicate taps, closing, or second guide instance', async () => {
  const h = setup(); let release, calls = 0; const reasons = [];
  const pending = new Promise(resolve => { release = resolve; });
  const handle = h.api.open({ species, plant: { id: 'p' }, onSave: async () => { calls++; await pending; }, onClose: reason => reasons.push(reason) });
  for (let i = 0; i < 3; i++) await h.find('Continuar').click();
  const action = h.find('Guardar cambios').click();
  assert.equal(handle.isSaving(), true); assert.equal(h.find('Guardando tu planta…').disabled, true);
  handle.close(); assert.equal(h.document.body.children.length, 1);
  assert.equal(h.api.open({ onSave: async () => {} }), handle);
  assert.equal(calls, 1); release(); await action;
  assert.equal(h.document.body.children.length, 0); assert.deepEqual(reasons, ['saved']);
});

test('untrusted names and care text are text nodes, never HTML', () => {
  const h = setup(); const text = '<img src=x onerror=attack()>';
  h.api.open({ memberName: text, species: [...species, { key: 'test', common_name: text, light: text }], plant: { id: 'p', species_key: 'test', display_name: text }, onSave: async () => {} });
  assert.ok(h.document.body.textContent.includes(text));
  assert.equal(h.nodes().filter(node => node.tagName === 'img').length, 1, 'Only the fixed local Roxy portrait');
});

test('cancel returns focus, retains nothing in storage and never saves', async () => {
  const h = setup(); const prior = h.document.activeElement; const reasons = [];
  h.api.open({ species, onSave: async () => { throw new Error('must not save'); }, onClose: reason => reasons.push(reason) });
  await h.nodes().find(node => node.tagName === 'dialog').emit('cancel');
  assert.equal(h.document.activeElement, prior); assert.deepEqual(reasons, ['cancelled']);
});

test('review requires explicit watered/not-watered choice; words in note do not infer it', async () => {
  const h = setup(); const saved = [];
  h.api.review({ memberName: 'Robert', plant: { id: 'p', display_name: 'Pothos', growing_medium: 'soil', soil_rule: 'Revisar tierra antes de regar.' }, onSave: async payload => saved.push(plain(payload)) });
  const notes = h.nodes().find(node => node.tagName === 'textarea'); notes.value = 'No regué, aunque la palabra regué aparece aquí.';
  await h.find('Guardar mi revisión').click(); assert.equal(saved.length, 0); assert.match(h.document.body.textContent, /No lo deduzco/);
  const choice = h.nodes().find(node => node.tagName === 'input' && node.value === 'CHECKED'); choice.checked = true; await choice.emit('change');
  await h.find('Guardar mi revisión').click(); assert.equal(saved[0].result, 'CHECKED'); assert.ok(!('photo_data_url' in saved[0]));
  assert.match(saved[0].observation, /No regué/); assert.equal(h.document.body.children.length, 0);
});

test('water review has no watered-soil control or unrelated soil advice', () => {
  const h = setup(); h.api.review({ plant: { id: 'p', growing_medium: 'water', soil_rule: 'This soil rule must not leak' }, onSave: async () => {} });
  assert.ok(!h.nodes().some(node => node.value === 'WATERED'));
  assert.doesNotMatch(h.document.body.textContent, /This soil rule/);
  assert.match(h.document.body.textContent, /agua y las raíces visibles/);
});

test('review error keeps note and explicit result for retry without assuming success', async () => {
  const h = setup(); const saved = [], reasons = [];
  h.api.review({ plant: { id: 'p' }, onSave: async payload => { saved.push(plain(payload)); throw new Error('No se pudo guardar'); }, onClose: reason => reasons.push(reason) });
  const notes = h.nodes().find(node => node.tagName === 'textarea'); notes.value = 'Tierra húmeda';
  const choice = h.nodes().find(node => node.tagName === 'input' && node.value === 'CHECKED'); choice.checked = true; await choice.emit('change');
  await h.find('Guardar mi revisión').click(); assert.equal(saved.length, 1); assert.equal(notes.value, 'Tierra húmeda'); assert.equal(choice.checked, true);
  assert.match(h.document.body.textContent, /No se pudo guardar/); assert.deepEqual(reasons, []);
});

test('review refuses empty records and does not diagnose plant health', async () => {
  const h = setup(); let calls = 0;
  h.api.review({ plant: { id: 'p', display_name: 'Planta de prueba' }, onSave: async () => { calls++; } });
  const choice = h.nodes().find(node => node.tagName === 'input' && node.value === 'CHECKED'); choice.checked = true; await choice.emit('change');
  await h.find('Guardar mi revisión').click(); assert.equal(calls, 0);
  assert.match(h.document.body.textContent, /Escribe qué observaste/);
  assert.match(h.document.body.textContent, /no puedo diagnosticar/);
});

test('review voice stays gesture driven, and cancel does not write', async () => {
  const h = setup(); let calls = 0;
  h.api.review({ plant: { id: 'p' }, onSave: async () => { calls++; } });
  assert.equal(h.spoken.length, 0); await h.find('Escuchar a Roxy').click(); assert.equal(h.spoken.length, 1);
  await h.find('Cerrar').click(); assert.equal(h.cancelled.length, 1); assert.equal(calls, 0);
});
