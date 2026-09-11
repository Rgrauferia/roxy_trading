# Cócteles de fuente original — ampliación 190

Fecha: 11 de septiembre de 2026. Worktree Home exclusivamente.
Estado: **38 candidatos bilingües entregados al integrador, no publicados por esta subtarea**.
Archivo: `data/home_drinks_expansion_cocktails.json` (array independiente).
No se modificaron catálogo activo, aplicación, pruebas, cuentas, compras ni mascotas.

## Resultado y límites

- 38 preparaciones adicionales, 170 líneas de ingredientes y 135 pasos tanto en original como en español.
- 125.932 bytes de JSON; cada texto fuente se conserva literalmente en `raw_source` con SHA-256.
- 38/38 filas pasan el validador `roxy_os.home_drinks._validate`.
- IDs, títulos originales/españoles, URL de imagen y hash de fuente son únicos al combinarlos con las 31 bebidas publicadas en 189.
- Se leyeron las bebidas locales en `home_recipe_fallback.py` para excluir sus 24 cócteles: no se vuelven a contar Mojito, Margarita, Daiquiri, Negroni, Manhattan, Martini, Gin tonic, Sangría, Piña colada, etc.
- Se mantienen cócteles con formulaciones diferentes, no varias traducciones de una preparación ni versiones repetidas cambiando sólo la fruta.
- No es una prueba de cocina, certificación culinaria, catálogo de 500 recetas revisadas ni garantía de ausencia de errores de la fuente.

Se comprobó continuidad Home; el script `tools/roxy_context_handoff.py --check`
falla por archivo ausente en este worktree, como ya consta en su estado. No se
copió memoria ni código de Trading. Los documentos compartidos de continuidad
son responsabilidad del integrador.

## Fuente y condiciones verificadas

Repositorio comunitario Open Drinks, revisión fijada
`f446f0e9356b9b43155d207b4f7c5214d9da91ab`.

- [README y declaración de licencia para código, recetas y contenido](https://github.com/alfg/opendrinks/tree/f446f0e9356b9b43155d207b4f7c5214d9da91ab#license).
- [Licencia MIT de la revisión](https://github.com/alfg/opendrinks/blob/f446f0e9356b9b43155d207b4f7c5214d9da91ab/LICENSE).
- [Directorio de originales](https://github.com/alfg/opendrinks/tree/f446f0e9356b9b43155d207b4f7c5214d9da91ab/src/recipes).
- [Directorio de imágenes](https://github.com/alfg/opendrinks/tree/f446f0e9356b9b43155d207b4f7c5214d9da91ab/src/assets/recipes).

No cuenta, clave ni pago necesarios para esta selección MIT. El aviso completo
de copyright/licencia ya se conserva en `assets/open-drinks-license.txt`.
El crédito identifica a quien contribuyó al repositorio, **no inventa autor
individual de la fotografía ni garantiza derechos de una eventual fuente externa**.

Se consultó un árbol de rutas y dos tandas delimitadas de 89 y 60 originales
(149 JSON; no espejo de todos los medios ni del catálogo entero). Los textos
con URL externa o `source` no vacío se retuvieron aunque el repositorio declare
licencia global. De los 149, 102 no tenían esas referencias; no se aprobó
automáticamente ese grupo.

## Curación de texto y traducción

Cada ingrediente EN se reconstruye uniendo literalmente quantity/measure/ingredient;
cada paso EN coincide con directions. Las listas ES mantienen igual longitud,
cantidades, unidades, alternativas y orden. Se cotejaron manualmente los 48
candidatos iniciales completos antes de los descartes visuales.

No se transforma oz en ml sin conocer su definición ni se asigna una ración por
defecto. Blue Lady declara dos raciones en la descripción: se conserva esa
declaración en nota, sin escalado. Irish Coffee conserva los rangos originales
y la capa de crema de 1/2–1 pulgada indicada en el procedimiento; no se inventa
un volumen de crema.

Se separan notas de hielo, guarniciones y limitaciones de los pasos originales.
No se completan recetas con IA ni se añaden ingredientes a Compra.
Las descripciones de salud/curas de resaca del proveedor no se convierten en
afirmaciones de Roxy. Esta selección es exclusivamente para adultos y no debe
mezclarse con mascotas ni presentarse como opción sin alcohol.

### Defectos materiales retenidos

- American Trilogy: applejack listado pero omitido en los pasos.
- Basil Smash: ginebra listada pero ausente del procedimiento.
- Airmail, Barracuda, El Diablo, Kir Royale, Bullfisher y otras: falta cantidad del líquido principal usado para completar.
- Blood and Sand: una copa aparece como ingrediente.
- Breakfast Martini: unidad «mli» y procedimiento escueto sin incorporar claramente la mermelada.
- Cable Car: secuencia de colados duplicada/confusa; no se reescribe.
- Dubliner y Gibson: unidades «line»/«peace» ambiguas; Gibson además casi duplica Martini.
- Gin Fizz: instrucciones de licuado contradictorias y clara sin especificación de pasteurización.
- Greyhound, The Salty Dog, Tuxedo: cantidades/proporciones dudosas sin resolver.
- Painkiller: una taza de nuez moscada y una taza de gajo de piña; se retiene, nunca se corrige silenciosamente.
- Planters Punch: «todos los ingredientes» incluye componentes añadidos otra vez después; cantidades no resueltas.
- Singapore Sling: limón/lima, agua con gas y amargo difieren entre lista y pasos.
- White Lady: clara fresca cruda, fuera de esta selección.
- Monkey Gland: 1/2 oz tanto de ginebra como de naranja; cantidad dudosa, retirada a petición del integrador sin imponer otra fórmula.
- Penicillin: contribución identificada «copilot»; no cumple el nivel de procedencia humana buscado para esta tanda.
- Carrulim: ruda y afirmaciones medicinales; sin revisión apropiada.
- Elderflower Cooler: «unidades de alcohol» como ingrediente.
- Fernet with Coke: 500 ml de líquidos y hielo en vaso declarado de 500 ml.
- Indian Summer: ingrediente «sweet and sour soup» ambiguo.
- Kenyan Dawa: cantidades e ingredientes concatenados/corruptos.
- Lynchburg Lemonade: omite jarabe y no precisa limonada.
- Nevada: vodka a gusto y leche condensada sin unidad.
- Rossini: «sparkling candy» no identifica con certeza el líquido.
- Umeshu Sparkling: cantidades sin unidad; no se convierten en medidas inventadas.
- Se excluyeron preparaciones que dependen de bases caseras sin procedimiento, variantes triviales, guarniciones flambeadas y otros textos que no alcanzaban el criterio editorial.

47 retenidos por referencias externas en el JSON:
`b-52`, `baby-guinness`, `bacardi-cocktail`, `bahama-mama`, `bay-breeze`, `between-the-sheets`, `black-velvet`, `blackthorn-cocktail`, `brandy-alexander`, `cynar-spritz`, `dark-and-stormy`, `death-in-the-afternoon`, `dorflinger`, `french-martini`, `godfather`, `grasshopper`, `hanky-panky`, `jungle-bird`, `lemon-drop`, `madras`, `mint-julep`, `old-cuban`, `rob-roy`, `scotch-soda`, `sea-breeze`, `sidecar`, `vesper`, `woo-woo`, `agua-de-valencia`, `apple-jack`, `astronaut`, `carajillo`, `cherry-bourbon-smash`, `clarito`, `colorado-bulldog`, `dolce-vita`, `dom-pedro`, `english-garden-cocktail`, `guarapita`, `hot-toddy`, `hurricane`, `jam-band`, `kansas-city-ice-water`, `lafayette`, `lillet-buck`, `macunaima`, `skeleton-key-cocktail`.

## Revisión visual coordinada

CUA de esta subtarea informó «No browser is available». Por ello **no se llamó
inspección visual a un HTTP 200**. Se creó la galería QA de referencias remotas:
`/tmp/roxy-drinks-190-qa/cocktails.html`, servida por el integrador en
`http://127.0.0.1:8787/cocktails.html`.

El integrador inspeccionó las 48 imágenes en seis capturas a 1200×950 y comunicó
nueve rechazos. Se retiraron del entregable sin sustituir su fotografía:

| ID retenido | Discordancia visual observada por el integrador |
|---|---|
| aqueduct | Imagen con tres bebidas distintas; correspondencia ambigua. |
| mudslide | Helado, crema batida y jarabe frente a líquido agitado y virutas. |
| southside | Cóctel naranja con adornos diferentes, sin la hoja de menta indicada. |
| tom-collins | Estrato rojo compatible con ingrediente no listado. |
| yale-cocktail | Violeta intenso sin componente violeta identificado en la receta. |
| boomerang | Rojo/rosa brillante no explicado por los ingredientes seleccionados. |
| calamity-jane | Presentación frutal opaca, sin concordancia con chile/fresa/albahaca. |
| desert-colada | Bebida amarilla uniforme, sin el jarabe de tuna separado de la receta. |
| jacqueline | Granada fresca, menta y lima no listadas. |

Estas son **inferencias de correspondencia visual, no análisis químicos ni
autenticación de la foto**. Las 38 entregadas pasaron el filtro visual del integrador;
no se descargaron, reempaquetaron ni generaron fotos en esta subtarea.

## Entregable

- `appletini`
- `april-rain`
- `aviation`
- `batanga`
- `bees-knees`
- `bellini`
- `bentley`
- `bikini-martini`
- `boulevardier`
- `bramble`
- `corpse-reviver-no2`
- `debonair`
- `devils-own`
- `french-75`
- `french-pearl`
- `gimlet`
- `hugo`
- `income-tax`
- `limoncello-spritz`
- `pink-gin`
- `ranch-water`
- `sazerac`
- `screwdriver`
- `stinger`
- `the-last-word`
- `vieux-carre`
- `white-russian`
- `across-the-pacific`
- `blue-lady`
- `bombeirinho`
- `cape-codder`
- `clavis-riga`
- `creole-cream`
- `green-beast`
- `irish-blues`
- `irish-coffee`
- `port-tonic`
- `two-one-two`

## Retención editorial adicional confirmada

Golden Brown pide espresso y agitado, pero no explicita su enfriamiento ni hielo.
El integrador confirmó retenerlo también. Se retiró del entregable sin inventar
un paso de enfriamiento ni alterar la fuente: 48 candidatos iniciales menos
nueve rechazos visuales y una retención editorial dan las 38 filas finales.
Una revisión visual no sustituye la revisión de seguridad ni una prueba de cocina.

Validación reproducible: cargar el array, ejecutar `_validate` sobre cada fila,
cotejar `sha256(raw_source.encode())`, comparar originales/longitudes ES y
comprobar duplicados contra `data/home_open_drinks.json`. Integrador responsable
de fusión, pruebas de runtime, límites de payload y publicación.
