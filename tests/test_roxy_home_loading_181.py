"""Execute the shipped photo/SW code with deterministic DOM/network doubles.

No browser, provider, household, generation call or external request is used.
These regressions do not claim a physical-phone performance measurement.
"""

import base64
import io
from pathlib import Path
import shutil
import subprocess

import pytest
from fastapi import HTTPException
from PIL import Image
from starlette.requests import Request

from roxy_os.home_recipe_photos import CARD_PHOTO_MAX_BYTES, RecipePhotoStore


ROOT = Path(__file__).resolve().parents[1]

NODE_HARNESS = r"""
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const scenario=process.argv[1],root=process.argv[2];
const source=fs.readFileSync(path.join(root,'assets/roxy_list.js'),'utf8');
const start=source.indexOf('  const recipeImage = recipe => {');
const end=source.indexOf('  const dbPromise = ',start);
assert.ok(start>=0&&end>start,'Test must execute the actual shipped photo helpers');
const snippet=source.slice(start,end);
const flush=async()=>{for(let i=0;i<16;i++)await Promise.resolve();};

function node(){
 const classes=new Set(),events=new Map();
 const item={isConnected:true,hidden:false,loading:'',children:[],parent:null,_src:'',
  classList:{add:v=>classes.add(v),remove:v=>classes.delete(v),contains:v=>classes.has(v)},
  append(child){this.children.push(child);child.parent=this;},
  remove(){this.isConnected=false;if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this);},
  addEventListener(name,fn,opts={}){if(!events.has(name))events.set(name,[]);events.get(name).push({fn,once:opts.once});},
  emit(name){const list=events.get(name)||[];events.set(name,list.filter(x=>!x.once));list.forEach(x=>x.fn());},
  set src(value){this._src=value;},get src(){return this._src;},
 };
 return item;
}
function response(status=200,blob=async()=>({exact:true}),type='image/webp'){
 return {status,headers:{get:key=>key==='content-type'?type:null},blob};
}
function harness(handler=async()=>response()){
 let now=0,sequence=0,observer;
 const timers=new Map(),calls={fetch:[],created:[],revoked:[],abort:0};
 const context={Map,AbortController,encodeURIComponent,queueMicrotask,
  document:{createElement:()=>node()},
  setTimeout(fn,delay){const id=++sequence;timers.set(id,{fn,at:now+delay,delay});return id;},
  clearTimeout(id){timers.delete(id);},
  IntersectionObserver:class {
   constructor(callback,options){this.callback=callback;this.options=options;this.targets=new Set();observer=this;}
   observe(target){this.targets.add(target);}
   unobserve(target){this.targets.delete(target);}
   enter(target,isIntersecting=true){this.callback([{target,isIntersecting}]);}
  },
  URL:{createObjectURL(blob){calls.created.push(blob);return 'blob:exact-'+calls.created.length;},
       revokeObjectURL(url){calls.revoked.push(url);}},
  fetch(url,options){calls.fetch.push({url,options});options.signal.addEventListener('abort',()=>calls.abort++);return handler(url,options,calls.fetch.length);},
 };
 vm.createContext(context);
 vm.runInContext(snippet+'\nthis.hydrate=hydrateRecipeImage;this.observed=observedRecipeImages;',context);
 return {context,calls,timers,get observer(){return observer;},
  async nextTimer(){await flush();assert.ok(timers.size,'Expected a bounded timer');
   const [id,timer]=[...timers].sort((a,b)=>a[1].at-b[1].at)[0];timers.delete(id);now=timer.at;timer.fn();await flush();return timer.delay;},
  get now(){return now;},
 };
}
const title={title:'Panqueques de avena'};
const status=host=>host.children.map(x=>x.textContent||'').join(' ');
const failure=(image,host)=>{
 assert.equal(image.classList.contains('recipe-image-loading'),false);
 assert.equal(image.isConnected,false);
 assert.equal(host.classList.contains('no-photo'),true);
 assert.ok(!status(host).includes('Cargando')&&!status(host).includes('preparando'));
 assert.ok(status(host).length>0,'Missing image has a finite honest message');
};
const cases={
 async observer_eager(){
  const h=harness(),host=node();
  // The real renderer connects a card in the same synchronous render task.
  const connected=node();connected.loading='lazy';connected.isConnected=false;
  const queued=h.context.hydrate(connected,title,host);connected.isConnected=true;await queued;await flush();
  assert.ok(h.observer.targets.has(connected));assert.equal(h.calls.fetch.length,0);
  h.observer.enter(connected,false);assert.equal(h.calls.fetch.length,0);
  h.observer.enter(connected);await flush();
  assert.equal(connected.loading,'eager','Native lazy loading must not postpone the blob a second time');
  assert.equal(h.observer.targets.has(connected),false);
  assert.equal(h.context.observed.has(connected),false);
  assert.equal(h.calls.fetch.length,1);
  assert.ok(h.calls.fetch[0].url.endsWith('&variant=card'));
  assert.equal(h.calls.fetch[0].options.credentials,'same-origin');
  assert.equal(connected.src,'blob:exact-1');
  connected.emit('load');assert.equal(connected.classList.contains('recipe-image-loading'),false);
  assert.equal(status(host),'');assert.deepEqual(h.calls.revoked,['blob:exact-1']);
 },
 async detached_observer(){
  const h=harness(),image=node();image.loading='lazy';image.isConnected=false;
  await h.context.hydrate(image,title,node());await flush();
  assert.equal(h.observer.targets.has(image),false);
  h.observer.enter(image);await flush();assert.equal(h.calls.fetch.length,0);
 },
 async detached_before_blob(){
  let finish;const h=harness(async()=>response(200,()=>new Promise(resolve=>finish=resolve)));
  const image=node(),host=node();const pending=h.context.hydrate(image,title,host);await flush();
  image.isConnected=false;finish({exact:true});await pending;
  assert.equal(image.src,'');assert.equal(h.calls.created.length,0);assert.equal(h.timers.size,0);
 },
 async stale_blob_cannot_replace_new_recipe(){
  let finishFirst,staleBodies=0;
  const h=harness((_url,_options,index)=>index===1?new Promise(resolve=>finishFirst=resolve):Promise.resolve(response(200,async()=>({recipe:'B'}))));
  const image=node(),host=node();
  const first=h.context.hydrate(image,{title:'Recipe A'},host);await flush();
  await h.context.hydrate(image,{title:'Recipe B'},host);
  assert.equal(image.src,'blob:exact-1');assert.equal(h.calls.created[0].recipe,'B');
  finishFirst(response(200,async()=>{staleBodies++;return {recipe:'A'};}));await first;
  assert.equal(image.src,'blob:exact-1','A late response must not replace the current recipe picture');
  assert.equal(h.calls.created.length,1,'A stale job must not allocate a new object URL');
  assert.equal(staleBodies,0,'A stale response must not download/decode its body unnecessarily');
 },
 async stale_failure_cannot_remove_new_recipe(){
  let finishFirst;
  const h=harness((_url,_options,index)=>index===1?new Promise(resolve=>finishFirst=resolve):Promise.resolve(response(200,async()=>({recipe:'B'}))));
  const image=node(),host=node();
  const first=h.context.hydrate(image,{title:'Recipe A'},host);await flush();
  await h.context.hydrate(image,{title:'Recipe B'},host);image.emit('load');
  finishFirst(response(404));await first;
  assert.equal(image.isConnected,true,'A stale missing photo must not remove the new recipe image');
  assert.equal(image.src,'blob:exact-1');assert.equal(status(host),'');
  assert.equal(host.classList.contains('no-photo'),false);
 },
 async stale_202_cannot_restart_status_or_retry(){
  let finishFirst;
  const h=harness((_url,_options,index)=>index===1?new Promise(resolve=>finishFirst=resolve):Promise.resolve(response()));
  const image=node(),host=node();const first=h.context.hydrate(image,{title:'Recipe A'},host);await flush();
  await h.context.hydrate(image,{title:'Recipe B'},host);image.emit('load');
  finishFirst(response(202));await flush();const staleTimers=h.timers.size;
  while(h.timers.size)await h.nextTimer();await first;
  assert.equal(staleTimers,0,'A stale 202 must not create a retry wait');
  assert.equal(status(host),'','A stale 202 must not reintroduce a preparing-photo message');
  assert.equal(h.calls.fetch.length,2);assert.equal(image.src,'blob:exact-1');
 },
 async detached_during_retry(){
  const h=harness(async()=>response(202)),image=node(),host=node();
  const pending=h.context.hydrate(image,title,host);await flush();image.isConnected=false;
  assert.equal(await h.nextTimer(),3000);await pending;
  assert.equal(h.calls.fetch.length,1);assert.equal(h.calls.created.length,0);assert.equal(h.timers.size,0);
 },
 async only_three_202_attempts(){
  const h=harness(async()=>response(202)),image=node(),host=node();
  const pending=h.context.hydrate(image,title,host);await flush();
  assert.equal(await h.nextTimer(),3000);assert.equal(await h.nextTimer(),3000);await pending;
  assert.equal(h.calls.fetch.length,3);assert.equal(h.now,6000);assert.equal(h.timers.size,0);
  failure(image,host);assert.equal(status(host),'Foto específica pendiente');
 },
 async pending_then_ready(){
  const h=harness(async(_url,_options,index)=>response(index<3?202:200)),image=node(),host=node();
  const pending=h.context.hydrate(image,title,host);await flush();
  await h.nextTimer();await h.nextTimer();await pending;
  assert.equal(h.calls.fetch.length,3);assert.equal(image.src,'blob:exact-1');assert.equal(h.timers.size,0);
  image.emit('load');assert.equal(status(host),'');assert.equal(image.classList.contains('recipe-image-loading'),false);
 },
 async fetch_timeout(){
  const h=harness((_url,{signal})=>new Promise((_resolve,reject)=>signal.addEventListener('abort',()=>reject(new Error('timeout')))));
  const image=node(),host=node();const pending=h.context.hydrate(image,title,host);
  assert.equal(await h.nextTimer(),12000);await pending;
  assert.equal(h.calls.abort,1);assert.equal(h.calls.fetch.length,1);assert.equal(h.timers.size,0);failure(image,host);
 },
 async body_timeout(){
  const h=harness(async(_url,{signal})=>response(200,()=>new Promise((_resolve,reject)=>signal.addEventListener('abort',()=>reject(new Error('body timeout'))))));
  const image=node(),host=node();const pending=h.context.hydrate(image,title,host);
  assert.equal(await h.nextTimer(),12000);await pending;
  assert.equal(h.calls.abort,1);assert.equal(h.calls.created.length,0);failure(image,host);
 },
 async network_error(){
  const h=harness(async()=>{throw new Error('offline');}),image=node(),host=node();
  await h.context.hydrate(image,title,host);assert.equal(h.timers.size,0);failure(image,host);
 },
 async http_failures(){
  for(const code of [401,403,404,429,500,503]){
   const h=harness(async()=>response(code)),image=node(),host=node();
   await h.context.hydrate(image,title,host);assert.equal(h.calls.fetch.length,1);assert.equal(h.timers.size,0);failure(image,host);
  }
  const h=harness(async()=>response(200,undefined,'application/json')),image=node(),host=node();
  await h.context.hydrate(image,title,host);failure(image,host);assert.equal(h.calls.created.length,0);
 },
 async decode_error(){
  const h=harness(),image=node(),host=node();await h.context.hydrate(image,title,host);
  image.emit('error');failure(image,host);assert.deepEqual(h.calls.revoked,['blob:exact-1']);
 },
 async hide_on_missing(){
  const h=harness(async()=>response(404)),image=node(),host=node();
  await h.context.hydrate(image,title,host,{hideOnMissing:true});
  assert.equal(image.hidden,true);assert.equal(image.classList.contains('recipe-image-loading'),false);assert.equal(status(host),'');
 },
 async card_not_full_or_asset(){
  const h=harness(),image=node();await h.context.hydrate(image,title,node());
  assert.ok(!h.calls.fetch[0].url.includes('variant=card'),'Detail remains a full image');
  for(const photo of [{photo_asset:'/assets/roxy_home/recipes/exact.jpg'}, {photo_data_url:'data:image/png;base64,EXACT'}]){
   const local=harness(),card=node();card.loading='lazy';
   await local.context.hydrate(card,{...title,...photo},node(),{immediate:true});
   assert.equal(local.calls.fetch.length,0);assert.equal(card.src,photo.photo_asset||photo.photo_data_url);
   assert.equal(card.loading,'eager');card.emit('load');assert.equal(card.classList.contains('recipe-image-loading'),false);
  }
 },
 async install_core_shell_only(){
  const listeners={},downloads=[];let installed,skipped=0;
  const sw={self:{location:{origin:'https://roxy.test'},addEventListener:(name,fn)=>listeners[name]=fn,
    skipWaiting:async()=>skipped++,clients:{claim:async()=>{}}},URL,
    caches:{open:async()=>({addAll:async paths=>downloads.push(...paths)})}};
  vm.createContext(sw);vm.runInContext(fs.readFileSync(path.join(root,'assets/roxy_list_sw.js'),'utf8'),sw);
  listeners.install({waitUntil:promise=>installed=promise});await installed;
  assert.equal(skipped,1);assert.ok(downloads.includes('/home'));assert.ok(downloads.includes('/lista-manifest.json'));
  assert.ok(downloads.some(p=>p.startsWith('/assets/roxy_list.js?')));
  assert.ok(downloads.some(p=>p.startsWith('/assets/roxy_list.css?')));
  assert.ok(downloads.length<=20,'Installation should not download the entire catalogue');
  assert.equal(new Set(downloads).size,downloads.length);
  assert.ok(downloads.every(p=>!p.includes('/vendor/')&&!p.includes('/recipes/')&&!p.includes('/products/')));
  assert.ok(downloads.every(p=>p==='/home'||p==='/lista-manifest.json'||p==='/assets/roxy_home_avatar.jpg'||/\.(css|js)\?/.test(p)));
  for(const pathname of ['/v1/home-food/recipe-photo?title=Exact&variant=card','/api/fitness/v1/me/profile','/api/fitness/v1/exercises']){
   let intercepted=false;listeners.fetch({request:{url:'https://roxy.test'+pathname,method:'GET',mode:'cors'},respondWith:()=>intercepted=true});
   assert.equal(intercepted,false,'The SW must not cache live/private API requests');
  }
 },
};
(async()=>{assert.ok(cases[scenario]);await cases[scenario]();console.log('PASS '+scenario);})().catch(e=>{console.error(e);process.exitCode=1;});
"""


@pytest.mark.parametrize("scenario", [
    "observer_eager", "detached_observer", "detached_before_blob", "detached_during_retry",
    "stale_blob_cannot_replace_new_recipe", "stale_failure_cannot_remove_new_recipe",
    "stale_202_cannot_restart_status_or_retry",
    "only_three_202_attempts", "pending_then_ready", "fetch_timeout", "body_timeout",
    "network_error", "http_failures", "decode_error", "hide_on_missing",
    "card_not_full_or_asset", "install_core_shell_only",
])
def test_actual_loading_code(scenario):
    node = shutil.which("node")
    assert node, "Node.js is required on PATH to execute the actual frontend regressions"
    result = subprocess.run([node, "-e", NODE_HARNESS, scenario, str(ROOT)],
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"PASS {scenario}" in result.stdout, "An unresolved promise must not silently count as a pass"


def test_card_helper_returns_a_bounded_derivative_of_only_the_approved_original(tmp_path):
    # Deliberately synthetic test pixels, never a production recipe image.
    pixels = Image.effect_noise((1200, 800), 80).convert("RGB")
    data = io.BytesIO()
    pixels.save(data, format="PNG")
    store = RecipePhotoStore(tmp_path / "photos", built_in_root=tmp_path / "built-in")
    original = store.save_generated("Synthetic exact recipe", base64.b64encode(data.getvalue()).decode(), approved=True)
    before = original.read_bytes()
    card, metadata = store.resolve_card("Synthetic exact recipe")
    assert card != original and metadata["variant"] == "card"
    assert card.stat().st_size <= CARD_PHOTO_MAX_BYTES < original.stat().st_size
    with Image.open(card) as image:
        assert image.format == "WEBP" and max(image.size) <= 480
        assert image.width / image.height == pytest.approx(1.5)
    assert original.read_bytes() == before
    assert store.resolve_card("A different recipe") is None
    store.save_generated("Synthetic exact recipe", base64.b64encode(before).decode(), approved=False)
    assert store.resolve_card("Synthetic exact recipe") is None


def test_card_endpoint_dispatches_only_after_visibility_and_rejects_unknown_variant(tmp_path, monkeypatch):
    from tools import roxy_home_service as service

    selected = tmp_path / "exact.webp"
    selected.write_bytes(b"synthetic preview")
    calls = []

    class Store:
        def resolve_card(self, title):
            calls.append(("card", title))
            return selected, {"media_type": "image/webp"}

        def resolve(self, title):
            calls.append(("full", title))
            return selected, {"media_type": "image/png"}

    monkeypatch.setattr(service, "_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "_recipe_photo_store", lambda: Store())
    monkeypatch.setattr(service, "_visible_photo_recipe", lambda *_args: ({"title": "Exact"}, None))
    request = Request({"type": "http", "method": "GET", "path": "/v1/home-food/recipe-photo", "headers": []})
    assert service.recipe_photo(" Exact ", request, variant="card").media_type == "image/webp"
    assert service.recipe_photo("Exact", request, variant="full").media_type == "image/png"
    assert calls == [("card", "Exact"), ("full", "Exact")]
    with pytest.raises(HTTPException) as invalid:
        service.recipe_photo("Exact", request, variant="arbitrary")
    assert invalid.value.status_code == 422
    monkeypatch.setattr(service, "_visible_photo_recipe", lambda *_args: (None, None))
    with pytest.raises(HTTPException) as missing:
        service.recipe_photo("Private recipe", request, variant="card")
    assert missing.value.status_code == 404
    assert len(calls) == 2, "Hidden recipes must not resolve a cached thumbnail"
