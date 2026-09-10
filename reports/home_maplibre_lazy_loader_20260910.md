# MapLibre local, bajo demanda — 10 de septiembre de 2026

## Entrega aislada

- `assets/roxy_maplibre_loader.js` expone `window.RoxyMapLibre.load()`.
- `tests/test_roxy_home_maplibre_loader.cjs` ejecuta el archivo real en Node con dobles de DOM y reloj, sin red ni datos personales.
- No se modifican HTML, JS principal, service worker, Docker ni el contenido de vendor en este bloque. El integrador debe conectar la API; el archivo solo no elimina la descarga incondicional actual.

El helper no crea etiquetas, temporizadores, mapas ni peticiones al evaluarse. La primera llamada descarga exclusivamente los dos recursos locales existentes:

```text
/assets/vendor/maplibre-gl.css?v=1
/assets/vendor/maplibre-gl.js?v=1
```

Llamadas concurrentes comparten una sola promesa. Se esperan CSS y JS; se verifican los constructores `Map`, `NavigationControl` y `AttributionControl`. Si la librería ya existe y es válida, no se añade otro script. Las etiquetas locales existentes se reutilizan, incluidas las que aún están cargando. No se modifica ni elimina vendor insertado por la página.

Un plazo global de 15 segundos acota cada intento. Los errores tienen códigos estables `MAPLIBRE_LOAD_TIMEOUT`, `MAPLIBRE_STYLE_ERROR`, `MAPLIBRE_SCRIPT_ERROR`, `MAPLIBRE_INVALID_GLOBAL`, `MAPLIBRE_DOM_UNAVAILABLE` y `MAPLIBRE_DOM_ERROR`. Después de error se permite otro intento; una parte cargada correctamente se conserva. Etiquetas propias sin terminar se retiran, las ajenas se conservan y dejan de reutilizarse tras su fallo. Los listeners y el temporizador del intento finalizado se limpian. Callbacks tardíos no pueden finalizar una promesa posterior.

Retirar un script no garantiza cancelar bytes que el navegador ya esté recibiendo o una ejecución ya iniciada. El integrador debe mantener el ticket de identidad de la apertura del globo y comprobar que Nexo siga activo después del `await`, antes de crear WebGL o pedir radar.

## Integración mínima pendiente de root

1. Cargar el helper ligero antes del JS principal y distribuirlo con Docker/SW.
2. Quitar los `<link>`/`<script>` incondicionales de MapLibre del HTML.
3. En `activateFamilyWeatherGlobe`, esperar `window.RoxyMapLibre.load()` antes de `ensureFamilyWeatherGlobe`. Reservar el identificador de apertura antes de esperar; comprobar identidad, globo activo y panel Nexo al volver. No hace falta descargar MapLibre para el mapa Google normal.
4. Distinguir errores de carga del visor de errores de RainViewer. Un visor fallido no es «globo interactivo activo» y no se debe atribuir a RainViewer.
5. Al salir de Nexo, invalidar aperturas pendientes y detener la reproducción del radar. El helper no decide visibilidad ni entra al mapa por su cuenta.
6. Ajustar tests existentes que exigen tags vendor en el HTML o extraen la función `activateFamilyWeatherGlobe` sin el nuevo helper. Mantener la distribución de vendor local.

El SW actual excluye vendor del precache y cachea estáticos del mismo origen al solicitarlos. Se conserva así el uso de la librería en visitas posteriores sin red. En la primera visita completamente offline, el loader fallará de forma finita: no promete un mapa global offline ni radar actualizado. Las teselas externas y su frescura siguen siendo responsabilidad del módulo de mapas.

Los archivos vendor suman 1.006.825 bytes sin comprimir (937.395 JS + 69.430 CSS). Retirar su carga incondicional evita ese trabajo al abrir otros módulos, pero no se presenta esta cifra como transferencia comprimida ni como mejora temporal medida en un teléfono.

## Hallazgo adicional comunicado al integrador

`render()` llama a `renderFamily()` y este llama a `renderFamilyMap()` incluso fuera de Nexo. La función no verifica el panel antes de `await loadFamilyGoogleMaps()`. Por tanto, para un miembro con proveedor configurado, el mapa Google también puede cargarse oculto desde Hoy/Recetas. Comprobar el panel antes y después del `await` reduce ese trabajo; al entrar a Nexo se debe dibujar primero la información cacheada incluso si falla su actualización. No se implementa ese cambio en este bloque.

## Pruebas

```sh
node --test tests/test_roxy_home_maplibre_loader.cjs
```

19 casos: ninguna mutación inicial; deduplicación; ambos órdenes CSS/JS; vendor ya cargado o pendiente; global incompleto; error de script/CSS con reintento y éxito parcial conservado; timeout completo y parcial; tags ajenos; callbacks A/B tardíos; CSS retirado o deshabilitado; revalidación del global; rechazo de URLs remotas como coincidencia; ausencia de DOM.

Estas pruebas verifican el cargador, no sustituyen un smoke test en navegador del globo, controles, zoom de Google a MapLibre, salida durante carga, radar degradado y navegación entre módulos tras el cableado.

## Integración verificada posteriormente, todavía local

El integrador añadió el helper al HTML, Docker y shell del SW, retiró los tags vendor incondicionales y conectó la carga con un identificador de apertura. También protegió Google Maps antes/después del await para evitar trabajo oculto fuera de Nexo y cerró el globo al cambiar de módulo.

`tests/test_roxy_home_globe_integration.cjs` ejecuta las funciones reales del JS principal y verifica 17 casos: éxito, visor sin red o sin WebGL, helper ausente, RainViewer sin disponibilidad, reintento, salida durante la descarga de librería o radar, cambio real mediante `selectPanel`, aperturas A/B fuera de orden, ausencia de Google Maps fuera de Nexo, distribución de archivos y orden de navegación. Las dos pruebas de reintento detectaron un aviso de error anterior conservado junto al radar recuperado; el integrador corrigió el reinicio del aviso y del tiempo.

La navegación conserva Recetas y Ejercicio consecutivos en el HTML y no mantiene reglas CSS `order` que alteren esa secuencia. Es una regresión estructural complementaria, no una medición visual de todos los tamaños de pantalla.

### Mejora de rendimiento pendiente — radar en segundo plano

`syncFamilyWeatherGlobePlayback()` programa un intervalo de 850 ms cuando hay varias observaciones y reproducción activa, pero no comprueba `document.hidden`. Salir de Nexo detiene el intervalo; pasar el navegador/app al segundo plano no lo detiene explícitamente. El navegador puede ralentizarlo, lo que no equivale a una pausa controlada por Roxy.

Próximo bloque propuesto: pausar el intervalo al ocultar el documento y reanudar sólo si Nexo/globo continúan activos y la persona no había pausado la reproducción. La reanudación debe comprobar frescura de radar y no multiplicar intervalos. No se implementó este cambio en el bloque actual ni se registra como resuelto.
