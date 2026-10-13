/* Hourly context from four contiguous, closed Exchange 15-minute candles.
 * Pure data transformation: no requests, interpolation, probabilities or index.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PulsoContextAggregate = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const QUARTER = 900000, HOUR = 3600000;
  const exactTime = n => Number.isSafeInteger(n) && n > 0 && n <= 8640000000000000;
  const number = n => typeof n === 'number' && Number.isFinite(n) && n > 0;
  function aggregateHour(context, nowMs) {
    if (!context || context.status !== 'VALID' || context.source !== 'PUBLIC_EXCHANGE'
      || context.purpose !== 'CONTEXT_ONLY_NOT_SETTLEMENT_INDEX' || context.contextOnly !== true
      || context.intervalSeconds !== 900 || !Array.isArray(context.rows) || !context.rows.length
      || !exactTime(nowMs) || !exactTime(context.closingCutoffMs) || context.closingCutoffMs > nowMs
      || !exactTime(context.validUntilMs) || context.validUntilMs <= nowMs) return null;
    const groups = new Map();
    let previous = null;
    for (const row of context.rows) {
      if (!row || !exactTime(row.openTimestampMs) || row.openTimestampMs % QUARTER !== 0
        || Date.parse(row.time) !== row.openTimestampMs
        || row.openTimestampMs + QUARTER > context.closingCutoffMs
        || (previous !== null && row.openTimestampMs - previous !== QUARTER)
        || ![row.open,row.high,row.low,row.close].every(number)
        || row.low > Math.min(row.open,row.close) || row.high < Math.max(row.open,row.close)
        || row.low > row.high) return null;
      previous = row.openTimestampMs;
      const start = Math.floor(row.openTimestampMs / HOUR) * HOUR;
      if (!groups.has(start)) groups.set(start, []);
      groups.get(start).push(row);
    }
    const rows = [];
    for (const [start, parts] of groups) {
      // The first and last source groups may be partial. They remain absent.
      if (parts.length !== 4 || start + HOUR > context.closingCutoffMs
        || parts.some((part,index) => part.openTimestampMs !== start + index*QUARTER)) continue;
      const volumeKnown = parts.every(part => typeof part.volume === 'number' && Number.isFinite(part.volume) && part.volume >= 0);
      rows.push({time:new Date(start).toISOString(),openTimestampMs:start,
        open:parts[0].open,high:Math.max(...parts.map(part=>part.high)),
        low:Math.min(...parts.map(part=>part.low)),close:parts[3].close,
        volume:volumeKnown ? parts.reduce((sum,part)=>sum+part.volume,0) : null,
        sourceCandleCount:4});
    }
    if (!rows.length) return null;
    const latestExpected = Math.floor((context.closingCutoffMs-HOUR)/HOUR)*HOUR;
    if (rows[rows.length-1].openTimestampMs !== latestExpected) return null;
    return {...context,intervalSeconds:3600,rows,
      latestClosedOpenTimestampMs:rows[rows.length-1].openTimestampMs,
      derived:true,derivedFromIntervalSeconds:900,
      aggregation:'FOUR_CONTIGUOUS_CLOSED_15_MINUTE_CANDLES',
      sourceCandleCount:rows.length*4,
      nativeHourlyProviderSeriesVerified:false,
      settlementReferenceVerified:false,contextOnly:true,
      execution_allowed:false,actionable:false};
  }
  return Object.freeze({aggregateHour});
});
