# Roxy Knowledge Allowed Sources

Este pipeline alimenta a Roxy solo con fuentes que el usuario tiene derecho a usar. La carpeta principal de entrada es `knowledge/inbox`.

## Fuentes permitidas

- **Libros**: solo libros comprados, licenciados, de dominio publico o con permiso explicito para uso personal/educativo.
- **Cursos**: transcripciones, notas y materiales de cursos solo si tienes derecho a usarlos.
- **Apuntes propios**: notas, resumenes, planes de trading, diarios y documentos escritos por el usuario.
- **Documentos publicos**: documentos oficiales, guias publicas, reportes regulatorios, material educativo publico y licencias abiertas.
- **Datos de mercado por API**: solo desde proveedores configurados con credenciales propias y terminos compatibles.
- **Calendario economico**: fuentes oficiales o proveedores con permiso de uso.
- **Indicadores**: formulas, reglas, limites y ejemplos creados por Roxy o documentos permitidos.
- **Noticias**: solo feeds licenciados, fuentes publicas permitidas o resumenes propios.
- **Estrategias internas**: reglas creadas por el usuario, backtests propios, playbooks y checklists internos.
- **Diario de trading**: resultados, capturas, errores y reflexiones del usuario.
- **Backtesting**: reportes generados por Roxy, notebooks y resultados historicos autorizados.

## Carpetas recomendadas

- `knowledge/inbox/libros`: PDFs/TXT/MD legales de libros o apuntes largos.
- `knowledge/inbox/cursos`: transcripciones y notas de cursos autorizados.
- `knowledge/inbox/datos-mercado`: exportaciones de OHLC, tick data, options chain o datasets autorizados.
- `knowledge/inbox/economia`: calendario economico, FOMC, CPI, PPI, GDP, NFP y fuentes oficiales.
- `knowledge/inbox/noticias`: noticias autorizadas o resumenes propios.
- `knowledge/inbox/indicadores`: documentacion de indicadores y ejemplos.
- `knowledge/inbox/estrategias`: playbooks, reglas y checklists internos.
- `knowledge/inbox/backtesting`: reportes de pruebas y resultados historicos.
- `knowledge/inbox/diario-trading`: diario personal de operaciones.

## Fuentes no permitidas

- Libros, cursos o PDFs descargados sin licencia.
- Contenido privado de terceros sin permiso.
- Datos de mercado o APIs usados fuera de sus terminos.
- Material con informacion personal sensible innecesaria.

## Descargas automaticas y APIs

El pipeline no descarga libros automaticamente ni conecta APIs por defecto. Para habilitar una fuente remota hay que agregarla primero al catalogo, validar licencia/credenciales y crear un conector explicito. Esto evita alimentar a Roxy con informacion ilegal, falsa o sin permiso.

La lista completa de conocimiento objetivo esta en `knowledge/sources/roxy-knowledge-roadmap.json`.

## PDFs legales

Se pueden colocar PDFs legales en `knowledge/inbox`. Si el PDF tiene texto embebido, el sistema lo extrae. Si no tiene texto legible, intenta OCR cuando las herramientas locales estan disponibles. Si no puede extraer texto, el archivo queda marcado como `failed` en `knowledge/processed`.
