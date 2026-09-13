const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const test=require('node:test');
const source=fs.readFileSync(require('node:path').join(__dirname,'../assets/roxy_list.js'),'utf8');
const part=(a,b)=>source.slice(source.indexOf(a),source.indexOf(b,source.indexOf(a)));
const normalize=source.split('\n').find(line=>line.startsWith('  const normalize ='));
function harness(){
  const elements=new Map();const el=()=>({children:[],dataset:{},hidden:false,attrs:{},value:'',textContent:'',
    replaceChildren(...rows){this.children=rows;},append(...rows){this.children.push(...rows);},prepend(row){this.children.unshift(row);},
    setAttribute(k,v){this.attrs[k]=v;},focus(){this.focused=true;},querySelector(selector){return this.children.find(row=>selector.includes(`"${row.dataset.recipeCollection}"`));}});
  const $=id=>{if(!elements.has(id))elements.set(id,el());return elements.get(id);};
  const ctx={$ ,user:'qa-household',identity:'member-a',recipeNavigationIdentity:'',recipeCollection:'all',recipeLocalGroup:'all',
    account:{id:'member-a',mode:'member'},recipeProfileIdentity:'',recipeProfileEnvelope:null,
    recipeImportExpanded:false,recipeSearch:'',recipeFilter:'all',recipeShowDrafts:false,renderCount:0,
    collectionIdentity:()=>ctx.identity,renderRecipes:()=>ctx.renderCount++,document:{createElement:el},
    recipeCategoryId:row=>row.category,makeButton:(title,cls,action)=>Object.assign(el(),{textContent:title,className:cls,click:action})};
  vm.createContext(ctx);vm.runInContext(normalize+'\n'+part('  const recipeCollectionChoices=','  function renderRecipes()'),ctx);return ctx;
}
test('opening a collection gives five broad destinations rather than one local count',()=>{
  const h=harness();h.renderRecipeNavigation(false);
  assert.deepEqual(h.$('recipeCollections').children.map(row=>row.textContent),['Explorar','Comidas','Bebidas','Postres','Mi recetario']);
  assert.equal(h.$('recipeCollections').children[0].attrs['aria-pressed'],'true');
});
for(const group of ['all','food','drinks','dessert','local','world'])test(`collection ${group} is selectable without mutating recipes`,()=>{
  const h=harness();h.renderRecipeNavigation(false);h.chooseRecipeCollection(group);assert.equal(h.recipeCollection,group);assert.equal(h.renderCount,1);
});
test('unknown collection is rejected',()=>{const h=harness();h.chooseRecipeCollection('anything');assert.equal(h.renderCount,0);assert.equal(h.recipeCollection,'all');});
test('same member rerender retains selection and search',()=>{const h=harness();h.renderRecipeNavigation(false);h.recipeCollection='drinks';h.recipeSearch='café';h.renderRecipeNavigation(false);assert.equal(h.recipeCollection,'drinks');assert.equal(h.recipeSearch,'café');});
test('member change clears previous selection, drafts, search and expanded importer',()=>{
  const h=harness();h.renderRecipeNavigation(false);h.recipeCollection='local';h.recipeLocalGroup='drinks';h.recipeShowDrafts=true;h.recipeSearch='private';h.recipeImportExpanded=true;
  h.identity='member-b';h.renderRecipeNavigation(false);assert.equal(h.recipeCollection,'all');assert.equal(h.recipeLocalGroup,'all');assert.equal(h.recipeShowDrafts,false);assert.equal(h.recipeSearch,'');assert.equal(h.recipeImportExpanded,false);
});
test('pet mode hides human collection and local category navigation',()=>{const h=harness();h.renderRecipeNavigation(true);assert.equal(h.$('recipeNavigation').hidden,true);assert.equal(h.$('recipeLocalGroups').hidden,true);});
test('completed current member preferences add Para ti and select it on the first render',()=>{
  const h=harness();h.recipeProfileIdentity='member-a';h.recipeProfileEnvelope={member_id:'member-a',profile:{completed:true}};h.renderRecipeNavigation(false);
  assert.deepEqual(h.$('recipeCollections').children.map(row=>row.textContent),['Para ti','Explorar','Comidas','Bebidas','Postres','Mi recetario']);
  assert.equal(h.recipeCollection,'personal');assert.equal(h.$('recipeCollections').children[0].attrs['aria-pressed'],'true');
  h.chooseRecipeCollection('all');h.renderRecipeNavigation(false);assert.equal(h.recipeCollection,'all','Rerender respects explicit browsing away from Para ti');
});
for(const completed of [false,undefined])test(`unfinished personal profile does not expose Para ti (${completed})`,()=>{
  const h=harness();h.recipeProfileIdentity='member-a';h.recipeProfileEnvelope={member_id:'member-a',profile:{completed}};h.renderRecipeNavigation(false);
  assert.equal(h.recipeCollection,'all');assert.equal(h.$('recipeCollections').children.some(row=>row.dataset.recipeCollection==='personal'),false);
});
test('switching to another member cannot inherit the previous personal navigation',()=>{
  const h=harness();h.recipeProfileIdentity='member-a';h.recipeProfileEnvelope={member_id:'member-a',profile:{completed:true}};h.renderRecipeNavigation(false);assert.equal(h.recipeCollection,'personal');
  h.identity='member-b';h.account.id='member-b';h.renderRecipeNavigation(false);assert.equal(h.recipeCollection,'all');
  assert.equal(h.$('recipeCollections').children.some(row=>row.dataset.recipeCollection==='personal'),false);
});
for(const category of ['coffee_hot','juices','smoothies','cocktails'])test(`${category} belongs only to drinks`,()=>{const h=harness();assert.equal(h.localRecipeGroup(category),'drinks');});
test('desserts and breakfast have separate parents',()=>{const h=harness();assert.equal(h.localRecipeGroup('desserts'),'dessert');assert.equal(h.localRecipeGroup('breakfast'),'food');});
test('search intersects parent group instead of silently escaping it',()=>{
  const h=harness();h.recipeSearch='leche';h.recipeLocalGroup='drinks';assert.equal(h.humanRecipeMatchesBrowse({title:'Arroz con leche',category:'desserts'}),false);
  assert.equal(h.humanRecipeMatchesBrowse({title:'Café con leche',category:'coffee_hot'}),true);
});
test('search intersects child category',()=>{const h=harness();h.recipeSearch='pollo';h.recipeLocalGroup='food';h.recipeFilter='soups';assert.equal(h.humanRecipeMatchesBrowse({title:'Pollo al horno',category:'chicken'}),false);assert.equal(h.humanRecipeMatchesBrowse({title:'Sopa de pollo',category:'soups'}),true);});
test('favorites retain favorite membership while searching',()=>{const h=harness();h.recipeLocalGroup='favorite';h.recipeFilter='favorite';h.recipeSearch='cafe';assert.equal(h.humanRecipeMatchesBrowse({title:'Café',category:'coffee_hot',favorite:false}),false);assert.equal(h.humanRecipeMatchesBrowse({title:'Café',category:'coffee_hot',favorite:true}),true);});
test('parent passes explicit autoload only to its selected human provider',()=>{
  const code=part('    const sourceContext=','    $(\'recipeSearch\').disabled=false;');
  assert.match(code,/autoLoad:true,browseGroup/);assert.match(code,/hidden:!myplateSelected/);assert.match(code,/hidden:petMode\|\|recipeCollection!=='drinks'/);
  assert.match(code,/hidden:petMode\|\|recipeCollection!=='world'/);
});
test('meal-plan fallback deliberately selects the usable local shelf',()=>{assert.match(part('  function showAllHumanRecipes(){','  function showMealRecipeUnavailable('),/recipeCollection='local';recipeLocalGroup='all'/);});
test('unselected local library exits before creating photo cards',()=>{
  const render=part('  function renderRecipes()','  function aquariumInhabitantsField(');
  assert.ok(render.indexOf("recipeCollection!=='local'")<render.indexOf('recipeCard(recipe)'));
  assert.match(render,/catalogSection.hidden=true;\s*return;/);
});
test('leaving empty pets cleans importer styling before the nonlocal early return',()=>{
  const render=part('  function renderRecipes()','  function aquariumInhabitantsField(');
  assert.ok(render.indexOf("if(!petMode)importStudio.classList.remove('pet-onboarding-mode')")<render.indexOf("recipeCollection!=='local'"));
});
test('draft original-source action opens the world collection before scrolling',()=>{
  const code=part("      const review=makeButton('Explorar recetas originales'","      root.append(notice,review)");
  assert.match(code,/recipeCollection='world';selectPanel\('recipes'\)/);
});
test('source browse requires the current authenticated scope to be visible',()=>{
  const ctx={user:'home-a',load:{},app:{hidden:true},collectionIdentity:()=> 'member:a'};
  ctx.$=()=>ctx.app;vm.createContext(ctx);vm.runInContext(part('  function recipeSourcesReady(){','  function activateRecipeSources(){'),ctx);
  assert.equal(ctx.recipeSourcesReady(),false);
  ctx.load.renderedScope={owner:'home-a',identity:'member:a'};
  assert.equal(ctx.recipeSourcesReady(),false);
  ctx.app.hidden=false;assert.equal(ctx.recipeSourcesReady(),true);
  ctx.app.open=true;assert.equal(ctx.recipeSourcesReady(),false,'Editing preferences pauses recipe media and requests');
  ctx.app.open=false;
  ctx.load.renderedScope.identity='member:b';assert.equal(ctx.recipeSourcesReady(),false);
  ctx.load.renderedScope={owner:'home-b',identity:'member:a'};assert.equal(ctx.recipeSourcesReady(),false);
});
test('normal and offline recovery activate browsing only after revealing confirmed scope',()=>{
  assert.equal((source.match(/load\.renderedScope=\{owner:requestedOwner,identity\};\$\('app'\)\.hidden=false;\s*activateRecipeSources\(\);/g)||[]).length,2);
  assert.match(part('    const sourceContext=','    const myplateSelected='),/isCurrent:\(\)=>recipeSourcesReady\(\)/);
});
test('local recipes use a single category selector with broad optgroups',()=>{
  const render=part('  function renderRecipes()','  function aquariumInhabitantsField(');
  assert.match(render,/createElement\('select'\)/);
  assert.match(render,/Categoría de mi recetario/);
  assert.match(render,/createElement\('optgroup'\)/);
  assert.doesNotMatch(render,/title:'Todo mi recetario'/);
  assert.match(render,/recipeLocalGroup=recipeFilter==='favorite'\?'favorite':'all'/);
});
test('preference entry stays accessible without a large promotional card',()=>{
  const render=part('  function renderRecipePreferences(', '  async function cacheSnapshot(');
  assert.match(render,/recipe-preferences-shortcut/);
  assert.match(render,/setAttribute\('aria-label',complete\?'Cambiar mis gustos':'Configurar mis gustos'\)/);
  assert.doesNotMatch(render,/Hagamos este recetario tuyo/);
});
test('draft and import tools follow recipe cards rather than blocking the first screen',()=>{
  const html=fs.readFileSync(require('node:path').join(__dirname,'../assets/roxy_list.html'),'utf8');
  assert.ok(html.indexOf('id="recipeEditorialFilters"')>html.indexOf('id="recipeLibrary"'));
  assert.ok(html.indexOf('id="recipeImportToggle"')>html.indexOf('id="recipeLibrary"'));
  assert.match(html,/<summary>Añadir recetas y otras fuentes<\/summary>/);
});
test('saved cooking shortcut cannot inherit the full-width food photograph layout',()=>{
  const css=fs.readFileSync(require('node:path').join(__dirname,'../assets/roxy_list.css'),'utf8');
  assert.match(css, /\.recipe-card\.resume-card\{[^}]*grid-template-columns:48px minmax\(0,1fr\)/);
  assert.match(css, /\.recipe-card\.resume-card>img\{[^}]*width:48px;height:48px;min-height:0;aspect-ratio:1/);
  assert.match(css, /\.recipe-card\.resume-card>span\{[^}]*min-width:0;overflow-wrap:anywhere/);
});
