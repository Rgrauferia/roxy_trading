/* Public REST only. Import/construction performs no request. No account or orders.
 * Requires contract-validation.js; ticker/book remain separate bid/ask snapshots.
 */
(function (root, factory) {
  'use strict';
  const validation = typeof module === 'object' && module.exports ? require('./contract-validation.js') : root.PulsoContractValidation;
  const api = factory(validation, root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PulsoRestFeed = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (validation, root) {
  'use strict';
  const ORIGIN = 'https://api.crypto.com';
  const ENDPOINTS = Object.freeze({catalogue: ORIGIN + '/dcm/v1/public/get-instruments',
    ticker: ORIGIN + '/fcm/v1/public/get-tickers', book: ORIGIN + '/fcm/v1/public/get-book',
    candles: ORIGIN + '/exchange/v1/public/get-candlestick'});
  const FRAMES = Object.freeze({300: '5m', 900: '15m'});
  const flags = () => ({execution_allowed: false, actionable: false, yesNoMappingVerified: false,
    costMappingVerified: false, settlementReferenceVerified: false});
  class FeedError extends Error {
    constructor(code, message, httpStatus) { super(message); this.name = 'FeedError'; this.code = code; if (httpStatus !== undefined) this.httpStatus = httpStatus; }
  }
  const fail = (code, message, httpStatus) => { throw new FeedError(code, message, httpStatus); };
  function clockMs(clock) {
    const now = clock();
    if (!Number.isSafeInteger(now) || now <= 0 || now > 8640000000000000) fail('INVALID_CLOCK', 'Se requiere un reloj exacto en ms.');
    return now;
  }
  function milliseconds(value, fallback, minimum, maximum) {
    if (value === undefined) return fallback;
    if (!Number.isSafeInteger(value) || value < minimum || value > maximum) fail('INVALID_INTERVAL', 'Intervalo fuera de límites.');
    return value;
  }
  function timersFor(input) {
    const source = input || root;
    const timers = {};
    for (const key of ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval']) {
      if (typeof source[key] !== 'function') fail('TIMERS_REQUIRED', 'Faltan temporizadores.');
      timers[key] = source[key].bind(source);
    }
    return timers;
  }
  function requireValidation() {
    if (!validation || typeof validation.parseExactJSON !== 'function' || typeof validation.matchSelectedContract !== 'function') fail('VALIDATION_REQUIRED', 'Carga primero contract-validation.js.');
  }
  function exactSymbol(value) {
    if (typeof value !== 'string' || !/^NX\.F\.OPT\.BTC\.I\.\d+\.\d+\.\d{8}$/.test(value)) fail('INVALID_SYMBOL', 'Se requiere el símbolo CDNA BTC exacto.');
    return value;
  }
  function numeric(value) {
    if (typeof value !== 'number' && (typeof value !== 'string' || !/^\d+(?:\.\d+)?$/.test(value))) fail('CANDLES_INVALID', 'OHLCV ausente o inválido.');
    const number = Number(value);
    if (!Number.isFinite(number)) fail('CANDLES_INVALID', 'OHLCV no finito.');
    return number;
  }
  function decodeCandles(payload, intervalSeconds, requestedAtMs, receivedAtMs) {
    clockMs(() => requestedAtMs); clockMs(() => receivedAtMs);
    if (receivedAtMs < requestedAtMs) fail('INVALID_CLOCK', 'El reloj retrocedió durante la lectura.');
    const interval = FRAMES[intervalSeconds], result = payload && payload.result;
    if (!interval || !payload || payload.code !== 0 || payload.method !== 'public/get-candlestick' || !result || result.instrument_name !== 'BTC_USD' || result.interval !== interval || !Array.isArray(result.data) || result.data.length < 21 || result.data.length > 300) fail('CANDLES_INVALID', 'Respuesta Exchange, instrumento o intervalo incorrecto.');
    const width = intervalSeconds * 1000;
    const all = result.data.map(row => {
      if (!row || !Number.isSafeInteger(row.t) || row.t <= 0 || row.t % width || row.t > requestedAtMs) fail('CANDLES_INVALID', 'Timestamp ms no alineado o futuro.');
      const open = numeric(row.o), high = numeric(row.h), low = numeric(row.l), close = numeric(row.c), volume = numeric(row.v);
      if (Math.min(open, high, low, close) <= 0 || volume < 0 || high < Math.max(open, low, close) || low > Math.min(open, high, close)) fail('CANDLES_INVALID', 'Geometría OHLCV incorrecta.');
      return {time: new Date(row.t).toISOString(), openTimestampMs: row.t, open, high, low, close, volume};
    }).sort((a, b) => a.openTimestampMs - b.openTimestampMs);
    for (let index = 1; index < all.length; index++) if (all[index].openTimestampMs - all[index - 1].openTimestampMs !== width) fail('CANDLES_INVALID', 'Velas duplicadas o huecos de cadencia.');
    // Freeze closed status at request start: crossing a boundary during GET
    // cannot turn its partial last candle into a final candle.
    const rows = all.filter(row => row.openTimestampMs + width <= requestedAtMs);
    const latest = rows.length ? rows[rows.length - 1].openTimestampMs : null;
    if (rows.length < 21 || latest !== Math.floor(receivedAtMs / width) * width - width) fail('STALE_CONTEXT', 'Falta la última vela cerrada; se necesita otra lectura.');
    return {status: 'VALID', source: 'PUBLIC_EXCHANGE', sourceURL: ENDPOINTS.candles,
      symbol: 'BTC/USD', instrumentSymbol: 'BTC_USD', intervalSeconds, rows,
      requestedAtMs, receivedAtMs, closingCutoffMs: requestedAtMs,
      latestClosedOpenTimestampMs: latest, providerTimestampMs: null,
      validUntilMs: latest + 2 * width, purpose: 'CONTEXT_ONLY_NOT_SETTLEMENT_INDEX',
      contextOnly: true, ...flags()};
  }
  function createRestClient(options) {
    options = options || {}; requireValidation();
    const fetchImpl = options.fetchImpl || (typeof root.fetch === 'function' ? root.fetch.bind(root) : null);
    if (typeof fetchImpl !== 'function') fail('FETCH_REQUIRED', 'No hay cliente fetch.');
    const clock = options.clock || Date.now, timers = timersFor(options.timers);
    const timeoutMs = milliseconds(options.timeoutMs, 8000, 1, 60000);
    const maxQuoteAgeMs = milliseconds(options.maxQuoteAgeMs, 60000, 1, 60000);
    const Abort = options.AbortController || root.AbortController;
    if (typeof Abort !== 'function') fail('ABORT_REQUIRED', 'Falta AbortController.');
    async function request(url, signal) {
      const requestedAtMs = clockMs(clock), controller = new Abort();
      let rejectCancellation, timeout;
      const cancellation = new Promise((_, reject) => { rejectCancellation = reject; });
      const cancel = error => { controller.abort(); rejectCancellation(error); };
      const externalAbort = () => cancel(new FeedError('ABORTED', 'Lectura cancelada.'));
      if (signal && signal.aborted) fail('ABORTED', 'Lectura cancelada.');
      if (signal) signal.addEventListener('abort', externalAbort, {once: true});
      timeout = timers.setTimeout(() => cancel(new FeedError('TIMEOUT', 'La lectura pública superó el tiempo límite.')), timeoutMs);
      try {
        const transport = (async () => {
          const response = await fetchImpl(url, {method: 'GET', credentials: 'omit', redirect: 'error', cache: 'no-store', signal: controller.signal});
          if (!response || response.status !== 200) fail('HTTP_ERROR', response && response.status === 403 ? 'El proveedor rechazó el acceso público (403). Seguimiento detenido; puedes usar la revisión manual.' : 'No se pudo leer el proveedor público (HTTP ' + (response && response.status || 'desconocido') + ').', response && response.status);
          if (response.redirected === true || (response.url && response.url !== url)) fail('REDIRECT_REJECTED', 'Se rechaza una respuesta redirigida.');
          const raw = await response.text();
          if (typeof raw !== 'string' || raw.length === 0 || raw.length > 5000000) fail('INVALID_JSON', 'Respuesta pública fuera del límite de tamaño.');
          const receivedAtMs = clockMs(clock);
          if (receivedAtMs < requestedAtMs) fail('INVALID_CLOCK', 'El reloj retrocedió durante la lectura.');
          return {raw, source: url, requestedAtMs, receivedAtMs,
            sourceServerDate: response.headers && typeof response.headers.get === 'function' ? response.headers.get('date') : null};
        })();
        return await Promise.race([transport, cancellation]);
      } catch (error) {
        if (error instanceof FeedError) throw error;
        fail(controller.signal.aborted ? 'ABORTED' : 'NETWORK_ERROR', 'No se pudo completar la lectura pública.');
      } finally {
        timers.clearTimeout(timeout);
        if (signal) signal.removeEventListener('abort', externalAbort);
      }
    }
    async function getCatalogue(input) {
      const filter = input && input.instrumentSymbol ? '&symbols=' + encodeURIComponent(exactSymbol(input.instrumentSymbol)) : '';
      const receipt = await request(ENDPOINTS.catalogue + '?inst_type=BINARY_OPTION&limit=1000' + filter, input && input.signal);
      const result = validation.decodeCatalogue(receipt.raw, {source: receipt.source, receivedAtMs: receipt.receivedAtMs, evidenceKind: 'PUBLIC_REST_READ'});
      if (result.status !== 'VALID') fail('CATALOGUE_INVALID', 'El catálogo público no pasó la validación.');
      return {...result, requestedAtMs: receipt.requestedAtMs, sourceServerDate: receipt.sourceServerDate};
    }
    async function quote(kind, input) {
      input = input || {};
      const symbol = exactSymbol(input.instrumentSymbol), name = kind === 'TICKER' ? 'ticker' : 'book';
      const url = ENDPOINTS[name] + '?instrument_name=' + encodeURIComponent(symbol) + (kind === 'BOOK' ? '&depth=1' : '');
      const receipt = await request(url, input.signal);
      const result = validation.normalizeQuoteSnapshot(receipt.raw, {kind, source: receipt.source,
        expectedInstrumentSymbol: symbol, receivedAtMs: receipt.receivedAtMs, maxAgeMs: maxQuoteAgeMs, allowOneSided: options.allowOneSided === true}, receipt.receivedAtMs);
      if (result.status !== 'VALID') fail(result.status === 'STALE' ? 'STALE_SNAPSHOT' : 'QUOTE_INVALID', 'El snapshot no pasó identidad, tiempo o bid/ask.');
      return {...result, requestedAtMs: receipt.requestedAtMs, sourceServerDate: receipt.sourceServerDate};
    }
    async function getIndex(input) {
      input = input || {};
      // Only the exact declared BTC CDNA index; never substitute Exchange spot.
      const instrument = 'BTCUSD-INDEX@CdnaFunded';
      if (input.underlyingSymbol !== instrument) return {status:'UNAVAILABLE',reason:'DECLARED_INDEX_UNSUPPORTED'};
      const receipt = await request(ENDPOINTS.ticker + '?instrument_name=' + encodeURIComponent(instrument), input.signal);
      let payload; try { payload=JSON.parse(receipt.raw); } catch (_) { return {status:'UNAVAILABLE',reason:'INDEX_RESPONSE_INVALID'}; }
      const rows = payload && payload.result && payload.result.data;
      if (payload.code !== 0 || payload.method !== 'public/get-tickers' || !Array.isArray(rows) || rows.length !== 1) return {status:'UNAVAILABLE',reason:'NO_PUBLIC_INDEX_TICKER'};
      const row=rows[0], value=row && row.a;
      const price=(typeof value==='number' || typeof value==='string' && /^\d+(?:\.\d+)?$/.test(value)) ? Number(value) : null;
      const now=receipt.receivedAtMs;
      if (!row || row.i!==instrument || !Number.isSafeInteger(row.t) || row.t>now || now-row.t>60000 || !(price>0) || !Number.isFinite(price)) return {status:'UNAVAILABLE',reason:'INDEX_NOT_FRESH_OR_IDENTIFIED'};
      return {status:'VALID',instrumentSymbol:instrument,price,providerTimestampMs:row.t,validUntilMs:row.t+60000,source:receipt.source,receivedAtMs:now};
    }
    async function getCandles(input) {
      input = input || {};
      const interval = FRAMES[input.intervalSeconds];
      if (!interval) fail('INVALID_INTERVAL', 'Se admiten velas de 5 o 15 minutos.');
      const receipt = await request(ENDPOINTS.candles + '?instrument_name=BTC_USD&timeframe=' + interval + '&count=300', input.signal);
      let payload;
      try { payload = JSON.parse(receipt.raw); } catch (_) { fail('INVALID_JSON', 'JSON Exchange inválido.'); }
      return {...decodeCandles(payload, input.intervalSeconds, receipt.requestedAtMs, receipt.receivedAtMs), sourceURL: receipt.source, sourceServerDate: receipt.sourceServerDate};
    }
    return Object.freeze({...(options.includeUnderlyingIndex === true ? {getIndex} : {}),getCatalogue, getTicker: input => quote('TICKER', input), getBook: input => quote('BOOK', input), getCandles});
  }
  function createReadController(options) {
    options = options || {}; requireValidation();
    const client = options.client;
    if (!client || ['getCatalogue', 'getTicker', 'getBook', 'getCandles'].some(name => typeof client[name] !== 'function')) fail('CLIENT_REQUIRED', 'Se requiere el cliente REST público.');
    const clock = options.clock || Date.now, timers = timersFor(options.timers);
    const pollMs = milliseconds(options.pollMs, 10000, 10000, 3600000);
    const Abort = options.AbortController || root.AbortController;
    if (typeof Abort !== 'function') fail('ABORT_REQUIRED', 'Falta AbortController.');
    const clone = value => JSON.parse(JSON.stringify(value));
    let selection = options.selection ? clone(options.selection) : null;
    let visible = typeof options.isVisible === 'function' ? Boolean(options.isVisible()) : !(root.document && root.document.hidden);
    let state = {connection: 'DISCONNECTED', following: false, mode: null, reason: 'NOT_STARTED', selection,
      match: null, data: null, lastError: null, ...flags()};
    let generation = 0, active = null, pollTimer = null, guardTimer = null, deadlineTimer = null, disposed = false, knownWindowCloseMs = null;
    const publish = () => { if (typeof options.onState === 'function') { try { options.onState(clone(state)); } catch (_) { /* A view callback cannot authorize or restart requests. */ } } };
    function clearTimers() {
      if (pollTimer !== null) timers.clearInterval(pollTimer);
      if (guardTimer !== null) timers.clearInterval(guardTimer);
      if (deadlineTimer !== null) timers.clearTimeout(deadlineTimer);
      pollTimer = guardTimer = deadlineTimer = null;
    }
    function stop(reason) {
      generation++; clearTimers();
      if (active) active.abort.abort();
      active = null; knownWindowCloseMs = null;
      state = {...state, connection: 'DISCONNECTED', following: false, mode: null,
        reason: reason || 'USER_STOP', match: null, data: null};
      publish(); return clone(state);
    }
    function disconnect(error) {
      const result = {code: error && error.code || 'READ_ERROR', message: error && error.message || 'Lectura pública incorrecta.'};
      if (error && error.httpStatus !== undefined) result.httpStatus = error.httpStatus;
      state.lastError = result; return stop(result.code);
    }
    function guard() {
      if (state.connection === 'DISCONNECTED') return;
      try {
        const now = clockMs(clock);
        if (typeof options.isVisible === 'function') visible = Boolean(options.isVisible());
        if (!visible) { stop('HIDDEN'); return; }
        if (selection && now >= selection.expiryTimestampMs) { stop('EXPIRED'); return; }
        if (knownWindowCloseMs !== null && now >= knownWindowCloseMs) { stop('CLOSED'); return; }
        if (state.data && [state.data.quotes.ticker, state.data.quotes.book].some(row => now > row.validUntilMs)) { stop('STALE_SNAPSHOT'); return; }
        if (state.data && [state.data.context.m5, state.data.context.m15].some(row => now >= row.validUntilMs)) stop('STALE_CONTEXT');
      } catch (error) { disconnect(error); }
    }
    function armGuards() {
      if (guardTimer === null) guardTimer = timers.setInterval(guard, 1000);
      if (deadlineTimer !== null) timers.clearTimeout(deadlineTimer);
      const end = knownWindowCloseMs !== null ? Math.min(selection.expiryTimestampMs, knownWindowCloseMs) : selection.expiryTimestampMs;
      deadlineTimer = timers.setTimeout(guard, Math.max(0, end - clockMs(clock)));
    }
    function getState() { guard(); return clone(state); }
    async function runCycle() {
      guard();
      if (disposed || !visible || active) return getState();
      const currentSelection = selection ? clone(selection) : null;
      let preflight;
      try { preflight = validation.matchSelectedContract({status: 'VALID', instruments: [], coverage: 'PARTIAL'}, currentSelection, clockMs(clock)); }
      catch (error) { return disconnect(error); }
      if (preflight.status === 'INVALID' || preflight.status === 'EXPIRED') return disconnect(new FeedError(preflight.status, 'Selección fija inválida o vencida.'));
      const token = generation, abort = new Abort();
      active = {abort, token};
      state = {...state, connection: 'READING', data: null, match: null, reason: 'READ_REQUESTED', lastError: null};
      armGuards(); publish();
      const assertCurrent = () => {
        if (token !== generation || abort.signal.aborted) fail('ABORTED', 'Lectura cancelada.');
        guard();
        if (token !== generation || abort.signal.aborted) fail('ABORTED', 'Lectura cancelada.');
      };
      try {
        const catalogue = await client.getCatalogue({instrumentSymbol: selection.instrumentSymbol, signal: abort.signal}); assertCurrent();
        let match = validation.matchSelectedContract(catalogue, currentSelection, clockMs(clock));
        if (match.status !== 'MATCHED') fail(match.status, 'El contrato seleccionado no está confirmado y abierto en esta página.');
        state.match = match; knownWindowCloseMs = match.contract.windowCloseTimestampMs; armGuards();
        const instrumentSymbol = match.contract.instrumentSymbol;
        const ticker = await client.getTicker({instrumentSymbol, signal: abort.signal}); assertCurrent();
        const book = await client.getBook({instrumentSymbol, signal: abort.signal}); assertCurrent();
        const index = typeof client.getIndex === 'function' ? await client.getIndex({underlyingSymbol:match.contract.underlyingSymbol,signal:abort.signal}) : {status:'UNAVAILABLE',reason:'NOT_REQUESTED'}; assertCurrent();
        const m5 = await client.getCandles({intervalSeconds: 300, signal: abort.signal}); assertCurrent();
        const m15 = await client.getCandles({intervalSeconds: 900, signal: abort.signal}); assertCurrent();
        const now = clockMs(clock);
        match = validation.matchSelectedContract(catalogue, currentSelection, now);
        if (match.status !== 'MATCHED') fail(match.status, 'La ventana seleccionada dejó de estar abierta.');
        const quoteWindowEnd = Math.min(match.contract.windowCloseTimestampMs, match.contract.expiryTimestampMs);
        for (const row of [ticker, book]) {
          if (row.status !== 'VALID' || row.instrumentSymbol !== instrumentSymbol || !Number.isSafeInteger(row.providerTimestampMs) || row.providerTimestampMs > now || now > row.validUntilMs) fail('STALE_OR_WRONG_QUOTE', 'El snapshot no es vigente para el contrato exacto.');
          if (row.providerTimestampMs < match.contract.windowStartTimestampMs || row.providerTimestampMs >= quoteWindowEnd) fail('QUOTE_OUTSIDE_SELECTED_WINDOW', 'El timestamp del snapshot queda fuera de la apertura y cierre del contrato seleccionado.');
        }
        for (const row of [m5, m15]) if (row.status !== 'VALID' || row.purpose !== 'CONTEXT_ONLY_NOT_SETTLEMENT_INDEX' || now >= row.validUntilMs) fail('STALE_CONTEXT', 'El contexto Exchange dejó de estar vigente.');
        state = {...state, connection: 'CONNECTED', reason: 'PUBLIC_REST_SNAPSHOTS', match,
          data: {catalogue, quotes: {ticker, book}, index, context: {m5, m15}, receivedAtMs: now,
            snapshotCoherence: 'EACH_RESPONSE_SEPARATE_NOT_SIMULTANEOUS', mappedYesNo: null, ...flags()}};
        armGuards(); publish(); return clone(state);
      } catch (error) {
        if (token !== generation) return clone(state);
        return disconnect(error);
      } finally { if (active && active.token === token) active = null; }
    }
    function authorize(input) {
      if (disposed) { disconnect(new FeedError('DISPOSED', 'El controlador está cerrado.')); return false; }
      if (!input || input.userInitiated !== true) { disconnect(new FeedError('USER_ACTION_REQUIRED', 'Inicia la lectura mediante una acción explícita.')); return false; }
      if (typeof options.isVisible === 'function') visible = Boolean(options.isVisible());
      if (!visible) { stop('HIDDEN'); return false; }
      return true;
    }
    async function readOnce(input) {
      if (!authorize(input) || active) return getState();
      state.mode = state.following ? 'POLLING' : 'MANUAL';
      return runCycle();
    }
    async function start(input) {
      if (!authorize(input) || state.following || active) return getState();
      state.following = true; state.mode = 'POLLING';
      pollTimer = timers.setInterval(() => { if (state.following && !active) void runCycle(); }, pollMs);
      return runCycle();
    }
    function setSelection(value) { stop('SELECTION_CHANGED'); selection = value ? clone(value) : null; state.selection = selection; state.lastError = null; publish(); return clone(state); }
    function setVisible(value) { visible = value === true; if (!visible) return stop('HIDDEN'); return getState(); }
    const onVisibility = () => setVisible(!root.document.hidden);
    if (!options.isVisible && root.document && typeof root.document.addEventListener === 'function') root.document.addEventListener('visibilitychange', onVisibility);
    function dispose() {
      disposed = true;
      if (!options.isVisible && root.document && typeof root.document.removeEventListener === 'function') root.document.removeEventListener('visibilitychange', onVisibility);
      return stop('DISPOSED');
    }
    return Object.freeze({readOnce, start, stop, setSelection, setVisible, getState, dispose});
  }
  return Object.freeze({ENDPOINTS, FeedError, decodeCandles, createRestClient, createReadController});
});
