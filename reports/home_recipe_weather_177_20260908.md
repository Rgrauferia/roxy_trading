# Roxy Home 177 — recetas originales, conservación y clima

Estado: publicado y comprobado, commit de implementación `ae7164fe6`, rama
`codex/roxy-home-nfc`. Home únicamente; `prototypes/` y los perfiles privados de
producción no se han editado.

## Cambios verificados

- Originales de Wikibooks: seis recetas, seis cocinas, 31 líneas de ingredientes,
  36 pasos y raciones originales en inglés. Tres fotos expresamente enlazadas
  por sus revisiones con licencia individual comprobada; tres sin foto original.
  Lector, filtros y TXT con atribución. No se inventan medidas ni traducciones.
- TheMealDB: búsqueda y filtro por país con consulta acotada de detalles,
  acciones explícitas y clave sólo de Home en servidor. Apagado: Roberto no
  tiene cuenta/clave, la licencia comercial sigue pendiente y no se pagó.
  Una prueba documentada de desarrollo confirmó el formato real de respuesta;
  no equivale a la integración comercial activa.
- Peticiones de recetas por texto/voz: no generar ni certificar recetas con IA
  ni sustituir búsquedas por plantillas arbitrarias. Se conservan las existentes.
- Corregido el truncado a 160 caracteres al guardar pasos: ahora se preservan
  párrafos y repeticiones, y se rechaza un exceso explícitamente. Ingredientes
  incompletos ya no reciben cantidad, unidad o raciones inventadas por defecto.
- La búsqueda local ahora resuelve la misma edición que el catálogo visible:
  por ejemplo, piña colada sin alcohol conserva sus tres pasos específicos.
- Preparaciones de mascotas: 57 fichas sin original verificado, ocho para Luna.
  Fotos y fichas conservadas, avisos de revisión y bloqueo de preparación,
  escalado y envío a Compra. Las guías veterinarias generales no son pruebas
  de autoría ni validación clínica de una receta concreta.
- Nexo: lluvia con profundidad, tamaños y velocidades diferentes, gotas finas
  y viento; nieve con movimiento distinto. Sin destellos de rayos inventados.
  El mapa sigue recibiendo gestos. Pausa con pestaña oculta, movimiento reducido,
  área fuera de pantalla o datos vencidos. El efecto ilustra Open-Meteo y no
  se etiqueta como observación exacta; el radar RainViewer sigue separado.

## Verificación local

975 pruebas Python Home/compras/proveedor aprobadas (47,97 s), incluida la revisión
de acceso a videos. Dos baterías Node del frontend aprobadas, sintaxis JS/SW
válida. Las pruebas usan directorios temporales, nunca datos de Roberto.

La revisión independiente detectó acceso a videos antiguos que eludía el aviso
de fuentes. Ahora GET/POST, reproducción, sincronización y aprobación vuelven a
comprobar la receta vigente del hogar; devuelven 422 antes de generar o mostrar
preparaciones pendientes. Los administradores pueden rechazarlas sin borrarlas.
22 pruebas nuevas; los clips usan `private, no-store` para no eludir el control
mediante caché compartida.

Navegador aislado 8767 a 393×852: abrir originales, cargar la foto de tortilla
(1024×768 de origen), créditos/licencia, abrir lector y avanzar al paso 2 de 8.
Luna QA conserva ocho fichas; abrir pavo conserva su foto, identifica el borrador
y no ofrece cocinarlo ni enviarlo a Compra. Bella QA y Betta QA permanecen.

Auditoría visual de clima: comparación antes/después en el mismo fixture y
viewport. Menos velo sobre el mapa, partículas diferenciadas; botón Acercar
recibe el clic, datos vencidos retiran la animación. Es una simulación visual
con datos de prueba; no una tormenta comprobada en un teléfono físico.

Evidencias locales fuera del repositorio:

- `/tmp/roxy-home-177-review/weather-before.png`
- `/tmp/roxy-home-177-review/weather-after.png`
- `/tmp/roxy-home-177-review/original-photo-mobile.png`
- `/tmp/roxy-home-177-review/original-reader-mobile.png`
- `/tmp/roxy-home-177-review/luna-source-review-mobile.png`

## Pendientes reales

Cuenta y licencia comercial TheMealDB; catálogo original amplio y traducción
fiel revisada; fotos originales que faltan; originales aptos para cada especie
y revisión veterinaria donde corresponda. No se certifica el catálogo actual
entero ni se declara la demo al 100%. Onboarding, voz/facturación y apertura del
registro mantienen sus bloqueos previos: este cambio no los habilita.

## Comprobación pública posterior al despliegue

HTML/APP177, JS178, CSS127, SW175, proveedorJS2, originalesJS1 y climaJS1.
Los siete archivos respondieron HTTP200 y coinciden byte a byte con el commit;
`/health` devuelve OK. Meta 177 también comprobada en el DOM del navegador.

El endpoint autenticado público sirve los seis originales. La foto de tortilla
ha cargado y el lector avanzó al paso 2/8 conservando su texto. Bella y Luna
siguen visibles. Luna aparece como Ferret, conserva ocho fichas pendientes;
la foto `ferret-cooked-turkey-bites.jpg` cargó al abrir pavo, sin acciones para
cocinar ni añadir a Compra una preparación sin verificar. No es recuperación
de una foto de perfil anterior ni certificación de esas ocho recetas.

Google Maps, Robert y Roxy siguen visibles. El dato público fue parcialmente
nublado, Open-Meteo con hora de validez; no se dibujó lluvia para ese dato.
No se forzó un estado de tormenta en producción, ni GPS ni micrófono. Captura:
`/tmp/roxy-home-177-review/nexo-public-177.png`.
Sigue pendiente la velocidad histórica junto a una ubicación antigua: evitar
que se interprete como movimiento actual antes del lanzamiento.
