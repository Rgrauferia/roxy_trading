'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const source=fs.readFileSync(require.resolve('../assets/roxy_home_living.js'),'utf8');
function harness(){
  const events={},navigation=[],speech=[],forms=[],guides=[];let current=true,stops=0,conversations=0;
  class Node {
    constructor(tag,text=''){this.tag=tag;this._text=text;this.children=[];this.events={};this.dataset={};this.attrs={};this.hidden=false;this.style={setProperty(){}};this.classes=new Set();this.classList={add:v=>this.classes.add(v),remove:v=>this.classes.delete(v),toggle:(v,on)=>on?this.classes.add(v):this.classes.delete(v)};}
    set className(v){this.classes=new Set(v.split(' '))}get className(){return [...this.classes].join(' ')}
    get textContent(){return this._text+this.children.map(n=>n.textContent).join('')}set textContent(v){this._text=v;this.children=[]}
    append(...nodes){this.children.push(...nodes)}replaceChildren(...nodes){this.children=nodes}
    get lastChild(){return this.children.at(-1)}setAttribute(k,v){this.attrs[k]=v}
    addEventListener(k,v){this.events[k]=v}focus(){document.activeElement=this}
    querySelector(selector){return this.querySelectorAll(selector)[0]||null}
    querySelectorAll(selector){const result=[];const visit=n=>{for(const c of n.children){if(selector.startsWith('.')?c.classes.has(selector.slice(1)):selector.startsWith('[data-destination=')?c.dataset.destination===selector.split('"')[1]:c.tag===selector)result.push(c);visit(c)}};visit(this);return result}
  }
  const root=new Node('section'),bar=new Node('div');
  const document={hidden:false,body:new Node('body'),createElement:t=>new Node(t),getElementById:id=>id==='homeLivingRoom'?root:bar,addEventListener:(k,fn)=>events[k]=fn};
  const window={RoxyHomeTour:{stop:()=>stops++,speak:(key,status,host)=>speech.push({key,status,host}),open:key=>guides.push(key)},RoxyHomeWorld:{isOpen:()=>false}};
  vm.runInNewContext(source,{window,document,Set});const api=window.RoxyHomeLiving;
  const owner={identity:'a',version:1,isCurrent:()=>current,navigate:p=>{navigation.push(p);api.show(p);api.enter()},converse:()=>conversations++,openForm:destination=>forms.push(destination)};
  api.bind(owner);
  const click=text=>{const b=root.querySelectorAll('button').find(n=>n.textContent===text&&!n.hidden);assert.ok(b,text);b.events.click()};
  const object=destination=>{const b=root.querySelector(`[data-destination="${destination}"]`);assert.ok(b,destination);return b};
  return {api,root,bar,owner,navigation,speech,forms,guides,object,click,events,document,window,expire:()=>current=false,get stops(){return stops},get conversations(){return conversations}};
}
test('rooms open existing tools, with no save or voice request on entry',()=>{
  const h=harness();assert.equal(h.speech.length,0);
  const objects=h.root.querySelectorAll('button').filter(n=>n.dataset.destination);
  assert.deepEqual(objects.map(n=>n.dataset.destination),['calendar','today','kitchen']);
  objects[0].events.click();assert.deepEqual(h.navigation,['calendar']);assert.equal(h.bar.hidden,false);assert.equal(h.speech.length,0);
  h.api.show('kitchen');assert.deepEqual(h.root.querySelectorAll('button').filter(n=>n.dataset.destination).map(n=>n.dataset.destination),['pantry','recipes','shopping']);
});
test('voice opt-in continues across rooms and cancels on navigation',()=>{
  const h=harness();h.click('Activar voz');assert.equal(h.speech.length,1);assert.equal(h.speech[0].key,'world-today');
  const before=h.stops;h.api.show('kitchen');h.api.enter();assert.ok(h.stops>before);assert.equal(h.speech.at(-1).key,'recipes');
  h.click('Silenciar');h.api.show('house');h.api.enter();assert.equal(h.speech.length,2);
});
test('late speech callbacks cannot update another room or member',()=>{
  const h=harness();h.click('Activar voz');const old=h.speech[0];h.api.show('kitchen');old.status('playing','Old');assert.equal(h.root.classes.has('rhl-speaking'),false);
  h.api.bind({...h.owner,identity:'b'});old.status('playing','Old');assert.equal(h.root.classes.has('rhl-speaking'),false);h.api.enter();assert.equal(h.speech.length,1);
});
test('routine account refresh preserves the room and active audio host',()=>{
  const h=harness();h.click('Activar voz');const host=h.root.querySelector('.rhl-audio');h.api.bind({...h.owner});assert.equal(h.root.querySelector('.rhl-audio'),host);
});
test('pausing ambient animation does not remove speech or stop it',()=>{
  const h=harness();h.click('Activar voz');const host=h.root.querySelector('.rhl-audio'),before=h.stops;h.click('Pausar ambiente');assert.equal(h.root.querySelector('.rhl-audio'),host);assert.equal(h.stops,before);assert.equal(h.root.querySelector('.rhl-stage').classes.has('rhl-still'),true);
});
test('expired session cannot navigate or start narration',()=>{
  const h=harness();h.expire();h.click('Activar voz');assert.equal(h.speech.length,0);assert.match(h.root.textContent,/Preparando/);
});
test('visibility change stops audio and returning does not autoplay',()=>{
  const h=harness();h.click('Activar voz');const before=h.stops;h.document.hidden=true;h.events.visibilitychange();assert.ok(h.stops>before);h.document.hidden=false;h.events.visibilitychange();assert.equal(h.speech.length,1);
});
test('conversation delegates to Home and stops room narration',()=>{
  const h=harness();h.click('Activar voz');const before=h.stops;h.click('Conversar');assert.equal(h.conversations,1);assert.ok(h.stops>before);
});
test('sign out removes room controls, resets sound and ignores old callbacks',()=>{
  const h=harness();h.click('Activar voz');h.api.bind(null);h.speech[0].status('playing','Old');assert.equal(h.root.querySelectorAll('button').length,0);assert.equal(h.bar.hidden,true);assert.equal(h.root.classes.has('rhl-speaking'),false);
  h.api.bind(h.owner);h.api.enter();assert.equal(h.speech.length,1);
});
test('returning from a tool restores focus to its room object',()=>{
  const h=harness();const calendar=h.root.querySelector('[data-destination="calendar"]');calendar.events.click();h.owner.navigate('house');assert.equal(h.document.activeElement?.dataset.destination,'calendar');
});

const roomCases=[
  ['garden','plants',['action:plant-new','plants','action:calendar-new']],
  ['wellness','fitness',['fitness','action:calendar-new','guide:fitness']],
  ['companions','pets',['action:pet-new','pets','shopping']],
  ['atelier','design',['action:design-new','design','guide:design']],
  ['connection','family',['family','action:family-privacy','guide:location']],
  ['agenda','calendar',['calendar','action:calendar-new','today']],
];

for(const [room,chapter,destinations] of roomCases)test(`${room} opens its actual tools, forms and fixed guide without saving or autoplay`,()=>{
  const h=harness();h.api.show(room);h.api.enter();
  assert.equal(h.bar.hidden,true);assert.equal(h.document.body.dataset.livingRoom,room);
  assert.deepEqual(h.root.querySelectorAll('button').filter(n=>n.dataset.destination).map(n=>n.dataset.destination),destinations);
  assert.equal(h.speech.length,0);assert.equal(h.forms.length,0);assert.equal(h.guides.length,0);
  for(const destination of destinations){
    h.api.show(room);h.object(destination).events.click();
    if(destination.startsWith('action:'))assert.equal(h.forms.at(-1),destination.slice(7));
    else if(destination.startsWith('guide:'))assert.equal(h.guides.at(-1),destination.slice(6));
    else assert.equal(h.navigation.at(-1),destination);
  }
  h.api.show(room);h.click('Activar voz');assert.equal(h.speech.at(-1).key,chapter);
});

test('every house entrance is reachable from the room map',()=>{
  const h=harness(),rooms=['house','kitchen',...roomCases.map(row=>row[0])];
  for(const room of rooms){
    h.api.show(room);const map=h.root.querySelector('.rhl-spaces');
    assert.equal(map.querySelectorAll('button').length,8);
    const active=map.querySelectorAll('button').filter(button=>button.attrs['aria-current']==='page');
    assert.equal(active.length,1);active[0].events.click();assert.equal(h.navigation.at(-1),room);
  }
});

test('existing tools keep a return button to their room without replacing the tool controls',()=>{
  for(const [tool,room] of [['today','house'],['recipes','kitchen'],['pantry','kitchen'],['shopping','kitchen'],['plants','garden'],['fitness','wellness'],['pets','companions'],['design','atelier'],['family','connection'],['calendar','agenda']]){
    const h=harness();h.api.show(tool);assert.equal(h.bar.hidden,false);assert.equal(h.root.querySelectorAll('button').length,0);
    const back=h.bar.querySelector('.rhl-back');assert.ok(back);back.events.click();
    assert.equal(h.navigation.at(-1),room);assert.equal(h.bar.hidden,true);assert.equal(h.document.body.dataset.livingRoom,room);
  }
});

test('expired or background session cannot invoke tools, forms or guides from retained controls',()=>{
  for(const hidden of [false,true])for(const [room,,destinations] of roomCases){
    const h=harness();h.api.show(room);const controls=destinations.map(h.object);
    if(hidden)h.document.hidden=true;else h.expire();
    controls.forEach(button=>button.events.click());
    assert.equal(h.forms.length,0);assert.equal(h.guides.length,0);assert.equal(h.navigation.length,0);
  }
});

test('expired conversation control cannot reopen Home conversation',()=>{
  const h=harness();h.expire();h.click('Conversar');assert.equal(h.conversations,0);
});

test('fixed guides pause room narration and do not switch the selected room',()=>{
  const h=harness();h.api.show('connection');h.click('Activar voz');const before=h.stops;
  h.object('guide:location').events.click();
  assert.deepEqual(h.guides,['location']);assert.deepEqual(h.navigation,[]);assert.ok(h.stops>before);
  assert.equal(h.speech.length,1);assert.equal(h.document.body.dataset.livingRoom,'connection');
});

test('an open immersive tour suppresses automatic room narration',()=>{
  const h=harness();h.click('Activar voz');h.window.RoxyHomeWorld.isOpen=()=>true;
  h.api.show('garden');h.api.enter();assert.equal(h.speech.length,1);
});

test('changing the session version resets voice and ignores its previous callback',()=>{
  const h=harness();h.click('Activar voz');const prior=h.speech[0];
  h.api.bind({...h.owner,version:2});h.api.enter();prior.status('playing','Obsolete');
  assert.equal(h.speech.length,1);assert.equal(h.root.classes.has('rhl-speaking'),false);
});
