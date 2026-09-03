(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const escapeHtml=value=>String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const APP_VERSION = '150';
  const now = () => new Date().toISOString();
  const categories = {ALL:'Todo',FOOD:'Alimentos',CLEANING:'Limpieza',PERSONAL:'Aseo personal',HEALTH:'Salud y farmacia',HOUSEHOLD:'Hogar y accesorios',PETS:'Mascotas',OTHER:'Otros',GENERAL:'Otros'};
  const categoryOrder = ['FOOD','CLEANING','PERSONAL','HEALTH','HOUSEHOLD','PETS','OTHER'];
  const aisleOrder = ['PRODUCE','DAIRY_EGGS','MEAT_SEAFOOD','BAKERY','PANTRY','BEVERAGES','FROZEN','FOOD','CLEANING','PERSONAL','HEALTH','HOUSEHOLD','BABY','PETS','OTHER'];
  const aisleToCategory = {PRODUCE:'FOOD',DAIRY_EGGS:'FOOD',MEAT_SEAFOOD:'FOOD',BAKERY:'FOOD',PANTRY:'FOOD',BEVERAGES:'FOOD',FROZEN:'FOOD',FOOD:'FOOD',CLEANING:'CLEANING',PERSONAL:'PERSONAL',HEALTH:'HEALTH',HOUSEHOLD:'HOUSEHOLD',BABY:'PERSONAL',PETS:'PETS',OTHER:'OTHER'};
  const aisleLabels = {PRODUCE:'Frutas y vegetales',DAIRY_EGGS:'Lácteos y huevos',MEAT_SEAFOOD:'Carnes y pescados',BAKERY:'Panadería',PANTRY:'Despensa',BEVERAGES:'Bebidas',FROZEN:'Congelados',FOOD:'Otros alimentos',CLEANING:'Limpieza general',PERSONAL:'Cuidado personal',HEALTH:'Farmacia',HOUSEHOLD:'Accesorios del hogar',BABY:'Cuidado del bebé',PETS:'Mascotas',OTHER:'Sin clasificar'};
  const staples = [
    ['Leche','DAIRY_EGGS','litro'],['Huevos','DAIRY_EGGS','docena'],['Queso','DAIRY_EGGS','paquete'],
    ['Pollo','MEAT_SEAFOOD','paquete'],['Tomate','PRODUCE','unidad'],['Aguacate','PRODUCE','unidad'],
    ['Plátanos','PRODUCE','racimo'],['Pan','BAKERY','paquete'],['Arroz','PANTRY','bolsa'],
    ['Café','BEVERAGES','bolsa'],['Aceite','PANTRY','botella'],['Papel higiénico','PERSONAL','paquete'],
    ['Agua','BEVERAGES','paquete'],['Detergente','CLEANING','botella'],['Jabón','PERSONAL','unidad']
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
    'pasta dental':'toothpaste.png', 'pasta de dientes':'toothpaste.png', 'pasta de diente':'toothpaste.png',
    'pasta para dientes':'toothpaste.png', dentifrico:'toothpaste.png', 'crema dental':'toothpaste.png', toothpaste:'toothpaste.png',
    sal:'salt.png', salt:'salt.png', suavizante:'fabric-softener.png', 'fabric softener':'fabric-softener.png',
    vainilla:'vanilla.png', vanilla:'vanilla.png',
    mandarina:'mandarin.png', mandarinas:'mandarin.png', naranja:'mandarin.png', naranjas:'mandarin.png',
    clementina:'mandarin.png', citrico:'mandarin.png', citricos:'mandarin.png',
    'dulce de leche':'dulce-de-leche.png', cajeta:'dulce-de-leche.png', arequipe:'dulce-de-leche.png',
    'ninja ice cream':'ice-cream.png', 'ninja creami':'ice-cream.png',
    'helado de dulce de leche':'ice-cream.png', 'elado de dulce de leche':'ice-cream.png', 'helado dulce de leche':'ice-cream.png', helado:'ice-cream.png', elado:'ice-cream.png', 'ice cream':'ice-cream.png', mantecado:'ice-cream.png',
    azucar:'sugar.png', sugar:'sugar.png',
    'gel de cejas':'eyebrow-gel.png', cejas:'eyebrow-gel.png', 'eyebrow gel':'eyebrow-gel.png',
    medicamento:'medicine.png', medicamentos:'medicine.png', medicina:'medicine.png', medicinas:'medicine.png',
    farmacia:'medicine.png', pastilla:'medicine.png', pastillas:'medicine.png',
    'bolsitas de olor':'scent-sachets.png', 'bolsa de olor':'scent-sachets.png',
    ambientador:'scent-sachets.png', aromatizante:'scent-sachets.png', sachet:'scent-sachets.png',
    'perlas aromaticas para ropa':'laundry-scent-beads.png', 'perlas aromaticas':'laundry-scent-beads.png',
    'perlas de olor':'laundry-scent-beads.png', 'bolitas de olor':'laundry-scent-beads.png',
    'pastillitas de olor':'laundry-scent-beads.png', 'pastillas de olor':'laundry-scent-beads.png',
    'pastillas de home':'laundry-scent-beads.png', 'pastillitas de aroma':'laundry-scent-beads.png',
    'pastillas de aroma':'laundry-scent-beads.png', 'bolitas para lavar ropa':'laundry-scent-beads.png',
    'potenciador de olor':'laundry-scent-beads.png', 'potenciador de aroma':'laundry-scent-beads.png',
    unstoppables:'laundry-scent-beads.png', unstopables:'laundry-scent-beads.png', 'scent booster':'laundry-scent-beads.png',
    'empapadores absorbentes para mascota':'pet-training-pads.png', 'empapadores para mascota':'pet-training-pads.png',
    'empapador para mascota':'pet-training-pads.png', 'pad para luna':'pet-training-pads.png',
    'pads para luna':'pet-training-pads.png', 'pad para bella':'pet-training-pads.png',
    'pads para bella':'pet-training-pads.png', 'pee pad':'pet-training-pads.png', 'pee pads':'pet-training-pads.png',
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
  let homeFood = {profile:{preferences:[],allergies:[],dislikes:[],household_size:1},meal_planning:{style:'normal',cook_days:2,meal_scope:'all',people:2,max_minutes:25,weekly_budget:85},pantry:[],recipes:[],local_recipes:[],cooking_sessions:[],weekly_plans:[]};
  let commerce = {profile:{objective:'balanced',organic_preference:'no_preference',favorite_retailers:[],favorite_brands:[],avoided_brands:[],dietary_labels:[],allow_substitutions:true,postal_code:'',location_enabled:false},providers:[],activity:{handoff_count:0,provider_counts:{},recent:[]},disclosure:''};
  let commerceLocation={enabled:false,latitude:null,longitude:null,accuracy:null};
  let priceRecommendations = null;
  let priceRecommendationsLoading = false;
  let pendingCommerceProvider = null;
  let recipeAudience = 'human';
  let petSpecies = 'dog';
  let selectedPetId = '';
  let petProfileStep = 1;
  let petProfilePhotoData = '';
  let petHubTab = 'care';
  let petRecipeFilter = 'all';
  let petProductFilter = 'all';
  let petMedicalAttachment = null;
  let pendingImportedRecipe = null;
  let currentPreparation = null;
  let user = localStorage.getItem('roxyShoppingUser') || 'local_user';
  let category = 'ALL';
  let recipeFilter = 'breakfast';
  let recipeSearch = '';
  let search = '';
  let showAllStaples = false;
  let busy = false;
  let installPrompt = null;
  let toastTimer = null;
  let currentRecipe = null;
  let currentCooking = null;
  let currentCookingVideo = null;
  let currentWeeklyPlan = null;
  const weeklyPlanReadyDays = new Set();
  let roxyStepAudio = null;
  let cookingVideoPoll = null;
  let cookingTimerTick = null;
  const announcedTimers = new Set();
  let greetingName=String(localStorage.getItem('roxyHomeGreetingName')||'').trim().slice(0,32);
  const appearanceDefaults={theme:'classic',background:'plant',avatar:'home',response_style:'balanced',text_scale:'standard'};
  const appearanceChoices={theme:['classic','olive','coastal','terracotta'],background:['plant','linen','clean','warm'],avatar:['home','professional','monogram'],response_style:['balanced','brief','close','explanatory'],text_scale:['compact','standard','large']};
  const avatarSources={home:'/assets/roxy_home_avatar.jpg',professional:'/assets/roxy_avatar_icon.jpg',monogram:'/assets/roxy_home/avatars/monogram.svg'};
  function cachedAppearance(){try{const value=JSON.parse(localStorage.getItem('roxyHomeAppearance')||'{}');return value&&typeof value==='object'?value:{}}catch(_error){return{}}}
  let appearance={...appearanceDefaults,...cachedAppearance()};
  let account={mode:'checking',display_name:'',storage_user_id:user,role:'',preferences:appearance};
  let homeCalendar={events:[],pending_draft:null,sync:{native_export:true,provider:'ICS'}};
  let homeWeather={status:'LOCATION_REQUIRED',daily:[]};
  let homeDaily=null;
  let homeDesign={projects:[],generation_configured:false};
  let homePlants={plants:[],due_today:[],vacation:{},species:[],identification_configured:false};
  let homeFamily={status:'UNAVAILABLE',members:[],places:[],alerts:[],capabilities:{}};
  let familyWatchId=null,familyMap=null,familyMapMarkers=[],familyRoutes=[],familyMapLoader=null,familyRefreshTimer=null,familyMapZoomListener=null;
  let familyMapViewportInitialized=false,familyHistoryOpen=false,familyHistoryPoints=[];
  let familySelectedMemberId='',familySelectedPlaceId='',familyMapStyle='roadmap',familyDirectionsRenderer=null,familyRouteSnapshot=null,familyRouteMode=false;
  let familyProfilePhotoData='';
  let familyProfileEmoji='';
  let familyWeatherGlobeMap=null,familyWeatherGlobeTimer=null,familyWeatherGlobeFrames=[],familyWeatherGlobeFrameIndex=0,familyWeatherGlobePlaying=true,familyWeatherGlobeLoadId=0,familyRadarMetadata=null,familyRadarFetchedAt=0,familyWeatherGlobeActive=false,familyMapTransitioning=false;
  let currentPlant=null;
  let designPoll=null;
  let calendarView='today';
  let calendarSelectedDate=new Date();
  let calendarDisplayMonth=new Date(calendarSelectedDate.getFullYear(),calendarSelectedDate.getMonth(),1);
  let pendingCalendarDraft=null;
  const familyMarkerColors={FOREST:'#155a3d',GOLD:'#b58a2c',OCEAN:'#28758a',TERRACOTTA:'#a85f43',PLUM:'#735170',SLATE:'#4e6068'};
  const calendarReminderTimers=new Map();
  let calendarAutoSyncRunning=false;

  const activePersonName=()=>String(account.mode==='member'?account.display_name:greetingName||'').trim();
  const safeAppearance=(values={})=>Object.fromEntries(Object.entries(appearanceChoices).map(([key,choices])=>{const value=String(values[key]||appearanceDefaults[key]);return[key,choices.includes(value)?value:appearanceDefaults[key]]}));
  const avatarSrc=()=>avatarSources[appearance.avatar]||avatarSources.home;

  function applyAppearance(values=appearance){
    appearance=safeAppearance(values);localStorage.setItem('roxyHomeAppearance',JSON.stringify(appearance));
    const root=document.documentElement;root.dataset.theme=appearance.theme;root.dataset.background=appearance.background;root.dataset.textScale=appearance.text_scale;
    const themeColors={classic:'#173f2b',olive:'#425d3a',coastal:'#285969',terracotta:'#754533'};const meta=document.querySelector('meta[name="theme-color"]');if(meta)meta.content=themeColors[appearance.theme]||themeColors.classic;
    document.querySelectorAll('[data-roxy-avatar]').forEach(image=>{image.src=avatarSrc()});
    const subtitle=$('homeBrandSubtitle');if(subtitle)subtitle.textContent=account.household_name||'Tu hogar, organizado';
  }

  function renderPersonalizationPreview(){
    const form=$('personalizationForm');if(!form)return;const selected=name=>form.querySelector(`input[name="${name}"]:checked`)?.value;
    const theme=selected('personalizationTheme')||appearance.theme;const background=selected('personalizationBackground')||appearance.background;const avatar=selected('personalizationAvatar')||appearance.avatar;
    const palettes={classic:['#eef3eb','#fffdfa','#174d36'],olive:['#f0f3e9','#fffdf7','#425d3a'],coastal:['#edf5f5','#fffefa','#285969'],terracotta:['#f7eee8','#fffaf5','#754533']};const colors=palettes[theme]||palettes.classic;const preview=$('personalizationPreview');const backgrounds={plant:`linear-gradient(120deg,${colors[1]} 28%,${colors[0]})`,linen:`repeating-linear-gradient(90deg,${colors[0]} 0 2px,${colors[1]} 2px 7px)`,warm:`radial-gradient(circle at 85% 10%,#e8c98f,${colors[1]} 55%)`,clean:colors[1]};preview.style.background=backgrounds[background];preview.style.borderColor=colors[2];$('personalizationPreviewAvatar').src=avatarSources[avatar]||avatarSources.home;$('personalizationPreviewGreeting').textContent=`Hola, ${$('personalizationDisplayName').value.trim()||activePersonName()||'bienvenido'}`;$('personalizationPreviewHome').textContent=$('personalizationHouseholdName').value.trim()||account.household_name||'Nuestro hogar';
  }

  function openPersonalization(){
    if(account.mode!=='member'){openAccountDialog();return}const prefs=safeAppearance(account.preferences||appearance);$('personalizationDisplayName').value=account.display_name||'';$('personalizationHouseholdName').value=account.household_name||'Nuestro hogar';$('personalizationHouseholdName').disabled=account.role!=='OWNER';$('personalizationHouseholdLabel').hidden=account.role!=='OWNER';
    Object.entries({personalizationTheme:prefs.theme,personalizationBackground:prefs.background,personalizationAvatar:prefs.avatar}).forEach(([name,value])=>{const input=document.querySelector(`input[name="${name}"][value="${value}"]`);if(input)input.checked=true});$('personalizationResponseStyle').value=prefs.response_style;$('personalizationTextScale').value=prefs.text_scale;$('personalizationError').textContent='';renderPersonalizationPreview();$('personalizationDialog').showModal();
  }

  async function savePersonalization(event){
    event.preventDefault();const form=event.currentTarget;const submit=form.querySelector('button[type="submit"]');const selected=name=>form.querySelector(`input[name="${name}"]:checked`)?.value;submit.disabled=true;$('personalizationError').textContent='';
    try{const result=await api('/v1/home-account/preferences',{method:'PUT',body:JSON.stringify({display_name:$('personalizationDisplayName').value.trim(),household_name:account.role==='OWNER'?$('personalizationHouseholdName').value.trim():null,theme:selected('personalizationTheme'),background:selected('personalizationBackground'),avatar:selected('personalizationAvatar'),response_style:$('personalizationResponseStyle').value,text_scale:$('personalizationTextScale').value})});account=result;appearance=safeAppearance(result.preferences);applyAppearance();renderHomeMoment();renderAccount();$('personalizationDialog').close();announce('Tu Roxy Home quedó personalizada en todos tus dispositivos')}catch(error){$('personalizationError').textContent=error.message}finally{submit.disabled=false}
  }

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
  const categoryIdentity = value => normalize(value).split(' ').map(word=>word.length>4&&word.endsWith('s')?word.slice(0,-1):word).join(' ');
  const shoppingCategoryTerms = {
    FROZEN:['helado','pizza congelada','vegetales congelados','fruta congelada','comida congelada','papas congeladas','nuggets congelados','ice cream','frozen pizza','frozen food'],
    CLEANING:['detergente','suavizante','lavaplatos','lavavajillas','jabon de platos','jabon para platos','limpiador','desinfectante','cloro','lejia','oxiclean','oxi clean','esponja','estropajo','trapeador','mopa','escoba','recogedor','bolsa de basura','papel toalla','papel de cocina','toalla de papel','ambientador','aromatizante','bolsitas de olor','bolitas de olor','pastillitas de olor','pastillas de olor','pastillas de home','pastillitas de aroma','pastillas de aroma','bolitas para lavar ropa','perlas aromaticas','perlas de olor','potenciador de olor','potenciador de aroma','unstoppables','unstopables','scent booster','insecticida','limpiavidrios','dish soap','cleaner','trash bag'],
    PERSONAL:['papel higienico','jabon','champu','shampoo','acondicionador','desodorante','pasta dental','pasta de dientes','pasta de diente','pasta para dientes','dentifrico','crema dental','cepillo dental','hilo dental','enjuague bucal','gel de bano','gel de ducha','toalla sanitaria','tampon','afeitadora','rasuradora','crema de afeitar','locion','protector solar','crema corporal','gel de cejas','maquillaje','algodon','hisopo','toallitas humedas','aceite para el cabello','aceite de cabello','aceite capilar','toothpaste','deodorant','toilet paper'],
    HEALTH:['medicamento','medicina','pastilla','analgesico','ibuprofeno','acetaminofen','paracetamol','aspirina','vitamina','suplemento','jarabe','curita','vendaje','termometro','farmacia','antialergico','antibiotico','medicine','vitamin','supplement','bandage'],
    PETS:['comida de perro','comida para perro','comida de gato','comida para gato','alimento de perro','alimento para perro','alimento de gato','alimento para gato','arena de gato','arena para gato','premio de perro','premio de gato','croquetas de perro','croquetas de gato','empapador para mascota','empapadores para mascota','empapadores absorbentes','pad para perro','pads para perro','pad para luna','pads para luna','pad para bella','pads para bella','pee pad','pee pads','puppy pad','training pad','mascota','dog food','cat food','pet food','cat litter'],
    BABY:['panal','panales','toallitas de bebe','toallitas para bebe','champu de bebe','jabon de bebe','baby wipes','diaper','diapers'],
    HOUSEHOLD:['papel aluminio','papel encerado','papel pergamino','film plastico','servilleta','vaso desechable','plato desechable','cubierto desechable','bombillo','bombilla','bateria','pilas','vela','fosforo','encendedor','filtro de cafe','bolsa ziploc','recipiente','percha','gancho de ropa','organizador','cargador','cable usb','extension electrica','adaptador','regleta','martillo','destornillador','tornillo','clavo','taladro','cinta metrica','utensilio','espatula','abrelatas','aceite de motor','aceite para motor','motor oil','aluminum foil','light bulb','battery','napkin','charger','usb cable','extension cord','tool'],
    DAIRY_EGGS:['leche','huevo','queso','yogur','yogurt','mantequilla','crema de leche','half and half','nata','formula de bebe','formula infantil','baby formula','milk','egg','cheese','butter'],
    MEAT_SEAFOOD:['pollo','carne','res','cerdo','pescado','salmon','atun','camaron','marisco','bistec','jamon','tocino','pavo','chicken','beef','pork','fish','steak','shrimp','turkey','ham','bacon'],
    PRODUCE:['tomate','aguacate','platano','banana','mandarina','naranja','manzana','fruta','vegetal','verdura','cebolla','ajo','papa','patata','zanahoria','lechuga','pepino','pimiento','brocoli','coliflor','espinaca','cilantro','perejil','limon','lima','fresa','uva','mango','pina','vegetable','fruit','apple','orange'],
    BAKERY:['pan','bagel','croissant','tortilla','arepa','panecillo','bollo','pastelito','bread','bun','roll','bakery'],
    BEVERAGES:['cafe','te','matcha','agua','jugo','zumo','refresco','soda','bebida','leche de almendra','leche de avena','agua de coco','bebida energetica','coffee','water','juice','drink','beverage'],
    PANTRY:['arroz','pasta','espagueti','macarron','fideo','harina','avena','cereal','aceite','sal','azucar','levadura','vainilla','canela','especia','salsa','frijol','garbanzo','lenteja','maiz','maicena','dulce de leche','conserva','lata','galleta','chocolate','miel','mermelada','mayonesa','ketchup','mostaza','comida de bebe','rice','flour','sugar','salt','oil','oat','spice','sauce'],
    FOOD:['alimento','comida','snack','aperitivo','ingrediente','food','grocery']
  };
  const inferShoppingAisle = (name,requested='GENERAL') => {
    const identity=` ${categoryIdentity(productLabel(name))} `;
    const matches=[];
    for(const group of aisleOrder){
      (shoppingCategoryTerms[group]||[]).forEach(term=>{const key=categoryIdentity(term);if(identity.includes(` ${key} `))matches.push([key.length,group])});
    }
    if(matches.length)return matches.sort((left,right)=>right[0]-left[0])[0][1];
    return aisleOrder.includes(requested)?requested:'OTHER';
  };
  const inferShoppingCategory = (name,requested='GENERAL') => aisleToCategory[inferShoppingAisle(name,requested)]||'OTHER';
  const shoppingSubcategoryTerms = [
    ['Ropa',['detergente','suavizante','oxiclean','blanqueador','bolitas de olor','pastillitas de olor','pastillas de olor','pastillas de home','pastillitas de aroma','pastillas de aroma','bolitas para lavar ropa','perlas aromaticas','perlas de olor','potenciador de olor','potenciador de aroma','unstoppables','unstopables','scent booster','laundry']],
    ['Cocina',['lavaplatos','lavavajillas','jabon de platos','esponja','estropajo','dish soap']],
    ['Baño',['limpiador de bano','limpiador de inodoro','toilet cleaner']],
    ['Papel y basura',['papel toalla','papel de cocina','toalla de papel','bolsa de basura','trash bag']],
    ['Cabello',['champu','shampoo','acondicionador']],
    ['Cuidado oral',['pasta dental','pasta de dientes','pasta de diente','pasta para dientes','dentifrico','crema dental','cepillo dental','hilo dental','enjuague bucal','toothpaste']],
    ['Belleza y piel',['gel de cejas','maquillaje','crema corporal','protector solar','locion']],
    ['Medicamentos',['medicamento','medicina','pastilla','analgesico','ibuprofeno','acetaminofen','paracetamol','aspirina','jarabe']],
    ['Vitaminas y suplementos',['vitamina','suplemento','vitamin','supplement']],
    ['Primeros auxilios',['curita','vendaje','termometro','agua oxigenada','alcohol isopropilico','bandage']],
    ['Iluminación y electricidad',['bombillo','bombilla','bateria','pilas','cargador','cable usb','extension electrica','adaptador','regleta','light bulb','battery','charger','usb cable','extension cord']],
    ['Herramientas',['martillo','destornillador','tornillo','clavo','taladro','cinta metrica','tool']],
    ['Organización',['organizador','percha','gancho de ropa','recipiente']],
    ['Accesorios de cocina',['papel aluminio','papel encerado','papel pergamino','film plastico','filtro de cafe','bolsa ziploc','utensilio','espatula','abrelatas']],
    ['Aromas',['vela','ambientador','aromatizante','bolsitas de olor','sachet']],
    ['Desechables',['servilleta','vaso desechable','plato desechable','cubierto desechable','napkin']],
    ['Alimentación de mascotas',['comida de perro','comida de gato','alimento de perro','alimento de gato','dog food','cat food','pet food']],
    ['Higiene de mascotas',['arena de gato','cat litter','empapador para mascota','empapadores para mascota','empapadores absorbentes','pad para luna','pads para luna','pad para bella','pads para bella','pee pad','pee pads']],
    ['Accesorios de mascotas',['correa de perro','premio de perro','premio de gato']]
  ];
  const inferShoppingSubcategory = (name,requested='GENERAL') => {
    const identity=` ${categoryIdentity(productLabel(name))} `;const matches=[];
    shoppingSubcategoryTerms.forEach(([label,terms])=>terms.forEach(term=>{const key=categoryIdentity(term);if(identity.includes(` ${key} `))matches.push([key.length,label])}));
    return matches.length?matches.sort((left,right)=>right[0]-left[0])[0][1]:aisleLabels[inferShoppingAisle(name,requested)]||'Sin clasificar';
  };
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
    const identity=normalize(label);
    if(/^(?:pasta de dientes?|pasta para dientes|pasta dentifrica|crema de dientes|crema para dientes|crema dental|dentifrico|toothpaste)$/.test(identity))return'Pasta dental';
    if(/\b(?:pad|pads|pas|pass|paz)\b.*\b(?:luna|bella|perro|mascota)\b/.test(identity)||/\b(?:empapador|empapadores|tapete|alfombrilla)\b.*\b(?:absorbente|perro|mascota)\b/.test(identity)||/^(?:pee|puppy|training) pads?$/.test(identity))return'Empapadores absorbentes para mascota';
    if(/\b(?:bolitas?|pastillitas?|pastillas?) (?:de )?(?:olor|aroma|home)\b/.test(identity)||/\bperlas? (?:aromaticas?|de olor|para lavar ropa)\b/.test(identity)||/^(?:bolitas para lavar ropa|potenciador de olor|potenciador de aroma|unstoppables|unstopables|scent booster|laundry scent beads)$/.test(identity))return'Perlas aromáticas para ropa';
    return label||String(value||'').trim();
  };
  const fallbackImage = itemCategory => itemCategory === 'PERSONAL'
    ? '/assets/roxy_home/products/soap.png'
    : itemCategory === 'CLEANING'
      ? '/assets/roxy_home/products/detergent.png'
        : itemCategory === 'HEALTH'
          ? '/assets/roxy_home/products/pain-relief.png'
          : itemCategory === 'DAIRY_EGGS'
            ? '/assets/roxy_home/products/milk.png'
            : itemCategory === 'MEAT_SEAFOOD'
              ? '/assets/roxy_home/products/beef.png'
              : itemCategory === 'BAKERY'
                ? '/assets/roxy_home/products/bread.png'
                : itemCategory === 'BEVERAGES'
                  ? '/assets/roxy_home/products/juice.png'
                  : itemCategory === 'FROZEN'
                    ? '/assets/roxy_home/products/ice-cream.png'
        : '/assets/roxy_home/products/groceries.png';
  const imagePath = (name, itemCategory='GENERAL') => {
    const identity = normalize(productLabel(name));
    const exact = Object.keys(productImages)
      .sort((left,right) => right.length-left.length)
      .find(key => identity === key || identity.startsWith(`${key} `) || identity.endsWith(` ${key}`) || identity.includes(` ${key} `));
    if (exact) return `/assets/roxy_home/products/${productImages[exact]}`;
    return fallbackImage(itemCategory);
  };
  const designProductIcon = name => {
    const value=normalize(name);
    if(/alfombra|tapete/.test(value))return'texture';
    if(/lampara|luz|luces/.test(value))return'floor_lamp';
    if(/cojin|almohad/.test(value))return'pill';
    if(/mesa|centro de mesa/.test(value))return'table_restaurant';
    if(/cortina/.test(value))return'curtains';
    if(/toalla|ropa de cama/.test(value))return'bed';
    if(/organizador|almacenamiento|estanteria/.test(value))return'shelves';
    if(/arte|cuadro/.test(value))return'gallery_thumbnail';
    if(/maceta|planta/.test(value))return'potted_plant';
    if(/taburete|silla/.test(value))return'chair';
    return'home_and_garden';
  };
  const makeDesignProductVisual = name => {const visual=document.createElement('span');visual.className='design-product-visual material-symbols-rounded';visual.setAttribute('aria-hidden','true');visual.textContent=designProductIcon(name);return visual};
  const recipeImage = recipe => {
    if (recipe && /^data:image\/(jpeg|png|webp);base64,/.test(String(recipe.photo_data_url || ''))) return recipe.photo_data_url;
    if (recipe && /^\/assets\//.test(String(recipe.photo_asset || ''))) return recipe.photo_asset;
    const title=String(recipe&&recipe.title||'').trim();
    return title?`/v1/home-food/recipe-photo?v=4&title=${encodeURIComponent(title)}`:'';
  };
  const waitForRecipeImage = delay => new Promise(resolve=>setTimeout(resolve,delay));
  async function hydrateRecipeImage(image,recipe,host,{hideOnMissing=false}={}){
    const url=recipeImage(recipe);if(!url){if(hideOnMissing)image.hidden=true;else{image.remove();host&&host.classList.add('no-photo')}return}
    const markMissing=()=>{image.classList.remove('recipe-image-loading');if(hideOnMissing)image.hidden=true;else{image.remove();host&&host.classList.add('no-photo')}};
    image.addEventListener('error',markMissing,{once:true});
    if(url.startsWith('data:image/')||url.startsWith('/assets/')){image.src=url;return}
    image.classList.add('recipe-image-loading');
    for(let attempt=0;attempt<20;attempt+=1){
      try{
        const response=await fetch(`${url}&attempt=${attempt}`,{credentials:'same-origin',cache:'no-store'});
        if(response.ok){const blob=await response.blob();const objectUrl=URL.createObjectURL(blob);image.addEventListener('load',()=>URL.revokeObjectURL(objectUrl),{once:true});image.src=objectUrl;image.classList.remove('recipe-image-loading');host&&host.classList.remove('no-photo');return}
        if(response.status!==202)break;
      }catch(error){if(!navigator.onLine)break}
      await waitForRecipeImage(15000);
    }
    markMissing()
  }

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
  async function refreshHomeFood(){homeFood=await api(`/v1/home-food/${encodeURIComponent(user)}`);await dbSet(`home-food:${user}`,homeFood);renderRecipes();renderHomeDaily()}

  async function load({quiet=false}={}) {
    if (!quiet) setBusy(true);
    try {
      account=await api('/v1/home-account/me');
      if(account.storage_user_id){user=account.storage_user_id;localStorage.setItem('roxyShoppingUser',user)}
      appearance=safeAppearance(account.preferences||appearance);applyAppearance();
      const rangeStart=new Date();rangeStart.setHours(0,0,0,0);rangeStart.setDate(rangeStart.getDate()-7);
      const rangeEnd=new Date(rangeStart);rangeEnd.setDate(rangeEnd.getDate()+370);
      const [shopping,food,shoppingCommerce,calendarData,dailyData,designData,weatherData,plantsData,familyData] = await Promise.all([
        api(`/v1/shopping/${encodeURIComponent(user)}`),
        api(`/v1/home-food/${encodeURIComponent(user)}`),
        api(`/v1/home-commerce/${encodeURIComponent(user)}`),
        api(`/v1/home-calendar/${encodeURIComponent(user)}?start=${encodeURIComponent(rangeStart.toISOString())}&end=${encodeURIComponent(rangeEnd.toISOString())}`),
        api(`/v1/home-daily/${encodeURIComponent(user)}`).catch(()=>null),
        api(`/v1/home-design/${encodeURIComponent(user)}`).catch(()=>({projects:[],generation_configured:false})),
        api(`/v1/home-weather/${encodeURIComponent(user)}?days=16`).catch(()=>null),
        api(`/v1/home-plants/${encodeURIComponent(user)}`).catch(()=>({plants:[],due_today:[],vacation:{},species:[],identification_configured:false})),
        account.mode==='member'?api('/v1/home-family').catch(()=>null):Promise.resolve(null)
      ]);
      snapshot = shopping;
      homeFood = food;
      commerce = shoppingCommerce;
      homeCalendar = calendarData;
      homeDaily = dailyData;
      homeDesign = designData;
      homePlants = plantsData;
      if(familyData)homeFamily=familyData;
      if(weatherData)homeWeather=weatherData;
      await cacheSnapshot();
      await dbSet(`home-food:${user}`,homeFood);
      await dbSet(`home-commerce:${user}`,commerce);
      await dbSet(`home-calendar:${user}`,homeCalendar);
      if(homeDaily)await dbSet(`home-daily:${user}`,homeDaily);
      await dbSet(`home-design:${user}`,homeDesign);
      await dbSet(`home-plants:${user}`,homePlants);
      if(familyData)await dbSet(`home-family:${user}`,homeFamily);
      if(weatherData)await dbSet(`home-weather:${user}`,homeWeather);
      await flushQueue();
      setConnection('Sincronizado ahora','online');
      populateHomeForms();
      render();
      renderAccount();
      renderHomeMoment();
      if(familyData){void redeemNexoInvitationFromUrl();void resumeFamilyLocationIfEnabled()}
      void autoSyncGoogleCalendar();
      if(!$('shoppingPanel').hidden)void loadPriceRecommendations({quiet:true});
      if(account.requires_profile_setup&&!sessionStorage.getItem('roxyHomeProfilePrompted')){sessionStorage.setItem('roxyHomeProfilePrompted','1');openAccountDialog()}
    } catch (error) {
      const cached = await dbGet(`snapshot:${user}`).catch(() => null);
      const cachedFood = await dbGet(`home-food:${user}`).catch(() => null);
      const cachedCommerce = await dbGet(`home-commerce:${user}`).catch(() => null);
      const cachedCalendar = await dbGet(`home-calendar:${user}`).catch(() => null);
      const cachedDaily = await dbGet(`home-daily:${user}`).catch(() => null);
      const cachedDesign = await dbGet(`home-design:${user}`).catch(() => null);
      const cachedWeather = await dbGet(`home-weather:${user}`).catch(() => null);
      const cachedFamily = await dbGet(`home-family:${user}`).catch(() => null);
      if (cached) snapshot = cached;
      if (cachedFood) homeFood = cachedFood;
      if (cachedCommerce) commerce = cachedCommerce;
      if (cachedCalendar) homeCalendar = cachedCalendar;
      if (cachedDaily) homeDaily = cachedDaily;
      if (cachedDesign) homeDesign = cachedDesign;
      if (cachedWeather) homeWeather = cachedWeather;
      if (cachedFamily) homeFamily = cachedFamily;
      if (cached || cachedFood || cachedCommerce || cachedCalendar || cachedDaily || cachedDesign || cachedWeather || cachedFamily) {
        setConnection('Sin conexión · mostrando lo guardado','offline');
        populateHomeForms();
        render();
      }
      if (error.status === 401 || error.status === 403) {
        account={...account,mode:'signed_out',requires_profile_setup:false};
        renderAccount();renderFamily();
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

  function selectPanel(panel,{smooth=true}={}) {
    const contentPanel=panel==='pets'?'recipes':panel;
    if(panel==='pets')recipeAudience='pet';else if(panel==='recipes')recipeAudience='human';
    document.body.classList.toggle('family-mode',panel==='family');
    document.body.classList.toggle('pet-module-mode',panel==='pets');
    document.body.classList.toggle('design-module-mode',panel==='design');
    document.querySelectorAll('[data-panel]').forEach(node => {
      const active = node.dataset.panel === contentPanel;
      node.hidden = !active;
      node.classList.toggle('active',active);
    });
    document.querySelectorAll('.bottom-nav [data-tab-link]').forEach(button => {
      const active=button.dataset.tabLink === panel;
      button.classList.toggle('active',active);
      if(active)requestAnimationFrame(()=>{const nav=button.closest('.bottom-nav');if(nav)nav.scrollTo({left:Math.max(0,button.offsetLeft-(nav.clientWidth-button.offsetWidth)/2),behavior:smooth?'smooth':'auto'})});
    });
    // The large greeting remains as dormant infrastructure for a future
    // dedicated welcome experience. Today starts and ends with useful content,
    // while the center Roxy tab remains the conversation entry point.
    $('homeWelcome').hidden=true;
    const hashes={today:'hoy',shopping:'compra',recipes:'recetas',pets:'mascotas',pantry:'despensa',calendar:'calendario',design:'renueva',plants:'jardin',family:'nexo',more:'mas'};
    location.hash=hashes[panel]||'hoy';
    if(contentPanel==='recipes')renderRecipes();
    window.scrollTo({top:0,behavior:smooth?'smooth':'auto'});
    if(panel==='family'){
      const familyPanel=$('familyPanel');
      if(familyPanel)familyPanel.scrollTo({top:0,behavior:'auto'});
    }
    if(panel==='shopping'&&account.mode!=='unknown'&&!priceRecommendations&&!priceRecommendationsLoading)void loadPriceRecommendations({quiet:true});
    if(panel==='design'&&account.mode!=='unknown')void refreshDesignProjects().catch(()=>{});
    if(panel==='plants'&&account.mode!=='unknown')void refreshPlants().catch(()=>{});
    if(panel==='family'&&account.mode==='member')void refreshFamily().catch(()=>{});
  }

  const calendarCategories={PERSONAL:'Personal',WORK:'Trabajo',FAMILY:'Familia',SCHOOL:'Escuela',APPOINTMENTS:'Citas',HOME:'Hogar'};
  const calendarIcons={PERSONAL:'person',WORK:'work',FAMILY:'family_restroom',SCHOOL:'school',APPOINTMENTS:'medical_services',HOME:'home'};
  const dateKey=value=>{const d=value instanceof Date?value:new Date(value);return`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`};
  const sameDate=(a,b)=>dateKey(a)===dateKey(b);
  const startOfWeek=value=>{const d=new Date(value);d.setHours(0,0,0,0);d.setDate(d.getDate()-d.getDay());return d};
  const formatCalendarDay=value=>new Intl.DateTimeFormat('es',{weekday:'long',day:'numeric',month:'long'}).format(value);
  const formatCalendarTime=value=>new Intl.DateTimeFormat('es',{hour:'numeric',minute:'2-digit',hour12:true}).format(new Date(value));
  const eventsForDay=value=>(homeCalendar.events||[]).filter(event=>sameDate(event.starts_at,value));
  const weatherForDay=value=>(homeWeather.daily||[]).find(row=>row.date===dateKey(value))||null;

  function renderWeather(){
    const ready=homeWeather&&homeWeather.status==='READY';const current=homeWeather.current||{};const today=weatherForDay(new Date());const location=(homeWeather.location||{}).label||'Tu ubicación';
    const apply=(prefix,calendar=false)=>{const icon=$(`${prefix}WeatherIcon`);const place=$(`${prefix}WeatherLocation`);const title=$(`${prefix}WeatherTitle`);const detail=$(`${prefix}WeatherDetail`);if(!icon||!place||!title||!detail)return;if(!ready){icon.textContent='location_off';place.textContent='Clima local';title.textContent='Activa tu ubicación aproximada';detail.textContent='Roxy podrá anticipar lluvia y ayudarte a organizar el día.';return}icon.textContent=current.icon||today?.icon||'partly_cloudy_day';place.textContent=calendar?`Pronóstico · ${location}`:location;title.textContent=calendar?`${current.condition||'Pronóstico listo'} · ${Math.round(Number(current.temperature||0))} °F`:`${Math.round(Number(current.temperature||0))} °F · ${current.condition||'Condiciones variables'}`;detail.textContent=today?`${today.temperature_min}–${today.temperature_max} °F · ${today.rain_probability}% de lluvia${today.best_outdoor_window?` · Mejor ventana ${today.best_outdoor_window.label}`:''}`:`Sensación de ${Math.round(Number(current.feels_like||0))} °F`;};
    apply('today');apply('calendar',true);[['todayWeatherAction',ready?'calendar_month':'location_on',ready?'Ver':'Activar'],['calendarWeatherAsk',ready?'mic':'location_on',ready?'Preguntar':'Activar']].forEach(([id,icon,label])=>{const button=$(id);if(!button)return;button.querySelector('.material-symbols-rounded').textContent=icon;button.querySelector('b').textContent=label;button.setAttribute('aria-label',ready?(id==='calendarWeatherAsk'?'Preguntarle a Roxy por el clima':'Ver el pronóstico en el calendario'):'Usar mi ubicación aproximada para mostrar el clima')});
  }

  function renderUpcomingEvent(){
    const upcoming=(homeCalendar.events||[]).filter(event=>new Date(event.ends_at)>new Date()).sort((a,b)=>new Date(a.starts_at)-new Date(b.starts_at))[0];
    const card=$('upcomingEventCard');card.hidden=!upcoming||Boolean(homeDaily);if(!upcoming||homeDaily)return;
    $('upcomingEventTitle').textContent=upcoming.title;
    $('upcomingEventTime').textContent=`${formatCalendarDay(new Date(upcoming.starts_at))} · ${formatCalendarTime(upcoming.starts_at)} · Te avisaré ${Number(upcoming.reminder_minutes||0)===60?'una hora':`${Number(upcoming.reminder_minutes||0)} min`} antes`;
  }

  function renderHomeDaily(){
    const section=$('homeDailyBrief');const cardsRoot=$('homeDailyCards');const suggestions=$('homeDailySuggestions');
    cardsRoot.replaceChildren();suggestions.replaceChildren();
    if(!homeDaily||!Array.isArray(homeDaily.cards)){section.hidden=true;return}
    section.hidden=false;$('homeDailySummary').textContent=homeDaily.summary||'Roxy reunió lo más importante de tu hogar.';
    homeDaily.cards.forEach(card=>{const button=document.createElement('button');button.type='button';button.className='home-daily-card';const icon=document.createElement('span');icon.className='material-symbols-rounded';icon.textContent=card.icon||'check_circle';icon.setAttribute('aria-hidden','true');const copy=document.createElement('span');const title=document.createElement('strong');title.textContent=card.title||'';const detail=document.createElement('small');detail.textContent=card.kind==='calendar'&&card.detail?`${formatCalendarDay(new Date(card.detail))} · ${formatCalendarTime(card.detail)}`:card.detail||'';copy.append(title,detail);const arrow=document.createElement('span');arrow.className='material-symbols-rounded';arrow.textContent='arrow_forward';arrow.setAttribute('aria-hidden','true');button.append(icon,copy,arrow);button.addEventListener('click',()=>{const action=card.action||{};if(card.kind==='pet'){selectedPetId=String(action.pet_id||'');petHubTab=action.tab||'care';selectPanel('pets');return}const panel=action.panel||'today';selectPanel(panel);if(card.kind==='meal')$('mealPlanStudio').scrollIntoView({behavior:'smooth',block:'start'});if(card.kind==='ready')openRoxyVoice()});cardsRoot.append(button)});
    (homeDaily.suggested_phrases||[]).slice(0,3).forEach(phrase=>{const button=document.createElement('button');button.type='button';button.textContent=phrase;button.addEventListener('click',()=>{$('roxyCommand').value=phrase;$('roxyCommand').focus()});suggestions.append(button)});
  }

  function scheduleCalendarReminders(){
    calendarReminderTimers.forEach(timer=>clearTimeout(timer));calendarReminderTimers.clear();
    if(!('Notification'in window)||Notification.permission!=='granted')return;
    (homeCalendar.events||[]).forEach(event=>{
      const delay=new Date(event.starts_at).getTime()-Number(event.reminder_minutes||0)*60000-Date.now();
      if(delay<=0||delay>2147483647)return;
      calendarReminderTimers.set(event.occurrence_id||event.id,setTimeout(()=>new Notification('Roxy Home',{body:`${event.title} · ${formatCalendarTime(event.starts_at)}`,icon:avatarSrc()}),delay));
    });
  }

  function calendarEventRow(event){
    const button=document.createElement('button');button.type='button';button.className='calendar-event-row';button.dataset.category=event.category||'PERSONAL';button.addEventListener('click',()=>openCalendarEvent(event));
    const time=document.createElement('time');time.dateTime=event.starts_at;time.textContent=formatCalendarTime(event.starts_at);
    const dot=document.createElement('span');dot.className='calendar-event-dot';dot.setAttribute('aria-hidden','true');
    const icon=document.createElement('span');icon.className='calendar-event-icon material-symbols-rounded';icon.textContent=calendarIcons[event.category]||'event';icon.setAttribute('aria-hidden','true');
    const copy=document.createElement('span');copy.className='calendar-event-copy';const title=document.createElement('strong');title.textContent=event.title;const detail=document.createElement('small');detail.textContent=[event.location,calendarCategories[event.category]||'Personal'].filter(Boolean).join(' · ');copy.append(title,detail);
    const reminder=document.createElement('span');reminder.className='calendar-event-reminder';reminder.textContent=Number(event.reminder_minutes||0)?`Aviso ${Number(event.reminder_minutes)===60?'1 h':`${event.reminder_minutes} min`} antes`:'Sin aviso';
    button.append(time,dot,icon,copy,reminder);return button;
  }

  function renderCalendarWeekStrip(){
    const root=$('calendarWeekStrip');root.replaceChildren();const first=startOfWeek(calendarSelectedDate);
    for(let index=0;index<7;index+=1){const day=new Date(first);day.setDate(first.getDate()+index);const weather=weatherForDay(day);const button=document.createElement('button');button.type='button';button.className='calendar-day-button';button.classList.toggle('active',sameDate(day,calendarSelectedDate));button.classList.toggle('has-events',eventsForDay(day).length>0);button.setAttribute('aria-pressed',String(sameDate(day,calendarSelectedDate)));const label=document.createElement('small');label.textContent=new Intl.DateTimeFormat('es',{weekday:'short'}).format(day).replace('.','');const number=document.createElement('strong');number.textContent=day.getDate();button.append(label,number);if(weather){const climate=document.createElement('span');climate.className='calendar-day-weather';climate.textContent=weather.emoji||'🌤️';climate.title=`${weather.condition}, ${weather.temperature_min} a ${weather.temperature_max} grados Fahrenheit, ${weather.rain_probability}% de lluvia`;button.append(climate)}button.addEventListener('click',()=>{calendarSelectedDate=day;calendarDisplayMonth=new Date(day.getFullYear(),day.getMonth(),1);renderCalendar()});root.append(button)}
  }

  function renderCalendarAgenda(){
    const root=$('calendarAgenda');root.replaceChildren();const dates=[];
    if(calendarView==='week'){const first=startOfWeek(calendarSelectedDate);for(let i=0;i<7;i+=1){const day=new Date(first);day.setDate(first.getDate()+i);dates.push(day)}}else dates.push(new Date(calendarSelectedDate));
    dates.forEach(day=>{const section=document.createElement('section');section.className='calendar-agenda-day';const header=document.createElement('header');const titleWrap=document.createElement('div');const title=document.createElement('h3');title.textContent=sameDate(day,new Date())?`Hoy, ${formatCalendarDay(day)}`:formatCalendarDay(day);titleWrap.append(title);const weather=weatherForDay(day);if(weather){const climate=document.createElement('small');climate.className='calendar-agenda-weather';climate.textContent=`${weather.emoji||''} ${weather.condition} · ${weather.temperature_min}–${weather.temperature_max} °F · ${weather.rain_probability}% lluvia`;titleWrap.append(climate)}const add=makeButton('+','',()=>openCalendarEvent(null,day),`Agregar evento el ${formatCalendarDay(day)}`);header.append(titleWrap,add);section.append(header);const events=eventsForDay(day);if(events.length)events.forEach(event=>section.append(calendarEventRow(event)));else{const empty=document.createElement('div');empty.className='calendar-empty';const icon=document.createElement('span');icon.className='material-symbols-rounded';icon.textContent='event_available';const copy=document.createElement('span');copy.textContent='No hay compromisos. Puedes decirle a Roxy qué quieres programar.';empty.append(icon,copy);section.append(empty)}root.append(section)});
  }

  function renderCalendarMonth(){
    const root=$('calendarMonth');root.replaceChildren();const header=document.createElement('div');header.className='calendar-month-header';const previous=makeButton('‹','',()=>{calendarDisplayMonth.setMonth(calendarDisplayMonth.getMonth()-1);renderCalendarMonth()},'Mes anterior');const title=document.createElement('h3');title.textContent=new Intl.DateTimeFormat('es',{month:'long',year:'numeric'}).format(calendarDisplayMonth);const next=makeButton('›','',()=>{calendarDisplayMonth.setMonth(calendarDisplayMonth.getMonth()+1);renderCalendarMonth()},'Mes siguiente');header.append(previous,title,next);const grid=document.createElement('div');grid.className='calendar-month-grid';['Dom','Lun','Mar','Mié','Jue','Vie','Sáb'].forEach(value=>{const label=document.createElement('small');label.textContent=value;grid.append(label)});const first=new Date(calendarDisplayMonth.getFullYear(),calendarDisplayMonth.getMonth(),1);const cursor=new Date(first);cursor.setDate(1-first.getDay());for(let i=0;i<42;i+=1){const day=new Date(cursor);day.setDate(cursor.getDate()+i);const weather=weatherForDay(day);const button=document.createElement('button');button.type='button';button.className='calendar-month-day';const number=document.createElement('span');number.textContent=day.getDate();button.append(number);if(weather){const climate=document.createElement('small');climate.textContent=weather.emoji||'🌤️';button.append(climate)}button.classList.toggle('outside',day.getMonth()!==calendarDisplayMonth.getMonth());button.classList.toggle('today',sameDate(day,new Date()));button.classList.toggle('has-events',eventsForDay(day).length>0);button.addEventListener('click',()=>{calendarSelectedDate=day;calendarView='today';renderCalendar()});grid.append(button)}root.append(header,grid);
  }

  function renderCalendarYear(){
    const root=$('calendarYear');root.replaceChildren();for(let month=0;month<12;month+=1){const date=new Date(calendarDisplayMonth.getFullYear(),month,1);const button=document.createElement('button');button.type='button';button.textContent=new Intl.DateTimeFormat('es',{month:'long'}).format(date);button.classList.toggle('current',month===new Date().getMonth()&&date.getFullYear()===new Date().getFullYear());button.addEventListener('click',()=>{calendarDisplayMonth=date;calendarSelectedDate=date;calendarView='month';renderCalendar()});root.append(button)}
  }

  function renderCalendar(){
    document.querySelectorAll('[data-calendar-view]').forEach(button=>button.classList.toggle('active',button.dataset.calendarView===calendarView));
    const agendaVisible=calendarView==='today'||calendarView==='week';$('calendarWeekStrip').hidden=!agendaVisible;$('calendarAgenda').hidden=!agendaVisible;$('calendarMonth').hidden=calendarView!=='month';$('calendarYear').hidden=calendarView!=='year';
    if(agendaVisible){renderCalendarWeekStrip();renderCalendarAgenda()}else if(calendarView==='month')renderCalendarMonth();else renderCalendarYear();renderWeather();
    const sync=homeCalendar.sync||{};const google=sync.google_calendar||{};$('calendarSyncStatus').lastChild.textContent=google.connected?' Google Calendar conectado':' Recordatorios del teléfono pendientes de conectar';$('calendarGoogleMessage').textContent=google.connected?'Sincronización automática activa. Confirma el evento una sola vez en Roxy y aparecerá en el calendario del teléfono.':google.message||'Conecta Google Calendar una sola vez.';$('calendarGoogleConnect').hidden=google.connected||!google.configured;$('calendarGoogleConnect').href=`/v1/home-calendar/${encodeURIComponent(user)}/google/connect`;$('calendarGoogleSync').hidden=true;$('calendarGoogleDisconnect').hidden=!google.connected;if(!google.configured)$('calendarGoogleMessage').textContent='La conexión segura todavía necesita las credenciales de Google en el servidor.';renderUpcomingEvent();scheduleCalendarReminders();
  }

  async function autoSyncGoogleCalendar(){
    const google=((homeCalendar.sync||{}).google_calendar||{});const events=homeCalendar.events||[];
    if(calendarAutoSyncRunning||!google.connected||!events.length)return;
    const lastSync=Date.parse(google.last_synced_at||'');
    if(Number.isFinite(lastSync)&&Date.now()-lastSync<5*60*1000)return;
    calendarAutoSyncRunning=true;
    try{const result=await api(`/v1/home-calendar/${encodeURIComponent(user)}/google/sync`,{method:'POST'});if((result.errors||[]).length){$('calendarGoogleMessage').textContent='Google Calendar está conectado, pero un evento necesita reintentarse. Roxy volverá a intentarlo automáticamente.'}else{homeCalendar.sync.google_calendar.last_synced_at=new Date().toISOString();$('calendarGoogleMessage').textContent='Sincronización automática activa. Confirma el evento una sola vez en Roxy y aparecerá en el calendario del teléfono.'}}catch(_error){$('calendarGoogleMessage').textContent='Google Calendar está conectado. Roxy reintentará la sincronización automáticamente.'}finally{calendarAutoSyncRunning=false}
  }

  async function syncGoogleCalendar(){
    const button=$('calendarGoogleSync');button.disabled=true;try{const result=await api(`/v1/home-calendar/${encodeURIComponent(user)}/google/sync`,{method:'POST'});announce(`${result.synced||0} eventos sincronizados con tu teléfono`);await load({quiet:true})}catch(error){announce(error.message)}finally{button.disabled=false}
  }

  async function disconnectGoogleCalendar(){
    if(!confirm('¿Desconectar Google Calendar de esta cuenta de Roxy?'))return;
    try{await api(`/v1/home-calendar/${encodeURIComponent(user)}/google/connection`,{method:'DELETE'});announce('Google Calendar desconectado');await load({quiet:true})}catch(error){announce(error.message)}
  }

  function calendarFormPayload(){
    const start=new Date(`${$('calendarEventDate').value}T${$('calendarEventTime').value}:00`);const minutes=Number($('calendarEventDuration').value||60);const end=new Date(start.getTime()+minutes*60000);const recurrence=$('calendarEventRecurrence').value;
    return{title:$('calendarEventTitle').value.trim(),starts_at:start.toISOString(),ends_at:end.toISOString(),timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||'America/New_York',category:$('calendarEventCategory').value,reminder_minutes:Number($('calendarEventReminder').value||0),location:$('calendarEventLocation').value.trim(),notes:$('calendarEventNotes').value.trim(),participants:$('calendarEventParticipants').value.split(',').map(value=>value.trim()).filter(Boolean),recurrence,recurrence_until:recurrence==='NONE'?null:$('calendarEventRecurrenceUntil').value||null,all_day:false};
  }

  function openCalendarEvent(event=null,day=new Date()){
    const existing=Boolean(event&&!event._draft);const googleConnected=Boolean((((homeCalendar.sync||{}).google_calendar)||{}).connected);$('calendarEventForm').reset();$('calendarEventError').textContent='';const starts=event?new Date(event.starts_at):new Date(day);if(!event){starts.setHours(Math.max(9,new Date().getHours()+1),0,0,0)}const ends=event?new Date(event.ends_at):new Date(starts.getTime()+3600000);$('calendarEventId').value=existing&&event.id||'';$('calendarEventDialogTitle').textContent=existing?'Editar evento':'Nuevo evento';$('calendarEventTitle').value=event&&event.title||'';$('calendarEventDate').value=dateKey(starts);$('calendarEventTime').value=`${String(starts.getHours()).padStart(2,'0')}:${String(starts.getMinutes()).padStart(2,'0')}`;$('calendarEventDuration').value=String(Math.max(30,Math.round((ends-starts)/60000)));$('calendarEventReminder').value=String(event&&event.reminder_minutes!=null?event.reminder_minutes:60);$('calendarEventCategory').value=event&&event.category||'PERSONAL';$('calendarEventRecurrence').value=event&&event.recurrence||'NONE';$('calendarEventRecurrenceUntil').value=event&&event.recurrence_until||'';$('calendarRecurrenceUntilLabel').hidden=$('calendarEventRecurrence').value==='NONE';$('calendarEventLocation').value=event&&event.location||'';$('calendarEventNotes').value=event&&event.notes||'';$('calendarEventParticipants').value=(event&&event.participants||[]).join(', ');$('calendarDeleteButton').hidden=!existing;$('calendarExportButton').hidden=!existing||googleConnected;if(existing&&!googleConnected)$('calendarExportButton').href=`/v1/home-calendar/${encodeURIComponent(user)}/events/${encodeURIComponent(event.id)}.ics`;$('calendarEventDialog').showModal();
  }

  function showCalendarConfirmation(draft,conflicts=[],mode='create'){
    pendingCalendarDraft={...draft,_mode:mode};const root=$('calendarConfirmSummary');root.replaceChildren();const title=document.createElement('strong');title.textContent=draft.title;const start=new Date(draft.starts_at);const copy=document.createElement('small');copy.textContent=`${formatCalendarDay(start)} · ${formatCalendarTime(start)} · ${calendarCategories[draft.category]||'Personal'} · aviso ${Number(draft.reminder_minutes||0)===60?'1 hora':`${Number(draft.reminder_minutes||0)} min`} antes`;root.append(title,copy);const warning=$('calendarConflictWarning');warning.hidden=!conflicts.length;warning.textContent=conflicts.length?`Hay un posible conflicto con “${conflicts[0].title}”. Puedes volver y cambiar la hora.`:'';$('calendarConfirmDialog').showModal();
  }

  async function submitCalendarEvent(event){
    event.preventDefault();const payload=calendarFormPayload();if(payload.recurrence!=='NONE'&&!payload.recurrence_until){$('calendarEventError').textContent='Indica hasta cuándo debe repetirse.';return}const id=$('calendarEventId').value;try{if(id){showCalendarConfirmation({...payload,id},[], 'edit')}else{const data=await api(`/v1/home-calendar/${encodeURIComponent(user)}/drafts`,{method:'POST',body:JSON.stringify({...payload,confirmed:false})});showCalendarConfirmation(data.draft,data.conflicts||[])}$('calendarEventDialog').close()}catch(error){$('calendarEventError').textContent=error.message}
  }

  async function confirmCalendarEvent(){
    if(!pendingCalendarDraft)return;const button=$('calendarConfirmSave');button.disabled=true;try{let result;if(pendingCalendarDraft._mode==='edit'){const id=pendingCalendarDraft.id;const payload={...pendingCalendarDraft};delete payload.id;delete payload._mode;result=await api(`/v1/home-calendar/${encodeURIComponent(user)}/events/${encodeURIComponent(id)}`,{method:'PUT',body:JSON.stringify(payload)})}else result=await api(`/v1/home-calendar/${encodeURIComponent(user)}/drafts/confirm`,{method:'POST',body:JSON.stringify({draft_id:pendingCalendarDraft.id,confirmed:true})});$('calendarConfirmDialog').close();pendingCalendarDraft=null;await load({quiet:true});selectPanel('calendar');const sync=result&&result.sync||{};announce(sync.synced?'Evento guardado y sincronizado con el calendario de tu teléfono':sync.reason==='not_connected'?'Evento guardado en Roxy Home. Conecta Google Calendar para recibirlo en tu teléfono':'Evento guardado en Roxy Home, pero no se pudo sincronizar con Google Calendar. Pulsa Sincronizar para reintentar');if('Notification'in window&&Notification.permission==='default')Notification.requestPermission().then(scheduleCalendarReminders)}catch(error){announce(error.message)}finally{button.disabled=false}
  }

  async function deleteCalendarEvent(){
    const id=$('calendarEventId').value;if(!id||!window.confirm('¿Eliminar este evento del calendario?'))return;try{await api(`/v1/home-calendar/${encodeURIComponent(user)}/events/${encodeURIComponent(id)}`,{method:'DELETE'});$('calendarEventDialog').close();await load({quiet:true});announce('Evento eliminado')}catch(error){announce(error.message)}
  }

  function renderFilters() {
    const root = $('categoryFilters');
    root.replaceChildren();
    const counts=activeItems().reduce((result,item)=>{const aisle=inferShoppingCategory(item.name,item.category);result[aisle]=(result[aisle]||0)+1;return result;},{});
    ['ALL',...categoryOrder].forEach(value => {
      const count=value==='ALL'?activeItems().length:counts[value]||0;
      const button = makeButton(`${categories[value]} ${count}`,'chip',() => { category=value; renderShopping(); });
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
    const isMeaningfulProduct=name=>{
      const identity=normalize(name);
      if(['por favor','gracias','ok','okay','si','no'].includes(identity))return false;
      return !['calendario','evento','cita','reunion','recordatorio','trabajo a las','trabajo manana','hoy trabajo','manana tengo que','a m','p m'].some(marker=>identity.includes(marker));
    };
    const remembered = (Array.isArray(snapshot.habitual_products) ? snapshot.habitual_products : [])
      .filter(item => item && item.name && isMeaningfulProduct(item.name) && !activeNames.has(normalize(item.name)))
      .map(item => [item.name,inferShoppingCategory(item.name,item.category),item.unit||'unidad',Number(item.purchase_count||item.times_used||1)]);
    const seen = new Set(remembered.map(row => normalize(row[0])));
    return [...remembered,...staples.filter(row => !seen.has(normalize(row[0]))).map(row=>[row[0],inferShoppingCategory(row[0],row[1]),row[2],row[3]])];
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
    payload={...payload,name:productLabel(payload.name),category:inferShoppingCategory(payload.name,payload.category)};
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
  function makeShoppingRow(item) {
      const article=document.createElement('article'); article.className='shopping-item';
      const label=productLabel(item.name);
      const itemCategory=inferShoppingCategory(label,item.category); item.category=itemCategory;
      const img=makeImage(label,itemCategory,''); img.className='product-thumb';
      const copy=document.createElement('div'); copy.className='shopping-copy';
      const strong=document.createElement('strong'); strong.textContent=label;
      const subcategory=inferShoppingSubcategory(label,item.category);
      const small=document.createElement('small'); small.textContent=`${categories[itemCategory]||'Otros'} · ${subcategory} · ${item.unit||'unidad'}`;
      copy.append(strong,small);
      const stepper=document.createElement('div'); stepper.className='stepper';
      const minus=makeButton('−','',()=>changeQuantity(item,-1),`Disminuir cantidad de ${label}`); minus.disabled=Number(item.quantity)<=1;
      const output=document.createElement('output'); output.value=String(item.quantity); output.textContent=String(item.quantity); output.setAttribute('aria-label',`Cantidad ${item.quantity}`);
      const plus=makeButton('+','',()=>changeQuantity(item,1),`Aumentar cantidad de ${label}`);
      stepper.append(minus,output,plus);
      const remove=makeButton('Eliminar','delete',()=>removeItem(item),`Eliminar ${label}`);
      const controls=document.createElement('div'); controls.className='item-controls'; controls.append(stepper,remove);
      article.append(img,copy,controls);
      return article;
  }
  function renderList() {
    const root = $('shoppingList');
    root.replaceChildren();
    const rows = activeItems().map(item=>{item.category=inferShoppingCategory(item.name,item.category);return item;}).filter(item => (category==='ALL'||item.category===category) && (!search||normalize(item.name).includes(normalize(search))));
    $('rowCount').textContent = `${rows.length} ${rows.length===1?'producto':'productos'}`;
    if (!rows.length) {
      const empty=document.createElement('div'); empty.className='empty';
      const strong=document.createElement('strong'); strong.textContent=activeItems().length?'Sin coincidencias':'Tu lista está lista para empezar';
      empty.append(strong,document.createTextNode(activeItems().length?' Prueba otra búsqueda.':' Agrega un producto o pídeselo a Roxy.'));
      root.append(empty); return;
    }
    categoryOrder.forEach(group=>{
      const grouped=rows.filter(item=>item.category===group);
      if(!grouped.length)return;
      const section=document.createElement('section'); section.className='shopping-category-group';
      const heading=document.createElement('header');
      const title=document.createElement('strong'); title.textContent=categories[group];
      const count=document.createElement('span'); count.textContent=String(grouped.length); count.setAttribute('aria-label',`${grouped.length} productos`);
      heading.append(title,count); section.append(heading,...grouped.map(makeShoppingRow)); root.append(section);
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
    (commerce.providers||[]).forEach(provider=>{const badge=document.createElement('span');badge.className=`provider-badge ${provider.configured?'ready':'pending'}`;const used=Number(provider.handoff_count||0);badge.textContent=`${provider.name} · ${provider.status_label||(provider.configured?'Listo':'Pendiente')}${used?` · usado ${used}`:''}`;badge.title=provider.next_step||provider.description||'';root.append(badge)});
    const recent=$('commerceRecent');recent.replaceChildren();const activity=commerce.activity||{};const latest=(activity.recent||[])[0];
    if(latest){const strong=document.createElement('strong');strong.textContent='Última compra preparada';const small=document.createElement('small');small.textContent=`${latest.provider_name} · ${latest.item_count} ${latest.item_count===1?'artículo':'artículos'} · falta confirmar en la tienda`;recent.append(strong,small)}
    $('prepareShoppingButton').disabled=!activeItems().length;
    $('prepareAmazonButton').disabled=!activeItems().length||!(commerce.providers||[]).some(provider=>provider.id==='amazon'&&provider.configured);
    renderPriceRecommendations();
  }

  function money(value,currency='USD'){return new Intl.NumberFormat('es-US',{style:'currency',currency,maximumFractionDigits:2}).format(Number(value||0))}
  function renderPriceCoverage(){
    const alertRoot=$('priceAlerts');const retailerRoot=$('nearbyRetailers');alertRoot.replaceChildren();retailerRoot.replaceChildren();
    const result=priceRecommendations||{};const activity=result.price_activity||commerce.price_activity||{};const alerts=(activity.new_alerts&&activity.new_alerts.length?activity.new_alerts:activity.recent_alerts)||[];
    alerts.slice(0,3).forEach(alert=>{const row=document.createElement('article');row.className='price-alert';const icon=document.createElement('span');icon.className='material-symbols-rounded';icon.textContent='trending_down';const copy=document.createElement('span');const strong=document.createElement('strong');strong.textContent=alert.message||`${alert.item_name} bajó de precio`;const small=document.createElement('small');small.textContent=`${alert.retailer_name} · ${money(alert.price,alert.currency||'USD')} · comprobado ${new Intl.DateTimeFormat('es',{dateStyle:'short'}).format(new Date(alert.observed_at))}`;copy.append(strong,small);row.append(icon,copy);alertRoot.append(row)});
    const retailers=result.nearby_retailers||[];if(retailers.length){const title=document.createElement('span');title.className='nearby-retailers-title';title.textContent=`Supermercados disponibles cerca de ti (${retailers.length}). Instacart confirma precio y disponibilidad al abrir la compra.`;retailerRoot.append(title);retailers.slice(0,12).forEach(retailer=>{const chip=document.createElement('span');chip.className='nearby-retailer';chip.textContent=retailer.name;retailerRoot.append(chip)})}
  }
  function renderPriceRecommendations(){
    const root=$('priceRecommendations');root.replaceChildren();const status=$('priceRecommendationStatus');const refresh=$('refreshPricesButton');refresh.disabled=priceRecommendationsLoading||!activeItems().length;renderPriceCoverage();
    if(priceRecommendationsLoading){status.textContent='Roxy está consultando precios vigentes cerca de ti…';return}
    if(!activeItems().length){status.textContent='Agrega productos a tu lista para comparar dónde conviene comprarlos.';return}
    if(!priceRecommendations){status.textContent='Roxy compara únicamente precios reales, tamaños compatibles y ofertas vigentes.';return}
    const rows=priceRecommendations.recommendations||[];
    if(!rows.length){status.textContent=priceRecommendations.message||'Todavía no hay precios verificables para estos productos. Puedes buscar en los comercios disponibles sin que Roxy invente una comparación.';return}
    const updated=priceRecommendations.updated_at?new Intl.DateTimeFormat('es',{dateStyle:'short',timeStyle:'short'}).format(new Date(priceRecommendations.updated_at)):'';
    const checked=priceRecommendations.retailers_checked||[];status.textContent=`${rows.length} ${rows.length===1?'recomendación verificada':'recomendaciones verificadas'}${checked.length?` · ${checked.length} ${checked.length===1?'comercio consultado':'comercios consultados'}`:''}${updated?` · actualizado ${updated}`:''}. Confirma el total en la tienda.`;
    rows.forEach(offer=>{
      const article=document.createElement('article');article.className='price-offer';const img=makeImage(offer.shopping_item,'FOOD',offer.product_title||offer.shopping_item);if(offer.image_url){img.src=offer.image_url;img.referrerPolicy='no-referrer'}const copy=document.createElement('div');copy.className='price-offer-copy';
      const title=document.createElement('strong');title.textContent=offer.shopping_item;const retailer=document.createElement('span');retailer.append(document.createTextNode(`${offer.retailer_name} · ${money(offer.price,offer.currency)}`));if(offer.regular_price){const regular=document.createElement('del');regular.textContent=money(offer.regular_price,offer.currency);retailer.append(regular)}const product=document.createElement('small');product.textContent=[offer.product_title,offer.package_label].filter(Boolean).join(' · ');copy.append(title,retailer,product);
      if(offer.unit_price&&offer.comparison_unit){const unit=document.createElement('small');unit.textContent=`${money(offer.unit_price,offer.currency)} por ${offer.comparison_unit}`;copy.append(unit)}
      const reason=document.createElement('small');reason.className='price-offer-reason';reason.textContent=(offer.reasons||[])[0]||'Mejor opción según tu perfil';copy.append(reason);
      const button=makeButton(`Ver en ${offer.retailer_name}`,'',()=>reviewRetailOffer(offer),`Revisar ${offer.shopping_item} en ${offer.retailer_name}`);article.append(img,copy,button);root.append(article);
    });
  }
  async function loadPriceRecommendations({quiet=false}={}){
    if(priceRecommendationsLoading)return;priceRecommendationsLoading=true;renderPriceRecommendations();
    try{priceRecommendations=await api(`/v1/home-commerce/${encodeURIComponent(user)}/recommendations`);if(!quiet&&priceRecommendations.status==='READY')announce('Roxy actualizó las recomendaciones de compra')}
    catch(error){priceRecommendations={status:'ERROR',recommendations:[],message:error.message||'No pude actualizar los precios.'};if(!quiet)announce(priceRecommendations.message)}
    finally{priceRecommendationsLoading=false;renderPriceRecommendations()}
  }
  function reviewRetailOffer(offer){
    const detail=[`${offer.shopping_item} en ${offer.retailer_name} por ${money(offer.price,offer.currency)}`,offer.package_label,offer.unit_price&&offer.comparison_unit?`${money(offer.unit_price,offer.currency)} por ${offer.comparison_unit}`:'',`Precio consultado: ${new Intl.DateTimeFormat('es',{dateStyle:'short',timeStyle:'short'}).format(new Date(offer.observed_at))}`].filter(Boolean).join('\n');
    if(!window.confirm(`${detail}\n\nLa tienda confirmará precio, disponibilidad y pago. ¿Abrir esta oferta?`))return;
    const opened=window.open(offer.product_url,'_blank','noopener,noreferrer');if(!opened)announce('Permite ventanas emergentes para abrir la tienda');
  }

  const kindLabels={meal:'Comida',bread:'Pan',dessert:'Postre',drink:'Bebida',other:'Otra'};
  const recipeCategories=[
    {id:'breakfast',title:'Desayunos',description:'Huevos, avena, yogur, pancakes y tostadas',icon:'egg_alt'},
    {id:'chicken',title:'Pollo',description:'Recetas cotidianas de pollo',icon:'skillet'},
    {id:'meat',title:'Carnes',description:'Res y cerdo',icon:'outdoor_grill'},
    {id:'seafood',title:'Pescados y mariscos',description:'Pescados, atún y camarones',icon:'set_meal'},
    {id:'rice',title:'Arroces',description:'Arroces, risottos y paellas',icon:'rice_bowl'},
    {id:'pasta',title:'Pastas y fideos',description:'Pastas, lasañas y fideos',icon:'ramen_dining'},
    {id:'soups',title:'Sopas, cremas y guisos',description:'Platos de cuchara reconfortantes',icon:'soup_kitchen'},
    {id:'bowls_salads',title:'Bowls y ensaladas',description:'Comidas frescas y completas',icon:''},
    {id:'vegetarian',title:'Vegetarianas',description:'Recetas sin carne',icon:'eco'},
    {id:'baked',title:'Horneados',description:'Pizzas, panes, masas y gratinados',icon:'bakery_dining'},
    {id:'sides_sauces',title:'Acompañamientos y salsas',description:'Guarniciones y básicos caseros',icon:'tapas'},
    {id:'desserts',title:'Postres',description:'Dulces clásicos para compartir',icon:'cake'},
    {id:'coffee_hot',title:'Café y calientes',description:'Café caliente, frío, té y chocolate',icon:'coffee'},
    {id:'juices',title:'Jugos y refrescantes',description:'Jugos, limonadas y aguas frescas',icon:'local_drink'},
    {id:'smoothies',title:'Batidos y smoothies',description:'Frutas, proteína y bowls',icon:'blender'},
    {id:'cocktails',title:'Cócteles',description:'Bebidas para adultos',icon:'local_bar'},
  ];
  const recipeCategoryLabels=Object.fromEntries(recipeCategories.map(row=>[row.id,row.title]));
  function recipeCategoryId(recipe){
    if(recipe&&recipe.category&&recipeCategories.some(row=>row.id===recipe.category))return recipe.category;
    const title=normalize(recipe.title||'');
    const ingredients=normalize((recipe.ingredients||[]).map(row=>typeof row==='string'?row:row.name||'').join(' '));
    if(recipe.kind==='drink')return recipe.drink_type==='alcoholic'?'cocktails':/(cafe|espresso|latte|mocha|te|chocolate caliente)/.test(title)?'coffee_hot':/(batido|smoothie)/.test(title)?'smoothies':'juices';
    if(recipe.kind==='dessert'||/(postre|dulce|galleta|bizcocho|pastel|tarta|flan|brownie|helado|arroz con leche|tiramisu|churro)/.test(title))return'desserts';
    if(recipe.kind==='bread'||/(^| )(pan|baguette|focaccia|brioche|arepa|pizza)( |$)/.test(title))return'baked';
    if(/(pasta|espagueti|spaghetti|lasana|macarron|fideo|ravioli|tortellini|linguini|penne)/.test(title))return'pasta';
    if(/(desayuno|avena|pancake|panqueque|waffle|tostada|omelet|huevos rancheros|yogur|granola)/.test(title)||(/huevo/.test(ingredients)&&/(tostada|desayuno)/.test(title)))return'breakfast';
    if(/(salmon|pescado|camaron|atun|ceviche|marisco)/.test(title))return'seafood';
    if(/(pollo|alita)/.test(title))return'chicken';
    if(/(arroz|risotto|paella)/.test(title))return'rice';
    if(/(sopa|crema|guiso|potaje|ajiaco)/.test(title))return'soups';
    if(/(ensalada|bowl)/.test(title))return'bowls_salads';
    return'meat';
  }
  function recipeCard(recipe){
    const button=document.createElement('button');button.type='button';button.className='recipe-card';
    const img=document.createElement('img');img.alt=`Resultado final de ${recipe.title||'la receta'}`;img.loading='lazy';img.decoding='async';if(recipe.photo_focus)img.style.objectPosition=recipe.photo_focus;hydrateRecipeImage(img,recipe,button);
    const copy=document.createElement('span');const strong=document.createElement('strong');strong.textContent=recipe.title;
    const drinkLabel=recipe.kind==='drink'?(recipe.drink_type==='alcoholic'?'Con alcohol':'Sin alcohol'):'';
    const recipePet=recipe.audience==='pet'?selectedPetProfile():null;const petLabel=recipe.audience==='pet'?[recipe.pet_variety,recipePet?'Para '+recipePet.name:'',({treat:'Premio ocasional',complement:'Complemento',feeding_guide:'Guía de alimentación',veterinary_plan:'Plan veterinario'}[recipe.safety_class]||'Receta para mascota')].filter(Boolean).join(' · '):'';
    const servings=Number(recipe.servings||1);const yieldLabel=recipe.audience==='pet'?(recipe.safety_class==='feeding_guide'?'1 guía':`${servings} ${servings===1?'pieza preparada':'piezas preparadas'}`):`${servings} ${servings===1?'porción':'porciones'}`;const small=document.createElement('small');small.textContent=`${recipe.favorite?'Favorita · ':''}${petLabel||drinkLabel||recipeCategoryLabels[recipeCategoryId(recipe)]||kindLabels[recipe.kind]||'Receta'} · ${yieldLabel} · ${(recipe.steps||[]).length} pasos`;
    const editorialStatus=String(recipe.editorial_status||'');const requiresReview=Boolean(editorialStatus)&&!editorialStatus.startsWith('verified');
    copy.append(strong,small);if(recipe.audience==='pet'&&recipe.personalization_reason){const match=document.createElement('em');match.className='pet-recipe-match';match.textContent=recipe.personalization_reason;copy.append(match)}button.append(img,copy);button.addEventListener('click',()=>recipe.catalog_key?openRecipe(recipe):requiresReview?openCatalogRecipe(recipe):openRecipe(recipe));return button;
  }
  function renderRecipes() {
    const root=$('recipeLibrary'); root.replaceChildren();
    const catalog=homeFood.local_catalog||{};
    const imageService=homeFood.recipe_image_service||{};const petMode=recipeAudience==='pet';
    $('recipesPanel').classList.toggle('pet-mode',petMode);
    $('recipeHeroEyebrow').textContent=petMode?'Bienestar personalizado':'Roxy cocina contigo';
    $('recipesTitle').textContent=petMode?'Mascotas':'Recetas';
    $('recipeHeroBadge').textContent=petMode?'Perfil privado':'Guardado automático';
    $('recipeImportTitle').textContent=petMode?'Tus mascotas':'Trae cualquier receta a Roxy';
    $('recipeLead').firstChild.textContent=petMode?'Cuidados, alimentación y salud organizados para cada mascota. ':'Elige una categoría o busca tu plato. Cada receta está lista para abrirse, guardarse y cocinarse paso a paso. ';
    $('recipeCatalogHint').textContent=petMode?'':catalog.total?`Roxy incluye ${catalog.total} recetas listas para guardar, adaptar y cocinar paso a paso.${imageService.pending?` Está completando ${imageService.pending} fotos para que cada plato se reconozca a primera vista.`:''}`:'';
    const filters=$('recipeFilters');filters.replaceChildren();filters.hidden=false;
    const pets=savedPets();const onboarding=$('petOnboardingEmpty');const catalogSection=$('recipeCatalogSection');const importStudio=$('recipeImportStudio');const petHub=$('petPersonalizedHub');
    $('petRecipeContext').hidden=!petMode;if(petMode)renderPetProfiles();
    catalogSection.setAttribute('role','region');catalogSection.setAttribute('aria-labelledby','libraryTitle');
    importStudio.classList.toggle('pet-profile-mode',petMode);
    if(recipeAudience==='pet'&&!pets.length){onboarding.hidden=false;catalogSection.hidden=true;petHub.hidden=true;importStudio.classList.add('pet-onboarding-mode');return}
    onboarding.hidden=true;importStudio.classList.remove('pet-onboarding-mode');petHub.hidden=recipeAudience!=='pet';
    if(recipeAudience==='pet'){renderPetHub();catalogSection.hidden=petHubTab!=='recipes';if(petHubTab!=='recipes')return}else catalogSection.hidden=false;
    $('recipeLibraryEyebrow').textContent=petMode?'Seguro para su perfil':'Incluidas y disponibles';
    $('libraryTitle').textContent=petMode?'Alimentación complementaria':'Recetario de Roxy';
    $('recipeLibraryHint').textContent=petMode?'Premios, complementos o guías claramente separados de su alimento completo':'Toca una receta incluida para guardarla en tu carpeta';
    $('recipeSearch').placeholder=petMode?'Buscar premio o guía segura…':'Buscar huevos, pollo, café…';
    if(recipeAudience==='human')[...recipeCategories,{id:'favorite',title:'Favoritas',icon:'favorite'}].forEach(category=>{const button=document.createElement('button');button.type='button';button.className=`recipe-filter-card${recipeFilter===category.id?' active':''}`;button.dataset.recipeFilter=category.id;if(category.icon){const icon=document.createElement('span');icon.className='material-symbols-rounded';icon.setAttribute('aria-hidden','true');icon.textContent=category.icon;button.append(icon)}const label=document.createElement('span');label.textContent=category.title;button.append(label);button.addEventListener('click',()=>{recipeFilter=category.id;renderRecipes()});filters.append(button)});
    else [{id:'all',title:'Todo',icon:'apps'},{id:'treat',title:'Premios',icon:'cookie'},{id:'feeding_guide',title:'Guías',icon:'fact_check'},{id:'favorite',title:'Favoritas',icon:'favorite'}].forEach(category=>{const button=document.createElement('button');button.type='button';button.className=`recipe-filter-card${petRecipeFilter===category.id?' active':''}`;const icon=document.createElement('span');icon.className='material-symbols-rounded';icon.setAttribute('aria-hidden','true');icon.textContent=category.icon;const label=document.createElement('span');label.textContent=category.title;button.append(icon,label);button.addEventListener('click',()=>{petRecipeFilter=category.id;renderRecipes()});filters.append(button)});
    const sessions=homeFood.cooking_sessions||[];
    const active=[...sessions].reverse().find(row=>row.status==='ACTIVE');
    if(active&&recipeAudience==='human'){
      const resume=document.createElement('button'); resume.type='button'; resume.className='recipe-card resume-card';
      const img=document.createElement('img'); img.src=avatarSrc(); img.alt='';
      const copy=document.createElement('span'); const strong=document.createElement('strong'); strong.textContent=`Continuar: ${active.recipe_title}`;
      const small=document.createElement('small'); small.textContent=`Paso ${Number(active.step_index||0)+1} de ${active.step_count}`;
      copy.append(strong,small); resume.append(img,copy); resume.addEventListener('click',()=>resumeCooking(active.id)); root.append(resume);
    }
    const saved=[];const seenSavedTitles=new Set();(homeFood.recipes||[]).slice().reverse().forEach(recipe=>{const title=normalize(recipe.title||'');if(!title||seenSavedTitles.has(title))return;seenSavedTitles.add(title);saved.push(recipe)});const savedTitles=new Set(saved.map(recipe=>normalize(recipe.title||'')));const included=(homeFood.local_recipes||[]).filter(recipe=>!savedTitles.has(normalize(recipe.title||'')));const pet=selectedPetProfile();const personalizedRows=pet?((homeFood.pet_recipe_recommendations||{})[String(pet.id)]||[]):[];const favoriteTitles=new Set(saved.filter(recipe=>recipe.favorite).map(recipe=>normalize(recipe.title||'')));const petRows=personalizedRows.map(recipe=>({...recipe,favorite:favoriteTitles.has(normalize(recipe.title||''))}));const allRows=recipeAudience==='pet'?petRows:recipeFilter==='favorite'?saved:[...saved,...included];
    const blockedIngredients=(pet?.allergies||[]).map(normalize).filter(value=>value&&!/^ninguna\b/.test(value));
    const petIdentity=normalize(`${pet?.exact_species||''} ${pet?.breed||''}`);const compatiblePetRows=allRows.filter(recipe=>{if(recipeAudience!=='pet')return recipe.audience!=='pet';if(recipe.audience!=='pet'||(recipe.pet_species&&recipe.pet_species!==petSpecies))return false;const exactTerms=(recipe.pet_exact_terms||[]).map(normalize).filter(Boolean);if(exactTerms.length&&!exactTerms.some(term=>petIdentity.includes(term)))return false;const lifeStages=(recipe.pet_life_stages||[]).map(normalize).filter(Boolean);if(lifeStages.length&&!lifeStages.includes(normalize(pet?.life_stage||'unknown')))return false;const ingredients=normalize((recipe.ingredients||[]).map(row=>typeof row==='string'?row:row.name||'').join(' '));return !blockedIngredients.some(item=>ingredients.includes(item))});const exactPetRows=recipeAudience==='pet'?compatiblePetRows.filter(recipe=>(recipe.pet_exact_terms||[]).map(normalize).some(term=>petIdentity.includes(term))):[];const exactKeys=new Set(exactPetRows.map(recipe=>recipe.catalog_key||recipe.id||recipe.title));const audienceRows=recipeAudience==='pet'?[...exactPetRows,...compatiblePetRows.filter(recipe=>!exactKeys.has(recipe.catalog_key||recipe.id||recipe.title))]:compatiblePetRows;
    const rows=audienceRows.filter(recipe=>{const matchesSearch=!recipeSearch||normalize(`${recipe.title||''} ${recipe.subcategory||''}`).includes(recipeSearch);const matchesCategory=recipeAudience==='pet'?(petRecipeFilter==='all'||(petRecipeFilter==='favorite'?recipe.favorite:recipe.safety_class===petRecipeFilter)):recipeFilter==='favorite'?recipe.favorite:recipeSearch||recipeCategoryId(recipe)===recipeFilter;return matchesSearch&&matchesCategory});
    const speciesLabel={dog:'para perros',cat:'para gatos',ferret:'para hurones',rabbit:'para conejos',guinea_pig:'para cobayas',hamster:'para hámsteres',bird:'para aves',fish:'para peces',reptile:'para reptiles',amphibian:'para anfibios',other:'para otras mascotas'}[petSpecies]||'para mascotas';
    $('recipeCount').textContent=recipeAudience==='pet'?`${rows.length} ${speciesLabel}`:recipeSearch||recipeFilter==='favorite'?`${rows.length} ${rows.length===1?'resultado':'resultados'}`:`${audienceRows.length} para personas`;
    if(recipeAudience==='pet'){
      const feedingHub=['fish','reptile','amphibian','invertebrate','farm_pet','other'].includes(petSpecies);const section=document.createElement('section');section.className='recipe-category';
      const heading=document.createElement('div');heading.className='recipe-category-heading';const copy=document.createElement('div');const title=document.createElement('h3');title.textContent=`${feedingHub?'Alimentación':'Recetario'} de ${pet?.name||'tu mascota'}`;const description=document.createElement('p');description.textContent=blockedIngredients.length?`Filtrado según su especie y ${blockedIngredients.length} ${blockedIngredients.length===1?'restricción':'restricciones'} registradas`:exactPetRows.length?`Selección para ${pet.name}: ${pet.breed||pet.exact_species}, ${({baby:'bebé',young:'joven',adult:'adulta',senior:'senior'})[pet.life_stage]||'etapa pendiente'}. Son premios ocasionales, no su comida completa.`:feedingHub?'Guías específicas; la etiqueta y el especialista determinan cantidad y frecuencia':'Premios y complementos separados de su alimento completo';copy.append(title,description);const count=document.createElement('span');count.textContent=String(rows.length);heading.append(copy,count);section.append(heading);
      const grid=document.createElement('div');grid.className='recipe-category-grid';rows.forEach(recipe=>grid.append(recipeCard(recipe)));if(!rows.length){const empty=document.createElement('div');empty.className='empty category-empty';const emptyCopy={favorite:'<strong>Aún no hay favoritas</strong>Abre una preparación o guía guardada para marcarla como favorita.',treat:'<strong>No hay premios compatibles para este perfil</strong>Roxy no inventará una receta cuando la especie o sus restricciones necesiten una guía más precisa.',feeding_guide:'<strong>No hay una guía específica en este filtro</strong>Conserva el plan de alimentación guardado y confirma los cambios con su especialista.'};empty.innerHTML=emptyCopy[petRecipeFilter]||'<strong>No hay una receta segura disponible todavía</strong>Roxy no mostrará recetas genéricas. Completa los detalles de alimentación y salud del perfil para afinar las opciones.';grid.append(empty)}section.append(grid);root.append(section);return;
    }
    const visibleCategories=recipeSearch?recipeCategories.filter(category=>rows.some(recipe=>recipeCategoryId(recipe)===category.id)):recipeCategories.filter(category=>category.id===recipeFilter);
    visibleCategories.forEach(category=>{
      const categoryRows=rows.filter(recipe=>recipeCategoryId(recipe)===category.id);
      if(!categoryRows.length&&recipeFilter==='all')return;
      const section=document.createElement('section');section.className='recipe-category';section.dataset.recipeCategory=category.id;
      const heading=document.createElement('div');heading.className='recipe-category-heading';
      const copy=document.createElement('div');const title=document.createElement('h3');title.textContent=category.title;const description=document.createElement('p');description.textContent=category.description;copy.append(title,description);
      const count=document.createElement('span');count.textContent=String(categoryRows.length);count.setAttribute('aria-label',`${categoryRows.length} ${categoryRows.length===1?'receta':'recetas'} en ${category.title}`);heading.append(copy,count);section.append(heading);
      const grid=document.createElement('div');grid.className='recipe-category-grid';categoryRows.forEach(recipe=>grid.append(recipeCard(recipe)));
      if(!categoryRows.length){const empty=document.createElement('div');empty.className='empty category-empty';empty.textContent=`Todavía no hay ${category.title.toLowerCase()} disponibles.`;grid.append(empty);}
      section.append(grid);root.append(section);
    });
    if(!rows.length){const empty=document.createElement('div');empty.className='empty';empty.innerHTML=recipeFilter==='favorite'?'<strong>Aún no tienes favoritas</strong>Abre una receta para marcarla como favorita.':'<strong>No encontré coincidencias</strong>Prueba otra palabra o categoría.';root.replaceChildren(empty);}
  }
  function savedPets(){return Array.isArray(homeFood.pets)?homeFood.pets:[]}
  function selectedPetProfile(){const rows=savedPets();let pet=rows.find(row=>String(row.id)===selectedPetId);if(!pet&&rows.length){pet=rows[0];selectedPetId=String(pet.id||'');petSpecies=pet.species||'other'}return pet||null}
  const petSpeciesLabels={dog:'Perro',cat:'Gato',ferret:'Hurón',rabbit:'Conejo',guinea_pig:'Cobaya',hamster:'Hámster',small_mammal:'Pequeño mamífero',bird:'Ave',fish:'Pez',reptile:'Reptil',amphibian:'Anfibio',invertebrate:'Invertebrado',farm_pet:'Mascota de granja',other:'Otra especie'};
  function renderPetProfileCompletion(pet){const root=$('petProfileCompletion');root.replaceChildren();const completion=(homeFood.pet_profile_completions||{})[String(pet.id)]||{percent:0,missing:[],next_step:1};root.classList.toggle('complete',completion.status==='complete');const copy=document.createElement('div');const title=document.createElement('strong');title.innerHTML=`Perfil <b>${Number(completion.percent||0)}%</b> completo`;const progress=document.createElement('progress');progress.max=100;progress.value=Number(completion.percent||0);progress.textContent=completion.percent+'%';const detail=document.createElement('p');detail.textContent=completion.status==='complete'?'Perfil completo para recomendaciones personalizadas.':(completion.missing||[]).slice(0,2).map(item=>item.label).join(' · ');copy.append(title,progress,detail);root.append(copy);if(completion.status!=='complete'){const button=makeButton('Completar perfil','secondary',()=>{openPetProfile(pet);petProfileStep=Number(completion.next_step||1);renderPetProfileStep()});root.append(button)}}
  function openPetHubSection(section){petHubTab=section;renderRecipes();requestAnimationFrame(()=>$('petPersonalizedHub').scrollIntoView({behavior:'smooth',block:'start'}))}
  function renderPetHub(){const pet=selectedPetProfile();if(!pet)return;$('petHubTitle').textContent=pet.name;const details=[pet.breed||pet.exact_species||petSpeciesLabels[pet.species]||'Mascota',pet.life_stage&&pet.life_stage!=='unknown'?({baby:'Bebé',young:'Joven',adult:'Adulto',senior:'Senior'})[pet.life_stage]:'',pet.photo_data_url?'':'Foto pendiente'].filter(Boolean);$('petHubSummary').textContent=details.join(' · ');const avatar=$('petHubAvatar');avatar.replaceChildren();if(pet.photo_data_url){const image=document.createElement('img');image.src=pet.photo_data_url;image.alt='Foto de '+pet.name;avatar.append(image)}else{const icon=document.createElement('span');icon.className='material-symbols-rounded';icon.textContent='add_a_photo';avatar.append(icon)}const tabs=document.querySelector('.pet-hub-tabs');if(tabs)tabs.scrollLeft=0;document.querySelectorAll('[data-pet-hub-tab]').forEach(button=>{const active=button.dataset.petHubTab===petHubTab;button.classList.toggle('active',active);button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1});document.querySelectorAll('[data-pet-hub-panel]').forEach(panel=>panel.hidden=panel.dataset.petHubPanel!==petHubTab);if(petHubTab==='care')renderPetCare(pet);if(petHubTab==='products')renderPetProducts(pet);if(petHubTab==='medical'){renderPetMedicalHistory(pet);renderPetDocuments(pet)}}
  function petRoutineTimeLabel(value){const [hour,minute]=String(value||'').split(':').map(Number);if(!Number.isFinite(hour))return'';return new Intl.DateTimeFormat('es-US',{hour:'numeric',minute:'2-digit'}).format(new Date(2020,0,1,hour,minute||0))}
  async function completePetRoutine(pet,routine,button){button.disabled=true;try{await api(`/v1/home-food/${encodeURIComponent(user)}/pets/${encodeURIComponent(pet.id)}/care-log`,{method:'POST',body:JSON.stringify({routine_id:routine.id,title:routine.title})});await refreshHomeFood();announce(routine.title+' registrado para '+pet.name)}catch(error){button.disabled=false;announce(error.message)}}
  function renderPetDailySummary(pet,plan){
    const root=$('petDailySummary');root.replaceChildren();
    const now=new Date();
    const routines=(plan.routines||[]).map(row=>{const completed=new Date(row.last_completed_at||0);const valid=Number.isFinite(completed.getTime())&&completed.getTime()>0;const localToday=valid&&completed.toDateString()===now.toDateString();const withinWeek=valid&&now.getTime()>=completed.getTime()&&now.getTime()-completed.getTime()<7*24*60*60*1000;return{...row,completed_today:row.cadence==='weekly'?withinWeek:localToday}});
    const daily=routines.filter(row=>row.cadence==='daily');
    const completed=daily.filter(row=>row.completed_today).length;
    const next=routines.find(row=>!row.completed_today)||routines[0];
    const week=document.createElement('section');week.className='pet-week-strip';const weekHeading=document.createElement('div');weekHeading.innerHTML='<strong>Esta semana</strong><span class="material-symbols-rounded" aria-hidden="true">calendar_month</span>';week.append(weekHeading);const days=document.createElement('div');days.className='pet-week-days';const labels=['Dom','Lun','Mar','Mié','Jue','Vie','Sáb'];for(let offset=-2;offset<=2;offset+=1){const date=new Date(now);date.setDate(now.getDate()+offset);const day=document.createElement('span');if(offset===0)day.className='active';const name=document.createElement('small');name.textContent=labels[date.getDay()];const number=document.createElement('strong');number.textContent=String(date.getDate());const dot=document.createElement('i');day.append(name,number,dot);days.append(day)}week.append(days);root.append(week);
    const todayHeading=document.createElement('div');todayHeading.className='pet-today-heading';const todayTitle=document.createElement('strong');todayTitle.textContent='Hoy';const todayProgress=document.createElement('span');todayProgress.textContent=daily.length?`${completed} de ${daily.length} completados`:'Plan listo';todayHeading.append(todayTitle,todayProgress);root.append(todayHeading);
    const list=document.createElement('div');list.className='pet-routine-timeline';routines.forEach(routine=>{const row=document.createElement('article');row.className='pet-routine-row'+(routine.completed_today?' completed':'');const icon=document.createElement('span');icon.className='material-symbols-rounded';icon.setAttribute('aria-hidden','true');icon.textContent=routine.icon||'checklist';const time=document.createElement('time');time.textContent=petRoutineTimeLabel(routine.time)||'Hoy';const copy=document.createElement('div');const title=document.createElement('strong');title.textContent=routine.title;const meta=document.createElement('small');meta.textContent=routine.cadence==='weekly'?'Esta semana':routine.detail;copy.append(title,meta);const button=document.createElement('button');button.type='button';button.className='pet-routine-check';button.disabled=routine.completed_today;button.setAttribute('aria-label',(routine.completed_today?'Completado: ':'Registrar: ')+routine.title);button.innerHTML='<span class="material-symbols-rounded" aria-hidden="true">'+(routine.completed_today?'check':'done')+'</span>';button.addEventListener('click',()=>completePetRoutine(pet,routine,button));row.append(icon,time,copy,button);list.append(row)});root.append(list);
    if(next){const nextCard=document.createElement('article');nextCard.className='pet-next-routine pet-next-routine-featured';const icon=document.createElement('span');icon.className='material-symbols-rounded';icon.setAttribute('aria-hidden','true');icon.textContent='event_upcoming';const copy=document.createElement('div');const label=document.createElement('small');label.textContent='Próximo';const nextTitle=document.createElement('strong');nextTitle.textContent=next.title+(petRoutineTimeLabel(next.time)?' · '+petRoutineTimeLabel(next.time):'');copy.append(label,nextTitle);nextCard.append(icon,copy);if(!next.completed_today){const action=makeButton('Registrar ahora','pet-next-action',event=>completePetRoutine(pet,next,event.currentTarget));nextCard.append(action)}root.append(nextCard)}
    if(plan.routine_notes){const note=document.createElement('p');note.className='pet-routine-note';note.innerHTML='<strong>Tu rutina guardada:</strong> ';note.append(document.createTextNode(plan.routine_notes));root.append(note)}
  }
  function renderPetCare(pet){const plan=(homeFood.pet_care_plans||{})[String(pet.id)]||{};const info=plan.information||{};const identity=info.display_name||pet.breed||pet.exact_species||petSpeciesLabels[pet.species]||'su especie';$('petCareTitle').textContent='Todo sobre '+pet.name;$('petCareIntro').textContent=info.scope==='breed'?`Información específica de ${identity}, personalizada con la etapa y los datos guardados de ${pet.name}.`:`Información general de ${identity}, adaptada con los datos que guardaste.`;const root=$('petCarePlan');root.replaceChildren();const stats=document.createElement('div');stats.className='pet-info-stats';const feedingCount=Number(pet.feeding_frequency||0);const feedingFrequency=feedingCount?`${feedingCount} ${feedingCount===1?'vez':'veces'} al día`:(info.frequency||'Depende de su especie');[['schedule','Vida aproximada',info.life_expectancy||'Por confirmar'],['restaurant','Frecuencia de alimentación',feedingFrequency]].forEach(([iconName,label,value])=>{const card=document.createElement('article');card.innerHTML=`<span class="material-symbols-rounded" aria-hidden="true">${iconName}</span><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong>`;stats.append(card)});root.append(stats);const healthTitle=info.scope==='breed'?'Qué vigilar en su raza':'Enfermedades más comunes';const cards=[['psychology','Cómo es',info.characteristics],['health_and_safety',healthTitle,info.common_health],['nutrition','Alimentación',info.feeding],['auto_awesome','Dato curioso',info.fun_fact]];cards.forEach(([iconName,titleText,body])=>{if(!body)return;const card=document.createElement('article');card.className='pet-info-card';card.innerHTML=`<span class="material-symbols-rounded" aria-hidden="true">${iconName}</span><div><h4>${escapeHtml(titleText)}</h4><p>${escapeHtml(body)}</p></div>`;root.append(card)});if(plan.needs_exact_species){const notice=document.createElement('button');notice.type='button';notice.className='pet-care-exact';notice.innerHTML='<span class="material-symbols-rounded" aria-hidden="true">edit</span><span><strong>Completa la especie exacta</strong><small>Así Roxy podrá reemplazar los rangos generales por información específica.</small></span>';notice.addEventListener('click',()=>openPetProfile(pet));root.append(notice)}if(plan.source_url){const source=document.createElement('a');source.className='pet-care-source';source.href=plan.source_url;source.target='_blank';source.rel='noopener noreferrer';source.textContent='Consultar fuente veterinaria · '+plan.source_label;root.append(source)}}
  async function logPetFeeding(pet,outcome,button){const labels={all:'Comió todo',partial:'Comió parte',refused:'No quiso comer'};button.disabled=true;try{await api(`/v1/home-food/${encodeURIComponent(user)}/pets/${encodeURIComponent(pet.id)}/care-log`,{method:'POST',body:JSON.stringify({routine_id:'feeding_observation',title:'Registro de alimentación',outcome})});petHubTab='nutrition';await refreshHomeFood();announce(labels[outcome]+' registrado para '+pet.name)}catch(error){button.disabled=false;announce(error.message)}}
  function renderPetNutrition(pet){
    const plan=(homeFood.pet_nutrition_plans||{})[String(pet.id)]||{};const root=$('petNutritionPlan');root.replaceChildren();$('petNutritionTitle').textContent=plan.title||'Plan de alimentación';
    const overview=document.createElement('article');overview.className='pet-nutrition-overview';const icon=document.createElement('span');icon.className='material-symbols-rounded';icon.setAttribute('aria-hidden','true');icon.textContent='nutrition';const copy=document.createElement('div');const label=document.createElement('small');label.textContent=plan.configured?'Plan guardado':'Falta completar el plan';const title=document.createElement('strong');title.textContent=plan.current_food||'Añade su alimento actual';const framework=document.createElement('p');framework.textContent=plan.framework||'';copy.append(label,title,framework);overview.append(icon,copy);root.append(overview);
    const facts=document.createElement('div');facts.className='pet-nutrition-facts';const sourceLabels={label:'Etiqueta',veterinarian:'Veterinario',specialist:'Especialista',unknown:'Sin confirmar'};const rows=[['Cantidad total',plan.amount?`${plan.amount} ${plan.unit||''}`.trim():'Pendiente'],['Frecuencia',plan.frequency?`${plan.frequency} veces por día o ciclo`:'Pendiente'],['Horarios',(plan.times||[]).join(' · ')||'Pendientes'],['Fuente',sourceLabels[plan.amount_source]||'Sin confirmar']];rows.forEach(([name,value])=>{const item=document.createElement('span');const small=document.createElement('small');small.textContent=name;const strong=document.createElement('strong');strong.textContent=value;item.append(small,strong);facts.append(item)});root.append(facts);
    if(plan.feeding_notes){const note=document.createElement('p');note.className='pet-routine-note';note.innerHTML='<strong>Observaciones:</strong> ';note.append(document.createTextNode(plan.feeding_notes));root.append(note)}
    const tracking=document.createElement('section');tracking.className='pet-feeding-tracker';const trackTitle=document.createElement('div');const heading=document.createElement('strong');heading.textContent='¿Cómo comió?';const last=document.createElement('small');const outcomeLabels={all:'Comió todo',partial:'Comió parte',refused:'No quiso comer',completed:'Registrado'};last.textContent=plan.last_feeding?`Último registro: ${outcomeLabels[plan.last_feeding.outcome]||'Registrado'} · ${new Intl.DateTimeFormat('es',{dateStyle:'medium',timeStyle:'short'}).format(new Date(plan.last_feeding.completed_at))}`:'Todavía no hay registros de alimentación';trackTitle.append(heading,last);const actions=document.createElement('div');[['all','Comió todo'],['partial','Comió parte'],['refused','No quiso comer']].forEach(([value,text])=>{const button=document.createElement('button');button.type='button';button.className=value==='refused'?'secondary':'primary';button.textContent=text;button.addEventListener('click',()=>logPetFeeding(pet,value,button));actions.append(button)});tracking.append(trackTitle,actions);root.append(tracking);
    const safety=document.createElement('p');safety.className='pet-product-method';safety.textContent=plan.safety_note||'La etiqueta y las indicaciones profesionales prevalecen.';root.append(safety);if(plan.source_url){const source=document.createElement('a');source.className='pet-care-source';source.href=plan.source_url;source.target='_blank';source.rel='noopener noreferrer';source.textContent='Fuente de cuidado: '+plan.source_label;root.append(source)}
  }
  function renderPetProducts(pet){
    const root=$('petProductRecommendations');const filters=$('petProductFilters');root.replaceChildren();filters.replaceChildren();
    const catalogRows=(homeFood.pet_recommendations||{})[String(pet.id)]||[];const rankedRows=[...catalogRows].sort((left,right)=>Number(Boolean(right.identity_specific))-Number(Boolean(left.identity_specific))||Number(right.score||0)-Number(left.score||0));const seenProducts=new Set();const allRows=rankedRows.filter(row=>{const key=normalize(`${row.brand||''} ${row.name||''}`);if(!key||seenProducts.has(key))return false;seenProducts.add(key);return true});
    const categories=[...new Set(allRows.map(row=>row.category).filter(Boolean))];
    if(petProductFilter!=='all'&&!categories.includes(petProductFilter))petProductFilter='all';
    [['all','Todos'],...categories.map(value=>[value,value])].forEach(([value,label])=>{const button=document.createElement('button');button.type='button';button.className=value===petProductFilter?'active':'';button.textContent=label;button.addEventListener('click',()=>{petProductFilter=value;renderPetProducts(pet)});filters.append(button)});
    const rows=petProductFilter==='all'?allRows:allRows.filter(row=>row.category===petProductFilter);
    rows.forEach(product=>{const card=document.createElement('article');card.className='pet-product-card';if(product.image_url){const image=document.createElement('img');image.className='pet-product-photo';image.src=product.image_url;image.alt=`${product.brand} ${product.name}`;image.loading='lazy';card.append(image)}else{const missing=document.createElement('div');missing.className='pet-product-photo pet-product-photo-missing';missing.innerHTML='<span class="material-symbols-rounded" aria-hidden="true">inventory_2</span><small>Foto oficial pendiente</small>';card.append(missing)}const badge=document.createElement('span');badge.className='pet-product-rank';badge.textContent=product.identity_specific?'Coincidencia exacta':product.personalization_scope==='life_stage'?'Para su etapa':product.personalization_scope==='selected_goal'?'Para su objetivo':'Esencial para su especie';const copy=document.createElement('div');copy.className='pet-product-copy';const brand=document.createElement('small');brand.textContent=product.brand;const title=document.createElement('h4');title.textContent=product.name;const category=document.createElement('strong');category.textContent=product.category;const profile=document.createElement('i');profile.className='pet-product-profile';profile.textContent=product.profile_label||('Para '+pet.name);const reasonLabel=document.createElement('b');reasonLabel.textContent='Por qué encaja con '+pet.name;const reason=document.createElement('p');reason.textContent=product.reason;copy.append(brand,title,category,profile,reasonLabel,reason);if(product.requires_vet||product.requires_measurement||product.select_before_cart){const warning=document.createElement('em');warning.textContent=product.select_before_cart?'Elige primero la fórmula exacta en el catálogo oficial':product.requires_measurement?'Mide primero el contorno del pecho; Roxy no adivinará la talla':'Añádelo para revisar; confirma peso, uso o cambio de dieta antes de comprar';copy.append(warning)}const actions=document.createElement('div');actions.className='pet-product-actions';const source=document.createElement('a');source.href=product.source_url;source.target='_blank';source.rel='noopener noreferrer';source.textContent=product.select_before_cart?'Elegir fórmula oficial':'Información oficial';actions.append(source);if(!product.select_before_cart)actions.append(makeButton(product.requires_measurement?'Añadir para medir':product.requires_vet?'Añadir para revisar':'Añadir al carrito','primary',()=>addPetProduct(product,pet)));card.append(badge,copy,actions);root.append(card)});
    if(!rows.length){const empty=document.createElement('div');empty.className='empty';empty.innerHTML=allRows.length?'<strong>No hay productos en esta categoría</strong>Prueba otro filtro.':pet.exact_species?'<strong>Aún no hay un producto verificado para esta especie</strong>Roxy no inventará una marca. Conserva el plan de cuidado y consulta a un veterinario de exóticos para elegir el producto correcto.':'<strong>Completa la especie exacta</strong>Roxy la necesita antes de recomendar un producto concreto.';root.append(empty)}
  }
  async function addPetProduct(product,pet){try{await api('/v1/shopping/'+encodeURIComponent(user),{method:'POST',body:JSON.stringify({name:product.shopping_name,quantity:1,unit:'unidad',category:'PETS',notes:'Para '+pet.name+'. '+product.disclosure})});await load({quiet:true});announce(product.brand+' añadido a la lista para revisar; tú confirmarás producto, precio y compra.')}catch(error){announce(error.message)}}
  function renderPetMedicalHistory(pet){const root=$('petMedicalHistory');root.replaceChildren();const rows=[...(pet.medical_history||[])].reverse();rows.forEach(record=>{const card=document.createElement('article');const date=document.createElement('time');date.textContent=record.occurred_on||'Sin fecha';const copy=document.createElement('div');const title=document.createElement('strong');title.textContent=record.title;const meta=document.createElement('small');meta.textContent=[record.provider,(record.medications||[]).join(', '),record.weight_kg?`${record.weight_kg} kg`:''].filter(Boolean).join(' · ')||'Registro privado';copy.append(title,meta);if(record.next_due_on){const due=document.createElement('em');due.textContent=(record.next_due_on<new Date().toISOString().slice(0,10)?'Seguimiento vencido: ':'Próximo control: ')+record.next_due_on;copy.append(due)}if(record.notes){const notes=document.createElement('p');notes.textContent=record.notes;copy.append(notes)}if(record.attachment_data_url){const attachment=document.createElement('a');attachment.className='pet-medical-attachment';attachment.href=record.attachment_data_url;attachment.download=record.attachment_name||'documento';attachment.textContent='Abrir documento · '+(record.attachment_name||'archivo adjunto');copy.append(attachment)}card.append(date,copy);root.append(card)});if(!rows.length){const empty=document.createElement('div');empty.className='empty';empty.innerHTML='<strong>Aún no hay registros</strong>Añade consultas, vacunas, diagnósticos, peso, tratamientos o documentos para conservar el contexto de esta mascota.';root.append(empty)}}
  function renderPetDocuments(pet){const root=$('petDocuments');root.replaceChildren();const rows=[...(pet.medical_history||[])].filter(record=>record.attachment_data_url).reverse();rows.forEach(record=>{const card=document.createElement('a');card.className='pet-document-card';card.href=record.attachment_data_url;card.download=record.attachment_name||'documento';const icon=document.createElement('span');icon.className='material-symbols-rounded';icon.setAttribute('aria-hidden','true');icon.textContent=String(record.attachment_type||'').includes('pdf')?'picture_as_pdf':'image';const copy=document.createElement('span');const title=document.createElement('strong');title.textContent=record.attachment_name||record.title||'Documento';const detail=document.createElement('small');detail.textContent=[record.title,record.occurred_on].filter(Boolean).join(' · ');copy.append(title,detail);const arrow=document.createElement('span');arrow.className='material-symbols-rounded';arrow.setAttribute('aria-hidden','true');arrow.textContent='download';card.append(icon,copy,arrow);root.append(card)});if(!rows.length){const empty=document.createElement('div');empty.className='pet-documents-empty';empty.innerHTML='<span class="material-symbols-rounded" aria-hidden="true">folder_open</span><strong>Aún no hay documentos</strong><p>Guarda aquí resultados, recetas médicas, informes o imágenes junto a su historial.</p>';root.append(empty)}}
  async function sharePetWithVet(){const pet=selectedPetProfile();if(!pet)return;const recent=[...(pet.medical_history||[])].reverse().slice(0,5);const text=[`Pasaporte de ${pet.name}`,`${pet.breed||pet.exact_species||petSpeciesLabels[pet.species]||'Mascota'}${pet.life_stage&&pet.life_stage!=='unknown'?' · '+({baby:'Bebé',young:'Joven',adult:'Adulto',senior:'Senior'})[pet.life_stage]:''}`,pet.weight_kg?`Peso: ${pet.weight_kg} kg`:'',`Alimento actual: ${pet.current_food||'Pendiente de confirmar'}`,`Alergias: ${(pet.allergies||[]).join(', ')||'Ninguna registrada'}`,`Condiciones: ${(pet.conditions||[]).join(', ')||'Ninguna registrada'}`,recent.length?'Registros recientes:\n'+recent.map(record=>`${record.occurred_on||'Sin fecha'} · ${record.title}`).join('\n'):'Sin registros médicos todavía','Resumen generado por Roxy Home. No sustituye el expediente veterinario.'].filter(Boolean).join('\n');try{if(navigator.share)await navigator.share({title:'Pasaporte de '+pet.name,text});else{await navigator.clipboard.writeText(text);announce('Pasaporte copiado para compartir con su veterinario')}}catch(error){if(error.name!=='AbortError')announce('No pude abrir el menú para compartir')}}
  function exportPetMedicalSummary(){const pet=selectedPetProfile();if(!pet)return;const lines=[`RESUMEN PRIVADO DE ${pet.name.toUpperCase()}`,`Generado por Roxy Home: ${new Date().toLocaleString('es')}`,'',`Especie: ${petSpeciesLabels[pet.species]||pet.species||'Sin indicar'}`,`Especie exacta o raza: ${pet.breed||pet.exact_species||'Sin indicar'}`,`Edad: ${pet.age_years??'Sin indicar'}`,`Peso actual: ${pet.weight_kg?pet.weight_kg+' kg':'Sin indicar'}`,`Alimento actual: ${pet.current_food||'Sin indicar'}`,`Alergias: ${(pet.allergies||[]).join(', ')||'Ninguna registrada'}`,`Condiciones: ${(pet.conditions||[]).join(', ')||'Ninguna registrada'}`,`Indicaciones veterinarias: ${pet.veterinarian_instructions||'Ninguna registrada'}`,'','HISTORIAL'];(pet.medical_history||[]).forEach(record=>{lines.push('',`${record.occurred_on||'Sin fecha'} · ${record.title}`,record.provider?`Profesional: ${record.provider}`:'',record.weight_kg?`Peso: ${record.weight_kg} kg`:'',(record.medications||[]).length?`Medicamentos: ${record.medications.join(', ')}`:'',record.next_due_on?`Próximo control: ${record.next_due_on}`:'',record.notes||'')});lines.push('','Este resumen no sustituye el expediente ni las indicaciones del profesional.');const blob=new Blob([lines.filter(value=>value!==null).join('\n')],{type:'text/plain;charset=utf-8'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=`roxy-${String(pet.name||'mascota').toLowerCase().replace(/[^a-z0-9]+/g,'-')}-resumen.txt`;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);announce('Resumen privado preparado para descargar')}
  function exportPetVaccines(){const pet=selectedPetProfile();if(!pet)return;const rows=(pet.medical_history||[]).filter(record=>record.record_type==='vaccine'||/vacun/i.test(record.title||''));const lines=[`HISTORIAL DE VACUNACIÓN DE ${pet.name.toUpperCase()}`,`Generado por Roxy Home: ${new Date().toLocaleString('es')}`,'',...(rows.length?rows.flatMap(record=>[`${record.occurred_on||'Sin fecha'} · ${record.title}`,record.provider?`Profesional: ${record.provider}`:'',record.next_due_on?`Próxima dosis o control: ${record.next_due_on}`:'',record.notes||'','']):['No hay vacunas registradas todavía.']),'Este documento es un resumen personal y no sustituye el certificado veterinario.'];const blob=new Blob([lines.join('\n')],{type:'text/plain;charset=utf-8'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=`roxy-${String(pet.name||'mascota').toLowerCase().replace(/[^a-z0-9]+/g,'-')}-vacunas.txt`;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);announce('Historial de vacunas preparado para descargar')}
  function openPetMedical(){const pet=selectedPetProfile();if(!pet)return;$('petMedicalForm').reset();petMedicalAttachment=null;$('petMedicalAttachmentStatus').textContent='PDF o imagen de hasta 1 MB. Se guarda en el expediente privado.';$('petMedicalDate').value=new Date().toISOString().slice(0,10);$('petMedicalError').textContent='';$('petMedicalTitle').textContent='Añadir registro de '+pet.name;$('petMedicalDialog').showModal()}
  function readPetMedicalAttachment(file){return new Promise((resolve,reject)=>{if(!file)return resolve(null);if(!['application/pdf','image/jpeg','image/png','image/webp'].includes(file.type))return reject(new Error('Usa un PDF, JPEG, PNG o WebP.'));if(file.size>1_000_000)return reject(new Error('El archivo debe pesar 1 MB o menos.'));const reader=new FileReader();reader.onload=()=>resolve({name:file.name.slice(0,120),type:file.type,data_url:String(reader.result||'')});reader.onerror=()=>reject(new Error('No pude leer el documento.'));reader.readAsDataURL(file)})}
  async function choosePetMedicalAttachment(event){$('petMedicalError').textContent='';try{petMedicalAttachment=await readPetMedicalAttachment(event.target.files?.[0]);$('petMedicalAttachmentStatus').textContent=petMedicalAttachment?`${petMedicalAttachment.name} · listo para guardar`:'PDF o imagen de hasta 1 MB. Se guarda en el expediente privado.'}catch(error){event.target.value='';petMedicalAttachment=null;$('petMedicalError').textContent=error.message}}
  async function savePetMedical(event){event.preventDefault();const pet=selectedPetProfile();if(!pet)return;try{await api('/v1/home-food/'+encodeURIComponent(user)+'/pets/'+encodeURIComponent(pet.id)+'/medical-history',{method:'POST',body:JSON.stringify({occurred_on:$('petMedicalDate').value||null,record_type:$('petMedicalType').value,title:$('petMedicalRecordTitle').value.trim(),provider:$('petMedicalProvider').value.trim(),medications:commaPetValues($('petMedicalMedications').value),next_due_on:$('petMedicalNextDue').value||null,weight_kg:$('petMedicalWeight').value===''?null:Number($('petMedicalWeight').value),notes:$('petMedicalNotes').value.trim(),attachment_name:petMedicalAttachment?.name||'',attachment_type:petMedicalAttachment?.type||'',attachment_data_url:petMedicalAttachment?.data_url||''})});$('petMedicalDialog').close();petHubTab='medical';await refreshHomeFood();announce('Registro guardado en el expediente privado de la mascota')}catch(error){$('petMedicalError').textContent=error.message}}
  function renderPetProfiles(){const root=$('petProfiles');root.replaceChildren();const rows=savedPets();if(!rows.length)return;const selected=selectedPetProfile();rows.forEach(pet=>{const chip=document.createElement('button');chip.type='button';chip.className=`pet-profile${String(pet.id)===String(selected?.id)?' active':''}`;if(pet.photo_data_url){const image=document.createElement('img');image.src=pet.photo_data_url;image.alt='';chip.append(image)}else{const icon=document.createElement('span');icon.className='material-symbols-rounded';icon.textContent='pets';chip.append(icon)}const name=document.createElement('span');name.textContent=pet.name;chip.append(name);chip.addEventListener('click',()=>{selectedPetId=String(pet.id);petSpecies=pet.species||'other';petRecipeFilter='all';petProductFilter='all';renderPetProfiles();renderRecipes()});root.append(chip)});$('petSafetySummary').textContent=`Las recomendaciones para ${selected?.name||'tu mascota'} respetan sus restricciones y las indicaciones veterinarias guardadas.`}
  const commaPetValues=value=>String(value||'').split(',').map(row=>row.trim()).filter(Boolean).slice(0,30);
  const selectedChoiceValues=id=>[...$(id).querySelectorAll('button.active')].map(button=>button.dataset.value);
  function renderPetChoices(id,values,selected=[]){const root=$(id);root.replaceChildren();const chosen=new Set((selected||[]).map(normalize));(values||[]).forEach(value=>{const button=document.createElement('button');button.type='button';button.dataset.value=value;button.textContent=value;button.classList.toggle('active',chosen.has(normalize(value)));button.addEventListener('click',()=>{if(/ninguna/i.test(value)){root.querySelectorAll('button').forEach(row=>row.classList.remove('active'));button.classList.add('active')}else{root.querySelectorAll('button').forEach(row=>{if(/ninguna/i.test(row.dataset.value))row.classList.remove('active')});button.classList.toggle('active')}});root.append(button)})}
  function fillPetDataList(id,values){const root=$(id);root.replaceChildren();(values||[]).forEach(value=>{const option=document.createElement('option');option.value=value;root.append(option)})}
  function fillPetSelect(id,values){const select=$(id);const previous=select.value;select.replaceChildren();values.forEach(([value,label])=>{const option=document.createElement('option');option.value=value;option.textContent=label;select.append(option)});if(values.some(([value])=>value===previous))select.value=previous}
  function adaptPetHealthFields(species){const mammal=['dog','cat','ferret','rabbit','guinea_pig','hamster','small_mammal','farm_pet'].includes(species);$('petSterilizedField').hidden=!mammal;if(!mammal)$('petProfileSterilized').value='unknown';const aquatic=['fish','amphibian'].includes(species);const habitatSpecies=['fish','reptile','amphibian','bird','invertebrate'].includes(species);$('petSizeLabel').textContent=aquatic?'Tamaño aproximado':habitatSpecies?'Tamaño actual':'Tamaño adulto';fillPetSelect('petProfileSize',aquatic?[["unknown","No estoy seguro"],["toy","Muy pequeño"],["small","Pequeño"],["medium","Mediano"],["large","Grande"]]:habitatSpecies?[["unknown","No estoy seguro"],["toy","Muy pequeño"],["small","Pequeño"],["medium","Mediano"],["large","Grande"]]:[["unknown","No estoy seguro"],["toy","Mini / toy"],["small","Pequeño"],["medium","Mediano"],["large","Grande"],["giant","Gigante"]]);$('petBodyLabel').textContent=aquatic?'Estado corporal observado':'Condición corporal';fillPetSelect('petProfileBody',aquatic?[["unknown","No estoy seguro"],["underweight","Delgado o retraído"],["ideal","Aspecto habitual"],["overweight","Abultado o hinchado"]]:[["unknown","No estoy seguro"],["underweight","Bajo peso"],["ideal","Ideal"],["overweight","Sobrepeso"]]);$('petActivityLabel').textContent=aquatic?'Comportamiento y actividad':species==='reptile'||species==='amphibian'||species==='invertebrate'?'Actividad observada':'Nivel de actividad';fillPetSelect('petProfileActivity',mammal?[["unknown","No estoy seguro"],["low","Bajo"],["moderate","Moderado"],["high","Alto"],["working","Trabajo o deporte"]]:[["unknown","No estoy seguro"],["low","Baja"],["moderate","Habitual"],["high","Muy activa"]])}
  function adaptPetQuestions(pet={}){const species=$('petProfileSpecies').value||pet.species||'other';const options=homeFood.pet_options||{};fillPetDataList('petBreedOptions',(options.breeds||{})[species]||[]);fillPetDataList('petExactSpeciesOptions',(options.exact_species||{})[species]||[]);$('petBreedLabel').textContent=species==='dog'||species==='cat'?'Raza exacta':'Raza o variedad';$('petExactSpeciesLabel').textContent=['fish','reptile','amphibian','bird','small_mammal','invertebrate','farm_pet','other'].includes(species)?'Especie exacta':'Tipo o especie exacta';$('petProfileExactSpecies').required=['fish','reptile','amphibian','bird','small_mammal','invertebrate','farm_pet','other'].includes(species);adaptPetHealthFields(species);renderPetChoices('petAllergyChoices',(options.allergies||{})[species]||(options.allergies||{}).default,pet.allergies);renderPetChoices('petConditionChoices',(options.conditions||{})[species]||(options.conditions||{}).default,pet.conditions);renderPetChoices('petGoalChoices',(options.goals||{})[species]||(options.goals||{}).default,pet.goals);adaptPetEnvironment()}
  const petStepLabels=['Identidad','Salud','Alimentación','Entorno','Rutinas'];
  function renderPetProfileStep(){document.querySelectorAll('[data-pet-step]').forEach(field=>field.hidden=Number(field.dataset.petStep)!==petProfileStep);$('petProfileProgress').value=petProfileStep;$('petProfileProgress').textContent=`${petProfileStep} de 5`;$('petProfileStepLabel').textContent=`Paso ${petProfileStep} de 5 · ${petStepLabels[petProfileStep-1]}`;$('petProfileBack').hidden=petProfileStep===1;$('petProfileNext').hidden=petProfileStep===5;$('petProfileSave').hidden=petProfileStep!==5;$('petProfileError').textContent=''}
  function adaptPetEnvironment(){const species=$('petProfileSpecies').value;const copy={fish:['Acuario y agua','Tipo de acuario','Litros, agua dulce o salada, temperatura, pH, filtración, ciclado y compañeros…'],reptile:['Terrario y ambiente','Tipo de terrario','Dimensiones, gradiente térmico, humedad, UVB, sustrato y refugios…'],amphibian:['Hábitat y agua','Tipo de hábitat','Temperatura, humedad, calidad del agua, sustrato y compañeros…'],bird:['Espacio y vida social','Tipo de aviario o espacio','Dimensiones, tiempo de vuelo, perchas, luz, sueño, compañeros y seguridad…'],small_mammal:['Recinto y enriquecimiento','Tipo de recinto','Dimensiones, cama, profundidad de sustrato, rueda, refugios y convivencia…'],invertebrate:['Microhábitat','Tipo de terrario','Dimensiones, ventilación, sustrato, temperatura, humedad, muda y refugios…'],farm_pet:['Refugio y espacio exterior','Tipo de refugio','Dimensiones, cercado, sombra, agua, suelo, grupo y protección climática…']}[species]||['Entorno y bienestar','Tipo de hábitat','Casa, actividad, acceso exterior, convivencia y necesidades del espacio…'];$('petEnvironmentLegend').textContent=copy[0];$('petHabitatLabel').textContent=copy[1];$('petProfileHabitat').placeholder=copy[1];$('petProfileEnvironment').placeholder=copy[2];$('petAdaptiveHint').lastChild.textContent=` Roxy adaptará alimentación, frecuencia y cuidados para ${$('petProfileExactSpecies').value.trim()||'esta especie'}.`}
  function openPetProfile(pet=null){petProfileStep=1;petProfilePhotoData=pet?.photo_data_url||'';$('petProfileForm').reset();const values={petProfileName:pet?.name,petProfileSpecies:pet?.species,petProfileExactSpecies:pet?.exact_species,petProfileBreed:pet?.breed,petProfileAge:pet?.age_years,petProfileSex:pet?.sex,petProfileSterilized:pet?.sterilized,petProfileLifeStage:pet?.life_stage,petProfileWeight:pet?.weight_kg,petProfileSize:pet?.size_class,petProfileBody:pet?.body_condition,petProfileActivity:pet?.activity_level,petProfileCurrentFood:pet?.current_food,petProfileFoodKind:pet?.current_food_kind,petProfileFeedingAmount:pet?.feeding_amount,petProfileFeedingUnit:pet?.feeding_unit,petProfileFeedingFrequency:pet?.feeding_frequency,petProfileFeedingTimes:(pet?.feeding_times||[]).join(', '),petProfileFeedingSource:pet?.feeding_amount_source,petProfileFeedingNotes:pet?.feeding_notes,petProfileVetInstructions:pet?.veterinarian_instructions,petProfileHabitat:pet?.habitat_type,petProfileEnvironment:pet?.environment_notes,petProfileRoutine:pet?.routine_notes};Object.entries(values).forEach(([id,value])=>{if(value!==undefined&&value!==null)$(id).value=value});$('petPhotoPreview').replaceChildren();if(petProfilePhotoData){const image=document.createElement('img');image.src=petProfilePhotoData;image.alt='Foto de '+(pet?.name||'la mascota');$('petPhotoPreview').append(image)}else{const icon=document.createElement('span');icon.className='material-symbols-rounded';icon.textContent='add_a_photo';const label=document.createElement('strong');label.textContent='Añadir foto';$('petPhotoPreview').append(icon,label)}adaptPetQuestions(pet||{});renderPetProfileStep();$('petProfileDialog').showModal()}
  function validatePetStep(){if(petProfileStep===1){if(!$('petProfileSpecies').value)return'Selecciona el tipo de mascota.';if(!$('petProfileName').value.trim())return'Escribe el nombre de tu mascota.';if($('petProfileExactSpecies').required&&!$('petProfileExactSpecies').value.trim())return'Selecciona o escribe la especie exacta para personalizar sus cuidados.'}return''}
  function advancePetProfile(direction){const error=direction>0?validatePetStep():'';if(error){$('petProfileError').textContent=error;return}petProfileStep=Math.max(1,Math.min(5,petProfileStep+direction));if(petProfileStep===4)adaptPetEnvironment();renderPetProfileStep()}
  async function previewPetPhoto(event){const file=event.currentTarget.files?.[0];if(!file)return;try{petProfilePhotoData=await imageDataUrl(file);if(petProfilePhotoData.length>1_500_000)throw new Error('La foto es demasiado grande. Usa una imagen más pequeña.');const image=document.createElement('img');image.src=petProfilePhotoData;image.alt='Vista previa de la mascota';$('petPhotoPreview').replaceChildren(image)}catch(error){petProfilePhotoData='';event.currentTarget.value='';$('petProfileError').textContent=error.message}}
  async function savePetProfile(event){event.preventDefault();const error=validatePetStep();if(error){$('petProfileError').textContent=error;return}const button=$('petProfileSave');button.disabled=true;try{const payload={name:$('petProfileName').value.trim(),species:$('petProfileSpecies').value,exact_species:$('petProfileExactSpecies').value.trim(),breed:$('petProfileBreed').value.trim(),age_years:$('petProfileAge').value===''?null:Number($('petProfileAge').value),weight_kg:$('petProfileWeight').value===''?null:Number($('petProfileWeight').value),life_stage:$('petProfileLifeStage').value,sex:$('petProfileSex').value,sterilized:$('petProfileSterilized').value,size_class:$('petProfileSize').value,activity_level:$('petProfileActivity').value,body_condition:$('petProfileBody').value,goals:selectedChoiceValues('petGoalChoices'),allergies:[...selectedChoiceValues('petAllergyChoices'),...commaPetValues($('petProfileAllergies').value)],conditions:[...selectedChoiceValues('petConditionChoices'),...commaPetValues($('petProfileConditions').value)],current_food:$('petProfileCurrentFood').value.trim(),current_food_kind:$('petProfileFoodKind').value,feeding_amount:$('petProfileFeedingAmount').value===''?null:Number($('petProfileFeedingAmount').value),feeding_unit:$('petProfileFeedingUnit').value,feeding_frequency:$('petProfileFeedingFrequency').value===''?0:Number($('petProfileFeedingFrequency').value),feeding_times:commaPetValues($('petProfileFeedingTimes').value),feeding_amount_source:$('petProfileFeedingSource').value,feeding_notes:$('petProfileFeedingNotes').value.trim(),veterinarian_instructions:$('petProfileVetInstructions').value.trim(),habitat_type:$('petProfileHabitat').value.trim(),environment_notes:$('petProfileEnvironment').value.trim(),routine_notes:$('petProfileRoutine').value.trim(),photo_data_url:petProfilePhotoData};const result=await api('/v1/home-food/'+encodeURIComponent(user)+'/pets',{method:'POST',body:JSON.stringify(payload)});selectedPetId=String(result.pet.id);petSpecies=result.pet.species;$('petProfileDialog').close();recipeAudience='pet';await refreshHomeFood();selectPanel('pets');announce(result.pet.name+' ya tiene un perfil de cuidado personalizado')}catch(error){$('petProfileError').textContent=error.message}finally{button.disabled=false}}
  function addPet(){openPetProfile()}
  function setRecipeAudience(value){recipeAudience=value==='pet'?'pet':'human';if(recipeAudience==='human'&&!recipeCategories.some(row=>row.id===recipeFilter))recipeFilter='breakfast';if(recipeAudience==='pet'&&savedPets().length)petHubTab='care';document.querySelectorAll('[data-recipe-audience]').forEach(button=>button.classList.toggle('active',button.dataset.recipeAudience===recipeAudience));$('petRecipeContext').hidden=recipeAudience!=='pet';renderPetProfiles();renderRecipes();if(recipeAudience==='pet'&&!savedPets().length)requestAnimationFrame(()=>$('recipeImportStudio').scrollIntoView({block:'start',behavior:'smooth'}))}
  function openRecipeImporter(type){pendingImportedRecipe=null;$('recipeImportType').value=type;$('recipeImportDialogTitle').textContent=type==='image'?'Escanear una receta':'Importar receta desde un enlace';$('recipeImageField').hidden=type!=='image';$('recipeUrlField').hidden=type!=='url';$('recipeImportImage').value='';$('recipeImportUrl').value='';$('recipeImportPreview').hidden=true;$('recipeImportPreview').replaceChildren();$('recipeImportSave').hidden=true;$('recipeImportAnalyze').hidden=false;$('recipeImportAnalyze').disabled=false;$('recipeImportDialog').showModal()}
  function imageDataUrl(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=()=>reject(new Error('No pude leer la imagen'));reader.onload=()=>{const image=new Image();image.onerror=()=>reject(new Error('La imagen no es válida'));image.onload=()=>{const scale=Math.min(1,1600/Math.max(image.width,image.height));const canvas=document.createElement('canvas');canvas.width=Math.round(image.width*scale);canvas.height=Math.round(image.height*scale);canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);resolve(canvas.toDataURL('image/jpeg',.78))};image.src=reader.result};reader.readAsDataURL(file)})}
  function renderImportedRecipe(recipe){const root=$('recipeImportPreview');root.replaceChildren();const title=document.createElement('h3');title.textContent=recipe.title;const description=document.createElement('p');description.textContent=recipe.description||'Revisa los datos antes de guardar.';const facts=document.createElement('dl');[['Ingredientes',(recipe.ingredients||[]).length],['Pasos',(recipe.steps||[]).length],['Porciones',recipe.servings||1]].forEach(([label,value])=>{const dt=document.createElement('dt');dt.textContent=label;const dd=document.createElement('dd');dd.textContent=String(value);facts.append(dt,dd)});root.append(title,description,facts);if(recipe.audience==='pet'){const warning=document.createElement('p');warning.textContent=recipe.veterinary_note||'Consulta al veterinario si esta preparación será parte habitual de su alimentación.';root.append(warning)}root.hidden=false}
  async function analyzeRecipeImport(event){event.preventDefault();const type=$('recipeImportType').value;const button=$('recipeImportAnalyze');button.disabled=true;button.textContent='Roxy está leyendo…';try{let source='';if(type==='image'){const file=$('recipeImportImage').files[0];if(!file)throw new Error('Selecciona una foto, página o captura');source=await imageDataUrl(file)}else{source=$('recipeImportUrl').value.trim();if(!source)throw new Error('Escribe el enlace público de la receta')}const data=await api(`/v1/home-food/${encodeURIComponent(user)}/recipe-imports`,{method:'POST',body:JSON.stringify({source_type:type,source,audience:recipeAudience,pet_species:recipeAudience==='pet'?petSpecies:''})});if(data.status==='NEEDS_CLARIFICATION')throw new Error(data.question);pendingImportedRecipe=data.recipe;renderImportedRecipe(data.recipe);$('recipeImportSave').hidden=false;$('recipeImportAnalyze').hidden=true;announce('Revisa la receta antes de guardarla')}catch(error){announce(error.message)}finally{button.disabled=false;button.textContent='Analizar con Roxy'}}
  async function saveImportedRecipe(){if(!pendingImportedRecipe)return;const button=$('recipeImportSave');button.disabled=true;try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/recipe-imports/commit`,{method:'POST',body:JSON.stringify({confirmed:true,recipe:pendingImportedRecipe})});$('recipeImportDialog').close();pendingImportedRecipe=null;await load({quiet:true});setRecipeAudience(data.recipe.audience==='pet'?'pet':'human');openRecipe(data.recipe);announce('Receta importada y lista para cocinar')}catch(error){announce(error.message)}finally{button.disabled=false}}
  async function openCatalogRecipe(recipe){
    try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/recipes`,{method:'POST',body:JSON.stringify({prompt:recipe.title,mode:'routine',recipe_type:recipe.drink_type||'general',catalog_key:recipe.catalog_key||''})});await load({quiet:true});openRecipe(data.recipe);announce('Receta incluida guardada en tu carpeta')}
    catch(error){announce(error.message)}
  }
  function openRecipeByTitle(title){const key=normalize(title);const rows=[...(homeFood.recipes||[]),...(homeFood.local_recipes||[])];const recipe=rows.find(row=>normalize(row.title||'')===key)||rows.find(row=>{const candidate=normalize(row.title||'');return candidate.length>7&&(key.includes(candidate)||candidate.includes(key))});if(recipe){recipe.catalog_key?openCatalogRecipe(recipe):openRecipe(recipe)}else{selectPanel('recipes');$('recipeSearch').value=title;recipeSearch=key;renderRecipes()}}
  function recipeQuantity(value){const number=Number(value);if(!Number.isFinite(number))return String(value||'');const whole=Math.floor(number);const fraction=number-whole;const matches=[[.25,'1/4'],[1/3,'1/3'],[.5,'1/2'],[2/3,'2/3'],[.75,'3/4']];const match=matches.find(([candidate])=>Math.abs(fraction-candidate)<.015);if(match)return`${whole?`${whole} `:''}${match[1]}`;return new Intl.NumberFormat('es',{maximumFractionDigits:2}).format(number)}
  function addTextList(root,rows,ordered=false){const list=document.createElement(ordered?'ol':'ul');(rows||[]).forEach(row=>{const item=document.createElement('li');item.textContent=typeof row==='string'?row:`${recipeQuantity(row.quantity)} ${row.unit||''} de ${row.name||''}${row.notes?` · ${row.notes}`:''}`.trim();list.append(item)});root.append(list);}
  function openRecipe(recipe){
    const catalogPreview=Boolean(recipe.catalog_key&&!recipe.id);currentRecipe=recipe;$('recipeDialogTitle').textContent=recipe.title||'Receta de Roxy';$('recipeDialogEyebrow').textContent=catalogPreview?'Vista previa segura':'Receta guardada';
    const root=$('recipeDialogContent');root.replaceChildren();
    const hero=document.createElement('div');hero.className='recipe-detail-hero';const img=document.createElement('img');img.alt=`Resultado final de ${recipe.title||'la receta'}`;if(recipe.photo_focus)img.style.objectPosition=recipe.photo_focus;hydrateRecipeImage(img,recipe,hero);
    const intro=document.createElement('div');const meta=document.createElement('strong');const recipeLabel=recipe.audience==='pet'?`${recipe.safety_class==='feeding_guide'?'Guía':'Preparación'} para ${({dog:'perros',cat:'gatos',ferret:'hurones',rabbit:'conejos',guinea_pig:'cobayas',hamster:'hámsteres',small_mammal:'pequeños mamíferos',bird:'aves',fish:'peces',reptile:'reptiles',amphibian:'anfibios',invertebrate:'invertebrados',farm_pet:'mascotas de granja',other:'mascotas'})[recipe.pet_species]||'mascotas'}`:recipe.kind==='drink'?(recipe.drink_type==='alcoholic'?'Bebida con alcohol':'Bebida sin alcohol'):(recipeCategoryLabels[recipeCategoryId(recipe)]||kindLabels[recipe.kind]||'Receta');const servings=Number(recipe.servings||1);const yieldLabel=recipe.audience==='pet'?(recipe.safety_class==='feeding_guide'?'orientación sin porción automática':`${servings} ${servings===1?'pieza preparada':'piezas preparadas'}; no equivalen a porciones diarias`):`${servings} ${servings===1?'porción':'porciones'}`;meta.textContent=`${recipeLabel} · ${yieldLabel}`;
    const description=document.createElement('p');description.textContent=recipe.description||'Receta guardada por Roxy.';intro.append(meta,description);hero.append(img,intro);
    const videoArea=document.createElement('section');videoArea.className='recipe-video-area';videoArea.setAttribute('aria-live','polite');
    const columns=document.createElement('div');columns.className='recipe-columns';
    const ingredients=document.createElement('section');const ingTitle=document.createElement('h3');ingTitle.textContent='Ingredientes';ingredients.append(ingTitle);addTextList(ingredients,recipe.ingredients||[]);
    const steps=document.createElement('section');const stepTitle=document.createElement('h3');stepTitle.textContent='Preparación';steps.append(stepTitle);addTextList(steps,recipe.steps||[],true);columns.append(ingredients,steps);
    if(recipe.audience==='pet'){
      const safety=document.createElement('section');safety.className='recipe-pet-safety';
      const safetyTitle=document.createElement('strong');safetyTitle.textContent=recipe.safety_class==='treat'?'Premio ocasional':'Complemento, no dieta completa';
      const safetyCopy=document.createElement('p');safetyCopy.textContent=recipe.veterinary_note||'Consulta a tu veterinario antes de incorporarla de forma habitual, especialmente si tu mascota tiene alergias o una condición médica.';
      safety.append(safetyTitle,safetyCopy);columns.append(safety);
    }
    if(String(recipe.editorial_status||'').startsWith('verified')){
      const review=document.createElement('section');review.className='recipe-editorial-review';
      const reviewTitle=document.createElement('strong');reviewTitle.textContent='Receta verificada';review.append(reviewTitle);
      if(recipe.canonical_variant){const variant=document.createElement('p');variant.textContent=recipe.canonical_variant;review.append(variant)}
      const sources=(recipe.sources||[]).filter(source=>/^https:\/\//.test(String(source.url||'')));
      if(sources.length){const sourceLabel=document.createElement('span');sourceLabel.textContent='Fuente: ';review.append(sourceLabel);sources.slice(0,3).forEach((source,index)=>{const link=document.createElement('a');link.href=source.url;link.target='_blank';link.rel='noopener noreferrer';link.textContent=source.title||source.authority||'Referencia culinaria';if(index)review.append(document.createTextNode(' · '));review.append(link)})}
      columns.append(review);
    }
    const actions=document.createElement('div');actions.className='recipe-detail-actions';
    if(catalogPreview){const save=makeButton('Guardar en mi recetario','primary',()=>openCatalogRecipe(recipe));actions.append(save)}else{const add=makeButton('Agregar ingredientes','secondary',()=>previewRecipe(recipe.id,Number(recipe.servings||1)));const buy=makeButton('Buscar para comprar','secondary',()=>preparePurchase('recipe',recipe.id));const guide=makeButton('Cocinar paso a paso','primary',()=>startCooking(recipe.id));actions.append(add,buy,guide)}
    root.append(hero,columns,actions);
    $('recipePersonalForm').hidden=catalogPreview;$('recipeFavorite').checked=Boolean(recipe.favorite);
    $('recipeNotes').value=recipe.user_notes||'';
    $('recipePhoto').value='';
    if(!$('recipeDialog').open)$('recipeDialog').showModal();
    if(catalogPreview)videoArea.hidden=true;else loadRecipeVideo(recipe,videoArea);
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

  async function readDesignPhoto(file){
    if(!file)throw new Error('Toma o selecciona una foto de la habitación');
    if(!['image/jpeg','image/png','image/webp'].includes(file.type))throw new Error('La foto debe ser JPEG, PNG o WebP');
    if(file.size>12_000_000)throw new Error('La foto original es demasiado grande');
    const source=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result||''));reader.onerror=()=>reject(new Error('No pude leer la foto'));reader.readAsDataURL(file)});
    const image=await new Promise((resolve,reject)=>{const node=new Image();node.onload=()=>resolve(node);node.onerror=()=>reject(new Error('No pude procesar la foto'));node.src=source});
    const maxSide=1800;const scale=Math.min(1,maxSide/Math.max(image.naturalWidth,image.naturalHeight));
    const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(image.naturalWidth*scale));canvas.height=Math.max(1,Math.round(image.naturalHeight*scale));
    canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);
    return canvas.toDataURL('image/jpeg',.84);
  }

  const commaValues=value=>String(value||'').split(',').map(row=>row.trim()).filter(Boolean).slice(0,20);
  async function refreshPlants(){homePlants=await api(`/v1/home-plants/${encodeURIComponent(user)}`);await dbSet(`home-plants:${user}`,homePlants);renderPlants()}
  const plantSpeciesLabel=key=>(homePlants.species||[]).find(row=>row.key===key)?.common_name||'Especie por confirmar';
  function populatePlantSpecies(){const select=$('plantSpecies');if(!select)return;const selected=select.value||'unknown';select.replaceChildren();(homePlants.species||[]).forEach(row=>{const option=document.createElement('option');option.value=row.key;option.textContent=row.key==='unknown'?'Que Roxy la proponga':`${row.common_name} · ${row.scientific_name}`;select.append(option)});select.value=(homePlants.species||[]).some(row=>row.key===selected)?selected:'unknown'}
  const plantTaskIcons={CHECK_SOIL:'water_drop',ROTATE:'sync',FERTILIZE:'nutrition'};
  const plantDateLabel=value=>{const date=new Date(`${value}T12:00:00`);return Number.isNaN(date.getTime())?'Próximamente':new Intl.DateTimeFormat('es-US',{weekday:'long',day:'numeric',month:'short'}).format(date)};
  function plantConditionConcern(plant){const light=String(plant?.light||'').toLowerCase(),current=plant?.light_exposure;if(current==='direct_afternoon'&&light.includes('indirecta'))return'El sol directo de tarde puede ser demasiado intenso para esta especie. Revisa si hay hojas quemadas y considera moverla.';if(current==='low'&&light.includes('brillante'))return'La ubicación puede tener menos luz de la recomendada. Observa crecimiento débil o pérdida de color.';return''}
  function plantWeatherContext(){const ready=homeWeather&&homeWeather.status==='READY';const current=homeWeather.current||{};const temperature=Number(current.temperature);const code=Number(current.code);const rain=Number.isFinite(code)&&((code>=51&&code<=67)||(code>=80&&code<=82)||code>=95);return{ready,current,temperature,rain,hot:Number.isFinite(temperature)&&temperature>=85,cold:Number.isFinite(temperature)&&temperature<=50}}
  function renderPlantEnvironment(){const weather=plantWeatherContext();$('plantTodayDate').textContent=new Intl.DateTimeFormat('es-US',{weekday:'long',day:'numeric',month:'long',year:'numeric'}).format(new Date());$('plantWeatherIcon').textContent=weather.ready?(weather.current.icon||'partly_cloudy_day'):'location_off';$('plantWeatherTitle').textContent=weather.ready?`${Math.round(weather.temperature)} °F · ${weather.current.condition||'Clima local'}`:'Clima local sin activar';$('plantWeatherDetail').textContent=weather.ready?'Open-Meteo · Roxy ajusta cuándo conviene revisar, no riega automáticamente.':'Activa tu ubicación para adaptar los cuidados.';const environment=homePlants.environment||{};$('plantSensorTitle').textContent=environment.sensor_status==='connected'?`${Math.round(Number(environment.temperature_c||0))} °C · ${Math.round(Number(environment.humidity_percent||0))}% humedad`:'Sensor interior opcional';$('plantSensorDetail').textContent=environment.sensor_status==='connected'?'Datos reales del hogar':'No conectado · Roxy no inventará temperatura ni humedad.';let advice='Comprueba la tierra y las hojas antes de decidir qué hacer.';if(weather.hot)advice='Hace más calor: revisa la tierra antes de lo habitual, pero no riegues sin comprobarla.';else if(weather.rain)advice='Hay lluvia: protege las plantas sensibles y pausa el riego exterior si la tierra sigue húmeda.';else if(weather.cold)advice='Hace frío: evita corrientes y aleja las plantas sensibles de ventanas muy frías.';$('plantWeatherAdvice').textContent=advice}
  function renderPlants(){
    const collection=$('plantCollection'),tasksRoot=$('plantTasksToday'),upcomingRoot=$('plantUpcomingCare'),healthRoot=$('plantHealthSummary'),shopping=$('plantShoppingSuggestion');if(!collection||!tasksRoot)return;collection.replaceChildren();tasksRoot.replaceChildren();upcomingRoot.replaceChildren();healthRoot.replaceChildren();shopping.replaceChildren();populatePlantSpecies();renderPlantEnvironment();
    const plants=homePlants.plants||[],due=homePlants.due_today||[],upcoming=(homePlants.upcoming_care||[]).filter(task=>!due.some(row=>row.id===task.id));$('plantCount').textContent=`${plants.length} ${plants.length===1?'planta':'plantas'}`;
    const todayCard=$('todayPlantCareCard');todayCard.hidden=!plants.length;$('todayPlantCareTitle').textContent=due.length?`${due.length} ${due.length===1?'cuidado pendiente':'cuidados pendientes'}`:'Tus plantas están al día';$('todayPlantCareDetail').textContent=due.length?due.map(row=>row.plant_name).slice(0,3).join(' · '):`${plants.length} ${plants.length===1?'planta acompañada':'plantas acompañadas'}`;
    $('plantCareTodayTitle').textContent=due.length?`${due.length} ${due.length===1?'planta necesita':'plantas necesitan'} atención`:'Tu jardín está al día';
    if(!due.length){const empty=document.createElement('div');empty.className='plant-priority-empty';empty.innerHTML=plants.length?'<span class="material-symbols-rounded" aria-hidden="true">task_alt</span><div><strong>Nada urgente hoy</strong><p>Roxy seguirá pendiente del clima, el calendario y tus próximas revisiones.</p></div>':'<span class="material-symbols-rounded" aria-hidden="true">photo_camera</span><div><strong>Empieza con una foto</strong><p>Añade una planta para identificarla y crear su plan preventivo.</p></div>';tasksRoot.append(empty)}
    due.slice(0,2).forEach(task=>{const plant=plants.find(row=>row.id===task.plant_id);const row=document.createElement('article');row.className='plant-priority-card';const image=document.createElement('img');image.src=task.photo_url;image.alt='';const concern=plantConditionConcern(plant);const copy=document.createElement('div');copy.innerHTML=`<small>Prioridad · ${escapeHtml(task.title||'Revisión')}</small><strong>${escapeHtml(task.plant_name)}</strong><p>${escapeHtml(concern||plant?.soil_rule||'Observa la tierra y las hojas antes de actuar.')}</p>`;const actions=document.createElement('div');actions.append(makeButton('Hacer revisión','primary',()=>addPlantJournal(plant,task)),makeButton('Recordar','secondary',()=>createPlantReminder(task)));row.append(image,copy,actions);tasksRoot.append(row)});
    upcoming.slice(0,3).forEach(task=>{const row=document.createElement('article');row.className='plant-upcoming-row';const icon=document.createElement('span');icon.className='material-symbols-rounded';icon.setAttribute('aria-hidden','true');icon.textContent=plantTaskIcons[task.action]||'event_repeat';const copy=document.createElement('div');copy.innerHTML=`<small>${escapeHtml(plantDateLabel(task.due_date))}</small><strong>${escapeHtml(task.title)}</strong><span>${escapeHtml(task.plant_name)}</span>`;const remind=makeButton(task.calendar_event_id?'En calendario':'Recordar','secondary',()=>createPlantReminder(task));remind.disabled=Boolean(task.calendar_event_id);row.append(icon,copy,remind);upcomingRoot.append(row)});if(!upcoming.length){const empty=document.createElement('p');empty.className='plant-upcoming-empty';empty.textContent=plants.length?'Los próximos cuidados aparecerán aquí.':'Añade una planta para crear su calendario.';upcomingRoot.append(empty)}
    const health=homePlants.health_summary||{total:plants.length,good:plants.length,watch:due.length,needs_identification:0};[['Bien',health.good,'check_circle'],['Vigilando',health.watch,'visibility'],['Por identificar',health.needs_identification,'help']].forEach(([label,count,icon])=>{const item=document.createElement('span');item.innerHTML=`<span class="material-symbols-rounded" aria-hidden="true">${icon}</span><strong>${count}</strong><small>${label}</small>`;healthRoot.append(item)});
    shopping.hidden=!plants.length;if(plants.length){const plant=plants[0];shopping.innerHTML='<img src="/assets/roxy_home/plants-soil-meter.png" alt="Medidor de humedad colocado en una maceta" /><div><p class="eyebrow">Roxy te sugiere</p><h3>Medidor de humedad para plantas</h3><p>Puede ayudarte a comprobar el sustrato; no sustituye observar la planta ni revisar compatibilidad.</p></div>';shopping.append(makeButton('Revisar antes de agregar','secondary',()=>addPlantProduct(plant,'Medidor de humedad para plantas')))}
    if(!plants.length){const empty=document.createElement('div');empty.className='plants-empty';empty.innerHTML='<span class="material-symbols-rounded" aria-hidden="true">local_florist</span><strong>Tu jardín empieza con una foto</strong><p>Roxy propondrá la especie y tú confirmarás antes de usar el plan de cuidado.</p>';collection.append(empty);return}
    plants.forEach(plant=>{const card=document.createElement('button');card.type='button';card.className='plant-card';const image=document.createElement('img');image.src=plant.photo_url;image.alt=`${plant.display_name}, ${plant.common_name}`;const copy=document.createElement('span');const status=plant.identification?.status==='PROPOSED'||plant.species_key==='unknown'?'<em>Confirmar especie</em>':'';copy.innerHTML=`<small>${escapeHtml(plant.room||'Sin ubicación')}</small><strong>${escapeHtml(plant.display_name)}</strong><span>${escapeHtml(plant.common_name||plantSpeciesLabel(plant.species_key))}</span>${status}`;const arrow=document.createElement('span');arrow.className='material-symbols-rounded';arrow.textContent='arrow_forward';card.append(image,copy,arrow);card.addEventListener('click',()=>openPlantDetail(plant));collection.append(card)})
  }
  async function createPlantReminder(task){try{const result=await api(`/v1/home-plants/${encodeURIComponent(user)}/${encodeURIComponent(task.plant_id)}/reminders`,{method:'POST',body:JSON.stringify({task_id:task.id,time:'09:00',reminder_minutes:60})});await load({quiet:true});announce(result.sync?.synced?'Recordatorio sincronizado con el calendario de tu teléfono':'Recordatorio guardado en Roxy Calendar; conecta Google para verlo en el teléfono')}catch(error){announce(error.message)}}
  function openPlantDetail(plant){currentPlant=plant;$('plantDetailTitle').textContent=plant.display_name;const root=$('plantDetailContent');root.replaceChildren();const hero=document.createElement('div');hero.className='plant-detail-hero';const image=document.createElement('img');image.src=plant.photo_url;image.alt=`Foto de ${plant.display_name}`;const copy=document.createElement('span');copy.innerHTML=`<strong>${escapeHtml(plant.common_name||'Especie por confirmar')}</strong><em>${escapeHtml(plant.scientific_name||'')}</em><small>${escapeHtml(plant.room||'Sin ubicación')} · ${plant.placement==='outdoor'?'Exterior':'Interior'}</small>`;hero.append(image,copy);root.append(hero);
    if(plant.identification?.status==='PROPOSED'||plant.species_key==='unknown'){const warning=document.createElement('section');warning.className='plant-confirm-species';warning.innerHTML=`<strong>Confirma la identificación</strong><p>${escapeHtml(plant.identification?.warning||'La foto es una propuesta, no una identificación definitiva.')}</p>`;const select=document.createElement('select');(homePlants.species||[]).filter(row=>row.key!=='unknown').forEach(row=>{const option=document.createElement('option');option.value=row.key;option.textContent=`${row.common_name} · ${row.scientific_name}`;option.selected=row.key===plant.species_key;select.append(option)});const confirm=makeButton('Confirmar especie','primary',async()=>{try{await api(`/v1/home-plants/${encodeURIComponent(user)}/${encodeURIComponent(plant.id)}`,{method:'PATCH',body:JSON.stringify({species_key:select.value})});$('plantDetailDialog').close();await refreshPlants();announce('Especie confirmada y cuidados actualizados')}catch(error){announce(error.message)}});warning.append(select,confirm);root.append(warning)}
    const concern=plantConditionConcern(plant);if(concern){const warning=document.createElement('section');warning.className='plant-condition-warning';warning.innerHTML=`<span class="material-symbols-rounded" aria-hidden="true">wb_sunny</span><div><strong>Ubicación a revisar</strong><p>${escapeHtml(concern)}</p></div>`;root.append(warning)}
    const lightLabels={unknown:'No confirmada',low:'Poca luz',indirect:'Luz indirecta',bright_indirect:'Luz indirecta brillante',direct_morning:'Sol directo de mañana',direct_afternoon:'Sol directo de tarde'};const facts=document.createElement('div');facts.className='plant-facts';[['Tipo de planta','eco',plant.plant_type],['Luz recomendada','light_mode',plant.light],['Luz en su lugar','wb_sunny',lightLabels[plant.light_exposure]||'No confirmada'],['Cuándo revisar','water_drop',plant.soil_rule],['Temperatura','thermostat',plant.temperature],['Humedad','humidity_percentage',plant.humidity],['Fertilizante','nutrition',plant.fertilizer],['Dato curioso','lightbulb',plant.history],['Mascotas',plant.pet_safe?'pets':'warning',plant.toxicity]].forEach(([title,icon,value])=>{const row=document.createElement('section');row.innerHTML=`<span class="material-symbols-rounded" aria-hidden="true">${icon}</span><div><strong>${title}</strong><p>${escapeHtml(value||'Información no confirmada')}</p></div>`;facts.append(row)});root.append(facts);
    const journal=plant.journal||[];if(journal.length){const history=document.createElement('section');history.className='plant-journal';history.innerHTML='<h3>Seguimiento visual</h3>';[...journal].reverse().forEach(entry=>{const row=document.createElement('article');if(entry.photo_url){if(String(entry.media_type||'').startsWith('video/')){const video=document.createElement('video');video.src=entry.photo_url;video.controls=true;video.preload='metadata';video.setAttribute('aria-label',`Video de evolución de ${plant.display_name}`);row.append(video)}else{const photo=document.createElement('img');photo.src=entry.photo_url;photo.alt=`Evolución de ${plant.display_name}`;row.append(photo)}}const copy=document.createElement('div');const stamp=new Date(entry.created_at||'');copy.innerHTML=`<strong>${Number.isNaN(stamp.getTime())?'Registro':stamp.toLocaleDateString('es-US',{day:'numeric',month:'long',year:'numeric'})}</strong><p>${escapeHtml(entry.notes||'Sin observaciones')}</p>`;row.append(copy);history.append(row)});root.append(history)}
    const actions=document.createElement('div');actions.className='plant-detail-actions';actions.append(makeButton('Revisar con foto o video','primary',()=>addPlantJournal(plant)),makeButton('Preparar compra de cuidado','secondary',()=>addPlantProduct(plant)),makeButton('Eliminar planta','danger-button',()=>deletePlant(plant)));root.append(actions);$('plantDetailDialog').showModal()}
  async function readPlantReviewMedia(file){if(!file)throw new Error('Selecciona una foto o video');if(file.type.startsWith('image/'))return readPlantPhoto(file);if(file.type!=='video/mp4')throw new Error('El video debe ser MP4');if(file.size>12_000_000)throw new Error('El video debe pesar 12 MB o menos');return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result||''));reader.onerror=()=>reject(new Error('No pude leer el video'));reader.readAsDataURL(file)})}
  async function addPlantJournal(plant,task=null){if(!plant)return;const picker=document.createElement('input');picker.type='file';picker.accept='image/jpeg,image/png,image/webp,video/mp4';picker.capture='environment';picker.addEventListener('change',async()=>{if(!picker.files?.[0])return;const notes=window.prompt('¿Qué observaste? Ej. hoja nueva, tierra húmeda, borde seco','')||'Revisión visual';try{const media=await readPlantReviewMedia(picker.files[0]);await api(`/v1/home-plants/${encodeURIComponent(user)}/${encodeURIComponent(plant.id)}/journal`,{method:'POST',body:JSON.stringify({notes,photo_data_url:media})});if(task)await api(`/v1/home-plants/${encodeURIComponent(user)}/${encodeURIComponent(plant.id)}/tasks/${encodeURIComponent(task.id)}/complete`,{method:'POST',body:JSON.stringify({observation:notes})});await refreshPlants();const updated=(homePlants.plants||[]).find(row=>row.id===plant.id);if(updated&&!task)openPlantDetail(updated);announce(task?'Revisión registrada y próximo cuidado programado':'Revisión guardada en su seguimiento visual')}catch(error){announce(error.message)}});picker.click()}
  async function addPlantProduct(plant,productName=''){const name=productName||`Fertilizante para ${plant.common_name||plant.display_name}`;try{await api(`/v1/shopping/${encodeURIComponent(user)}`,{method:'POST',body:JSON.stringify({name,quantity:1,unit:'unidad',category:'HOUSEHOLD',notes:`Para ${plant.display_name}. Revisar marca, etiqueta, compatibilidad, precio y disponibilidad antes de comprar.`})});await load({quiet:true});if($('plantDetailDialog').open)$('plantDetailDialog').close();selectPanel('shopping');announce('Producto preparado en tu lista para que lo revises antes de comprar')}catch(error){announce(error.message)}}
  async function deletePlant(plant){if(!window.confirm(`¿Eliminar ${plant.display_name} de Mi jardín?`))return;try{await api(`/v1/home-plants/${encodeURIComponent(user)}/${encodeURIComponent(plant.id)}`,{method:'DELETE'});$('plantDetailDialog').close();await refreshPlants();announce('Planta eliminada de Mi jardín')}catch(error){announce(error.message)}}
  async function readPlantPhoto(file){return readDesignPhoto(file)}
  async function submitPlant(event){event.preventDefault();const form=event.currentTarget;const button=$('plantSubmit');button.disabled=true;button.textContent='Roxy está observando…';try{const photo=await readPlantPhoto($('plantPhoto').files[0]);let speciesKey=$('plantSpecies').value;if(speciesKey==='unknown'&&homePlants.identification_configured){const identified=await api(`/v1/home-plants/${encodeURIComponent(user)}/identify`,{method:'POST',body:JSON.stringify({photo_data_url:photo})});const proposal=identified.proposal||{};if(proposal.species_key&&proposal.species_key!=='unknown'){const label=plantSpeciesLabel(proposal.species_key);const confidence=Math.round(Number(proposal.confidence||0)*100);const confirmed=window.confirm(`Roxy propone que es ${label} (${confidence}% de confianza). La foto no sustituye una identificación experta. ¿Confirmas esta especie?`);$('plantSpecies').value=proposal.species_key;if(!confirmed){announce('Revisa la especie propuesta y pulsa Añadir cuando esté correcta');return}speciesKey=proposal.species_key}}const data=await api(`/v1/home-plants/${encodeURIComponent(user)}`,{method:'POST',body:JSON.stringify({display_name:$('plantName').value,species_key:speciesKey,room:$('plantRoom').value,placement:$('plantPlacement').value,pot_type:$('plantPot').value,drainage:$('plantDrainage').checked,light_exposure:$('plantLightExposure').value,notes:$('plantNotes').value,photo_data_url:photo})});$('plantDialog').close();form.reset();await refreshPlants();if(data.plant?.identification?.status==='CONFIRMED')announce('Planta confirmada y añadida a Mi jardín');else announce('Planta añadida. Abre su ficha para confirmar la especie.')}catch(error){announce(error.message)}finally{button.disabled=false;button.textContent='Analizar y añadir'}}
  async function savePlantVacation(event){event.preventDefault();try{await api(`/v1/home-plants/${encodeURIComponent(user)}/vacation`,{method:'PUT',body:JSON.stringify({enabled:$('plantVacationEnabled').checked,starts_on:$('plantVacationStart').value,ends_on:$('plantVacationEnd').value,caregiver:$('plantVacationCaregiver').value,notes:$('plantVacationNotes').value})});$('plantVacationDialog').close();await refreshPlants();announce('Plan de viaje guardado para el hogar')}catch(error){announce(error.message)}}

  const familyPlaceIcons={HOME:'home',WORK:'business_center',STORE:'storefront',OTHER:'location_on'};
  const familyPlaceLabels={HOME:'Casa',WORK:'Trabajo',STORE:'Tienda frecuente',OTHER:'Otro lugar'};
  const familyInitials=name=>String(name||'?').trim().split(/\s+/).slice(0,2).map(row=>row[0]||'').join('').toUpperCase();
  const familyTime=value=>{if(!value)return'';const date=new Date(value);return Number.isNaN(date.getTime())?'':new Intl.DateTimeFormat('es',{day:'numeric',month:'short',hour:'numeric',minute:'2-digit'}).format(date)};
  function currentBrowserPosition(){
    if(!navigator.geolocation)return Promise.reject(new Error('Este navegador no permite compartir ubicación'));
    return new Promise((resolve,reject)=>navigator.geolocation.getCurrentPosition(position=>resolve({latitude:position.coords.latitude,longitude:position.coords.longitude,accuracy_m:position.coords.accuracy}),error=>{const messages={1:'No autorizaste la ubicación. Puedes activarla en los ajustes del navegador.',2:'No pude determinar tu ubicación ahora.',3:'La ubicación tardó demasiado. Inténtalo nuevamente.'};reject(new Error(messages[error.code]||'No pude obtener tu ubicación'))},{enableHighAccuracy:false,maximumAge:60000,timeout:12000}));
  }
  const browserLocationPayload=position=>({latitude:position.coords.latitude,longitude:position.coords.longitude,accuracy_m:position.coords.accuracy,altitude_m:position.coords.altitude,speed_mps:position.coords.speed,heading_deg:position.coords.heading,recorded_at:new Date(position.timestamp).toISOString(),consent:true});
  function familyAvatarNode(member,className='family-member-avatar'){
    const avatar=document.createElement('span');avatar.className=className;avatar.style.background=familyMarkerColors[member.marker_color]||familyMarkerColors.FOREST;
    if(member.profile_photo){const image=document.createElement('img');image.src=member.profile_photo;image.alt='';avatar.append(image)}else avatar.textContent=member.profile_emoji||familyInitials(member.display_name);
    return avatar;
  }
  function familyWeatherMode(){
    if(homeWeather.status!=='READY')return '';
    const current=homeWeather.current||{};const code=Number(current.code);
    if(!Number.isFinite(code))return '';
    if(code>=95)return 'storm';
    if(code>=71&&code<=86)return 'snow';
    if((code>=51&&code<=67)||(code>=80&&code<=82))return 'rain';
    if(code===45||code===48)return 'fog';
    if(code===0)return current.is_day===false?'clear-night':'sunny';
    if(code<=3)return 'cloudy';
    const feels=Number(current.feels_like);
    return Number.isFinite(feels)&&feels<=45?'cold':'';
  }
  function renderFamilyWeatherFx(){
    const root=$('familyWeatherFx'),note=$('familyWeatherFxNote');if(!root)return;const mode=familyWeatherMode();root.className=`family-weather-fx${mode?` is-${mode}`:''}`;
    if(root.dataset.mode!==mode){root.replaceChildren();root.dataset.mode=mode;const count={rain:42,storm:54,snow:32,cloudy:5,fog:5}[mode]||0;for(let index=0;index<count;index+=1){const particle=document.createElement('i');particle.style.setProperty('--x',`${(index*37)%101}%`);particle.style.setProperty('--y',`${12+(index*19)%54}%`);particle.style.setProperty('--delay',`${-((index*173)%3200)}ms`);particle.style.setProperty('--duration',`${900+(index*97)%1700}ms`);particle.style.setProperty('--size',`${4+(index*7)%8}px`);root.append(particle)}}
    if(note){note.hidden=!mode||familyWeatherGlobeActive;note.textContent=`Ambiente visual ${({rain:'de lluvia',storm:'de tormenta',snow:'de nieve',cloudy:'de nubes',fog:'de niebla'}[mode]||'meteorológico')} según Open-Meteo`}
  }
  async function loadFamilyRadarMetadata(force=false){
    if(!force&&familyRadarMetadata&&Date.now()-familyRadarFetchedAt<300000)return familyRadarMetadata;
    const response=await fetch('https://api.rainviewer.com/public/weather-maps.json',{cache:'no-store'});if(!response.ok)throw new Error(`RainViewer HTTP ${response.status}`);
    const metadata=await response.json(),frames=(metadata.radar?.past||[]).slice(-10);if(!metadata.host||!frames.length)throw new Error('RainViewer no entregó fotogramas de radar');
    familyRadarMetadata={host:metadata.host,frames};familyRadarFetchedAt=Date.now();return familyRadarMetadata;
  }
  function familyWeatherGlobeCenter(){
    const viewer=(homeFamily.members||[]).find(row=>row.is_viewer&&row.location),weather=homeWeather.location||{},source=viewer?.location||weather;
    const lat=Number(source.latitude),lng=Number(source.longitude);return Number.isFinite(lat)&&Number.isFinite(lng)?[lng,lat]:[-81.3792,28.5383];
  }
  function familyWeatherGlobeStyle(){return{version:8,projection:{type:'globe'},sources:{osm:{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,attribution:'© OpenStreetMap contributors'}},layers:[{id:'space',type:'background',paint:{'background-color':'#020a0f'}},{id:'osm-dark',type:'raster',source:'osm',paint:{'raster-opacity':.94,'raster-saturation':-.82,'raster-contrast':.3,'raster-brightness-min':0,'raster-brightness-max':.22}}]}}
  function setFamilyWeatherGlobeFrame(index){
    if(!familyWeatherGlobeFrames.length)return;familyWeatherGlobeFrameIndex=Math.max(0,Math.min(Number(index)||0,familyWeatherGlobeFrames.length-1));const frame=familyWeatherGlobeFrames[familyWeatherGlobeFrameIndex],source=familyWeatherGlobeMap?.getSource('rainviewer-radar');
    if(source?.setTiles)source.setTiles([`${familyRadarMetadata.host}${frame.path}/256/{z}/{x}/{y}/2/1_1.png`]);
    $('familyWeatherGlobeTimeline').value=String(familyWeatherGlobeFrameIndex);$('familyWeatherGlobeTime').textContent=new Intl.DateTimeFormat('es-US',{hour:'numeric',minute:'2-digit'}).format(new Date(frame.time*1000));
  }
  function stopFamilyWeatherGlobePlayback(){if(familyWeatherGlobeTimer){clearInterval(familyWeatherGlobeTimer);familyWeatherGlobeTimer=null}}
  function syncFamilyWeatherGlobePlayback(){
    stopFamilyWeatherGlobePlayback();const button=$('familyWeatherGlobePlay'),icon=button.querySelector('.material-symbols-rounded'),label=button.querySelector('b');icon.textContent=familyWeatherGlobePlaying?'pause':'play_arrow';label.textContent=familyWeatherGlobePlaying?'Pausar':'Reproducir';button.setAttribute('aria-label',label.textContent+' animación');
    if(familyWeatherGlobePlaying&&familyWeatherGlobeFrames.length>1)familyWeatherGlobeTimer=setInterval(()=>setFamilyWeatherGlobeFrame((familyWeatherGlobeFrameIndex+1)%familyWeatherGlobeFrames.length),850);
  }
  function ensureFamilyWeatherGlobe(){
    if(familyWeatherGlobeMap)return familyWeatherGlobeMap;if(!window.maplibregl)throw new Error('El visor 3D no pudo cargarse');
    familyWeatherGlobeMap=new maplibregl.Map({container:'familyWeatherGlobe',style:familyWeatherGlobeStyle(),center:familyWeatherGlobeCenter(),zoom:1.35,minZoom:0,maxZoom:10,pitch:0,bearing:0,renderWorldCopies:false,attributionControl:false,dragRotate:true,touchZoomRotate:true});
    familyWeatherGlobeMap.addControl(new maplibregl.NavigationControl({showCompass:true,showZoom:true,visualizePitch:true}),'bottom-right');familyWeatherGlobeMap.addControl(new maplibregl.AttributionControl({compact:true}),'bottom-left');
    familyWeatherGlobeMap.on('load',()=>{familyWeatherGlobeMap.setProjection?.({type:'globe'});if(familyRadarMetadata&&familyWeatherGlobeFrames.length)installFamilyWeatherGlobeRadar()});
    familyWeatherGlobeMap.on('zoomend',()=>{if(familyWeatherGlobeActive&&!familyMapTransitioning&&familyWeatherGlobeMap.getZoom()>=5.35)exitFamilyWeatherGlobe({useGlobeCenter:true})});
    familyWeatherGlobeMap.on('error',event=>{if(String(event?.error?.message||'').includes('openstreetmap')){$('familyWeatherGlobeNotice').textContent='El mapa base está degradado, pero el globo y los controles siguen disponibles. El radar solo se muestra cuando RainViewer entrega datos reales.'}});return familyWeatherGlobeMap;
  }
  function installFamilyWeatherGlobeRadar(){
    if(!familyWeatherGlobeMap?.isStyleLoaded()||!familyWeatherGlobeFrames.length)return;const frame=familyWeatherGlobeFrames[familyWeatherGlobeFrameIndex]||familyWeatherGlobeFrames.at(-1),tiles=[`${familyRadarMetadata.host}${frame.path}/256/{z}/{x}/{y}/2/1_1.png`];
    if(!familyWeatherGlobeMap.getSource('rainviewer-radar')){familyWeatherGlobeMap.addSource('rainviewer-radar',{type:'raster',tiles,tileSize:256,minzoom:0,maxzoom:7,attribution:'Radar © RainViewer'});familyWeatherGlobeMap.addLayer({id:'rainviewer-radar',type:'raster',source:'rainviewer-radar',paint:{'raster-opacity':.78,'raster-fade-duration':180,'raster-saturation':.18,'raster-contrast':.12}})}else familyWeatherGlobeMap.getSource('rainviewer-radar').setTiles?.(tiles);setFamilyWeatherGlobeFrame(familyWeatherGlobeFrameIndex);
  }
  async function activateFamilyWeatherGlobe(){
    if(familyWeatherGlobeActive)return;familyWeatherGlobeActive=true;familyMapTransitioning=true;const panel=$('familyWeatherGlobePanel');panel.classList.add('is-active');panel.setAttribute('aria-hidden','false');document.body.classList.add('family-globe-active');$('familyWeatherFxNote').hidden=true;
    const current=homeWeather.current||{},location=homeWeather.location||{};$('familyWeatherGlobeCurrent').textContent=homeWeather.status==='READY'?`${current.emoji||''} ${Math.round(Number(current.temperature||0))}° · ${current.condition||'Clima actual'} · ${location.label||'Tu ubicación'} · Open-Meteo`:'Clima actual no activado · el radar global puede explorarse sin compartir ubicación';
    try{const map=ensureFamilyWeatherGlobe(),googleCenter=familyMap?.getCenter?.(),center=googleCenter?[googleCenter.lng(),googleCenter.lat()]:familyWeatherGlobeCenter();map.jumpTo({center,zoom:1.65});requestAnimationFrame(()=>map.resize());setTimeout(()=>{familyMapTransitioning=false},520);const loadId=++familyWeatherGlobeLoadId;$('familyWeatherGlobeStatus').textContent='Conectando con RainViewer…';const metadata=await loadFamilyRadarMetadata();if(loadId!==familyWeatherGlobeLoadId||!familyWeatherGlobeActive)return;familyWeatherGlobeFrames=metadata.frames;familyWeatherGlobeFrameIndex=familyWeatherGlobeFrames.length-1;const timeline=$('familyWeatherGlobeTimeline');timeline.max=String(familyWeatherGlobeFrames.length-1);timeline.disabled=false;$('familyWeatherGlobePlay').disabled=familyWeatherGlobeFrames.length<2;installFamilyWeatherGlobeRadar();$('familyWeatherGlobeStatus').textContent='Radar real · últimas 2 horas';familyWeatherGlobePlaying=true;syncFamilyWeatherGlobePlayback()}catch(error){familyMapTransitioning=false;stopFamilyWeatherGlobePlayback();familyWeatherGlobeFrames=[];$('familyWeatherGlobeTimeline').disabled=true;$('familyWeatherGlobePlay').disabled=true;$('familyWeatherGlobeStatus').textContent='Radar temporalmente no disponible';$('familyWeatherGlobeTime').textContent='Globo interactivo activo';$('familyWeatherGlobeNotice').textContent=`RainViewer no respondió (${error.message}). El globo y el clima actual de Open-Meteo siguen disponibles; no se muestran datos simulados.`;console.warn('Radar meteorológico no disponible',error)}
  }
  function exitFamilyWeatherGlobe({useGlobeCenter=false}={}){
    if(!familyWeatherGlobeActive)return;familyWeatherGlobeActive=false;familyMapTransitioning=true;stopFamilyWeatherGlobePlayback();familyWeatherGlobeLoadId+=1;const panel=$('familyWeatherGlobePanel');panel.classList.remove('is-active');panel.setAttribute('aria-hidden','true');document.body.classList.remove('family-globe-active');renderFamilyWeatherFx();
    if(familyMap){if(useGlobeCenter&&familyWeatherGlobeMap){const center=familyWeatherGlobeMap.getCenter();familyMap.setCenter({lat:center.lat,lng:center.lng})}familyMap.setZoom(7)}setTimeout(()=>{familyMapTransitioning=false},520);
  }
  function familyWeatherMapStyles(baseStyles){
    const mode=familyWeatherMode();
    const atmosphere={
      sunny:[{elementType:'geometry',stylers:[{saturation:10},{lightness:4}]}],
      cloudy:[{elementType:'geometry',stylers:[{saturation:-38},{lightness:-5},{gamma:.92}]}],
      fog:[{elementType:'geometry',stylers:[{saturation:-58},{lightness:10},{gamma:1.08}]}],
      rain:[{elementType:'geometry',stylers:[{saturation:-52},{lightness:-10},{gamma:.86}]}],
      storm:[{elementType:'geometry',stylers:[{saturation:-70},{lightness:-18},{gamma:.78}]}],
      snow:[{elementType:'geometry',stylers:[{saturation:-50},{lightness:13},{gamma:1.12}]}],
      'clear-night':[{elementType:'geometry',stylers:[{saturation:-44},{lightness:-19},{gamma:.76}]}],
      cold:[{elementType:'geometry',stylers:[{saturation:-22},{lightness:5},{gamma:1.02}]}]
    };
    return [...baseStyles,...(atmosphere[mode]||[])];
  }
  function familyHistorySegments(points=[]){
    const raw=points.map(point=>({lat:Number(point.latitude),lng:Number(point.longitude),accuracy:Number(point.accuracy_m||0),speed:point.speed_mps===null||point.speed_mps===undefined||point.speed_mps===''?null:Number(point.speed_mps),recordedAt:new Date(point.recorded_at||point.received_at||0).getTime()})).filter(point=>Number.isFinite(point.lat)&&Number.isFinite(point.lng)&&Number.isFinite(point.recordedAt)&&(!point.accuracy||point.accuracy<=150)).sort((a,b)=>a.recordedAt-b.recordedAt);
    const clean=[];
    raw.forEach(point=>{
      const previous=clean[clean.length-1];
      if(!previous){clean.push(point);return}
      const elapsed=Math.max(1,(point.recordedAt-previous.recordedAt)/1000),distance=familyTripDistance([previous,point]);
      if(point.recordedAt<=previous.recordedAt||distance/elapsed>55)return;
      if(distance<18&&elapsed<120){if(point.accuracy&&(!previous.accuracy||point.accuracy<previous.accuracy))clean[clean.length-1]=point;return}
      clean.push(point);
    });
    const sessions=[];
    clean.forEach(point=>{const session=sessions[sessions.length-1],previous=session?.[session.length-1];if(!session||point.recordedAt-previous.recordedAt>1200000)sessions.push([point]);else session.push(point)});
    return sessions.map(session=>{const simplified=[];session.forEach((point,index)=>{const previous=simplified[simplified.length-1];if(index===0||index===session.length-1||!previous||familyTripDistance([previous,point])>=25)simplified.push(point)});return simplified}).filter(segment=>segment.length>=3&&familyTripDistance(segment)>=200&&familyTripDistance([segment[0],segment[segment.length-1]])>=100&&segment[segment.length-1].recordedAt-segment[0].recordedAt>=120000);
  }
  function clearFamilyRoutes(){familyRoutes.forEach(route=>route.setMap(null));familyRoutes=[]}
  function renderFamilyHistory(points=[]){
    clearFamilyRoutes();
    const segments=familyHistorySegments(points);const usable=segments.filter(segment=>segment.length>=2);const samples=usable.reduce((total,segment)=>total+segment.length,0);const realSamples=usable.filter(segment=>segment.length>=3).reduce((total,segment)=>total+segment.length,0);
    usable.forEach(segment=>{
      const exact=segment.length>=3;
      familyRoutes.push(new google.maps.Polyline({map:familyMap,path:segment.map(point=>({lat:point.lat,lng:point.lng})),strokeColor:'#b58a2c',strokeOpacity:exact ? .92 : 0,strokeWeight:6,icons:exact?undefined:[{icon:{path:'M 0,-1 0,1',strokeOpacity:.9,strokeWeight:5,scale:4},offset:'0',repeat:'18px'}]}));
    });
    const status=$('familyMapStatus');if(!status)return;
    if(realSamples>=3)status.textContent=`Trayecto real · ${realSamples} puntos GPS guardados. Puedes mover y alejar el mapa libremente.`;
    else if(samples===2)status.textContent='Trayecto aproximado: solo recibí inicio y final. Mantén Roxy abierta durante el viaje para guardar el camino real.';
    else if(familyWatchId!==null)status.textContent='Grabando tu recorrido real… Puedes mover y alejar el mapa libremente.';
  }
  function familyTripDistance(segment=[]){
    const radians=value=>value*Math.PI/180;let meters=0;
    for(let index=1;index<segment.length;index+=1){const previous=segment[index-1],current=segment[index];const lat=radians(current.lat-previous.lat),lng=radians(current.lng-previous.lng);const a=Math.sin(lat/2)**2+Math.cos(radians(previous.lat))*Math.cos(radians(current.lat))*Math.sin(lng/2)**2;meters+=6371000*2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a))}
    return meters;
  }
  function showFamilyTripOnMap(segment=[]){
    if(!familyMap||segment.length<2)return;
    clearFamilyRoutes();const path=segment.map(point=>({lat:point.lat,lng:point.lng}));familyRoutes.push(new google.maps.Polyline({map:familyMap,path,strokeColor:'#b58a2c',strokeOpacity:.95,strokeWeight:7}));const bounds=new google.maps.LatLngBounds();path.forEach(point=>bounds.extend(point));familyMap.fitBounds(bounds,70);$('familyMapStatus').textContent=`Recorrido seleccionado · ${segment.length} puntos GPS. Puedes mover y alejar el mapa libremente.`;$('familyPanel').scrollTo({top:0,behavior:'smooth'});
  }
  function renderFamilyHistoryPanel(points=[]){
    const panel=$('familyHistoryPanel'),list=$('familyHistoryList'),summary=$('familyHistorySummary');if(!panel||!list||!summary)return;
    panel.hidden=!familyHistoryOpen;$('familyHistoryButton')?.setAttribute('aria-expanded',String(familyHistoryOpen));if(!familyHistoryOpen)return;
    const member=familySelectedMember();const segments=familyHistorySegments(points).reverse();list.replaceChildren();summary.textContent=member?`Trayectos reales y lugares visitados por ${member.display_name||'esta persona'}. Solo las personas autorizadas de tu Nexo pueden verlos.`:'Selecciona una persona para ver sus recorridos reales.';
    if(!segments.length){const empty=document.createElement('div');empty.className='family-history-empty';empty.textContent='Aún no hay un recorrido completo. Mantén “Ubicación en vivo” activa mientras te desplazas y Roxy guardará los puntos reales del camino.';list.append(empty);return}
    familyHistoryDays(segments).forEach(day=>{const section=document.createElement('section');section.className='family-history-day';section.innerHTML=`<h4>${escapeHtml(day.label)}</h4>`;day.segments.forEach(segment=>{section.append(familyHistoryTripCard(segment));const place=familyHistoryPlace(segment[segment.length-1]);if(place){const visit=document.createElement('article');visit.className='family-history-visit';visit.innerHTML=`<span class="material-symbols-rounded" aria-hidden="true">location_on</span><div><strong>${escapeHtml(place.name)}</strong><small>Llegada registrada a las ${escapeHtml(familyClock(segment[segment.length-1].recordedAt))}</small></div>`;section.append(visit)}});list.append(section)});
  }
  function familyHistoryPlace(point){
    if(!point)return null;let closest=null,distance=Infinity;
    (homeFamily.places||[]).forEach(place=>{const meters=familyTripDistance([point,{lat:Number(place.latitude),lng:Number(place.longitude)}]);if(Number.isFinite(meters)&&meters<distance&&meters<=Math.max(100,Number(place.radius_m||200))){closest=place;distance=meters}});return closest;
  }
  function familyHistoryDays(segments=[]){
    const groups=[];segments.forEach(segment=>{const date=new Date(segment[0].recordedAt),key=`${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;let group=groups.find(row=>row.key===key);if(!group){group={key,label:new Intl.DateTimeFormat('es',{weekday:'long',day:'numeric',month:'long'}).format(date),segments:[]};groups.push(group)}group.segments.push(segment)});return groups;
  }
  function familyHistoryTripCard(segment){
    const first=segment[0],last=segment[segment.length-1],started=new Date(first.recordedAt),ended=new Date(last.recordedAt),minutes=Math.max(1,Math.round((last.recordedAt-first.recordedAt)/60000)),miles=familyTripDistance(segment)/1609.344,origin=familyHistoryPlace(first)?.name||'Ubicación de salida',destination=familyHistoryPlace(last)?.name||'Ubicación de llegada',speeds=segment.map(point=>point.speed).filter(speed=>Number.isFinite(speed)&&speed>=0),peak=speeds.length?Math.round(Math.max(...speeds)*2.23694):null,row=document.createElement('article');
    row.className='family-history-trip-card';row.innerHTML=`<div class="family-history-route-icon"><span class="material-symbols-rounded" aria-hidden="true">directions_car</span></div><div class="family-history-trip-copy"><strong>${escapeHtml(origin===destination?`Recorrido desde ${origin}`:`${origin} → ${destination}`)}</strong><small>${escapeHtml(familyClock(started))}–${escapeHtml(familyClock(ended))} · ${minutes} min · ${miles.toFixed(1)} mi</small>${peak===null?'':`<em>Pico GPS ${peak} mph</em>`}</div>`;const button=document.createElement('button');button.type='button';button.textContent='Ver recorrido';button.addEventListener('click',()=>showFamilyTripOnMap(segment));row.append(button);return row;
  }
  async function loadFamilyHistoryPanel(open=true){
    familyHistoryOpen=open;const member=familySelectedMember();if(!member){familyHistoryPoints=[];renderFamilyHistoryPanel([]);return}
    if(open){$('familyHistoryPanel').hidden=false;$('familyHistoryList').innerHTML='<div class="family-history-empty">Cargando recorridos reales…</div>'}
    try{const history=await api(`/v1/home-family/members/${encodeURIComponent(member.id)}/history?limit=1000`);familyHistoryPoints=history.points||[]}catch(error){familyHistoryPoints=[];if(open)announce(error.message)}renderFamilyHistoryPanel(familyHistoryPoints);
  }
  const familyFriendlyDate=()=>new Intl.DateTimeFormat('es',{weekday:'long',day:'numeric',month:'long',year:'numeric'}).format(new Date());
  const familyClock=value=>{const date=new Date(value);return Number.isNaN(date.getTime())?'':new Intl.DateTimeFormat('es',{hour:'numeric',minute:'2-digit'}).format(date)};
  function familyBatteryLabel(member){
    const raw=member?.device?.battery_percent??member?.battery_percent;
    const value=Number(raw);
    return Number.isFinite(value)&&value>=0&&value<=100?`${Math.round(value)}%`:'Activo';
  }
  function familySelectedMember(){
    const rows=(homeFamily.members||[]).filter(row=>row.sharing_enabled);
    if(!rows.length)return null;
    let member=rows.find(row=>String(row.id)===String(familySelectedMemberId));
    if(!member)member=rows.find(row=>row.is_viewer)||rows[0];
    familySelectedMemberId=String(member.id||'');
    return member;
  }
  function familyNextCalendarEvent(){
    const now=Date.now();
    return (homeCalendar.events||[]).filter(event=>event.location&&new Date(event.starts_at||event.start||0).getTime()>now).sort((a,b)=>new Date(a.starts_at||a.start)-new Date(b.starts_at||b.start))[0]||null;
  }
  function renderFamilyExperience(){
    const rail=$('familyMemberRail'),focus=$('familyFocusCard'),route=$('familyRouteCard');
    if(!rail||!focus||!route)return;
    const accountName=homeFamily.account?.household_name||homeFamily.household_name||'Nuestro hogar';
    $('familyHouseholdName').textContent=accountName;
    $('familyTodayLabel').textContent=`${familyFriendlyDate()} · Privado y en vivo`;
    const weatherDay=(homeWeather.daily||[])[0],weatherCurrent=homeWeather.current||{};
    const weatherReady=homeWeather.status==='READY';
    $('familyWeatherSummary').textContent=weatherReady?`${weatherCurrent.emoji||weatherDay?.emoji||''} ${Math.round(Number(weatherCurrent.temperature??weatherDay?.temperature_max??0))}° · ${weatherCurrent.condition||weatherDay?.condition||'clima local'}`.trim():'Clima sin activar';
    renderFamilyWeatherFx();
    $('familyTrafficSummary').textContent=familyRouteSnapshot?.traffic||'Selecciona una ruta';
    rail.replaceChildren();
    const rows=(homeFamily.members||[]).filter(member=>member.sharing_enabled);
    const member=familySelectedMember();
    rows.forEach(member=>{
      const button=document.createElement('button');button.type='button';button.className=`family-rail-person${String(member.id)===familySelectedMemberId?' active':''}`;
      button.append(familyAvatarNode(member,'family-rail-avatar'));
      const name=document.createElement('strong');name.textContent=member.display_name||'Miembro';
      const device=document.createElement('small');device.innerHTML=`<span class="material-symbols-rounded" aria-hidden="true">${Number.isFinite(Number(member?.device?.battery_percent??member?.battery_percent))?'battery_5_bar':'smartphone'}</span>${escapeHtml(familyBatteryLabel(member))}`;
      button.append(name,device);button.addEventListener('click',()=>{familySelectedMemberId=String(member.id);familyRouteMode=false;familyHistoryPoints=[];renderFamilyExperience();void renderFamilyMap();if(familyHistoryOpen)void loadFamilyHistoryPanel(true)});rail.append(button);
    });
    if(!member){const needsPersonalLogin=account.mode!=='member'&&!account.requires_profile_setup;focus.innerHTML=needsPersonalLogin?'<div class="family-focus-empty"><strong>Tus personas están protegidas</strong><p>Elige tu perfil personal para recuperar tu Nexo, ubicaciones y recorridos. No necesitas configurar ninguna API.</p><button type="button" class="primary" data-nexo-sign-in>Entrar con mi perfil</button></div>':'<div class="family-focus-empty"><strong>Añade a tu primera persona</strong><p>Cuando acepte la invitación y active su ubicación aparecerá aquí.</p></div>';focus.querySelector('[data-nexo-sign-in]')?.addEventListener('click',()=>$('pairDialog').showModal());route.hidden=true;return}
    const speed=Number(member.location?.speed_mps||0);const place=(homeFamily.places||[]).find(row=>row.kind==='WORK'&&member.is_viewer)||(homeFamily.places||[]).find(row=>row.kind==='HOME');
    focus.replaceChildren();focus.append(familyAvatarNode(member,'family-focus-avatar'));
    const copy=document.createElement('div');copy.className='family-focus-copy';copy.innerHTML=`<h4>${escapeHtml(member.display_name||'Miembro')}</h4><p>${escapeHtml(member.status||place?.name||'Ubicación compartida')} · ${member.updated_at?`actualizado ${escapeHtml(familyTime(member.updated_at))}`:'esperando señal'}</p><span><span class="material-symbols-rounded" aria-hidden="true">${speed>.5?'directions_car':'schedule'}</span>${speed>.5?`${Math.round(speed*2.23694)} mph`:'Última posición recibida'}</span><span><span class="material-symbols-rounded" aria-hidden="true">smartphone</span>${Number.isFinite(Number(member?.device?.battery_percent??member?.battery_percent))?`Batería ${familyBatteryLabel(member)}`:'Batería disponible en la futura app móvil'}</span>`;
    const actions=document.createElement('div');actions.className='family-focus-actions';actions.innerHTML='<button type="button" class="primary" data-family-leave><span class="material-symbols-rounded" aria-hidden="true">notifications</span>Avisarme cuando salga</button><button type="button" class="secondary" data-family-route><span class="material-symbols-rounded" aria-hidden="true">route</span>Ver camino</button>';
    actions.querySelector('[data-family-leave]').addEventListener('click',()=>{if(!place){$('familySettings').open=true;$('familyPlaceName').focus();announce('Guarda primero Casa o Trabajo para crear este aviso.');return}announce('Roxy usará tus lugares guardados para avisarte dentro de la aplicación.')});
    actions.querySelector('[data-family-route]').addEventListener('click',()=>{if(!familyNextCalendarEvent()||!member?.location){announce('Necesito una ubicación compartida y un próximo evento con dirección para preparar el camino.');return}familyRouteMode=true;void renderFamilyRouteCard(member)});focus.append(copy,actions);
    void renderFamilyRouteCard(member);
  }
  function openFamilyRoute(member){
    const event=familyNextCalendarEvent();const origin=member?.location?`${member.location.latitude},${member.location.longitude}`:'';const destination=event?.location||'';
    if(!origin||!destination){announce('Necesito una ubicación compartida y un próximo evento con dirección para calcular el camino.');return}
    window.open(`https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}&travelmode=driving`,'_blank','noopener');
  }
  async function renderFamilyRouteCard(member){
    const root=$('familyRouteCard'),focus=$('familyFocusCard'),sheet=root?.closest('.family-presence-card');const event=familyNextCalendarEvent();
    if(!root||!event||!member?.location){if(root)root.hidden=true;if(focus)focus.hidden=false;sheet?.classList.remove('is-route-mode');return}
    if(!familyRouteMode){root.hidden=true;if(focus)focus.hidden=false;sheet?.classList.remove('is-route-mode');return}
    if(focus)focus.hidden=true;sheet?.classList.add('is-route-mode');
    const starts=new Date(event.starts_at||event.start);const margin=Math.max(0,Number(localStorage.getItem('roxy-family-route-margin')||10));
    let durationMinutes=null,trafficText='Ruta lista';
    if(window.google?.maps){
      try{const service=new google.maps.DirectionsService();const result=await service.route({origin:{lat:Number(member.location.latitude),lng:Number(member.location.longitude)},destination:event.location,travelMode:google.maps.TravelMode.DRIVING,drivingOptions:{departureTime:new Date(Math.max(Date.now()+60000,starts.getTime()-3600000)),trafficModel:google.maps.TrafficModel.BEST_GUESS}});const leg=result.routes?.[0]?.legs?.[0];durationMinutes=Math.ceil(Number((leg?.duration_in_traffic||leg?.duration)?.value||0)/60);const base=Math.ceil(Number(leg?.duration?.value||0)/60);const delay=Math.max(0,durationMinutes-base);trafficText=delay?`+${delay} min de tráfico`:'Sin retraso relevante';familyRouteSnapshot={result,traffic:delay?`${durationMinutes} min · tráfico +${delay}`:`${durationMinutes} min · tráfico normal`};$('familyTrafficSummary').textContent=familyRouteSnapshot.traffic;if(familyDirectionsRenderer)familyDirectionsRenderer.setMap(null);familyDirectionsRenderer=new google.maps.DirectionsRenderer({map:familyMap,directions:result,suppressMarkers:false,polylineOptions:{strokeColor:'#c09232',strokeWeight:6,strokeOpacity:.9}})}catch(_error){durationMinutes=null}
    }
    const eventDate=new Intl.DateTimeFormat('es',{weekday:'long',day:'numeric',month:'long',year:'numeric'}).format(starts);
    const depart=new Date(starts.getTime()-((durationMinutes||0)+margin)*60000);root.hidden=false;root.innerHTML=`<div class="family-route-person">${member.profile_photo?`<img src="${escapeHtml(member.profile_photo)}" alt="" />`:`<span>${escapeHtml(member.profile_emoji||familyInitials(member.display_name))}</span>`}<div><small>Para llegar tranquilo</small><h4>Sal a las ${durationMinutes?familyClock(depart):'hora sugerida'}</h4><p>${escapeHtml(eventDate)}</p></div></div><div class="family-route-timeline"><span><b>${durationMinutes?familyClock(new Date(depart.getTime()-5*60000)):'—'}</b><i class="material-symbols-rounded">notifications</i><small>Recordatorio</small></span><em></em><span><b>${durationMinutes?familyClock(depart):'—'}</b><i class="material-symbols-rounded">directions_car</i><small>Salir</small></span><em></em><span><b>${escapeHtml(familyClock(starts))}</b><i class="material-symbols-rounded">event</i><small>Cita</small></span></div><dl><div><dt>Evento</dt><dd>${escapeHtml(event.title||event.name||'Próximo evento')} · ${escapeHtml(familyClock(starts))}</dd></div><div><dt>Trayecto</dt><dd>${durationMinutes?`${durationMinutes} min`:'Abrir Google Maps para calcular'}</dd></div><div><dt>Tráfico</dt><dd>${escapeHtml(trafficText)}</dd></div><div><dt>Clima</dt><dd>${escapeHtml($('familyWeatherSummary').textContent)}</dd></div><div><dt>Margen</dt><dd>${margin} min</dd></div></dl><div class="family-route-actions"><button type="button" class="primary" data-route-reminder><span class="material-symbols-rounded">notifications</span>Recordarme</button><button type="button" class="secondary" data-route-open>Ver ruta</button><button type="button" class="secondary" data-route-margin>Cambiar margen</button></div>`;
    root.insertAdjacentHTML('afterbegin','<button type="button" class="family-route-back" data-route-back><span class="material-symbols-rounded" aria-hidden="true">arrow_back</span>Volver a Nexo</button>');root.querySelector('[data-route-back]').addEventListener('click',()=>{familyRouteMode=false;if(familyDirectionsRenderer){familyDirectionsRenderer.setMap(null);familyDirectionsRenderer=null}renderFamilyExperience();void renderFamilyMap()});root.querySelector('[data-route-open]').addEventListener('click',()=>openFamilyRoute(member));root.querySelector('[data-route-reminder]').addEventListener('click',()=>announce('El recordatorio se guarda con tu evento de calendario.'));root.querySelector('[data-route-margin]').addEventListener('click',()=>{const value=window.prompt('¿Cuántos minutos de margen quieres? ',String(margin));if(value===null)return;const next=Math.max(0,Math.min(120,Number(value)||0));localStorage.setItem('roxy-family-route-margin',String(next));void renderFamilyRouteCard(member)});
  }
  async function readFamilyProfilePhoto(file){
    if(!file)throw new Error('Selecciona una foto');
    if(file.type&&!file.type.startsWith('image/'))throw new Error('Selecciona una imagen de tu galería');
    if(file.size>12_000_000)throw new Error('La foto original es demasiado grande');
    const source=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result||''));reader.onerror=()=>reject(new Error('No pude leer la foto'));reader.readAsDataURL(file)});
    const image=await new Promise((resolve,reject)=>{const node=new Image();node.onload=()=>resolve(node);node.onerror=()=>reject(new Error('No pude procesar la foto'));node.src=source});
    const side=Math.min(image.naturalWidth,image.naturalHeight);const x=(image.naturalWidth-side)/2;const y=(image.naturalHeight-side)/2;const canvas=document.createElement('canvas');canvas.width=360;canvas.height=360;const context=canvas.getContext('2d');context.drawImage(image,x,y,side,side,0,0,360,360);let quality=.84;let encoded=canvas.toDataURL('image/jpeg',quality);while(encoded.length>350000&&quality>.52){quality-=.08;encoded=canvas.toDataURL('image/jpeg',quality)}return encoded;
  }
  function renderFamilyProfilePhoto(photo=''){
    familyProfilePhotoData=photo||'';const preview=$('familyProfilePhotoPreview');preview.src=familyProfilePhotoData;preview.hidden=!familyProfilePhotoData;$('familyProfileRemovePhoto').hidden=!familyProfilePhotoData;
  }
  function loadFamilyGoogleMaps(){
    const key=homeFamily.map?.browser_key;if(!key)return Promise.reject(new Error('Falta configurar Google Maps para Roxy Home'));
    if(window.google?.maps)return Promise.resolve(window.google.maps);
    if(familyMapLoader)return familyMapLoader;
    familyMapLoader=new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=`https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&v=weekly&loading=async`;script.async=true;script.onload=()=>resolve(window.google.maps);script.onerror=()=>reject(new Error('No se pudo cargar Google Maps'));document.head.append(script)});return familyMapLoader;
  }
  function createFamilyMapPerson(member,point){
    class PersonOverlay extends google.maps.OverlayView{
      onAdd(){
        const node=document.createElement('button');node.type='button';node.className=`family-map-person${String(member.id)===familySelectedMemberId?' active':''}`;node.setAttribute('aria-label',`Ver a ${member.display_name||'miembro'}`);
        const portrait=document.createElement('span');portrait.className='family-map-person-portrait';const avatar=familyAvatarNode(member,'family-map-person-avatar');const live=document.createElement('span');live.className='material-symbols-rounded family-map-person-live';live.setAttribute('aria-hidden','true');live.textContent='fiber_manual_record';portrait.append(avatar,live);
        const label=document.createElement('span');label.className='family-map-person-label';const name=document.createElement('strong');name.textContent=member.display_name||'Miembro';const status=document.createElement('small');status.textContent=member.status||'Ubicación compartida';label.append(name,status);node.append(portrait,label);
        node.addEventListener('click',()=>{familySelectedMemberId=String(member.id);familyRouteMode=false;renderFamilyExperience();void renderFamilyMap()});this.node=node;this.getPanes().overlayMouseTarget.append(node);
      }
      draw(){const pixel=this.getProjection().fromLatLngToDivPixel(new google.maps.LatLng(point.lat,point.lng));if(!pixel||!this.node)return;this.node.style.transform=`translate(${Math.round(pixel.x)}px,${Math.round(pixel.y)}px) translate(-50%,-50%)`}
      onRemove(){this.node?.remove();this.node=null}
    }
    const overlay=new PersonOverlay();overlay.setMap(familyMap);return overlay;
  }
  function selectFamilyMapPlace(placeId){
    familySelectedPlaceId=String(placeId||'');document.querySelectorAll('.family-map-place').forEach(node=>{const active=node.dataset.placeId===familySelectedPlaceId;node.classList.toggle('active',active);node.setAttribute('aria-expanded',String(active))});
  }
  function createFamilyMapPlace(place,point){
    class PlaceOverlay extends google.maps.OverlayView{
      onAdd(){
        const kind=familyPlaceIcons[place.kind]?place.kind:'OTHER';const node=document.createElement('button');node.type='button';node.className=`family-map-place family-map-place-${kind.toLowerCase()}${String(place.id)===familySelectedPlaceId?' active':''}`;node.dataset.placeId=String(place.id||'');node.setAttribute('aria-label',`Ver ${familyPlaceLabels[kind]||'lugar'} ${place.name||''}`.trim());node.setAttribute('aria-expanded',String(String(place.id)===familySelectedPlaceId));
        const badge=document.createElement('span');badge.className='family-map-place-badge';const icon=document.createElement('span');icon.className='material-symbols-rounded family-map-place-icon';icon.setAttribute('aria-hidden','true');icon.textContent=familyPlaceIcons[kind];badge.append(icon);
        const pointIcon=document.createElement('span');pointIcon.className='material-symbols-rounded family-map-place-point';pointIcon.setAttribute('aria-hidden','true');pointIcon.textContent='arrow_drop_down';
        const label=document.createElement('span');label.className='family-map-place-label';label.textContent=place.name||familyPlaceLabels[kind]||'Lugar';node.append(badge,pointIcon,label);node.addEventListener('click',()=>selectFamilyMapPlace(place.id));this.node=node;this.getPanes().overlayMouseTarget.append(node);
      }
      draw(){const pixel=this.getProjection().fromLatLngToDivPixel(new google.maps.LatLng(point.lat,point.lng));if(!pixel||!this.node)return;this.node.style.transform=`translate(${Math.round(pixel.x)}px,${Math.round(pixel.y)}px) translate(-50%,-100%)`}
      onRemove(){this.node?.remove();this.node=null}
    }
    const overlay=new PlaceOverlay();overlay.setMap(familyMap);return overlay;
  }
  async function renderFamilyMap(){
    const root=$('familyMap');if(!root)return;const located=(homeFamily.members||[]).filter(row=>row.sharing_enabled&&row.location);
    if(account.mode!=='member'&&!account.requires_profile_setup){root.innerHTML='<div class="family-map-empty"><span class="material-symbols-rounded" aria-hidden="true">shield_lock</span><strong>Nexo está protegido</strong><p>Elige tu perfil personal para ver a las personas, el mapa y los recorridos de tu hogar. No necesitas configurar una API.</p><button type="button" class="primary" data-nexo-sign-in>Entrar con mi perfil</button></div>';root.querySelector('[data-nexo-sign-in]').addEventListener('click',()=>$('pairDialog').showModal());return}
    if(homeFamily.map?.provider!=='GOOGLE_MAPS'){root.innerHTML='<div class="family-map-empty"><span class="material-symbols-rounded" aria-hidden="true">map</span><strong>Mapa listo para conectar</strong><p>Configura la clave de navegador exclusiva de Roxy Home para mostrar el mapa real.</p></div>';return}
    const nexoMapStyles=[{elementType:'geometry',stylers:[{color:'#edf0e7'}]},{elementType:'labels.icon',stylers:[{visibility:'off'}]},{elementType:'labels.text.fill',stylers:[{color:'#596b5f'}]},{elementType:'labels.text.stroke',stylers:[{color:'#fbfaf5'},{weight:3}]},{featureType:'administrative.locality',elementType:'labels.text.fill',stylers:[{color:'#40594a'}]},{featureType:'poi',stylers:[{visibility:'off'}]},{featureType:'transit',stylers:[{visibility:'off'}]},{featureType:'road',elementType:'geometry',stylers:[{color:'#fffdf8'}]},{featureType:'road',elementType:'geometry.stroke',stylers:[{color:'#d9dfd5'}]},{featureType:'road',elementType:'labels.icon',stylers:[{visibility:'off'}]},{featureType:'road.highway',elementType:'geometry',stylers:[{color:'#e7ddc4'}]},{featureType:'road.highway',elementType:'geometry.stroke',stylers:[{color:'#c9b57d'}]},{featureType:'landscape.natural',elementType:'geometry',stylers:[{color:'#e5ecdf'}]},{featureType:'landscape.man_made',elementType:'geometry',stylers:[{color:'#f2f0e8'}]},{featureType:'water',elementType:'geometry',stylers:[{color:'#d8e8e5'}]},{featureType:'water',elementType:'labels.text.fill',stylers:[{color:'#688682'}]}];
    try{await loadFamilyGoogleMaps();const mapOptions={styles:familyWeatherMapStyles(nexoMapStyles),disableDefaultUI:true,keyboardShortcuts:false,streetViewControl:false,fullscreenControl:false,mapTypeControl:false,zoomControl:true,zoomControlOptions:{position:google.maps.ControlPosition.RIGHT_BOTTOM},scaleControl:true,gestureHandling:'greedy',clickableIcons:false,backgroundColor:'#e7ece3'};if(!familyMap){root.replaceChildren();familyMap=new google.maps.Map(root,{center:located.length?{lat:Number(located[0].location.latitude),lng:Number(located[0].location.longitude)}:{lat:28.5383,lng:-81.3792},zoom:located.length?14:9,mapTypeId:'roadmap',...mapOptions});familyMapZoomListener=familyMap.addListener('zoom_changed',()=>{if(!familyMapTransitioning&&!familyWeatherGlobeActive&&Number(familyMap.getZoom())<=5)void activateFamilyWeatherGlobe()})}else familyMap.setOptions(mapOptions);
      familyMapMarkers.forEach(marker=>marker.setMap(null));familyMapMarkers=[];const bounds=new google.maps.LatLngBounds();const places=(homeFamily.places||[]).filter(place=>Number.isFinite(Number(place.latitude))&&Number.isFinite(Number(place.longitude)));if(!places.some(place=>String(place.id)===familySelectedPlaceId))familySelectedPlaceId=String(places.find(place=>place.kind==='HOME')?.id||'');places.forEach(place=>{const point={lat:Number(place.latitude),lng:Number(place.longitude)};familyMapMarkers.push(createFamilyMapPlace(place,point))});located.forEach(member=>{const point={lat:Number(member.location.latitude),lng:Number(member.location.longitude)};familyMapMarkers.push(createFamilyMapPerson(member,point));bounds.extend(point)});if(!familyMapViewportInitialized){if(located.length===1){familyMap.setCenter(bounds.getCenter());familyMap.setZoom(15)}else if(located.length>1)familyMap.fitBounds(bounds,76);else if(places.length){familyMap.setCenter({lat:Number(places[0].latitude),lng:Number(places[0].longitude)});familyMap.setZoom(14)}familyMapViewportInitialized=true}
      const selected=familySelectedMember();clearFamilyRoutes();if(familyHistoryOpen&&selected?.location){const history=await api(`/v1/home-family/members/${encodeURIComponent(selected.id)}/history?limit=1000`).catch(()=>({points:[]}));familyHistoryPoints=history.points||[];renderFamilyHistoryPanel(familyHistoryPoints)}void renderFamilyRouteCard(selected);
    }catch(error){root.innerHTML=`<div class="family-map-empty"><span class="material-symbols-rounded" aria-hidden="true">wifi_off</span><strong>No pude abrir el mapa</strong><p>${escapeHtml(error.message)}</p></div>`}
  }
  async function refreshFamily(){homeFamily=await api('/v1/home-family');await dbSet(`home-family:${user}`,homeFamily);renderFamily()}
  function renderFamily(){
    const members=$('familyMembers');const places=$('familyPlaces');const alerts=$('familyAlerts');const connections=$('familyConnections');if(!members||!places||!alerts||!connections)return;
    members.replaceChildren();places.replaceChildren();alerts.replaceChildren();connections.replaceChildren();$('familyPrivacyNotice').textContent=homeFamily.privacy_notice||'La ubicación solo se comparte con tu permiso.';
    $('familyInviteForm').hidden=!homeFamily.can_manage_connections;
    const rows=homeFamily.members||[];const viewer=rows.find(row=>row.is_viewer);const enabled=Boolean(viewer?.sharing_enabled);$('familyStopLocation').hidden=!enabled;$('familyLiveState').textContent=familyWatchId!==null?'En vivo':enabled?'Activada · esperando señal':'Desactivada';$('familyLiveState').classList.toggle('is-live',familyWatchId!==null);$('familyShareLocation').innerHTML=familyWatchId!==null?'<span class="material-symbols-rounded" aria-hidden="true">near_me</span> Ubicación en vivo activa':enabled?'<span class="material-symbols-rounded" aria-hidden="true">sync</span> Reanudar actualización':'<span class="material-symbols-rounded" aria-hidden="true">near_me</span> Activar ubicación permanente';
    const profileForm=$('familyProfileForm');profileForm.hidden=!viewer;if(viewer){$('familyProfileName').value=viewer.display_name||'';$('familyProfileInitials').textContent=viewer.profile_emoji||familyInitials(viewer.display_name);renderFamilyProfilePhoto(viewer.profile_photo||'');familyProfileEmoji=viewer.profile_emoji||'';profileForm.querySelectorAll('[name="familyProfileEmoji"]').forEach(input=>{input.checked=input.value===familyProfileEmoji});const color=viewer.marker_color||'FOREST';profileForm.querySelectorAll('[name="familyMarkerColor"]').forEach(input=>{input.checked=input.value===color});profileForm.querySelector('.family-profile-preview').style.background=familyMarkerColors[color]||familyMarkerColors.FOREST}void renderFamilyMap();
    if(!rows.length){const empty=document.createElement('p');empty.className='family-empty';empty.textContent=account.mode==='member'?'Añade personas desde Administrar perfiles.':!account.requires_profile_setup?'Elige tu perfil personal para volver a ver las personas guardadas.':'Crea primero los perfiles personales para usar Nuestro Nexo.';members.append(empty)}
    rows.forEach(member=>{const row=document.createElement('article');row.className=`family-member${member.sharing_enabled?'':' is-private'}${member.external?' is-external':''}`;const avatar=familyAvatarNode(member);const copy=document.createElement('span');const title=document.createElement('strong');title.textContent=`${member.display_name||'Miembro'}${member.is_viewer?' · Tú':''}`;const status=document.createElement('small');status.textContent=member.sharing_enabled?(member.status||'Ubicación compartida'):'Ubicación privada';const speed=Number(member.location?.speed_mps||0);const updated=document.createElement('em');updated.textContent=member.updated_at?`${speed>.5?`${Math.round(speed*2.23694)} mph · `:''}Actualizado ${familyTime(member.updated_at)}`:'Sin ubicación compartida';copy.append(title,status,updated);if(member.external){const badge=document.createElement('b');badge.className='family-trust-badge';badge.textContent=member.relationship||'Conexión de confianza';copy.append(badge)}row.append(avatar,copy);if(member.is_viewer&&!member.sharing_enabled){const share=document.createElement('button');share.type='button';share.className='family-member-share';share.innerHTML='<span class="material-symbols-rounded" aria-hidden="true">near_me</span><span>Compartir mi ubicación</span>';share.setAttribute('aria-label','Activar mi ubicación en Nexo');share.addEventListener('click',()=>void shareFamilyLocation());row.append(share)}members.append(row)});
    const trusted=homeFamily.connections||[];if(!trusted.length){const empty=document.createElement('p');empty.className='family-empty';empty.textContent=homeFamily.can_manage_connections?'Todavía no has conectado a nadie fuera de esta casa.':'No hay conexiones externas en este Nexo.';connections.append(empty)}
    trusted.forEach(member=>{const row=document.createElement('article');row.className='family-connection';const avatar=familyAvatarNode(member);const copy=document.createElement('span');copy.innerHTML=`<strong>${escapeHtml(member.display_name||'Conexión')}</strong><small>${escapeHtml(member.relationship||'Persona de confianza')} · acceso solo a Nexo</small>`;row.append(avatar,copy);if(homeFamily.can_manage_connections){const remove=document.createElement('button');remove.type='button';remove.setAttribute('aria-label',`Retirar a ${member.display_name}`);remove.innerHTML='<span class="material-symbols-rounded" aria-hidden="true">person_remove</span>';remove.addEventListener('click',()=>revokeFamilyConnection(member));row.append(remove)}connections.append(row)});
    const saved=homeFamily.places||[];if(!saved.length){const empty=document.createElement('p');empty.className='family-empty';empty.textContent='Guarda Casa o Trabajo para recibir recordatorios con contexto.';places.append(empty)}
    saved.forEach(place=>{const row=document.createElement('article');row.className='family-place';const icon=document.createElement('span');icon.className='material-symbols-rounded';icon.textContent=familyPlaceIcons[place.kind]||'location_on';const copy=document.createElement('span');copy.innerHTML=`<strong>${escapeHtml(place.name)}</strong><small>${escapeHtml(familyPlaceLabels[place.kind]||'Lugar')} · radio ${Number(place.radius_m||200)} m</small>`;const remove=document.createElement('button');remove.type='button';remove.className='family-place-remove';remove.innerHTML='<span class="material-symbols-rounded" aria-hidden="true">delete</span>';remove.setAttribute('aria-label',`Eliminar ${place.name}`);remove.addEventListener('click',()=>deleteFamilyPlace(place));row.append(icon,copy,remove);places.append(row)});
    const notices=[...(homeFamily.alerts||[])].reverse();if(!notices.length){const empty=document.createElement('p');empty.className='family-empty';empty.textContent='Cuando haya un recordatorio contextual aparecerá aquí.';alerts.append(empty)}
    notices.forEach(alert=>{const row=document.createElement('article');row.className='family-alert';row.innerHTML=`<span class="material-symbols-rounded" aria-hidden="true">${alert.kind==='SHOPPING_AFTER_WORK'?'shopping_cart':'notifications'}</span><div><strong>${escapeHtml(alert.title||'Recordatorio')}</strong><p>${escapeHtml(alert.message||'')}</p><small>${escapeHtml(familyTime(alert.created_at))}</small></div>`;alerts.append(row)});
    renderFamilyExperience();
  }
  async function sendFamilyPosition(position){const result=await api('/v1/home-family/location',{method:'PUT',body:JSON.stringify(browserLocationPayload(position))});homeFamily=await api('/v1/home-family');renderFamily();if(result.alert){announce(result.alert.message);if('Notification'in window&&Notification.permission==='granted')new Notification('Roxy Home',{body:result.alert.message})}}
  async function startFamilyLocationWatcher({automatic=false}={}){
    const button=$('familyShareLocation');if(familyWatchId!==null)return true;
    if(!navigator.geolocation){if(!automatic)announce('Este navegador no permite compartir ubicación');return false}
    button.disabled=true;button.innerHTML=`<span class="material-symbols-rounded" aria-hidden="true">progress_activity</span> ${automatic?'Reanudando…':'Solicitando permiso…'}`;
    try{
      await new Promise((resolve,reject)=>{let settled=false;familyWatchId=navigator.geolocation.watchPosition(async position=>{try{await sendFamilyPosition(position);if(!settled){settled=true;resolve()}}catch(error){if(!settled){settled=true;reject(error)}}},error=>{if(!settled){settled=true;reject(new Error(({1:'El permiso de ubicación está bloqueado. Actívalo en los ajustes de Safari para reanudar.',2:'No pude determinar tu ubicación ahora.',3:'La ubicación tardó demasiado.'})[error.code]||'No pude obtener tu ubicación'))}},{enableHighAccuracy:true,maximumAge:0,timeout:20000})});
      if(!automatic)announce('Ubicación activada. Roxy la reanudará automáticamente cada vez que abras la aplicación.');
      return true;
    }catch(error){if(familyWatchId!==null)navigator.geolocation.clearWatch(familyWatchId);familyWatchId=null;$('familyMapStatus').textContent='La preferencia sigue activa, pero el navegador necesita permiso para volver a actualizar.';if(!automatic)announce(error.message);return false}
    finally{button.disabled=false;renderFamily()}
  }
  async function shareFamilyLocation(){return startFamilyLocationWatcher({automatic:false})}
  async function resumeFamilyLocationIfEnabled(){const viewer=(homeFamily.members||[]).find(row=>row.is_viewer);if(!viewer?.sharing_enabled||familyWatchId!==null)return false;return startFamilyLocationWatcher({automatic:true})}
  async function stopFamilyLocation(){if(!window.confirm('¿Desactivar la ubicación? Roxy dejará de reanudarla al abrir la aplicación y borrará el recorrido compartido.'))return;try{if(familyWatchId!==null)navigator.geolocation.clearWatch(familyWatchId);familyWatchId=null;await api('/v1/home-family/location',{method:'DELETE'});$('familyMapStatus').textContent='La ubicación permanente está desactivada y el recorrido compartido fue borrado.';await refreshFamily();announce('Ubicación desactivada hasta que decidas volver a activarla')}catch(error){announce(error.message)}}
  async function createFamilyInvitation(event){event.preventDefault();const form=event.currentTarget;const button=form.querySelector('button[type="submit"]');button.disabled=true;try{const data=await api('/v1/home-family/invitations',{method:'POST',body:JSON.stringify({display_name:$('familyInviteName').value.trim(),relationship:$('familyInviteRelationship').value.trim()||'Persona de confianza'})});const url=new URL('/lista',location.origin);url.searchParams.set('nexo_invite',data.invitation.token);url.hash='family';const result=$('familyInviteResult');result.hidden=false;result.replaceChildren();const copy=document.createElement('p');copy.innerHTML=`<strong>Invitación lista para ${escapeHtml(data.invitation.display_name||'tu conexión')}</strong><small>Caduca en 7 días y solo permite entrar a Nuestro Nexo.</small>`;const share=makeButton('Compartir invitación','primary',async()=>{try{if(navigator.share)await navigator.share({title:'Invitación a Nuestro Nexo',text:'Te invito a compartir ubicación conmigo de forma privada en Roxy Home.',url:url.toString()});else{await navigator.clipboard.writeText(url.toString());announce('Enlace copiado')}}catch(error){if(error.name!=='AbortError')announce('No pude compartir el enlace')}});result.append(copy,share);form.reset();await refreshFamily()}catch(error){announce(error.message)}finally{button.disabled=false}}
  async function redeemNexoInvitationFromUrl(){const url=new URL(location.href);const token=url.searchParams.get('nexo_invite');if(!token||sessionStorage.getItem(`nexo-invite:${token}`))return;try{await api('/v1/home-family/invitations/redeem',{method:'POST',body:JSON.stringify({token})});sessionStorage.setItem(`nexo-invite:${token}`,'1');url.searchParams.delete('nexo_invite');history.replaceState(null,'',`${url.pathname}${url.search}#family`);await refreshFamily();selectPanel('family');announce('Ya formas parte de este Nexo. Solo compartes esta sección.')}catch(error){announce(error.message)}}
  async function revokeFamilyConnection(member){if(!window.confirm(`¿Retirar a ${member.display_name} de Nuestro Nexo? También se borrará su recorrido compartido aquí.`))return;try{await api(`/v1/home-family/connections/${encodeURIComponent(member.id)}`,{method:'DELETE'});await refreshFamily();announce('Conexión retirada de Nuestro Nexo')}catch(error){announce(error.message)}}
  function inferFamilyPlaceKind(){const name=$('familyPlaceName').value.toLocaleLowerCase('es');if(/trabajo|oficina|empleo|work/.test(name))$('familyPlaceKind').value='WORK';else if(/walmart|publix|tienda|supermercado|market/.test(name))$('familyPlaceKind').value='STORE';else if(/casa|hogar|home/.test(name))$('familyPlaceKind').value='HOME'}
  async function saveFamilyPlace(event){event.preventDefault();const form=event.currentTarget;const button=form.querySelector('button[type="submit"]');button.disabled=true;try{inferFamilyPlaceKind();const position=await currentBrowserPosition();await api('/v1/home-family/places',{method:'POST',body:JSON.stringify({name:$('familyPlaceName').value.trim(),kind:$('familyPlaceKind').value,...position,radius_m:200})});form.reset();await refreshFamily();announce('Lugar guardado y clasificado correctamente')}catch(error){announce(error.message)}finally{button.disabled=false}}
  async function persistFamilyProfile(message='Tu nombre, imagen y marcador de Nexo quedaron guardados'){const form=$('familyProfileForm');const marker=form.querySelector('[name="familyMarkerColor"]:checked')?.value||'FOREST';const emoji=form.querySelector('[name="familyProfileEmoji"]:checked')?.value||'';await api('/v1/home-family/profile',{method:'PUT',body:JSON.stringify({display_name:$('familyProfileName').value.trim(),marker_color:marker,photo_data_url:familyProfilePhotoData,profile_emoji:emoji})});await refreshFamily();announce(message)}
  async function saveFamilyProfile(event){event.preventDefault();const form=event.currentTarget;const button=form.querySelector('button[type="submit"]');button.disabled=true;try{await persistFamilyProfile()}catch(error){announce(error.message)}finally{button.disabled=false}}
  async function deleteFamilyPlace(place){if(!window.confirm(`¿Eliminar ${place.name} de los lugares del hogar?`))return;try{await api(`/v1/home-family/places/${encodeURIComponent(place.id)}`,{method:'DELETE'});await refreshFamily();announce('Lugar eliminado')}catch(error){announce(error.message)}}

  async function refreshDesignProjects(){
    homeDesign=await api(`/v1/home-design/${encodeURIComponent(user)}`);await dbSet(`home-design:${user}`,homeDesign);renderDesign();
    const pending=(homeDesign.projects||[]).some(project=>project.proposal_status==='GENERATING');
    if(pending&&!designPoll)designPoll=setTimeout(()=>{designPoll=null;refreshDesignProjects().catch(()=>{})},5000);
  }
  function renderDesignConnections(){
    const root=$('designConnectionGrid');if(!root)return;root.replaceChildren();
    const icons={walmart_affiliate:'storefront',ebay_browse:'sell',best_buy_products:'tv',impact:'hub',cj_affiliate:'join_inner',awin:'account_tree',amazon_creators:'package_2',pinterest_trends:'trending_up',dataforseo_merchant:'compare_arrows'};
    (homeDesign.connections||[]).forEach(connection=>{const article=document.createElement('article');article.className=`design-connection ${connection.connection_status==='ready'?'ready':'pending'}`;const icon=document.createElement('span');icon.className='material-symbols-rounded';icon.textContent=icons[connection.id]||'link';const copy=document.createElement('div');const heading=document.createElement('div');const name=document.createElement('strong');name.textContent=connection.name;const status=document.createElement('em');status.textContent=connection.status_label;heading.append(name,status);const capabilities=document.createElement('p');capabilities.textContent=connection.capabilities;const use=document.createElement('small');use.textContent=`En Renueva: ${connection.use}`;const next=document.createElement('span');next.textContent=connection.next_step;copy.append(heading,capabilities,use,next);article.append(icon,copy);root.append(article)});
  }
  function renderDesign(){
    const root=$('designProjects');if(!root)return;root.replaceChildren();
    const projects=homeDesign.projects||[];
    $('designOnboarding').hidden=Boolean(projects.length);$('designGenerationNotice').hidden=!projects.length;
    $('designGenerationNotice').textContent=homeDesign.generation_configured?'Roxy puede analizar la foto privada y crear la propuesta elegida. Los importes son objetivos hasta que una tienda confirme precio y disponibilidad.':'Tu proyecto y presupuesto se guardarán; el análisis visual necesita la conexión privada de OpenAI de Home.';
    const stage=projects.some(project=>project.proposal_url)?4:projects.some(project=>project.analysis_status==='READY_AI')?3:projects.length?2:1;$('designProgress').querySelectorAll('li').forEach((item,index)=>{item.classList.toggle('active',index+1===stage);item.classList.toggle('complete',index+1<stage)});renderDesignConnections();
    if(!projects.length)return;
    projects.forEach(project=>{
      const card=document.createElement('article');card.className='design-project';
      const visuals=document.createElement('div');visuals.className='design-visuals';let comparisonControl=null;
      const before=document.createElement('div');before.className='design-visual';const beforeImage=document.createElement('img');beforeImage.src=project.photo_url;beforeImage.alt=`Foto actual de ${project.name}`;const beforeLabel=document.createElement('span');beforeLabel.textContent='Actual';before.append(beforeImage,beforeLabel);(project.analysis?.furniture_recommendations||[]).slice(0,3).forEach((row,index)=>{const marker=document.createElement('button');marker.type='button';marker.className='design-room-marker';marker.textContent=String(index+1);marker.title=row.name;marker.style.setProperty('--marker-x',`${[52,24,82][index]}%`);marker.style.setProperty('--marker-y',`${[50,34,39][index]}%`);marker.addEventListener('click',()=>announce(`${row.name}: ${row.placement||row.role}`));before.append(marker)});
      const after=document.createElement('div');after.className='design-visual';
      if(project.proposal_status==='GENERATING'){const placeholder=document.createElement('div');placeholder.className='design-proposal-placeholder';placeholder.textContent='Roxy está transformando tu espacio…';after.append(placeholder)}
      else if(project.proposal_url){const afterImage=document.createElement('img');afterImage.src=`${project.proposal_url}?v=${encodeURIComponent(project.updated_at||'')}`;afterImage.alt=`Propuesta de Roxy para ${project.name}`;const afterLabel=document.createElement('span');const tierLabel=(project.budget_tiers||[]).find(row=>row.id===(project.proposal_tier||project.selected_tier))?.label||'Roxy';afterLabel.textContent=`Propuesta ${tierLabel}`;after.append(afterImage,afterLabel)}
      else{const placeholder=document.createElement('div');placeholder.className='design-proposal-placeholder';const status=project.proposal_status==='GENERATING'?'Roxy está transformando tu espacio…':project.proposal_status==='FAILED'?'La propuesta no terminó. Puedes intentarlo otra vez.':'Aquí aparecerá tu propuesta visual';placeholder.textContent=status;after.append(placeholder)}
      visuals.append(before,after);
      if(project.proposal_url&&project.proposal_status!=='GENERATING'){
        visuals.classList.add('is-comparison');after.style.clipPath='inset(0 50% 0 0)';
        const compare=document.createElement('div');compare.className='design-comparison-control';const setComparison=value=>{after.style.clipPath=`inset(0 ${100-value}% 0 0)`;slider.value=String(value);[beforeButton,splitButton,afterButton].forEach(button=>button.classList.toggle('active',Number(button.dataset.value)===value))};const beforeButton=makeButton('Antes','secondary',()=>setComparison(0));beforeButton.dataset.value='0';const splitButton=makeButton('Comparar','secondary',()=>setComparison(50));splitButton.dataset.value='50';splitButton.classList.add('active');const afterButton=makeButton('Después','secondary',()=>setComparison(100));afterButton.dataset.value='100';const slider=document.createElement('input');slider.type='range';slider.min='0';slider.max='100';slider.value='50';slider.setAttribute('aria-label','Desliza para comparar la habitación actual y el rediseño');slider.addEventListener('input',()=>{const value=Number(slider.value);after.style.clipPath=`inset(0 ${100-value}% 0 0)`;[beforeButton,splitButton,afterButton].forEach(button=>button.classList.remove('active'))});compare.append(beforeButton,splitButton,afterButton,slider);comparisonControl=compare;
      }
      const body=document.createElement('div');body.className='design-project-body';const heading=document.createElement('div');heading.className='design-project-heading';const copy=document.createElement('div');const title=document.createElement('h3');title.textContent=project.name;const meta=document.createElement('p');meta.textContent=`${project.room_label} · ${project.style_label}${project.measurements?` · ${project.measurements}`:''}`;copy.append(title,meta);const edit=document.createElement('button');edit.type='button';edit.className='design-project-menu';edit.innerHTML='<span class="material-symbols-rounded" aria-hidden="true">more_vert</span>';edit.setAttribute('aria-label',`Opciones de ${project.name}`);edit.addEventListener('click',()=>{const fitSection=card.querySelector('.design-fit');if(fitSection){fitSection.open=true;fitSection.scrollIntoView({behavior:'smooth',block:'center'})}});heading.append(copy,edit);
      const tierTabs=document.createElement('div');tierTabs.className='design-tier-tabs';tierTabs.setAttribute('aria-label','Nivel de presupuesto');(project.budget_tiers||[]).forEach(tier=>{const button=document.createElement('button');button.type='button';button.classList.toggle('active',tier.id===(project.selected_tier||'balanced'));button.innerHTML=`<strong>${tier.label}</strong><small>$${Number(tier.budget||0).toLocaleString('en-US')}</small>`;button.addEventListener('click',()=>{project.selected_tier=tier.id;project.products=tier.products||[];renderDesign()});tierTabs.append(button)});
      const activeBudget=(project.budget_tiers||[]).find(row=>row.id===(project.selected_tier||'balanced'))?.budget||project.budget||0;const budgetPlan=document.createElement('section');budgetPlan.className='design-budget-plan';budgetPlan.innerHTML=`<div><span><strong>Plan dentro de tu presupuesto</strong><small>Objetivo $${Number(activeBudget).toLocaleString('en-US')} · precios pendientes de tienda</small></span><b>${project.selected_tier==='economy'?'Esencial':project.selected_tier==='complete'?'Completo':'Equilibrado'}</b></div><progress max="100" value="100">100%</progress>`;budgetPlan.append(tierTabs);
      const decisions=document.createElement('div');decisions.className='design-decision-tabs';decisions.setAttribute('aria-label','Decisión sobre los elementos actuales');[['check_circle','Conservar'],['swap_horiz','Cambiar'],['add','Añadir']].forEach(([icon,label],index)=>{const button=document.createElement('button');button.type='button';button.classList.toggle('active',index===0);button.innerHTML=`<span class="material-symbols-rounded" aria-hidden="true">${icon}</span>${label}`;button.addEventListener('click',()=>{decisions.querySelectorAll('button').forEach(item=>item.classList.toggle('active',item===button));announce(`${label}: revisa los elementos identificados por Roxy.`)});decisions.append(button)});
      const analysis=document.createElement('section');analysis.className='design-analysis';const analysisHeading=document.createElement('div');const analysisTitle=document.createElement('strong');analysisTitle.textContent='Lectura de Roxy';const analyze=makeButton((project.analysis_status==='READY_AI'?'Reanalizar y rediseñar':'Analizar y rediseñar'),'secondary',()=>analyzeDesignProject(project.id));analyze.disabled=!homeDesign.generation_configured;analysisHeading.append(analysisTitle,analyze);const analysisCopy=document.createElement('p');analysisCopy.textContent=project.analysis?.summary||'Roxy organizará oportunidades, puntos fuertes y medidas que falten.';analysis.append(analysisHeading,analysisCopy);const insights=document.createElement('ul');[...(project.analysis?.strengths||[]),...(project.analysis?.opportunities||[]),...(project.analysis?.questions||[])].slice(0,6).forEach(value=>{const item=document.createElement('li');item.textContent=value;insights.append(item)});if(insights.children.length)analysis.append(insights);
      const recommendations=document.createElement('section');recommendations.className='design-furniture-recommendations';const recommendationRows=project.analysis?.furniture_recommendations||[];if(recommendationRows.length){const recommendationHeading=document.createElement('header');recommendationHeading.innerHTML='<span><strong>Muebles recomendados</strong><small>Qué pieza, cómo debe verse y dónde colocarla</small></span>';recommendations.append(recommendationHeading);recommendationRows.forEach(row=>{const article=document.createElement('article');const visual=makeDesignProductVisual(row.name);const text=document.createElement('span');const name=document.createElement('strong');name.textContent=row.name;const detail=document.createElement('small');detail.textContent=[row.style_details,row.placement].filter(Boolean).join(' · ');text.append(name,detail);const badge=document.createElement('em');badge.textContent=row.priority==='essential'?'Principal':'Opcional';article.append(visual,text,badge);recommendations.append(article)})}
      const fit=document.createElement('details');fit.className='design-fit';const fitSummary=document.createElement('summary');const fitIcon=document.createElement('span');fitIcon.className='material-symbols-rounded';fitIcon.textContent=project.fit_assessment?.status==='READY_TO_COMPARE'?'straighten':'warning';const fitCopy=document.createElement('span');const fitTitle=document.createElement('strong');fitTitle.textContent=project.fit_assessment?.label||'Validar medidas';const fitMessage=document.createElement('small');fitMessage.textContent=project.fit_assessment?.message||'Añade medidas para comprobar compatibilidad.';fitCopy.append(fitTitle,fitMessage);fitSummary.append(fitIcon,fitCopy);const fitForm=document.createElement('form');fitForm.className='design-fit-form';const fitFields=[['wall_width','Pared disponible'],['passage_width','Paso o puerta'],['max_depth','Profundidad máxima']];fitFields.forEach(([key,labelText])=>{const label=document.createElement('label');const span=document.createElement('span');span.textContent=`${labelText} (pulgadas)`;const input=document.createElement('input');input.type='number';input.name=key;input.min='0';input.max='2000';input.step='.25';input.inputMode='decimal';input.value=Number(project.fit_constraints?.[key]||0)||'';input.placeholder='Ej. 36';label.append(span,input);fitForm.append(label)});const fitSave=document.createElement('button');fitSave.type='submit';fitSave.className='secondary';fitSave.textContent='Guardar medidas';fitForm.append(fitSave);fitForm.addEventListener('submit',event=>saveDesignMeasurements(event,project.id));fit.append(fitSummary,fitForm);
      const activeTier=(project.budget_tiers||[]).find(row=>row.id===(project.selected_tier||'balanced'));const tierProducts=((activeTier&&activeTier.products)||project.products||[]);const products=document.createElement('section');products.className='design-product-list';const selectionHeading=document.createElement('header');const selectionCopy=document.createElement('span');const selectionTitle=document.createElement('strong');selectionTitle.textContent='Piezas de esta propuesta';const selectionHint=document.createElement('small');selectionHint.textContent='Desmarca lo que ya tienes o no quieres comprar.';selectionCopy.append(selectionTitle,selectionHint);const selectionTotal=document.createElement('b');selectionHeading.append(selectionCopy,selectionTotal);products.append(selectionHeading);const updateDesignSelection=()=>{const checked=[...products.querySelectorAll('[data-design-product]:checked')];const total=checked.reduce((sum,node)=>sum+Number(node.dataset.budgetTarget||0),0);selectionTotal.textContent=`${checked.length} ${checked.length===1?'pieza':'piezas'} · ≈ $${total.toLocaleString('en-US',{maximumFractionDigits:0})}`;products.querySelectorAll('label').forEach(label=>label.classList.toggle('is-unselected',!label.querySelector('input').checked))};tierProducts.forEach(row=>{const label=document.createElement('label');const check=document.createElement('input');check.type='checkbox';check.checked=row.selected!==false;check.dataset.designProduct=row.id;check.dataset.budgetTarget=String(row.budget_target||0);const visual=makeDesignProductVisual(row.name);const name=document.createElement('span');const strong=document.createElement('strong');strong.textContent=row.name;const priority=document.createElement('small');priority.textContent=row.priority==='optional'?'Complemento opcional':'Pieza principal';name.append(strong,priority);const target=document.createElement('em');target.textContent=row.budget_target?`≈ $${Number(row.budget_target).toFixed(0)}`:'Comparar';check.addEventListener('change',updateDesignSelection);label.append(check,visual,name,target);products.append(label)});updateDesignSelection();
      const revision=document.createElement('form');revision.className='design-revision';const revisionLabel=document.createElement('label');const revisionTitle=document.createElement('span');revisionTitle.textContent='Pídele un cambio a Roxy';const revisionInput=document.createElement('input');revisionInput.name='instruction';revisionInput.maxLength=500;revisionInput.placeholder='Ej. Conserva el sofá y usa paredes beige';revisionInput.required=true;revisionLabel.append(revisionTitle,revisionInput);const revisionButton=document.createElement('button');revisionButton.type='submit';revisionButton.className='secondary';revisionButton.textContent='Aplicar cambio';revisionButton.disabled=!homeDesign.generation_configured||project.proposal_status==='GENERATING';revision.append(revisionLabel,revisionButton);revision.addEventListener('submit',event=>reviseDesignProject(event,project));
      const actions=document.createElement('div');actions.className='design-project-actions';const generate=makeButton(project.proposal_status==='FAILED'?'Intentar propuesta otra vez':project.proposal_url?'Actualizar propuesta':'Crear propuesta','primary',()=>generateDesignProposal(project.id,project.selected_tier));generate.disabled=project.proposal_status==='GENERATING'||!homeDesign.generation_configured;const buy=makeButton('Revisar productos','secondary',()=>prepareDesignPurchase(project,card));const remove=makeButton('Eliminar proyecto','danger-button',()=>deleteDesignProject(project));actions.append(generate,buy,remove);
      body.append(budgetPlan,analysis);if(recommendationRows.length)body.append(recommendations);body.append(fit,products,revision,actions);card.append(heading,visuals,decisions);if(comparisonControl)card.append(comparisonControl);card.append(body);root.append(card);
    });
  }
  async function submitDesignProject(event){
    event.preventDefault();const form=event.currentTarget;const button=$('designProjectSubmit');button.disabled=true;button.textContent='Guardando proyecto…';
    try{const photo=await readDesignPhoto($('designPhoto').files[0]);const data=await api(`/v1/home-design/${encodeURIComponent(user)}/projects`,{method:'POST',body:JSON.stringify({name:$('designName').value,room_type:$('designRoom').value,style:$('designStyle').value,budget:Number($('designBudget').value||0),measurements:$('designMeasurements').value,keep_items:commaValues($('designKeep').value),priorities:commaValues($('designPriorities').value),notes:$('designNotes').value,photo_data_url:photo})});$('designDialog').close();form.reset();$('designBudget').value='500';await refreshDesignProjects();announce('Espacio guardado. Roxy empieza el análisis.');if(homeDesign.generation_configured)await analyzeDesignProject(data.project.id)}catch(error){announce(error.message)}finally{button.disabled=false;button.textContent='Guardar espacio y analizar'}
  }
  async function generateDesignProposal(projectId,tier='balanced'){
    try{await api(`/v1/home-design/${encodeURIComponent(user)}/projects/${encodeURIComponent(projectId)}/proposal`,{method:'POST',body:JSON.stringify({tier})});announce('Roxy está creando la opción elegida sobre tu habitación real');await refreshDesignProjects()}catch(error){announce(error.message)}
  }
  async function analyzeDesignProject(projectId){
    try{announce('Roxy está revisando la habitación, los muebles y la distribución');const data=await api(`/v1/home-design/${encodeURIComponent(user)}/projects/${encodeURIComponent(projectId)}/analysis`,{method:'POST',body:'{}'});await refreshDesignProjects();announce('Análisis actualizado. Roxy está creando un rediseño completo.');await generateDesignProposal(projectId,data.project?.selected_tier||'balanced')}catch(error){announce(error.message)}
  }
  async function reviseDesignProject(event,project){
    event.preventDefault();const form=event.currentTarget;const button=form.querySelector('button[type="submit"]');const instruction=String(new FormData(form).get('instruction')||'').trim();if(!instruction)return;button.disabled=true;
    try{await api(`/v1/home-design/${encodeURIComponent(user)}/projects/${encodeURIComponent(project.id)}/revision`,{method:'POST',body:JSON.stringify({instruction,tier:project.selected_tier||'balanced'})});form.reset();announce('Roxy está aplicando tu cambio a la propuesta');await refreshDesignProjects()}catch(error){announce(error.message)}finally{button.disabled=false}
  }
  async function saveDesignMeasurements(event,projectId){
    event.preventDefault();const form=event.currentTarget;const button=form.querySelector('button[type="submit"]');const values=Object.fromEntries(new FormData(form));button.disabled=true;
    try{await api(`/v1/home-design/${encodeURIComponent(user)}/projects/${encodeURIComponent(projectId)}/measurements`,{method:'PUT',body:JSON.stringify({wall_width:Number(values.wall_width||0),passage_width:Number(values.passage_width||0),max_depth:Number(values.max_depth||0)})});await refreshDesignProjects();announce('Medidas guardadas. Roxy las usará para la propuesta y la comparación de productos.')}catch(error){announce(error.message)}finally{button.disabled=false}
  }
  async function prepareDesignPurchase(project,card){
    const ids=[...card.querySelectorAll('[data-design-product]:checked')].map(node=>node.dataset.designProduct);if(!ids.length){announce('Selecciona al menos un producto');return}
    try{const data=await api(`/v1/home-design/${encodeURIComponent(user)}/projects/${encodeURIComponent(project.id)}/commerce`,{method:'POST',body:JSON.stringify({product_ids:ids,provider_ids:[],tier:project.selected_tier||'balanced'})});currentPreparation=data.preparation;renderCommercePreparation(data.preparation,data.providers||commerce.providers||[]);$('commerceDialog').showModal()}catch(error){announce(error.message)}
  }
  async function deleteDesignProject(project){
    if(!window.confirm(`¿Eliminar “${project.name}” y sus imágenes privadas?`))return;
    try{await api(`/v1/home-design/${encodeURIComponent(user)}/projects/${encodeURIComponent(project.id)}`,{method:'DELETE'});await refreshDesignProjects();announce('Proyecto eliminado')}catch(error){announce(error.message)}
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
  async function preparePurchase(source='shopping',recipeId=null,preferredProviderId=null){
    const button=source==='shopping'?(preferredProviderId==='amazon'?$('prepareAmazonButton'):$('prepareShoppingButton')):null;
    const originalLabel=button&&button.textContent;
    if(button){button.disabled=true;button.textContent='Roxy está preparando…'}
    try{
      const data=await api(`/v1/home-commerce/${encodeURIComponent(user)}/preparations`,{method:'POST',body:JSON.stringify({source,recipe_id:recipeId,provider_ids:[]})});
      currentPreparation=data.preparation;
      renderCommercePreparation(data.preparation,data.providers||commerce.providers||[]);
      if($('recipeDialog').open)$('recipeDialog').close();
      if(!$('commerceDialog').open)$('commerceDialog').showModal();
      if(preferredProviderId){requestProviderLinks(preferredProviderId);setTimeout(()=>$('commerceConfirmation').scrollIntoView({behavior:'smooth',block:'center'}),50)}
    }catch(error){announce(error.message)}finally{if(button){button.disabled=false;button.textContent=originalLabel}}
  }
  function renderCommercePreparation(preparation,providers){
    $('commerceDialogTitle').textContent=preparation.source_title||'Tu compra personalizada';
    $('commerceDisclosureDialog').textContent=preparation.disclosure||commerce.disclosure||'';
    $('commerceProviderDisclosure').hidden=true;$('commerceProviderDisclosure').textContent='';
    const items=$('commerceItems');items.replaceChildren();
    if(preparation.source==='design'){const selected=preparation.items||[];const estimate=selected.reduce((sum,row)=>sum+Number(row.budget_target||0),0);const summary=document.createElement('div');summary.className='commerce-budget-summary';summary.innerHTML=`<span><small>Selección para comparar</small><strong>${selected.length} ${selected.length===1?'pieza':'piezas'}</strong></span><span><small>Presupuesto estimado</small><strong>≈ $${estimate.toLocaleString('en-US',{maximumFractionDigits:0})}</strong></span><p>Las fotos, medidas y precios reales aparecerán al abrir el comercio.</p>`;items.append(summary)}
    (preparation.items||[]).forEach(row=>{const article=document.createElement('article');const visual=preparation.source==='design'?makeDesignProductVisual(row.name):makeImage(row.name,row.category||'GENERAL','');const copy=document.createElement('div');const strong=document.createElement('strong');strong.textContent=`${row.quantity} ${row.unit} · ${row.name}`;const small=document.createElement('small');small.textContent=row.reason;copy.append(strong,small);if((row.avoided_brands||[]).length){const avoided=document.createElement('small');avoided.textContent=`Evitar: ${row.avoided_brands.join(', ')}`;copy.append(avoided)}if(row.allergen_review_required){const warning=document.createElement('em');warning.textContent='Verifica la etiqueta por tus alergias';copy.append(warning)}article.append(visual,copy);items.append(article)});
    pendingCommerceProvider=null;$('commerceConfirmation').hidden=true;$('commerceConfirmCheck').checked=false;$('commerceConfirmButton').disabled=true;$('commerceHandoffNote').textContent='';
    const actions=$('commerceActions');actions.replaceChildren();
    providers.filter(provider=>(preparation.providers||[]).includes(provider.id)).forEach(provider=>{const designLabel=preparation.source==='design'&&provider.design_only?`Abrir ${provider.name} · ${provider.affiliate_connected?'afiliado':'catálogo oficial'}`:'';const button=makeButton(provider.configured?(designLabel||`Continuar con ${provider.name}`):`${provider.name} · ${provider.status_label||'falta conectar'}`,provider.configured?'primary':'secondary',()=>requestProviderLinks(provider.id));button.disabled=!provider.configured;button.title=provider.next_step||provider.description||'';actions.append(button)});
  }
  function requestProviderLinks(providerId){
    if(!currentPreparation)return;
    const provider=(commerce.providers||[]).find(row=>row.id===providerId)||{id:providerId,name:'el comercio'};
    pendingCommerceProvider=provider;
    $('commerceConfirmTitle').textContent=`Continuar de forma segura con ${provider.name}`;
    $('commerceConfirmCopy').textContent=currentPreparation.source==='design'?`Roxy abrirá la búsqueda exacta en el catálogo oficial de ${provider.name}. Allí confirmarás la foto, medidas, disponibilidad y precio real antes de comprar.`:`Roxy preparará la entrega de tu lista. ${provider.name} mostrará disponibilidad, sustituciones y precio final antes del pago.`;
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
      const heading=document.createElement('strong');heading.textContent=`Productos preparados para ${provider.name}`;actions.append(heading);
      if(result.guidance){const guidance=document.createElement('p');guidance.className='commerce-guidance';guidance.textContent=result.guidance;actions.append(guidance)}
      const providerDisclosure=$('commerceProviderDisclosure');providerDisclosure.textContent=result.provider_disclosure||'';providerDisclosure.hidden=!result.provider_disclosure;
      (result.links||[]).slice(0,100).forEach(row=>{
        if(result.mode!=='product_links'){
          const link=document.createElement('a');link.className='primary commerce-link';link.href=row.url;link.target='_blank';link.rel='noopener sponsored';link.dataset.externalCheckout=provider.id;link.textContent=result.mode==='full_list'?`Revisar productos y pagar en ${provider.name}`:`Abrir ${provider.name} para seleccionar y pagar`;actions.append(link);return;
        }
        const article=document.createElement('article');article.className='commerce-product-link';
        const img=makeImage(row.label,row.category||'GENERAL','');
        const copy=document.createElement('div');const title=document.createElement('strong');title.textContent=row.label;
        const amount=document.createElement('span');amount.textContent=`${row.quantity||1} ${row.unit||'unidad'}`;
        const reason=document.createElement('small');reason.textContent=row.reason||'Búsqueda adaptada a tu lista.';copy.append(title,amount,reason);
        if((row.avoided_brands||[]).length){const avoided=document.createElement('small');avoided.className='commerce-avoid';avoided.textContent=`Evita: ${row.avoided_brands.join(', ')}`;copy.append(avoided)}
        if(row.allergen_review_required){const warning=document.createElement('em');warning.textContent='Comprueba ingredientes y alérgenos en la etiqueta';copy.append(warning)}
        const link=document.createElement('a');link.className='primary commerce-link';link.href=row.url;link.target='_blank';link.rel='noopener sponsored';link.dataset.externalCheckout=provider.id;link.setAttribute('aria-label',`Buscar ${row.label} en ${provider.name}`);link.textContent=`Buscar en ${provider.name}`;
        article.append(img,copy,link);actions.append(article);
      });
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
    $('cookingImage').hidden=false;hydrateRecipeImage($('cookingImage'),data.recipe,null,{hideOnMissing:true});
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
    $('commercePriceAlerts').checked=shoppingProfile.price_alerts_enabled!==false;
    $('commercePriceDrop').value=String(shoppingProfile.price_drop_percent||10);
    commerceLocation={enabled:shoppingProfile.location_enabled===true,latitude:shoppingProfile.latitude??null,longitude:shoppingProfile.longitude??null,accuracy:shoppingProfile.location_accuracy_m??null};
    renderCommerceLocation();
  }
  const commaList=value=>String(value||'').split(',').map(row=>row.trim()).filter(Boolean);
  function renderCommerceLocation(){const active=commerceLocation.enabled&&commerceLocation.latitude!==null&&commerceLocation.longitude!==null;$('commerceLocationStatus').textContent=active?`Ubicación aproximada guardada${commerceLocation.accuracy?` · precisión del dispositivo ${Math.round(commerceLocation.accuracy)} m`:''}. Solo se usa al consultar ofertas.`:'No guardada. Roxy no rastrea tu ubicación en segundo plano.';$('commerceClearLocation').hidden=!active;$('commerceUseLocation').textContent=active?'Actualizar ubicación':'Usar mi ubicación'}
  const commerceProfilePayload=()=>({objective:$('commerceObjective').value,organic_preference:$('commerceOrganic').value,favorite_retailers:commaList($('commerceRetailers').value),favorite_brands:commaList($('commerceBrands').value),avoided_brands:commaList($('commerceAvoidedBrands').value),dietary_labels:commaList($('commerceDietary').value),allow_substitutions:$('commerceSubstitutions').checked,postal_code:$('commercePostalCode').value.trim(),price_alerts_enabled:$('commercePriceAlerts').checked,price_drop_percent:Number($('commercePriceDrop').value||10),location_enabled:commerceLocation.enabled,latitude:commerceLocation.latitude,longitude:commerceLocation.longitude,location_accuracy_m:commerceLocation.accuracy});
  async function persistCommerceProfile(message='Tu perfil personal de compra quedó guardado'){await api(`/v1/home-commerce/${encodeURIComponent(user)}/profile`,{method:'PUT',body:JSON.stringify(commerceProfilePayload())});priceRecommendations=null;announce(message);await load({quiet:true})}
  function captureCommerceLocation(autoSave=false){if(!navigator.geolocation){announce('Este navegador no permite compartir ubicación');return}$('commerceUseLocation').disabled=true;['todayWeatherAction','calendarWeatherAsk'].forEach(id=>{$(id).disabled=true});$('commerceLocationStatus').textContent='Esperando tu autorización…';navigator.geolocation.getCurrentPosition(async position=>{commerceLocation={enabled:true,latitude:Number(position.coords.latitude.toFixed(3)),longitude:Number(position.coords.longitude.toFixed(3)),accuracy:Math.round(position.coords.accuracy||0)};renderCommerceLocation();try{if(autoSave)await persistCommerceProfile('Ubicación aproximada guardada. Roxy ya está cargando el clima real.');else announce('Ubicación aproximada lista. Guarda el perfil para usarla.')}catch(error){announce(error.message)}finally{$('commerceUseLocation').disabled=false;['todayWeatherAction','calendarWeatherAsk'].forEach(id=>{$(id).disabled=false})}},error=>{$('commerceUseLocation').disabled=false;['todayWeatherAction','calendarWeatherAsk'].forEach(id=>{$(id).disabled=false});renderCommerceLocation();announce(error.code===1?'No autorizaste la ubicación. Puedes seguir usando Roxy sin compartirla.':'No pude obtener la ubicación. Intenta nuevamente.')},{enableHighAccuracy:false,timeout:10000,maximumAge:300000})}
  function clearCommerceLocation(){commerceLocation={enabled:false,latitude:null,longitude:null,accuracy:null};renderCommerceLocation();announce('La ubicación se borrará cuando guardes el perfil')}
  async function saveHomeProfile(event){event.preventDefault();try{await api(`/v1/home-food/${encodeURIComponent(user)}/profile`,{method:'PUT',body:JSON.stringify({preferences:commaList($('homePreferences').value),allergies:commaList($('homeAllergies').value),dislikes:commaList($('homeDislikes').value),household_size:Number($('homeHousehold').value||1)})});announce('Preferencias guardadas en Roxy Home');await load({quiet:true});}catch(error){announce(error.message)}}
  async function saveCommerceProfile(event){event.preventDefault();try{await persistCommerceProfile()}catch(error){announce(error.message)}}
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
  const mealTypeLabels={breakfast:'Desayuno',lunch:'Comida',dinner:'Cena'};
  const mealDayStates={scheduled:'Planificado',cooked:'Ya cocinado',leftovers:'Comeremos sobras',skipped:'Día libre'};
  function renderMealPlan(plan){
    currentWeeklyPlan=plan||null;const result=$('mealPlanResult');const setup=$('mealPlanSetup');const daysRoot=$('mealPlanDays');daysRoot.replaceChildren();
    const remembered=homeFood.meal_planning||{};
    setup.classList.toggle('has-plan',Boolean(plan));
    setup.open=true;
    if(!plan){result.hidden=true;$('mealPlanCreate').textContent='Crear mi plan semanal';$('mealPlanCookDays').value=String(remembered.cook_days||2);$('mealPlanScope').value=remembered.meal_scope||'all';const rememberedStyle=document.querySelector(`input[name="mealPlanStyle"][value="${CSS.escape(remembered.style||'normal')}"]`);if(rememberedStyle)rememberedStyle.checked=true;return}
    result.hidden=false;$('mealPlanCreate').textContent='Actualizar mi plan semanal';$('mealPlanFocus').textContent=plan.focus||'Tu semana organizada';$('mealPlanBalance').textContent=plan.balance_note||plan.style_description||'Variado y equilibrado';$('mealPlanPrepTip').textContent=plan.prep_tip||'';
    $('mealPlanCookDays').value=String(plan.cook_days||2);$('mealPlanScope').value=plan.meal_scope||'all';
    const selected=document.querySelector(`input[name="mealPlanStyle"][value="${CSS.escape(plan.style||'normal')}"]`);if(selected)selected.checked=true;
    const planDays=plan.days||[];const today=new Date();today.setHours(12,0,0,0);const localDateKey=value=>`${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,'0')}-${String(value.getDate()).padStart(2,'0')}`;const storedTodayIndex=planDays.findIndex(day=>day.date===localDateKey(today));const rebaseDates=storedTodayIndex<0;const openDayIndex=storedTodayIndex<0?0:storedTodayIndex;
    planDays.forEach((day,index)=>{
      const dayStatus=day.status||'scheduled';const isOpen=index===openDayIndex;const article=document.createElement('article');article.className=`meal-plan-day meal-plan-day-${dayStatus}${isOpen?' open':''}`;
      const date=rebaseDates?new Date(today.getTime()+index*86400000):new Date(`${day.date}T12:00:00`);const weekday=new Intl.DateTimeFormat('es',{weekday:'short'}).format(date).replace('.','');const fullDate=new Intl.DateTimeFormat('es',{weekday:'long',day:'numeric',month:'long'}).format(date);
      const toggle=document.createElement('button');toggle.type='button';toggle.className='meal-plan-day-toggle';toggle.setAttribute('aria-expanded',String(isOpen));
      const summary=(day.meals||[]).map(meal=>meal.title).join(' · ');const stateCopy=dayStatus==='scheduled'?(isOpen?(day.meals||[]).map(meal=>mealTypeLabels[meal.meal_type]).join(' · '):summary):mealDayStates[dayStatus];toggle.innerHTML=`<span class="meal-plan-date"><small>${weekday}</small><strong>${date.getDate()}</strong></span><span class="meal-plan-day-title"><strong>${fullDate}</strong><small>${stateCopy}</small></span><span class="material-symbols-rounded meal-plan-chevron" aria-hidden="true">expand_less</span>`;
      toggle.addEventListener('click',()=>{const willOpen=!article.classList.contains('open');document.querySelectorAll('.meal-plan-day').forEach(row=>{row.classList.remove('open');row.querySelector('.meal-plan-day-toggle').setAttribute('aria-expanded','false')});article.classList.toggle('open',willOpen);toggle.setAttribute('aria-expanded',String(willOpen))});
      const body=document.createElement('div');body.className='meal-plan-day-body';
      (day.meals||[]).forEach((meal,mealIndex)=>{const row=document.createElement('article');row.className='meal-plan-meal';const image=document.createElement('img');hydrateRecipeImage(image,{title:meal.title,ingredients:meal.ingredients||[],kind:'meal'},row);image.alt=`${mealTypeLabels[meal.meal_type]||'Comida'}: ${meal.title}`;const copy=document.createElement('div');copy.className='meal-plan-meal-copy';const type=document.createElement('small');type.textContent=mealTypeLabels[meal.meal_type]||'Comida';const title=document.createElement('button');title.type='button';title.className='meal-plan-recipe-link';title.textContent=meal.title;title.setAttribute('aria-label',`Abrir receta ${meal.title}`);title.addEventListener('click',()=>openRecipeByTitle(meal.title));const meta=document.createElement('span');meta.className='meal-plan-meal-meta';meta.innerHTML=`<span class="material-symbols-rounded" aria-hidden="true">schedule</span>${meal.minutes||0} min`;const actions=document.createElement('span');actions.className='meal-plan-meal-actions';const swap=document.createElement('button');swap.type='button';swap.className='meal-plan-icon-button';swap.setAttribute('aria-label',`Cambiar ${meal.title}`);swap.innerHTML='<span class="material-symbols-rounded" aria-hidden="true">autorenew</span>';swap.addEventListener('click',()=>updateWeeklyPlanMeal(index,mealIndex,'swap'));const favorite=document.createElement('button');favorite.type='button';favorite.className=`meal-plan-icon-button${meal.favorite?' active':''}`;favorite.setAttribute('aria-label',`${meal.favorite?'Quitar de':'Guardar en'} favoritos ${meal.title}`);favorite.setAttribute('aria-pressed',String(Boolean(meal.favorite)));favorite.innerHTML=`<span class="material-symbols-rounded" aria-hidden="true">${meal.favorite?'favorite':'favorite_border'}</span>`;favorite.addEventListener('click',()=>updateWeeklyPlanMeal(index,mealIndex,'favorite'));actions.append(swap,favorite);copy.append(type,title,meta);row.append(image,copy,actions);body.append(row)});
      if(day.rescheduled_from){const moved=document.createElement('p');moved.className='meal-plan-reuse-note';moved.textContent='Roxy movió aquí las comidas de un día que quedó libre.';body.append(moved)}if(day.reuse_note){const reuse=document.createElement('p');reuse.className='meal-plan-reuse-note';reuse.textContent=day.reuse_note;body.append(reuse)}const live=document.createElement('details');live.className='meal-plan-live';const liveTitle=document.createElement('summary');liveTitle.textContent=dayStatus==='scheduled'?'Cambiar este día':mealDayStates[dayStatus];const liveActions=document.createElement('div');[['cooked','task_alt','Ya cocinamos'],['leftovers','takeout_dining','Comeremos sobras'],['skip','event_busy','No cocinaremos']].forEach(([action,icon,label])=>{const button=document.createElement('button');button.type='button';button.className=dayStatus===action?'active':'';button.disabled=dayStatus===action;button.innerHTML=`<span class="material-symbols-rounded" aria-hidden="true">${icon}</span>${label}`;button.addEventListener('click',()=>updateWeeklyPlanDay(index,action));liveActions.append(button)});if(dayStatus!=='scheduled'){const reset=document.createElement('button');reset.type='button';reset.innerHTML='<span class="material-symbols-rounded" aria-hidden="true">restart_alt</span>Restaurar';reset.addEventListener('click',()=>updateWeeklyPlanDay(index,'reset'));liveActions.append(reset)}live.append(liveTitle,liveActions);if(day.status_note){const note=document.createElement('p');note.textContent=day.status_note;live.append(note)}body.append(live);const ready=document.createElement('label');ready.className='meal-plan-ready';ready.innerHTML='<span>Ya tengo los ingredientes de este día</span>';const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=weeklyPlanReadyDays.has(index)||['cooked','leftovers','skipped'].includes(dayStatus);checkbox.disabled=['cooked','leftovers','skipped'].includes(dayStatus);checkbox.addEventListener('change',()=>checkbox.checked?weeklyPlanReadyDays.add(index):weeklyPlanReadyDays.delete(index));ready.append(checkbox);body.append(ready);article.append(toggle,body);daysRoot.append(article);
    });
    const prepRoot=$('mealPlanPrepSessions');prepRoot.replaceChildren();(plan.prep_sessions||[]).forEach(session=>{const article=document.createElement('article');article.className='meal-plan-prep-session';const header=document.createElement('header');const title=document.createElement('strong');title.textContent=session.title;const meta=document.createElement('span');const sessionDate=new Date(`${session.date}T12:00:00`);meta.textContent=`${new Intl.DateTimeFormat('es',{weekday:'long',day:'numeric'}).format(sessionDate)} · ${session.minutes} min`;header.append(title,meta);const list=document.createElement('ul');(session.tasks||[]).forEach(task=>{const item=document.createElement('li');item.textContent=task;list.append(item)});article.append(header,list);prepRoot.append(article)});
  }
  async function createWeeklyPlan(event){event.preventDefault();const button=$('mealPlanCreate');button.disabled=true;button.textContent='Roxy está organizando…';const style=(document.querySelector('input[name="mealPlanStyle"]:checked')||{}).value||'normal';const remembered=homeFood.meal_planning||{};const sameStyle=(currentWeeklyPlan&&currentWeeklyPlan.style||remembered.style)===style;const people=Number(currentWeeklyPlan&&currentWeeklyPlan.people||remembered.people||homeFood.profile&&homeFood.profile.household_size||2);const maxMinutes=style==='quick'?20:Number(sameStyle&&(currentWeeklyPlan&&currentWeeklyPlan.max_minutes||remembered.max_minutes)||25);const weeklyBudget=Number(currentWeeklyPlan&&currentWeeklyPlan.weekly_budget||remembered.weekly_budget||85);try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/weekly-plans`,{method:'POST',body:JSON.stringify({style,people,max_minutes:maxMinutes,weekly_budget:weeklyBudget,cook_days:Number($('mealPlanCookDays').value||2),meal_scope:$('mealPlanScope').value||'all'})});weeklyPlanReadyDays.clear();homeFood.meal_planning=data.meal_planning||homeFood.meal_planning;homeFood.weekly_plans=[...(homeFood.weekly_plans||[]),data.plan];renderMealPlan(data.plan);announce('Tu plan semanal quedó guardado y Roxy recordará estas preferencias')}catch(error){announce(error.message)}finally{button.disabled=false;button.textContent='Actualizar mi plan semanal'}}
  async function updateWeeklyPlanMeal(dayIndex,mealIndex,action){if(!currentWeeklyPlan)return;try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/weekly-plans/${encodeURIComponent(currentWeeklyPlan.id)}/meal`,{method:'PATCH',body:JSON.stringify({day_index:dayIndex,meal_index:mealIndex,action})});homeFood.weekly_plans=(homeFood.weekly_plans||[]).map(plan=>plan.id===data.plan.id?data.plan:plan);renderMealPlan(data.plan);document.querySelectorAll('.meal-plan-day').forEach((row,index)=>{const open=index===dayIndex;row.classList.toggle('open',open);row.querySelector('.meal-plan-day-toggle').setAttribute('aria-expanded',String(open))});announce(action==='swap'?'Roxy cambió esa comida':'Favorito actualizado')}catch(error){announce(error.message)}}
  async function updateWeeklyPlanDay(dayIndex,action){if(!currentWeeklyPlan)return;try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/weekly-plans/${encodeURIComponent(currentWeeklyPlan.id)}/day`,{method:'PATCH',body:JSON.stringify({day_index:dayIndex,action})});homeFood.weekly_plans=(homeFood.weekly_plans||[]).map(plan=>plan.id===data.plan.id?data.plan:plan);renderMealPlan(data.plan);document.querySelectorAll('.meal-plan-day').forEach((row,index)=>{const open=index===dayIndex;row.classList.toggle('open',open);row.querySelector('.meal-plan-day-toggle').setAttribute('aria-expanded',String(open))});announce(action==='reset'?'Día restaurado':`Semana reorganizada · ${(data.shopping_preview||[]).length} ingredientes pendientes`)}catch(error){announce(error.message)}}
  async function commitWeeklyPlan(){if(!currentWeeklyPlan)return;const confirmed=window.confirm('¿Agregar a tu lista los ingredientes de los días que todavía no tienes preparados?');if(!confirmed)return;const button=$('mealPlanShopping');button.disabled=true;try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/weekly-plans/${encodeURIComponent(currentWeeklyPlan.id)}/shopping-commit`,{method:'POST',body:JSON.stringify({confirmed:true,excluded_days:[...weeklyPlanReadyDays]})});await load({quiet:true});announce(`${(data.items||[]).length} ingredientes agregados a tu lista`)}catch(error){announce(error.message)}finally{button.disabled=false}}
  function toggleWeeklyPrep(){const section=$('mealPlanPrep');section.hidden=!section.hidden;$('mealPlanPrepare').setAttribute('aria-expanded',String(!section.hidden));if(!section.hidden)section.scrollIntoView({behavior:'smooth',block:'nearest'})}
  function renderSafety(result){const root=$('foodSafetyResult');root.replaceChildren();root.hidden=false;const title=document.createElement('h3');title.textContent='Investigación vigente';const answer=document.createElement('p');answer.textContent=result.answer||'No se encontró una respuesta concluyente.';root.append(title,answer);const sources=(result.sources||[]).filter(row=>row&&/^https?:\/\//.test(String(row.url||'')));if(sources.length){const list=document.createElement('ul');list.className='source-list';sources.forEach(source=>{const item=document.createElement('li');const link=document.createElement('a');link.href=source.url;link.target='_blank';link.rel='noopener noreferrer';link.textContent=source.title||source.authority||source.url;item.append(link);list.append(item)});root.append(list)}}
  async function researchFoodSafety(event){event.preventDefault();try{const data=await api(`/v1/home-food/${encodeURIComponent(user)}/food-safety`,{method:'POST',body:JSON.stringify({question:$('foodSafetyQuestion').value})});renderSafety(data.result)}catch(error){announce(error.message)}}

  function submitCustom(event){event.preventDefault();const name=$('customName').value.trim();const quantity=Number($('customQuantity').value);const unit=$('customUnit').value.trim();if(!name||!unit||!(quantity>0)){announce('Completa producto, cantidad y unidad');return}addItem({name,quantity,unit,category:$('customCategory').value});$('customForm').reset();$('customQuantity').value='1';$('customUnit').value='unidad';$('customDialog').close()}
  async function pair(event){event.preventDefault();const token=$('apiToken').value;const candidate=$('userId').value.trim()||'local_user';$('pairError').textContent='';try{await api(`/v1/shopping/session/${encodeURIComponent(candidate)}`,{method:'POST',headers:{Authorization:`Bearer ${token}`}});user=candidate;localStorage.setItem('roxyShoppingUser',user);$('apiToken').value='';$('pairDialog').close();await load()}catch(error){$('pairError').textContent=error.message}}
  async function login(event){event.preventDefault();$('loginError').textContent='';try{const result=await api('/v1/home-account/login',{method:'POST',body:JSON.stringify({username:$('loginUsername').value.trim(),password:$('loginPassword').value})});account=result;user=result.storage_user_id;localStorage.setItem('roxyShoppingUser',user);$('loginPassword').value='';$('pairDialog').close();await load()}catch(error){$('loginError').textContent=error.message}}
  function renderAccount(){const person=activePersonName();$('accountSummary').textContent=account.mode==='member'?`${person} · ${account.household_name} · la compra, recetas y despensa son compartidas.`:account.mode==='signed_out'?'Tu sesión personal está cerrada. Entra de nuevo; Roxy no ha ejecutado ningún borrado de personas ni recorridos.':account.requires_profile_setup?'Este dispositivo usa el acceso anterior. Crea los perfiles personales sin perder los datos actuales.':'Entra con tu perfil para que Roxy sepa quién eres.';$('accountButton').textContent=account.mode==='member'?'Administrar personas':account.requires_profile_setup?'Crear perfiles personales':'Entrar con mi perfil'}
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
    try{const result=await sendRoxyHomeCommand({command});input.value='';announce(result.message||'Listo');if(result.data&&result.data.weekly_plan){await load({quiet:true});selectPanel('today')}if(result.data&&result.data.recipe){await load({quiet:true});selectPanel('recipes');openRecipe(result.data.recipe)}if(result.data&&result.data.cooking){await load({quiet:true});showCooking(result.data.cooking)}if(result.data&&result.data.calendar_draft){showCalendarConfirmation(result.data.calendar_draft,result.data.calendar_conflicts||[])}if(result.data&&result.data.calendar_event){await load({quiet:true});selectPanel('calendar')}if(result.data&&result.data.weather&&result.data.weather.status==='READY'){homeWeather=result.data.weather;renderWeather();renderCalendar()}if(result.data&&result.data.price_recommendations){priceRecommendations=result.data.price_recommendations;selectPanel('shopping');renderPriceRecommendations()}}catch(error){announce(error.message)}finally{button.disabled=false;button.textContent='Enviar'}
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
  async function sendRoxyHomeCommand(parameters={}){const command=String(parameters.command||parameters.text||parameters.request||'').trim();if(!command)return{ok:false,error:'missing_command'};const result=await api(`/v1/assistant/command/${encodeURIComponent(user)}`,{method:'POST',body:JSON.stringify({text:command})});await load({quiet:true});if(result.message)roxyVoiceTranscript(result.message);if(result.data&&result.data.cooking)showCooking(result.data.cooking);if(result.data&&result.data.calendar_draft)showCalendarConfirmation(result.data.calendar_draft,result.data.calendar_conflicts||[]);if(result.data&&result.data.calendar_event)selectPanel('calendar');if(result.data&&result.data.weather&&result.data.weather.status==='READY'){homeWeather=result.data.weather;renderWeather();renderCalendar()}if(result.data&&result.data.price_recommendations){priceRecommendations=result.data.price_recommendations;selectPanel('shopping');renderPriceRecommendations()}if(result.data&&result.data.preparation){currentPreparation=result.data.preparation;renderCommercePreparation(currentPreparation,result.data.providers||commerce.providers||[]);if(!$('commerceDialog').open)$('commerceDialog').showModal()}return result}
  function recoverRoxyVoiceSpeech(speech,startedAt){setTimeout(()=>{if(!roxyVoiceConversation||!speech)return;const answer=String(roxyLastAgentMessage||'').toLowerCase();const falseFailure=/no (?:puedo|tengo acceso)|no (?:est[aá]|estaba) funcionando|b[uú]squeda.{0,30}recet|problema.{0,30}recet/.test(answer);if(roxyLastAgentMessageAt<=startedAt||falseFailure){const instruction=`[RESULTADO CONFIRMADO DE ROXY HOME. NO LLAMES HERRAMIENTAS.] Lee en voz alta exactamente este resultado completo y después pregunta si deseo agregar los ingredientes o cocinar paso a paso: ${speech}`;if(typeof roxyVoiceConversation.sendUserMessage==='function')roxyVoiceConversation.sendUserMessage(instruction)}},3200)}
  async function sendCommandToRoxyOSForVoice(parameters={}){const startedAt=Date.now();const result=await sendRoxyHomeCommand(parameters);const speech=String(result.speech||result.message||'').trim();recoverRoxyVoiceSpeech(speech,startedAt);return{ok:Boolean(result.ok),intent:result.intent||'general',must_speak:true,speech,message:speech,data:result.data||{},instruction:'Espera a que termine esta herramienta. Lee en voz alta ahora el campo speech completo. No lo resumas, no lo contradigas y no digas que no tienes acceso.'}}
  function roxyHomeClientTools(){return{getCurrentScreenContext:async()=>({ok:true,app:'Roxy Home',page:'Hoy, plan de comidas, compra, recetas, despensa, calendario y clima',provider:'ElevenLabs',member:{display_name:activePersonName(),role:account.role,household_name:account.household_name},profile:homeFood.profile||{},pantry:(homeFood.pantry||[]).slice(0,80),daily_brief:homeDaily,weather:homeWeather&&homeWeather.status==='READY'?{location:homeWeather.location,current:homeWeather.current,daily:(homeWeather.daily||[]).slice(0,8)}:{status:homeWeather&&homeWeather.status},shopping_list:currentShoppingSummary(),calendar:{upcoming:(homeCalendar.events||[]).slice(0,20)},latest_recipe:currentRecipe&&{id:currentRecipe.id,title:currentRecipe.title,servings:currentRecipe.servings},instruction:'Eres la misma Roxy, operando únicamente con memoria y permisos de Home. Usa los datos reales de esta pantalla, sintetiza y recomienda con criterio sin inventar.'}),getShoppingList:async()=>({ok:true,shopping_list:currentShoppingSummary()}),summarizeCurrentScreen:async()=>({ok:true,summary:`Roxy Home muestra ${activeItems().length} productos pendientes, ${(homeFood.recipes||[]).length} recetas guardadas y ${(homeCalendar.events||[]).length} eventos próximos.`,shopping_list:currentShoppingSummary()}),sendCommandToRoxyOS:sendCommandToRoxyOSForVoice}}
  function roxyHomeOverrides(){const shopping=JSON.stringify(currentShoppingSummary());const person=activePersonName();const greeting=person?`Hola, ${person}. ¿Qué hacemos hoy?`:'Hola. ¿Qué hacemos hoy?';return{agent:{language:'es',firstMessage:greeting,prompt:{prompt:`Eres Roxy, con la misma identidad y voz del ecosistema Roxy, operando únicamente dentro de Roxy Home. La aplicación actual es Roxy Home, en las secciones Compra, Recetas, Plan semanal, Despensa y Calendario. Estás hablando con ${person||'una persona del hogar'}; dirígete a esa persona por su nombre de forma natural, sin repetir su nombre en cada frase. Conversa en español natural, cálido y adulto. Comprende la intención antes de contestar: responde primero, explica brevemente por qué y ofrece una recomendación concreta cuando aporte valor. No copies listas de datos sin interpretarlas. Compara opciones, comenta ventajas y límites, y puedes discrepar con amabilidad. Distingue hechos de inferencias, reconoce lo que no sabes y no reveles razonamiento interno paso a paso. Usa vocabulario variado pero sencillo, evita muletillas y no hagas más de una pregunta de seguimiento. No vuelvas a presentarte ni digas “soy Roxy” o “estoy aquí para ayudarte”; el usuario ya sabe quién eres. Mantén la conversación abierta después del saludo y nunca uses end_call salvo que el usuario diga claramente terminar o adiós. La lista visible actual es ${shopping}. Para crear, consultar, mover o cancelar eventos, consultar el clima local o de otro destino, y para pedir una receta, cambiar la lista, organizar el menú o cocinar paso a paso, siempre usa sendCommandToRoxyOS. No respondas antes de que la herramienta termine. Nunca afirmes que guardaste un evento antes de que la herramienta lo confirme. Para un evento nuevo, lee la propuesta y pregunta si debe confirmarse; cuando el usuario diga sí, vuelve a llamar la herramienta con “confirmo”. Los eventos recurrentes necesitan fecha de inicio y final. Diferencia: dentista o llamada con fecha y hora va al calendario; comprar leche va a compras; pagar una factura antes de una fecha es una tarea y no debe convertirse en evento sin aclararlo. Cuando la herramienta termine, lee en voz alta exactamente el campo speech completo, incluyendo si se sincronizó con el teléfono o si falta conectar Google Calendar. Si recibes RESULTADO CONFIRMADO DE ROXY HOME, no vuelvas a llamar herramientas. Expresiones como quita, saca o ya no necesito son órdenes de eliminación. No inventes eventos, artículos, recetas, precios, disponibilidad ni alergias. No compres, no pagues, no controles dispositivos y no uses memoria ni herramientas de Trading, Finanzas o Study.`}}}}
  async function startRoxyVoice(){if(roxyVoiceConversation||roxyVoiceStarting)return;openRoxyVoice();roxyVoiceStarting=true;roxyLastAgentMessage='';roxyLastAgentMessageAt=0;$('roxyVoiceStart').disabled=true;let phase='configuración';roxyVoiceStatus('Conectando con ElevenLabs…');try{if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia)throw new DOMException('Micrófono no disponible','NotFoundError');phase='permiso del micrófono';roxyVoicePermissionStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});const config=await api(`/v1/assistant/session/${encodeURIComponent(user)}`);phase='carga del agente';const eleven=await loadElevenLabs();const Conversation=eleven.Conversation||(eleven.default&&eleven.default.Conversation);if(!Conversation||!Conversation.startSession)throw new Error('SDK de ElevenLabs no disponible');phase='conexión de voz';const options={connectionType:'websocket',overrides:roxyHomeOverrides(),dynamicVariables:{...(config.dynamic_variables||{}),shopping_list_json:JSON.stringify(currentShoppingSummary())},clientTools:roxyHomeClientTools(),onConnect:()=>{roxyVoiceStarting=false;roxyVoiceStatus('Roxy te está escuchando');$('roxyVoiceStart').disabled=true;$('roxyVoiceEnd').disabled=false},onDisconnect:details=>{console.info('Roxy Home ElevenLabs disconnected',details||'normal');stopRoxyPermissionStream();roxyVoiceConversation=null;roxyVoiceStarting=false;const endedByAgent=details&&details.reason==='agent';roxyVoiceStatus(endedByAgent?'Roxy terminó la llamada antes de tiempo. Pulsa iniciar para reconectar.':'Conversación terminada',endedByAgent);$('roxyVoiceStart').disabled=false;$('roxyVoiceEnd').disabled=true},onError:error=>{console.warn('Roxy Home ElevenLabs error',error);stopRoxyPermissionStream();roxyVoiceStarting=false;roxyVoiceStatus(roxyVoiceError(error,'conversación'),true);$('roxyVoiceStart').disabled=false;$('roxyVoiceEnd').disabled=true},onModeChange:mode=>{const state=String(mode&&mode.mode||mode||'').toLowerCase();if(state.includes('speaking'))roxyVoiceStatus('Roxy está respondiendo');else if(state.includes('listening'))roxyVoiceStatus('Roxy te está escuchando')},onMessage:message=>{const source=String(message&&((message.source||message.role||message.type))||'').toLowerCase();const text=message&&(message.message||message.text||message.transcript||message.content||(message.agent_response_event&&message.agent_response_event.agent_response)||(message.user_transcription_event&&message.user_transcription_event.user_transcript));if(typeof text==='string'&&text.trim()){const fromUser=source.includes('user');if(!fromUser){roxyLastAgentMessage=text.trim();roxyLastAgentMessageAt=Date.now()}roxyVoiceTranscript(text.trim(),fromUser?'Tú':'Roxy')}}};if(config.conversation_token)options.conversationToken=config.conversation_token;else options.agentId=config.agent_id;roxyVoiceConversation=await Conversation.startSession(options);stopRoxyPermissionStream()}catch(error){console.warn('Roxy Home ElevenLabs start failed',error);stopRoxyPermissionStream();roxyVoiceConversation=null;roxyVoiceStarting=false;roxyVoiceStatus(roxyVoiceError(error,phase),true);$('roxyVoiceStart').disabled=false;$('roxyVoiceEnd').disabled=true}}
  async function endRoxyVoice(){const conversation=roxyVoiceConversation;roxyVoiceConversation=null;stopRoxyPermissionStream();if(conversation&&typeof conversation.endSession==='function'){try{await conversation.endSession()}catch(error){console.warn('Roxy Home ElevenLabs end failed',error)}}roxyVoiceStarting=false;roxyVoiceStatus('Conversación terminada');$('roxyVoiceStart').disabled=false;$('roxyVoiceEnd').disabled=true}

  function renderProductLookup(result){
    const root=$('productLookupResult');root.replaceChildren();
    const product=result.product||result.nutrition_reference;
    if(!product){const empty=document.createElement('p');const nameLookup=result.capabilities?.name_lookup!==false;empty.textContent=!nameLookup&&!result.barcode?'La búsqueda por nombre necesita activar la referencia privada de USDA en Roxy Home. Mientras tanto, escanea o escribe el código de barras para consultar Open Food Facts.':'No encontré una coincidencia verificable. Revisa el código o escribe un nombre más específico.';root.append(empty);return}
    const hero=document.createElement('div');hero.className=`product-lookup-product${product.image_url?'':' no-image'}`;
    if(product.image_url){const image=document.createElement('img');image.src=product.image_url;image.alt=`Envase de ${product.name||'producto'}`;image.referrerPolicy='no-referrer';hero.append(image)}
    const copy=document.createElement('span');const title=document.createElement('strong');title.textContent=product.name||result.query||'Producto identificado';const detail=document.createElement('small');detail.textContent=[product.brand,product.quantity].filter(Boolean).join(' · ')||'Coincidencia de una fuente pública';copy.append(title,detail);hero.append(copy);root.append(hero);
    const facts=document.createElement('div');facts.className='product-facts';
    if(product.nutriscore){const row=document.createElement('span');row.textContent=`Nutri-Score ${product.nutriscore}`;facts.append(row)}
    if(product.nova_group){const row=document.createElement('span');row.textContent=`NOVA ${product.nova_group}`;facts.append(row)}
    const nutrition=result.nutrition_reference;if(nutrition&&nutrition.serving_size){const row=document.createElement('span');row.textContent=`Porción ${nutrition.serving_size} ${nutrition.serving_unit||''}`.trim();facts.append(row)}
    if(facts.children.length)root.append(facts);
    const recall=document.createElement('div');recall.className=`product-recall${result.recalls&&result.recalls.length?' has-match':''}`;recall.textContent=result.recall_summary?.message||'Revisa siempre la etiqueta y los avisos oficiales.';root.append(recall);
    const links=document.createElement('div');links.className='product-source-links';(result.sources||[]).forEach(source=>{if(!source.url)return;const link=document.createElement('a');link.href=source.url;link.target='_blank';link.rel='noopener noreferrer';link.textContent=`Ver ${source.label||'fuente'}`;links.append(link)});if(links.children.length)root.append(links);
    const add=document.createElement('button');add.type='button';add.className='primary full';add.textContent='Agregar a mi lista';add.addEventListener('click',()=>addItem({name:product.name||result.query,quantity:1,unit:'unidad',category:inferShoppingCategory(product.name||result.query,'FOOD')}));root.append(add);
  }
  async function lookupProduct(event){
    event.preventDefault();const button=$('productLookupButton');const barcode=$('productLookupBarcode').value.replace(/\D/g,'');const query=$('productLookupQuery').value.trim();
    if(!barcode&&!query){announce('Escanea un código o escribe el nombre del producto.');return}
    button.disabled=true;button.textContent='Consultando…';$('productLookupResult').textContent='Roxy está consultando las fuentes disponibles…';
    try{const result=await api(`/v1/home-products/${encodeURIComponent(user)}/lookup`,{method:'POST',body:JSON.stringify({barcode,query})});renderProductLookup(result)}catch(error){$('productLookupResult').textContent=error.message;announce(error.message)}finally{button.disabled=false;button.textContent='Consultar fuentes'}
  }
  async function scanProductBarcode(event){
    const file=event.currentTarget.files?.[0];if(!file)return;
    if(!('BarcodeDetector'in window)){announce('Este navegador no puede leer códigos desde fotos. Escribe los números que aparecen debajo del código.');event.currentTarget.value='';return}
    try{const bitmap=await createImageBitmap(file);const detector=new BarcodeDetector({formats:['ean_13','ean_8','upc_a','upc_e']});const codes=await detector.detect(bitmap);bitmap.close();const value=String(codes[0]?.rawValue||'').replace(/\D/g,'');if(!value)throw new Error('No pude leer el código. Acerca la cámara y evita reflejos.');$('productLookupBarcode').value=value;announce(`Código ${value} detectado`);$('productLookupForm').requestSubmit()}catch(error){announce(error.message)}finally{event.currentTarget.value=''}
  }

  function render(){renderShopping();renderRecipes();renderWeather();renderCalendar();renderHomeDaily();renderDesign();renderPlants();renderFamily();const latest=(homeFood.weekly_plans||[]).slice(-1)[0]||null;renderMealPlan(latest)}
  function bind(){
    document.addEventListener('error',event=>{const image=event.target;if(!(image instanceof HTMLImageElement)||!image.src.includes('/v1/home-food/recipe-photo'))return;const card=image.closest('.recipe-card,.recipe-detail-hero,.meal-plan-meal');if(card)card.classList.add('no-photo');image.remove()},true);
    $('searchInput').addEventListener('input',event=>{search=event.target.value;renderShopping()});
    $('toggleStaples').addEventListener('click',()=>{showAllStaples=!showAllStaples;renderShopping()});
    $('focusListButton').addEventListener('click',()=>$('shoppingList').scrollIntoView({behavior:'smooth',block:'start'}));
    $('customForm').addEventListener('submit',submitCustom);
    $('pairForm').addEventListener('submit',pair);
    $('loginForm').addEventListener('submit',login);
    $('accountButton').addEventListener('click',openAccountDialog);
    $('personalizationButton').addEventListener('click',openPersonalization);
    $('personalizationForm').addEventListener('submit',savePersonalization);
    $('personalizationForm').addEventListener('input',renderPersonalizationPreview);
    $('personalizationForm').addEventListener('change',renderPersonalizationPreview);
    $('bootstrapAccountForm').addEventListener('submit',bootstrapAccount);
    $('addMemberForm').addEventListener('submit',addHouseholdMember);
    $('completeButton').addEventListener('click',complete);
    $('confirmComplete').addEventListener('click',confirmComplete);
    $('shareButton').addEventListener('click',share);
    $('disconnectButton').addEventListener('click',disconnect);
    $('homeProfileForm').addEventListener('submit',saveHomeProfile);
    $('commerceProfileForm').addEventListener('submit',saveCommerceProfile);
    $('commerceUseLocation').addEventListener('click',()=>captureCommerceLocation(false));
    $('commerceClearLocation').addEventListener('click',clearCommerceLocation);
    $('refreshPricesButton').addEventListener('click',()=>loadPriceRecommendations());
    $('prepareAmazonButton').addEventListener('click',()=>preparePurchase('shopping',null,'amazon'));
    $('prepareShoppingButton').addEventListener('click',()=>preparePurchase('shopping'));
    $('productLookupForm').addEventListener('submit',lookupProduct);
    $('productBarcodeImage').addEventListener('change',scanProductBarcode);
    $('commerceConfirmCheck').addEventListener('change',()=>{$('commerceConfirmButton').disabled=!$('commerceConfirmCheck').checked});
    $('commerceConfirmCancel').addEventListener('click',()=>{pendingCommerceProvider=null;$('commerceConfirmation').hidden=true});
    $('commerceConfirmButton').addEventListener('click',confirmProviderHandoff);
    const selectedDesignRoom=()=>document.querySelector('[data-design-room].active')?.dataset.designRoom||'living_room';
    const openDesignDialog=({room=selectedDesignRoom(),camera=false}={})=>{$('designRoom').value=room;if(camera)$('designPhoto').setAttribute('capture','environment');else $('designPhoto').removeAttribute('capture');$('designDialog').showModal()};
    $('newDesignProjectButton').addEventListener('click',()=>openDesignDialog());
    $('designTakePhotoButton').addEventListener('click',()=>openDesignDialog({camera:true}));
    $('designUploadButton').addEventListener('click',()=>openDesignDialog());
    $('designStartAnalysis').addEventListener('click',()=>openDesignDialog());
    document.querySelectorAll('[data-design-room]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-design-room]').forEach(item=>item.classList.toggle('active',item===button));$('designRoom').value=button.dataset.designRoom}));
    $('designProjectForm').addEventListener('submit',submitDesignProject);
    $('newPlantButton').addEventListener('click',()=>{$('plantIdentificationNote').hidden=true;$('plantDialog').showModal()});
    $('plantForm').addEventListener('submit',submitPlant);
    $('plantCalendarButton').addEventListener('click',()=>selectPanel('calendar'));
    $('plantVacationButton').addEventListener('click',()=>{const value=homePlants.vacation||{};$('plantVacationEnabled').checked=Boolean(value.enabled);$('plantVacationStart').value=value.starts_on||'';$('plantVacationEnd').value=value.ends_on||'';$('plantVacationCaregiver').value=value.caregiver||'';$('plantVacationNotes').value=value.notes||'';$('plantVacationDialog').showModal()});
    $('plantVacationForm').addEventListener('submit',savePlantVacation);
    $('familyShareLocation').addEventListener('click',shareFamilyLocation);
    $('familyStopLocation').addEventListener('click',stopFamilyLocation);
    $('familyPrivacyButton').addEventListener('click',()=>{$('familySettings').open=true;$('familySettings').scrollIntoView({behavior:'smooth',block:'start'})});
    $('familyChatButton').addEventListener('click',()=>$('roxyVoiceLauncher').click());
    $('familyHomeMenu').addEventListener('click',()=>{$('familySettings').open=true;$('familySettings').scrollIntoView({behavior:'smooth',block:'start'})});
    $('familyAddConnection').addEventListener('click',()=>{$('familySettings').open=true;$('familyInviteName').focus();$('familySettings').scrollIntoView({behavior:'smooth',block:'start'})});
    $('familyHistoryButton').addEventListener('click',()=>void loadFamilyHistoryPanel(!familyHistoryOpen));
    $('familyHistoryClose').addEventListener('click',()=>{familyHistoryOpen=false;renderFamilyHistoryPanel(familyHistoryPoints)});
    $('familyMapLayers').addEventListener('click',()=>{if(!familyMap)return;familyMapStyle=familyMapStyle==='roadmap'?'satellite':'roadmap';familyMap.setMapTypeId(familyMapStyle);announce(familyMapStyle==='satellite'?'Vista satélite activada':'Vista de mapa activada')});
    $('familyMapLocate').addEventListener('click',()=>{const member=(homeFamily.members||[]).find(row=>row.is_viewer&&row.location);if(!familyMap||!member){announce('Activa tu ubicación para centrar el mapa.');return}familyMap.panTo({lat:Number(member.location.latitude),lng:Number(member.location.longitude)});familyMap.setZoom(16)});
    $('familyWeatherGlobeClose').addEventListener('click',()=>exitFamilyWeatherGlobe());
    $('familyWeatherGlobePlay').addEventListener('click',()=>{familyWeatherGlobePlaying=!familyWeatherGlobePlaying;syncFamilyWeatherGlobePlayback()});
    $('familyWeatherGlobeLocate').addEventListener('click',()=>{if(!familyWeatherGlobeMap)return;familyWeatherGlobeMap.flyTo({center:familyWeatherGlobeCenter(),zoom:4.6,duration:1100,essential:true});announce('Radar centrado en tu ubicación disponible')});
    $('familyWeatherGlobeTimeline').addEventListener('input',event=>{familyWeatherGlobePlaying=false;setFamilyWeatherGlobeFrame(event.currentTarget.value);syncFamilyWeatherGlobePlayback()});
    $('familyPlaceForm').addEventListener('submit',saveFamilyPlace);
    $('familyPlaceName').addEventListener('input',inferFamilyPlaceKind);
    $('familyProfileForm').addEventListener('submit',saveFamilyProfile);
    $('familyProfileName').addEventListener('input',()=>{$('familyProfileInitials').textContent=familyProfileEmoji||familyInitials($('familyProfileName').value)});
    $('familyProfilePhoto').addEventListener('change',async event=>{const input=event.currentTarget;try{const file=input.files?.[0];if(!file)return;input.disabled=true;renderFamilyProfilePhoto(await readFamilyProfilePhoto(file));familyProfileEmoji='';$('familyProfileForm').querySelectorAll('[name="familyProfileEmoji"]').forEach(option=>{option.checked=option.value===''});const viewer=(homeFamily.members||[]).find(member=>member.is_viewer);if(viewer){viewer.profile_photo=familyProfilePhotoData;viewer.profile_emoji=''}renderFamilyExperience();await renderFamilyMap();await persistFamilyProfile('Tu foto ya está guardada y visible en Nexo')}catch(error){announce(error.message);input.value=''}finally{input.disabled=false}});
    $('familyProfileRemovePhoto').addEventListener('click',async()=>{const button=$('familyProfileRemovePhoto');button.disabled=true;try{renderFamilyProfilePhoto('');$('familyProfilePhoto').value='';await persistFamilyProfile('Tu foto se eliminó de Nexo')}catch(error){announce(error.message)}finally{button.disabled=false}});
    $('familyProfileForm').querySelectorAll('[name="familyProfileEmoji"]').forEach(input=>input.addEventListener('change',()=>{familyProfileEmoji=input.value;$('familyProfileInitials').textContent=familyProfileEmoji||familyInitials($('familyProfileName').value);if(familyProfileEmoji){renderFamilyProfilePhoto('');$('familyProfilePhoto').value=''}}));
    $('familyProfileForm').querySelectorAll('[name="familyMarkerColor"]').forEach(input=>input.addEventListener('change',()=>{$('familyProfileForm').querySelector('.family-profile-preview').style.background=familyMarkerColors[input.value]}));
    $('familyInviteForm').addEventListener('submit',createFamilyInvitation);
    window.addEventListener('pageshow',()=>{if(homeFamily.members?.length)void resumeFamilyLocationIfEnabled()});
    document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'&&homeFamily.members?.length)void resumeFamilyLocationIfEnabled()});
    $('pantryForm').addEventListener('submit',savePantry);
    $('recipeForm').addEventListener('submit',createRecipe);
    $('scanRecipeButton').addEventListener('click',()=>openRecipeImporter('image'));
    $('importRecipeUrlButton').addEventListener('click',()=>openRecipeImporter('url'));
    $('recipeImportForm').addEventListener('submit',analyzeRecipeImport);
    $('recipeImportSave').addEventListener('click',saveImportedRecipe);
    $('addPetButton').addEventListener('click',addPet);
    $('startPetProfile').addEventListener('click',openPetProfile);
    $('closePetProfile').addEventListener('click',()=>$('petProfileDialog').close());
    $('petProfileLater').addEventListener('click',()=>$('petProfileDialog').close());
    $('petProfileBack').addEventListener('click',()=>advancePetProfile(-1));
    $('petProfileNext').addEventListener('click',()=>advancePetProfile(1));
    $('petProfileForm').addEventListener('submit',savePetProfile);
    $('petProfilePhoto').addEventListener('change',previewPetPhoto);
    $('petProfileSpecies').addEventListener('change',()=>adaptPetQuestions());
    $('editPetProfile').addEventListener('click',()=>openPetProfile(selectedPetProfile()));
    $('addPetMedical').addEventListener('click',openPetMedical);
    $('exportPetMedical').addEventListener('click',exportPetMedicalSummary);
    $('exportPetVaccines').addEventListener('click',exportPetVaccines);
    $('addPetDocument').addEventListener('click',openPetMedical);
    $('petMedicalForm').addEventListener('submit',savePetMedical);
    $('petMedicalAttachment').addEventListener('change',choosePetMedicalAttachment);
    document.querySelectorAll('[data-pet-hub-tab]').forEach(button=>{button.addEventListener('click',()=>{petHubTab=button.dataset.petHubTab;renderRecipes()});button.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const tabs=[...document.querySelectorAll('[data-pet-hub-tab]')];const current=tabs.indexOf(button);const target=event.key==='Home'?0:event.key==='End'?tabs.length-1:(current+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;tabs[target].click();tabs[target].focus()})});
    document.querySelectorAll('[data-recipe-audience]').forEach(button=>button.addEventListener('click',()=>setRecipeAudience(button.dataset.recipeAudience)));
    $('beverageForm').addEventListener('submit',createBeverage);
    $('pantryRecipeButton').addEventListener('click',createRecipeFromPantry);
    $('recipePersonalForm').addEventListener('submit',saveRecipePersonalization);
    $('deleteRecipeButton').addEventListener('click',deleteCurrentRecipe);
    $('substitutionForm').addEventListener('submit',createSubstitution);
    $('mealPlanForm').addEventListener('submit',createWeeklyPlan);
    $('mealPlanForm').addEventListener('change',()=>{if(currentWeeklyPlan&&!$('mealPlanCreate').disabled)$('mealPlanForm').requestSubmit()});
    $('mealPlanShopping').addEventListener('click',commitWeeklyPlan);
    $('mealPlanPrepare').addEventListener('click',toggleWeeklyPrep);
    $('foodSafetyForm').addEventListener('submit',researchFoodSafety);
    $('roxyCommandForm').addEventListener('submit',submitRoxyCommand);
    $('greetingSettingsButton').addEventListener('click',()=>account.mode==='member'?openPersonalization():openGreetingSettings());
    $('greetingForm').addEventListener('submit',saveGreeting);
    $('clearGreetingButton').addEventListener('click',clearGreeting);
    $('roxyVoiceLauncher').addEventListener('click',openRoxyVoice);
    $('roxyVoiceClose').addEventListener('click',closeRoxyVoice);
    $('roxyVoiceStart').addEventListener('click',startRoxyVoice);
    $('roxyVoiceEnd').addEventListener('click',endRoxyVoice);
    $('calendarAddButton').addEventListener('click',()=>openCalendarEvent());
    $('calendarVoiceButton').addEventListener('click',openRoxyVoice);
    $('todayWeatherAction').addEventListener('click',()=>{if(homeWeather&&homeWeather.status==='READY')selectPanel('calendar');else captureCommerceLocation(true)});
    $('calendarWeatherAsk').addEventListener('click',()=>{if(homeWeather&&homeWeather.status==='READY'){$('roxyCommand').value='Roxy, ¿cómo estará el clima esta semana?';openRoxyVoice()}else captureCommerceLocation(true)});
    $('calendarGoogleSync').addEventListener('click',syncGoogleCalendar);
    $('calendarGoogleDisconnect').addEventListener('click',disconnectGoogleCalendar);
    $('calendarEventForm').addEventListener('submit',submitCalendarEvent);
    $('calendarEventRecurrence').addEventListener('change',event=>{$('calendarRecurrenceUntilLabel').hidden=event.target.value==='NONE'});
    $('calendarConfirmSave').addEventListener('click',confirmCalendarEvent);
    $('calendarConfirmCancel').addEventListener('click',async()=>{const draft=pendingCalendarDraft;$('calendarConfirmDialog').close();if(draft&&draft._mode!=='edit'){try{await api(`/v1/home-calendar/${encodeURIComponent(user)}/drafts`,{method:'DELETE'})}catch(_error){}}pendingCalendarDraft=null;if(draft&&!draft.action)openCalendarEvent({...draft,_draft:draft._mode!=='edit'})});
    $('calendarDeleteButton').addEventListener('click',deleteCalendarEvent);
    document.querySelectorAll('[data-calendar-view]').forEach(button=>button.addEventListener('click',()=>{calendarView=button.dataset.calendarView;renderCalendar()}));
    $('previousStepButton').addEventListener('click',()=>updateCooking('previous'));
    $('nextStepButton').addEventListener('click',()=>updateCooking('next'));
    $('speakStepButton').addEventListener('click',speakCurrentStep);
    $('startTimerButton').addEventListener('click',startCookingTimer);
    document.querySelectorAll('[data-tab-link]').forEach(button=>button.addEventListener('click',event=>{event.preventDefault();selectPanel(button.dataset.tabLink)}));
    document.querySelectorAll('[data-open-custom]').forEach(button=>button.addEventListener('click',()=>$('customDialog').showModal()));
    document.querySelectorAll('[data-close-dialog]').forEach(button=>button.addEventListener('click',()=>$(button.dataset.closeDialog).close()));
    $('pairDialog').addEventListener('cancel',event=>{event.preventDefault();$('pairDialog').close()});
    $('pairDialog').addEventListener('click',event=>{if(event.target===$('pairDialog'))$('pairDialog').close()});
    $('recipeSearch').addEventListener('input',event=>{recipeSearch=normalize(event.target.value);renderRecipes()});
    $('installButton').addEventListener('click',async()=>{if(installPrompt){installPrompt.prompt();await installPrompt.userChoice;installPrompt=null;$('installButton').hidden=true}});
    window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installPrompt=event;$('installButton').hidden=false});
    window.addEventListener('online',()=>load({quiet:true}));
  }

  applyAppearance();bind();renderHomeMoment();setInterval(renderHomeMoment,30000);render();
  window.addEventListener('pageshow',event=>{if(event.persisted)location.reload()});
  if('scrollRestoration'in history)history.scrollRestoration='manual';
  const initialPanels={hoy:'today',compra:'shopping',recetas:'recipes',mascotas:'pets',pets:'pets',despensa:'pantry',calendario:'calendar',renueva:'design',jardin:'plants',familia:'family',nexo:'family',family:'family',mas:'more'};
  selectPanel(initialPanels[location.hash.slice(1)]||'today',{smooth:false});const calendarSyncResult=new URLSearchParams(location.search).get('calendar_sync');if(calendarSyncResult){sessionStorage.setItem('roxyCalendarSyncNotice',calendarSyncResult);history.replaceState(null,'',`${location.pathname}${location.hash||'#calendario'}`)}load().then(()=>{const notice=sessionStorage.getItem('roxyCalendarSyncNotice');if(notice){sessionStorage.removeItem('roxyCalendarSyncNotice');announce(notice==='connected'?'Google Calendar quedó conectado. Tus próximos eventos ya se están sincronizando.':notice==='denied'?'No se autorizó Google Calendar. No hice cambios.':'No pude terminar la conexión con Google Calendar. Inténtalo de nuevo.')}});
  if('serviceWorker'in navigator&&(location.protocol==='https:'||location.hostname==='localhost')){
    const homeRoute=location.pathname.startsWith('/home');
    navigator.serviceWorker.register(homeRoute?'/home-sw.js':'/lista-sw.js',{scope:homeRoute?'/home':'/lista',updateViaCache:'none'}).then(registration=>registration.update()).catch(()=>{});
  }
  async function refreshStaleApp(){
    if(document.visibilityState==='hidden')return;
    try{
      const response=await fetch(`${location.pathname}?version-check=${Date.now()}`,{cache:'no-store',credentials:'same-origin'});
      if(!response.ok)return;
      const html=await response.text();
      const match=html.match(/name="roxy-home-version" content="([^"]+)"/);
      if(match&&match[1]!==APP_VERSION)location.reload();
    }catch(_error){}
  }
  document.addEventListener('visibilitychange',refreshStaleApp);
})();
