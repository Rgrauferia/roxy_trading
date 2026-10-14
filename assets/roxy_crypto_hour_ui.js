(() => {
  "use strict";
  const core = globalThis.RoxyContractCore;
  const $ = id => document.getElementById(id);
  const QUOTE_FIELDS = [
    ["entryPrice", "Precio de entrada"], ["entryFee", "Comisión de entrada"],
    ["conversionCost", "Coste de conversión"], ["winPayout", "Pago bruto si gana"],
    ["losePayout", "Pago bruto si pierde"], ["winSettlementFee", "Comisión si gana"],
    ["loseSettlementFee", "Comisión si pierde"]
  ];
  const CONTRACT_FIELDS = ["strike", "windowStart", "expiry", "quoteObservedAt", "settlementReference", "settlementRule", "tieRule"];
  const state = {
    practice: false, interval: 300, touched: false, notice: "", result: null,
    datasets: {300: null, 900: null}, chartResults: {300: null, 900: null},
    imports: {300: "Sin archivo.", 900: "Sin archivo."}, lastChartKey: "", lastOutcomeKey: "",
    feedBusy: false, feedGeneration: 0, dataGeneration: 0, csvTokens: {300: 0, 900: 0}
  };
  const money = value => Number.isFinite(value) ? new Intl.NumberFormat("es-ES", {maximumFractionDigits: 6, minimumFractionDigits: 2}).format(value) : "—";
  const price = value => Number.isFinite(value) ? new Intl.NumberFormat("es-ES", {maximumFractionDigits: 4}).format(value) : "—";
  const percentage = value => Number.isFinite(value) ? new Intl.NumberFormat("es-ES", {style: "percent", maximumFractionDigits: 2}).format(value) : "—";
  const numberValue = id => $(id).value.trim() === "" ? null : Number($(id).value);
  const safeDate = value => { const timestamp = Date.parse(value); return Number.isFinite(timestamp) ? timestamp : null; };
  const asTime = value => typeof value === "number" ? (Math.abs(value) < 1e11 ? value * 1000 : value) : Date.parse(value);
  const errorMessage = error => typeof error === "string" ? error : error?.message || error?.code || "Dato no válido.";

  for (const [name, label] of QUOTE_FIELDS) {
    const row = document.createElement("div"); row.className = "quote-row";
    const nameLabel = document.createElement("span"); nameLabel.className = "quote-label"; nameLabel.textContent = label; row.append(nameLabel);
    for (const side of ["yes", "no"]) {
      const input = document.createElement("input"); input.id = `${side}_${name}`;
      input.type = "number"; input.min = "0"; input.step = "any"; input.inputMode = "decimal";
      input.placeholder = "Sin dato"; input.autocomplete = "off";
      const labelElement = document.createElement("label"); labelElement.className = "sr-only";
      labelElement.htmlFor = input.id; labelElement.textContent = `${side === "yes" ? "Sí" : "No"}: ${label}`;
      const holder = document.createElement("div"); holder.append(labelElement, input); row.append(holder);
    }
    $("quoteFields").append(row);
  }

  function readContract() {
    const contract = {
      symbol: "BTC/USD", horizonSeconds: 3600, condition: "above", strike: numberValue("strike"),
      windowStart: $("windowStart").value.trim(), expiry: $("expiry").value.trim(),
      quoteObservedAt: $("quoteObservedAt").value.trim(), settlementReference: $("settlementReference").value.trim(),
      settlementRule: $("settlementRule").value.trim(), tieRule: $("tieRule").value, referenceVerified: $("referenceVerified").checked,
      quotes: {yes: {}, no: {}}
    };
    for (const side of ["yes", "no"]) for (const [name] of QUOTE_FIELDS) contract.quotes[side][name] = numberValue(`${side}_${name}`);
    return contract;
  }

  function update(now = Date.now(), options = {}) {
    const input = readContract();
    if (!core || typeof core.evaluateContract !== "function") {
      $("resultTitle").textContent = "Espera: módulo de validación no disponible";
      $("resultExplanation").textContent = "Esta copia no incluye el motor de revisión. No es posible validar los datos.";
      $("reviewMetric").textContent = "Módulo ausente"; return;
    }
    try { state.result = core.evaluateContract(input, now); }
    catch (_) { state.result = {status: "BLOCKED", blockingReasons: ["No se pudo validar esta entrada. Revisa los campos."], errors: [], economics: {}, execution_allowed: false, actionable: false}; }
    for (const interval of [300, 900]) {
      const dataset = state.datasets[interval];
      if (dataset) {
        try { state.chartResults[interval] = core.analyzeCandles(dataset.rows, {intervalSeconds: interval, source: dataset.source, symbol: "BTC/USD", observedAt: dataset.observedAt}, now); }
        catch (_) { state.chartResults[interval] = {status: "INVALID", errors: [{message: "No se pudieron validar las velas."}], closedRows: []}; }
      } else state.chartResults[interval] = null;
    }
    renderSummary(input, now);
    renderOutcome();
    renderChart(input, !!options.forceChart);
    renderImports();
  }

  function renderSummary(input, now) {
    const contract = state.result?.contract || {};
    const expiry = safeDate(input.expiry);
    const remaining = Number.isFinite(contract.remainingSeconds) ? contract.remainingSeconds : expiry === null ? null : Math.floor((expiry - now) / 1000);
    $("remainingMetric").textContent = remaining === null ? "—" : remaining <= 0 ? "Vencido" : `${String(Math.floor(remaining / 3600)).padStart(2, "0")}:${String(Math.floor(remaining % 3600 / 60)).padStart(2, "0")}:${String(Math.floor(remaining % 60)).padStart(2, "0")}`;
    $("strikeMetric").textContent = input.strike > 0 && Number.isFinite(input.strike) ? price(input.strike) : "—";
    const quoteTimestamp = safeDate(input.quoteObservedAt);
    const age = Number.isFinite(contract.quoteAgeSeconds) ? contract.quoteAgeSeconds : quoteTimestamp === null ? null : (now - quoteTimestamp) / 1000;
    $("quoteAgeMetric").textContent = age === null ? "—" : age < 0 ? "Hora futura" : `${Math.floor(age)} s`;
    const expires = contract.quoteValidUntil ? safeDate(contract.quoteValidUntil) : null;
    $("quoteAgeNote").textContent = quoteTimestamp === null ? "Introduce la hora observada" : expires !== null && expires <= now ? "Cotización antigua: vuelve a comprobarla" : "Hora manual fija; sin actualización automática";
    const ready = state.result?.status === "READY_FOR_REVIEW";
    $("contractPill").textContent = ready ? "DATOS PARA REVISAR" : remaining !== null && remaining <= 0 ? "CONTRATO VENCIDO" : "ESPERAR / REVISAR DATOS";
    $("contractPill").className = `pill ${ready ? "good" : "warn"}`;
    $("reviewMetric").textContent = ready ? "Comparación disponible" : "Esperar datos válidos";
    $("provenanceLabel").textContent = state.practice ? "SINTÉTICO · contrato de práctica; revisa la fuente de cada gráfico" : "Contrato manual · sin cotización de Strike Options conectada";
    $("syntheticBanner").hidden = !state.practice;
    $("clockLabel").textContent = `Reloj UTC · ${new Date(now).toISOString().slice(11, 19)}`;
    $("notice").textContent = state.notice;
  }

  function renderOutcome() {
    const result = state.result;
    const ready = result?.status === "READY_FOR_REVIEW";
    const reasons = Array.isArray(result?.blockingReasons) ? result.blockingReasons : (result?.errors || []).map(errorMessage);
    const economics = result?.economics || {};
    const warnings = [...(result?.warnings || []).map(errorMessage), ...["yes", "no"].flatMap(side => (economics[side]?.warnings || []).map(warning => `${side === "yes" ? "Sí" : "No"}: ${errorMessage(warning)}`))];
    const key = JSON.stringify([ready, reasons, warnings, economics, state.touched, state.practice]);
    if (key === state.lastOutcomeKey) return; state.lastOutcomeKey = key;
    $("resultBox").className = `outcome${ready ? " ready" : ""}`;
    $("resultTitle").textContent = ready ? state.practice ? "Práctica: costes comparables" : "Datos listos para revisión" : "Espera: revisión bloqueada";
    $("resultExplanation").textContent = ready ? "La comparación aritmética está completa. No constituye una recomendación; no hay probabilidad propia validada para elegir Sí o No." : "Faltan datos o alguna condición es inválida o antigua. No hay una conclusión sobre qué lado tomar.";
    const list = $("blockingList"); list.replaceChildren();
    if (state.touched || ready) for (const message of [...new Set(reasons)].slice(0, 12)) {
      const li = document.createElement("li"); li.textContent = message; list.append(li);
    } else {
      const li = document.createElement("li"); li.textContent = "Completa las reglas, las horas con zona y todos los importes de ambos lados, o carga la práctica sintética."; list.append(li);
    }
    for (const message of [...new Set(warnings)]) {
      const li = document.createElement("li"); li.textContent = `Atención: ${message}`; list.append(li);
    }
    for (const side of ["yes", "no"]) {
      const value = economics[side] || {};
      $(side + "Entry").textContent = money(value.entryCost);
      $(side + "Win").textContent = money(value.netWin);
      $(side + "Lose").textContent = money(value.netLose);
      $(side + "Break").textContent = Number.isFinite(value.breakEven) ? `${percentage(value.breakEven)}${value.breakEvenFeasible === false ? " · no viable" : ""}` : "—";
    }
  }

  function renderImports() {
    for (const interval of [300, 900]) {
      const result = state.chartResults[interval];
      const label = $(interval === 300 ? "csv5Status" : "csv15Status");
      if (!result) { label.textContent = state.imports[interval]; continue; }
      const dataset = state.datasets[interval];
      const prefix = dataset?.source === "SYNTHETIC" ? "SINTÉTICO" : dataset?.source === "PUBLIC_EXCHANGE" ? "API pública Exchange" : "CSV manual";
      label.textContent = result.status === "VALID" ? `${prefix} · ${result.closedRows.length} velas cerradas válidas. Obtención: ${dataset.observedAt || "sin declarar"}.` : `${prefix} · ${result.status === "STALE" ? "datos antiguos" : "datos inválidos"}: ${(result.errors || []).map(errorMessage).slice(0, 2).join(" ") || "No se puede usar el gráfico."}`;
    }
  }

  function renderChart(input, force = false) {
    const result = state.chartResults[state.interval];
    const key = JSON.stringify([state.interval, result?.status, result?.closedRows?.length, result?.lastClose, input.strike, state.result?.status, state.practice, state.datasets[state.interval]?.observedAt]);
    if (!force && key === state.lastChartKey) return; state.lastChartKey = key;
    $("chart5Btn").setAttribute("aria-pressed", String(state.interval === 300));
    $("chart15Btn").setAttribute("aria-pressed", String(state.interval === 900));
    const rows = result?.status === "VALID" ? result.closedRows : [];
    const empty = $("chartEmpty");
    empty.hidden = rows.length > 0;
    const validStrike = state.result?.status === "READY_FOR_REVIEW" && Number.isFinite(input.strike) && input.strike > 0;
    if (!rows.length) {
      empty.textContent = result ? `Gráfico bloqueado: ${(result.errors || []).map(errorMessage).slice(0, 2).join(" ") || "faltan velas recientes y válidas."}` : "Importa velas cerradas de 5 o 15 minutos, o carga la práctica sintética.";
      $("chartDescription").textContent = "Sin velas recientes válidas. No hay un precio de mercado conectado.";
      $("dataSummary").textContent = "Sin velas válidas para mostrar.";
      $("candleTable").replaceChildren();
      $("scenarioText").replaceChildren(paragraph("Necesitas velas recientes y válidas. El contrato y las cotizaciones se revisan por separado; no hay una señal de entrada."));
      clearCanvas(); return;
    }
    const source = state.datasets[state.interval].source === "SYNTHETIC" ? "SINTÉTICO" : state.datasets[state.interval].source === "PUBLIC_EXCHANGE" ? "Crypto.com Exchange · API pública; no es una verificación del índice de liquidación" : "CSV introducido manualmente; proveedor no autenticado";
    const last = rows[rows.length - 1];
    $("chartDescription").textContent = `${source} · BTC/USD · velas de ${state.interval / 60} min · ${rows.length} velas cerradas. Último cierre: ${price(last.close)}. ${validStrike ? "Nivel del contrato marcado; la referencia del CSV puede diferir de la liquidación." : "El nivel del contrato se mostrará cuando el contrato y las cotizaciones sean válidos."}`;
    $("dataSummary").textContent = `${rows.length} velas cerradas de ${state.interval / 60} minutos. Última apertura ${new Date(asTime(last.time)).toISOString()}. Cierre ${price(last.close)}. Rango de las últimas 20 velas: ${price(result.indicators?.range20?.low)} a ${price(result.indicators?.range20?.high)}. Fuente: ${source}. La tabla muestra las últimas 12 velas.`;
    const table = $("candleTable"); table.replaceChildren();
    for (const row of rows.slice(-12)) {
      const tr = document.createElement("tr");
      for (const value of [new Date(asTime(row.time)).toISOString().slice(0, 16).replace("T", " "), price(row.open), price(row.high), price(row.low), price(row.close), price(row.volume)]) {
        const td = document.createElement("td"); td.textContent = value; tr.append(td);
      }
      table.append(tr);
    }
    renderScenarios(input, result, validStrike);
    drawChart(rows, result.indicators || {}, validStrike ? input.strike : null);
  }

  function paragraph(text) { const p = document.createElement("p"); p.textContent = text; return p; }

  function renderScenarios(input, result, validContract) {
    const box = $("scenarioText"); box.replaceChildren();
    if (!validContract) { box.append(paragraph("Las velas son descriptivas. Completa y valida el contrato y sus cotizaciones para relacionar el gráfico con su nivel; todavía no hay un escenario utilizable.")); return; }
    const close = result.closedRows[result.closedRows.length - 1].close;
    const range = result.indicators?.range20;
    const trendLabels = {ABOVE_BOTH_EMAS: "El último cierre está por encima de ambas EMA.", BELOW_BOTH_EMAS: "El último cierre está por debajo de ambas EMA.", MIXED: "Las EMA muestran un contexto mixto."};
    const orientation = close > input.strike ? "por encima" : close < input.strike ? "por debajo" : "igual al nivel";
    box.append(paragraph(`Contexto observado: último cierre ${orientation} del objetivo ${price(input.strike)}. ${trendLabels[result.indicators?.trend] || "No hay lectura de tendencia suficiente."}`));
    box.append(paragraph(`Escenario por encima: si el precio de la referencia de liquidación termina por encima de ${price(input.strike)}, aplica el pago de Sí según las reglas verificadas. Una caída a ese nivel o por debajo invalidaría esa condición.`));
    box.append(paragraph(`Escenario por debajo: si la referencia termina por debajo de ${price(input.strike)}, aplica la regla de No que copiaste. ${input.tieRule === "NO_WINS" ? "Empate: según la opción verificada, corresponde a No." : "El empate no está validado para esta comparación de dos resultados."}`));
    if (range && Number.isFinite(range.high) && Number.isFinite(range.low)) box.append(paragraph(`Rango observado en 20 velas: ${price(range.low)}–${price(range.high)}. Es una descripción histórica, sin proyección futura ni garantía de permanencia.`));
    box.append(paragraph("Estos escenarios no asignan probabilidades ni seleccionan un lado. El último cierre del CSV y las EMA no prueban el resultado al vencimiento."));
  }

  function clearCanvas() {
    const canvas = $("priceChart"); const rect = canvas.getBoundingClientRect();
    canvas.width = Math.max(1, Math.round(rect.width * (window.devicePixelRatio || 1)));
    canvas.height = Math.max(1, Math.round(rect.height * (window.devicePixelRatio || 1)));
    canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
  }

  function drawChart(allRows, indicators, strike) {
    const canvas = $("priceChart"); const rect = canvas.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return;
    const ratio = window.devicePixelRatio || 1; canvas.width = Math.round(rect.width * ratio); canvas.height = Math.round(rect.height * ratio);
    const ctx = canvas.getContext("2d"); ctx.scale(ratio, ratio);
    const width = rect.width, height = rect.height;
    const rows = allRows.slice(-Math.min(80, Math.max(24, Math.floor(width / 7))));
    const firstTime = asTime(rows[0].time), lastTime = asTime(rows[rows.length - 1].time);
    const left = 10, right = width < 420 ? 65 : 78, top = 20, bottom = 29, volHeight = 50;
    const plotWidth = width - left - right, plotHeight = height - top - bottom - volHeight - 14;
    const values = rows.flatMap(row => [row.low, row.high]);
    for (const name of ["ema9", "ema21"]) for (const point of indicators[name] || []) if (asTime(point.time) >= firstTime && Number.isFinite(point.value)) values.push(point.value);
    if (Number.isFinite(strike)) values.push(strike);
    const low = Math.min(...values), high = Math.max(...values), pad = Math.max((high - low) * .12, high * .0002, .01);
    const min = low - pad, max = high + pad;
    const y = value => top + (max - value) / (max - min) * plotHeight;
    const step = plotWidth / rows.length, x = index => left + (index + .5) * step;
    ctx.fillStyle = "#0a1726"; ctx.fillRect(0, 0, width, height);
    ctx.font = "10px system-ui"; ctx.textAlign = "left"; ctx.textBaseline = "middle";
    for (let i = 0; i <= 4; i++) {
      const v = max - i / 4 * (max - min), py = y(v);
      ctx.strokeStyle = "#203146"; ctx.beginPath(); ctx.moveTo(left, py); ctx.lineTo(width - right, py); ctx.stroke();
      ctx.fillStyle = "#9db0c4"; ctx.fillText(price(v), width - right + 8, py);
    }
    const range = indicators.range20;
    if (range && Number.isFinite(range.low) && Number.isFinite(range.high)) {
      ctx.fillStyle = "rgba(139,188,255,.055)"; ctx.fillRect(left, y(range.high), plotWidth, Math.max(1, y(range.low) - y(range.high)));
    }
    const volumeMax = Math.max(...rows.map(row => row.volume), 1);
    rows.forEach((row, index) => {
      const cx = x(index), green = row.close >= row.open, color = green ? "#62e7b1" : "#e8969f";
      ctx.strokeStyle = color; ctx.beginPath(); ctx.moveTo(cx, y(row.high)); ctx.lineTo(cx, y(row.low)); ctx.stroke();
      ctx.fillStyle = color; const body = Math.min(7, Math.max(2, step * .62));
      ctx.fillRect(cx - body / 2, y(Math.max(row.close, row.open)), body, Math.max(1, Math.abs(y(row.close) - y(row.open))));
      ctx.fillStyle = green ? "rgba(98,231,177,.35)" : "rgba(232,150,159,.35)";
      const volumeHeight = row.volume / volumeMax * volHeight;
      ctx.fillRect(cx - body / 2, height - bottom - volumeHeight, body, volumeHeight);
    });
    const times = new Map(rows.map((row, index) => [asTime(row.time), index]));
    for (const [name, color] of [["ema9", "#8bbcff"], ["ema21", "#f0c477"]]) {
      ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.beginPath(); let drawing = false;
      for (const point of indicators[name] || []) {
        const index = times.get(asTime(point.time));
        if (index === undefined || !Number.isFinite(point.value)) continue;
        if (drawing) ctx.lineTo(x(index), y(point.value)); else { ctx.moveTo(x(index), y(point.value)); drawing = true; }
      }
      ctx.stroke(); ctx.lineWidth = 1;
    }
    if (Number.isFinite(strike)) {
      ctx.strokeStyle = "#f0b7ef"; ctx.setLineDash([5, 4]); ctx.beginPath(); ctx.moveTo(left, y(strike)); ctx.lineTo(width - right, y(strike)); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = "#f0b7ef"; ctx.fillText(price(strike), width - right + 8, y(strike));
    }
    ctx.fillStyle = "#9db0c4"; ctx.textBaseline = "alphabetic"; ctx.font = "10px system-ui";
    ctx.textAlign = "left"; ctx.fillText(new Date(firstTime).toISOString().slice(11, 16) + " UTC", left, height - 9);
    ctx.textAlign = "right"; ctx.fillText(new Date(lastTime).toISOString().slice(11, 16) + " UTC", width - right, height - 9);
    ctx.textAlign = "left"; ctx.fillText("Vol.", width - right + 8, height - bottom - 8);
  }

  async function importCsv(interval, file) {
    if (!file) return;
    const generation = state.dataGeneration;
    const token = ++state.csvTokens[interval];
    const observedAt = $(interval === 300 ? "csv5ObservedAt" : "csv15ObservedAt").value.trim();
    state.feedGeneration++; state.feedBusy = false; $("publicFeedBtn").disabled = false; $("publicFeedBtn").textContent = "Leer velas públicas";
    state.touched = true; state.notice = "";
    state.datasets[interval] = null; state.chartResults[interval] = null; state.imports[interval] = "Leyendo archivo local…";
    update(Date.now(), {forceChart: true});
    if (file.size > 2 * 1024 * 1024) { state.datasets[interval] = null; state.imports[interval] = "Archivo demasiado grande: máximo 2 MiB."; update(Date.now(), {forceChart: true}); return; }
    try {
      const text = await file.text();
      if (generation !== state.dataGeneration || token !== state.csvTokens[interval]) return;
      const parsed = core.parseCandleCSV(text);
      if (parsed.status !== "VALID") { state.datasets[interval] = null; state.imports[interval] = "CSV inválido: " + (parsed.errors || []).map(errorMessage).slice(0, 3).join(" "); }
      else {
        state.datasets[interval] = {rows: parsed.rows, source: "MANUAL_CSV", observedAt, fileName: file.name};
        state.imports[interval] = "CSV cargado para validación.";
        state.interval = interval;
        state.notice = "CSV cargado localmente. Comprueba que contiene BTC/USD y que su fuente corresponde al instrumento que estudias.";
      }
    } catch (_) {
      if (generation !== state.dataGeneration || token !== state.csvTokens[interval]) return;
      state.datasets[interval] = null; state.imports[interval] = "No se pudo leer el CSV. Comprueba su formato.";
    }
    update(Date.now(), {forceChart: true});
  }

  async function fetchPublicPanels() {
    if (state.feedBusy) return;
    state.feedBusy = true; const generation = ++state.feedGeneration; const dataGeneration = ++state.dataGeneration;
    state.datasets = {300: null, 900: null}; state.chartResults = {300: null, 900: null};
    state.imports = {300: "Lectura pública pendiente.", 900: "Lectura pública pendiente."};
    $("publicFeedBtn").disabled = true; $("publicFeedBtn").textContent = "Leyendo velas…";
    $("feedStatus").textContent = "Consultando únicamente velas públicas de BTC/USD. Las cotizaciones del contrato no se actualizan.";
    state.notice = ""; update(Date.now(), {forceChart: true});
    try {
      if (!globalThis.RoxyMarketFeed || typeof globalThis.RoxyMarketFeed.fetchPanels !== "function") throw new Error("El módulo de lectura pública no está disponible.");
      const feed = await globalThis.RoxyMarketFeed.fetchPanels();
      if (generation !== state.feedGeneration || dataGeneration !== state.dataGeneration) return;
      for (const interval of [300, 900]) state.datasets[interval] = {rows: feed.panels[interval], source: "PUBLIC_EXCHANGE", observedAt: feed.panelObservedAt?.[interval] || feed.observedAt, requestedAt: feed.panelRequestedAt?.[interval] || feed.requestedAt, provider: feed.provider};
      $("feedStatus").textContent = `Lectura recibida: ${feed.observedAt}. Sin actualización automática; pulsa de nuevo para volver a consultar. Fuente Exchange para estudio, no referencia de liquidación verificada.`;
      state.notice = "Velas públicas recibidas para validar. Los datos del contrato y su hora observada siguen siendo manuales.";
    } catch (error) {
      if (generation !== state.feedGeneration || dataGeneration !== state.dataGeneration) return;
      state.datasets = {300: null, 900: null};
      state.imports = {300: "Lectura pública fallida. No se conserva ningún gráfico anterior.", 900: "Lectura pública fallida. No se conserva ningún gráfico anterior."};
      $("feedStatus").textContent = `No se recibieron velas utilizables. ${typeof error?.message === "string" ? error.message : "Vuelve a intentar la lectura manual."}`;
      state.notice = "Lectura pública fallida: gráficos vacíos. Puedes importar un CSV reciente con su hora de obtención.";
    } finally {
      if (generation === state.feedGeneration && dataGeneration === state.dataGeneration) {
        state.feedBusy = false; $("publicFeedBtn").disabled = false; $("publicFeedBtn").textContent = "Leer velas públicas";
        update(Date.now(), {forceChart: true});
      }
    }
  }

  function loadPractice() {
    const now = Date.now(); const start = Math.floor(now / 3600000) * 3600000;
    state.feedGeneration++; state.dataGeneration++; state.feedBusy = false; $("publicFeedBtn").disabled = false; $("publicFeedBtn").textContent = "Leer velas públicas";
    state.practice = true; state.touched = true;
    const values = {strike: 12500, windowStart: new Date(start).toISOString(), expiry: new Date(start + 3600000).toISOString(), quoteObservedAt: new Date(now).toISOString(), settlementReference: "ÍNDICE INVENTADO PARA PRÁCTICA", settlementRule: "REGLA SINTÉTICA: Sí paga si el índice inventado es estrictamente superior al nivel. No paga si es inferior o igual. No son reglas reales de Crypto.com.", tieRule: "NO_WINS"};
    for (const [key, value] of Object.entries(values)) $(key).value = value;
    $("referenceVerified").checked = false;
    const quotes = {
      yes: {entryPrice: 4.2, entryFee: .1, conversionCost: 0, winPayout: 10, losePayout: 0, winSettlementFee: .1, loseSettlementFee: 0},
      no: {entryPrice: 5.8, entryFee: .1, conversionCost: 0, winPayout: 10, losePayout: 0, winSettlementFee: .1, loseSettlementFee: 0}
    };
    for (const side of ["yes", "no"]) for (const [name] of QUOTE_FIELDS) $(`${side}_${name}`).value = quotes[side][name];
    const end = Math.floor(now / 300000) * 300000;
    const rows = []; let previous = 12482;
    for (let i = 0; i < 243; i++) {
      const time = end - (243 - i) * 300000;
      const close = 12482 + i * .085 + Math.sin(i * .29) * 6.2 + Math.cos(i * .08) * 4;
      const open = previous; const high = Math.max(open, close) + 1.8 + (i % 7) * .14;
      const low = Math.min(open, close) - 1.5 - (i % 5) * .17;
      rows.push({time: new Date(time).toISOString(), open, high, low, close, volume: 180 + (i % 23) * 11}); previous = close;
    }
    const aggregated = [];
    for (let i = 0; i + 2 < rows.length; i++) {
      if (asTime(rows[i].time) % 900000 !== 0) continue;
      const group = rows.slice(i, i + 3);
      aggregated.push({time: group[0].time, open: group[0].open, high: Math.max(...group.map(row => row.high)), low: Math.min(...group.map(row => row.low)), close: group[2].close, volume: group.reduce((sum, row) => sum + row.volume, 0)});
    }
    for (const [interval, candleRows] of [[300, rows.slice(-240)], [900, aggregated.slice(-80)]]) state.datasets[interval] = {rows: candleRows, source: "SYNTHETIC", observedAt: new Date(now).toISOString()};
    $("csv5").value = ""; $("csv15").value = ""; $("csv5ObservedAt").value = ""; $("csv15ObservedAt").value = "";
    $("feedStatus").textContent = "Práctica sintética cargada. No se ha consultado la API pública.";
    state.notice = "Datos inventados cargados. La casilla de reglas sigue sin marcar: no puedes afirmar que comprobaste una regla real a partir de esta práctica.";
    update(now, {forceChart: true});
  }

  function reset() {
    state.feedGeneration++; state.dataGeneration++; state.feedBusy = false; $("publicFeedBtn").disabled = false; $("publicFeedBtn").textContent = "Leer velas públicas";
    for (const id of CONTRACT_FIELDS) $(id).value = "";
    $("referenceVerified").checked = false;
    for (const side of ["yes", "no"]) for (const [name] of QUOTE_FIELDS) $(`${side}_${name}`).value = "";
    $("csv5").value = ""; $("csv15").value = ""; $("csv5ObservedAt").value = ""; $("csv15ObservedAt").value = "";
    $("feedStatus").textContent = "Sin conexión iniciada. La lectura empieza solo al pulsar el botón.";
    state.practice = false; state.touched = false; state.notice = "Datos limpiados. Puedes empezar una revisión manual.";
    state.datasets = {300: null, 900: null}; state.chartResults = {300: null, 900: null}; state.imports = {300: "Sin archivo.", 900: "Sin archivo."};
    update(Date.now(), {forceChart: true});
  }

  function exportReview() {
    update();
    const snapshot = {
      schema: "roxy-crypto-hour-manual-review/v1", exportedAt: new Date().toISOString(),
      provenance: state.practice ? "SYNTHETIC_PRACTICE" : "MANUAL_UNVERIFIED", contract: readContract(),
      review: state.result, candles: Object.fromEntries([300, 900].map(interval => [String(interval), state.datasets[interval] ? {source: state.datasets[interval].source, provider: state.datasets[interval].provider || null, requestedAt: state.datasets[interval].requestedAt || null, observedAt: state.datasets[interval].observedAt, rows: state.datasets[interval].rows, analysis: state.chartResults[interval]} : null])),
      execution_allowed: false, actionable: false, external_delivery: false,
      note: "Revisión local sin probabilidad validada. No introduzcas credenciales en los campos; comprueba el archivo antes de compartirlo. No autoriza operaciones."
    };
    const blob = new Blob([JSON.stringify(snapshot, null, 2)], {type: "application/json"});
    const url = URL.createObjectURL(blob); const link = document.createElement("a");
    link.href = url; link.download = `roxy-crypto-revision-${new Date().toISOString().slice(0, 10)}${state.practice ? "-SINTETICA" : ""}.json`;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    state.notice = "Revisión exportada a tu equipo. El archivo contiene los importes y los datos que introdujiste; revísalo antes de compartirlo.";
    $("notice").textContent = state.notice;
  }

  let pendingUpdate;
  for (const id of [...CONTRACT_FIELDS, "referenceVerified", ...["yes", "no"].flatMap(side => QUOTE_FIELDS.map(([name]) => `${side}_${name}`))]) {
    $(id).addEventListener("input", () => { state.touched = true; clearTimeout(pendingUpdate); pendingUpdate = setTimeout(() => update(Date.now(), {forceChart: true}), 120); });
  }
  $("evaluateBtn").addEventListener("click", () => { state.touched = true; state.notice = "Revisión actualizada con tu hora observada; ninguna cotización se ha refrescado automáticamente."; update(Date.now(), {forceChart: true}); $("resultHeading").scrollIntoView({behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start"}); });
  $("practiceBtn").addEventListener("click", loadPractice);
  $("resetBtn").addEventListener("click", reset);
  $("exportBtn").addEventListener("click", exportReview);
  $("csv5").addEventListener("change", event => importCsv(300, event.target.files[0]));
  $("csv15").addEventListener("change", event => importCsv(900, event.target.files[0]));
  $("publicFeedBtn").addEventListener("click", fetchPublicPanels);
  for (const [id, interval] of [["csv5ObservedAt", 300], ["csv15ObservedAt", 900]]) $(id).addEventListener("input", () => {
    if (state.datasets[interval]?.source === "MANUAL_CSV") state.datasets[interval].observedAt = $(id).value.trim();
    update(Date.now(), {forceChart: true});
  });
  for (const [id, interval] of [["chart5Btn", 300], ["chart15Btn", 900]]) $(id).addEventListener("click", () => { state.interval = interval; update(Date.now(), {forceChart: true}); });
  if (typeof ResizeObserver === "function") new ResizeObserver(() => renderChart(readContract(), true)).observe($("priceChart").parentElement);
  else window.addEventListener("resize", () => renderChart(readContract(), true));
  update(Date.now(), {forceChart: true});
  setInterval(() => update(), 1000);
})();
