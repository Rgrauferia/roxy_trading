# Roxy Home — extractor editorial v5

10 de septiembre de 2026. Mejora **local del importador**, no catálogo publicado.

## Resultado comprobado

Se reprocesaron **en memoria y sin red** los mismos 510 originales de la instantánea congelada. No se ejecutó el importador contra proveedores ni se guardó otra versión del manifiesto.

| Medida | Instantánea v4 | Reextracción v5 |
|---|---:|---:|
| ES con referencias a archivos de imagen | 0/121 | 14/121 |
| EN con referencias a archivos de imagen | 94/389 | 98/389 |
| ES con notas/contexto suplementario extraído | 2/121 | 33/121 |
| EN con notas/contexto suplementario extraído | 213/389 | 258/389 |
| Recetas culinariamente aprobadas por esta operación | 0 | 0 |
| Recetas publicadas por esta operación | 0 | 0 |

Las 14 referencias ES identificadas en la auditoría anterior y los seis bloques `Artes culinarias/Trucos` pasan pruebas por receta. El método alternativo y el picadillo del gazpacho morañiego ahora tienen bloques separados: siguen siendo **cuatro pasos principales**, sin fusionar versiones. Se encontraron 361 bloques de contexto: 16 plantillas de notas, 215 secciones de notas, 129 secciones suplementarias y una sección alternativa. Esta amplitud incluye equipo/referencias u otros apartados, no 361 instrucciones de cocina nuevas.

Hay 112 filas con referencias, 113 nombres distintos y 114 referencias en total. **No son 112 fotos exactas ni licenciadas:** no se descargaron píxeles, no se consultaron nuevos metadatos y no se aprobó visualmente ningún recurso. Una imagen de una guarnición, materia prima o plato parecido necesita revisión independiente.

La comparación de las 510 filas confirma **cero cambios** en ingredientes, pasos, rendimiento, tiempo, original íntegro, SHA-256, revisión de fuente y huella de contenido. Las 510 conservan bloqueos de publicación/cocina/Compra. El hash del archivo congelado sigue siendo:

`746ced612d6ca725084128ad9b4c7e9dca602171d0eb1a3621c883de02ee83c5`

## Implementación

- `tools/roxy_home_recipe_import_wikibooks.py`: versión `wikibooks-candidate-import-5`. Descubre archivos en campos de plantilla, enlaces del cuerpo y galerías; admite nombres simples en campos de imagen. Conserva cada referencia con origen, posición y fragmento exacto. La lista de nombres elimina duplicados equivalentes sin perder sus apariciones en la evidencia.
- Extrae notas de campos, plantillas Trucos y encabezados suplementarios; guarda texto crudo, posición, SHA-256 y estado explícito de fuente no confiable. Las variantes no sustituyen ni amplían los pasos principales. Una segunda plantilla de receta se trata separadamente; una prueba sintética impide sobrescribir la primera.
- Comentarios y ejemplos `nowiki`/`pre`/`code`/`source`/`syntaxhighlight` no generan referencias o notas ficticias. El descubrimiento conserva posiciones; la extracción de texto sigue leyendo el original para no romper unidades que usan `nowiki` autocerrado.
- Nombres de imagen con URL, rutas, separadores de parámetros, caracteres de control, marcado o extensión no admitida se rechazan y señalan. La lectura de metadatos vuelve a validar todos los nombres antes de pedir nada al proveedor.
- Límites explícitos: 250.000 caracteres de fuente, 128 referencias y 64 bloques editoriales por página; nombre de archivo máximo 255 bytes. Un exceso interrumpe con error: no recorta ni devuelve una receta parcialmente extraída. Las entradas rechazadas siguen necesitando revisión; estos límites no son una afirmación sobre los límites propios de Wikimedia.
- Texto parecido a instrucciones para el modelo en notas se conserva como evidencia y se marca para revisión; no se sigue. Marcado activo se señala. **Los bloques crudos no son HTML sanitizado**: no se deben insertar en `innerHTML`, ejecutar ni tratar como políticas de Roxy.

## Pruebas y reproducción

Archivo nuevo: `tests/test_roxy_home_recipe_source_context.py`, **52 pruebas**. Usa originales/revisiones de la instantánea y fixtures sintéticos para límites, duplicados, variantes, galerías, nombres peligrosos, comentarios, marcado activo e instrucciones no confiables. La prueba de corpus compara las 510 filas y comprueba el hash del manifiesto antes y después.

```sh
/Users/robertograu/roxy_trading/.venv/bin/python -m pytest -q \
  tests/test_roxy_home_recipe_import_wikibooks.py \
  tests/test_roxy_home_recipe_source_context.py \
  tests/test_roxy_home_open_recipes_177.py
```

Resultado: **160 aprobadas** (33 importador + 52 contexto + 75 catálogo/gates), 0 fallos. `git diff --check` correcto. No se ejecutaron aquí las baterías completas de Home ni una prueba de despliegue porque no cambió runtime.

Preflight: estado/continuidad completos leídos con versión pública 182; cambios existentes preservados. `tools/roxy_context_handoff.py --check` sigue sin poder ejecutarse porque el helper no existe en Home, como ya documenta la continuidad. No se copió el helper de Trading.

## Límites y siguiente decisión

No se modificaron `data/home_recipe_candidates_20260910.json`, `home_open_recipes`, UI, servicio, Docker, datos reales ni continuidad compartida. No hubo compras, cuentas, claves, contratos o nuevas búsquedas masivas.

El cambio reduce pérdida de contexto; **no corrige los errores de las recetas fuente** documentados en `reports/home_recipe_es20_editorial_triage_20260910.md`. Antes de una promoción hay que resolver los defectos editoriales, verificar recurso/variante/licencia, revisar la preparación y conservar cada corrección aprobada. El lector de bloques es para revisión técnica/editorial; no se ha conectado a la voz, a Compra ni al recetario público.
