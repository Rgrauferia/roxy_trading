# Roxy Home209 — biblioteca ampliada y vista real

14 de septiembre de 2026. Candidata local; público203 sin modificación. No commit, push ni deploy.

## Resultado comprobado

Biblioteca unificada dentro de Ejercicio → Ejercicios, con entrada visual Roxy, modalidades, búsqueda, duración e idioma real. Conserva acceso directo a las fichas ilustradas y a las tres guías paso a paso anteriores. El formulario de filtros ya no dispara el formulario padre de preferencias. Maneja errores, respuestas tardías, cambio de identidad y desmontaje sin restaurar contenido antiguo.

- 25 fichas wger / 48 ilustraciones: 23 textos ES y 2 EN. Las 21 anteriores y sus 44 imágenes siguen intactas. Nuevas: plancha458, dominadas475, cuadrupedia957 y flexiones1551. El título original de1551 sigue Push-Up; su descripción es española. Fuentes y licencias particulares preservadas.
- Tres guías NHS / 16 movimientos distintos del catálogo anterior: fuerza7, equilibrio5, flexibilidad4.
- 18 recursos externos nuevos: 15 clases NHS/InstructorLive y 3 demostraciones Mayo. Yoga, Pilates, cardio/baile, fuerza, calistenia y movilidad. Hay solapamientos de modalidades; no sumar sus contadores como recursos distintos.
- Vídeos externos en inglés y enlaces a la página original. No se descargaron, doblaron, incrustaron ni reprodujeron completos los18vídeos. Títulos y resúmenes editoriales en español. Duración y material desconocidos siguen marcados; vacíos no equivalen a sin equipo.

El catálogo wger estaba temporalmente vacío durante la incorporación porque su validador v2 aún rechazaba otros autores. Se corrigió a v3 con lista exacta de medios, autor, licencia y hash revisados. Pruebas de API protegen IDs y contenido anteriores.

## Evidencia

422 pruebas Python de integración (clases, API, planes, PostgreSQL, repositorio, dominio, guías, demo y paquete) y59 del catálogo aprobadas.191 Node de integración y9 del catálogo aprobadas. Las41 de Discovery se repitieron tras ajustar concordancia singular; no sumarlas otra vez. Dos avisos de deprecación de Starlette/httpx; sin fallos finales. git diff --check limpio.

CUA en navegador real: catálogo18 visible; filtro Calistenia devuelve3 demostraciones; Yoga devuelve1 y Yoga+10min devuelve0 con recuperación; formulario no abandona Ejercicios. Tras reinicio de8771 se recupera Plan de prueba · septiembre y actividad realizada; fichas25 cargadas y plancha abierta con imagen real y texto ES. La imagen de plancha confirmó naturalWidth positivo. Se mostró la UI a Roberto.

Capturas útiles en reports/home-fitness-209/: biblioteca-entrada.png, biblioteca-clases.png, calistenia.png y plancha-escritorio.png. Son vistas actuales a858px de ancho. plancha-movil.png es una captura fallida del cambio de viewport y NO demuestra móvil: el navegador mantuvo innerWidth858 pese a pedir393. Override restablecido. Revisión visual móvil209 pendiente; no reutilizar QA207 como prueba de esta biblioteca.

## Runtime y paquete

HTML/APP209, JS216, SW209; DiscoveryJS2/CSS1, FitnessJS10, CatalogJS3. Nuevos assets y JSON incluidos en Docker y caché del shell; demo permite GET autenticado de clases.

Preview http://127.0.0.1:8771/lista#ejercicio, PID22637, sesión47027. PostgreSQL y datos sintéticos se conservan en /tmp/roxy-home-fitness-207-65_2kmfh. No contraseñas ni configuración privada en este informe. Preview8770/PID63912 no se reinició; mantiene voz fija Home en memoria. No nuevas llamadas de voz/IA en209.

## Lo pendiente sigue pendiente

Descubrimiento por filtros no es asignación personalizada por edad/peso/capacidad. Agenda207 sigue guardando guías generales elegidas por la persona; no se añadieron las nuevas clases como planes prescriptivos ni se inventaron cargas, series o calorías. No hay conexión Apple Watch, adaptación clínica ni película nueva. Avatar/Runway pausados. PostgreSQL público sin configurar; no se declaró terminado todo Home.

Continuar con selección y progresión por lugar, equipo, nivel, objetivos, días y minutos; preferencias/medidas privadas; instrucciones revisadas, seguimiento real y diseño inmersivo. Referencias: home_fitness_catalogue_209_sources.md, home_fitness_adaptation_209_sources.md y home_fitness_design_208_20260914.md.
