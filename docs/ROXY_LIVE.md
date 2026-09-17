# Roxy Live: gráfica, programación y noticias

## Estado de esta entrega

Es código ejecutable en una **vista adicional** del proyecto, no una imagen ni
un reemplazo de la pantalla de Opciones. Archivos: `roxy_live.py`,
`pages/1_Roxy_Live.py` y `tests/test_roxy_live.py`.

No se modificaron `streamlit_app.py`, el despliegue, la voz, el login ni la
lógica que envía órdenes. La integración con las pestañas superiores, avatar,
voz y chat de la pantalla existente queda pendiente. No se ha comprobado la
rama que el servicio publicado usa actualmente.

## Probar sin detener la transmisión actual

Desde la carpeta del proyecto, con sus dependencias ya instaladas:

```bash
git fetch origin
git switch --track origin/chatgpt/roxy-live-programming-20260917
python -m streamlit run pages/1_Roxy_Live.py --server.port 8505
```

Si la rama ya existe localmente, usar `git switch` sin `--track`. No descartar
cambios locales para cambiar de rama. Abrir `http://localhost:8505` en esa
computadora. Un iPhone no accede al servidor de la Mac mediante su propio
`localhost`.

La vista también puede descubrirse como página **Roxy Live** cuando la app
principal usa la navegación de Streamlit basada en `pages/`. Si usa
`st.navigation`, es necesario registrarla explícitamente; si oculta la barra
lateral, habrá que añadir un enlace visible. Ese recorrido no está probado en
el despliegue. El comando anterior abre la vista directamente.

Un PR no publica la web: primero hay que validar la integración, aprobar los
cambios y desplegar la rama/versión correspondiente.

## Configuración existente del servidor

```dotenv
ALPACA_API_KEY=
ALPACA_API_SECRET=
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_DATA_FEED=iex
```

También admite `ALPACA_SECRET_KEY`, `APCA_API_KEY_ID` y `APCA_API_SECRET_KEY`.
Nunca escribir claves reales en Git, URLs, capturas o el navegador. La carga
opcional de `.env` no sobrescribe las variables de entorno existentes. No lee
secretos que solo estén guardados en otro servicio o en otra aplicación.

Solo consulta barras, titulares y calendario mediante GET a servidores
oficiales de Alpaca. No envía órdenes, no consulta posiciones/saldos y no hace
llamadas a OpenAI o Codex. Se necesitan las credenciales y permisos de datos
correspondientes; no se ha probado la cuenta real. IEX es cobertura parcial;
SIP requiere permisos. SPX no se sustituye por SPY ni por los números de la
imagen de referencia.

Sin acceso a datos, la vista muestra un error/estado vacío: no inventa velas,
titulares ni un estado de mercado abierto. Los derechos de mostrar datos y
noticias públicamente deben revisarse con el proveedor antes de emitirlos.

## Qué hace

La gráfica 15m muestra las últimas 200 velas disponibles de una ventana de
diez días, incluidos datos de horario extendido. Es una muestra acotada, no
un historial completo. Valida OHLCV, elimina duplicados y muestra hora/edad
actual de la última vela.

Soporte y resistencia proceden de las 20 velas cerradas anteriores al cierre
evaluado. Las flechas alcista/bajista son escenarios condicionales a distancias
de 1 y 2 veces el rango verdadero medio de 14 barras. No son predicciones,
probabilidades, una estrategia validada ni confirmación multitemporal.

La programación usa `America/New_York` y el calendario del proveedor:
09:15 preparación, 09:30 apertura, 10:30 análisis, 12:00 educación/chat,
13:30 seguimiento, 15:00 Power Hour y 15:55 resumen. El resumen tiene prioridad
en el solapamiento y termina 16:05 en una sesión normal. En un cierre
anticipado comienza cinco minutos antes del cierre; los bloques posteriores
se recortan o se omiten. Un calendario desconocido no se considera abierto.
Es una agenda visual: no cambia escenas de OBS ni reproduce narración.

Noticias: titulares de las últimas 24 horas con fuente, enlace HTTP(S) y
fecha; sin duplicados, texto escapado, sin resumen por IA ni verificación
independiente del contenido. No afirma que una noticia cause un movimiento.

Caché: barras 60 segundos, noticias 300, calendario 900. La vista se actualiza
cada 15 segundos mientras la sesión de Streamlit está activa; versiones sin
`st.fragment` ofrecen actualización manual. No es un proceso autónomo 24/7.

## Seguridad y autenticación

Esta página no hereda una barrera de login situada exclusivamente dentro de
`streamlit_app.py`. Solo expone datos públicos de mercado, no funciones ni
datos privados de cuentas. Antes de incorporarla a la web, decidir si será
pública o colocarla detrás de la autenticación del despliegue. No mover el
login ni ejecutar el terminal de trading para renderizar esta página.

## Pruebas ejecutadas

```bash
python -m pytest tests/test_roxy_live.py -q
python -m py_compile roxy_live.py pages/1_Roxy_Live.py tests/test_roxy_live.py
```

Resultado local: **26 pruebas aprobadas**. Incluyen límites horarios, cambios
de horario de verano, cierre anticipado, calendario desconocido, velas
incorrectas/incompletas, niveles sin anticipación de datos, enlaces/fechas,
GET-only, no filtración de secretos, construcción real de Plotly y
renderizado con un sustituto de Streamlit.

Los datos sintéticos existen únicamente en las pruebas. No se ejecutó el
servidor Streamlit real, ni pruebas de navegador, OBS, la cuenta Alpaca real o
la suite completa del repositorio. Compilar y pasar estas pruebas no prueba
que la web publicada ya funcione con la nueva vista.

## Referencias técnicas

- https://docs.streamlit.io/develop/concepts/multipage-apps/pages-directory
- https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment
- https://docs.alpaca.markets/us/reference/stockbars
