// Isolated visible fixture: never loads Maps, credentials, accounts or locations.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');
const html=fs.readFileSync(path.join(root,'assets/roxy_list.html'),'utf8');
const notice=html.match(/<aside id="familyMapLoadNotice".*?<\/aside>/)[0];
http.createServer((req,res)=>{
  res.setHeader('Cache-Control','no-store');
  if(req.url==='/style.css'||req.url==='/readiness.js'){
    res.setHeader('Content-Type',req.url==='/style.css'?'text/css':'text/javascript');
    res.end(fs.readFileSync(path.join(root,'assets',req.url==='/style.css'?'roxy_list.css':'roxy_home_map_readiness.js')));return;
  }
  res.setHeader('Content-Type','text/html; charset=utf-8');
  res.end(`<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nexo · prueba de mapa lento</title><link rel="stylesheet" href="/style.css"><style>body{padding:16px;font:15px system-ui}main{max-width:393px;margin:auto}.stage{height:560px;position:relative;background:#e7ece3;border-radius:25px}.stage>p{padding:18px}.controls{display:flex;gap:8px;margin:16px 0}h1{font-size:24px}</style><main><h1>Prueba aislada de mapa lento</h1><p>Datos sintéticos. No es un mapa real ni usa ubicaciones.</p><div class="controls"><button id="delay">Simular espera</button><button id="ready">Simular mapa listo</button></div><p id="state" role="status">Sin iniciar</p><div class="stage"><p>Área de mapa de prueba</p>${notice}</div></main><script src="/readiness.js"></script><script>
let handler=null,controller=null,retries=0;
const label=document.getElementById('state'),notice=document.getElementById('familyMapLoadNotice');
function start(){controller?.dispose();controller=RoxyMapReadiness.create({timeoutMs:1000,onState:state=>{notice.hidden=state.phase!=='delayed';label.textContent=state.phase==='ready'?'Mapa de prueba listo':state.phase==='delayed'?'Demora detectada sin reintento automático':'Esperando mapa de prueba'}});controller.attach({addListener(_name,fn){handler=fn;return{remove(){handler=null}}}})}
document.getElementById('delay').addEventListener('click',start);
document.getElementById('ready').addEventListener('click',()=>handler?.());
document.getElementById('familyMapRetry').addEventListener('click',()=>{retries++;start();label.textContent='Reintento manual '+retries+'; sin GPS ni cambios de ubicación'});
</script></html>`);
}).listen(8789,'127.0.0.1',()=>process.stdout.write('Map readiness QA: http://127.0.0.1:8789/\n'));
