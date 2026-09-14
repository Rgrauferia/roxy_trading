# Ejercicio 214: revisión de integración y privacidad

Fecha: 14 de septiembre de 2026. Trabajo local, sin despliegue ni cambios a las bases de datos de las vistas previas.

## Resultado verificado

- La proyección `training-progress` devuelve resultados privados de la persona autenticada. El archivo de pruebas heredado quedó completo y pasa: identidad incorrecta, sesión compartida o ausente, lectura sin escrituras, historial retenido sin perfil, contenido anterior y fallo privado 503 sin reflejar detalles internos.
- Una propuesta para repetir comprueba el ID del registro propio y su versión. Una versión desactualizada produce 409; un registro ausente o ajeno produce 422. Esas solicitudes conservan perfiles, planes, registros e idempotencias. No basta enviar otro miembro en un parámetro de consulta.
- Los objetivos elegidos se conservan al guardar, volver a leer, exportar, añadir y reprogramar actividades. No crean resultados realizados. Una sesión que ya tiene resultados conserva sus objetivos originales: no se permite cambiarlos retroactivamente, incluidos los casos donde antes no tenía objetivos.
- Los traspasos de Progreso a Rutinas y Mi plan se consumen; limpiar o salir del espacio personal borra los traspasos pendientes. Los metadatos usan copias independientes.

## Correcciones acotadas del recorrido

`Ver registro` abría el calentamiento. Ahora el plan transmite una opción explícita de revisión y el lector abre las series realmente guardadas. Si el registro ya fue eliminado, muestra un aviso y mantiene los campos reales vacíos. Entrar normalmente desde una actividad sigue comenzando por el calentamiento. La consulta no concede permiso ni guarda o completa automáticamente una actividad.

Al entrar al lector también se elimina el aviso anterior de que el plan se guardó o reprogramó. Este aviso pertenecía al plan y quedaba encima de la escena.

Pruebas adicionales cubren el cambio entre ambos modos sin trasladar ediciones sin guardar, la lectura de historia cuando no se permiten nuevas escrituras y respuestas tardías al ocultar la vista.

## Ejecuciones

1. Python de todo Ejercicio más empaquetado Home: **1045 pasaron; 48 omitidas** porque esa primera invocación no llevaba la ruta de binarios PostgreSQL. Evidencia: `review-python-full.log`. Dos advertencias de deprecación de Starlette/httpx y anyio.
2. Se ejecutaron esas 48 pruebas PostgreSQL con `ROXY_FITNESS_TEST_PG_BIN=/tmp/roxy-home-pg-207-12g4auxo/install/bin`, más las cinco pruebas finales de objetivos/plan: **53 pasaron, cero omitidas**. Evidencia: `review-postgres.log`. Usan clusters desechables TLS/RLS; no migran ni reinician 8770/8771. Las cinco de objetivos ya están incluidas en la primera ejecución y no deben sumarse dos veces. **Cobertura total de esa selección: 1093 casos Python, todos verificados.**
3. Node de Ejercicio y de integración visual Home: **363 pasaron, cero fallos u omitidas**. Evidencia: `review-node-full.log`.
4. `git diff --check`: sin errores de espacios.

No se presenta esta revisión sintética como una prueba visual o como publicación. La comprobación en navegador y las capturas son responsabilidad de la tarea principal. No se modificaron rutinas, dosis, contenido clínico, secretos, datos del hogar ni conexiones de voz.

## Archivos de esta revisión

- `tests/test_roxy_home_fitness_training_targets_plan.py` — 5 casos de almacenamiento y preservación histórica.
- `tests/test_roxy_home_fitness_training_targets_api.py` — 9 casos de referencias de repetición por HTTP.
- `tests/test_roxy_fitness_progress_integration.cjs` — 9 casos de traspasos, metadatos y avisos.
- `tests/test_roxy_fitness_training_record_review.cjs` — 6 casos de consulta directa del registro.
- `assets/roxy_fitness_planner.js`, `assets/roxy_fitness_training.js` — solo las correcciones de apertura del registro y limpieza del aviso descritas arriba, sobre los cambios previos conservados.
