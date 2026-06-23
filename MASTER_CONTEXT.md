# Resumen Maestro de Roxy Trading

Fecha de contexto: 2026-06-11
Proyecto actual: `/Users/robertograu/roxy_trading`
App local: `http://127.0.0.1:3000`

## Objetivo Del Proyecto

Roxy Trading es un asistente de trading para analizar acciones, opciones y criptomonedas usando una estrategia principal basada en medias moviles, confirmacion multi-timeframe, volumen, riesgo y memoria de resultados.

La cadencia de desarrollo queda guardada en `ROXY_DEVELOPMENT_CADENCE.md`. Ese archivo define el objetivo superior: avanzar Roxy hacia una aplicacion comercial, clara, segura y rentable como producto. No usar cadencias de reporte como fuente de trading live: precios, senales y alertas deben operar en segundos y mostrar latencia/fuente.

La cadencia tambien tiene un runner local preparado: `tools/roxy_development_cadence.py` con LaunchAgent `deployment/com.roxy.development-cadence.plist`, deshabilitado por defecto. Es solo auditoria: no edita codigo ni opera; no sustituye el dashboard realtime.

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
- Filtro multitemporal de canal/tendencia: Semana -> Dia -> Hora -> 15m.
- Memoria de Roxy para medir senales que llegan a 2%, 5%, 10% o stop.
- Contexto de newsletters semanales en `data/weekly_newsletters.jsonl` mediante `market_newsletter.py`. Se usa como contexto macro/sectorial y fuente para `market_news`, no como senal directa de compra.
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
- Duracion estimada de tendencia/canal segun clase: tendencia 1-3 meses; canal largo 10-12 dias; canal corto/contra tendencia 5-8 dias.
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
- El gatillo de 15m no pelea contra el canal/tendencia mayor.

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

### 11. Multitemporalidad Canal/Tendencia

Regla aprendida de clase:

- La tendencia mayor suele durar `1-3 meses aprox`.
- En tendencia alcista:
  - Canal alcista largo plazo: `10-12 dias aprox`.
  - Canal alcista corto plazo, canal bajista o lateral: `5-8 dias aprox`.
- En tendencia bajista:
  - Canal bajista largo plazo: `10-12 dias aprox`.
  - Canal bajista corto plazo, canal alcista o lateral: `5-8 dias aprox`.
- En tendencia lateral:
  - Canal alcista piso a techo y canal bajista techo a piso: `10-12 dias aprox`.
  - Canal alcista, bajista o lateral corto: `5-8 dias aprox`.

Cadena operativa:

- Semana: canal -> Dia: tendencia.
- Dia: canal largo plazo -> Hora: tendencia largo plazo.
- Hora: canal -> 15m: gatillo/tendencia de entrada.

Uso en Roxy:

- 15m nunca es suficiente solo.
- Si el canal mayor bloquea, Roxy baja probabilidad o marca `No operar`.
- Si 1h/dia confirman, 15m puede activar entrada solo con volumen, stop y target valido.

### 12. Patron Imparable EMA9

Aprendido del video `01-15-Masterclass Patron Imparable 15 Enero 2026.mp4`.

Lectura esperada:

- EMA9 guia o recupera el movimiento.
- SMA20 y SMA40 sostienen el canal o muestran recuperacion.
- SMA200 no bloquea compras.
- Bollinger deja espacio para continuidad.
- Evitar si SMA20 esta lateral/invertida sin recuperacion.
- Evitar si EMA9 cruza bajista o el movimiento parece manipulacion sin cierre confirmado.
- 15m y 1h deben confirmar antes de operar.

Uso en Roxy:

- Entra como familia formal `Patron imparable EMA9`.
- Puede activar `WATCH` cuando hay recuperacion de EMA9/SMA20 pero falta volumen o confirmacion.
- Puede activar `BUY` solo cuando EMA9, SMA20/SMA40, SMA200, bandas, volumen y cierre estan alineados.
- No se opera una media aislada; exige estructura completa.

### 13. Checklist Y No Negociables

Aprendido del video `04-12-Check List y No Negociables.mp4`.

Reglas principales:

- Revisar FED/earnings antes de operar.
- Identificar tendencia y canal en hora.
- Revisar panorama completo: 15m, hora, dia y semanal.
- Trazar lateralidades/canales y observar Bollinger en hora/15m.
- Operar solo la estrategia definida, no improvisar.
- Respetar plan, stop, target y limite de perdida.
- No sobreoperar.
- No entrar en vela llena.
- No entrar expuesto fuera de Bollinger.
- En lateralidad, operar piso a techo o techo a piso.
- No tomar posicion pegada a un punto de rebote contrario.
- No operar canal/tendencia agotada por dias.

Uso en Roxy:

- `trade_brief.py` bloquea entradas por no negociables medibles: exposicion a Bollinger y vela demasiado llena.
- `smart_alerts.py` usa esos no negociables para evitar alertas limpias cuando la entrada no esta limpia.
- `streamlit_app.py` incluye la guia de estudio `Checklist y no negociables`.
- Roxy debe explicar que falta antes de pasar de `WATCH` a `BUY`.

### 14. Busqueda/Rebote En Media Movil Con Confirmacion

Aprendido de:

- `02-19 - MasterClass Busqueda de la Media Movil.mp4`.
- `03-03-Repaso de Busqueda de la Media Movil 3 Marzo 2026.mp4`.
- `06-05-Rebote en Media con Confimacion 05 Junio 2026.mp4`.

Reglas principales:

- No operar una media aislada; la media debe actuar como zona de piso/techo dentro de una estructura.
- En compras, el precio debe estar sobre SMA200 o recuperarla con cierre fuerte.
- La zona operable es EMA9/SMA20/SMA40, con cierre verde o rechazo claro.
- 15m debe dar entrada y 1h debe sostener tendencia.
- El volumen debe acompanar y el stop debe quedar medible debajo de la zona.
- Si la estructura esta bajista o debajo de SMA200, Roxy bloquea compras y espera recuperacion.
- Target minimo 2% debe ser viable antes de alertar.

Uso en Roxy:

- Entra como familia formal `Busqueda de media movil con confirmacion`.
- `salto_strategies.py` detecta toque/rebote en EMA9/SMA20/SMA40 con contexto no bajista.
- Roxy la usa para separar rebote sano de cruce, ruptura o simple lateralidad.

### 15. EMA9 Toques Y Reinicio

Aprendido de `03-25-Masterclass EMA 9  25 Marzo 2026.mp4`.

Reglas principales:

- EMA9 puede guiar un canal fuerte, pero no se deben tomar toques ilimitados.
- En canal alcista, Roxy permite hasta 4 eventos de toque EMA9 si SMA20/SMA40 no se debilitan.
- Si hay mas de 4 toques, Roxy debe esperar reinicio/separacion nueva entre EMA9 y SMA antes de promover el setup.
- En canal bajista, EMA9 se usa como rechazo defensivo; calls quedan bloqueados salvo recuperacion.
- En lateralidad EMA9 produce ruido; exigir soporte/resistencia o ruptura limpia.

Uso en Roxy:

- `Patron imparable EMA9` ahora revisa capacidad de toques EMA9 antes de promover a setup fuerte.
- La explicacion de Roxy debe mencionar si espera reinicio o nueva separacion.

### 16. Timing De Ejecucion 1m/5m

Aprendido de:

- `03-31-Clase Trimestral Timing 31 Marzo 2026.mp4`.
- `04-07-Clase Timinng 1-Min 07 Abril 2026.mp4`.
- `05-05-Refuerzo de Saltos 05 Mayo 2026.mp4`.

Reglas principales:

- 1m y 5m no deciden una operacion; solo afinan el precio de entrada.
- La decision real debe venir de 15m como gatillo, 1h como tendencia y 2h/4h como validacion del salto.
- Si 1m muestra BUY pero 15m/1h no validan, Roxy debe marcar `Esperar` o `No operar`.
- La entrada se busca cerca del cierre solo cuando el plan completo ya esta valido: estructura, volumen, stop, target 2%, no negociables y memoria sana.
- No perseguir velas de micro-timeframe; si el precio se fue lejos de entrada, esperar nuevo pullback o nueva vela limpia.

Uso en Roxy:

- `trade_brief.py` agrega el check `1m/5m solo timing`.
- `smart_alerts.py` bloquea alertas de micro-timeframe si no hay confirmacion superior.
- El Trade Plan explica que 1m/5m ayudan a precision, pero no autorizan BUY por si solos.
- El detector de videos ahora reconoce `timing` y `timinng` para seguir capturando clases nuevas aunque el nombre venga con typo.

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
- `multitimeframe_rules.py`: reglas de duracion de tendencia/canal y lectura Semana-Dia-Hora-15m.
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

Actualizacion 2026-06-11:

- `roxy_ai.py` actualiza cada senal con `current_gain_pct`, `current_drawdown_pct`, `best_target_hit`, `best_target_pct`, `current_reward_r`, `best_reward_r` y `outcome_state`.
- `update_alert_outcomes()` mide el resultado usando el mejor precio observado (`max_price`), no solo el precio actual. Si una senal llego a 5% y luego retrocede, Roxy conserva que llego a 5%.
- `accuracy_tracker.py` expone esos campos en alertas reales y en el diario WATCH.
- La pantalla `Precision / rendimiento` muestra una tabla visible de `Ultimas senales medidas` con fuente, simbolo, estrategia, resultado, mejor target, movimiento actual, mejor movimiento y R.
- Roxy separa `stopped_after_target` de `stopped_before_target` para no castigar igual una senal que dio salida parcial y luego retrocedio.
- Estados de aprendizaje actuales: `HIT_2PCT`, `HIT_5PCT`, `HIT_10PCT`, `HIT_2PCT_THEN_STOP`, `HIT_5PCT_THEN_STOP`, `HIT_10PCT_THEN_STOP`, `STOP`, `NEAR_2PCT`, `DANGER_STOP` y abierto/pendiente.

Objetivo minimo antes de subir tamano:

- 30 senales medidas.
- Separadas por estrategia.
- Cada una marcada como llego a 2%, llego a 5%, llego a 10% o toco stop.

Hasta entonces, Roxy debe trabajar como asistente de decision y paper/preview, no como motor automatico.

## Tareas Pendientes Prioritarias

### Alta Prioridad

- Completar backtest visual y memoria por cada estrategia de saltos en `accuracy_tracker.py`, `roxy_ai.py` y `streamlit_app.py`.
- Leer y convertir cualquier video/PDF nuevo en reglas medibles de estrategia y lecciones del modo Estudios.
- Anadir timeframe `2h` si la fuente de datos lo permite o derivarlo desde velas intradia.
- Mejorar el grafico principal con velas mas claras, zonas de entrada, zonas de soporte/resistencia, bandas, senales y etiquetas menos saturadas.
- Hacer que el Trade Plan muestre mas directo: `Operar / Mirar Call / Esperar / No operar`.
- Registrar cada senal WATCH/BUY/AVOID para medir resultados reales y cerrar automaticamente cuando toca target o stop.

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
- Video localizado: `/Users/robertograu/Downloads/11-09-MASTERCLASS DE MEDIAS MOVILES 9 Noviembre 2025.mp4`.
- Material extraido del video: `training_videos/masterclass_medias_2025_11_09/`.
- Notas de estudio del video: `training_videos/masterclass_medias_2025_11_09/notes/masterclass_medias_moviles.md`.
- Pipeline de aprendizaje por videos y materiales: `tools/video_learning_ingest.py`.
- Flujo documentado: `docs/video_learning_workflow.md`.
- Indice dinamico de videos/materiales para Estudios: `training_videos/video_learning_index.json`.
- Coordinacion entre pestanas Codex: `training_videos/ROXY_LEARNING_SYNC.md`.
- Revision automatica cuando no hay videos nuevos: `training_videos/idle_learning_review.md` y `training_videos/idle_learning_review.json`.
- LaunchAgent preparado: `deployment/com.roxy.video-learning.plist` (`com.roxy.video-learning`, cada 35 min / 2100 segundos).
- En la pestana `Estudios`, los expanders `Materiales de estudio analizados por Roxy` y `Biblioteca de videos estudiados por Roxy` permiten revisar notas y ejecutar `Escanear videos ahora`.
- Al analizar videos/materiales nuevos, Roxy puede moverlos al archivo externo `/Volumes/RoxyData/RoxyVideosAnalizados` usando `--archive-dir`.
- El boton de la app usa ese archivo externo si el disco `RoxyData` esta conectado.
- El LaunchAgent `com.roxy.video-learning` fue actualizado con `--archive-dir /Volumes/RoxyData/RoxyVideosAnalizados --archive-indexed --idle-review`.
- El pipeline ahora procesa tambien PDFs, imagenes, Office/texto/csv y los guarda en `materials` dentro de `training_videos/video_learning_index.json`.
- Biblioteca grande de estudio Natalia: `/Volumes/RoxyData/natalia_trading_copy_20260614_175259` contiene 162 videos y 80 materiales. Estado/worker: `training_videos/NATALIA_LEARNING_STATUS.md`, `tools/natalia_learning_worker.sh`, log `logs/natalia_learning_worker.log`. Se procesa por lotes sin mover la biblioteca original. Al terminar, el worker genera `training_videos/NATALIA_LEARNING_SUMMARY.md` con lo aprendido, reglas para Roxy, mejoras y fuentes consideradas.
- Materiales de estudio indexados al 2026-06-12: 69 PDFs/apuntes/Office, incluyendo VWAP, Liquidity, Dark Pools, Market Making, FOMC, Economic Cycle, Fundamental Ratios, Strategy Pair Trading, Hedging, Cointegration, Trading Technique, Complete Investing Course, Cryptocurrency Investing Course, Forex Foundation Trading Course, Market/Stock Exchange, ECN/commissions, order types, Level 1/Level 2/Time and Sales, expectancy, risk/money management, psicologia, sesgos, short squeeze, trend analysis y documentos de fundamentales.
- Archivos internos detectados por accidente fueron retirados del indice y movidos a `/Volumes/RoxyData/RoxyVideosAnalizados/No_Estudio`; no se borraron.
- El conocimiento de clase ahora entra al analisis mediante `apply_learned_strategy_brain()` en `salto_strategies.py`.
- Ese cerebro aprendido detecta estrategias tipo salto, enriquece el setup SMA con `learned_strategy`, `learned_strategy_status`, gatillo, razon, requisitos y timeframes.
- `build_symbol_trade_brief()` ahora expone `learned_strategy` y lo usa en razones, checks y explicacion de Roxy antes de decidir `Comprar accion`, `Mirar call`, `Esperar` o `No operar`.
- Plan operativo 24h: `daily_opportunity_plan.py` convierte cada brief en `Operar ahora`, `Proxima entrada`, `Vigilar`, `Esperar datos` o `No operar`.
- El plan operativo 24h ahora incluye `mtf_alignment`, `mtf_channel`, `mtf_duration` y explicacion multitemporal para evitar gatillos 15m contra canal mayor.
- El plan se guarda en `alerts/roxy_daily_opportunity_plan.json` y tambien aparece en `alerts/roxy_ai_brief.txt`, `alerts/roxy_status.json`, Centro y Alertas IA 24h.
- La prediccion de Roxy es operativa: probabilidad, gatillo esperado, invalidacion, entrada, stop y objetivos 2/5/10. No es garantia ni orden automatica.
- Regla diaria: operar solo cuando 1h confirma, 15m da entrada, volumen acompana, riesgo es bajo y target 2% es viable.
- Filtro anti-ruido actualizado: aunque todo lo demas este bien, Roxy no debe alertar si la vela esta demasiado llena o el precio esta expuesto fuera de Bollinger.
- Videos ya indexados por el pipeline nuevo:
  - `11-09-MASTERCLASS DE MEDIAS MOVILES 9 Noviembre 2025.mp4`.
  - `01-15-Masterclass Patron Imparable 15 Enero 2026.mp4`.
  - `02-28-Masterclass Bandas de Bollinger.mp4`.
  - `02-19 - MasterClass Busqueda de la Media Movil.mp4`.
  - `03-03-Repaso de Busqueda de la Media Movil 3 Marzo 2026.mp4`.
  - `03-06-Masterclass Timing 6 Marzo 2026.mp4`.
  - `03-09-Canales y Tendencias 09 Marzo 2026.mp4`.
  - `03-24-Marcacion de Canales y Tendencias 24 Marzo 2026.mp4`.
  - `03-25-Masterclass EMA 9  25 Marzo 2026.mp4`.
  - `03-25-Masterclass EMA 9  25 Marzo 2026_2.mp4`.
  - `03-31-Clase Trimestral Timing 31 Marzo 2026.mp4`.
  - `04-07-Clase Timinng 1-Min 07 Abril 2026.mp4`.
  - `04-12-Check List y No Negociables.mp4`.
  - `05-05-Refuerzo de Saltos 05 Mayo 2026.mp4`.
  - `05-08-Debilidad en las Tendencias y Canales 08 Mayo 2026.mp4`.
  - `05-26-Como Identificar y Operar Lateralidades 26 Mayo 2026.mp4`.
  - `05-26-Cruces de Medias Moviles.mp4`.
  - `05-28-Clase Trimestral 28 Mayo 2026.mp4`.
  - `06-02-Clase Trimestral 02 Junio 2026.mp4`.
  - `06-05-Rebote en Media con Confimacion 05 Junio 2026.mp4`.
- Videos de soporte/plataforma procesados y archivados en `/Volumes/RoxyData/RoxyVideosAnalizados`; se usan como contexto operativo, no como gatillos tecnicos:
  - `04-08-Soporte Classroom  08 Abril 2026.mp4`.
  - `04-15-Soporte Tecnico 15 Abril 2026.mp4`.
  - `05-20-Soporte Webull 20 Mayo 2026.mp4`.
  - `06-01-Soporte FED Parte 2 01 Junio 2026.mp4` aporta filtro macro/FED.
- `tools/video_learning_ingest.py` reconoce ahora palabras clave como `check list`, `checklist`, `negociable`, `negociables`, `patron`, `imparable`, `media`, `medias`, `ema`, `sma`, `salto`, `canal`, `lateralidad`, `VWAP`, `liquidity`, `FOMC`, `economic`, `valuation`, `fundamental`, `dark pools`, `short squeeze`, `pair trading`, `hedging` y `trend analysis`.
- `tools/video_learning_ingest.py` ignora carpetas/archivos temporales `.download`, `.crdownload`, `.part` y `.tmp` para no fallar mientras Chrome descarga videos.
- `tools/video_learning_ingest.py` tambien ignora el proyecto no relacionado `RoxyEnterprise` para que plantillas legales o documentos internos no contaminen la memoria de trading.
- Ultima revision de aprendizaje: `33` videos y `69` materiales. Temas dominantes: medias moviles, fundamentales/valoracion, opciones, canal alcista, microestructura, SMA20/SMA40, SMA200, VWAP/liquidez y macro/FED.
- Ultima tanda procesada: `8` videos de `Operativa` de mayo/junio 2026 y `26` materiales nuevos. Todo fue archivado en `/Volumes/RoxyData/RoxyVideosAnalizados`.
- La otra pestana de Codex debe leer `training_videos/ROXY_LEARNING_SYNC.md` antes de modificar reglas aprendidas.
- Estado conocido: el escaneo manual funciona y ya proceso 14+ videos de estrategia; el LaunchAgent esta instalado cada 35 minutos. Si macOS limita acceso a carpetas, la ruta mas confiable es usar el boton dentro de Roxy o ejecutar el script manualmente.
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

## Regla De Rentabilidad 1R

Roxy ahora exige que cada oportunidad operable tenga reward/risk minimo de 1.0R:

- Si el objetivo minimo es 2% pero el stop arriesga 3%, Roxy bloquea BUY/alerta porque paga solo 0.67R.
- La regla aparece como `Reward/Risk viable` en el Trade Plan y en las alertas 24h.
- Una senal puede tener setup, volumen y tendencia, pero si el plan no compensa el riesgo queda en Esperar/No operar.
- Esto protege el plan de cuenta pequena: no tomar operaciones donde una perdida borra varias ganancias.
- La alerta A+/operable debe mantener entrada, stop, target y tamano claros antes de cualquier ejecucion manual o futura integracion.

## Filtros Aprendidos De Timing Y Saltos

Roxy tambien aplica estos no negociables medibles:

- `No perseguir extension`: si el precio esta demasiado separado sobre SMA20, Roxy espera pullback antes de comprar.
- `SMA40 sostiene canal`: si una estructura alcista/pullback cierra debajo de SMA40, baja de BUY a Esperar hasta recuperar.
- `No expuesto Bollinger`: no comprar fuera de banda por persecucion de vela.
- `No vela llena`: no entrar tarde en vela demasiado extendida.
- `1m/5m solo timing`: 1m y 5m sirven para afinar entrada, no para autorizar una operacion sin 15m/1h/2h/4h.

## Filtro Macro FED

Del video `06-01-Soporte FED Parte 2 01 Junio 2026.mp4`, Roxy incorpora una regla macro conservadora:

- La FED mueve el mercado por cambios de expectativa: comunicado, decision de tasas, conferencia de Powell, minutes, dot plot y discursos pueden crear reacciones fuertes.
- CPI, PCE, NFP/jobs, inflacion, yields y Treasury se tratan como eventos macro de riesgo medio.
- En contexto FED/macro activo, Roxy baja agresividad y bloquea BUY/alerta si la oportunidad no tiene confirmacion limpia.
- Para permitir una alerta durante evento FED/macro, Roxy exige: 15m/1h confirmados, 2h/4h sin bloqueo, score >= 85, reward/risk >= 1.5R y volumen relativo >= 1.1x.
- Si no pasa, el Trade Plan muestra `Evento FED/macro` y la alerta queda en espera de post-noticia o confirmacion mas fuerte.
- Calendario local: `data/macro_events.csv`.
- Ejemplo de formato: `data/macro_events.example.csv`.
- Modulo lector: `macro_calendar.py`.
- El watcher `tools/roxy_ai_watch.py` carga el calendario local en cada corrida y lo guarda como `macro_calendar` dentro de `alerts/roxy_ai_brief.json`, `alerts/roxy_status.json` y textos.
- Si hay evento activo, `apply_global_alert_context()` agrega `macro_event=True`, `event_risk=True`, `news_event` y `macro_context` a cada oportunidad antes de recalcular `smart_alerts`.
- El gate humano es `WAIT_MACRO_CONFIRMATION` / `Esperar evento macro`.

## Opciones Profesionales

Roxy ya no trata `Mirar Call` como una recomendacion general. La accion base puede estar en BUY, pero el contrato tambien debe pasar filtros propios:

- DTE dentro del rango operativo.
- Delta en zona razonable para calls/puts.
- Spread bajo.
- Volumen y open interest suficientes.
- Break-even viable contra el objetivo esperado.
- Max loss medible y comparado contra 1R de la cuenta.
- Greeks disponibles; con Tradier u otro feed profesional se prefieren delta/gamma/theta/vega reportados.

El motor principal vive en `options_strategy.py` con `analyze_option_contract()` y `best_option_contract()`. El Trade Plan, alertas IA y la pestaña `Opciones` usan esa misma lectura para mostrar contrato, DTE, delta, spread, OI, volumen, break-even, max loss, contratos por riesgo y bloqueos.

## Capa De Enriquecimiento Aprendido

Roxy ahora tiene una capa separada en `trade_enrichment.py` para usar lo aprendido de videos/materiales sin sobrescribir la decision principal:

- La decision base sigue saliendo de `build_symbol_trade_brief()` con reglas duras: 15m/1h, 2h/4h, volumen, riesgo, target, reward/risk, no negociables, memoria y opciones.
- `build_trade_enrichment()` agrega contexto de estructura 20/40/100/200, volumen, microestructura, opciones, expectativa/memoria, psicologia, momentum/short squeeze, soportes/resistencias, fundamentales y reglas de ejecucion.
- El enriquecimiento se guarda en `brief["enrichment"]` y `brief["enrichment_checks"]`.
- No se mezcla con `condition_checks`, para que una idea nueva de estudio no convierta por accidente un `Esperar` en `Operar`.
- `direct_plan` ahora incluye `enrichment_summary` y `execution_rule` para que la pantalla pueda explicar la oportunidad con lenguaje simple.
- Esta capa debe crecer con cada tanda de material estudiado: Level2, Time&Sales, dark pools, short squeeze, risk management, psicologia, expectancy, fundamentales y nuevas clases.

## Alpaca Paper Practice Lab

Alpaca paper se usa como laboratorio de practica controlada, no como promesa de rentabilidad. Roxy puede registrar cada setup operable y medirlo contra resultados paper:

- Solo acciones/ETF en Alpaca paper; crypto y opciones quedan en analisis/preview por ahora.
- Cada candidato guarda simbolo, estrategia, entrada, stop, targets 2%, 5%, 10%, take profit, riesgo, notional y razon.
- Si la senal esta incompleta, queda como `BLOCKED` con la razon: falta BUY/ALERT, falta stop, crypto no soportado, riesgo no cabe en la cuenta, etc.
- La memoria vive en `alerts/alpaca_paper_practice.csv`.
- El modulo `alpaca_paper_practice.py` construye candidatos, deduplica el journal, lee precios paper y calcula si cada setup llego a 2%, 5%, 10% o toco stop.
- El dashboard muestra `Alpaca Paper Practice Lab` con candidatas listas, bloqueadas, medidas, hits a 2% y stops.
- Esto alimenta decisiones futuras por estrategia: Pullback, Canal alcista, Cruce de medias, Canal bajista y nuevas estrategias aprendidas.

## Confirmacion Visual TradingView

Las oportunidades del panel `Roxy Live Market` incluyen un enlace directo a TradingView para validar visualmente el setup antes de cualquier practica paper/manual:

- Acciones usan el ticker limpio directo (`AAPL`, `SPCX`, etc.).
- Cripto usa el par sin slash (`BTCUSD`, `ETHUSD`, etc.), consistente con el hub de investigacion.
- Los candidatos de IPO/ticker nuevo tambien exponen `tradingview_url` para revisar rapidamente si ya hay grafica o actividad.
- Esto no habilita ejecucion real; solo agrega una confirmacion visual externa para evitar operar senales sin revisar velas, volumen y niveles.

## Contrato De Datos Visible En Activo

La vista `Activo` muestra un contrato de datos live arriba del plan/grafica para evitar que Roxy parezca operable cuando el precio no lo permite:

- Si el precio viene de broker/exchange confirmado y esta fresco, marca `LIVE_PRICE_OK`.
- Si el precio viene de fallback publico como yfinance, marca `NO_TRADE_FROM_PUBLIC_PRICE`.
- Si el precio falla o esta viejo, marca `NO_TRADE_PRICE_FAIL` / `NO_TRADE_STALE_PRICE`.
- La grafica profesional tambien renderiza su contrato de velas antes del chart; si no hay historial suficiente, muestra `Grafica pendiente` con fuente, gate y accion.
- Esto mantiene el modo paper/analisis y no habilita ordenes reales.

## Alertas Bloqueadas Por Precio Live

El motor `smart_alerts.py` reconoce los gates de precio live ademas de los gates de grafica:

- `LIVE_PRICE_OK` permite alerta solo si los demas checks pasan.
- `NO_TRADE_FROM_PUBLIC_PRICE`, `NO_TRADE_PRICE_FAIL`, `NO_TRADE_STALE_PRICE` y `WAIT_PRICE_CONFIRMATION` bloquean `ALERT_READY` y fuerzan `BLOCKED_REALTIME_DATA`.
- `alert_quality.py` cuenta estos gates en la cobertura para diferenciar oportunidades con precio exchange/broker de oportunidades sostenidas por fallback publico.
- Esto evita que una oportunidad tecnicamente lista mande alerta si el precio actual viene de yfinance/fallback, esta viejo o fallo.

## Panel Alertas Live

La UI muestra `Alertas Live` en Dashboard y en la vista `Activo`:

- Resume alertas listas, bloqueadas por datos, solo vigilancia y no operar.
- Cada fila expone ticker, estado humano, gate de alerta, gate de datos, fuente, readiness, score, razon, siguiente accion y link a TradingView.
- Cada fila tambien expone `Decision alerta`, `Cambio decision`, `Alerta decision`, `Accion decision` y `Detalle decision`.
- Las decisiones accionables normalizadas son `Entra ahora`, `Espera pullback`, `No operar`, `Confirmar externo` y `Vigilar`.
- Roxy solo manda notificacion cuando una oportunidad conocida cambia hacia `Entra ahora`, `Espera pullback` o `No operar`; el primer snapshot no manda ruido.
- Canales externos soportados: email, Discord, Slack, webhook generico, Mac local, Pushover y Telegram.
- `WEBHOOK_URL` recibe payload estructurado con `message`, `source=roxy_trading` y `metadata` para automatizaciones de telefono.
- `BLOCKED_REALTIME_DATA` y gates como `NO_TRADE_FROM_PUBLIC_PRICE` quedan visibles para que el usuario no confunda una oportunidad con una entrada operable.
- TradingView sigue siendo confirmacion visual externa; no dispara ejecucion.

## Panel Alpaca Visible En Activo

La vista `Activo` ahora muestra `Alpaca Market Data` debajo del contrato de precio live:

- Expone estado Alpaca, feed, modo paper/live_readonly, endpoint, credenciales, permisos de senales y guardrail de ordenes.
- `AUTH_INVALID`, `NOT_CONFIGURED`, `PLACEHOLDER_KEYS`, `FEED_PERMISSION` y `ENDPOINT_MISMATCH` quedan visibles como bloqueos de senales, no como fallos silenciosos.
- El panel muestra `Ordenes reales: OFF` y `live_orders_allowed=False`; sigue siendo diagnostico read-only para analisis/paper/manual.
- Si hay probes, muestra latest_trade, latest_quote y latest_bar con fuente, timestamp, precio, error y accion siguiente.
- Cualquier cambio de credenciales debe recargar el mismo servidor `localhost:3000`; no se levanta otro puerto.

## Fuente De Datos Por Oportunidad

Cada oportunidad visible ahora carga un estado de fuente de datos derivado de su contrato de precio/grafica:

- `Broker/exchange live`: Alpaca, Binance/Coinbase/Polygon u otra fuente operable con gate `LIVE_PRICE_OK`, `LIVE_DATA_OK` o `ANALYSIS_OK`.
- `Fallback publico`: yfinance/Yahoo/public market data o gates como `NO_TRADE_FROM_PUBLIC_PRICE`, `NO_TRADE_FROM_FALLBACK` y `EXTERNAL_CONFIRM_REQUIRED`; se puede mirar, pero exige confirmacion externa.
- `Datos bloqueados`: fallos o datos stale (`NO_TRADE_PRICE_FAIL`, `NO_TRADE_STALE_PRICE`, `NO_TRADE_STALE_DATA`) bloquean entradas.
- `Sin contrato`: la oportunidad no debe alertar como operable hasta adjuntar contrato de precio/grafica.

La tabla enfocada, ranking del scanner, `Alertas Live` y el panel de oportunidad muestran estado/gate/fuente/accion de datos. Esto hace visible cuando una idea viene de fallback publico aunque el setup tecnico parezca atractivo.

Actualizacion:

- El bucket de datos ahora degrada la prioridad: `Live real` puede quedar en `Operar`; `Fallback` baja a `Vigilar / Confirmar externo`; `Bloqueadas` y `Sin contrato` bajan a `Evitar / No operar`.
- El Dashboard muestra contadores separados: `Live real`, `Fallback`, `Bloqueadas` y `Sin contrato`.
- `Alertas Live` no muestra como lista una oportunidad `ALERT_READY` si el contrato de datos no es operable.

## Paper Results Por Fuente De Datos

El `Alpaca Paper Practice Lab` ahora guarda y resume el origen de datos de cada candidato paper:

- Cada candidato registra `data_bucket`, `data_source` y `data_gate`.
- La memoria paper separa resultados por fuente: `Live real`, `Fallback`, `Bloqueadas` y `Sin contrato`.
- El panel muestra tasas a 2%, 5%, 10% y stop por estrategia y por fuente de datos.
- Esto permite detectar si una estrategia funciona solo cuando el precio viene de Alpaca/exchange, o si las ideas sostenidas por fallback publico fallan mas.
- Sigue siendo forward-test paper/read-only; no habilita ordenes reales.

## Source Memory Bias

Roxy usa la memoria paper por fuente como sesgo suave de decision:

- Con muestra baja marca `Aprendiendo`; no bloquea ni sube prioridad.
- Si una fuente tiene mas stops que hits a 2% con muestra suficiente, marca `Memoria fuente negativa` y baja prioridad.
- Si una fuente supera stops con hits a 2%, marca `Memoria fuente positiva` y sube confianza visual, sin saltarse gates de datos/riesgo.
- `focused_opportunity_table()` expone `source_memory_bias`, `source_memory_detail` y `source_memory_action`.
- `Alertas Live` muestra `Memoria fuente` y `Accion memoria`; una alerta lista con memoria fuente negativa se degrada visualmente.
- Esto sigue sin activar ordenes reales; solo ajusta ranking, explicacion y confianza.

## Strategy + Source Memory Bias

Roxy tambien aprende por combinacion `estrategia + fuente`:

- `Alpaca Paper Practice Lab` resume `strategy_family + data_bucket + data_source`.
- Cada oportunidad expone `strategy_source_memory_bias`, `strategy_source_memory_detail` y `strategy_source_memory_action`.
- `Alertas Live` muestra `Memoria setup+fuente` y `Accion setup+fuente`.
- `Alertas Live` tambien muestra entrada, zona de entrada, stop, Target 2% y `R:R 2%` para que una alerta diga donde entrar/salir antes de abrir el plan.
- Si la combinacion especifica tiene mas stops que hits a 2%, baja prioridad aunque la fuente general sea buena.
- Si la combinacion especifica tiene hits a 2% por encima de stops, sube confianza visual, pero no salta validacion de entrada, stop, target, fuente live ni riesgo.
- El objetivo es que Roxy priorice setups que han funcionado con la fuente correcta y deje de insistir en combinaciones debiles.
- Alpaca Paper Practice ahora cierra automaticamente tracks de acciones/ETF cuando un precio live de la tabla o snapshot toca 2%, 5%, 10% o stop.
- Los cierres Alpaca paper se persisten en `alerts/alpaca_paper_practice.csv` como `CLOSED_HIT_2`, `CLOSED_HIT_5`, `CLOSED_HIT_10` o `CLOSED_STOP`, con timestamp, precio y movimiento.
- La memoria fuente y setup+fuente lee esos cierres persistidos, asi no pierde el resultado si luego el precio live desaparece.

## Paper Risk Guard

Roxy ahora tiene un guard operativo paper visible en Dashboard:

- Combina `alerts/alpaca_paper_practice.csv` y `alerts/crypto_paper_practice.csv`.
- Calcula señales paper abiertas, stops paper de hoy, riesgo abierto, perdida paper realizada del dia y riesgo libre restante contra un limite 2R diario.
- Estados:
  - `Puede operar`: dentro de 1R por trade y 2R diario.
  - `Riesgo alto`: cerca del maximo de señales abiertas o del limite diario.
  - `Modo proteccion`: bloquea nuevas entradas paper si hay 2 stops hoy, 2R alcanzado o demasiadas señales abiertas.
- `Paper Execution Gate` respeta este guard: si el guard esta en proteccion, no arma nuevas entradas paper.
- Ordenes reales siguen apagadas; esto solo controla simulacion/paper/manual.

## Market Event Guard

Roxy ahora penaliza y bloquea oportunidades por eventos:

- Lee el contexto macro de `brief["macro_calendar"]`; si no viene, consulta `macro_calendar_status()` sobre `data/macro_events.csv`.
- Detecta `Evento macro activo`, `Evento macro proximo`, `Earnings cercanos`, `Earnings revisar` y `Sin evento`.
- `Evento macro activo` y `Earnings cercanos` fuerzan `No operar` en `Trade Decision Card 2.0`.
- `Evento macro proximo` y `Earnings revisar` fuerzan `Esperar` o bajan prioridad.
- `focused_opportunity_table()` expone `market_event_state`, `market_event_detail`, `market_event_action`, `market_event_tone` y `market_event_severity`.
- `Opportunity Ranking 2.0` resta prioridad a oportunidades cerca de FED/FOMC/CPI/eventos macro o earnings.
- Dashboard muestra un panel `Eventos` con evento activo, impacto y accion recomendada.
- Esto no ejecuta dinero real; solo impide que Roxy trate como entrada limpia una senal expuesta a noticias/eventos.

## Serious Backtest Performance

Roxy ahora tiene una capa de resumen serio para trades historicos de backtest:

- `trade_brief.summarize_backtest_performance()` resume cualquier CSV de trades por estrategia, timeframe, ticker o fuente.
- Calcula `trades`, `wins`, `losses`, `win_rate`, `profit_factor`, `max_drawdown`, `max_drawdown_pct`, `avg_r`, `total_r`, `avg_return_pct`, `total_pnl` y `expectancy`.
- Si el CSV trae `risk_dollars`, calcula `r_multiple`; si ya trae `r_multiple`, lo usa directo.
- La pantalla `Backtest` muestra `Backtest serio por timeframe` con mejor setup, timeframe, profit factor, R promedio, drawdown y scatter PF vs R promedio.
- Esta capa no ejecuta trades; sirve para decidir que estrategias/timeframes merecen subir o bajar peso antes de pensar en real.
- `streamlit_app.py` convierte ese resumen en `Backtest positivo`, `Backtest negativo`, `Backtest neutral` o `Backtest aprendiendo`.
- `focused_opportunity_table()` expone `backtest_memory_bias`, `backtest_memory_detail` y `backtest_memory_action`.
- `Opportunity Ranking 2.0` suma prioridad a `Backtest positivo` y resta prioridad a `Backtest negativo`.
- `Trade Decision Card 2.0` muestra `Backtest`; si la memoria historica es negativa, Roxy baja la accion a `Esperar`.

## Trade Decision Card 2.0

Roxy muestra una decision operativa arriba de Dashboard y en `Activo`:

- Accion ahora: `Entrar paper/manual`, `Confirmar externo`, `Esperar confirmacion` o `No operar`.
- Entrada sugerida, stop, salidas parciales 2%/5%/10%, invalidacion y siguiente paso.
- Muestra `R:R 2%`; si el objetivo 2% paga menos de 1R, la entrada queda bloqueada.
- La decision combina senal tecnica, gate de datos, memoria de fuente, memoria setup+fuente, riesgo y niveles.
- `Memoria fuente` y `Memoria setup+fuente` se muestran dentro de la tarjeta principal para explicar por que Roxy favorece, espera o bloquea una entrada.
- Fallback publico fuerza `Confirmar externo`.
- Datos bloqueados/sin contrato o memoria setup+fuente negativa fuerzan `No operar`.
- Es decision para paper/manual; no ejecuta dinero real.

## Opportunity Ranking 2.0

Dashboard muestra `Mejores oportunidades ahora`:

- Ranking basado en accion de `Trade Decision Card 2.0`, fuente live, memoria fuente, memoria setup+fuente, riesgo, readiness, entrada, stop y targets.
- `Opportunity Ranking 2.1` ajusta la prioridad al `Capital disponible` y `Riesgo %` del Trade Desk. Con $100 y 1% de riesgo, Roxy calcula 1R=$1, tamano, capital usado, riesgo en dolares, recompensa esperada a 2% y si el setup cabe como accion completa, fraccionada, crypto pequeno, opcion o solo vigilancia.
- Modo `Tengo $X hoy`: el Trade Desk permite definir capital disponible, riesgo maximo por trade, mercado (`Todos`, `Acciones`, `Crypto`, `Opciones`) y maximo de trades/dia. Roxy filtra/demueve oportunidades por presupuesto antes de mostrarlas como candidatas principales.
- El Dashboard muestra `Con $100, usar primero` debajo de `Operar ahora / vigilar`: separa `Operable`, `Presupuesto pequeno` y `Solo vigilar`, para que el usuario vea primero que oportunidades tienen sentido con su presupuesto real.
- El Dashboard tambien muestra `Mejor uso del presupuesto`: calcula una expectativa simple ajustada a capital con probabilidad derivada de readiness, accion, fuente live, memoria setup+fuente, backtest y TradingView. Muestra EV aproximado, R esperado, probabilidad, capital usado, riesgo y score de presupuesto. Es una ayuda de priorizacion paper/manual, no promesa de rentabilidad.
- El Dashboard muestra `Plan de trade por presupuesto` para las 3-5 mejores oportunidades filtradas: cuanto comprar, entrada, stop, target 1/2, perdida maxima, ganancia posible, EV aproximado, veredicto y siguiente paso. Sigue siendo paper/manual y no coloca ordenes reales.
- `Aprendizaje por resultado` compara diarios paper stock/crypto: si llego al 2%, si toco stop, que estrategia funciono mejor para cuenta pequena y que setup debe priorizar o bajar manana.
- La pantalla principal queda mas limpia: graficas, mejor oportunidad, recomendacion de presupuesto, decision entrar/esperar/no operar y noticias importantes. Diagnosticos, laboratorios, ranking completo y tablas largas quedan en expanders o pestanas secundarias.
- Dashboard tambien muestra `Operar ahora / vigilar` justo despues de la grafica operativa: separa oportunidades con accion inmediata de setups que solo deben monitorearse, con entrada, stop, salida, readiness y link a la grafica del activo.
- La vista principal debe abrir primero en `Roxy Trade Desk`; la navegacion de paginas vive en el sidebar para que la mesa de operacion sea el primer bloque visible.
- La grafica operativa principal ya no se recrea dentro del fragment live del Dashboard. El fragment refresh actualiza listas/pulso, mientras el chart queda estable para evitar pantalla negra, blink o perdida de zoom.
- La grafica principal usa un componente browser-side con Lightweight Charts: carga hasta 1000 velas crypto desde BinanceUS, muestra rangos 1D/1W/1M/3M/1Y/ALL y actualiza la vela actual por WebSocket `wss://stream.binance.us:9443/ws/<symbol>@kline_<interval>` dentro del navegador, con REST ticker/klines como fallback y sin rerun de Streamlit.
- El Trade Desk ahora abre como workstation de dos graficas lado a lado, inspirado en TC2000: izquierda `Tendencia` y derecha `Entrada`. Por defecto `1h + 15m`; si el usuario trabaja 4h/1d, la segunda grafica baja a 1h para gatillo.
- Cada grafica tiene toolbar propia con cursor, linea de tendencia, rayo, horizontal, vertical, rectangulo/zona, medida, texto, borrar ultimo, `Snap` y `Show`. Los dibujos se guardan en `localStorage` por simbolo/timeframe para que el trader pueda marcar entrada, salida y stop.
- La grafica muestra `TICK LIVE` arriba y un contrato visible `2 GRAFICAS LIVE · STREAM ON · velas live · Tick live`. Crypto usa `BinanceUS ticker`/browser stream 24h; acciones fuera de horario extendido muestran `mercado cerrado`/`FAIL` en vez de fingir movimiento. Streaming real de acciones requiere WebSocket broker/premium durante mercado abierto.
- Para acciones, Roxy ya no usa la ultima vela extendida de yfinance como precio principal si existe `currentPrice`/`regularMarketPrice`. Caso validado: `COIN` mostraba vela post-market `169.45` mientras TradingView/Robinhood mostraban `169.62`; ahora el `TICK LIVE` toma `yfinance currentPrice` y enseña comparacion `reg 169.62 / post 169.45` para que el trader vea por que difieren las plataformas.
- `Live real` y memoria positiva suben prioridad.
- `Fallback`, datos bloqueados, sin contrato, riesgo alto o memoria setup+fuente negativa bajan prioridad.
- Cada fila muestra accion, ticker, estrategia, entrada, stop, targets 2/5/10, `R:R 2%`, riesgo, readiness, fuente, memoria setup+fuente, razon, siguiente paso, link a `Activo` y TradingView.
- Sigue siendo paper/manual/read-only.

## Entry/Exit Plan Engine

Roxy genera un plan de entrada/salida por oportunidad:

- Zona de entrada (`entry_zone_low` / `entry_zone_high`) alrededor de la entrada sugerida.
- Stop, targets 2%/5%/10%, reward/risk a 2%, regla de invalidacion y regla de confirmacion.
- Bloquea si falta entrada/stop, si la fuente no es operable, si el riesgo supera 3.5%, si el precio ya se alejo de la zona o si target 2% paga menos de 1R.
- `Trade Decision Card 2.0` muestra `Zona entrada`, `Confirmacion` y `No perseguir`.
- `Mejores oportunidades ahora` incluye zona de entrada y confirmacion para que cada fila diga donde entrar/salir y que debe pasar antes de actuar.

## Entry Proximity Alert

Roxy mide el precio actual contra la zona de entrada:

- `Entrada en zona`: el precio esta dentro de la zona operable y puede subir prioridad si los demas gates estan OK.
- `Cerca de entrada`: el precio esta cerca, pero aun requiere confirmacion 15m o pullback corto.
- `No perseguir`: el precio se extendio demasiado sobre la entrada y la tarjeta cambia a esperar pullback.
- `Invalida`: el precio perdio el stop y la oportunidad queda bloqueada.
- `Sin precio`: no hay precio actual explicito; Roxy no asume que `entry` es el precio live.
- El estado aparece en `Trade Decision Card 2.0` y en `Mejores oportunidades ahora`, y afecta el ranking sin habilitar ordenes reales.
- `Alertas Live` ahora eleva `Entrada en zona` arriba de la tabla, muestra `Estado entrada`, `Accion entrada` y `Detalle entrada`, y baja a `Esperar precio live` cuando falta precio actual.
- Roxy guarda `alerts/entry_proximity_state.json` con el ultimo estado por mercado/ticker, incluyendo `state`, `dashboard_state`, `actionable_state` y `actionable_transition`.
- Detecta transiciones de precio como `Cerca de entrada -> Entrada en zona` y transiciones accionables como `Vigilar -> Entra ahora`, `Entra ahora -> Espera pullback` o `Entra ahora -> No operar`.
- Solo registra notificacion accionable cuando una oportunidad conocida cambia hacia `Entra ahora`, `Espera pullback` o `No operar`; el primer snapshot no dispara alerta para evitar ruido.
- Cuando una transicion valida de accion/ETF entra en zona, Roxy crea automaticamente un candidato en `alerts/alpaca_paper_practice.csv` con entrada, stop y targets 2%/5%/10%.
- Si Roxy abre/refresca y el primer snapshot ya esta en `Entrada en zona`, tambien crea candidato paper valido, pero no manda notificacion de transicion.
- `Alpaca Paper Practice Lab` solo persiste candidatos `READY_FOR_PAPER`; los bloqueados siguen visibles para diagnostico, pero no inflan el journal ni la precision.
- Dashboard muestra `Por que no esta lista para paper`, con bloqueos por fuente, TradingView, gatillo, plan, zona de entrada, entry/stop/target/R:R/riesgo, memoria, backtest y eventos.
- Un `TradingView confirma` fresco puede convertir un setup WATCH en gatillo paper/manual solo si readiness >= 70 y el resto de gates ya esta alineado: fuente live, plan READY, precio en zona, stop/target/R:R validos.
- Crypto usa journal separado: `crypto_paper_practice.py` y `alerts/crypto_paper_practice.csv`.
- Cuando BTC/ETH/SOL u otro par crypto entra en zona, Roxy crea automaticamente un candidato crypto paper con cantidad fraccionaria, entrada, stop y targets 2%/5%/10%.
- Dashboard muestra `Crypto Paper Practice Lab` separado de Alpaca para no mezclar acciones/ETF con crypto.
- `Crypto Paper Practice Lab` toma precios live desde las oportunidades actuales del Dashboard para marcar cada track como `OPEN`, `HIT_2`, `HIT_5`, `HIT_10` o `STOP`.
- Si un track crypto toca 2%, 5%, 10% o stop, Roxy persiste el cierre en `alerts/crypto_paper_practice.csv` como `CLOSED_HIT_2`, `CLOSED_HIT_5`, `CLOSED_HIT_10` o `CLOSED_STOP`, con precio, timestamp y movimiento.
- La memoria crypto se resume por estrategia y por contexto (`symbol`, `timeframe`, `strategy_family`, `data_source`) para aprender que setups funcionan por ticker/fuente/marco.
- `focused_opportunity_table()` ahora expone `crypto_context_memory_bias`, `crypto_context_memory_detail` y `crypto_context_memory_action`.
- `Trade Decision Card 2.0` muestra `Memoria crypto`; si el contexto crypto tiene mas stops que hits a 2%, la accion baja a `Esperar`.
- `Opportunity Ranking 2.0` incluye `Memoria crypto`: una memoria positiva suma ranking y una memoria negativa penaliza el setup aunque la senal tecnica sea BUY.

## TradingView Webhook Confirmation

Roxy ahora tiene una primera capa de confirmacion entrante desde TradingView, sin abrir otra URL ni habilitar ordenes reales:

- Nuevo modulo `tradingview_webhooks.py`.
- Journal local `alerts/tradingview_webhooks.jsonl`.
- CLI de prueba: `tools/tradingview_webhook_ingest.py`.
- Endpoint autenticado en `tools/admin_api.py`: `POST /tradingview/webhook`.
- Endpoint autenticado en `tools/voice_service.py`: `POST /v1/webhooks/tradingview` y `GET /v1/webhooks/tradingview/status`.
- Runner fijo: `make tradingview-bridge`, usa `tools/tradingview_bridge.py` y puerto local `8001`; si ya esta sano, lo reutiliza.
- Los endpoints HTTP requieren `TRADINGVIEW_WEBHOOK_SECRET`; si falta, rechazan POSTs en vez de quedar abiertos.
- El secreto puede llegar por header `X-TradingView-Secret`, `X-Roxy-TradingView-Secret`, `X-Roxy-Webhook-Secret`, `X-Webhook-Secret` o campo payload `passphrase`/`secret`/`webhook_secret`/`roxy_secret`.
- TradingView necesita URL publica HTTPS; Roxy mantiene dashboard fijo en `http://localhost:3000` y bridge local en `http://127.0.0.1:8001`.
- Nuevo diagnostico `tools/tradingview_tunnel.py` y `make tradingview-tunnel-check`: valida `TRADINGVIEW_PUBLIC_WEBHOOK_URL`, normaliza `/tradingview/webhook`, recomienda `cloudflared`/`ngrok` y no inicia servidores nuevos.
- Dashboard muestra `Tunnel publico`, `URL TradingView`, `Tool tunnel` y `Comando tunnel` sin exponer secretos.
- Secretos se redaccionan antes de guardar el payload normalizado.
- Normaliza payloads comunes de TradingView: `symbol`/`ticker`, `timeframe`/`interval`, `signal`/`action`, `price`/`close`, `strategy`, `message` y timestamps.
- Sanitiza secretos en payloads (`secret`, `token`, `passphrase`, `password`, `api_key`, etc.) antes de guardar.
- Deduplica alertas por ticker, timeframe, senal, evento, precio, estrategia y mensaje.
- Normaliza `NASDAQ:AAPL` a `AAPL` y crypto tipo `BINANCE:BTCUSDT` para que pueda confirmar oportunidades `BTC/USD`.
- `focused_opportunity_table()` expone `tradingview_confirmation`, `tradingview_confirmation_detail` y `tradingview_confirmation_action`.
- `TradingView confirma` sube prioridad; `TradingView contradice` baja ranking y fuerza la tarjeta a `Esperar`.
- `Opportunity Ranking 2.0` muestra columna `TV Webhook`.
- `Trade Decision Card 2.0` muestra KPI `TV Webhook`.
- Dashboard muestra panel `TradingView Webhooks` con ultimo webhook, conteo fresco 90m y ultimas senales recibidas.
- Esto es solo confirmacion 15m/1h para paper/manual; no ejecuta dinero real.
- La web estable sigue siendo `http://localhost:3000`; el endpoint es una capacidad de bridge/API y no se arranca automaticamente con `make dev-web`.

## Monetization Readiness

La meta comercial de Roxy es monetizarla sin vender promesas que no estan probadas:

- Nuevo modulo `monetization_readiness.py`.
- La pagina `Precision` muestra `Preparacion comercial / monetizacion`.
- El panel separa `Beta Scanner`, `Pro Trader` y `Desk` como escenarios de suscripcion, con neto mensual estimado despues de comision de tienda.
- Roxy puede posicionarse como scanner educativo live + paper trading cuando los datos estan frescos, las ordenes reales siguen OFF y hay suficientes setups trackeados.
- Roxy no debe posicionarse como asesor financiero, garantia de ganancias, advice personalizado ni ejecucion automatica con dinero real.
- Antes de publicar precision o subir el claim comercial de senales, Roxy exige muestra cerrada suficiente en paper/mediciones: entrada, stop, targets, cierre, hit rate y stop rate.
- El panel usa los journals existentes `alerts/alpaca_paper_practice.csv` y `alerts/crypto_paper_practice.csv`; no habilita ordenes reales.

## Paper Result Closer

Roxy ahora tiene cierre automatico paper para construir precision real defendible:

- Nuevo modulo `paper_result_closer.py`.
- Lee `alerts/alpaca_paper_practice.csv` y `alerts/crypto_paper_practice.csv`.
- Solo considera tracks elegibles abiertos: `READY_FOR_PAPER`, `OPEN`, `OBSERVING` o status vacio, con entrada y stop validos.
- Filas `BLOCKED` no se cierran aunque el precio haya tocado target/stop; no fueron entradas paper validas y contaminarian la precision.
- Los candidatos `BLOCKED` nuevos ya no se persisten desde el lab principal; solo se guardan entradas paper realmente listas.
- Consulta precios live con la ruta existente `build_live_price_snapshot()`.
- Cierra como `CLOSED_HIT_2`, `CLOSED_HIT_5`, `CLOSED_HIT_10` o `CLOSED_STOP`.
- Guarda auditoria en `alerts/paper_result_closer.json`.
- La pagina `Precision` ejecuta el cierre en cache de 60 segundos y muestra `Cierre auto paper`, `Stocks revisados` y `Crypto revisados`.
- Ordenes reales siguen OFF; esto solo actualiza journals paper y metricas de precision.

## Price Session Guardrail

Caso COIN validado el 2026-06-16: TradingView/Robinhood mostraban `169.62`, mientras una vela extendida publica podia cerrar en `169.45`.

- Para acciones, `living_market.py` prioriza `currentPrice`/`regularMarketPrice` antes de usar la ultima vela extendida de yfinance.
- `build_live_price_snapshot()` conserva `regular_market_price`, `post_market_price` y `pre_market_price` para comparar sesiones.
- El Trade Desk muestra `Chequeo de precio` con `Precio principal`, `Regular/current`, `Post-market` y diferencia porcentual.
- El panel `Entrada exacta` muestra precio actual, zona de entrada, stop, target 2/5/10, distancia y R:R antes de mirar las dos graficas.
- Si la fuente es `PUBLIC_MARKET_DATA`, Roxy puede analizar, pero sigue bloqueando entrada automatica y exige confirmacion externa/broker.

## TC2000-Style Chart Workstation

Actualizacion 2026-06-16:

- Las dos graficas del Trade Desk usan una presentacion mas cercana a TC2000: fondo negro, grid sobrio, simbolo amarillo, botones de timeframe y barra de indicadores compacta.
- Las etiquetas de EMA/SMA en el eje derecho quedan apagadas por defecto (`Labels` OFF) para que no tapen las velas. El usuario puede prenderlas cuando quiera.
- Medias disponibles: EMA9, SMA20, SMA40, SMA100, SMA200. Bollinger queda disponible como `BBand 20 2` con upper/lower y mid opcional.
- La toolbar vertical usa iconos y agrega cursor, crosshair, linea, rayo, horizontal, vertical, rectangulo, canal, Fibonacci, flecha, medicion, texto, undo/eraser, borrar todo, Snap y Show.
- Las preferencias de indicadores se guardan por simbolo/timeframe en `localStorage`, sin cambiar la URL ni recargar la pantalla.
- Regla visual: primero legibilidad de velas; las senalizaciones y etiquetas nunca deben dominar la grafica.

Actualizacion 2026-06-16, segunda pasada:

- Bollinger ahora tambien se dibuja como nube/campo blanco-gris entre banda superior e inferior, no solo como lineas, para parecerse mas al campo visual de TC2000.
- La toolbar se saco del area de precio y vive en un riel lateral propio; las herramientas siguen siendo seleccionables y no cubren las velas.
- La marca visible dentro de la grafica es `Roxy AI Trading`; no se agrega logo de TradingView en el chart propio.
- Las graficas del Trade Desk ganan altura por defecto para aprovechar mejor la pantalla fija `http://localhost:3000`.
- En modo Dashboard limpio, broker/riesgo/guardrails paper se movieron a un expander cerrado para que lo primero visible sea operar, descubrir oportunidades y leer el mercado.
- Ranking secundario, fuentes, webhooks, alertas y voz quedaron dentro de un expander secundario; la decision y cola de accion siguen visibles.
- Noticias, IPOs y tickers nuevos se muestran como tarjetas con `Abrir noticia`, para poder revisar la fuente completa sin quedarse con un titular corto.

Actualizacion 2026-06-17:

- `BBand` queda encendido por defecto en el payload de la grafica; antes existian `BB Upper/Lower`, pero el toggle agrupador podia quedar apagado y esconder la nube visual.
- Las tarjetas de noticias se renderizan con HTML plano sin indentacion Markdown para evitar que Streamlit muestre `<article ...>` como codigo crudo.
- En Dashboard, el panel `Roxy Live Market` compacto ya no muestra siete tarjetas grandes; queda como tira de estado y mueve noticias/diagnostico a un expander.
- El expander `Cambiar activo, mercado, timeframe y riesgo` inicia cerrado para que las velas suban en pantalla.
- En la grafica operativa interactiva, las dos graficas live aparecen antes del snapshot de entrada/stop; el snapshot queda debajo como contexto operativo.
- La toolbar de herramientas del chart queda abajo, fuera del area de precio, para no tapar velas ni eje; no debe volver al lateral dentro de la grafica.
- Las herramientas de dibujo muestran previsualizacion al arrastrar y quedan sobre la capa de velas solo cuando una herramienta esta activa, con `Snap`/`Show` operativos por grafica.
- La nube Bollinger se mantiene como campo blanco/gris tenue; no debe ocultar velas ni medias moviles.
- La configuracion de Lightweight Charts desactiva `attributionLogo` y se mantiene la marca propia `Roxy AI Trading`.
- `Trade Decision Card 2.0`, confirmaciones extendidas, Paper Labs, broker/riesgo y guardrails quedan en expanders cerrados por defecto; la vista principal prioriza grafica, oportunidades y accion inmediata.
- El panel operativo debajo del contexto ya no muestra tarjetas grandes para `Entrada/Stop/Targets/Esperamos/Plataforma/Grafica actual`; queda como tira compacta y el checklist se abre solo desde `Detalles operativos`.

## Market Discovery Dashboard

Actualizacion 2026-06-16:

- El Dashboard incorpora `Market Discovery`, inspirado en las capturas de Webull/Robinhood que mostro el usuario.
- La seccion vive dentro de `Roxy Trade Desk` para que aparezca en la misma web fija `http://localhost:3000`, sin abrir otra app ni otro puerto.
- Patrones adoptados:
  - `Market Movers`: pestanas/logica Most Active, Top Gainers, Top Losers y 52 Week / Breakout.
  - `Stock Monitor`: feed compacto de actividad inusual por ticker, hora, volumen relativo, riesgo y setup.
  - `Sector / Setup Map`: heatmap de sectores/setups usando el scanner interno cuando no hay mapa sectorial proveedor.
  - `Discover Crypto 24/7`: lista de crypto con actividad relativa y score para mercados que no cierran.
  - `Asset Detail`: ficha tipo Robinhood con precio, riesgo, target, RVol, 52W, P/E y contexto del activo.
- `dashboard_reference_patterns()` conserva los aprendizajes de las fotos para pruebas y futuras iteraciones.
- `market_discovery_mood()` calcula un marcador `Fear / Neutral / Greed` desde oportunidades, readiness, BUY ratio, datos live y bloqueos.
- `market_discovery_mover_sections()`, `stock_monitor_rows()`, `crypto_discovery_rows()` y `market_discovery_sector_tiles()` transforman datos reales del scanner en bloques visuales; no usan texto demo.
- El panel sigue siendo analisis/paper/manual. No habilita compras reales ni cambia las safety gates existentes.

## Budget-Aware Opportunity Engine

Actualizacion 2026-06-18:

- El scanner ahora aplica el modo `Tengo $X hoy` antes de decidir que oportunidades mostrar.
- El ranking presupuestado penaliza oportunidades que no caben con el capital disponible o que tienen stop ancho, spread alto, volumen relativo bajo, precio stale/fallback o memoria paper negativa.
- Cada oportunidad calcula probabilidad estimada de llegar al 2%, expectativa en R, valor esperado, eficiencia de capital y calidad (`Alta`, `Media`, `Baja`).
- La vista principal muestra `Top 3 para tu presupuesto` con estado operativo, entrada, stop, target 1, cantidad teorica, riesgo maximo, ganancia esperada y razon de calidad.
- `Plan de trade por presupuesto` conserva la explicacion operativa por oportunidad: cuanto comprar, donde entrar, donde salir, cuanto se puede perder y si vale la pena con ese capital.
- Las oportunidades filtradas por presupuesto se registran en los journals paper cuando estan listas para medir resultado; Roxy sigue comparando si llegaron al 2%, tocaron stop y que setups deben priorizarse manana.
- Ranking detallado, memoria de estrategias y paneles de laboratorio quedan dentro de expanders cerrados para que la pantalla principal se concentre en graficas, mejor oportunidad, presupuesto, decision y noticias importantes.
- El ranking presupuestado ahora separa cada oportunidad en `OPERAR_AHORA`, `ESPERAR_CONFIRMACION`, `SOLO_VIGILAR` o `NO_OPERAR`. La pantalla principal muestra `Top 3 para tu presupuesto` y oculta `NO_OPERAR` cuando existen candidatos mas limpios.
- La UI solo usa lenguaje de compra cuando el estado es `Operar ahora`; las senales que aun esperan confirmacion se muestran como plan/tamano teorico paper/manual, sin sugerir ejecucion inmediata.
- Guardrail intacto: esto no coloca ordenes reales. Sigue siendo analisis paper/manual.

## Strategy Scanner Contract

Actualizacion 2026-06-18:

- `roxy_ai.py` acepta `score` como respaldo de `confluence_score` y `relative_volume` como respaldo de `relative_volume_15m`, para que el scanner live y el motor de oportunidades hablen el mismo contrato.
- Si una fila trae `entry` y `stop` pero no trae `risk_pct`, Roxy calcula el riesgo desde entrada/stop antes de evaluar la estrategia.
- Si una fila vigilable no trae target, Roxy agrega target minimo 2% solo como objetivo de evaluacion; no convierte eso en entrada real.
- El ranking penaliza senales `WATCH`, decisiones que no son `TRADE_FOR_*`, stops anchos, riesgo/target faltante y estructuras `AVOID`.
- `extract_opportunities()` deduplica por `market + symbol` para no llenar el brief con el mismo ticker repetido en varios timeframes.
- Los overrides de estrategia quedan aislados en pruebas unitarias de `roxy_ai` para que el aprendizaje local/autopilot no rompa la validacion base.
- Lectura operativa: una oportunidad puede estar en vigilancia con score alto, pero solo pasa a operar si `smart_alerts.py` confirma 15m/1h/2h-4h, volumen, riesgo, reward/risk, no negociables, datos realtime y memoria.

## Proximo Paso Recomendado

El siguiente bloque de trabajo debe ser:

1. Elevar mejores oportunidades a `Entrada en zona` solo cuando TradingView/fuente live/MTF confirmen, para alimentar mas tracks paper limpios.
2. Conectar canales de telefono reales (email push/Discord/Slack/Mac) a las transiciones accionables ya filtradas.
3. Anadir backtest por las estrategias aprendidas de videos, incluyendo saltos por EMA, distancia entre medias, ruptura y cambio de canal.
4. Conectar una fuente profesional de Greeks en vivo para alimentar la evaluacion de opciones ya implementada.
5. Mantener ejecucion real bloqueada; usar paper hasta tener muestra suficiente y metricas estables.

Este archivo queda como contexto maestro para que Roxy Trading continue sin perder direccion.
