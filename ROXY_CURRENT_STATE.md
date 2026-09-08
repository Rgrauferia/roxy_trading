# Roxy Home — estado operativo

Actualizado: 2026-09-08. Este documento pertenece exclusivamente a la rama Home.
No mezclar cambios, memoria, secretos ni despliegues de Trading/Crypto.

## 176 — publicado y comprobado en Render

Commit `65d829d42`, publicado desde `codex/roxy-home-nfc`. HTML/APP176, JS177,
CSS126, SW174 y proveedorJS1. 805 pruebas Home/compras/proveedor aprobadas;
sintaxis JS/SW/diff correctas. UI móvil QA separada: Luna ocho preparaciones,
huevos en Desayunos con pasos propios, proveedor pendiente sin acciones falsas.
No se editaron mascotas, fotos, historial ni Compra públicos. Prototipo preservado.
HTML/JS/CSS/SW/proveedorJS públicos HTTP200 y byte a byte idénticos; health OK.
Navegador público: Bella/Luna conservadas, Luna Ferret con ocho recetas y ocho
fotos distintas cargadas; huevos guardados en Desayunos con cinco pasos propios,
proveedor comercial pendiente sin búsqueda habilitada. Google Maps y Robert/Roxy
visibles; clima con fuente/hora y modelo separado del radar. No se pidió GPS ni voz.
26 pruebas focalizadas adicionales aprobadas tras el último ajuste de carga JS.
QA 8767 y fixture 8788 detenidos, puertos sin listener. Vista pública de Luna
conservada y viewport restaurado. Datos de prueba sólo en temporal; sin borrar
datos públicos ni detener el prototipo cinematográfico 8796.

Eliminado reescritor genérico de recetas cortas; reparaciones por clave concreta,
cinco originales recuperadas tras revisión: 59 listas / 458 borradores humanos.
Importaciones cortas conservadas; petición desconocida no se sustituye por pollo.
«Ninguna diagnosticada» ya no bloquea Luna ni elimina la pestaña. Restricciones
reales mantienen gates; especialistas sin recetas inventadas. Clima más fino,
viento/intensidad/día/noche, validez UTC y apagado de efectos con datos vencidos;
modelo Open-Meteo separado de radar RainViewer, no tormenta fotorrealista.

Roberto autorizó preparar/revisar TheMealDB, NO pagar. Adaptador y búsqueda UI
preparados pero apagados: faltan licencia comercial, clave exclusiva Home y prueba
real. $10 anunciado no confirma cobertura comercial; FAQ/terceros requieren
revisión. Texto/medidas originales inglesas sin inventar porciones, sin guardado
ni Compra automática. Demo no consulta proveedor externo. Fotos humanas pendientes
y 458 borradores sin completar; no declarar demo/lista universal al 100%.
Detalle: `reports/home_recipe_weather_fixes_176_20260908.md`.

## Onboarding cinematográfico — prototipo local, 2026-09-08

Roberto aprobó una película interactiva que se pausa en decisiones y cambia el
inicio según las elecciones. Primer prototipo en `prototypes/roxy-cinema`, preview
local `http://127.0.0.1:8796/`; no desplegado ni conectado al registro real.
Cuatro clips generados, pausas, ramas mascotas/plantas, idioma ES/EN, cuatro temas,
inicio filtrado, ajustes y persistencia exclusivamente local. Roberto aprobó seguir
desde esta vista. Añadidas tres apariencias (Clásica, Casual y Acuarela), selección
antes de Recetas y edición posterior; las dos nuevas son retratos explícitos sin
animación facial. No reproducen el video de otra apariencia. Renueva y Nexo ahora
explican beneficios/permisos con escenas ilustrativas y permiten añadir/omitir;
son ocho capítulos de decisión, no ocho videos. Tres imágenes nuevas mediante
ImageGen; sala Renueva reutilizada del activo Home. Fotos/voz no son datos reales.
Sin modificar Bella, Luna, cuentas, permisos, voz pública ni la versión 175.
Voz de dispositivo opcional y provisional; avatar propio, narración final,
animación de las variantes/Renueva/Nexo e integración al registro pendientes.
La ruta Home que devuelve READY no prueba disponibilidad de voz; último fallo
real registrado `payment_issue`, no repetido hoy. Revisar aislamiento de agente
Home antes de conectar proveedor, sin copiar claves ni agente de otro producto.
20 tests del flujo (2.592 combinaciones unitarias), build y 28 archivos runtime
verificados. Navegador iPhone/Pixel: galería, ES/EN, capítulos, atrás, guardar,
recargar y ajustes probados; corregido scroll heredado entre capítulos y encuadre.
Detalle/evidencias: README, `design-qa.md` y `media-manifest-20260908.md` del prototipo.
Videos del bloque anterior: 30 créditos Higgsfield consumidos; saldo histórico
consultado 9.5. No nuevos videos/audio, compra ni cambio de facturación este bloque.
El script `tools/roxy_context_handoff.py` no existe en este worktree Home; intento
de check falla por archivo ausente. No copiar herramientas de Trading para suplirlo.
No confundir este bloque visual con demo lista/publicada; sin commit/push/despliegue.

## Ubicación y despliegue

Bloque 166 comprobado en público (HTML/JS/health y sesión de Roberto):
capacidades de mascotas, acuario estructurado, fix HTTP 500 por campos vacíos,
Ferret visible sin renombrar datos, recetas humanas/borradores separados,
conservación de recetas antiguas, Nexo precisión/tráfico/lluvia/radar.
502 pruebas Home/compras aprobadas. Ver `reports/home_demo_readiness_20260906.md`.
Roberto eligió **registro abierto a cualquiera**, hogar privado por participante
y demo de 5 días. Bloque 167 implementa registro **apagado por defecto**,
hogares privados, vencimiento a solo lectura, cinco solicitudes de Roxy al día
por hogar, cuotas de admisión y verificación Turnstile en servidor. No está abierto.
Falta configurar Turnstile y probar el alta real, recuperación/soporte y revisar
el alcance de funciones. No habilitar por el simple hecho de pasar los tests.
169 comprobado en público: arranque de Google Maps corregido, mapa y tráfico
visibles. Registro devuelve `enabled:false`. 168 separa controles de zoom y
ubicación, evita tapar la atribución y corrige aviso de permiso denegado.
Una prueba de zoom alcanzó el botón superpuesto de ubicación; el navegador denegó
permiso y Robert siguió privado. No se guardó preferencia ni se borró historial.
No aumentar gasto ni cambiar facturación. Voz continúa pendiente por `payment_issue`.

- Worktree: `/Users/robertograu/.codex/worktrees/roxy-home-renueva`.
- Rama local: `codex/roxy-home-renueva`; destino de despliegue: `origin/codex/roxy-home-nfc`.
- URL: https://roxy-home.onrender.com/lista#mascotas.
- Servicio Render: `roxy-home`, `srv-da0l3vs9v7es739kcmd0`, montaje persistente `/var/data`.
- Versión pública comprobada: 176, commit de implementación `65d829d42`.
  HTML/APP 176, JS 177, CSS 126, SW 174, proveedorJS 1; los cinco archivos
  públicos coinciden con el commit. Sin nuevas fotos generadas en 176.
  805 pruebas Home/compras/proveedor aprobadas, más 26 focalizadas tras el
  último ajuste. Registro apagado, demo de cinco días aún no abierta.
  Pruebas de Nexo/texto conservadas de 169 (`fbefb85f3`), no repetidas en 171:
  zoom separado, transición al globo, 13 fotogramas de radar real animados,
  pausa/reanudación y regreso al mapa comprobados en navegador público.
  RainViewer acepta sus rutas opacas manteniendo validación de host y frescura.
  Bella y Luna aparecen con miniaturas cargadas; ocho fotos de recetas de Luna
  comprobadas en 176. Robert/Roxy siguen en Nexo. Respuesta de Roxy por texto
  conservada como evidencia de 175, no repetida en 176. Voz no verificada.
  Pruebas locales con 17 perfiles sintéticos y hogar demo separado; ninguno se
  añadió a producción. Servidor QA 8767 detenido al cerrar el bloque 175;
  pestaña QA cerrada y viewport restaurado. Pestaña pública conservada.

## Fotos de recetas y productos — 171 público comprobado

170 público comprobado: corregida cancelación prematura de fotos de recetas al construir
la lista; dominios oficiales de fotos de productos habilitados solo en img-src,
fallback honesto, enlace Kaytee y nombre de variante MidWest corregidos. Título e
importación móvil corregidos con capturas. Retirada instrucción de lavar corazones
de pollo crudos; no se alteran recetas guardadas. Detalle y límites:
`reports/home_pet_photo_followup_20260906.md`. Commit `6186b136d`, cinco archivos
públicos coincidentes y health correcto. Luna: 8 fotos de recetas y 8 de productos
cargadas en público. Bella y Luna conservadas. Algunas fotos de Bella todavía
no existen; cobertura consultada 557/683, 126 pendientes y cola 20.
171 mejora estados de carga/generación/ausencia sin iconos rotos ni fotos genéricas.
Verificado en HTTP y navegador, incluida URL normal sin parámetros: las ocho fotos
de Luna cargadas y visibles; Bella informa preparación de fotos aún ausentes.
Capturas 25/26/27 en `/tmp/roxy-pets-followup-Cbgxlb`; captura 24 es de 170 pese al
nombre, no usarla como prueba de 171. 522 pruebas Home/compras aprobadas; JS/SW y
diff válidos. Servidor QA 8767 detenido, pestaña QA cerrada y viewport restaurado.
No se modificaron perfiles, historial, carro, permisos de ubicación ni facturación.
Próximo bloque: ingredientes completos y alergias de productos, variedad real sin
duplicados por raza y fotos pendientes. No declarar demo listo ni habilitar registro.

## 172 público comprobado — seguridad y fotos de mascotas

Implementado y comprobado en público, commit `1216a182d`: ingredientes completos y Compra
coherente, cribado bilingüe de alergias, cinco fórmulas oficiales revisadas,
productos con restricciones pendientes y bloqueo en servidor, ID de producto
estable y receta vinculada a la mascota actual. Restricciones se revalidan al
cocinar/escalar/enviar a Compra. Importaciones conservadas; copias del catálogo
reciben correcciones sin perder notas, favorita ni foto personal. Catálogo sin
duplicados de preparación por raza: perro 13 / Bernese joven 15, todas con imagen
individual revisada; cinco imágenes nuevas. Luna conserva ocho preparaciones.
HTML/APP 172, JS 173, CSS 124, SW 170. Registro sigue apagado; voz/facturación
pendientes. Ver `reports/home_pet_safety_172_20260906.md`. 565 pruebas Home/compras
aprobadas; JS/SW, JSON y diff válidos. HTML/JS/CSS/SW y cinco fotos nuevas idénticos
al commit en público; health correcto. Bella 15 recetas/15 fotos cargadas y Luna
conservada como Ferret con ocho recetas; miniaturas de ambos perfiles cargadas.
QA únicamente local: 17 perfiles sintéticos, pavo/calabaza guardada con foto,
ingredientes correctos en Compra; Ferret con restricción, fórmula visible y sin
botón de añadir; equipo permitido. No se modificaron mascotas/carrito públicos.

## 173 público comprobado — fotos de gatos y contador de Compra

Ocho imágenes individuales generadas y revisadas para las preparaciones exactas:
gatos pasan a 12 recetas distintas con 12 fotos; filtros de perfil/restricciones
conservados. Compra cuenta líneas de producto, no suma gramos/litros/unidades;
etiqueta singular/plural. HTML/APP 173, JS 174, CSS 124, SW 171. 569 pruebas
Home/compras aprobadas (51.01 s), JS/SW/diff válidos. QA móvil aislado sin
desbordamiento y contador 3 correcto. Público: HTML/JS/SW y ocho imágenes nuevas
idénticos al commit `8bafa33a5`; recarga normal meta 173, Bella y Luna visibles y
miniaturas cargadas. No se modificaron mascotas ni compras de producción.
Ver `reports/home_pet_photos_173_20260906.md`; no declarar demo lista.

## 174 público comprobado — aves/pequeños mamíferos y correcciones de Jardín

Doce imágenes individuales revisadas (cuatro corregidas antes de integrar);
periquito, conejo, cobaya y hámster con tres fotos cargadas por perfil en QA móvil.
Recetas y productos comparten cribado médico exacto; «ninguna salvo diabetes» no
equivale a ausencia de condiciones. Retirada cantidad ficticia de «piezas» en
picaditos y otras preparaciones. No se activan recetas para especies especialistas.
Jardín: avisos de luz/drenaje llegan al resumen; no se afirma salud a partir de
un calendario vacío. Edición de condiciones conserva foto/historial. Clima ausente
no se convierte en 0 grados. Repetir una revisión no duplica tareas; «no regué»
no se interpreta como riego. 592 pruebas Home/compras aprobadas (51.82 s);
JS/SW/JSON/diff válidos. Navegador local: alta, edición, conservación de foto y
recordatorio de Jardín visible en Calendario (13/9 a las 9:00, aviso 1 h antes).
Público: HTML/JS/CSS/SW y doce imágenes HTTP 200 idénticos al commit
`735e63fec`; health correcto, registro apagado. Navegador normal meta 174,
Bella y Luna presentes y sus dos fotos de perfil cargadas.
HTML/APP 174, JS 175, CSS 124, SW 172.

## 175 público comprobado — coherencia de presupuesto en Renueva

La alternativa Completa excedía el presupuesto pero el encabezado decía que estaba
dentro. Ahora muestra límite, objetivo, exceso exacto y aclara estimaciones sin
impuestos/envío. Indicador semántico de comparación, contraste y texto legible.
Las ideas de fallback no se presentan como análisis de la foto, ni el guardado
anuncia un análisis si el proveedor está desconectado. Comparación temporal
conservada ante refresh en segundo plano, sin alterar presupuesto guardado.
QA local: sala sintética guardada y recuperada con foto; no análisis externo.
HTML/APP 175, JS 176, CSS 125, SW 173. 594 pruebas Home/compras aprobadas
(50.60 s), JS/SW/diff válidos. Comparación móvil antes/después inspeccionada;
sin desbordamiento, advertencia legible y selección estable.
HTML/JS/CSS/SW públicos HTTP 200 idénticos al commit `09298929e`; health correcto.
Recarga normal: meta 175, Bella y Luna presentes, ambas miniaturas cargadas.
Registro sigue apagado (`enabled:false`, `trial_days:5`). El recorrido con proyecto
sintético se probó sólo en QA, no con un proyecto real ni generación externa.
Ver `reports/home_renueva_audit_175_20260907.md`.
Inventario actual: 57 filas de preparaciones para mascotas, todas con activo
individual revisado (no 57 recetas por mascota); 94 guías separadas.

## Puerta de lanzamiento actual

No declarar lista la demo pública. Hace falta intervención del administrador para
resolver el aviso de pago de Render y `payment_issue` de ElevenLabs; no se cambió
facturación. Turnstile aún no está configurado y el alta real, recuperación y
soporte no están validados. La elección de registro abierto sigue aprobada, pero
no se habilitó sin estas pruebas. También queda curación editorial de borradores
humanos y verificación real de las integraciones; conservar sus restricciones.

## Cambio confirmado en infraestructura

Roberto autorizó ampliar únicamente el disco de Home de 1 a 10 GB, a un costo
publicado aproximado de USD 2.50/mes por disco (incremento USD 2.25/mes).
Render guardó 10 GB y el shell confirmó `/var/data`: 9.9G total, 957M usados,
8.9G disponibles, 10% usado. Antes estaba al 100% con 644K disponibles.
Las fotos de recetas ocupaban unos 925 MB. El panel conserva un aviso de pago
fallido: Roberto debe revisar su método de pago. No se modificó facturación,
servidor, otros servicios ni se contrataron servicios nuevos.
Se verificó un respaldo previo de 598K en
`/var/data/roxy_home/home_food.before-storage-fix-20260905.json` (copia sin sobrescritura).

## Bloque de protección anterior (162), conservado

- Se elimina la escritura destructiva sobre el JSON original cuando falta disco.
- Un archivo ilegible/corrupto falla de forma explícita (503), no se convierte en
  un hogar vacío susceptible de sobrescribir los perfiles.
- Antes de cada mutación se conserva una copia `.bak` de la versión válida anterior.
- Las ediciones de mascotas usan ID estable; los campos omitidos conservan su
  valor. Se conserva foto e historial. La mascota 21 se rechaza sin borrar la primera.
- La respuesta 202 de fotos no se interpreta como una imagen: se espera el archivo real.
- La generación de imágenes reserva 512 MiB para datos y respaldos antes de llamar a IA.
- Público: HTML 162, JS 159, CSS 116 (sin cambios), service worker 156.
- Verificado por HTTP y en el navegador público: versión 162; `/health` devuelve
  `status: ok`. Tras recargar, Bella y Luna aparecen en la UI. No se alteraron
  sus datos para realizar esta comprobación.
- `node --check assets/roxy_list.js`: correcto.
- 231 pruebas aprobadas: toda la suite `tests/test_roxy_home*.py`. Se corrigió
  un test de calendario que dependía del mes real, fijando la fecha de su escenario
  sin modificar el comportamiento del calendario. Python: `/Users/robertograu/roxy_trading/.venv/bin/python`
  (solo intérprete; no modifica el checkout Trading).

## Versión 163 — desplegada y comprobada en público

- JS 160, CSS 117, SW/APP 157. 335 tests aprobados (282 Home + 53 compras) y node --check JS/SW.
- Carrito corregido: productos enviados como PETS no se reclasifican como
  alimentos humanos por nombres como Litter Pan. Añadir/ver en Compra probado.
- Recetas separadas de guías de cuidado. Hábitat por especie con observaciones
  persistentes para acuarios, aves, reptiles y campos de otros grupos.
- Diferencia canario/psitácida/nectarívoro y evita dietas de otro grupo. Referencias
  específicas para betta/gecko; no certifica convivencia ni inventa sensores.
- Importación texto/captura/URL vinculada a mascota por ID y con gates de salud,
  etapa e ingredientes; Responses Terra para revisión de mascotas y contexto
  sanitizado, sin trasladar datos humanos. Requiere confirmar para guardar/comprar.
- Historial conserva entrada 101 y siguientes (límite explícito 1000), fechas de
  seguimiento y directorios externos por especie. Descarga real TXT comprobada.
- Ocho recetas ferret con ocho imágenes individuales; cuatro WebP nuevas. No
  se reactivan collages. Estados de carga ya no muestran alta de mascota fugaz.
- QA aislada con seis perfiles sintéticos; ninguno añadido a producción.
- Auditoría, límites y fuentes: reports/home_pets_audit_20260905.md; prompts de
  imágenes: reports/home_pet_artwork_20260905.md.
- Push a codex/roxy-home-nfc y autodespliegue Render comprobados. HTTP público:
  HTML 163, JS 160, CSS 117, SW 157; health ok. Durante reinicio hubo 502
  transitorios y se verificó recuperación, no se ignoraron.
- Navegador público tras recargar: Bella y Luna presentes. Recetas separadas;
  imágenes nuevas de medallones de pavo y pato de Luna cargan y corresponden
  a sus ingredientes. Evidencia: /tmp/roxy-pet-audit-20260905/public-luna-recipe-163.jpg.

## Pendientes reales — no declarar módulo terminado

- Luna está guardada como `ferret`. En esta auditoría se observó una miniatura de
  Luna en el selector público; no se verificó que fuera su foto original ni se
  restauró su perfil. La tarea anterior recreó Luna; no confundir eso con recuperación.
  Los datos de edad/salud ingresados por esa tarea no están verificados.
- Ferret y hurón doméstico son el mismo animal; Roberto prefiere el nombre Ferret.
- La frecuencia guardada de Bella muestra 1 vez/día; es dato existente, no una
  prescripción comprobada. Mejorar etiqueta para distinguir plan guardado de guía.
- Completar revisión/fotos del resto de recetas y productos. El catálogo todavía
  contiene assets genéricos no autorizados para mostrarse como imagen exacta.
- Cobertura antes del nuevo despliegue: 558/683 imágenes; 125 faltantes. Errores
  históricos: 80 RateLimitError y 45 OSError. El disco lleno se confirmó; la causa
  concreta de RateLimitError no está confirmada. No seguir ajustando concurrencia a ciegas.
- Probar todas las especies, personalización y fotos de productos/recetas en UI.
- Cobertura universal NO terminada: ampliar fichas revisadas, acuarios compartidos
  y compatibilidad estructurada. No toda especie admite recetas caseras.
- Petco permite solicitar afiliación mediante Impact; PetSmart Creators publica un
  programa. No hay aprobación ni API pública verificada. No se aceptaron acuerdos.
- Plan aprobado en conversación: beta web de cinco días antes de App Store; alcance,
  cupo, presupuesto IA y fecha deben definirse. Ejercicios es una sección solicitada,
  todavía no diseñada ni implementada. PostgreSQL y multimedia separada son
  recomendaciones, no contrataciones ni migraciones realizadas.

## Versión 164 — primer bloque de auditoría desplegado y comprobado

- HTML/APP 164, JS 163, CSS 118, SW 160. Públicos e idénticos a los archivos locales
  comprobados; health ok. DOM: Bella/Luna presentes, ambos integrantes Nexo y
  separación de recetas. Capturas y límites en el informe de auditoría.
- 350 tests Home + Shopping aprobados; node --check JS/SW y git diff --check.
- Auditoría por módulo y pendientes: reports/home_full_audit_20260905.md.
- Inventario automatizado completo: 668 fichas (517 humanas, 57 preparaciones para
  mascotas, 94 guías); 463 requieren revisión editorial. Se bloquea cocinar/enviar
  borradores a Compra y se exige revisión explícita. No se completó su curación.
- Respeto de hidden, campos numéricos de Compra/presupuesto, carga diferida de
  fotos, límites separados de medios y operaciones, conservación de caché de
  Jardín/Renueva, privacidad/antigüedad Nexo, etiquetas reales de afiliación.
- Comparador de actualización corregido: APP debe coincidir con HTML, no con SW.
- Voz: ElevenLabs rechazó la llamada pública con payment_issue. Requiere facturación
  del administrador. Alternativa escrita probada en QA con respuesta real de lista;
  cierre/cancelación de micrófono protegidos. No se cambió facturación.
- UI pública inicial recorrida, escrituras sólo en QA aislada. Alta de producto y
  evento verificadas; automatización bloqueada al intentar confirmación nativa de
  eliminar evento ficticio. No dar por completados los recorridos UI restantes.

## Versión 165 — cuarentena de foto desplegada y verificada

- En público 164, Aderezo César mostraba una ensalada, no el aderezo. Se bloquea
  exclusivamente esa asociación en servidor y cliente, sin borrar el archivo ni
  sustituirlo por otra foto genérica. Requiere imagen revisada antes de desbloquear.
- Se corrige el aviso de abrir/revisar antes de guardar. HTML/APP 165, JS 164,
  CSS 118, SW 161. 352 tests aprobados y node --check JS/SW.
- HTTP público y DOM confirman 165; JS/CSS/SW idénticos byte a byte a lo probado.
  Health ok. Endpoint de la imagen devuelve 404 y captura pública confirma ficha
  de Aderezo César sin la ensalada incorrecta. Archivo original no borrado.
- Cobertura pública final: 557/683 listas, 126 pendientes (incluye una en cuarentena),
  cola 0, contador diario 42; se informa INCOMPLETE. Las causas históricas de los
  límites del proveedor siguen sin verificar; no aumentar concurrencia a ciegas.
- Despensa y Más inspeccionados en público después de 164; pendientes sus cambios
  interactivos. Servidor QA detenido; no se dejaron mascotas ficticias en producción.

## Continuidad

Consultar también `data/roxy_continuity.json`, implementación y pruebas.
Este worktree no trae `tools/roxy_context_handoff.py`; la comprobación ejecutada en
el worktree origen Trading reportó archivos de continuidad ausentes. No copiar
memoria de Trading a Home para silenciar ese aviso.
