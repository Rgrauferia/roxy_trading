# Roxy Home 212 — mediciones y agenda por disponibilidad

## Entrega local verificada

Progreso incorpora mediciones privadas opcionales de peso y estatura, con fecha, unidades métricas o imperiales, revisión y consentimiento separado. El historial permite corregir entradas, exportarlas y eliminarlas. Las diferencias comparan valores declarados; no se calcula IMC, calorías, diagnóstico ni cargas de entrenamiento. La preferencia sin peso mantiene esta sección cerrada hasta una elección explícita.

Mi plan incorpora Organizar con mi disponibilidad: elige entre las tres guías NHS existentes y una fecha inicial, propone hasta siete días desde horarios guardados, permite editar y revisar, y guarda usando el contrato existente sin reemplazar las actividades anteriores. Respeta el tiempo disponible con traslado, horas ambiguas/inexistentes por DST, actividades existentes y un día entre guías de fuerza. Las guías no tienen duración total publicada: los minutos de la propuesta son una elección de agenda, no una duración técnica demostrada. Se guardan las fechas y horas; el calendario Home conserva su confirmación separada de duración.

## Privacidad y consistencia

Migración aditiva003 para mediciones en PostgreSQL Home, TLS verificado y FORCE RLS; no almacenamiento de salud en JSON o localStorage. Elegibilidad de perfil adulto comprobada dentro de la misma transacción que consentimiento/escritura. Control de versiones e idempotencia; purga de datos visibles al cambiar identidad u ocultar la página. El export/borrado global de Ejercicio incluye mediciones. Validación HTTP sanitizada, incluidos JSON NaN/Infinity, sin repetir los valores recibidos. Una respuesta de guardado incierta exige comprobar el servidor antes de repetir. Las propuestas son de solo lectura y vuelven a comprobar la versión y consentimiento de preferencias antes de guardar.

## Pruebas

- 700 pruebas Python aprobadas, incluidas PostgreSQL real TLS/RLS, API, contratos, catálogo, paquete y demo. Log python-final.log.
- 260 pruebas Node aprobadas, incluidas planificador, mediciones, integración del estudio y Home. Log node-final.log.
- CUA real sobre la misma cuenta sintética: preferencias adultas casa/sin material, martes/jueves/sábado18–19h y30min; mediciones13/14sep en kg/cm y lb/pies; comparación entre unidades correcta.
- Propuesta15/17/19sep18:00 revisada y guardada. Las dos actividades207 permanecen; una realizada y cuatro pendientes al final. Dos mediciones persistidas. No se alteraron colecciones del hogar ni el evento compartido previo.
- Progreso a858px y393px, sin overflow horizontal; historial de actividades plegado para acercar medidas a los conteos. Capturas progress-desktop-final.jpg y progress-mobile-final.jpg; las anteriores se conservan. Tras reinicio del servidor y recarga se recuperaron5actividades y2mediciones, sin errores de consola. QA visual comparada con progress-final.jpg de211 en la misma entrada visual; conserva tipografía, colores y habitación aprobados.
- Nuevos botones, revisión y consentimiento accesibles; tests de limpieza al ocultar/cambiar miembro y recuperación de errores.

## Archivos y ejecución

Nuevos measurements.py, proposals.py,003_measurements.sql,roxy_fitness_measurements.js/css y pruebas. Router, repositorio global, módulo principal, planificador y privacidad integrados. HTML/APP/SW212; list219,fitness14,planner8,measurementsJS/CSS1. Docker incluye los nuevos assets; migraciones usan mecanismo previo. Sin commit,push,deploy ni modificaciones a Trading.

Preview8771/PID69109/sesión98513 conserva el estado sintético /tmp/roxy-home-fitness-207-65_2kmfh y las migraciones001–003.8770/PID63912 no se reinició: conserva su voz fija en memoria.8771 sigue sin proveedor de voz; no se añadió una voz alternativa.

## Pendiente real y orden aprobado

Esta entrega conecta disponibilidad con agenda general, NO completa el entrenador personalizado solicitado. La biblioteca sigue con25fichas wger,3guías y18recursos externos; no se añadieron rutinas de gimnasio ni vídeos nuevos. Falta ampliar y revisar técnica/equipo/variantes, rutinas casa/gym por capacidad/nivel/tiempo, progresiones y seguimiento por ejercicio. El informe plan-sources.md identifica correcciones y propuestas editoriales viables; no fingir certificación clínica ni marcar gates anteriores como aprobados. Apple Watch requiere trabajo nativo y no está conectado. Avatar/Runway siguen pausados.

Roberto pidió pasar después a Mascotas: aplicar la experiencia inmersiva y comprobar perfiles, cuidados, historial, recordatorios, calendario, persistencia y errores. Mascotas está en cola, no iniciado ni declarado completo. Público203 y su PostgreSQL permanecen sin cambios; esta entrega es local. Todos los originales y prototipos se preservan.
