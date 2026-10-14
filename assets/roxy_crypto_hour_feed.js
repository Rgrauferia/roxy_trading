(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.RoxyMarketFeed = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const ENDPOINT = 'https://api.crypto.com/exchange/v1/public/get-candlestick';
  const PROVIDER = 'Crypto.com Exchange · API pública';
  const FRAMES = Object.freeze({300: '5m', 900: '15m'});
  function number(value, label) {
    if (typeof value !== 'number' && (typeof value !== 'string' || !/^-?\d+(?:\.\d+)?$/.test(value))) throw new Error(label + ': número ausente o inválido');
    const result = Number(value);
    if (!Number.isFinite(result)) throw new Error(label + ': número no finito');
    return result;
  }
  function decode(payload, intervalSeconds) {
    const interval = FRAMES[intervalSeconds];
    if (!interval) throw new Error('Intervalo no admitido');
    const result = payload && payload.result;
    if (!payload || payload.code !== 0 || payload.method !== 'public/get-candlestick' || !result || result.instrument_name !== 'BTC_USD' || result.interval !== interval) throw new Error('Fuente, instrumento o intervalo inesperado');
    if (!Array.isArray(result.data) || result.data.length < 21 || result.data.length > 300) throw new Error('Muestra pública ausente o fuera de límites');
    return result.data.map((row, index) => {
      if (!row || typeof row !== 'object' || Array.isArray(row)) throw new Error('Vela pública inválida');
      const time = number(row.t, 'Fecha ' + index);
      if (!Number.isSafeInteger(time) || time <= 0 || time % (intervalSeconds * 1000)) throw new Error('Fecha de vela no alineada');
      const o = number(row.o, 'Apertura'), h = number(row.h, 'Máximo'), l = number(row.l, 'Mínimo'), c = number(row.c, 'Cierre'), v = number(row.v, 'Volumen');
      if (Math.min(o, h, l, c) <= 0 || v < 0 || h < Math.max(o, l, c) || l > Math.min(o, h, c)) throw new Error('OHLCV incoherente');
      return {time: new Date(time).toISOString(), open: o, high: h, low: l, close: c, volume: v};
    });
  }
  async function fetchPanel(intervalSeconds, dependencies) {
    const interval = FRAMES[intervalSeconds];
    if (!interval) throw new Error('Intervalo no admitido');
    const requestedAt = dependencies.now();
    if (!Number.isFinite(requestedAt)) throw new Error('Reloj de petición no válido');
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await dependencies.fetch(ENDPOINT + '?instrument_name=BTC_USD&timeframe=' + interval + '&count=300', {
        method: 'GET', credentials: 'omit', mode: 'cors', cache: 'no-store', redirect: 'error', signal: controller.signal
      });
      if (!response.ok) throw new Error('Fuente pública no disponible: HTTP ' + response.status);
      const content = await response.text();
      if (typeof content !== 'string' || content.length > 500000) throw new Error('Respuesta pública fuera de límites');
      let payload;
      try { payload = JSON.parse(content); } catch (_) { throw new Error('Respuesta pública no válida'); }
      const decoded = decode(payload, intervalSeconds);
      // A response received after a boundary may still contain a partial candle
      // obtained before that boundary. Freeze closed status at request start.
      const rows = decoded.filter(row => Date.parse(row.time) + intervalSeconds * 1000 <= requestedAt);
      const receivedAt = dependencies.now();
      if (!Number.isFinite(receivedAt) || receivedAt < requestedAt) throw new Error('Reloj de recepción no válido');
      return {rows, observedAt: new Date(receivedAt).toISOString(), requestedAt: new Date(requestedAt).toISOString(), intervalSeconds};
    } catch (error) {
      if (error && error.name === 'AbortError') throw new Error('La fuente pública tardó demasiado; datos retirados');
      throw error;
    } finally { clearTimeout(timer); }
  }
  async function fetchPanels(options) {
    const dependencies = {fetch: options && options.fetch || globalThis.fetch, now: options && options.now || Date.now};
    if (typeof dependencies.fetch !== 'function') throw new Error('Lectura pública no disponible en este navegador');
    const values = await Promise.all([fetchPanel(300, dependencies), fetchPanel(900, dependencies)]);
    return {
      symbol: 'BTC/USD', provider: PROVIDER, source: 'PUBLIC_EXCHANGE',
      observedAt: values.map(value => value.observedAt).sort()[0],
      requestedAt: values.map(value => value.requestedAt).sort()[0],
      panelObservedAt: Object.fromEntries(values.map(value => [value.intervalSeconds, value.observedAt])),
      panelRequestedAt: Object.fromEntries(values.map(value => [value.intervalSeconds, value.requestedAt])),
      panels: Object.fromEntries(values.map(value => [value.intervalSeconds, value.rows])),
      settlementReferenceVerified: false, execution_allowed: false, actionable: false,
      notice: 'Velas de Crypto.com Exchange para estudiar el mercado. No acreditan el índice ni el precio de liquidación del contrato CDNA.'
    };
  }
  return Object.freeze({decode, fetchPanels, ENDPOINT, PROVIDER});
});
