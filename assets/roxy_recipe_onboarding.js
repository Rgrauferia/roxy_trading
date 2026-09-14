/* Member-private culinary welcome. Uses only the supplied Home account API. */
(function (global) {
  'use strict';
  const ENDPOINT = '/v1/home-account/recipe-profile';
  const mounts = new WeakMap();
  let sequence = 0;
  const choices = {
    cuisine_mode: [['mixed', 'Un poco de todo', 'A little of everything'], ['origin', 'Sabores de mi origen', 'Flavours from my origin'], ['selected', 'Elegir mis cocinas', 'Choose my cuisines']],
    cuisines: [['mexican','Mexicana','Mexican'],['peruvian','Peruana','Peruvian'],['caribbean','Caribeña','Caribbean'],['central_american','Centroamericana','Central American'],['south_american','Sudamericana','South American'],['spanish','Española','Spanish'],['italian','Italiana','Italian'],['mediterranean','Mediterránea','Mediterranean'],['middle_eastern','Medio Oriente','Middle Eastern'],['indian','India','Indian'],['chinese','China','Chinese'],['japanese','Japonesa','Japanese'],['korean','Coreana','Korean'],['thai','Tailandesa','Thai'],['american','Estadounidense','American'],['other','Otras cocinas','Other cuisines']],
    diet: [['omnivore','Sin dieta específica','No specific diet'],['vegetarian','Vegetariana','Vegetarian'],['vegan','Vegana','Vegan'],['pescatarian','Pescetariana','Pescatarian'],['undisclosed','Prefiero no indicarlo','Prefer not to say']],
    favorite_foods: [['rice','Arroz','Rice'],['pasta','Pasta','Pasta'],['legumes','Legumbres','Legumes'],['vegetables','Verduras','Vegetables'],['chicken','Pollo','Chicken'],['meat','Carne','Meat'],['fish','Pescado','Fish'],['seafood','Mariscos','Seafood'],['eggs','Huevos','Eggs'],['soups','Sopas','Soups'],['salads','Ensaladas','Salads'],['desserts','Postres','Desserts']],
    allergy_status: [['none','No tengo alergias alimentarias conocidas','No known food allergies'],['listed','Quiero indicar mis alergias','I want to list my allergies'],['undisclosed','Prefiero no indicarlo','Prefer not to say']],
    allergies: [['milk','Leche','Milk'],['eggs','Huevo','Eggs'],['fish','Pescado','Fish'],['shellfish','Mariscos','Shellfish'],['tree_nuts','Frutos secos','Tree nuts'],['peanuts','Cacahuate / maní','Peanuts'],['wheat','Trigo','Wheat'],['soy','Soja','Soy'],['sesame','Sésamo','Sesame'],['other','Otra alergia','Other allergy']],
    skill: [['beginner','Estoy empezando','Just getting started'],['intermediate','Me manejo en la cocina','Comfortable in the kitchen'],['confident','Cocino con confianza','Confident cook'],['undisclosed','Prefiero no indicarlo','Prefer not to say']],
  };
  const copy = {
    es: {
      eyebrow:'ROXY · TU COCINA', title:'Una cocina que se parece a ti', editTitle:'Afinemos tus gustos', badge:'4 pasos, a tu ritmo', steps:['Tus sabores','Tus gustos','Tu ritmo','Tu ficha'],
      hello:'Hola', narrations:['Me encantará conocerte un poco. Elige el idioma y los sabores que te apetece encontrar. Tu origen no decide tus gustos.', 'Cuéntame qué disfrutas y qué necesitas evitar. Puedes reservarte lo que prefieras.', 'Hay días para algo rápido y otros para cocinar con calma. Empecemos por lo que te resulta cómodo.', 'Así quedarán tus preferencias. Revísalas antes de guardar; podrás volver a cambiarlas desde Recetas.'],
      language:'¿En qué idioma prefieres las recetas?', languageHint:'Esta preferencia es para Recetas. Cada ficha conserva el idioma disponible de su fuente.', country:'País de origen (opcional)', countryHint:'Puedes indicar un país o región, o dejarlo vacío si prefieres no indicarlo.', countryPlaceholder:'Por ejemplo, Perú o el Caribe', cuisines:'¿Qué te gustaría explorar?', selectedCuisines:'Elige una o varias cocinas',
      diet:'¿Cómo te gusta comer?', favorites:'¿Qué te gusta especialmente?', favoritesHint:'Opcional. Puedes elegir varios o dejarlo para después.', dislikes:'Ingredientes que prefieres evitar', dislikesHint:'Opcional: separados por comas, hasta 20. Usa el apartado de alergias para una alergia.', dislikesPlaceholder:'Por ejemplo, cilantro, aceitunas',
      allergy:'¿Hay alergias alimentarias que deba tener en cuenta?', allergyHint:'Indicarlo es opcional. «Prefiero no indicarlo» deja esta información desconocida.', allergens:'Selecciona tus alergias', otherAllergies:'Otra alergia alimentaria', allergyNote:'Las preferencias no certifican que una receta sea apta. Revisa ingredientes, etiquetas y contaminación cruzada antes de cocinar.',
      time:'¿Cuánto tiempo sueles tener?', timeHint:'Límite orientativo para buscar recetas. Cuando la fuente no indique duración, lo verás.', timePlaceholder:'Sin límite / prefiero no indicar', minutes:'minutos', skill:'¿Cómo te sientes en la cocina?',
      review:'Tu punto de partida', preview:'Esto ayudará a ordenar las recetas disponibles según tus elecciones. Podrás explorar el catálogo completo y ajustar los filtros.', summary:'Tu cocina va tomando forma', empty:'Elige lo que te representa. Puedes cambiar de idea en cualquier paso.', unknown:'Sin indicar', anyTime:'Sin límite indicado', noFavorites:'Abierto a descubrir', noDislikes:'Sin preferencias indicadas',
      consent:'Quiero guardar estas preferencias, incluidas las alergias que decida indicar, en mi perfil privado de Roxy Home para personalizar Recetas.', privacy:'Puedes modificarlas desde Recetas → Mis gustos. No se añaden productos a Compra al guardar.', privacyLink:'Privacidad', next:'Continuar', back:'Atrás', save:'Guardar y descubrir recetas', saveEdit:'Guardar cambios', cancel:'Cancelar', saving:'Guardando…', saved:'Preferencias guardadas.',
      langError:'Elige español o inglés para continuar.', modeError:'Elige cómo quieres explorar las cocinas.', originError:'Indica tu país o región, o elige otra forma de explorar.', cuisineError:'Elige al menos una cocina.', dietError:'Elige una dieta o «Prefiero no indicarlo».', allergyError:'Elige cómo prefieres responder sobre alergias.', listError:'Selecciona al menos una alergia.', otherError:'Escribe la otra alergia que quieres guardar.', dislikesError:'Indica hasta 20 ingredientes, de 60 caracteres como máximo cada uno.', timeError:'Indica entre 5 y 240 minutos, o deja el campo vacío.', skillError:'Elige tu experiencia o «Prefiero no indicarlo».', consentError:'Confirma que quieres guardar estas preferencias.',
      saveError:'No pude confirmar el guardado. Tus respuestas siguen aquí. Puedes comprobar la versión guardada antes de reintentar.', conflict:'El perfil cambió en otra sesión. Carga la versión guardada para revisarla antes de guardar de nuevo.', reload:'Descartar cambios y cargar el perfil guardado', loading:'Comprobando perfil…', loadError:'No pude cargar el perfil guardado. Conservamos tus respuestas.', stale:'Tu sesión cambió. Vuelve a abrir tus preferencias desde tu cuenta.',
      listen:'Escuchar a Roxy', stop:'Detener voz', voiceHint:'Guía con la voz oficial de Roxy · en español', voiceUnavailable:'Puedes seguir leyendo; la voz oficial no está disponible ahora.', voiceError:'No se pudo reproducir la voz. Puedes continuar leyendo.',
    },
    en: {
      eyebrow:'ROXY · YOUR KITCHEN', title:'A kitchen that feels like you', editTitle:'Let’s refine your tastes', badge:'4 steps, at your pace', steps:['Your flavours','Your tastes','Your rhythm','Your profile'],
      hello:'Hello', narrations:['I’d love to get to know you a little. Choose the language and flavours you’d like to find. Your origin doesn’t decide your tastes.', 'Tell me what you enjoy and what you need to avoid. You can keep anything you prefer private.', 'Some days call for a quick meal; others leave time to cook. Let’s start with what feels comfortable.', 'Here are your preferences. Review them before saving; you can change them later from Recipes.'],
      language:'Which language do you prefer for recipes?', languageHint:'This preference is for Recipes. Each recipe keeps its source’s available language.', country:'Country of origin (optional)', countryHint:'You can enter a country or region, or leave blank if you prefer not to say.', countryPlaceholder:'For example, Peru or the Caribbean', cuisines:'What would you like to explore?', selectedCuisines:'Choose one or more cuisines',
      diet:'How do you like to eat?', favorites:'What do you especially enjoy?', favoritesHint:'Optional. Choose several or leave it for later.', dislikes:'Ingredients you prefer to avoid', dislikesHint:'Optional: separate with commas, up to 20. Use the allergy section for allergies.', dislikesPlaceholder:'For example, cilantro, olives',
      allergy:'Any food allergies you’d like me to consider?', allergyHint:'Sharing is optional. “Prefer not to say” keeps this information unknown.', allergens:'Select your allergies', otherAllergies:'Other food allergy', allergyNote:'Preferences do not certify a recipe as suitable. Check ingredients, labels and cross-contact before cooking.',
      time:'How much time do you usually have?', timeHint:'A guide for finding recipes. You’ll see when a source has no cooking time.', timePlaceholder:'No limit / prefer not to say', minutes:'minutes', skill:'How do you feel in the kitchen?',
      review:'Your starting point', preview:'This will help order available recipes based on your choices. You can explore the full catalogue and adjust filters.', summary:'Your kitchen is taking shape', empty:'Choose what feels like you. You can change your mind at any step.', unknown:'Not shared', anyTime:'No time limit shared', noFavorites:'Open to discovery', noDislikes:'No preferences shared',
      consent:'I want to save these preferences, including any allergies I choose to share, in my private Roxy Home profile to personalise Recipes.', privacy:'You can edit them in Recipes → My tastes. Saving does not add products to Shopping.', privacyLink:'Privacy', next:'Continue', back:'Back', save:'Save and discover recipes', saveEdit:'Save changes', cancel:'Cancel', saving:'Saving…', saved:'Preferences saved.',
      langError:'Choose Spanish or English to continue.', modeError:'Choose how you want to explore cuisines.', originError:'Enter your country or region, or choose another way to explore.', cuisineError:'Choose at least one cuisine.', dietError:'Choose a diet or “Prefer not to say”.', allergyError:'Choose how you would like to answer about allergies.', listError:'Select at least one allergy.', otherError:'Enter the other allergy you want to save.', dislikesError:'Enter up to 20 ingredients, each with no more than 60 characters.', timeError:'Enter between 5 and 240 minutes, or leave blank.', skillError:'Choose your experience or “Prefer not to say”.', consentError:'Confirm that you want to save these preferences.',
      saveError:'I couldn’t confirm the save. Your answers are still here. You can check the saved version before trying again.', conflict:'This profile changed in another session. Load the saved version to review it before saving again.', reload:'Discard changes and load the saved profile', loading:'Checking profile…', loadError:'I couldn’t load the saved profile. Your answers are still here.', stale:'Your session changed. Reopen your preferences from your account.',
      listen:'Listen to Roxy', stop:'Stop voice', voiceHint:'Official Roxy guide · spoken in Spanish', voiceUnavailable:'You can keep reading; the official voice is unavailable right now.', voiceError:'Voice could not play. You can continue reading.',
    },
  };
  const text = value => typeof value === 'string' ? value.trim() : '';
  const list = value => Array.isArray(value) ? [...value] : [];
  const allowed = (key, value) => choices[key].some(row => row[0] === value);
  function createModel(envelope = {}) {
    const p = envelope.profile || {};
    return {step:0, revision:envelope.revision, memberId:text(envelope.member_id), editing:Boolean(p.completed), consent:false, values:{
      language:['es','en'].includes(p.language) ? p.language : '', country_of_origin:text(p.country_of_origin),
      cuisine_mode:allowed('cuisine_mode', p.cuisine_mode) ? p.cuisine_mode : '', cuisines:list(p.cuisines),
      diet:allowed('diet', p.diet) ? p.diet : '', favorite_foods:list(p.favorite_foods), dislikes:list(p.dislikes).join(', '),
      allergy_status:allowed('allergy_status', p.allergy_status) ? p.allergy_status : '', allergies:list(p.allergies), other_allergies:text(p.other_allergies),
      max_minutes:p.max_minutes == null ? '' : String(p.max_minutes), skill:allowed('skill', p.skill) ? p.skill : '',
    }};
  }
  function validate(model, step = model.step) {
    const v = model.values;
    if (step === 0) {
      if (!['es','en'].includes(v.language)) return 'langError';
      if (!allowed('cuisine_mode', v.cuisine_mode)) return 'modeError';
      if (v.cuisine_mode === 'origin' && !text(v.country_of_origin)) return 'originError';
      if (v.cuisine_mode === 'selected' && !v.cuisines.length) return 'cuisineError';
    }
    if (step === 1) {
      if (!allowed('diet', v.diet)) return 'dietError';
      if (!allowed('allergy_status', v.allergy_status)) return 'allergyError';
      if (v.allergy_status === 'listed' && !v.allergies.length) return 'listError';
      if (v.allergy_status === 'listed' && v.allergies.includes('other') && !text(v.other_allergies)) return 'otherError';
      const avoided = v.dislikes.split(',').map(text).filter(Boolean);
      if (avoided.length > 20 || avoided.some(item => item.length > 60)) return 'dislikesError';
    }
    if (step === 2) {
      if (v.max_minutes !== '' && (!/^\d+$/.test(v.max_minutes) || Number(v.max_minutes) < 5 || Number(v.max_minutes) > 240)) return 'timeError';
      if (!allowed('skill', v.skill)) return 'skillError';
    }
    if (step === 3 && !model.consent) return 'consentError';
    return '';
  }
  function payload(model) {
    const v = model.values, disclosed = v.allergy_status === 'listed';
    return {member_id:model.memberId, expected_revision:model.revision, profile:{
      schema_version:1, completed:true, consent:true, language:v.language, country_of_origin:text(v.country_of_origin),
      cuisine_mode:v.cuisine_mode, cuisines:v.cuisine_mode === 'selected' ? [...v.cuisines] : [],
      diet:v.diet, favorite_foods:[...v.favorite_foods], dislikes:[...new Set(v.dislikes.split(',').map(text).filter(Boolean))],
      allergy_status:v.allergy_status, allergies:disclosed ? [...v.allergies] : [], other_allergies:disclosed && v.allergies.includes('other') ? text(v.other_allergies) : '',
      max_minutes:v.max_minutes === '' ? null : Number(v.max_minutes), skill:v.skill,
    }};
  }
  function render(container, options = {}) {
    mounts.get(container)?.dispose();
    const envelope = options.profile || {}, doc = container.ownerDocument || global.document;
    let model = createModel(envelope), disposed = false, request = null, speech = null;
    const id = `recipe-onboarding-${++sequence}`, initialIdentity = options.identity;
    const owned = [], el = (tag, cls, value) => { const node = doc.createElement(tag); if (cls) node.className = cls; if (value != null) node.textContent = value; return node; };
    const on = (node, event, fn) => { node.addEventListener(event, fn); owned.push(() => node.removeEventListener(event, fn)); };
    const isCurrent = () => !disposed && options.identity === initialIdentity && container.isConnected !== false && !container.closest?.('[hidden]') && (typeof options.isCurrent !== 'function' || options.isCurrent());
    const tr = () => copy[model.values.language === 'en' ? 'en' : 'es'];
    const label = (key, value) => choices[key].find(row => row[0] === value)?.[model.values.language === 'en' ? 2 : 1] || tr().unknown;
    const button = (value, cls, fn) => { const node = el('button', cls, value); node.type = 'button'; node.addEventListener('click', () => { if (isCurrent() && !node.disabled) fn(); }); return node; };
    const shell = el('section', 'recipe-onboarding'); shell.setAttribute('aria-labelledby', `${id}-title`);
    container.replaceChildren(shell);
    let content, errorBox, footer, next, reload, voiceButton, voiceStatus, voiceArea, narrationNode, overview, stepHeading;
    function stopSpeech() {
      if (speech) global.RoxyHomeTour?.stop();
      speech = null;
      if (voiceButton) voiceButton.textContent = tr().listen;
    }
    function speak() {
      if (speech && global.RoxyHomeTour?.isPlaying()) { stopSpeech(); return; }
      if (!global.RoxyHomeTour) { voiceStatus.textContent = tr().voiceUnavailable; return; }
      speech = true;
      void global.RoxyHomeTour.speak(`recipe-${model.step}`, (state, message) => {
        if (!isCurrent()) return;
        speech = ['loading','playing','ready'].includes(state);
        voiceStatus.textContent = message;
        voiceButton.textContent = speech ? tr().stop : tr().listen;
      }, voiceArea);
    }
    function showError(key) { errorBox.hidden = false; errorBox.textContent = tr()[key]; errorBox.focus?.(); }
    function clearError() { errorBox.hidden = true; errorBox.textContent = ''; }
    function summaryRows() {
      const v = model.values, t = tr();
      const rows = [[t.language, v.language === 'en' ? 'English' : v.language === 'es' ? 'Español' : t.unknown]];
      if (v.country_of_origin) rows.push([t.country, v.country_of_origin]);
      rows.push([t.cuisines, v.cuisine_mode === 'selected' ? v.cuisines.map(item => label('cuisines', item)).join(', ') || t.unknown : label('cuisine_mode', v.cuisine_mode)]);
      rows.push([t.diet, label('diet', v.diet)], [t.favorites, v.favorite_foods.map(item => label('favorite_foods', item)).join(', ') || t.noFavorites]);
      rows.push([t.allergy, v.allergy_status === 'listed' ? v.allergies.map(item => item === 'other' ? v.other_allergies || label('allergies', item) : label('allergies', item)).join(', ') || t.unknown : label('allergy_status', v.allergy_status)]);
      rows.push([t.dislikes, v.dislikes || t.noDislikes], [t.time, v.max_minutes ? `${v.max_minutes} ${t.minutes}` : t.anyTime], [t.skill, label('skill', v.skill)]);
      return rows;
    }
    function refreshOverview() {
      overview.replaceChildren(el('span','rco-eyebrow',tr().summary));
      const v = model.values, selected = [];
      if (v.language) selected.push(v.language === 'es' ? 'Español' : 'English');
      if (v.cuisine_mode) selected.push(v.cuisine_mode === 'selected' ? v.cuisines.map(item => label('cuisines',item)).join(' · ') : label('cuisine_mode',v.cuisine_mode));
      if (v.diet) selected.push(label('diet',v.diet));
      if (v.max_minutes) selected.push(`${v.max_minutes} ${tr().minutes}`);
      overview.append(el('p','',selected.filter(Boolean).join(' · ') || tr().empty));
    }
    function field(key, title, hint = '', type = 'text', maxLength = 64) {
      const wrapper = el('label','rco-field'), control = el('input'); control.type = type; control.name = key; control.id = `${id}-${key}`; control.value = model.values[key]; control.maxLength = maxLength;
      if (type === 'number') { control.min = '5'; control.max = '240'; control.step = '1'; control.inputMode = 'numeric'; }
      wrapper.append(el('span','',title), control);
      if (hint) { const help = el('small','',hint); help.id = `${control.id}-hint`; control.setAttribute('aria-describedby',help.id); wrapper.append(help); }
      control.addEventListener('input', () => { if (!isCurrent() || request) return; model.values[key] = control.value; model.consent = false; clearError(); refreshOverview(); });
      return {wrapper, control};
    }
    function group(key, legend, multi = false, dependent = false) {
      const groupNode = el('fieldset', `rco-choices${multi ? ' rco-chips' : ''}`); groupNode.append(el('legend','',legend));
      const rows = key === 'language' ? [['es','Español','Español'],['en','English','English']] : choices[key];
      rows.forEach(row => {
        const option = el('label','rco-choice'), input = el('input'); input.type = multi ? 'checkbox' : 'radio'; input.name = `${id}-${key}`; input.value = row[0]; input.id = `${id}-${key}-${row[0]}`; input.checked = multi ? model.values[key].includes(row[0]) : model.values[key] === row[0];
        input.addEventListener('change', () => {
          if (!isCurrent() || request) return;
          if (multi) model.values[key] = input.checked ? [...new Set([...model.values[key],row[0]])] : model.values[key].filter(value => value !== row[0]);
          else { if (!input.checked) return; model.values[key] = row[0]; }
          model.consent = false; clearError();
          if (dependent || key === 'language') paint(input.id); else refreshOverview();
        });
        option.append(input, el('span','',row[model.values.language === 'en' ? 2 : 1])); groupNode.append(option);
      }); return groupNode;
    }
    function updateBusy() {
      shell.setAttribute('aria-busy', request ? 'true' : 'false');
      content.querySelectorAll?.('input, button').forEach(node => { node.disabled = Boolean(request); });
      footer.querySelectorAll?.('button').forEach(node => { node.disabled = Boolean(request); });
      if (voiceButton) voiceButton.disabled = Boolean(request) || !global.RoxyHomeTour;
      next.textContent = request ? request.method === 'GET' ? tr().loading : tr().saving : model.step === 3 ? model.editing ? tr().saveEdit : tr().save : tr().next;
    }
    function validEnvelope(value, saving) {
      return value && value.member_id === model.memberId && Number.isInteger(value.revision) && value.revision >= (saving ? model.revision + 1 : 0) && (!saving || value.profile?.completed === true);
    }
    async function perform(method) {
      if (!isCurrent() || request) return;
      if (!model.memberId || !Number.isInteger(model.revision) || typeof options.api !== 'function') { showError('stale'); return; }
      if (method === 'PUT') {
        for (let step = 0; step < 4; step++) { const problem = validate(model,step); if (problem) { model.step = step; paint(); showError(problem); return; } }
      }
      stopSpeech(); clearError(); reload.hidden = true;
      const operation = {method,controller:new AbortController(),timer:null}; request = operation; updateBusy();
      let rejectTimeout;
      const deadline = new Promise((_, reject) => { rejectTimeout = reject; operation.timer = setTimeout(() => { operation.controller.abort(); const error = new Error('timeout'); error.name = 'TimeoutError'; reject(error); }, 12000); });
      operation.cancel = () => { operation.controller.abort(); const error = new Error('aborted'); error.name = 'AbortError'; rejectTimeout(error); };
      try {
        const result = await Promise.race([Promise.resolve().then(() => {
          if (!isCurrent() || operation.controller.signal.aborted) { const error = new Error('aborted'); error.name = 'AbortError'; throw error; }
          return options.api(ENDPOINT, {method, signal:operation.controller.signal, ...(method === 'PUT' ? {body:JSON.stringify(payload(model))} : {})});
        }),deadline]);
        if (!isCurrent() || request !== operation) return;
        if (!validEnvelope(result,method === 'PUT')) { showError('stale'); return; }
        if (method === 'GET') { model = createModel(result); request = null; paint(); }
        else { model.revision = result.revision; dispose(); if (typeof options.onSaved === 'function') options.onSaved(result); }
      } catch (error) {
        if (!isCurrent() || request !== operation) return;
        showError(method === 'GET' ? 'loadError' : Number(error?.status || error?.statusCode) === 409 ? 'conflict' : 'saveError'); reload.hidden = false;
      } finally { clearTimeout(operation.timer); if (request === operation) request = null; if (!disposed) updateBusy(); }
    }
    function paint(focusId) {
      stopSpeech(); shell.replaceChildren(); shell.lang = model.values.language || 'es';
      const t = tr(), header = el('header','rco-header'), heading = el('div');
      heading.append(el('p','rco-eyebrow',t.eyebrow)); const title = el('h2','',model.editing ? t.editTitle : t.title); title.id = `${id}-title`; heading.append(title,el('p','rco-badge',t.badge)); header.append(heading);
      if (!options.required) header.append(button(t.cancel,'rco-cancel',() => { if (request) return; dispose(); options.onCancel?.(); })); shell.append(header);
      const progress = el('ol','rco-progress'); progress.setAttribute('aria-label',t.badge);
      t.steps.forEach((value,index) => { const item = el('li'); if (index === model.step) item.setAttribute('aria-current','step'); if (index < model.step) item.setAttribute('data-complete','true'); item.append(el('span','rco-number',String(index+1)),el('span','',value)); progress.append(item); }); shell.append(progress);
      const companion = el('div','rco-companion'), avatar = el('img','rco-avatar'); avatar.src = '/assets/roxy_home_avatar.jpg'; avatar.alt = ''; avatar.width = 104; avatar.height = 104; avatar.decoding = 'async'; avatar.addEventListener('error',() => { avatar.hidden = true; });
      const speechArea = el('div','rco-speech-area'); speechArea.append(el('strong','', 'Roxy'));
      narrationNode = el('p','rco-narration',`${model.step === 0 ? `${t.hello}${text(options.displayName) ? `, ${text(options.displayName).slice(0,60)}` : ''}. ` : ''}${t.narrations[model.step]}`); narrationNode.setAttribute('aria-live','polite'); speechArea.append(narrationNode);
      voiceArea = el('div','rco-voice-area'); voiceButton = button(t.listen,'rco-voice',speak); voiceStatus = el('small','',t.voiceHint); voiceStatus.setAttribute('role','status'); voiceArea.append(voiceButton,voiceStatus); speechArea.append(voiceArea); companion.append(avatar,speechArea); shell.append(companion);
      overview = el('aside','rco-overview'); overview.setAttribute('aria-live','polite'); overview.setAttribute('aria-atomic','true'); shell.append(overview); refreshOverview();
      content = el('div','rco-content'); stepHeading = el('h3','',model.step === 3 ? t.review : t.steps[model.step]); stepHeading.tabIndex = -1; content.append(stepHeading); shell.append(content);
      if (model.step === 0) {
        content.append(group('language',t.language),el('p','rco-hint',t.languageHint));
        const country = field('country_of_origin',t.country,t.countryHint); country.control.placeholder = t.countryPlaceholder; content.append(country.wrapper,group('cuisine_mode',t.cuisines,false,true));
        if (model.values.cuisine_mode === 'selected') content.append(group('cuisines',t.selectedCuisines,true));
      } else if (model.step === 1) {
        content.append(group('diet',t.diet),group('favorite_foods',t.favorites,true),el('p','rco-hint',t.favoritesHint));
        const dislikes = field('dislikes',t.dislikes,t.dislikesHint,'text',1219); dislikes.control.placeholder = t.dislikesPlaceholder; content.append(dislikes.wrapper,group('allergy_status',t.allergy,false,true),el('p','rco-hint',t.allergyHint));
        if (model.values.allergy_status === 'listed') { content.append(group('allergies',t.allergens,true,true)); if (model.values.allergies.includes('other')) content.append(field('other_allergies',t.otherAllergies,'','text',200).wrapper); }
        content.append(el('p','rco-note',t.allergyNote));
      } else if (model.step === 2) {
        const time = field('max_minutes',t.time,t.timeHint,'number'); time.control.placeholder = t.timePlaceholder; content.append(time.wrapper,group('skill',t.skill));
      } else {
        content.append(el('p','rco-preview',t.preview)); const facts = el('dl','rco-summary');
        summaryRows().forEach(([key,value]) => { const row = el('div'); row.append(el('dt','',key),el('dd','',value)); facts.append(row); }); content.append(facts,el('p','rco-note',t.allergyNote));
        const consent = el('label','rco-consent'), check = el('input'); check.type = 'checkbox'; check.id = `${id}-consent`; check.name = 'consent'; check.checked = model.consent;
        check.addEventListener('change',() => { if (isCurrent() && !request) { model.consent = check.checked; clearError(); } }); consent.append(check,el('span','',t.consent)); content.append(consent);
      }
      errorBox = el('p','rco-error'); errorBox.setAttribute('role','alert'); errorBox.tabIndex = -1; errorBox.hidden = true; shell.append(errorBox);
      reload = button(t.reload,'rco-reload',() => perform('GET')); reload.hidden = true; shell.append(reload);
      footer = el('footer','rco-footer');
      if (model.step > 0) footer.append(button(t.back,'rco-secondary',() => { if (!request) { model.step--; paint(); } }));
      next = button(model.step === 3 ? t.save : t.next,'rco-primary',() => { if (request) return; const problem = validate(model); if (problem) { showError(problem); return; } if (model.step === 3) { perform('PUT'); return; } model.step++; paint(); }); footer.append(next); shell.append(footer);
      const privacy = el('p','rco-privacy',t.privacy + ' '), link = el('a','',t.privacyLink); link.href = '/privacy'; link.target = '_blank'; link.rel = 'noopener'; privacy.append(link); shell.append(privacy); updateBusy();
      if (focusId) { const target = [...shell.querySelectorAll('input')].find(node => node.id === focusId); target?.focus(); }
      else if (model.step > 0) stepHeading.focus?.();
    }
    function checkScope() { if (!isCurrent()) dispose(); }
    function onVisibility() { stopSpeech(); if (doc.hidden && request) request.cancel(); checkScope(); }
    function dispose() {
      if (disposed) return; disposed = true; stopSpeech();
      if (request) { clearTimeout(request.timer); request.cancel(); request = null; }
      observer?.disconnect(); owned.splice(0).forEach(remove => remove()); shell.remove(); if (mounts.get(container) === controller) mounts.delete(container);
      model = null;
    }
    const observer = global.MutationObserver ? new global.MutationObserver(checkScope) : null;
    const controller = {dispose}; mounts.set(container,controller);
    if (!isCurrent()) { dispose(); return controller; }
    paint(); on(doc,'visibilitychange',onVisibility); on(global,'pagehide',dispose);
    observer?.observe(doc.documentElement || doc.body, {childList:true,subtree:true,attributes:true,attributeFilter:['hidden']});
    return controller;
  }
  global.RoxyRecipeOnboarding = Object.freeze({render});
})(window);
