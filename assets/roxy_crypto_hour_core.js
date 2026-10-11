/* Roxy Crypto: isolated descriptive contract study. No network, accounts or execution.
 * API: evaluateContract(input, nowMs), analyzeCandles(rows, opts, nowMs),
 *      parseCandleCSV(text). See the public result fields and tests for examples.
 * A 60-second freshness limit is a preparation criterion, not a Trading setting.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.RoxyContractCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const FRESHNESS_MS = 60000;
  const QUOTE_FIELDS = Object.freeze([
    'entryPrice', 'entryFee', 'conversionCost', 'winPayout', 'losePayout',
    'winSettlementFee', 'loseSettlementFee'
  ]);
  const NUMBER_RE = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;
  const ISO_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?(Z|([+-])(\d{2}):(\d{2}))$/;

  function issue(code, field, message) { return { code, field, message }; }
  function object(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }
  function number(value) {
    if (typeof value === 'number') return Number.isFinite(value) ? value : null;
    if (typeof value !== 'string') return null;
    const text = value.trim();
    if (!text || !NUMBER_RE.test(text)) return null;
    const parsed = Number(text);
    return Number.isFinite(parsed) ? parsed : null;
  }
  function timestamp(value) {
    if (typeof value !== 'string') return null;
    const match = ISO_RE.exec(value.trim());
    if (!match) return null;
    const year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);
    const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
    const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    if (month < 1 || month > 12 || day < 1 || day > days[month - 1]
        || Number(match[4]) > 23 || Number(match[5]) > 59
        || (match[6] !== undefined && Number(match[6]) > 59)
        || (match[10] !== undefined && Number(match[10]) > 23)
        || (match[11] !== undefined && Number(match[11]) > 59)) return null;
    const parsed = Date.parse(value.trim());
    return Number.isFinite(parsed) ? parsed : null;
  }
  function iso(ms) {
    return Number.isFinite(ms) && Math.abs(ms) <= 8640000000000000 ? new Date(ms).toISOString() : null;
  }
  function currentClock(nowMs, errors) {
    const chosen = nowMs === undefined ? Date.now() : nowMs;
    if (typeof chosen !== 'number' || !Number.isFinite(chosen) || Math.abs(chosen) > 8640000000000000) {
      errors.push(issue('INVALID_CLOCK', 'nowMs', 'El reloj debe ser un instante finito en milisegundos.'));
      return null;
    }
    return chosen;
  }
  function noExecution() { return { execution_allowed: false, actionable: false }; }
  function textPresent(value) { return typeof value === 'string' && value.trim().length > 0; }

  function quoteEconomics(value, side, binaryTieConfirmed) {
    const errors = [];
    const warnings = [];
    const values = {};
    const path = 'quotes.' + side;
    if (!object(value)) {
      errors.push(issue('QUOTE_REQUIRED', path, 'Faltan los costes y pagos explícitos de ' + side + '.'));
    } else {
      for (const field of QUOTE_FIELDS) {
        const parsed = number(value[field]);
        if (parsed === null || parsed < 0) {
          errors.push(issue('INVALID_AMOUNT', path + '.' + field,
            'Declara ' + field + ' como importe finito y no negativo; un vacío no significa cero.'));
        } else values[field] = parsed;
      }
    }
    if (errors.length) return Object.assign({ status: 'INVALID', errors, warnings }, noExecution());
    const entryCost = values.entryPrice + values.entryFee + values.conversionCost;
    const netWin = values.winPayout - values.winSettlementFee - entryCost;
    const netLose = values.losePayout - values.loseSettlementFee - entryCost;
    const denominator = netWin - netLose;
    if (![entryCost, netWin, netLose, denominator].every(Number.isFinite)) {
      errors.push(issue('AMOUNT_OVERFLOW', path, 'La suma o resta de importes excede el rango finito.'));
    } else if (denominator <= 0) {
      errors.push(issue('NONPOSITIVE_PAYOFF_SPREAD', path,
        'El resultado neto al acertar debe superar al resultado neto al fallar.'));
    }
    if (errors.length) return Object.assign({ status: 'INVALID', errors, warnings }, noExecution());
    const calculatedBreakEven = binaryTieConfirmed ? -netLose / denominator : null;
    if (binaryTieConfirmed && !Number.isFinite(calculatedBreakEven)) {
      errors.push(issue('BREAKEVEN_OVERFLOW', path, 'No se puede calcular un umbral finito de equilibrio.'));
      return Object.assign({ status: 'INVALID', errors, warnings }, noExecution());
    }
    const breakEven = binaryTieConfirmed ? calculatedBreakEven : null;
    const breakEvenFeasible = binaryTieConfirmed && breakEven >= 0 && breakEven <= 1;
    const thresholdReason = binaryTieConfirmed ? null
      : 'El umbral de dos resultados requiere confirmar que el empate liquida No; otra regla necesita un modelo aparte.';
    if (!binaryTieConfirmed) {
      warnings.push(issue('BINARY_TIE_RULE_REQUIRED', path, thresholdReason));
    } else if (!breakEvenFeasible) {
      warnings.push(issue('BREAKEVEN_OUTSIDE_UNIT_INTERVAL', path,
        'El umbral de equilibrio está fuera de 0–100 %; revisa estos pagos y costes.'));
    }
    if (netWin <= 0) {
      warnings.push(issue('NO_POSITIVE_WIN_PROFIT', path,
        'Acertar no produce un beneficio neto positivo con estos importes.'));
    }
    if (netLose > 0) {
      warnings.push(issue('POSITIVE_LOSING_OUTCOME', path,
        'El resultado al fallar también es positivo; verifica los términos declarados.'));
    }
    return Object.assign({
      status: 'VALID', side, errors, warnings, inputs: values, entryCost,
      netWin, netLose, payoffSpread: denominator,
      potentialNetProfit: netWin, potentialNetLoss: Math.max(0, -netLose),
      breakEven, breakEvenFeasible, thresholdReason,
      thresholdMeaning: binaryTieConfirmed ? 'REQUIRED_WIN_FREQUENCY_NOT_FORECAST' : 'UNAVAILABLE_UNVERIFIED_TIE_RULE'
    }, noExecution());
  }

  function evaluateContract(input, nowMs) {
    const errors = [];
    const warnings = [];
    const clock = currentClock(nowMs, errors);
    if (!object(input)) {
      errors.push(issue('CONTRACT_REQUIRED', 'input', 'Falta el contrato que deseas estudiar.'));
      input = {};
    }
    // Accept either top-level contract fields or the UI's explicit wrapper.
    const source = object(input.contract) ? input.contract : input;
    const quoteSource = object(input.quotes) ? input.quotes : {};
    const strike = number(source.strike);
    const horizon = number(source.horizonSeconds);
    const start = timestamp(source.windowStart);
    const expiry = timestamp(source.expiry);
    const observed = timestamp(source.quoteObservedAt);
    if (source.symbol !== 'BTC/USD') {
      errors.push(issue('UNSUPPORTED_SYMBOL', 'symbol', 'Esta preparación requiere el contrato BTC/USD explícito.'));
    }
    if (horizon !== 3600) {
      errors.push(issue('UNSUPPORTED_HORIZON', 'horizonSeconds', 'Esta preparación cubre contratos de una hora (3600 segundos).'));
    }
    if (source.condition !== 'above') {
      errors.push(issue('UNSUPPORTED_CONDITION', 'condition', 'Declara la condición exacta: above (por encima).'));
    }
    if (strike === null || strike <= 0) {
      errors.push(issue('INVALID_STRIKE', 'strike', 'El nivel objetivo debe ser finito y mayor que cero.'));
    }
    for (const [field, value] of [['windowStart', start], ['expiry', expiry], ['quoteObservedAt', observed]]) {
      if (value === null) {
        errors.push(issue('INVALID_TIMESTAMP', field, 'Declara ' + field + ' en ISO con Z o un desplazamiento UTC explícito.'));
      }
    }
    if (start !== null && expiry !== null && expiry - start !== 3600000) {
      errors.push(issue('WINDOW_DURATION_MISMATCH', 'expiry', 'La ventana declarada debe durar exactamente una hora.'));
    }
    if (clock !== null) {
      if (start !== null && clock < start) {
        errors.push(issue('WINDOW_NOT_STARTED', 'windowStart', 'La ventana de este contrato todavía no ha comenzado.'));
      }
      if (expiry !== null && clock >= expiry) {
        errors.push(issue('CONTRACT_EXPIRED', 'expiry', 'Este contrato ya venció; sus tiempos no se extienden al recalcular.'));
      }
      if (observed !== null && observed > clock) {
        errors.push(issue('QUOTE_FROM_FUTURE', 'quoteObservedAt', 'La hora declarada de cotización está en el futuro.'));
      }
      if (observed !== null && clock - observed > FRESHNESS_MS) {
        errors.push(issue('QUOTE_STALE', 'quoteObservedAt', 'La cotización declarada supera el límite de preparación de 60 segundos.'));
      }
    }
    if (observed !== null && start !== null && observed < start) {
      errors.push(issue('QUOTE_BEFORE_WINDOW', 'quoteObservedAt', 'La cotización es anterior al inicio declarado de este contrato.'));
    }
    if (observed !== null && expiry !== null && observed >= expiry) {
      errors.push(issue('QUOTE_AFTER_EXPIRY', 'quoteObservedAt', 'La cotización declarada no corresponde a una ventana vigente.'));
    }
    if (!textPresent(source.settlementReference)) {
      errors.push(issue('SETTLEMENT_REFERENCE_REQUIRED', 'settlementReference', 'Falta la referencia exacta usada para liquidar el contrato.'));
    }
    if (!textPresent(source.settlementRule)) {
      errors.push(issue('SETTLEMENT_RULE_REQUIRED', 'settlementRule', 'Falta la regla exacta de liquidación, incluida la igualdad al nivel objetivo.'));
    }
    if (source.referenceVerified !== true) {
      errors.push(issue('SETTLEMENT_TERMS_UNVERIFIED', 'referenceVerified', 'Los términos y la referencia de liquidación siguen sin verificar.'));
    }
    if (source.tieRule !== 'NO_WINS') {
      errors.push(issue('BINARY_TIE_RULE_REQUIRED', 'tieRule',
        'Confirma que el empate liquida No. Una regla desconocida o de devolución requiere otro modelo de resultados.'));
    }
    const economics = {
      yes: quoteEconomics(quoteSource.yes, 'yes', source.tieRule === 'NO_WINS'),
      no: quoteEconomics(quoteSource.no, 'no', source.tieRule === 'NO_WINS')
    };
    for (const side of ['yes', 'no']) {
      errors.push(...economics[side].errors);
      warnings.push(...economics[side].warnings);
      if (economics[side].status === 'VALID' && economics[side].breakEven !== null && !economics[side].breakEvenFeasible) {
        errors.push(issue('IMPOSSIBLE_OR_INCONSISTENT_THRESHOLD', 'quotes.' + side,
          'Los pagos de ' + side + ' requieren revisar un umbral fuera de 0–100 %.'));
      }
    }
    const remainingSeconds = clock !== null && expiry !== null ? Math.max(0, (expiry - clock) / 1000) : null;
    return Object.assign({
      schemaVersion: 1, status: errors.length ? 'BLOCKED' : 'READY_FOR_REVIEW',
      errors, warnings, blockingReasons: errors.map(item => item.message), economics,
      contract: {
        symbol: source.symbol === 'BTC/USD' ? source.symbol : null,
        horizonSeconds: horizon === 3600 ? horizon : null,
        condition: source.condition === 'above' ? source.condition : null,
        strike: strike !== null && strike > 0 ? strike : null,
        windowStart: iso(start), expiry: iso(expiry), quoteObservedAt: iso(observed),
        evaluatedAt: iso(clock), remainingSeconds,
        quoteAgeSeconds: clock !== null && observed !== null ? (clock - observed) / 1000 : null,
        quoteValidUntil: observed !== null ? iso(observed + FRESHNESS_MS) : null,
        settlementReference: textPresent(source.settlementReference) ? source.settlementReference.trim() : null,
        settlementRule: textPresent(source.settlementRule) ? source.settlementRule.trim() : null,
        tieRule: source.tieRule === 'NO_WINS' ? 'NO_WINS' : source.tieRule === 'REFUND_OR_OTHER' ? 'REFUND_OR_OTHER' : null,
        referenceVerified: source.referenceVerified === true
      },
      assessmentKind: 'DESCRIPTIVE_COST_STUDY',
      conclusion: 'El umbral de equilibrio describe costes; no estima la probabilidad de ganar ni elige un lado.'
    }, noExecution());
  }

  function ema(rows, period) {
    const values = [];
    if (rows.length < period) return values;
    let average = rows[0].close;
    for (let i = 1; i < period; i++) average += (rows[i].close - average) / (i + 1);
    const alpha = 2 / (period + 1);
    for (let i = period - 1; i < rows.length; i++) {
      if (i >= period) average += alpha * (rows[i].close - average);
      values.push({ time: rows[i].time, timeMs: rows[i].timeMs, value: average });
    }
    return values;
  }

  function analyzeCandles(rows, opts, nowMs) {
    const errors = [];
    const warnings = [];
    const clock = currentClock(nowMs, errors);
    opts = object(opts) ? opts : {};
    const intervalSeconds = number(opts.intervalSeconds);
    const intervalMs = intervalSeconds === 300 || intervalSeconds === 900 ? intervalSeconds * 1000 : null;
    const source = ['MANUAL_CSV', 'PUBLIC_EXCHANGE', 'SYNTHETIC'].includes(opts.source) ? opts.source : null;
    const observed = opts.observedAt === undefined || opts.observedAt === null ? null : timestamp(opts.observedAt);
    const synthetic = source === 'SYNTHETIC';
    const requiresFreshness = source === 'MANUAL_CSV' || source === 'PUBLIC_EXCHANGE';
    if (intervalMs === null) errors.push(issue('UNSUPPORTED_CANDLE_INTERVAL', 'intervalSeconds', 'Importa velas de 5 o 15 minutos por separado.'));
    if (source === null) errors.push(issue('CANDLE_SOURCE_REQUIRED', 'source', 'Declara la fuente MANUAL_CSV, PUBLIC_EXCHANGE o SYNTHETIC.'));
    if (opts.symbol !== 'BTC/USD') errors.push(issue('CANDLE_SYMBOL_REQUIRED', 'symbol', 'Declara BTC/USD para estas velas.'));
    if (requiresFreshness && observed === null) {
      errors.push(issue('COLLECTION_TIME_REQUIRED', 'observedAt', 'Declara cuándo se obtuvieron estas velas; importar el archivo no renueva los datos.'));
    } else if (opts.observedAt !== undefined && opts.observedAt !== null && observed === null) {
      errors.push(issue('INVALID_COLLECTION_TIME', 'observedAt', 'La obtención necesita fecha ISO con zona UTC explícita.'));
    }
    if (observed !== null && clock !== null && observed > clock) {
      errors.push(issue('COLLECTION_FROM_FUTURE', 'observedAt', 'La hora de obtención declarada está en el futuro.'));
    }
    if (!Array.isArray(rows) || rows.length === 0 || rows.length > 10000) {
      errors.push(issue('CANDLES_REQUIRED', 'rows', 'Importa entre 1 y 10000 filas de velas.'));
      rows = [];
    }
    const normalized = [];
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      const path = 'rows.' + i;
      if (!object(row)) {
        errors.push(issue('INVALID_CANDLE_ROW', path, 'Cada vela debe contener time, open, high, low, close y volume.'));
        continue;
      }
      const timeMs = timestamp(row.time);
      const values = {};
      let invalid = false;
      if (timeMs === null) {
        errors.push(issue('INVALID_CANDLE_TIME', path + '.time', 'La apertura de cada vela necesita una fecha ISO con Z o desplazamiento UTC.'));
        invalid = true;
      } else if (intervalMs !== null && timeMs % intervalMs !== 0) {
        errors.push(issue('MISALIGNED_CANDLE', path + '.time', 'La apertura no coincide con el intervalo UTC declarado.'));
        invalid = true;
      }
      for (const field of ['open', 'high', 'low', 'close', 'volume']) {
        const parsed = number(row[field]);
        if (parsed === null || (field === 'volume' ? parsed < 0 : parsed <= 0)) {
          errors.push(issue('INVALID_CANDLE_NUMBER', path + '.' + field,
            'Precios positivos y volumen no negativo deben ser valores finitos explícitos.'));
          invalid = true;
        } else values[field] = parsed;
      }
      if (!invalid && (values.high < Math.max(values.open, values.close)
          || values.low > Math.min(values.open, values.close) || values.high < values.low)) {
        errors.push(issue('INVALID_CANDLE_GEOMETRY', path, 'Los máximos y mínimos no contienen la apertura y el cierre.'));
        invalid = true;
      }
      if (timeMs !== null && clock !== null && timeMs > clock) {
        errors.push(issue('CANDLE_FROM_FUTURE', path + '.time', 'Una vela comienza después del reloj de análisis.'));
        invalid = true;
      }
      if (!invalid) normalized.push(Object.assign({ time: iso(timeMs), timeMs }, values));
    }
    if (intervalMs !== null) {
      for (let i = 1; i < normalized.length; i++) {
        const delta = normalized[i].timeMs - normalized[i - 1].timeMs;
        if (delta === 0) errors.push(issue('DUPLICATE_CANDLE', 'rows.' + i, 'Hay aperturas de velas duplicadas.'));
        else if (delta < 0) errors.push(issue('UNSORTED_CANDLES', 'rows.' + i, 'Las velas deben estar en orden cronológico ascendente.'));
        else if (delta !== intervalMs) errors.push(issue('CANDLE_GAP', 'rows.' + i, 'Faltan velas o los intervalos están mezclados.'));
      }
    }
    // A historical snapshot never finalizes an open candle just because time passes.
    const closingCutoff = clock !== null ? (observed !== null ? Math.min(observed, clock) : clock) : null;
    const closedRows = intervalMs !== null && closingCutoff !== null
      ? normalized.filter(row => row.timeMs + intervalMs <= closingCutoff) : [];
    const droppedOpenRows = normalized.length - closedRows.length;
    if (droppedOpenRows > 0) warnings.push(issue('OPEN_CANDLES_EXCLUDED', 'rows', 'Se excluyeron ' + droppedOpenRows + ' velas sin cerrar al obtener la lectura.'));
    if (closedRows.length < 21) errors.push(issue('INSUFFICIENT_CLOSED_CANDLES', 'rows', 'Se necesitan al menos 21 velas cerradas para EMA 9/21.'));
    const expectedLastMs = intervalMs !== null && clock !== null ? Math.floor(clock / intervalMs) * intervalMs - intervalMs : null;
    const lastRow = closedRows.length ? closedRows[closedRows.length - 1] : null;
    const isStaleClose = requiresFreshness && expectedLastMs !== null && lastRow !== null && lastRow.timeMs !== expectedLastMs;
    const isStaleCollection = requiresFreshness && observed !== null && clock !== null && clock - observed > FRESHNESS_MS;
    const staleErrors = [];
    if (isStaleClose) staleErrors.push(issue('LATEST_CLOSED_CANDLE_MISSING', 'rows', 'Falta la última vela que debería estar cerrada según el reloj actual.'));
    if (isStaleCollection) staleErrors.push(issue('CANDLE_COLLECTION_STALE', 'observedAt', 'La obtención declarada supera 60 segundos; el archivo no se actualiza al importar.'));
    const invalid = errors.length > 0;
    errors.push(...staleErrors);
    const status = invalid ? 'INVALID' : staleErrors.length ? 'STALE' : 'VALID';
    let indicators = null;
    if (status === 'VALID') {
      const ema9 = ema(closedRows, 9);
      const ema21 = ema(closedRows, 21);
      const recent = closedRows.slice(-20);
      const current = lastRow.close;
      const last9 = ema9[ema9.length - 1].value;
      const last21 = ema21[ema21.length - 1].value;
      const trend = current > last9 && current > last21 ? 'ABOVE_BOTH_EMAS'
        : current < last9 && current < last21 ? 'BELOW_BOTH_EMAS' : 'MIXED';
      indicators = {
        ema9, ema21,
        range20: { high: Math.max(...recent.map(row => row.high)), low: Math.min(...recent.map(row => row.low)), candleCount: 20 },
        trend, lastClose: current,
        description: 'Los indicadores describen velas históricas; no proyectan precio ni probabilidad.'
      };
    }
    return Object.assign({
      schemaVersion: 1, status, errors, warnings, blockingReasons: errors.map(item => item.message),
      source, synthetic, symbol: opts.symbol === 'BTC/USD' ? opts.symbol : null,
      intervalSeconds: intervalMs !== null ? intervalSeconds : null,
      // Invalid/stale input cannot silently become a plotted valid series.
      closedRows: status === 'VALID' ? closedRows : [], indicators,
      inputCount: rows.length, closedCount: closedRows.length, droppedOpenRows,
      lastClose: status === 'VALID' && lastRow ? lastRow.close : null,
      freshness: {
        evaluatedAt: iso(clock), observedAt: iso(observed),
        closingCutoff: iso(closingCutoff),
        observedAgeSeconds: observed !== null && clock !== null ? (clock - observed) / 1000 : null,
        validUntil: observed !== null ? iso(observed + FRESHNESS_MS) : null,
        expectedLastClosedTime: iso(expectedLastMs), actualLastClosedTime: lastRow ? lastRow.time : null,
        latestClosedPresent: lastRow !== null && lastRow.timeMs === expectedLastMs,
        collectionTimeDeclared: observed !== null
      },
      assessmentKind: 'DESCRIPTIVE_HISTORICAL_CANDLES'
    }, noExecution());
  }

  function parseCandleCSV(text) {
    const errors = [];
    if (typeof text !== 'string' || text.trim() === '') {
      return { status: 'INVALID', rows: [], errors: [issue('CSV_REQUIRED', 'csv', 'Selecciona un CSV con velas y cabecera.')] };
    }
    // RFC-style quoted fields; no formulas/evaluation, date guessing or locale coercion.
    text = text.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    const records = [];
    let row = [], cell = '', quoted = false, quoteClosed = false;
    function finishCell() { row.push(cell); cell = ''; quoteClosed = false; }
    function finishRow() { finishCell(); records.push(row); row = []; }
    for (let i = 0; i < text.length; i++) {
      const char = text[i];
      if (quoted) {
        if (char === '"' && text[i + 1] === '"') { cell += '"'; i++; }
        else if (char === '"') { quoted = false; quoteClosed = true; }
        else cell += char;
      } else if (char === ',') finishCell();
      else if (char === '\n') finishRow();
      else if (char === '"' && cell === '' && !quoteClosed) quoted = true;
      else if (quoteClosed || char === '"') {
        errors.push(issue('INVALID_CSV_QUOTES', 'csv', 'Las comillas del CSV no están bien delimitadas.'));
        break;
      } else cell += char;
    }
    if (quoted) errors.push(issue('UNCLOSED_CSV_QUOTE', 'csv', 'Una celda entre comillas no tiene cierre.'));
    if (cell !== '' || row.length > 0) finishRow();
    while (records.length && records[records.length - 1].every(item => item.trim() === '')) records.pop();
    const expected = ['time', 'open', 'high', 'low', 'close', 'volume'];
    const header = records.length ? records.shift().map(item => item.trim().toLowerCase()) : [];
    if (header.length !== 6 || new Set(header).size !== 6 || expected.some(field => !header.includes(field))) {
      errors.push(issue('INVALID_CSV_HEADER', 'csv', 'La cabecera debe contener exactamente time, open, high, low, close, volume.'));
    }
    if (records.length < 1 || records.length > 10000) errors.push(issue('INVALID_CSV_ROW_COUNT', 'csv', 'El CSV debe contener entre 1 y 10000 velas.'));
    const rows = [];
    if (!errors.length) {
      for (let i = 0; i < records.length; i++) {
        const cells = records[i];
        if (cells.length !== 6) {
          errors.push(issue('INVALID_CSV_COLUMN_COUNT', 'csv.' + (i + 2), 'Cada fila debe contener las seis columnas.'));
          continue;
        }
        const output = {};
        for (let j = 0; j < header.length; j++) {
          const field = header[j];
          if (field === 'time') {
            if (timestamp(cells[j]) === null) errors.push(issue('INVALID_CSV_TIME', 'csv.' + (i + 2) + '.time', 'La apertura necesita ISO con zona UTC.'));
            else output.time = iso(timestamp(cells[j]));
          } else {
            const parsed = number(cells[j]);
            if (parsed === null) errors.push(issue('INVALID_CSV_NUMBER', 'csv.' + (i + 2) + '.' + field, 'Cada importe debe ser un número explícito; vacíos y texto no son cero.'));
            else output[field] = parsed;
          }
        }
        rows.push(output);
      }
    }
    return { status: errors.length ? 'INVALID' : 'VALID', rows: errors.length ? [] : rows, errors };
  }

  return Object.freeze({ evaluateContract, analyzeCandles, parseCandleCSV, FRESHNESS_MS });
});
