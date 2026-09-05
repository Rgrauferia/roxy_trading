# Roxy Home — estado operativo

Actualizado: 2026-09-05. Este documento pertenece exclusivamente a la rama Home.
No mezclar cambios, memoria, secretos ni despliegues de Trading/Crypto.

## Ubicación y despliegue

- Worktree: `/Users/robertograu/.codex/worktrees/roxy-home-renueva`.
- Rama local: `codex/roxy-home-renueva`; destino de despliegue: `origin/codex/roxy-home-nfc`.
- URL: https://roxy-home.onrender.com/lista#mascotas.
- Servicio Render: `roxy-home`, `srv-da0l3vs9v7es739kcmd0`, montaje persistente `/var/data`.
- Versión pública comprobada: 162, commit de implementación `479397228`.
  La versión anterior era 161 (`477269308`).

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

## Bloque de protección desplegado y verificado

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

## Candidata 163 — probada localmente, aún no desplegada

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

## Pendientes reales — no declarar módulo terminado

- Luna está guardada como `ferret`, pero sin foto. Bella tiene foto. No se recuperó
  el perfil/foto original de Luna. La tarea anterior recreó Luna; no confundir esto
  con recuperación. Sus datos de edad/salud ingresados por esa tarea no están verificados.
- Ferret y hurón doméstico son el mismo animal; Roberto prefiere el nombre Ferret.
- Publicar y comprobar la candidata 163; hasta entonces público sigue en 162.
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

## Continuidad

Consultar también `data/roxy_continuity.json`, implementación y pruebas.
Este worktree no trae `tools/roxy_context_handoff.py`; la comprobación ejecutada en
el worktree origen Trading reportó archivos de continuidad ausentes. No copiar
memoria de Trading a Home para silenciar ese aviso.
