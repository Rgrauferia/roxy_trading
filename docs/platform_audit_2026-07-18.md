# Auditoría técnica de Roxy

Fecha: 2026-07-18
Alcance: repositorio local, aplicación Streamlit, servicios, datos, pruebas, rutas y estado operativo.

## 1. Resumen ejecutivo

Roxy contiene una base cuantitativa y operativa considerable: 347 módulos Python de aplicación, 167 archivos de prueba, 2.616 pruebas y 29 tablas SQLite, además de flujos de acciones/cripto, gráficas interactivas, estrategias, paper trading, alertas, voz, tareas personales, compras, hogar, documentos, correo y diagnósticos. No es una maqueta vacía. El conteo excluye `.venv`, Git, dependencias JavaScript y los proyectos auxiliares `roxy-self-improvement`/`roxy-terminal-agent`.

La deuda estructural principal sigue siendo la concentración del frontend, aunque `streamlit_app.py` bajó de 54.750 a 46.424 líneas al extraer CSS, voz, gráficas, stock live y Academy WebGL y luego incorporar las vistas operativas personales. La navegación canónica, el estado por usuario, indicadores, datos, gráficas y diagnóstico ya fueron centralizados en contratos probados, pero todavía conviven render y lógica de aplicación en un módulo demasiado grande.

Estado comprobado en esta auditoría:

| Área | Estado | Evidencia |
|---|---|---|
| Frontend | Operativo | HTTP 200 en `127.0.0.1:3000` |
| Backend de voz | Operativo | HTTP 200 en `127.0.0.1:8010/health` |
| Base de datos | Operativa | `quick_check=ok`, 29 tablas totales, 213,2 MB |
| Runtime frontend | Operativo | Python 3.12, Streamlit 1.59.2, NumPy 2.4.6; `pip check` limpio |
| Gráficas | Operativas con alcance parcial | Workspace 15m/1h, cursor, dibujos, indicadores y persistencia probados; cripto operable, acciones premium bloqueadas |
| Cripto | Operativa | BinanceUS/ccxt y WebSocket; velas recientes y volumen válido |
| Acciones/opciones premium | Bloqueadas | Alpaca está configurado pero responde `AUTH_INVALID`; Polygon no está configurado |
| Finviz | No configurado | No hay URL/token de exportación efectivos |
| ElevenLabs | Configurado pero no autenticado | La solicitud real responde HTTP 401; circuito persistente evita reintentos repetidos y la voz local/fallback permanece disponible |
| TradingView webhook | No configurado | Falta secreto; los enlaces/widgets no equivalen a confirmación autenticada |
| Ejecución real | Bloqueada correctamente | `ROXY_ENABLE_LIVE_BROKER_EXECUTION=0`, Alpaca paper activo |
| Suite | Operativa | 2.616/2.616 pruebas; cero advertencias y código de salida 0 en 149,38 s |
| Auditoría visual | Operativa | Matriz 42/42 aprobada en escritorio, iPad y teléfono; probes principal/búsqueda `OK` |
| SLO operativo | Núcleo recuperado / externo bloqueado | 11 ciclos core `OK`, recuperación sostenida; acciones/opciones bloqueadas por Alpaca |
| Mantenimiento | Interno protegido / externo degradado | Logs operativos limpios; snapshots RoxyData expiran a 5 s y permanecen `WARN` explícito |

### Fotografía de aceptación actual

Fecha de verificación: 2026-07-20 01:08 UTC. Esta matriz no sustituye los criterios de la sección 10; los cruza con evidencia viva y evita considerar el proyecto terminado por el solo hecho de que la suite pase.

| Fase | Estado actual | Evidencia que sí existe | Condición pendiente |
|---|---|---|---|
| 1. Auditoría y estabilización | `PARTIAL_EXTERNAL` | Core recuperado, frontend/voz/DB vivos, rutas y controles auditados, suite limpia, Diagnóstico operativo | Rotar Alpaca o configurar una ruta premium equivalente; recuperar acceso a snapshots externos si se desean |
| 2. Sistema visual y navegación | `ACCEPTED_LOCAL` | Registro canónico, estados uniformes, logos con cache/provenance, matriz responsive 42/42 | Validación física remota depende del despliegue seguro de sincronización |
| 3. Infraestructura de datos | `PARTIAL_MARKET` | Gateway, cache, provenance, reconexión/backfill y cripto realtime verificados | Acciones/opciones no pueden probarse end-to-end hasta autenticar proveedor premium; Finviz no configurado |
| 4. Gráficas profesionales | `ACCEPTED_CRYPTO_PARTIAL_STOCK` | 15m/1h, 10 temporalidades, indicadores centrales, sesiones, contador, crosshair, dibujos y estado durable | Repetir aceptación con streaming bursátil autenticado; falta evidencia física remota del layout sincronizado |
| 5. Estrategias y oportunidades | `ACCEPTED_CRYPTO_PARTIAL_STOCK` | 20 familias, geometría, niveles explícitos, estados, alertas, watchlist, archivo e idempotencia | Cobertura de oportunidades bursátiles permanece bloqueada por datos premium; candidatas sin target siguen WATCH explícito |
| 6. Cerebro y voz | `PARTIAL_EXTERNAL` | Contexto único, comandos UI, watchlist/alertas y backend local 8010 probados | ElevenLabs rechaza la credencial; acceso remoto exige Bearer, bind explícito y HTTPS |
| 7. Ecosistema | `IN_PROGRESS` | Calendario, actividad, memoria, notificaciones, protocolos de dispositivo, tareas, compras, documentos, Gmail read-only y adaptador Home Assistant fail-closed existen | OAuth Gmail real, Outlook, sincronización remota, cliente móvil, cifrado documental y credenciales reales de Home Assistant siguen fuera del cierre operativo actual |

Conclusión de aceptación: Roxy es utilizable diariamente para cripto, análisis local, paper trading, alertas, backtesting y voz local. No es correcto declarar 100% de la visión original mientras las fases 1, 3, 4, 5, 6 y 7 conserven las condiciones anteriores.

## 2. Mapa de arquitectura actual

```text
Usuario / navegador
  |
  v
streamlit_app.py
  |-- autenticación local/OAuth/passkeys
  |-- estado Streamlit + query params + dashboard_ui_state.json
  |-- módulos de mercado, gráficas, oportunidades, voz y academia
  |-- fragments de refresco y componentes HTML/JS embebidos
  |
  +--> symbol_detail.py ----------> Alpaca / Polygon / yfinance / ccxt
  +--> living_market.py ----------> RSS / Nasdaq / BinanceUS / yfinance
  +--> roxy_ai.py ----------------> brief, gates, memoria y estado operativo
  +--> moving_average_strategy.py -> SMA/ATR/volumen relativo
  +--> salto_strategies.py -------> detección de familias de estrategia
  +--> smart_alerts.py -----------> gates y transición de alertas
  +--> storage.py ----------------> SQLite (db/roxy.db)
  +--> tools/elevenlabs_roxy.py --> ElevenLabs
  +--> tools/voice_service.py ----> FastAPI :8010, sesiones/contexto/feedback
  +--> tools/roxy_stock_stream_bridge.py -> Alpaca WebSocket opcional
  |
  v
Archivos de runtime
  |-- alerts/*.json, *.jsonl, *.csv
  |-- output/*.csv, backtests, reportes
  |-- data/ y cache local
  |-- LaunchAgents: Streamlit, health, live scan, voz, mantenimiento
```

Problema de límites: la UI, el enrutamiento, CSS, componentes JS, lógica de datos, estrategias y render de gráficas conviven en el mismo módulo. Esto impide aislar errores, aumenta el tiempo de importación y hace muy costosa la prueba de una sola pantalla.

## 3. Páginas y funciones existentes

### Superficies activas

| Superficie | Función actual | Estado |
|---|---|---|
| Autenticación | Login, registro, OAuth Google/Apple, passkeys, restauración, cambio y recuperación local | Implementada y probada end-to-end; recuperación por correo explícitamente no configurada |
| Dashboard | Centro de mando, oportunidades, ranking, gates, estado live | Implementada; demasiados paneles y dependencias |
| Activo | Plan, gráfica, indicadores, diagnóstico, decisión | Implementada con datos reales/fallback visible |
| Capital | Plan de capital y riesgo | Implementada; orientada a simulación/paper |
| Plataformas | Estado y routing preview-only | Implementada; no ejecuta órdenes reales |
| Opciones | Candidatos, contratos, calidad y preview | Implementada; bloqueada si acciones premium no autentica |
| Backtest | Resultados y evaluación | Implementada |
| Precisión | Memoria de resultados y seguimiento | Implementada; muestra limitaciones de muestra |
| Estudios | Manual, ejemplos y laboratorio | Implementada; contiene conocimiento fallback |
| Roxy IA | Estado, aprendizaje y asistente | Implementada con varias capas de contexto |
| Diagnóstico | Frontend, voz, DB, proveedores, cache, autenticación y modo de ejecución | Añadida y validada en navegador real |

### Módulos especiales por query string

| Módulo | Estado |
|---|---|
| `acciones-operar` | Activo y renderizado directamente |
| `crypto-20m` | Implementado |
| `crypto-2h` | Implementado |
| `crypto-daily` | Implementado |
| `classroom` | Implementado |
| `watchlist` | Normalizado a la pestaña canónica de watchlists |
| `scanner` | Normalizado al screener/oportunidades canónico |
| `historial` | Normalizado a actividad/operaciones según contexto |
| `alertas` | Normalizado a `view=Alertas`, con almacén durable y transiciones live |
| `progreso` | Normalizado a Rendimiento/Precisión |
| `portafolio` | Normalizado a Capital/Operaciones paper; no finge broker conectado |
| `opciones` | Normalizado a `view=Opciones`; bloqueado cuando el proveedor premium no autentica |

Las rutas heredadas se normalizan hacia páginas y pestañas canónicas. Watchlists, alertas, gráficas y estado visible son durables y aislados por usuario local; la sincronización remota entre dispositivos sigue requiriendo un backend de identidad/estado desplegado.

## 4. Reporte de problemas priorizado

### P0 — bloquean operación o confianza

1. Alpaca responde `AUTH_INVALID`. Acciones y opciones premium deben permanecer bloqueadas hasta rotar/corregir credenciales. Polygon no existe como ruta premium alterna.
2. El watchdog vigilaba el puerto 8501 mientras Streamlit usa 3000. Esto generaba falsos fallos de frontend y reinicios. Se corrigió el LaunchAgent a `127.0.0.1:3000`.
3. El health global bloquea señales por fallos auxiliares: volumen `/Volumes/RoxyData` no escribible, backup obsoleto y probe visual sin navegador. Se añadió separación para permitir únicamente los mercados que el contrato `market_realtime` declara operables; un fallo real de velas/indicadores continúa bloqueando todo.
4. Las rutas heredadas ya fueron normalizadas. Watchlists, alertas y estado UI tienen revisiones por usuario y un backend de sincronización con control de conflicto; los dispositivos físicos remotos permanecen bloqueados hasta configurar `VOICE_API_KEY` y usuarios permitidos.
5. El contrato de voz ya conserva ElevenLabs como ruta preferida y SpeechSynthesis como fallback explícito cuando el servicio no está configurado.

### P1 — riesgo alto de inconsistencias

1. El motor central versionado `roxy_trader/indicators.py` alimenta `moving_average_strategy.py`, `symbol_detail.py`, `living_market.py`, `roxy_scanner.py` y el dashboard heredado. Opciones conserva cálculos de riesgo propios del instrumento, no fórmulas duplicadas de EMA/RSI/MACD.
2. `st.session_state`, query params, watchlists y estado durable usan aislamiento, locks, revisión monotónica y reemplazo condicional. El protocolo remoto existe; falta configurar autenticación y desplegarlo fuera de loopback para dispositivos físicos.
3. Resuelto: las rutas directas de acciones y cripto se inicializan únicamente con el activo visible como `User selection`; no expanden el contexto a un universo estático ni lo presentan como watchlist.
4. La identidad de activos usa un resolvedor central con cache local, metadata, fuente, TTL, host allowlist y fallback financiero no alfabético. La cobertura explícita es 15 acciones/ETF y las 25 criptos del universo operativo actual; activos nuevos siguen requiriendo CoinGecko o Finnhub y permanecen `DEGRADED` si no resuelven.
5. Se retiraron 785 líneas inalcanzables de UI legacy, placeholders y prototipos; una prueba estructural protege el único punto de entrada activo.
6. El registro de rutas canónicas normaliza destinos heredados y las pruebas exigen que cada superficie enfocada tenga un destino registrado. Aún queda deuda visual por HTML/CSS embebido, no rutas silenciosas conocidas.

### P2 — rendimiento, mantenimiento y UX

1. Resuelto parcialmente: CSS global, runtime de voz y gráfica principal ya son recursos cacheados con diagnóstico. Aún quedan componentes HTML/JS especializados dentro de `streamlit_app.py` que deben extraerse sólo después de preservar sus contratos visuales y funcionales.
2. Resuelto: los TTL antes dispersos usan `roxy-cache/1.0.0`, con límites por clase, overrides validados, diagnóstico y guardas contra literales no clasificados.
3. `com.roxy.streamlit` es el dueño único comprobado del puerto 3000; los mensajes históricos de conflicto permanecen en el log antiguo, no como proceso activo.
4. Chromium/Playwright está instalado y los probes reales ya se ejecutan en escritorio, iPad y teléfono.
5. El backup runtime diario está instalado y verificado. Si TCC bloquea el volumen externo, utiliza un archivo local verificado y conserva el estado de permiso requerido.
6. README y AUTH ya describen el arranque canónico en 3000, voz en 8010, límites de proveedor, seguridad de sesión y recuperación local. Documentación especializada antigua fuera de esas rutas aún debe revisarse al tocar cada módulo.

## 5. Datos simulados, estáticos o fallback

| Elemento | Ubicación | Riesgo | Acción propuesta |
|---|---|---|---|
| Universo fallback de acciones/cripto | Retirado de rutas directas | Resuelto: podía parecer watchlist real | El activo visible inicia como `User selection`; tablas reales no se completan con símbolos estáticos |
| Paper/simulated trading | `storage.py`, adapters, UI | Correcto si permanece explícito | Mantener badge global PAPER |
| Broker simulation hub | `render_broker_simulation_hub` | Puede confundirse con conexión | Mostrar `PREVIEW_ONLY` por fila |
| Gráfica SVG/line fallback | funciones `static_*` y fallback de Plotly | Menor capacidad interactiva | Mantener solo como estado degradado visible |
| Academia fallback | perfiles locales en `streamlit_app.py` | Contenido no respaldado por fuente cargada | Mostrar `FALLBACK` y fuente |
| Identidad y logos cacheados | `asset_identity.py`, Diagnóstico | Resuelto para el universo operativo actual: 28/28 activos, 40 blobs válidos, cero inconsistencias | Finnhub/CoinGecko/Simple Icons/dominio con provenance; advertir automáticamente cualquier símbolo operativo sin cobertura |
| Bloque legacy inalcanzable | retirado de `streamlit_app.py` | Resuelto | Mantener la prueba estructural que impide reintroducirlo |
| Defaults de capital/riesgo | varios helpers | Pueden parecer datos de cuenta | Distinguir `USER_INPUT`, `ACCOUNT_API`, `DEFAULT` |

No se encontraron precios numéricos falsos en `roxy_fallback_asset_rows`; sus precios son nulos. Sí existen visuales estáticos de referencia y nombres/tickers hardcodeados que no deben presentarse como mercado actual.

## 6. Mapa de integraciones

| Proveedor | Uso previsto/actual | Estado comprobado | Política correcta |
|---|---|---|---|
| Alpaca | Cuenta paper, acciones, velas, latest trade, streaming bridge | Configurado; autenticación inválida | Bloquear acciones/opciones; nunca degradar silenciosamente |
| Polygon | Velas premium alternas | No configurado | Ruta secundaria para acciones |
| yfinance | Velas/precios públicos fallback | Implementado | Mostrar `FALLBACK`, latencia no garantizada |
| Finviz Elite | Screener, patrones, sectores, noticias | Cliente implementado; no configurado | No tratar como streaming |
| BinanceUS/ccxt | Cripto REST y WebSocket | Operativo | Fuente principal cripto actual |
| Crypto.com | Ticker/velas públicas y credenciales privadas opcionales | REST público disponible | Separar público de cuenta privada |
| TradingView | Widget/enlaces y webhook de confirmación | UI disponible; webhook sin secreto | No contar como confirmación hasta webhook autenticado |
| ElevenLabs | Voz | Clave presente pero rechazada por HTTP 401; circuito `AUTH_INVALID` persistente y fallback local | No presentar como conectado; rotar con el instalador seguro y revalidar |
| FastAPI voz | Sesiones, contexto, SSE, feedback, conocimiento | Operativo en 8010 | Unificar URL contractual y contexto con Streamlit |
| RSS Yahoo/Nasdaq | Noticias e IPOs | Implementado | Mostrar feed y timestamp |
| Finnhub Profile 2 | Perfil corporativo y logo | Soportado; no configurado | Usar solo al existir `FINNHUB_KEY`/`FINNHUB_API_KEY` |
| CoinGecko | Identidad y logo de cripto | Público y cacheado; sujeto a rate limit | Cache local 14 días y fallback Simple Icons |
| Simple Icons / dominio oficial | Logo de respaldo | Cache local operativo | Solo hosts allowlisted; fallback genérico si falla |
| Deriv | Contratos públicos por WebSocket | Implementado | Solo análisis/preview |
| Schwab | Preview de tickets | Credenciales no verificadas | Preview-only hasta OAuth y permisos |
| Webull | Confirmación/ruta alterna | Sin integración operativa comprobada | No mostrar como conectado |
| Robinhood | Placeholders de vault | No usado para órdenes | Eliminar de superficies operativas |

## 7. Propuesta de navegación

Usar una sola definición tipada de rutas, con permisos, estado y destino. No mantener menús HTML separados.

```text
Mercado
  Resumen | Acciones | Criptomonedas | ETFs | Índices | Sectores | Calendario | Noticias
Trading
  Oportunidades | Screener | Watchlists | Gráficas | Estrategias | Alertas | Operaciones | Backtesting | Rendimiento
Roxy
  Chat y voz | Actividad | Memoria | Automatizaciones | Notificaciones
Ecosistema
  Asistente personal | Hogar | Compras | Documentos | Servicios | Dispositivos
Sistema
  Integraciones | Fuentes de datos | Permisos | Diagnóstico | Configuración
```

Primera migración: mapear las páginas existentes a esta taxonomía sin duplicarlas. Toda ruta aún no implementada debe abrir un estado `NOT_IMPLEMENTED` explícito, nunca caer silenciosamente a Acciones.

## 8. Propuesta técnica para gráficas

### Contrato de datos

Crear un DTO único por vela:

```text
Candle(symbol, market, timeframe, ts, open, high, low, close, volume,
       session, provider, provider_ts, received_at, latency_class, is_final)
```

Reglas:

- timestamps UTC y calendario de mercado explícito;
- `provider`, `latency_class` y `is_final` obligatorios;
- 20m/30m/2h/4h derivados en backend a partir de velas base reales;
- cache por `(provider, symbol, timeframe, session)`;
- WebSocket actualiza la vela activa; REST repara huecos;
- una sola selección global de símbolo y un `ChartWorkspaceState` por usuario.

### Motor central de indicadores

Crear `roxy_trader/indicators.py` con versión de fórmula y salidas estables:

- EMA 9/21/50/200;
- SMA configurable;
- VWAP por sesión;
- RSI Wilder 14;
- MACD 12/26/9;
- Bollinger 20/2;
- ATR Wilder 14;
- volumen promedio y relativo;
- máximos/mínimos regular, premarket y día.

Cada función debe aceptar velas normalizadas, devolver columnas y metadata de versión, y validarse contra fixtures conocidos. `living_market.py`, `symbol_detail.py` y estrategias deben consumir ese motor.

### Render

Para una experiencia tipo TC2000, Plotly debe quedar como fallback. La ruta recomendada es TradingView Lightweight Charts para velas/volumen/crosshair/zoom, con una capa propia de dibujos persistidos. La Charting Library completa solo debe usarse si se obtiene licencia.

El workspace principal tendrá dos instancias sincronizadas:

- 15m: entrada, gatillo y volumen;
- 1h: tendencia, contexto e invalidación.

Ambas reciben el mismo `selected_asset_id`; el cambio de símbolo no recarga la página. Dibujos y estrategias usan coordenadas `(timestamp, price)` y se guardan por usuario/layout.

## 9. Plan por fases

### Fase 1 — auditoría y estabilización

- dividir health de mercado, infraestructura y testing;
- corregir rutas y dueño único de Streamlit;
- resolver credenciales Alpaca o configurar Polygon;
- alinear contrato de voz y suite;
- retirar código inalcanzable;
- completar panel Diagnóstico.

### Fase 2 — sistema visual y navegación

- registro central de rutas;
- tokens claro/oscuro y componentes compartidos;
- estados operativos uniformes;
- servicio/cache de logos;
- QA escritorio/iPad/móvil con capturas nuevas.

### Fase 3 — infraestructura de datos

- `MarketDataGateway` normalizado;
- cache central, deduplicación y backfill;
- streaming con reconexión y métricas;
- provenance y latencia en cada DTO;
- eliminar seeds de las superficies operativas.

### Fase 4 — gráficas profesionales

- workspace 15m/1h;
- motor central de indicadores;
- dibujos persistentes y sincronizados;
- sesiones extendidas y vela activa;
- pruebas de performance y huecos.

### Fase 5 — estrategias y oportunidades

- detectores versionados;
- geometría visible en gráfica;
- máquina de estados de oportunidad;
- watchlist/alertas/archivo conectados;
- backtest y seguimiento de falsos positivos/negativos.

### Fase 6 — cerebro y voz

- contexto operativo único;
- comandos UI tipados;
- confirmación de acciones sensibles;
- continuidad voz/texto;
- observabilidad y recuperación.

### Fase 7 — ecosistema

- módulos personales detrás de permisos explícitos;
- calendario/correo/documentos/hogar;
- API y cliente móvil sobre el mismo contexto.

## 10. Criterios de aceptación por fase

### Fase 1

- cero rutas que caigan silenciosamente a otro módulo;
- health de mercado no bloqueado por almacenamiento auxiliar;
- frontend, DB y voz con checks visibles;
- suite sin fallos no documentados;
- cero código activo marcado como demo sin badge.

### Fase 2

- una sola fuente de navegación;
- contraste, foco, teclado y reflow probados;
- paridad funcional en 1440x900, 1024x1366 y 390x844;
- logos cacheados con fuente y fallback verificable.

### Fase 3

- toda cotización incluye proveedor, timestamp y clase de latencia;
- ninguna fuente retrasada se etiqueta realtime;
- reconexión y backfill probados;
- peticiones duplicadas medidas y reducidas.

### Fase 4

- las dos gráficas cambian de activo en menos de 500 ms cuando hay cache;
- 1m, 5m, 15m, 20m, 30m, 1h, 2h, 4h, 1d y 1w producen OHLC válido;
- indicadores coinciden con fixtures de referencia;
- dibujos y layout sobreviven recarga y cambio de dispositivo.

### Fase 5

- cada oportunidad tiene regla, geometría, entrada, stop, objetivo, R:R e invalidación;
- estados siguen transiciones válidas y quedan auditados;
- expiradas/invalidadas se archivan automáticamente;
- alerta y watchlist muestran el mismo `opportunity_id`.

### Fase 6

- voz conoce activo, página, timeframe, estrategia e indicadores visibles;
- comandos UI se ejecutan sobre el mismo estado;
- una respuesta de voz no crea turnos duplicados;
- fallos de ElevenLabs producen estado claro y recuperación definida.

### Fase 7

- permisos por integración y acción;
- logs sin secretos;
- aislamiento de datos por usuario;
- sincronización multi-dispositivo con conflictos definidos.

## 11. Correcciones aplicadas en esta pasada

1. Añadidos 20m y 30m al selector central.
2. Añadido resampling real: 20m desde 5m y 30m desde 15m, para acciones y cripto.
3. Añadido `system_diagnostics.py`, reutilizable fuera de Streamlit y sin exponer secretos.
4. Añadida página `Diagnostico` con frontend, voz, DB, proveedores, cache y modo de ejecución.
5. Corregida persistencia de la vista para que cumpla el contrato de URL/sesión.
6. Corregido `com.roxy.health_watchdog` para vigilar el puerto 3000.
7. Separados fallos auxiliares de almacenamiento/backup/probe de los fallos reales de mercado; un fallo real de OHLC/indicadores sigue bloqueando.
8. Añadidas pruebas de diagnóstico, temporalidades y severidad de health.

Validación anterior a la última integración: la suite completa pasaba con 2.125 pruebas y código de salida 0.

## 12. Actualización de estabilización y QA visual

Después de la auditoría inicial se completaron estas correcciones adicionales:

1. Se instaló Chromium para el probe local y se creó acceso diagnóstico local, efímero, firmado con HMAC y sin exponer el token en la URL final.
2. Se corrigió el limpiador de voz que podía ocultar el `body` o componentes generales de Roxy; ahora solo inspecciona elementos con identidad explícita de voz/flotante.
3. Se corrigió la sintaxis del puente JavaScript del Desktop Helper y se añadió fallback de voz del navegador cuando ElevenLabs no está configurado.
4. Se normalizaron rutas heredadas (`watchlist`, `scanner`, `alertas`, `historial`, `portafolio`, `opciones`) hacia páginas y pestañas canónicas.
5. Se eliminó del Dashboard inicial el escenario holográfico decorativo y se reemplazó por una superficie financiera compacta, centrada en gráfica, fuente, riesgo, plan, oportunidades y calendario.
6. Se retiraron del inicio precios de índices, porcentajes, horarios y niveles de entrada/stop/objetivo codificados a mano. Si el contrato no entrega una lectura, la UI muestra `Sin lectura`, `Fuente no disponible` o `Pendiente`.
7. Se verificó el Dashboard en navegador real:
   - escritorio 1280x900: OK;
   - iPad 820x1180: OK;
   - teléfono 390x844: OK;
   - sin desbordamiento horizontal, estado/URL persistentes y sin los valores simulados prohibidos.
8. Se dejó un único proceso Streamlit bajo `com.roxy.streamlit`, puerto 3000 y HTTP 200.
9. Se instaló respaldo diario. macOS deniega al LaunchAgent escribir directamente en el volumen externo por TCC, por lo que el servicio usa fallback local verificado, conserva el motivo y valida miembros críticos del archivo.
10. El health check ya reconoce ese fallback verificado como recuperación, en vez de mantener un `PermissionError` histórico como fallo activo.
11. La regresión completa pasa: 2.120 pruebas, código de salida 0.
12. El workspace de acciones fue probado en navegador real con AAPL y conserva simultáneamente las superficies 15m/1h, URL/estado y gráfica operativa.
13. Se retiró el fallback de Yahoo/Stooq ejecutado directamente desde el navegador, que generaba errores CORS repetidos. Los precios live ahora llegan únicamente por el bridge/snapshot o el refresco del servidor; si no responden, la gráfica conserva la última vela real y lo declara.
14. El mantenimiento de output prueba escritura antes de archivar. Bajo LaunchAgent, RoxyData devuelve permiso denegado y activa `output/maintenance_archive`; el reporte real quedó `OK`, protegido, con cero errores de archivo y `external_archive_ready=false`.
15. Se eliminó Clearbit del render activo. `asset_identity.py` normaliza símbolo/mercado, combina perfil, descarga solo desde hosts permitidos, valida MIME/tamaño, cachea bytes y metadata durante 14 días y entrega data URI al navegador.
16. El panel Diagnóstico incluye Finnhub, CoinGecko y un control de integridad del cache de logos. La precarga actual dejó 25 identidades conocidas resueltas; el DOM de AAPL confirmó `simple_icons`, `cached=true`, data URI local, alt accesible, cero Clearbit y cero errores de consola.
17. Se creó `roxy_trader/indicators.py`, actualizado al contrato `roxy-indicators/1.1.0`: SMA, EMA configurables, RSI Wilder, MACD, Bollinger, ATR Wilder, volumen medio/relativo y VWAP por sesión. Los consumidores comparten fórmulas y metadata; el chart contract expone EMA 9/21/50/200, VWAP y ATR14 además de los indicadores anteriores.
18. Se retiró la dependencia directa de `ta` en `roxy_scanner.py`; scanner y workspace comparan contra el mismo motor. La regresión focalizada de indicadores/consumidores pasa: 59 pruebas.
19. Se corrigió el contrato del plan operativo: niveles `null`, vacíos, cero o negativos ya no se publican como precios. Sin entrada, stop y objetivo positivos, la gráfica muestra `Plan pendiente`, no calcula R/R ni deriva estados de entrada/salida.
20. El probe visual ahora inspecciona también el texto de los iframes de componentes Streamlit. La validación AAPL 15m/1h confirma el estado pendiente y rechaza `0.0000` y `Tomar ganancia / no perseguir`, con URL/estado persistentes y cero errores bloqueantes.
21. El resumen de Acciones dejó de dibujar velas, OHLC, futuros, forex, alertas, watchlists y métricas de portafolio de demostración. Las vistas previas conducen a las gráficas reales; cuando falta proveedor o historial muestran un estado explícito. También se corrigió el HTML que Streamlit presentaba como código por indentación.
22. El contrato de contexto operativo ahora da prioridad a `symbol/market/tf` visibles en la URL y sincroniza ese resultado con sesión, gráficas y voz, evitando que la voz explique un ticker anterior.
23. Se creó `roxy_trader/watchlists.py`: listas múltiples por usuario, normalización, deduplicación, bloqueo de archivo, escritura atómica y alta/baja durable. La ruta `tab=watchlists` permite crear listas, agregar el activo seleccionado, abrirlo en análisis y eliminarlo.
24. La orden `Roxy, agrégala a mi watchlist` se resuelve localmente con el activo visible y actualiza el mismo almacén/contexto. La prueba de navegador confirmó alta, lectura durable desde una sesión nueva y baja en backend; el repintado visual de la misma sesión puede tardar durante el rerun de Streamlit y seguirá bajo observación.
25. Se añadieron alertas de precio durables al mismo almacén por usuario. La UI y la voz crean reglas exactas `sube a`/`baja a`, las vinculan al activo y watchlist visibles, las evalúan solo con precio positivo y fuente/freshness declaradas, y permiten archivarlas. La prueba real activó AAPL con `yfinance currentPrice`, manteniendo la etiqueta `STALE` en vez de presentarlo como streaming.
26. El panel Diagnóstico ahora inspecciona esquema, usuarios, listas, activos y alertas activas/activadas del estado operativo. Un archivo ausente se muestra `NO_DATA` y un JSON inválido se muestra `ERROR`.
27. Se añadió la lista administrada `Roxy Oportunidades`. Solo sincroniza filas trade-ready con contrato explícito `LIVE_*`, bucket `Live real` y estado `Broker/exchange live`; rechaza yfinance, seeds públicos y filas sin contrato. Si el proveedor está degradado conserva la última lista válida en vez de interpretar el corte como expiración.
28. El terminal activo de Acciones lee alertas y watchlists durables, retiró nivel/XP y nombres corporativos de relleno, y convirtió accesos de navegación, mapa, movers, noticias, alertas y watchlists en rutas reales. La fuente pública o degradada mantiene su estado visible.
29. Un scan saludable que deja de incluir una oportunidad la mueve al historial como `Expirada`, con timestamp y motivo. Un scan degradado no la expira. El historial es visible desde la lista administrada y el panel Diagnóstico cuenta oportunidades archivadas.
30. Se creó `ROXY_ROUTE_REGISTRY` como fuente canónica inicial para las rutas activas de mercado, trading, educación y diagnóstico. El terminal consume ese registro y una ruta desconocida falla explícitamente; también se retiraron los badges numéricos de módulos que no provenían de una métrica real.
31. La regresión final pasa con 2.131 pruebas y código de salida 0. El terminal conectado fue renderizado con éxito en escritorio 1280x900, iPad 820x1180 y teléfono 390x844: 3.621 caracteres útiles, URL/estado persistentes y ausencia confirmada de nivel/XP, nombre corporativo de relleno y contadores prohibidos.

Evidencia generada:

- `alerts/dashboard_probe_professional.json/png`
- `alerts/dashboard_probe_ipad.json/png`
- `alerts/dashboard_probe_mobile.json/png`
- `alerts/actions_workspace_probe.json/png`
- `alerts/asset_identity_render_probe.json`
- `output/asset_identity_render_probe.png`
- `alerts/indicator_engine_render_probe.json`
- `output/indicator_engine_render_probe.png`
- `alerts/actions_overview_real_data_probe.json`
- `output/actions_overview_real_data_probe.png`
- `alerts/watchlists_render_probe.json`
- `output/watchlists_render_probe.png`
- `alerts/alerts_render_probe.json`
- `output/alerts_render_probe.png`
- `alerts/actions_connected_terminal_probe.json`
- `output/actions_connected_terminal_probe.png`
- `alerts/actions_connected_terminal_ipad_probe.json`
- `output/actions_connected_terminal_ipad_probe.png`
- `alerts/actions_connected_terminal_mobile_probe.json`
- `output/actions_connected_terminal_mobile_probe.png`
- `alerts/runtime_backup.json`
- `alerts/output_maintenance.json`
- `alerts/roxy_realtime_check.json`

Bloqueo externo vigente: las credenciales efectivas de Alpaca responden `AUTH_INVALID` y Polygon no está configurado. Roxy mantiene acciones/opciones premium en estado degradado explícito; cripto, frontend, gráficas históricas, indicadores, base de datos, respaldo y diagnóstico continúan operativos. No se debe declarar streaming premium de acciones al 100% hasta corregir una de esas dos integraciones.

## 13. Cierre de duplicaciones, datos heredados y superficies Cripto

La siguiente pasada cerró deuda activa que todavía podía aparentar funcionalidad sin un contrato verificable:

1. `render_roxy_actions_command_center` quedó como adaptador del terminal canónico y se retiró el bloque duplicado de Acciones que mantenía cálculos, rutas y tarjetas propias.
2. `render_roxy_actions_folder` conserva una sola ruta de gráfica profesional y elimina más de 400 líneas inalcanzables. Entrada, stop, objetivo, R:R, riesgo y readiness ya no reciben números iniciales inventados.
3. El terminal dejó de publicar cambios, fuentes, puntuaciones, alertas, XP o niveles de mercado codificados a mano cuando el contrato no los entrega.
4. Cripto reutiliza la señal calculada por fila, obtiene sparklines de las mismas velas reales y evita repetir timeouts del proveedor para cada activo cuando BinanceUS está caído.
5. Las seis gráficas operativas de Cripto usan exclusivamente historial de exchange. Ya no invocan yfinance ni una gráfica sintética como fallback; la ausencia de velas produce un estado bloqueado explícito.
6. La consulta de contratos Deriv quedó bajo demanda para no bloquear precios, oportunidades ni gráficas. La tabla dejó de etiquetar la dirección interna `YES/NO/WAIT` como si fuera un contrato Deriv verificado; ahora muestra `ARRIBA/ABAJO/ESPERAR` como `Dirección Roxy`.
7. Las alertas visibles provienen del almacén durable, los eventos macro declaran fuente/estado y los planes incompletos permanecen pendientes en vez de derivar niveles desde un precio aislado.
8. Las rutas directas `crypto-20m`, `crypto-2h` y `crypto-daily` evitan ejecutar el scan completo del Dashboard antes de pintar el workspace seleccionado.
9. El runtime WebSocket compara el precio vivo con el ancla del cálculo. Si la desviación supera 2%, invalida temporalmente entrada, stop y objetivo, cambia el estado a `ESPERAR RECÁLCULO` y explica el porcentaje de desfase.
10. Se retiraron universos, estrellas, planetas, cometas y nebulosas de las tres superficies operativas y de sus gráficas. El resultado visual usa fondo financiero sobrio, jerarquía compacta y estados funcionales.
11. El probe de navegador prioriza el frame principal, limita el tiempo por iframe y nunca guarda el token diagnóstico en el reporte público.
12. `ROXY_ROUTE_REGISTRY` cubre ahora todas las vistas enfocadas, pestañas de Acciones y destinos del menú inferior de Cripto. Los tres menús inferiores duplicados se reemplazaron por un renderer canónico; `Mi Progreso` heredado se dirige a `Rendimiento` y el botón central abre `Roxy IA` en vez de volver silenciosamente al inicio.
13. Se creó `roxy_trader/market_data.py` con contrato `roxy-market-data/1.0.0`. Normaliza OHLCV y timestamps UTC, rechaza velas imposibles/no positivas y adjunta proveedor, fuente, mercado, timeframe, estado, filas, última vela, momento de consulta, clase de latencia y banderas realtime/delayed. `symbol_detail.py` aplica ya este contrato a Alpaca, Polygon, yfinance y BinanceUS, incluidos los timeframes derivados. El gateway registra prioridades, conserva cada intento y devuelve `NO_DATA` explícito si ningún proveedor entrega velas válidas.
14. El detector real `Uptrend Pullback to EMA21` quedó conectado al workspace 15m/1h. Evalúa las dos series centrales, publica estado, razones y advertencias, y dibuja zona de pullback, confirmación, stop/invalidez y target sobre Lightweight Charts. Si el estado es accionable pero todavía requiere vela, el encabezado, panel, voz y gráfica comparten `WAITING_CONFIRMATION` y la misma procedencia.
15. La capa visual deduplica niveles del plan y anotaciones del detector. `Solo velas` oculta todas las líneas estratégicas; `Plan Roxy` y `Indicadores` mantienen una lectura compacta sin repetir entrada/stop/target en el mismo precio.
16. El motor geométrico central detecta ahora tendencia alcista/bajista, consolidación, ruptura/ruptura bajista con volumen, triángulo simétrico/ascendente/descendente y wedge ascendente/descendente. Las estructuras convergentes exigen pivotes reales, regresiones independientes de máximos/mínimos y reducción verificable del rango. El chart recibe coordenadas `(timestamp, price)` y dibuja una línea de resistencia y otra de soporte; solo la estructura primaria por timeframe entra a la capa visual para evitar ruido.

### QA real de Cripto

Se validaron 20m, 2h y Daily de forma secuencial en los tres tamaños principales. Las nueve combinaciones conservaron vista, símbolo, mercado y temporalidad, renderizaron contenido útil y registraron cero errores bloqueantes de consola o página:

| Superficie | Escritorio 1440x1000 | iPad 820x1180 | Móvil 390x844 |
|---|---:|---:|---:|
| Crypto 20m | OK | OK | OK |
| Crypto 2h | OK | OK | OK |
| Crypto Daily | OK | OK | OK |

Las pruebas paralelas se descartaron como evidencia porque varias sesiones Streamlit pueden competir por el mismo bloqueo de caché durante el arranque en frío. La validación secuencial representa el flujo real de un usuario y dejó tiempos observados entre 9 y 47 segundos según caché y proveedor; la reducción adicional de esa latencia sigue abierta en Fase 3.

Evidencia nueva:

- `alerts/crypto_professional_final_probe.json`
- `output/crypto_professional_final_probe.png`
- `alerts/crypto_20m_desktop_probe.json`
- `alerts/crypto_2h_desktop_probe.json`
- `alerts/crypto_daily_desktop_probe.json`
- `alerts/crypto_20m_ipad_probe.json`
- `alerts/crypto_2h_ipad_probe.json`
- `alerts/crypto_daily_ipad_probe.json`
- `alerts/crypto_20m_mobile_probe.json`
- `alerts/crypto_2h_mobile_probe.json`
- `alerts/crypto_daily_mobile_probe.json`
- `alerts/canonical_navigation_mobile_probe.json`
- `output/canonical_navigation_mobile_probe.png`
- `alerts/actions_visual_strategy_probe.json`
- `output/actions_visual_strategy_probe.png`

Estado honesto: estas correcciones estabilizan y profesionalizan la superficie actual, pero no convierten todavía todo el alcance solicitado en “100% listo”. Permanecen abiertos el streaming premium de acciones, el backtesting integral y la expansión de estrategias visuales.

Validación de esta integración: **2.157 pruebas aprobadas**, 41 advertencias conocidas de dependencias/deprecaciones y código de salida 0. La navegación operativa principal ya está centralizada; todavía quedan menús propios del módulo educativo y pantallas administrativas heredadas por migrar antes de cerrar completamente esa fase.

## 14. Gráficas principales con dibujo y estrategia unificados

1. La ruta primaria de análisis de Acciones usa ahora el mismo runtime completo de dibujo para las dos gráficas operativas: entrada 15m y tendencia 1h. El renderer profesional anterior permanece como respaldo, seguido por Plotly, SVG y estado sin datos.
2. Las dos gráficas incluyen cursor, crosshair, zoom, pan, escala manual/automática, líneas de tendencia, rayos, horizontales/verticales, zonas, canales, Fibonacci, flechas, medición, texto, borrador, selección/edición, bloqueo, deshacer/rehacer, fullscreen y niveles rápidos de entrada/stop/objetivo.
3. Indicadores y configuraciones visuales se guardan por símbolo, timeframe y perfil. Los dibujos se guardan por símbolo/timeframe y sobreviven una recarga del navegador. Este almacenamiento sigue siendo local al dispositivo; la sincronización durable multi-dispositivo permanece abierta y no se presenta como completada.
4. Las anotaciones del motor central —zona de entrada, confirmación, invalidación, objetivos y líneas geométricas— llegan también al runtime con dibujo. Si existe una estrategia validada, los niveles automáticos no se duplican como dibujos del plan; el usuario puede aplicar una copia editable desde la barra de herramientas.
5. Se corrigió un defecto de escala: un precio live ausente se convertía a cero y ampliaba el eje hasta valores negativos. El autoscale descarta ahora anclas no positivas, conserva telemetría verificable y en la evidencia AAPL 15m produjo un dominio 327.45–336.33.
6. La carga inicial del componente se redujo de 3.000 a 640 velas por panel principal. Mantiene contexto suficiente para 15m/1h y reduce tamaño de payload/tiempo de creación de iframe; los datos fuente continúan en caché para otros rangos.
7. El probe de navegador cambió a lectura DOM inmediata durante reruns de Streamlit, con fallback compatible. En arranque secuencial validó 1.439 caracteres útiles, URL/estado persistentes, `WAITING_CONFIRMATION`, ambas gráficas, controles de dibujo y cero errores bloqueantes.
8. Una prueba de interacción creó un nivel editable (`0 → 1 dibujo`) y, después de recargar, recuperó `1 dibujo guardado`. La barra expone 29 controles operativos en cada panel.

Evidencia:

- `alerts/actions_drawing_tools_probe.json`
- `output/actions_drawing_tools_probe.png`
- `output/playwright/actions-tools-scale-fixed.png`
- `output/playwright/actions-tools-interaction.png`

Regresión completa posterior: **2.157 pruebas aprobadas**, 41 advertencias conocidas y código de salida 0.

## 15. Estado durable de gráficas y limpieza final del terminal

1. Se creó `roxy_trader/chart_state.py` con esquema versionado, normalización estricta, límite de 200 dibujos, bloqueo de archivo y escritura atómica. El estado se separa por usuario, mercado, símbolo y timeframe.
2. El servidor valida herramientas, precios, tiempos, textos y settings antes de guardar. Rechaza símbolos vacíos, herramientas desconocidas, números no finitos, payloads demasiado grandes y contexto distinto a la gráfica visible.
3. Cada gráfica carga primero la configuración durable del servidor y después aplica, si existe, la copia local más reciente. En un dispositivo nuevo, el estado del servidor restaura dibujos e indicadores sin depender de `localStorage` previo.
4. La barra incluye `Sincronizar grafica`. El navegador serializa solo la gráfica visible, usa Base64 URL-safe, elimina el token diagnóstico, navega por el canal autenticado de Streamlit y Roxy borra inmediatamente `chart_sync` de la URL después de persistir.
5. La prueba end-to-end guardó un nivel horizontal AAPL 15m en una sesión y una segunda sesión limpia restauró `1 dibujo guardado`, `serverDrawingCount=1` y `syncState=restored`. La URL final no contiene `chart_sync`.
6. El terminal de Acciones dejó de usar estrellas, nebulosas y animaciones de fondo. Conserva un fondo financiero lineal, jerarquía de datos y estados reales. El probe de resumen produjo 3.625 caracteres útiles, URL/estado persistentes y cero errores bloqueantes.

Evidencia:

- `alerts/actions_chart_sync_probe.json`
- `output/actions_chart_sync_probe.png`
- `alerts/actions_terminal_professional_probe.json`
- `output/actions_terminal_professional_probe.png`

Regresión completa posterior: **2.163 pruebas aprobadas**, 41 advertencias conocidas y código de salida 0.

## 16. Backtesting reproducible y conectado

1. El motor de medias quedó versionado como `roxy-ma-backtest/2.0.0`. Se eliminó un sesgo temporal: el stop activo durante una vela se comprueba antes de actualizar el trailing stop con las medias calculadas al cierre de esa misma vela. Una regresión dedicada exige que ese stop nuevo sólo pueda actuar en la vela siguiente.
2. Se creó `roxy_trader/backtests.py` con el contrato durable de ejecuciones. Cada corrida conserva usuario, símbolo, mercado, temporalidad, versión del motor y estrategia, configuración completa, proveedor, clase de latencia, banderas realtime/delayed, cantidad y rango de velas, métricas, equity y operaciones.
3. El almacén usa bloqueo de archivo, escritura atómica, JSON estricto sin `NaN`/`Infinity`, separación por usuario y retención acotada a 100 corridas. Un profit factor sin pérdidas se conserva mediante una bandera explícita, no como JSON inválido.
4. La ejecución reutiliza `roxy-market-data/1.0.0`: descarta OHLC imposible, no inventa velas y devuelve `DATA_INSUFFICIENT`, `NO_TRADES`, `COMPLETED` o `ERROR` con causa visible.
5. La página Backtest dejó de depender como superficie principal de los CSV por lotes de junio. El usuario puede ejecutar el activo visible en 15m, 1h o diario, y configurar capital, porcentaje de posición, comisión, slippage y cooldown. Los CSV anteriores permanecen identificados como historial legado.
6. La interfaz explica las hipótesis de ejecución: señal al cierre, entrada en la apertura siguiente, comisión y slippage. También muestra fuente, retraso, última vela, momento de ejecución, versiones, retorno, equity, trades, win rate, profit factor, drawdown, curva y operaciones reproducibles.
7. La prueba real de AAPL 1h descargó 1.020 velas válidas, declaró `yfinance` como `Retrasado / fallback`, ejecutó 24 operaciones y guardó la corrida. Una sesión de navegador nueva restauró ese resultado desde el almacén durable sin volver a ejecutarlo.
8. El probe de navegador confundía rutas canónicas con etiquetas de navegación (`Dashboard`/`Inicio`, `Backtest`/`Backtesting`). Ahora mantiene por separado la ruta esperada y su etiqueta visible, eliminando falsos fallos sin relajar la comprobación de URL o selección.
9. La evidencia `alerts/backtest_render_probe.json` terminó `OK`: 5.423 caracteres útiles, AAPL/stock/1h y vista persistentes, cero errores bloqueantes de consola y cero errores de página. La captura está en `output/playwright/backtest_reproducible.png`.

Regresión completa posterior: **2.163 pruebas aprobadas, 1 omitida**, 40 advertencias conocidas y código de salida 0.

Límite vigente: el backtest de acciones puede usar yfinance como histórico público retrasado y lo declara. No se promueve a streaming ni autoriza operación real; Alpaca continúa en `AUTH_INVALID` y Polygon no está configurado.

## 17. Rendimiento y operaciones paper sin evidencia inflada

1. El resumen paper dejó de contar candidatos `BLOCKED` como evidencia trackeada. En el estado actual existen 1.488 candidatos crudos, pero 1.453 están bloqueados y no contribuyen a precisión, preparación ni rentabilidad.
2. Se corrigió otra fuente de inflación: snapshots repetidos por el scanner sobre el mismo activo, estrategia, temporalidad y sesión se consolidan como un episodio. Los 35 cierres crudos actuales representan 4 episodios independientes; 31 duplicados correlacionados quedan visibles como consolidados, no como trades adicionales.
3. La consistencia semanal usa la misma consolidación. Por tanto, repetir una señal cada cinco minutos y cerrarlas juntas ya no puede satisfacer artificialmente los umbrales de muestra.
4. Rendimiento usa ahora los backtests durables del usuario en `data/roxy_backtests.json`; los CSV antiguos por lotes dejaron de contar en sus KPI. La UI muestra candidatos, bloqueados, duplicados, episodios paper elegibles, cierres, resultados y fuente.
5. Se retiraron de la superficie activa de Rendimiento los escenarios hipotéticos de precios, usuarios pagos e ingresos. El panel se centra en evidencia operativa, estados de fuente y límites de la muestra.
6. Las filas de memoria dejaron de llamarse `Alerta real` sin contrato; usan `Alerta rastreada` e incluyen proveedor, clase de dato y gate cuando esos campos existen.
7. Se creó `roxy_trader/operations.py`. El snapshot de operaciones es de solo lectura, combina los journals de acciones y cripto, excluye bloqueados, consolida episodios, calcula riesgo/P&L sólo cuando hay datos suficientes y declara `PAPER_ONLY` con órdenes reales apagadas.
8. La ruta `Capital` se presenta como `Portafolio y operaciones`. El registro paper y el estado del broker son la superficie principal; la proyección de crecimiento quedó dentro de un expander titulado como hipotético.
9. El gráfico hipotético de capital dejó de usar una escala/log binding que producía warnings Vega al renderizarse dentro del expander.

Evidencia:

- `alerts/performance_evidence_probe.json`
- `output/playwright/performance_evidence.png`
- `alerts/paper_operations_probe.json`
- `output/playwright/paper_operations.png`

Regresión completa posterior: **2.167 pruebas aprobadas, 1 omitida**, 40 advertencias conocidas y código de salida 0.

Ambos probes terminaron `OK`, conservaron ruta/activo/mercado/timeframe y registraron cero errores bloqueantes. Rendimiento renderizó 6.741 caracteres útiles; Portafolio y operaciones, 4.879.

Regresión completa posterior: **2.165 pruebas aprobadas, 1 omitida**, 41 advertencias conocidas y código de salida 0.

## 18. Diagnóstico recuperado, aislamiento de simulación y brokers efectivos

1. El probe central separa la ruta canónica de su etiqueta visible y compara textos requeridos sin depender de mayúsculas o espacios. `Dashboard` se valida contra `Inicio`; `Capital`, contra `Portafolio y operaciones`; `Backtest`, contra `Backtesting`.
2. El watchdog dejó de solicitar literalmente `Dashboard` dentro de una pantalla cuyo selector visible dice `Inicio`. Los probes principal y de búsqueda se regeneraron `OK`, con 2.251 y 2.239 caracteres útiles, estado/URL persistentes y sólo warnings benignos del navegador.
3. `alerts/roxy_realtime_check.json` pasó de `FAIL` funcional a `WARN`. La causa actual es externa y explícita: Alpaca paper responde `AUTH_INVALID`. El SLO histórico conserva los fallos anteriores y se recuperará con muestras nuevas; no se borró historial para maquillar la estabilidad.
4. La tabla SQLite heredada contiene posiciones de prueba del usuario `tester`. No se eliminaron. `storage.get_simulated_trades` acepta ahora filtro de usuario y el portafolio usa siempre `roxy_os_user_id()`, igual que las posiciones abiertas.
5. La prueba visual del portafolio confirmó que el usuario diagnóstico no ve `tester`, muestra ausencia de posiciones propias y declara las tablas exactas de origen. El probe terminó `OK` con 5.428 caracteres útiles y cero errores bloqueantes.
6. El antiguo `Roxy Trader Simulation Hub` y sus capacidades genéricas codificadas (`AAPL · TSLA · BTC`, `1m–1M`, brokers futuros) se retiraron del código activo. El renderer de brokers deriva plataformas, modo y configuración desde `PLATFORM_PROFILES` y el vault/env efectivo; capital, 1R, setups listos y vigilancia provienen de la sesión actual.

Evidencia:

- `alerts/dashboard_render_probe.json`
- `alerts/dashboard_render_probe_search.json`
- `alerts/roxy_realtime_check.json`
- `alerts/paper_operations_probe.json`
- `output/playwright/paper_operations.png`

## 19. Integraciones validadas y diagnóstico runtime no bloqueante

1. El Live Provider Center separa ahora configuración de operación. Tener `ALPACA_API_KEY` y secreto presentes ya no basta para declarar el proveedor listo: la pantalla superpone el resultado de `alpaca_account_probe` del watchdog.
2. Con el estado vigente `AUTH_INVALID`, la tarjeta de Alpaca muestra `Autenticacion invalida`, modo `AUTH_INVALID` y tono de error. El resumen superior declara `Alpaca no operativo` y `PROVIDER_AUTH_FAILED`; yfinance permanece identificado sólo como fallback disponible.
3. Un probe `OK` cambia Alpaca a `PAPER_VALIDATED`/`PAPER_LIVE_VALIDATED`. Si todavía no existe reporte runtime, la UI conserva el estado prudente de credenciales presentes y no inventa una validación.
4. La ruta y el encabezado visible usan ya `Integraciones` de forma consistente. La banda resume `Fuentes disponibles`, porque una fuente pública o fallback no es una credencial.
5. El diagnóstico transforma el reporte del watchdog en filas operativas seguras: frontend, backend de mercado, heartbeat, gráficas realtime, almacenamiento, logs, notificaciones, Alpaca runtime y rutas STOCK/CRYPTO/OPTIONS con estado de alertas.
6. La antigüedad del reporte forma parte del contrato. Un reporte vencido degrada a `WARNING` incluso una comprobación que fue `OK`, evitando presentar snapshots antiguos como conexión actual.
7. La carga inicial ya no ejecuta `PRAGMA quick_check` sobre la base de 211,7 MB ni probes HTTP recursivos desde la propia sesión Streamlit. La UI usa el watchdog vigente y deja lectura local, caché, identidad, puertos y comprobación de base bajo demanda. El chequeo profundo sigue disponible para mantenimiento y pruebas.
8. El resumen runtime se renderiza como texto accesible antes de cualquier tabla, de modo que estados críticos no dependan del canvas de `st.dataframe` ni de una operación local lenta.

Evidencia:

- `alerts/platforms_runtime_probe.json`
- `output/playwright/platforms_runtime.png`
- `alerts/diagnostics_runtime_probe.json`
- `output/playwright/diagnostics_runtime.png`

Ambos probes terminaron `OK`, conservaron vista, símbolo, mercado y temporalidad, y registraron cero errores bloqueantes de consola o página. Integraciones renderizó 9.324 caracteres útiles; Diagnóstico, 2.901.

Regresión completa posterior: **2.174 pruebas aprobadas, 1 omitida**, 40 advertencias conocidas y código de salida 0.

## 20. Noticias y calendario como rutas canónicas verificables

1. `Noticias` y `Calendario` son páginas enfocadas registradas en `ROXY_ROUTE_REGISTRY`; ya no dependen de enlaces heredados ni de una pestaña oculta. Los alias `News` y `Calendar` resuelven a las rutas canónicas en español.
2. Ambas páginas usan una ruta rápida y no cargan el scanner completo, oportunidades ni contexto de gráficas antes de pintar información que no depende de ellos.
3. Noticias consulta RSS reales, normaliza titular, resumen, fuente, enlace y publicación, y muestra estado, cantidad, fuentes, última actualización y ruta de caché. Los enlaces sólo aceptan `http`/`https` y abren con `noopener noreferrer`.
4. El caché de noticias es durable, atómico y versionado como esquema 2. Si todos los RSS fallan, conserva el último snapshot y lo marca `DELAYED`; si no existe cache, muestra `NO_DATA`. Nunca genera titulares para llenar espacio.
5. Se corrigió una desviación horaria: `feedparser` entrega `struct_time` UTC y ahora se convierte con `calendar.timegm`, no con `time.mktime`. El caché v1 quedó invalidado para no conservar publicaciones desplazadas al futuro. El snapshot vigente tiene 24 noticias, 3 fuentes y ningún timestamp futuro.
6. Calendario reutiliza el motor central `macro_calendar_status`. Esta observación inicial quedó reemplazada por las secciones 48 y 49: la mera legibilidad del archivo ya no basta para declarar `CONNECTED`.
7. La pantalla no inserta eventos macro de demostración. Fuente, frescura, cobertura y actividad se evalúan por separado.
8. Noticias y Calendario se validaron secuencialmente en escritorio, iPad (820×1180) y móvil (390×844). Todas las combinaciones conservaron vista, símbolo, mercado y temporalidad y registraron cero errores bloqueantes.

Evidencia:

- `alerts/news_route_probe.json`
- `alerts/news_ipad_probe.json`
- `alerts/news_mobile_probe.json`
- `output/playwright/news_route.png`
- `output/playwright/news_ipad.png`
- `output/playwright/news_mobile.png`
- `alerts/calendar_route_probe.json`
- `alerts/calendar_ipad_probe.json`
- `alerts/calendar_mobile_probe.json`
- `output/playwright/calendar_route.png`
- `output/playwright/calendar_ipad.png`
- `output/playwright/calendar_mobile.png`

Regresión completa posterior: **2.179 pruebas aprobadas, 1 omitida**, 40 advertencias conocidas y código de salida 0.

## 21. Voz unificada con contexto, navegación y alertas reales

1. El servicio de voz incorpora ahora el activo, mercado, temporalidad y página visibles en la misma solicitud que procesa el cerebro local. Las expresiones relativas como “esta oportunidad” ya no se interpretan como tickers (`ESTA`); se resuelven contra el contexto operativo seleccionado.
2. La prueba real con AAPL devolvió una respuesta prudente porque no había oportunidad clara, conservando `active_symbol=AAPL`, `active_market=stock`, `active_timeframe=1h` y `active_page=Activo`. La prueba con LINK/USD explicó el setup real vigente (`WATCH`/`WAIT`, entrada 8,39, stop 8,18 y confirmaciones faltantes) con latencia local inferior a 12 ms.
3. “Roxy, agrégala a mi watchlist” usa el activo visible sin volver a preguntar. La mutación durable y el mensaje de confirmación se procesan antes de los retornos rápidos de Acciones y Crypto, de modo que el comando funciona también dentro de módulos directos.
4. “Roxy, cambia a la gráfica de una hora” es ahora una acción nativa `set_timeframe`, no una respuesta conversacional. Conserva NVDA, mercado, módulo y pestaña, cambia URL, estado de sesión y temporalidad seleccionada de 15m a 1h, y devuelve confirmación audible. El probe acepta una temporalidad final explícita para validar intencionalmente cambios de estado, sin confundirlos con pérdida de persistencia.
5. La voz también crea alertas exactas sobre el activo visible y las atribuye a `voice_command`. Para LINK/USD se verificó una regla por encima de 12,34 que permanece `Activa` y otra por encima de 1,23 que pasó a `Activada` con precio 8,389, fuente `BinanceUS ticker`, frescura `LIVE`, hora de evaluación y hora de activación durables.
6. Alertas dejó de cargar todo el centro de Acciones y de consultar hasta veinte símbolos secuencialmente en cada rerun. Es una ruta canónica rápida (`?view=Alertas`), evalúa inmediatamente el activo visible con el motor central y deja los demás al monitor operativo.
7. Todos los enlaces activos hacia Alertas usan la nueva ruta registrada. El estado sin dato, la fuente y la frescura siguen siendo explícitos; no se inventa un precio mientras una cotización no está disponible.
8. La prueba móvil 390×844 mostró LINK/USD a 8,3890, fuente BinanceUS y estado `LIVE`; el contenido se adapta a una sola columna sin desbordamiento funcional.

Evidencia:

- `alerts/voice_context_probe.json`
- `alerts/voice_opportunity_probe.json`
- `alerts/voice_watchlist_add_probe.json`
- `alerts/voice_watchlist_actions_probe.json`
- `alerts/voice_timeframe_probe.json`
- `alerts/voice_alert_create_probe.json`
- `alerts/voice_alert_trigger_create_probe.json`
- `alerts/voice_alert_transition_probe.json`
- `alerts/voice_alert_mobile_probe.json`
- `output/playwright/voice_watchlist_add.png`
- `output/playwright/voice_watchlist_actions.png`
- `output/playwright/voice_timeframe.png`
- `output/playwright/voice_alert_create.png`
- `output/playwright/voice_alert_transition.png`
- `output/playwright/voice_alert_mobile.png`

Límite vigente: las acciones que requieren streaming premium siguen bloqueadas por `AUTH_INVALID` de Alpaca. La prueba de alertas operativas utiliza cripto porque BinanceUS sí responde con un contrato `LIVE`; el sistema no extrapola ese estado a acciones u opciones.

Regresión completa posterior: **2.191 pruebas aprobadas**, 41 advertencias conocidas y código de salida 0.

## 22. Estado de interfaz aislado por usuario y retiro de UI inalcanzable

1. `alerts/dashboard_ui_state.json` dejó de ser un único registro global. `roxy_trader/ui_state.py` implementa el esquema 2 con estados separados por usuario, normalización de identidad, bloqueo de archivo, escritura atómica y `fsync`.
2. El esquema anterior se migra de forma conservadora únicamente a `local_user`. Un usuario autenticado nuevo recibe estado vacío y nunca hereda el ticker, mercado, temporalidad o página del registro global heredado.
3. La prueba sobre el archivo runtime real conserva simultáneamente `local_user = LINK/USD · Alertas · 1h` y `roxy_diagnostic_probe = ETH/USD · Calendario · 4h`. La segunda sesión no sobrescribió la primera.
4. La ruta Alertas publica primero el estado durable de las reglas antes de solicitar una cotización. En un arranque frío, la pantalla ya puede mostrar símbolo, nivel, estado y última fuente mientras el proveedor responde; después evalúa el activo visible y refresca el contrato live.
5. Se eliminaron 785 líneas de UI heredada que estaban después del `return` definitivo de `main()`. Incluían login local alterno, placeholders, un prototipo de señales AI, paneles admin y ejecución paper duplicada que nunca podían ejecutarse. El punto de entrada y las superficies canónicas permanecen intactos.
6. `streamlit_app.py` bajó de 58.880 a 58.094 líneas. La compilación AST/Python y las pruebas enfocadas confirmaron que no se retiró código alcanzable.

Evidencia:

- `alerts/ui_state_isolation_probe.json`
- `alerts/alerts_progressive_probe.json`
- `alerts/dashboard_ui_state.json`
- `output/playwright/ui_state_isolation.png`

Regresión completa posterior: **2.194 pruebas aprobadas**, 41 advertencias conocidas y código de salida 0.

## 23. Autenticación end-to-end y eliminación de secretos en URL

1. Una sesión limpia de navegador confirmó que el Dashboard no es accesible sin autenticación. La puerta muestra login, registro, passkey y proveedores OAuth configurables en escritorio y móvil, con cero errores de consola.
2. Se ejecutó un flujo real completo con una cuenta diagnóstica: registro, creación de sesión, entrada al Dashboard, navegación interna hacia Alertas y cierre de sesión. La cuenta y sus registros de prueba se eliminaron después de verificar el flujo.
3. La prueba descubrió que `rx_session` y un `rx_profile` que incluía el token se propagaban a cada enlace interno. Esto exponía la sesión en URL, historial y potencialmente `Referer`. La propagación por enlaces y el `MutationObserver` asociado se retiraron.
4. El perfil público del navegador ya no contiene `session_token`. Los enlaces internos conservan únicamente contexto funcional (`view`, `symbol`, `market`, `tf`, `module`, `tab`). La sesión se restaura desde almacenamiento local sólo mediante un parámetro transitorio, que el servidor valida contra un usuario existente y elimina inmediatamente de la URL.
5. Se eliminó la recuperación insegura que permitía crear un usuario desconocido a partir de un perfil suministrado por el cliente o de cualquier username/password no registrado. Un login desconocido es ahora estrictamente rechazado.
6. Los tokens persistidos en `roxy_users` se rotan en cada autenticación y se guardan únicamente como SHA-256; los tokens planos heredados se migran después de una validación correcta.
7. Se añadió `Cerrar sesion` a todas las superficies autenticadas. La acción revoca el hash en servidor, borra sesión y perfil del navegador, elimina parámetros sensibles y vuelve al login. La prueba real terminó con `storedToken=null` y login visible.
8. El helper GitHub OAuth local tenía un `IndentationError` no cubierto por la suite. Se corrigió, ahora respeta un `state` explícito, rechaza callbacks sin estado o con estado incorrecto, escapa salida y protege el archivo callback con modo `0600`. La ruta equivalente del admin API exige además estado obligatorio, no expirado y de un solo uso, ignora redirect URI suministrado por el cliente y usa el almacenado en servidor; dejó de escribir el token del proveedor en texto plano. La documentación aclara qué flujo es sólo de desarrollo y cuál pertenece al API protegido.
9. La compilación recursiva de `roxy_trader`, `tools`, `streamlit_app.py`, diagnóstico e identidad terminó sin errores. El warning de escape inválido del runtime de voz también fue corregido; sólo quedan dos advertencias de dependencias externas (`urllib3`/LibreSSL y `websockets.legacy`).

Evidencia:

- `output/playwright/auth_gate.png`
- `output/playwright/auth_gate_mobile.png`
- pruebas `tests/test_auth_session_security.py`
- pruebas `tests/test_oauth_security.py`
- pruebas `tests/test_secrets_oauth_callback.py`
- `alerts/final_dashboard_probe.json`
- `output/playwright/final_dashboard.png`

Regresión completa posterior: **2.204 pruebas aprobadas**, 2 advertencias de dependencias conocidas y código de salida 0.

## 24. Endurecimiento de acceso y corrección del SLO operativo

1. El login incorpora un limitador persistente por identidad normalizada: cinco fallos dentro de quince minutos bloquean nuevos intentos durante quince minutos. La identidad se almacena únicamente como SHA-256 y el bloqueo sobrevive reinicios.
2. Un usuario inexistente y una contraseña incorrecta devuelven el mismo mensaje y ejecutan el mismo PBKDF, evitando enumeración por contenido o por diferencia obvia de tiempo.
3. Las cuentas nuevas usan PBKDF2-SHA256 con 600.000 iteraciones y mínimo de diez caracteres. Los hashes heredados de 160.000 iteraciones siguen validando y se actualizan automáticamente después del siguiente login correcto.
4. Las sesiones recordadas tienen una vida máxima de treinta días por defecto (`ROXY_SESSION_MAX_AGE_SECONDS` permite ajustar el contrato). Una sesión vencida se revoca en servidor y el navegador elimina el token al fallar la restauración.
5. Los respaldos JSON de usuarios se escriben con lock, archivo temporal, `fsync` y reemplazo atómico. Tanto esos archivos como SQLite quedan en modo `0600`; el runtime activo fue corregido y las futuras escrituras conservan ese permiso.
6. Una prueba real de navegador registró una cuenta, confirmó `password_iterations=600000`, hash de sesión de 64 caracteres sin token plano, cero enlaces con `rx_session`/`rx_profile`, logout con token local eliminado y cero excepciones de Streamlit. La cuenta temporal se eliminó después de JSON y de seis tablas relacionadas.
7. El SLO histórico ya no puede degradar el núcleo por sus propios fallos anteriores. Sólo se excluye su check autorreferencial; cualquier otro `FAIL` continúa afectando el core. Tras diez ciclos sanos consecutivos el diagnóstico informa **Core operativo / externo bloqueado** y mantiene Alpaca `AUTH_INVALID` como degradación externa explícita.
8. El reporte de mantenimiento dejó de producir falsos mismatches cuando el archivo histórico limitante cambia dentro de la tolerancia aceptada. El check volvió a `OK` con presupuestos, archivos y operación protegidos.
9. La cabecera del Dashboard buscaba la fuente del símbolo sólo entre las tres primeras oportunidades. Ahora recorre la tabla completa; si el símbolo no tiene señal lo declara como `Sin oportunidad para este activo` y separa esa fuente de la fuente real de velas mostrada en la gráfica.
10. El texto azul de recuperación de contraseña no respondía. Ahora es un control real que declara que falta el proveedor de correo y orienta hacia passkey o administrador local. Una sesión autenticada puede cambiar su contraseña desde `Seguridad de cuenta`; el flujo verifica la contraseña actual, aplica la política vigente, rota el token y revoca las demás sesiones recordadas. El administrador local tiene además `tools/reset_local_password.py`, que usa `getpass` y nunca acepta la contraseña como argumento.
11. El flujo se probó en navegador: registro, cambio persistido, rechazo de la contraseña antigua, login con la nueva, cero excepciones y limpieza de la cuenta temporal en JSON/SQLite.
12. El watchdog podía capturar la ventana entre una nueva confluencia y el brief producido al final del mismo ciclo, registrar `ai_brief WARN` y volver a alimentar el SLO con un fallo ya resuelto. Ahora realiza una lectura final de consistencia cuando el brief parece atrasado y sólo reemplaza el diagnóstico si el estado realmente mejora. Un atraso persistente continúa en `WARN`. La prueba runtime cerró con lag `0.0`, brief `OK` y diez ciclos de núcleo sano.

Evidencia:

- `output/playwright/auth_security_hardened.png`
- `alerts/dashboard_source_contract_probe.json`
- `output/playwright/dashboard_source_contract.png`
- `alerts/password_change_e2e_probe.json`
- pruebas `tests/test_auth_guard.py`
- pruebas `tests/test_auth_session_security.py`
- pruebas `tests/test_reset_local_password.py`
- pruebas de SLO y mantenimiento en `tests/test_roxy_realtime_check.py`

Validación enfocada posterior: **73 pruebas aprobadas**, cero fallos. La regresión completa de ese corte aprobó **2.222 pruebas**; la regresión integral posterior descrita en la sección 25 elevó el total a 2.228.

## 25. Diagnóstico de autenticación y migración completa de sesiones heredadas

1. `system_diagnostics.py` incorpora una comprobación de seguridad de autenticación de solo lectura. Verifica la política PBKDF2, la vida máxima de sesión, permisos de JSON/SQLite, existencia del limitador persistente, hashes heredados débiles y tokens de sesión en texto claro. El resultado sólo contiene conteos y estados; nunca devuelve usernames, correos, hashes o secretos.
2. La comprobación encontró cuatro sesiones heredadas guardadas en texto claro en `data/roxy_users.json`, `profile_json` y la columna legacy de SQLite. La carga de usuarios ahora migra todos esos valores a SHA-256 de forma inmediata, no sólo cuando un usuario restaura manualmente una sesión.
3. La migración conserva la sesión válida porque el navegador sigue presentando el token original y el servidor compara únicamente su hash. Los valores legacy vacíos o inválidos se eliminan sin crear una sesión.
4. Se corrigió la persistencia SQLite que convertía un valor ausente en el marcador visual `—`. La columna legacy se escribe ahora como cadena vacía y el limitador persistente se inicializa junto con el esquema de autenticación, antes del primer intento de login.
5. El almacenamiento runtime terminó con permisos `0600`, cuatro sesiones representadas únicamente por hash y cero tokens en texto claro tanto en JSON como en SQLite. El diagnóstico devuelve `CONNECTED`, `throttle=activo` y `tokens plaintext 0`.
6. Una sesión nueva de Chromium registró una cuenta temporal, abrió `?view=Diagnostico`, confirmó visualmente el estado de seguridad, la limpieza del parámetro transitorio de sesión y cero excepciones de Streamlit. La cuenta, memoria y estado UI de QA se eliminaron después de la prueba.
7. La política de password, sesión y bloqueo vive ahora en `roxy_trader/auth_guard.py`; login y diagnóstico importan el mismo contrato. El ciclo vivo posterior cerró con `ai_brief=OK`, gráficas `OK` y diez ciclos consecutivos de núcleo sano: **Core operativo / externo bloqueado**. Alpaca `AUTH_INVALID` y los medios de aprendizaje no archivados permanecen visibles como avisos externos/auxiliares.

Evidencia:

- `output/playwright/auth_diagnostic_connected.png`
- pruebas `tests/test_system_diagnostics.py`

- pruebas `tests/test_auth_session_security.py`
- diagnóstico runtime `authentication_security_check('.') = CONNECTED`

Regresión completa final, repetida después de centralizar la política de acceso: **2.228 pruebas aprobadas**, 2 advertencias conocidas de dependencias (`urllib3`/LibreSSL y `websockets.legacy`), cero fallos y código de salida 0 en 144,98 segundos. La compilación recursiva y `git diff --check` también terminaron limpios.

## 26. Eliminación de fórmulas técnicas divergentes

1. El inventario exhaustivo de `.ewm()` y medias/desviaciones móviles fuera del motor central identificó cinco consumidores restantes: `dashboard.py`, `roxy_alpaca_bot.py`, `tools/features.py`, `tools/modeling.py` y dos rutas activas de `streamlit_app.py`.
2. El dashboard heredado y el bot Alpaca dejaron de usar RSI/ATR por media simple. Ambos delegan EMA, RSI Wilder, ATR Wilder y VWAP por sesión al contrato central. Esto impide que una misma vela tenga lecturas distintas según la pantalla o el ejecutor.
3. El feature store conserva sus nombres compatibles (`sma_10`, `ema_10`, `rsi_14`, `atr_14`), pero sus valores provienen del motor 1.1.0 y llevan metadata de versión. El modelado usa las mismas SMA y eliminó el `bfill` que introducía información futura durante el warmup.
4. El payload de gráficas, la validación histórica cripto, la señal de horizonte cripto y la semilla de oportunidades desplegada usan las mismas EMA, Bollinger, SMA y volumen promedio que el resto de Roxy. Bollinger queda unificado con desviación poblacional `ddof=0`.
5. Los cálculos de soporte/resistencia, mediana estructural y volatilidad estadística de retornos permanecen locales porque no representan una fórmula técnica duplicada. El barrido termina con cero `.ewm()` fuera de `roxy_trader/indicators.py`.
6. Una prueba estructural falla si cualquiera de las rutas operativas reintroduce EMA/RSI/ATR/Bollinger local. Las pruebas numéricas comparan el feature store con el motor central para SMA, EMA, RSI y ATR.
7. El watchdog posterior confirmó 1.000 velas reales de LINK/USD 1h, RSI/MACD presentes, cuatro contratos de gráfica operables, `ai_brief=OK` y cero fallos de indicadores. Después de diez ciclos sanos consecutivos, el SLO volvió a **Core operativo / externo bloqueado**. Alpaca sigue bloqueado externamente y no altera este resultado.

Evidencia:

- `roxy_trader/indicators.py` (`roxy-indicators/1.1.0`)
- pruebas `tests/test_indicator_engine.py`
- validación enfocada: **390 pruebas aprobadas**
- watchdog `chart_indicators=OK` y `chart_realtime_health_report=OK`

Regresión completa: **2.231 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 123,61 segundos.

## 27. Política central de caché y coalescencia de proveedores

1. Se creó `roxy_trader/cache_policy.py` con contrato `roxy-cache/1.0.0`. Define 21 clases para cotizaciones, planes derivados, velas cripto, oportunidades, webhooks, contratos, gráficas, voz, screeners, memoria, noticias, perfiles e identidad.
2. Cada clase declara TTL por defecto, mínimo, máximo, tolerancia de stale y comportamiento de fallo. Los overrides `ROXY_CACHE_TTL_*` se aceptan sólo como enteros y se recortan a límites seguros; un nombre desconocido falla cerrado.
3. Los 30 decoradores `st.cache_data` activos de `streamlit_app.py` y `dashboard.py` dejaron de contener TTL numéricos privados. Noticias e identidad en disco consumen el mismo contrato; Finviz también comparte su TTL con el cliente externo subyacente.
4. Noticias publica ahora `cache_freshness` y diferencia `FRESH`, `STALE` y `EXPIRED`. Un snapshot vencido puede conservarse como respaldo, pero siempre se presenta como `DELAYED`; nunca vuelve a parecer recién obtenido.
5. La cabecera de mercado y el refresco bursátil comparten `cached_stock_provider_snapshot`. Una prueba con proveedor instrumentado confirmó una sola llamada para ambos consumidores dentro del TTL. Dos rutas cripto que pedían OHLCV directamente reutilizan ahora `roxy_crypto_history_for_signal`.
6. Diagnóstico muestra `Politica de cache`, versión, número de clases, overrides y rangos efectivos. Chromium confirmó `CONNECTED`, 21 clases, cero overrides, TTL de quotes 1–5 s, identidad 86.400–1.209.600 s, URL limpia y cero excepciones de Streamlit.
7. Una guarda AST impide introducir nuevos decoradores cacheados sin TTL explícito o con literales numéricos no clasificados. Pruebas adicionales cubren límites, overrides inválidos, estados de edad y coalescencia real.

Evidencia:

- `roxy_trader/cache_policy.py`
- `output/playwright/cache_policy_diagnostic.png`
- pruebas `tests/test_cache_policy.py`
- pruebas `tests/test_system_diagnostics.py`
- validación enfocada: **450 pruebas aprobadas**

Regresión completa: **2.241 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 126,13 segundos.

## 28. Separación entre disponibilidad del núcleo y almacenamiento auxiliar

1. El SLO distinguía correctamente proveedores premium y biblioteca de aprendizaje, pero todavía trataba un disco externo montado con permiso de escritura denegado como fallo del núcleo de trading. Esto impedía recuperar el estado operativo aunque datos, gráficas, alertas, voz y backend estuvieran sanos.
2. La telemetría publica ahora `external_disk_writable`, `external_disk_permission_required` y `external_disk_operational_write_verified`. El aviso permanece visible en el diagnóstico global.
3. Sólo la combinación estricta `mounted=True`, `permission_required=True` y `writable=False` queda fuera del núcleo. Un volumen ausente conserva `FAIL`; falta de espacio u otros avisos continúan degradando el SLO.
4. La rama `skipped_not_due` del mantenimiento histórico quedó protegida con una aserción contractual para acción, resultado, presupuesto, mínimos efectivos y conteos de eliminación. El reporte vivo cerró con 1.370 alias y `report_metrics_contract=OK`.
5. Ocho ciclos adicionales después de la corrección completaron la ventana de recuperación: **Core operativo / externo bloqueado**, racha `OK x10`. El estado se mantiene en `INFO` porque Alpaca paper continúa en `AUTH_INVALID`; no se presenta stock/opciones como operable.

Validación:

- módulo completo del watchdog: **623 pruebas aprobadas**;
- regresión integral: **2.243 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 124,62 segundos;
- historial runtime: 120 entradas, aproximadamente 76,2% del presupuesto y mantenimiento post-append `OK`.

## 29. Base de presupuestos y telemetría de APIs

1. El inventario de consumo encontró protecciones aisladas —limitador interno de CCXT y clasificación de HTTP 429 en algunas rutas—, pero no un registro transversal de solicitudes, latencia o margen por proveedor.
2. Se creó `roxy_trader/api_budget.py` con contrato `roxy-api-budget/1.0.0` para Alpaca, Polygon, Finnhub, Finviz, yfinance, Binance, BinanceUS, Crypto.com, CoinGecko, RSS, ElevenLabs, Tradier, Nasdaq y Stooq.
3. Estos valores son presupuestos operativos conservadores de Roxy y se etiquetan como tales. No sustituyen ni pretenden representar el límite contractual del plan del usuario. Los overrides por entorno están acotados y un proveedor desconocido falla cerrado.
4. `ApiUsageLedger` ofrece telemetría SQLite multiproceso por ventana: solicitudes, errores, latencia media, HTTP 429, utilización y margen. El esquema excluye deliberadamente URL, cabeceras, payloads y secretos.
5. El panel técnico incorpora `Uso y limites de APIs`. Mientras ninguna ruta activa haya emitido eventos muestra `NO_DATA`; no convierte la mera existencia de una política en telemetría simulada.
6. La instrumentación activa cubre ticker/OHLCV y escáneres Binance/BinanceUS, latest trade/quote/bar/bars de Alpaca, puente REST de streaming, descargas yfinance, Stooq, Polygon, perfil Finnhub, identidad CoinGecko, Finviz, Crypto.com, Nasdaq, RSS, Tradier y sesiones ElevenLabs. El observador conserva exactamente las excepciones originales y nunca permite que una falla del ledger interrumpa el proveedor.
7. La prueba runtime inicial obtuvo BTC/USD ticker, diez velas 1h e identidad CoinGecko. Una segunda prueba obtuvo tres noticias, 17 registros IPO Nasdaq y ticker BTC/USDT real de Crypto.com.
8. Esa segunda prueba detectó un 404 real en `public/get-ticker`. La documentación oficial vigente publica `public/get-tickers` y transporte GET; el cliente se corrigió y quedó probado contra respuesta real. Referencia: [Crypto.com Exchange API v1](https://exchange-docs.crypto.com/exchange/v1/rest-ws/index.html).
9. ElevenLabs respondió HTTP 401 pese a tener variables presentes. El diagnóstico ya no confunde configuración con autenticación: muestra `WARNING`, `elevenlabs ERROR` y conteos de ventana/24h, sin exponer credenciales. Finviz y Polygon continúan `NOT_CONFIGURED`.
10. El ledger conserva treinta días, publica ventana actual y últimas 24 horas, vuelve a `NO_DATA` si no hay eventos recientes y muestra overrides inválidos/recortados sólo por nombre de variable. El archivo queda `0600`.
11. Chromium confirmó el check servido después de reiniciar únicamente el LaunchAgent desactualizado: 14 proveedores, actividad real por proveedor, incidente ElevenLabs, URL limpia y cero errores de consola. La oferta Passkey desapareció al pulsar “Ahora no”.
12. La cuenta temporal y sus tres memorias fueron eliminadas; las cuatro tablas relacionadas terminaron con cero filas. El watchdog posterior cerró `Core operativo / externo bloqueado`, racha `OK x16`, gráficas y contrato de métricas `OK`.
13. La protección automática quedó calibrada en tres modos. `protect` es el valor predeterminado: mantiene el tráfico normal fail-open, pero después de un HTTP 429 real bloquea temporalmente nuevas llamadas a ese proveedor durante 60 segundos. `observe` conserva sólo la telemetría; `enforce` añade bloqueo al agotar el presupuesto operativo configurado.
14. Los intentos bloqueados se almacenan en una tabla separada para no contarlos falsamente como solicitudes salientes. Las rutas de ElevenLabs y del puente bursátil capturan el cooldown y degradan de forma explícita en vez de derribar su sesión o proceso.
15. Una rotación concurrente del foco operativo cambió la sonda de Dashboard de `LINK/USD` a `ETH/USD`. La autorrecuperación regeneró las rutas primaria y de búsqueda, ambas conservaron símbolo/mercado/temporalidad y cero errores de interfaz; diez ciclos posteriores recuperaron el SLO a racha de núcleo `OK x10` sin ocultar Alpaca `AUTH_INVALID` ni ElevenLabs 401.

Evidencia:

- `output/playwright/api_budget_diagnostic.png`
- `output/playwright/api_budget_provider_incident.png`
- `data/roxy_api_usage.sqlite` (telemetría local, modo `0600`)
- pruebas `tests/test_api_budget.py`
- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_auth_session_security.py`

Validación final: pruebas enfocadas de presupuesto, diagnóstico y rutas instrumentadas aprobadas; regresión integral de **2.264 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 138,03 segundos. Compilación recursiva, `git diff --check`, sondas reales y recuperación SLO completan la verificación.

## 30. Retiro de tarjetas de estrategias sin datos

1. La auditoría posterior encontró tres estados vacíos que todavía llenaban la pantalla con familias de ejemplo (`Wedge`, `Triangle`, `Channel`, reversals y EMA), puntuación cero y ranuras de entrada/stop/target. Aunque sus textos decían “pendiente”, visualmente seguían pareciendo detecciones.
2. `render_finviz_pattern_strategy_board` deja ahora el panel vacío y explica que Finviz no entregó candidatos; no crea un símbolo `FINVIZ` ni patrones de referencia.
3. `render_roxy_strategy_split_board` muestra una sola condición `Sin datos reales / 0 detecciones`, sin inventar familias, tickers, puntuaciones o niveles.
4. La ruta activa del terminal de Acciones también sustituyó su tarjeta grande con cuatro campos vacíos por un estado compacto `Finviz sin candidatos reales`, enlazado a Integraciones y Escáner.
5. Una guarda estructural revisa los tres renderizadores y falla si vuelven `reference_strategies`, `fallback_families`, el símbolo sintético `FINVIZ` o la tarjeta `strategy-empty`.
6. Chromium validó la ruta `acciones-operar/estrategias` con AAPL: símbolo, mercado y timeframe persistentes, textos operativos presentes, contenido prohibido ausente y cero errores de consola o página.

Evidencia:

- `output/playwright/strategy_empty_state.png`
- `alerts/strategy_empty_state_probe.json`
- pruebas `tests/test_strategy_separation.py`

Regresión integral de ese corte: **2.264 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 138,03 segundos.

## 31. Eliminación del universo estático en rutas directas

1. `main()` creaba ocho acciones o cinco criptomonedas como filas `Universe seed` cada vez que se abría una ruta directa. `roxy_asset_rows_for_market` volvía además a completar símbolos hasta el límite aunque la URL solicitara uno solo.
2. El helper fue sustituido por `roxy_selected_asset_row`: registra exclusivamente el símbolo visible, con provenance `User selection`, cotización nula y gate `NO_DATA` hasta que el proveedor entregue datos verificables.
3. El selector de mercado conserva y ordena filas reales recibidas, pero ya no agrega prioridades ausentes. La superficie cripto de 20 minutos tampoco reconstruye por sí sola una cesta BTC/ETH/SOL/XRP/BNB.
4. Una guarda AST impide reintroducir `roxy_fallback_asset_rows`, `Universe seed`, la lista `wanted` de cripto o inicializaciones distintas al activo visible.
5. Chromium aprobó Acciones/AAPL y Cripto/ETH en escritorio, Acciones/AAPL en teléfono 390×844 y Cripto/ETH en iPad 820×1180. Las cuatro pruebas conservaron URL, símbolo, mercado y timeframe, sin texto de catálogo estático, errores de consola, errores de página ni overflow horizontal de documento.
6. En teléfono la barra completa de dibujo permanece desplazable dentro del iframe con controles táctiles de 28 px; el canvas y la escala de precio usan todo el ancho disponible. No se redujeron botones hasta volverlos ilegibles.

Evidencia:

- `output/playwright/direct_stock_selection.png`
- `output/playwright/direct_crypto_selection.png`
- `output/playwright/direct_stock_selection_mobile.png`
- `output/playwright/direct_crypto_selection_ipad.png`
- pruebas `tests/test_strategy_separation.py`
- pruebas `tests/test_dashboard_probe_auth.py`

Regresión integral de ese corte: **2.265 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 133,48 segundos.

## 32. Cierre fail-closed del API de secretos

1. Una solicitud real al backend vivo demostró que `/api/auth/mock-login` emitía sin autenticación un token de siete días para cualquier username. La sonda temporal creó una sesión y se eliminó inmediatamente después de confirmar el defecto; el conteo lógico quedó en cero.
2. El endpoint devuelve ahora `404` por defecto. Sólo puede emitir una sesión de un día cuando coinciden `ROXY_ENABLE_MOCK_LOGIN=1`, un `ROXY_ENV` de desarrollo/test y un cliente loopback; el username se limita a 64 caracteres seguros.
3. El modo admin anterior aceptaba todas las llamadas si no existían `ADMIN_TOKEN`, `ADMIN_USERS` o `ADMIN_ORGS`. Ahora falla con `403`; el bypass opcional requiere simultáneamente `ROXY_ALLOW_INSECURE_DEV_ADMIN=1`, desarrollo/test y loopback.
4. Listar nombres de secretos, consultar metadata o revisions también exige admin. Reveal, create, rotate y API keys ya usaban el dependency y permanecen protegidos. La comparación del token admin usa tiempo constante.
5. `Seguridad API de secretos` se añadió al diagnóstico rápido y profundo. Muestra runtime, mock habilitado/deshabilitado, postura admin y número/nombre de flags de bypass, nunca sus valores. Una flag de desarrollo en producción es `ERROR`; en desarrollo es `WARNING`; sin bypass es `CONNECTED`.
6. El backend reiniciado respondió `health=200`, `mock_login=404`, `secrets_list=403` y no creó sesiones para el intento bloqueado. Chromium confirmó el check `CONNECTED`, estado/URL persistentes, cero errores y ausencia de tokens de prueba.

Evidencia:

- `output/playwright/secrets_api_security_diagnostic.png`
- `alerts/secrets_api_security_probe.json`
- pruebas `tests/test_secrets_api_security.py`
- pruebas `tests/test_secrets_service.py`
- pruebas `tests/test_system_diagnostics.py`

Regresión integral de ese corte: **2.270 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 131,60 segundos.

## 33. Frontera autenticada para voz, AI y automatización

1. El backend compartido no tenía `VOICE_API_KEY` configurada. Voz, perfiles y el inventario de fuentes de conocimiento aceptaban cualquier cliente; `/api/ai/signal` además permitía generar señales, consumir proveedor LLM y escribir auditoría sin autenticación.
2. La voz conserva operación local: sin clave acepta exclusivamente hosts loopback (`127.0.0.1`, `::1`, `localhost`) y devuelve HTTP 503 a clientes remotos. Con clave exige Bearer y comparación en tiempo constante.
3. `/api/ai/signal` usa ahora el autenticador central. Admin puede ejecutarlo; una API key gestionada necesita scope `ai:signal`. El endpoint anónimo vivo cambió de HTTP 200 a 401.
4. A/B ya exigía autenticación; se verificó junto con AI. `auto_api` dejó de ser fail-open cuando fallaba importar el autenticador y ahora rechaza con 503 en ese caso. API keys de A/B y auto mantienen scopes `ab:execute` y `auto:execute`.
5. El backend reiniciado respondió `ai_no_auth=401`, `auto_no_auth=401`, `ab_no_auth=401`, `profile_loopback=200` y `health=200`. Una prueba unitaria construyó un cliente remoto y confirmó 503 sin realizar tráfico externo.
6. `Seguridad API de voz` aparece en diagnóstico: `CONNECTED` con clave; `WARNING` sin clave, explicando que sólo loopback opera y remoto recibe 503. Chromium confirmó ambas filas de seguridad, URL/estado persistentes, cero errores y ninguna clave en pantalla.

Evidencia:

- `output/playwright/voice_api_security_diagnostic.png`
- `alerts/voice_api_security_probe.json`
- pruebas `tests/test_llm_agent.py`
- pruebas `tests/test_voice_service.py`

- pruebas `tests/test_secrets_api_security.py`

Regresión integral de ese corte: **2.273 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 129,79 segundos.

## 34. Cifrado del resultado OAuth de un solo uso

1. `oauth_results` almacenaba temporalmente el token de sesión Roxy en una columna plaintext entre el callback de GitHub y la consulta firmada del navegador. El runtime no contenía filas actuales, pero el contrato permitía escribirlas.
2. El esquema incorpora `encrypted_session_token`. El callback cifra con Fernet, escribe vacía la columna heredada y nunca persiste el token Roxy en claro.
3. `auth_check_state` verifica la firma como antes, descifra una sola vez, elimina la fila y devuelve el mismo token creado por la sesión. Un resultado sin ciphertext ni legado válido falla explícitamente.
4. `ensure_tables` migra filas heredadas sólo cuando existe una clave Fernet válida; en ausencia de filas no fuerza configuración ni genera un falso warning. El diagnóstico de autenticación cuenta cualquier legado plaintext como error agregado.
5. La prueba de integración crea estado OAuth, simula proveedor, verifica ciphertext/no plaintext, consume el resultado firmado, compara el token y confirma eliminación de la fila.
6. Tras reiniciar el backend, el DB vivo tiene la columna cifrada, cero filas, cero plaintext y salud HTTP 200. `Seguridad de autenticacion` permanece `CONNECTED`, `tokens plaintext 0`.

Evidencia:

- pruebas `tests/test_secrets_oauth_callback.py`
- pruebas `tests/test_system_diagnostics.py`
- runtime `oauth_results`: columna cifrada presente, filas 0, plaintext 0

Regresión integral: **2.274 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 128,47 segundos.

## 35. Contrato único entre activo, watchlist, alertas, gráficas y voz

1. La ruta canónica `trading.charts` aceptaba `market=crypto`, pero `main()` construía siempre una fila `stock`. Una criptomoneda abierta desde watchlist conservaba ETH/BTC en el URL mientras el workspace filtraba internamente acciones y podía dejar la pantalla sin gráfica.
2. El workspace dual resuelve ahora el mercado desde el URL/contexto visible, crea la fila seleccionada con ese mismo mercado y filtra el conjunto con el contrato correcto. El runtime bursátil sólo se inicia para acciones; todas las alternativas de gráfica reciben `selected_market`.
3. ETH/USD fue validado en la ruta unificada con las dos gráficas 15m + 1h. Escritorio 1440×1100 y teléfono 390×844 conservaron símbolo, mercado y timeframe, sin AAPL residual, errores de consola, errores de página ni overflow horizontal.
4. Crear una alerta ya agregaba el activo a una lista durable, pero el snapshot de sesión consumido por voz podía permanecer obsoleto. `sync_roxy_watchlist_session` actualiza ahora lista seleccionada y símbolos después de mutaciones por UI, voz o alerta.
5. `Roxy Oportunidades` es un conjunto derivado del último scan saludable. El almacenamiento rechaza ahora `add_asset` y `remove_asset` manuales cuando una lista tiene `system_managed=true`; ni voz ni llamadas directas pueden corromperla. Si una alerta se crea mientras esa lista está visible, se vincula de forma explícita a `Principal`.
6. La primera sonda de navegador encontró un `NameError` por dependencia no importada. Se corrigió el import compartido y la prueba de integración obliga a resolver el normalizador en ejecución, además de las guardas estructurales de ruta.

Evidencia:

- `output/playwright/crypto_dual_chart_context.png`
- `output/playwright/crypto_dual_chart_context_mobile.png`
- `alerts/crypto_dual_chart_context_probe.json`
- `alerts/crypto_dual_chart_context_mobile_probe.json`
- pruebas `tests/test_canonical_routes.py`
- pruebas `tests/test_watchlists.py`

Regresión integral: **2.277 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 130,51 segundos. Compilación Python y `git diff --check` también terminaron limpios.

## 36. Monitor durable de alertas fuera de pantalla

1. La auditoría de extremo a extremo comprobó que `evaluate_price_alerts` sólo era llamado desde la pantalla visible. El texto “los demás permanecen a cargo del monitor operativo” no correspondía a ningún productor background.
2. Se creó el contrato `roxy-price-alert-monitor/1.0.0`. El monitor agrupa reglas activas de todos los usuarios, deduplica cada par mercado/símbolo, obtiene una sola cotización por ciclo y evalúa únicamente reglas con precio positivo, fuente declarada y freshness válida.
3. Cripto exige `EXCHANGE_TICKER`, proveedor identificado y edad máxima de 120 segundos. Acciones exige `BROKER_DATA`, proveedor Alpaca, mercado abierto y la misma vigencia; yfinance no puede disparar una regla y queda registrado como `PROVEEDOR_PREMIUM_BLOQUEADO`.
4. Las reglas bloqueadas conservan `Activa` y guardan `monitor_status`, razón, fuente, freshness y hora. Las evaluables guardan `EVALUADA`; una transición nueva guarda `ACTIVADA`, notifica una sola vez y no vuelve a entrar al inventario activo.
5. `com.roxy.price-alert-monitor` ejecuta `tools/price_alert_monitor.py` cada 60 segundos. El servicio fue incorporado al auto-recovery de LaunchAgents; el watchdog valida instalación, intervalo, comando, antigüedad del reporte y contrato.
6. El proceso vivo completó múltiples ciclos con código 0. El corte observado tenía una regla cripto activa, una evaluación, cero bloqueos y cero transiciones. El reporte se escribe atómicamente con modo `0600`.
7. La pantalla Alertas muestra estado y detalle del monitor. La pantalla Diagnóstico muestra `Monitor de alertas CONNECTED`, contrato, antigüedad y conteos. La evaluación inmediata del activo visible usa el mismo gate, por lo que no existe un bypass mediante la UI.
8. Playwright confirmó las dos pantallas con URL/estado persistentes, cero errores de consola/página y overflow horizontal cero. Una primera sonda de Diagnóstico detectó que Streamlit retenía el módulo importado anterior; se reinició sólo el servicio canónico y la repetición quedó aprobada.
9. El watchdog final muestra `price_alert_monitor OK`, `price_alert_monitor_service OK`, 15 plists válidos, `report_metrics_contract OK` y núcleo `OK x25`. El estado global sigue `WARN` por Alpaca `AUTH_INVALID` y otras dependencias externas declaradas.

Evidencia:

- `alerts/price_alert_monitor.json`
- `alerts/background_alert_monitor_ui_probe.json`
- `alerts/background_alert_monitor_diagnostic_probe.json`
- `output/playwright/background_alert_monitor_ui.png`
- `output/playwright/background_alert_monitor_diagnostic.png`
- pruebas `tests/test_alert_monitor.py`
- pruebas `tests/test_watchlists.py`
- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_launchd_recovery.py`
- pruebas `tests/test_roxy_realtime_check.py`

Regresión integral: **2.287 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 129,41 segundos. Compilación recursiva, lint de plist y `git diff --check` terminaron limpios.

## 37. Sincronización autónoma de oportunidades con watchlist y voz

1. La auditoría encontró que `sync_roxy_operational_watchlist` sólo se ejecutaba al renderizar el centro de mando. El productor `ma_live` podía detectar y clasificar el mercado durante todo el día, pero la lista durable no cambiaba hasta que alguien abría esa pantalla.
2. Se creó `roxy-opportunity-sync/1.0.0` y se conectó al final de `tools/roxy_ai_watch.py`, que ya forma parte del ciclo autónomo `ma_live`. El reporte atómico `alerts/opportunity_sync.json` registra antigüedad, salud de fuente, candidatas, entradas confirmadas y resultado por usuario.
3. La promoción exige simultáneamente artefactos actuales de scan/confluencia, freshness `FRESH`, mercado permitido por el diagnóstico realtime, gráfica operable y gate `LIVE_PRICE_OK`, `LIVE_DATA_OK` o `ANALYSIS_OK`. El contrato agrega fuente explícita; cripto del productor actual queda identificado como BinanceUS API.
4. La lista `Roxy Oportunidades` sigue siendo administrada e inmutable manualmente. Sólo recibe filas listas para entrada; una candidata `WATCH` no se convierte en recomendación. En el ciclo vivo observado hubo dos o tres candidatas cripto según el scan, pero cero entradas confirmadas, por lo que la lista permaneció honestamente vacía.
5. Un scan degradado no prueba que una señal haya expirado y conserva la última lista. Un scan saludable que deja de confirmar una entrada sí la retira y la archiva como `Expirada`, con hora y razón.
6. El usuario local se incluye siempre en la sincronización, junto con usuarios que ya tengan estado durable. La voz usa la lista autónoma como fallback cuando ninguna página ha cargado una tabla en la sesión, conservando símbolo, entrada, stop, objetivo, confianza y razón.
7. Watchlists muestra `Sincronizacion autonoma`, conteo de candidatas y entradas confirmadas. Diagnóstico y watchdog validan contrato, vigencia y salud. Playwright aprobó ambas superficies con URL/estado persistentes y cero errores bloqueantes.
8. El watchdog completo cerró con `opportunity_sync OK`, contrato de métricas `OK` y núcleo sostenido `OK x10`; el estado global permanece degradado exclusivamente por dependencias externas declaradas como Alpaca `AUTH_INVALID`.

Evidencia:

- `alerts/opportunity_sync.json`
- `alerts/opportunity_sync_diagnostic_probe.json`
- `alerts/opportunity_sync_watchlist_probe.json`
- `output/playwright/opportunity_sync_diagnostic.png`
- `output/playwright/opportunity_sync_watchlist.png`
- pruebas `tests/test_opportunity_sync.py`
- pruebas `tests/test_watchlists.py`
- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_roxy_realtime_check.py`

Regresión integral: **2.295 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 130,35 segundos. `streamlit_app.py` tiene 58.394 líneas; la deuda de separación del frontend continúa explícita.

## 38. Contrato único de oportunidades para voz local, ElevenLabs y backend

1. La voz local ya podía consultar la lista autónoma, pero `render_roxy_elevenlabs_assistant` enviaba únicamente el snapshot de sesión. Sin abrir una pantalla de oportunidades, ElevenLabs recibía un contexto vacío aunque existiera una lista administrada.
2. `roxy_resolved_voice_opportunity_snapshot` centraliza la resolución: usa primero la tabla visible y, si está vacía, la lista durable `Roxy Oportunidades`. El mismo objeto alimenta respuesta local, metadata de Roxy OS, variables dinámicas, client tools y payload de ElevenLabs.
3. La prueba runtime encontró que el parser trataba `LINK` como palabra genérica incluso dentro de `LINK/USD`; una solicitud relativa terminaba explicando LTC/USD, el primer activo del plan. Los parsers de ambos cerebros aceptan ahora pares explícitos con cotizaciones USD, USDT, USDC, BTC, ETH o EUR, sin abrir la puerta a tokens de URL arbitrarios.
4. El cerebro interactivo priorizaba el plan diario, pero ese plan había descartado fuente, gate y temporalidad. `_opportunity_rows` fusiona ahora la etapa/readiness del plan con el contrato original del brief por símbolo, conservando una sola versión completa de cada oportunidad.
5. El productor normaliza cada oportunidad antes de guardar el brief: `data_bucket`, `data_state`, `data_gate` y `data_source` quedan disponibles para todas las superficies, no sólo calculados dentro de Streamlit. Valores `NaN` de target se reemplazan por el objetivo exacto de 2% cuando el setup no es `AVOID`.
6. Si se solicita un símbolo ausente, los dos helpers fallan cerrados y explican que no existe oportunidad actual. Ya no devuelven el primer activo de la lista. Los precios hablados usan precisión adaptativa para cripto y muestran objetivo absoluto cuando existe.
7. El endpoint vivo `/v1/assist/state` respondió HTTP 200 para LINK/USD con `active_symbol=LINK/USD`, mercado `crypto`, temporalidad `15m`, entrada 8.3890, stop 8.2059, objetivo 8.5568, fuente BinanceUS API, `LIVE_DATA_OK` y `WAIT_VOLUME`. AAPL ausente devolvió espera/scan sin mencionar ETH o LTC.
8. Playwright conservó LINK/USD, cripto y 15m después de recargar frontend y backend, con cero errores bloqueantes. ElevenLabs externo continúa mostrando su HTTP 401 real; el fallback local permanece operativo y no se presenta el proveedor externo como conectado.

Evidencia:

- `alerts/voice_shared_context_probe.json`
- `output/playwright/voice_shared_context.png`
- pruebas `tests/test_voice_assistant.py`
- pruebas `tests/test_roxy_interactive_brain.py`
- pruebas `tests/test_elevenlabs_roxy.py`


- pruebas `tests/test_voice_service.py`
- pruebas `tests/test_watchlists.py`

Regresión integral: **2.301 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 127,77 segundos. `streamlit_app.py` tiene 58.398 líneas.

## 39. Contrato permanente para botones y enlaces de interfaz

1. El inventario AST revisó 63 llamadas a botón y cuatro enlaces de componente en `streamlit_app.py`. Las dos llamadas que inicialmente parecían ignorar el clic (`Limpiar filtros`) usan callbacks declarados; el botón de sincronización automática está explícitamente deshabilitado y los enlaces restantes reciben destino real.
2. No se encontraron botones renderizados como expresión sin callback, condición o estado deshabilitado. Tampoco existen `href="#"` ni enlaces `javascript:` en el frontend activo.
3. Se añadió `ui_control_contract_check` al diagnóstico rápido y profundo. El check falla visiblemente si una futura edición introduce un botón huérfano o un placeholder de enlace, e informa líneas concretas para repararlo.
4. El análisis AST se almacena en caché usando ruta, `mtime_ns` y tamaño del archivo. El primer cálculo tarda aproximadamente 1,6 s sobre 58 mil líneas; las siguientes consultas en el mismo proceso son inmediatas y cualquier cambio de archivo invalida el resultado.
5. La primera sonda de navegador capturó correctamente la cabecera mientras el diagnóstico frío seguía calculando, sin errores de consola o página. La repetición con la ventana completa mostró `Controles de interfaz CONNECTED`, 63 botones, cero acciones huérfanas y URL/estado persistentes.

Evidencia:

- `alerts/ui_control_contract_probe.json`
- `output/playwright/ui_control_contract.png`
- pruebas `tests/test_system_diagnostics.py`

Regresión integral: **2.303 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 131,90 segundos.

## 40. Integridad canónica de rutas y mapa operativo

1. La auditoría de enlaces internos encontró dos destinos visibles sin contrato propio: `tab=mapa` y `tab=noticias`. El normalizador aceptaba ambos como variantes del resumen, pero el renderer terminaba marcando `escaner`; la URL cambiaba sin abrir la superficie prometida.
2. `market.stocks_map` forma ahora parte de `ROXY_ROUTE_REGISTRY`, aparece en las pestañas canónicas de Acciones y conserva símbolo, mercado y temporalidad. La ruta renderiza una superficie dedicada y responsive; cada activo abre las gráficas sincronizadas.
3. El mapa no rellena el espacio con activos inventados. Muestra únicamente las filas recibidas y declara fuente, estado y última actualización. Si el contexto visible está esperando una cotización verificada, ese estado aparece literalmente y no se presenta como streaming.
4. Los titulares sin URL y el CTA `Ver Más Noticias` abren `market.news`. Ya no existe ningún enlace literal a la pestaña oculta `noticias`.
5. Se creó `navigation_route_contract_check`, independiente de Streamlit y almacenado en caché por metadatos del archivo. El diagnóstico revisa parámetros internos literales `view`, `module` y `tab`; cualquier valor fuera del contrato queda `WARNING` con el destino exacto.
6. La aplicación real contiene 140 parámetros internos auditados: cero vistas, módulos o pestañas inválidas. Playwright abrió directamente `tab=mapa`, confirmó URL/estado persistentes, texto de fuente/estado/hora y cero errores bloqueantes. La primera inspección visual descubrió estilos acoplados al terminal general; se aislaron los estilos del mapa y la segunda captura confirmó jerarquía, pestaña activa, tarjeta de activo y adaptación compacta.

Evidencia:

- `alerts/navigation_map_probe.json`
- `output/playwright/navigation_map.png`
- pruebas `tests/test_canonical_routes.py`
- pruebas `tests/test_system_diagnostics.py`

Regresión integral: **2.306 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 133,08 segundos. Compilación dirigida y `git diff --check` terminaron limpios.

## 41. Base segura para sincronización entre dispositivos

1. La auditoría confirmó que `roxy_watchlists.json` y `dashboard_ui_state.json` estaban aislados por usuario, bloqueados y escritos atómicamente, pero no tenían revisión por usuario. Dos instalaciones podían aplicar “última escritura gana” sin detectar pérdida de cambios.
2. Watchlists/alertas migraron al esquema 2 y estado UI al esquema 3. Ambos exponen una revisión monotónica por usuario y aceptan reemplazo condicional. Una revisión vencida conserva el estado más nuevo y devuelve conflicto.
3. `roxy-device-sync/1.1.0` unifica snapshots de watchlists, alertas, navegación, tareas y compras. El backend canónico ofrece `GET /v1/state-sync/{user_id}` y `PUT /v1/state-sync/{user_id}`; una colisión se representa como HTTP 409, no como éxito aparente.
4. La ruta usa la misma autenticación Bearer en tiempo constante que la API de voz. Además exige `ROXY_STATE_SYNC_USERS`; el valor por defecto permite únicamente `local_user`, por lo que conocer un token no permite escoger arbitrariamente otro namespace de usuario.
5. Las actualizaciones autónomas de `Roxy Oportunidades` y la telemetría periódica de alertas no avanzan la revisión de edición manual. Las listas administradas y su archivo son de solo lectura en el protocolo remoto, de modo que un cliente no puede borrar o reemplazar señales producidas por Roxy.
6. `Sincronizacion entre dispositivos` aparece en Diagnóstico. Watchlists muestra contrato, revisión y estado real. En el entorno vivo actual la ruta respondió 200 por loopback con el snapshot real de `local_user`, pero `auth_mode=loopback-only`; por eso la interfaz dice `Solo este dispositivo` y bloquea explícitamente iPad/teléfono hasta configurar `VOICE_API_KEY`.
7. Playwright aprobó Watchlists y Diagnóstico con URL/estado persistentes, contrato visible y cero errores bloqueantes. No se declara sincronización física terminada mientras la autenticación remota siga sin configurar.

Evidencia:

- `alerts/device_sync_watchlist_probe.json`
- `alerts/device_sync_diagnostic_probe.json`
- `output/playwright/device_sync_watchlist.png`
- `output/playwright/device_sync_diagnostic.png`
- pruebas `tests/test_device_sync.py`
- pruebas `tests/test_ui_state.py`
- pruebas `tests/test_watchlists.py`
- pruebas `tests/test_voice_service.py`
- pruebas `tests/test_system_diagnostics.py`

Regresión integral: **2.314 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 132,33 segundos. Compilación dirigida y `git diff --check` terminaron limpios.

## 42. Retiro de superficies heredadas y simulación duplicada

1. El inventario de términos simulados encontró `show_market_tab` y `show_news_tab`: 461 líneas sin ninguna llamada ni ruta activa. Duplicaban Mercado y Noticias e incluían un simulador anterior con fallback fijo de equity, sugerencias Grok prototipo y un asistente local separado.
2. Se eliminaron ambas superficies completas. No se tocaron las operaciones paper históricas ni los datos del usuario; sólo código inalcanzable y duplicado.
3. Una regresión de arquitectura impide reintroducir los dos renderers, `equity = 10000.0`, `Generate Grok suggestion` o `Voice Assistant (prototype)` dentro del frontend principal.
4. La superficie canónica `Noticias` cargó 24 noticias RSS de tres fuentes, mostró estado `CONNECTED`, cache y hora de actualización. La superficie `Capital` mostró broker paper no conectado, órdenes reales `OFF`, fuente de forward-test y `Simulador local por usuario` con identidad aislada.
5. Playwright aprobó ambas rutas con URL/estado persistentes y cero errores bloqueantes. `streamlit_app.py` bajó a 57.939 líneas; la deuda de modularización sigue abierta, pero este corte eliminó duplicación real sin ocultarla detrás de otro alias.

Evidencia:

- `alerts/canonical_news_probe.json`
- `alerts/canonical_portfolio_simulation_probe.json`
- `output/playwright/canonical_news.png`
- `output/playwright/canonical_portfolio_simulation.png`
- prueba `tests/test_canonical_routes.py::test_dead_legacy_market_news_and_prototype_simulator_stay_removed`

Regresión integral: **2.315 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 131,81 segundos.

## 43. Auditoría de consumidores frontend y dominios finitos de Opciones

1. Un análisis AST encontró 768 funciones top-level y 36 definiciones sin referencia nominal dentro del frontend. Cada candidata se cruzó con pruebas y documentación para no retirar adaptadores o funciones importadas externamente.
2. Se retiraron el analizador SMA sin ruta, tres paneles antiguos de oportunidad, un buscador alterno de Acciones, un renderer alterno de Opciones y 1.070 líneas de CSS `visual lock` que nunca eran ejecutadas. También se eliminaron helpers huérfanos del corte anterior. El adaptador `render_roxy_actions_command_center` se conservó porque tiene contrato de compatibilidad probado.
3. En total `streamlit_app.py` pasó de 57.939 a 55.046 líneas en esta auditoría, sin cambiar los productores, datos históricos ni rutas activas; las diez líneas finales corresponden al gate finito agregado a los gráficos de Opciones.
4. Las pruebas afectadas (Acciones, opciones, estrategias, focused workspace y watchdog) aprobaron 1.020 casos. La ruta Acciones pasó Playwright con Escáner Finviz y Watchlists visibles, URL/estado persistentes y cero errores bloqueantes.
5. La primera sonda de Opciones confirmó la ruta y el estado `Solo lectura`, pero detectó dos warnings Vega de dominio infinito para spread y liquidez. Los frames ahora descartan cualquier valor no finito y las escalas usan dominios máximos finitos calculados.
6. Después de reiniciar el servicio canónico, la segunda sonda de Opciones quedó `OK`: cero errores de consola/página y cero warnings `empty_chart_extent`. Permanecen únicamente avisos blandos conocidos del sandbox/feature policy y versión Vega-Lite.

Evidencia:

- `alerts/dead_renderer_cleanup_actions_probe.json`
- `alerts/dead_renderer_cleanup_options_probe.json`
- `output/playwright/dead_renderer_cleanup_actions.png`
- `output/playwright/dead_renderer_cleanup_options.png`
- pruebas `tests/test_canonical_routes.py`
- pruebas `tests/test_focused_opportunities.py`

Regresión integral: **2.316 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 135,15 segundos.

## 44. Contrato permanente de consumidores frontend

1. La segunda pasada clasificó las definiciones sin referencia contra todos los archivos Python del repositorio. Se conservaron adaptadores importados por pruebas, `chart_health.py` y `tools/roxy_realtime_check.py`; las APIs externas legítimas quedaron en una allowlist explícita.
2. Se eliminaron 16 funciones sin consumidor —autenticación heredada, comando de texto alterno, resumen móvil, helpers de opciones/derivados, renderers de alertas y loaders huérfanos— y cuatro helpers que quedaron aislados después de retirar sus consumidores.
3. `frontend_function_contract_check` analiza el AST sin importar Streamlit. Cualquier función top-level sin consumidor interno ni contrato externo cambia Diagnóstico a `WARNING` y enumera su nombre.
4. El contrato vivo registra 737 funciones top-level: 720 con consumidor interno, 17 APIs externas declaradas y cero sin contrato. El resultado se almacena en caché por ruta, `mtime_ns` y tamaño.
5. Playwright abrió Diagnóstico con `Consumidores frontend` y `sin contrato 0`, URL/estado persistentes y cero errores bloqueantes. `streamlit_app.py` quedó en 54.672 líneas.

Evidencia:

- `alerts/frontend_consumers_diagnostic_probe.json`
- `output/playwright/frontend_consumers_diagnostic.png`
- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_canonical_routes.py`
- pruebas `tests/test_focused_opportunities.py`
- pruebas `tests/test_chart_health.py`

Regresión integral: **2.318 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 129,58 segundos.

## 45. Matriz responsive verificable y dominios de gráficas finitos

1. Se creó `roxy-responsive-matrix/1.0.0` para comprobar las ocho rutas canónicas de uso diario —Acciones, Gráficas, Watchlists, Crypto, Noticias, Capital, Roxy y Diagnóstico— en escritorio 1440×1000, iPad 820×1180 y teléfono 390×844.
2. Cada una de las 24 combinaciones exige contenido propio de la ruta, símbolo/mercado/temporalidad persistentes, desbordamiento horizontal máximo de cuatro píxeles y cero errores bloqueantes de consola o página. El reporte JSON se escribe atómicamente y cada caso conserva una captura independiente.
3. La primera ejecución detectó dominios Vega vacíos en Opciones, Capital y Roxy aunque las rutas cargaban. Opciones y Capital descartan valores no finitos y usan escalas explícitas. En Roxy, la bitácora usa un dominio epoch finito con etiqueta UTC y la barra de readiness desactiva el apilado implícito que generaba campos sintéticos vacíos.
4. `empty_chart_extent` es ahora un fallo de la matriz. Los avisos blandos del sandbox del navegador, feature policy y versión declarada de Vega permanecen clasificados y visibles, pero no se confunden con datos o escalas rotas.
5. `responsive_matrix_check` valida contrato, coherencia de conteos, cobertura 24/24, los tres dispositivos y vigencia máxima de 24 horas. Diagnóstico muestra `NO_DATA`, `ERROR`, `WARNING` o `CONNECTED` según evidencia real; una matriz parcial no se presenta como validación completa.
6. La sonda móvil dirigida de Roxy terminó con contexto persistente, cero desbordamiento, cero errores bloqueantes y cero `empty_chart_extent`. La matriz completa se vuelve a generar después de cada corrección para que el panel no dependa de evidencia anterior al cambio.

Evidencia:

- `alerts/responsive_route_matrix.json`
- `alerts/roxy_mobile_chart_extent_fixed_probe.json`
- `output/playwright/roxy_mobile_chart_extent_fixed.png`
- 24 capturas en `output/playwright/responsive_matrix/`
- pruebas `tests/test_responsive_route_matrix.py`

- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_focused_opportunities.py`

Validación final: **24/24 combinaciones aprobadas**, ocho por dispositivo, cero desbordamiento horizontal, cero errores bloqueantes y cero `empty_chart_extent`. Diagnóstico quedó `CONNECTED`. Regresión integral: **2.326 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 131,46 segundos. `streamlit_app.py` tiene 54.750 líneas; el contrato de consumidores registra 740 funciones top-level, 723 consumidores internos, 17 APIs externas y cero definiciones sin contrato.

## 46. Reparación del reporte semanal y aislamiento del dashboard heredado

1. `weekly_ai.py` intentaba importar `fetch_stocks` y `opportunity_engine` desde `dashboard.py`, pero esas funciones no existen. El import ejecutaba la aplicación Streamlit heredada como efecto secundario, luego era absorbido por un `except` y el reporte podía terminar vacío sin explicar por qué.
2. El reporte usa ahora `fetch_symbol_history_with_source` y el scorer alimentado por `roxy_trader/indicators.py`. No importa ni ejecuta el dashboard heredado.
3. `roxy-weekly-research/1.0.0` conserva proveedor, modo, fallback, niveles y razones. Historial insuficiente y errores quedan en `skipped`, con `total_analyzed` y `total_skipped`; ya no se confunden cero resultados con cero oportunidades. JSON y texto se reemplazan atómicamente después de `fsync`.
4. Todo lote semanal es `RESEARCH_ONLY`. Si la fuente efectiva es yfinance, se marca `RESEARCH_ONLY_FALLBACK`. `alert_eligible` permanece falso porque una clasificación diaria no puede saltarse precio live, 15m/1h, volumen, riesgo y compuertas del motor de alertas.
5. La prueba real de AAPL obtuvo historial yfinance, modo `FALLBACK`, score 30/`AVOID`, uso `RESEARCH_ONLY_FALLBACK` y cero elegibilidad de alerta. Esto valida el flujo sin presentar el fallback como dato premium.

6. Se retiró `grok_integration.py`: no tenía consumidores, contenía un `TODO/pass` de proveedor y devolvía recomendaciones locales que podían confundirse con análisis conectado. La prueba estructural impide reintroducir ese stub junto con la antigua UI Grok.

Pruebas dirigidas: **31 aprobadas**, incluyendo motor central, scanner, rutas canónicas y cinco contratos nuevos del reporte semanal.

## 47. Identidad real para todo el universo cripto operativo

1. La auditoría del último archivo de confluencia encontró 25 criptomonedas. Diez tenían logo cacheado y quince —MATIC, PEPE, RNDR, BONK, DOT, FET, FLOKI, GLM, GRT, NEAR, OCEAN, RLC, SHIB, TRAC y WIF— caían al icono genérico.
2. Los IDs, nombres e imágenes se verificaron contra `/coins/markets` de CoinGecko. El catálogo conserva el ticker del exchange y registra los nombres/migraciones del proveedor: MATIC migrado a POL, RNDR/Render y FET/Artificial Superintelligence Alliance.
3. La primera precarga confirmó un límite operativo: después de cinco perfiles, CoinGecko degradó solicitudes y varios slugs de Simple Icons no existían. Cada activo conocido conserva ahora también la URL oficial de `coin-images.coingecko.com`; si el perfil limita peticiones, el resolvedor descarga esa imagen allowlisted y la cachea, sin sustituirla por una letra. Blob y metadata usan archivos temporales únicos, `fsync` y reemplazo atómico.
4. El diagnóstico registra 40 logos, cero inconsistencias: CoinGecko 20, dominios oficiales 5 y Simple Icons 15. La revisión directa del scan cerró 25/25 criptos con logo real cacheado y cero fallbacks genéricos.
5. Las filas de Crypto 20min/2H/Daily muestran nombre completo junto al ticker y logo; el panel seleccionado comparte la misma identidad. FET/USDT mostró “Artificial Superintelligence Alliance”, precio/fuente BinanceUS y decisión `NO OPERAR`, sin convertir identidad visual en señal.
6. Playwright aprobó FET en iPad y teléfono con nombre completo, URL/estado persistentes, cero desbordamiento horizontal y cero errores bloqueantes. La inspección visual confirmó que logo, nombre, precio, plan, fuente y estado permanecen legibles.

Evidencia:

- `alerts/crypto_identity_fet_ipad_probe.json`
- `alerts/crypto_identity_fet_mobile_probe.json`
- `output/playwright/crypto_identity_fet_ipad.png`
- `output/playwright/crypto_identity_fet_mobile.png`
- `output/asset_identity_cache/`
- pruebas `tests/test_asset_identity.py`
- pruebas `tests/test_roxy_operational_charts.py`

- pruebas `tests/test_system_diagnostics.py`

Pruebas dirigidas: **51 aprobadas**, cero fallos. Regresión integral: **2.333 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 131,08 segundos.

## 48. Calendario macro: archivo presente no equivale a conexión

1. `data/macro_events.csv` existía con sólo el encabezado. `macro_calendar_status` devolvía `configured=True` y la UI convertía esa existencia en `CONNECTED`, aunque había cero eventos válidos.
2. El contrato distingue ahora `NOT_CONFIGURED`, `NO_DATA`, `DELAYED` y `CONNECTED`. También publica filas crudas, eventos válidos, última fecha, cobertura, eventos activos y próximos.
3. El archivo vivo queda correctamente en `NO_DATA`, cobertura `UNKNOWN`, cero eventos válidos y detalle “no se presenta como conectado”. No se agregaron eventos simulados ni fechas hardcodeadas.
4. La página Calendario muestra estado, causa, fuente local y cobertura. `Calendario macro` forma parte del panel de Diagnóstico y conserva el mismo estado; una futura fuente no podrá considerarse operativa sólo por crear el archivo.
5. Fue necesario reiniciar el único servicio Streamlit para descartar el módulo Python anterior en memoria. Después del reinicio, Calendario móvil y Diagnóstico iPad aprobaron URL/estado persistentes y cero errores bloqueantes.

Evidencia:

- `alerts/calendar_no_data_mobile_probe.json`
- `alerts/calendar_no_data_diagnostic_probe.json`
- `output/playwright/calendar_no_data_mobile.png`
- `output/playwright/calendar_no_data_diagnostic.png`
- pruebas `tests/test_roxy_ai.py`
- pruebas `tests/test_system_diagnostics.py`

Pruebas dirigidas: **132 aprobadas**, cero fallos. Regresión integral: **2.335 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 132,00 segundos.

## 49. Calendario macro oficial, fresco y automatizado

1. `tools/macro_calendar_sync.py` obtiene las tablas directamente de los calendarios oficiales de U.S. Bureau of Economic Analysis y Federal Reserve Board, valida tipo y tamaño de respuesta, extrae año/fecha/hora con biblioteca estándar y normaliza los eventos a America/New_York. No depende de credenciales privadas ni de fechas hardcodeadas.
2. El snapshot vivo contiene 32 publicaciones verificables de 2026: 24 de BEA y ocho reuniones FOMC, 28 todavía futuras al momento del corte. Cada fila conserva severidad, moneda, fuente, URL y `fetched_at`; el reporte atómico `roxy-macro-calendar-sync/1.0.0` conserva conteos por fuente, próxima publicación, ETag y Last-Modified de ambos upstreams.
3. Si BEA o Federal Reserve falla o cambia a HTML no parseable, el proceso escribe `WARN` sin exponer el mensaje crudo y conserva el último calendario combinado válido. CSV y JSON se escriben con archivo temporal único, `fsync` y reemplazo atómico.
4. Se corrigió la ventana temporal: 24 horas significa realmente desde ahora hasta ahora+24h. Una fuente oficial fresca continúa `CONNECTED` aunque no haya evento en esa ventana; `DELAYED` depende de una antigüedad superior a 48 horas, no de la ausencia de eventos próximos.
5. La página Calendario usa una ventana informativa de 30 días y muestra todas las publicaciones, mientras la compuerta de riesgo mantiene su ventana operativa de 24 horas y sólo activa eventos MEDIUM/HIGH. Estado de fuente, actividad y cobertura no se mezclan. Las decisiones FOMC quedan HIGH y las reuniones con proyecciones se distinguen en el título.
6. `com.roxy.macro-calendar` quedó instalado y cargado con ejecución al iniciar y cada 21.600 segundos. Diagnóstico separa `Calendario macro`, `Sincronizacion calendario macro` y `Servicio calendario macro`, por lo que archivo, fetch y automatización pueden fallar de forma independiente y visible.
7. Playwright aprobó Calendario en teléfono y Diagnóstico en escritorio con URL/estado persistentes, cero desbordamiento horizontal y cero errores bloqueantes. La inspección visual inicial confirmó BEA, cuatro publicaciones dentro de 30 días y estado `CONNECTED`; después de integrar Federal Reserve la misma ventana contiene cinco publicaciones y dos fuentes oficiales, sin presentar la primera publicación LOW como riesgo activo.
8. BLS/CPI/NFP no se presentan como integrados. Tanto la agenda HTML como el ICS oficial respondieron HTTP 403 a la recuperación automatizada de este entorno; Roxy conserva esa cobertura como pendiente en lugar de copiar fechas desde una fuente secundaria o inventarlas.

Evidencia:

- `alerts/macro_calendar_sync.json`
- `alerts/calendar_bea_mobile_probe.json`
- `alerts/calendar_bea_diagnostic_probe.json`
- `output/playwright/calendar_bea_mobile.png`
- `output/playwright/calendar_bea_diagnostic.png`
- `alerts/calendar_official_sources_mobile_probe.json`
- `alerts/calendar_official_sources_diagnostic_probe.json`
- `output/playwright/calendar_official_sources_mobile.png`
- `output/playwright/calendar_official_sources_diagnostic.png`
- pruebas `tests/test_macro_calendar_sync.py`
- pruebas `tests/test_macro_calendar_launchd.py`
- pruebas `tests/test_roxy_ai.py`
- pruebas `tests/test_system_diagnostics.py`

Pruebas dirigidas: **129 aprobadas**, cero fallos. Regresión integral: **2.346 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 131,72 segundos.

## 50. Contexto efectivo de proveedores y retiro del toggle Grok desconectado

1. Diagnóstico leía las credenciales desde `os.environ`, mientras el watchdog usa el `.env` efectivo del LaunchAgent y ElevenLabs carga `.env.local`. El resultado visible era contradictorio: `Alpaca NOT_CONFIGURED` junto a `Alpaca runtime AUTH_INVALID`, aunque las credenciales sí estaban presentes.
2. `effective_diagnostic_provider_env` combina únicamente nombres allowlisted desde proceso, LaunchAgent y archivos locales usados por el proveedor. No carga variables ajenas, no devuelve valores en ninguna fila y respeta la precedencia del proceso.
3. Las filas de configuración describen ahora presencia, no salud: Alpaca y ElevenLabs son `CONFIGURED` en este entorno. Las filas runtime conservan el resultado real y separado. Alpaca sigue `AUTH_INVALID` en paper; `ElevenLabs runtime` lee telemetría SQLite de sólo lectura y muestra `AUTH_INVALID`, operación `conversation_token`, HTTP 401 y antigüedad.
4. La interfaz ya no puede afirmar “no configurado” cuando el servicio realmente está intentando autenticar, ni puede confundir una clave presente con una conexión funcional. Finviz, Polygon y Finnhub continúan `NOT_CONFIGURED` porque no existe configuración efectiva.
5. Se retiraron de la carga Streamlit los imports sin consumidor `grok_control`, `auth` y `ENABLE_GROK_CODE_FAST`. `grok_control.py` era un toggle JSON descrito por sí mismo como placeholder y no habilitaba ningún proveedor. El OAuth real del backend en `tools/secrets_service.py` conserva su propio uso de `auth.py`.
6. Playwright aprobó Diagnóstico en iPad con `Alpaca runtime`, `ElevenLabs runtime`, `AUTH_INVALID` y `HTTP 401` visibles, URL/estado persistentes y cero errores bloqueantes.

Evidencia:

- `alerts/effective_provider_diagnostic_probe.json`
- `output/playwright/effective_provider_diagnostic.png`
- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_elevenlabs_roxy.py`
- pruebas `tests/test_api_budget.py`
- pruebas `tests/test_canonical_routes.py`

Pruebas dirigidas: **389 aprobadas** en el contrato frontend/diagnóstico y **88 aprobadas** en proveedor/telemetría, con una advertencia conocida de dependencia en cada grupo. Regresión integral: **2.348 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 131,98 segundos.

## 51. Voz unificada con activo, oportunidad, temporalidad y watchlist reales

1. Los comandos de voz ya no viven como un chatbot separado. `roxy_os_context` entrega al orquestador el mismo snapshot de oportunidades, el texto visible y el contrato operativo que usa la interfaz. El agente de trading prioriza el activo explícito o visible; una oportunidad de mayor puntuación para otro símbolo no puede sustituirlo.
2. “Explícame esta oportunidad” filtra por coincidencia exacta con el símbolo seleccionado. Si ese activo no aparece en la tabla verificable, Roxy lo declara y no explica otra señal como si fuera la actual. La respuesta válida incluye temporalidad, precio disponible, base del precio, entrada, stop, objetivo, confianza, razón y confirmación pendiente. El brief de LINK/USD expone `close_15m`; la voz lo presenta como “último cierre 15m”, no como una cotización streaming.
3. Una sesión nueva obtiene contexto durable primero desde la watchlist autónoma `Roxy Oportunidades`; si esa lista está vacía, usa `alerts/roxy_ai_brief.json`, que es el brief real producido por el cerebro central. El adaptador conserva `entry_tf`, temporalidad de gráfica/tendencia, explicación, bloqueador y siguiente acción. No genera oportunidades ni precios de relleno.
4. “Agrégala a mi watchlist” usa el activo actual y la lista activa durable. Las listas administradas por el sistema son de sólo lectura: si `Roxy Oportunidades` está seleccionada, el comando guarda en `Principal` y lo explica, sin corromper la lista autónoma.
5. “Cambia a la gráfica de una hora” actualiza estado de sesión y URL sin recargar toda la aplicación. La deduplicación de comandos sólo bloquea repeticiones accidentales durante cuatro segundos; el mismo comando puede ejecutarse de nuevo después de esa ventana.
6. ElevenLabs continúa correctamente degradado: configuración presente, pero la telemetría runtime devuelve HTTP 401/AUTH_INVALID. Estos contratos funcionan mediante el control local de Roxy y no convierten esa credencial inválida en estado conectado.
7. Playwright aprobó los tres recorridos reales: cambio de temporalidad, adición durable de SOL/USD y explicación seleccionada de LINK/USD en teléfono. El último control conservó símbolo/mercado/15m, mostró únicamente LINK/USD y registró cero errores bloqueantes.

Evidencia:

- `alerts/voice_timeframe_e2e_probe.json`
- `alerts/voice_watchlist_e2e_probe.json`
- `alerts/voice_selected_opportunity_e2e_probe.json`
- `output/playwright/voice_timeframe_e2e.png`
- `output/playwright/voice_watchlist_e2e.png`
- `output/playwright/voice_selected_opportunity_e2e.png`
- pruebas `tests/test_roxy_os.py`

## 121. Home Assistant real con degradacion y controles fail-closed

1. `HomeAgent` era declarativo: siempre decia que Home Assistant debia conectarse, pero no inspeccionaba configuracion, red, autenticacion ni dispositivos. Una accion de voz generaba un objeto de comando aunque ningun proveedor existiera.
2. `HomeAssistantClient` publica `roxy-home-assistant/1.0.0`. Usa `ROXY_HOME_ASSISTANT_URL`, `ROXY_HOME_ASSISTANT_TOKEN` y timeout acotado; distingue `SERVICE_NOT_CONFIGURED`, `CONFIGURATION_ERROR`, `AUTH_INVALID`, `UNAVAILABLE`, `ERROR` y `CONNECTED`.
3. La URL base rechaza credenciales embebidas, paths, queries y fragmentos. HTTP sin TLS solo se permite en loopback, IP privada o `.local`; hosts publicos requieren HTTPS.
4. La lectura usa `/api/states`, conserva solo dominios soportados y normaliza entidad, nombre, estado, unidad y timestamp. Atributos crudos, tokens de imagen y metadatos sensibles no entran al resultado. Camaras y cerraduras quedan marcadas como sensibles y solo lectura.
5. La escritura solo permite `turn_on`/`turn_off` para `light` y `switch`. Exige simultaneamente `ROXY_HOME_CONTROL_ENABLED=1`, permiso `smart_home`, entidad exacta, preview coincidente y segunda confirmacion. Locks, camaras y servicios fuera de allowlist devuelven `BLOCKED` antes de cualquier red.
6. `Roxy Home` muestra proveedor, estado, hora de comprobacion y causa real. Sin credenciales presenta `SERVICE_NOT_CONFIGURED` e instrucciones adaptables a movil; no aparenta dispositivos ni controles disponibles. Si conecta, lista entidades y separa lectura de escritura.
7. Las sondas Chromium de escritorio y telefono cerraron `OK`, conservaron URL/contexto y no registraron errores bloqueantes. El runtime actual se verifico sin URL/token y publica correctamente `SERVICE_NOT_CONFIGURED`, no `CONNECTED`.
8. `home_assistant_check.json` separa `contract_status=OK` de `status=WARN`: la integracion y su degradacion estan probadas, pero la aceptacion operativa requiere credenciales reales. Fase 7 conserva ese bloqueo explicitamente.
9. Las pruebas simulan conexion, autenticacion rechazada, timeout, filtrado de atributos y todas las puertas de escritura. La regresion integral cerro **2.597/2.597** en 153,51 s, sin advertencias y con codigo de salida 0.

Evidencia:

- `alerts/home_assistant_check.json`
- `alerts/home_assistant_desktop_probe.json`
- `alerts/home_assistant_mobile_probe.json`
- `output/playwright/home_assistant_desktop.png`
- `output/playwright/home_assistant_mobile.png`
- `roxy_os/home_assistant.py`
- `tools/home_assistant_check.py`
- pruebas `tests/test_home_assistant.py`
- pruebas `tests/test_home_assistant_check.py`
- pruebas `tests/test_roxy_os.py`

## 120. Lista de compras durable compartida con voz y texto

1. `ShoppingAgent` almacenaba cada articulo como una memoria generica `shopping_item`. No existian cantidades, unidades, categorias, deduplicacion, estado comprado ni una pantalla desde la que verificar o corregir la lista.
2. `ShoppingListStore` publica `roxy-shopping-list/1.0.0` sobre un archivo atomico con lock. Los articulos incluyen usuario, identidad normalizada, nombre visible, cantidad, unidad, categoria, notas, estado, fuente y timestamps.
3. Agregar de nuevo el mismo articulo pendiente con la misma unidad incrementa la cantidad en lugar de crear ruido duplicado; la identidad elimina diferencias de mayusculas y acentos. Usuarios distintos permanecen aislados.
4. Los estados `PENDING`, `PURCHASED` y `ARCHIVED` tienen transiciones validadas y recuperables. No existe borrado destructivo desde la interfaz.
5. El orquestador deriva la ruta de compras del mismo directorio que su memoria temporal o productiva. Voz, texto, contexto y la ruta canonica `Compras` consumen una sola fuente; el contrato de respuesta conserva `content` para clientes anteriores sin mantener dos almacenamientos.
6. La interfaz permite cantidad, unidad, categoria y notas; muestra fuente, ultima escritura y `LOCAL_ONLY`, y declara el estado vacio sin datos simulados. La ruta usa el camino rapido y no carga mercado para gestionar la casa.
7. Las sondas Chromium de escritorio y telefono cerraron `OK`, conservaron URL/simbolo/mercado/temporalidad y no registraron errores bloqueantes. El flujo de navegador creo un articulo, lo marco comprado y luego lo archivo de forma recuperable bajo el usuario de diagnostico.
8. El check dedicado prueba persistencia, aislamiento, deduplicacion, ciclo de vida, voz compartida, ruta/contexto y runtime responsive sin mutar datos productivos. Fase 7 incorpora compras como evidencia, pero permanece `IN_PROGRESS` por correo, documentos, hogar, sincronizacion remota y cliente movil.
9. La regresion integral cerro **2.587/2.587** en 147,17 s, sin advertencias y con codigo de salida 0.

Evidencia:

- `alerts/shopping_list_check.json`
- `alerts/shopping_list_desktop_probe.json`
- `alerts/shopping_list_mobile_probe.json`
- `output/playwright/shopping_list_desktop.png`
- `output/playwright/shopping_list_mobile.png`
- `roxy_os/shopping_list.py`
- `tools/shopping_list_check.py`
- pruebas `tests/test_shopping_list.py`
- pruebas `tests/test_shopping_list_check.py`
- pruebas `tests/test_roxy_os.py`
- pruebas `tests/test_watchlists.py`
- pruebas `tests/test_dashboard_probe_auth.py`
- pruebas `tests/test_elevenlabs_roxy.py`

Pruebas dirigidas del contrato de voz/contexto: **98 aprobadas**, cero fallos.

## 52. Retiro de acciones falsas y adaptador broker placeholder

1. La watchlist administrada `Roxy Oportunidades` mostraba “Sincronización automática” como un botón deshabilitado. No ejecutaba una acción y contradecía el criterio de no presentar controles puramente visuales. Ahora es un estado informativo explícito: “Sincronización automática activa · lista de solo lectura”.
2. La restricción subyacente permanece probada de extremo a extremo: la lista autónoma rechaza mutaciones manuales, conserva su contenido y las adiciones de voz se dirigen a una lista personal mutable.
3. `adapters/broker.py` no tenía importadores ni pruebas consumidoras. Declaraba `AlpacaBroker` como placeholder, `CCXTBroker` siempre lanzaba `NotImplementedError` y la primera clase referenciaba `os` sin importarlo. Se retiró el archivo para que inventario o mantenimiento futuro no lo confundan con la integración Alpaca real, que vive en los conectores operativos y sigue bloqueada por `AUTH_INVALID`.
4. Un análisis AST de todos los `st.button`, `st.link_button` y `st.download_button` restantes encontró que las llamadas no usadas como condición sólo corresponden a controles con `on_click` o enlaces reales. No quedan otros botones Streamlit conocidos que sean simples adornos deshabilitados.
5. Playwright aprobó la watchlist autónoma en iPad: lista correcta, sincronización `OK`, estado de sólo lectura visible, URL/estado persistentes y cero errores bloqueantes.
6. La inspección visual encontró una respuesta genérica de Roxy en cada carga sin comando. `text_display("")` devuelve `"-"` para celdas sin dato; ese valor se estaba ejecutando como `roxy_os_cmd` y luego se mostraba como una barra verde vacía. El procesador de comandos y los tres mensajes efímeros afectados usan ahora texto crudo para decidir presencia. Una página normal no invoca al agente, no genera voz pendiente y no reserva espacio para feedback inexistente.

Evidencia:

- `alerts/watchlist_readonly_status_probe.json`
- `output/playwright/watchlist_readonly_status.png`
- pruebas `tests/test_watchlists.py`

Pruebas dirigidas de watchlists y carga sin comando: **42 aprobadas**, cero fallos.

Regresión integral después de este bloque: **2.357 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 126,42 segundos.

## 53. Estrategias visuales centrales: cruce, retesteo, volumen, divergencia y RSI

1. `roxy_trader/operational_strategies.py` publica el contrato `roxy-visual-strategies/1.1.0` y continúa usando exclusivamente `roxy_trader.indicators`. EMA y RSI no se recalculan con fórmulas distintas en la UI.
2. El detector central cubre ahora 20 familias auditables: tendencia alcista/bajista, cruces EMA9/21, ruptura alcista/bajista, retesteo alcista/bajista, consolidación, tres triángulos, dos wedges, soporte/resistencia, incremento de volumen, divergencia RSI alcista/bajista y sobrecompra/sobreventa.
3. Los cruces exigen que EMA9 cambie realmente de lado respecto a EMA21 entre las dos últimas velas. Se publican como `WAITING_CONFIRMATION`, nunca como entrada automática.
4. El retesteo busca una ruptura real ocurrida entre dos y diez velas atrás, vuelve a calcular el nivel desde las 20 velas anteriores y exige que el precio lo conserve como soporte/resistencia. Sólo pasa a `READY` con vela en la dirección correcta y volumen relativo mínimo de 0,8x.
5. El aumento de volumen exige al menos 1,5x contra el promedio de las 20 velas anteriores. La divergencia exige dos pivotes separados por cuatro velas, cambio de precio mínimo de 0,25% en dirección divergente y cambio RSI contrario de al menos tres puntos. La anotación dibuja el tramo de precio entre ambos pivotes.
6. RSI ≥70 y RSI ≤30 se muestran como estados `WATCHING` y explican expresamente que no son señales automáticas de venta o compra. La capa no convierte un extremo de momentum en recomendación.
7. Soporte y resistencia se derivan de pivotes confirmados. Retesteos, cruces, volumen y zonas RSI generan marcadores/niveles; divergencias generan líneas con coordenadas reales `(timestamp, price)`. La UI dibuja como máximo dos estructuras prioritarias por temporalidad y lista hasta seis, evitando saturar la gráfica.
8. La misma evaluación 15m/1h se habilitó para acciones y cripto. En el estado vivo, LINK/USD mostró consolidación y soporte/resistencia en 15m, retesteo alcista en 1h y tendencia alcista; ambas gráficas conservaron 640 velas y fuente `BinanceUS WebSocket + REST fallback`.
9. La franja compacta `ESTRUCTURAS REALES` expone estrategia, temporalidad, estado y confianza encima de las gráficas. Escritorio y teléfono aprobaron URL/estado persistentes, cero desbordamiento horizontal y cero errores bloqueantes.
10. Diagnóstico incorpora `Motor de estrategias visuales`: valida sintaxis, versión, dependencia del motor central y presencia de las 20 familias. El control vivo quedó `CONNECTED · familias 20/20 · indicadores centrales si`.
11. El primer watchdog posterior encontró una desalineación transitoria: ETH/USD acababa de entrar al brief activo después de generarse el reporte de gráficas, por lo que figuraba como “active chart missing”. Se regeneró el contrato con los símbolos activos: 16 gráficas, LINK/USD y ETH/USD incluidos en 15m/1h, cero `fail` y cero `warn`. Diez ciclos sanos consecutivos restauraron el SLO a `Core operativo / externo bloqueado`; el historial no fue borrado ni maquillado.

Evidencia:

- `alerts/visual_strategy_link_desktop_probe.json`
- `alerts/visual_strategy_link_mobile_probe.json`
- `alerts/visual_strategy_diagnostic_probe.json`
- `output/playwright/visual_strategy_link_desktop.png`
- `output/playwright/visual_strategy_link_mobile.png`
- `output/playwright/visual_strategy_diagnostic.png`
- pruebas `tests/test_operational_strategies.py`
- pruebas `tests/test_roxy_operational_charts.py`
- pruebas `tests/test_system_diagnostics.py`

Pruebas dirigidas del motor, gráficas y diagnóstico: **91 aprobadas**, cero fallos.

Regresión integral después de esta ampliación: **2.366 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 130,38 segundos.

## 54. Backtesting reproducible, ejecución realista y validación temporal

1. `ma_backtester.py` publica `roxy-ma-backtest/2.2.0`. La anualización ya no supone siempre 252 velas: usa mercado y temporalidad, incluyendo sesión bursátil y mercado cripto 24/7. Sharpe, Sortino y retorno anualizado declaran el número de periodos usado.
2. La ejecución conserva señal al cierre y entrada en la apertura siguiente. Comisión y slippage se contabilizan por separado y también como costo total. Un gap que atraviesa el stop sale en la apertura real de la vela (`STOP_GAP`), no en el stop anterior favorable e inalcanzable.
3. Cada ejecución valida capital, tamaño y costos antes de procesar datos. El contrato SHA-256 incluye OHLCV normalizado, símbolo, mercado, temporalidad, versiones del motor/estrategia y todos los parámetros; repetir exactamente la misma entrada produce el mismo hash, mientras cambiar una vela o temporalidad lo modifica.
4. `roxy-backtest-validation/1.0.0` agrega una separación cronológica anclada 70/30 sin reajuste de parámetros. In-sample y out-of-sample conservan retorno, drawdown, Sharpe, operaciones, win rate, profit factor y PnL. Las operaciones que cruzan el corte se excluyen y se cuentan. Con menos de 450 velas se muestra `DATA_INSUFFICIENT`, sin inventar validación.
5. La interfaz expone parámetros de score, extensión, pullback y stop junto con capital, posición, comisión, slippage y cooldown. Muestra costos, comparación equivalente contra buy-and-hold, validación OOS, corte temporal, hash y versiones. Las ejecuciones durables se pueden seleccionar y comparar; los registros antiguos 2.0 permanecen identificados en vez de reescribirse.
6. El proveedor se presenta por su etiqueta efectiva y modalidad. BinanceUS aparece como `API/REST proveedor`, no como streaming. Estados `COMPLETED`, `NO_TRADES`, `DATA_INSUFFICIENT` y `ERROR` conservan causa y procedencia.
7. La versión 2.2 reutiliza las medias/ATR/volumen calculadas por el motor central una sola vez. Un fixture de 1.000 velas conservó exactamente 64 operaciones y retorno -0,13283324, mientras el tiempo aislado bajó de 4,33 s a 1,22 s (aproximadamente 72%). Una prueba de equivalencia compara el diccionario completo de señal y falla si la ruta optimizada intenta recalcular indicadores.
8. `Motor de backtesting` en Diagnóstico verifica siete contratos por AST/texto: gap de stop, anualización, costos, validación temporal, hash de entrada, almacenamiento atómico bloqueado y una sola pasada de indicadores. El estado vivo quedó `CONNECTED`, versiones 2.2.0/1.0.0 y contratos 7/7.
9. Playwright pulsó realmente `Ejecutar backtest real` para LINK/USD 1h. El flujo obtuvo 1.000 velas de BinanceUS, guardó hash `a3208c8af279…`, dejó validación `AVAILABLE`, persistió URL/estado y registró cero errores de consola/página y cero desbordamiento. El mismo resultado se validó en teléfono.
10. El resultado no se maquilla: 14 operaciones, retorno -0,55% y costo de ejecución 69,70 en el último corte real. Roxy lo muestra como evidencia histórica desfavorable, no como recomendación. La sonda completa en una sesión Chromium nueva tardó 44,34 s; el motor ya no es el cuello dominante. Una sonda sólo de resultado midió contenido inicial visible en 17,38 s, por lo que el arranque/rerender general de Streamlit permanece abierto como deuda P2 y no se atribuye falsamente al cálculo de estrategia.
11. El reinicio dirigido del LaunchAgent Streamlit reveló y corrigió primero el módulo 2.0 y luego cargó 2.2; el servicio volvió a HTTP 200 con PID nuevo. El watchdog cerró con core operativo sostenido, 14 gráficas revisadas, cero fallos/warnings de gráficas; el `WARN` global sigue correspondiendo a bloqueos externos conocidos (Alpaca `AUTH_INVALID`, permisos de disco externo y archivo de video pendiente).

Evidencia:

- `alerts/backtest_real_action_probe.json`
- `alerts/backtest_real_action_probe.png`
- `alerts/backtest_saved_result_probe.json`
- `alerts/backtest_saved_result_probe.png`
- `alerts/backtest_mobile_probe.json`
- `alerts/backtest_mobile_probe.png`
- `alerts/backtest_diagnostic_probe.json`
- `alerts/backtest_diagnostic_probe.png`
- `alerts/backtest_timing_probe.json`
- `alerts/backtest_fast_route_probe.json`
- `data/roxy_backtests.json`
- pruebas `tests/test_ma_backtester.py`
- pruebas `tests/test_backtests.py`
- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_dashboard_probe_auth.py`

Pruebas dirigidas finales: **84 aprobadas** para motor/wrapper/diagnóstico/probe y **360 aprobadas** para backtesting, rutas canónicas y superficies enfocadas. Regresión integral: **2.381 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 131,64 segundos.

## 55. Arranque operacional, CSS condicional y recuperación completa de Academy

1. El runtime Three.js de 589 KiB ya no se inyecta en Dashboard, gráficas, Backtesting, Diagnóstico ni ninguna otra superficie operacional. Se carga únicamente en Academy, donde sí tiene un consumidor visual explícito.
2. El bloque continuo de estilos de autenticación/Academy, de casi 4.900 líneas, se separa del payload autenticado operacional. Login y Academy reciben el CSS completo; las páginas de mercado/trading reciben sólo el sistema visual que utilizan. La selección ocurre después de restaurar la sesión y antes del render.
3. En Chromium nuevo, Backtesting pasó de 17,377 s a 10,502 s de contenido inicial al retirar WebGL global y luego a 7,559 s con CSS condicional: mejora aproximada de **56,5%**. El recorrido completo pasó de 18,728 s a 8,632 s, mejora de **53,9%**. Conservó 4.130 caracteres útiles, URL/estado, cero errores bloqueantes y cero desbordamiento.
4. Login en teléfono conservó `¡Bienvenido de nuevo!`, controles visibles, ancho responsive de 382 px y fondo esperado. La optimización no entrega una hoja operacional incompleta al usuario sin sesión.
5. La primera prueba real de Academy descubrió un defecto previo que los estilos ocultaban: `ROXY_ACADEMY_PROGRESS_PATH` y `ROXY_ACADEMY_LEVEL_1_LESSONS` no existían. La página sólo mostraba `Cerrar sesion` y el fondo mientras Streamlit registraba `NameError`. Se restauró un contrato durable de progreso y un currículo inicial de 20 lecciones únicas con quiz, feedback, examen y símbolos de ejemplo.
6. El ejemplo educativo dejó llamadas yfinance sin límite. Ahora solicita un cierre diario real con máximo de cuatro segundos y lo etiqueta `Ultimo cierre real · no streaming`; si falla, declara dato no disponible y continúa.
7. Academy se ejecuta antes del centro de comandos, inbox y voz global. En servidor limpio mostró contenido útil en 5,750 s y completó en 8,252 s, con 1.263 caracteres, URL/estado y cero errores. El probe acepta capitalización de marca (`ACADEMY`) sin falso negativo.
8. La matriz posterior a la separación global cerró **24/24** en escritorio, iPad y teléfono, sin desbordamiento, pérdida de símbolo/mercado/temporalidad, gráfica vacía ni error bloqueante.
9. El contrato de métricas del watchdog revalida su proyección final después del mantenimiento tardío del historial. El aviso interno transitorio de ocho alias ya presentes desapareció; no hay fallos y quedan sólo avisos externos/operativos declarados: video por archivar, permiso del disco externo y Alpaca `AUTH_INVALID`.

Evidencia:

- `alerts/backtest_timing_probe.json`
- `alerts/backtest_timing_no_webgl_probe.json`
- `alerts/backtest_timing_operational_css_probe.json`
- `alerts/auth_style_after_split.png`
- `alerts/academy_style_after_split_probe.json`
- `alerts/academy_style_after_split_probe.png`
- `alerts/responsive_route_matrix.json`
- `output/playwright/responsive_matrix/`
- `alerts/roxy_realtime_check.json`
- pruebas `tests/test_academy_runtime.py`
- pruebas `tests/test_canonical_routes.py`
- pruebas `tests/test_dashboard_probe_auth.py`
- pruebas `tests/test_roxy_three_universe.py`
- pruebas `tests/test_roxy_realtime_check.py`

Pruebas dirigidas: **110 aprobadas** para Academy/rutas/auth/probe/Three/diagnóstico y **650 aprobadas** para watchdog/Academy/probe. Regresión integral: **2.389 pruebas aprobadas**, 2 advertencias conocidas, cero fallos y código de salida 0 en 133,10 segundos. Matriz responsive: **24/24 aprobada**.

## 56. Perfil de arranque, payload por consumidor y compatibilidad Streamlit

1. Se añadió un perfilador de arranque que sólo responde a una sesión diagnóstica firmada y al parámetro explícito `profile_startup=1`. Produce `roxy-frontend-startup-profile/1.0.0`, fases acumuladas y un `pstats` local; una sesión normal ejecuta exactamente el callback sin escribir perfiles.
2. En Backtesting sobre servidor limpio, restaurar sesión tomó 0,003 s, preparar estilos 0,099 s, completar el shell operacional 0,608 s y renderizar la vista enfocada bajo profiler 0,787 s. Todo `main()` terminó en 1,402 s. Esto demostró que el cuello restante dominante está en inicialización/DOM del cliente, no en el motor de backtesting ni en Python.
3. El perfil de 804.943 llamadas atribuyó 0,748 s a `show_focused_roxy_app`, 0,399 s a `show_backtest_screen`, 0,149 s a cinco serializaciones Altair y 0,106 s al resumen de memoria de fuentes. No se encontró una consulta de proveedor bloqueante dentro del render.
4. El asistente ElevenLabs contiene aproximadamente 81,8 KiB de runtime fuente. Ahora sólo se carga en páginas que consumen voz/contexto: Dashboard, Alertas, Activo, Opciones, Estudios y Roxy IA, además de los workspaces de acciones/crypto que ya lo cargan de forma explícita. Backtest, Diagnóstico, Noticias, Calendario, Capital y Plataformas no reciben ese payload sin consumidor.
5. La configuración de passkey dejó de repetirse en todas las páginas y se limita a Plataformas, Roxy IA y Diagnóstico, donde corresponde a seguridad/sistema. El contrato de autenticación y los callbacks no cambiaron.
6. Backtesting bajó nuevamente de 8,632 s a 7,408 s totales y de 7,559 s a 6,251 s de contenido inicial. Frente a la línea base previa de 18,728/17,377 s, la mejora acumulada es aproximadamente **60,4% total** y **64,0% hasta contenido útil**.
7. El adaptador de compatibilidad ya prefiere `width="stretch|content"` cuando la versión instalada de Streamlit lo soporta. Altair consume ese argumento y lo aplica al objeto chart sin reenviarlo a una API que aún no lo acepta. Esto corrigió tanto la advertencia de eliminación posterior a 2025-12-31 como un `TypeError` tardío del gráfico de hitos en Capital.
8. Capital/Portafolio aprobó el recorrido real con 3.031 caracteres útiles, URL/estado persistentes y cero errores de página/consola. Las 369 pruebas dirigidas de rutas, oportunidades, capital y WebGL aprobaron; sólo quedan las dos advertencias conocidas de LibreSSL/websockets en la suite.
9. La matriz global posterior volvió a cerrar **24/24**. La regresión final cerró **2.393/2.393**, cero fallos, código 0 en 132,80 s.

Evidencia:

- `alerts/frontend_startup_profile.json`
- `alerts/frontend_startup_profile.pstats`
- `alerts/backtest_profile_probe.json`
- `alerts/backtest_timing_scoped_payload_probe.json`
- `alerts/backtest_timing_scoped_payload_probe.png`
- `alerts/capital_width_contract_probe.json`
- `alerts/capital_width_contract_probe.png`
- `alerts/responsive_route_matrix.json`
- pruebas `tests/test_canonical_routes.py`
- pruebas `tests/test_roxy_three_universe.py`
- pruebas `tests/test_auth_session_security.py`
- pruebas `tests/test_dashboard_probe_auth.py`

Regresión integral: **2.393 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 132,80 segundos. Matriz responsive: **24/24 aprobada**.

## 57. Hoja visual modular, integridad operativa y reducción de concentración

1. La hoja visual de 778.230 caracteres dejó de vivir como un literal monolítico dentro de `streamlit_app.py`. Se extrajo sin reinterpretar ni reformatear a tres recursos versionables: base compartida (149.723 bytes), Academy/autenticación (619.258 bytes) y cierre responsive (9.275 bytes).
2. El cargador `roxy_application_style_markup()` conserva el orden exacto del payload anterior y cachea las dos composiciones válidas. Login y Academy reciben base + Academy/auth + responsive; las páginas operativas reciben base + responsive y evitan más de 600 KiB que no consumen.
3. El archivo principal bajó de 55.277 a 49.706 líneas. La reducción no cambia selectores ni reglas: una prueba reconstruye ambas composiciones y demuestra que la variante operacional coincide exactamente con el recorte condicional que se usaba antes.
4. El sistema falla de forma explícita si un recurso requerido no existe. Diagnóstico incorpora `Recursos visuales frontend`, que verifica presencia, lectura, marcadores estructurales, cierre de la hoja, tamaño total y que el payload operacional sea realmente menor.
5. Login se inspeccionó en Chromium móvil después de la extracción: contenedor de 352 × 708 px, botón visible, fondo calculado correcto y cero desbordamiento horizontal. Academy aprobó en iPad con contenido real y Diagnóstico publicó el nuevo control, ambos sin errores de consola o página y con URL/estado persistentes.
6. La matriz responsive global posterior volvió a cerrar **24/24** en escritorio, iPad y teléfono, sin pérdida de símbolo, mercado o temporalidad, ni desbordamiento o gráfica vacía.

Evidencia:

- `assets/styles/roxy_base.css.html`
- `assets/styles/roxy_academy_auth.css`
- `assets/styles/roxy_responsive.css.html`
- `alerts/css_module_academy_probe.json`
- `alerts/css_module_diagnostic_probe.json`
- `output/playwright/css_module_login_mobile.png`
- `alerts/responsive_route_matrix.json`
- pruebas `tests/test_brand_logo.py`
- pruebas `tests/test_canonical_routes.py`
- pruebas `tests/test_system_diagnostics.py`

Pruebas dirigidas del contrato visual y diagnóstico: **73 aprobadas**, una advertencia conocida de LibreSSL y cero fallos.

Regresión integral posterior: **2.397/2.397 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 125,32 segundos. Matriz responsive: **24/24 aprobada**.

## 58. Runtime de voz modular e interpolación segura de contexto

1. El runtime del navegador de ElevenLabs dejó de estar incrustado como un `rf-string` de 1.381 líneas dentro de `streamlit_app.py`. La plantilla exacta de 71.709 caracteres vive ahora en `assets/runtime/roxy_elevenlabs_assistant.js.html` y la función de render bajó a 189 líneas.
2. La extracción fue mecánica y se verificó antes de escribir: con payload y avatar de prueba, el documento reconstruido coincidió exactamente con el generado por el literal anterior. El archivo principal bajó de 49.706 a 48.557 líneas aun incluyendo cargador, validaciones y control diagnóstico nuevos.
3. El cargador cacheado exige exactamente dos marcadores de payload, uno de avatar, envoltura `<script>` completa y `Conversation.startSession`. Un recurso ausente o truncado produce un error explícito en vez de montar una voz parcialmente rota.
4. El contexto de usuario ya no se inserta mediante `json.dumps` directo. `roxy_json_for_inline_script()` neutraliza `<`, `>`, `&`, U+2028 y U+2029; una prueba introduce deliberadamente `</script><script>alert(...)` y confirma que no puede cerrar la etiqueta ni ejecutar un segundo script.
5. Diagnóstico incorpora `Runtime frontend de voz` y valida plantilla, marcadores y serialización segura. En estado vivo publicó `CONNECTED · plantilla 71.709 caracteres · marcadores 3/3 · JSON protegido para script`.
6. Una página Crypto que consume realmente el asistente aprobó en Chromium con 1.907 caracteres útiles, símbolo/mercado/temporalidad y URL persistentes, cero errores bloqueantes. Diagnóstico aprobó con 6.090 caracteres y mostró el nuevo control.

Evidencia:

- `assets/runtime/roxy_elevenlabs_assistant.js.html`
- `alerts/voice_runtime_module_dashboard_probe.json`
- `alerts/voice_runtime_diagnostic_probe.json`
- `output/playwright/voice_runtime_module_dashboard.png`
- `output/playwright/voice_runtime_diagnostic.png`
- pruebas `tests/test_elevenlabs_roxy.py`
- pruebas `tests/test_dashboard_probe_auth.py`
- pruebas `tests/test_system_diagnostics.py`

Pruebas focales de voz, autenticación de probes y diagnóstico: **108 aprobadas**, una advertencia conocida de LibreSSL y cero fallos. Regresión integral: **2.400/2.400 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 124,14 segundos.

## 59. Aislamiento de streaming stock/crypto en el workspace dual

1. La validación del workspace dual con `LINK/USD · crypto · 15m` descubrió una fuga de proveedor: el terminal aceptaba correctamente el mercado crypto, pero montaba incondicionalmente el runtime WebSocket de acciones y enviaba `LINKUSD` al refresco Yahoo. Además rotulaba la cabecera como NASDAQ.
2. `roxy_live_stock_symbols()` filtra ahora las filas por mercado normalizado antes de construir la suscripción. Pares crypto, aunque se abran dentro del workspace sincronizado de análisis, no pueden entrar al stream, snapshot o fallback de cotizaciones bursátiles.
3. El runtime stock sólo se monta cuando existe al menos un símbolo bursátil real. Para crypto, el terminal conserva sus gráficas y contexto compartido, evita el iframe/red innecesario y muestra `CRYPTO` como recinto en vez de NASDAQ.
4. Chromium repitió exactamente la URL que reveló el defecto: 1.689 caracteres útiles, `LINK/USD`, mercado crypto y 15m persistentes, etiqueta `CRYPTO`, desbordamiento horizontal 0 y cero errores bloqueantes. El servidor limpio no volvió a registrar consultas Yahoo para `LINKUSD`.
5. La matriz posterior cerró **24/24** en escritorio, iPad y teléfono. La regresión integral volvió a cerrar **2.400/2.400**, cero fallos y dos advertencias conocidas.
6. El chequeo operacional completo regeneró brief, calidad, snapshot y probe con el foco autónomo vigente. Después de que el mercado rotara legítimamente de SOL/USD a ETH/USD, diez ciclos sanos consecutivos dejaron `Core operativo / externo bloqueado`; gráficas e indicadores están OK, el contrato de métricas tiene 1.383 alias y el `WARN` global corresponde a Alpaca `AUTH_INVALID`, biblioteca de video y confirmación de mercado declarados.

Evidencia:

- `alerts/crypto_dual_chart_stock_runtime_guard_probe.json`
- `output/playwright/crypto_dual_chart_stock_runtime_guard.png`
- `alerts/responsive_route_matrix.json`
- `alerts/dashboard_render_probe.json`
- `alerts/roxy_realtime_check.json`
- pruebas `tests/test_canonical_routes.py`

Pruebas dirigidas de rutas/voz: **82 aprobadas**, una advertencia conocida y cero fallos. Regresión integral final: **2.400 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 124,38 segundos. Matriz responsive: **24/24 aprobada**.

## 60. Runtime modular y seguro de la gráfica profesional

1. El mayor bloque frontend restante era `render_browser_live_candle_chart_panel`: 2.129 líneas de HTML, CSS y JavaScript dentro de Python. Su documento exacto de 112.350 caracteres vive ahora en `assets/runtime/roxy_live_candle_chart.html`; el render Python bajó a 58 líneas.
2. La extracción fue mecánica y comprobó equivalencia exacta antes de escribir. Incluyendo cargador, diagnóstico y guardas nuevos, `streamlit_app.py` bajó de 48.571 a 46.537 líneas.
3. El cargador cacheado exige un marcador de payload, un marcador del bundle, raíz de gráfica, Lightweight Charts, crosshair, streaming y cierre de script. Un recurso incompleto falla explícitamente antes de mostrar una gráfica parcialmente funcional.
4. Tanto el payload de velas/contexto como el bundle local de Lightweight Charts pasan por `roxy_json_for_inline_script()`. Las pruebas introducen cierres `</script>`, scripts secundarios, ampersand y U+2028 en ambos canales y confirman que no pueden romper el documento.
5. Diagnóstico incorpora `Runtime frontend de graficas`: verifica la plantilla de 112.350 caracteres, el vendor local de 163.680, marcadores 2/2 y serialización segura. El estado vivo quedó `CONNECTED`.
6. Playwright abrió el workspace dual real con BTC/USD. Las dos gráficas cargaron 640 velas cada una, 15m/1h sincronizados, WebSocket BinanceUS, Bollinger, EMA9/21, volumen, crosshair y herramientas de dibujo. Se activó EMA20 dentro del primer iframe y el checkbox cambió a `checked` sin recarga ni error de consola.
7. La sonda automatizada del workspace obtuvo 2.509 caracteres incluyendo iframes, velas e indicadores; Diagnóstico obtuvo 6.264 caracteres y publicó el contrato. Ambas conservaron URL/estado y cero errores bloqueantes.
8. La regresión integral cerró **2.403/2.403** y la matriz responsive volvió a **24/24**. El watchdog cerró con 13 ciclos core sanos, gráficas/indicadores/probes OK y `Core operativo / externo bloqueado`; el `WARN` conserva Alpaca `AUTH_INVALID`, video pendiente y espera legítima de confirmación de mercado.

Evidencia:

- `assets/runtime/roxy_live_candle_chart.html`
- `assets/vendor/lightweight-charts.4.2.3.min.js`
- `alerts/chart_runtime_module_probe.json`
- `alerts/chart_runtime_diagnostic_probe.json`
- `output/playwright/chart_runtime_module_workspace.png`
- `output/playwright/chart_runtime_diagnostic.png`
- `alerts/responsive_route_matrix.json`
- `alerts/roxy_realtime_check.json`
- pruebas `tests/test_roxy_operational_charts.py`
- pruebas `tests/test_focused_opportunities.py`
- pruebas `tests/test_system_diagnostics.py`

Pruebas focales de gráficas, oportunidades y diagnóstico: **433 aprobadas**, una advertencia conocida y cero fallos. Regresión integral: **2.403 pruebas aprobadas**, 2 advertencias conocidas de dependencias, cero fallos y código de salida 0 en 134,84 segundos. Matriz responsive: **24/24 aprobada**.

## 61. Catálogo cripto validado y escáner BinanceUS compartido

1. La telemetría reveló cuatro errores `scanner_ohlcv` por ciclo. Las cuatro filas correspondían a `WIF/USD` en 15m/1h/2h/4h: BinanceUS publica ese activo como `WIF/USDT`. La watchlist y el instalador canónico usan ahora el par real; no se oculta el error ni se inventa una cotización USD.
2. `binanceus_symbol_coverage()` carga el catálogo vivo una vez por ejecución y produce el contrato `roxy-binanceus-symbol-coverage/1.0.0`. Informa pares solicitados, exactos, fallback USD/USDT y no soportados, además del mapa efectivo. Si el catálogo no responde, queda `PROVIDER_UNAVAILABLE` y el escáner falla abierto hacia sus peticiones normales para conservar evidencia del proveedor, no una falsa cobertura.
3. El escáner reutiliza una sola instancia rate-limited de `ccxt.binanceus` para todos los activos y temporalidades. Cada fila persistida incorpora `provider_symbol`, `symbol_resolution` y `data_source=ccxt:binanceus`.
4. La validación real recorrió 25 activos × 4 temporalidades: **100/100 filas, 25/25 pares exactos, cero no soportados y cero señales `ERROR`**. El tiempo bajó de 46,42 s a 9,92 s, aproximadamente **78,6% menos**; cada temporalidad terminó entre 2,17 y 2,24 s.
5. El siguiente ciclo del servicio continuo produjo `ma_live_strategy_crypto_20260719_102848.csv` con las mismas 100 filas, WIF/USDT en cuatro temporalidades, columnas de procedencia completas y cero errores. El ledger posterior registró 126 llamadas `scanner_ohlcv` BinanceUS con estado `OK` y ninguna con `ERROR`.
6. Diagnóstico incorpora `Cobertura de simbolos BinanceUS`, valida contrato, coherencia, vigencia y degradación. Chromium publicó `CONNECTED · 25/25 pares disponibles`, 6.358 caracteres útiles, URL/estado persistentes y cero errores bloqueantes de consola o página.
7. La regresión integral cerró **2.410/2.410** en 124,96 s. El watchdog regeneró scan, confluencia, calidad, snapshot y probes: datos live, 100 filas, temporalidades, gráficas, indicadores, servicios y contratos están OK. El `WARN` global continúa limitado a Alpaca `AUTH_INVALID`, biblioteca de video no archivada y espera legítima de confirmación de mercado.

Evidencia:

- `alerts/binanceus_symbol_coverage.json`
- `alerts/ma_live_scan_timing.json`
- `alerts/binanceus_coverage_diagnostic_probe.json`
- `output/playwright/binanceus_coverage_diagnostic.png`
- `output/ma_live_strategy_crypto_20260719_102848.csv`
- `alerts/roxy_realtime_check.json`
- pruebas `tests/test_scanner.py`
- pruebas `tests/test_ma_scan.py`
- pruebas `tests/test_system_diagnostics.py`

## 62. Runtime stock live modular y URLs protegidas

1. `render_roxy_stock_live_runtime` contenía 463 líneas de JavaScript para EventSource, snapshot, reconexión, estado de mercado y sincronización de cotizaciones. El documento evaluado exacto de 26.051 caracteres vive ahora en `assets/runtime/roxy_stock_live_runtime.js.html`; el render quedó en 17 líneas y sus cargadores/validadores suman 20 líneas adicionales.
2. La extracción conserva exactamente EventSource, snapshot, fallback, eventos `roxy-stock-quote`, atributos de fuente/frescura y estados `LIVE/LAST/RESPALDO`. `streamlit_app.py` bajó a 46.129 líneas.
3. Las URLs `ROXY_STOCK_STREAM_URL` y `ROXY_STOCK_SNAPSHOT_URL` ya no entran mediante `json.dumps` sin neutralizar caracteres de script. Ambas usan `roxy_json_for_inline_script`; una regresión inyecta `</script><script>`, ampersand y U+2028 y demuestra que no pueden cerrar el runtime ni abrir código secundario.
4. El cargador exige exactamente dos marcadores, envoltura de script, EventSource, snapshot y evento de quote. Un archivo ausente o truncado falla explícitamente. Diagnóstico incorpora `Runtime frontend stock live` y reporta plantilla, marcadores y protección de URLs por separado de la autenticación del proveedor.
5. Chromium abrió el resumen operativo AAPL con 3.162 caracteres útiles, estado/URL persistentes, proveedor visible y cero errores bloqueantes. Diagnóstico publicó el runtime como `CONNECTED` con 6.517 caracteres útiles y también cero errores de consola o página.
6. Las pruebas dirigidas de gráficas, rutas y diagnóstico cerraron 121/121. La regresión integral cerró **2.414/2.414** en 122,53 s, con sólo las dos advertencias conocidas de LibreSSL y `websockets.legacy`.

Evidencia:

- `assets/runtime/roxy_stock_live_runtime.js.html`
- `alerts/stock_live_runtime_module_probe.json`
- `alerts/stock_live_runtime_diagnostic_probe.json`
- `output/playwright/stock_live_runtime_module.png`
- `output/playwright/stock_live_runtime_diagnostic.png`
- pruebas `tests/test_roxy_operational_charts.py`
- pruebas `tests/test_system_diagnostics.py`

## 63. Runtime Academy WebGL modular y equivalencia de literales

1. `render_roxy_three_universe_runtime` contenía 406 líneas de WebGL embebido. La plantilla evaluada de 18.970 caracteres vive ahora en `assets/runtime/roxy_three_universe_runtime.js.html`; el render quedó en ocho líneas y el archivo principal bajó a 45.755 líneas.
2. El runtime conserva montaje progresivo, `MutationObserver`, canvas, movimiento reducido, fallback CSS y bundle local Three.js. El cargador cacheado valida plantilla, marcador y bundle antes de renderizar y serializa el vendor con protección de caracteres de script.
3. La primera sonda visual detectó una diferencia de equivalencia: el texto extraído desde el código fuente conservaba un nivel adicional en `\\n`, por lo que el script dinámico terminaba en `SyntaxError` al insertarse. Se corrigieron ambas plantillas nuevas usando el valor evaluado del literal Python original; esto preserva exactamente las secuencias que recibía el navegador antes de la extracción.
4. Academy repitió la prueba tras la corrección: 1.263 caracteres útiles, mapa y planeta visibles, URL/estado persistentes y cero errores de consola o página. La vista stock AAPL también se repitió para demostrar que el ajuste de equivalencia no alteró EventSource/snapshot.
5. Diagnóstico incorpora `Runtime frontend Academy WebGL` y valida plantilla, vendor, marcador y carga progresiva. La sonda conjunta publicó los runtimes stock y Academy como `CONNECTED`, con 6.643 caracteres útiles y cero errores bloqueantes.
6. La regresión integral cerró **2.417/2.417** en 119,07 s, con sólo las dos advertencias conocidas de dependencias.
7. La matriz responsive posterior cerró **24/24**. El watchdog regeneró scan, confluencia, brief, calidad, snapshot y probes: núcleo, datos cripto, gráficas, indicadores y servicios permanecen OK; el `WARN` global continúa atribuido a Alpaca `AUTH_INVALID`, biblioteca de video no archivada y espera legítima de confirmación.

Evidencia:

- `assets/runtime/roxy_three_universe_runtime.js.html`
- `alerts/three_runtime_academy_probe.json`
- `alerts/frontend_runtime_diagnostic_probe.json`
- `alerts/responsive_route_matrix.json`
- `alerts/roxy_realtime_check.json`
- `output/playwright/three_runtime_academy.png`
- `output/playwright/frontend_runtime_diagnostic.png`
- pruebas `tests/test_roxy_three_universe.py`
- pruebas `tests/test_system_diagnostics.py`

## 64. Gráfica profesional de acciones modular y contrato DOM seguro

1. `render_roxy_actions_pro_chart_panel` concentraba 778 líneas y 51.893 caracteres de HTML/CSS/JavaScript. La plantilla evaluada exacta de 50.689 caracteres vive ahora en `assets/runtime/roxy_actions_pro_chart.html`; el archivo principal bajó a 45.065 líneas.
2. El runtime conserva velas, EMA 9/21, medias 20/40, Bollinger, volumen, crosshair, escala inteligente, bandas de entrada/stop/target, estados del plan y sincronización con eventos `roxy-stock-quote`.
3. El payload y el bundle local Lightweight Charts dejaron de interpolarse con `json.dumps` directo y usan el serializador seguro compartido. El DOM id generado debe cumplir `[A-Za-z0-9_-]{1,80}`; una prueba inyecta cierre de atributo/script y confirma que se rechaza antes del render.
4. El cargador cacheado exige un marcador de payload, uno de vendor, dos de DOM id, raíz de gráfica, crosshair y sincronización de quote. Diagnóstico incorpora `Runtime grafica profesional de acciones` y valida también el bundle local.
5. Playwright cargó un documento aislado con 120 velas y el motor central de indicadores. La gráfica mostró AAPL 15m, entrada 107,50, stop 105,40, target 111,80, R/R 1:2 y volumen; los botones `Solo velas` e `Indicadores` cambiaron de estado sin recarga y con cero errores de runtime.
6. La ruta integrada AAPL 15m/1h aprobó con 2.764 caracteres útiles y estado/URL persistentes. Diagnóstico publicó el contrato como `CONNECTED` con 6.756 caracteres útiles y cero errores bloqueantes.
7. Las pruebas dirigidas cerraron 128/128. La regresión integral cerró **2.422/2.422** en 121,14 s, con sólo las dos advertencias conocidas de dependencias.

Evidencia:

- `assets/runtime/roxy_actions_pro_chart.html`
- `output/playwright/actions_pro_chart_runtime_probe.html`
- `output/playwright/actions_pro_chart_runtime_module.png`
- `alerts/actions_pro_chart_integration_probe.json`
- `alerts/actions_pro_chart_runtime_diagnostic_probe.json`
- `output/playwright/actions_pro_chart_integration.png`
- `output/playwright/actions_pro_chart_runtime_diagnostic.png`
- pruebas `tests/test_roxy_operational_charts.py`
- pruebas `tests/test_system_diagnostics.py`

## 65. Backtesting sin dominios vacíos y curva de equity local

1. La sonda de navegador de Backtesting reveló 11 advertencias únicas `empty_chart_extent`: dos en la curva de equity, dos en tasa de acierto, dos en profit factor, dos en resultados y tres en el scatter de rendimiento. Los datos persistidos eran válidos —133 operaciones legacy y 800 puntos de equity del run durable—; el problema estaba en cinco superficies Altair/Vega, no en el motor ni en la fuente.
2. La curva activa usa ahora `assets/runtime/roxy_backtest_equity_chart.html` y el bundle local Lightweight Charts 4.2.3. Conserva datos reales, fuente, temporalidad, primer/último valor, cambio, crosshair, zoom, desplazamiento y redimensionado. El payload se normaliza, deduplica y acota a 1.201 puntos conservando siempre el último; payload y vendor pasan por el serializador seguro compartido.
3. Los cuatro gráficos históricos se migraron a Plotly con entradas finitas y se movieron detrás de `Cargar comparación histórica legacy`, apagado por defecto. El usuario conserva la comparación por lotes, pero la ruta inicial ya no descarga ni renderiza visualizaciones que no pertenecen a la ejecución durable visible.
4. Diagnóstico incorpora `Runtime curva de equity backtest` y valida recurso, vendor local, marcadores, raíz, crosshair, `ResizeObserver` y serialización segura. Chromium publicó `CONNECTED`, 6.888 caracteres útiles, URL/estado persistentes y cero errores bloqueantes.
5. La ruta real LINK/USD 1h mostró 800 puntos de equity y validación temporal con cero errores de consola/página, cero `empty_chart_extent` y ningún aviso de versión Vega. El contenido inicial sin esperar texto interno del iframe quedó en 5,199 s y el recorrido en 6,340 s.
6. El perfil Python bajó de 1,402 s en `main()` a 0,312 s, aproximadamente **77,7% menos**; el shell operacional pasó de 0,608 s a 0,010 s en la muestra limpia. El archivo principal queda en 45.197 líneas después de incorporar cargador, render y diagnóstico.
7. `tools/responsive_route_matrix.py` puede ejecutarse directamente desde cualquier directorio: inserta la raíz del proyecto antes de importar el probe compartido. Una prueba subprocess evita que vuelva a depender accidentalmente de `PYTHONPATH=.`.
8. La regresión integral cerró **2.429/2.429** en 123,42 s, con sólo las advertencias conocidas de LibreSSL y `websockets.legacy`. La matriz responsive posterior volvió a cerrar **24/24** en escritorio, iPad y teléfono. El watchdog regeneró scan/confluencia con 100/25 filas, 14 gráficas sin fallos ni avisos, servicios y núcleo `OK x12`; el `WARN` global sigue limitado a Alpaca `AUTH_INVALID`, permiso del disco externo y fuentes de video todavía no archivadas.

Evidencia:

- `assets/runtime/roxy_backtest_equity_chart.html`
- `alerts/backtest_lightweight_equity_probe.json`
- `alerts/backtest_timing_lightweight_probe.json`
- `alerts/backtest_equity_runtime_diagnostic_probe.json`
- `alerts/frontend_startup_profile.json`
- `alerts/responsive_route_matrix.json`
- `alerts/roxy_realtime_check.json`
- `output/playwright/backtest_lightweight_equity_probe.png`
- `output/playwright/backtest_equity_runtime_diagnostic.png`
- pruebas `tests/test_backtests.py`
- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_responsive_route_matrix.py`

## 66. Terminal de Acciones sin identidad ni estados simulados

1. La auditoría del mayor renderer restante encontró cuatro afirmaciones no contractuales: saludo fijo a una persona, `ROXY OS 2.0`, `TradingView integrado` aunque la superficie usa Lightweight Charts, y `Finviz + Roxy AI` aunque Finviz puede no estar configurado. Se sustituyeron por contexto compartido, operación asistida, vendor local real y fuente declarada.
2. Las tarjetas de Futuros y Forex/bonos se construían siempre con listas vacías. Ahora sólo entran al DOM cuando existe al menos una fila verificada; la plataforma no reserva espacio cotidiano para módulos sin proveedor ni rellena valores de demostración.
3. El badge superior calculaba disponibilidad únicamente sobre `rows`, aunque las cotizaciones visibles podían proceder de la selección, Finviz/pulse o del refresco servidor. La evaluación inicial considera todas las filas consumidoras y el runtime actualiza `data-roxy-stock-provider-state` y `data-roxy-stock-market-state` desde el mismo evento que actualiza el precio.
4. El runtime modular EventSource/snapshot y el refresco servidor comparten los nuevos selectores. Fuente, frescura, hora y sesión quedan en texto/título; un mercado cerrado muestra el último precio real y no finge ticks live.
5. Chromium abrió AAPL 15m en la ruta integrada: publicó `Alpaca IEX REST` y `Mercado cerrado · ultimo precio real`, eliminó `Catalogo sin precio`, `TradingView integrado` y la tarjeta Forex vacía, conservó 3.024 caracteres útiles y estado/URL, con cero errores bloqueantes.
6. Las pruebas dirigidas de rutas, terminal y diagnóstico cerraron 138/138. La regresión integral cerró **2.430/2.430** en 121,19 s, con sólo las dos advertencias conocidas de dependencias.

Evidencia:

- `alerts/actions_truthful_surface_probe.json`
- `alerts/actions_provider_state_probe.json`
- `output/playwright/actions_truthful_surface.png`
- `output/playwright/actions_provider_state.png`
- `assets/runtime/roxy_stock_live_runtime.js.html`
- pruebas `tests/test_roxy_operational_charts.py`
- pruebas `tests/test_canonical_routes.py`
- pruebas `tests/test_system_diagnostics.py`

## 67. Refresco servidor stock modular y payload protegido

1. `render_roxy_stock_server_refresh` conservaba 207 líneas de JavaScript dentro de su fragmento Python, a pesar de que el bridge EventSource ya estaba modularizado. El documento evaluado exacto de 12.539 caracteres vive ahora en `assets/runtime/roxy_stock_server_refresh.js.html`; el renderer queda dedicado a reunir cotizaciones verificadas y programar el fragmento.
2. El cargador cacheado exige un único marcador de payload, cierre de script, precio, estado de proveedor, evento `roxy-stock-quote`, actualización de metadatos y estado del trade. Un recurso ausente, truncado o con marcadores duplicados falla explícitamente.
3. Las cotizaciones dejaron de interpolarse con `json.dumps` directo. `roxy_stock_server_refresh_runtime_markup()` usa el serializador común; la regresión inyecta cierre de script, script secundario, ampersand y U+2028 dentro de `source` y demuestra que permanecen como datos.
4. Diagnóstico amplió `Runtime frontend stock live` para validar conjuntamente stream y refresh: 26.285 + 12.539 caracteres, tres marcadores y URLs/cotizaciones protegidas. Chromium publicó el contrato como `CONNECTED` con 6.957 caracteres útiles y cero errores bloqueantes.
5. La ruta integrada de Acciones volvió a actualizar fuente efectiva y sesión desde el recurso extraído. En ejecuciones consecutivas mostró legítimamente Alpaca IEX y luego `yfinance currentPrice`, siempre `Mercado cerrado · ultimo precio real`; esto prueba que el badge no está fijado a un proveedor.
6. `streamlit_app.py` bajó de 45.215 a 45.065 líneas. Las pruebas dirigidas cerraron 112/112 y la regresión integral **2.432/2.432** en 129,41 s, con sólo las dos advertencias conocidas de dependencias.

Evidencia:

- `assets/runtime/roxy_stock_server_refresh.js.html`
- `alerts/stock_server_refresh_module_probe.json`
- `alerts/stock_server_refresh_diagnostic_probe.json`
- `output/playwright/stock_server_refresh_module.png`
- `output/playwright/stock_server_refresh_diagnostic.png`
- pruebas `tests/test_roxy_operational_charts.py`
- pruebas `tests/test_system_diagnostics.py`

## 68. Presentación del terminal de Acciones separada de la lógica

1. `render_roxy_actions_reference_market_terminal` mezclaba la preparación de datos con 537 líneas de CSS/HTML dentro de un `f-string`. La plantilla evaluada de 30.593 caracteres (30.609 bytes UTF-8) vive ahora en `assets/runtime/roxy_actions_reference_terminal.html`; el renderer bajó de 1.213 a 731 líneas.
2. La frontera entre lógica y presentación queda representada por 33 slots explícitos: navegación, estado/fuente, pestaña, gráficas, IA, escáner, mapa, movers, noticias, activo, niveles, alertas, watchlist, estrategia y barra operativa. El cargador cacheado exige cada slot exactamente una vez y valida la estructura principal antes de renderizar.
3. `roxy_actions_reference_terminal_markup()` rechaza slots faltantes o inesperados y sustituye todos en una sola pasada. Así, contenido que coincida accidentalmente con el nombre de otro marcador no inicia una segunda interpolación.
4. Diagnóstico incorpora `Presentacion terminal de Acciones`: valida recurso, 33/33 marcadores, estilos, terminal, top strip, fila de gráficas, grid, estrategia y cargador. Chromium publicó `CONNECTED · plantilla 30.593 caracteres · marcadores 33/33 · carga cacheada y slots completos` con 7.045 caracteres útiles y cero errores bloqueantes.
5. La ruta real AAPL 15m conservó 3.030 caracteres útiles, proveedor/sesión, URLs y estado persistentes, sin marcadores visibles ni textos de vendor falsos. Playwright CLI abrió además un documento aislado con los 33 slots: navegación, 15m/1h, fuente, alertas, watchlist y estrategia quedaron presentes, con cero errores y cero warnings de consola.
6. `streamlit_app.py` queda en 44.668 líneas, 397 menos que antes del bloque aun incluyendo cargador, contratos y diagnóstico. Las pruebas dirigidas cerraron 144/144; la regresión integral cerró **2.436/2.436** en 120,76 s.
7. La matriz responsive posterior cerró **24/24** en escritorio, iPad y teléfono. El watchdog regenerado mantiene núcleo `OK x17`; el `WARN` global sigue limitado a Alpaca `AUTH_INVALID`, permiso del disco externo y fuentes de video pendientes de archivo.

Evidencia:

- `assets/runtime/roxy_actions_reference_terminal.html`
- `alerts/actions_reference_terminal_module_probe.json`
- `alerts/actions_reference_terminal_diagnostic_probe.json`
- `alerts/responsive_route_matrix.json`
- `alerts/roxy_realtime_check.json`
- `output/playwright/actions_reference_terminal_module.png`
- `output/playwright/actions_reference_terminal_diagnostic.png`
- `output/playwright/actions_reference_terminal_isolated.html`
- `output/playwright/actions_reference_terminal_isolated.png`
- pruebas `tests/test_roxy_operational_charts.py`
- pruebas `tests/test_strategy_separation.py`
- pruebas `tests/test_system_diagnostics.py`

## 69. Objetivos explícitos y contrato central de gráficas

1. La auditoría de `build_professional_price_chart` y `build_chart_level_plan` encontró una divergencia funcional: si existía entrada pero faltaba target, ambas superficies generaban silenciosamente +2%, +5% y +10%. Esos niveles alimentaban líneas, zonas de recompensa, R/R, badges y estados como si procedieran del motor.
2. `explicit_chart_target_rows()` es ahora el único recolector para ambas superficies. Acepta `target_ladder` y campos de target ya presentes en brief, confluencia o setup; normaliza valores finitos/positivos, deduplica por precio y conserva procedencia exacta.
3. Se retiraron los tres objetivos implícitos. Sin target provisto no aparece línea, zona de recompensa, distancia a target, R/R ni estado de objetivo. Los tests demuestran tanto ausencia total como representación correcta cuando el brief incluye explícitamente 2%, 5% y 10%.
4. Los targets explícitos de confluencia dejaron de dibujarse dos veces con etiquetas diferentes. Cualquier etiqueta que empiece por `Objetivo` recibe línea y texto visibles, incluidos objetivo recomendado, técnico o target 1.
5. Diagnóstico incorpora `Contrato de datos de graficas`: exige el recolector compartido, procedencia, normalización finita y ausencia de `.rolling()`/`.ewm()` dentro de los renderers. Una regresión dedicada reintroduce multiplicadores implícitos y confirma estado `ERROR`.
6. La primera sonda del diagnóstico reveló un problema de rendimiento en el propio chequeo: extraía texto de unas 740 funciones aunque necesitaba cinco y dejaba la ruta incompleta. Se limitó a cinco nodos AST y cortes directos por líneas; la ejecución aislada bajó a 2,3 s y queda cacheada por metadatos.
7. Tras reiniciar el servicio, Diagnóstico publicó `CONNECTED · objetivos explícitos con procedencia · indicadores centrales sin rolling/ewm local · OHLCV finito` con 7.188 caracteres útiles. La ruta AAPL 15m/1h conservó 2.764 caracteres, estado/URL y cero errores bloqueantes.
8. Pruebas focales de gráficas, indicadores, oportunidades y diagnóstico: **467/467**. Regresión integral: **2.440/2.440** en 143,85 s, dos advertencias conocidas y cero fallos. El watchdog posterior mantiene núcleo `OK x19`; el `WARN` global continúa externo.

Evidencia:

- `alerts/professional_chart_data_contract_probe.json`
- `alerts/professional_chart_explicit_targets_probe.json`
- `output/playwright/professional_chart_data_contract.png`
- `output/playwright/professional_chart_explicit_targets.png`
- `alerts/roxy_realtime_check.json`
- pruebas `tests/test_focused_opportunities.py`
- pruebas `tests/test_indicator_engine.py`
- pruebas `tests/test_system_diagnostics.py`

## 70. Semántica direccional LONG/SHORT en gráficas

1. La gráfica profesional ya no interpreta toda oportunidad como LONG. `chart_trade_direction()` normaliza señales explícitas (`LONG/BUY/CALL/ALCISTA` y `SHORT/SELL/PUT/BAJISTA`) y, si faltan, utiliza únicamente geometría coherente de stop y objetivos como respaldo.
2. Las zonas de riesgo y recompensa son direccionales: un SHORT admite stop por encima de la entrada y objetivo por debajo; los límites visuales siempre se ordenan sin alterar el significado operativo.
3. Las distancias mostradas también respetan la dirección. En SHORT, caer hacia el target produce porcentaje positivo y subir hacia el stop produce porcentaje negativo. La selección del objetivo activo usa el nivel direccional más cercano, no el precio máximo indiscriminadamente.
4. La fila de estado que alimenta la gráfica conserva `trade_direction`, por lo que el consumidor puede auditar si interpreta LONG o SHORT junto con entrada, stop, objetivo y R/R.
5. `Contrato de datos de graficas` exige ahora la función direccional y sus reglas SHORT; si desaparecen, el panel técnico cambia a `ERROR`.
6. La regresión dedicada usa entrada 100, stop 105, objetivo 95 y precio actual 98. Verifica `SHORT`, stop `-7,1%`, objetivo `+3,1%`, R/R `1,00` y zona de recompensa 95–100.
7. Pruebas focales ampliadas: **470/470**. En navegador real, Diagnóstico publicó `CONNECTED · LONG/SHORT normalizado` con 7.213 caracteres; la ruta de análisis AAPL conservó ambas temporalidades y no produjo errores ni advertencias de consola.
8. Regresión integral posterior: **2.441/2.441** en 126,64 s, con dos advertencias conocidas de dependencias y cero fallos.

Evidencia:

- `alerts/professional_chart_directional_diagnostic_probe.json`
- `alerts/professional_chart_directional_actions_probe.json`
- pruebas `tests/test_focused_opportunities.py`
- pruebas `tests/test_system_diagnostics.py`

## 71. Streaming fiel para 20m y 30m

1. El barrido de temporalidades encontró que la interfaz aceptaba 20m y 30m, pero `chart_stream_binance_interval()` no los reconocía y enviaba ambos al valor por defecto 1h. El histórico sí derivaba esos periodos correctamente, por lo que una gráfica podía mezclar historia 20m con actualizaciones vivas 1h.
2. El contrato de streaming ahora separa intervalo visible, intervalo de origen y agregación. 30m usa el kline 30m nativo de BinanceUS; 20m consume klines reales de 5m y agrupa cuatro velas en el navegador.
3. El agregador conserva apertura de la primera vela, máximo, mínimo, último cierre y suma de volumen. Mantiene cada kline 5m por timestamp y reemplaza sus actualizaciones acumulativas, evitando contar varias veces el volumen de una vela activa.
4. El ticker de dos segundos sigue actualizando el bucket visible de 20m con baja latencia; el REST de klines continúa siendo respaldo y reconstrucción. El payload declara `WEBSOCKET_DERIVED_MARKET_STREAM`, `derivedFrom=5m`, intervalos de fuente/destino y proveedor `5m→20m`.
5. La pareja de gráficas ya conserva selecciones 20m y 30m: contexto 1h a la izquierda y el periodo solicitado a la derecha. Antes ambos caían silenciosamente en la pareja 1h/15m.
6. El diagnóstico `Runtime frontend de graficas` exige ahora el agregador, mapa de velas fuente, campos de agregación y mapeos 20m/30m. Publica `20m derivado de 5m y 30m nativo` sólo cuando todo el contrato está presente.
7. Chromium real abrió BTC/USD 20m, conservó URL/estado, mostró `DATOS REALES BINANCEUS WEBSOCKET 5M→20M + REST FALLBACK`, produjo 2.349 caracteres útiles y cero errores bloqueantes. La inspección visual confirmó velas, indicadores, volumen y estado del proveedor.
8. Pruebas focales: **474/474**. Regresión integral: **2.443/2.443** en 121,20 s, dos advertencias conocidas y cero fallos.

Evidencia:

- `alerts/chart_derived_timeframe_diagnostic_probe.json`
- `alerts/chart_20m_live_runtime_probe.json`
- `output/playwright/chart_20m_live_runtime.png`
- pruebas `tests/test_requested_timeframes.py`
- pruebas `tests/test_focused_opportunities.py`
- pruebas `tests/test_system_diagnostics.py`

## 72. Selector completo y etiquetas técnicas veraces en Inicio

1. La gráfica principal de Inicio aceptaba una temporalidad 20m por URL/estado, pero sólo ofrecía enlaces para 1m, 5m, 15m, 1h, 1d y 1w. Faltaban 20m, 30m, 2h y 4h, por lo que el usuario no podía recorrer desde esa superficie todos los periodos declarados por Roxy.
2. La misma gráfica dibujaba las series `SMA20` y `SMA40` del payload central, pero sus etiquetas visibles decían `EMA 20` y `EMA 40`. Los estados sin datos incluso anunciaban `EMA 21` y `EMA 50` sin una serie renderizada.
3. Los estados real, cargando y esperando historial comparten ahora `TIMEFRAME_OPTIONS`, el catálogo canónico de diez periodos. Cada control conserva símbolo, mercado y periodo en URL; el periodo activo se marca por coincidencia exacta.
4. Los indicadores visibles declaran correctamente `EMA 9`, `SMA 20`, `SMA 40`, `BB 20 2` y volumen. La corrección no altera fórmulas: sólo alinea la presentación con las columnas centrales que realmente se dibujan.
5. El contenedor cambió de `overflow:hidden` a distribución flexible con salto de línea, evitando que los cuatro controles añadidos queden ocultos en anchos pequeños.
6. Chromium real validó BTC/USD 20m en 1.440×1.000 y 390×844. Ambas vistas muestran los diez periodos, SMA 20/40, conservan 20m, registran desbordamiento horizontal 0 y cero errores bloqueantes. La captura móvil confirma que 20m queda activo y todos los botones son legibles.
7. Pruebas focales de frontend/gráficas: **474/474**. Regresión integral: **2.445/2.445** en 123,39 s, dos advertencias conocidas y cero fallos.

Evidencia:

- `alerts/home_chart_full_timeframes_desktop_probe.json`
- `alerts/home_chart_full_timeframes_phone_probe.json`
- `output/playwright/home_chart_full_timeframes_desktop.png`
- `output/playwright/home_chart_full_timeframes_phone.png`
- pruebas `tests/test_focused_opportunities.py`

## 73. EMA50/EMA200 y periodos completos en la gráfica interactiva

1. El motor de estrategias ya utilizaba EMA50, pero el runtime profesional sólo permitía EMA9/20/21; EMA200 tampoco estaba disponible. Esto impedía inspeccionar en la gráfica dos indicadores exigidos por el contrato funcional aunque la fórmula central existiera.
2. `live_candle_chart_payload()` completa ahora EMA9, EMA20, EMA21, EMA50 y EMA200 mediante `exponential_moving_average()` del motor central cuando la columna no viene enriquecida. No existe un cálculo JavaScript alterno.
3. El payload incorpora series, colores y estado persistible para EMA50/200. Permanecen opcionales en la vista limpia, el preset Completo activa ambas, Crypto 2H activa EMA50 y Crypto Daily activa EMA200.
4. El runtime añade controles EMA50 y EMA200 y da mayor grosor a las medias 200. Los settings continúan aislados por usuario/símbolo/temporalidad/perfil.
5. Los botones rápidos del iframe también cubren ahora los diez periodos canónicos. Antes repetían la omisión de 20m, 30m, 2h y 4h encontrada en Inicio.
6. `Runtime frontend de graficas` exige los seis controles nuevos y publica `EMA50/200 disponibles`; una plantilla parcial cambia a `ERROR`.
7. Chromium real validó el workspace con EMA50, EMA200, 20m, 30m, 2h y 4h dentro de los iframes: 2.745 caracteres, URL/estado persistentes y cero errores bloqueantes. Diagnóstico publicó el contrato con 7.308 caracteres y cero fallos de consola/página.
8. Pruebas focales: **477/477**. Regresión integral: **2.446/2.446** en 124,36 s, dos advertencias conocidas y cero fallos.

Evidencia:

- `alerts/live_chart_ema_long_controls_probe.json`
- `alerts/live_chart_ema_long_diagnostic_probe.json`
- `output/playwright/live_chart_ema_long_controls.png`
- pruebas `tests/test_focused_opportunities.py`
- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_indicator_engine.py`

## 74. Payload técnico central para RSI, MACD, ATR, VWAP y RVol

1. La auditoría confirmó que la gráfica profesional Altair ya dibuja paneles RSI14 y MACD histograma, con zonas 30/70, línea cero, estado y tooltips. Sin embargo, el runtime Lightweight Charts dependía de columnas preenriquecidas y no garantizaba el mismo conjunto técnico.
2. `live_candle_chart_payload()` ejecuta ahora una única llamada a `add_central_indicators()` sobre la ventana OHLCV limpia. Ese pase produce SMA/EMA, RSI Wilder, MACD 12/26/9, ATR Wilder, Bollinger, VWAP por sesión, volumen promedio y volumen relativo con el contrato `roxy-indicators/1.1.0`.
3. El payload expone series completas `RSI14`, `MACD`, `MACD Signal` y `MACD Hist`, además de métricas actuales RSI, MACD, ATR/ATR%, VWAP y RVol. Cada valor incluye la versión del motor que lo calculó.
4. VWAP se añadió como overlay configurable al chart live y queda activo en vistas intradía. La vista diaria lo mantiene desactivado por defecto porque su VWAP reinicia por sesión, pero el usuario puede activarlo.
5. El pie operativo del runtime muestra valores reales de RSI, MACD histograma, ATR absoluto/porcentual, VWAP y RVol. Los estados sin cálculo usan `--`; la sonda real rechaza expresamente esos cinco marcadores vacíos.
6. Una regresión previa esperaba eliminar una EMA9 corrupta suministrada por un proveedor. Con el pase central, Roxy la reconstruye desde cierres reales; la prueba exige ahora una línea reparada dentro del régimen de precios y conserva el filtro de dominio.
7. `Runtime frontend de graficas` exige pase central, payload de osciladores/métricas, control VWAP y lectura técnica. Chromium publicó 2.718 caracteres en el workspace y 7.328 en Diagnóstico, con valores no vacíos y cero errores bloqueantes.
8. Pruebas focales: **477/477**. Regresión integral: **2.446/2.446** en 125,98 s, dos advertencias conocidas y cero fallos.

Evidencia:

- `alerts/live_chart_central_technicals_probe.json`
- `alerts/live_chart_central_technicals_values_probe.json`
- `alerts/live_chart_central_technicals_diagnostic_probe.json`
- `output/playwright/live_chart_central_technicals.png`
- pruebas `tests/test_indicator_engine.py`
- pruebas `tests/test_focused_opportunities.py`
- pruebas `tests/test_roxy_operational_charts.py`
- pruebas `tests/test_system_diagnostics.py`

## 75. Paneles RSI/MACD sincronizados en Lightweight Charts

1. El runtime interactivo ya no limita RSI/MACD a una lectura textual. Incorpora dos paneles Lightweight Charts dentro del mismo documento que las velas: RSI14 y MACD 12/26/9.
2. RSI usa la serie Wilder calculada por el motor central, escala fija 0–100 y líneas visibles 30/70 para sobreventa/sobrecompra. MACD presenta línea principal, señal y barras verdes/rojas del histograma alrededor de cero.
3. El chart principal propaga cada cambio de rango visible a ambos paneles mediante `subscribeVisibleTimeRangeChange`; zoom, pan y selección de rango mantienen alineadas las fechas sin recalcular valores.
4. RSI y MACD son configurables desde checkboxes y participan en los presets: `Solo velas` los oculta, `Limpio` y `Completo` los muestran. El estado persiste con el resto de settings del símbolo/temporalidad/perfil.
5. El layout reserva altura propia para los osciladores sin cubrir precio, volumen, dibujos ni niveles. En teléfono se apilan verticalmente dentro del iframe; la página externa conserva desbordamiento horizontal cero.
6. La captura de escritorio confirma 640 velas reales, VWAP, volumen, RSI 51,7, líneas 30/70 y MACD con línea/señal/histograma. Los valores técnicos del pie coinciden con el mismo payload central.
7. Diagnóstico exige DOM de ambos paneles y sincronización temporal. Chromium cerró escritorio con 3.087 caracteres, teléfono con 3.115 y Diagnóstico con 7.349; las tres rutas tuvieron cero errores bloqueantes, cero warnings bloqueantes y URL/estado persistentes.
8. Pruebas focales: **478/478**. Regresión integral: **2.447/2.447** en 123,89 s, dos advertencias conocidas y cero fallos.

Evidencia:

- `alerts/live_chart_oscillator_panels_desktop_probe.json`
- `alerts/live_chart_oscillator_panels_phone_probe.json`
- `alerts/live_chart_oscillator_panels_diagnostic_probe.json`
- `output/playwright/live_chart_oscillator_panels_desktop.png`
- `output/playwright/live_chart_oscillator_panels_phone.png`
- pruebas `tests/test_focused_opportunities.py`
- pruebas `tests/test_system_diagnostics.py`

## 76. Cuenta regresiva de vela y sesiones extendidas explícitas

1. La gráfica recibe ahora un contrato de sesión separado de la cotización. Distingue horario programado, apertura regular informada por el proveedor y sesión observada de la última vela; un reloj de premercado no se presenta como mercado regular abierto.
2. Para acciones intradía, el contrato declara que el historial solicita horario extendido y clasifica cada última vela como `Premarket`, `Regular`, `After-hours` o fuera de sesión usando `America/New_York`. La base del estado queda visible y no pretende resolver feriados sin confirmación del proveedor.
3. Para cripto, el contrato declara sesión 24h y habilita la cuenta regresiva contra el inicio real de la última vela más el intervalo solicitado. Esto también conserva los periodos derivados, incluido 20m desde velas reales de 5m.
4. El runtime actualiza el contador cada segundo. Una vela vigente muestra sesión, temporalidad y tiempo restante; una vela vencida muestra `esperando proveedor` y una sesión cerrada muestra la sesión de la última vela en vez de reiniciar un contador ficticio.
5. Un `market_open=false` durante horario regular bloquea la cuenta regresiva como `PROVIDER_MARKET_CLOSED`; durante premercado o after-hours permanece identificado como horario extendido, no como streaming regular.
6. `Runtime frontend de graficas` exige el DOM y la función del contador, además del contrato de sesión generado por el backend.
7. Chromium verificó BTC/USD 15m en escritorio y teléfono con contador 24h, y AAPL 15m cerrado con última sesión de vela. Las tres sondas conservaron símbolo/mercado/temporalidad y tuvieron cero errores de consola bloqueantes, cero warnings bloqueantes y cero errores de página.
8. Pruebas focales: **120/120**, incluido premercado frente a cierre reportado por proveedor y el contrato 24h de cripto. Regresión integral oficial: **2.449/2.449** en 121,05 s, con dos advertencias conocidas de dependencias y cero fallos.

Evidencia:

- `alerts/live_chart_candle_countdown_crypto_probe.json`
- `alerts/live_chart_session_closed_stock_probe.json`
- `alerts/live_chart_candle_countdown_phone_probe.json`
- `output/playwright/live_chart_candle_countdown_crypto.png`
- `output/playwright/live_chart_session_closed_stock.png`
- `output/playwright/live_chart_candle_countdown_phone.png`
- pruebas `tests/test_roxy_operational_charts.py`
- pruebas `tests/test_system_diagnostics.py`

## 77. Identidad visual por vela para horario extendido

1. Cada vela intradía de acciones incorpora ahora `sessionPhase`, calculado desde su timestamp real en `America/New_York`: `PREMARKET`, `REGULAR`, `AFTER_HOURS` u `OFF_SESSION`.
2. El runtime conserva el relleno verde/rojo como dirección de precio. Sólo el borde y la mecha cambian: azul sobrio para premercado y ámbar para after-hours; la sesión regular mantiene el color direccional. No se alteran OHLC, volumen, indicadores ni escalas.
3. Una leyenda visible declara exactamente esa semántica. El payload también publica colores, estado habilitado y base visual para evitar que el frontend invente una clasificación propia.
4. La visualización sólo se activa para acciones intradía. Cripto conserva su semántica 24h y la sonda rechaza expresamente la leyenda PRE/POST en BTC/USD.
5. La captura AAPL 15m confirma bordes azules y ámbar alrededor de velas extendidas junto a velas regulares direccionales. Escritorio y teléfono conservaron URL/estado, contenido útil y cero errores bloqueantes de consola, warning o página.
6. Diagnóstico exige el clasificador backend, contrato visual, decorador frontend y leyenda; una plantilla parcial cambia a `ERROR`.
7. Pruebas focales: **121/121**, incluida una serie determinista con vela premarket, regular y after-hours. Regresión integral: **2.450/2.450** en 120,49 s, dos advertencias conocidas de dependencias y cero fallos.

Evidencia:

- `alerts/live_chart_extended_session_visual_probe.json`
- `alerts/live_chart_extended_session_visual_phone_probe.json`
- `alerts/live_chart_crypto_no_stock_session_visual_probe.json`
- `output/playwright/live_chart_extended_session_visual.png`
- `output/playwright/live_chart_extended_session_visual_phone.png`
- `output/playwright/live_chart_crypto_no_stock_session_visual.png`
- pruebas `tests/test_roxy_operational_charts.py`
- pruebas `tests/test_system_diagnostics.py`

## 78. Escala automática/manual y viewport durable

1. El control ambiguo `Escala` se convirtió en `Escala auto`. Activado aplica el dominio robusto de las velas visibles y `autoScale=true`; desactivado cambia realmente el eje a `manual-axis`, permitiendo arrastrarlo sin que cada tick live reactive el autoajuste.
2. El preset Completo conserva autoescala por defecto. El modo manual sólo se activa por decisión explícita y su checkbox persiste con los indicadores por símbolo, temporalidad y perfil.
3. Zoom, pan y botones 1D/1W/1M/3M/1Y/ALL guardan una ventana `{from,to}` validada. El almacenamiento local está aislado por símbolo y temporalidad y rechaza rangos invertidos, no finitos o mayores de diez años.
4. Al recargar, el runtime recorta el viewport guardado contra los límites reales del historial y sólo lo restaura si contiene al menos diez velas; un estado inválido vuelve al rango operativo recomendado.
5. La sincronización explícita de gráfica incluye ahora el viewport. `ChartStateStore` versión 2 lo sanea, persiste por usuario/símbolo/mercado/temporalidad y lo devuelve junto con settings y dibujos para restauración entre dispositivos.
6. Playwright seleccionó 1M en BTC/USD 15m, observó `{from:1783905300,to:1784480400}`, recargó y confirmó exactamente el mismo rango. Después desactivó autoescala, esperó ticks BinanceUS y verificó `manual-axis`, checkbox desmarcado y setting durable.
7. La sonda de workspace publicó 3.096 caracteres y Diagnóstico 7.441; ambas conservaron URL/estado y registraron cero errores o warnings bloqueantes y cero errores de página.
8. Pruebas focales: **127/127**. Regresión integral: **2.451/2.451** en 124,36 s, dos advertencias conocidas de dependencias y cero fallos.

Evidencia:

- `alerts/live_chart_viewport_persistence_probe.json`
- `alerts/live_chart_viewport_render_probe.json`
- `alerts/live_chart_viewport_diagnostic_probe.json`
- `output/playwright/live_chart_viewport_manual_scale.png`
- `output/playwright/live_chart_viewport_render.png`
- `output/playwright/live_chart_viewport_diagnostic.png`
- pruebas `tests/test_chart_state.py`
- pruebas `tests/test_roxy_operational_charts.py`
- pruebas `tests/test_system_diagnostics.py`

## 79. Alertas técnicas durables con monitor verificable

1. El almacén durable admite cinco reglas reales: precio por encima/debajo, cruce EMA alcista/bajista y volumen relativo por encima de un umbral. Los cruces exigen una transición entre las dos últimas velas; no se activan sólo porque una media ya esté por encima de otra.
2. El monitor recurrente usa el contrato `roxy-durable-alert-monitor/2.0.0`. Para reglas técnicas solicita OHLCV normalizado, ejecuta el motor central `roxy-indicators/1.1.0` y rechaza velas incompletas, viejas, públicas no operativas o sin proveedor verificable.
3. Las acciones requieren `BROKER_DATA` o `PREMIUM_DATA`; un fallback público queda explícitamente bloqueado. Cripto puede evaluar con velas reales del exchange. Una carencia se registra por regla sin contaminar otras reglas del mismo símbolo.
4. La gráfica sincronizada y el panel completo de Alertas crean reglas EMA9/21 y RVol con símbolo, mercado y temporalidad visibles. Todas se almacenan en la misma watchlist durable y comparten etiquetas y estados.
5. La voz usa exactamente ese mismo contexto: “avísame cuando EMA9 cruce sobre EMA21” y “notifica si el volumen relativo supera 1,5” crean reglas para el activo y timeframe visibles, con `source=voice_command`.
6. Las actualizaciones sólo de cotización no fingen haber evaluado una regla EMA/RVol. Los registros legacy malformados se aíslan para que no derriben la creación de reglas nuevas.
7. Una sonda real creó dos reglas temporales BTC/USD 15m y las evaluó con cotización y velas BinanceUS: 2 evaluables, 0 bloqueadas y 0 activadas porque ninguna condición ocurrió durante la ejecución. Las transiciones de activación se cubren con series deterministas en pruebas.
8. Chromium verificó workspace, panel completo, teléfono y Diagnóstico con cero errores o warnings bloqueantes. Diagnóstico publica el contrato v2 y declara cobertura de precio, cruces EMA y volumen relativo.
9. Regresión integral: **2.463/2.463** en 129,42 s, con dos advertencias conocidas de dependencias y cero fallos.

Evidencia:

- `alerts/technical_alert_monitor_live_probe.json`
- `alerts/technical_alert_chart_workspace_probe.json`
- `alerts/technical_alert_full_panel_probe.json`
- `alerts/technical_alert_chart_phone_probe.json`
- `alerts/technical_alert_diagnostic_probe.json`
- `output/playwright/technical_alert_chart_workspace.png`
- `output/playwright/technical_alert_full_panel.png`
- `output/playwright/technical_alert_chart_phone.png`
- `output/playwright/technical_alert_diagnostic.png`
- pruebas `tests/test_watchlists.py`
- pruebas `tests/test_alert_monitor.py`

- pruebas `tests/test_system_diagnostics.py`

## 80. Ciclo de vida, expiración y entrega reintentable de alertas

1. Cada regla nueva tiene una vigencia UTC explícita. El panel permite 24 horas, 7, 30 o 90 días; la gráfica permite 24 horas, 7 o 30 días. Precio conserva 30 días por defecto y reglas técnicas 7 días cuando se crean por voz o API sin preferencia adicional.
2. Antes de solicitar cotizaciones, el monitor marca `Expirada` toda regla `Activa` cuyo `expires_at` terminó. Conserva `expired_at`, detalle, historial y botón de archivo, pero la retira del inventario evaluable para no consumir APIs.
3. Una activación queda primero con `notification_status=PENDING`. Entrega exitosa o registro local cambia a `DELIVERED`; un fallo pasa a `RETRY_PENDING` y el siguiente ciclo reintenta sin volver a consultar mercado ni recalcular la señal.
4. Después de diez intentos fallidos queda `DELIVERY_FAILED`, visible en Diagnóstico como fallo permanente hasta revisión o archivo. El reporte separa activas, evaluadas, activadas, expiradas, entregas pendientes, fallos del ciclo y fallos permanentes.
5. Las alertas legacy ya activadas que no tenían contrato de entrega no se reenvían automáticamente. Esto evita duplicar notificaciones históricas al desplegar la mejora.
6. La interfaz muestra vigencia, vencimiento, estado de entrega e intentos. Los resúmenes denominados “alertas activas” filtran sólo `Activa`; `Activada` y `Expirada` siguen disponibles en el panel durable hasta archivo manual.
7. El monitor real evaluó una regla activa con BinanceUS y publicó: 1 activa, 1 evaluada, 0 bloqueadas, 0 activadas nuevas, 0 expiradas, 0 pendientes y 0 fallos. Chromium verificó panel y Diagnóstico con URL/estado persistentes y cero errores bloqueantes.
8. Regresión integral: **2.468/2.468** en 120,81 s, con dos advertencias conocidas de dependencias y cero fallos.

Evidencia:

- `alerts/price_alert_monitor.json`
- `alerts/alert_lifecycle_panel_probe.json`
- `alerts/alert_lifecycle_diagnostic_probe.json`
- `output/playwright/alert_lifecycle_panel.png`
- `output/playwright/alert_lifecycle_diagnostic.png`
- pruebas `tests/test_watchlists.py`
- pruebas `tests/test_alert_monitor.py`
- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_roxy_realtime_check.py`

## 81. Parámetros EMA configurables en gráfica, panel, voz y monitor

1. El panel completo y el expander de la gráfica ya no fijan visualmente EMA9/21. Ambos permiten una media rápida de 2–200 y una lenta de 3–400; el almacén exige `rápida < lenta <= 400` antes de crear la regla.
2. Las etiquetas y botones reflejan los valores actuales. La regla durable conserva `fast_period` y `slow_period`, el monitor los entrega al cargador OHLCV y el motor central calcula exactamente esas EMA.
3. La voz ya compartía este contrato y reconoce pares explícitos, por ejemplo “EMA12 cruce debajo de EMA34”; por tanto gráfica, panel y voz producen el mismo registro y no fórmulas paralelas.
4. Chromium verificó el panel abierto y, mediante interacción real, abrió el expander colapsado de BTC/USD 15m. Encontró los controles `EMA rápida=9`, `EMA lenta=21` y RVol 1,50 con cero errores de consola.
5. La prueba durable crea EMA12/34 en 2h y confirma que persistencia y etiqueta devuelven exactamente `EMA12 cruza debajo de EMA34 · 2h`.
6. Regresión integral: **2.469/2.469** en 124,82 s, con dos advertencias conocidas de dependencias y cero fallos.

Evidencia:

- `alerts/configurable_alert_parameters_panel_probe.json`
- `alerts/configurable_alert_parameters_chart_interactive_probe.json`
- `output/playwright/configurable_alert_parameters_panel.png`
- `output/playwright/configurable_alert_parameters_chart_expanded.png`
- pruebas `tests/test_watchlists.py`
- pruebas `tests/test_alert_monitor.py`

## 82. Sincronización multidispositivo sin retroceso del monitor

1. `replace_user_snapshot` normaliza identidad de cada regla y rechaza tipos, símbolos o identificadores inválidos antes de aceptar un snapshot remoto.
2. Para una regla ya existente, el servidor conserva como autoridad los campos autónomos: activación, expiración, última evaluación, fuente, frescura, indicadores observados, monitor y todo el estado de entrega.
3. Un dispositivo todavía puede archivar explícitamente una regla y crear una nueva regla `Activa`, pero no puede fabricar que una regla nueva ya fue `Activada` o `Expirada`.
4. La protección cubre un conflicto que la revisión general no detectaba: `DELIVERED` no incrementa la revisión de edición. La prueba captura un snapshot `PENDING`, registra entrega en servidor con la misma revisión, reaplica el snapshot antiguo y confirma que permanecen `DELIVERED`, intento y `notified_at`.
5. Watchlists administradas y archivo de oportunidades conservan las protecciones multidispositivo existentes; esta mejora sólo agrega autoridad del monitor sobre telemetría de alertas.
6. Regresión integral: **2.470/2.470** en 125,65 s, con dos advertencias conocidas de dependencias y cero fallos.

Evidencia:

- pruebas `tests/test_device_sync.py`
- pruebas `tests/test_watchlists.py`
- pruebas `tests/test_alert_monitor.py`

## 83. Coherencia oportunidad–watchlist–voz y frescura del contexto

1. La voz ya no reutiliza indefinidamente una tabla guardada en sesión. El snapshot visible debe pertenecer al mismo módulo y tener menos de diez minutos; al cambiar de sección o vencer, se descarta antes de resolver la respuesta.
2. La watchlist autónoma sólo se usa como fuente `trade_ready` mientras su última sincronización saludable sigue vigente. El brief central también requiere `source_freshness=FRESH` y antigüedad máxima de diez minutos.
3. Cuando el brief tiene filas `WATCH` pero ninguna entrada confirmada, publica `snapshot_kind=watch_candidate`. Python, el contrato enviado a ElevenLabs y el fallback de voz en navegador dicen “candidatas en observación; ninguna está lista para entrada”, no “mejores oportunidades”.
4. El productor de candidatas cripto conserva `current_price` desde `close` del scan normalizado y declara `price_basis=ultimo cierre del scan normalizado`. La voz muestra esa base, la fuente BinanceUS API y el estado broker/exchange, sin presentarlo como tick streaming.
5. Para candidatas, `ai_score` se nombra `Score de vigilancia`, no `Confianza`; la confianza de la tarjeta operativa pertenece a otro motor y ya no se mezcla verbalmente. Una oportunidad realmente promovida conserva el lenguaje de oportunidad verificada.
6. Los encabezados cripto 20m, 2H y Daily ahora dicen `Candidatas y oportunidades`, mientras cada tarjeta mantiene su decisión `NO OPERAR`, `ESPERAR` u operable según el motor de horizonte.
7. El ciclo real regeneró el brief con tres candidatas WATCH, precios 1.868,21 ETH, 76,10 SOL y 64.653,67 BTC, fuente BinanceUS, y cero entradas `trade_ready`. Chromium verificó encabezado, lenguaje, base de precio y fuente; además prohibió `Mejores oportunidades 2H` y `Confianza 100`.
8. Regresión integral: **2.472/2.472** en 124,17 s, con dos advertencias conocidas de dependencias y cero fallos.

Evidencia:

- `alerts/roxy_ai_brief.json`
- `alerts/opportunity_sync.json`
- `alerts/voice_candidate_semantics_probe.json`
- `alerts/voice_candidate_price_coherence_probe.json`
- `alerts/opportunity_watch_voice_coherence_probe.json`
- `output/playwright/opportunity_watch_voice_coherence.png`
- pruebas `tests/test_roxy_ai.py`
- pruebas `tests/test_watchlists.py`
- pruebas `tests/test_dashboard_probe_auth.py`
- pruebas `tests/test_elevenlabs_roxy.py`
- pruebas `tests/test_opportunity_sync.py`

## 84. Objetivos explícitos y niveles incompletos para candidatas WATCH

1. Se eliminó el fallback central que asignaba `recommended_target_pct=0.02`, objetivos +2/+5/+10 y `recommended_target_price` a cualquier señal sin objetivo. Un nivel inexistente ya no se convierte en una operación aparentemente completa.
2. `normalize_opportunity_row` sólo calcula precio objetivo cuando recibe un porcentaje explícito. También puede inferir 2%, 5% o 10% de una decisión explícita `TRADE_FOR_*PCT`, registrando `target_basis=decision_operativa_explicita`. Si el proveedor ya suministra `target_*_price`, conserva ese precio y registra el nombre exacto del campo; nunca lo recalcula.
3. Las candidatas rescatadas desde el scan publican `target_contract=MISSING_EXPLICIT_TARGET`, `levels_status=WATCH_ONLY_INCOMPLETE` y `levels_source=normalized_scan`; su target permanece nulo en JSON y en la sincronización de oportunidades.
4. La voz llama al valor de entrada `Referencia del scan` y al stop `Referencia de riesgo`. Cuando falta objetivo dice `Target sin definir; no hay objetivo explícito. Niveles incompletos para operar`; no los presenta como entrada, stop y target ejecutables.
5. El mismo contrato se entrega al runtime ElevenLabs y al fallback local del navegador. La sonda real encontró las tres advertencias, score de vigilancia y fuente; prohibió un target +2% y `Confianza 100`.
6. El brief real conserva tres candidatas y cero filas `trade_ready`; ETH, SOL y BTC tienen objetivo porcentual/precio nulo y contrato incompleto explícito.
7. El watchdog vivo publicó `scan WATCH target contract 3/3, inconsistent 0`; faltantes o contradicciones cambian el check `ai_brief` a `FAIL`.
8. Regresión integral: **2.474/2.474** en 122,32 s, con dos advertencias conocidas de dependencias y cero fallos.

Evidencia:

- `alerts/roxy_ai_brief.json`
- `alerts/opportunity_sync.json`
- `alerts/watch_candidate_incomplete_levels_probe.json`
- `output/playwright/watch_candidate_incomplete_levels.png`
- pruebas `tests/test_roxy_ai.py`
- pruebas `tests/test_watchlists.py`
- pruebas `tests/test_elevenlabs_roxy.py`

## 85. Propagación del activo hacia noticias, fundamentales y niveles

1. La página canónica `Noticias` resuelve `symbol`, `market` y `tf` mediante el mismo contrato URL/sesión usado por gráficas, alertas y voz. También actualiza el contexto compartido para que navegar a Noticias no restaure un ticker anterior.
2. Los titulares específicos se filtran con límites de ticker, símbolo/base cripto, nombre del activo y alias cripto conocidos. No se aceptan coincidencias parciales; tickers bursátiles ambiguos de una o dos letras exigen prefijo `$` salvo que coincida el nombre de compañía.
3. La pantalla separa `Noticias específicas de <símbolo>` y `Contexto general de mercado`. Si no hay coincidencias verificadas, lo declara expresamente en lugar de atribuir noticias globales al activo.
4. El bloque Finviz de Acciones dejó de rellenar “Noticias relevantes” con otros símbolos. Sólo muestra filas cuyo ticker coincide exactamente; si el proveedor respondió sin coincidencias, muestra ese estado y enlaza al feed general.
5. El panel fundamental continúa recibiendo el símbolo central y ahora declara `Yahoo Finance via yfinance`, estado, sello de actualización y TTL de caché. Para cripto indica que el perfil de compañía no aplica; para una acción sin respuesta identifica proveedor y estado `sin datos`.
6. Los niveles auditados mantienen el símbolo dentro de `roxy_trade_plan_from_row`; sólo quedan operables si entrada, stop y target son verificables. El motor visual puede promoverlos desde velas reales y conserva `plan_source`; si faltan, borra objetivos parciales y declara plan pendiente.
7. Chromium verificó BTC/USD 15m y AAPL 1h en la página Noticias, con URL/estado persistentes, encabezado específico, fuente/actualización, separación del contexto general y cero errores bloqueantes. El snapshot real incluyó una noticia de Bitcoin y una de Apple.
8. Regresión integral: **2.479/2.479** en 124,61 s, con dos advertencias conocidas de dependencias y cero fallos.

Evidencia:

- `alerts/selected_asset_news_btc_probe.json`
- `alerts/selected_asset_news_aapl_probe.json`
- `output/playwright/selected_asset_news_btc.png`
- `output/playwright/selected_asset_news_aapl.png`
- pruebas `tests/test_focused_opportunities.py`
- pruebas `tests/test_company_profile.py`
- pruebas `tests/test_roxy_operational_charts.py`

## 86. Navegación canónica con contexto y temporalidad 20m

1. `roxy_primary_navigation_html` acepta ahora el contrato común `symbol`, `market`, `tf` y lo incorpora en todos los destinos registrados. Inicio, oportunidades, Crypto 20m/2H/Daily, watchlists, estrategias, educación y diagnóstico dejan de reconstruir el activo desde defaults.
2. El mapa de Acciones y la pantalla de gráficas entregan su selección actual a esa navegación. Los tres módulos cripto hacen lo mismo; el bottom navigation ya seguía el contrato y queda alineado.
3. Los accesos rápidos del Dashboard a oportunidades, watchlists, alertas, capital, estudios y diagnóstico usan rutas canónicas con el contexto visible, no URLs parciales.
4. Los enlaces cripto hacia Inicio, Alertas y Noticias conservan símbolo, mercado y marco. “Ver noticias y fuentes” abre la página canónica de Noticias, no un panel local desconectado.
5. La auditoría interactiva descubrió que Crypto 20m aceptaba `tf=20m` en la URL pero lo reescribía internamente a `1m`; además, cada candidata enlazaba de nuevo a `1m`. El módulo admite ahora 20m y sus tarjetas conservan el marco seleccionado.
6. La fuente intrabar puede seguir declarando velas BinanceUS de 1m para construir la lectura de ciclo; esto se muestra como intervalo de datos y ya no modifica silenciosamente la temporalidad operativa elegida por el usuario.
7. Playwright abrió Crypto 20m con ETH/USD, siguió la navegación a Crypto 2H y a Noticias, y comprobó en los destinos `ETH/USD`, `market=crypto` y `tf=20m`. La sonda autenticada final renderizó Noticias ETH/USD con “marco visible 20m”, URL persistente y cero errores de consola.
8. Regresión integral: **2.480/2.480** en 180,55 s, con dos advertencias conocidas de dependencias y cero fallos.

Evidencia:

- `alerts/navigation_context_eth_news_probe.json`
- `output/playwright/navigation_context_eth_news.png`
- pruebas `tests/test_canonical_routes.py`
- pruebas `tests/test_roxy_operational_charts.py`
- pruebas `tests/test_watchlists.py`

## 87. Opciones ligadas al subyacente e identidad operativa verificable

1. La página Opciones resuelve el mismo `symbol`, `market` y `tf` que gráficas, noticias, watchlists, alertas y voz. El encabezado y la leyenda muestran el subyacente central en vez de abrir una tabla global sin contexto.
2. Para acciones, el selector abre en el símbolo visible. Si el snapshot no contiene contratos de ese activo, conserva el ticker y declara `Sin contratos verificables`; no sustituye silenciosamente AAPL/NVDA por otro subyacente disponible.
3. Cambiar manualmente el selector de opciones actualiza sesión y URL como mercado `stock`, manteniendo un único contexto operativo para las páginas posteriores.
4. Con un activo cripto, el panel falla cerrado: explica que las opciones bursátiles no aplican y no muestra contratos de acciones ajenos. Chromium confirmó BTC/USD 20m con este estado explícito.
5. Con AAPL, Chromium confirmó símbolo, mercado y timeframe persistentes, además del bloqueo real de la ruta por `Alpaca AUTH_INVALID`; no se mostraron candidatos falsos ni se presentó el proveedor como operativo.
6. El diagnóstico de identidad dejó de limitarse a contar archivos. Ahora extrae los símbolos de los cuatro scans live más recientes, brief, sincronización de oportunidades y estado durable de watchlists/alertas, normaliza pares cripto y compara ese conjunto con metadata y blobs cacheados.
7. El estado real es `CONNECTED`: **28/28 activos operativos cubiertos**, 40 logos cacheados, cero inconsistencias; fuentes `coingecko=20`, `official_domain=5`, `simple_icons=15`. Cualquier activo nuevo sin logo cambia automáticamente el check a `WARNING` y lista el faltante.
8. El check de identidad se muestra en la carga normal de Diagnóstico, no sólo detrás del botón profundo. Chromium verificó los conteos y cero errores bloqueantes.
9. El check `salto_integration` usaba “synthetic active/watch” para describir detecciones sobre una serie aislada de validación. No alimentaba scanner, brief ni UI, pero el texto podía sugerir señales falsas. El contrato vivo dice ahora `isolated fixture detections; fixture-only, 0 market rows published` y exporta esos dos campos verificables.
10. La matriz responsive anterior no incluía Opciones y todavía exigía el encabezado legacy de Noticias. El contrato `roxy-responsive-matrix/1.1.0` cubre ahora 10 rutas —incluidas Opciones acción/cripto y Crypto 20m real— por escritorio, iPad y teléfono.
11. Diagnóstico dejó de aceptar el número histórico `checked == 24`. Exige 30 filas, tres dispositivos 10/10 y diez rutas 3/3; la ejecución real cerró **30/30**, sin overflow, pérdida de contexto, errores bloqueantes ni extensiones de gráfica vacías. Chromium confirmó el resultado visible después de reiniciar únicamente Streamlit para cargar el módulo actualizado.
12. Regresión integral: **2.486/2.486** en 125,67 s, con dos advertencias conocidas de dependencias y cero fallos.

Evidencia:

- `alerts/options_crypto_context_probe.json`
- `alerts/options_stock_context_probe.json`
- `alerts/identity_coverage_diagnostic_probe.json`
- `output/playwright/options_crypto_context.png`
- `output/playwright/options_stock_context.png`
- `output/playwright/identity_coverage_diagnostic.png`
- `alerts/responsive_route_matrix.json`
- `alerts/responsive_30_diagnostic_probe.json`
- `output/playwright/responsive_matrix/`
- `output/playwright/responsive_30_diagnostic.png`
- pruebas `tests/test_focused_opportunities.py`
- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_roxy_realtime_check.py`
- pruebas `tests/test_responsive_route_matrix.py`

## 88. Portafolio paper, riesgo y aislamiento de backtests

1. `Capital` resuelve y conserva el contrato central `symbol`, `market` y `tf`. Chromium abrió la ruta con ETH/USD, mercado cripto y 20m; la selección permaneció visible y persistente durante toda la carga.
2. El resumen de operaciones declara `PAPER_ONLY` y una valuación `REALIZED_PAPER_ONLY`. El P&L sólo se calcula para episodios cerrados con nocional y movimiento observados; la pantalla indica expresamente que no contiene equity del broker ni P&L no realizado.
3. Cada fila consolidada declara `CLOSED_PAPER_RESULT` o `ENTRY_PLAN_ONLY` como base de precio. El cálculo contempla dirección larga/corta y deja de asumir silenciosamente que cualquier movimiento pertenece a una compra.
4. El simulador SQLite continúa aislado por usuario. El adaptador normaliza símbolo y valida cantidad, precio, slippage y fill rate antes de persistir; una venta forzada tampoco puede superar la posición disponible ni crear un cierre fantasma.
5. Cada fill local registra `price_source` y `price_ts`. El default se identifica como `caller_supplied_unverified`; por tanto, una cifra entregada por un llamador no aparece como cotización live sin procedencia.
6. `EXECUTION_ENABLED` cambió a fail-closed: sin opt-in explícito permanece apagado. Los únicos valores habilitantes aceptados son `1`, `true`, `yes`, `on` o `paper`.
7. El `PaperTrader` heredado de backtesting ya no crea ni agrega `db/trades.csv` al importarse. Opera en memoria y sólo exporta un CSV de auditoría cuando el llamador entrega una ruta absoluta explícita; sus resultados no contaminan el journal operativo.
8. El probe real renderizó 6.329 caracteres útiles, encontró `REALIZED_PAPER_ONLY`, la advertencia de equity/P&L y órdenes reales apagadas, con cero errores de página o consola.
9. Regresión integral: **2.496/2.496** en 124,90 s, con dos advertencias conocidas de dependencias y cero fallos.

Evidencia:

- `alerts/paper_portfolio_context_probe.json`
- `output/playwright/paper_portfolio_context.png`
- pruebas `tests/test_operations.py`
- pruebas `tests/test_paper_trader.py`
- pruebas `tests/test_execution_backtest_trader.py`
- pruebas `tests/test_auto_exec_gate.py`
- pruebas `tests/test_storage_snapshot.py`
- pruebas `tests/test_risk.py`

## 89. Calendario, actividad, memoria y notificaciones canónicas

1. `Actividad`, `Memoria` y `Notificaciones` son ahora páginas registradas, navegables y compatibles con el contrato común `symbol`, `market` y `tf`; dejaron de ser conceptos dispersos dentro de otros módulos.
2. Actividad se construye únicamente con alertas, oportunidades archivadas y fills paper del usuario activo. No consulta ni muestra actividad de otros perfiles y no presenta ninguno de esos registros como orden real.
3. Notificaciones separa salud agregada de canales y entregas por usuario. Muestra configuración, estados `DELIVERED`/pendientes/fallidos e intentos durables, pero no expone el contenido del historial global de mensajes.
4. Memoria usa evidencia cuantitativa paper/backtest versionada y declara que no es memoria conversacional privada ni promesa de rendimiento.
5. El calendario conserva el activo central y explica que el contexto macro es global. El flag `alerts_allowed` falla cerrado si falta archivo o eventos válidos y se limita a `CALENDAR_EVENTS_ONLY`; `market_signal_gate=CONTEXT_ONLY` impide confundir una agenda válida con permiso de trading.
6. El sync vivo continúa `OK` con 32 eventos oficiales BEA/Federal Reserve, 28 futuros y sello 2026-07-19T16:37:05Z. No se agregaron eventos de demostración.
7. Chromium verificó Notificaciones con ETH/USD 20m, Actividad con AAPL 1h, Memoria con BTC/USD 15m y Calendario con BTC/USD 15m; todas conservaron URL/estado y cerraron sin errores bloqueantes.
8. Regresión integral: **2.499/2.499** en 125,72 s, con dos advertencias conocidas de dependencias y cero fallos.

Evidencia:

- `alerts/calendar_context_contract_probe.json`
- `alerts/notifications_context_probe.json`
- `alerts/activity_user_scope_probe.json`
- `alerts/memory_evidence_probe.json`
- `output/playwright/calendar_context_contract.png`
- `output/playwright/notifications_context.png`
- `output/playwright/activity_user_scope.png`
- `output/playwright/memory_evidence.png`
- pruebas `tests/test_macro_calendar_contract.py`
- pruebas `tests/test_canonical_routes.py`

## 90. Recuperación del foco visual y matriz responsive 42/42

1. El watchdog detectó correctamente que el probe visual conservaba ETH/USD después de que el motor de calidad confirmara la rotación operativa a BTC/USD. No se aceptó el render antiguo como evidencia vigente.
2. El autoheal regeneró los probes principal y de búsqueda desde `roxy_status.json`: foco BTC/USD y búsqueda AAPL. Ambos preservaron URL/estado, renderizaron más de 2.380 caracteres y quedaron sin errores bloqueantes.
3. El estado global pasó de `SYSTEM_FAIL` a `WARN`: núcleo recuperándose y bloqueo externo premium explícito por Alpaca `AUTH_INVALID`. Cripto permanece operable; acciones y opciones continúan bloqueadas.
4. `roxy-responsive-matrix/1.2.0` incorpora Calendario, Actividad, Memoria y Notificaciones a las diez rutas anteriores. El contrato exige ahora 14 rutas por escritorio, iPad y teléfono.
5. La ejecución real cerró **42/42**, sin overflow, pérdida de contexto, errores bloqueantes ni extensiones de gráfica vacías. Diagnóstico rechaza cualquier reporte anterior o incompleto y espera exactamente 42 comprobaciones.

Evidencia:

- `alerts/dashboard_render_probe.json`
- `alerts/dashboard_render_probe_search.json`
- `alerts/roxy_realtime_check.json`
- `alerts/responsive_route_matrix.json`
- `output/playwright/responsive_matrix/`
- pruebas `tests/test_responsive_route_matrix.py`
- pruebas `tests/test_system_diagnostics.py`

## 91. SLO visual medido y recuperación del servicio Streamlit

1. La matriz responsive registra por cada combinación `navigation_dom_seconds` e `initial_content_ready_seconds`; el tiempo total del probe ya no se usa como sustituto de velocidad porque incluye esperas deliberadas de estabilidad.
2. El contrato falla si una carga fría supera 15 segundos hasta contenido inicial, aunque la página termine apareciendo y no tenga errores de consola.
3. Las 42 combinaciones quedaron dentro del SLO: promedio **6,466 s**, p95 **7,943 s** y máximo **9,833 s**. La más lenta fue Acciones escritorio; ninguna superó 15 segundos.
4. Diagnóstico muestra `contenido inicial p95 7.9s/SLO 15.0s, max 9.8s`; Chromium verificó esta evidencia en la aplicación real.
5. Durante un reinicio de validación, el job `com.roxy.streamlit` quedó descargado de launchd. Se recuperó desde el plist instalado con `bootstrap`, volvió a estado `running`, puerto 3000 y HTTP health `ok`; el probe posterior aprobó. No se ocultó el incidente como simple timeout.
6. Regresión integral: **2.500/2.500** en 124,95 s, con dos advertencias conocidas de dependencias y cero fallos.

Evidencia:

- `alerts/responsive_route_matrix.json`
- `alerts/responsive_performance_diagnostic_probe.json`
- `output/playwright/responsive_performance_diagnostic.png`
- pruebas `tests/test_responsive_route_matrix.py`
- pruebas `tests/test_system_diagnostics.py`

## 92. Runtime Python 3.12, seguridad de dependencias y eliminación de bloqueos de E/S

1. El entorno activo fue migrado de Python 3.9 a **Python 3.12.13** mediante promoción blue/green. Streamlit quedó fijado en **1.54.0**, primera versión corregida que conserva la navegación canónica de Roxy. Los LaunchAgents de Streamlit, scanner, watchdog, backup, alertas y calendario, además del servicio de voz, usan ahora `.venv/bin/python` y `python3.12/site-packages`.
   Tras aprobar la regresión y verificar que no existían referencias, `.venv39` salió del proyecto y quedó recuperable en la Papelera como `roxy_venv39_python39_20260719`.
2. La auditoría de dependencias bajó de 83 hallazgos en 26 paquetes bajo el runtime heredado a un solo hallazgo build-only en `setuptools`, fijado transitivamente por `ccxt`. Diagnóstico reporta **0 vulnerabilidades accionables de runtime** y documenta por separado esa excepción de construcción.
3. Se detectaron 1.022 procesos duplicados del daemon de backup: el socket de `screen` podía desaparecer aunque el proceso Python siguiera vivo, por lo que el watchdog creaba otro worker en cada ciclo. El supervisor identifica ahora PIDs reales, considera heartbeat + proceso, elimina duplicados y conserva exactamente un daemon.
4. El backup reiniciado hereda el último archivo verificado en su heartbeat y usa por defecto `output/runtime_backups`; no aparece falsamente degradado durante las 24 horas entre respaldos.
5. Mantenimiento de salida y backup dejaron de seleccionar automáticamente `/Volumes/RoxyData`. Los destinos externos requieren configuración explícita. El watchdog también deja desactivado el chequeo del volumen salvo `ROXY_EXTERNAL_DISK_PATH` o `--external-disk-path`, evitando que un volumen montado pero sin respuesta congele la plataforma. Los tamaños de directorios personales se miden en subprocesos acotados a dos segundos; un candidato lento queda `unreadable` sin detener la supervisión.
6. Las ejecuciones de prueba con `base_dir` o directorios runtime alternativos ya no heredan rutas reales de caché externa ni escanean el directorio personal al medir presión de almacenamiento. Regresiones dedicadas verifican que caché y candidatos de espacio permanezcan dentro del entorno aislado.
7. Una cotización válida de Alpaca ya no dispara después una consulta redundante a Yahoo: precio, cierre anterior y sesión se resuelven desde el mismo snapshot del proveedor. Esto elimina latencia de red oculta y evita discrepancias de fuente.
8. El bridge stock valida orígenes exactos, impide comodines, limita el bind local a loopback y sólo confía en proxies locales.
9. Regresión integral final bajo Python 3.12: **2.509/2.509** en 144,40 s, cero fallos. Tras añadir la última regresión de E/S, el módulo de watchdog cerró 629/629 y los probes de navegador conservaron símbolo, mercado y timeframe sin errores bloqueantes.

Evidencia:

- `alerts/dependency_audit.json`
- `alerts/dashboard_python312_probe.json`
- `alerts/diagnostic_python312_probe.json`
- `output/playwright/dashboard_python312.png`
- `output/playwright/diagnostic_python312.png`
- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_runtime_backup_screen.py`
- pruebas `tests/test_runtime_backup.py`
- pruebas `tests/test_living_market.py`
- pruebas `tests/test_roxy_stock_stream_bridge.py`
- pruebas `tests/test_roxy_realtime_check.py`

## 93. Salud degradada correcta y aprendizaje sin dependencias externas implícitas

1. El diagnóstico de aprendizaje contabilizaba 162 fuentes ya alojadas en `/Volumes/RoxyData` como 370,87 GiB “sin archivar” localmente. Ahora clasifica por ruta externa sin tocar el montaje: **163 fuentes externas, 0 fuentes locales pendientes y 0 GiB locales**. La biblioteca queda `OK` con 204 videos, 186 materiales, 390 manifests y 16 temas.
2. La ingesta manual dejó de añadir `/Volumes/RoxyData` a sus fuentes predeterminadas. Sólo usa carpetas locales salvo `ROXY_VIDEO_SOURCES`; el archivo externo requiere `ROXY_VIDEO_ARCHIVE_DIR`. Los LaunchAgents existentes conservan sus rutas porque están declaradas explícitamente.
3. El inventario de presión de almacenamiento es informativo y usa `measurement_state=PARTIAL` cuando un directorio supera el timeout. La capacidad crítica continúa perteneciendo al check real de espacio; una carpeta no medible ya no convierte el núcleo en fallo.
4. `health_stability_slo` pasó de `FAIL` a `INFO`: núcleo recuperándose, proveedor premium bloqueado de forma explícita. El estado global permanece correctamente en `WARN` por Alpaca `AUTH_INVALID`; no se disfraza como operación total.
5. Las advertencias opcionales de colores de sidebar emitidas por Streamlit 1.54 están clasificadas de forma coherente como benignas tanto en el probe como en el agregador histórico; no aparecen ya como alertas accionables.
6. Los recorridos de directorios personales están limitados a dos segundos por candidato. Esto y las rutas aisladas de pruebas eliminan bloqueos indefinidos de E/S.
7. El generador interno de velas de validación usa unidades temporales explícitas, reduciendo la regresión integral de 4.879 a **1.279 advertencias**.
8. Regresión integral final: **2.515/2.515** en 145,79 s. Módulo de salud: 631/631; módulo de ingesta: 31/31.

Evidencia:

- `alerts/roxy_realtime_check.json`
- `alerts/daily_readiness_diagnostic_probe.json`
- `output/playwright/daily_readiness_diagnostic.png`
- `training_videos/video_learning_index.json`
- pruebas `tests/test_roxy_realtime_check.py`
- pruebas `tests/test_video_learning_ingest.py`

## 94. Contrato UTC compatible con Python futuro

1. Se añadió `roxy_time.py` como reloj central: UTC aware para contratos nuevos y UTC naive explícito para conservar compatibilidad exacta con las columnas de texto SQLite existentes.
2. Todos los usos productivos de `datetime.utcnow()` fueron eliminados de storage, sesiones OAuth, API keys, auditoría, paper trading, backtests, reportes, snapshots, cache de prompts y UI.
3. La migración no mezcla formatos ni cambia comparaciones de expiración: `utc_now_naive()` conserva el contrato histórico mientras evita la API deprecada.
4. Una prueba recorre todas las fuentes Python de producción y falla si se reintroduce `datetime.utcnow()`.
5. Los fixtures de gráficas usan unidades temporales explícitas. La suite pasó de 1.279 advertencias a sólo **2 advertencias externas** (`websockets.legacy` y el adaptador `fastapi.testclient`).
6. Regresión integral final: **2.517/2.517** en 145,55 s; cero fallos.

Evidencia:

- `roxy_time.py`
- `tests/test_roxy_time.py`
- `alerts/utc_runtime_diagnostic_probe.json`
- `output/playwright/utc_runtime_diagnostic.png`
- pruebas de storage, secrets/OAuth, API auth, riesgo, paper trading, reportes, gráficas y estrategias.

## 95. Herramientas manuales para estructuras tecnicas

1. La grafica profesional permite dibujar manualmente triangulos simetricos, wedges ascendentes y wedges descendentes sobre las velas reales.
2. Cada estructura usa coordenadas de tiempo/precio, admite seleccion, movimiento, redimensionado por anclas, deshacer/rehacer y borrado.
3. Los nuevos tipos forman parte de la lista segura del estado central de graficas; se guardan por usuario, simbolo y temporalidad y pueden sincronizarse con Roxy.
4. Validacion real: se dibujo un triangulo en BTC/USD 15m, se verifico el contador operativo y se recargo la pagina conservando el objeto, sin errores de consola.
5. La plantilla compartida ya rotula correctamente `Crypto 15m/1h` o `Acciones 15m/1h` segun el mercado real; BTC/USD no vuelve a presentarse como accion.
6. Regresion integral final: **2.518/2.518** en 146,80 s, con las dos advertencias externas conocidas y cero fallos.

Evidencia:

- `output/playwright/manual_structure_triangle_drawn.png`
- `output/playwright/manual_structure_triangle_persisted.png`
- `alerts/manual_structure_tools_probe.json`
- `output/playwright/manual_structure_tools_probe.png`
- pruebas `tests/test_chart_state.py`
- pruebas `tests/test_focused_opportunities.py`

## 96. Cursor sincronizado entre las graficas 15m y 1h

1. Las dos graficas profesionales comparten el cursor por un canal aislado por mercado y simbolo; una grafica de otro activo no puede recibir el evento.
2. El tiempo seleccionado en 15m se proyecta sobre la vela mas cercana de 1h, y viceversa, conservando el OHLC y precio propios de cada timeframe.
3. El runtime muestra `Cursor enlazado` y `Cursor 15m ↔ 1h`; la receptora no retransmite el evento y no crea ciclos de eco.
4. `tools/dual_chart_crosshair_probe.py` abre el workspace real, mueve el cursor y valida canal, recepcion, etiqueta, ausencia de eco y cero errores bloqueantes de consola.
5. Las lineas truncadas del warning benigno de NumPy ya no contaminan los errores operativos; el filtro reconoce su firma estable.

Evidencia:

- `alerts/dual_chart_crosshair_probe.json`
- `output/playwright/dual_chart_crosshair_probe.png`
- `output/playwright/dual_crosshair_linked_full.png`
- pruebas `tests/test_dual_chart_crosshair_probe.py`
- pruebas `tests/test_roxy_operational_charts.py`

## 97. Coherencia del foco operativo descartado

1. Los handoffs `ALERT_QUALITY_DISCARD`, `ALERT_QUALITY_ROTATION` y `ALERT_QUALITY_CONFIRMATION_ROTATION` son focos operativos explicitos, incluso cuando coinciden con el candidato superior anterior.
2. El snapshot publica alineacion coherente con el plan diario y el watchdog valida el foco real en vez de inferirlo solo por igualdad de simbolo.
3. La sonda durable del cursor forma parte del watchdog: evidencia ausente o vencida queda informativa; un fallo vigente queda `FAIL`.
4. La regresion integral de este corte cerro **2.523/2.523**, con dos advertencias externas conocidas.

Evidencia:

- `alerts/roxy_status.json`
- `alerts/roxy_realtime_check.json`
- pruebas `tests/test_roxy_ai.py`
- pruebas `tests/test_roxy_realtime_check.py`

## 98. Ciclo durable de invalidacion y archivo de oportunidades

1. `DISCARD_STALE_SINGLE` elimina el simbolo de oportunidades activas, recalcula conteos y reconstruye el plan diario sin el candidato obsoleto.
2. El evento se guarda como `Invalidada` por usuario y aparece en el historial de oportunidades cerradas con motivo, fecha y condicion de reactivacion.
3. `alerts/opportunity_lifecycle.json` conserva el descarte entre ciclos y reinicios. Un cambio posterior a `BLOCKED_REALTIME_DATA` no vuelve a insertar el simbolo.
4. La politica `FRESH_ALERT_READY` permite reactivar el activo unicamente con un gatillo nuevo y operable; vencer el enfriamiento no basta.
5. La sincronizacion es idempotente: ciclos repetidos actualizan el episodio existente y no duplican registros.
6. El dashboard real fue validado con cero candidatas activas, sincronizacion `OK` y LTC/USD visible como `Invalidada`, sin errores bloqueantes.
7. El validador acepta un plan activo vacio cuando el unico candidato fue descartado.
8. Regresion integral: **2.531/2.531** en 145,82 s, con las dos advertencias externas conocidas.

Evidencia:

- `alerts/opportunity_lifecycle.json`
- `alerts/opportunity_sync.json`
- `alerts/opportunity_archive_render_probe.json`
- `output/playwright/opportunity_archive_render_probe.png`
- pruebas `tests/test_roxy_ai.py`
- pruebas `tests/test_opportunity_sync.py`
- pruebas `tests/test_roxy_realtime_check.py`

## 99. Diagnostico del ciclo de vida de oportunidades

1. El watchdog valida contrato, frescura, estructura de eventos, simbolos duplicados, estado `Invalidada`, timestamps y politica `FRESH_ALERT_READY`.
2. El chequeo cruza el archivo durable con el brief activo y falla si un simbolo archivado reaparece simultaneamente como oportunidad activa.
3. Diagnostico recibe el resultado mediante el reporte realtime; la lectura viva muestra **1 archivada, 0 solapamientos y estado OK**.
4. El watchdog ignora placeholders `-`, `NONE`, `NULL` y `N/A` al escoger una grafica. Una lista activa vacia ya no provoca una consulta falsa a Yahoo ni degrada el sistema.
5. El modulo completo de salud cerro **635/635** en 14,01 s.

Evidencia:

- `alerts/opportunity_lifecycle.json`
- `alerts/roxy_realtime_check.json`
- pruebas `tests/test_roxy_realtime_check.py`

## 100. Telemetria completa en chequeos de solo lectura

1. `--no-history` ya no deja vacios los campos de mantenimiento posterior al append ni degrada el contrato de metricas.
2. El watchdog publica `skipped_no_history`, resultado `ok`, objetivo de bytes y plan de retencion calculado sin modificar el historial.
3. La prueba conserva los bytes exactos del archivo antes y despues del chequeo, por lo que la ruta de diagnostico sigue siendo realmente de solo lectura.
4. `Ciclo de oportunidades` y `Contrato de telemetria` forman parte de la superficie visible de Diagnostico y traducen estados watchdog a `CONNECTED`, `WARNING` o `ERROR`.
5. Chromium verifico ambos como `CONNECTED`: lifecycle con una archivada y cero solapamientos; telemetria con todos los aliases presentes. No hubo errores bloqueantes de consola o pagina.
6. Los modulos completos de watchdog y diagnostico cerraron **705/705** en 14,78 s.

Evidencia:

- `alerts/opportunity_lifecycle_diagnostic_probe.json`
- `output/playwright/opportunity_lifecycle_diagnostic.png`
- `alerts/roxy_realtime_check.json`
- pruebas `tests/test_roxy_realtime_check.py`
- pruebas `tests/test_system_diagnostics.py`

## 101. Reduccion verificable de solicitudes BinanceUS

1. El scanner solicitaba 25 pares en 15m, 1h, 2h y 4h por separado: 100 llamadas OHLCV cada cinco minutos y 20.855 llamadas `scanner_ohlcv` observadas en las ultimas 24 horas.
2. Roxy conserva 15m como serie independiente, obtiene una sola serie 1h ampliada a 1.000 velas y deriva localmente 2h y 4h con OHLCV agregado sobre limites UTC.
3. La serie 4h derivada conserva al menos 250 velas, suficientes para SMA/EMA200; 2h conserva al menos 500. Los indicadores siguen usando el motor central.
4. La ejecucion real de BTC/USD y ETH/USD produjo ocho filas validas usando cuatro llamadas OHLCV en vez de ocho. El reporte marco `DIRECT` para 15m, `SHARED_1H` para 1h y `DERIVED_FROM_1H` para 2h/4h.
5. El ciclo completo de 25 pares evita **50 solicitudes por ciclo**, reduce las llamadas OHLCV del scanner en 50% y puede evitar hasta 14.400 solicitudes diarias con el intervalo configurado de cinco minutos.
6. El ciclo vivo posterior termino en 12,2 s frente a aproximadamente 15,9 s antes del cambio. Diagnostico muestra `Eficiencia del scanner CONNECTED`, 50 solicitudes evitadas y cero errores bloqueantes de navegador.
7. El watchdog falla o advierte si el reporte falta, vence, se corrompe o vuelve a solicitar directamente 2h/4h.
8. Los modulos completos afectados cerraron **718/718** en 14,97 s.

Evidencia:

- `alerts/crypto_scan_fetch_optimization_probe.json`
- `alerts/ma_live_scan_timing.json`
- `alerts/roxy_realtime_check_efficiency_probe.json`
- `alerts/scanner_efficiency_diagnostic_probe.json`
- `output/playwright/scanner_efficiency_diagnostic.png`
- pruebas `tests/test_ma_scan.py`
- pruebas `tests/test_roxy_realtime_check.py`
- pruebas `tests/test_system_diagnostics.py`

## 102. Watchdog observable y mantenimiento externo acotado

1. Una ejecucion programada cada cinco minutos permanecio mas de diez minutos con el lock activo. El volcado de pila confirmo el bloqueo en `cleanup_log_snapshots`, durante `pathlib.glob` sobre `/Volumes/RoxyData/MacArchive/log_snapshots`.
2. El watchdog publica ahora cada fase en el estado y en la metadata del lock. Una ejecucion concurrente bloqueada conserva la fase del PID propietario en vez de sobrescribir el diagnostico.
3. `SIGUSR1` genera un volcado de todas las pilas Python sin terminar el proceso. Esto permitio identificar el punto exacto del bloqueo vivo.
4. El estado y la metadata del lock usan reemplazo atomico; los lectores concurrentes ya no pueden observar JSON parcialmente escrito.
5. La enumeracion de snapshots se ejecuta en un subproceso con limite de cinco segundos y una sola lectura para todos los patrones. Un volumen USB que no responde queda `WARN` con el error por patron, sin congelar el servicio.
6. El mantenimiento real termino en seis segundos y publico `Revisar acceso a snapshots en RoxyData`. El archivo distingue correctamente el archivo local del externo.
7. El watchdog completo posterior termino en 1 min 48 s, libero el lock y salio con codigo 0. Los reintentos del mismo fallo externo se espacian una hora; un chequeo posterior termino en cinco segundos sin repetir la limpieza.
8. Las pruebas dirigidas de mantenimiento, contrato, lock y recuperacion cerraron **115/115**; la validacion adicional del reintento acotado cerro **24/24**.
9. La regresion integral posterior cerro **2.543/2.543** en 145,01 s, con dos advertencias externas de deprecacion y codigo de salida 0.

Evidencia:

- `alerts/roxy_realtime_lock.json`
- `alerts/output_maintenance.json`
- `alerts/output_maintenance_watchdog_probe.json`
- `alerts/roxy_realtime_check.json`
- pruebas `tests/test_output_maintenance.py`
- pruebas `tests/test_roxy_realtime_check.py`

## 103. Contrato real de acceso remoto para voz

1. El servicio vivo escucha en `127.0.0.1:8010`; por tanto una clave Bearer por si sola no permite acceso desde iPad o telefono.
2. Diagnostico separa ahora `Seguridad API de voz` de `Acceso remoto de voz`. El segundo inspecciona el LaunchAgent real y verifica bind, autenticacion y transporte HTTPS/reverse proxy.
3. Loopback queda `NOT_CONFIGURED`; bind remoto sin clave queda bloqueado; bind y clave sin HTTPS quedan `WARNING`; solo las tres condiciones producen `CONNECTED`.
4. La sincronizacion entre dispositivos usa el mismo contrato y deja de afirmar que configurar unicamente `VOICE_API_KEY` resuelve el acceso remoto.
5. Roxy no cambio el bind, no genero secretos y no expuso puertos. La habilitacion remota sigue siendo una accion explicita de seguridad.
6. La sonda Chromium autenticada encontro `Acceso remoto de voz`, el bind `127.0.0.1:8010` y el contrato de telemetria conectado en 8.530 caracteres, con URL/estado persistidos y cero errores bloqueantes.
7. El alias `output_maintenance_local_cache_cleanup_skipped_ratio` publica `0.0` cuando no hay candidatos ni omisiones; el contrato de metricas vuelve a `OK` con cero aliases faltantes.
8. Las suites completas afectadas cerraron **719/719** en 15,23 s, con dos advertencias externas conocidas.

Evidencia:

- `alerts/voice_remote_access_diagnostic_probe.json`
- `output/playwright/voice_remote_access_diagnostic.png`
- `alerts/roxy_realtime_check.json`
- pruebas `tests/test_secrets_api_security.py`
- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_roxy_realtime_check.py`

## 104. Servicio de voz administrado y recuperable

1. El LaunchAgent manual que invocaba Uvicorn directamente fue sustituido por `tools/voice_live_launchd.py`, un instalador autoritativo con acciones `install`, `status` y `uninstall`.
2. El servicio carga el `.env` administrado desde `~/Library/Application Support/RoxyTrading/.env`, con permisos `0600`, y exporta el proyecto y su entorno virtual mediante `PYTHONPATH` antes de iniciar Uvicorn.
3. La configuracion segura sigue siendo `127.0.0.1:8010`. La migracion no abrio el servicio a la red, no creo credenciales y no declaro HTTPS inexistente.
4. `launchd_recovery` incluye ahora `voice_live` entre los siete servicios centrales. Reinstala el servicio si falta, no esta cargado, usa un comando antiguo, no carga el entorno administrado o se desvia del host/puerto configurado.
5. La plantilla de entorno y la documentacion describen el contrato remoto completo: bind explicito, `VOICE_API_KEY`, lista `ROXY_STATE_SYNC_USERS` y transporte HTTPS/TLS. El puerto 8010 no debe exponerse directamente.
6. El estado vivo confirma plist instalado y cargado, entorno y `PYTHONPATH` administrados, host loopback y puerto 8010. `/health` responde HTTP 200.
7. La sonda de voz cerro **4/4**: salud, pagina Roxy Live, contexto de sesiones y dashboard activo. La recuperacion durable publica **7 servicios, 0 fallidos**.
8. Las pruebas dirigidas cerraron **10/10** y las suites integradas de recuperacion, watchdog, diagnostico, seguridad y voz cerraron **755/755** en 15,48 s, con dos advertencias externas conocidas.
9. La regresion integral posterior cerro **2.548/2.548** en 146,64 s, con codigo de salida 0. El siguiente ciclo programado libero el lock, termino con codigo 0 y publico el contrato de metricas `OK` con cero aliases faltantes.

Evidencia:

- `alerts/launchd_recovery.json`
- `alerts/roxy_realtime_check.json`
- `tools/voice_live_launchd.py`
- pruebas `tests/test_voice_live_launchd.py`
- pruebas `tests/test_launchd_recovery.py`
- pruebas `tests/test_roxy_realtime_check.py`
- pruebas `tests/test_roxy_voice_smoke.py`

## 105. Separacion entre mantenimiento local y archivo externo

1. El SLO trataba el timeout de `/Volumes/RoxyData/MacArchive/log_snapshots` como una falla del nucleo aunque la base de datos, los historiales, los presupuestos, el archivo local y la limpieza interna estuvieran protegidos.
2. `output_maintenance_report` conserva `WARN` y la accion `Revisar acceso a snapshots en RoxyData`; la degradacion externa no se oculta ni se presenta como resuelta.
3. El chequeo publica ahora `external_degraded=true` e `internal_protected=true` solo cuando el unico issue de higiene es `log snapshot scan warn` y no existen errores de archivo, contrato, SQLite, presupuesto, ejecucion parcial o modo dry-run.
4. La historia usa esa distincion para evaluar el nucleo. Errores internos siguen degradando el SLO; las entradas historicas anteriores conservan compatibilidad mediante sus pruebas de higiene, operacion, presupuesto y archivo.
5. La sonda real paso de `FAIL / Core con fallas` a `INFO / Core recuperando / externo bloqueado`, con mantenimiento protegido, issue interno falso y recuperacion sostenida explicita. No se borro ni reescribio la ventana historica.
6. El watchdog programado termino con codigo 0, libero el lock y persistio las dos banderas. El contrato de metricas cerro `OK` con **1.417 claves** y cero aliases faltantes.
7. Las pruebas especificas cerraron **19/19** y el modulo completo del watchdog cerro **644/644** en 14,47 s, con una advertencia externa conocida. `git diff --check` y `pip check` terminaron limpios.

Evidencia:

- `alerts/output_maintenance_external_classification_probe.json`
- `alerts/output_maintenance.json`
- `alerts/roxy_realtime_check.json`
- `alerts/roxy_realtime_history.jsonl`
- pruebas `tests/test_roxy_realtime_check.py`

## 106. Recuperacion honesta de credenciales y permisos locales

1. El centro de proveedores mostraba simultaneamente `Autenticacion invalida` y `Paper listo`: el Safety Gate inferia operacion solo por presencia de key/secret, mientras el watchdog ya habia probado `AUTH_INVALID`.
2. El gate y el panel de cuenta consumen ahora el mismo `alpaca_account_probe`. Credenciales presentes pero rechazadas producen `AUTH_INVALID`, `Paper orders: OFF`, cuenta pendiente y cero intento redundante de cliente.
3. La sonda Chromium de Integraciones encontro `Alpaca no operativo`, `Autenticacion invalida` y `Paper orders: OFF`; prohibio `Paper orders: ON`, con 9.369 caracteres y URL/estado persistidos.
4. ElevenLabs expone estado y HTTP estructurados. Un 401 hace una sola solicitud prioritaria por ciclo de cache, no intenta inmediatamente el segundo endpoint con la misma clave y habilita el fallback de voz local del navegador.
5. Diagnostico mantiene `ElevenLabs runtime ERROR / AUTH_INVALID / HTTP 401`; el fallback no presenta al proveedor externo como conectado.
6. El `.env` fuente tenia permisos `0644` y fue corregido a `0600`. El entorno administrado ya estaba en `0600`. `Seguridad de entorno de proveedores` verifica ambos sin leer valores y devuelve `CONNECTED` con etiquetas separadas `proyecto=0600` y `administrado=0600`.
7. Una primera prueba visual coincidio con la recarga de un modulo importado y capturo correctamente la excepcion. Se reinicio solo Streamlit, se repitio la prueba y cerro `OK` con 8.757 caracteres. El ciclo limpio posterior dejo las dos rutas Dashboard `OK`, lock liberado, salida 0 y contrato de metricas sin faltantes.
8. Las suites afectadas cerraron **141/141**. La regresion integral posterior cerro **2.554/2.554** en 145,10 s, con dos advertencias externas conocidas y codigo de salida 0.

Evidencia:

- `alerts/alpaca_runtime_gate_probe.json`
- `output/playwright/alpaca_runtime_gate.png`
- `alerts/provider_auth_diagnostic_probe.json`
- `output/playwright/provider_auth_diagnostic.png`
- `alerts/provider_security_diagnostic_probe.json`
- `output/playwright/provider_security_diagnostic.png`
- `alerts/roxy_realtime_check.json`
- pruebas `tests/test_alpaca_operations_gate.py`
- pruebas `tests/test_alpaca_paper_account.py`
- pruebas `tests/test_live_provider_center.py`
- pruebas `tests/test_elevenlabs_roxy.py`
- pruebas `tests/test_system_diagnostics.py`

## 107. Rotacion segura y propagacion de proveedores

1. `tools/provider_credential_setup.py` crea un flujo unico para Alpaca y ElevenLabs. Las claves se leen con `getpass` y nunca se aceptan como argumentos de proceso.
2. La configuracion candidata se valida contra el proveedor antes de persistir. Un `AUTH_INVALID` conserva los archivos actuales, no reinicia servicios y devuelve codigo no exitoso.
3. Una validacion correcta actualiza el `.env` del proyecto y el administrado mediante archivo temporal, `fsync`, reemplazo atomico y permisos `0600`.
4. Solo despues de autenticar, el comando reinicia Streamlit, scanner live, monitor de alertas, watchdog y voz si esos LaunchAgents estan cargados. Los valores nunca aparecen en el JSON de resultado.
5. `--save-unverified` queda como override explicito para una caida externa; no es la ruta normal ni convierte una autenticacion fallida en conexion valida.
6. Las pruebas cubren reemplazo y preservacion de variables, sincronizacion byte a byte, permisos, rechazo sin persistencia/reinicio, exito con propagacion y ausencia de secretos en el resultado: **3/3**.
7. El comando `--help`, `git diff --check`, `pip check` y la verificacion viva de ambos archivos `0600` terminaron correctamente.
8. La regresion integral posterior cerro **2.557/2.557** en 150,54 s, con dos advertencias externas conocidas y codigo de salida 0.

Evidencia:

- `tools/provider_credential_setup.py`
- pruebas `tests/test_provider_credential_setup.py`
- `README.md`

## 108. Inventario de almacenamiento acotado y accionable

1. El diagnostico de presion local inspeccionaba hasta nueve directorios en serie. Varias rutas protegidas o lentas podian acumular sus limites de espera dentro del heartbeat del watchdog.
2. Las mediciones de produccion se ejecutan ahora en paralelo con un maximo de cuatro workers; cada `du` conserva su timeout individual de dos segundos y no puede bloquear indefinidamente el proceso principal.
3. La duracion real del inventario bajo presion bajo de aproximadamente 3,1 s a 2,0 s. La ruta con datos de prueba continua siendo determinista y no usa threads.
4. Una medicion parcial ya no publica solamente `unreadable 3`: conserva nombre, ruta y causa acotada para `Downloads`, `Pictures` y `Library/Caches`, sin recorrer ni modificar su contenido.
5. El artefacto `local_storage_pressure_sources.json` fue regenerado con `measurement_state=PARTIAL`, el detalle de las tres rutas y el mismo plan seguro: los datos de usuario requieren revision manual y no se borran automaticamente.
6. Las pruebas dirigidas cerraron **12/12**, incluyendo concurrencia real del inventario, compatibilidad del cache, detalle de timeouts y propagacion al watchdog.
7. La regresion integral posterior cerro **2.558/2.558** en 146,72 s, con las dos advertencias externas conocidas y codigo de salida 0. `git diff --check` y `pip check` permanecen limpios.

Evidencia:

- `alerts/local_storage_pressure_sources.json`
- `tools/roxy_realtime_check.py`
- pruebas `tests/test_roxy_realtime_check.py`

## 109. Runtime visual sin advertencias de tema

1. Las sondas Chromium registraban entre 18 y 21 advertencias por render de `theme.sidebar`, aun cuando sus colores visibles eran validos. Retirar la seccion no corrigio el problema y confirmo que provenia del runtime Streamlit 1.54, que serializaba colores opcionales vacios.
2. `requirements.txt` actualiza el runtime a `streamlit>=1.59.2,<1.60`. La instalacion no cambio dependencias transitivas y `pip check` permanece limpio.
3. Streamlit 1.59 representa el selectbox como un combobox cuyo valor esta en el atributo `value`, no en `body.innerText`. La sonda lee ahora el valor DOM real de `Vista` y mantiene controles separados de URL, simbolo, mercado y temporalidad.
4. No se debilito el contrato de render: `Inicio` queda validado como seleccion real, mientras `Live sin reload` y `Roxy Trading` siguen siendo landmarks independientes de contenido.
5. Las sondas oficiales de ETH/USD y AAPL cerraron `OK`, con seleccion `Inicio`, estado/URL persistidos, cero errores de consola y cero advertencias de la familia `streamlit_optional_sidebar_theme`. Permanecen once avisos benignos del navegador y del sandbox de iframes.
6. Las pruebas dirigidas de navegador, responsive y watchdog cerraron **678/678**. La regresion integral posterior cerro **2.558/2.558** en 147,73 s, con dos advertencias de dependencias externas conocidas y codigo de salida 0.

Evidencia:

- `alerts/dashboard_streamlit_159_probe.json`
- `alerts/dashboard_render_probe.json`
- `alerts/dashboard_render_probe_search.json`
- `output/playwright/dashboard_streamlit_159.png`
- `requirements.txt`
- `tools/dashboard_render_probe.py`

## 110. Suite sin advertencias de dependencias

1. Las dos advertencias persistentes provenian de contratos externos concretos: Alpaca 0.43.5 importa `websockets.legacy`, deprecado desde WebSockets 14, y Starlette 1.x deja `httpx` como adaptador transitorio de pruebas.
2. `requirements.txt` fija `websockets>=13,<14`. Esa linea satisface tanto Streamlit 1.59 como Alpaca, conserva el cliente legacy requerido por Alpaca y evita la deprecacion introducida en la version 14.
3. El entorno declara `httpx2>=2.7,<3`, adaptador mantenido que Starlette intenta cargar primero para `TestClient`; ya no cae en el fallback deprecado de `httpx`.
4. Las 53 pruebas dirigidas de voz, secretos, agente, sincronizacion, streaming y watchdog pasaron sin warnings. La sonda de voz cerro 4/4 y ambos servicios vivos respondieron HTTP 200 despues del reinicio.
5. La sonda Chromium posterior cerro `OK`, seleccion `Inicio`, cero errores de consola y URL/estado persistidos.
6. La regresion integral final cerro **2.558/2.558** en 146,21 s, **sin advertencias**, con codigo de salida 0. `pip check` no encontro requisitos incompatibles.

Evidencia:

- `alerts/dependency_runtime_probe.json`
- `output/playwright/dependency_runtime.png`
- `requirements.txt`
- pruebas `tests/test_voice_service.py`
- pruebas `tests/test_roxy_voice_smoke.py`
- pruebas `tests/test_roxy_realtime_check.py`

## 111. Contexto coherente de proveedores y seguridad local de voz

1. Diagnostico exigia simultaneamente `ELEVENLABS_API_KEY` y `ELEVENLABS_AGENT_ID` para considerar configurado el proveedor, aunque los flujos actuales de token de conversacion y TTS pueden operar con la clave y un agente predeterminado. Eso producia la contradiccion `ElevenLabs NOT_CONFIGURED` junto a `ElevenLabs runtime AUTH_INVALID`.
2. La presencia de la clave ahora produce `CONFIGURED`; la autenticacion viva permanece separada y sigue mostrando `AUTH_INVALID / HTTP 401`. No se convierte una clave rechazada en una conexion valida.
3. El chequeo de permisos incluye ahora `.env.local` cuando existe, ademas de `.env` y el entorno administrado. Las tres fuentes reales estan en `0600`; el diagnostico nunca lee ni renderiza sus valores.
4. `Seguridad API de voz` deja de marcar el modo local fail-closed como warning: loopback esta `CONNECTED`, clientes remotos reciben 503 y `Acceso remoto de voz` conserva `NOT_CONFIGURED` hasta que existan bind explicito, Bearer y HTTPS.
5. Las pruebas dirigidas cerraron **80/80**. La sonda Chromium de Diagnostico cerro `OK` con 8.825 caracteres, las tres etiquetas `0600`, proveedor configurado y runtime rechazado explicitamente.
6. La regresion integral intermedia cerro **2.560/2.560** en 146,34 s, sin advertencias y con codigo de salida 0.

Evidencia:

- `alerts/provider_context_consistency_probe.json`
- `output/playwright/provider_context_consistency.png`
- `system_diagnostics.py`
- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_secrets_api_security.py`

## 112. Auditoria de dependencias renovada sin romper CCXT

1. `pip-audit` fue regenerado despues de las actualizaciones de Streamlit, WebSockets y httpx2; el reporte ya refleja `streamlit 1.59.2` y `websockets 13.1`.
2. Setuptools 83 corrige `PYSEC-2026-3447`, pero CCXT 4.5.67 —la version mas reciente— declara una dependencia exacta en Setuptools 82.0.1. La prueba de actualizacion produjo un conflicto real de `pip check` y fue revertida inmediatamente.
3. `requirements.txt` hace explicita la restriccion `setuptools==82.0.1`. El entorno final vuelve a `pip check` limpio.
4. El unico hallazgo es de generacion de distribuciones fuente y permanece clasificado como excepcion build-only; Diagnostico informa cero vulnerabilidades accionables de runtime sin ocultar la excepcion.

Evidencia:

- `alerts/dependency_audit.json`
- `requirements.txt`
- `README.md`
- `system_diagnostics.py`

## 113. Circuito persistente para autenticacion rechazada de ElevenLabs

1. La telemetria acumulaba 571 respuestas de autenticacion rechazadas en 24 horas. El cache de sesion evitaba dobles llamadas dentro de un render, pero no sobrevivía reinicios ni distintos procesos.
2. `tools/elevenlabs_roxy.py` persiste ahora un circuito `AUTH_INVALID` ligado al hash no reversible de agente y credencial. No almacena la clave, usa escritura atomica y permisos `0600`.
3. Un 401/403 abre el circuito durante seis horas. La misma credencial recibe un estado local con tiempo restante sin tocar el proveedor; una credencial rotada cambia el fingerprint y vuelve a validarse inmediatamente.
4. El flujo seguro de `provider_credential_setup.py` conserva su comportamiento: una credencial candidata nueva no queda bloqueada por el circuito anterior y solo se persiste si el proveedor la acepta.
5. Diagnostico muestra `Circuito protector activo`, conserva `AUTH_INVALID / HTTP 401` y mantiene la accion de recuperacion segura. El fallback local de voz sigue disponible.
6. La prueba viva produjo una unica llamada para abrir el circuito; dos intentos posteriores conservaron el total de eventos **571 → 571 → 571**. La sonda Chromium cerro `OK` con 9.000 caracteres y URL/estado persistidos.
7. Las suites dirigidas cerraron **126/126** sin advertencias.
8. La regresion integral posterior cerro **2.562/2.562** en 147,60 s, sin advertencias y con codigo de salida 0.

Evidencia:

- `alerts/elevenlabs_auth_circuit.json`
- `alerts/elevenlabs_auth_circuit_probe.json`
- `output/playwright/elevenlabs_auth_circuit.png`
- `tools/elevenlabs_roxy.py`
- `system_diagnostics.py`
- pruebas `tests/test_elevenlabs_roxy.py`
- pruebas `tests/test_system_diagnostics.py`

## 114. Sondas visuales concurrentes sin reducir cobertura

1. El watchdog verificaba las rutas operativas de ETH/USD y busqueda AAPL en serie. Cada navegador conserva una observacion de 12 segundos para demostrar actualizacion viva sin recarga, por lo que la fase completa consumia aproximadamente 39 segundos.
2. `ensure_dashboard_render_probe_report` ejecuta ahora ambas sondas independientes con dos workers. Cada proceso mantiene su propia URL, captura, reporte, timeout y contrato de persistencia; no se redujo el tiempo de observacion ni se omitio ninguna comprobacion.
3. La prueba dirigida usa una barrera de threads y exige un pico de dos ejecuciones simultaneas. Las aserciones de URL y texto requerido son independientes del orden de scheduling, evitando una prueba fragil.
4. La medicion viva cerro `primary OK; search OK` en **21,09 s**, frente a unos 39 s anteriores: una reduccion aproximada del 46 %. ETH/USD y AAPL conservaron simbolo, mercado y temporalidad `1h`, y ambas rutas confirmaron `live_no_reload=true`.
5. El ciclo 38 del LaunchAgent termino con codigo 0, libero el candado y publico las dos sondas oficiales `OK` en 19,81 s y 20,55 s dentro de la misma ventana concurrente. La recuperacion sostenida del nucleo avanzo a 5/10; los bloqueos externos permanecen identificados.
6. El modulo completo del watchdog cerro **645/645**. La regresion integral posterior cerro **2.562/2.562** en 145,19 s, sin advertencias y con codigo de salida 0.

Evidencia:

- `alerts/dashboard_render_probe.json`
- `alerts/dashboard_render_probe_search.json`
- `alerts/roxy_realtime_lock.json`
- `tools/roxy_realtime_check.py`
- pruebas `tests/test_roxy_realtime_check.py`

## 115. Compatibilidad temporal NumPy/yfinance sin ocultar advertencias

1. NumPy 2.5.1 introdujo una deprecacion para unidades genericas de `timedelta`; `yfinance` 1.5.1, su version mas reciente, todavia usa ese camino en `_interval_to_timedelta` y `_dts_in_same_interval`.
2. La llamada minima a `yfinance.utils._interval_to_timedelta("1h")` reprodujo una advertencia con NumPy 2.5.1. La documentacion oficial de NumPy confirma que este comportamiento se convertira en error futuro.
3. `requirements.txt` declara temporalmente `numpy>=2.0,<2.5`. Se instalo NumPy 2.4.6, la ultima version de la rama compatible; el mismo caso minimo produce cero advertencias y `pip check` permanece limpio.
4. No se agrego un filtro para silenciar el problema. El limite queda visible y documentado hasta que yfinance elimine la conversion generica.
5. El servicio Streamlit fue reiniciado sobre NumPy 2.4.6 y respondio HTTP 200. Un ciclo completo del watchdog termino con codigo 0 y agrego **0 bytes** a su log de errores, frente a las advertencias repetidas anteriores.
6. Las 201 pruebas dirigidas de datos, graficas, research, streaming y watchlists pasaron. `dependency_audit.json` fue regenerado y refleja NumPy 2.4.6; conserva solamente la excepcion build-only conocida de Setuptools.

Evidencia:

- `requirements.txt`
- `alerts/dependency_audit.json`
- `alerts/roxy_realtime_lock.json`
- pruebas de mercado y graficas bajo `tests/`

## 116. Marcadores de foco y SLO sin dobles conteos

1. `roxy_status.json` usa `-` cuando no existe una oportunidad operativa. La decision de autoheal interpretaba ese marcador como ticker real, mientras la sonda elegia correctamente ETH/USD como fallback; el desacuerdo forzaba una segunda pareja de navegadores.
2. Los valores vacios conocidos (`-`, `--`, raya, `N/A`, `NA`, `NONE`, `NULL`) se normalizan ahora en una sola funcion. Si aparece un ticker real en el siguiente campo, conserva prioridad y sigue obligando a actualizar la sonda.
3. El ciclo de aceptacion paso de aproximadamente 80 s a **32 s**, no entro en fases de render, no modifico las capturas frescas y agrego 0 bytes al log de errores. El LaunchAgent termino con codigo 0.
4. El SLO podia contar dos veces la entrada actual despues de anexarla al historial: el resumen estructurado mostraba 7/10 y el texto 8/10. `validate_health_stability_slo` reemplaza ahora la ultima entrada cuando coincide `generated_at`, en vez de volver a agregarla.
5. El siguiente ciclo vivo publico **8/10** y 2 ciclos restantes tanto en `stability_summary` como en `health_stability_slo`; el fragmento textual tambien coincide. Las sondas permanecieron frescas sin regeneracion.
6. La prueba de SLO exige tres muestras y streak 3 cuando `current_entry` coincide con la tercera fila, impidiendo regresar al conteo 4. La prueba de foco verifica tanto marcadores vacios como cambio real a BTC/USD.
7. El modulo del watchdog cerro **647/647**. La regresion integral final cerro **2.564/2.564** en 145,89 s, sin advertencias y con codigo de salida 0. `git diff --check` y `pip check` permanecen limpios.

Evidencia:

- `alerts/roxy_realtime_check.json`
- `alerts/roxy_realtime_history.jsonl`
- `alerts/dashboard_render_probe.json`
- `alerts/roxy_realtime_lock.json`
- `tools/roxy_realtime_check.py`
- pruebas `tests/test_roxy_realtime_check.py`

## 117. Recuperacion sostenida y degradacion externa explicita

1. El unico warning de mantenimiento interno aparente provenia del directorio externo `/Volumes/RoxyData/MacArchive/log_snapshots`: existe, pero su exploracion acotada expira a los cinco segundos. Archivos locales, SQLite, historiales, cache y presupuesto permanecen operativos.
2. El reporte fuente distingue ahora `internal_protected=true`, `external_snapshot_degraded=true` y `protected=false`. Conserva status `WARN` y la accion `Revisar acceso a snapshots en RoxyData`; no convierte una dependencia externa inaccesible en `OK`.
3. La etiqueta generica `Revisar limpieza` fue reemplazada en este caso aislado por `Interno protegido / snapshots degradados`, tanto en higiene como en operacion y aliases superiores. Fallos reales de archivo, permisos internos o SQLite conservan su clasificacion anterior.
4. La prueba dedicada exige status degradado, proteccion interna, proteccion global falsa y aliases consistentes. Las 64 pruebas de mantenimiento y las suites combinadas de Diagnostico/watchdog pasaron.
5. El ciclo natural 43 avanzo el nucleo a 9/10. El ciclo natural 44 cerro **10/10** en `stability_summary` y `health_stability_slo`, `core_recovery_state=RECOVERED`, `core_recovered_sustained=true` y etiqueta `Core operativo / externo bloqueado`.
6. El LaunchAgent termino con codigo 0 y quedo en reposo. Alpaca `AUTH_INVALID` y snapshots RoxyData degradados siguen visibles como bloqueos externos; no se presentan como resueltos.
7. La regresion integral final cerro **2.565/2.565** en 146,31 s, sin advertencias y con codigo de salida 0.

Evidencia:

- `alerts/output_maintenance.json`
- `alerts/output_maintenance.txt`
- `alerts/roxy_realtime_check.json`
- `alerts/roxy_realtime_history.jsonl`
- `alerts/roxy_realtime_lock.json`
- `tools/output_maintenance.py`
- pruebas `tests/test_output_maintenance.py`
- pruebas `tests/test_roxy_realtime_check.py`

## 118. Aceptacion por fase generada desde evidencia viva

1. El resumen ejecutivo se actualizo contra el worktree y runtime actuales: 342 modulos Python de aplicacion, 157 archivos de prueba, 45.851 lineas en `streamlit_app.py`, 29 tablas SQLite, Streamlit 1.59.2, NumPy 2.4.6 y regresion 2.570/2.570 sin advertencias.
2. La cabecera ya no presenta la vision total como terminada. Una matriz cruza las siete fases con evidencia, alcance aceptado y condiciones pendientes; diferencia aceptacion local, mercado parcial y bloqueo externo.
3. `tools/platform_acceptance.py` publica `roxy-platform-acceptance/1.0.0`. Lee fail-closed el health, matriz responsive, salud de graficas, sincronizacion/ciclo de oportunidades, mantenimiento y cinco pruebas de voz. Evidencia ausente produce `INCOMPLETE`, nunca un aprobado por defecto.
4. El snapshot real queda `IN_PROGRESS`: 0/7 fases aceptadas sin condiciones, 6 parciales y 1 incompleta. Cripto es el unico mercado permitido; acciones/opciones siguen bloqueadas. Fase 7 conserva correo, documentos, hogar, compras y cliente movil como pendientes.
5. El contrato promueve automaticamente fases de datos, graficas y oportunidades a `ACCEPTED` si acciones y cripto aparecen permitidas; aun asi no puede declarar la vision completa mientras Ecosistema permanezca en progreso.
6. Diagnostico muestra tres metricas y una lista semantica con estado, evidencia y pendiente por fase, ademas de la tabla explorable. La primera sonda descubrio que el dataframe por si solo no exponia sus celdas como texto accesible; la lista visible corrigio esa brecha sin retirar la tabla.
7. La sonda Chromium final cerro `OK`, 2.056 caracteres, URL/estado persistidos, estados parciales y pendiente movil visibles, cero errores bloqueantes. Las cinco pruebas del contrato pasaron; la regresion integral cerro **2.570/2.570** en 147,92 s, sin advertencias.

Evidencia:

- `alerts/platform_phase_acceptance.json`
- `alerts/platform_phase_acceptance_probe.json`
- `output/playwright/platform_phase_acceptance.png`
- `tools/platform_acceptance.py`
- `streamlit_app.py`
- pruebas `tests/test_platform_acceptance.py`

## 119. Tareas personales durables conectadas a Roxy

1. La auditoria de fase 7 encontro que los recordatorios de voz se guardaban como memorias genericas: no tenian fecha estructurada, prioridad, ciclo de vida ni una vista operativa. Verlos en una respuesta de voz no demostraba que existiera un sistema de tareas.
2. `PersonalTaskStore` publica un contrato local atomico y bloqueado por archivo. Cada registro contiene usuario normalizado, titulo, notas, fecha UTC opcional, prioridad, estado, fuente y timestamps. No incluye seeds ni relleno simulado; una vista vacia lo declara expresamente.
3. Los estados `PENDING`, `IN_PROGRESS`, `DONE` y `ARCHIVED` usan transiciones validadas. Archivar es recuperable y reemplaza una eliminacion destructiva. Las lecturas y mutaciones filtran por usuario; una identidad distinta recibe `KeyError` en vez de modificar datos ajenos.
4. El agente de calendario ya no crea un recordatorio separado en memoria. Voz y texto escriben el mismo archivo `data/roxy_personal_tasks.json` que consume la ruta canonica `Tareas`; el snapshot de tareas activas tambien entra al contexto compartido de Roxy.
5. La interfaz muestra estado de sincronizacion, fuente y ultima escritura reales; permite crear, iniciar, completar, restaurar, archivar y filtrar. Las fechas introducidas como ET se almacenan en UTC. El estado local participa ahora en el contrato revisionado; el transporte fisico permanece bloqueado hasta configurar Bearer, bind remoto y HTTPS.
6. La ruta se agrego al camino rapido del frontend, evitando cargar mercado, graficas y proveedores para gestionar una tarea. El probe aprendio la diferencia entre la ruta `Tareas` y su etiqueta accesible `Tareas personales`, conservando la validacion estricta de URL y selector.
7. Las sondas Chromium de 1.440x1.000 y 390x844 cerraron `OK`, sin errores bloqueantes, sin perdida de simbolo/mercado/temporalidad y con los estados operativos visibles. Un flujo manual automatizado creo y completo una tarea del usuario de diagnostico; luego se archivo de manera recuperable.
8. `roxy-personal-tasks/1.0.0` comprueba durabilidad, aislamiento, ciclo de vida, coherencia de voz, ruta/contexto y runtime escritorio/movil usando datos temporales. La fase 7 incorpora esa evidencia, pero conserva `IN_PROGRESS`: correo, documentos, hogar, compras, sincronizacion remota y cliente movil siguen pendientes.
9. Las 78 pruebas dirigidas pasaron. La regresion integral cerro **2.580/2.580** en 146,94 s, sin advertencias y con codigo de salida 0.

Evidencia:

- `alerts/personal_task_check.json`
- `alerts/personal_tasks_desktop_probe.json`
- `alerts/personal_tasks_mobile_probe.json`
- `output/playwright/personal_tasks_desktop.png`
- `output/playwright/personal_tasks_mobile.png`
- `roxy_os/personal_tasks.py`
- `tools/personal_task_check.py`
- pruebas `tests/test_personal_tasks.py`
- pruebas `tests/test_personal_task_check.py`
- pruebas `tests/test_roxy_os.py`

## 122. Repositorio documental privado y verificable

1. El lector previo aceptaba rutas arbitrarias despues de un permiso, pero Roxy no tenia un repositorio propio, inventario por usuario, integridad, ciclo de vida ni una superficie desde la que administrar documentos cotidianos.
2. `DocumentVault` publica `roxy-document-vault/1.0.0`. Importa solo TXT, MD, CSV, JSON, PDF, DOCX y XLSX hasta 10 MB; sanea nombres, impide traversal, calcula SHA-256 y consolida contenido activo duplicado.
3. El indice es atomico y usa lock. Directorios y objetos usan permisos 700/600. Cada lectura valida usuario, estado activo, existencia e integridad del contenido antes de devolver bytes; una identidad distinta no puede acceder por ID.
4. Archivar no elimina el objeto y puede revertirse. La interfaz no expone paths internos ni lee contenido durante el listado. `Preparar contenido` es una accion separada; solo entonces habilita preview de texto o descarga verificada.
5. El agente `documents` responde a “mis documentos” con metadatos del mismo vault y declara `content_read=false`. El snapshot entra al contexto compartido, pero el contenido no se inyecta automaticamente en voz o memoria.
6. La ruta `Documentos` muestra fuente, usuario, timestamp y `LOCAL_ONLY_UNENCRYPTED`. La advertencia de falta de cifrado es visible; el limite Streamlit global se redujo de 200 MB a 10 MB para coincidir con el backend.
7. Playwright aprobo escritorio y telefono en estado vacio. Un segundo flujo real cargo el fixture sin secretos, guardo el objeto, preparo y mostro el contenido verificado, ofrecio descarga y archivo el registro; cero errores de consola bloqueantes.
8. El contrato dedicado prueba durabilidad, SHA-256, aislamiento, deduplicacion, archivo/restauracion, voz metadata-only, lectura explicita y runtime responsive sin mutar usuarios productivos. Queda `contract_status=OK` y `status=WARN` por cifrado en reposo ausente.
9. La regresion integral cerro **2.606/2.606** en 148,64 s, sin advertencias y con codigo de salida 0.

Evidencia:

- `alerts/document_vault_check.json`
- `alerts/document_vault_desktop_probe.json`
- `alerts/document_vault_mobile_probe.json`
- `output/playwright/document_vault_desktop.png`
- `output/playwright/document_vault_mobile.png`
- `roxy_os/document_vault.py`
- `tools/document_vault_check.py`
- pruebas `tests/test_document_vault.py`
- pruebas `tests/test_document_vault_check.py`
- pruebas `tests/test_roxy_os.py`

## 123. Gmail metadata-only y envio bloqueado

1. Roxy solo tenia SMTP para alertas salientes. No existia una bandeja personal, lector OAuth ni separacion entre metadatos, cuerpos y envio; la recuperacion de cuenta tambien declaraba correo no configurado.
2. `GmailReadonlyClient` publica `roxy-email-readonly/1.0.0` sobre endpoints fijos de Gmail. Usa `ROXY_GMAIL_ACCESS_TOKEN`, timeout acotado y distingue `SERVICE_NOT_CONFIGURED`, `AUTH_INVALID`, `RATE_LIMITED`, `UNAVAILABLE`, `ERROR` y `CONNECTED`.
3. La consulta de INBOX limita el lote a cinco mensajes y solicita `format=metadata` con solo From, Subject y Date. No incluye snippet, body ni adjuntos; cada fila declara `body_loaded=false`.
4. El token solo entra al header Bearer y nunca aparece en snapshots, errores o diagnósticos. `send()` no tiene camino de red y siempre devuelve `SEND_DISABLED`; la politica global tambien bloquea solicitudes textuales de envio sensible.
5. `EmailAgent` comparte el mismo snapshot de metadatos con voz y abre la ruta `Correo`; no resume cuerpos. La pagina usa cache clasificado `email_metadata` de 30 segundos, incorporado como la clase 22 del contrato central de cache.
6. La interfaz muestra `READ_ONLY`, proveedor, estado y timestamp. Sin OAuth publica `SERVICE_NOT_CONFIGURED`; Gmail y Outlook/Microsoft Graph tienen ahora adaptadores reales independientes y ninguno se presenta como conectado sin token.
7. Playwright aprobo escritorio y telefono, con URL/contexto persistidos, envio deshabilitado visible y cero errores bloqueantes. El runtime real no tiene token y permanece correctamente degradado.
8. Dos regresiones integrales iniciales detectaron contratos historicos: un TTL literal fuera de la politica y el conteo anterior de 21 clases. Se creo `email_metadata`, el diagnostico paso a 22 clases y ambos casos quedaron cubiertos antes de aceptar el cambio.
9. Este corte histórico cerró Gmail con `contract_status=OK`, `status=WARN`, `provider_status=SERVICE_NOT_CONFIGURED` y `send_enabled=false`; la ampliación posterior a Outlook se documenta en la sección 126.

Evidencia:

- `alerts/email_check.json`
- `alerts/email_desktop_probe.json`
- `alerts/email_mobile_probe.json`
- `output/playwright/email_desktop.png`
- `output/playwright/email_mobile.png`
- `roxy_os/email_service.py`
- `tools/email_check.py`
- `roxy_trader/cache_policy.py`
- pruebas `tests/test_email_service.py`
- pruebas `tests/test_email_check.py`
- pruebas `tests/test_cache_policy.py`
- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_roxy_os.py`

## 124. Sincronizacion revisionada de tareas y compras

1. El contrato entre dispositivos sube a `roxy-device-sync/1.1.0`. El snapshot canónico contiene cuatro ambitos por usuario: watchlists/alertas, estado visible, tareas personales y lista de compras.
2. Tareas y compras almacenan una revision monotonica por usuario. Crear, consolidar o cambiar realmente el ciclo de vida incrementa la revision; un dispositivo con una revision vencida recibe conflicto y no puede sobrescribir cambios nuevos.
3. Los reemplazos remotos normalizan cada fila, limitan el lote a 1.000 registros y fuerzan el namespace solicitado por la ruta. Un payload no puede insertar datos bajo otra identidad.
4. `PUT /v1/state-sync/{user_id}` conserva semantica parcial: solo procesa ambitos presentes. Una actualizacion exclusiva de tareas no reemplaza ni provoca conflictos en watchlists, interfaz o compras.
5. El reinicio del servicio descubrio un `NaN` historico en una oportunidad archivada. FastAPI rechazo correctamente el snapshot como JSON no conforme y devolvio 500. `WatchlistStore` convierte ahora metricas no finitas en `null`, persiste con `allow_nan=False` y prueba tanto snapshot como archivo estricto.
6. Tras reiniciar el LaunchAgent, `/health` y el endpoint vivo respondieron correctamente. El snapshot real devolvio `status=OK`, contrato `1.1.0`, los cuatro ambitos y `auth_mode=loopback-only`; no se expusieron contenidos personales durante la verificacion.
7. `roxy-device-sync-check/1.0.0` prueba con almacenes temporales los cuatro ambitos, proteccion contra escrituras vencidas y aislamiento de actualizaciones parciales. El runtime actual queda `contract_status=OK`, `status=WARN` y `remote_status=NOT_CONFIGURED`.
8. Fase 7 reconoce la sincronizacion revisionada como capacidad probada, pero sigue `IN_PROGRESS`. Faltan credencial Bearer, bind no-loopback, HTTPS/reverse proxy y una validacion completa en iPad/telefono fisicos.
9. La regresion integral final cerro **2.627/2.627** en 150,41 s, sin advertencias. `pip check` no encontro dependencias rotas y `git diff --check` termino limpio.

Evidencia:

- `alerts/device_sync_check.json`
- `roxy_trader/device_sync.py`
- `roxy_trader/watchlists.py`
- `tools/device_sync_check.py`
- `tools/voice_service.py`
- pruebas `tests/test_device_sync.py`
- pruebas `tests/test_device_sync_check.py`
- pruebas `tests/test_personal_tasks.py`
- pruebas `tests/test_shopping_list.py`
- pruebas `tests/test_watchlists.py`

## 125. Cifrado autenticado del repositorio documental

1. `DocumentVault` sube a `roxy-document-vault/1.1.0`. Cada objeto nuevo se cifra con AES-256-GCM, nonce aleatorio y el SHA-256 del contenido como dato autenticado asociado; el nombre y el contenido original no se escriben dentro del blob cifrado.
2. La clave de 32 bytes vive fuera de `data/roxy_documents`, por defecto en Application Support de Roxy, y usa permisos 600. El indice conserva solo un fingerprint corto; una clave distinta produce `KEY_MISMATCH` y no intenta descifrar silenciosamente.
3. La lectura autentica primero el ciphertext y luego vuelve a verificar el SHA-256 del plaintext. Alterar un byte produce un error de autenticacion cubierto por prueba.
4. La migracion de objetos heredados valida el hash antes de cifrar y reemplaza cada objeto de forma atomica. Es idempotente y distingue objetos migrados, ya cifrados y faltantes.
5. El repositorio vivo contenia un objeto archivado heredado. La migracion real cerro con 1 cifrado, 0 faltantes y verificacion posterior correcta; clave e indice quedaron con permisos 600. No se imprimio ni registro material secreto.
6. La interfaz muestra `LOCAL_ENCRYPTED`, algoritmo y estado de clave. Si encuentra estado mixto ofrece una accion explicita de migracion; ya no presenta la advertencia historica de contenido sin cifrar.
7. Las sondas reales de escritorio (1.440x1.000) y telefono (390x844) cerraron `OK`, conservaron URL/simbolo/mercado/temporalidad y mostraron AES-256-GCM sin errores bloqueantes.
8. `document_vault_check.json` queda `status=OK`, `contract_status=OK` y `at_rest_encryption=true`. La aceptacion de Fase 7 elimina el bloqueo documental, pero permanece en progreso por transporte movil, Home Assistant y OAuth/Outlook.
9. La regresion integral final cerro **2.631/2.631** en 200,04 s, sin advertencias ni fallos.

Evidencia:

- `alerts/document_vault_check.json`
- `alerts/document_vault_desktop_probe.json`
- `alerts/document_vault_mobile_probe.json`
- `output/playwright/document_vault_desktop.png`
- `output/playwright/document_vault_mobile.png`
- `roxy_os/document_vault.py`
- `tools/document_vault_check.py`
- pruebas `tests/test_document_vault.py`
- pruebas `tests/test_document_vault_check.py`
- pruebas `tests/test_platform_acceptance.py`

## 126. Outlook Microsoft Graph metadata-only

1. El contrato de correo sube a `roxy-email-readonly/1.1.0`. `ROXY_EMAIL_PROVIDER=gmail|outlook` selecciona el proveedor canónico para voz y contexto; la interfaz permite cambiarlo sin recargar la aplicación.
2. `OutlookReadonlyClient` usa exclusivamente endpoints fijos `https://graph.microsoft.com/v1.0/me` y `/me/mailFolders/inbox/messages`. Requiere `ROXY_OUTLOOK_ACCESS_TOKEN` con `Mail.Read`; sin token no hace ninguna petición y devuelve `SERVICE_NOT_CONFIGURED`.
3. La consulta limita `$top` a cinco y `$select` a id, conversación, remitente, asunto, fecha, lectura y categorías. No solicita `body`, `bodyPreview`, adjuntos ni contenido MIME.
4. Gmail valida ahora también el identificador de cada mensaje antes de componer su ruta; referencias con traversal o query injection se descartan sin realizar una segunda petición.
5. Ambos adaptadores normalizan el mismo snapshot, distinguen autenticación inválida, rate limit, timeout, HTTP y JSON defectuoso. `send()` no contiene un camino de red y siempre devuelve `SEND_DISABLED`.
6. El agente de Roxy usa el proveedor configurado, identifica Gmail u Outlook en su explicación y comparte exclusivamente asuntos/metadatos; `body_read=false` permanece invariable.
7. Playwright abrió la ruta real con autenticación diagnóstica, seleccionó Outlook y confirmó `SERVICE_NOT_CONFIGURED`, `Mail.Read`, modo `READ_ONLY`, contexto persistente y cero errores de consola. Las sondas de escritorio y teléfono quedaron `OK` y prohíben el texto histórico `NOT_IMPLEMENTED`.
8. `email_check.json` prueba ambos proveedores: Gmail y Outlook están `SERVICE_NOT_CONFIGURED`, el contrato está `OK` y el estado general queda `WARN` hasta aportar OAuth real. Fase 7 ya no bloquea por implementación ausente, sino por conexión OAuth verificable.
9. La regresion integral final cerro **2.636/2.636** en 149,14 s, sin advertencias ni fallos.
10. La primera prueba del endpoint vivo descubrio una desconexion no cubierta por la UI: “revisa mis correos” se enviaba al cerebro bursatil, que interpretaba `REVISA` como ticker. El servicio de voz enruta ahora intenciones personales de correo, documentos, calendario, hogar y compras a `RoxyOrchestrator` antes de extraer simbolos de mercado.
11. Tras reiniciar `com.roxy.voice-live`, `/v1/assist/state` devolvio `intent=email_query`, `agent=email`, `response_source=roxy_os`, cuerpo no leido y envio deshabilitado. La respuesta bursatil incorrecta desaparecio y quedo cubierta por integracion HTTP.
12. La regresion integral posterior al cambio de voz cerro **2.637/2.637** en 148,50 s, sin advertencias ni fallos.

Evidencia:

- `alerts/email_check.json`
- `alerts/email_desktop_probe.json`
- `alerts/email_mobile_probe.json`
- `output/playwright/email_desktop.png`
- `output/playwright/email_mobile.png`
- `output/playwright/email_outlook_desktop.png`
- `roxy_os/email_service.py`
- `tools/email_check.py`
- pruebas `tests/test_email_service.py`
- pruebas `tests/test_email_check.py`
- pruebas `tests/test_platform_acceptance.py`
- pruebas `tests/test_roxy_os.py`
- pruebas `tests/test_voice_service.py`

## 127. Cliente móvil PWA para estado operativo

1. La auditoría confirmó que `/roxy-live` era una superficie extensa de voz y perfil, pero no consumía `/v1/state-sync`: mostrar una watchlist escrita en localStorage no equivalía a compartir el estado canónico.
2. `/roxy-mobile` publica una PWA enfocada en operación diaria. Su manifest permite instalación standalone; el service worker cachea únicamente shell estático y excluye toda ruta `/v1/`.
3. El cliente consume `roxy-device-sync/1.1.0` y muestra revisiones de watchlists, interfaz, tareas y compras. Permite cambiar símbolo/temporalidad, agregar tareas/artículos/activos y actualizar estados sin recargar.
4. Cada escritura envía `expected_revision`. HTTP 409 obliga a descargar el snapshot nuevo y muestra conflicto; nunca reintenta una edición vencida de manera silenciosa.
5. Token y snapshots viven solo en memoria JavaScript: no usan localStorage ni sessionStorage. Fuera de localhost, el cliente bloquea cualquier petición si el origen no es HTTPS. Las respuestas API usan `cache=no-store` y el service worker no las intercepta.
6. El servidor entrega CSP sin `unsafe-inline`, `frame-ancestors none`, `form-action self`, `no-referrer`, `nosniff` y `Cache-Control: no-store`. El service worker tiene alcance explícito `/`.
7. La primera ejecución Playwright encontró un error de sintaxis del renderer y un favicon 404. Ambos se corrigieron antes de aceptar la superficie; `node --check` cubre cliente y worker en el diagnóstico.
8. El navegador real conectó por loopback, recibió contrato `1.1.0`, `auth_mode=loopback-only`, dos watchlists y el estado UI real. Tareas y compras vacías mostraron estados explícitos sin datos simulados. Escritorio y 390x844 cerraron con cero errores.
9. `roxy-mobile-client/1.0.0` queda `contract_status=OK`, `client_status=READY_LOCAL`, `pwa_installable=true` y `remote_status=NOT_CONFIGURED`. El cliente está implementado; aún faltan Bearer, bind no-loopback, HTTPS y validación en iPad/teléfono físicos.
10. La regresión integral final cerró **2.641/2.641** en 149,43 s, sin advertencias ni fallos. Node, compilación Python, dependencias y `git diff --check` también terminaron limpios.

Evidencia:

- `alerts/mobile_client_check.json`
- `output/playwright/roxy_mobile_desktop.png`
- `output/playwright/roxy_mobile_phone.png`
- `assets/roxy_mobile.html`
- `assets/roxy_mobile.css`
- `assets/roxy_mobile.js`
- `assets/roxy_mobile_sw.js`
- `tools/mobile_client_check.py`
- pruebas `tests/test_mobile_client_check.py`
- pruebas `tests/test_voice_service.py`
- pruebas `tests/test_device_sync.py`
- pruebas `tests/test_platform_acceptance.py`

## 128. Gateway móvil HTTPS aislado y listo para prueba física

1. El cliente PWA ya existía, pero el servicio canónico seguía limitado a loopback. Se creó un gateway independiente en `0.0.0.0:8443`; el backend local de voz conserva su bind privado y no comparte su LaunchAgent ni su archivo de entorno.
2. `tools/mobile_gateway.py` genera una CA local, certificado de servidor con SAN para localhost, hostname e IPv4 LAN, clave Bearer de alta entropía y allowlist exclusiva de `local_user`. Claves, token, entorno y hoja de emparejamiento viven fuera del repositorio con permisos 600 dentro de un directorio 700.
3. El LaunchAgent no contiene el token ni credenciales de proveedores. Solo carga el entorno aislado y arranca Uvicorn con certificado y clave explícitos. La reinstalación reutiliza credenciales válidas; `--rotate` es una acción separada que obliga a volver a vincular dispositivos.
4. La reinstalación descubrió una carrera real de `launchd`: un `bootstrap` podía devolver error 5, o aceptar el servicio antes de terminar el `bootout` anterior. El instalador ahora reintenta, espera el asentamiento y confirma que la etiqueta permanece cargada; el chequeo de runtime también tolera el tiempo de arranque del API.
   El recuperador general permite `--service mobile_gateway` para volver a cargar una instalación detenida, pero el gateway permanece opcional y no degrada el núcleo de una instalación que aún no habilitó acceso móvil.
5. `/roxy-mobile-pair` solo responde a loopback y muestra la URL, usuario y Bearer al operador sentado frente al Mac. `/roxy-mobile-ca.crt` distribuye únicamente el certificado público. `/roxy-mobile-ca.mobileconfig` construye un perfil iOS/iPadOS instalable con payload `com.apple.security.root`; contiene la CA pública, pero no el Bearer ni una clave privada. La hoja y el perfil usan `no-store`; la hoja además aplica CSP restrictiva.
6. La prueba TLS local validó la cadena contra la CA propia, `/health=200`, state-sync sin credencial `401` y con Bearer `200`, `auth_mode=bearer` y contrato `roxy-device-sync/1.1.0`. Los cuatro ámbitos canónicos —watchlists, UI, tareas y compras— llegaron en el mismo snapshot sin imprimir contenidos ni secretos.
7. `roxy-mobile-gateway/1.0.0` verifica archivos privados, SAN/expiración, LaunchAgent aislado, proceso, política HTTPS/Bearer/allowlist, runtime autenticado y perfil CA iOS sin credenciales. El snapshot real queda `contract_status=OK`, `gateway_status=READY_FOR_PHYSICAL_TEST`, `physical_reachability=UNVERIFIED` y `secrets_exposed=false`.
8. La aceptación de Fase 7 reemplaza el bloqueo genérico de “falta HTTPS/Bearer” por el pendiente exacto: instalar/confiar la CA y validar desde iPad o teléfono físico. El diagnóstico interno muestra `WARNING`, no `CONNECTED`, hasta disponer de esa evidencia.
9. Las conexiones del propio Mac hacia sus direcciones LAN aceptaron TCP pero no completaron HTTP/TLS —el mismo comportamiento apareció contra Streamlit HTTP—, por lo que no constituyen una prueba válida del camino Wi-Fi. No se declara conectividad física ni se rebaja este límite mediante una excepción insegura.
10. La compilación estricta terminó limpia y, tras incorporar el perfil iOS y el estado coherente de sincronización, la regresión integral cerró **2.654/2.654** en 153,43 s, sin fallos ni advertencias. `pip check` y `git diff --check` se ejecutaron después para verificar dependencias y formato del worktree.

Evidencia:

- `alerts/mobile_gateway_check.json`
- `tools/mobile_gateway.py`
- `tools/mobile_gateway_check.py`
- `tools/voice_service.py`
- `system_diagnostics.py`
- pruebas `tests/test_mobile_gateway.py`
- pruebas `tests/test_mobile_gateway_check.py`
- pruebas `tests/test_voice_service.py`
- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_platform_acceptance.py`

## 129. Comprobante remoto verificable y recuperación sostenida del núcleo

1. La auditoría del flujo móvil detectó que una futura conexión real no dejaba evidencia durable: incluso después de usar el iPad, el diagnóstico habría permanecido indefinidamente en `UNVERIFIED`.
2. La PWA llama ahora `POST /v1/mobile/physical-proof/{user_id}` solamente cuando su origen es HTTPS y no es localhost. El endpoint vuelve a exigir Bearer, rate limit y allowlist; rechaza explícitamente loopback, HTTP y usuarios no permitidos.
3. `roxy-mobile-physical-proof/1.0.0` guarda fuera del repositorio un timestamp, el usuario permitido y fingerprints unidireccionales de cliente, Bearer y CA. No persiste IP, token, clave privada, User-Agent ni contenido personal. El archivo usa reemplazo atómico y permisos 600.
4. La evidencia queda ligada al material criptográfico actual. Rotar Bearer/CA, alterar el comprobante, usar otro usuario, omitir HTTPS o dejarlo vencer por más de 30 días impide la promoción.
5. `mobile_gateway_check` conserva `READY_FOR_PHYSICAL_TEST / UNVERIFIED` sin una conexión física. Con comprobante válido cambia a `CONNECTED_PHYSICAL / VERIFIED_REMOTE_CLIENT`; cliente PWA, sincronización, diagnóstico y aceptación consumen el mismo estado. Una prueba local recibió 403 y no creó el archivo.
6. La matriz de Fase 1 exponía `INCOMPLETE` sin explicar que la ventana sostenida iba 7/10. El contrato ahora muestra el contador y ciclos restantes mientras está `PENDING`, aunque el runtime actual ya sea OK.
7. Se observaron, sin forzar reinicios, los tres heartbeats programados restantes: 8/10, 9/10 y finalmente 10/10. El estado vivo quedó `RECOVERED`, `core_recovered_sustained=true`, runtime `OK` y etiqueta `Core operativo / externo bloqueado`.
8. La aceptación consolidada pasa de 5 a 6 fases parciales y deja solo Fase 7 incompleta. Fase 1 es `PARTIAL_EXTERNAL`; sus únicos bloqueos son Alpaca `AUTH_INVALID`/proveedor equivalente y snapshots RoxyData fuera de timeout.
9. La compilación estricta de Python, `node --check` y la regresión integral final cerraron **2.662/2.662** en 153,46 s, sin fallos ni advertencias.

Evidencia:

- `alerts/mobile_gateway_check.json`
- `alerts/mobile_client_check.json`
- `alerts/device_sync_check.json`
- `alerts/platform_phase_acceptance.json`
- `alerts/roxy_realtime_check.json`
- `assets/roxy_mobile.js`
- `tools/voice_service.py`
- `tools/mobile_gateway_check.py`
- pruebas `tests/test_voice_service.py`
- pruebas `tests/test_mobile_gateway_check.py`
- pruebas `tests/test_mobile_client_check.py`
- pruebas `tests/test_device_sync_check.py`
- pruebas `tests/test_platform_acceptance.py`
- pruebas `tests/test_system_diagnostics.py`

## 130. Activación segura de Home Assistant, Gmail y Outlook

1. La auditoría confirmó que el modo bursátil degradado ya usa velas reales de yfinance, declara `FALLBACK/is_delayed` y bloquea señales rápidas, alertas y ejecución. No se creó una segunda ruta ni se relajó el gate premium.
2. El hueco operativo estaba en la activación: `provider_credential_setup.py` solo aceptaba Alpaca y ElevenLabs aunque los adaptadores Home Assistant, Gmail y Outlook ya existían.
3. El instalador admite ahora `home_assistant`, `gmail` y `outlook`. Cada proveedor tiene una allowlist de variables y grupos requeridos; rechaza claves cruzadas, valores vacíos y placeholders antes de cualquier petición o escritura.
4. Home Assistant valida URL segura y token mediante `/api/`, sin leer entidades durante la instalación. Persiste `ROXY_HOME_CONTROL_ENABLED=0`; habilitar luces/switches continúa siendo una decisión separada con permiso y doble confirmación.
5. Gmail valida el perfil con alcance `gmail.readonly`; Outlook valida `/me` con `Mail.Read`. Ambos resultados conservan `read_only=true`, `send_enabled=false` y no incluyen token ni cuenta en el JSON del instalador.
6. Los tokens de correo se identifican como access tokens temporales. Su expiración vuelve a `AUTH_INVALID`; el flujo no afirma refresh OAuth automático donde todavía no existe.
7. Una validación fallida conserva el entorno anterior y no reinicia servicios. Una validación correcta escribe proyecto y entorno administrado mediante temporal, `fsync`, reemplazo atómico y permisos 600, y reinicia solo consumidores cargados.
8. El gateway móvil carga primero el entorno administrado compartido y después su entorno aislado. De este modo voz/contexto móvil ve las mismas integraciones, mientras el Bearer propio del gateway tiene precedencia; ninguna credencial queda incrustada en el plist.
9. La aceptación por fases incluye ahora el comando seguro exacto junto a cada bloqueo de Alpaca, ElevenLabs, Home Assistant y correo, sin presentar una integración como conectada antes de la validación real.
10. La compilación estricta y la regresión integral cerraron **2.668/2.668** en 156,98 s, sin fallos ni advertencias.

Evidencia:

- `tools/provider_credential_setup.py`
- `tools/mobile_gateway.py`
- `tools/mobile_gateway_check.py`
- `tools/platform_acceptance.py`
- `README.md`
- pruebas `tests/test_provider_credential_setup.py`
- pruebas `tests/test_mobile_gateway.py`
- pruebas `tests/test_mobile_gateway_check.py`
- pruebas `tests/test_platform_acceptance.py`

## 131. Historial del dashboard atómico y recuperación real reabierta

1. Una regresión integral concurrente descubrió una carrera que las pruebas unitarias anteriores no cubrían: `DataFrame.to_csv(path)` truncaba `db/scan_history.csv` antes de terminar la escritura y el watchdog podía leerlo durante esa ventana como un CSV vacío.
2. El fallo era operativo, no cosmético. `dashboard_history_hygiene` reportó `EmptyDataError`, el contrato perdió temporalmente aliases derivados y el SLO retiró correctamente la aceptación sostenida del núcleo.
3. Append y compactación usan ahora un lock exclusivo por historial y escriben en un temporal del mismo directorio con `flush`, `fsync`, permisos 600 y `os.replace`. Los lectores ven el archivo anterior completo o el nuevo completo, nunca una versión truncada.
4. Dieciséis appends simultáneos quedaron serializados sin perder filas, sin temporales residuales y con CSV y lock en modo 600. La regresión integral posterior al primer cierre atómico terminó **2.669/2.669** en 153,16 s.
5. La revisión adicional cerró una pérdida potencial distinta: si un CSV existente es ilegible, append ya no lo interpreta como historial vacío ni lo reemplaza por una fila. Conserva exactamente sus bytes y devuelve `unreadable:<tipo>`; un archivo verdaderamente vacío sí se inicializa de forma segura.
6. Las 727 pruebas enfocadas de historial, mantenimiento, watchdog y aceptación pasaron después de esta protección fail-closed.
7. El primer heartbeat natural posterior al arreglo devolvió `dashboard_history_hygiene=OK`, `report_metrics_contract=OK`, `health_stability_slo=INFO` y runtime `OK`. La aceptación permanece deliberadamente pendiente en 1/10 hasta completar de nuevo diez ciclos programados limpios; no se reutiliza la racha previa al incidente.

Evidencia:

- `dashboard_history.py`
- `tests/test_dashboard_history.py`
- `alerts/roxy_realtime_check.json`
- `alerts/platform_phase_acceptance.json`

## 132. Persistencia transaccional de práctica y snapshots centrales

1. La búsqueda de la clase de fallo del historial encontró read-modify-write sin exclusión en los diarios de práctica bursátil y cripto. Un registrador y el cerrador automático podían leer la misma versión y el último en guardar eliminaba filas creadas por el otro.
2. `durable_storage.py` centraliza lock exclusivo por archivo y reemplazo atómico en el mismo directorio con `flush`, `fsync`, modo 600 y limpieza del temporal. Registrar candidatos y cerrar resultados mantienen el lock durante toda la transacción.
3. El cerrador de resultados vuelve a cargar cada diario dentro de la transacción justo antes de aplicar cierres. Una fila agregada durante la consulta de precios se conserva aunque deba esperar al siguiente ciclo para recibir precio.
4. Dieciséis registros bursátiles y dieciséis cripto concurrentes conservaron todos los candidatos. Un diario malformado ya no se interpreta como vacío ni se sobrescribe; CSV, locks y reporte de cierre quedan privados.
5. El diario de aprendizaje autónomo tenía el mismo patrón de pérdida. Ahora compacta y agrega bajo lock, preserva archivos ilegibles y pasó una prueba de dieciséis appends simultáneos sin filas perdidas.
6. El watchdog publicaba deliberadamente un informe preliminar en la ruta canónica para que el generador del brief lo consumiera. Durante esa ventana un lector real observó JSON válido pero sin `stability_summary`. El brief usa ahora `ROXY_REALTIME_HEALTH_PATH` apuntando a un snapshot de trabajo privado; la ruta pública conserva el último contrato completo hasta el reemplazo final.
7. Informes de health, brief/memoria de IA, calidad de alertas, salud de gráficas y mantenimiento usan reemplazo atómico durable. La prueba de integración mantiene intacto el snapshot canónico durante la regeneración, restaura el entorno y elimina los archivos de trabajo.
8. La regresión integral cerró **2.678/2.678** en 156,10 s. El heartbeat natural siguiente publicó 55 checks completos, los contratos críticos en OK y avanzó la nueva racha a 3/10; `pip check` y `git diff --check` terminaron limpios.

Evidencia:

- `durable_storage.py`
- `alpaca_paper_practice.py`
- `crypto_paper_practice.py`
- `paper_result_closer.py`
- `roxy_ai.py`
- `alert_quality.py`
- `chart_health.py`
- `tools/output_maintenance.py`
- `tools/roxy_realtime_check.py`
- pruebas `tests/test_alpaca_paper_practice.py`
- pruebas `tests/test_crypto_paper_practice.py`
- pruebas `tests/test_paper_result_closer.py`
- pruebas `tests/test_roxy_ai.py`
- pruebas `tests/test_roxy_realtime_check.py`

## 133. Durabilidad transversal para mercado, memoria y sesiones concurrentes

1. Se amplió la auditoría desde el incidente puntual a todos los productores operativos que la UI elige como “último archivo”. Scan, confluencia, opciones, snapshots y backtesting publican ahora CSV completos mediante rename atómico; sus reportes JSON/texto siguen la misma regla.
2. `durable_storage.py` sincroniza contenido y, cuando el sistema lo admite, el directorio padre después de `os.replace`. Un fallo de serialización conserva la versión completa anterior y no deja temporales.
3. Los historiales de calidad de alertas y notificaciones usan una transacción read-modify-write bajo lock. El mantenimiento usa el mismo lock para compactar/recortar, por lo que ya no puede borrar un append concurrente. Cooldowns de símbolos también quedan serializados.
4. Los locks internos vacíos y ocultos no cuentan como huella de datos; los `.lock` visibles o con contenido sí se contabilizan. Esto evita que el propio mecanismo de integridad simule crecimiento de almacenamiento.
5. Noticias guarda highlights bajo lock y reemplazo atómico. Dieciséis escritores simultáneos conservaron dieciséis enlaces únicos. Caché RSS, resumen legible y exportadores heredados dejaron de truncar destinos visibles.
6. Memoria de conversación, perfiles y feedback del cerebro comparten ahora transacciones por archivo. Dieciséis sesiones, perfiles y feedback concurrentes quedaron completos y privados.
7. Roxy OS eliminó la caché de archivo como fuente de verdad para mutaciones: cada `remember`/`delete` recarga dentro del lock. Dieciséis instancias distintas conservaron todas las memorias; un almacén corrupto falla cerrado y conserva sus bytes.
8. Academy protege el progreso de múltiples usuarios de Streamlit con lock y reemplazo atómico. Estado de proximidad, perfil de arranque, backups, heartbeats, recuperación launchd, probes de dashboard/cursor, desarrollo autónomo, ingestión de aprendizaje y clima también publican snapshots completos.
9. El cuarto heartbeat se observó mientras corría: el JSON canónico conservó el ciclo completo anterior hasta el reemplazo final. Los ciclos siguientes avanzaron sin regresión hasta **6/10**, con 55 checks, runtime OK y contratos críticos en verde.
10. La regresión integral posterior a esta capa cerró **2.689/2.689** en 156,47 s. `pip check` y `git diff --check` terminaron limpios.

Evidencia:

- `durable_storage.py`
- `ma_reporting.py`
- `ma_confluence.py`
- `news.py`
- `notifier.py`
- `roxy_os/memory/memory_manager.py`
- `streamlit_app.py`
- `tools/ma_scan.py`
- `tools/options_scan.py`
- `tools/ma_confluence.py`
- `tools/ma_backtest.py`
- `tools/snapshot_exporter.py`
- `tools/roxy_interactive_brain.py`
- `tools/runtime_backup.py`
- `tools/roxy_realtime_check.py`
- pruebas `tests/test_durable_storage.py`
- pruebas `tests/test_news.py`
- pruebas `tests/test_notifier.py`
- pruebas `tests/test_roxy_os.py`
- pruebas `tests/test_roxy_interactive_brain.py`
- pruebas `tests/test_academy_runtime.py`

## 134. SLO sin autorreferencia y recuperación natural restablecida

1. Al alcanzar diez ciclos internos sanos apareció una regresión de clasificación: el promedio global histórico seguía en 0% por bloqueos externos y `health_stability_slo` se marcó `FAIL`. Ese fallo observacional entraba después en el propio historial y podía retirar la recuperación que intentaba medir.
2. El historial ya excluía el SLO como dependencia del runtime, pero el último ciclo también contenía `notification_delivery=WARN`: existía una ruta local durable y sana, aunque no un canal externo. El clasificador no consumía la verificación `notification_delivery_healthy_from_history_metrics` y cortaba incorrectamente la racha del núcleo.
3. La ruta local writable, cooldown íntegro, historial dentro de presupuesto y ausencia de líneas malformadas permiten ahora que el aviso de canal externo permanezca visible globalmente sin degradar el núcleo. Un fallo real de notificaciones o cualquier otro control interno continúa cortando la recuperación de inmediato.
4. Una regresión reproduce una ventana de 100 ciclos con 74% histórico, fallos antiguos, proveedor premium bloqueado, SLO previo en `FAIL` y notificación local en el último ciclo. Los últimos diez ciclos internos sanos producen `INFO`, `RECOVERED` y no eliminan la advertencia histórica.
5. Los heartbeats 81, 82 y 83 se observaron sin forzar ejecución. La racha avanzó 8/10, 9/10 y 10/10. El artefacto final contiene 55 controles, `core_runtime_status=OK`, `core_operational=true`, `core_recovered_sustained=true` y `Core operativo / externo bloqueado`.
6. El diagnóstico sistémico reconoce que voz y sincronización permanecen privadas detrás del gateway HTTPS/Bearer. La lectura viva revisó 62 controles; la exposición física sigue correctamente en `UNVERIFIED` y no se fabricó evidencia desde localhost.
7. Aceptación, matriz responsive y los snapshots de tareas, compras, documentos, correo, Home Assistant y cliente/gateway móvil comparten ahora `durable_storage.atomic_write_text`: temporal privado, `fsync`, reemplazo atómico y sincronización del directorio.
8. La ejecución directa de `tools/platform_acceptance.py` detectó y cerró una diferencia entre importación y CLI: el script resuelve explícitamente la raíz del proyecto. La prueba de subprocess exige código 2 mientras existan bloqueos externos, JSON válido y modo 600.
9. La aceptación viva quedó `PARTIAL_EXTERNAL` para Fase 1, con seis fases parciales y una en progreso. Ya no lista recuperación pendiente; conserva únicamente Alpaca/proveedor premium y snapshots RoxyData como bloqueos de estabilización.
10. La regresión integral final, incluida la ejecución CLI real, cerró **2.694/2.694** en 155,39 s. Compilación de Python, sintaxis JavaScript, `pip check` y `git diff --check` terminaron limpios.

Evidencia:

- `durable_storage.py`
- `system_diagnostics.py`
- `tools/roxy_realtime_check.py`
- `tools/platform_acceptance.py`
- `tools/device_sync_check.py`
- `tools/document_vault_check.py`
- `tools/email_check.py`
- `tools/home_assistant_check.py`
- `tools/mobile_client_check.py`
- `tools/mobile_gateway_check.py`
- `tools/personal_task_check.py`
- `tools/shopping_list_check.py`
- `tools/responsive_route_matrix.py`
- `alerts/roxy_realtime_check.json`
- `alerts/platform_phase_acceptance.json`
- pruebas `tests/test_roxy_realtime_check.py`
- pruebas `tests/test_system_diagnostics.py`
- pruebas `tests/test_platform_acceptance.py`
