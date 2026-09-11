# Roxy Home · ampliación de cócteles 191

Fecha: 11 de septiembre de 2026. Estado: lote editorial local entregado para integración; no constituye un despliegue, una prueba de cocina ni una certificación de seguridad.

## Resultado verificable

Se entrega `data/home_drinks_cocktails_191.json`, un array de **9 cócteles nuevos**, con **37 líneas de ingredientes y 33 pasos en cada idioma**, por **29.724 bytes**. Cada fila conserva el JSON original íntegro y su SHA-256, la URL de procedencia fijada a una revisión y la fotografía señalada por ese mismo original. El catálogo activo no se modifica en esta subtarea.

La validación local mediante `roxy_os.home_drinks._validate` pasa para las 9 filas. Al combinar en memoria el lote con las 87 bebidas existentes, se obtienen 96 filas sin duplicados de ID, título original, título español, URL de foto ni SHA-256. La ausencia de duplicados estructurales no se presenta como evaluación culinaria.

## Procedencia y licencia

Fuente única: [Open Drinks, repositorio original](https://github.com/alfg/opendrinks/tree/f446f0e9356b9b43155d207b4f7c5214d9da91ab), revisión `f446f0e9356b9b43155d207b4f7c5214d9da91ab`. Se reconfirmó la [licencia MIT fijada a la misma revisión](https://raw.githubusercontent.com/alfg/opendrinks/f446f0e9356b9b43155d207b4f7c5214d9da91ab/LICENSE): permite reutilización y modificación, incluida la comercial, conservando el aviso de copyright y la licencia; no ofrece garantía. No se abrió cuenta, no se pagó, no se usaron claves ni APIs de prueba en producción.

Roxy ya distribuye el texto completo de licencia en `assets/open-drinks-license.txt`. Las filas incluyen contribuidor GitHub, enlace al original y crédito visible. El copyright declarado en la licencia es 2019 Alfred Gutierrez. La licencia del repositorio no demuestra por sí sola que el contribuidor posea todos los derechos de una foto de terceros; el crédito señala explícitamente que el autor individual de la imagen no está declarado. Se excluyeron imágenes con marca externa no aclarada. No se descargaron ni reempaquetaron imágenes; el lote referencia URLs originales inmutables.

## Investigación acotada y filtros

Se reutilizó la revisión anterior de 149 originales sin repetir sus consultas ni reconsiderar los descartes 190. En esta tanda se consultaron **170 originales adicionales**, en lotes de 75, 49 y 46:

- 71 contenían una fuente externa declarada o una URL en el JSON: no se adoptan sin licencia específica.
- 99 no tenían esos indicadores. Tras revisión textual y de variedad, 22 pasaron a galería visual.
- De esas 22, 12 se retuvieron por incoherencia de imagen o atribución; quedaron 10 candidatas; la revisión textual final retuvo también Coquito por no indicar expresamente la operación de licuar, resultando 9.
- Los otros 77 no avanzaron por integridad insuficiente, preparaciones/medidas ambiguas, contenido duplicativo o criterios de selección editorial. No se declararon defectuosos todos por igual ni se intentó completar sus pasos con IA.

No se añadieron recetas con huevo crudo, flameado, fermentación doméstica indefinida, dosis/suplementos para salud, preparaciones caseras sin procedimiento ni referencias comerciales externas sin derechos demostrados. Las guarniciones o el hielo presentes sólo en los pasos se conservan sin inventar cantidades. No se generan raciones, ABV, nutrientes, vida útil, instrucciones nuevas ni garantías de resultados.

## Lote entregado

| ID | Título español | Ingredientes | Pasos | Fuente |
| --- | --- | ---: | ---: | --- |
| `black-martini` | Black Martini de ginebra y sambuca negra | 3 | 3 | [Original fijado](https://github.com/alfg/opendrinks/blob/f446f0e9356b9b43155d207b4f7c5214d9da91ab/src/recipes/black-martini.json) |
| `coco-loco` | Coco Loco de ron y leche de coco | 4 | 7 | [Original fijado](https://github.com/alfg/opendrinks/blob/f446f0e9356b9b43155d207b4f7c5214d9da91ab/src/recipes/coco-loco.json) |
| `embuscade` | Embuscade normando de cerveza y Calvados | 5 | 5 | [Original fijado](https://github.com/alfg/opendrinks/blob/f446f0e9356b9b43155d207b4f7c5214d9da91ab/src/recipes/embuscade.json) |
| `mind-eraser` | Mind Eraser de café, vodka y soda | 3 | 3 | [Original fijado](https://github.com/alfg/opendrinks/blob/f446f0e9356b9b43155d207b4f7c5214d9da91ab/src/recipes/mind-eraser.json) |
| `monaco` | Monaco de cerveza, limonada y granadina | 3 | 2 | [Original fijado](https://github.com/alfg/opendrinks/blob/f446f0e9356b9b43155d207b4f7c5214d9da91ab/src/recipes/monaco.json) |
| `venus-flytrap` | Venus Flytrap de ginebra y lima makrut | 10 | 4 | [Original fijado](https://github.com/alfg/opendrinks/blob/f446f0e9356b9b43155d207b4f7c5214d9da91ab/src/recipes/venus-flytrap.json) |
| `white-bear` | White Bear de champán y vodka | 4 | 4 | [Original fijado](https://github.com/alfg/opendrinks/blob/f446f0e9356b9b43155d207b4f7c5214d9da91ab/src/recipes/white-bear.json) |
| `zorbatini` | Zorbatini de vodka y ouzo | 2 | 2 | [Original fijado](https://github.com/alfg/opendrinks/blob/f446f0e9356b9b43155d207b4f7c5214d9da91ab/src/recipes/zorbatini.json) |
| `rumchata-bourbon` | RumChata Bourbon | 3 | 3 | [Original fijado](https://github.com/alfg/opendrinks/blob/f446f0e9356b9b43155d207b4f7c5214d9da91ab/src/recipes/rumchata-bourbon.json) |

Observaciones preservadas:

- Black Martini lleva sambuca negra; no es el martini seco local con vermut.
- Coco Loco conserva el procedimiento; se traduce naturalmente el error original que repite «blender». No se inventa la cantidad de hielo.
- Embuscade conserva el orden y la adición lenta de cerveza; no se agitan líquidos carbonatados en un recipiente cerrado.
- Mind Eraser conserva su nombre, pero no reproduce en pantalla la promesa de pérdida de memoria de la descripción original.
- Monaco trata la limonada como ingrediente ya preparado; la fuente no facilita una receta base y no se fabrica una.
- Venus Flytrap sí incluye el procedimiento de infusión y la proporción de una hoja doble por 2 oz de ginebra. «Kefir/keffir lime» se traduce como lima makrut, no como kéfir lácteo; se conserva el falernum preparado. La lista dice gajo de lima y el paso dice rodaja; ambos originales quedan visibles sin una corrección inventada.
- White Bear conserva la opción de hielo y la guarnición de limón. La foto muestra dos copas; no se convierte por ello el lote en dos raciones declaradas.
- Zorbatini sí indica decorar con una aceituna verde en el procedimiento; no se inventa una cantidad para Compra.
- RumChata Bourbon conserva el amargo de mole opcional y la nuez moscada opcional indicada en los pasos.

## Revisión de imágenes y retenciones

La tarea raíz inspeccionó las cinco galerías de seis tarjetas como máximo, con fotos remotas en modo `contain`, ID, título e ingredientes. Archivos QA temporales: `/tmp/roxy-drinks-191-qa/cocktails-1.html` a `cocktails-5.html`. La revisión fue visual, no un simple HTTP 200. Las observaciones de color, guarnición y presentación son inferencias de correspondencia, no una autenticación química ni prueba de seguridad.

| ID retenido | Motivo |
| --- | --- |
| `irish-breakfast-shot` | Rótulo/marca gráfica externa sin crédito específico confirmado y volumen aparente incompatible. |
| `midnight-in-paris` | Mora, no frambuesa/limón de la lista, y hielo grande en lugar de triturado. |
| `rebujito` | Foto comercial identificada con La Corrala Bar sin permiso individual confirmado. |
| `purple-haze` | Menta y moras frescas no indicadas en ingredientes ni pasos. |
| `angevine-soup` | Rodajas de cítrico no indicadas; la receta sólo usa jugo de lima. |
| `bitter-but-good` | Rodaja de naranja en la fotografía en lugar de la piel indicada. |
| `sergeant-pepper` | Franja roja sobre la crema sin ingrediente o paso que la explique; el original sólo permite pimienta negra adicional. |
| `sgroppino` | Rodaja de limón no indicada en ingredientes ni pasos. |
| `sunshine-cocktail` | Ramita y fruta decorativa no indicadas en ingredientes ni pasos. |
| `washington-apple` | Manzana cortada ausente tanto de ingredientes como de pasos. |
| `bourbon-lemonade` | Foto de limonada/jarra con menta no indicada y sin las cerezas de la receta; apariencia genérica de otro preparado. |
| `elderflower-tini` | Rama similar a tomillo y limón en la foto, sin indicación de guarnición en ingredientes ni pasos. |

No se sustituyó ninguna foto por una genérica ni por una imagen generada para rescatar la cantidad.

## Ejemplos de otras retenciones textuales

- Coquito superó la revisión visual, pero la lectura textual final detectó que el paso 2 sólo indica añadir los ingredientes a la licuadora y el siguiente pasa a embotellar. La descripción tampoco indica licuar. Se retuvo por preparación incompleta; no se añadió esa operación por inferencia. Sus 12 ingredientes y 4 pasos no forman parte del lote final.

- Amaretto Sour y New York Sour con huevo crudo; Libertine con huevo.
- Blue Oasis incluye agitación con soda carbonatada; no se reescribe el procedimiento para publicarla.
- Galack Colada tiene una discrepancia de leche condensada entre lista y pasos; Orange Ouzo y Pink Ouzo mezclan limón/lima con otras cantidades ambiguas.
- Swinging Sultan difiere entre la cantidad de raki de ingredientes y pulverizaciones de los pasos.
- Sweet Dreams contiene una medida de 1/32 oz no aclarada; Orgasm suma un volumen elevado sin rendimiento declarado, no resuelto aquí.
- Brandy Wine Punch, Marquisette, Gluhwein y Norwegian Glogg dependen de botellas/vasos de tamaño no indicado.
- Bruce Wayne, Diana's Lips, Tom Yum y Coronarita requieren bases o infusiones no explicadas suficientemente.
- Lust for Life y Pick a Daisy atribuyen recetas a negocios/publicaciones externos sin demostrar licencia de redistribución.
- Marpha incluye fermentación/mohos durante meses sin un procedimiento adecuado para este catálogo.
- Varias recetas asignan directamente imágenes de otro preparado: Buttery Nipple/Baby Guinness, Caramel Apple Shot/Caramel Frappuccino, Chocolate Cake Shot/Nutella Milkshake, Pineapple Upside Down Shot/Pineapple Juice, Birthday Cake Shot/Oreo Frappe y Blue Kamikaze/Blue Lagoon. No se incorporaron.
- Capeta añade guaraná; no se incorporó a esta tanda de bebidas generales.
- Pompous Mexican requiere invertir una botella/vaso sellándolo con un dedo y Somaek deja caer un vaso de chupito dentro del vaso de cerveza; no se adoptaron esos procedimientos.

## Validación y límites de entrega

Comprobaciones ejecutadas sobre el archivo final:

1. JSON parseable, 9 filas válidas conforme al esquema de producción.
2. SHA-256 coincidente con cada original exacto.
3. Título, contribuidor, ingredientes originales y pasos vinculados al JSON; URL de fuente y fotografía exactamente fijadas.
4. Longitudes ES/EN iguales, sin truncamiento de ingredientes o pasos.
5. 96 IDs, títulos ES/EN, fotos y hashes distintos al unir en memoria con el catálogo activo.
6. Suite de bebidas existente: `121 passed in 1.18s` (`tests/test_roxy_home_drinks.py`). Esta ejecución comprueba la implementación compartida actual; la validación específica del lote final se realizó por separado tras retirar Coquito.
7. Ninguna petición de proveedor al cargar/validar el catálogo; sin escrituras de perfil, compras, secretos o datos domésticos.

Preflight: se trabajó en el worktree Home y se preservaron las modificaciones existentes. `tools/roxy_context_handoff.py` no existe en este worktree; no se copió desde Trading. Continuidad, versionado, fusión al catálogo activo, pruebas globales y despliegue corresponden a la tarea raíz. Las 9 recetas están preparadas para esa revisión; no se afirma publicación ni que el objetivo global de 500 recetas se haya cumplido por este lote.
