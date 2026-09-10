# Coconut Pyramids — vínculo de foto y versión

10/09/2026. Revisión independiente de una candidata; **no aprobación culinaria, edición de recetas ni publicación**. Complementa el [informe de diez EN](home_recipe_10en_editorial_20260910.md); no lo reemplaza.

## Hallazgo nuevo

La fotografía sí tiene un vínculo documental más fuerte que una imagen genérica: el autor de Commons también añadió ese archivo a la receta el día que los metadatos fechan la imagen. **Sin embargo, la revisión asociada entonces no tiene el mismo rendimiento que la candidata actual.**

| Evidencia | Fuente de 2013 | Candidata archivada de 2025 |
|---|---|---|
| Revisión de receta | [2526443](https://en.wikibooks.org/w/index.php?title=Cookbook%3ACoconut+Pyramids&oldid=2526443), 16/05/2013 13:35:57 UTC | [4523979](https://en.wikibooks.org/w/index.php?title=Cookbook%3ACoconut+Pyramids&oldid=4523979), 15/07/2025 19:37:53 UTC |
| Autor de edición comprobado aquí | ChrisHodgesUK; comentario de añadir imagen/ampliar/corregir | No se consultó autor de esta revisión; se conserva el original archivado |
| Rendimiento de cabecera | 12, en plantilla posicional | 6, en campo `servings` |
| Cerezas opcionales | Aproximadamente 12 | Aproximadamente 6 |
| Formación | Pirámides sin número en el paso | Seis o siete pirámides en el paso |
| Base | 100 g coco desecado, 50 g azúcar, un huevo | Misma base |
| Horno | 180 °C, 15–20 min, dorado pálido | Mismos parámetros |
| Imagen enlazada | `Coconut pyramid sharp.png`, pie/alt que identifica pirámides en cápsulas en una venta de pasteles | Mismo archivo, sin ese pie/alt |

La revisión histórica tiene cinco líneas de ingredientes y siete pasos, como la candidata. La foto no debe utilizarse para deducir tamaño, tiempo, textura interior o cuántas piezas rinde hoy la mezcla. El cambio de rendimiento podría afectar dimensiones; **no se ensayó ni se declara un resultado físico**.

## Imagen y derechos archivados

[Descripción Commons, revisión 862967573](https://commons.wikimedia.org/w/index.php?title=File:Coconut_pyramid_sharp.png&oldid=862967573): ChrisHodgesUK, obra propia, CC BY-SA 3.0, 2304×1844; SHA-1 del archivo `26ce318c51b0cd09f450fa809299d89f04b917f7`. `DateTimeOriginal` declara 16/05/2013 y `DateTime` 13:31:12 de ese día; no confundir estos metadatos con prueba forense de captura. La descripción dice que se consulte el recetario, pero no contiene enlace a una revisión.

El cotejo con la edición 2526443 refuerza **foto vinculada documentalmente a la receta de 2013**. No establece ejecución de la revisión 4523979. No inspeccioné píxeles en este bloque; la tarea principal realiza esa revisión. La licencia de foto es separada del texto CC BY-SA 4.0: conservar autor, fuente, licencia e indicación de cambios, sin inventar cesión exclusiva ni aval del autor.

## Qué falta para cada alcance

- **Ficha original legible:** los cinco ingredientes y siete pasos de 2025 están conservados y no presentan una omisión material de la preparación básica detectada aquí. Presentar además las dos notas originales por separado: chocolate opcional y conservación descrita por la fuente. Identificar idioma/revisión, mantener seis frente a seis–siete sin normalizar, y no convertir los veinte minutos declarados en tiempo total garantizado. Un lector fiel no es una receta probada ni una autorización para cocinar/escalar/Compra.
- **Foto exacta de la versión 2025:** falta cotejo visual y evidencia de esa variante/rendimiento. Puede describirse como foto que la fuente utiliza, con procedencia 2013 y alcance explícito; no como prueba de ejecución actual. No elegir silenciosamente la receta antigua solo para hacer coincidir una fotografía.
- **Guía culinaria validada:** faltan prueba física, resultado/enfriado y revisión de conservación/ingredientes comerciales. No transformar «unos días» en una caducidad calculada, añadir temperatura interna universal, garantizar ausencia de gluten ni adoptar la afirmación introductoria de aptitud infantil.

## Método y conservación

Se usó el enfoque de calidad de datos para separar fidelidad, versión y aprobación. Preflight de Home completo con 183 publicado; helper de handoff ausente como ya documentado. Se releyeron candidata y metadatos existentes sin descargarlos de nuevo. El caché utilizado es `/tmp/roxy-recipe-source-cache-20260910/e89b8f5ad592b3662a661a5daf8d2afeeb6487c3869a383e453284b16b114887.json`.

Solo faltaba la revisión de receta contemporánea a la foto: se hizo **una consulta nueva** al API oficial de Wikibooks con `rvstart=2013-05-17T00:00:00Z`, `rvlimit=1`, que devolvió 2526443. El intento previo de abrir esa consulta en la herramienta web no pudo resolver la URL; no produjo evidencia. No se continuó paginación ni se consultaron más versiones. SHA-256 del wikitext histórico obtenido:

`114e8770c6b8381c8ea4d75a1c8a012663a08f4002623ad3c47947fdfb1e718a`

La respuesta completa inicialmente quedó en la salida de la consulta. Después se
conservó literalmente, sin nueva descarga, en
`reports/home_recipe_coconut_revision_2526443_2013.json`. El original está en
`query.pages["290958"].revisions[0].slots.main["*"]` (1290 caracteres); su hash
coincide con el obtenido en la consulta. SHA-256 del JSON de evidencia:
`da697fee404687868134c971a6bbff29a489ee7efd5bed7cc136428c3aa17f42`.

SHA-256 del original 2025, revalidado contra la candidata:

`76de192d78bb20fa8cf0cd23cdd95b3a62c5eecd88946b7f706669bfbd84882e`

El manifiesto de 510 sigue íntegro (`746ced612d6ca725084128ad9b4c7e9dca602171d0eb1a3621c883de02ee83c5`), con todos los bloqueos de esta candidata sin cambios. Solo se añadió este informe; no se tocaron runtime, importador, datos reales, publicaciones ni pagos.
