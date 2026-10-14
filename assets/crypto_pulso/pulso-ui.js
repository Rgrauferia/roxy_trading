/* Pulso display logic. Historical phone observations never become a live feed.
 * Network access belongs to the separately gated, read-only RestFeed adapter.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else {
    root.PulsoUI = api;
    if (root.document) {
      if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', () => api.mount(root), {once: true});
      else api.mount(root);
    }
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const MAX_POINTS = 3600;
  const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const timestamp = value => typeof value === 'number' && Number.isSafeInteger(value) && value > 0 && value <= 8640000000000000 ? value : null;
  function numeric(value) {
    if (typeof value === 'string' && /^\d+(?:\.\d+)?$/.test(value)) value = Number(value);
    return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
  }
  function formatCountdown(expiryTimestampMs, nowMs) {
    if (timestamp(expiryTimestampMs) === null || timestamp(nowMs) === null) return '--:--:--';
    const seconds = Math.max(0, Math.ceil((expiryTimestampMs - nowMs) / 1000));
    const part = value => String(value).padStart(2, '0');
    return part(Math.floor(seconds / 3600)) + ':' + part(Math.floor(seconds % 3600 / 60)) + ':' + part(seconds % 60);
  }
  function appendSnapshot(history, snapshot, contract, nowMs) {
    const existing = Array.isArray(history) ? history.slice() : [];
    const result = (reason, data = existing) => ({history: data, appended: false, reason});
    if (!isObject(contract) || contract.status !== 'VALID' || typeof contract.instrumentSymbol !== 'string'
      || timestamp(contract.windowStartTimestampMs) === null || timestamp(contract.windowCloseTimestampMs) === null
      || timestamp(contract.expiryTimestampMs) === null || contract.windowCloseTimestampMs <= contract.windowStartTimestampMs) return result('CONTRACT_INVALID');
    const clock = timestamp(nowMs), close = Math.min(contract.windowCloseTimestampMs, contract.expiryTimestampMs);
    if (clock === null) return result('CLOCK_INVALID');
    if (clock >= close) return result('EXPIRED_OR_CLOSED_NO_ROLLOVER');
    if (clock < contract.windowStartTimestampMs) return result('CONTRACT_NOT_OPEN');
    if (!isObject(snapshot) || snapshot.status !== 'VALID' || snapshot.kind !== 'TICKER') return result('VALID_TICKER_REQUIRED');
    if (snapshot.instrumentSymbol !== contract.instrumentSymbol) return result('INSTRUMENT_MISMATCH');
    const time = timestamp(snapshot.providerTimestampMs), validUntil = timestamp(snapshot.validUntilMs);
    if (time === null || time > clock || validUntil === null || validUntil < clock) return result('TIMESTAMP_INVALID_OR_STALE');
    if (time < contract.windowStartTimestampMs || time >= close) return result('OUTSIDE_SELECTED_WINDOW');
    const bid = numeric(snapshot.bid), ask = numeric(snapshot.ask), last = snapshot.last === null || snapshot.last === undefined ? null : numeric(snapshot.last);
    if (bid === null || ask === null || bid > ask || (snapshot.last !== null && snapshot.last !== undefined && last === null)) return result('QUOTE_INVALID');
    // A changed selection starts its own history. Wrong-symbol snapshots above
    // cannot clear or contaminate an existing history.
    const sameContract = existing.every(point => isObject(point) && point.instrumentSymbol === contract.instrumentSymbol);
    const points = sameContract ? existing : [];
    if (points.some((point, index) => timestamp(point.providerTimestampMs) === null
      || point.providerTimestampMs < contract.windowStartTimestampMs || point.providerTimestampMs >= close
      || numeric(point.bid) === null || numeric(point.ask) === null || Number(point.bid) > Number(point.ask)
      || (index > 0 && point.providerTimestampMs <= points[index - 1].providerTimestampMs))) return result('HISTORY_INVALID', []);
    if (points.length && time <= points[points.length - 1].providerTimestampMs) return result('TIMESTAMP_NOT_NEW', points);
    const point = {
      instrumentSymbol: contract.instrumentSymbol, providerTimestampMs: time,
      receivedAtMs: timestamp(snapshot.receivedAtMs), bid, ask, last,
      source: typeof snapshot.source === 'string' ? snapshot.source : null
    };
    return {history: points.concat(point).slice(-MAX_POINTS), appended: true, reason: null};
  }
  function buildCandles(data, intervalSeconds, expectedInstrumentSymbol) {
    // OHLC of actual source observations, never interpolated exchange candles.
    // Empty intervals stay absent. Callers must label this sampling distinction.
    if (!Array.isArray(data) || !Number.isSafeInteger(intervalSeconds) || intervalSeconds <= 0
      || typeof expectedInstrumentSymbol !== 'string' || !expectedInstrumentSymbol) return [];
    const intervalMs = intervalSeconds * 1000;
    if (!Number.isSafeInteger(intervalMs)) return [];
    const candles = [];
    let previous = null;
    for (const point of data) {
      if (!isObject(point) || point.instrumentSymbol !== expectedInstrumentSymbol) return [];
      const time = timestamp(point.providerTimestampMs), value = numeric(point.value);
      if (time === null || value === null || (previous !== null && time <= previous)) return [];
      previous = time;
      const start = Math.floor(time / intervalMs) * intervalMs;
      let candle = candles[candles.length - 1];
      if (!candle || candle.intervalStartMs !== start) {
        candle = {instrumentSymbol: expectedInstrumentSymbol, intervalStartMs: start, intervalSeconds,
          open: value, high: value, low: value, close: value, sampleCount: 1,
          firstObservationMs: time, lastObservationMs: time, origin: 'OBSERVED_SAMPLES_OHLC'};
        candles.push(candle);
      } else {
        candle.high = Math.max(candle.high, value); candle.low = Math.min(candle.low, value);
        candle.close = value; candle.sampleCount += 1; candle.lastObservationMs = time;
      }
    }
    return candles;
  }
  function money(value) {
    const number = numeric(value);
    return number === null ? '—' : new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2}).format(number);
  }
  function utc(value) {
    return timestamp(value) === null ? '—' : new Date(value).toISOString().replace('T', ' ').replace('.000Z', ' UTC');
  }
  function quoteValue(value) {
    const number = numeric(value);
    return number === null ? '—' : number.toFixed(2);
  }
  function displayTime(value, seconds) {
    return timestamp(value) === null ? '—' : new Intl.DateTimeFormat('en-GB', {timeZone: 'America/New_York',
      hour: '2-digit', minute: '2-digit', ...(seconds ? {second: '2-digit'} : {}), hourCycle: 'h23'}).format(new Date(value));
  }
  function displayDate(value) {
    return timestamp(value) === null ? '—' : new Intl.DateTimeFormat('es-US', {timeZone: 'America/New_York',
      day: 'numeric', month: 'short', year: 'numeric'}).format(new Date(value));
  }
  function wellFormedSelection(selection) {
    return isObject(selection) && selection.symbol === 'BTC/USD' && selection.operator === '>'
      && selection.horizonSeconds === 3600 && timestamp(selection.expiryTimestampMs) !== null
      && typeof selection.strike === 'string' && /^\d+(?:\.\d+)?$/.test(selection.strike)
      && Number.isFinite(Number(selection.strike)) && Number(selection.strike) > 0;
  }
  function prepareCanvas(canvas, env) {
    if (!canvas || typeof canvas.getContext !== 'function') return null;
    const context = canvas.getContext('2d');
    if (!context) return null;
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(260, rect.width || canvas.clientWidth || 600), height = Math.max(120, rect.height || canvas.clientHeight || 260);
    const ratio = Math.min(3, env.devicePixelRatio || 1);
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    return {context, width, height};
  }
  function emptyChart(canvas, env, title, detail) {
    const plot = prepareCanvas(canvas, env);
    if (!plot) return;
    const {context: c, width, height} = plot;
    // The HTML overlay owns the empty state when present. Do not draw a second
    // overlapping caption into its canvas.
    const placeholders = {'chart-main': 'main-placeholder', 'chart-15m': 'placeholder-15m', 'chart-1h': 'placeholder-1h'};
    if (canvas.id && env.document && env.document.getElementById(placeholders[canvas.id])) return;
    c.fillStyle = '#91a2af'; c.font = '14px system-ui'; c.textAlign = 'center';
    c.fillText(title, width / 2, height / 2 - 7);
    c.fillStyle = '#647b8a'; c.font = '12px system-ui'; c.fillText(detail, width / 2, height / 2 + 17);
  }
  function drawQuotes(canvas, env, points) {
    if (!points.length) return emptyChart(canvas, env, 'Sin cotizaciones válidas del contrato', 'Cotización nativa del instrumento · sin serie inventada');
    const plot = prepareCanvas(canvas, env);
    if (!plot) return;
    const {context: c, width, height} = plot;
    const box = {left: 62, right: width - 18, top: 30, bottom: height - 34};
    const values = points.flatMap(point => [point.bid, point.ask]);
    let low = Math.min(...values), high = Math.max(...values);
    const padding = Math.max((high - low) * 0.12, 0.01);
    low = Math.max(0, low - padding); high += padding;
    const first = points[0].providerTimestampMs, final = points[points.length - 1].providerTimestampMs;
    const x = time => first === final ? (box.left + box.right) / 2 : box.left + (time - first) / (final - first) * (box.right - box.left);
    const y = value => box.bottom - (value - low) / (high - low) * (box.bottom - box.top);
    c.font = '11px system-ui'; c.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const value = low + (high - low) * i / 4, position = y(value);
      c.strokeStyle = '#213340'; c.lineWidth = 1; c.beginPath(); c.moveTo(box.left, position); c.lineTo(box.right, position); c.stroke();
      c.fillStyle = '#91a2af'; c.fillText(value.toFixed(2), box.left - 9, position + 4);
    }
    [['bid', '#2fe5c6'], ['ask', '#ff697b']].forEach(([key, color]) => {
      c.strokeStyle = color; c.fillStyle = color; c.lineWidth = 2;
      c.beginPath(); points.forEach((point, index) => index ? c.lineTo(x(point.providerTimestampMs), y(point[key])) : c.moveTo(x(point.providerTimestampMs), y(point[key]))); c.stroke();
      if (points.length === 1) { c.beginPath(); c.arc(x(first), y(points[0][key]), 3, 0, Math.PI * 2); c.fill(); }
    });
    c.textAlign = 'left'; c.fillStyle = '#2fe5c6'; c.fillText('Bid', box.left, 17);
    c.fillStyle = '#ff697b'; c.fillText('Ask', box.left + 38, 17);
    const label = time => new Date(time).toISOString().slice(11, 19) + ' UTC';
    c.fillText(label(first), box.left, height - 9); c.textAlign = 'right'; c.fillText(label(final), box.right, height - 9);
  }
  function contextCandles(context, intervalSeconds, nowMs) {
    if (!isObject(context) || context.status !== 'VALID' || context.source !== 'PUBLIC_EXCHANGE'
      || context.purpose !== 'CONTEXT_ONLY_NOT_SETTLEMENT_INDEX' || context.contextOnly !== true
      || context.intervalSeconds !== intervalSeconds || !Array.isArray(context.rows)
      || timestamp(context.closingCutoffMs) === null || context.closingCutoffMs > nowMs) return [];
    const intervalMs = intervalSeconds * 1000, candles = [];
    let previous = null;
    for (const row of context.rows) {
      if (!isObject(row)) return [];
      const time = timestamp(row.openTimestampMs);
      const [open, high, low, close] = [row.open, row.high, row.low, row.close].map(numeric);
      if (time === null || Date.parse(row.time) !== time || time % intervalMs !== 0
        || time + intervalMs > context.closingCutoffMs || (previous !== null && time <= previous)
        || [open, high, low, close].some(value => value === null)
        || low > Math.min(open, close) || high < Math.max(open, close) || low > high) return [];
      previous = time;
      candles.push({intervalStartMs: time, intervalSeconds, open, high, low, close});
    }
    return candles;
  }
  function drawCandles(canvas, env, candles, intervalLabel, derived) {
    if (!candles.length) return emptyChart(canvas, env, 'Sin velas BTC de ' + intervalLabel, 'Contexto de mercado · no es el índice de liquidación');
    const plot = prepareCanvas(canvas, env);
    if (!plot) return;
    const {context: c, width, height} = plot;
    const box = {left: 63, right: width - 15, top: 27, bottom: height - 30};
    const low = Math.min(...candles.map(row => row.low)), high = Math.max(...candles.map(row => row.high));
    const padding = Math.max((high - low) * 0.1, 1), minimum = low - padding, maximum = high + padding;
    const first = candles[0].intervalStartMs, last = candles[candles.length - 1].intervalStartMs;
    const intervalMs = candles[0].intervalSeconds * 1000;
    const x = time => box.left + (time - first + intervalMs / 2) / (last - first + intervalMs) * (box.right - box.left);
    const y = value => box.bottom - (value - minimum) / (maximum - minimum) * (box.bottom - box.top);
    const bodyWidth = Math.min(12, Math.max(1, (box.right - box.left) * intervalMs / (last - first + intervalMs) * 0.6));
    c.font = '10px system-ui'; c.textAlign = 'right';
    for (let i = 0; i <= 2; i++) {
      const value = minimum + (maximum - minimum) * i / 2, position = y(value);
      c.strokeStyle = '#213340'; c.beginPath(); c.moveTo(box.left, position); c.lineTo(box.right, position); c.stroke();
      c.fillStyle = '#91a2af'; c.fillText('$' + value.toFixed(0), box.left - 7, position + 3);
    }
    candles.forEach(row => {
      const position = x(row.intervalStartMs);
      c.strokeStyle = c.fillStyle = row.close >= row.open ? '#2fe5c6' : '#ff697b';
      c.beginPath(); c.moveTo(position, y(row.high)); c.lineTo(position, y(row.low)); c.stroke();
      c.fillRect(position - bodyWidth / 2, Math.min(y(row.open), y(row.close)), bodyWidth, Math.max(1, Math.abs(y(row.close) - y(row.open))));
    });
    c.textAlign = 'left'; c.fillStyle = '#91a2af'; c.fillText('BTC spot Exchange · ' + intervalLabel + (derived ? ' agrupada de 15m' : ''), box.left, 14);
    const label = time => new Date(time).toISOString().slice(11, 16) + ' UTC';
    c.fillText(label(first), box.left, height - 9); c.textAlign = 'right'; c.fillText(label(last), box.right, height - 9);
  }
  function technicalReading(candles, strike) {
    if (!Array.isArray(candles) || candles.length < 21 || !Number.isFinite(Number(strike)) || Number(strike) <= 0
        || candles.some(c => !c || ![c.open, c.high, c.low, c.close].every(v => typeof v === 'number' && Number.isFinite(v) && v > 0))) {
      return {text: 'Datos insuficientes para una lectura técnica.', detail: '', available: false};
    }
    const closes = candles.map(c => c.close);
    const ema = n => { let value = closes[0]; for (const price of closes.slice(1)) value += 2 / (n + 1) * (price - value); return value; };
    const fast = ema(9), slow = ema(21), price = closes[closes.length - 1], target = Number(strike);
    const distance = (price / target - 1) * 100;
    const recent = candles.slice(-12), low = Math.min(...recent.map(c => c.low)), high = Math.max(...recent.map(c => c.high));
    const trend = fast > slow ? 'EMA 9 por encima de EMA 21' : fast < slow ? 'EMA 9 por debajo de EMA 21' : 'EMA 9 y EMA 21 coinciden';
    return {available: true, text: 'Último cierre ' + money(price) + ': ' + Math.abs(distance).toFixed(2) + '% ' + (distance >= 0 ? 'por encima' : 'por debajo') + ' del nivel. ' + trend + '.',
      detail: 'Rango observado en las últimas 12 velas de 5m: ' + money(low) + '–' + money(high) + '. Este rango describe el pasado.', ema9: fast, ema21: slow, distancePct: distance, low, high};
  }
  function mount(environment) {
    const env = environment || (typeof window !== 'undefined' ? window : null);
    if (!env || !env.document) return null;
    if (env.__PULSO_UI_CONTROLLER__) return env.__PULSO_UI_CONTROLLER__;
    const doc = env.document, validation = env.PulsoContractValidation;
    const ids = ['status', 'market-status', 'live-start', 'live-stop', 'refresh', 'reload-catalogue', 'catalog-status',
      'contract-form', 'symbol', 'strike', 'expiry', 'contract-choice', 'confirm-contract', 'price', 'price-source',
      'level', 'expiry-label', 'countdown', 'question', 'bid', 'ask', 'last', 'quote-time', 'yes-price', 'no-price',
      'phone-time', 'chart-main', 'chart-15m', 'chart-1h', 'chart-status', 'event-log', 'api-details',
      'main-placeholder', 'placeholder-15m', 'placeholder-1h', 'chart-note-1h', 'today', 'now', 'contract-date', 'footer-state', 'connection-error', 'technical-reading', 'technical-source'];
    const elements = {};
    ids.forEach(id => { elements[id] = doc.getElementById(id); });
    const write = (id, value) => { if (elements[id]) elements[id].textContent = value; };
    const clock = () => env.Date ? env.Date.now() : Date.now();
    const networkEnabled = env.PULSO_NETWORK_ENABLED === true;
    const phone = isObject(env.PULSO_BOOTSTRAP_PHONE) ? env.PULSO_BOOTSTRAP_PHONE : null;
    let catalogue = validation && typeof env.PULSO_BOOTSTRAP_CATALOGUE === 'string'
      ? validation.decodeCatalogue(env.PULSO_BOOTSTRAP_CATALOGUE, {evidenceKind: 'ARCHIVED_PUBLIC_CATALOGUE'}) : null;
    const observed = phone && isObject(phone.contract) ? phone.contract : {};
    let selection = {symbol: 'BTC/USD', strike: observed.visible_strike || '', operator: '>', horizonSeconds: 3600,
      expiryTimestampMs: timestamp(observed.catalogue_expiry_timestamp_ms)};
    if (typeof observed.catalogue_symbol === 'string') selection.instrumentSymbol = observed.catalogue_symbol;
    if (observed.catalogue_inst_id !== undefined) selection.instId = String(observed.catalogue_inst_id);
    if (typeof observed.catalogue_open_utc === 'string' && timestamp(Date.parse(observed.catalogue_open_utc)) !== null) selection.windowStartTimestampMs = Date.parse(observed.catalogue_open_utc);
    let client = null, feed = null, feedState = null, history = [], catalogueFromNetwork = false;
    let catalogueError = null;
    let catalogueLoading = false, catalogueAbort = null, catalogueVersion = 0, currentReadPromise = null;
    let currentMatch = null, stoppedWindowKey = null, lastLogKey = null, disposed = false;
    const listeners = [];
    const identityKey = item => [item.symbol, item.strike, item.operator, item.horizonSeconds, item.expiryTimestampMs,
      item.instrumentSymbol || '', item.instId || '', item.windowStartTimestampMs || ''].join('|');
    function listen(element, name, handler) {
      if (!element) return;
      element.addEventListener(name, handler); listeners.push(() => element.removeEventListener(name, handler));
    }
    function log(message) {
      const list = elements['event-log'];
      if (!list) return;
      const tag = /^(UL|OL)$/.test(list.tagName) ? 'li' : 'p';
      const item = doc.createElement(tag);
      item.textContent = new Date(clock()).toISOString().slice(11, 19) + ' UTC · ' + message;
      list.appendChild(item);
      while (list.children.length > 12) list.removeChild(list.firstElementChild);
    }
    function exactPhoneSelection() {
      return selection.symbol === 'BTC/USD' && String(selection.strike) === String(observed.visible_strike)
        && selection.operator === '>' && selection.expiryTimestampMs === observed.catalogue_expiry_timestamp_ms
        && (!selection.instrumentSymbol || selection.instrumentSymbol === observed.catalogue_symbol)
        && (!selection.instId || String(selection.instId) === String(observed.catalogue_inst_id));
    }
    function renderPhone() {
      const records = phone && Array.isArray(phone.observations) && exactPhoneSelection() ? phone.observations : [];
      const latest = records[records.length - 1];
      write('price', latest ? money(latest.btc_display_price) : '—');
      write('price-source', latest ? 'Captura del teléfono · ' + latest.visible_phone_clock + ' · histórica' : 'Sin precio verificado');
      write('yes-price', latest ? money(latest.yes_display_price) : '—');
      write('no-price', latest ? money(latest.no_display_price) : '—');
      write('phone-time', latest ? phone.observation_date + ' · ' + latest.visible_phone_clock
        + ' (reloj con precisión de minuto) · captura histórica. Timestamp del proveedor no disponible.'
        + (records.length > 1 ? ' Anterior: ' + records[0].visible_phone_clock + ', Sí ' + money(records[0].yes_display_price) + ', No ' + money(records[0].no_display_price) + '.' : '')
        : 'Sin captura histórica de esta selección.');
    }
    function renderCatalogue() {
      const valid = catalogue && catalogue.status === 'VALID';
      const contracts = valid ? catalogue.instruments.filter(row => row.status === 'VALID' && row.durationSeconds === 3600 && row.operator === '>' && row.expiryTimestampMs > clock()).sort((a, b) => a.expiryTimestampMs - b.expiryTimestampMs || Number(a.strike) - Number(b.strike)) : [];
      const choice = elements['contract-choice'];
      if (choice) {
        choice.textContent = '';
        const placeholder = doc.createElement('option'); placeholder.value = ''; placeholder.textContent = 'Selecciona strike y vencimiento explícitos'; choice.appendChild(placeholder);
        contracts.forEach(contract => {
          const option = doc.createElement('option'); option.value = contract.instrumentSymbol;
          option.textContent = 'BTC > ' + money(contract.strike) + ' · ' + utc(contract.expiryTimestampMs)
            + (clock() >= contract.expiryTimestampMs ? ' · vencido' : '');
          choice.appendChild(option);
        });
        choice.value = contracts.some(contract => contract.instrumentSymbol === selection.instrumentSymbol) ? selection.instrumentSymbol : '';
        choice.disabled = !networkEnabled || !contracts.length;
      }
      write('catalog-status', catalogueLoading ? 'Leyendo solo catálogo público; selección fija, sin rollover' : valid ? (catalogueFromNetwork ? 'Catálogo público leído' : 'Catálogo histórico archivado') + ' · '
        + contracts.length + ' contrato(s) BTC 1h en la página cargada · '
        + (catalogue.coverage === 'PARTIAL' ? 'cobertura parcial; unicidad global sin comprobar' : 'página cargada; unicidad global sin comprobar')
        : 'Sin catálogo validado.');
    }
    function renderForm() {
      if (elements.symbol) { elements.symbol.value = 'BTC/USD'; elements.symbol.disabled = true; }
      if (elements.strike) { elements.strike.value = selection.strike; elements.strike.readOnly = !networkEnabled; }
      if (elements.expiry) { elements.expiry.value = timestamp(selection.expiryTimestampMs) === null ? '' : new Date(selection.expiryTimestampMs).toISOString(); elements.expiry.readOnly = !networkEnabled; }
    }
    function renderDetails(entries) {
      const element = elements['api-details'];
      if (!element) return;
      if (element.tagName !== 'DETAILS') { write('api-details', entries.map(([label, value]) => label + ': ' + value).join('\n')); return; }
      let summary = Array.from(element.children).find(child => child.tagName === 'SUMMARY');
      if (!summary) { summary = doc.createElement('summary'); summary.textContent = 'Fuente y comprobaciones'; element.appendChild(summary); }
      Array.from(element.children).forEach(child => { if (child !== summary) element.removeChild(child); });
      const list = doc.createElement('dl'); list.className = 'details-list';
      entries.forEach(([label, value]) => {
        const row = doc.createElement('div'), term = doc.createElement('dt'), detail = doc.createElement('dd');
        term.textContent = label; detail.textContent = value; row.appendChild(term); row.appendChild(detail); list.appendChild(row);
      });
      element.appendChild(list);
    }
    function activeQuote(nowMs) {
      const ticker = feedState && feedState.data && feedState.data.quotes ? feedState.data.quotes.ticker : null;
      const contract = currentMatch && currentMatch.status === 'MATCHED' ? currentMatch.contract : null;
      if (!ticker || !contract || ticker.status !== 'VALID' || ticker.kind !== 'TICKER'
        || ticker.instrumentSymbol !== contract.instrumentSymbol || timestamp(ticker.validUntilMs) === null
        || nowMs > ticker.validUntilMs || timestamp(ticker.providerTimestampMs) === null || ticker.providerTimestampMs > nowMs
        || ticker.providerTimestampMs < contract.windowStartTimestampMs || ticker.providerTimestampMs >= contract.windowCloseTimestampMs) return null;
      return ticker;
    }
    function render() {
      if (disposed) return;
      const nowMs = clock();
      currentMatch = validation ? validation.matchSelectedContract(catalogue, selection, nowMs) : null;
      const elapsed = timestamp(selection.expiryTimestampMs) !== null && nowMs >= selection.expiryTimestampMs;
      const closed = currentMatch && ['EXPIRED', 'CLOSED'].includes(currentMatch.status);
      if ((elapsed || closed) && feed && stoppedWindowKey !== identityKey(selection)) {
        stoppedWindowKey = identityKey(selection); feed.stop('SELECTED_CONTRACT_EXPIRED_NO_ROLLOVER');
      }
      const quote = activeQuote(nowMs);
      write('today', displayDate(nowMs)); write('now', displayTime(nowMs, true));
      write('level', selection.strike ? money(selection.strike) : '—'); write('expiry-label', displayTime(selection.expiryTimestampMs, false) + ' ET');
      write('contract-date', displayDate(selection.expiryTimestampMs) + ' · 1 hora');
      write('countdown', formatCountdown(selection.expiryTimestampMs, nowMs));
      write('question', '¿BTC terminará por encima de ' + money(selection.strike) + ' a las ' + displayTime(selection.expiryTimestampMs, false) + ' ET?');
      const currentError = catalogueError || (feedState && feedState.lastError && feedState.lastError.message);
      write('connection-error', currentError || '');
      if (elements['connection-error']) elements['connection-error'].hidden = !currentError;
      write('status', !networkEnabled ? 'Conexión pendiente' : catalogueLoading ? 'Leyendo catálogo público' : feedState && feedState.connection === 'READING' ? 'Leyendo datos públicos'
        : feedState && feedState.following ? 'Seguimiento REST activo' : quote ? 'Lectura REST validada' : currentError ? 'Fuente no disponible' : 'Selecciona un contrato');
      write('market-status', elapsed || closed ? 'Contrato vencido o cerrado · sin rollover automático'
        : currentMatch && currentMatch.status === 'MATCHED' ? 'Metadatos coincidentes en la página cargada · sincronización App sin verificar'
        : currentMatch && currentMatch.status === 'NOT_OPEN' ? 'Ventana del contrato aún no abierta'
        : 'Selección sin coincidencia validada · no se sustituye por otro contrato');
      write('bid', quote ? quoteValue(quote.bid) : '—'); write('ask', quote ? quoteValue(quote.ask) : '—'); write('last', quote ? quoteValue(quote.last) : '—');
      write('quote-time', quote ? 'Proveedor: ' + utc(quote.providerTimestampMs) + ' · edad ' + Math.max(0, Math.floor((nowMs - quote.providerTimestampMs) / 1000))
        + ' s · cotización nativa FCM REST ticker. Bid/ask no equivalen a Sí/No de la App.' : 'Sin ticker vigente del símbolo seleccionado.');
      write('chart-status', history.length ? history.length + ' observaciones reales del mismo contrato · última: '
        + utc(history[history.length - 1].providerTimestampMs) + (quote ? '' : ' · historial; cotización vigente no disponible')
        : 'Sin historial de ticker válido para este contrato. Las capturas del teléfono no generan esta gráfica.');
      if (elements['main-placeholder']) elements['main-placeholder'].hidden = history.length > 0;
      drawQuotes(elements['chart-main'], env, history);
      const contexts = feedState && feedState.data && feedState.data.context ? feedState.data.context : {};
      const candles15m = contextCandles(contexts.m15, 900, nowMs);
      const candles5m = contextCandles(contexts.m5, 300, nowMs);
      if (candles5m.length) {
        const latest = candles5m[candles5m.length - 1];
        write('price', money(latest.close));
        write('price-source', 'BTC spot Exchange · cierre 5m ' + displayTime(latest.intervalStartMs + 300000, true) + ' ET · no índice CDNA');
        const result = technicalReading(candles5m, selection.strike);
        write('technical-reading', result.text);
        write('technical-source', 'Descripción de velas cerradas · no probabilidad del contrato. ' + result.detail);
      } else {
        renderPhone();
        write('technical-reading', 'Esperando velas verificadas de BTC/USD.');
        write('technical-source', 'La probabilidad del cierre requiere un modelo y datos de liquidación validados.');
      }
      let hourContext = contexts.m60, candles1h = contextCandles(hourContext, 3600, nowMs);
      if (!candles1h.length && env.PulsoContextAggregate && typeof env.PulsoContextAggregate.aggregateHour === 'function') {
        hourContext = env.PulsoContextAggregate.aggregateHour(contexts.m15, nowMs);
        candles1h = contextCandles(hourContext, 3600, nowMs);
      }
      const hourDerived = candles1h.length > 0 && hourContext && hourContext.derived === true;
      if (elements['placeholder-15m']) elements['placeholder-15m'].hidden = candles15m.length > 0;
      if (elements['placeholder-1h']) elements['placeholder-1h'].hidden = candles1h.length > 0;
      drawCandles(elements['chart-15m'], env, candles15m, '15 min');
      drawCandles(elements['chart-1h'], env, candles1h, '1 h', hourDerived);
      write('chart-note-1h', hourDerived ? 'Agrupada de cuatro velas reales de 15m, contiguas y cerradas · Exchange spot; no es el índice CDNA.'
        : candles1h.length ? 'Velas de 1h del contexto Exchange spot; no es el índice de liquidación CDNA.'
        : 'Sin serie de 1h comprobada. Se requieren cuatro velas reales de 15m, contiguas y cerradas.');
      renderDetails([
        ['Selección fija', selection.instrumentSymbol || 'identidad pendiente'],
        ['Vencimiento exacto', utc(selection.expiryTimestampMs) + ' · sin rollover automático'],
        ['Catálogo público DCM', catalogue && catalogue.source || 'sin fuente validada'],
        ['Alcance de coincidencia', 'Página cargada; sincronización efectiva con la App y unicidad global sin verificar'],
        ['Ticker nativo FCM', quote && quote.source || 'sin cotización vigente'],
        ['Precio BTC de cabecera', candles5m.length ? 'Último cierre spot Exchange de 5m; no índice CDNA ni precio instantáneo' : 'Sin precio actual verificado'],
        ['Contexto BTC spot', 'Exchange; velas de 15m: ' + candles15m.length + ', de 1h: ' + candles1h.length
          + (hourDerived ? ' (agrupadas de cuatro velas de 15m)' : '') + '. No es el índice de liquidación CDNA'],
        ['Índice declarado en catálogo', currentMatch && currentMatch.contract ? currentMatch.contract.underlyingSymbol + ' · serie no verificada' : 'sin candidato activo; serie no verificada'],
        ['Lectura de Roxy', 'Modelo pendiente de validación. Sin mapeo Sí/No, costes, reglas completas ni operación financiera'],
        ['Estado de conexión', (networkEnabled ? 'Lecturas públicas explícitas habilitadas' : 'Conexión pendiente; red deshabilitada en este paquete')
          + (feedState && feedState.lastError ? ' · ' + feedState.lastError.code + ': ' + feedState.lastError.message : '')]
      ]);
      write('footer-state', elapsed || closed ? 'Vencimiento fijo agotado · sin rollover · capturas del teléfono históricas'
        : !networkEnabled ? 'Conexión pendiente · capturas históricas · modelo pendiente de validación'
        : quote ? 'Cotización nativa REST validada · correspondencia Sí/No y modelo pendientes' : 'Sin cotización vigente · modelo pendiente de validación');
      ['live-start', 'refresh'].forEach(id => {
        if (elements[id]) elements[id].disabled = !networkEnabled || !feed || !wellFormedSelection(selection)
          || selection.expiryTimestampMs <= nowMs || catalogueLoading || currentReadPromise !== null
          || (feedState && (feedState.connection === 'READING' || feedState.following));
      });
      if (elements['reload-catalogue']) elements['reload-catalogue'].disabled = !networkEnabled || !client || catalogueLoading || typeof env.AbortController !== 'function';
      if (elements['live-stop']) elements['live-stop'].disabled = !networkEnabled || !feed || !(feedState && (feedState.following || feedState.connection === 'READING'));
      if (elements['confirm-contract']) elements['confirm-contract'].disabled = !networkEnabled || catalogueLoading;
    }
    function onState(state) {
      if (!isObject(state) || !isObject(state.selection) || identityKey(state.selection) !== identityKey(selection)) return;
      feedState = state;
      if (state.data && state.data.catalogue && state.data.catalogue.status === 'VALID') {
        catalogue = state.data.catalogue; catalogueFromNetwork = true; renderCatalogue();
      }
      const match = validation ? validation.matchSelectedContract(catalogue, selection, clock()) : null;
      const ticker = state.data && state.data.quotes ? state.data.quotes.ticker : null;
      if (match && match.status === 'MATCHED' && ticker) {
        const result = appendSnapshot(history, ticker, match.contract, clock());
        if (result.appended) history = result.history;
      }
      const key = state.connection + '|' + state.following + '|' + state.reason + '|' + (state.lastError && state.lastError.code || '');
      if (key !== lastLogKey) { lastLogKey = key; log(state.lastError ? state.lastError.code + ': ' + state.lastError.message : state.reason || state.connection); }
      render();
    }
    function changeSelection(next) {
      if (!validation || !wellFormedSelection(next)) { log('Selección inválida: requiere BTC/USD, strike y vencimiento UTC explícitos de 1h.'); return false; }
      cancelCatalogue(); catalogueError = null;
      if (identityKey(next) !== identityKey(selection)) { history = []; feedState = null; stoppedWindowKey = null; lastLogKey = null; }
      selection = {...next};
      if (feed) feed.setSelection(selection);
      renderForm(); renderCatalogue(); renderPhone(); render();
      log('Selección fijada; historial del contrato aislado. Sin rollover automático.');
      return true;
    }
    function submit(event) {
      if (event) event.preventDefault();
      if (!networkEnabled) return;
      const chosen = elements['contract-choice'] && elements['contract-choice'].value;
      const contract = catalogue && catalogue.status === 'VALID' ? catalogue.instruments.find(row => row.status === 'VALID' && row.instrumentSymbol === chosen && row.durationSeconds === 3600) : null;
      if (contract) return changeSelection({symbol: 'BTC/USD', strike: contract.strike, operator: '>', horizonSeconds: 3600,
        expiryTimestampMs: contract.expiryTimestampMs, instrumentSymbol: contract.instrumentSymbol, instId: contract.instId,
        windowStartTimestampMs: contract.windowStartTimestampMs});
      const value = elements.expiry ? elements.expiry.value.trim() : '';
      let time = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value) ? Date.parse(value) : null;
      if (timestamp(time) !== null && new Date(time).toISOString() !== value && new Date(time).toISOString().replace('.000Z', 'Z') !== value) time = null;
      return changeSelection({symbol: 'BTC/USD', strike: elements.strike ? elements.strike.value.trim() : '', operator: '>', horizonSeconds: 3600, expiryTimestampMs: time});
    }
    if (!validation) log('Falta el módulo de validación; lectura bloqueada.');
    if (networkEnabled && validation && env.PulsoRestFeed && typeof env.PulsoRestFeed.createRestClient === 'function'
      && typeof env.PulsoRestFeed.createReadController === 'function' && typeof env.fetch === 'function') {
      client = env.PulsoRestFeed.createRestClient({fetchImpl: env.fetch.bind(env), clock, timers: env});
      feed = env.PulsoRestFeed.createReadController({client, selection, clock, timers: env, onState, isVisible: () => !doc.hidden});
      feedState = feed.getState();
    }
    function request(method) {
      if (!networkEnabled || !feed || !wellFormedSelection(selection) || selection.expiryTimestampMs <= clock()
        || catalogueLoading || currentReadPromise !== null || (feedState && feedState.connection === 'READING')) return;
      currentReadPromise = Promise.resolve().then(() => feed[method]({userInitiated: true}))
        .catch(error => { log('Lectura detenida: ' + (error && error.message || 'error de lectura pública')); })
        .finally(() => { currentReadPromise = null; render(); });
      render();
    }
    function cancelCatalogue() {
      catalogueVersion += 1;
      if (catalogueAbort) catalogueAbort.abort();
      catalogueAbort = null; catalogueLoading = false;
    }
    async function reloadCatalogue() {
      if (!networkEnabled || !client || catalogueLoading || typeof env.AbortController !== 'function') return;
      catalogueLoading = true; catalogueError = null;
      const version = ++catalogueVersion;
      catalogueAbort = new env.AbortController();
      const signal = catalogueAbort.signal;
      if (feed) feed.stop('CATALOGUE_REFRESH');
      renderCatalogue(); render();
      try {
        const previousRead = currentReadPromise;
        if (previousRead) await previousRead;
        if (disposed || signal.aborted || version !== catalogueVersion) return;
        // This path reads catalogue metadata only, even if the old fixed
        // selection expired. It never chooses an instrument or reads quotes.
        const loaded = await client.getCatalogue({signal});
        if (disposed || signal.aborted || version !== catalogueVersion) return;
        if (!loaded || loaded.status !== 'VALID') throw new Error('Catálogo público no validado.');
        catalogue = loaded; catalogueFromNetwork = true;
        log('Catálogo actualizado; la selección y el vencimiento siguen fijos.');
      } catch (error) {
        if (!signal.aborted && version === catalogueVersion && !disposed) { catalogueError = error && error.message || 'Error de lectura pública'; catalogue = null; catalogueFromNetwork = false; log('Catálogo detenido: ' + catalogueError); }
      } finally {
        if (version === catalogueVersion) { catalogueAbort = null; catalogueLoading = false; renderCatalogue(); render(); }
      }
    }
    listen(elements['live-start'], 'click', () => request('start'));
    listen(elements.refresh, 'click', () => request('readOnce'));
    listen(elements['reload-catalogue'], 'click', reloadCatalogue);
    listen(elements['live-stop'], 'click', () => { if (networkEnabled && feed) feed.stop('USER_STOP'); });
    listen(elements['contract-form'], 'submit', submit);
    listen(elements['contract-choice'], 'change', () => {
      const chosen = elements['contract-choice'] && elements['contract-choice'].value;
      const contract = catalogue && catalogue.status === 'VALID' ? catalogue.instruments.find(row => row.status === 'VALID' && row.instrumentSymbol === chosen && row.durationSeconds === 3600 && row.operator === '>') : null;
      if (!contract) return;
      // Populate required fields before native form validation runs on submit.
      // This only edits the draft; fixing the contract remains an explicit action.
      if (elements.strike) elements.strike.value = contract.strike;
      if (elements.expiry) elements.expiry.value = new Date(contract.expiryTimestampMs).toISOString();
    });

    [elements.strike, elements.expiry].forEach(element => listen(element, 'input', () => { if (elements['contract-choice']) elements['contract-choice'].value = ''; }));
    if (elements['confirm-contract'] && elements['confirm-contract'].type !== 'submit') listen(elements['confirm-contract'], 'click', submit);
    listen(doc, 'visibilitychange', () => { if (doc.hidden) cancelCatalogue(); if (feed) feed.setVisible(!doc.hidden); renderCatalogue(); render(); });
    listen(env, 'resize', render);
    renderForm(); renderCatalogue(); renderPhone(); render();
    log(networkEnabled ? 'Listo para lecturas públicas explícitas; no se realizó ninguna al abrir.' : 'Conexión pendiente: red deshabilitada. Observaciones históricas, modelo pendiente.');
    const interval = typeof env.setInterval === 'function' ? env.setInterval(render, 1000) : null;
    const controller = Object.freeze({
      getState: () => ({selection: {...selection}, match: currentMatch, history: history.map(point => ({...point})), networkEnabled, liveFeedVerified: false}),
      dispose: () => { disposed = true; cancelCatalogue(); if (interval !== null && typeof env.clearInterval === 'function') env.clearInterval(interval); listeners.forEach(remove => remove()); if (feed) feed.dispose(); delete env.__PULSO_UI_CONTROLLER__; }
    });
    env.__PULSO_UI_CONTROLLER__ = controller;
    return controller;
  }
  return Object.freeze({formatCountdown, appendSnapshot, buildCandles, technicalReading, mount});
});
