# Roxy Home · selección educativa de ejercicios

Comprobado el 8 de septiembre de 2026. La selección incorpora **8 fichas, 14 párrafos originales y 16 ilustraciones**. Siete fichas conservan el español publicado por wger; una conserva el inglés. **Cero fotografías, videos, plantillas, prescripciones o aprobaciones clínicas.** No es el catálogo completo de wger y no demuestra cobertura para todas las personas, objetivos o equipos.

## Resultado verificable

`roxy_os/fitness/catalog.py` ofrece `fitness_catalog()` y `fitness_catalog_entry(id)`. `data/home_fitness_catalog.json` conserva los datos seleccionados: ID y UUID de ejercicio/traducción/medio, autor e historial de autores, licencia y URL por recurso, fecha de consulta, actualización de la fuente y SHA-256 de las instrucciones originales, del texto normalizado y de cada imagen inspeccionada. El archivo JSON está afectado por el ignore existente de `data/`; debe incluirse expresamente en el commit de integración.

| ID wger | Título original | Idioma | Traducción ID | Imágenes ID | Licencia del texto |
| --- | --- | --- | --- | --- | --- |
| 91 | Curl con barra | es | 2617 | 27, 28 | CC BY-SA 4.0 |
| 92 | Curl de bíceps con mancuerna | es | 2051 | 23, 24 | CC BY-SA 3.0 |
| 95 | Curl de Bíceps en Polea | es | 2672 | 19, 20 | CC BY-SA 4.0 |
| 135 | Butterfly | en | 98 | 111, 112 | CC BY-SA 3.0 |
| 272 | Curl Martillo | es | 2735 | 47, 48 | CC BY-SA 4.0 |
| 365 | Curl de piernas (tumbado) | es | 4317 | 179, 180 | CC BY-SA 4.0 |
| 366 | Curl femoral sentado | es | 2637 | 181, 182 | CC BY-SA 4.0 |
| 572 | Encogimientos de hombros con mancuernas | es | 4361 | 39, 40 | CC BY-SA 4.0 |

Los 16 medios son ilustraciones Everkinetic declaradas individualmente CC BY-SA 3.0 por la API. Se inspeccionaron una por una: curl con barra recta, curl de mancuernas con giro, curl de polea baja, butterfly con antebrazos apoyados, martillo con agarre neutro, curl de piernas tumbado, curl de piernas sentado y encogimiento con mancuernas. Se conserva cada pareja de posiciones; no se convierte una imagen fija en video ni se afirma evaluar técnica personal. PNG originales remotos, sin edición, recorte ni rehosting en los activos del producto; dibujados sobre fondo blanco en la interfaz.

La versión española de Butterfly solo describía la posición inicial: se eligió el texto inglés completo sin traducirlo ni completarlo con IA. Las listas de equipo de wger están vacías en algunas fichas; no se rellenan ni se interpretan como ejercicio sin equipo. Los nombres de categoría/equipo siguen en su inglés original. La prosa se conserva íntegra, incluyendo pausas descritas por su autor; no se extrae una dosis personal ni se crean series, repeticiones, carga o calendario.

## Procedencia y derechos

Se consultaron únicamente GET anónimos a la API pública. La [documentación oficial](https://wger.readthedocs.io/en/latest/api/api.html) permite leer el catálogo público sin autenticar; las cuentas y datos de usuario son otra superficie. No se crearon cuentas ni se aceptaron contratos comerciales o pagos. No se enviaron datos personales. No hay llamadas al proveedor al abrir el catálogo: el servidor devuelve una selección fija y validada, y el navegador solicita los PNG públicos al host permitido.

Las respuestas originales de los ocho [endpoints `exerciseinfo`](https://wger.de/api/v2/exerciseinfo/91/) respondieron correctamente y se contrastaron por ID con la selección final. La [lista de licencias](https://wger.de/api/v2/license/?limit=20) diferencia licencias de recursos; no se deduce permiso de una etiqueta global. Los textos de las traducciones y los metadatos base pueden tener licencias distintas y se mantienen separados. El texto fuente se convierte a párrafos planos retirando HTML y normalizando espacios, sin traducción ni palabras añadidas.

[CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) y [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) exigen atribución, referencia a la licencia e indicación de cambios, con compartir igual cuando corresponda. Cada ficha entrega estas atribuciones al consumidor de la API. La normalización/selección de datos de Roxy se distribuye bajo CC BY-SA 4.0; las licencias originales de cada recurso siguen identificadas. Esta declaración corresponde al catálogo de datos y no cambia la licencia del código de la aplicación. No se afirma respaldo de wger/Everkinetic ni revisión médica.

El [repositorio original de Everkinetic](https://github.com/everkinetic/data/blob/main/LICENSE.md) publica CC BY-SA 4.0; se mantiene **CC BY-SA 3.0 de cada PNG distribuido por wger**, sin sustituirla por la licencia del repositorio actual. El [registro histórico de Butterfly en Commons](https://commons.wikimedia.org/wiki/File:Butterfly_machine_2.svg) también identifica a Everkinetic y CC BY-SA 3.0. La evidencia concreta de los 16 PNG son sus respectivas respuestas `exerciseimage`, no un supuesto permiso universal para todos los medios de wger.

El patrón de página humana `/en/exercise/{id}/view` está confirmado en el [código oficial de rutas](https://github.com/wger-project/wger/blob/master/wger/exercises/urls.py). En la consulta directa la página humana respondió con un control antibot; **no se contabiliza ese HTTP 200 como revisión visual de la página**. El origen efectivamente consultado para texto y derechos es la API, que se entrega junto al enlace humano. No se intentó eludir el control antibot.

## Selección y exclusiones

Se inspeccionaron metadatos de dos páginas de 100 ejercicios y un índice de 374 imágenes, sin descargar el conjunto de medios. Solo se descargaron a un directorio temporal las imágenes candidatas para verificación visual; ningún video. Los conteos del proveedor variaron durante la investigación y no son cobertura del producto.

La clasificación `style=4` del proveedor no bastó: varias supuestas fotos eran dibujos. Se excluyeron medios con marcas comerciales ajenas, origen ambiguo o otra variante. Ejemplos concretos:

- Ejercicio 81, medio 410: ilustración de remo unilateral apoyado, frente a texto español de remo inclinado bilateral.
- Ejercicio 184, medio 332: foto con mancuernas frente a texto de peso muerto con barra.
- Ejercicio 203: español sobre disco/variante por encima de la cabeza frente a foto de goblet con mancuerna y talones elevados.
- Ejercicio 94, medio 379: marca comercial ajena visible; no se trató el nombre del cargador como autor original confirmado.
- Ejercicio 50, medio 359: foto tumbado en banco frente a texto de extensión por encima de la cabeza.
- Las traducciones españolas incompletas de 135 y 348 no se completaron; 135 tiene el original inglés seleccionado y 348 quedó fuera.

Las exclusiones no se publican como técnicas alternativas. Tampoco se reemplazan con imágenes generadas, una foto genérica de gimnasio o una ficha parecida.

## Validación y límites

**50 pruebas** de catálogo aprobadas; comparación real con las ocho respuestas oficiales y los 16 hashes de medios aprobada; `git diff --check` correcto. Pruebas: aislamiento de copias, ausencia/corrupción de archivo, atribución obligatoria, licencia desconocida o ID de licencia incorrecto, coincidencia de IDs, controles de host/ruta/esquema, URL con credenciales/control/query/fragmento, bloqueo de SVG/data/javascript, texto modificado, HTML activo, campos extra del proveedor y prohibición de usar estas fichas como catálogo aprobado del motor de duración.

El contenido es `education_only_professional_review_pending`, `clinical_approval=false`, `can_activate_training=false`. El lector no aprueba a una persona ni sus contraindicaciones. La respuesta pública elimina campos extra del proveedor y conserva solo el contrato explícito; las instrucciones son texto plano. Falta la revisión profesional para activar entrenamientos, y este bloque no la crea.

Las imágenes se verificaron al incorporar la selección y sus hashes quedan registrados. Como se sirven desde wger, su disponibilidad y sus bytes futuros dependen del proveedor; no se afirma fijación inmutable de un PNG remoto. La interfaz debe mostrar un estado de imagen no disponible ante fallo y mantener atribución y enlace al original.

Evidencia temporal de consulta e inspección: `/tmp/roxy-fitness-catalog.4xMlC9`. Los archivos duraderos de este bloque son el JSON, módulo, pruebas y este informe. La integración de rutas, UI, continuidad y despliegue corresponde a la tarea principal; este informe no afirma publicación. Se preservó el prototipo existente y no se modificó Trading/Crypto.
