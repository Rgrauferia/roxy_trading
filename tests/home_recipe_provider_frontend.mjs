import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

class Element {
  constructor(tag) { this.tagName=tag.toUpperCase();this.children=[];this.listeners={};this._text='';this.value='';this.hidden=false;this.parent=null; }
  get textContent() { return this._text+this.children.map(child=>child.textContent).join(''); }
  set textContent(text) { this._text=String(text);this.children.forEach(child=>{child.parent=null;});this.children=[]; }
  set innerHTML(_) { throw new Error('Provider HTML must never be interpreted'); }
  get firstChild() { return this.children[0]; }
  get isConnected() { return this.root||Boolean(this.parent?.isConnected); }
  append(...children) { children.forEach(child=>{child.parent=this;this.children.push(child);}); }
  replaceChildren(...children) { this.children.forEach(child=>{child.parent=null;});this.children=[];this._text='';if(this.tagName==='SELECT')this.value='';this.append(...children); }
  replaceWith(child) { const parent=this.parent;if(parent){const at=parent.children.indexOf(this);parent.children[at]=child;child.parent=parent;this.parent=null;} }
  setAttribute(name,value) { this[name]=value; }
  addEventListener(name,fn) { (this.listeners[name]||=[]).push(fn); }
  async emit(name) { for(const fn of this.listeners[name]||[])await fn({preventDefault(){}}); }
  click() { return this.emit('click'); }
  reportValidity() { return !all(this,'input').concat(all(this,'select')).some(el=>el.required&&(!el.value||el.value.length<(el.minLength||0))); }
}
const all=(parent,tag)=>parent.children.flatMap(child=>[...(child.tagName===tag.toUpperCase()?[child]:[]),...all(child,tag)]);
const document={createElement:tag=>new Element(tag),body:new Element('body')};document.body.root=true;
const sandbox={window:{},document,URL,fetch(){throw new Error('Only the supplied same-origin API client may run');}};
vm.runInNewContext(fs.readFileSync(new URL('../assets/roxy_home_recipe_provider.js',import.meta.url),'utf8'),sandbox);
const {render}=sandbox.window.RoxyRecipeProvider;
const service={access_allowed:true,access_status:'allowed'};
const container=()=>{const el=new Element('div');document.body.append(el);return el;};
const button=(parent,text)=>all(parent,'button').find(el=>el.textContent===text);
const cards=parent=>all(parent,'details').filter(el=>el.className==='provider-recipe-card');
const recipe=(title='Original recipe',area='Italian')=>({title,provider_original:{area,instructions:'First original paragraph.\nSecond original paragraph.'},
  ingredients:[{measure:'½ cup',name:'Rice'},{measure:'To taste',name:'Salt'}],steps:['First original paragraph.','Second original paragraph.'],
  image_url:'https://www.themealdb.com/images/media/meals/example.jpg',sources:[{title:'TheMealDB',url:'https://www.themealdb.com/'},{title:'Unsafe',url:'javascript:alert(1)'}]});

const unavailable=container();let deniedCalls=0;
render(unavailable,{user:'private',service:{access_allowed:false},api:()=>{deniedCalls++;}});
assert.equal(deniedCalls,0);assert.equal(all(unavailable,'button').length,0);assert.ok(unavailable.textContent.includes('Conexión pendiente'));
render(unavailable,{user:'private',service:{access_allowed:false,access_status:'not_included_in_demo'},api:()=>{deniedCalls++;}});
assert.ok(unavailable.textContent.includes('no está incluida en la demo'));assert.equal(deniedCalls,0);

const panel=container(),paths=[];
const api=async path=>{paths.push(path);return path.includes('/areas?')?{areas:['Italian','French','Italian','<img onerror=alert(1)>']}:
  {recipes:Array.from({length:6},(_,i)=>recipe(`<b>Original ${i}</b>`))};};
render(panel,{user:'home/a',service,api});assert.equal(paths.length,0);
panel.firstChild.open=true;await panel.firstChild.emit('toggle');assert.equal(paths.length,0,'opening alone must not query countries');
await button(panel,'Cargar países y regiones').click();
assert.equal(paths[0],'/v1/home-food/home%2Fa/providers/recipes/areas?requested=true');
const select=all(panel,'select')[0];assert.equal(select.children.length,4,'deduplicate area values');
assert.ok(select.children.some(option=>option.textContent==='Italia'&&option.value==='Italian'));
assert.ok(select.children.some(option=>option.textContent==='<img onerror=alert(1)>'),'area labels remain literal text');
assert.equal(all(panel,'img').length,0);
select.value='Italian';await select.emit('change');assert.equal(paths.length,1,'selection alone must not query recipes');
await all(panel,'form')[1].emit('submit');
assert.equal(paths[1],'/v1/home-food/home%2Fa/providers/recipes/browse?area=Italian&requested=true');
assert.equal(cards(panel).length,4,'country browse is capped at four complete records');
assert.equal(cards(panel)[0].firstChild.textContent,'<b>Original 0</b>');
assert.deepEqual(all(cards(panel)[0],'li').map(el=>el.textContent),['½ cup Rice','To taste Salt']);
const instructions=all(cards(panel)[0],'p').find(el=>el.className==='provider-original-instructions');
assert.equal(instructions.textContent,'First original paragraph.\nSecond original paragraph.');assert.equal(instructions.lang,'en');
assert.ok(all(panel,'a').every(anchor=>anchor.href.startsWith('https://')));
const photo=all(cards(panel)[0],'img')[0];await photo.emit('error');assert.ok(cards(panel)[0].textContent.includes('fotografía del proveedor no está disponible'));
assert.ok(panel.textContent.includes('No se ha guardado ni enviado a Compra'));
const sameDetails=panel.firstChild;render(panel,{user:'home/a',service,api});assert.equal(panel.firstChild,sameDetails);

const racing=container(),waiting=[];
render(racing,{user:'queries',service,api:path=>new Promise(resolve=>waiting.push({path,resolve}))});
const input=all(racing,'input')[0],form=all(racing,'form')[0];
input.value='first';const first=form.emit('submit');
input.value='second';await input.emit('input');assert.equal(button(racing,'Consultar TheMealDB').disabled,false);
const second=form.emit('submit');assert.equal(waiting.length,2);
assert.ok(waiting[1].path.includes('/search?q=second&limit=12&requested=true'));
waiting[1].resolve({recipes:[recipe('Second result')]});await second;
waiting[0].resolve({recipes:[recipe('First result')]});await first;
assert.equal(cards(racing)[0].firstChild.textContent,'Second result','older query cannot replace newer results');
assert.equal(button(racing,'Consultar TheMealDB').disabled,false);
input.value='pending';const changing=form.emit('submit');input.value='unsubmitted';await input.emit('input');
waiting[2].resolve({recipes:[recipe('Outdated result')]});await changing;
assert.equal(cards(racing).length,0,'editing query invalidates an in-flight response even before submitting');
assert.ok(racing.textContent.includes('Pulsa Consultar'));

const switching=container();let resolveAreas;
render(switching,{user:'old',service,api:()=>new Promise(resolve=>{resolveAreas=resolve;})});
const oldAreaRequest=button(switching,'Cargar países y regiones').click();
render(switching,{user:'new',service,api:async()=>({areas:['French']})});
resolveAreas({areas:['Italian']});await oldAreaRequest;
assert.equal(all(switching,'select')[0].children.length,0,'old household country response must be discarded');
await button(switching,'Cargar países y regiones').click();
assert.equal(all(switching,'select')[0].children[1].value,'French');
render(switching,{user:'new',service,api,hidden:true});assert.equal(switching.children.length,0);assert.equal(switching.hidden,true);

const failure=container();let attempts=0;
render(failure,{user:'retry',service,api:async()=>{if(++attempts===1)throw new Error('provider unavailable');return {areas:['French']};}});
await button(failure,'Cargar países y regiones').click();assert.ok(failure.textContent.includes('No se pudieron cargar'));
assert.equal(button(failure,'Cargar países y regiones').disabled,false);await button(failure,'Cargar países y regiones').click();
assert.equal(all(failure,'select')[0].children[1].value,'French');
console.log('PASS: unavailable/demo gates, explicit country loading, local controls, encoded browse/search, four-record limit, original text/photos, safe DOM/links, query/user tokens, retry and hidden mode.');
