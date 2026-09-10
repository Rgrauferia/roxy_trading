/* Roxy Home: a local, explicit plant setup conversation. No AI/provider calls. */
(function (global) {
  'use strict';
  const choices = Object.freeze({
    placement: [['indoor', 'Dentro de casa'], ['outdoor', 'Al aire libre']],
    light_exposure: [['unknown', 'Todavía no lo sé'], ['low', 'Poca luz'], ['indirect', 'Luz sin sol directo'], ['bright_indirect', 'Mucha luz, sin sol directo'], ['direct_morning', 'Sol de mañana'], ['direct_afternoon', 'Sol de tarde']],
    growing_medium: [['unknown', 'Necesito comprobarlo'], ['soil', 'Tierra o sustrato'], ['water', 'Agua']],
    pot_type: [['unknown', 'No lo sé / otro'], ['plastic', 'Plástico'], ['terracotta', 'Terracota'], ['ceramic', 'Cerámica']],
  });
  const clean = (value, max = 800) => typeof value === 'string' ? value.trim().slice(0, max) : '';
  const allowed = (key, value, fallback) => choices[key].some(row => row[0] === value) ? value : fallback;
  const label = (key, value) => choices[key].find(row => row[0] === value)?.[1] || 'Por confirmar';
  const normalizeSpecies = rows => {
    const seen = new Set();
    const result = [];
    (Array.isArray(rows) ? rows : []).forEach(row => {
      if (!row || !/^[a-z][a-z0-9_]{0,39}$/.test(row.key || '') || seen.has(row.key)) return;
      seen.add(row.key);
      result.push({ key: row.key, common_name: clean(row.common_name, 100) || 'Especie por confirmar', scientific_name: clean(row.scientific_name, 100), light: clean(row.light), soil_rule: clean(row.soil_rule), toxicity: clean(row.toxicity), fertilizer: clean(row.fertilizer) });
    });
    if (!seen.has('unknown')) result.unshift({ key: 'unknown', common_name: 'Todavía no conozco la especie', scientific_name: '' });
    return result;
  };
  function createModel(options = {}) {
    const plant = options.plant && typeof options.plant === 'object' ? options.plant : null;
    const species = normalizeSpecies(options.species);
    const initialKey = species.some(row => row.key === plant?.species_key) ? plant.species_key : 'unknown';
    // The supplied existing profile may contain richer care text than the picker.
    if (plant && initialKey !== 'unknown') {
      const entry = species.find(row => row.key === initialKey);
      ['light', 'soil_rule', 'toxicity', 'fertilizer'].forEach(key => { if (!entry[key]) entry[key] = clean(plant[key]); });
    }
    return {
      step: 0, editing: Boolean(plant?.id), originalSpeciesKey: initialKey,
      originalIdentificationStatus: clean(plant?.identification?.status, 30),
      memberName: clean(options.memberName, 60), species,
      values: {
        display_name: clean(plant?.display_name, 60), species_key: initialKey,
        room: clean(plant?.room, 60), placement: allowed('placement', plant?.placement, 'indoor'),
        light_exposure: allowed('light_exposure', plant?.light_exposure, 'unknown'),
        growing_medium: allowed('growing_medium', plant?.growing_medium, 'unknown'),
        pot_type: allowed('pot_type', plant?.pot_type, 'unknown'),
        drainage: typeof plant?.drainage === 'boolean' ? plant.drainage : null,
        notes: clean(plant?.notes), photo_data_url: '',
      },
    };
  }
  function selectedProfile(model) { return model.species.find(row => row.key === model.values.species_key) || model.species.find(row => row.key === 'unknown'); }
  function confirmedSpecies(model) { return model.values.species_key !== 'unknown' && (!model.editing || model.originalIdentificationStatus === 'CONFIRMED'); }
  function plantName(model) { return clean(model.values.display_name, 60) || (model.values.species_key !== 'unknown' ? selectedProfile(model).common_name : 'tu planta'); }
  function narration(model) {
    const profile = selectedProfile(model);
    const name = plantName(model);
    if (model.step === 0) {
      const greeting = `Hola${model.memberName ? `, ${model.memberName}` : ''}.`;
      if (!confirmedSpecies(model)) return `${greeting} ${model.editing ? 'Vamos a completar la ficha de' : 'Vamos a conocer a'} ${name}. No necesitas saber de plantas: iremos paso a paso. Si no conoces la especie, podemos dejarla pendiente; no voy a inventarla por su nombre o su foto.`;
      return `${greeting} ${model.editing ? 'Vamos a revisar cómo vive' : 'Estás añadiendo'} ${profile.common_name}${model.editing ? '.' : ' a tu casa.'} Primero confirmamos su identidad. Después miramos su lugar y sus raíces para preparar una ficha que te sirva de verdad.`;
    }
    if (model.step === 1) return `Ahora pensemos en el lugar de ${name}. ${confirmedSpecies(model) && profile.light ? `Su ficha indica: ${profile.light}. ` : 'La luz recomendada depende de confirmar la especie. '}No pasa nada si aún no sabes cuánta luz recibe. Elige lo que observas; el tiempo exterior no mide la temperatura dentro de tu casa.`;
    if (model.step === 2) {
      if (model.values.growing_medium === 'water') return `${name} está en agua, según me indicas. No le aplicaré una instrucción de regar tierra ni un aviso de agujeros de drenaje. Para concretar sus cuidados, importa saber si es un esqueje enraizando o un cultivo permanente.`;
      if (model.values.growing_medium === 'soil') return `Para cuidar a ${name}, primero comprobamos la tierra y cómo sale el agua. Drenaje significa una salida para el exceso de agua; no necesitas regar ahora para responder. Si no puedes comprobarlo, marca que todavía no lo sabes.`;
      return `Una pregunta importante: ¿las raíces de ${name} están en tierra o sustrato, o directamente en agua? Cambia su cuidado. Si no puedes comprobarlo ahora, lo dejaremos pendiente sin adivinar.`;
    }
    return `Esta es la ficha que vamos a guardar para ${name}. Revisa lo que sabemos y lo que falta confirmar. Después podrás registrar tus observaciones y elegir recordatorios en su ficha. No se ha guardado nada todavía.`;
  }
  function summary(model) {
    const v = model.values, p = selectedProfile(model);
    const facts = [['Nombre en casa', plantName(model)], ['Especie', v.species_key === 'unknown' ? 'Por identificar' : `${confirmedSpecies(model) ? '' : 'Propuesta sin confirmar: '}${p.common_name}${p.scientific_name ? ` · ${p.scientific_name}` : ''}`], ['Su lugar', `${v.room || 'Zona por confirmar'} · ${label('placement', v.placement)}`], ['Luz que observas', label('light_exposure', v.light_exposure)], ['Sus raíces están en', label('growing_medium', v.growing_medium)]];
    if (v.growing_medium === 'soil') facts.push(['Drenaje', v.drainage === true ? 'Confirmaste que sí' : v.drainage === false ? 'Confirmaste que no' : 'Por comprobar']);
    const pending = [];
    if (!confirmedSpecies(model)) pending.push('Confirmar la especie antes de ofrecer cuidados específicos.');
    if (!v.room) pending.push('Anotar la habitación o zona donde vive.');
    if (v.light_exposure === 'unknown') pending.push('Observar qué luz recibe durante el día.');
    if (v.growing_medium === 'unknown') pending.push('Comprobar si las raíces están en tierra/sustrato o en agua.');
    if (v.growing_medium === 'soil' && v.drainage === null) pending.push('Comprobar cómo sale el exceso de agua del recipiente.');
    if (v.growing_medium === 'water') pending.push('Confirmar si es un esqueje o un cultivo permanente antes de elegir nutrientes.');
    const care = [];
    if (confirmedSpecies(model) && p.light) care.push(['Luz indicada en su ficha', p.light]);
    if (confirmedSpecies(model) && v.growing_medium === 'soil' && p.soil_rule) care.push(['Antes de regar', p.soil_rule]);
    if (v.growing_medium === 'water') care.push(['Observación inicial', 'Observa agua, raíces y hojas. Necesitamos una guía de cultivo en agua para esta especie; no trasladamos una pauta de tierra.']);
    if (v.growing_medium === 'soil' && v.drainage === false) care.push(['Antes del próximo riego', 'Confirmaste que no tiene drenaje. Revisa cómo puede salir el exceso de agua antes de volver a regar.']);
    if (confirmedSpecies(model) && p.toxicity) care.push(['Si hay mascotas en casa', p.toxicity]);
    return { facts, pending, care };
  }
  function payload(model) {
    const v = model.values;
    const result = {
      display_name: clean(v.display_name, 60) || (v.species_key !== 'unknown' ? selectedProfile(model).common_name : 'Mi planta'),
      species_key: model.species.some(row => row.key === v.species_key) ? v.species_key : 'unknown',
      room: clean(v.room, 60), placement: allowed('placement', v.placement, 'indoor'),
      light_exposure: allowed('light_exposure', v.light_exposure, 'unknown'),
      growing_medium: allowed('growing_medium', v.growing_medium, 'unknown'),
      pot_type: allowed('pot_type', v.pot_type, 'unknown'),
      drainage: typeof v.drainage === 'boolean' ? v.drainage : null, notes: clean(v.notes),
    };
    if (v.photo_data_url) result.photo_data_url = v.photo_data_url;
    // Updating conditions must not silently confirm an existing visual proposal.
    if (model.editing && result.species_key === model.originalSpeciesKey) delete result.species_key;
    return result;
  }
  function validate(model, step = model.step) {
    if (step === 0 && !model.editing && !/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=\s]+$/.test(model.values.photo_data_url)) return 'Añade una foto actual en JPEG, PNG o WebP para reconocer esta planta en tu jardín.';
    return '';
  }
  let active = null, counter = 0;
  function open(options = {}) {
    if (typeof options.onSave !== 'function') throw new TypeError('La guía necesita un guardado explícito.');
    if (active) { if (active.isSaving()) return active; active.close(); }
    const doc = global.document, model = createModel(options), id = `rg-guide-${++counter}`;
    const previousFocus = doc.activeElement;
    let closed = false, saving = false, photoPending = false, photoRevision = 0, utterance = null;
    let speechText = '', speechButton, speechStatus, region, errorBox, nextButton, backButton;
    const el = (tag, className, text) => { const node = doc.createElement(tag); if (className) node.className = className; if (text != null) node.textContent = text; return node; };
    const button = (text, className, action) => { const node = el('button', className, text); node.type = 'button'; node.addEventListener('click', action); return node; };
    const dialog = el('dialog', 'rg-guide'); dialog.id = id; dialog.setAttribute('aria-labelledby', `${id}-title`);
    const shell = el('section', 'rg-shell'); dialog.append(shell);
    const header = el('header', 'rg-header');
    const heading = el('div'); heading.append(el('p', 'rg-eyebrow', 'ROXY · TU JARDÍN'));
    const title = el('h2', '', model.editing ? 'Conozcamos mejor a tu planta' : 'Una nueva vida en casa'); title.id = `${id}-title`; heading.append(title);
    const closeButton = button('Cerrar', 'rg-close', () => close()); header.append(heading, closeButton); shell.append(header);
    const progress = el('ol', 'rg-progress'); progress.setAttribute('aria-label', 'Pasos para configurar tu planta');
    ['Su identidad', 'Su lugar', 'Sus raíces', 'Su ficha'].forEach((text, i) => { const item = el('li'); item.append(el('span', 'rg-step-number', String(i + 1)), el('span', '', text)); progress.append(item); }); shell.append(progress);
    const roxy = el('div', 'rg-roxy'); const avatar = el('img'); avatar.src = '/assets/roxy_home_avatar.jpg'; avatar.alt = ''; avatar.width = 64; avatar.height = 64; avatar.setAttribute('data-roxy-avatar', '');
    avatar.addEventListener('error', () => { avatar.hidden = true; });
    const voiceCopy = el('div'); voiceCopy.append(el('strong', '', 'Roxy, paso a paso contigo'));
    const speech = el('p', 'rg-speech'); speech.setAttribute('aria-live', 'polite'); speech.setAttribute('aria-atomic', 'true'); voiceCopy.append(speech);
    const speechActions = el('div', 'rg-speech-actions');
    const canSpeak = Boolean(global.speechSynthesis && global.SpeechSynthesisUtterance);
    function stopSpeech() {
      if (!utterance) return;
      const owned = utterance; utterance = null; owned.onend = owned.onerror = owned.onstart = null;
      global.speechSynthesis.cancel();
      if (speechButton) speechButton.textContent = 'Escuchar a Roxy';
      if (speechStatus) speechStatus.textContent = 'Voz del dispositivo · sin micrófono';
    }
    function speak() {
      if (!canSpeak || closed) return;
      if (utterance) { stopSpeech(); return; }
      const spoken = new global.SpeechSynthesisUtterance(speechText); utterance = spoken; spoken.lang = 'es-US'; spoken.rate = 0.95;
      spoken.onstart = () => { if (utterance === spoken && !closed) { speechButton.textContent = 'Detener voz'; speechStatus.textContent = 'Leyendo con la voz de tu dispositivo'; } };
      const finish = () => { if (utterance === spoken) { utterance = null; speechButton.textContent = 'Escuchar a Roxy'; speechStatus.textContent = 'Voz del dispositivo · sin micrófono'; } };
      spoken.onend = finish;
      spoken.onerror = () => { finish(); if (!closed) speechStatus.textContent = 'No pude reproducir la voz. Puedes continuar leyendo.'; };
      try { global.speechSynthesis.speak(spoken); } catch (_) { spoken.onerror(); }
    }
    speechButton = button('Escuchar a Roxy', 'rg-voice', speak); speechButton.disabled = !canSpeak;
    speechStatus = el('small', '', canSpeak ? 'Voz del dispositivo · sin micrófono' : 'La voz no está disponible en este navegador. Todo está por escrito.');
    speechActions.append(speechButton, speechStatus); voiceCopy.append(speechActions); roxy.append(avatar, voiceCopy); shell.append(roxy);
    region = el('div', 'rg-content'); shell.append(region);
    errorBox = el('p', 'rg-error'); errorBox.setAttribute('role', 'alert'); errorBox.hidden = true; shell.append(errorBox);
    const footer = el('footer', 'rg-footer');
    backButton = button('Atrás', 'rg-secondary', () => { if (!saving && model.step > 0) { model.step--; render(); } });
    nextButton = button('Continuar', 'rg-primary', async () => {
      if (saving || photoPending || closed) return;
      const validation = validate(model, model.step);
      if (validation) { showError(validation); return; }
      if (model.step < 3) { model.step++; render(); return; }
      saving = true; stopSpeech(); clearError(); updateBusy();
      try {
        await options.onSave(payload(model), { plantId: options.plant?.id || null, editing: model.editing });
        saving = false; close('saved');
      } catch (error) {
        if (!closed) showError(clean(error?.message) || 'No pude confirmar el guardado. Conservamos lo que escribiste; revisa la conexión antes de reintentar.');
      } finally { saving = false; if (!closed) updateBusy(); }
    });
    footer.append(backButton, nextButton); shell.append(footer);
    shell.append(el('p', 'rg-privacy', 'Tú observas; Roxy te ayuda a interpretar la ficha. Sin sensores, no puedo vigilar ni regar tu planta. Los recordatorios se activan por separado.'));
    function clearError() { errorBox.textContent = ''; errorBox.hidden = true; }
    function showError(message) { errorBox.textContent = message; errorBox.hidden = false; errorBox.scrollIntoView?.({ block: 'nearest' }); }
    function updateBusy() { closeButton.disabled = saving; backButton.disabled = saving; nextButton.disabled = saving || photoPending; nextButton.textContent = saving ? 'Guardando tu planta…' : photoPending ? 'Preparando tu foto…' : model.step === 3 ? model.editing ? 'Guardar cambios' : 'Guardar en mi jardín' : 'Continuar'; }
    function updateNarration() { const next = narration(model); if (next !== speechText) { stopSpeech(); speechText = next; speech.textContent = next; } }
    function field(labelText, control, help = '') {
      const row = el('label', 'rg-field'); row.append(el('span', '', labelText), control);
      if (help) row.append(el('small', '', help)); return row;
    }
    function textInput(key, placeholder, max, multiline = false) {
      const input = el(multiline ? 'textarea' : 'input'); if (!multiline) input.type = 'text'; input.value = model.values[key]; input.maxLength = max; input.placeholder = placeholder;
      input.addEventListener('input', () => { model.values[key] = input.value; });
      input.addEventListener('change', updateNarration); return input;
    }
    function selectInput(key, rows, onChange) {
      const select = el('select'); rows.forEach(([value, text]) => { const opt = el('option', '', text); opt.value = value; select.append(opt); }); select.value = String(model.values[key] ?? '');
      select.addEventListener('change', () => { model.values[key] = select.value; clearError(); updateNarration(); if (onChange) onChange(); }); return select;
    }
    function choiceGroup(key, legendText, onChange) {
      const group = el('fieldset', 'rg-choice-group'); group.append(el('legend', '', legendText));
      choices[key].forEach(([value, text]) => { const option = el('label', 'rg-choice'); const input = el('input'); input.type = 'radio'; input.name = `${id}-${key}`; input.value = value; input.checked = model.values[key] === value;
        input.addEventListener('change', () => { if (!input.checked) return; model.values[key] = value; updateNarration(); if (onChange) onChange(); }); option.append(input, el('span', '', text)); group.append(option); }); return group;
    }
    function notesField() { return field('Algo que quieras contarme', textInput('notes', 'Por ejemplo: llegó ayer, es un esqueje, una hoja cambió de color…', 800, true), 'Opcional. Describe lo que observas; no hace falta conocer la causa.'); }
    function identityStep() {
      region.append(el('h3', '', '¿Quién llega a casa?'));
      const selection = selectInput('species_key', model.species.map(row => [row.key, row.key === 'unknown' ? 'No la conozco / no está en la lista' : `${row.common_name} · ${row.scientific_name}`]), () => { speciesHelp.textContent = model.values.species_key === 'unknown' ? 'Si es otra especie que no aparece, pon ese nombre abajo. Quedará por identificar, sin asignarle el cuidado de otra planta.' : 'Escoge esta especie solo si la conoces. Elegirla es tu confirmación; la guía no la identifica por la foto.'; });
      if (model.editing) selection.disabled = true;
      region.append(field('Especie que conoces', selection));
      const speciesHelp = el('p', 'rg-hint', model.editing ? 'Conservamos su identificación actual. Si está pendiente, confírmala desde su ficha.' : model.values.species_key === 'unknown' ? 'Si es otra especie que no aparece, pon ese nombre abajo. Quedará por identificar, sin asignarle el cuidado de otra planta.' : 'Escoge esta especie solo si la conoces. La guía no la identifica por la foto.'); region.append(speciesHelp);
      region.append(field('¿Cómo la llamaremos?', textInput('display_name', 'Ej. Pothos de la cocina', 60), 'Puedes usar su nombre o un apodo. No se usará para adivinar la especie.'));
      if (model.editing) { region.append(el('p', 'rg-hint', 'Al guardar conservaremos su foto y su historial.')); return; }
      const input = el('input'); input.type = 'file'; input.accept = 'image/jpeg,image/png,image/webp';
      const preview = el('div', 'rg-photo-preview');
      function showPreview() { preview.replaceChildren(); if (model.values.photo_data_url) { const image = el('img'); image.src = model.values.photo_data_url; image.alt = 'La foto que elegiste para tu planta'; image.addEventListener('error', () => { image.hidden = true; preview.append(el('span', '', 'No se puede previsualizar esta foto. Prueba otra imagen.')); }); preview.append(image, el('span', '', 'Esta es tu foto, no una identificación automática.')); } }
      input.addEventListener('change', async () => {
        const file = input.files?.[0]; if (!file) return; const revision = ++photoRevision; photoPending = true; clearError(); updateBusy();
        try {
          if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new Error('Usa una foto JPEG, PNG o WebP. Si tu teléfono utiliza HEIC, exporta la foto como JPEG.');
          if (!file.size || file.size > 20_000_000) throw new Error('Elige una foto de hasta 20 MB.');
          const data = options.readPhoto ? await options.readPhoto(file) : await new Promise((resolve, reject) => { if (file.size > 6_000_000) { reject(new Error('Elige una foto de hasta 6 MB.')); return; } const reader = new global.FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error('No pude leer esa foto.')); reader.readAsDataURL(file); });
          if (closed || revision !== photoRevision) return;
          if (typeof data !== 'string' || data.length > 8_100_000 || !/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=\s]+$/.test(data)) throw new Error('La foto no tiene un formato válido o supera 6 MB después de prepararla.');
          model.values.photo_data_url = data; showPreview();
        } catch (error) { if (!closed && revision === photoRevision) showError(clean(error?.message) || 'No pude preparar la foto.'); }
        finally { if (!closed && revision === photoRevision) { photoPending = false; updateBusy(); } }
      });
      region.append(field('Una foto actual', input, 'Se guarda únicamente al confirmar la ficha. No se envía a un identificador ni a una IA desde esta guía.'), preview); showPreview();
    }
    function placeStep() {
      region.append(el('h3', '', 'Cada rincón tiene su luz'));
      region.append(field('¿En qué habitación o zona estará?', textInput('room', 'Cocina, sala, balcón…', 60)));
      region.append(choiceGroup('placement', '¿Dentro o fuera?'));
      region.append(field('¿Qué luz recibe habitualmente?', selectInput('light_exposure', choices.light_exposure), 'Luz indirecta: el lugar está iluminado, pero los rayos del sol no caen directamente sobre las hojas.'));
      const profile = selectedProfile(model); if (confirmedSpecies(model) && profile.light) region.append(el('p', 'rg-care-tip', `En su ficha: ${profile.light}.`));
      region.append(el('p', 'rg-hint', 'Puedes elegir “Todavía no lo sé” y observarla durante el día. Una foto aislada no mide las horas de luz.'));
    }
    function rootsStep() {
      region.append(el('h3', '', 'Empezamos por sus raíces'));
      const conditional = el('div');
      function showConditional() {
        conditional.replaceChildren();
        if (model.values.growing_medium === 'soil') {
          const drainage = el('select'); [['unknown', 'Todavía no lo sé'], ['yes', 'Sí, el exceso de agua puede salir'], ['no', 'No, no tiene salida']].forEach(([value, text]) => { const opt = el('option', '', text); opt.value = value; drainage.append(opt); }); drainage.value = model.values.drainage === true ? 'yes' : model.values.drainage === false ? 'no' : 'unknown'; drainage.addEventListener('change', () => { model.values.drainage = drainage.value === 'yes' ? true : drainage.value === 'no' ? false : null; });
          conditional.append(field('¿El recipiente permite salir al exceso de agua?', drainage, 'Comprueba el recipiente que contiene las raíces, no solo la maceta decorativa exterior.'), field('Material del recipiente', selectInput('pot_type', choices.pot_type)));
        } else if (model.values.growing_medium === 'water') conditional.append(el('p', 'rg-care-tip', 'Gracias, este detalle cambia su ficha. No mostraremos una pauta de riego de tierra. Cuéntame abajo si está enraizando o lleva tiempo viviendo en agua.'));
        else conditional.append(el('p', 'rg-hint', 'Lo dejaremos pendiente. No hace falta sacar la planta de su recipiente ni lastimar las raíces para responder ahora.'));
      }
      region.append(choiceGroup('growing_medium', '¿Dónde están las raíces?', showConditional), conditional, notesField()); showConditional();
    }
    function summaryStep() {
      region.append(el('h3', '', `${plantName(model)}, en tu hogar`));
      const data = summary(model), list = el('dl', 'rg-summary');
      data.facts.forEach(([key, value]) => { const row = el('div'); row.append(el('dt', '', key), el('dd', '', value)); list.append(row); }); region.append(list);
      data.care.forEach(([heading, value]) => { const card = el('section', 'rg-care-tip'); card.append(el('strong', '', heading), el('p', '', value)); region.append(card); });
      if (data.pending.length) { const pending = el('section', 'rg-pending'); pending.append(el('h4', '', 'Lo que vamos a comprobar')); const items = el('ul'); data.pending.forEach(text => items.append(el('li', '', text))); pending.append(items); region.append(pending); }
      if (model.values.notes) region.append(el('p', 'rg-hint', `Tu observación: ${model.values.notes}`));
      region.append(el('p', 'rg-hint', 'Guardar crea o actualiza la ficha del hogar. No añade compras ni activa notificaciones por sí solo.'));
    }
    function render() {
      stopSpeech(); clearError(); region.replaceChildren();
      [...progress.children].forEach((item, i) => { if (i === model.step) item.setAttribute('aria-current', 'step'); else item.removeAttribute('aria-current'); item.dataset.complete = String(i < model.step); });
      updateNarration(); [identityStep, placeStep, rootsStep, summaryStep][model.step](); backButton.hidden = model.step === 0; updateBusy();
      dialog.scrollTop = 0; const stepTitle = region.querySelector('h3'); if (stepTitle) { stepTitle.tabIndex = -1; stepTitle.focus({ preventScroll: true }); }
    }
    function close(reason = 'cancelled') {
      if (closed || saving) return; closed = true; photoRevision++; stopSpeech();
      model.values.photo_data_url = ''; dialog.close(); dialog.remove();
      if (active === controller) active = null;
      if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
      if (typeof options.onClose === 'function') options.onClose(reason);
    }
    const controller = { close, isSaving: () => saving };
    dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
    doc.body.append(dialog); active = controller; dialog.showModal(); render(); return controller;
  }
  function reviewText(plant, memberName) {
    const name = clean(plant?.display_name, 60) || 'tu planta';
    return `Hola${clean(memberName, 60) ? `, ${clean(memberName, 60)}` : ''}. Miremos a ${name} juntos. No hace falta saber el nombre de un problema: cuéntame qué ves. Una revisión no significa que hayas regado, y no puedo diagnosticar su salud con este registro.`;
  }
  function review(options = {}) {
    if (!options.plant?.id || typeof options.onSave !== 'function') throw new TypeError('La revisión necesita una planta y un guardado explícito.');
    if (active) { if (active.isSaving()) return active; active.close(); }
    const plant = options.plant, doc = global.document, previousFocus = doc.activeElement;
    const id = `rg-review-${++counter}`;
    let closed = false, saving = false, photoPending = false, photoRevision = 0, result = '', photo = '', utterance = null;
    const el = (tag, className, text) => { const node = doc.createElement(tag); if (className) node.className = className; if (text != null) node.textContent = text; return node; };
    const button = (text, className, action) => { const node = el('button', className, text); node.type = 'button'; node.addEventListener('click', action); return node; };
    const dialog = el('dialog', 'rg-guide'); dialog.setAttribute('aria-labelledby', `${id}-title`);
    const shell = el('section', 'rg-shell'), header = el('header', 'rg-header'), heading = el('div');
    heading.append(el('p', 'rg-eyebrow', 'ROXY · UNA PAUSA PARA TU PLANTA'));
    const title = el('h2', '', `¿Cómo está ${clean(plant.display_name, 60) || 'tu planta'} hoy?`); title.id = `${id}-title`; heading.append(title);
    const closeButton = button('Cerrar', 'rg-close', () => close()); header.append(heading, closeButton); shell.append(header);
    const roxy = el('div', 'rg-roxy');
    const avatar = el('img'); avatar.src = '/assets/roxy_home_avatar.jpg'; avatar.alt = ''; avatar.setAttribute('data-roxy-avatar', ''); avatar.width = 56; avatar.height = 56; avatar.addEventListener('error', () => { avatar.hidden = true; });
    const copy = el('div'), speech = reviewText(plant, options.memberName); copy.append(el('strong', '', 'Roxy, paso a paso contigo'), el('p', 'rg-speech', speech));
    const canSpeak = Boolean(global.speechSynthesis && global.SpeechSynthesisUtterance);
    const speechStatus = el('small', '', canSpeak ? 'Voz del dispositivo · sin micrófono' : 'Voz no disponible. Puedes continuar por escrito.');
    function stopSpeech() { if (!utterance) return; utterance.onstart = utterance.onend = utterance.onerror = null; utterance = null; global.speechSynthesis.cancel(); voiceButton.textContent = 'Escuchar a Roxy'; speechStatus.textContent = 'Voz del dispositivo · sin micrófono'; }
    const voiceButton = button('Escuchar a Roxy', 'rg-voice', () => {
      if (!canSpeak || closed) return; if (utterance) { stopSpeech(); return; }
      const spoken = new global.SpeechSynthesisUtterance(speech); utterance = spoken; spoken.lang = 'es-US'; spoken.rate = .95;
      spoken.onstart = () => { if (!closed && utterance === spoken) voiceButton.textContent = 'Detener voz'; };
      const finish = () => { if (utterance === spoken) { utterance = null; voiceButton.textContent = 'Escuchar a Roxy'; } };
      spoken.onend = finish; spoken.onerror = () => { finish(); if (!closed) speechStatus.textContent = 'No pude reproducir la voz. Puedes continuar leyendo.'; };
      try { global.speechSynthesis.speak(spoken); } catch (_) { spoken.onerror(); }
    }); voiceButton.disabled = !canSpeak;
    const voiceRow = el('div', 'rg-speech-actions'); voiceRow.append(voiceButton, speechStatus); copy.append(voiceRow); roxy.append(avatar, copy); shell.append(roxy);
    const steps = el('ol', 'rg-review-checklist');
    const observations = ['Mira las hojas: ¿notas cambios de color, bordes secos, manchas o crecimiento nuevo?'];
    if (plant.growing_medium === 'soil') observations.push(plant.identification?.status === 'CONFIRMED' && clean(plant.soil_rule) || 'Comprueba cómo está el sustrato. La pauta específica depende de confirmar la especie.');
    else if (plant.growing_medium === 'water') observations.push('Observa el agua y las raíces visibles. No aplicamos una pauta de riego de tierra a una planta en agua.');
    else observations.push('Antes de decidir un cuidado, confirma si está en tierra/sustrato o en agua desde “Conocer mi planta”.');
    observations.push('Cuéntame lo que ves y lo que hiciste. No cambies el cuidado solo para marcar esta revisión como completada.');
    observations.forEach(text => steps.append(el('li', '', text))); shell.append(steps);
    const notes = el('textarea'); notes.maxLength = 600; notes.placeholder = 'Ej. Revisé la tierra: sigue húmeda. Hay una hoja nueva.';
    const notesLabel = el('label', 'rg-field'); notesLabel.append(el('span', '', 'Esto es lo que observo'), notes, el('small', '', 'Tu observación se guarda en su historial. No se interpreta como un diagnóstico.')); shell.append(notesLabel);
    const group = el('fieldset', 'rg-choice-group'); group.append(el('legend', '', '¿Qué hiciste en esta revisión?'));
    const actions = plant.growing_medium === 'water' ? [['CHECKED', 'Revisé el agua, las raíces o las hojas']] : [['CHECKED', 'Solo revisé; no regué'], ['WATERED', 'Revisé y sí regué']];
    actions.forEach(([value, text]) => { const choice = el('label', 'rg-choice'), input = el('input'); input.type = 'radio'; input.name = `${id}-result`; input.value = value; input.checked = false; input.addEventListener('change', () => { if (input.checked) result = value; }); choice.append(input, el('span', '', text)); group.append(choice); }); shell.append(group);
    const photoLabel = el('label', 'rg-field'), fileInput = el('input'); fileInput.type = 'file'; fileInput.accept = 'image/jpeg,image/png,image/webp';
    photoLabel.append(el('span', '', 'Foto de hoy · opcional'), fileInput, el('small', '', 'Puedes registrar solo texto. La foto no sustituye la identificación o una revisión experta.'));
    const preview = el('div', 'rg-photo-preview'); shell.append(photoLabel, preview);
    const error = el('p', 'rg-error'); error.setAttribute('role', 'alert'); error.hidden = true; shell.append(error);
    function showError(text) { error.textContent = text; error.hidden = false; }
    function clearError() { error.hidden = true; error.textContent = ''; }
    function updateBusy() { saveButton.disabled = saving || photoPending; closeButton.disabled = saving; saveButton.textContent = saving ? 'Guardando revisión…' : photoPending ? 'Preparando foto…' : 'Guardar mi revisión'; }
    fileInput.addEventListener('change', async () => {
      const file = fileInput.files?.[0]; if (!file) return; const revision = ++photoRevision; photoPending = true; clearError(); updateBusy();
      try {
        if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || !file.size || file.size > 20_000_000) throw new Error('Elige una foto JPEG, PNG o WebP de hasta 20 MB.');
        const data = options.readPhoto ? await options.readPhoto(file) : await new Promise((resolve, reject) => { if (file.size > 6_000_000) { reject(new Error('Elige una foto de hasta 6 MB.')); return; } const reader = new global.FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error('No pude leer la foto.')); reader.readAsDataURL(file); });
        if (closed || revision !== photoRevision) return;
        if (typeof data !== 'string' || data.length > 8_100_000 || !/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=\s]+$/.test(data)) throw new Error('La foto no tiene un formato válido o supera 6 MB después de prepararla.');
        photo = data; preview.replaceChildren(); const image = el('img'); image.src = photo; image.alt = 'Foto de esta revisión'; image.addEventListener('error', () => { image.hidden = true; }); preview.append(image, el('span', '', 'Se añadirá al historial; la foto principal se conserva.'));
      } catch (err) { if (!closed && revision === photoRevision) showError(clean(err?.message) || 'No pude preparar la foto.'); }
      finally { if (!closed && revision === photoRevision) { photoPending = false; updateBusy(); } }
    });
    const footer = el('footer', 'rg-footer');
    const saveButton = button('Guardar mi revisión', 'rg-primary', async () => {
      if (saving || photoPending || closed) return; clearError();
      if (!result) { showError('Elige si solo revisaste o si también regaste. No lo deduzco de tu nota.'); return; }
      const observation = clean(notes.value, 600); if (!observation && !photo) { showError('Escribe qué observaste o añade una foto antes de guardar.'); return; }
      saving = true; stopSpeech(); updateBusy();
      try {
        await options.onSave({ observation, result, ...(photo ? { photo_data_url: photo } : {}) }, { plantId: plant.id });
        saving = false; close('saved');
      } catch (err) { if (!closed) showError(clean(err?.message) || 'No pude confirmar el guardado. Conservamos tu revisión para que puedas reintentarlo.'); }
      finally { saving = false; if (!closed) updateBusy(); }
    }); footer.append(saveButton); shell.append(footer);
    shell.append(el('p', 'rg-privacy', 'Esto registra lo que tú observas. No activa riego, compras, notificaciones ni una evaluación automática de la salud de la planta.'));
    function close(reason = 'cancelled') { if (closed || saving) return; closed = true; photoRevision++; stopSpeech(); photo = ''; dialog.close(); dialog.remove(); if (active === controller) active = null; if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true }); if (typeof options.onClose === 'function') options.onClose(reason); }
    const controller = { close, isSaving: () => saving }; dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
    dialog.append(shell); doc.body.append(dialog); active = controller; dialog.showModal(); title.tabIndex = -1; title.focus({ preventScroll: true }); return controller;
  }
  global.RoxyGardenGuide = Object.freeze({ open, review, model: Object.freeze({ create: createModel, narration, summary, payload, validate, reviewText }) });
})(typeof window !== 'undefined' ? window : globalThis);
