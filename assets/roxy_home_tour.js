/* Home's member-bound welcome and official, fixed-script narration. */
((global) => {
  'use strict';
  let context = null, mounted = null, latest = null, player = null;
  const el = (tag, text, cls) => { const n = document.createElement(tag); if(text != null)n.textContent=text; if(cls)n.className=cls; return n; };
  const button = (text, fn, cls='rht-button') => {const n=el('button',text,cls); n.type='button'; n.addEventListener('click',fn);return n;};
  const icon = name => { const n=el('span',name,'material-symbols-rounded');n.setAttribute('aria-hidden','true');return n; };
  const valid = owner => Boolean(owner && context===owner && owner.isCurrent() && !document.hidden);
  function bind(next) {
    global.RoxyHomeLiving?.bind(next);
    global.RoxyHomeWorld?.bind(next);
    if (!next || context?.identity!==next.identity || context?.version!==next.version) { close(); stop(); latest=null; }
    if(context&&next&&context.identity===next.identity&&context.version===next.version){Object.assign(context,next);return;}
    context=next;
  }
  async function request(owner, path, options={}) {
    if(!valid(owner))throw new Error('Tu sesión cambió. Vuelve a abrir la guía.');
    const response=await fetch(path,{credentials:'same-origin',cache:'no-store',...options,headers:{'Content-Type':'application/json','X-Roxy-Member-Id':owner.identity,'X-Roxy-Session-Version':String(owner.version),...(options.headers||{})}});
    if(!valid(owner))throw new Error('Tu sesión cambió. Vuelve a abrir la guía.');
    if(!response.ok){let detail;try{detail=(await response.json()).detail}catch(_){};throw new Error(typeof detail==='string'?detail:detail?.message||'No pudimos abrir esta guía. Reintenta.');}
    return response;
  }
  function stop() {
    if(!player)return;
    const prior=player;player=null;clearTimeout(prior.timer);prior.controller.abort();
    if(prior.audio){prior.audio.pause();prior.audio.removeAttribute('src');prior.audio.load();prior.audio.remove();}
    if(prior.url)URL.revokeObjectURL(prior.url);
    prior.status?.('paused','Voz oficial pausada');
  }
  async function speak(chapter, status=()=>{}, host=null) {
    global.RoxyHomeWorld?.stop();
    stop();const owner=context;
    owner?.beforeMedia?.();
    if(!valid(owner)){status('error','Inicia sesión para escuchar la voz oficial.');return;}
    const task={controller:new AbortController(),status,timer:null,audio:null,url:null};player=task;
    const current=()=>player===task&&valid(owner);
    const fail=message=>{if(player!==task)return;stop();status('error',message);};
    task.timer=setTimeout(()=>fail('La voz tardó demasiado. Pulsa Escuchar para reintentar.'),35000);
    status('loading','Preparando la voz oficial de Roxy…');
    try{
      const response=await request(owner,'/v1/home-tour/speech',{method:'POST',signal:task.controller.signal,body:JSON.stringify({chapter})});
      const blob=await response.blob();if(!current())return;
      if(blob.type!=='audio/mpeg'||blob.size<1024||blob.size>10*1024*1024)throw new Error('No llegó un audio válido. Reintenta la voz oficial.');
      task.url=URL.createObjectURL(blob);const audio=el('audio',null,'rht-audio');task.audio=audio;audio.controls=true;audio.preload='auto';audio.src=task.url;
      audio.setAttribute('aria-label','Voz oficial de Roxy');audio.setAttribute('playsinline','');
      (host||mounted?.audioHost||document.body).append(audio);
      if(!host&&!mounted)audio.hidden=true;
      audio.addEventListener('playing',()=>{if(!current()){stop();return;}clearTimeout(task.timer);task.timer=setTimeout(()=>fail('La lectura se detuvo. Puedes volver a escucharla.'),180000);status('playing','Habla Roxy · voz oficial');});
      audio.addEventListener('pause',()=>{if(current()&&!audio.ended)status('paused','Voz oficial pausada');});
      audio.addEventListener('ended',()=>{if(current()){stop();status('ended','Capítulo leído · continúa cuando quieras');}});
      audio.addEventListener('error',()=>fail('No se pudo reproducir la voz oficial. Reintenta.'));
      try{await audio.play();}catch(error){if(!current())return;if(error.name==='NotAllowedError'){clearTimeout(task.timer);if(audio.hidden){fail('Pulsa Escuchar para activar la voz oficial.');}else{status('ready','Toca reproducir en el audio para escuchar a Roxy.');}}else throw error;}
    }catch(error){if(player===task){stop();status('error',error.name==='AbortError'?'La voz se interrumpió. Puedes reintentar.':error.message);}}
  }
  function close(){if(!mounted)return;const old=mounted;mounted=null;old.controller.abort();stop();old.dialog.close();old.dialog.remove();if(old.focus?.isConnected)old.focus.focus({preventScroll:true});}
  async function open(chapter='welcome',{automatic=false,legacy=false}={}){
    if(global.RoxyHomeWorld&&!legacy)return global.RoxyHomeWorld.open(chapter,{automatic});
    const owner=context;if(!valid(owner))return;
    if(mounted){if(mounted.data){const idx=mounted.data.chapters.findIndex(row=>row.id===chapter);if(idx>=0){mounted.index=idx;draw(mounted);}}return;}
    const dialog=el('dialog',null,'rht-dialog');dialog.setAttribute('aria-label','Conoce Roxy Home');
    const state={dialog,owner,controller:new AbortController(),data:null,index:0,voice:false,busy:false,error:'',focus:document.activeElement,audioHost:null,automatic};mounted=state;
    dialog.addEventListener('cancel',()=>close());document.body.append(dialog);dialog.append(el('p','Preparando tu recorrido…','rht-loading'),button('Cerrar',close));dialog.showModal();
    const timer=setTimeout(()=>state.controller.abort(),12000);
    try{
      const data=await (await request(owner,'/v1/home-tour',{signal:state.controller.signal})).json();
      if(mounted!==state||!valid(owner))return;
      if(data.member_id!==owner.identity||data.version!==1||!Array.isArray(data.chapters)||data.chapters.length!==13)throw new Error('Actualiza Home para abrir el recorrido completo.');
      latest=data;state.data=data;const target=automatic&&data.progress&&!data.progress.completed?data.progress.chapter:chapter;
      state.index=Math.max(0,data.chapters.findIndex(row=>row.id===target));draw(state);
    }catch(error){if(mounted!==state)return;dialog.replaceChildren(el('h2','Volvamos a intentarlo'),el('p',error.name==='AbortError'?'El recorrido tardó demasiado en cargar.':error.message),button('Reintentar',()=>{close();void open(chapter,{automatic});}),button('Entrar a Home',close));}
    finally{clearTimeout(timer)}
  }
  async function save(state, completed){
    if(mounted!==state||!valid(state.owner)||state.busy)return false;
    state.busy=true;state.error='';const controls=state.dialog.querySelectorAll('button');controls.forEach(b=>b.disabled=true);
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
    try{
      const result=await (await request(state.owner,'/v1/home-tour',{method:'PUT',signal:controller.signal,body:JSON.stringify({expected_revision:state.data.revision,progress:{version:1,chapter:state.data.chapters[state.index].id,completed:completed||state.data.progress?.completed===true}})})).json();
      if(mounted!==state||!valid(state.owner))return false;
      state.data={...state.data,...result};latest=state.data;if(completed)state.owner.onCompleted?.();return true;
    }catch(error){if(mounted===state){state.error=error.name==='AbortError'?'No pudimos confirmar el guardado. Cierra y vuelve a abrir para comprobarlo.':error.message;}return false;}
    finally{clearTimeout(timer);state.busy=false;if(mounted===state){controls.forEach(b=>b.disabled=false);const error=state.dialog.querySelector('.rht-error');if(error){error.textContent=state.error;error.hidden=!state.error;}}}
  }
  function go(state,index){if(state.busy||mounted!==state)return;state.index=index;draw(state);void save(state,false);}
  async function enter(state, action){if(!await save(state,true))return;const owner=state.owner;close();if(valid(owner))owner.navigate(action);}
  function draw(state){
    if(mounted!==state||!valid(state.owner))return;stop();
    const row=state.data.chapters[state.index];state.dialog.replaceChildren();
    const header=el('header',null,'rht-header');const brand=el('strong','Roxy Home');const count=el('span',`${String(state.index+1).padStart(2,'0')} / ${state.data.chapters.length}`,'rht-count');
    header.append(brand,count,button('Entrar a Home',()=>void enter(state,'today'),'rht-exit'));state.dialog.append(header);
    const layout=el('div',null,'rht-layout'),visual=el('div',null,'rht-visual');
    const photo=el('img');photo.src=row.image;photo.alt='';visual.append(photo);
    let film=null;let paused=Boolean(global.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
    visual.classList.toggle('rht-motion-paused',paused);
    if(row.video){film=el('video');film.muted=true;film.loop=true;film.playsInline=true;film.preload='metadata';film.src=row.video;film.setAttribute('aria-label','Escena animada de Roxy');visual.append(film);if(!paused)void film.play().catch(()=>{});}
    const motion=button(paused?'Animar escena':'Pausar escena',()=>{paused=!paused;visual.classList.toggle('rht-motion-paused',paused);if(film){if(paused)film.pause();else void film.play().catch(()=>{});}motion.textContent=paused?'Animar escena':'Pausar escena';},'rht-motion');visual.append(motion);
    const badge=el('div',null,'rht-visual-label');badge.append(icon(row.icon),el('span',row.subtitle));visual.append(badge);layout.append(visual);
    const content=el('section',null,'rht-content');const eyebrow=el('p',state.index===0?'BIENVENIDA A TU HOME':'DESCUBRE TU HOME','rht-eyebrow');const title=el('h1',row.title);title.tabIndex=-1;
    content.append(eyebrow,title,el('p',row.speech,'rht-narration'));
    const audioBar=el('div',null,'rht-voicebar');const status=el('span','La voz se activa cuando tú quieras.','rht-voice-status');status.setAttribute('role','status');const listen=button('Escuchar a Roxy',()=>{if(player){state.voice=false;stop();return;}state.voice=true;play();},'rht-listen');audioBar.append(listen,status);content.append(audioBar);state.audioHost=el('div',null,'rht-audio-host');content.append(state.audioHost);
    function play(){void speak(row.id,(mode,text)=>{if(mounted!==state||!listen.isConnected)return;if(mode==='error')state.voice=false;status.textContent=text;listen.textContent=['loading','playing','ready'].includes(mode)?'Pausar voz':'Escuchar a Roxy';state.dialog.classList.toggle('rht-speaking',mode==='playing');},state.audioHost);}
    const steps=el('ol',null,'rht-steps');row.steps.forEach(text=>steps.append(el('li',text)));content.append(steps);
    const error=el('p',state.error,'rht-error');error.hidden=!state.error;error.setAttribute('role','alert');content.append(error);
    const actions=el('div',null,'rht-actions');actions.append(button(row.action,()=>void enter(state,row.id==='welcome'?'today':row.id==='appearance'?'appearance':row.id==='location'?'family':row.id==='calendar'?'calendar-new':row.panel),'rht-button rht-primary'));
    if(state.index<state.data.chapters.length-1)actions.append(button('Siguiente capítulo',()=>go(state,state.index+1),'rht-button rht-secondary'));
    else actions.append(button('Terminar recorrido',()=>void enter(state,'today'),'rht-button rht-secondary'));
    content.append(actions);layout.append(content);state.dialog.append(layout);
    const nav=el('nav',null,'rht-chapters');nav.setAttribute('aria-label','Capítulos de Roxy Home');state.data.chapters.forEach((item,index)=>{const jump=button('',()=>go(state,index),'rht-chapter');jump.append(icon(item.icon),el('span',item.id==='welcome'?'Bienvenida':item.id==='appearance'?'Mi Roxy':item.id==='today'?'Hoy':item.id==='recipes'?'Cocina':item.id==='shopping'?'Compra':item.id==='pantry'?'Despensa':item.id==='fitness'?'Ejercicio':item.id==='design'?'Renueva':item.id==='plants'?'Jardín':item.id==='pets'?'Mascotas':item.id==='family'?'Nexo':item.id==='location'?'Ubicación':'Calendario'));jump.setAttribute('aria-current',index===state.index?'step':'false');nav.append(jump);});state.dialog.append(nav);
    title.focus({preventScroll:true});state.dialog.scrollTop=0;if(state.voice)play();
  }
  const MODULES=[['recipes','Cocina','menu_book'],['shopping','Compra','shopping_cart'],['fitness','Ejercicio','exercise'],['design','Renueva','chair'],['plants','Jardín','potted_plant'],['pets','Mascotas','pets'],['family','Nexo','hub'],['calendar','Calendario','event']];
  function home(root){
    if(!root)return;root.replaceChildren();const intro=el('div',null,'rht-home-intro'),portrait=el('img');portrait.src='/assets/roxy_home_avatar.jpg';portrait.alt='Roxy';
    const copy=el('div');copy.append(el('p','TU CASA, A TU RITMO','rht-eyebrow'),el('h2','¿Qué hacemos hoy?'),el('p','Un hogar tiene muchas historias. Estoy aquí para acompañarte.'));
    intro.append(portrait,copy,button('Conoce Roxy Home',()=>void open('welcome'),'rht-button rht-primary'));root.append(intro);
    const modules=el('nav',null,'rht-home-modules');modules.setAttribute('aria-label','Todos los espacios de Home');MODULES.forEach(([key,label,symbol])=>{const item=button('',()=>{if(valid(context))context.navigate(key);},'rht-home-module');item.append(icon(symbol),el('span',label));modules.append(item);});root.append(modules);
  }
  document.addEventListener('visibilitychange',()=>{if(document.hidden){if(mounted)mounted.voice=false;stop();mounted?.dialog.querySelectorAll('video').forEach(video=>video.pause());}});
  global.RoxyHomeTour={bind,open,close,stop,speak,home,isPlaying:()=>Boolean(player)};
})(window);
