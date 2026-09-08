# Roxy Home — fuentes reales de recetas, 2026-09-08

## Fotografías añadidas tras el primer informe

Se incorporaron las fotos que las revisiones de tortilla, Potatoes Anna y Saganaki
enlazan expresamente. Metadatos de licencia y autor consultados en Commons:
LLuisa Nunez/Hohum (CC BY-SA 2.5), Hayford Peirce (CC BY-SA 3.0) y Tammy Green
(CC BY-SA 2.0). La tarea principal abrió y examinó las tres imágenes: tortilla
de patata, patatas en capas y queso frito corresponden visualmente a sus platos.
Esto no acredita el tamaño de la ración ni una prueba en cocina. La imagen de
Potatoes Anna es pequeña (217×294); no se genera una sustituta de mayor calidad.
Daigakuimo, Indian Chai y Risotto II no tienen foto enlazada por la revisión usada.
Siguen con aviso explícito, sin imágenes genéricas. Las fotos externas sólo se
piden al abrir la ficha; autor, licencia, página individual y cambios originales
se muestran al lado de la imagen y se incluyen en la exportación TXT.

## Resultado verificable

Se creó `data/home_open_recipes.json` con seis recetas de Wikibooks: 31 líneas
de ingredientes, 36 pasos originales y raciones expresas. Son textos en inglés
de revisiones fijas obtenidas por la API oficial; no se añadieron pasos,
traducciones, tiempos, ingredientes ni porciones. No se contrataron servicios,
se crearon cuentas, se enviaron mensajes, se cambiaron claves ni se modificó
producción. Este informe no acredita el despliegue del código que integre el JSON.

La opción directamente reutilizable y gratuita comprobada es Wikibooks bajo
CC BY-SA 4.0, con atribución y conservación de la licencia. La selección es
pequeña y curada: la licencia abierta no garantiza que cualquier ficha esté
completa, libre de errores culinarios o apta para una alergia.

## Selección conservada

| ID estable | Receta original | Etiqueta culinaria de la fuente | Raciones | Ingredientes | Pasos | Revisión |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| wikibooks-385022 | Spanish Potato Omelette | Spanish | 4 | 5 | 8 | 4500599 |
| wikibooks-150880 | Potatoes Anna | French | 4 | 2 | 5 | 4502892 |
| wikibooks-128617 | Daigakuimo (Japanese Candied Sweet Potato) | Japanese | 4 | 6 | 5 | 4494175 |
| wikibooks-219286 | Pan-Fried White Brined Cheese (Saganaki) | Greek | 1 | 5 | 6 | 4613881 |
| wikibooks-167989 | Indian Chai | Indian, según el título | 1 | 5 | 3 | 4522385 |
| wikibooks-108144 | Risotto II | Italian | 6 | 8 | 9 | 4525538 |

Los campos `source_url`, `source_revision_url`, `source_history_url`, `revid`,
`source_modified_at`, `original_wikitext` y `source_sha256` permiten auditar cada
texto. Las etiquetas proceden de categorías, introducción o título de la fuente;
no representan una afirmación de origen nacional exclusivo. Saganaki conserva
la referencia de su fuente a versiones griegas y grecoamericanas. La tortilla
añade la atribución a su [página española de origen](https://es.wikibooks.org/wiki/Artes_culinarias/Recetas/Tortilla_de_patatas).

Las medidas cualitativas originales (por ejemplo, al gusto, una rodaja o aceite
para freír) se conservan; no se transformaron en gramos inventados. Daigakuimo
conserva la equivalencia aproximada original de una libra/medio kilo, sin
convertirla en una cantidad calculada. Las recetas sin tiempo total no reciben
un tiempo ficticio. La lista de compra o escalado requiere manejar esas medidas
con honestidad y no implica compra automática.

No se importaron etiquetas de dieta. Un caso concreto descartado es la categoría
de Daigakuimo que afirma ausencia de gluten pese a que la receta incluye salsa
de soja. Los alérgenos deben derivarse de los ingredientes y productos reales.
No se realizó una prueba en cocina ni certificación médica.

Se excluyeron de la selección Shakshuka I, Spanish Omelet y Guacamole I por
ausencia de raciones. Greek Salad carece de cantidades. Simple Spaghetti tiene
notas científicas incorrectas y equivalencias de unidades ambiguas. Los ejemplos
no se arreglaron completándolos con IA. Son motivos de selección, no cambios en
Wikibooks.

## Licencia y atribución de Wikibooks

La [política oficial de copyright](https://en.wikibooks.org/wiki/Wikibooks:Copyrights)
declara CC BY-SA 4.0 para la mayoría del texto. Los
[términos de Wikimedia, sección 7](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use/en)
permiten uso comercial conforme a esa licencia y reconocen el enlace a la página
como atribución a sus colaboradores. Las adaptaciones y traducciones distribuidas
deben indicar los cambios, enlazar la licencia y mantener ShareAlike. Hay que
preservar atribuciones adicionales de material importado; las fotos tienen
licencias independientes. Las páginas de discusión de las seis seleccionadas
no existían en la consulta API, y el texto original no contenía avisos de licencia
especial. El JSON incorpora atribución y el aviso de retirar únicamente marcado
wiki para visualización. Debe mostrarse esa información junto a la receta y en
exportaciones/copias; no basta con conservarla invisiblemente en servidor.

[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) permite compartir
y adaptar con atribución, enlace a la licencia y cambios indicados. La licencia
del contenido reutilizado no equivale por sí sola a licenciar todo el código de
Roxy Home bajo CC BY-SA; mantener separados los textos y sus avisos facilita una
distribución clara.

## Endpoints verificados y formato

Base pública sin clave: `https://en.wikibooks.org/w/api.php`.

- Consulta fijada por revisión: `action=query&revids=4500599|4502892|4494175|4613881|4522385|4525538&prop=revisions&rvprop=ids|content|timestamp&rvslots=main&format=json&formatversion=2`.
  Devuelve `query.pages[]`, `pageid`, `title`, `revisions[].revid`, `timestamp` y
  `slots.main.content` con el wikitext original.
- Consulta de ficha: `action=parse&page=Cookbook:Spanish_Omelet&prop=wikitext|revid|categories|images|langlinks&redirects=1&format=json&formatversion=2`.
  Se comprobó HTTP 200, JSON de 4.702 bytes, página 23021 y revisión 4517807.
  `parse` contiene categorías (incluida ausencia de raciones), imágenes y enlaces
  de otros idiomas. Esa ficha se rechazó; es distinta a Spanish Potato Omelette.
- Descubrimiento documentado: `action=query&list=categorymembers&cmtitle=Category:Italian_recipes&cmlimit=20&format=json&formatversion=2`.
  No ejecutar un recolector sin límites ni publicar automáticamente resultados.

Documentación: [revisiones](https://www.mediawiki.org/wiki/API:Revisions),
[parse](https://www.mediawiki.org/wiki/API:Parsing_wikitext) y
[categorías](https://www.mediawiki.org/wiki/API:Categorymembers).
La API devuelve contenido, no objetos de receta normalizados: la extracción
conserva las listas originales de ingredientes y procedimiento. Ningún HTML
externo se debe insertar sin sanitizar.

Se usó un User-Agent identificado como RoxyHomeSourceResearch/177 con el enlace
del producto. La [política de API de Wikimedia](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_API_Usage_Guidelines)
exige identidad, respeto a respuestas de limitación y licencias. Esta selección
local evita solicitudes por cada visualización; no hay nueva API externa en
producción por crear el archivo.

## Imágenes — consulta inicial, sustituida por la revisión visual de arriba

En la primera entrega, todas las fichas usaban `image_url` vacío y explicaban que no se incluyó
una foto revisada visualmente. No se sustituyeron por platos parecidos.
Se consultó la API oficial de Commons con `action=query`, `prop=imageinfo` e
`iiprop=url|extmetadata` ([documentación](https://www.mediawiki.org/wiki/API:Imageinfo)).
Los metadatos útiles son `imageinfo[].url`, `descriptionurl` y
`extmetadata.LicenseShortName`, `LicenseUrl`, `Artist`, `AttributionRequired`.

Comprobaciones iniciales, anteriores a activar las tres fotos descritas al inicio:

- [Saganaki.jpg](https://commons.wikimedia.org/wiki/File:Saganaki.jpg): Tammy Green,
  CC BY-SA 2.0, foto de restaurante. No confirma que se cocinó la receta concreta.
- [Pommes Anna.jpg](https://commons.wikimedia.org/wiki/File:Pommes_Anna.jpg):
  Hayford Peirce, CC BY-SA 3.0, imagen editada digitalmente según metadatos.
- [Tortilla patatas.jpg](https://commons.wikimedia.org/wiki/File:Tortilla_patatas.jpg):
  CC BY-SA 2.5; la respuesta no trae autor legible por máquina. Falta resolver la
  atribución específica antes de activar esa foto.

## TheMealDB: económico anunciado, comercial aún no acreditado

La [portada oficial](https://www.themealdb.com/) anuncia USD 10 una vez para
acceso premium de por vida. La [guía oficial](https://www.themealdb.com/docs_api_guide.php)
anuncia GBP 10 en enlaces del mismo upgrade. Su
[FAQ](https://www.themealdb.com/faq.php) todavía pide un nivel comercial de Patreon
para aplicaciones comerciales, sin publicar precio. Por eso USD 10 no se registra
como precio comercial confirmado. No se completó checkout ni se pidió una clave.

La [página de API](https://www.themealdb.com/api.php) indica que la clave privada
se envía por correo después del upgrade y permite la clave pública `1` para
desarrollo/educación. Producción/App Store requiere supporter. Las operaciones
son `search.php?s=...`, `lookup.php?i=...`, `list.php?a=list` y
`filter.php?a=...`, bajo `https://www.themealdb.com/api/json/v1/{HOME_KEY}/`.
El filtro ofrece resúmenes; el detalle debe obtener instrucciones e ingredientes.
No se utilizó una clave de prueba para habilitar producción.

Los [términos oficiales](https://www.themealdb.com/terms_of_use.php), actualizados
el 1 de julio de 2025, permiten copiar/modificar respuestas de endpoints oficiales
y usar arte propio con atribución. Prohíben reutilizar contenido de terceros sin
su permiso o base legal. Por tanto, pagar acceso no licencia automáticamente todas
las recetas o fotos de otros editores. El marcador de Creative Commons no sustituye
la procedencia y condiciones de la imagen. No se alteraron los gates existentes.
Confirmar tarifa/cobertura comercial y derechos concretos sigue siendo necesario
para activar este proveedor; Wikibooks sí permite avanzar sin compra.

## Otras alternativas

| Fuente | Precio oficial observado | Ajuste al objetivo |
| --- | --- | --- |
| Wikibooks | Sin cuota ni clave para estas consultas públicas | Mejor opción inmediata para contenido local reutilizable con CC BY-SA y curación. |
| Spoonacular | Gratis 50 puntos/día; Cook USD 29/mes más excedentes | Instrucciones cuando existen, pero sin almacenamiento persistente de ingredientes/pasos. |
| Edamam | USD 9/99 al mes para recetas web; USD 399 al mes para contenido propio | Los planes web no entregan instrucciones; el propio sí, con restricciones de reutilización/caché. |
| USDA/Nutrition.gov | Acceso público | Selección manual útil; confirmar autoría federal y derechos de cada foto/colaborador. |

Los [planes de Spoonacular](https://spoonacular.com/food-api/pricing) confirman la
cuota gratuita y USD 29/mes. Sus [términos](https://spoonacular.com/food-api/terms)
prohíben guardar pasos, ingredientes y versiones derivadas; el caché de hasta una
hora exige permiso escrito previo. ID, título y URL de imagen tienen excepción.
No sirve para poblar indefinidamente el catálogo guardado actual.

[Edamam](https://developer.edamam.com/edamam-recipe-api) distingue recetas web de
terceros sin instrucciones y contenido propio con instrucciones. El plan de
contenido propio mostrado es USD 399/mes. No autoriza crear una copia de su base;
las peticiones deben responder a un usuario y el caché depende del plan. No se
contrató ni se usó una prueba.

[Nutrition.gov](https://www.nutrition.gov/recipes) reúne fuentes federales y
Cooperative Extension, que no deben confundirse. La
[política USDA](https://www.usda.gov/about-usda/policies-and-links) considera la
mayoría de su información dominio público, pide créditos y señala materiales de
terceros que necesitan permiso. MyPlate Kitchen oficial devolvió 403 en esta
sesión: no se pudo verificar allí una API o descarga oficial vigente. Un espejo
privado no prueba la titularidad federal ni licencia automáticamente sus mejoras.
El [recetario bilingüe NHLBI de 2024](https://www.nhlbi.nih.gov/resources/delicious-heart-healthy-latino-recipes-book-platillos-latinos-sabrosos-y-saludables)
es otra fuente para una futura selección por página y derechos; no se descargó
un libro entero en este trabajo.

## Continuidad y comprobaciones

Se leyó completo `ROXY_CURRENT_STATE.md`, se consultó `data/roxy_continuity.json`
y `git status --short` (sólo `?? prototypes/` al inicio). Se ejecutó el check de
handoff con el intérprete autorizado; falló porque falta
`tools/roxy_context_handoff.py` en Home, tal como ya documenta continuidad. No se
copiaron archivos ni secretos de Trading.

La implementación y continuidad del bloque 177 las coordina la tarea principal.
Este subtrabajo sólo crea el JSON y este informe. Debe verificarse la integración
y UI antes de anunciar recetas desplegadas o cocinar/guardar/comprar disponibles.

Validación local aprobada: JSON válido, seis revisiones/IDs únicos, SHA256 de cada
wikitext conservado, raciones coincidentes con el resumen original, igualdad
exacta de las 31 líneas de ingredientes y 36 pasos tras retirar marcado wiki,
licencias/atribuciones presentes y ninguna foto o etiqueta dietaria activada.
