# Objetivo 500: cobertura comprobable y siguiente lote editorial

Fecha: 2026-09-10. Revisión local de solo lectura; no descarga nueva, compra, aprobación automática ni modificación de candidatas/runtime. No es una certificación culinaria ni una confirmación de despliegue.

## Resultado

**Existen 510 fuentes estructuradas, no 510 recetas confirmadas para cocinar con Roxy.** El lote conserva ingredientes y pasos originales, pero la cobertura de fotografía individual y la revisión culinaria son insuficientes. Ampliar el lector de fuentes es distinto de habilitar voz, temporizadores, escalado o compras.

La revisión añade dos evidencias al informe inicial: (1) un recuento estricto de rendimiento y metadatos fotográficos, y (2) lectura íntegra de otras 15 fuentes inglesas —89 ingredientes y 86 pasos— que no tenían alertas heurísticas. Algunas contienen errores manifiestos. Por tanto, «sin alertas» no puede utilizarse como puerta de publicación.

## Medición del archivo congelado

Fuente: `data/home_recipe_candidates_20260910.json`, generado `2026-09-10T16:12:50.371433+00:00`. SHA-256: `746ced612d6ca725084128ad9b4c7e9dca602171d0eb1a3621c883de02ee83c5`.

| Comprobación reproducible | Resultado | Qué demuestra y qué no |
|---|---:|---|
| Filas / IDs / revisiones lengua-página-revisión / huellas exactas de contenido | 510 / 510 / 510 / 510 | Sin duplicado exacto en estas claves; no deduplicación semántica de platos. |
| Idioma original | 121 ES; 389 EN | No significa 510 traducciones españolas revisadas. |
| Ingredientes / pasos numerados extraídos | 3.859 / 3.275 | Estructura y orden de extracción; no suficiencia de cada preparación. |
| Texto original cuyo SHA coincide | 510 | Se conserva la revisión auditada íntegra. |
| Rendimiento no vacío | 510 | El control inicial exige algún dígito, no una porción válida. |
| Rendimiento numérico positivo simple / rango positivo simple | 399 / 54 | Comprobación sintáctica estricta; no cantidad culinariamente validada. |
| Otros rendimientos | 57 | Incluye texto como «1 a 2», rendimientos de piezas y un `0` literal: Pan de Pita, ES21371. No convertirlo automáticamente en una porción. |
| Tiempo no vacío | 497 | No garantiza tiempo total ni coherencia con los pasos. |
| Registro de licencia/atribución del texto | 510 | CC BY-SA 4.0 y atribución guardadas; la fotografía tiene derechos independientes. |
| Filas con metadatos de imagen | 94 | Las otras 416 no tienen esos metadatos en el lote congelado. |
| Alguna imagen marcada con metadato de licencia abierta | 93 | Es la bandera del importador, no una validación individual de derechos. |
| Metadatos mínimos de imagen completos | 86 | Autor no vacío, licencia, URL y revisión de descripción, SHA del archivo y dimensiones. |
| Anteriores, sin autor explícitamente «assumed / no machine-readable author» | 82 | Aún no equivale a autoría acreditada, foto exacta ni revisión visual. |
| Metadatos mínimos y URL de licencia no vacía | 65 | La ausencia de URL no invalida por sí sola dominio público; requiere revisar su declaración. |
| Sin alertas heurísticas / anteriores con metadatos mínimos de foto | 209 / 32 | Ninguno de los dos grupos queda aprobado por ello. |
| Publicables / cocinar con Roxy / añadir a Compra en este lote | 0 / 0 / 0 | Las 510 candidatas siguen bloqueadas. |

El análisis v5 ya existente detecta referencias de imagen en 112 fuentes, frente a las 94 referencias principales del lote v4: **18 referencias adicionales, no 18 fotos revisadas**. Deben reutilizarse las referencias ya descubiertas; no volver a descargar todo. Iced Tea y Hawthorn Tea comparten `File:NCI iced tea.jpg`: una imagen vinculada por dos fuentes tampoco acredita dos fotografías específicas diferentes.

Hay siete coincidencias exactas de página/revisión con el archivo local de fuentes anterior: Tomato Pasta, Oat Porridge, Risotto II, Saganaki, Pancakes, Potatoes Anna y Pohe. No contarlas otra vez como siete recetas nuevas. El estado local preparado para 185 tiene siete fuentes legibles en total, incluidas cuatro de este lote; **legible no significa guía de cocina aprobada**. Ese estado de implementación no demuestra que 185 esté publicado.

## Fallos concretos que la estructura no detecta

Se leyeron completas 15 fuentes EN elegidas entre las 32 sin alertas y con metadatos mínimos de imagen. Es una muestra dirigida, no aleatoria; no calcular una tasa de error de las 510 a partir de ella.

| Fuente y revisión | Evidencia que exige detener o aclarar la guía |
|---|---|
| Baingan Bartha I · EN7281 · 4629607 | El ingrediente empareja **1 pound con 450 kg** de berenjena. No corregir silenciosamente el original. |
| Shortbread · EN129695 · 4515326 | Empareja 380 g de harina con 1½ tazas. Requiere decidir y documentar qué formulación respalda la fuente; no elegir unidades por intuición. |
| Strawberry and Yogurt Eton Mess · EN141020 · 4587373 | Empareja 10 ml de vainilla con 1 cucharada. Hay una discrepancia de unidades que la presencia de números no resuelve. |
| Naan · EN33064 · 4512549 | Termina aplicando mantequilla que no figura entre los cinco ingredientes; la temperatura del horno queda como «lo más caliente posible». |
| Chapati · EN7277 · 4630849 | Incluye sal, pero no la incorpora explícitamente; comprobar temperatura de sartén con la mano no es una instrucción adecuada para improvisar una guía de principiantes. |
| Ambrosia Fruit Salad · EN30009 · 4630232 | Utiliza dos latas de piña sin tamaño. La variedad de envases impide normalizar la compra sin información adicional. |
| Khara Pongal · EN7289 · 4615203 | Agua medida sin incorporación explícita; agrupa olla y olla a presión sin procedimiento equivalente. No inventar parámetros de presión. |
| Buckeyes · EN107030 · 4517463 | Palillos en la lista de ingredientes; no enviarlos como alimento. Revisar además la equivalencia de una taza/320 g de mantequilla de cacahuete. |

Las otras siete lecturas íntegras nuevas fueron Rhubarb Crumble I (EN72877), Potato Curry (EN7980), Butter Tea (EN56144), Brandy Butter (EN101882), Tomato Juice (EN246028), Danwake (EN470263) y Eärgon Salsa (EN245915). Los originales, notas, advertencias y referencias siguen en el archivo congelado, sin reparaciones automáticas.

## Próximas 10 revisiones mejor delimitadas

Cola editorial propuesta **entre las fuentes ya leídas**, no clasificación culinaria de las 510 ni aprobación de estas diez. Los originales de las cuatro ES y Romanian Spread se volvieron a leer íntegramente para esta cola. «Foto con metadatos» no indica inspección de píxeles; ninguna imagen nueva se ha visto en esta revisión.

| Orden / fuente | I / pasos; rendimiento original | Siguiente comprobación concreta |
|---|---|---|
| 1. Guacamol guatemalteco · ES39203 · rev212184 | 5 / 7; 4 | Base sencilla y coherente. Falta foto. Tortillas son acompañamiento, no ingrediente medido; no importar categoría «Diabetes» como aptitud clínica. |
| 2. Quesadillas · ES20788 · rev210974 | 2 / 4; 1 | Tres tortillas y 50 g de queso; calor bajo y queso fundido explícitos. Falta foto. Los rellenos de «Trucos» no son recetas completas adicionales. |
| 3. Coctel de frutas con yogurt · ES20590 · rev210661 | 4 / 4; 1 a 2 | Conservar el rango y aclarar preparación previa del melón. Un minuto no cubre necesariamente toda la preparación. Falta foto. |
| 4. Eärgon Salsa · EN245915 · rev4518824 | 4 / 3; 4 | Base medida. Conservar advertencias de manipulación de chile; revisar afirmación de conservación 7–10 días. Foto con metadatos muestra acompañamiento, no añadir brócoli a la fórmula. |
| 5. Tomato Juice · EN246028 · rev4496294 | 4 / 3; 4 | Conservar cantidades explícitas de agua; no inferir volumen a partir de «tres latas» de pasta medida por peso. Revisar almacenamiento. Foto con metadatos vinculada al contexto Eärgon. |
| 6. Butter Tea · EN56144 · rev4522466 | 4 / 3; 2 | La fuente permite remover; revisar alternativa de licuadora con líquido caliente. No incorporar beneficios médicos del texto. Foto de la bebida no prueba la variante con leche. |
| 7. Brandy Butter · EN101882 · rev4523688 | 3 / 4; 8 | Separar variante de azúcar, alcohol y afirmación de conservación por semanas. Foto con metadatos. Es una salsa/condimento, no ocho comidas ni una receta sin alcohol. |
| 8. Potato Curry (Aloo Masala) · EN7980 · rev4615205 | 9 / 7; 4–6 | Ingrediente exige patata previamente cocida parcialmente; falta ese prerrequisito detallado. Foto con metadatos pendiente de correspondencia visual. |
| 9. Romanian Roasted Eggplant Spread II · EN469311 · rev4505504 | 5 / 5; 15 | Aclarar si 1–1½ lb corresponde al total o a cada berenjena; 15 minutos no cubren necesariamente asado y enfriado. Mayonesa opcional no hereda etiqueta vegana automáticamente. |
| 10. Salsa alioli fácil · ES9305 · rev426933 | 4 / 6; 4 | Base usa mayonesa preparada. La sugerencia de mayonesa casera no incluye receta propia. Falta foto; no fabricar cantidades para «ajustar textura». |

Esta cola prioriza revisiones acotadas, por lo que contiene bebidas, salsas y acompañamientos. **No satisface por sí sola la variedad de desayunos y platos principales pedida por Roberto.** No inflar el número contando raciones, traducciones o variaciones no desarrolladas.

## Bloqueo técnico independiente del contenido

Verificado en `roxy_os/home_open_recipes.py`, funciones `_catalog`, `_translations` y `open_recipe_catalog`:

- Catálogo: máximo **200 filas y 1.000.000 bytes**. Superar cualquiera devuelve catálogo vacío; no trunca solo el exceso.
- Traducciones: máximo **200 filas y 250.000 bytes**. Superar cualquiera devuelve traducciones vacías.
- Respuesta de catálogo: máximo **24 resultados**, sin cursor ni desplazamiento. Aunque 500 filas fueran aprobadas editorialmente, el recorrido completo necesita paginación; buscar por texto no sustituye una navegación de catálogo completa.

Por tanto, **ingestar 500 filas en el archivo actual rompería su admisión**. La siguiente entrega debe dimensionar almacenamiento y límites, paginar las tarjetas y cargar el detalle al abrirlo, con pruebas de integridad, búsqueda, cambio de idioma, límites de respuesta y rendimiento móvil. No aumentar límites a ciegas ni enviar el original íntegro al navegador. Este informe no cambia esos límites.

## Ruta masiva factible, sin inventar

1. Mantener el archivo congelado como evidencia. Ejecutar validaciones y reextracción v5 en memoria, reutilizando originales/hashes/notas/referencias; resultados editoriales en un registro separado, por revisión. Ningún marcador de estructura ni de ausencia de alertas activa publicación.
2. Trabajar lotes pequeños con una ficha uniforme: ingredientes usados, unidades/rangos, preparación previa, utensilios, tamaño del recipiente cuando importa, orden, señales de cocción, tiempos, rendimiento, notas/variantes, alérgenos y fuente. Ante una laguna sustancial, conservar como fuente para leer o retener; no completarla con texto probable.
3. Tramitar las fotos como otro requisito: página/revisión/archivo exacto, autoría/licencia, inspección visual y alcance de la leyenda. Los 82 registros con metadatos más completos son una cola de revisión, no un catálogo fotográfico aprobado. Una foto genérica o generada no resuelve la petición de fotografía específica de la receta.
4. Para llegar a 500 con fotos y pasos amplios, hace falta una fuente editorial adicional con derechos suficientes o revisión/producción propia documentada. Reutilizar la investigación de proveedores existente, verificar licencia y acceso antes de activar llamadas o pagar, y evaluar una muestra representativa de platos principales, desayunos y distintas cocinas. Tener API o una clave no certifica cada receta ni su fotografía.
5. En paralelo, resolver el bloqueo de capacidad y navegación anterior antes de importar lotes grandes en producción. No confundir los 510 documentos de auditoría, deliberadamente fuera del runtime, con el formato de fichas públicas.
6. Tras revisión editorial y de medios, validar traducción y experiencia de Roxy por receta: números y unidades leídos correctamente, notas no mezcladas con pasos, temporizadores no inventados, compras confirmadas y cantidades sin inferencias. Mantener métricas separadas: candidata, fuente legible, foto revisada, guía culinaria aprobada y guía de voz probada.

No se puede justificar hoy «500 recetas confirmadas y enseñadas sin errores». Tampoco existe base en estos datos para prometer terminar las 500 en un día. Lo verificable es el inventario y esta cola concreta, sin ampliar permisos ni presentar planes como entregas.

## Reproducción y fuentes locales

Los recuentos se calcularon con Node, lectura de JSON y `crypto.createHash('sha256')`, sin red. Rendimiento simple: `^\d+(?:\.\d+)?$`, valor positivo. Rango: dos números positivos separados por guion/en dash/em dash y límite superior no menor al inferior. El grupo de otros rendimientos es el complemento; no está etiquetado automáticamente como erróneo.

Metadatos mínimos: `open_license_metadata_present === true`; autor, licencia, URL de descripción y SHA no vacíos; revisión y dimensiones positivas. Para el recuento 82 se excluyen autores con `no machine`, `assum`, `unknown`, `unidentified`, `anonymous`, `not provided` o `not known`. Es una regla de auditoría de campos, no resolución legal. El SHA del archivo congelado se volvió a comprobar y no cambió.

Evidencia y contexto reutilizados:

- `tools/roxy_home_recipe_import_wikibooks.py`, especialmente `measured`, `editorial_flags`, `candidate` y `audit_rows`.
- `reports/home_recipe_500_source_audit_20260910.md`.
- `reports/home_recipe_es20_editorial_triage_20260910.md`.
- `reports/home_recipe_10en_editorial_20260910.md`.
- `reports/home_recipe_14_publication_audit_20260910.md`.
- `reports/home_recipe_source_context_v5_20260910.md`.
- `reports/home_recipe_provider_options_20260910.md` (investigación fechada, no cuenta o licencia activa).
- Cada fila conserva `source_revision_url`, `source_history_url`, `rights` y `original_wikitext`; los IDs y revisiones de este informe resuelven exactamente esas fuentes sin nueva descarga.
