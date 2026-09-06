# Roxy Home — estado operativo

Actualizado: 2026-09-06. Este documento pertenece exclusivamente a la rama Home.
No mezclar cambios, memoria, secretos ni despliegues de Trading/Crypto.

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
167 comprobado en público: arranque de Google Maps corregido, mapa y tráfico
visibles. Registro devuelve `enabled:false`. Candidato 168 separa controles de
zoom y ubicación, evita tapar la atribución y corrige aviso de permiso denegado.
Una prueba de zoom alcanzó el botón superpuesto de ubicación; el navegador denegó
permiso y Robert siguió privado. No se guardó preferencia ni se borró historial.
No aumentar gasto ni cambiar facturación. Voz continúa pendiente por `payment_issue`.

- Worktree: `/Users/robertograu/.codex/worktrees/roxy-home-renueva`.
- Rama local: `codex/roxy-home-renueva`; destino de despliegue: `origin/codex/roxy-home-nfc`.
- URL: https://roxy-home.onrender.com/lista#mascotas.
- Servicio Render: `roxy-home`, `srv-da0l3vs9v7es739kcmd0`, montaje persistente `/var/data`.
- Versión pública comprobada: 167, commit de implementación `ce2fd3f53`.
  Candidato 168 aún sin desplegar; 517 tests Home/compras aprobados y regresión
  adicional de botones de zoom, sin llamadas de ubicación.

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
