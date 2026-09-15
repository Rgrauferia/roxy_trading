/* Everyday rooms. All objects navigate to the existing, authenticated tools. */
((global) => {
  'use strict';
  const rooms = {
    house: {name:'Sala',eyebrow:'TU CASA, A TU RITMO',title:'Qué gusto estar en casa.',line:'Un momento para ti. Un lugar para todo lo que quieres cuidar.',speech:'world-today',
      image:'/assets/roxy_home/world/living-room-205.png',
      objects:[['calendar','calendar_month','Calendario','Haz espacio para lo importante',12,39],['today','today','Mi día','Agenda, cuidados y plan semanal',45,71],['kitchen','arrow_forward','Ir a la cocina','¿Qué cocinamos hoy?',83,42]]},
    kitchen: {name:'Cocina',eyebrow:'SABORES QUE HACEN HOGAR',title:'Algo rico empieza aquí.',line:'Abre el recetario, mira qué tienes y cocinamos juntos.',speech:'recipes',
      image:'/assets/roxy_home/world/kitchen-room-205.png',
      objects:[['pantry','kitchen','Despensa','Lo que ya tienes en casa',11,40],['recipes','menu_book','Recetario','Elige y prepara con Roxy',59,56],['shopping','shopping_bag','Mi compra','Lo que hace falta',79,50]]},
    garden: {name:'Jardín',eyebrow:'PEQUEÑOS CUIDADOS, NUEVA VIDA',title:'Tu rincón para florecer.',line:'Conozcamos cada planta y acompañemos su crecimiento.',speech:'plants',image:'/assets/roxy_home/world/garden-room-206.png',
      objects:[['action:plant-new','potted_plant','Añadir una planta','Cuéntame dónde vive y cómo la cuidas',29,44],['plants','yard','Mis plantas','Fotos, cuidados y seguimiento',79,76],['action:calendar-new','event','Anotar un cuidado','Elige fecha y revisa antes de guardar',76,49]]},
    wellness: {name:'Ejercicio',eyebrow:'UN MOMENTO PARA TI',title:'Muévete a tu ritmo.',line:'Explora las guías, conoce cada movimiento y hazle espacio en tu día.',speech:'fitness',image:'/assets/roxy_home/world/fitness-room-206.png',
      objects:[['fitness','exercise','Explorar movimientos','Fuerza suave, equilibrio y flexibilidad',49,79],['action:calendar-new','calendar_month','Reservar mi momento','Elige cuándo quieres moverte',76,38],['guide:fitness','auto_stories','Roxy, guíame','Conoce cómo usar este espacio',60,57]]},
    companions: {name:'Mascotas',eyebrow:'ELLOS TAMBIÉN SON FAMILIA',title:'Un lugar para sus historias.',line:'Conoce a cada compañero y reúne sus cuidados en un mismo lugar.',speech:'pets',image:'/assets/roxy_home/world/pets-room-206.png',
      objects:[['action:pet-new','pets','Presentar mi mascota','Crea su ficha paso a paso',24,41],['pets','favorite','Mis compañeros','Perfiles, cuidados e historial',54,60],['shopping','shopping_bag','Lista de compra','Revisa lo que hace falta',81,43]]},
    atelier: {name:'Renueva',eyebrow:'IMAGINA LO QUE VIENE',title:'Hagamos espacio a tus ideas.',line:'Parte de tu casa real: tus fotos, lo que quieres conservar y lo que sueñas cambiar.',speech:'design',image:'/assets/roxy_home/world/living-room-205.png',
      objects:[['action:design-new','add_photo_alternate','Mi próximo espacio','Empieza un proyecto con tus fotos',23,42],['design','chair','Mis proyectos','Retoma tus habitaciones guardadas',52,62],['guide:design','auto_stories','Crear con Roxy','Conoce el proceso de Renueva',81,42]]},
    connection: {name:'Nexo',eyebrow:'CERCA DE QUIENES QUIERES',title:'Cada persona tiene su lugar.',line:'Tu hogar conectado, con la ubicación y la privacidad bajo tu control.',speech:'family',image:'/assets/roxy_home/world/living-room-205.png',
      objects:[['family','diversity_1','Abrir Nexo','Personas, lugares y mapa de tu hogar',52,63],['action:family-privacy','tune','Mi privacidad','Revisa tus opciones antes de compartir',24,43],['guide:location','location_on','Entender la ubicación','Roxy te explica los permisos',81,42]]},
    agenda: {name:'Calendario',eyebrow:'TIEMPO PARA LO IMPORTANTE',title:'Tu día también merece calma.',line:'Reúne tus planes y revísalos antes de guardarlos.',speech:'calendar',image:'/assets/roxy_home/world/living-room-205.png',
      objects:[['calendar','calendar_month','Abrir mi calendario','Consulta días, semanas y eventos',20,41],['action:calendar-new','edit_calendar','Crear un evento','Fecha, hora y confirmación',51,62],['today','today','Mi día','Cuidados y comidas de la semana',81,42]]},
  };

  const roomTools={house:'today',kitchen:'recipes',garden:'plants',wellness:'fitness',companions:'pets',atelier:'design',connection:'family',agenda:'calendar'};
  const toolRooms={today:'house',recipes:'kitchen',pantry:'kitchen',shopping:'kitchen',plants:'garden',fitness:'wellness',pets:'companions',design:'atelier',family:'connection',calendar:'agenda'};
  const workspacePanels=new Set(['today','calendar','recipes','shopping','pantry']);
  let context=null,panel='house',room='house',root=null,bar=null,sound=false,motion=true,voiceRevision=0,lastFocus='';
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n};
  const icon=name=>{const n=el('span',name,'material-symbols-rounded');n.setAttribute('aria-hidden','true');return n};
  const button=(text,fn,cls)=>{const b=el('button',text,cls);b.type='button';b.addEventListener('click',fn);return b};
  const valid=()=>Boolean(context&&context.isCurrent()&&!document.hidden);
  function stop(){voiceRevision++;global.RoxyHomeTour?.stop();root?.classList.remove('rhl-speaking')}
  function navigate(destination){
    if(!valid())return;
    if(!rooms[destination])lastFocus=destination;
    if(destination.startsWith('action:')){stop();context.openForm?.(destination.slice(7));return;}
    if(destination.startsWith('guide:')){stop();void global.RoxyHomeTour?.open(destination.slice(6));return;}
    context.navigate(destination);
  }
  function statusNode(){return root?.querySelector('.rhl-voice-status')}
  function narrate(){
    if(!valid()||!sound||!rooms[panel]||global.RoxyHomeWorld?.isOpen())return;
    const revision=++voiceRevision,owner=context;
    global.RoxyHomeTour?.speak(rooms[panel].speech,(state,message)=>{
      if(revision!==voiceRevision||owner!==context||!valid())return;
      root.classList.toggle('rhl-speaking',state==='playing');
      const node=statusNode();if(node)node.textContent=state==='ended'?'Aquí estoy, seguimos a tu ritmo.':message;
    },root.querySelector('.rhl-audio'));
  }
  function bind(next){
    if(context&&next&&context.identity===next.identity&&context.version===next.version){Object.assign(context,next);return;}
    if(!next||context?.identity!==next.identity||context?.version!==next.version){stop();sound=false;lastFocus='';}
    context=next;
    root=document.getElementById('homeLivingRoom');bar=document.getElementById('homeLivingBar');
    render();
  }
  function show(next){const changed=panel!==next;stop();panel=next;room=rooms[next]?next:toolRooms[next]||'house';render();return changed;}
  function roomNavigation(cls){
    const nav=el('nav',null,cls);nav.setAttribute('aria-label','Habitaciones de tu casa');
    for(const [key,name] of [['house','Sala'],[room==='house'?'kitchen':room,rooms[room==='house'?'kitchen':room].name]]){
      const b=button(name,()=>navigate(key));b.setAttribute('aria-current',room===key?'page':'false');nav.append(b);
    }
    return nav;
  }
  function render(){
    if(!root||!bar)return;
    const ready=Boolean(context&&context.isCurrent());
    document.body.classList.toggle('rhl-enabled',ready);
    document.body.classList.toggle('rhl-scene-view',ready&&Boolean(rooms[panel]));
    document.body.classList.toggle('rhl-workspace-view',ready&&workspacePanels.has(panel));
    document.body.dataset.livingRoom=room;
    root.replaceChildren();bar.replaceChildren();bar.hidden=!ready||Boolean(rooms[panel]);
    if(!ready){root.append(el('p','Preparando tu casa…','rhl-loading'));return;}
    if(!rooms[panel]){
      const back=button('',()=>navigate(room),'rhl-back');back.append(icon('arrow_back'),el('span',`Volver · ${rooms[room].name}`));
      bar.append(back);
      return;
    }
    const data=rooms[panel];
    const stage=el('div',null,'rhl-stage');stage.classList.toggle('rhl-still',!motion);
    const img=el('img',null,'rhl-room-image');img.src=data.image;img.alt=`${data.name} de la casa de Roxy`;img.fetchPriority='high';stage.append(img);
    const header=el('header',null,'rhl-room-header');header.append(el('span',data.name,'rhl-breadcrumb'));
    const copy=el('div',null,'rhl-intro');copy.append(el('p',data.eyebrow,'rhl-eyebrow'),el('h1',data.title),el('p',data.line));
    const objects=el('nav',null,'rhl-objects');objects.setAttribute('aria-label',`Qué hacemos en ${data.name}`);
    for(const [destination,symbol,title,detail,x,y] of data.objects){
      const b=button('',()=>navigate(destination),'rhl-object');b.dataset.destination=destination;b.style.setProperty('--x',`${x}%`);b.style.setProperty('--y',`${y}%`);
      const label=el('span',null,'rhl-object-label');label.append(el('strong',title),el('small',detail));b.append(icon(symbol),label,icon('north_east'));objects.append(b);
    }
    const dock=el('section',null,'rhl-roxy');dock.setAttribute('aria-label','Roxy te acompaña');
    const portrait=el('img',null,'rhl-portrait');portrait.src='/assets/roxy_home/world/roxy-host.png';portrait.alt='Roxy';
    const words=el('div',null,'rhl-roxy-words');words.append(el('strong','Estoy aquí contigo.'),el('p',sound?'Roxy te acompaña con su voz oficial.':'Toca un objeto y lo hacemos juntos.','rhl-voice-status'));
    words.lastChild.setAttribute('role','status');
    const controls=el('div',null,'rhl-roxy-controls');
    const voice=button(sound?'Silenciar':'Activar voz',()=>{sound=!sound;stop();render();root.querySelector('.rhl-sound')?.focus({preventScroll:true});if(sound)narrate()},'rhl-sound');voice.setAttribute('aria-pressed',String(sound));
    const repeat=button('Repetir',()=>{sound=true;narrate()},'rhl-repeat');repeat.hidden=!sound;
    const talk=button('Conversar',()=>{if(!valid())return;stop();context.converse?.()},'rhl-talk');
    controls.append(voice,repeat,talk);dock.append(portrait,words,controls,el('div',null,'rhl-audio'));
    const footer=el('div',null,'rhl-scene-footer');
    const explore=button('Explorar mi casa',()=>navigate('more'),'rhl-explore');footer.append(explore);
    const animate=button(motion?'Pausar ambiente':'Animar ambiente',()=>{motion=!motion;stage.classList.toggle('rhl-still',!motion);animate.textContent=motion?'Pausar ambiente':'Animar ambiente';animate.setAttribute('aria-pressed',String(!motion))},'rhl-motion');animate.setAttribute('aria-pressed',String(!motion));footer.append(animate);
    stage.append(header,copy,objects,dock,footer);root.append(stage);
    const focus=root.querySelector(`[data-destination="${lastFocus}"]`);if(focus)focus.focus({preventScroll:true});
  }
  // Narration continues after an intentional room change, never on page load.
  function enter(){if(sound&&rooms[panel])narrate()}
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});
  global.RoxyHomeLiving={bind,show,enter,stop,isRoom:key=>Boolean(rooms[key]),toolFor:key=>roomTools[key]||key,entryFor:key=>key==='fitness'&&typeof global.RoxyFitnessWorld?.mount==='function'?'fitness':['recipes','pantry','shopping'].includes(key)?key:toolRooms[key]||key};
})(window);
