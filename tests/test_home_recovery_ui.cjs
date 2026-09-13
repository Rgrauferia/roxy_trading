// Actual recovery controller, synthetic DOM/fetch/clipboard only; no real secrets.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const code = fs.readFileSync(require('node:path').join(__dirname,'../assets/roxy_home_recovery.js'),'utf8');
const codes = () => Array.from({length:8},(_,i)=>`${String(i+1).padStart(8,'0')}-AAAAAAAA-BBBBBBBB-CCCCCCCC`);
const deferred = () => { let resolve,reject; const promise = new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject}; };
const flush = async () => { for(let i=0;i<24;i++)await Promise.resolve(); };
class Target {
  constructor(){this.listeners=new Map();}
  addEventListener(key,fn){if(!this.listeners.has(key))this.listeners.set(key,new Set());this.listeners.get(key).add(fn);}
  removeEventListener(key,fn){this.listeners.get(key)?.delete(fn);}
  fire(key){for(const fn of [...this.listeners.get(key)||[]])fn({target:this,preventDefault(){}});}
}
class Element extends Target {
  constructor(tag,doc){super();this.tagName=tag;this.ownerDocument=doc;this.parentNode=null;this.children=[];this._text='';this.value='';this.hidden=false;this.disabled=false;this.checked=false;this.attributes={};}
  append(...nodes){for(const node of nodes){node.remove();node.parentNode=this;this.children.push(node);}}
  replaceChildren(...nodes){this.children.forEach(node=>node.parentNode=null);this.children=[];this._text='';this.append(...nodes);}
  remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(node=>node!==this);this.parentNode=null;}
  set textContent(value){this.replaceChildren();this._text=String(value);}
  get textContent(){return this._text+this.children.map(node=>node.textContent).join('');}
  get isConnected(){return this.root||Boolean(this.parentNode?.isConnected);}
  setAttribute(key,value){this.attributes[key]=String(value);}
  getAttribute(key){return this.attributes[key];}
  querySelectorAll(selector){const tags=selector.split(',').map(value=>value.trim());return descendants(this).filter(node=>tags.includes(node.tagName));}
  focus(){this.ownerDocument.activeElement=this;}
  click(){if(!this.disabled){if(this.tagName==='a')this.ownerDocument.downloads.push({href:this.href,download:this.download});this.fire('click');}}
  showModal(){this.open=true;}
  close(){this.open=false;this.fire('close');}
}
const descendants=root=>root.children.flatMap(node=>[node,...descendants(node)]);
const find=(h,tag,label)=>{const found=descendants(h.document.body).find(node=>node.tagName===tag&&node.textContent===label);assert.ok(found,`Missing ${tag}: ${label}`);return found;};
const input=(h,name,value)=>{const found=descendants(h.document.body).find(node=>node.tagName==='input'&&node.name===name);assert.ok(found,`Missing input ${name}`);if(value!==undefined)found.value=value;return found;};
const form=h=>descendants(h.document.body).find(node=>node.tagName==='form');
const error=h=>descendants(h.document.body).find(node=>node.className==='hr-error');
function harness({fetch:transport,clipboard,clipboardMissing=false}={}){
  let now=0,id=0;const timers=new Map(),requests=[],forbidden=[],copied=[],blobs=new Map(),revoked=[];
  const document=new Target();document.hidden=false;document.downloads=[];document.createElement=tag=>new Element(tag,document);document.body=document.createElement('body');document.body.root=true;
  const window=new Target();window.document=document;window.navigator={};if(!clipboardMissing)window.navigator.clipboard={writeText:async text=>{copied.push(text);if(clipboard)return clipboard(text);}};
  window.URL={createObjectURL:blob=>{const url=`blob:synthetic-${blobs.size}`;blobs.set(url,blob);return url;},revokeObjectURL:url=>revoked.push(url)};
  window.fetch=async(path,options)=>{requests.push({path,options});if(transport)return transport(path,options,requests.length);return{ok:true,json:async()=>options.method==='GET'?{enabled:false,remaining:0,generated_at:null}:{username:'member.test',recovery_codes:codes(),remaining:8,generated_at:'2026-09-13T00:00:00Z'}};};
  const deny=name=>{forbidden.push(name);throw new Error(`Forbidden ${name}`);};
  vm.runInNewContext(code,{window,AbortController,Blob,Date,setTimeout(fn,delay){const key=++id;timers.set(key,{fn,due:now+delay});return key;},clearTimeout(key){timers.delete(key);},localStorage:{getItem(){deny('localStorage');},setItem(){deny('localStorage');}},sessionStorage:{getItem(){deny('sessionStorage');},setItem(){deny('sessionStorage');}},indexedDB:{open(){deny('indexedDB');}},console:{log(){deny('console');},error(){deny('console');}}});
  const tick=async duration=>{const until=now+duration;for(;;){const next=[...timers].filter(([,value])=>value.due<=until).sort((a,b)=>a[1].due-b[1].due)[0];if(!next)break;const[key,value]=next;timers.delete(key);now=value.due;value.fn();await flush();}now=until;await flush();};
  return {api:window.RoxyHomeRecovery,document,window,requests,forbidden,copied,blobs,revoked,timers,tick};
}
const response=(data,status=200)=>({ok:status>=200&&status<300,status,json:async()=>data});
function fillReset(h){input(h,'username','member.test');input(h,'recovery_code',codes()[0]);input(h,'new_password','synthetic-password-123');input(h,'password_repeat','synthetic-password-123');}
function confirmRotation(h){input(h,'current_password','synthetic-old-password');const check=input(h,'confirm_rotation');check.checked=true;}

test('public reset opens without network, storage or an email recovery promise',()=>{
  const h=harness();h.api.openReset();assert.equal(h.requests.length,0);assert.deepEqual(h.forbidden,[]);
  assert.match(h.document.body.textContent,/códigos que guardaste previamente/);assert.match(h.document.body.textContent,/No enviamos códigos por correo/);
  assert.equal(descendants(h.document.body).find(node=>node.tagName==='dialog').getAttribute('aria-labelledby').includes('title'),true);
});
test('code interstitial does not continue until explicit saved confirmation, and clears its source array',async()=>{
  const h=harness(),source=codes();let callback=0,settled=false;const pending=h.api.showCodes({username:'member.test',recovery_codes:source,onContinue:()=>callback++}).then(value=>{settled=true;return value;});
  assert.ok(source.every(value=>value===''));assert.equal(descendants(h.document.body).filter(node=>node.tagName==='code').length,8);
  find(h,'button','Ya los guardé · continuar').click();await flush();assert.equal(settled,false);assert.equal(callback,0);assert.equal(h.requests.length,0);assert.deepEqual(h.copied,[]);assert.equal(h.document.downloads.length,0);
  const saved=input(h,'codes_saved');saved.checked=true;saved.fire('change');find(h,'button','Ya los guardé · continuar').click();assert.equal(await pending,true);assert.equal(callback,1);assert.equal(h.document.body.textContent,'');assert.deepEqual(h.forbidden,[]);
});
test('copy and TXT export are explicit and never replace the saved checkbox',async()=>{
  const h=harness(),pending=h.api.showCodes({username:'member.test',recovery_codes:codes()});
  find(h,'button','Copiar códigos').click();await flush();assert.equal(h.copied.length,1);assert.match(h.copied[0],/Usuario: member.test/);for(const value of codes())assert.ok(h.copied[0].includes(value));
  assert.equal(input(h,'codes_saved').checked,false);assert.equal(find(h,'button','Ya los guardé · continuar').disabled,true);
  find(h,'button','Descargar TXT').click();assert.equal(h.document.downloads.length,1);const exported=await [...h.blobs.values()][0].text();assert.equal(exported,h.copied[0]);assert.equal(h.document.downloads[0].download,'roxy-home-recovery-codes.txt');
  h.api.reset();assert.equal(await pending,false);assert.equal(h.revoked.length,1);assert.equal(h.timers.size,0);assert.equal(h.document.body.textContent,'');
});
for(const mode of ['button','escape','native-close','identity','pagehide'])test(`closing codes via ${mode} clears plaintext without asserting it was saved`,async()=>{
  const h=harness();let callback=0;const pending=h.api.showCodes({username:'member.test',recovery_codes:codes(),onContinue:()=>callback++});
  const dialog=descendants(h.document.body).find(node=>node.tagName==='dialog'),oldCodes=dialog.querySelectorAll('code');
  if(mode==='button')find(h,'button','Cerrar').click();if(mode==='escape')dialog.fire('cancel');if(mode==='native-close')dialog.close();if(mode==='identity')h.api.reset();if(mode==='pagehide')h.window.fire('pagehide');
  assert.equal(await pending,false);assert.equal(callback,0);assert.equal(h.document.body.textContent,'');assert.equal(dialog.isConnected,false);
  assert.ok(oldCodes.every(node=>!node.isConnected&&node.textContent===''));assert.equal(h.timers.size,0);
});
test('switching to a password manager masks rendered codes but preserves the one-time bundle until return',async()=>{
  const h=harness();let settled=false;const pending=h.api.showCodes({username:'member.test',recovery_codes:codes()}).then(value=>{settled=true;return value;});
  const saved=input(h,'codes_saved');saved.checked=true;saved.fire('change');
  const oldCodes=descendants(h.document.body).filter(node=>node.tagName==='code'),content=descendants(h.document.body).find(node=>node.className==='hr-content');
  find(h,'button','Copiar códigos').click();await flush();h.document.hidden=true;h.document.fire('visibilitychange');await flush();
  assert.equal(settled,false);assert.equal(content.hidden,true);assert.ok(oldCodes.every(node=>node.isConnected&&node.textContent===''));assert.equal(saved.checked,false);assert.equal(h.copied.length,1);
  h.document.hidden=false;h.document.fire('visibilitychange');assert.equal(content.hidden,false);assert.deepEqual(oldCodes.map(node=>node.textContent),codes());assert.equal(find(h,'button','Ya los guardé · continuar').disabled,true);
  find(h,'button','Descargar TXT').click();h.document.hidden=true;h.document.fire('visibilitychange');await flush();assert.equal(settled,false);assert.equal(h.document.downloads.length,1);
  h.document.hidden=false;h.document.fire('visibilitychange');saved.checked=true;saved.fire('change');find(h,'button','Ya los guardé · continuar').click();assert.equal(await pending,true);assert.ok(oldCodes.every(node=>node.textContent===''));
});
test('an identity change while hidden destroys the retained bundle instead of restoring it',async()=>{
  let current=true;const h=harness();h.api.openManage({id:'member-a',isCurrent:()=>current});await flush();confirmRotation(h);form(h).fire('submit');await flush();
  const oldCodes=descendants(h.document.body).filter(node=>node.tagName==='code');assert.equal(oldCodes.length,8);h.document.hidden=true;h.document.fire('visibilitychange');current=false;h.document.hidden=false;h.document.fire('visibilitychange');assert.equal(h.document.body.textContent,'');assert.ok(oldCodes.every(node=>node.textContent===''));
});
test('a bundle received while hidden is not rendered until the same account returns',async()=>{
  const pending=deferred(),h=harness({fetch:async(path)=>path.endsWith('/codes')?pending.promise:response({enabled:false,remaining:0})});
  h.api.openManage({id:'member-a',isCurrent:()=>true});await flush();confirmRotation(h);form(h).fire('submit');await flush();h.document.hidden=true;h.document.fire('visibilitychange');pending.resolve(response({username:'member.test',recovery_codes:codes()}));await flush();
  const nodes=descendants(h.document.body).filter(node=>node.tagName==='code');assert.equal(nodes.length,8);assert.ok(nodes.every(node=>node.textContent===''));h.document.hidden=false;h.document.fire('visibilitychange');assert.deepEqual(nodes.map(node=>node.textContent),codes());h.api.reset();
});
test('invalid code bundles are not displayed and are consumed without a success callback',async()=>{
  const h=harness(),invalid=codes().slice(0,7);assert.equal(await h.api.showCodes({username:'member.test',recovery_codes:invalid}),false);assert.equal(h.document.body.textContent,'');assert.ok(invalid.every(value=>value===''));
  const duplicate=Array(8).fill(codes()[0]);assert.equal(await h.api.showCodes({username:'member.test',recovery_codes:duplicate}),false);assert.equal(h.copied.length,0);
});
test('failed or late clipboard completion cannot reveal a closed bundle',async()=>{
  const clipboard=deferred(),h=harness({clipboard:()=>clipboard.promise}),pending=h.api.showCodes({username:'member.test',recovery_codes:codes()});
  find(h,'button','Copiar códigos').click();h.api.reset();clipboard.reject(new Error('clipboard denied'));await flush();assert.equal(await pending,false);assert.equal(h.document.body.textContent,'');
});
test('management reads only status with the member binding and never presents old codes',async()=>{
  const h=harness({fetch:async()=>response({enabled:true,remaining:3,generated_at:'2026-09-13T10:00:00Z',recovery_codes:codes()})});
  h.api.openManage({id:'member-a',username:'member.test',isCurrent:()=>true});await flush();assert.equal(h.requests.length,1);assert.equal(h.requests[0].path,'/v1/home-account/recovery');assert.equal(h.requests[0].options.headers['X-Roxy-Member-Id'],'member-a');assert.equal(h.requests[0].options.cache,'no-store');assert.equal(h.requests[0].options.credentials,'same-origin');assert.match(h.document.body.textContent,/3 códigos/);assert.equal(descendants(h.document.body).filter(node=>node.tagName==='code').length,0);
});
test('rotation needs password and explicit confirmation, clears password immediately and returns exactly one bundle',async()=>{
  const h=harness();h.api.openManage({id:'member-a'});await flush();form(h).fire('submit');assert.equal(h.requests.length,1);assert.match(error(h).textContent,/contraseña actual/);
  input(h,'current_password','synthetic-old-password');form(h).fire('submit');assert.equal(h.requests.length,1);assert.match(error(h).textContent,/Confirma/);
  confirmRotation(h);const password=input(h,'current_password');form(h).fire('submit');assert.equal(password.value,'');await flush();assert.equal(h.requests.length,2);assert.equal(h.requests[1].path,'/v1/home-account/recovery/codes');assert.deepEqual(JSON.parse(h.requests[1].options.body),{current_password:'synthetic-old-password'});assert.equal(h.requests[1].options.headers['X-Roxy-Member-Id'],'member-a');assert.equal(descendants(h.document.body).filter(node=>node.tagName==='code').length,8);
});
test('duplicate rotation submits produce a single write and late codes are wiped after identity disposal',async()=>{
  const pending=deferred(),late={username:'member.test',recovery_codes:codes()},h=harness({fetch:async(path)=>path.endsWith('/codes')?pending.promise:response({enabled:false,remaining:0})});
  h.api.openManage({id:'member-a'});await flush();confirmRotation(h);const submitForm=form(h);submitForm.fire('submit');submitForm.fire('submit');await flush();assert.equal(h.requests.length,2);
  h.api.reset();assert.equal(h.requests[1].options.signal.aborted,true);pending.resolve(response(late));await flush();assert.ok(late.recovery_codes.every(value=>value===''));assert.equal(h.document.body.textContent,'');
});
test('uncertain rotation allows another explicit password-confirmed generation without claiming recoverable codes',async()=>{
  const pending=deferred(),h=harness({fetch:async(path)=>path.endsWith('/codes')?pending.promise:response({enabled:true,remaining:8})});
  h.api.openManage({id:'member-a'});await flush();confirmRotation(h);form(h).fire('submit');await flush();await h.tick(12000);assert.equal(h.requests[1].options.signal.aborted,true);assert.match(error(h).textContent,/confirmar la creación/);assert.equal(input(h,'current_password').value,'');assert.equal(input(h,'confirm_rotation').checked,false);assert.equal(descendants(h.document.body).filter(node=>node.tagName==='code').length,0);
  h.api.reset();pending.resolve(response({username:'member.test',recovery_codes:codes()}));await flush();
});
test('closing reset clears password and code fields including detached field references',()=>{
  const h=harness();h.api.openReset();fillReset(h);const password=input(h,'new_password'),code=input(h,'recovery_code'),repeat=input(h,'password_repeat');find(h,'button','Cerrar').click();assert.equal(password.value,'');assert.equal(repeat.value,'');assert.equal(code.value,'');assert.equal(h.requests.length,0);
});
test('reset validates full code, password length and confirmation before sending',()=>{
  const h=harness();h.api.openReset();fillReset(h);input(h,'recovery_code','not-code');form(h).fire('submit');assert.match(error(h).textContent,/código completo/);assert.equal(h.requests.length,0);
  input(h,'recovery_code',codes()[0]);input(h,'new_password','short');form(h).fire('submit');assert.match(error(h).textContent,/12 y 128/);
  input(h,'new_password','synthetic-password-123');input(h,'password_repeat','different-password-123');form(h).fire('submit');assert.match(error(h).textContent,/no coinciden/);assert.equal(h.requests.length,0);
});
test('reset enforces username bounds consistently with registration',()=>{
  const h=harness();h.api.openReset();fillReset(h);assert.equal(input(h,'username').minLength,3);assert.equal(input(h,'username').maxLength,64);
  for(const value of ['ab','a'.repeat(65)]){input(h,'username',value);form(h).fire('submit');assert.match(error(h).textContent,/3 a 64/);assert.equal(h.requests.length,0);}
  assert.match(h.document.body.textContent,/Si no guardaste códigos, esta función no puede recuperar tu cuenta\. No tenemos recuperación por correo\./);assert.doesNotMatch(h.document.body.textContent,/canal de soporte|necesitarás asistencia/);
});
for(const format of ['compact','spaces','mixed'])test(`reset accepts and normalizes a complete 32-hex code pasted as ${format}`,async()=>{
  const h=harness({fetch:async()=>response({status:'RESET'})});h.api.openReset();fillReset(h);const code=codes()[0].toLowerCase();input(h,'recovery_code',format==='compact'?code.replaceAll('-',''):format==='spaces'?code.replaceAll('-',' '):` ${code.replace('-', ' - ')} `);form(h).fire('submit');await flush();assert.equal(h.requests.length,1);assert.equal(JSON.parse(h.requests[0].options.body).recovery_code,codes()[0]);
});
test('successful reset requires a manual login and discloses invalidation of all previous recovery codes',async()=>{
  const h=harness({fetch:async()=>response({status:'RESET'})});h.api.openReset();fillReset(h);const oldPassword=input(h,'new_password');form(h).fire('submit');assert.equal(oldPassword.value,'');await flush();
  assert.equal(h.requests.length,1);const request=h.requests[0];assert.equal(request.path,'/v1/home-account/recovery/reset');assert.equal(request.options.headers['X-Roxy-Member-Id'],undefined);assert.equal(JSON.parse(request.options.body).recovery_code,codes()[0]);assert.match(h.document.body.textContent,/Inicia sesión manualmente/);assert.match(h.document.body.textContent,/Todos tus códigos.*invalidados/);assert.match(h.document.body.textContent,/genera un juego nuevo/);assert.equal(descendants(h.document.body).filter(node=>node.tagName==='input').length,0);assert.deepEqual(h.forbidden,[]);
});
for(const status of [400,401,403,404,422])test(`wrong account/code response ${status} has the same generic message without echoing credentials`,async()=>{
  const h=harness({fetch:async()=>response({detail:'member.test secret diagnostic'},status)});h.api.openReset();fillReset(h);form(h).fire('submit');await flush();assert.equal(error(h).textContent,'No pudimos verificar esos datos. Revisa el usuario y un código válido sin usar.');assert.equal(input(h,'recovery_code').value,'');assert.equal(input(h,'new_password').value,'');assert.equal(h.document.body.textContent.includes('secret diagnostic'),false);
});
test('duplicate reset taps do not spend multiple recovery codes',async()=>{
  const pending=deferred(),h=harness({fetch:()=>pending.promise});h.api.openReset();fillReset(h);const submitForm=form(h);submitForm.fire('submit');submitForm.fire('submit');await flush();assert.equal(h.requests.length,1);pending.resolve(response({status:'RESET'}));await flush();
});
test('management without an individual member never makes an authenticated request',async()=>{
  const h=harness();h.api.openManage({username:'shared'});await flush();assert.equal(h.requests.length,0);assert.equal(h.document.body.textContent,'');
});
test('a superseded management status response cannot populate another member dialog',async()=>{
  const pending=deferred(),h=harness({fetch:async(_path,_options,n)=>n===1?pending.promise:response({enabled:false,remaining:0})});h.api.openManage({id:'member-a'});await flush();h.api.openManage({id:'member-b'});await flush();pending.resolve(response({enabled:true,remaining:8}));await flush();assert.equal(h.requests[0].options.signal.aborted,true);assert.match(h.document.body.textContent,/Aún no has activado/);assert.equal(h.document.body.textContent.includes('8 códigos de recuperación disponibles'),false);
});
