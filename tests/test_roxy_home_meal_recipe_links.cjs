/* Execute actual meal-link resolution against synthetic Home recipes; no network or storage. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../assets/roxy_list.js'), 'utf8');
function section(first, last) {
  const start = source.indexOf(first), end = source.indexOf(last, start);
  assert.ok(start >= 0 && end > start, `Missing implementation section: ${first}`);
  return source.slice(start, end);
}
const normalizeCode = source.split('\n').find(line => line.startsWith('  const normalize ='));
assert.ok(normalizeCode);
const helper = source.includes('  function resolveMealRecipe(') ? section('  function resolveMealRecipe(', '  function openRecipeByTitle(') : '';
const executable = normalizeCode + '\n' + section('  function humanRecipeShelf(', '  function recipeDisplayTitle(')
  + helper + section('  function openRecipeByTitle(', '  function recipeQuantity(');
const recipe = (overrides = {}) => ({title:'Pollo al horno', audience:'human', editorial_status:'ready', kind:'meal',
  ingredients:[{name:'Pollo', quantity:1, unit:'kg'}], steps:['Preparar los ingredientes.', 'Cocinar según la fuente.'], ...overrides});
function harness({saved = [], catalog = [], state = {}} = {}) {
  const opened = [], catalogSaves = [], notices = [], panels = [], renders = [], elements = new Map();
  const element = () => ({value:'', hidden:false, children:[], _text:'',
    get textContent() { return this._text + this.children.map(child => child.textContent || '').join(''); },
    set textContent(value) { this._text = String(value); this.children = []; },
    replaceChildren(...children) { this._text = ''; this.children = children; }, append(...children) { this.children.push(...children); },
    showModal() { this.open = true; }, close() { this.open = false; }, focus() {}, scrollIntoView() { this.scrolled = true; }});
  const $ = id => {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  };
  const ctx = {homeFood:{recipes:saved, local_recipes:catalog}, homeFoodReady:true, homeFoodLoadFailed:false,
    recipeSearch:'', recipeFilter:'all', recipeShowDrafts:false, recipeAudience:'human', activePanel:'today', currentRecipe:null, $, ...state,
    announce:message => notices.push(message), openRecipe:row => opened.push(row), openCatalogRecipe:row => catalogSaves.push(row),
    selectPanel:panel => { panels.push(panel); ctx.activePanel = panel; if (panel === 'recipes') ctx.recipeAudience = 'human'; },
    renderRecipes:() => renders.push({search:ctx.recipeSearch, filter:ctx.recipeFilter, audience:ctx.recipeAudience, drafts:ctx.recipeShowDrafts}),
    api:() => { throw new Error('A meal link must not call AI or mutate recipes'); },
    setRecipeAudience:audience => { ctx.recipeAudience = audience; },
    document:{createElement:element}, makeButton:(text, className, action) => ({textContent:text, className, click:action}),
  };
  $('recipeSearch').value = ctx.recipeSearch;
  vm.createContext(ctx); vm.runInContext(executable, ctx);
  return {ctx, opened, catalogSaves, notices, panels, renders, $, open:value => ctx.openRecipeByTitle(value)};
}

test('legacy exact normalized titles open an available human recipe', () => {
  const target = recipe({id:11, title:'Arroz con salmón'}), h = harness({saved:[target]});
  h.open('  ARROZ con SALMÓN  '); assert.equal(h.opened[0], target); assert.equal(h.catalogSaves.length, 0);
});

test('catalog_key resolves an exact stable catalog recipe even when the displayed meal title differs', () => {
  const target = recipe({catalog_key:'oven-chicken', title:'Pollo asado con patatas'}), wrong = recipe({catalog_key:'another', title:'Pollo al horno'});
  const h = harness({catalog:[wrong, target]}); h.open({catalog_key:'oven-chicken', title:'Pollo al horno'});
  assert.equal(h.opened[0], target); assert.equal(h.catalogSaves.length, 0, 'opening a catalog recipe must be a read-only preview');
});

test('recipe_id opens the exact saved recipe instead of another equal-title recipe', () => {
  const target = recipe({id:22, title:'Sopa guardada'}), wrong = recipe({id:21, title:'Sopa guardada'}), h = harness({saved:[wrong, target]});
  h.open({recipe_id:'22', title:'Título histórico del plan'}); assert.equal(h.opened[0], target); assert.equal(h.catalogSaves.length, 0);
});

test('a saved catalog recipe opens without saving it again', () => {
  const target = recipe({id:30, catalog_key:'oven-chicken'}), h = harness({saved:[target]});
  h.open({recipe_id:30, catalog_key:'oven-chicken', title:target.title}); assert.equal(h.opened[0], target); assert.equal(h.catalogSaves.length, 0);
});

for (const title of ['Pollo', 'Pollo al horno con verduras', 'Arroz con pollo al horno']) {
  test(`substring title ${JSON.stringify(title)} cannot silently open another meal`, () => {
    const h = harness({saved:[recipe({id:1})]}); h.open(title); assert.equal(h.opened.length, 0); assert.equal(h.catalogSaves.length, 0);
  });
}

for (const blocked of [
  {audience:'pet', pet_species:'dog', pet_id:'bella'},
  {editorial_status:'needs_canonical_review'},
]) {
  test(`meal title cannot open ${JSON.stringify(blocked)}`, () => {
    const h = harness({saved:[recipe({id:1, ...blocked})], catalog:[recipe({catalog_key:'blocked', ...blocked})]});
    h.open('Pollo al horno'); assert.equal(h.opened.length, 0); assert.equal(h.catalogSaves.length, 0);
  });
}

test('a ready human recipe is not shadowed by a pet or draft with the same title', () => {
  const target = recipe({catalog_key:'human-ready'});
  const h = harness({saved:[recipe({id:1, audience:'pet'}), recipe({id:2, editorial_status:'needs_canonical_review'})], catalog:[target]});
  h.open(target.title); assert.equal(h.opened[0], target); assert.equal(h.catalogSaves.length, 0);
});

for (const reference of [{catalog_key:'deleted-key'}, {recipe_id:999}]) {
  test(`missing stable reference ${JSON.stringify(reference)} cannot fall through to a title-only substitute`, () => {
    const h = harness({saved:[recipe({id:1, catalog_key:'different-key'})]}); h.open({...reference, title:'Pollo al horno'});
    assert.equal(h.opened.length, 0); assert.equal(h.catalogSaves.length, 0);
  });
}

test('a missing meal never poisons recipeSearch or makes the available human catalog disappear', () => {
  const target = recipe({catalog_key:'ready'}), h = harness({catalog:[target]});
  h.open('Receta ausente del plan'); assert.equal(h.opened.length, 0); assert.equal(h.catalogSaves.length, 0);
  assert.equal(h.ctx.recipeSearch, ''); assert.equal(h.$('recipeSearch').value, '');
  assert.equal(h.ctx.recipeAudience, 'human'); assert.equal(h.ctx.recipeShowDrafts, false); assert.equal(h.ctx.recipeFilter, 'all');
  const visible = h.ctx.humanRecipeShelf(h.ctx.homeFood.local_recipes).filter(row => !h.ctx.recipeSearch || row.title.toLowerCase().includes(h.ctx.recipeSearch));
  assert.equal(visible.length, 1); assert.equal(visible[0], target); assert.equal(h.panels.length, 0, 'missing recipe remains in the meal-plan context');
  assert.equal(h.$('recipeDialog').open, true); assert.match(h.$('recipeDialogEyebrow').textContent, /no disponible/);
  assert.match(h.$('recipeDialogContent').textContent, /No se ha borrado tu recetario/); assert.equal(h.ctx.currentRecipe, null);
});

test('meal button passes the complete stable recipe reference rather than dropping it to the title', () => {
  const planStart = source.indexOf("title.className='meal-plan-recipe-link'"); assert.ok(planStart >= 0);
  const planLink = source.slice(planStart, source.indexOf("const meta=", planStart));
  assert.match(planLink, /openRecipeByTitle\(meal\)/);
});

test('legacy title selects ready canonical source ahead of an equal-title saved copy', () => {
  const canonical = recipe({catalog_key:'canonical'}), h = harness({catalog:[canonical], saved:[recipe({id:1, catalog_key:'canonical', steps:['Edited saved step']})]});
  h.open({title:'Pollo al horno'}); assert.equal(h.opened[0], canonical); assert.equal(h.catalogSaves.length, 0);
});

for (const collection of ['saved', 'catalog']) {
  test(`ambiguous legacy title in ${collection} does not choose a different recipe arbitrarily`, () => {
    const rows = [recipe({id:1, catalog_key:'one'}), recipe({id:2, catalog_key:'two'})], h = harness({[collection]:rows});
    h.open({title:'Pollo al horno'}); assert.equal(h.opened.length, 0); assert.equal(h.$('recipeDialog').open, true);
  });
}

for (const incomplete of [
  {ingredients:[]}, {ingredients:null}, {ingredients:[null]}, {ingredients:[{name:'   '}]},
  {steps:[]}, {steps:null}, {steps:['   ']}, {steps:[null]}, {steps:[42]},
]) {
  test(`incomplete recipe ${JSON.stringify(incomplete)} is never opened as a meal`, () => {
    const h = harness({catalog:[recipe({catalog_key:'incomplete', ...incomplete})]});
    h.open({catalog_key:'incomplete', title:'Pollo al horno'}); assert.equal(h.opened.length, 0); assert.equal(h.$('recipeDialog').open, true);
  });
}

test('catalog reference selects the ready canonical copy even if a saved copy has the same key', () => {
  const canonical = recipe({catalog_key:'canonical', title:'Fuente actual'}), saved = recipe({id:1, catalog_key:'canonical', title:'Versión guardada'});
  const h = harness({catalog:[canonical], saved:[saved]}); h.open({catalog_key:'canonical', title:'Nombre anterior'}); assert.equal(h.opened[0], canonical);
});

test('id alias resolves only the exact saved recipe and never a title fallback', () => {
  const target = recipe({id:55}), h = harness({saved:[target]}); h.open({id:'55', title:'Nombre anterior'}); assert.equal(h.opened[0], target);
  h.open({id:56, title:target.title}); assert.equal(h.opened.length, 1); assert.equal(h.$('recipeDialog').open, true);
});

test('missing dialog preserves current filters until explicit browse, then restores all ready human recipes', () => {
  const h = harness({catalog:[recipe({catalog_key:'ready'})], state:{recipeSearch:'búsqueda anterior', recipeFilter:'favorite', recipeShowDrafts:true, recipeAudience:'pet', currentRecipe:recipe({id:'old'})}});
  h.open('Cena de preparaciones de la semana');
  assert.equal(h.ctx.recipeSearch, 'búsqueda anterior'); assert.equal(h.$('recipeSearch').value, 'búsqueda anterior'); assert.equal(h.ctx.recipeShowDrafts, true);
  assert.equal(h.ctx.recipeFilter, 'favorite'); assert.equal(h.panels.length, 0); assert.equal(h.ctx.currentRecipe, null);
  const browse = h.$('recipeDialogContent').children.find(child => child.textContent === 'Ver recetas disponibles'); assert.ok(browse); browse.click();
  assert.equal(h.$('recipeDialog').open, false); assert.equal(h.ctx.recipeSearch, ''); assert.equal(h.$('recipeSearch').value, '');
  assert.equal(h.ctx.recipeFilter, 'all'); assert.equal(h.ctx.recipeShowDrafts, false); assert.equal(h.ctx.recipeAudience, 'human'); assert.deepEqual(h.panels, ['recipes']);
  assert.equal(h.$('recipeCatalogSection').scrolled, true); assert.equal(h.catalogSaves.length, 0);
});

test('showAllHumanRecipes resets a poisoned search and draft/favorite shelf without data mutations', () => {
  const target = recipe({catalog_key:'ready'}), h = harness({catalog:[target], state:{recipeSearch:'cena inexistente', recipeFilter:'favorite', recipeShowDrafts:true, recipeAudience:'pet'}});
  const before = JSON.stringify(h.ctx.homeFood); h.ctx.showAllHumanRecipes();
  assert.equal(h.ctx.recipeSearch, ''); assert.equal(h.$('recipeSearch').value, ''); assert.equal(h.ctx.recipeFilter, 'all'); assert.equal(h.ctx.recipeShowDrafts, false);
  assert.equal(h.ctx.recipeAudience, 'human'); assert.deepEqual(h.panels, ['recipes']); assert.equal(JSON.stringify(h.ctx.homeFood), before); assert.equal(h.catalogSaves.length, 0);
});

test('missing dialog can return to plan setup without changing the recipe library', () => {
  const h = harness({state:{recipeSearch:'arroz', recipeFilter:'rice'}}); h.open('Cena de preparaciones de la semana');
  const review = h.$('recipeDialogContent').children.find(child => child.textContent === 'Revisar mi plan'); assert.ok(review); review.click();
  assert.equal(h.$('recipeDialog').open, false); assert.deepEqual(h.panels, ['today']); assert.equal(h.$('mealPlanSetup').open, true);
  assert.equal(h.ctx.recipeSearch, 'arroz'); assert.equal(h.ctx.recipeFilter, 'rice'); assert.equal(h.catalogSaves.length, 0);
});

test('empty recipe search presents an explicit action to clear filters', () => {
  const render = section('  function renderRecipes()', '  function aquariumInhabitantsField(');
  const empty = render.slice(render.lastIndexOf('if(!rows.length)'));
  assert.match(empty, /makeButton\([^\n]*showAllHumanRecipes/);
});
