# Resumen Maestro de Roxy Trading

Fecha de contexto: 2026-06-08
Proyecto actual: `/Users/robertograu/roxy_trading`
App local: `http://127.0.0.1:8501`

## Objetivo Del Proyecto

Roxy Trading es un asistente de trading para analizar acciones, opciones y criptomonedas usando una estrategia principal basada en medias moviles, confirmacion multi-timeframe, volumen, riesgo y memoria de resultados.

El sistema debe responder de forma clara:

- `Operar`
- `Mirar Call`
- `Esperar`
- `No operar`

Cada decision debe traer entrada, stop, objetivos 2%, 5% y 10%, tamano de posicion para cuenta pequena, explicacion simple y ruta manual hacia la plataforma correspondiente.

Roxy funciona como asistente de decision y preparacion. La ejecucion real queda bloqueada hasta tener credenciales, paper trading probado, controles de riesgo y aprobacion explicita.

## Estado Actual Del Proyecto

### Implementado

- Dashboard profesional en Streamlit.
- Scanner de mercado para acciones y criptomonedas.
- Timeframes principales: `15m`, `1h`, `4h`, `1d`.
- Lectura de premarket/postmarket para acciones intradia cuando la fuente lo permite.
- Estrategia base con SMA `20`, `40`, `100`, `200`.
- Grafica principal con precio, medias, EMA9, bandas de Bollinger, volumen, soporte, resistencia, entrada, stop y targets.
- Trade Plan por simbolo.
- AI Trade Brief por simbolo.
- Panel de riesgo para cuenta inicial de `$500`.
- Objetivos visuales: 2%, 5%, 10%.
- Alertas inteligentes con filtro de ruido.
- Memoria de Roxy para medir senales que llegan a 2%, 5%, 10% o stop.
- Roxy Lab para comparar estrategias y proponer ajustes.
- Modo Estudios para aprender estrategias con ejemplos.
- Opciones con flujo inicial para calls/puts y soporte para datos profesionales si se configura proveedor.
- Plataformas en modo preview/manual: Crypto.com, Charles Schwab y Webull.
- Roxy Voice como prototipo de voz local.
- Boveda local de credenciales cifrada para integraciones futuras.

### Estado De Ejecucion

Roxy no envia ordenes reales todavia.

El sistema prepara tickets manuales y payloads preview, pero mantiene bloqueado el envio real por seguridad. Los adaptadores live estan marcados como `PREVIEW_ONLY` en `platform_execution.py`.

Para ejecucion real faltan:

- Credenciales reales por plataforma.
- OAuth/aprobacion de Schwab.
- API key/secret de Crypto.com Exchange.
- Webull OpenAPI si la cuenta es elegible.
- Paper trading con historial suficiente.
- Confirmacion manual final antes de activar cualquier envio real.

## Lo Que Roxy Puede Analizar

### Mercados

- Acciones.
- ETFs.
- Opciones sobre acciones/ETFs.
- Criptomonedas.

### Watchlists Relevantes

- `data/watchlist_stocks.txt`
- `data/watchlist_crypto.txt`
- `data/watchlist_ai_core.txt`
- `data/watchlist_ai_development.txt`
- `data/watchlist_crypto_ai_development.txt`

Watchlist IA/desarrollo objetivo: NVDA, AMD, AAPL, MSFT, GOOGL, META, AMZN, PLTR, AVGO, ARM, TSM, ASML, MU, SMCI, CRWD, NET, SNOW, MDB, NOW, AI.

## Informacion Que Roxy Usa

- Precio OHLCV.
- Volumen y volumen relativo.
- SMA20, SMA40, SMA100, SMA200.
- EMA9.
- Bandas de Bollinger.
- ATR / riesgo relativo.
- Soporte y resistencia de rango reciente.
- Tendencia por timeframe.
- Confirmacion 1h.
- Entrada 15m.
- Score de confluencia.
- Backtest por estrategia.
- Memoria historica por simbolo y estrategia.
- Estado de sesion de mercado.
- Datos de opciones cuando existen: DTE, delta, gamma, theta, vega, IV, bid, ask, spread, volumen, open interest, break-even y max loss.

## Regla Principal De Alertas

Roxy solo debe alertar una oportunidad real cuando:

- 1h confirma tendencia.
- 15m da entrada.
- Volumen acompana.
- Riesgo esta controlado.
- Target minimo de 2% es viable.
- La estructura no esta en AVOID.
- La memoria no penaliza esa estrategia.
- Los datos estan frescos.

Si una condicion falla, Roxy debe decir que movimiento especifico esta esperando.

Ejemplos:

- `WATCH`: esperar gatillo BUY en 15m mientras 1h se mantiene valido.
- `BUY`: operar solo con entrada, stop, targets y tamano definidos.
- `AVOID`: no operar porque la estructura esta bajista, debajo de medias o sin target/riesgo valido.

## Estrategias Implementadas

Estas estrategias estan conectadas en `trade_brief.py`, `symbol_detail.py`, `accuracy_tracker.py`, `roxy_ai.py` y `streamlit_app.py`.

### 1. Canal Alcista

Busca continuidad cuando las medias estan ordenadas y el precio respeta la estructura.

Lectura esperada:

- SMA20 > SMA40 > SMA100 > SMA200.
- Precio sobre medias principales.
- Pullback sano hacia EMA9/SMA20/SMA40.
- Entrada solo si 15m confirma y 1h mantiene tendencia.

### 2. Canal Lateral

Busca rango, soporte/resistencia y posibles rupturas controladas.

Lectura esperada:

- Precio comprimido en canal.
- No hay tendencia limpia.
- Comprar solo ruptura con volumen o rebote claro en soporte.
- Evitar compras pegadas al techo del canal.

### 3. Pullback

Busca retroceso dentro de tendencia sana.

Lectura esperada:

- Tendencia principal alcista.
- Precio retrocede hacia media clave.
- No se persigue precio extendido.
- Entrada se activa cuando 15m vuelve a BUY y el riesgo es medible.

### 4. Rebote En Media

Busca rechazo o recuperacion sobre medias importantes.

Lectura esperada:

- Precio toca o se acerca a SMA20/SMA40/EMA9.
- Vela de rechazo o recuperacion.
- Volumen acompana.
- Stop queda cerca y target 2% es viable.

### 5. Cruce De Medias

Busca transicion de estructura.

Lectura esperada:

- SMA20 empieza a cruzar o sostenerse sobre SMA40.
- Precio recupera medias.
- Confirmacion 1h/15m antes de operar.
- Evitar senales tempranas sin volumen.

### 6. Tendencia Bajista

Filtro defensivo para evitar compras debiles.

Lectura esperada:

- Precio debajo de SMA200 o medias desordenadas hacia abajo.
- Roxy bloquea compras.
- Esperar recuperacion sobre SMA200 y cruce positivo SMA20/SMA40.

### 7. Canal Fortalecido De Largo Plazo

Detectado en la grafica de detalle.

Lectura esperada:

- SMA20/SMA40 sostienen el avance.
- Precio mantiene canal principal.
- Se busca pullback controlado, no perseguir precio extendido.

### 8. Tendencia Lateral De Largo Plazo

Detectado en la grafica de detalle.

Lectura esperada:

- Precio trabaja alrededor de SMA100/SMA200.
- Roxy espera ruptura o rebote claro.
- Riesgo debe estar cerca del soporte o de la media validada.

### 9. Banda / Nube De Volatilidad

Contexto visual para detectar expansion, compresion y extremos.

Lectura esperada:

- Bandas de Bollinger muestran espacio o compresion.
- No es gatillo por si sola.
- Se usa junto con medias, volumen y estructura.

### 10. Rebote En Soporte

Detectado cuando el precio esta cerca del piso del canal.

Lectura esperada:

- Precio cerca de soporte.
- Esperar vela de rechazo.
- Confirmar 15m antes de operar.

## Estrategias Nuevas Recibidas Para Integrar

Estas estrategias vienen de las fotos y del PDF `MASTERCLASS DE SALTOS.pdf`. Deben entrar como nuevas familias formales en el motor, estudios, backtest y laboratorio.

### 1. Salto Por Cruce De EMA En Horas

Requisitos:

- Formacion de canal alcista.
- Precio cierra tocando EMA9.
- Medias 20 y 40 ordenadas en canal sostenido.
- Distancia sana entre EMA9 y SMA20.
- Canal iniciando.
- Confirmar en 2h y 4h.
- Comprar 5 minutos antes del cierre del mercado.

### 2. Salto Por Distancia Entre Medias Moviles

Requisitos:

- Precio sube o baja de forma continua.
- Las medias se separan por fuerza del movimiento.
- Precio cierra sobre la media movil.
- Osciladores superiores cierran o se debilitan.
- En 1h, 2h y 4h deben cerrar osciladores.
- Confirmar en 15m separacion entre canal y tendencia.
- Comprar 5 minutos antes del cierre del mercado.

### 3. Salto Por Ruptura De Maximos Historicos

Requisitos:

- Precio rompe maximos o minimos historicos.
- Ruptura confirmada al mantenerse sobre resistencia.
- Revisar estructura del canal contra separacion de medias.
- Osciladores abiertos con espacio para salto.
- Precio cierra sobre la resistencia.
- Comprar 5 minutos antes del cierre del mercado.

### 4. Salto Por Cruce De EMA En 2 Horas

Requisitos:

- Formacion de canal bajista.
- EMA9 cruzando SMA.
- Precio cierra en el cruce de EMA.
- Debe tener espacio en Bollinger para saltar.
- Confirmar con 1h y 4h.
- Precio debajo de EMA9 en 4h.
- Comprar 5 minutos antes del cierre del mercado.

### 5. Salto Para Cambio De Canal

Requisitos:

- Precio forma canal bajista o alcista.
- Confirmar si el canal es corto o largo plazo.
- Observar cuando el canal deja de formar nuevos maximos o minimos.
- Medias del canal se separan de las medias de tendencia.
- EMA9 y SMA20 presentan debilidad.
- Comprar 5 minutos antes del cierre del mercado.

## Arquitectura Principal

### UI

- `streamlit_app.py`: app principal.
- Tabs actuales: Centro, Plan de trade, Riesgo $500, Plataformas, Opciones, Backtest, Precision, Estudios, Roxy Lab, Voz.
- `ROXY_LOGO_SVG`: logo integrado.

### Estrategia Y Brief

- `moving_average_strategy.py`: calculo de medias y senales SMA.
- `trade_brief.py`: decision final por simbolo, explicacion, targets, riesgo y plan directo.
- `symbol_detail.py`: grafica, datos de simbolo, estrategia visual y deteccion de referencias.
- `trade_plan.py`: logica complementaria de planes de operacion.

### IA, Memoria Y Alertas

- `roxy_ai.py`: brief IA, memoria, laboratorio, aprendizaje y estado.
- `accuracy_tracker.py`: precision, targets alcanzados y stops.
- `smart_alerts.py`: filtro de alertas sin ruido.
- `alerts/roxy_ai_memory.json`: memoria persistente.
- `alerts/roxy_learning_journal.csv`: diario de aprendizaje.
- `alerts/roxy_ai_brief.json`: ultimo brief IA.
- `alerts/roxy_ai_brief.txt`: version legible del brief.

### Opciones

- `options_strategy.py`: escaneo y scoring de contratos.
- Soporte actual:
  - Yahoo/basic como fallback.
  - Tradier si existe `TRADIER_ACCESS_TOKEN`.
  - Deteccion de ORATS, Polygon, ThetaData y MarketData.app como proveedores posibles.

### Plataformas

- `platform_router.py`: decide ruta por activo.
- `platform_execution.py`: preview, guardrails y estado de credenciales.
- `schwab_preview.py`: payload previewOrder para Schwab.
- `platform_credentials.py`: boveda local de credenciales.

### Voz

- `tools/voice_assistant.py`: respuestas locales.
- `tools/voice_service.py`: servicio FastAPI prototipo.
- Puede responder sobre oportunidades, aprendizaje, laboratorio, alertas y cuenta simulada.

## Flujo Ideal De Uso

1. Roxy escanea watchlists.
2. Encuentra simbolo con estructura.
3. Valida 1h.
4. Espera entrada 15m.
5. Revisa volumen.
6. Calcula stop y riesgo.
7. Verifica target minimo 2%.
8. Consulta memoria.
9. Decide: operar accion, mirar call, esperar o no operar.
10. Prepara ruta manual a plataforma.
11. Usuario ejecuta manualmente en Crypto.com, Schwab o Webull.
12. Resultado se registra en memoria para aprendizaje.

## Gestion De Riesgo

Configuracion objetivo:

- Cuenta inicial: `$500`.
- Riesgo base por trade: `1%`.
- Riesgo aproximado por operacion: `$5`.
- Roxy debe calcular cuantas acciones, fracciones o contratos caben en ese riesgo.
- Opciones deben ser `solo paper` si el max loss no cabe en 1R.
- No perseguir entradas sin stop definido.

Regla de proteccion:

- Si stop no existe, no operar.
- Si riesgo supera 3.5%, esperar.
- Si target minimo 2% no es viable, no operar.
- Si volumen no acompana, esperar.

## Estado Actual De Precision

Roxy todavia esta juntando evidencia. La precision real no debe considerarse confiable hasta tener suficientes senales cerradas.

Objetivo minimo antes de subir tamano:

- 30 senales medidas.
- Separadas por estrategia.
- Cada una marcada como llego a 2%, llego a 5%, llego a 10% o toco stop.

Hasta entonces, Roxy debe trabajar como asistente de decision y paper/preview, no como motor automatico.

## Tareas Pendientes Prioritarias

### Alta Prioridad

- Integrar formalmente las 5 estrategias de saltos en `trade_brief.py`, `symbol_detail.py`, `roxy_ai.py`, `accuracy_tracker.py` y `streamlit_app.py`.
- Leer y convertir `MASTERCLASS DE SALTOS.pdf` en reglas de estrategia y lecciones del modo Estudios.
- Anadir timeframe `2h` si la fuente de datos lo permite o derivarlo desde velas intradia.
- Mejorar el grafico principal con velas mas claras, zonas de entrada, zonas de soporte/resistencia, bandas, senales y etiquetas menos saturadas.
- Hacer que el Trade Plan muestre mas directo: `Operar / Mirar Call / Esperar / No operar`.
- Registrar cada senal WATCH/BUY/AVOID para medir resultados reales.

### Media Prioridad

- Mejorar opciones con proveedor profesional de Greeks.
- Integrar Tradier o Polygon/ORATS como fuente principal.
- Crear backtest visual especifico para cada estrategia nueva de saltos.
- Separar resultados por estrategia, simbolo, timeframe y mercado.
- Mejorar Roxy Lab para recomendar promover, pausar o endurecer cada estrategia.
- Mejorar estudios con ejemplos reales detectados por Roxy.

### Seguridad Y Ejecucion

- Mantener ejecucion real apagada.
- Probar primero preview.
- Luego paper.
- Luego live con confirmacion doble.
- Anadir logs de cada orden manual y resultado.
- No guardar claves sin cifrado.
- No enviar ordenes desde UI hasta que el sistema tenga pruebas suficientes.

### Notificaciones

- Mantener alertas locales por archivo/Mac.
- Email es la mejor via al telefono si el correo tiene push.
- Webhook/Slack/Discord estan preparados, pero no configurados.
- No usar Telegram.

## Datos Y Archivos Importantes

- Base de datos: `db/roxy.db`.
- Historial de scans: `db/scan_history.csv`.
- Alertas: `alerts/`.
- Output de scanner: `output/`.
- Logs: `logs/`.
- Tests: `tests/`.
- Scripts: `tools/`.

## Comandos Utiles

Abrir app:

```bash
streamlit run streamlit_app.py
```

Scanner live:

```bash
python tools/ma_live.py
```

Escaneo diario:

```bash
python tools/ma_daily.py
```

Backtest:

```bash
python tools/ma_backtest.py
```

Tests:

```bash
PYTHONPATH=. .venv/bin/pytest -q
```

## Como Cargar Este Contexto En Un Proyecto Nuevo

Para continuar en un proyecto nuevo, copiar este archivo como primer contexto:

```text
MASTER_CONTEXT.md
```

El nuevo proyecto debe empezar leyendo este documento antes de tocar codigo. Prioridad inicial:

1. Mantener la filosofia de Roxy: asistente de decision, no ejecucion impulsiva.
2. Preservar la regla de alertas inteligentes.
3. Integrar las estrategias de saltos como familias formales.
4. Mantener cuenta de $500 y riesgo 1% como perfil base.
5. Reusar memoria y backtests antes de aumentar tamano.
6. Mantener ejecucion real bloqueada hasta pruebas.

## Proximo Paso Recomendado

El siguiente bloque de trabajo debe ser:

1. Extraer el PDF `MASTERCLASS DE SALTOS.pdf`.
2. Crear modulo `salto_strategies.py`.
3. Anadir las 5 estrategias de saltos al motor.
4. Agregarlas al modo Estudios.
5. Agregarlas a Roxy Lab y backtest.
6. Actualizar la grafica para marcar cada setup de salto con etiquetas visuales.

Este archivo queda como contexto maestro para que Roxy Trading continue sin perder direccion.
