/* Source-led educational agenda. No private storage, prescriptions or workout logs. */
((scope) => {
  'use strict';
  const DAY_NAMES = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
  const DAY_KEYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
  const FORM_DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
  const PREFIX = '/api/fitness/v1/programs';
  let state = null, active = true;
  const plain = (value, maximum = 1000) => typeof value === 'string' && value.trim().length > 0 && value.length <= maximum && !/[<>\x00-\x08\x0b-\x1f\x7f]/.test(value);
  const lines = (value, minimum = 1, maximum = 40) => Array.isArray(value) && value.length >= minimum && value.length <= maximum && value.every(line => plain(line, 8000));
  const validZone = value => { if (typeof value !== 'string' || value.length > 64) return false; try { new Intl.DateTimeFormat('en', {timeZone:value}); return true; } catch (_) { return false; } };
  function dateValue(value) {
    if (typeof value !== 'string' || !/^20\d{2}-\d{2}-\d{2}$/.test(value)) return null;
    const date = new Date(`${value}T12:00:00Z`);
    return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value ? date : null;
  }
  function todayInZone(zone, now = new Date()) {
    const parts = new Intl.DateTimeFormat('en-US', {timeZone:validZone(zone) ? zone : 'UTC', year:'numeric', month:'2-digit', day:'2-digit'}).formatToParts(now);
    const part = name => parts.find(value => value.type === name).value;
    return `${part('year')}-${part('month')}-${part('day')}`;
  }
  function agendaDates(start, days) {
    const initial = dateValue(start);
    if (!initial || !Array.isArray(days) || !days.length || days.length > 7 || new Set(days).size !== days.length || days.some(day => !DAY_KEYS.includes(day))) throw new Error('Elige una fecha válida y al menos un día.');
    return Array.from({length:7}, (_, index) => {
      const date = new Date(initial); date.setUTCDate(date.getUTCDate() + index);
      const key = DAY_KEYS[date.getUTCDay()];
      return {date:date.toISOString().slice(0, 10), key, label:DAY_NAMES[date.getUTCDay()], number:date.getUTCDate(), chosen:days.includes(key)};
    });
  }
  function safeURL(value, kind) {
    if (typeof value !== 'string' || value.length > 1000 || value !== value.trim()) return '';
    try {
      const url = new URL(value);
      if (url.protocol !== 'https:' || url.username || url.password || url.port || url.search) return '';
      if (kind === 'license') return ['www.nationalarchives.gov.uk', 'nationalarchives.gov.uk'].includes(url.hostname) && url.pathname === '/doc/open-government-licence/version/3/' && !url.hash ? value : '';
      if (url.hostname !== 'www.nhs.uk') return '';
      if (kind === 'terms') return url.pathname === '/our-policies/terms-and-conditions/' ? value : '';
      return /^\/live-well\/exercise\/[a-z-]+\/$/.test(url.pathname) && !url.hash ? value : '';
    } catch (_) { return ''; }
  }
  const flags = payload => payload?.status === 'education_only' && payload.active_training === false && payload.can_activate_plans === false && payload.clinical_approval === false && payload.can_persist === false;
  function validSummary(row) {
    return row && /^[a-z][a-z0-9-]{1,79}$/.test(row.id || '') && plain(row.title_en, 240) && plain(row.title_es, 240) && plain(row.frequency_en, 2000) && plain(row.frequency_es, 2000) &&
      Number.isInteger(row.exercise_count) && row.exercise_count >= 1 && row.exercise_count <= 40 && row.duration_seconds === null && dateValue(row.checked_on) &&
      plain(row.source_version, 120) && /^[a-f0-9]{64}$/.test(row.source_sha256 || '') && safeURL(row.source_url, 'source') && safeURL(row.license_url, 'license') && safeURL(row.terms_url, 'terms');
  }
  function validateCatalog(payload) {
    if (!flags(payload) || JSON.stringify(payload).length > 150000 || !Array.isArray(payload.programs) || payload.programs.length > 12 || payload.total !== payload.programs.length || !payload.programs.every(validSummary) || new Set(payload.programs.map(row => row.id)).size !== payload.programs.length) throw new Error('No pudimos verificar los programas de la fuente.');
    return payload.programs;
  }
  function validateDetail(payload, summary) {
    const program = payload?.program;
    if (!flags(payload) || JSON.stringify(payload).length > 300000 || !validSummary(program) || !summary || ['id','title_en','title_es','exercise_count','source_version','checked_on','source_sha256','frequency_en','frequency_es','duration_seconds','source_url','terms_url','license_url'].some(key => program[key] !== summary[key]) ||
      !lines(program.intro_en) || !lines(program.intro_es) || program.intro_en.length !== program.intro_es.length || !lines(program.notes_es, 0, 30) ||
      !plain(program.attribution_en, 4000) || !plain(program.attribution_es, 4000) || !Array.isArray(program.exercises) || program.exercises.length !== program.exercise_count ||
      new Set(program.exercises.map(row => row?.id)).size !== program.exercises.length || program.exercises.some(row => !row || !/^[a-z][a-z0-9-]{1,99}$/.test(row.id || '') || !plain(row.name_en, 240) || !plain(row.name_es, 240) || !lines(row.instructions_en) || !lines(row.instructions_es) || row.instructions_en.length !== row.instructions_es.length)) throw new Error('La guía recibida no coincide con su fuente completa. No organizamos una versión parcial.');
    return program;
  }
  const calendarEscape = value => String(value).replace(/\\/g, '\\\\').replace(/\n/g, '\\n').replace(/,/g, '\\,').replace(/;/g, '\\;');
  function calendarText(agenda, now = new Date(), uid = () => scope.crypto.randomUUID()) {
    if (!Array.isArray(agenda) || agenda.length !== 7 || agenda.some(day => !dateValue(day.date) || typeof day.chosen !== 'boolean')) throw new Error('Agenda inválida.');
    const first = dateValue(agenda[0].date);
    if (agenda.some((day, index) => { const date = new Date(first); date.setUTCDate(date.getUTCDate() + index); return date.toISOString().slice(0, 10) !== day.date; })) throw new Error('Agenda inválida.');
    const stamp = now.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
    const rows = ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Roxy Home//Personal agenda//ES','CALSCALE:GREGORIAN'];
    agenda.filter(day => day.chosen).forEach(day => {
      const end = dateValue(day.date); end.setUTCDate(end.getUTCDate() + 1);
      rows.push('BEGIN:VEVENT', `UID:${calendarEscape(uid())}@roxy.home`, `DTSTAMP:${stamp}`, `DTSTART;VALUE=DATE:${day.date.replace(/-/g, '')}`, `DTEND;VALUE=DATE:${end.toISOString().slice(0, 10).replace(/-/g, '')}`, 'SUMMARY:Actividad personal', 'CLASS:PRIVATE', 'TRANSP:TRANSPARENT', 'END:VEVENT');
    });
    return rows.concat('END:VCALENDAR', '').join('\r\n');
  }
  function guideText(program, language = 'es') {
    const locale = language === 'en' ? 'en' : 'es';
    return [program[`title_${locale}`], locale === 'en' ? 'Educational source guide. Not a personalised workout or clinical clearance.' : 'Guía educativa de una fuente. No es un entrenamiento personalizado ni autorización clínica.',
      ...program[`intro_${locale}`], ...program.exercises.flatMap((exercise, index) => [`${index + 1}. ${exercise[`name_${locale}`]}`, ...exercise[`instructions_${locale}`]]),
      ...(locale === 'es' && program.notes_es.length ? ['Notas de la adaptación de Roxy:', ...program.notes_es] : []), program[`attribution_${locale}`], `Open Government Licence v3: ${program.license_url}`,
      locale === 'en' ? 'Original source and dated copy:' : 'Procedencia del original en inglés (no autoría ni aval de esta adaptación):',
      program.source_url, `Versión del original: ${program.source_version}`, `Consulta: ${program.checked_on}`, `Condiciones: ${program.terms_url}`].join('\n\n');
  }
  const element = (tag, text, className) => { const el = document.createElement(tag); if (text !== undefined && text !== null) el.textContent = text; if (className) el.className = className; return el; };
  const button = (label, action, className = 'fxp-button') => { const el = element('button', label, className); el.type = 'button'; el.addEventListener('click', action); return el; };
  const link = (label, href) => { const el = element('a', label); el.href = href; el.target = '_blank'; el.rel = 'noopener noreferrer'; el.referrerPolicy = 'no-referrer'; return el; };
  const current = (owner, token) => state === owner && active && !document.hidden && token === owner.generation;
  function stopReaderVoice(owner) { if(owner.voiceOwned||owner.voiceActive)scope.RoxyHomeTour?.stop();owner.voiceOwned=false;owner.voiceActive=false; }
  function cancel(owner) { stopReaderVoice(owner); owner.controller?.abort(); owner.controller = null; owner.generation++; owner.busy = false; }
  function purge(owner) { cancel(owner); owner.catalog = null; owner.program = null; owner.agenda = null; owner.selectedId = ''; owner.selectedDate = ''; owner.reader = false; owner.movement = 0; owner.instruction = 0; owner.language = 'es'; owner.error = ''; owner.notice = ''; owner.days = []; owner.start = todayInZone(owner.timezone); owner.revalidating = false; }
  function focus(owner, selector) { const el = owner.root.querySelector(selector); el?.focus({preventScroll:true}); (el?.closest?.('.fx-session-cinema')||el)?.scrollIntoView?.({block:'start', behavior:'auto'}); }
  async function request(owner, path) {
    const controller = new AbortController(); owner.controller = controller;
    let timer;
    try {
      return await Promise.race([
        (async () => { const response = await fetch(path, {credentials:'same-origin', cache:'no-store', headers:{Accept:'application/json'}, signal:controller.signal}); if (!response.ok) { const err = new Error(response.status === 401 ? 'Inicia sesión en Roxy Home para consultar estas guías.' : 'No pudimos consultar la fuente. Puedes reintentar.'); err.status = response.status; throw err; } return response.json(); })(),
        new Promise((_, reject) => { timer = setTimeout(() => { controller.abort(); const err = new Error('La consulta tardó demasiado. Puedes reintentar.'); err.name = 'TimeoutError'; reject(err); }, 12000); })
      ]);
    } finally { clearTimeout(timer); if (owner.controller === controller) owner.controller = null; }
  }
  async function loadCatalog(owner) {
    if (!current(owner, owner.generation) || owner.root?.isConnected === false) return;
    cancel(owner); const token = owner.generation; owner.busy = true; owner.error = ''; draw(owner);
    try { const result = await request(owner, PREFIX); if (!current(owner, token)) return; owner.catalog = validateCatalog(result); }
    catch (error) { if (current(owner, token) && error.name !== 'AbortError') owner.error = error.message; }
    finally { if (current(owner, token)) { owner.busy = false; draw(owner); } }
  }
  async function loadProgram(owner, id) {
    if (!current(owner, owner.generation)) return;
    const summary = owner.catalog?.find(row => row.id === id); if (!summary) return;
    cancel(owner); const token = owner.generation; owner.selectedId = id; owner.program = null; owner.agenda = null; owner.reader = false; owner.movement = 0; owner.instruction = 0; owner.language = 'es'; owner.days = []; owner.busy = true; owner.error = ''; owner.notice = ''; draw(owner);
    try { const result = await request(owner, `${PREFIX}/${encodeURIComponent(id)}`); if (!current(owner, token)) return; owner.program = validateDetail(result, summary); }
    catch (error) { if (current(owner, token) && error.name !== 'AbortError') owner.error = error.message; }
    finally { if (current(owner, token)) { owner.busy = false; draw(owner); focus(owner, '.fxp-program-title'); } }
  }
  function download(owner, text, type, filename) {
    if (!current(owner, owner.generation)) return;
    const url = URL.createObjectURL(new Blob([text], {type})), a = element('a'); a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function invalidateAgenda(owner) { if (!current(owner, owner.generation)) return; owner.agenda = null; owner.reader = false; owner.notice = 'Cambiaste la selección. Organiza de nuevo para ver esas fechas.'; owner.error = ''; drawAgenda(owner); }
  function organize(owner) {
    if (!owner.program || owner.busy || !current(owner, owner.generation)) return;
    owner.error = '';
    try {
      if (!validZone(owner.timezone)) throw new Error('Revisa la zona horaria, por ejemplo America/New_York.');
      owner.agenda = agendaDates(owner.start, owner.days); const today = todayInZone(owner.timezone);
      owner.selectedDate = owner.agenda.some(day => day.date === today) ? today : owner.agenda[0].date;
      owner.reader = false; owner.notice = ''; draw(owner); focus(owner, '.fxp-agenda-heading');
    } catch (error) { owner.error = error.message; drawAgenda(owner); focus(owner, '.fxp-error'); }
  }
  function draw(owner) {
    if (state !== owner || !owner.root) return;
    const wrap = element('section', null, 'fxp-shell'); wrap.setAttribute('aria-label', 'Agenda educativa de ejercicio'); owner.root.replaceChildren(wrap); owner.wrap = wrap;
    if (!active || document.hidden) return;
    const heading = element('header', null, 'fxp-heading'); heading.append(element('p', 'GUÍAS CON FUENTE · TÚ ELIGES LOS DÍAS', 'fxp-eyebrow')); if (!owner.agenda) heading.append(element('h3', 'Tu semana, con una guía real'), element('p', 'Organiza una rutina publicada en las fechas que tú elijas. Agenda temporal, no un entrenamiento personalizado.')); wrap.append(heading);
    if (owner.revalidating) { const checking = element('p', 'Comprobando la sesión antes de recuperar tu agenda…', 'fxp-status'); checking.setAttribute('role', 'status'); wrap.append(checking); return; }
    let configuration = wrap;
    if (owner.agenda) { owner.agendaRoot = element('div', null, 'fxp-agenda-root'); wrap.append(owner.agendaRoot); drawAgenda(owner); configuration = element('details', null, 'fxp-configuration'); configuration.append(element('summary', 'Cambiar programa o fechas · consultar introducción')); wrap.append(configuration); }
    if (owner.catalog) {
      const choices = element('div', null, 'fxp-programs'); choices.setAttribute('aria-label', 'Programas educativos');
      owner.catalog.forEach(row => {
        const card = button('', () => void loadProgram(owner, row.id), 'fxp-program-card'); card.setAttribute('aria-pressed', String(owner.selectedId === row.id)); card.setAttribute('aria-label', `Ver programa: ${row.title_es}`);
        card.append(element('strong', row.title_es), element('span', `${row.exercise_count} movimientos · guía publicada`)); choices.append(card);
      }); configuration.append(choices);
      if (!owner.catalog.length) wrap.append(element('p', 'No hay programas verificados disponibles. La biblioteca de movimientos sigue accesible.'));
    }
    if (owner.busy) { const status = element('p', owner.selectedId ? 'Cargando la guía completa…' : 'Cargando programas de la fuente…', 'fxp-status'); status.setAttribute('role', 'status'); wrap.append(status); }
    if (owner.error && !owner.program) { const error = element('p', owner.error, 'fxp-error'); error.setAttribute('role', 'alert'); wrap.append(error, button(owner.selectedId ? 'Reintentar esta guía' : 'Reintentar programas', () => owner.selectedId ? void loadProgram(owner, owner.selectedId) : void loadCatalog(owner))); }
    if (!owner.program) return;
    const program = owner.program, locale = owner.language, description = element('section', null, 'fxp-description');
    const title = element('h3', program[`title_${locale}`], 'fxp-program-title'); title.tabIndex = -1;
    description.append(title, element('p', locale === 'es' ? 'Adaptación al español de Roxy, sin aval de la entidad que publicó el original.' : 'Texto original en inglés. Copia fechada, no revisión clínica de Roxy.', 'fxp-caption'), button(locale === 'es' ? 'Ver original en inglés' : 'Ver adaptación en español', () => { if (!current(owner, owner.generation)) return; owner.language = locale === 'es' ? 'en' : 'es'; draw(owner); focus(owner, owner.reader ? '.fxp-reader-title' : '.fxp-program-title'); }, 'fxp-button fxp-quiet'), element('p', 'Duración total no indicada por la fuente. No afirmamos que quepa en tu tiempo disponible.', 'fxp-caption'));
    const attributionNotice = element('div', null, 'fxp-reader-attribution'); attributionNotice.append(element('p', program[`attribution_${locale}`], 'fxp-caption'), link('Open Government Licence v3', program.license_url)); if (locale === 'en') attributionNotice.append(link('Original NHS', program.source_url)); description.append(attributionNotice);
    const intro = element('details', null, 'fxp-source-intro'); intro.lang = locale; intro.append(element('summary', 'Antes de usar esta guía')); program[`intro_${locale}`].forEach(line => intro.append(element('p', line))); intro.open = !owner.agenda; description.append(intro, button('Ver movimientos de la guía', () => { if (!current(owner, owner.generation)) return; owner.reader = true; owner.movement = 0; owner.instruction = 0; drawAgenda(owner); focus(owner, '.fxp-reader-title'); })); configuration.append(description);
    const form = element('form', null, 'fxp-form'); form.setAttribute('aria-label', 'Organizar una semana educativa');
    const fields = element('div', null, 'fxp-fields');
    const startLabel = element('label', 'Fecha inicial'), start = element('input'); start.type = 'date'; start.value = owner.start; start.required = true; start.setAttribute('aria-label', 'Fecha inicial'); start.addEventListener('change', () => { owner.start = start.value; invalidateAgenda(owner); }); startLabel.append(start);
    const zoneLabel = element('label', 'Zona horaria'), zone = element('input'); zone.type = 'text'; zone.value = owner.timezone; zone.maxLength = 64; zone.required = true; zone.setAttribute('aria-label', 'Zona horaria'); zone.addEventListener('input', () => { owner.timezone = zone.value.trim(); invalidateAgenda(owner); }); zoneLabel.append(zone); fields.append(startLabel, zoneLabel); form.append(fields);
    const days = element('fieldset', null, 'fxp-day-choices'); days.append(element('legend', '¿Qué días quieres reservar?'));
    FORM_DAYS.forEach(key => { const label = element('label'), input = element('input'); input.type = 'checkbox'; input.value = key; input.name = 'agenda_day'; input.checked = owner.days.includes(key); input.addEventListener('change', () => { owner.days = input.checked ? [...new Set([...owner.days, key])] : owner.days.filter(day => day !== key); invalidateAgenda(owner); }); label.append(input, element('span', DAY_NAMES[DAY_KEYS.indexOf(key)])); days.append(label); }); form.append(days);
    form.append(element('p', 'Repetiremos esta misma guía en tus días elegidos. No asignamos progresiones, cargas ni un horario recomendado para ti.', 'fxp-caption'));
    const organizeButton = element('button', 'Organizar esta semana', 'fxp-button fxp-primary'); organizeButton.type = 'submit'; form.append(organizeButton); form.addEventListener('submit', event => { event.preventDefault(); event.stopPropagation(); organize(owner); }); configuration.append(form);
    if (!owner.agenda) { owner.agendaRoot = element('div', null, 'fxp-agenda-root'); wrap.append(owner.agendaRoot); drawAgenda(owner); }
    const credits = element('details', null, 'fxp-credits'); credits.append(element('summary', 'Fuente, adaptación y licencia'), element('p', program[`attribution_${locale}`]), link('Open Government Licence v3', program.license_url));
    const original = element('details', null, 'fxp-original-source'); original.append(element('summary', 'Procedencia del original en inglés'), element('p', locale === 'es' ? 'Esta información identifica el material original, no la autoría ni el aval de la adaptación.' : program.attribution_en), element('p', `Versión del original ${program.source_version} · consultado ${program.checked_on}`), link('Consultar original en inglés', program.source_url), link('Condiciones de la fuente', program.terms_url)); credits.append(original); if (locale === 'es') program.notes_es.forEach(line => credits.append(element('p', line))); wrap.append(credits);
    wrap.append(element('p', 'La agenda sólo permanece en esta pestaña: desaparece al salir del módulo, recargar o cambiar de persona. Las actividades sólo se guardan en el calendario del hogar si pulsas Reservar actividad en Home y confirmas el evento. No guardamos un entrenamiento ni datos de salud.', 'fxp-caption'));
  }
  function drawAgenda(owner) {
    stopReaderVoice(owner);
    const root = owner.agendaRoot; if (!root || !current(owner, owner.generation)) return; root.replaceChildren();
    if (owner.error) { const error = element('p', owner.error, 'fxp-error'); error.setAttribute('role', 'alert'); error.tabIndex = -1; root.append(error); }
    if (owner.notice) { const notice = element('p', owner.notice, 'fxp-status'); notice.setAttribute('role', 'status'); root.append(notice); }
    if (!owner.program) return;
    if (!owner.agenda) { if (owner.reader) drawReader(owner, root); return; }
    const today = todayInZone(owner.timezone), header = element('h3', 'Tu agenda de siete días', 'fxp-agenda-heading'); header.tabIndex = -1; root.append(header, element('p', `${owner.agenda[0].date} — ${owner.agenda[6].date} · ${owner.timezone}`, 'fxp-caption'));
    root.append(element('p', 'Guía general: no evalúa si estos movimientos son adecuados para ti. Si sientes dolor, detén el movimiento.', 'fxp-caption'));
    if (owner.view === 'today' && !owner.agenda.some(day => day.date === today)) root.append(element('p', 'Hoy queda fuera de estas fechas. La agenda conserva los días que elegiste.', 'fxp-caption'));
    const days = element('div', null, 'fxp-dates'); days.setAttribute('aria-label', 'Fechas de tu agenda');
    owner.agenda.forEach(day => { const select = button('', () => { owner.selectedDate = day.date; owner.reader = false; drawAgenda(owner); focus(owner, '.fxp-day-title'); }, 'fxp-date'); select.setAttribute('aria-label', `${day.date}: ${day.chosen ? 'guía elegida' : 'sin actividad reservada'}${day.date === today ? ', hoy' : ''}`); select.setAttribute('aria-pressed', String(owner.selectedDate === day.date)); if (day.date === today) select.setAttribute('aria-current', 'date'); select.append(element('small', day.label), element('strong', String(day.number)), element('span', day.chosen ? 'Guía' : 'Libre')); days.append(select); }); root.append(days);
    const day = owner.agenda.find(row => row.date === owner.selectedDate) || owner.agenda[0], panel = element('section', null, 'fxp-day-detail'), title = element('h4', `${day.label} · ${day.date}`, 'fxp-day-title'); title.tabIndex = -1; panel.append(title);
    if (day.chosen) panel.append(element('strong', owner.program.title_es), element('p', 'Elegido por ti · guía educativa, no sesión activada.'), button('Ver guía del día', () => { owner.reader = true; owner.movement = 0; owner.instruction = 0; drawAgenda(owner); focus(owner, '.fxp-reader-title'); }, 'fxp-button fxp-primary'));
    else panel.append(element('p', 'No reservaste una actividad para este día. Un día libre no significa que Roxy haya prescrito descanso.'));
    if (day.chosen && typeof owner.scheduleActivity === 'function') {
      panel.append(button('Reservar actividad en Home', () => {
        if (current(owner, owner.generation)) owner.scheduleActivity(day.date);
      }, 'fxp-button fxp-primary'), element('p', 'Abre un borrador «Actividad personal» sin datos de salud. Revisa y confirma para guardarlo en el calendario del hogar, visible para sus miembros.', 'fxp-caption'));
    }
    root.append(panel);
    const downloads = element('div', null, 'fxp-downloads'); downloads.append(button('Descargar agenda .ics', () => { if (current(owner, owner.generation) && owner.agenda) download(owner, calendarText(owner.agenda), 'text/calendar;charset=utf-8', 'agenda-personal-roxy.ics'); }), button('Descargar guía TXT', () => { if (current(owner, owner.generation) && owner.program) download(owner, guideText(owner.program, owner.language), 'text/plain;charset=utf-8', `${owner.program.id}-${owner.language}.txt`); })); root.append(downloads, element('p', 'El archivo sólo incluye eventos de día completo «Actividad personal», marcados privados y sin alarmas. Tú decides si lo importas; el calendario de destino controla quién puede verlos. No incluye el programa ni datos de salud.', 'fxp-caption'));
    if (owner.reader) drawReader(owner, root);
  }
  // Both real readers share this source-only stage. It never schedules, advances
  // automatically, prescribes a dose, or describes the ambient image as technique.
  function renderSessionScene(options, ui) {
    const {program, movement, language, titleClass, instructionsClass, onInstruction} = options;
    const {element, button} = ui, exercise = program.exercises[movement], lines = exercise[`instructions_${language}`];
    const selected = Math.min(Math.max(Number.isInteger(options.instruction) ? options.instruction : 0, 0), lines.length - 1);
    const stage = element('div', null, 'fx-session-stage');
    const atmosphere = element('p', 'Escena de compañía · guía escrita', 'fx-session-image-note');stage.append(atmosphere);
    const story = element('div', null, 'fx-session-story');
    story.append(element('p', `Movimiento ${movement + 1} de ${program.exercises.length} · ${language === 'es' ? 'Adaptación en español' : 'Original en inglés'}`, 'fx-session-eyebrow'));
    const title = element('h3', exercise[`name_${language}`], titleClass);title.tabIndex = -1;story.append(title, element('p', program[`title_${language}`], 'fx-session-program'));
    const cue = element('div', null, 'fx-session-cue');cue.lang = language;
    cue.append(element('p', `Indicación ${selected + 1} de ${lines.length}`, 'fx-session-cue-count'));
    const line = element('p', lines[selected], 'fx-session-current-instruction');line.tabIndex = -1;line.setAttribute('aria-live', 'polite');cue.append(line);story.append(cue);
    const steps = element('nav', null, 'fx-session-steps');steps.setAttribute('aria-label', 'Indicaciones del movimiento');
    lines.forEach((_, index) => {const step = button(String(index + 1), () => onInstruction(index), 'fx-session-step');step.setAttribute('aria-label', `Ir a la indicación ${index + 1}`);step.setAttribute('aria-pressed', String(index === selected));if(index === selected)step.setAttribute('aria-current', 'step');steps.append(step);});story.append(steps);
    const controls = element('div', null, 'fx-session-cue-controls');
    const previous = button('Indicación anterior', () => onInstruction(selected - 1), 'fx-session-button fx-session-quiet'), next = button('Siguiente indicación', () => onInstruction(selected + 1), 'fx-session-button');
    previous.disabled = selected === 0;next.disabled = selected === lines.length - 1;controls.append(previous, next);story.append(controls);
    story.append(element('p', 'Tú marcas el ritmo. Avanza cuando estés listo.', 'fx-session-pace'));
    stage.append(story);
    const source = element('details', null, 'fx-session-all-instructions');source.append(element('summary', 'Ver todas las indicaciones de este movimiento'));
    const paragraphs = element('div', null, instructionsClass);paragraphs.lang = language;lines.forEach(text => paragraphs.append(element('p', text)));source.append(paragraphs);
    return {stage, source};
  }
  function drawReader(owner, root) {
    const program = owner.program, locale = owner.language, reader = element('section', null, 'fxp-reader fx-session-cinema');
    reader.setAttribute('data-fx-reading', 'true');reader.setAttribute('aria-label', 'Guía de movimiento con Roxy');
    const setInstruction = index => {if(!current(owner, owner.generation)||index < 0||index >= program.exercises[owner.movement][`instructions_${owner.language}`].length)return;stopReaderVoice(owner);owner.instruction = index;drawAgenda(owner);focus(owner, '.fx-session-current-instruction');};
    const scene = renderSessionScene({program,movement:owner.movement,language:locale,instruction:owner.instruction,titleClass:'fxp-reader-title',instructionsClass:'fxp-instructions',onInstruction:setInstruction}, {element,button});
    reader.append(scene.stage);
    const content = element('div', null, 'fx-session-support');
    content.append(element('p', 'Guía general, no evaluación individual. Si sientes dolor, detén el movimiento.', 'fxp-caption fx-session-safety'));
    const intro = element('details', null, 'fx-session-intro');intro.lang = locale;intro.append(element('summary', 'Antes de empezar'));program[`intro_${locale}`].forEach(line => intro.append(element('p', line)));intro.open = owner.movement === 0 && !owner.instruction;content.append(intro, scene.source);
    const controls = element('div', null, 'fx-session-transport');controls.setAttribute('aria-label', 'Controles de la guía');
    const previous = button('Movimiento anterior', () => {if(current(owner, owner.generation)&&owner.movement > 0){owner.movement--;owner.instruction = 0;drawAgenda(owner);focus(owner, '.fxp-reader-title');}}, 'fxp-button fx-session-button fx-session-quiet');
    const next = button('Movimiento siguiente', () => {if(current(owner, owner.generation)&&owner.movement < program.exercises.length - 1){owner.movement++;owner.instruction = 0;drawAgenda(owner);focus(owner, '.fxp-reader-title');}}, 'fxp-button fx-session-button');
    previous.disabled = owner.movement === 0;next.disabled = owner.movement === program.exercises.length - 1;controls.append(previous);
    if(scope.RoxyHomeTour){
      const voiceStatus = element('p', 'Voz oficial de Roxy · lectura del movimiento completo en español', 'fxp-caption fx-session-voice-status');voiceStatus.setAttribute('role', 'status');
      const voiceHost = element('div', null, 'fxp-voice-host fx-session-voice-host');
      const play = () => {
        if(!current(owner, owner.generation))return;stopReaderVoice(owner);owner.voiceActive = true;owner.voiceOwned = true;
        void scope.RoxyHomeTour.speak(`fitness:${program.id.replace('gentle-', '')}:${owner.movement}`, (phase, message) => {
          if(!current(owner, owner.generation)||voice.isConnected === false)return;
          owner.voiceActive = ['loading','playing','ready'].includes(phase);if(['ended','error'].includes(phase))owner.voiceOwned = false;voiceStatus.textContent = message;
          voice.textContent = owner.voiceActive ? 'Pausar voz' : 'Escuchar movimiento en español';
        }, voiceHost);
      };
      const voice = button('Escuchar movimiento en español', () => {if(!current(owner, owner.generation))return;if(owner.voiceActive){stopReaderVoice(owner);voice.textContent = 'Escuchar movimiento en español';voiceStatus.textContent = 'Voz oficial pausada';}else play();}, 'fxp-button fx-session-button fx-session-voice');
      controls.append(voice, button('Repetir voz', play, 'fxp-button fx-session-button fx-session-quiet'));content.append(voiceStatus, voiceHost);
    }
    controls.append(next);reader.append(controls, content);
    const attribution = element('footer', null, 'fxp-reader-attribution fx-session-credit');
    attribution.append(button(locale === 'es' ? 'Ver original en inglés' : 'Ver adaptación en español', () => {if(!current(owner, owner.generation))return;owner.language = locale === 'es' ? 'en' : 'es';draw(owner);focus(owner, '.fxp-reader-title');}, 'fxp-button fx-session-button fx-session-quiet'));
    attribution.append(element('p', program[`attribution_${locale}`], 'fxp-caption'), element('p', `Original: ${program.source_version} · consultado ${program.checked_on}`, 'fxp-caption'), link('Open Government Licence v3', program.license_url), link('Procedencia del original en inglés', program.source_url), link('Condiciones de la fuente', program.terms_url));
    if(locale === 'es')program.notes_es.forEach(line => attribution.append(element('p', line, 'fxp-caption')));
    reader.append(attribution, button('Cerrar guía', () => {if(!current(owner, owner.generation))return;owner.reader = false;drawAgenda(owner);focus(owner, owner.agenda ? '.fxp-day-title' : '.fxp-program-title');}, 'fxp-button fx-session-button fx-session-exit'));root.append(reader);
  }
  function mount(node, options = {}) {
    if (!node) return;
    const identity = typeof options.identity === 'string' ? options.identity : '';
    const previousView = state?.view;
    if (!state || state.identity !== identity) {
      if (state) { purge(state); state.root?.replaceChildren(); }
      const zone = validZone(options.timezone) ? options.timezone : 'UTC';
      state = {root:node, identity, timezone:zone, view:options.view === 'today' ? 'today' : 'week', generation:0, controller:null, busy:false}; purge(state);
    } else { state.root = node; state.view = options.view === 'today' ? 'today' : 'week'; }
    state.scheduleActivity = options.scheduleActivity;
    if (state.agenda && state.view === 'today' && previousView !== 'today') { const today = todayInZone(state.timezone); if (state.agenda.some(day => day.date === today)) { state.selectedDate = today; state.reader = false; } }
    draw(state); if (active && !document.hidden && !state.catalog && !state.busy && !state.error) void loadCatalog(state);
  }
  function setActive(value) {
    const next = value === true; if (next === active) return; active = next;
    if (state && !active) { purge(state); draw(state); }
    else if (state && !document.hidden) { draw(state); if (!state.catalog) void loadCatalog(state); }
  }
  function clear() { if (state) { purge(state); state.root?.replaceChildren(); } state = null; }
  async function resume(owner) {
    cancel(owner); const token = owner.generation; owner.revalidating = true; draw(owner);
    try {
      const status = await request(owner, '/api/fitness/v1/status'); if (!current(owner, token)) return;
      if (status.personal_login !== true || status.member_id !== owner.identity) { purge(owner); owner.error = status.personal_login === true ? 'Cambió la persona conectada. Vuelve a abrir Ejercicio desde Roxy Home.' : ''; draw(owner); if (!owner.error) void loadCatalog(owner); return; }
      owner.revalidating = false; draw(owner); if (!owner.catalog) void loadCatalog(owner); else if (owner.selectedId && !owner.program) void loadProgram(owner, owner.selectedId);
    } catch (error) { if (current(owner, token)) { purge(owner); owner.error = 'No pudimos confirmar la sesión. La agenda no se mostrará hasta volver a consultar.'; draw(owner); } }
  }
  scope.RoxyFitnessPrograms = {mount, setActive, clear, validateCatalog, validateDetail, renderSessionScene};
  if (typeof document !== 'undefined') document.addEventListener('visibilitychange', () => { if (!state) return; if (document.hidden) { cancel(state); state.reader = false; state.revalidating = true; draw(state); } else if (active) void resume(state); });
  scope.addEventListener?.('pagehide', clear);
  if (typeof module !== 'undefined') module.exports = {todayInZone, agendaDates, validZone, validateCatalog, validateDetail, calendarText, guideText, safeURL, renderSessionScene};
})(typeof window !== 'undefined' ? window : globalThis);
