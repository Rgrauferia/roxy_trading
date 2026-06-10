# Coordinacion entre pestanas de Codex

Este proyecto puede tener varias sesiones de Codex trabajando al mismo tiempo. Para evitar pisar cambios, cada sesion debe respetar estas areas de responsabilidad.

## Division de trabajo

### Codex aprendizaje/videos

- Procesa videos, PDFs, capturas y notas de clases.
- Trabaja principalmente en `training_videos/`, `tools/video_learning_ingest.py`, `tests/test_video_learning_ingest.py` y material de estrategia.
- Extrae reglas de estudio, requisitos, ejemplos y notas para el Centro de Estudios.
- No cambia servicios 24/7, LaunchAgents, backups, limpieza, alert delivery ni health checks sin coordinarlo.

### Codex operacion/producto

- Mantiene la app operativa: LaunchAgents, health realtime, limpieza automatica, backups, alertas, disponibilidad Streamlit y verificacion continua.
- Trabaja principalmente en `tools/roxy_realtime_check.py`, `tools/*launchd*.py`, `tools/output_maintenance.py`, `tools/runtime_backup*.py`, tests de health/servicios y documentacion operativa.
- Puede leer notas generadas en `training_videos/`, pero no debe editar ni mover archivos de esa carpeta mientras haya ingesta o descarga activa.
- No modifica reglas de estrategia aprendidas de videos salvo para cablearlas de forma segura al producto.
- Evita cambios visuales grandes en `streamlit_app.py`; si necesita tocarlo por estabilidad, debe hacerlo en commits pequenos y coordinados.

### Codex dashboard/UI/graficas

- Mejora como se ve y funciona la pagina: layout, informacion en pantalla, filtros, tablas, graficas interactivas, estados visuales y experiencia de uso.
- Trabaja principalmente en `streamlit_app.py`, componentes visuales, graficas Altair/Plotly/Streamlit y tests de dashboard.
- Puede consumir artefactos de `alerts/`, `output/` y reportes generados, pero no cambia los productores backend si no es necesario.
- No toca LaunchAgents, backups, limpieza automatica, `tools/roxy_realtime_check.py`, `training_videos/` ni `tools/video_learning_ingest.py`.
- No cambia ejecucion real de trades ni reglas profundas de estrategia/cerebro.

## Reglas de seguridad

- Ninguna regla aprendida de video habilita operaciones reales automaticas.
- Las alertas siguen bloqueadas por confirmacion multi-timeframe, riesgo, volumen, frescura de datos y calidad de alerta.
- Si una sesion toca un archivo compartido como `streamlit_app.py`, debe dejar cambios pequenos, testeados y con commit enfocado.
- La sesion dashboard tiene prioridad sobre cambios visuales de `streamlit_app.py`; la sesion operacion solo debe tocarlo por estabilidad o compatibilidad.
- Antes de commitear, revisar `git status --short` y no incluir cambios de la otra sesion.

## Handoff recomendado

- Aprendizaje/videos deja resumen en `training_videos/README_FOR_CODEX.md` o en el indice generado por `tools/video_learning_ingest.py`.
- Dashboard/UI decide como mostrar esos artefactos en la pagina sin cambiar el contenido original.
- Operacion/producto verifica que esos artefactos no rompan health, storage, alertas ni servicios 24/7.
- Si hay conflicto en un archivo compartido, priorizar conservar ambos cambios y separar commits por responsabilidad.
