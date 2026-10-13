/* Pure Pulso data matching. No fetch, account, order or model probability.
 * Catalogue times: OPEN/CLOSE are UTC strings; expiry is ms; metadata update is ns.
 * The selected expiry is immutable input. NO_MATCH never rolls to another hour.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PulsoContractValidation = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const NS_KEY = /("last_updated_time"\s*:\s*)(\d+)(?=\s*[,}])/g;
  const ISO = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?(Z|[+-]\d{2}:\d{2})$/;
  const FIX_UTC = /^(\d{4})(\d{2})(\d{2})-(\d{2}):(\d{2}):(\d{2})\.(\d{3})$/;
  const CATALOGUE_PATH = '/dcm/v1/public/get-instruments';
  const QUOTE_PATHS = {TICKER: '/fcm/v1/public/get-tickers', BOOK: '/fcm/v1/public/get-book'};
  const flags = () => ({execution_allowed: false, actionable: false, yesNoMappingVerified: false, costMappingVerified: false});
  const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const issue = (code, field, message) => ({code, field, message});
  const nonempty = value => typeof value === 'string' && value.trim().length > 0;
  function ms(value) { return typeof value === 'number' && Number.isSafeInteger(value) && value > 0 && value <= 8640000000000000 ? value : null; }
  function decimal(value) {
    if (typeof value === 'number') { if (!Number.isFinite(value)) return null; value = String(value); }
    if (typeof value !== 'string' || !/^\d+(?:\.\d+)?$/.test(value)) return null;
    const parts = value.split('.');
    const integer = parts[0].replace(/^0+(?=\d)/, '');
    const fraction = (parts[1] || '').replace(/0+$/, '');
    return fraction ? integer + '.' + fraction : integer;
  }
  function positiveDecimal(value) { const result = decimal(value); return result !== null && result !== '0' ? result : null; }
  function dateParts(year, month, day, hour, minute, second, millis) {
    const values = [year, month, day, hour, minute, second, millis].map(Number);
    const [y, mo, d, h, mi, s, milli] = values;
    if (y < 1970 || mo < 1 || mo > 12 || d < 1 || h > 23 || mi > 59 || s > 59 || milli > 999) return null;
    const result = Date.UTC(y, mo - 1, d, h, mi, s, milli);
    const check = new Date(result);
    if (check.getUTCFullYear() !== y || check.getUTCMonth() !== mo - 1 || check.getUTCDate() !== d) return null;
    return result;
  }
  function utcSlot(value) {
    if (typeof value !== 'string') return null;
    const match = FIX_UTC.exec(value);
    return match ? dateParts(...match.slice(1)) : null;
  }
  function awareTime(value) {
    if (typeof value !== 'string') return null;
    const match = ISO.exec(value);
    if (!match || dateParts(match[1], match[2], match[3], match[4], match[5], match[6] || '0', (match[7] || '').padEnd(3, '0') || '0') === null) return null;
    const result = Date.parse(value);
    return ms(result);
  }
  function sourceURL(value, expectedPath) {
    if (!nonempty(value)) return null;
    try {
      const url = new URL(value);
      return url.origin === 'https://api.crypto.com' && !url.username && !url.password && url.pathname === expectedPath ? url.href : null;
    } catch (_) { return null; }
  }
  function parseExactJSON(raw) {
    if (typeof raw !== 'string' || raw.length === 0 || raw.length > 5000000) throw new Error('Se necesita JSON crudo dentro del límite de tamaño.');
    // Match only the literal known numeric property. Escaped occurrences inside
    // JSON text cells have escaped closing quotes and cannot match this key.
    return JSON.parse(raw.replace(NS_KEY, (_, prefix, digits) => prefix + JSON.stringify(digits)));
  }
  function nanoseconds(value) {
    if (typeof value === 'string' && /^\d+$/.test(value)) return {value, exact: true, reason: null};
    if (typeof value === 'bigint' && value >= 0n) return {value: String(value), exact: true, reason: null};
    if (typeof value === 'number' && Number.isSafeInteger(value) && value >= 0) return {value: String(value), exact: true, reason: null};
    return {value: null, exact: false, reason: typeof value === 'number' ? 'UNSAFE_OR_INVALID_NUMBER_ALREADY_PARSED' : 'MISSING_OR_INVALID_NANOSECONDS'};
  }
  function normalizeInstrument(raw) {
    const errors = [], warnings = [];
    if (!isObject(raw)) return {status: 'INVALID', errors: [issue('INSTRUMENT_REQUIRED', 'instrument', 'Falta el instrumento.')], warnings, ...flags()};
    const attributes = isObject(raw.event_details) && isObject(raw.event_details.attributes) ? raw.event_details.attributes : {};
    const strike = positiveDecimal(attributes.STRIKE_PRICE);
    const opened = utcSlot(attributes.OPEN_TIME), closed = utcSlot(attributes.CLOSE_TIME);
    const expiry = ms(raw.expiry_timestamp_ms);
    const id = typeof raw.inst_id === 'string' && /^\d+$/.test(raw.inst_id) && !/^0+$/.test(raw.inst_id) ? raw.inst_id : Number.isSafeInteger(raw.inst_id) && raw.inst_id > 0 ? String(raw.inst_id) : null;
    if (!nonempty(raw.symbol) || id === null) errors.push(issue('EXACT_IDENTITY_REQUIRED', 'symbol/inst_id', 'Faltan symbol e inst_id exactos.'));
    if (raw.base_ccy !== 'BTC' || raw.quote_ccy !== 'USD' || raw.inst_type !== 'BINARY_OPTION' || raw.security_sub_type !== 'BINARY_OPTION') errors.push(issue('NOT_BTC_USD_BINARY', 'instrument', 'Se requiere un instrumento BTC/USD BINARY_OPTION explícito.'));
    if (strike === null) errors.push(issue('NUMERIC_STRIKE_REQUIRED', 'event_details.attributes.STRIKE_PRICE', 'Falta strike numérico; STRIKE_INDEX o display_name no lo sustituyen.'));
    if (attributes.STRIKE_OPERATOR !== '>') errors.push(issue('OPERATOR_UNSUPPORTED', 'STRIKE_OPERATOR', 'Este matcher admite únicamente el operador > exacto.'));
    if (opened === null || closed === null || closed <= opened) errors.push(issue('UTC_WINDOW_REQUIRED', 'OPEN_TIME/CLOSE_TIME', 'Falta una ventana UTC válida.'));
    if (expiry === null || (closed !== null && expiry < closed)) errors.push(issue('EXPIRY_REQUIRED', 'expiry_timestamp_ms', 'El vencimiento debe ser ms exactos y no anterior al cierre.'));
    if (!nonempty(raw.underlying_symbol)) errors.push(issue('UNDERLYING_REQUIRED', 'underlying_symbol', 'Falta el identificador de subyacente.'));
    const updated = nanoseconds(raw.last_updated_time);
    if (!updated.exact) warnings.push(issue('NS_PRECISION_UNVERIFIED', 'last_updated_time', 'No se conserva precisión exacta del timestamp ns de metadatos.'));
    return {
      status: errors.length ? 'INVALID' : 'VALID', errors, warnings,
      instrumentSymbol: nonempty(raw.symbol) ? raw.symbol : null, instId: id, symbol: 'BTC/USD',
      strike, operator: attributes.STRIKE_OPERATOR || null,
      windowStartTimestampMs: opened, windowCloseTimestampMs: closed,
      durationSeconds: opened !== null && closed !== null ? (closed - opened) / 1000 : null,
      expiryTimestampMs: expiry, underlyingSymbol: raw.underlying_symbol || null,
      lastUpdatedTimeNs: updated.value, lastUpdatedTimeNsExact: updated.exact,
      tradable: raw.tradable === true,
      contractSize: decimal(raw.contract_size), priceTickSize: positiveDecimal(raw.price_tick_size), quantityTickSize: positiveDecimal(raw.qty_tick_size),
      settlementReferenceVerified: false, tieRuleVerified: false,
      ...flags()
    };
  }
  function decodeCatalogue(input, options) {
    options = isObject(options) ? options : {};
    let payload;
    try { payload = typeof input === 'string' ? parseExactJSON(input) : input; }
    catch (_) { return {status: 'INVALID', errors: [issue('INVALID_JSON', 'catalogue', 'JSON de catálogo inválido.')], instruments: [], ...flags()}; }
    if (!isObject(payload)) return {status: 'INVALID', errors: [issue('CATALOGUE_REQUIRED', 'catalogue', 'Falta el catálogo.')], instruments: [], ...flags()};
    const source = sourceURL(options.source || payload.source, CATALOGUE_PATH);
    const envelope = Array.isArray(payload.data) && payload.api_code === 0 && payload.http_status === 200;
    const body = envelope ? payload : payload.response || payload;
    const success = envelope || (body.code === 0 && body.method === 'public/get-instruments' && isObject(body.result));
    const rows = envelope ? payload.data : isObject(body.result) ? body.result.data : null;
    const errors = [];
    if (!source) errors.push(issue('CATALOGUE_SOURCE_REQUIRED', 'source', 'Se requiere origen público DCM exacto.'));
    if (payload.http_status !== undefined && payload.http_status !== 200) errors.push(issue('CATALOGUE_HTTP_ERROR', 'http_status', 'La respuesta HTTP archivada no fue correcta.'));
    if (!success || !Array.isArray(rows) || rows.length > 1000) errors.push(issue('CATALOGUE_INVALID', 'data', 'Respuesta de catálogo ausente o incorrecta.'));
    if (errors.length) return {status: 'INVALID', errors, instruments: [], ...flags()};
    const nextCursor = envelope ? payload.next_cursor || null : body.result.next_cursor || null;
    return {
      status: 'VALID', errors: [], source,
      evidenceKind: options.evidenceKind || 'PUBLIC_READ_ONLY_SNAPSHOT',
      instruments: rows.map(normalizeInstrument),
      coverage: payload.has_next_cursor === true || Boolean(nextCursor) ? 'PARTIAL' : 'LOADED_PAGE_NO_CURSOR', nextCursor,
      receivedAtMs: ms(options.receivedAtMs), sourceServerDate: payload.response_server_date || null,
      ...flags()
    };
  }
  function matchSelectedContract(catalogue, selection, nowMs) {
    const errors = [], warnings = [];
    const clock = ms(nowMs === undefined ? Date.now() : nowMs);
    const expiry = isObject(selection) ? ms(selection.expiryTimestampMs) : null;
    const strike = isObject(selection) ? positiveDecimal(selection.strike) : null;
    if (!isObject(selection) || selection.symbol !== 'BTC/USD' || selection.operator !== '>' || selection.horizonSeconds !== 3600 || expiry === null || strike === null) errors.push(issue('FIXED_SELECTION_REQUIRED', 'selection', 'Declara BTC/USD, >, strike, 3600 s y vencimiento fijo exacto.'));
    if (clock === null) errors.push(issue('INVALID_CLOCK', 'nowMs', 'Falta un reloj exacto en ms.'));
    if (!isObject(catalogue) || catalogue.status !== 'VALID' || !Array.isArray(catalogue.instruments)) errors.push(issue('CATALOGUE_NOT_VALID', 'catalogue', 'El catálogo no está validado.'));
    const base = {errors, warnings, selectedExpiryTimestampMs: expiry, remainingSeconds: expiry !== null && clock !== null ? Math.max(0, (expiry - clock) / 1000) : null, candidates: [], contract: null, matchKind: 'EXACT_SELECTED_FIELDS_NOT_APP_SYNC', uniquenessScope: 'LOADED_PAGE', fullCatalogueUniquenessVerified: false, ...flags()};
    if (errors.length) return {status: 'INVALID', ...base};
    const candidates = catalogue.instruments.filter(row => row.status === 'VALID' && row.symbol === 'BTC/USD' && row.operator === '>' && row.strike === strike && row.durationSeconds === 3600 && row.expiryTimestampMs === expiry
      && (selection.instrumentSymbol === undefined || selection.instrumentSymbol === row.instrumentSymbol)
      && (selection.instId === undefined || String(selection.instId) === row.instId)
      && (selection.windowStartTimestampMs === undefined || selection.windowStartTimestampMs === row.windowStartTimestampMs));
    base.candidates = candidates;
    if (clock >= expiry) return {status: 'EXPIRED', ...base, reason: 'SELECTED_CONTRACT_EXPIRED_NO_ROLLOVER'};
    if (candidates.length === 0) return {status: 'NO_MATCH', ...base, coverage: catalogue.coverage, reason: catalogue.coverage === 'PARTIAL' ? 'NO_MATCH_IN_LOADED_PAGE' : 'NO_MATCH_IN_LOADED_CATALOGUE'};
    if (candidates.length > 1) return {status: 'AMBIGUOUS', ...base, reason: 'MULTIPLE_EXACT_CANDIDATES'};
    const contract = candidates[0];
    base.warnings.push(...contract.warnings);
    if (clock < contract.windowStartTimestampMs) return {status: 'NOT_OPEN', ...base, contract, reason: 'SELECTED_WINDOW_NOT_OPEN'};
    if (clock >= contract.windowCloseTimestampMs) return {status: 'CLOSED', ...base, contract, reason: 'SELECTED_TRADING_WINDOW_CLOSED'};
    if (!contract.tradable) return {status: 'NOT_TRADABLE', ...base, contract, reason: 'CATALOGUE_TRADABLE_FALSE'};
    return {status: 'MATCHED', ...base, contract, coverage: catalogue.coverage};
  }
  function normalizeQuoteSnapshot(input, options, nowMs) {
    options = isObject(options) ? options : {};
    const errors = [];
    let payload;
    try { payload = typeof input === 'string' ? parseExactJSON(input) : input; } catch (_) { payload = null; }
    const kind = options.kind;
    const path = QUOTE_PATHS[kind];
    const source = path && sourceURL(options.source || (isObject(payload) ? payload.source : null), path);
    const body = isObject(payload) ? payload.response || payload : null;
    if (isObject(payload) && payload.http_status !== undefined && payload.http_status !== 200) errors.push(issue('QUOTE_HTTP_ERROR', 'http_status', 'La respuesta HTTP archivada no fue correcta.'));
    if (!path || !source || !isObject(body) || body.code !== 0 || body.method !== 'public/get-' + (kind === 'TICKER' ? 'tickers' : 'book') || !isObject(body.result) || !Array.isArray(body.result.data) || body.result.data.length !== 1) errors.push(issue('QUOTE_RESPONSE_INVALID', 'snapshot', 'Se necesita un snapshot público FCM de un instrumento.'));
    const row = !errors.length ? body.result.data[0] : null;
    const instrument = row && (kind === 'TICKER' ? row.i : body.result.instrument_name);
    const providerTimestampMs = row ? ms(row.t) : null;
    if (!nonempty(options.expectedInstrumentSymbol) || instrument !== options.expectedInstrumentSymbol) errors.push(issue('QUOTE_IDENTITY_MISMATCH', 'instrument', 'La cotización no corresponde al símbolo fijado.'));
    if (providerTimestampMs === null) errors.push(issue('QUOTE_TIMESTAMP_REQUIRED', 't', 'Falta timestamp exacto del proveedor en ms.'));
    let bid = null, ask = null, last = null, bidQuantity = null, askQuantity = null;
    if (row) {
      if (kind === 'TICKER') { bid = decimal(row.b); ask = decimal(row.k); last = row.a === undefined ? null : decimal(row.a); }
      else {
        const levels = [row.bids, row.asks];
        if (levels.some(values => !Array.isArray(values) || values.length === 0 || !Array.isArray(values[0]) || values[0].length !== 2)) errors.push(issue('BOOK_LEVELS_INVALID', 'bids/asks', 'El nivel observado requiere precio y cantidad explícitos, sin campos fabricados.'));
        else { bid = decimal(row.bids[0][0]); bidQuantity = positiveDecimal(row.bids[0][1]); ask = decimal(row.asks[0][0]); askQuantity = positiveDecimal(row.asks[0][1]); }
      }
    }
    if (bid === null || ask === null || !Number.isFinite(Number(bid)) || !Number.isFinite(Number(ask)) || Number(bid) > Number(ask) || (kind === 'BOOK' && (bidQuantity === null || askQuantity === null))) errors.push(issue('BID_ASK_INVALID', 'bid/ask', 'Bid/ask y cantidades deben ser explícitos y coherentes.'));
    const clock = ms(nowMs === undefined ? Date.now() : nowMs);
    const receivedAtMs = ms(options.receivedAtMs);
    if (clock === null || (providerTimestampMs !== null && clock !== null && providerTimestampMs > clock) || (receivedAtMs !== null && clock !== null && receivedAtMs > clock)) errors.push(issue('QUOTE_CLOCK_INVALID', 'time', 'El snapshot contiene tiempos futuros o un reloj inválido.'));
    const maxAgeMs = Number.isSafeInteger(options.maxAgeMs) && options.maxAgeMs >= 0 ? options.maxAgeMs : 60000;
    const ageMs = providerTimestampMs !== null && clock !== null ? clock - providerTimestampMs : null;
    const snapshotId = nonempty(options.snapshotId) ? options.snapshotId : instrument && providerTimestampMs !== null && source ? kind + ':' + instrument + ':' + providerTimestampMs : null;
    const status = errors.length ? 'INVALID' : ageMs > maxAgeMs ? 'STALE' : 'VALID';
    return {
      status, errors, kind: path ? kind : null, source: source || null, snapshotId,
      snapshotIdKind: nonempty(options.snapshotId) ? 'DECLARED_SNAPSHOT_ID' : 'DERIVED_SOURCE_INSTRUMENT_PROVIDER_TIME',
      instrumentSymbol: instrument || null, providerTimestampMs, receivedAtMs, providerAgeMs: ageMs,
      validUntilMs: providerTimestampMs !== null ? providerTimestampMs + maxAgeMs : null,
      sourceServerDate: isObject(payload) ? payload.response_server_date || null : null,
      bid: status === 'INVALID' ? null : bid, ask: status === 'INVALID' ? null : ask,
      last: status === 'INVALID' ? null : last, bidQuantity: status === 'INVALID' ? null : bidQuantity, askQuantity: status === 'INVALID' ? null : askQuantity,
      quoteMeaning: 'INSTRUMENT_BID_ASK_NOT_APP_YES_NO', mappedYesNo: null,
      // A VALID snapshot only checks identity/age: consumers must also require
      // an active matchSelectedContract result and remove it at close/expiry.
      requiresContractWindowValidation: true,
      settlementReferenceVerified: false, ...flags()
    };
  }
  return Object.freeze({parseExactJSON, normalizeInstrument, decodeCatalogue, matchSelectedContract, normalizeQuoteSnapshot});
});
