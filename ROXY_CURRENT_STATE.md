# Roxy Home — estado operativo

Actualizado: 2026-09-10. Este documento pertenece exclusivamente a la rama Home.
No mezclar cambios, memoria, secretos ni despliegues de Trading/Crypto.

## 183 — candidato verificado; publicación pendiente

Despensa: corregida pérdida de decimales/unidades con coma. Entrada semicolon,
compatibilidad legacy de tres campos, error por línea y ninguna sustitución
parcial ante entradas inválidas. API valida lista completa antes de mutar.
Nexo/Comercio: JSON corrupto o ausente tras inicializar ya no se trata como vacío;
lecturas que actualizan estado fallan con503 y conservan bytes. Marcador,
escritura atómica, bloqueo y permisos0600; campos desconocidos/legacy válidos retenidos.
Nexo radar: liberar mapa, timers y peticiones al ocultarse/salir; reanudar sólo
misma identidad/permisos. Clima descarta respuestas obsoletas y limita espera10s.
No modificación del acabado gráfico de lluvia ni falsas condiciones meteorológicas.
Extractor de recetasv5 recupera notas/fotos referenciadas sin cambiar ingredientes,
pasos ni hashes de510 candidatas: siguen0 aprobadas, manifiesto/runtime sin cambios.

Pruebas183:1653 Python aprobadas,11 PostgreSQL omitidas;211 Node y2mjs aprobados.
Revisión independiente encontró coerción true→1.0 en API; rechazada antes de
convertir con dos pruebas nuevas422 e inventario previo intacto.
HTML/APP183, JS185, CSS129, SW182. QA navegador1280x720 y393x852:
reproduce1,5litros→1/unidad5 antes del arreglo; ahora error visible y posterior
1.5litros conservado tras recarga. AliasAlex QA/Olivo/textogrande persisten.
Sin desbordamiento horizontal393px. Datos sólo sintéticos en8768; no teléfono
físico ni todos los módulos verificados. Evidencia /tmp/roxy-home-qa-183/.
Detalle: reports/home_release_183_20260910.md. NO afirmar demo terminada.

## Incidente de persistencia — 182 PUBLICADO y comprobado; NO demo terminada

182 publicado desde 6c19d6170cdc57e1e978b18ca552e83bddfaf356; Render Live
dep-dahe0ctckfvc73bpk2h0. Health200/ok y seis archivos públicos HTTP200 idénticos
al commit (HTML/JS/CSS/SW/guía Jardín/catálogo Ejercicio). Web Shell de la nueva
instancia confirma las cuatro rutas PLANTS/DESIGN en /var/data/roxy_home,
padre escribible y /var/data en montaje distinto de /app. No recuperar por
inferencia el contenido perdido: Pothos real sigue pendiente.

181 se publicó desde 87dc13ead6ba2de5323625c16a22c2b172b2237a.
Render Live, health200/ok y nueve assets públicos idénticos al commit.
La revisión pública tras recargar detectó Jardín vacío; antes la pantalla
mostraba un Pothos en Cosina. Render Web Shell confirmó PLANTS_PATH/IMAGE_DIR
y DESIGN_PATH/IMAGE_DIR UNSET, archivos de plantas ausentes en /app/data y
ninguna copia de plantas/Renueva en /var/data. No se han recuperado los datos;
no recrear plantas ni restaurar pruebas sintéticas. Evitar recargar teléfonos
que conserven la copia previa. Fotos originales no garantizadas en caché.

182 publicado: HTML/APP182, JS184, CSS129, SW181. Rutas persistentes de Jardín/Renueva, JSON fail-closed con marcador,
escrituras atómicas/fotos únicas, 503 sin revelar rutas; protección de copia
anterior en cliente y aislamiento de Renueva por miembro (no asumir dueño de
caché legacy de hogar). 1503 Python aprobadas,11 PG omitidas;139 Node y2 mjs.
Navegador393: alta Mango QA, ficha específica, pérdida simulada sólo en datos
sintéticos conserva copia descargable y aviso legible; luego se restauró archivo
QA original. Cero errores/warnings de consola. No planta real recuperada.
Load protege carreras entre miembros/hogares y oculta DOM viejo al cambiar;
cachés Commerce/Calendar/Daily/Nexo/Weather también se separan por identidad.
Navegador público conserva sesión, meta182/JS184; Ejercicio junto a Recetas,
21 fichas educativas y seis fotos de Desayunos cargadas (480px). Sin scripts
de Google Maps fuera de Nexo ni errores/warnings observados. No representa
comprobación de todas las fotos ni del teléfono físico. Capturas10/11 públicas
765×454; QA responsive393×852 aislado. Pothos sigue ausente en la vista pública.
No aplicar Blueprint: su disco declarado1GB difiere del real10GB; no pagos.
Render mantiene aviso Payment failed. Usuario debe resolver facturación.

Heartbeat activo `roxy-home-jornada-de-mejoras`: cada hora hasta el 10/09/2026
23:59 America/New_York (20260911T035900Z). Sólo Home, no pagos/contratos sin
autoridad concreta; avisar sólo avances relevantes, fallo o acción necesaria.
Prototipo8796 preservado; servidor QA8768 detenido y pestaña cerrada. Su carpeta
temporal sintética permanece para evidencia; no restaurar sus datos en producción.
Impact requiere login. No se han confirmado marcas precalificadas en la cuenta.
Recetas500 NO logrado: 510 candidatas,0 aprobadas; segunda auditoría20ES
detectó defectos materiales y fotos ilustrativas, no se publican por cantidad.

## 181 — publicado con incidente de Jardín pendiente

Estado de pruebas previo a publicación. HTML/APP181, JS182, CSS128,
SW179, FitnessCSS5/catalogJS2, GardenGuide1 y MapLibreLoader1. No tocar prototypes/.
Jardín: guía de cuatro pasos con saludo del miembro, voz del dispositivo
opcional, tierra/agua/desconocido, drenaje nullable, diario de texto sin foto
obligatoria y elección explícita CHECKED/WATERED. No identifica fotos por IA
desde la guía. Mango y romero tienen fichas/fuentes específicas y límites de
espacio/maceta. No sensores, vigilancia autónoma ni notificaciones implícitas.
Eliminados anuncio genérico y alertas interiores basadas sólo en calor exterior.
QA navegador 393x852: login sintético, añadir Monstera, registrar revisión sin
foto y editar ubicación/medio conservando foto y diario. No datos reales escritos.
Ejercicio junto a Recetas en barra fija de seis accesos; resto en Más.
Biblioteca educativa 21 fichas (19 ES/2 EN), 44 ilustraciones, 0 videos;
buscador/detalle probados. Entrenamientos y almacenamiento privado público no activados.
Fotos: tarjetas WebP de fuente existente (480px, máximo100KB), carga visible,
timeout/reintentos acotados y protección A/B para no sustituir imágenes nuevas.
SW deja de precargar biblioteca fotográfica; GoogleMaps sólo en Nexo y
MapLibre bajo demanda al abrir globo. Rutas descartan respuestas tardías tras
revocación/cambio de persona; no se ha mejorado el acabado gráfico del clima.
Pruebas: 1454 Python aprobadas, 11 PostgreSQL omitidas; 97 Node aprobadas y
dos baterías mjs aprobadas. Evidencia /tmp/roxy-home-day-20260910/.

Recetas: 4868 páginas fuente examinadas, 510 CANDIDATAS (121 ES/389 EN),
ninguna aprobada ni publicada; data/home_recipe_candidates_20260910.json es
evidencia editorial fuera del runtime/Docker. 14 originales archivados en
home_open_recipes; 8 retenidos por problemas reales, 6 legibles con2 fotos/27pasos,
NO recetas ensayadas ni guía culinaria aprobada. No modificar las recetas guardadas.
TheMealDB sigue sin cuenta/clave/tier comercial confirmado; opciones y conflictos
de precio/licencia documentados en reports/home_recipe_provider_options_20260910.md.
Impact requiere iniciar sesión al10/09; no se comprobaron precalificados de cuenta.
No pagos, contratos, claves, plantas reales, mascotas ni compras modificados.
Siguiente: recuperar copia real del Pothos si el teléfono aún la conserva,
continuar auditoría integral y catálogo500,
resolver proveedor/licencia; revisar voz real, plantas conversacionales, clima,
persistencia fitness y condiciones del demo antes de anunciar lanzamiento.

## 180 — acceso, aislamiento de Compra y metadatos del clima PUBLICADOS

Login corregido: tras recibir la cookie, recarga el documento en Hoy. Antes,
un cambio de fragmento dejaba abierto el formulario con contraseña correcta.
Evita envíos duplicados y conserva el formulario ante rechazo. Navegador real
con cuenta sintética desechable: error incorrecto visible y acceso correcto
abre Hoy; 41 pruebas Node login/Ejercicio y 5 backend cuentas aprobadas.
No se ha probado todavía el teléfono ni las credenciales reales del usuario.

Compra deja de añadir dietas/alergias humanas a artículos PETS, limpieza y
otras categorías no alimentarias, incluidas preparaciones guardadas antiguas.
Unidades Instacart se traducen solo por equivalencias exactas, sin inventar
pesos; envases ambiguos/cantidades inválidas requieren revisión antes de red.
87 pruebas de comercio aprobadas. No llamadas de compra ni cambios de afiliación.
El globo de Nexo reutiliza frescura meteorológica y ya no inventa 0° si falta
temperatura ni llama actual a un dato vencido. Conserva un 0° válido y fecha/fuente.
32 pruebas de clima aprobadas; no hay cambios de gráficos ni catálogo de Ejercicio.
Publicado HTML/APP180, JS181, SW178 desde bb81c99e5 en codex/roxy-home-nfc.
Validación global: 1.289 pruebas Python aprobadas y 41 Node. Once pruebas de
PostgreSQL se omiten en este entorno ordinario; no se modificó esa capa y la
evidencia local real de 179 se conserva. Render confirmó bb81c99e5 como último
commit live; HTML/JS/SW públicos HTTP200 byte a byte idénticos y health200/ok.
Navegador público meta180, sesión conservada, mapa y globo reales cargados; la
cabecera muestra Modelo Open-Meteo/hora válida y radar RainViewer operativo.
Captura vista: /tmp/roxy-home-audit-20260910/globe-180.png. No tormenta observada.

Render accesible con sesión el 10/09; último live bb81c99e5/180, y aviso
«Payment failed» comunicado al usuario. No pagos ni cambios de tarjeta.
Los avisos históricos de sesión cerrada en 179 ya no describen el acceso actual.
Recetario original: 6 fichas Wikibooks; TheMealDB sigue sin cuenta/clave/licencia
comercial confirmadas. Ejercicio: 8 fichas/16 ilustraciones, 0 vídeos, cobertura
insuficiente y sin entrenamientos activos. Clima aún no tiene el acabado pedido.
Ver informes de acceso/Instacart del 09/09, continuados el 10/09. Datos públicos
de mascotas y hogar preservados. `prototypes/` sin tocar. Siguiente paso: usuario
reintenta acceso desde teléfono y atiende aviso de facturación. La evidencia
posterior al despliegue se registra localmente, sin volver a desplegar el mismo código.

## 179 — Ejercicio educativo PUBLICADO y comprobado

Roberto autorizó continuar y publicar. Se incorpora selección fija de wger:
8 fichas, 7 originales ES y 1 EN, 14 párrafos y 16 ilustraciones Everkinetic,
NO fotografías. IDs/licencias/autores/fechas/hashes por recurso. Búsqueda por
nombre/grupo/material, detalle y atribución; grupos/material traducidos, indicaciones
originales conservadas. No se asignan sesiones, cargas ni se habilita cribado.
GET educativos autenticados funcionan incluso con acceso compartido o demo
vencida; no acceden a preferencias ni consumen cuota IA. API no-store y fuera del SW.
Privacidad de Ejercicio añadida a /privacy, con enlace desde consentimiento/Ajustes.
Se corrigieron mensajes de resultado incierto: un 503 no demuestra que no se guardó.

PostgreSQL 17.11 REAL local: 11 pruebas aprobadas, TLS verify-full, rol restringido,
FORCE RLS entre dos miembros, concurrencia/idempotencia, revocación, eliminación y
persistencia tras reinicio. No se aprovisionó ni comprobó PostgreSQL en Render.
Sesión Render cerrada; acceso con GitHub abierto y solicitado al usuario, sin claves
copiadas, pagos ni cambios de entorno. Entrenamientos necesitan catálogo más amplio,
cribado/plantillas revisados por profesionales, modo sesión y validación.

1.242 pruebas Python Home/compras/proveedor aprobadas (1.168 + 74); 11 skips en
entorno ordinario se ejecutaron aparte con PostgreSQL real, 11/11. 33 pruebas Node.
Ocho fichas recorridas en navegador; las 16 imágenes cargan, búsqueda/retorno y
enlace privacidad comprobados, sin errores/warnings ni desbordamiento a 1049×714.
La ampliación no se ha comprobado todavía en teléfono físico; el intento de
viewport móvil no cambió el tamaño efectivo del tab en esta ejecución.
Ver reports/home_fitness_catalog_20260908.md,
reports/home_fitness_postgres_integration_20260908.md y design-qa.md.

Publicado desde commit 762ef1ae5 en codex/roxy-home-nfc. HTML/APP179, JS180, SW177,
fitnessJS4/CSS4, catalogueJS1. Ocho recursos públicos HTTP200 y byte a byte iguales:
HTML, JS principal, SW, tres assets fitness, privacidad y hero. Health HTTP200/ok.
Hubo un 502 transitorio durante el despliegue; luego la web y health se recuperaron.
API educativa sin autenticar devuelve 401 y private/no-store. Navegador autenticado:
179, bienvenida, ocho fichas, búsqueda piernas y Curl femoral sentado con 2/2
imágenes cargadas, sin errores/warnings ni desbordamiento. Guardado público
NO disponible, confirmado por UI; no entrenamientos activos. No módulo completo.
Cuenta local de QA sintética temporal en 8767, sin proveedores ni guardado privado.
No se modificaron mascotas, compras o datos de usuarios. Prototipo 8796 preservado.
Siguiente acción requerida del usuario: iniciar sesión en Render para revisar la
base privada Home y condiciones/coste antes de aprovisionar; ninguna nueva compra
autorizada. Revisor cualificado necesario para cribado y plantillas de entrenamiento.
La evidencia de publicación se registra localmente después del commit desplegado;
no requiere otro despliegue del mismo código.

## 178 — evidencia histórica de la primera base local, antes del candidato 179

Se añadió Ejercicio al menú Home y una navegación de cinco accesos al entrar.
Bienvenida con Roxy ilustrativa, cinco pasos voluntarios de preferencias, objetivos,
unidades/zona horaria, disponibilidad con hasta cuatro ventanas por día y material
confirmado. Seis secciones navegables: Hoy, Mi semana, Ejercicios, Progreso,
Alimentación y Servicios. La semana muestra disponibilidad, NO entrenamientos.
Enlaces al recetario y Hoy existentes sin modificar menús, calendario ni Compra.

API `/api/fitness/v1`, identidad exclusivamente por miembro autenticado,
consentimiento/versiones/idempotencia, exportación/eliminación y repositorio
PostgreSQL exclusivo Home preparados. No fallback JSON ni caché privada en navegador.
CSRF de mismo origen, bloqueo del acceso compartido, vinculación contra cambio de
miembro en otra pestaña y limpieza del estado privado ante sesión cambiada/vencida.
TLS verify-full, rol sin privilegios de propietario y FORCE RLS requeridos.
Migración manual: `migrations/fitness/001_foundation.sql`. PostgreSQL real NO
aprovisionado ni probado; Docker daemon no disponible. Las pruebas usan dobles SQL.

No hay cribado profesional aprobado, catálogo licenciado, plantillas ni sesiones
activas. No prescripciones, suplementación, afiliados, reservas o wearables.
CSEP requiere licencia de integración; wger investigado sin incorporar catálogo;
MuscleWiki no contratado. La ilustración de Roxy no enseña técnica.

1.174 pruebas Python Home/compras y 25 Node UI aprobadas. Recorrido local con
preferencias sintéticas, seis pestañas, errores de zona horaria, dos ventanas por
día, pasos/ajustes y enlaces comprobados. QA 393×852, 768×1024 y 1280×900 sin
desbordamiento; progreso corregido para CSP (paso 2 = 40 %). Sin errores/warnings
en la comprobación final del navegador. Ver `design-qa.md` y
`reports/home_fitness_implementation_20260908.md` para alcance y límites.

Vista local: `http://127.0.0.1:8767/fitness-preview`, helper
`python -m tools.roxy_home_fitness_preview`, cuenta sintética temporal sin claves
externas ni PostgreSQL. Selecciones de Ejercicio solo en memoria, se pierden al
recargar. Se deja servidor local abierto; viewport restaurado. Prototipo 8796
y datos públicos Bella/Luna preservados. No pagos, cambios de entorno público,
push ni despliegue. Público sigue 177. Candidato HTML/APP178, JS179, CSS127,
SW176, fitnessJS3/CSS3. Siguiente puerta: PostgreSQL real con aislamiento entre
dos miembros y revisión/licencia de contenido antes de habilitar entrenamientos.

## 177 — publicado y comprobado en Render

Commit de implementación `ae7164fe6`, rama `codex/roxy-home-nfc`. HTML/APP177,
JS178, CSS127, SW175, proveedorJS2, originalesJS1 y climaJS1: siete archivos
públicos HTTP200 y byte a byte idénticos; health OK y meta 177 en navegador.
Originales públicos: seis fichas, foto de tortilla cargada y lector paso 2/8.
Bella y Luna visibles; Luna Ferret conserva ocho fichas pendientes y foto de
pavo cargada. Google Maps, Robert/Roxy y clima parcialmente nublado visibles;
no lluvia inventada para esa condición ni prueba de tormenta real. No se pidió
GPS/micrófono ni se editaron perfiles, fotos o compras públicos.

Nueva selección gratuita de seis originales Wikibooks de seis cocinas: 31 líneas
de ingredientes, 36 pasos y raciones originales en inglés; revisiones fijas,
SHA-256, atribución y CC BY-SA 4.0. Lectura paso a paso y descarga TXT; no se
inventan medidas ni se convierten a Compra/IA. No significa recetario completo.
TheMealDB añade búsqueda por país y consulta de hasta cuatro detalles completos.
Roberto confirma que NO tiene cuenta ni clave. Sin pagos ni cambios de entorno;
licencia comercial/terceros y clave Home siguen pendientes. Una consulta de
desarrollo autorizada con la clave pública 1 respondió HTTP200 (52771, ocho
ingredientes, 619 caracteres de instrucciones); no es acceso comercial verificado.

Eliminada generación/certificación automática de recetas y fallback inventado en
solicitudes de texto/voz. Reutiliza preparaciones revisadas y compatibles; si no
existe, pide una fuente original. Mascotas: las 57 preparaciones locales carecen
de original validado; referencias generales NO las certifican. Fichas y fotos se
conservan con aviso; cocinar/escalar/Compra quedan bloqueados hasta verificar.
Directorio Hill’s para perros/gatos y guías VCA/Oxbow para Ferret, sin convertir
estas guías en recetas. No se han editado Bella, Luna ni otros datos públicos.

Nexo: Canvas con lluvia en profundidad, viento, nieve diferenciada y gotas finas;
apagado por datos vencidos/movimiento reducido/oculto, coste acotado y limpieza.
Comparación visual antes/después de fixture aislado y lector original móvil
comprobados. Clima de modelo Open-Meteo no es observación exacta ni radar; mantiene
RainViewer separado. No se afirma tormenta fotorrealista ni prueba en teléfono físico.
Ver reports/home_recipe_sources_177_20260908.md y home_pet_provenance_177_20260908.md.
975 pruebas Python Home/compras/proveedor y dos baterías Node aprobadas; videos
también respetan la revisión de recetas. Corregido el recorte
silencioso de pasos al guardar y la edición duplicada en búsquedas locales.
Prototipo cinematográfico preservado.

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
- Versión pública comprobada: 177, commit de implementación `ae7164fe6`.
  HTML/APP 177, JS 178, CSS 127, SW 175, proveedorJS 2, originalesJS 1 y climaJS 1;
  los siete archivos públicos coinciden con el commit. Sin nuevas fotos generadas.
  975 pruebas Home/compras/proveedor y dos baterías Node aprobadas.
  Registro apagado, demo de cinco días aún no abierta.
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
