'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../assets/roxy_fitness_world.js'),'utf8');

function harness({reduced=false,voice=true}={}){
  const opened=[],exited=[],speeches=[],events={};let stopped=0;
  class Node{
    constructor(tag='div'){this.tag=tag;this.children=[];this.attrs={};this.dataset={};this.events={};this.text='';this.hidden=false;this.disabled=false;this.classList={add(){}};}
    setAttribute(key,value){this.attrs[key]=String(value);if(key.startsWith('data-'))this.dataset[key.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=String(value);}
    getAttribute(key){return this.attrs[key]??null;}
    get textContent(){return this.text+this.children.map(n=>n.textContent).join('');}set textContent(v){this.text=String(v);this.children=[];}
    addEventListener(key,fn){(this.events[key]||=new Set()).add(fn);}removeEventListener(key,fn){this.events[key]?.delete(fn);}
    contains(n){return n===this||this.children.some(c=>c.contains(n));}
    closest(selector){return this.matches(selector)?this:this.parent?.closest(selector)||null;}
    focus(){this.focused=true;}
    matches(selector){
      if(selector.endsWith(':last-child'))return this.parent?.children.at(-1)===this&&this.matches(selector.slice(0,-11));
      if(selector.startsWith('.'))return (this.attrs.class||'').split(' ').includes(selector.slice(1));
      if(selector.startsWith('#'))return this.attrs.id===selector.slice(1);
      const attr=selector.match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/);if(attr)return attr[2]===undefined?attr[1] in this.attrs:this.attrs[attr[1]]===attr[2];
      return this.tag===selector;
    }
    querySelectorAll(selector){
      const result=[],parts=selector.split(',').map(s=>s.trim());
      const visit=n=>{for(const child of n.children){if(parts.some(part=>{const split=part.split(/\s+/);if(!child.matches(split.pop()))return false;let ancestor=child.parent;while(split.length){const expected=split.pop();while(ancestor&&!ancestor.matches(expected))ancestor=ancestor.parent;if(!ancestor)return false;ancestor=ancestor.parent;}return true;}))result.push(child);visit(child);}};visit(this);return result;
    }
    querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
    set innerHTML(html){
      this.html=html;this.children=[];const stack=[this];
      for(const token of html.match(/<[^>]+>|[^<]+/g)||[]){if(token.startsWith('</')){stack.pop();continue;}if(token.startsWith('<')){const tag=token.match(/^<([\w-]+)/)?.[1];if(!tag)continue;const n=new Node(tag);for(const match of token.matchAll(/([\w-]+)="([^"]*)"/g))n.setAttribute(match[1],match[2]);n.hidden=/\shidden(?:\s|>)/.test(token);n.parent=stack.at(-1);n.parent.children.push(n);if(!['img','br','input'].includes(tag))stack.push(n);}else stack.at(-1).text+=token;}
    }
    click(){if(this.disabled)return;let n=this;while(n){for(const fn of n.events.click||[])fn({target:this});n=n.parent;}}
  }
  const root=new Node(),motion={matches:reduced,addEventListener:(event,fn)=>events.motion=fn},document={hidden:false,body:new Node('body'),addEventListener:(event,fn)=>events[event]=fn};
  const scope={document,matchMedia:()=>motion,RoxyHomeTour:{stop:()=>stopped++,...(voice?{speak:(...args)=>speeches.push(args)}:{})}};scope.window=scope;
  vm.runInNewContext(source,scope);const api=scope.RoxyFitnessWorld;
  const options=(identity='a')=>({identity,open:(...args)=>opened.push(JSON.parse(JSON.stringify(args))),exit:panel=>exited.push(panel)});
  api.mount(root,options());api.update({active:true,checking:false,view:'welcome'});
  const find=selector=>{const n=root.querySelector(selector);assert.ok(n,selector);return n;};
  return {api,root,motion,document,events,opened,exited,speeches,options,find,click:selector=>find(selector).click(),get stopped(){return stopped;}};
}

test('entry scenery has real tool destinations and never starts audio automatically',()=>{
  const h=harness();assert.equal(h.speeches.length,0);assert.match(h.root.html,/studio-cinema-211\.png/);assert.match(h.root.html,/studio-map-211\.png/);
  h.click('[data-fxw-open="yoga"]');h.click('[data-fxw-open="strength"]');h.click('[data-fxw-open="week"]');
  assert.deepEqual(h.opened,[['library',['yoga','pilates']],['library',['strength','calisthenics']],['week',[]]]);
  h.click('[data-fxw="preferences"]');h.click('[data-fxw="progress"]');assert.deepEqual(h.opened.slice(-2),[['preferences'],['progress']]);
});
test('map selection opens the selected real collection and backward navigation returns through entry to Casa',()=>{
  const h=harness();h.click('[data-fxw="map"]');assert.equal(h.find('.fxw-map').hidden,false);assert.equal(h.find('.fxw-map h1').focused,true);
  h.click('[data-fxw-select="strength"]');assert.equal(h.find('.fxw-detail-title').textContent,'Fuerza y calistenia');h.click('[data-fxw="open"]');assert.deepEqual(h.opened.at(-1),['library',['strength','calisthenics']]);
  h.api.update({active:true,checking:false,view:'space'});assert.equal(h.find('.fxw-tools').hidden,false);h.click('[data-fxw="back"]');assert.deepEqual(h.opened.at(-1),['room']);
  h.api.update({active:true,checking:false,view:'welcome'});h.click('[data-fxw="back"]');assert.equal(h.find('.fxw-entry').hidden,false);h.click('[data-fxw="back"]');assert.deepEqual(h.exited,['house']);
  h.click('[data-fxw="more"]');assert.equal(h.exited.at(-1),'more');
});
test('identity changes and reset return to entry and clear selected room without replacing the content host',()=>{
  const h=harness(),content=h.find('#fxWorldContent');h.click('[data-fxw="map"]');h.click('[data-fxw-select="strength"]');
  assert.equal(h.api.mount(h.root,h.options('b')),content);h.api.update({active:true,checking:false,view:'welcome'});assert.equal(h.find('.fxw-entry').hidden,false);assert.equal(h.find('.fxw-detail-title').textContent,'Yoga y Pilates');
  h.click('[data-fxw="map"]');h.api.reset();assert.equal(h.find('.fxw-entry').hidden,true);assert.equal(h.find('[data-fxw="map"]').disabled,true);
  h.api.update({active:true,checking:false,view:'welcome'});assert.equal(h.find('.fxw-entry').hidden,false);assert.equal(h.opened.length,0);
});
test('checking identity disables exercise entry until the owning module resolves it',()=>{
  const h=harness();h.api.update({active:true,checking:true,view:'welcome'});h.click('[data-fxw-open="yoga"]');h.click('[data-fxw="progress"]');assert.equal(h.opened.length,0);
  h.api.update({active:true,checking:false,view:'welcome'});h.click('[data-fxw-open="yoga"]');assert.equal(h.opened.length,1);
});
test('ambient pause and reduced motion preserve navigation and do not start or interrupt narration',()=>{
  const h=harness(),before=h.stopped;h.click('[data-fxw="motion"]');assert.equal(h.find('.fxw-scene').dataset.paused,'true');assert.equal(h.stopped,before);assert.equal(h.speeches.length,0);
  h.click('[data-fxw="motion"]');assert.equal(h.find('.fxw-scene').dataset.paused,'false');h.motion.matches=true;h.events.motion();assert.equal(h.find('.fxw-scene').dataset.paused,'true');
  h.click('[data-fxw="map"]');assert.equal(h.find('.fxw-map').hidden,false);
});
test('official voice receives fixed key, callback and audio host in their actual positions',()=>{
  const h=harness();h.click('[data-fxw="voice"]');const [key,callback,host]=h.speeches[0];
  assert.equal(key,'fitness');assert.equal(typeof callback,'function');assert.equal(host,h.find('.fxw-voice-audio'));
  callback('playing','Roxy te acompaña');assert.equal(h.find('.fxw-voice-status').textContent,'Roxy te acompaña');
  h.click('[data-fxw="voice"]');assert.equal(h.speeches.length,1);assert.equal(h.find('.fxw-voice-status').textContent,'');callback('playing','Tarde');assert.equal(h.find('.fxw-voice-status').textContent,'');
});
test('leaving, identity replacement, reset and hiding reject obsolete voice callbacks',()=>{
  for(const action of [h=>h.api.setActive(false),h=>h.api.mount(h.root,h.options('b')),h=>h.api.reset(),h=>{h.document.hidden=true;h.events.visibilitychange();}]){
    const h=harness();h.click('[data-fxw="voice"]');const callback=h.speeches[0][1];action(h);callback('playing','Old member speech');assert.equal(h.find('.fxw-voice-status').textContent,'');
  }
});
test('missing voice offers a readable status without selecting a different voice',()=>{
  const h=harness({voice:false});h.click('[data-fxw="voice"]');assert.match(h.find('.fxw-voice-status').textContent,/aún no está disponible/);assert.equal(h.speeches.length,0);
});
