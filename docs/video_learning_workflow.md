# Roxy Video Learning Workflow

Objetivo: convertir clases descargadas, PDFs, imagenes y documentos de estudio en conocimiento util para Roxy sin habilitar ejecucion real.

## Flujo

1. Detectar videos/materiales de trading en:
   - `/Users/robertograu/Downloads`
   - `/Users/robertograu/Movies`
   - `/Users/robertograu/Desktop`
   - carpetas Roxy/Trading en `/Volumes/RoxyData`
2. Para videos: extraer metadata con `ffprobe`, audio con `ffmpeg`, capturas cada 5 minutos y OCR con `tesseract`.
3. Para PDFs/documentos/imagenes: extraer texto con `pypdf`, XML interno de Office, texto plano o OCR con `tesseract`.
4. Generar notas `auto_knowledge.md`.
5. Clasificar temas: medias, canales, lateralidad, timing, opciones, VWAP, liquidez, macro/FED, fundamentales y estrategias.
6. Archivar fuentes procesadas en el disco externo si esta disponible.
7. Actualizar `training_videos/video_learning_index.json`.
8. Mostrar videos y materiales en Estudios.
9. Si no hay material nuevo, generar una revision de aprendizaje con mejoras candidatas en `training_videos/idle_learning_review.md`.

El scanner evita carpetas de proyectos no relacionados, incluyendo `RoxyEnterprise`, para no mezclar plantillas legales o documentos internos con material de trading.

## Comandos

Procesar videos nuevos:

```bash
.venv/bin/python tools/video_learning_ingest.py
```

Procesar videos nuevos o estudiar lo ya aprendido si no hay nada nuevo:

```bash
.venv/bin/python tools/video_learning_ingest.py --idle-review
```

Procesar solo Downloads:

```bash
.venv/bin/python tools/video_learning_ingest.py --source /Users/robertograu/Downloads
```

Procesar un video/candidato por corrida:

```bash
.venv/bin/python tools/video_learning_ingest.py --source /Users/robertograu/Downloads --limit 1
```

Transcribir audio con Whisper local:

```bash
.venv/bin/python tools/video_learning_ingest.py --source /Users/robertograu/Downloads --limit 1 --transcribe --model-size tiny
```

## Coordinacion entre pestanas de Codex

- Estado compartido: `training_videos/ROXY_LEARNING_SYNC.md`.
- Indice consumido por la app: `training_videos/video_learning_index.json`.
- Revision de aprendizaje cuando no hay videos nuevos: `training_videos/idle_learning_review.md`.
- Cada video procesado tiene `manifest.json`, `ocr_combined.txt` y `notes/auto_knowledge.md`.
- Cada material procesado tiene `manifest.json`, `extracted_text.txt` cuando aplica y `notes/auto_knowledge.md`.
- Ninguna regla aprendida pasa directo a ejecucion real; primero entra en Estudios/Roxy Lab y luego se mide.

## Automatizacion local

- LaunchAgent: `com.roxy.video-learning`.
- Configuracion: `deployment/com.roxy.video-learning.plist`.
- Intervalo: cada 35 minutos (`2100` segundos).
- Si encuentra videos o materiales nuevos, los procesa y puede archivarlos en `/Volumes/RoxyData/RoxyVideosAnalizados`.
- Si no encuentra nada nuevo, actualiza `idle_learning_review.md/json` para que Roxy siga estudiando el conocimiento ya extraido.

## Dependencias

- `ffmpeg`
- `ffprobe`
- `tesseract`
- `faster-whisper` en `.venv` para transcripcion opcional
- `pypdf` en `.venv` para PDFs
