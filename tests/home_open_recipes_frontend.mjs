import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

// Focused DOM contract tests; production browser layout is checked separately.
const catalog = JSON.parse(fs.readFileSync(new URL('../data/home_open_recipes.json', import.meta.url), 'utf8'));
// Mirror the server's reviewed-publication projection, not the editorial archive.
catalog.recipes = catalog.recipes.filter(row => row.audit?.publishable !== false);
const payload = () => ({status:'READY', recipes:structuredClone(catalog.recipes).map(row => ({...row,
  attribution:row.rights.attribution, license_url:row.rights.license_url}))});
const code = fs.readFileSync(new URL('../assets/roxy_home_open_recipes.js', import.meta.url), 'utf8');
const downloads = [], blobs = [], revoked = [], timers = [];
let activeElement;
class Element {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.listeners = {}; this._text = ''; this.value = ''; this.hidden = false; this.parent = null; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  set textContent(text) { this._text = String(text); this.children.forEach(child => { child.parent = null; }); this.children = []; }
  get firstChild() { return this.children[0]; }
  get isConnected() { return this.root || Boolean(this.parent?.isConnected); }
  append(...children) { children.forEach(child => { child.parent = this; this.children.push(child); }); }
  replaceChildren(...children) { this.children.forEach(child => { child.parent = null; }); this.children = []; this._text = ''; this.append(...children); }
  remove() { if (this.parent) { this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null; } }
  setAttribute(name, value) { this[name] = value; }
  addEventListener(name, action) { (this.listeners[name] ||= []).push(action); }
  async emit(name) { for (const action of this.listeners[name] || []) await action({preventDefault() {}}); }
  click() { if (this.tagName === 'A') downloads.push({href:this.href, filename:this.download}); else return this.emit('click'); }
  focus() { activeElement = this; }
}
const document = {createElement:tag => new Element(tag), body:new Element('body')}; document.body.root = true;
class TestURL extends URL {
  static createObjectURL(blob) { blobs.push(blob); return `blob:original-${blobs.length}`; }
  static revokeObjectURL(url) { revoked.push(url); }
}
const sandbox = {window:{}, document, URL:TestURL, Blob, setTimeout:fn => timers.push(fn),
  fetch() { throw new Error('No frontend external/network fetch is allowed'); }};
vm.runInNewContext(code, sandbox);
const {render} = sandbox.window.RoxyOpenRecipes;
const all = (parent, tag) => parent.children.flatMap(child => [...(child.tagName === tag.toUpperCase() ? [child] : []), ...all(child, tag)]);
const container = () => { const el = new Element('div'); document.body.append(el); return el; };
const findButton = (parent, text) => all(parent, 'button').find(el => el.textContent === text);
const open = async details => { details.open = true; await details.emit('toggle'); };
const close = async details => { details.open = false; await details.emit('toggle'); };
const cards = parent => all(parent, 'details').filter(el => el.className === 'provider-recipe-card');

const panel = container(), requests = [];
const api = async path => { requests.push(path); return payload(); };
render(panel, {user:'household/a', api});
assert.equal(requests.length, 0, 'rendering must not make a request');
const initialDetails = panel.firstChild;
await open(initialDetails);
assert.deepEqual(requests, ['/v1/home-food/household%2Fa/open-recipes']);
assert.equal(cards(panel).length, 6);
assert.equal(all(panel, 'ol').reduce((count, list) => count + list.children.length, 0), 27);
cards(panel).forEach((card, i) => {
  assert.deepEqual(all(card, 'ul')[0].children.map(el => el.textContent), catalog.recipes[i].ingredients_original);
  assert.deepEqual(all(card, 'ol')[0].children.map(el => el.textContent), catalog.recipes[i].steps_original);
  assert.equal(all(card, 'ol')[0].lang, 'en');
  assert.ok(card.textContent.includes(catalog.recipes[i].rights.attribution));
});
const sourceImages = all(panel, 'img');
assert.equal(sourceImages.length, 2, 'only photographs from unheld source recipes');
assert.ok(sourceImages.every(image => !image.src), 'no remote image request before opening its recipe');
const photographed = catalog.recipes.filter(row => row.image_url);
assert.deepEqual(photographed.map(row => row.id), ['wikibooks-150880', 'wikibooks-219286']);
photographed.forEach(row => {
  const filename = decodeURIComponent(new URL(row.image_url).pathname.split('/').pop()).replaceAll('_', ' ');
  assert.ok(row.original_wikitext.includes(`Image:${filename}`), 'actual image must be embedded in pinned source recipe');
  assert.equal(row.image_mime, 'image/jpeg'); assert.equal(row.image_commercial_use_permitted, true);
  assert.ok(row.image_dimensions.width > 0 && row.image_dimensions.height > 0);
  assert.ok(row.photo_scope.startsWith('Fotografía publicada con '));
  assert.ok(row.photo_scope.endsWith('no verifica cantidades ni resultado'));
  assert.ok(row.image_author && row.image_source_revision); assert.equal(row.photo_verified, undefined);
});
const firstPhotoCard = cards(panel)[0]; await open(firstPhotoCard);
assert.equal(sourceImages[0].src, photographed[0].image_url);
assert.equal(sourceImages[0].referrerPolicy, 'no-referrer'); assert.equal(sourceImages[0].width, photographed[0].image_dimensions.width);
assert.ok(firstPhotoCard.textContent.includes(photographed[0].image_author));
assert.ok(all(firstPhotoCard, 'a').some(anchor => anchor.href === photographed[0].image_license_url));
assert.ok(all(firstPhotoCard, 'a').some(anchor => anchor.href === photographed[0].image_source_url));
await sourceImages[0].emit('error'); assert.equal(all(firstPhotoCard, 'img').length, 0);
assert.ok(firstPhotoCard.textContent.includes('La fotografía original no se pudo cargar'));
const cuisine = all(panel, 'select')[0], search = all(panel, 'input')[0];
assert.ok(cuisine.children.some(option => option.textContent === 'Francia'));
search.value = 'lentil'; await search.emit('input');
assert.equal(cards(panel).length, 1); assert.equal(cards(panel)[0].firstChild.textContent, 'Red Lentil Soup');
search.value = ''; cuisine.value = 'French'; await cuisine.emit('change');
assert.equal(cards(panel).length, 1); assert.equal(cards(panel)[0].firstChild.textContent, 'Potatoes Anna');
assert.equal(requests.length, 1, 'filtering must remain local');

const card = cards(panel)[0], reader = all(card, 'section')[0];
await findButton(card, 'Leer paso a paso').click();
assert.equal(reader.hidden, false); assert.equal(reader.children[0].textContent, 'Paso 1 de 5');
assert.equal(reader.children[1].textContent, catalog.recipes[0].steps_original[0]);
assert.equal(activeElement, reader.children[1]);
assert.equal(findButton(card, 'Anterior').disabled, true);
for (let i = 0; i < 10; i++) await findButton(card, 'Siguiente').click();
assert.equal(reader.children[0].textContent, 'Paso 5 de 5'); assert.equal(findButton(card, 'Siguiente').disabled, true);
await findButton(card, 'Anterior').click(); assert.equal(reader.children[0].textContent, 'Paso 4 de 5');
await findButton(card, 'Terminar lectura').click(); assert.equal(reader.hidden, true);
assert.equal(downloads.length, 0, 'reading does not trigger downloads');
await findButton(card, 'Descargar original TXT').click();
const text = await blobs[0].text();
assert.equal(downloads[0].filename, 'roxy-original-wikibooks-150880.txt');
for (const original of [...catalog.recipes[0].ingredients_original, ...catalog.recipes[0].steps_original,
  catalog.recipes[0].source_url, catalog.recipes[0].source_revision_url, catalog.recipes[0].rights.license_url,
  catalog.recipes[0].rights.attribution, ...catalog.recipes[0].rights.additional_attribution_urls, catalog.recipes[0].rights.changes]) assert.ok(text.includes(original));
for (const field of ['image_author', 'image_license', 'image_source_url', 'image_license_url']) assert.ok(text.includes(catalog.recipes[0][field]));
timers.forEach(fn => fn()); assert.deepEqual(revoked, ['blob:original-1']);
render(panel, {user:'household/a', api}); assert.equal(panel.firstChild, initialDetails, 'same signature preserves open state');
await close(initialDetails); await open(initialDetails); assert.equal(requests.length, 1, 'reopening reuses loaded local catalog');
render(panel, {user:'household/a', api, hidden:true}); assert.equal(panel.hidden, true); assert.equal(panel.children.length, 0);
assert.equal(requests.length, 1, 'hidden pet view must not fetch human originals');

const stalePanel = container(); let resolveOld;
render(stalePanel, {user:'old-user', api:() => new Promise(resolve => { resolveOld = resolve; })});
const pending = open(stalePanel.firstChild);
render(stalePanel, {user:'new-user', api:async () => { const data = payload(); data.recipes = [data.recipes[5]]; return data; }});
await open(stalePanel.firstChild); resolveOld(payload()); await pending;
assert.equal(cards(stalePanel).length, 1); assert.equal(cards(stalePanel)[0].firstChild.textContent, 'Tomato Pasta', 'stale household response must be discarded');

const retryPanel = container(); let attempts = 0;
render(retryPanel, {user:'retry-user', api:async () => { if (++attempts === 1) throw new Error('offline'); return payload(); }});
await open(retryPanel.firstChild); assert.equal(cards(retryPanel).length, 0); assert.ok(retryPanel.textContent.includes('No se pudo cargar'));
await close(retryPanel.firstChild); await open(retryPanel.firstChild); assert.equal(cards(retryPanel).length, 6);
const unsafePanel = container(); const unsafe = payload(); unsafe.recipes = [unsafe.recipes[0]]; unsafe.recipes[0].source_url = 'javascript:alert(1)';
render(unsafePanel, {user:'unsafe-source', api:async () => unsafe}); await open(unsafePanel.firstChild);
assert.ok(all(unsafePanel, 'a').every(anchor => anchor.href.startsWith('https://')));
assert.equal(all(unsafePanel, 'a').some(anchor => anchor.textContent === 'Fuente original · Wikibooks'), false);
for (const mutation of [
  {image_url:'https://upload.wikimedia.org.evil.test/wikipedia/commons/4/41/Tortilla_patatas.jpg'},
  {image_url:'https://upload.wikimedia.org:444/wikipedia/commons/4/41/Tortilla_patatas.jpg'},
  {image_url:'https://user@upload.wikimedia.org/wikipedia/commons/4/41/Tortilla_patatas.jpg'},
  {image_url:'https://upload.wikimedia.org/wikipedia/commons/4/41/Tortilla_patatas.svg'},
  {image_url:'https://upload.wikimedia.org/wikipedia/commons/4/41/Tortilla_patatas.jpg?tracking=1'},
  {image_mime:'image/svg+xml'}, {image_source_url:'https://example.com/wiki/File:photo.jpg'},
  {image_license_url:'https://creativecommons.org/licenses/by-nc/4.0/'}, {image_commercial_use_permitted:false},
  {image_status:'unverified'}, {image_author:''}, {image_license:'CC BY-NC 4.0'}
]) {
  const bad = payload(); bad.recipes = [{...bad.recipes[0], ...mutation}]; const photoPanel = container();
  render(photoPanel, {user:'bad-photo', api:async () => bad}); await open(photoPanel.firstChild);
  assert.equal(all(photoPanel, 'img').length, 0, JSON.stringify(mutation));
  assert.ok(photoPanel.textContent.includes('No hay una fotografía de la fuente disponible'));
}
console.log('PASS: deferred same-origin GET, exact originals, licensed source-only photos on explicit recipe opening, error fallback, local filters, bounded reader, attributed TXT, signature persistence, hidden mode, stale responses, retry and safe links.');
