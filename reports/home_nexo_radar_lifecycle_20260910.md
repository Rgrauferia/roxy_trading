# Nexo: lifecycle de radar y clima — 10 septiembre 2026

Implementación local para el siguiente bloque después de 182. No es una prueba
en teléfono ni un despliegue. No se cambian gráficos, proveedores, datos de
personas, permisos, claves, facturación ni versiones. Root coordina la publicación.

## Corregido

- El radar deja de crear fotogramas/tile requests al ocultar documento/aplicación,
  abandonar Nexo o cerrar el globo. Cancela petición de metadatos, timeout,
  transición y resize pendientes; detiene y elimina la instancia MapLibre para
  liberar renderer, listeners internos y recursos GPU/red de ese visor.
- Regresar del segundo plano reconstruye una sola instancia únicamente si Nexo
  sigue abierto y no cambió la identidad ni el contexto de consentimiento. Conserva
  la vista y el fotograma disponible, además de la pausa manual. No abre el globo
  automáticamente después de salir del módulo, cerrar sesión o revocar permisos.
- El scope compara hogar, modo/id de miembro, autorización meteorológica y
  conjunto de participantes/permisos Nexo. Los cambios normales de coordenadas no
  reconstruyen el visor. La revocación elimina vista y texto anteriores.
- Aperturas, respuestas, errores, eventos MapLibre y callbacks cancelados de A no
  alteran una apertura B. La comprobación ocurre también después de cada await.
- RainViewer mantiene validación de host/rutas y edad. Se revalida el caché antes
  de reusar; una observación vencida se actualiza incluso si el usuario pausó la
  animación. Sin respuesta no se presentan fotogramas simulados.
- Metadatos y lectura del body tienen salida finita en 10 segundos, incluso ante
  un fetch/body que no coopera con AbortSignal. Un body tardío no escribe caché.
- Actualización del modelo meteorológico: identidad, ubicación autorizada y
  ticket por solicitud. Respuestas de otro miembro del mismo hogar no sobrescriben
  el estado ni liberan la solicitud vigente. Cambio/revocación observados abortan
  solicitudes; revocar y volver a conceder no revive el resultado anterior.
  Timeout de 10 segundos y limpieza; respuestas fuera de pantalla no repintan.

## Semántica de ubicación

El centro inicial usa la ubicación del viewer **sólo si `sharing_enabled`** está
vigente, o la ubicación meteorológica aproximada si `location_enabled` está
vigente. Se rechazan null/vacío/booleanos y coordenadas fuera de rango, pero se
conserva cero real. No modifica ni concede esos permisos. No se reutiliza el
viewport Google, que podría proceder de un miembro anterior. Sin ubicación
autorizada se conserva el centro geográfico de fallback de la aplicación; el
radar global sigue siendo explorable sin publicar ubicación propia. Ningún dato
de identidad/coordenadas se añade a la consulta pública de metadatos RainViewer.
Las solicitudes de tiles representan, como antes, la zona explorada en el mapa.

## Archivos / pruebas

- `assets/roxy_list.js`: sólo bloque weather/radar/globo y hook al render climático.
- `tests/test_roxy_home_radar_lifecycle_182.cjs`: 28 casos nuevos, funciones reales.
- `tests/test_roxy_home_weather_refresh_182.cjs`: 15 casos nuevos, funciones reales.
- `tests/test_roxy_home_globe_integration.cjs`: fixture adaptado a lifecycle real;
  17 contratos conservados, centro esperado ahora autorizado en vez de viewport viejo.
- `tests/test_roxy_home_weather_scene.py`: fixture incorpora consentimiento y
  guardas de nueva activación; conserva cero/frescura/ausencia/errores originales.

79 pruebas Node focalizadas aprobadas (43 nuevas +17 integración +19 loader).
183 pruebas Python de clima, renderer, demo readiness y map visibility aprobadas;
33 de clima/renderer/map visibility repetidas después del último ajuste de refresh,
todas aprobadas. `node --check` y `git diff --check` correctos.
Sin APIs reales, GPS, micrófono, browser compartido ni perfiles públicos. Fixtures
usan dos identidades ficticias y relojes/mapas/HTTP controlados, no datos reales.

## Límites / siguiente revisión

No se ha auditado aquí el lifecycle de Google Maps/Traffic, watchers de GPS,
historial o rutas; sus componentes no se modifican. Tampoco se elimina el pequeño
tick climático existente de 30 s que comprueba frescura (no solicita clima fuera
de Nexo/oculto). El globo elimina su propio intervalo de 850 ms y renderer.
Cambios de contexto se observan al render, cambio de visibilidad, hidden del app,
callbacks o ticks; la actualización del modelo se descarta si termina fuera de
contexto. Hace falta QA visual de volver/salir, background/foreground y WebGL en
Safari/iPhone real para medir consumo y continuidad. Este bloque no mejora el
realismo visual de lluvia/tormenta ni certifica precisión a nivel de calle.
