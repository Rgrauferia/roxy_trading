# Nexo: primera carga del mapa — diagnóstico y contrato del helper

Fecha: 2026-09-10. Alcance: código y pruebas aisladas; el agente principal realizó
la observación del navegador público. No se modificaron ubicación, cuentas ni permisos.

## Evidencia y límite del diagnóstico

El navegador público 184 mostró marcadores sobre un fondo claro durante más de
un minuto, sin calles ni rótulos. La captura proporcionada por el agente principal
es `/tmp/roxy-home-qa-185/01-public-nexo-stale.png`. Tras pulsar una vez **Acercar
mapa**, aparecieron teselas, rótulos y atribución (captura 03 del recorrido principal).
No se observaron errores de consola en esa comprobación.

La causa exacta no está demostrada: son hipótesis la inicialización/redimensión,
una carga de teselas detenida o una incidencia transitoria del navegador/proveedor.
No afirmar fallo de facturación, clave, servidor o clima a partir de este síntoma.
El estilo conserva calles, agua y etiquetas; el velo meteorológico no explica por
sí solo la ausencia completa del mapa base.

Sí se confirma una carencia de la aplicación: `loadFamilyGoogleMaps` comprueba
las bibliotecas, y `renderFamilyMap` considera suficiente construir `Map`. Antes
del helper no había un listener `tilesloaded` ni límite de espera para el mapa
base. Los tests existentes cubrían bibliotecas, navegación y permisos, no esta
primera carga visual. Google define `tilesloaded` como el fin de carga de las
teselas visibles; `idle` sólo indica reposo tras mover o ampliar el mapa.
[Referencia oficial de Map](https://developers.google.com/maps/documentation/javascript/reference/map#Map.tilesloaded).

La CSP actual no cubre todos los hosts alternativos de satélite `*.google.com`
ni usa nonce para estilos inyectados. Esto es un riesgo de compatibilidad separado,
no la causa verificada del incidente: la recuperación mediante zoom y ausencia de
violaciones observadas no justifican ampliar permisos de forma especulativa.
[CSP oficial](https://developers.google.com/maps/documentation/javascript/content-security-policy)
y [dominios oficiales](https://developers.google.com/maps/domains).

## Helper y responsabilidad del integrador

Archivo: `assets/roxy_home_map_readiness.js`. No depende de Google ni hace
peticiones, cambios de vista, reintentos, lecturas de ubicación o almacenamiento.

```js
const controller = window.RoxyMapReadiness.create({
  // Guarda identidad de la creación; no usar aquí la visibilidad del panel.
  isCurrent: () => identityStillMatches(),
  onState: state => renderNotice(state),
  timeoutMs: 12000,
});
const map = new google.maps.Map(element, options);
controller.attach(map); // Inmediatamente después de construir, antes de otros awaits.
controller.setActive(!document.hidden && activePanel === 'family');
```

- Estado: `{phase, active, canRetry}`; fases `idle`, `loading`, `ready`, `delayed`.
- `ready` sólo tras el primer `tilesloaded`, no por constructor, markers o `idle`.
- A los 12 segundos activos sin ese evento, `delayed`, no `failed` ni `offline`.
  Texto sugerido: «El mapa tarda en cargar. Puedes reintentar o probar el zoom».
- `attach` repetido con la misma instancia no duplica aviso ni prolonga el timer.
- `setActive(false)` cancela la espera. Una carga completada oculta se recuerda
  sin repintar. Al regresar, un mapa ya listo no vuelve a esperar un evento nuevo.
- La demora no causa reintentos automáticos. Después de `delayed`, el evento
  tardío sigue pudiendo cambiar a `ready` y retirar el aviso.
- `dispose()` es definitivo e idempotente; usar al cerrar sesión, cambiar identidad
  o destruir/reemplazar mapa. Crear otro controller para una nueva sesión.
- Si el usuario elige explícitamente reintentar, el integrador decide una sola
  reconstrucción/reinicialización, conservando centro, zoom y permisos en memoria.
  No solicitar GPS ni guardar coordenadas por esta acción. No reutilizar un
  controller ya destruido. No tapar la atribución o controles de Google.
- El helper comprueba sólo la primera carga, no garantiza que todas las teselas
  posteriores, tráfico, rutas o radar estén disponibles.

## Pruebas

`node --test tests/test_roxy_home_map_readiness_185.cjs`: **14 aprobadas**.
Biblioteca versus teselas; llegada temprana/tardía; demora sin bucle; reuso de
instancia; callbacks antiguos; pausa/retorno; pérdida de identidad; limpieza;
timeout acotado. Una prueba detectó que un callback vencido podía limpiar la
referencia del timer nuevo; se corrigió comprobando generación e ID antes de mutar.
No prueba real de red ni remedio demostrado de la causa original.
