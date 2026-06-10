# Coordinacion entre pestanas de Codex

Este proyecto puede tener dos sesiones de Codex trabajando al mismo tiempo. Para evitar pisar cambios, cada sesion debe respetar estas areas de responsabilidad.

## Division de trabajo

### Codex aprendizaje/videos

- Procesa videos, PDFs, capturas y notas de clases.
- Trabaja principalmente en `training_videos/`, `tools/video_learning_ingest.py`, `tests/test_video_learning_ingest.py` y material de estrategia.
- Extrae reglas de estudio, requisitos, ejemplos y notas para el Centro de Estudios.
- No cambia servicios 24/7, LaunchAgents, backups, limpieza, alert delivery ni health checks sin coordinarlo.

### Codex operacion/producto

- Mantiene la app operativa: Streamlit, LaunchAgents, health realtime, limpieza automatica, backups, alertas, dashboard operativo y verificacion continua.
- Trabaja principalmente en `tools/roxy_realtime_check.py`, `tools/*launchd*.py`, `tools/output_maintenance.py`, `streamlit_app.py` para estado operativo, tests de dashboard/health y documentacion operativa.
- Puede leer notas generadas en `training_videos/`, pero no debe editar ni mover archivos de esa carpeta mientras haya ingesta o descarga activa.
- No modifica reglas de estrategia aprendidas de videos salvo para cablearlas de forma segura al producto.

## Reglas de seguridad

- Ninguna regla aprendida de video habilita operaciones reales automaticas.
- Las alertas siguen bloqueadas por confirmacion multi-timeframe, riesgo, volumen, frescura de datos y calidad de alerta.
- Si una sesion toca un archivo compartido como `streamlit_app.py`, debe dejar cambios pequenos, testeados y con commit enfocado.
- Antes de commitear, revisar `git status --short` y no incluir cambios de la otra sesion.

## Handoff recomendado

- Aprendizaje/videos deja resumen en `training_videos/README_FOR_CODEX.md` o en el indice generado por `tools/video_learning_ingest.py`.
- Operacion/producto lee esos artefactos y decide como mostrarlos o verificarlos en la UI sin cambiar el contenido original.
- Si hay conflicto en un archivo compartido, priorizar conservar ambos cambios y separar commits por responsabilidad.
