const CACHE='roxy-list-shell-v20';
const SHELL=['/home','/lista-manifest.json','/assets/roxy_list.css?v=20','/assets/roxy_list.js?v=20','/assets/roxy_avatar_icon.jpg','/assets/roxy_avatar_card.jpg','/assets/roxy_home/home-hero-plant.png','/assets/roxy_home/products/milk.png','/assets/roxy_home/products/eggs.png','/assets/roxy_home/products/rice.png','/assets/roxy_home/products/bread.png','/assets/roxy_home/products/bananas.png','/assets/roxy_home/products/chicken.png','/assets/roxy_home/products/cheese.png','/assets/roxy_home/products/tomato.png','/assets/roxy_home/products/avocado.png','/assets/roxy_home/products/coffee.png','/assets/roxy_home/products/oil.png','/assets/roxy_home/products/toilet-paper.png','/assets/roxy_home/products/water.png','/assets/roxy_home/products/detergent.png','/assets/roxy_home/products/soap.png','/assets/roxy_home/products/yeast.png','/assets/roxy_home/products/butter.png','/assets/roxy_home/products/cleaning-powder.png','/assets/roxy_home/products/paper-towels.png','/assets/roxy_home/products/pain-relief.png','/assets/roxy_home/products/salt.png','/assets/roxy_home/products/fabric-softener.png','/assets/roxy_home/products/vanilla.png'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=='GET'||url.pathname.startsWith('/v1/'))return;
  if(event.request.mode==='navigate'){
    event.respondWith(fetch(event.request).then(response=>{if(response.ok)caches.open(CACHE).then(cache=>cache.put(event.request,response.clone()));return response}).catch(()=>caches.match(event.request)));
    return;
  }
  event.respondWith(caches.match(event.request).then(cached=>cached||fetch(event.request).then(response=>{if(response.ok)caches.open(CACHE).then(cache=>cache.put(event.request,response.clone()));return response})));
});
