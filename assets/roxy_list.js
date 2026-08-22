(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const now = () => new Date().toISOString();
  const categories = {ALL:'Todo',FOOD:'Alimentos',HOUSEHOLD:'Hogar',PERSONAL:'Aseo',HEALTH:'Salud',OTHER:'Otros',GENERAL:'General'};
  const staples = [
    ['Leche','FOOD','litro'],['Huevos','FOOD','docena'],['Queso','FOOD','paquete'],
    ['Pollo','FOOD','paquete'],['Tomate','FOOD','unidad'],['Aguacate','FOOD','unidad'],
    ['Plátanos','FOOD','racimo'],['Pan','FOOD','paquete'],['Arroz','FOOD','bolsa'],
    ['Café','HOUSEHOLD','bolsa'],['Aceite','HOUSEHOLD','botella'],['Papel higiénico','PERSONAL','paquete'],
    ['Agua','HOUSEHOLD','paquete'],['Detergente','HOUSEHOLD','botella'],['Jabón','PERSONAL','unidad']
  ];
  const productImages = {
    leche:'milk.png', milk:'milk.png', huevos:'eggs.png', huevo:'eggs.png',
    arroz:'rice.png', rice:'rice.png', pan:'bread.png', bread:'bread.png',
    platanos:'bananas.png', platano:'bananas.png', bananas:'bananas.png', banana:'bananas.png',
    pollo:'chicken.png', chicken:'chicken.png', queso:'cheese.png', cheese:'cheese.png',
    tomate:'tomato.png', tomato:'tomato.png', aguacate:'avocado.png', avocado:'avocado.png',
    cafe:'coffee.png', coffee:'coffee.png', aceite:'oil.png', oil:'oil.png',
    'papel higienico':'toilet-paper.png', agua:'water.png', water:'water.png',
    detergente:'detergent.png', detergent:'detergent.png', jabon:'soap.png', soap:'soap.png',
    levadura:'yeast.png', yeast:'yeast.png', mantequilla:'butter.png', butter:'butter.png',
    oxiclean:'cleaning-powder.png', 'oxi clean':'cleaning-powder.png', 'limpiador en polvo':'cleaning-powder.png',
    'papel toalla':'paper-towels.png', 'papel de cocina':'paper-towels.png', 'toalla de papel':'paper-towels.png',
    'paper towel':'paper-towels.png', analgésico:'pain-relief.png', analgesico:'pain-relief.png',
    ibuprofeno:'pain-relief.png', acetaminofen:'pain-relief.png', paracetamol:'pain-relief.png',
    'pastillitas de dolor':'pain-relief.png', 'pastillas de dolor':'pain-relief.png',
    sal:'salt.png', salt:'salt.png', suavizante:'fabric-softener.png', 'fabric softener':'fabric-softener.png',
    vainilla:'vanilla.png', vanilla:'vanilla.png',
    mandarina:'mandarin.png', mandarinas:'mandarin.png', naranja:'mandarin.png', naranjas:'mandarin.png',
    clementina:'mandarin.png', citrico:'mandarin.png', citricos:'mandarin.png',
    'dulce de leche':'dulce-de-leche.png', cajeta:'dulce-de-leche.png', arequipe:'dulce-de-leche.png',
    'ninja ice cream':'ice-cream.png', 'ninja creami':'ice-cream.png',
    'helado de dulce de leche':'ice-cream.png', helado:'ice-cream.png', 'ice cream':'ice-cream.png', mantecado:'ice-cream.png',
    azucar:'sugar.png', sugar:'sugar.png',
    'gel de cejas':'eyebrow-gel.png', cejas:'eyebrow-gel.png', 'eyebrow gel':'eyebrow-gel.png',
    medicamento:'medicine.png', medicamentos:'medicine.png', medicina:'medicine.png', medicinas:'medicine.png',
    farmacia:'medicine.png', pastilla:'medicine.png', pastillas:'medicine.png',
    'bolsitas de olor':'scent-sachets.png', 'bolsa de olor':'scent-sachets.png',
    ambientador:'scent-sachets.png', aromatizante:'scent-sachets.png', sachet:'scent-sachets.png',
    harina:'flour.png', flour:'flour.png', maicena:'flour.png', fecula:'flour.png',
    pasta:'pasta.png', espagueti:'pasta.png', spaghetti:'pasta.png', macarrones:'pasta.png',
    macarron:'pasta.png', fideos:'pasta.png', fideo:'pasta.png', lasana:'pasta.png', ramen:'pasta.png',
    yogur:'yogurt.png', yogurt:'yogurt.png', 'yogur griego':'yogurt.png',
    jugo:'juice.png', zumo:'juice.png', juice:'juice.png', refresco:'juice.png',
    cebolla:'vegetables.png', cebollas:'vegetables.png', papa:'vegetables.png', papas:'vegetables.png',
    patata:'vegetables.png', patatas:'vegetables.png', ajo:'vegetables.png', ajos:'vegetables.png',
    zanahoria:'vegetables.png', zanahorias:'vegetables.png', vegetales:'vegetables.png', verduras:'vegetables.png',
    carne:'beef.png', res:'beef.png', bistec:'beef.png', steak:'beef.png', hamburguesa:'beef.png',
    pescado:'fish.png', pescados:'fish.png', salmon:'fish.png', tilapia:'fish.png', atun:'fish.png',
    champu:'shampoo.png', shampoo:'shampoo.png', acondicionador:'shampoo.png'
  };

  let snapshot = {items:[],history:[],habitual_products:[],revision:0};
  let homeFood = {profile:{preferences:[],allergies:[],dislikes:[],household_size:1},pantry:[],recipes:[],cooking_sessions:[],weekly_plans:[]};
  let commerce = {profile:{objective:'balanced',organic_preference:'no_preference',favorite_retailers:[],favorite_brands:[],avoided_brands:[],dietary_labels:[],allow_substitutions:true,postal_code:''},providers:[],activity:{handoff_count:0,provider_counts:{},recent:[]},disclosure:''};
  let pendingCommerceProvider = null;
  let currentPreparation = null;
  let user = localStorage.getItem('roxyShoppingUser') || 'local_user';
  let category = 'ALL';
  let recipeFilter = 'all';
  let search = '';
  let showAllStaples = false;
  let busy = false;
  let installPrompt = null;
  let toastTimer = null;
  let currentRecipe = null;
  let currentCooking = null;
  let currentCookingVideo = null;
  let roxyStepAudio = null;
  let cookingVideoPoll = null;
  let cookingTimerTick = null;
  const announcedTimers = new Set();
  let greetingName=String(localStorage.getItem('roxyHomeGreetingName')||'').trim().slice(0,32);
  let account={mode:'unknown',display_name:'',storage_user_id:user,role:''};

  const activePersonName=()=>String(account.mode==='member'?account.display_name:greetingName||'').trim();

  function renderHomeMoment(){
    const moment=new Date();
    const hour=moment.getHours();
    const personName=activePersonName();
    const salutation=hour<12?'Buenos días':hour<19?'Buenas tardes':'Buenas noches';
    $('homeGreeting').textContent=`${salutation}${personName?',':''}`;
    const person=$('homePerson');person.textContent=personName;person.hidden=!personName;
    $('greetingSettingsButton').textContent=account.mode==='member'?'Perfil':greetingName?'Cambiar':'Tu nombre';
    $('homeDate').textContent=new Intl.DateTimeFormat('es',{weekday:'long',day:'numeric',month:'long',year:'numeric'}).format(moment);
    const timeText=new Intl.DateTimeFormat('es',{hour:'numeric',minute:'2-digit'}).format(moment);
    const timeNode=$('homeTime');timeNode.textContent=timeText;timeNode.dateTime=moment.toISOString();
  }

  function openGreetingSettings(){$('greetingName').value=greetingName;$('greetingDialog').showModal();$('greetingName').focus()}
  function saveGreeting(event){event.preventDefault();const name=$('greetingName').value.trim().slice(0,32);if(!name){announce('Escribe un nombre o elige Sin nombre');return}greetingName=name;localStorage.setItem('roxyHomeGreetingName',name);renderHomeMoment();$('greetingDialog').close();announce(`Este dispositivo saludará a ${name}`)}
  function clearGreeting(){greetingName='';localStorage.removeItem('roxyHomeGreetingName');renderHomeMoment();$('greetingDialog').close();announce('Saludo sin nombre en este dispositivo')}

  const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
  const productLabel = value => {
    let label=String(value||'').replace(/\s+/g,' ').trim();
    const wrappers=[
      /^(?:por favor\s+)?(?:agrega(?:r)?|añade|anade|pon|apunta|incluye|mete)\s+/i,
      /^(?:a|en)\s+(?:mi|la)\s+lista(?:\s+de\s+compras?)?\s+/i,
      /^(?:mi|la)\s+lista(?:\s+de\s+compras?)?\s+/i,
      /^lista\s+de\s+compras?\s+/i
    ];
    let previous='';
    while(label&&label!==previous){previous=label;wrappers.forEach(pattern=>{label=label.replace(pattern,'').trim()})}
    return label||String(value||'').trim();
  };
  const fallbackImage = itemCategory => itemCategory === 'PERSONAL'
    ? '/assets/roxy_home/products/soap.png'
    : itemCategory === 'HOUSEHOLD'
      ? '/assets/roxy_home/products/detergent.png'
      : itemCategory === 'HEALTH'
        ? '/assets/roxy_home/products/pain-relief.png'
        : '/assets/roxy_home/products/groceries.png';
  const imagePath = (name, itemCategory='GENERAL') => {
    const identity = normalize(productLabel(name));
    const exact = Object.keys(productImages)
      .sort((left,right) => right.length-left.length)
      .find(key => identity === key || identity.startsWith(`${key} `) || identity.endsWith(` ${key}`) || identity.includes(` ${key} `));
    if (exact) return `/assets/roxy_home/products/${productImages[exact]}`;
    return fallbackImage(itemCategory);
  };
  const recipeImage = recipe => {
    if (recipe && /^data:image\/(jpeg|png|webp);base64,/.test(String(recipe.photo_data_url || ''))) return recipe.photo_data_url;
    const searchable=normalize(`${recipe&&recipe.title||''} ${recipe&&recipe.description||''} ${(recipe&&recipe.ingredients||[]).map(row=>row&&row.name||'').join(' ')}`);
    if(/\b(pizza|pizzeta|calzone)\b/.test(searchable))return'/assets/roxy_home/recipes/pizza.png';
    if(/\b(pasta|espagueti|spaghetti|macarron|fideo|lasana|ravioli)\b/.test(searchable))return'/assets/roxy_home/recipes/pasta.png';
    if(/\b(pan|baguette|focaccia|brioche|bollo|masa madre)\b/.test(searchable))return'/assets/roxy_home/recipes/bread.png';
    if(/\b(postre|pastel|tarta|bizcocho|flan|arroz con leche|galleta|helado)\b/.test(searchable))return'/assets/roxy_home/recipes/dessert.png';
    if(/\b(sopa|caldo|crema|ensalada|aguacate|vegetal|verdura)\b/.test(searchable))return'/assets/roxy_home/recipes/soup-salad.png';
    if(/\b(bebida|limonada|jugo|zumo|batido|smoothie|mojito|coctel|cocktail)\b/.test(searchable))return'/assets/roxy_home/recipes/drinks.png';
    const kind = recipe && recipe.kind;
    if (kind === 'bread') return '/assets/roxy_home/recipes/bread.png';
    if (kind === 'drink') return '/assets/roxy_home/recipes/drinks.png';
    if (kind === 'dessert') return '/assets/roxy_home/recipes/dessert.png';
    return imagePath((recipe && recipe.ingredients && recipe.ingredients[0] && recipe.ingredients[0].name) || 'pollo','FOOD');
  };

  const dbPromise = new Promise((resolve,reject) => {
    const request = indexedDB.open('roxy-shopping-offline',1);
    request.onupgradeneeded = () => request.result.createObjectStore('state');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  async function dbGet(key) {
    const db = await dbPromise;
    return new Promise((resolve,reject) => {
      const req = db.transaction('state').objectStore('state').get(key);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  async function dbSet(key,value) {
    const db = await dbPromise;
    return new Promise((resolve,reject) => {
      const tx = db.transaction('state','readwrite');
      tx.objectStore('state').put(value,key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  const activeItems = () => snapshot.items.filter(item => item.status !== 'ARCHIVED');
  function announce(text) {
    $('toast').textContent = text;
    $('toast').hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => $('toast').hidden = true, 3000);
  }
  function setConnection(text,state='') {
    $('connectionState').textContent = text;
    $('connectionState').className = `connection ${state}`;
  }
  function setBusy(value) {
    busy = value;
    $('app').setAttribute('aria-busy', String(value));
  }
  async function api(path,options={}) {
    const response = await fetch(path, {
      credentials:'include', cache:'no-store',
      headers:{Accept:'application/json','Content-Type':'application/json',...(options.headers||{})},
      ...options
    });
    let data = {};
    try { data = await response.json(); } catch (_error) {}
    if (!response.ok) {
      const detail=data.detail;
      const error = new Error(String((detail&&typeof detail==='object'&&detail.message)||detail||`HTTP ${response.status}`));
      error.status = response.status;
      throw error;
    }
    return data;
  }
  async function cacheSnapshot() { await dbSet(`snapshot:${user}`,snapshot); }

  async function load({quiet=false}={}) {
    if (!quiet) setBusy(true);
    try {
      account=await api('/v1/home-account/me');
      if(account.storage_user_id){user=account.storage_user_id;localStorage.setItem('roxyShoppingUser',user)}
      const [shopping,food,shoppingCommerce] = await Promise.all([
        api(`/v1/shopping/${encodeURIComponent(user)}`),
        api(`/v1/home-food/${encodeURIComponent(user)}`),
        api(`/v1/home-commerce/${encodeURIComponent(user)}`)
      ]);
      snapshot = shopping;
      homeFood = food;
      commerce = shoppingCommerce;
      await cacheSnapshot();
      await dbSet(`home-food:${user}`,homeFood);
      await dbSet(`home-commerce:${user}`,commerce);
      await flushQueue();
      setConnection('Sincronizado ahora','online');
      populateHomeForms();
      render();
      renderAccount();
      renderHomeMoment();
      if(account.requires_profile_setup&&!sessionStorage.getItem('roxyHomeProfilePrompted')){sessionStorage.setItem('roxyHomeProfilePrompted','1');openAccountDialog()}
    } catch (error) {
      const cached = await dbGet(`snapshot:${user}`).catch(() => null);
      const cachedFood = await dbGet(`home-food:${user}`).catch(() => null);
      const cachedCommerce = await dbGet(`home-commerce:${user}`).catch(() => null);
      if (cached) snapshot = cached;
      if (cachedFood) homeFood = cachedFood;
      if (cachedCommerce) commerce = cachedCommerce;
      if (cached || cachedFood || cachedCommerce) {
        setConnection('Sin conexión · mostrando lo guardado','offline');
        populateHomeForms();
        render();
      }
      if (error.status === 401 || error.status === 403) {
        $('userId').value = user;
        if (!$('pairDialog').open) $('pairDialog').showModal();
      } else if (!cached) setConnection('No se pudo cargar Roxy Home','offline');
    } finally {
      if (!quiet) setBusy(false);
    }
  }

  async function queueMutation(row) {
    const queue = await dbGet(`queue:${user}`).catch(() => []) || [];
    queue.push(row);
    await dbSet(`queue:${user}`,queue);
    await cacheSnapshot();
    setConnection('Sin conexión · cambio pendiente','offline');
  }
  async function updateQueuedCreate(tempId,quantity) {
    const key = `queue:${user}`;
    let queue = await dbGet(key).catch(() => []) || [];
    if (quantity === null) queue = queue.filter(row => row.tempId !== tempId);
    else queue = queue.map(row => row.tempId === tempId ? {...row,options:{...row.options,body:JSON.stringify({...JSON.parse(row.options.body),quantity})}} : row);
    await dbSet(key,queue);
    await cacheSnapshot();
  }
  async function flushQueue() {
    const key = `queue:${user}`;
    const queue = await dbGet(key).catch(() => []) || [];
    if (!queue.length) return;
    for (const row of queue) {
      try { await api(row.path,row.options); }
      catch (error) { if (!error.status) return; throw error; }
    }
    await dbSet(key,[]);
    snapshot = await api(`/v1/shopping/${encodeURIComponent(user)}`);
    await cacheSnapshot();
    announce('Cambios sin conexión sincronizados');
  }
  async function mutate(row,optimistic) {
    if (busy) return;
    busy = true;
    optimistic();
    renderShopping();
    await cacheSnapshot();
    try { await api(row.path,row.options); await load({quiet:true}); }
    catch (error) {
      if (error.status) { announce(error.message); await load({quiet:true}); }
      else await queueMutation(row);
    } finally { busy = false; }
  }

  function makeButton(label,className,handler,aria) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.textContent = label;
    if (aria) button.setAttribute('aria-label',aria);
    button.addEventListener('click',handler);
    return button;
  }
  function makeImage(name,itemCategory,alt='') {
    const img = document.createElement('img');
    img.src = imagePath(name,itemCategory);
    img.alt = alt;
    img.loading = 'lazy';
    img.addEventListener('error',() => {
      const fallback = fallbackImage(itemCategory);
      if (!img.src.endsWith(fallback)) img.src = fallback;
    },{once:true});
    return img;
  }

  function selectPanel(panel) {
    document.querySelectorAll('[data-panel]').forEach(node => {
      const active = node.dataset.panel === panel;
      node.hidden = !active;
      node.classList.toggle('active',active);
    });
    document.querySelectorAll('.bottom-nav [data-tab-link]').forEach(button => button.classList.toggle('active',button.dataset.tabLink === panel));
    location.hash = panel === 'shopping' ? 'compra' : panel === 'recipes' ? 'recetas' : panel === 'pantry' ? 'despensa' : panel;
    window.scrollTo({top:0,behavior:'smooth'});
  }

  function renderFilters() {
    const root = $('categoryFilters');
    root.replaceChildren();
    ['ALL','FOOD','HOUSEHOLD','PERSONAL','OTHER'].forEach(value => {
      const button = makeButton(categories[value],'chip',() => { category=value; renderShopping(); });
      button.classList.toggle('active',category===value);
      button.setAttribute('aria-pressed',String(category===value));
      root.append(button);
    });
  }
  function filteredStaple(row) {
    return (category === 'ALL' || row[1] === category) && (!search || normalize(row[0]).includes(normalize(search)));
  }
  function suggestedProducts() {
    const activeNames = new Set(activeItems().map(item => normalize(item.name)));
    const remembered = (Array.isArray(snapshot.habitual_products) ? snapshot.habitual_products : [])
      .filter(item => item && item.name && !activeNames.has(normalize(item.name)))
      .map(item => [item.name,item.category||'GENERAL',item.unit||'unidad',Number(item.purchase_count||item.times_used||1)]);
    const seen = new Set(remembered.map(row => normalize(row[0])));
    return [...remembered,...staples.filter(row => !seen.has(normalize(row[0])) )];
  }
  function renderStaples() {
    const root = $('usualProducts');
    root.replaceChildren();
    const learnedCount = (Array.isArray(snapshot.habitual_products) ? snapshot.habitual_products : []).length;
    $('usualHint').textContent = learnedCount
      ? `Roxy recuerda ${learnedCount} ${learnedCount===1?'producto':'productos'} de tu historial.`
      : 'Roxy aprenderá automáticamente de lo que agregas y compras.';
    const matches = suggestedProducts().filter(filteredStaple);
    const compact = category === 'ALL' && !search && !showAllStaples;
    const rows = compact ? matches.slice(0,4) : matches;
    rows.forEach(([name,itemCategory,unit,frequency=0]) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'product';
      button.setAttribute('aria-label',`Agregar ${name}`);
      const img = makeImage(name,itemCategory,'');
      const copy = document.createElement('span'); copy.className='product-copy';
      const title = document.createElement('strong'); title.textContent = name;
      copy.append(title);
      if(frequency){const detail=document.createElement('small');detail.textContent=frequency===1?'Lo usaste antes':`${frequency} compras`;copy.append(detail)}
      const add = document.createElement('b'); add.textContent = '+'; add.setAttribute('aria-hidden','true');
      button.append(img,copy,add);
      button.addEventListener('click',() => addItem({name,quantity:1,unit,category:itemCategory}));
      root.append(button);
    });
    if (!root.children.length) {
      const empty = document.createElement('div'); empty.className='empty'; empty.textContent='No hay sugerencias que coincidan.'; root.append(empty);
    }
    $('toggleStaples').hidden = category !== 'ALL' || Boolean(search) || matches.length <= 4;
    $('toggleStaples').textContent = showAllStaples ? 'Ver menos' : 'Ver todos';
  }
  function addItem(payload) {
    const tempId = `offline-${crypto.randomUUID()}`;
    const item = {id:tempId,status:'PENDING',source:'roxy_home_pwa',created_at:now(),updated_at:now(),...payload};
    mutate({tempId,path:`/v1/shopping/${encodeURIComponent(user)}`,options:{method:'POST',body:JSON.stringify(payload)}},() => {
      const existing = activeItems().find(row => normalize(row.name) === normalize(payload.name) && row.unit === payload.unit);
      if (existing) existing.quantity = Number(existing.quantity) + Number(payload.quantity);
      else snapshot.items.push(item);
      announce(`${payload.name} agregado`);
    });
  }
  function changeQuantity(item,delta) {
    const quantity = Math.max(1,Number(item.quantity||1)+delta);
    if (String(item.id).startsWith('offline-')) { item.quantity=quantity; renderShopping(); updateQueuedCreate(item.id,quantity); return; }
    mutate({path:`/v1/shopping/${encodeURIComponent(user)}/${encodeURIComponent(item.id)}`,options:{method:'PATCH',body:JSON.stringify({quantity})}},() => item.quantity=quantity);
  }
  function removeItem(item) {
    if (String(item.id).startsWith('offline-')) {
      snapshot.items=snapshot.items.filter(row=>row.id!==item.id); renderShopping(); updateQueuedCreate(item.id,null); return;
    }
    mutate({path:`/v1/shopping/${encodeURIComponent(user)}/${encodeURIComponent(item.id)}`,options:{method:'DELETE'}},() => {
      snapshot.items=snapshot.items.filter(row=>row.id!==item.id); announce(`${item.name} eliminado`);
    });
  }
  function renderList() {
    const root = $('shoppingList');
    root.replaceChildren();
    const rows = activeItems().filter(item => (category==='ALL'||item.category===category) && (!search||normalize(item.name).includes(normalize(search))));
    $('rowCount').textContent = `${rows.length} ${rows.length===1?'producto':'productos'}`;
    if (!rows.length) {
      const empty=document.createElement('div'); empty.className='empty';
      const strong=document.createElement('strong'); strong.textContent=activeItems().length?'Sin coincidencias':'Tu lista está lista para empezar';
      empty.append(strong,document.createTextNode(activeItems().length?' Prueba otra búsqueda.':' Agrega un producto o pídeselo a Roxy.'));
      root.append(empty); return;
    }
    rows.forEach(item => {
      const article=document.createElement('article'); article.className='shopping-item';
      const label=productLabel(item.name);
      const img=makeImage(label,item.category,''); img.className='product-thumb';
      const copy=document.createElement('div'); copy.className='shopping-copy';
      const strong=document.createElement('strong'); strong.textContent=label;
      const small=document.createElement('small'); small.textContent=`${categories[item.category]||'General'} · ${item.unit||'unidad'}`;
      copy.append(strong,small);
      const stepper=document.createElement('div'); stepper.className='stepper';
      const minus=makeButton('−','',()=>changeQuantity(item,-1),`Disminuir cantidad de ${label}`); minus.disabled=Number(item.quantity)<=1;
      const output=document.createElement('output'); output.value=String(item.quantity); output.textContent=String(item.quantity); output.setAttribute('aria-label',`Cantidad ${item.quantity}`);
      const plus=makeButton('+','',()=>changeQuantity(item,1),`Aumentar cantidad de ${label}`);
      stepper.append(minus,output,plus);
      const remove=makeButton('Eliminar','delete',()=>removeItem(item),`Eliminar ${label}`);
      const controls=document.createElement('div'); controls.className='item-controls'; controls.append(stepper,remove);
      article.append(img,copy,controls); root.append(article);
    });
  }
  function renderHistory() {
    const root=$('historyList'); root.replaceChildren();
    const rows=Array.isArray(snapshot.history)?snapshot.history:[];
    if(!rows.length){root.textContent='Todavía no hay compras archivadas.';return;}
    rows.forEach(trip=>{const row=document.createElement('div');row.className='history-row';const strong=document.createElement('strong');strong.textContent=new Intl.DateTimeFormat('es',{dateStyle:'medium'}).format(new Date(trip.completed_at));const small=document.createElement('small');small.textContent=`${trip.item_count||0} productos · ${(trip.items||[]).slice(0,5).map(item=>item.name).join(', ')}`;row.append(strong,small);root.append(row)});
  }
  function renderShopping() {
    renderFilters(); renderStaples(); renderList(); renderHistory();
    const rows=activeItems();
    $('pendingTotal').textContent=new Intl.NumberFormat('es',{maximumFractionDigits:2}).format(rows.reduce((total,item)=>total+Number(item.quantity||0),0));
    $('completeButton').disabled=!rows.length;
    renderCommerceSummary();
  }

  function renderCommerceSummary(){
    const profile=commerce.profile||{};
    const objectiveLabels={balanced:'equilibrio entre calidad y precio',lowest_price:'el menor precio por unidad',organic:'productos orgánicos',favorites:'tus marcas favoritas'};
    $('commerceSummary').textContent=`Roxy priorizará ${objectiveLabels[profile.objective]||objectiveLabels.balanced}.`;
    $('affiliateDisclosure').textContent=commerce.disclosure||'';
    const root=$('commerceProviderBadges');root.replaceChildren();
    (commerce.providers||[]).forEach(provider=>{const badge=document.createElement('span');badge.className=`provider-badge ${provider.configured?'ready':'pending'}`;const used=Number(provider.handoff_count||0);badge.textContent=`${provider.name} · ${provider.configured?'listo':'pendiente'}${used?` · usado ${used}`:''}`;root.append(badge)});
    const recent=$('commerceRecent');recent.replaceChildren();const activity=commerce.activity||{};const latest=(activity.recent||[])[0];
    if(latest){const strong=document.createElement('strong');strong.textContent='Última compra preparada';const small=document.createElement('small');small.textContent=`${latest.provider_name} · ${latest.item_count} ${latest.item_count===1?'artículo':'artículos'} · falta confirmar en la tienda`;recent.append(strong,small)}
    $('prepareShoppingButton').disabled=!activeItems().length;
  }

  const kindLabels={meal:'Comida',bread:'Pan',dessert:'Postre',drink:'Bebida',other:'Otra'};
  function recipeCard(recipe){
    const button=document.createElement('button');button.type='button';button.className='recipe-card';
    const img=document.createElement('img');img.src=recipeImage(recipe);img.alt=`Foto de ${recipe.title||'la receta'}`;img.loading='lazy';
    const copy=document.createElement('span');const strong=document.createElement('strong');strong.textContent=recipe.title;
    const drinkLabel=recipe.kind==='drink'?(recipe.drink_type==='alcoholic'?'Con alcohol':'Sin alcohol'):'';
    const small=document.createElement('small');small.textContent=`${recipe.favorite?'Favorita · ':''}${drinkLabel||kindLabels[recipe.kind]||'Receta'} · ${recipe.servings||1} porciones · ${(recipe.steps||[]).length} pasos`;
    copy.append(strong,small);button.append(img,copy);button.addEventListener('click',()=>openRecipe(recipe));return button;
  }
  function renderRecipes() {
    const root=$('recipeLibrary'); root.replaceChildren();
    const catalog=homeFood.local_catalog||{};
    $('recipeCatalogHint').textContent=catalog.total?`Roxy conoce ${catalog.total} recetas localmente y reserva OpenAI para algo especial.`:'';
    const sessions=homeFood.cooking_sessions||[];
    const active=[...sessions].reverse().find(row=>row.status==='ACTIVE');
    if(active){
      const resume=document.createElement('button'); resume.type='button'; resume.className='recipe-card resume-card';
      const img=document.createElement('img'); img.src='/assets/roxy_avatar_card.jpg'; img.alt='';
      const copy=document.createElement('span'); const strong=document.createElement('strong'); strong.textContent=`Continuar: ${active.recipe_title}`;
      const small=document.createElement('small'); small.textContent=`Paso ${Number(active.step_index||0)+1} de ${active.step_count}`;
      copy.append(strong,small); resume.append(img,copy); resume.addEventListener('click',()=>resumeCooking(active.id)); root.append(resume);
    }
    const rows=(homeFood.recipes||[]).filter(recipe=>recipeFilter==='all'||(recipeFilter==='favorite'?recipe.favorite:recipeFilter==='alcoholic'||recipeFilter==='non_alcoholic'?recipe.drink_type===recipeFilter:recipe.kind===recipeFilter)).slice().reverse();
    $('recipeCount').textContent=`${rows.length} ${rows.length===1?'receta':'recetas'}`;
    const categories=[
      {id:'meal',title:'Comidas',description:'Platos, panes y preparaciones saladas',matches:recipe=>recipe.kind!=='drink'&&recipe.kind!=='dessert'},
      {id:'dessert',title:'Postres',description:'Dulces y preparaciones para compartir',matches:recipe=>recipe.kind==='dessert'},
      {id:'drink',title:'Bebidas',description:'Con alcohol y sin alcohol',matches:recipe=>recipe.kind==='drink'},
    ];
    const visibleCategories=recipeFilter==='dessert'?categories.slice(1,2):(recipeFilter==='drink'||recipeFilter==='alcoholic'||recipeFilter==='non_alcoholic')?categories.slice(2):recipeFilter==='meal'||recipeFilter==='bread'?categories.slice(0,1):categories;
    visibleCategories.forEach(category=>{
      const categoryRows=rows.filter(category.matches);
      const section=document.createElement('section');section.className='recipe-category';section.dataset.recipeCategory=category.id;
      const heading=document.createElement('div');heading.className='recipe-category-heading';
      const copy=document.createElement('div');const title=document.createElement('h3');title.textContent=category.title;const description=document.createElement('p');description.textContent=category.description;copy.append(title,description);
      const count=document.createElement('span');count.textContent=String(categoryRows.length);count.setAttribute('aria-label',`${categoryRows.length} recetas en ${category.title}`);heading.append(copy,count);section.append(heading);
      const grid=document.createElement('div');grid.className='recipe-category-grid';categoryRows.forEach(recipe=>grid.append(recipeCard(recipe)));
      if(!categoryRows.length){const empty=document.createElement('div');empty.className='empty category-empty';empty.textContent=`Todavía no hay ${category.title.toLowerCase()} guardadas.`;grid.append(empty);}
      section.append(grid);root.append(section);
    });
    if(!rows.length&&recipeFilter==='favorite'){const empty=document.createElement('div');empty.className='empty';empty.innerHTML='<strong>Aún no tienes favoritas</strong>Abre una receta para marcarla como favorita.';root.replaceChildren(empty);}
  }
  function addTextList(root,rows,ordered=false){const list=document.createElement(ordered?'ol':'ul');(rows||[]).forEach(row=>{const item=document.createElement('li');item.textContent=typeof row==='string'?row:`${row.quantity||''} ${row.unit||''} de ${row.name||''}${row.notes?` · ${row.notes}`:''}`.trim();list.append(item)});root.append(list);}
  function openRecipe(recipe){
    currentRecipe=recipe;$('recipeDialogTitle').textContent=recipe.title||'Receta de Roxy';
    const root=$('recipeDialogContent');root.replaceChildren();
    const hero=document.createElement('div');hero.className='recipe-detail-hero';const img=document.createElement('img');img.src=recipeImage(recipe);img.alt=`Foto de ${recipe.title||'la receta'}`;
    const intro=document.createElement('div');const meta=document.createElement('strong');const recipeLabel=recipe.kind==='drink'?(recipe.drink_type==='alcoholic'?'Bebida con alcohol':'Bebida sin alcohol'):(kindLabels[recipe.kind]||'Receta');meta.textContent=`${recipeLabel} · ${recipe.servings||1} porciones`;
    const description=document.createElement('p');description.textContent=recipe.description||'Receta guardada por Roxy.';intro.append(meta,description);hero.append(img,intro);
    const columns=document.createElement('div');columns.className='recipe-columns';
    const ingredients=document.createElement('section');const ingTitle=document.createElement('h3');ingTitle.textContent='Ingredientes';ingredients.append(ingTitle);addTextList(ingredients,recipe.ingredients||[]);
    const steps=document.createElement('section');const stepTitle=document.createElement('h3');stepTitle.textContent='Preparación';steps.append(stepTitle);addTextList(steps,recipe.steps||[],true);columns.append(ingredients,steps);
    const actions=document.createElement('div');actions.className='recipe-detail-actions';
    const add=makeButton('Agregar ingredientes','secondary',()=>previewRecipe(recipe.id,Number(recipe.servings||1)));
    const buy=makeButton('Buscar para comprar','secondary',()=>preparePurchase('recipe',recipe.id));
    const guide=makeButton('Cocinar paso a paso','primary',()=>startCooking(recipe.id));actions.append(add,guide);
    actions.insertBefore(buy,guide);
    root.append(hero,columns,actions);
    $('recipeFavorite').checked=Boolean(recipe.favorite);
    $('recipeNotes').value=recipe.user_notes||'';
    $('recipePhoto').value='';
    if(!$('recipeDialog').open)$('recipeDialog').showModal();
  }

  function recipeVideoStatusLabel(status){return({QUEUED:'En cola',PROCESSING:'Roxy está creando las demostraciones',REVIEW:'Pendiente de revisión',READY:'Video disponible',FAILED:'La generación no terminó',REJECTED:'No pasó la revisión'})[status]||'Video de la receta'}
  function renderRecipeVideo(video,service,area,recipe){
    if(currentRecipe&&currentRecipe.id!==recipe.id)return;
    area.replaceChildren();
    if(!video){
      if(!service||!service.enabled){area.hidden=true;return}
      area.hidden=false;const heading=document.createElement('div');heading.className='recipe-video-heading';const copy=document.createElement('div');const title=document.createElement('h3');title.textContent='Video de esta receta';const note=document.createElement('p');note.textContent=`Cuando empieces a cocinar, Roxy preparará ${service.clip_count} demostraciones prácticas automáticamente, las guardará y las reutilizará para todos.`;copy.append(title,note);heading.append(copy);area.append(heading);return;
    }
    area.hidden=false;const heading=document.createElement('div');heading.className='recipe-video-heading';const copy=document.createElement('div');const title=document.createElement('h3');title.textContent='Video creado por Roxy';const note=document.createElement('p');note.textContent=`${recipeVideoStatusLabel(video.status)} · ${video.visibility==='shared'?'biblioteca compartida':'solo este hogar'} · generado con IA`;copy.append(title,note);heading.append(copy);area.append(heading);
    const playable=(video.clips||[]).filter(clip=>clip.playback_url);
    if(playable.length){
      const playlist=document.createElement('div');playlist.className='recipe-video-playlist';
      playable.forEach((clip,index)=>{const card=document.createElement('article');const media=document.createElement('video');media.controls=true;media.preload='metadata';media.playsInline=true;media.src=clip.playback_url;media.setAttribute('aria-label',`${clip.step_label||`Clip ${index+1}`} de ${recipe.title}`);const label=document.createElement('strong');label.textContent=clip.step_label||`Momento ${index+1}`;const disclosure=document.createElement('small');disclosure.textContent=video.status==='READY'?'Visual generado con IA y revisado. Sigue las instrucciones escritas de Roxy.':'Vista previa privada; todavía no se comparte.';card.append(media,label,disclosure);playlist.append(card);if(index<playable.length-1)media.addEventListener('ended',()=>{const next=playlist.querySelectorAll('video')[index+1];if(next)next.play().catch(()=>{})})});
      area.append(playlist);
    }
    if(['QUEUED','PROCESSING'].includes(video.status)){
      const refresh=makeButton('Comprobar progreso','secondary',()=>syncRecipeVideo(video.id,recipe,area));heading.append(refresh);
    }else if(video.status==='REVIEW'){
      const review=document.createElement('p');review.className='recipe-video-review';review.textContent='Roxy ya guardó las demostraciones. Antes de compartirlas con otros usuarios se revisarán la acción, los ingredientes, la técnica y la seguridad.';area.append(review);
    }else if(video.status==='FAILED'){
      const failed=document.createElement('p');failed.className='recipe-video-review error';failed.textContent='No se cobró una nueva generación desde esta pantalla. Un administrador puede revisar el proveedor antes de intentarlo otra vez.';area.append(failed);
    }
  }
  async function loadRecipeVideo(recipe,area){
    area.hidden=false;area.textContent='Buscando un video guardado…';
    try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/recipes/${encodeURIComponent(recipe.id)}/video`);renderRecipeVideo(data.video,data.service,area,recipe)}catch(error){area.hidden=true;announce(error.message)}
  }
  async function syncRecipeVideo(videoId,recipe,area){
    area.setAttribute('aria-busy','true');
    try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/recipe-videos/${encodeURIComponent(videoId)}/sync`,{method:'POST',body:'{}'});renderRecipeVideo(data.video,homeFood.recipe_video_service||{},area,recipe);announce(data.status==='REVIEW'?'Las demostraciones están guardadas y listas para revisión':'Roxy actualizó el progreso del video')}
    catch(error){announce(error.message)}finally{area.removeAttribute('aria-busy')}
  }

  function readRecipePhoto(file){
    if(!file)return Promise.resolve(null);
    if(!['image/jpeg','image/png','image/webp'].includes(file.type))return Promise.reject(new Error('La foto debe ser JPEG, PNG o WebP'));
    if(file.size>1_500_000)return Promise.reject(new Error('La foto debe pesar menos de 1.5 MB'));
    return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result||''));reader.onerror=()=>reject(new Error('No pude leer la foto'));reader.readAsDataURL(file)});
  }
  async function saveRecipePersonalization(event){
    event.preventDefault();if(!currentRecipe)return;
    const button=event.currentTarget.querySelector('button[type="submit"]');button.disabled=true;
    try{
      const photo=await readRecipePhoto($('recipePhoto').files[0]);
      const data=await api(`/v1/home-food/${encodeURIComponent(user)}/recipes/${encodeURIComponent(currentRecipe.id)}`,{method:'PATCH',body:JSON.stringify({favorite:$('recipeFavorite').checked,user_notes:$('recipeNotes').value,photo_data_url:photo})});
      currentRecipe=data.recipe;await load({quiet:true});openRecipe(data.recipe);announce('Receta personalizada y guardada');
    }catch(error){announce(error.message)}finally{button.disabled=false}
  }
  async function deleteCurrentRecipe(){
    if(!currentRecipe)return;
    const title=currentRecipe.title||'esta receta';
    if(!window.confirm(`¿Eliminar “${title}”?\n\nLa receta y sus sesiones de cocina se borrarán de este hogar. La lista de compras no cambiará.`))return;
    const button=$('deleteRecipeButton');button.disabled=true;
    try{await api(`/v1/home-food/${encodeURIComponent(user)}/recipes/${encodeURIComponent(currentRecipe.id)}`,{method:'DELETE'});currentRecipe=null;$('recipeDialog').close();await load({quiet:true});renderRecipes();announce('Receta eliminada')}
    catch(error){announce(error.message)}finally{button.disabled=false}
  }
  async function previewRecipe(recipeId,servings){
    try{
      const data=await api(`/v1/home-food/${encodeURIComponent(user)}/recipes/${encodeURIComponent(recipeId)}/shopping-preview`,{method:'POST',body:JSON.stringify({confirmed:false,servings})});
      if(!data.items.length){announce('Ya tienes todos los ingredientes en la despensa');return;}
      const names=data.items.map(row=>`${row.quantity} ${row.unit} de ${row.name}`).join('\n');
      if(!window.confirm(`Roxy agregará estos ingredientes a tu lista:\n\n${names}\n\n¿Confirmas?`))return;
      await api(`/v1/home-food/${encodeURIComponent(user)}/recipes/${encodeURIComponent(recipeId)}/shopping-commit`,{method:'POST',body:JSON.stringify({confirmed:true,servings})});
      announce('Ingredientes agregados a la lista');await load({quiet:true});
    }catch(error){announce(error.message);}
  }
  async function preparePurchase(source='shopping',recipeId=null){
    const button=source==='shopping'?$('prepareShoppingButton'):null;
    if(button){button.disabled=true;button.textContent='Roxy está preparando…'}
    try{
      const data=await api(`/v1/home-commerce/${encodeURIComponent(user)}/preparations`,{method:'POST',body:JSON.stringify({source,recipe_id:recipeId,provider_ids:[]})});
      currentPreparation=data.preparation;
      renderCommercePreparation(data.preparation,data.providers||commerce.providers||[]);
      if($('recipeDialog').open)$('recipeDialog').close();
      if(!$('commerceDialog').open)$('commerceDialog').showModal();
    }catch(error){announce(error.message)}finally{if(button){button.disabled=false;button.textContent='Buscar productos de mi lista'}}
  }
  function renderCommercePreparation(preparation,providers){
    $('commerceDialogTitle').textContent=preparation.source_title||'Tu compra personalizada';
    $('commerceDisclosureDialog').textContent=preparation.disclosure||commerce.disclosure||'';
    $('commerceProviderDisclosure').hidden=true;$('commerceProviderDisclosure').textContent='';
    const items=$('commerceItems');items.replaceChildren();
    (preparation.items||[]).forEach(row=>{const article=document.createElement('article');const img=makeImage(row.name,'FOOD','');const copy=document.createElement('div');const strong=document.createElement('strong');strong.textContent=`${row.quantity} ${row.unit} · ${row.name}`;const small=document.createElement('small');small.textContent=row.reason;copy.append(strong,small);if((row.avoided_brands||[]).length){const avoided=document.createElement('small');avoided.textContent=`Evitar: ${row.avoided_brands.join(', ')}`;copy.append(avoided)}if(row.allergen_review_required){const warning=document.createElement('em');warning.textContent='Verifica la etiqueta por tus alergias';copy.append(warning)}article.append(img,copy);items.append(article)});
    pendingCommerceProvider=null;$('commerceConfirmation').hidden=true;$('commerceConfirmCheck').checked=false;$('commerceConfirmButton').disabled=true;$('commerceHandoffNote').textContent='';
    const actions=$('commerceActions');actions.replaceChildren();
    providers.filter(provider=>(preparation.providers||[]).includes(provider.id)).forEach(provider=>{const button=makeButton(provider.configured?`Continuar con ${provider.name}`:`${provider.name} · falta conectar cuenta`,provider.configured?'primary':'secondary',()=>requestProviderLinks(provider.id));button.disabled=!provider.configured;actions.append(button)});
  }
  function requestProviderLinks(providerId){
    if(!currentPreparation)return;
    const provider=(commerce.providers||[]).find(row=>row.id===providerId)||{id:providerId,name:'el comercio'};
    pendingCommerceProvider=provider;
    $('commerceConfirmTitle').textContent=`Continuar de forma segura con ${provider.name}`;
    $('commerceConfirmCopy').textContent=`Roxy preparará la entrega de tu lista. ${provider.name} mostrará disponibilidad, sustituciones y precio final antes del pago.`;
    $('commerceConfirmCheck').checked=false;$('commerceConfirmButton').disabled=true;$('commerceConfirmation').hidden=false;
    $('commerceConfirmCheck').focus();
  }
  async function confirmProviderHandoff(){
    if(!currentPreparation||!pendingCommerceProvider||!$('commerceConfirmCheck').checked)return;
    const provider=pendingCommerceProvider;
    const confirmButton=$('commerceConfirmButton');confirmButton.disabled=true;confirmButton.textContent='Preparando acceso seguro…';
    try{
      const result=await api(`/v1/home-commerce/${encodeURIComponent(user)}/preparations/${encodeURIComponent(currentPreparation.id)}/checkout`,{method:'POST',body:JSON.stringify({provider_id:provider.id,confirmed:true})});
      $('commerceConfirmation').hidden=true;
      const actions=$('commerceActions');actions.replaceChildren();
      const heading=document.createElement('strong');heading.textContent=`Pago protegido por ${provider.name}`;actions.append(heading);
      const providerDisclosure=$('commerceProviderDisclosure');providerDisclosure.textContent=result.provider_disclosure||'';providerDisclosure.hidden=!result.provider_disclosure;
      (result.links||[]).slice(0,100).forEach(row=>{const link=document.createElement('a');link.className='primary commerce-link';link.href=row.url;link.target='_blank';link.rel='noopener sponsored';link.dataset.externalCheckout=provider.id;link.textContent=result.mode==='full_list'?`Revisar productos y pagar en ${provider.name}`:result.mode==='affiliate_link'?`Abrir ${provider.name} para seleccionar y pagar`:`Revisar ${row.label} en ${provider.name}`;actions.append(link)});
      $('commerceHandoffNote').textContent=`La cuenta, dirección y método de pago permanecen protegidos por ${provider.name}. Puedes regresar a Roxy al terminar.`;
      commerce.activity=commerce.activity||{handoff_count:0,provider_counts:{},recent:[]};if(result.handoff&&!commerce.activity.recent.some(row=>row.id===result.handoff.id)){commerce.activity.handoff_count=Number(commerce.activity.handoff_count||0)+1;commerce.activity.recent=[result.handoff,...(commerce.activity.recent||[])].slice(0,10);commerce.activity.provider_counts[result.handoff.provider_id]=Number(commerce.activity.provider_counts[result.handoff.provider_id]||0)+1;const providerRow=(commerce.providers||[]).find(row=>row.id===result.handoff.provider_id);if(providerRow)providerRow.handoff_count=Number(providerRow.handoff_count||0)+1;renderCommerceSummary()}
      announce('Enlaces preparados. Tú confirmas la compra en el comercio.');
    }catch(error){announce(error.message);confirmButton.disabled=false}finally{confirmButton.textContent='Continuar al comercio'}
  }
  async function startCooking(recipeId){
    try{
      const data=await api(`/v1/home-food/${encodeURIComponent(user)}/recipes/${encodeURIComponent(recipeId)}/cooking-sessions`,{method:'POST',body:'{}'});
      currentCooking=data;currentCookingVideo=data.recipe_video||null;$('recipeDialog').close();showCooking(data);renderCookingVideo(data.recipe_video_status,data.recipe_video);await load({quiet:true});
      if(data.recipe_video_status==='QUEUED')announce('Empezamos. Roxy también está preparando y guardando el video para reutilizarlo.');
      else if(data.recipe_video_status==='REUSED')announce('Empezamos con el video que Roxy ya tenía guardado.');
      else if(data.recipe_video_status==='BUDGET_LIMIT')announce('Empezamos la receta. El video esperará al próximo presupuesto disponible.');
      else if(data.recipe_video_status==='LIBRARY_BUILDING')announce('Empezamos la receta. Roxy usará la guía hablada mientras completa su videoteca reutilizable, sin generar un cobro nuevo.');
      else if(['DISABLED','MISSING_KEY','MISSING_BUDGET','COST_LIMIT'].includes(data.recipe_video_status)){const service=homeFood.recipe_video_service||{};announce(service.message||'La guía funciona, pero falta terminar la configuración del video.');}
      speakCurrentStep();
    }catch(error){announce(error.message);}
  }
  async function resumeCooking(sessionId){
    try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/cooking-sessions/${encodeURIComponent(sessionId)}`);currentCooking=data;showCooking(data);await refreshCookingVideo(data.recipe.id);speakCurrentStep();}catch(error){announce(error.message);}
  }
  const normalizedStepText=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
  function clipStepNumber(clip,steps,index,totalClips){
    const explicit=Number(clip&&clip.step_index);if(Number.isInteger(explicit)&&explicit>=0)return explicit+1;
    const label=normalizedStepText(clip&&clip.step_label);
    for(let stepIndex=0;stepIndex<steps.length;stepIndex+=1){const step=normalizedStepText(steps[stepIndex]);if(step&&label.includes(step.slice(0,Math.min(55,step.length))))return stepIndex+1}
    return Math.min(steps.length,Math.max(1,Math.round(index*Math.max(0,steps.length-1)/Math.max(1,totalClips-1))+1));
  }
  function clipMatchesStep(clip,stepNumber,steps,index,totalClips){const mapped=(clip&&Array.isArray(clip.step_indices)?clip.step_indices:[]).map(value=>Number(value)+1).filter(Number.isFinite);return mapped.length?mapped.includes(stepNumber):clipStepNumber(clip,steps,index,totalClips)===stepNumber}
  function currentStepVideo(){return $('cookingVideo').querySelector('video[data-current-step="true"]')}
  function waitForMediaDuration(media){if(Number.isFinite(media.duration)&&media.duration>0)return Promise.resolve();return new Promise(resolve=>{let settled=false;const finish=()=>{if(settled)return;settled=true;clearTimeout(timer);resolve()};const timer=setTimeout(finish,2500);media.addEventListener('loadedmetadata',finish,{once:true});media.addEventListener('durationchange',finish,{once:true});if(typeof media.load==='function')media.load()})}
  async function startSynchronizedStepVideo(audio){const media=currentStepVideo();if(!media){await audio.play();return}media.muted=true;media.currentTime=0;media.dataset.syncActive='true';await Promise.all([waitForMediaDuration(media),waitForMediaDuration(audio)]);const videoSeconds=Number(media.duration||0);const audioSeconds=Number(audio.duration||0);if(videoSeconds>0&&audioSeconds>0){const cycles=Math.max(1,Math.ceil(audioSeconds/videoSeconds));media.loop=cycles>1;media.playbackRate=Math.min(4,Math.max(.25,videoSeconds*cycles/audioSeconds))}else{media.loop=true;media.playbackRate=1}const audioStarted=audio.play();media.play().catch(()=>{});await audioStarted}
  function stopSynchronizedStepVideo(finish=false){const media=currentStepVideo();if(!media)return;delete media.dataset.syncActive;media.loop=false;media.pause();media.playbackRate=1;if(finish&&Number.isFinite(media.duration)&&media.duration>0){try{media.currentTime=Math.max(0,media.duration-.04)}catch(_error){}}}
  function renderCookingVideo(status,video){
    const root=$('cookingVideo');const visual=$('cookingImage').parentElement;if(visual)visual.hidden=false;root.replaceChildren();root.setAttribute('aria-live','polite');clearTimeout(cookingVideoPoll);cookingVideoPoll=null;
    const service=homeFood.recipe_video_service||{};
    if(!video){if(service.enabled){root.hidden=false;const strong=document.createElement('strong');strong.textContent='Video de Roxy';const small=document.createElement('small');small.textContent='El video se preparará automáticamente al comenzar una receta nueva.';root.append(strong,small);}else root.hidden=true;return;}
    currentCookingVideo=video;root.hidden=false;
    const strong=document.createElement('strong');strong.textContent=video.status==='READY'?'Video disponible':video.status==='REVIEW'?'Video terminado':video.status==='FAILED'?'No se pudo crear el video':'Roxy está creando las demostraciones';
    const completed=(video.clips||[]).filter(clip=>clip.status==='COMPLETED').length;const total=Number(video.clip_count||(video.clips||[]).length||3);const elapsed=Math.max(0,Math.floor((Date.now()-Date.parse(video.created_at||new Date().toISOString()))/60000));
    const small=document.createElement('small');small.textContent=video.status==='REVIEW'?'Las demostraciones ya están guardadas y esperan revisión antes de compartirse.':video.status==='READY'?'Este video ya fue revisado y puede reutilizarse.':video.status==='FAILED'?'La receta continúa disponible. Roxy podrá intentarlo nuevamente con una versión corregida.':`${completed} de ${total} demostraciones listas${elapsed?` · ${elapsed} min`:''}. Puedes seguir cocinando; Roxy actualiza el progreso automáticamente.`;root.append(strong,small);
    const steps=(currentCooking&&currentCooking.recipe&&currentCooking.recipe.steps)||[];const stepNumber=Number(currentCooking&&currentCooking.step_number||1);const allClips=video.clips||[];
    const currentClip=allClips.map((clip,index)=>({clip,index})).find(row=>clipMatchesStep(row.clip,stepNumber,steps,row.index,allClips.length)&&row.clip.playback_url);
    if(currentClip){if(visual)visual.hidden=true;const clips=document.createElement('div');clips.className='cooking-video-clips';const media=document.createElement('video');media.controls=true;media.muted=true;media.playsInline=true;media.preload='auto';media.src=currentClip.clip.playback_url;media.dataset.currentStep='true';media.setAttribute('aria-label',`Demostración del paso ${stepNumber}: ${currentClip.clip.step_label||''}`);const label=document.createElement('span');label.className='cooking-video-step-label';const labelTitle=document.createElement('span');labelTitle.textContent=`Roxy demuestra el paso ${stepNumber}`;const labelNote=document.createElement('small');labelNote.textContent='La demostración ajusta su velocidad y termina junto con la explicación de Roxy.';label.append(labelTitle,labelNote);clips.append(media,label);root.append(clips)}
    else if(['REVIEW','READY'].includes(video.status)){const note=document.createElement('small');note.textContent=`El paso ${stepNumber} todavía no tiene una demostración específica. Roxy mantendrá la guía hablada y escrita.`;root.append(note)}
    if(['QUEUED','PROCESSING'].includes(video.status))cookingVideoPoll=setTimeout(()=>syncCookingVideo(video.id),12000);
  }
  async function syncCookingVideo(videoId){
    if(!videoId)return;
    try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/recipe-videos/${encodeURIComponent(videoId)}/sync`,{method:'POST',body:'{}'});renderCookingVideo(data.status,data.video);}
    catch(_error){const root=$('cookingVideo');root.hidden=false;const small=document.createElement('small');small.textContent='Roxy volverá a comprobar el video en unos segundos.';root.append(small);cookingVideoPoll=setTimeout(()=>syncCookingVideo(videoId),20000);}
  }
  async function refreshCookingVideo(recipeId){
    try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/recipes/${encodeURIComponent(recipeId)}/video`);renderCookingVideo(data.video&&data.video.status,data.video);}
    catch(_error){renderCookingVideo('',null);}
  }
  function showCooking(data){
    currentCooking=data;
    const total=(data.recipe.steps||[]).length;
    $('cookingTitle').textContent=data.recipe.title;
    $('cookingProgress').textContent=data.session.status==='COMPLETED'?'Receta terminada':`Paso ${data.step_number} de ${total}`;
    $('cookingStep').textContent=data.session.status==='COMPLETED'?'¡Listo! Terminaste la receta. Quedará guardada para cuando quieras repetirla.':data.current_step;
    $('cookingImage').src=recipeImage(data.recipe);
    $('previousStepButton').disabled=data.step_number<=1||data.session.status==='COMPLETED';
    $('nextStepButton').textContent=data.step_number>=total?'Terminar':'Siguiente';
    $('nextStepButton').disabled=data.session.status==='COMPLETED';
    const automaticSeconds=Number(data.suggested_timer_seconds||stepTimerSeconds(data.current_step));if(automaticSeconds)$('timerMinutes').value=String(Math.round(automaticSeconds/6)/10);
    renderCookingTimers();
    clearInterval(cookingTimerTick);
    cookingTimerTick=setInterval(renderCookingTimers,1000);
    if(!$('cookingDialog').open)$('cookingDialog').showModal();
    if(currentCookingVideo)renderCookingVideo(currentCookingVideo.status,currentCookingVideo);
  }
  function stepTimerSeconds(step){
    const text=normalizedStepText(step);let seconds=0;const patterns=[{regex:/(\d+(?:[.,]\d+)?)\s*(?:horas?|hrs?|h)\b/g,factor:3600},{regex:/(\d+(?:[.,]\d+)?)\s*(?:minutos?|mins?|min)\b/g,factor:60},{regex:/(\d+(?:[.,]\d+)?)\s*(?:segundos?|segs?|seg|s)\b/g,factor:1}];
    patterns.forEach(({regex,factor})=>{for(const match of text.matchAll(regex))seconds+=Number(String(match[1]).replace(',','.'))*factor});return Math.round(seconds);
  }
  function timerRemaining(timer){return Math.max(0,Math.ceil((new Date(timer.ends_at).getTime()-Date.now())/1000))}
  function renderCookingTimers(){
    const root=$('cookingTimers');root.replaceChildren();
    const timers=((currentCooking&&currentCooking.session&&currentCooking.session.timers)||[]).filter(timer=>timer.status==='ACTIVE'||timer.status==='FINISHED');
    if(!timers.length){const small=document.createElement('small');small.textContent='No hay temporizadores activos.';root.append(small);return}
    timers.forEach(timer=>{
      const remaining=timer.status==='FINISHED'?0:timerRemaining(timer);
      const row=document.createElement('div');row.className=`timer-row${remaining===0?' finished':''}`;
      const copy=document.createElement('span');const strong=document.createElement('strong');strong.textContent=timer.label||'Temporizador';const value=document.createElement('small');value.textContent=remaining===0?'Terminado':`${String(Math.floor(remaining/60)).padStart(2,'0')}:${String(remaining%60).padStart(2,'0')}`;copy.append(strong,value);row.append(copy);
      if(remaining>0)row.append(makeButton('Cancelar','delete',()=>cancelCookingTimer(timer.id),`Cancelar ${timer.label||'temporizador'}`));
      root.append(row);
      if(remaining===0&&!announcedTimers.has(timer.id)){announcedTimers.add(timer.id);announce(`${timer.label||'Temporizador'} terminado`);if('vibrate'in navigator)navigator.vibrate([200,100,200]);if('speechSynthesis'in window){const alert=new SpeechSynthesisUtterance(`${timer.label||'Temporizador'} terminado`);alert.lang='es-US';speechSynthesis.speak(alert)}}
    });
  }
  async function createCookingTimer(seconds,label,{automatic=false}={}){
    if(!currentCooking||!(seconds>0))return false;const stepNumber=Number(currentCooking.step_number||1);const marker=`Paso ${stepNumber} ·`;
    if(automatic&&((currentCooking.session.timers)||[]).some(timer=>String(timer.label||'').startsWith(marker)))return false;
    const button=$('startTimerButton');button.disabled=true;
    try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/cooking-sessions/${encodeURIComponent(currentCooking.session.id)}/timers`,{method:'POST',body:JSON.stringify({duration_seconds:Math.round(seconds),label})});showCooking(data);announce(automatic?`Roxy inició el temporizador del paso ${stepNumber}`:'Temporizador iniciado');return true}catch(error){announce(error.message);return false}finally{button.disabled=false}
  }
  async function startCookingTimer(){
    if(!currentCooking)return;const minutes=Number($('timerMinutes').value);if(!(minutes>0)){announce('Indica cuántos minutos');return}
    await createCookingTimer(minutes*60,`Temporizador de ${minutes} min`);
  }
  async function startAutomaticStepTimer(){
    if(!currentCooking||currentCooking.session.status==='COMPLETED')return;const seconds=Number(currentCooking.suggested_timer_seconds||stepTimerSeconds(currentCooking.current_step));if(!(seconds>0))return;
    const minutes=seconds/60;await createCookingTimer(seconds,`Paso ${currentCooking.step_number} · ${Number.isInteger(minutes)?minutes:minutes.toFixed(1)} min`,{automatic:true});
  }
  async function cancelCookingTimer(timerId){
    if(!currentCooking)return;
    try{await api(`/v1/home-food/${encodeURIComponent(user)}/cooking-sessions/${encodeURIComponent(currentCooking.session.id)}/timers/${encodeURIComponent(timerId)}`,{method:'DELETE'});await resumeCooking(currentCooking.session.id);announce('Temporizador cancelado')}catch(error){announce(error.message)}
  }
  async function updateCooking(action){
    if(!currentCooking)return;
    try{
      const data=await api(`/v1/home-food/${encodeURIComponent(user)}/cooking-sessions/${encodeURIComponent(currentCooking.session.id)}`,{method:'POST',body:JSON.stringify({action})});
      showCooking(data);await load({quiet:true});
      if(['next','previous'].includes(action)&&data.session.status!=='COMPLETED')speakCurrentStep();
    }catch(error){announce(error.message);}
  }
  async function speakCurrentStep(){
    if(!currentCooking)return;
    const button=$('speakStepButton');const original=button.textContent;button.disabled=true;button.textContent='Roxy hablando…';
    try{
      if(roxyStepAudio){roxyStepAudio.pause();stopSynchronizedStepVideo();roxyStepAudio=null}
      const response=await fetch(`/v1/home-food/${encodeURIComponent(user)}/cooking-sessions/${encodeURIComponent(currentCooking.session.id)}/speech`,{method:'POST',credentials:'include',cache:'no-store',headers:{Accept:'audio/mpeg'}});
      if(!response.ok){let detail='';try{detail=String((await response.json()).detail||'')}catch(_error){}throw new Error(detail||`HTTP ${response.status}`)}
      const url=URL.createObjectURL(await response.blob());const audio=new Audio(url);roxyStepAudio=audio;audio.addEventListener('ended',()=>{stopSynchronizedStepVideo(true);URL.revokeObjectURL(url);if(roxyStepAudio===audio)roxyStepAudio=null;startAutomaticStepTimer()},{once:true});audio.addEventListener('error',()=>{stopSynchronizedStepVideo();URL.revokeObjectURL(url)},{once:true});await startSynchronizedStepVideo(audio);
    }catch(error){
      const speech=currentCooking.session.status==='COMPLETED'?'Receta terminada. Buen provecho.':`Paso ${currentCooking.step_number}. ${currentCooking.current_step}`;
      if(roxyVoiceConversation&&typeof roxyVoiceConversation.sendUserMessage==='function'){roxyVoiceConversation.sendUserMessage(`[LECTURA DE RECETA. NO LLAMES HERRAMIENTAS.] Lee exactamente con la voz oficial de Roxy: ${speech}`);announce('Roxy leerá el paso en la conversación')}
      else announce(error.message||'No pude conectar la voz oficial de Roxy');
    }finally{button.disabled=false;button.textContent=original}
  }

  function populateHomeForms(){
    const profile=homeFood.profile||{};
    $('homePreferences').value=(profile.preferences||[]).join(', ');
    $('homeAllergies').value=(profile.allergies||[]).join(', ');
    $('homeDislikes').value=(profile.dislikes||[]).join(', ');
    $('homeHousehold').value=profile.household_size||1;
    $('pantryItems').value=(homeFood.pantry||[]).map(row=>`${row.name}, ${row.quantity}, ${row.unit}`).join('\n');
    const shoppingProfile=commerce.profile||{};
    $('commerceObjective').value=shoppingProfile.objective||'balanced';
    $('commerceOrganic').value=shoppingProfile.organic_preference||'no_preference';
    $('commerceRetailers').value=(shoppingProfile.favorite_retailers||[]).join(', ');
    $('commerceBrands').value=(shoppingProfile.favorite_brands||[]).join(', ');
    $('commerceAvoidedBrands').value=(shoppingProfile.avoided_brands||[]).join(', ');
    $('commerceDietary').value=(shoppingProfile.dietary_labels||[]).join(', ');
    $('commercePostalCode').value=shoppingProfile.postal_code||'';
    $('commerceSubstitutions').checked=shoppingProfile.allow_substitutions!==false;
  }
  const commaList=value=>String(value||'').split(',').map(row=>row.trim()).filter(Boolean);
  async function saveHomeProfile(event){event.preventDefault();try{await api(`/v1/home-food/${encodeURIComponent(user)}/profile`,{method:'PUT',body:JSON.stringify({preferences:commaList($('homePreferences').value),allergies:commaList($('homeAllergies').value),dislikes:commaList($('homeDislikes').value),household_size:Number($('homeHousehold').value||1)})});announce('Preferencias guardadas en Roxy Home');await load({quiet:true});}catch(error){announce(error.message)}}
  async function saveCommerceProfile(event){event.preventDefault();try{await api(`/v1/home-commerce/${encodeURIComponent(user)}/profile`,{method:'PUT',body:JSON.stringify({objective:$('commerceObjective').value,organic_preference:$('commerceOrganic').value,favorite_retailers:commaList($('commerceRetailers').value),favorite_brands:commaList($('commerceBrands').value),avoided_brands:commaList($('commerceAvoidedBrands').value),dietary_labels:commaList($('commerceDietary').value),allow_substitutions:$('commerceSubstitutions').checked,postal_code:$('commercePostalCode').value.trim()})});announce('Tu perfil personal de compra quedó guardado');await load({quiet:true})}catch(error){announce(error.message)}}
  async function savePantry(event){event.preventDefault();const items=$('pantryItems').value.split('\n').map(line=>{const [name,quantity='1',unit='unidad']=line.split(',').map(value=>value.trim());return{name,quantity:Number(quantity)||1,unit:unit||'unidad'}}).filter(row=>row.name);try{await api(`/v1/home-food/${encodeURIComponent(user)}/pantry`,{method:'PUT',body:JSON.stringify({items})});announce('Despensa actualizada');await load({quiet:true});}catch(error){announce(error.message)}}
  async function createRecipe(event){
    event.preventDefault();const button=$('recipeSubmit');button.disabled=true;button.textContent='Roxy está creando…';
    try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/recipes`,{method:'POST',body:JSON.stringify({prompt:$('recipePrompt').value,mode:$('recipeMode').value})});$('recipePrompt').value='';await load({quiet:true});renderRecipes();openRecipe(data.recipe);announce(data.generation_mode==='local_recipe_catalog'?'Receta común creada desde el recetario local, sin gastar una consulta de OpenAI':'Receta especial creada con OpenAI y guardada en Mis recetas');}
    catch(error){announce(error.message)}finally{button.disabled=false;button.textContent='Crear con Roxy'}
  }
  async function createRecipeFromPantry(){
    const pantry=homeFood.pantry||[];
    if(!pantry.length){selectPanel('pantry');announce('Guarda primero lo que tienes en la despensa');return}
    const button=$('pantryRecipeButton');button.disabled=true;button.textContent='Roxy está combinando…';
    const available=pantry.map(row=>`${row.quantity} ${row.unit} de ${row.name}`).join(', ');
    try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/recipes`,{method:'POST',body:JSON.stringify({prompt:`Crea una receta práctica usando principalmente estos ingredientes de mi despensa: ${available}. Minimiza lo que falte comprar, respeta mi perfil y señala sustituciones útiles.`,mode:'routine'})});await load({quiet:true});selectPanel('recipes');openRecipe(data.recipe);announce(data.generation_mode==='local_recipe_catalog'?'Receta guardada desde el recetario local':'Receta creada con tu despensa')}catch(error){announce(error.message)}finally{button.disabled=false;button.textContent='Crear una receta con lo que tengo'}
  }
  async function createBeverage(event){
    event.preventDefault();const button=$('beverageSubmit');button.disabled=true;button.textContent='Roxy está mezclando…';
    const type=$('beverageType').value;const safety=type==='alcoholic'?'Es una bebida para adultos: identifica claramente cada ingrediente alcohólico y ofrece una variante sin alcohol.':'No uses ningún ingrediente con alcohol.';
    try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/recipes`,{method:'POST',body:JSON.stringify({prompt:`Prepara esta bebida: ${$('beveragePrompt').value}. ${safety}`,mode:'routine',recipe_type:type})});$('beveragePrompt').value='';await load({quiet:true});openRecipe(data.recipe);announce(data.generation_mode==='local_recipe_catalog'?'Bebida preparada desde el recetario local, sin gastar una consulta de OpenAI':type==='alcoholic'?'Bebida especial con alcohol guardada':'Bebida especial sin alcohol guardada')}catch(error){announce(error.message)}finally{button.disabled=false;button.textContent='Crear bebida'}
  }
  async function createSubstitution(event){event.preventDefault();const root=$('substitutionResult');root.replaceChildren();root.hidden=false;try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/substitutions`,{method:'POST',body:JSON.stringify({prompt:$('substitutionPrompt').value,mode:'routine'})});const title=document.createElement('h3');title.textContent='Sustitución de Roxy';const copy=document.createElement('p');copy.textContent=data.result.answer||data.result.explanation||JSON.stringify(data.result.substitutions||data.result);root.append(title,copy)}catch(error){root.hidden=true;announce(error.message)}}
  function renderPlan(plan){const root=$('weeklyPlanResult');root.replaceChildren();root.hidden=false;const title=document.createElement('h3');title.textContent='Plan semanal';root.append(title);(plan.days||[]).forEach(day=>{const heading=document.createElement('strong');heading.textContent=day.day||'Día';root.append(heading);addTextList(root,day.meals||[])})}
  async function createWeeklyPlan(event){event.preventDefault();try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/weekly-plans`,{method:'POST',body:JSON.stringify({prompt:$('weeklyPlanPrompt').value,mode:'routine'})});renderPlan(data.plan)}catch(error){announce(error.message)}}
  function renderSafety(result){const root=$('foodSafetyResult');root.replaceChildren();root.hidden=false;const title=document.createElement('h3');title.textContent='Investigación vigente';const answer=document.createElement('p');answer.textContent=result.answer||'No se encontró una respuesta concluyente.';root.append(title,answer);const sources=(result.sources||[]).filter(row=>row&&/^https?:\/\//.test(String(row.url||'')));if(sources.length){const list=document.createElement('ul');list.className='source-list';sources.forEach(source=>{const item=document.createElement('li');const link=document.createElement('a');link.href=source.url;link.target='_blank';link.rel='noopener noreferrer';link.textContent=source.title||source.authority||source.url;item.append(link);list.append(item)});root.append(list)}}
  async function researchFoodSafety(event){event.preventDefault();try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/food-safety`,{method:'POST',body:JSON.stringify({question:$('foodSafetyQuestion').value})});renderSafety(data.result)}catch(error){announce(error.message)}}

  function submitCustom(event){event.preventDefault();const name=$('customName').value.trim();const quantity=Number($('customQuantity').value);const unit=$('customUnit').value.trim();if(!name||!unit||!(quantity>0)){announce('Completa producto, cantidad y unidad');return}addItem({name,quantity,unit,category:$('customCategory').value});$('customForm').reset();$('customQuantity').value='1';$('customUnit').value='unidad';$('customDialog').close()}
  async function pair(event){event.preventDefault();const token=$('apiToken').value;const candidate=$('userId').value.trim()||'local_user';$('pairError').textContent='';try{await api(`/v1/shopping/session/${encodeURIComponent(candidate)}`,{method:'POST',headers:{Authorization:`Bearer ${token}`}});user=candidate;localStorage.setItem('roxyShoppingUser',user);$('apiToken').value='';$('pairDialog').close();await load()}catch(error){$('pairError').textContent=error.message}}
  async function login(event){event.preventDefault();$('loginError').textContent='';try{const result=await api('/v1/home-account/login',{method:'POST',body:JSON.stringify({username:$('loginUsername').value.trim(),password:$('loginPassword').value})});account=result;user=result.storage_user_id;localStorage.setItem('roxyShoppingUser',user);$('loginPassword').value='';$('pairDialog').close();await load()}catch(error){$('loginError').textContent=error.message}}
  function renderAccount(){const person=activePersonName();$('accountSummary').textContent=account.mode==='member'?`${person} · ${account.household_name} · la compra, recetas y despensa son compartidas.`:account.requires_profile_setup?'Este dispositivo usa el acceso anterior. Crea los perfiles personales sin perder los datos actuales.':'Los perfiles ya existen. Entra con tu usuario para que Roxy sepa quién eres.';$('accountButton').textContent=account.mode==='member'?'Administrar personas':account.requires_profile_setup?'Crear perfiles personales':'Entrar con mi perfil'}
  function renderMembers(rows){const root=$('accountMembers');root.replaceChildren();rows.forEach(row=>{const article=document.createElement('article');article.className='member-row';const copy=document.createElement('div');const strong=document.createElement('strong');strong.textContent=row.display_name;const small=document.createElement('small');small.textContent=`@${row.username}`;copy.append(strong,small);const role=document.createElement('span');role.textContent=row.role==='OWNER'?'ADMINISTRA':'MIEMBRO';article.append(copy,role);root.append(article)})}
  async function openAccountDialog(){if(account.mode!=='member'&&!account.requires_profile_setup){$('pairDialog').showModal();return}const bootstrap=account.mode!=='member';$('bootstrapAccountForm').hidden=!bootstrap;$('memberManagement').hidden=bootstrap;$('accountDialog').showModal();if(bootstrap){$('ownerDisplayName').value=greetingName;return}try{const result=await api('/v1/home-account/members');renderMembers(result.members||[]);$('addMemberForm').hidden=account.role!=='OWNER'}catch(error){announce(error.message)}}
  async function bootstrapAccount(event){event.preventDefault();$('bootstrapAccountError').textContent='';try{const result=await api('/v1/home-account/bootstrap',{method:'POST',body:JSON.stringify({household_name:$('householdName').value.trim(),display_name:$('ownerDisplayName').value.trim(),username:$('ownerUsername').value.trim(),password:$('ownerPassword').value,storage_user_id:user})});account=result;$('ownerPassword').value='';$('accountDialog').close();await load();announce(`Bienvenido, ${result.display_name}. Tus datos siguen en el hogar compartido.`)}catch(error){$('bootstrapAccountError').textContent=error.message}}
  async function addHouseholdMember(event){event.preventDefault();$('memberError').textContent='';try{const result=await api('/v1/home-account/members',{method:'POST',body:JSON.stringify({display_name:$('memberDisplayName').value.trim(),username:$('memberUsername').value.trim(),password:$('memberPassword').value})});$('addMemberForm').reset();const members=await api('/v1/home-account/members');renderMembers(members.members||[]);announce(`Perfil de ${result.member.display_name} creado`)}catch(error){$('memberError').textContent=error.message}}
  function complete(){const rows=activeItems();if(!rows.length)return;$('confirmCopy').textContent=`Se archivarán ${rows.length} productos y quedarán en el historial.`;$('confirmDialog').showModal()}
  async function confirmComplete(){const rows=activeItems();$('confirmDialog').close();await mutate({path:`/v1/shopping/${encodeURIComponent(user)}/complete`,options:{method:'POST'}},()=>{snapshot.history=[{id:`offline-${crypto.randomUUID()}`,completed_at:now(),item_count:rows.length,total_quantity:rows.reduce((n,item)=>n+Number(item.quantity||0),0),items:rows},...(snapshot.history||[])];snapshot.items=snapshot.items.filter(item=>!rows.includes(item));announce('Compra archivada')})}
  async function share(){const rows=activeItems();const text='Lista de compras de Roxy\n'+(rows.length?rows.map(item=>`${item.quantity} ${item.unit||'unidad'} · ${item.name}`).join('\n'):'Lista vacía');try{if(navigator.share)await navigator.share({title:'Lista de compras',text,url:location.href});else{await navigator.clipboard.writeText(text);announce('Lista copiada')}}catch(error){if(error.name!=='AbortError')announce('No se pudo compartir')}}
  async function disconnect(){try{await api('/v1/shopping/session',{method:'DELETE'});}catch(_error){}localStorage.removeItem('roxyShoppingUser');location.reload()}

  async function submitRoxyCommand(event){
    event.preventDefault();const input=$('roxyCommand');const command=input.value.trim();if(!command)return;
    const button=event.currentTarget.querySelector('button');button.disabled=true;button.textContent='…';
    try{const result=await sendRoxyHomeCommand({command});input.value='';announce(result.message||'Listo');if(result.data&&result.data.recipe){await load({quiet:true});selectPanel('recipes');openRecipe(result.data.recipe)}if(result.data&&result.data.cooking){await load({quiet:true});showCooking(result.data.cooking)}}catch(error){announce(error.message)}finally{button.disabled=false;button.textContent='Enviar'}
  }

  let roxyVoiceConversation=null;let roxyVoiceStarting=false;let roxyElevenLabsModule=null;let roxyVoicePermissionStream=null;let roxyLastAgentMessage='';let roxyLastAgentMessageAt=0;
  const roxyVoiceUrls=['https://esm.sh/@elevenlabs/client@1.8.1?bundle','https://cdn.jsdelivr.net/npm/@elevenlabs/client@1.8.1/+esm','https://esm.run/@elevenlabs/client@1.8.1'];
  function roxyVoiceStatus(text,error=false){$('roxyVoiceStatus').textContent=text;$('roxyVoiceStatus').classList.toggle('error',error)}
  function roxyVoiceTranscript(text,source='Roxy'){$('roxyVoiceTranscript').textContent=`${source}: ${text}`}
  function stopRoxyPermissionStream(){if(!roxyVoicePermissionStream)return;roxyVoicePermissionStream.getTracks().forEach(track=>track.stop());roxyVoicePermissionStream=null}
  function roxyVoiceError(error,phase){const name=String(error&&error.name||'Error').replace(/[^A-Za-z]/g,'').slice(0,32)||'Error';if(name==='NotAllowedError'||name==='SecurityError')return'Safari no tiene permiso para usar el micrófono. Actívalo en los ajustes del sitio.';if(name==='NotFoundError')return'El iPhone no encontró un micrófono disponible.';if(name==='NotReadableError'||name==='AbortError')return'El micrófono está ocupado por otra aplicación. Ciérrala y vuelve a intentar.';return`No pude iniciar ElevenLabs en la etapa ${phase} (${name}). Pulsa iniciar para reintentar.`}
  function openRoxyVoice(){$('roxyVoicePanel').hidden=false;$('roxyVoiceLauncher').setAttribute('aria-expanded','true');$('roxyVoiceLauncher').classList.add('active');$('roxyVoiceStart').focus()}
  function closeRoxyVoice(){$('roxyVoicePanel').hidden=true;$('roxyVoiceLauncher').setAttribute('aria-expanded','false');$('roxyVoiceLauncher').classList.remove('active');$('roxyVoiceLauncher').focus()}
  async function loadElevenLabs(){if(roxyElevenLabsModule)return roxyElevenLabsModule;let lastError=null;for(const url of roxyVoiceUrls){try{roxyElevenLabsModule=await import(url);return roxyElevenLabsModule}catch(error){lastError=error}}throw lastError||new Error('ElevenLabs SDK no disponible')}
  function currentShoppingSummary(){const rows=activeItems();return{pending_count:rows.length,total_quantity:rows.reduce((total,item)=>total+Number(item.quantity||0),0),items:rows.slice(0,50).map(item=>({name:item.name,quantity:item.quantity,unit:item.unit,category:item.category}))}}
  async function sendRoxyHomeCommand(parameters={}){const command=String(parameters.command||parameters.text||parameters.request||'').trim();if(!command)return{ok:false,error:'missing_command'};const result=await api(`/v1/assistant/command/${encodeURIComponent(user)}`,{method:'POST',body:JSON.stringify({text:command})});await load({quiet:true});if(result.message)roxyVoiceTranscript(result.message);if(result.data&&result.data.cooking)showCooking(result.data.cooking);if(result.data&&result.data.preparation){currentPreparation=result.data.preparation;renderCommercePreparation(currentPreparation,result.data.providers||commerce.providers||[]);if(!$('commerceDialog').open)$('commerceDialog').showModal()}return result}
  function recoverRoxyVoiceSpeech(speech,startedAt){setTimeout(()=>{if(!roxyVoiceConversation||!speech)return;const answer=String(roxyLastAgentMessage||'').toLowerCase();const falseFailure=/no (?:puedo|tengo acceso)|no (?:est[aá]|estaba) funcionando|b[uú]squeda.{0,30}recet|problema.{0,30}recet/.test(answer);if(roxyLastAgentMessageAt<=startedAt||falseFailure){const instruction=`[RESULTADO CONFIRMADO DE ROXY HOME. NO LLAMES HERRAMIENTAS.] Lee en voz alta exactamente este resultado completo y después pregunta si deseo agregar los ingredientes o cocinar paso a paso: ${speech}`;if(typeof roxyVoiceConversation.sendUserMessage==='function')roxyVoiceConversation.sendUserMessage(instruction)}},3200)}
  async function sendCommandToRoxyOSForVoice(parameters={}){const startedAt=Date.now();const result=await sendRoxyHomeCommand(parameters);const speech=String(result.speech||result.message||'').trim();recoverRoxyVoiceSpeech(speech,startedAt);return{ok:Boolean(result.ok),intent:result.intent||'general',must_speak:true,speech,message:speech,data:result.data||{},instruction:'Espera a que termine esta herramienta. Lee en voz alta ahora el campo speech completo. No lo resumas, no lo contradigas y no digas que no tienes acceso.'}}
  function roxyHomeClientTools(){return{getCurrentScreenContext:async()=>({ok:true,app:'Roxy Home',page:'Lista de compras y recetas',provider:'ElevenLabs',member:{display_name:activePersonName(),role:account.role,household_name:account.household_name},shopping_list:currentShoppingSummary(),latest_recipe:currentRecipe&&{id:currentRecipe.id,title:currentRecipe.title,servings:currentRecipe.servings},instruction:'Eres la misma Roxy, operando únicamente con memoria y permisos de Home. Usa los datos reales de esta pantalla.'}),getShoppingList:async()=>({ok:true,shopping_list:currentShoppingSummary()}),summarizeCurrentScreen:async()=>({ok:true,summary:`Roxy Home muestra ${activeItems().length} productos pendientes y ${(homeFood.recipes||[]).length} recetas guardadas.`,shopping_list:currentShoppingSummary()}),sendCommandToRoxyOS:sendCommandToRoxyOSForVoice}}
  function roxyHomeOverrides(){const shopping=JSON.stringify(currentShoppingSummary());const person=activePersonName();const greeting=person?`Hola, ${person}. Soy Roxy y estoy contigo en Roxy Home. ¿Qué necesitas?`:'Hola, soy Roxy. Estoy contigo en Roxy Home. ¿Qué necesitas?';return{agent:{language:'es',firstMessage:greeting,prompt:{prompt:`Eres Roxy, con la misma identidad y voz del ecosistema Roxy, operando únicamente dentro de Roxy Home. La aplicación actual es Roxy Home, en las secciones Compra, Recetas y Despensa. Estás hablando con ${person||'una persona del hogar'}; dirígete a esa persona por su nombre de forma natural, especialmente al saludar y confirmar acciones. Habla en español natural, cálido y directo. Mantén la conversación abierta después del saludo, escucha la respuesta del usuario y nunca uses end_call salvo que el usuario diga claramente terminar o adiós. La lista visible actual es ${shopping}. Usa getShoppingList antes de afirmar qué productos hay. Para pedir una receta, agregar o quitar artículos, consultar la lista, preparar la compra para elegir un comercio, agregar ingredientes o guiar una receta paso a paso, siempre usa sendCommandToRoxyOS. No respondas antes de que la herramienta termine. La herramienta es tu acceso real a las recetas y a la lista: nunca digas que no puedes acceder a ellas. Cuando termine, lee en voz alta exactamente el campo speech completo; que el texto aparezca en pantalla no cuenta como haberlo dicho. Después puedes preguntar si desea agregar los ingredientes o empezar la guía paso a paso. Si recibes un mensaje que comienza con RESULTADO CONFIRMADO DE ROXY HOME, no vuelvas a llamar herramientas: lee literalmente el resultado incluido. Para cocinar guiado reconoce guíame, siguiente paso, paso anterior, repite, pon un temporizador y cuánto tiempo queda. Expresiones como quita, saca, remueve o ya no necesito son órdenes de eliminación. Conserva cantidades y unidades naturales como paquetes, botellas, bolsas, kilos, gramos y docenas. Puedes preparar enlaces de compra para revisión, pero nunca afirmar que compraste, pagar ni finalizar una orden. No simules cambios. No inventes elementos de la lista, recetas, precios, disponibilidad ni alergias. No controles dispositivos. No uses memoria, secretos ni herramientas de Trading, Finanzas o Study.`}}}}
  async function startRoxyVoice(){if(roxyVoiceConversation||roxyVoiceStarting)return;openRoxyVoice();roxyVoiceStarting=true;roxyLastAgentMessage='';roxyLastAgentMessageAt=0;$('roxyVoiceStart').disabled=true;let phase='configuración';roxyVoiceStatus('Conectando con ElevenLabs…');try{if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia)throw new DOMException('Micrófono no disponible','NotFoundError');phase='permiso del micrófono';roxyVoicePermissionStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});const config=await api(`/v1/assistant/session/${encodeURIComponent(user)}`);phase='carga del agente';const eleven=await loadElevenLabs();const Conversation=eleven.Conversation||(eleven.default&&eleven.default.Conversation);if(!Conversation||!Conversation.startSession)throw new Error('SDK de ElevenLabs no disponible');phase='conexión de voz';const options={connectionType:'websocket',overrides:roxyHomeOverrides(),dynamicVariables:{...(config.dynamic_variables||{}),shopping_list_json:JSON.stringify(currentShoppingSummary())},clientTools:roxyHomeClientTools(),onConnect:()=>{roxyVoiceStarting=false;roxyVoiceStatus('Roxy te está escuchando');$('roxyVoiceStart').disabled=true;$('roxyVoiceEnd').disabled=false},onDisconnect:details=>{console.info('Roxy Home ElevenLabs disconnected',details||'normal');stopRoxyPermissionStream();roxyVoiceConversation=null;roxyVoiceStarting=false;const endedByAgent=details&&details.reason==='agent';roxyVoiceStatus(endedByAgent?'Roxy terminó la llamada antes de tiempo. Pulsa iniciar para reconectar.':'Conversación terminada',endedByAgent);$('roxyVoiceStart').disabled=false;$('roxyVoiceEnd').disabled=true},onError:error=>{console.warn('Roxy Home ElevenLabs error',error);stopRoxyPermissionStream();roxyVoiceStarting=false;roxyVoiceStatus(roxyVoiceError(error,'conversación'),true);$('roxyVoiceStart').disabled=false;$('roxyVoiceEnd').disabled=true},onModeChange:mode=>{const state=String(mode&&mode.mode||mode||'').toLowerCase();if(state.includes('speaking'))roxyVoiceStatus('Roxy está respondiendo');else if(state.includes('listening'))roxyVoiceStatus('Roxy te está escuchando')},onMessage:message=>{const source=String(message&&((message.source||message.role||message.type))||'').toLowerCase();const text=message&&(message.message||message.text||message.transcript||message.content||(message.agent_response_event&&message.agent_response_event.agent_response)||(message.user_transcription_event&&message.user_transcription_event.user_transcript));if(typeof text==='string'&&text.trim()){const fromUser=source.includes('user');if(!fromUser){roxyLastAgentMessage=text.trim();roxyLastAgentMessageAt=Date.now()}roxyVoiceTranscript(text.trim(),fromUser?'Tú':'Roxy')}}};if(config.conversation_token)options.conversationToken=config.conversation_token;else options.agentId=config.agent_id;roxyVoiceConversation=await Conversation.startSession(options);stopRoxyPermissionStream()}catch(error){console.warn('Roxy Home ElevenLabs start failed',error);stopRoxyPermissionStream();roxyVoiceConversation=null;roxyVoiceStarting=false;roxyVoiceStatus(roxyVoiceError(error,phase),true);$('roxyVoiceStart').disabled=false;$('roxyVoiceEnd').disabled=true}}
  async function endRoxyVoice(){const conversation=roxyVoiceConversation;roxyVoiceConversation=null;stopRoxyPermissionStream();if(conversation&&typeof conversation.endSession==='function'){try{await conversation.endSession()}catch(error){console.warn('Roxy Home ElevenLabs end failed',error)}}roxyVoiceStarting=false;roxyVoiceStatus('Conversación terminada');$('roxyVoiceStart').disabled=false;$('roxyVoiceEnd').disabled=true}

  function render(){renderShopping();renderRecipes()}
  function bind(){
    $('searchInput').addEventListener('input',event=>{search=event.target.value;renderShopping()});
    $('toggleStaples').addEventListener('click',()=>{showAllStaples=!showAllStaples;renderShopping()});
    $('focusListButton').addEventListener('click',()=>$('shoppingList').scrollIntoView({behavior:'smooth',block:'start'}));
    $('customForm').addEventListener('submit',submitCustom);
    $('pairForm').addEventListener('submit',pair);
    $('loginForm').addEventListener('submit',login);
    $('accountButton').addEventListener('click',openAccountDialog);
    $('bootstrapAccountForm').addEventListener('submit',bootstrapAccount);
    $('addMemberForm').addEventListener('submit',addHouseholdMember);
    $('completeButton').addEventListener('click',complete);
    $('confirmComplete').addEventListener('click',confirmComplete);
    $('shareButton').addEventListener('click',share);
    $('disconnectButton').addEventListener('click',disconnect);
    $('homeProfileForm').addEventListener('submit',saveHomeProfile);
    $('commerceProfileForm').addEventListener('submit',saveCommerceProfile);
    $('prepareShoppingButton').addEventListener('click',()=>preparePurchase('shopping'));
    $('commerceConfirmCheck').addEventListener('change',()=>{$('commerceConfirmButton').disabled=!$('commerceConfirmCheck').checked});
    $('commerceConfirmCancel').addEventListener('click',()=>{pendingCommerceProvider=null;$('commerceConfirmation').hidden=true});
    $('commerceConfirmButton').addEventListener('click',confirmProviderHandoff);
    $('pantryForm').addEventListener('submit',savePantry);
    $('recipeForm').addEventListener('submit',createRecipe);
    $('beverageForm').addEventListener('submit',createBeverage);
    $('pantryRecipeButton').addEventListener('click',createRecipeFromPantry);
    $('recipePersonalForm').addEventListener('submit',saveRecipePersonalization);
    $('deleteRecipeButton').addEventListener('click',deleteCurrentRecipe);
    $('substitutionForm').addEventListener('submit',createSubstitution);
    $('weeklyPlanForm').addEventListener('submit',createWeeklyPlan);
    $('foodSafetyForm').addEventListener('submit',researchFoodSafety);
    $('roxyCommandForm').addEventListener('submit',submitRoxyCommand);
    $('greetingSettingsButton').addEventListener('click',()=>account.mode==='member'?openAccountDialog():openGreetingSettings());
    $('greetingForm').addEventListener('submit',saveGreeting);
    $('clearGreetingButton').addEventListener('click',clearGreeting);
    $('roxyVoiceLauncher').addEventListener('click',openRoxyVoice);
    $('roxyVoiceClose').addEventListener('click',closeRoxyVoice);
    $('roxyVoiceStart').addEventListener('click',startRoxyVoice);
    $('roxyVoiceEnd').addEventListener('click',endRoxyVoice);
    $('previousStepButton').addEventListener('click',()=>updateCooking('previous'));
    $('nextStepButton').addEventListener('click',()=>updateCooking('next'));
    $('speakStepButton').addEventListener('click',speakCurrentStep);
    $('startTimerButton').addEventListener('click',startCookingTimer);
    document.querySelectorAll('[data-tab-link]').forEach(button=>button.addEventListener('click',event=>{event.preventDefault();selectPanel(button.dataset.tabLink)}));
    document.querySelectorAll('[data-open-custom]').forEach(button=>button.addEventListener('click',()=>$('customDialog').showModal()));
    document.querySelectorAll('[data-close-dialog]').forEach(button=>button.addEventListener('click',()=>$(button.dataset.closeDialog).close()));
    document.querySelectorAll('[data-recipe-filter]').forEach(button=>button.addEventListener('click',()=>{recipeFilter=button.dataset.recipeFilter;document.querySelectorAll('[data-recipe-filter]').forEach(row=>row.classList.toggle('active',row===button));renderRecipes()}));
    $('installButton').addEventListener('click',async()=>{if(installPrompt){installPrompt.prompt();await installPrompt.userChoice;installPrompt=null;$('installButton').hidden=true}});
    window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installPrompt=event;$('installButton').hidden=false});
    window.addEventListener('online',()=>load({quiet:true}));
  }

  bind();renderHomeMoment();setInterval(renderHomeMoment,30000);render();load();
  if('serviceWorker'in navigator&&(location.protocol==='https:'||location.hostname==='localhost')){
    const homeRoute=location.pathname.startsWith('/home');
    navigator.serviceWorker.register(homeRoute?'/home-sw.js':'/lista-sw.js',{scope:homeRoute?'/home':'/lista',updateViaCache:'none'}).catch(()=>{});
  }
})();
