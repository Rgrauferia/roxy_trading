/* The house is a member-bound scene controller. Decisions are saved only at review. */
((global) => {
  'use strict';
  let context = null, state = null;
  const node = (tag, text, cls) => {const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
  const btn = (text, action, cls='rhw-choice') => {const n=node('button',text,cls);n.type='button';n.addEventListener('click',action);return n;};
  const symbol = value => {const n=node('span',value,'material-symbols-rounded');n.setAttribute('aria-hidden','true');return n;};
  const clone = value => JSON.parse(JSON.stringify(value));
  const current = s => state===s && context===s.owner && s.owner.isCurrent();
  const THEMES=[['classic','Bosque','#234c3b'],['olive','Oliva','#79845c'],['coastal','Mar','#638f9f'],['terracotta','Tierra','#bc8064']];
  const VOICES=[['brief','Al grano','Lo esencial, con claridad.'],['close','Con cercanía','Una compañía cálida.'],['explanatory','Paso a paso','Cada detalle, a tu ritmo.'],['balanced','Un poco de todo','Según lo que necesites.']];
  const AVATARS=[['host','Anfitriona','/assets/roxy_home/world/roxy-host.png'],['home','En casa','/assets/roxy_home_avatar.jpg'],['professional','Profesional','/assets/roxy_avatar_icon.jpg'],['monogram','Símbolo','/assets/roxy_home/avatars/monogram.svg']];
  const ROOMS=[['recipes','Cocina','menu_book'],['shopping','Compra','shopping_bag'],['pantry','Despensa','kitchen'],['fitness','Mi movimiento','exercise'],['design','Renueva','chair'],['plants','Jardín','potted_plant'],['pets','Mascotas','pets'],['family','Nexo','hub'],['location','Ubicación','location_on'],['calendar','Calendario','event'],['today','Mi día','today']];
  const SETUP=['name','theme','voice','avatar','review'];
  function bind(next){
    if(!next || context?.identity!==next.identity || context?.version!==next.version){close();context=next;return;}
    if(context)Object.assign(context,next);else context=next;
  }
  function stop(s=state){
    if(!s)return;s.audioSequence++;s.speechRequest?.abort();s.speechRequest=null;clearTimeout(s.audioTimer);
    if(s.source){s.source.onended=null;try{s.source.stop();}catch(_){}s.source.disconnect();s.source=null;}
    if(s.film){s.film.pause();s.film.removeAttribute('src');s.film.load();s.film.remove();s.film=null;}
    s.dialog.classList.remove('rhw-speaking');
  }
  function close(){
    const s=state;if(!s)return;state=null;stop(s);s.controller.abort();s.form?.dispose?.();s.nested?.close?.();
    s.audioContext?.close().catch(()=>{});s.buffers.clear();s.dialog.close();s.dialog.remove();
    document.body.classList.remove('rhw-active');s.focus?.isConnected&&s.focus.focus({preventScroll:true});
  }
  async function request(s,path,options={}){
    if(!current(s))throw new Error('Tu sesión cambió. Vuelve a entrar.');
    const controller=new AbortController();const abort=()=>controller.abort();
    s.controller.signal.addEventListener('abort',abort,{once:true});options.signal?.addEventListener('abort',abort,{once:true});
    const timer=setTimeout(abort,options.method==='POST'?35000:12000);
    try{
      const response=await fetch(path,{...options,signal:controller.signal,credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','X-Roxy-Member-Id':s.owner.identity,'X-Roxy-Session-Version':String(s.owner.version)}});
      if(!current(s))throw new Error('Tu sesión cambió. Vuelve a entrar.');
      if(!response.ok){let detail;try{detail=(await response.json()).detail;}catch(_){}throw new Error(typeof detail==='string'?detail:detail?.message||'No pudimos completar este paso. Reintenta.');}
      // Keep the deadline and cancellation attached until the body is consumed.
      if(path.endsWith('/speech')){const blob=await response.blob();return {blob:async()=>blob};}
      const data=await response.json();return {json:async()=>data};
    }finally{clearTimeout(timer);s.controller.signal.removeEventListener('abort',abort);options.signal?.removeEventListener('abort',abort);}
  }
  function message(s,text,error=false){if(!current(s))return;s.status.textContent=text;s.status.classList.toggle('rhw-error',error);}
  function unlock(s){
    const Audio=global.AudioContext||global.webkitAudioContext;
    if(!Audio){s.muted=true;message(s,'Este navegador no permite la voz continua. Puedes seguir con los textos.',true);return;}
    if(!s.audioContext){s.audioContext=new Audio();s.gain=s.audioContext.createGain();s.gain.connect(s.audioContext.destination);}
    return s.audioContext.resume();
  }
  async function speak(s,key){
    stop(s);s.spokenKey=key;
    if(s.caption&&s.data.world.speech[key])s.caption.textContent=s.data.world.speech[key];
    if(!current(s)||s.muted||document.hidden)return;
    const sequence=s.audioSequence,alive=()=>current(s)&&sequence===s.audioSequence&&!s.muted&&!document.hidden;
    if(!s.audioContext||s.audioContext.state!=='running'){message(s,'Pulsa Activar sonido para continuar con mi voz.');return;}
    s.owner.beforeMedia?.();message(s,'Roxy prepara su voz…');
    const controller=new AbortController();s.speechRequest=controller;
    s.audioTimer=setTimeout(()=>{if(alive()){stop(s);message(s,'La voz tardó demasiado. Pulsa Repetir para reintentar.',true);}},35000);
    try{
      let buffer=s.buffers.get(key);
      if(!buffer){
        const response=await request(s,'/v1/home-tour/speech',{method:'POST',signal:controller.signal,body:JSON.stringify({chapter:key})});
        const blob=await response.blob();if(!alive())return;
        if(blob.type!=='audio/mpeg'||blob.size<1024||blob.size>10*1024*1024)throw new Error('El audio no llegó completo. Puedes reintentarlo.');
        buffer=await s.audioContext.decodeAudioData(await blob.arrayBuffer());if(!alive())return;
        if(s.buffers.size>=20)s.buffers.delete(s.buffers.keys().next().value);s.buffers.set(key,buffer);
      }
      if(!alive())return;
      const source=s.audioContext.createBufferSource();source.buffer=buffer;source.connect(s.gain);s.source=source;
      source.onended=()=>{if(alive()){s.source=null;source.disconnect();s.dialog.classList.remove('rhw-speaking');message(s,'Te escucho: elige lo que prefieras.');}};
      clearTimeout(s.audioTimer);source.start();s.dialog.classList.add('rhw-speaking');message(s,'Roxy · voz original');
      // Only reviewed, voice-matched films may be placed in the server manifest.
      const film=s.data.world.films?.[key];
      if(film){const video=node('video');video.src=film;video.muted=true;video.playsInline=true;video.setAttribute('aria-label','Roxy hablando');s.backdrop.append(video);s.film=video;void video.play().catch(()=>video.remove());}
    }catch(error){if(alive()){clearTimeout(s.audioTimer);message(s,error.name==='AbortError'?'La voz tardó demasiado. Puedes repetirla o seguir eligiendo.':error.message,true);}}
  }
  function labelFor(rows,key){return rows.find(row=>row[0]===key)?.[1]||key;}
  function chapterFor(scene){return SETUP.includes(scene)?'appearance':scene==='map'?'welcome':scene;}
  function progress(s,completed=false){
    const chapter=chapterFor(s.scene);
    s.saveQueue=s.saveQueue.then(async()=>{
      if(!current(s)||s.progressConflict)return;
      try{const result=await(await request(s,'/v1/home-tour',{method:'PUT',body:JSON.stringify({expected_revision:s.data.revision,progress:{version:1,chapter,completed:completed||Boolean(s.data.progress?.completed)}})})).json();if(current(s)){Object.assign(s.data,result);if(completed)s.owner.onCompleted?.();}}
      catch(error){if(current(s)){s.progressConflict=true;message(s,error.message,true);}}
    });return s.saveQueue;
  }
  async function open(chapter='welcome',{automatic=false}={}){
    if(!context?.isCurrent()||document.hidden)return;
    if(state){go(state,chapter==='welcome'?'map':chapter==='appearance'?'name':chapter);return;}
    const dialog=node('dialog',null,'rhw-dialog');dialog.setAttribute('aria-label','Tu casa con Roxy');
    const s={owner:context,dialog,focus:document.activeElement,controller:new AbortController(),audioSequence:0,buffers:new Map(),source:null,muted:false,started:false,scene:chapter==='welcome'||chapter==='appearance'?'name':chapter,saveQueue:Promise.resolve(),busy:false,progressConflict:false};state=s;
    dialog.addEventListener('cancel',event=>{event.preventDefault();close();});document.body.append(dialog);document.body.classList.add('rhw-active');dialog.showModal();
    dialog.append(node('p','Abriendo tu casa…','rhw-loading'),btn('Cerrar',close));
    try{
      s.data=await(await request(s,'/v1/home-tour')).json();if(!current(s))return;
      if(s.data.member_id!==s.owner.identity||s.data.world?.version!==1||!s.data.personalization)throw new Error('Actualiza Home para entrar en tu casa.');
      if(automatic&&!s.data.progress?.completed&&ROOMS.some(row=>row[0]===s.data.progress?.chapter))s.scene=s.data.progress.chapter;
      s.original=clone(s.data.personalization);s.draft=clone(s.original);s.reduced=Boolean(global.matchMedia?.('(prefers-reduced-motion: reduce)').matches);draw(s);
    }catch(error){if(current(s))dialog.replaceChildren(node('h1','Volvamos a intentarlo'),node('p',error.message),btn('Reintentar',()=>{close();void open(chapter);}),btn('Entrar a Home',close));}
  }
  function go(s,scene){if(!current(s)||s.busy)return;stop(s);s.form?.dispose?.();s.form=null;s.scene=scene;s.inline=false;delete s.dialog.dataset.roomStyle;draw(s);if(s.started)void progress(s);}
  function imageFor(s){
    if(['recipes','shopping','pantry'].includes(s.scene))return s.data.world.kitchen_image;
    if(s.scene==='design')return '/assets/roxy_home/renueva-living-room-hero.webp';
    if(s.scene==='plants')return '/assets/roxy_home/home-hero-plant.png';
    if(s.scene==='pets')return '/assets/roxy_home/pet-onboarding-hero.png';
    if(s.scene==='fitness')return '/assets/roxy_home/fitness/roxy-fitness-welcome.jpg';
    return s.data.world.entry_image;
  }
  function draw(s){
    if(!current(s))return;stop(s);s.dialog.replaceChildren();s.dialog.dataset.scene=s.scene;s.dialog.dataset.theme=s.draft.preferences.theme;s.dialog.classList.toggle('rhw-still',s.reduced);
    s.backdrop=node('div',null,'rhw-backdrop');const image=node('img');image.src=imageFor(s);image.alt='';s.backdrop.append(image);s.dialog.append(s.backdrop,node('div',null,'rhw-shade'));
    const header=node('header',null,'rhw-header');const brand=node('div',null,'rhw-brand');brand.append(node('span','R','rhw-mark'),node('span','ROXY HOME'));
    const controls=node('div',null,'rhw-controls');
    s.sound=btn(s.muted?'Activar sonido':'Silenciar',()=>{s.muted=!s.muted;s.sound.textContent=s.muted?'Activar sonido':'Silenciar';if(s.muted){stop(s);message(s,'Puedes seguir a tu ritmo, sin sonido.');}else{void unlock(s)?.then(()=>speak(s,s.spokenKey||`world-${s.scene}`));}},'rhw-icon-button');
    if(s.started){controls.append(btn('Repetir',()=>{s.muted=false;s.sound.textContent='Silenciar';void unlock(s)?.then(()=>speak(s,s.spokenKey||`world-${s.scene}`));},'rhw-icon-button'),s.sound,btn('Mi casa',()=>go(s,'map'),'rhw-icon-button'));}
    controls.append(btn('Salir',close,'rhw-icon-button'));header.append(brand,controls);s.dialog.append(header);
    const main=node('main',null,'rhw-main');s.main=main;s.dialog.append(main);
    s.status=node('p','','rhw-status');s.status.setAttribute('role','status');s.dialog.append(s.status);
    if(!s.started){
      main.classList.add('rhw-arrival');main.append(node('p','TU HISTORIA EMPIEZA AQUÍ','rhw-eyebrow'),node('h1','Entra.\nEstás en casa.'),node('p','Soy Roxy. Vamos a crear un hogar que se parezca a ti.','rhw-lead'));
      const start=btn('Entrar con Roxy  ↗',()=>{s.started=true;const ready=unlock(s);s.starting=true;draw(s);s.starting=false;void ready?.then(()=>speak(s,`world-${s.scene}`));},'rhw-primary');
      main.append(start,btn('Entrar sin sonido',()=>{s.started=true;s.muted=true;draw(s);},'rhw-text-button'),node('p','Elige, explora y configura tu Home durante el recorrido.','rhw-small'));return;
    }
    const phase=SETUP.indexOf(s.scene),crumb=node('p',phase>=0?`CONOCIÉNDONOS · ${phase+1} / ${SETUP.length}`:s.scene==='map'?'CADA RINCÓN, UNA HISTORIA':`EN CASA · ${labelFor(ROOMS,s.scene)}`,'rhw-eyebrow');main.append(crumb);
    if(phase>=0)drawSetup(s,main);else if(s.scene==='map')drawMap(s,main);else drawRoom(s,main);
    const footer=node('footer',null,'rhw-footer');const portrait=node('img');portrait.src='/assets/roxy_home_avatar.jpg';portrait.alt='Roxy';
    s.caption=node('p',s.data.world.speech[`world-${s.scene}`]||'Vamos paso a paso.','rhw-caption');footer.append(portrait,s.caption);s.dialog.append(footer);
    if(phase>0)main.append(btn('← Volver',()=>go(s,SETUP[phase-1]),'rhw-text-button'));
    main.querySelector('h1')?.setAttribute('tabindex','-1');main.querySelector('h1')?.focus({preventScroll:true});
    if(!s.muted&&!s.starting)void speak(s,`world-${s.scene}`);
  }
  function options(s,main,rows,key,next){
    const group=node('div',null,rows===AVATARS?'rhw-options rhw-avatars':'rhw-options');group.setAttribute('role','group');group.setAttribute('aria-label',main.querySelector('h1')?.textContent||'Opciones');
    rows.forEach(([value,title,detail])=>{
      const b=btn('',()=>{s.draft.preferences[key]=value;s.dialog.dataset.theme=s.draft.preferences.theme;group.querySelectorAll('button').forEach(item=>item.setAttribute('aria-pressed',String(item===b)));});
      b.setAttribute('aria-pressed',String(s.draft.preferences[key]===value));
      if(rows===THEMES){const swatch=node('span',null,'rhw-swatch');swatch.style.background=detail;b.append(swatch);}
      if(rows===AVATARS){const avatar=node('img');avatar.src=detail;avatar.alt='';b.append(avatar);}
      b.append(node('strong',title));if(rows===VOICES)b.append(node('small',detail));group.append(b);
    });main.append(group,btn('Así me gusta  →',()=>go(s,next),'rhw-primary'));
  }
  function drawSetup(s,main){
    if(s.scene==='name'){
      main.append(node('h1','¿Cómo te\nllamo?'),node('p','El nombre que te haga sentir en casa.','rhw-lead'));
      const form=node('form',null,'rhw-name-form'),label=node('label','Tu nombre'),input=node('input');input.name='display_name';input.value=s.draft.display_name;input.required=true;input.maxLength=80;input.autocomplete='given-name';label.append(input);form.append(label);
      const next=node('button','Me gusta, continuemos  →','rhw-primary');next.type='submit';form.append(next);form.addEventListener('submit',event=>{event.preventDefault();const name=input.value.trim();if(!name){input.focus();return;}s.draft.display_name=name;go(s,'theme');});main.append(form,btn('Explorar primero',()=>go(s,'map'),'rhw-text-button'));
    }else if(s.scene==='theme'){main.append(node('h1','Dale tu color\na la casa.'),node('p','Prueba un ambiente. Tú eliges cómo se siente Home.','rhw-lead'));options(s,main,THEMES,'theme','voice');}
    else if(s.scene==='voice'){main.append(node('h1','A tu manera.'),node('p','¿Cómo quieres que te acompañe?','rhw-lead'));options(s,main,VOICES,'response_style','avatar');}
    else if(s.scene==='avatar'){main.append(node('h1','Siempre Roxy.\nMás tuya.'),node('p','Elige mi imagen en los accesos de Home.','rhw-lead'));options(s,main,AVATARS,'avatar','review');}
    else{
      main.append(node('h1',`${s.draft.display_name},\neste es tu Home.`));const summary=node('dl',null,'rhw-summary');
      [['Te llamaré',s.draft.display_name],['Ambiente',labelFor(THEMES,s.draft.preferences.theme)],['Te acompaño',labelFor(VOICES,s.draft.preferences.response_style)],['Mi imagen',labelFor(AVATARS,s.draft.preferences.avatar)]].forEach(([key,value])=>{const row=node('div');row.append(node('dt',key),node('dd',value));summary.append(row);});main.append(summary,node('p','Guardar aplica estas elecciones a tu perfil. Podrás cambiarlas desde Mi Roxy.','rhw-small'));
      main.append(btn('Guardar y recorrer mi casa  →',()=>void saveChoices(s),'rhw-primary'),btn('Explorar sin guardar',()=>{s.draft=clone(s.original);go(s,'map');},'rhw-text-button'));
    }
  }
  async function saveChoices(s){
    if(!current(s)||s.busy)return;s.busy=true;stop(s);s.main.querySelectorAll('button').forEach(n=>n.disabled=true);message(s,'Guardando tu Home…');
    try{
      const result=await(await request(s,'/v1/home-tour/personalization',{method:'PUT',body:JSON.stringify({...s.draft,expected:s.original})})).json();
      if(!current(s))return;if(result.member_id!==s.owner.identity)throw new Error('Tu sesión cambió. Vuelve a abrir Home.');
      s.original=clone(result.personalization);s.draft=clone(s.original);s.owner.onPersonalized?.(result.personalization);s.busy=false;go(s,'map');message(s,'Tu personalización quedó guardada.');
    }catch(error){if(current(s)){s.busy=false;s.main.querySelectorAll('button').forEach(n=>n.disabled=false);message(s,error.message,true);}}
  }
  function drawMap(s,main){
    main.append(node('h1','¿Dónde empezamos?'),node('p','Cada espacio tiene algo para ti. Elige una puerta.','rhw-lead'));
    const rooms=node('nav',null,'rhw-rooms');rooms.setAttribute('aria-label','Habitaciones de tu casa');
    ROOMS.forEach(([key,label,icon])=>{const b=btn('',()=>go(s,key),'rhw-room');b.append(symbol(icon),node('span',label),node('span','↗'));rooms.append(b);});main.append(rooms,btn('Afinar mi Roxy',()=>go(s,'name'),'rhw-text-button'),btn('Entrar en la aplicación',async()=>{await progress(s,true);if(current(s)&&!s.progressConflict){close();s.owner.navigate('today');}},'rhw-primary'));
  }
  function demonstration(s,main,kind){
    const surface=node('div',null,'rhw-demonstration');surface.append(node('small','PRUEBA EN LA ESCENA · NO CAMBIA TUS DATOS'));
    if(kind==='shopping'||kind==='pantry'){
      const list=node('div',null,'rhw-example-list');surface.append(list);
      ['Tomates','Pasta','Aceite'].forEach(name=>surface.append(btn(`+ ${name}`,()=>{const row=node('span',`✓ ${name} · 1 unidad`);list.append(row);},'rhw-chip')));
    }else if(kind==='calendar'){
      const days=node('div',null,'rhw-example-week');['L','M','X','J','V'].forEach(day=>{const b=btn(day,()=>{days.querySelectorAll('button').forEach(n=>n.classList.remove('selected'));b.classList.add('selected');b.replaceChildren(node('span',day),node('small','Mi actividad'));},'rhw-example-day');days.append(b);});surface.append(days);
    }else if(kind==='design'){
      [['natural','Natural'],['warm','Cálido'],['fresh','Fresco']].forEach(([key,title])=>surface.append(btn(title,()=>{s.dialog.dataset.roomStyle=key;surface.querySelectorAll('button').forEach(n=>n.setAttribute('aria-pressed',String(n.textContent===title)));},'rhw-chip')));
    }else return;main.append(surface);
  }
  function drawRoom(s,main){
    const row=s.data.chapters.find(item=>item.id===s.scene);if(!row){go(s,'map');return;}
    const titles={recipes:'Aquí empiezan\ntus sabores.',shopping:'Lo que hace\nfalta en casa.',pantry:'Abre la\ndespensa.',fitness:'Un momento\npara ti.',design:'Tu espacio.\nTu siguiente idea.',plants:'La vida\ncrece aquí.',pets:'También es\nsu casa.',family:'Los tuyos,\nmás cerca.',location:'Tú decides\ncuándo compartir.',calendar:'Hazle espacio\na lo importante.',today:'¿Qué hacemos\nhoy?'};
    main.append(node('h1',titles[s.scene]||row.title));
    const prompts={recipes:'Vamos a conocerte mientras estás en la cocina.',shopping:'Prueba cómo se forma una lista y prepara la tuya.',pantry:'Lo que ya tienes también inspira lo que cocinas.',fitness:'Explora fuerza suave, equilibrio y flexibilidad.',design:'Prueba un ambiente. Después trabajamos con tu habitación.',plants:'Una foto, un nombre y su rincón favorito.',pets:'Una ficha propia para cada compañero.',family:'Conexiones y permisos, elegidos por cada persona.',location:'El permiso se activa en Nexo, cuando tú lo decidas.',calendar:'Elige una fecha, prepara el evento y revisa antes de guardar.',today:'Tus próximos eventos y cuidados, reunidos.'};main.append(node('p',prompts[s.scene],'rhw-lead'));
    demonstration(s,main,s.scene);
    if(s.scene==='recipes')main.append(btn('Abrir el cuaderno · mis gustos',()=>void recipeForm(s),'rhw-primary'),btn('Elegir una receta',()=>leaveFor(s,'recipes'),'rhw-text-button'));
    else{
      const actions={plants:['Conocer a mi planta','plant-new'],pets:['Añadir a mi compañero','pet-new'],design:['Trabajar con mi habitación','design-new'],calendar:['Crear mi evento','calendar-new'],shopping:['Abrir mi lista real','shopping'],pantry:['Abrir mi despensa','pantry'],fitness:['Elegir una guía','fitness'],family:['Revisar mi Nexo','family'],location:['Ver controles de ubicación','family'],today:['Abrir mi día','today']};
      const [label,destination]=actions[s.scene]||[row.action,row.panel];main.append(btn(label,()=>destination.endsWith('-new')?nestedForm(s,destination):leaveFor(s,destination),'rhw-primary'));
    }
    const next=ROOMS[(ROOMS.findIndex(item=>item[0]===s.scene)+1)%ROOMS.length];main.append(btn(`Vamos a ${next[1]}  →`,()=>go(s,next[0]),'rhw-text-button'));
  }
  async function recipeForm(s){
    if(!current(s)||s.busy)return;stop(s);s.inline=true;s.main.replaceChildren(node('h1','Cuéntame tus sabores.'));const host=node('div',null,'rhw-form-host');s.main.append(host);s.main.append(btn('Volver a la cocina',()=>go(s,'recipes'),'rhw-text-button'));message(s,'Abriendo tu cuaderno…');
    try{s.form=await s.owner.mountRecipe?.(host,{isCurrent:()=>current(s)&&s.inline,speak:key=>speak(s,key),stop:()=>stop(s),onSaved:()=>{if(current(s)){go(s,'recipes');message(s,'Tus gustos se guardaron en tu perfil privado.');}},onCancel:()=>go(s,'recipes')});if(current(s)&&s.inline){if(!s.form)throw new Error('No se pudo abrir tu cuaderno.');if(s.muted)message(s,'Tu cuaderno está abierto. Elige a tu ritmo.');}}
    catch(error){if(current(s))message(s,error.message,true);}
  }
  function nestedForm(s,destination){if(!current(s))return;stop(s);message(s,'Completa la ficha. Al cerrarla volverás a esta habitación.');s.nested=s.owner.openForm?.(destination,{isCurrent:()=>current(s),speak:key=>speak(s,key),repeat:key=>{if(!current(s))return;s.muted=false;s.sound.textContent='Silenciar';void unlock(s)?.then(()=>speak(s,key));},stop:()=>stop(s)});}
  async function leaveFor(s,destination){if(!current(s))return;await progress(s,true);if(current(s)&&!s.progressConflict){close();s.owner.navigate(destination);}}
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&state){stop(state);message(state,'La voz está pausada. Pulsa Repetir para continuar.');}});
  global.addEventListener('pagehide',close);
  global.RoxyHomeWorld={bind,open,close,stop:()=>stop(),isOpen:()=>Boolean(state)};
})(window);
