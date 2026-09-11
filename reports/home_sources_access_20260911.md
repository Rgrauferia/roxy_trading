# Fuentes de recetas: acceso comprobado el 11/09/2026

Alcance: consulta de documentación oficial de cada proveedor y cinco solicitudes pequeñas de recetas a MyPlate.food. Sin cuentas, claves, pagos, acuerdos, importaciones masivas ni cambios en producción. No equivale a revisión culinaria de 500 recetas.

## Nueva ruta utilizable sin cuenta: MyPlate.food

La [API oficial del proveedor](https://myplate.food/api) permite llamadas comerciales **en vivo, por solicitud**, sin clave. Publica 1.072 recetas; limita a 20 solicitudes/minuto/IP y 100 detalles/día/IP, compartidos con MCP. Devuelve 429 con Retry-After. Excluye replicar la colección a una base propia; para exportación, espejo o mayor volumen requiere acuerdo. Su [OpenAPI](https://myplate.food/api/v1/openapi.json) confirma estos límites.

Prueba HTTP real: total **1.072** sin filtro; **81** en Dessert; **20** en Beverage; **47** coincidencias de texto `pasta` (no 47 recetas clasificadas necesariamente como pasta). Búsquedas de 1–3 resultados, sin recorrer el catálogo. Detalle `2-step-chicken`: cuatro ingredientes medidos, rendimiento de cuatro porciones, preparación completa y criterio de temperatura de la fuente. No se guardó el texto del proveedor en el repositorio.

Contrato observado:

- Base: `https://myplate.food/api/v1`.
- `GET /recipes?q=...&category=...&food_group=...&limit=...&offset=...`; máximo publicado 100. Respuesta `query`, `count`, `total`, `results`, `source`, `canonical_url`.
- Cada resumen lleva slug, nombre, descripción, categoría, imagen y URLs canónica/API; algunos incluyen enlaces a traducciones.
- `GET /recipes/{slug}`: ingredientes `{text,note}`, `directions` **string completo**, rendimiento, ración, notas, contribuyente y origen. No asumir lista numerada ni inventar pasos al separar texto.
- El esquema no documenta un parámetro de idioma. La búsqueda comprobada fue inglesa; enlaces ES no demuestran que haya detalles JSON en español.

Es un proveedor independiente, **no una API oficial de USDA**. [Nutrition.gov](https://www.nutrition.gov/topics/basic-nutrition/online-tools) enlaza tres recetas suyas; esto no prueba aprobación federal de todas sus transformaciones. La [página comercial del proveedor](https://myplate.food/partners) distingue las recetas originales de su edición enriquecida: traducciones, datos completados y fotos remasterizadas con IA. Permite API comercial en vivo; reutilización comercial masiva/feeds se cotiza. No presentar las imágenes remasterizadas como fotografías originales intactas ni copiar su catálogo alegando dominio público de la base.

**Recomendación técnica:** un catálogo externo bajo demanda puede dar variedad inmediatamente, manteniendo atribución y contribuyente, texto original, límite local de llamadas, lectura transitoria y error/reintento honesto. No precargar detalles, crear un espejo, persistir recetas/fotos en Home/SW ni alimentar automáticamente planes/Compra. La cuota de 100 detalles por día de la IP de Render es pequeña para una beta: mostrar límites y negociar acceso antes de escalar. Esto habilitaría consulta a 1.072 fuentes; **no demuestra 500 recetas auditadas ni 500 listas para cocinar con Roxy**.

## TheMealDB y TheCocktailDB

[TheMealDB](https://www.themealdb.com/) sigue anunciando 793 recetas, 793 imágenes y US$10 único. [API](https://www.themealdb.com/api.php): clave pública 1 para desarrollo/educación, supporter para App Store y catálogo completo. [Términos](https://www.themealdb.com/terms_of_use.php): permiten copiar/modificar respuestas oficiales con condiciones, pero excluyen derechos de terceros no autorizados. [FAQ](https://www.themealdb.com/faq.php) pide nivel comercial de Patreon; moneda/tier y derechos deben aclararse antes de activar una clave de producción. No se necesita fabricar recetas mientras se resuelve, pero tampoco se puede usar la clave de prueba para publicar el catálogo.

[TheCocktailDB API](https://www.thecocktaildb.com/api.php) aplica el mismo límite de uso de prueba y ofrece lista completa con Premium. Sus [términos](https://www.thecocktaildb.com/terms_of_use.php) tienen las mismas reservas de terceros. Ningún acceso de producción confirmado en esta tarea.

## Fuentes reutilizables sin pago: la revisión sigue siendo necesaria

[Wikibooks Copyrights](https://en.wikibooks.org/wiki/Wikibooks:Copyrights) permite copiar/adaptar texto con CC BY-SA 4.0, atribución, licencia y señalamiento de cambios; cada medio tiene licencia propia. No exige cuenta de pago. Las 510 candidatas ya archivadas tienen un problema editorial, no una imposibilidad de acceso: no aprobarlas por cantidad.

[Public Domain Recipes](https://publicdomainrecipes.com/) muestra unas 415 entradas y enlaza su [repositorio oficial](https://github.com/ronaldl29/public-domain-recipes). Su README declara todo el contenido de dominio público; Unlicense permite uso comercial. Fotografías deben ser del plato hecho por el contribuyente según sus reglas, pero no garantiza su verificación. La muestra Pasta Arrabbiata tiene cantidades ambiguas y no indica raciones; no resuelve automáticamente el estándar de Roxy. Puede aportar futuras candidatas con hash/autor/imagen revisados, no un lote aprobado inmediato.

## Resultado

Sí existe una ruta gratuita y sin cuenta para ampliar **consulta**: MyPlate.food, bajo demanda y con límites explícitos. No hay evidencia para afirmar que 500 recetas están hoy revisadas detalle por detalle. No convertir el número anunciado por un proveedor, un índice externo o una licencia en certificación editorial.
