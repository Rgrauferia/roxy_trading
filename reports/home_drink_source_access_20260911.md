# Bebidas: fuente comercial reutilizable — 11/09/2026

Alcance inicial: investigación de acceso y muestreo. Ampliado por instrucción
del agente integrador a una selección bilingüe local de 31 bebidas tras retirar
dos fotografías incompatibles detectadas en QA visual. **No
publicado por este agente**; interfaz/despliegue y QA visual pertenecen al integrador.
Continuidad Home leída; `roxy_context_handoff.py --check` intentado y ausente en
este worktree. No se ha usado el checkout Trading salvo su intérprete habitual.

## Ruta utilizable

**Open Drinks (alfg/opendrinks)** ofrece una base de bebidas contribuida por su
comunidad. El README declara expresamente que **código, recetas y contenido**
están bajo MIT, no sólo el programa. MIT permite uso comercial, modificación y
redistribución incluyendo el aviso completo de copyright/licencia. No requiere
clave, cuenta ni suscripción. Esta declaración permite preparar una selección
local atribuida; no demuestra que cada contribuidor tenga derechos sobre una
foto externa ni que toda receta sea correcta.

Fuentes primarias consultadas:

- [Repositorio y declaración de licencia](https://github.com/alfg/opendrinks#license).
- [Licencia MIT](https://raw.githubusercontent.com/alfg/opendrinks/f446f0e9356b9b43155d207b4f7c5214d9da91ab/LICENSE), copyright 2019 Alfred Gutierrez.
- [Guía de contribución](https://raw.githubusercontent.com/alfg/opendrinks/f446f0e9356b9b43155d207b4f7c5214d9da91ab/CONTRIBUTING.md).
- [Árbol Git consultado](https://api.github.com/repos/alfg/opendrinks/git/trees/master?recursive=1).

Revisión fijada: `f446f0e9356b9b43155d207b4f7c5214d9da91ab`.
El árbol no está truncado: **756 JSON** en `src/recipes/`, **730 entradas** de
activos en `src/assets/recipes/`. Son conteos de archivos, NO recetas aprobadas,
fotos únicas ni bebidas distintas deduplicadas con las existentes de Roxy.

Hay nombres de café frío/vietnamita/coco, espresso, latte, jugos, limonadas,
batidos, tés, chocolate, bebidas vegetales, mocktails y cócteles. Más de cien
nombres incluyen coffee/juice/smoothie/tea/milkshake/lemonade y similares; ello
no clasifica su contenido alcohólico ni valida los ingredientes.

## Contrato y medios

Cada JSON usa `name`, `description`, `github`, `ingredients` (cantidad, medida,
ingrediente), `directions` (lista ordenada), `image`, `source` opcional y
`keywords`. No hay un campo estándar de raciones. **No inventar rendimiento 1**
ni escalar automáticamente; mostrar las cantidades del lote original cuando
sean completas. El contribuidor GitHub se puede conservar como atribución de
contribución, no necesariamente como autor verificado de la fotografía.

La guía pide JPG de la bebida con nombre correspondiente, preferentemente
600×400 y máximo 200 KB. No incluye metadatos por foto de autor/licencia.
Algunos JSON enlazan páginas comerciales de terceros; la licencia global del
repositorio no demuestra derechos sobre esos terceros. Retener esos registros
hasta verificar el original y los derechos correspondientes. Buscar fuentes
tanto en `source` como en texto de direcciones/descripciones, no sólo el campo.
Una foto debe inspeccionarse y vincularse a la variante concreta antes de
presentarla como exacta; no se descargaron ni inspeccionaron imágenes en esta
investigación.

## Muestreo real y prioridades

Se leyeron 35 JSON completos (3 con web y 32 por HTTP de sólo lectura). No se
descargó ni replicó todo el catálogo. La muestra confirma que una aprobación
masiva sería incorrecta.

Primeras candidatas sin `source` externo, con cantidades principales y pasos:

| Archivo | Interés / comprobación pendiente |
|---|---|
| `vietnamese-coffee.json` | Café, 4 ingredientes y 4 pasos; agua/calor y foto deben comprobarse. |
| `coconut-coffee.json` | Café de coco, cantidades de leche/crema y opciones explícitas; shot no equivale a un ml inventado. |
| `iced-matcha-latte.json` | Matcha frío con crema, 5 ingredientes y 8 pasos; título no implica leche no listada. |
| `tropical-smoothie.json` | Batido, 9 ingredientes, mezcla 30 segundos y servir. |
| `negroni.json` | 3 partes de 1 oz, hielo y piel de naranja; no asumir número de porciones. |
| `manhattan.json` | 50/10/10 ml + bitters, mezcla 20 segundos; variante de bourbon y dos vermuts. |
| `virgin-mojito.json` | Sin alcohol, cantidad de agua especificada; campos irregularmente repartidos requieren conservación literal. |
| `afterglow.json` | Mezcla de 8/8/2 oz, hielo/agitado; volumen grande sin rendimiento explícito. |

Son **candidatas**, no aprobaciones editoriales, traducciones, derechos de foto
confirmados ni ensayos de cocina. Los enlaces exactos son
`https://raw.githubusercontent.com/alfg/opendrinks/<revision>/src/recipes/<archivo>`.

Ejemplos que se deben retener, no completar con IA:

- `banana-smoothie`: huevo crudo en batidora y campos de ingredientes mal
  repartidos. No activar como guía segura por conservar el texto original.
- `lemonade`: no declara cantidades de los ingredientes principales.
- `cold-coffee`: mug/scoop ambiguos; agua usada sólo en pasos; vainilla ambigua.
- `iced-coffee-frappe`: cantidad de café ausente.
- `mango-juice`: lista y pasos divergen (agua duplicada, naranja/jengibre nuevos).
- `orange-carrot-smoothie`: hielo listado sin paso de uso; líquido opcional no
  listado. Revisar, no insertar instrucciones por inferencia.
- `sugarcane-juice`: medida de limón cambia y sal aparece sólo en preparación.
- `yogurt-fruit-shake`: una licuadora está incluida como ingrediente y un
  contenedor de yogur no tiene tamaño.
- `dalgona-coffee`: coffee powder no especifica instantáneo; no corregir en silencio.
- `shirley-temple`: ½ taza de cerezas de guarnición vs una cereza en el paso.
- `mojito`: 6 oz de ron sin rendimiento; no asumir que es una copa.

Fuentes comerciales explícitas observadas: `oatmilk-shaken-espresso` (Starbucks),
`strawberry-watermelon-juice` (Spice Up The Curry), `almond-banana-smoothie`
(Tarla Dalal), `peanut-butter-banana-smoothie` (Allrecipes),
`hibiscus-mint-tea` (Half Baked Harvest). `mango-peach-smoothie` enlaza Best of
This Life en una dirección aunque no tenga `source`; no basta filtrarlo por campo.

## Implementación recomendada para este bloque

Seleccionar una tanda variada pequeña/mediana con revisión de cantidades,
pasos, variante, foto y alcohol; conservar JSON originales fijados y hashes,
atribución GitHub, aviso MIT y notas fuera de los pasos. No reutilizar lenguaje
de salud de descripciones (detox/immune/cold relief) como afirmación de Roxy.
Clasificación con/sin alcohol se verifica por ingredientes; no basarse sólo en
keywords. Café, té, kombucha, extractos y bitters necesitan reglas de categoría
claras; no prometer cero alcohol sin fundamento. No mezclar con mascotas.

La fuente elimina el bloqueo de cuenta/pago y aporta variedad real; **no elimina
la revisión editorial**. El total de archivos no debe mostrarse como incremento
de recetas listas. TheCocktailDB key 1 no es la alternativa de producción sin
contrato, y en este bloque no se usó.

## Selección local entregada al integrador

`data/home_open_drinks.json`: **31 preparaciones nuevas**, 141 líneas de
ingredientes y 117 pasos tanto en original como en traducción española.
Ocho cafés/tés/chocolate, cuatro batidos, cinco mezclas sin licores, dos jugos y
doce cócteles. Se compararon los nombres y formulaciones con las 34 bebidas
locales comunicadas por el integrador y los 20 nombres de MyPlate. No se
recuentan Negroni, Manhattan, Mojito, Cuba Libre, Piña Colada, limonada básica,
batido de banana ni sus traducciones. No es una deduplicación global de todos
los ingredientes de MyPlate; no se consumieron sus fichas para esta selección.

La selección usa únicamente JSON sin URL externa en ningún campo. Se leyeron
completos los ingredientes y las instrucciones elegidos y se cotejó la
traducción conservando cantidades, unidades, alternativas y orden. No se
reproduce la descripción del proveedor como aval de salud. `raw_source`
conserva los bytes de texto originales, comprobados con SHA-256; las líneas EN
son unión literal de los tres campos de cada ingrediente y los pasos EN no
cambian. La licencia MIT completa se conserva en `assets/open-drinks-license.txt`.

Todos los registros usan revisión Git fija, autor de contribución y crédito
honesto: **no se inventa autor individual de la foto**. El 11/09 se comprobó que
las 33 imágenes específicas respondían HTTP 200 `image/jpeg`, 13–173 KB;
sus 33 SHA-256 fueron distintos. Eso demuestra disponibilidad y ausencia de
duplicados binarios en este lote, **no una auditoría visual o garantía de
derechos de terceros**. El integrador debe revisar las fotos en la galería.
No se guardaron ni reexportaron archivos de imagen mediante esta subtarea.

Comprobación estructural inicial propia: 33 IDs únicos, todos los hashes coinciden,
listas EN idénticas al JSON original, longitudes ES/EN coincidentes y ninguna
URL de tercero en los originales. JSON inicial de 108.991 bytes antes de las
notas finales sobre hielo y guarniciones; inferior a 150 KB. Las pruebas del
adaptador son responsabilidad de la subtarea de QA.

Limitaciones visibles, no subsanadas inventando pasos o raciones:

- No hay ensayo de cocina propio, raciones confirmadas ni escalado automático.
- Hielo y guarniciones opcionales presentes sólo en pasos se explican fuera de
  la receta; no se agregan cantidades ficticias.
- Rooibos empieza con té ya preparado y enfriado. Palm Sugar Sharbat pide
  semillas de albahaca ya remojadas; no se autoriza sustituirlas por semillas
  secas. El original no aporta procedimiento de esas bases.
- Sparkling Punch se declara sin alcohol en la descripción y keywords de la
  fuente. Una nota exige elegir **sidra espumosa sin alcohol**; no se confunde
  con sidra alcohólica. No se modifica silenciosamente su lista EN.
- London Fog contiene extracto de vainilla; se indica revisar su etiqueta si
  se necesita evitar también el alcohol de extractos.
- Indonesian Avocado Milkshake tiene lista/pasos coherentes de leche y agave;
  se omite su descripción contradictoria que decía leche condensada y se
  documenta. Berry and Oat especifica linaza molida en el paso y se señala.
- Sambharam contiene lácteos; no se replica su keyword `vegan` incorrecta.
- Afterglow quedó excluido de la selección final: tras agitar el texto pasa
  a decorar sin indicar vertido/colado. Se mantiene sólo como candidato en
  el análisis anterior, no como nueva bebida entregada.

### Retenciones tras QA visual del integrador

Se retiraron del JSON de ejecución, sin sustituir sus imágenes ni alterar recetas:

- `mint-chocolate-milkshake`: foto con crema batida y trozos de chocolate en
  tarro; la receta pide borde con chocolate fundido y hojas de menta, sin esa
  crema batida. No se añade crema al texto para hacer coincidir la foto.
- `sweet-lassi`: foto con azafrán/guarnición especiada que no está en la receta.

El lote pasó de 33 a **31**; ingredientes de 151 a **141** y pasos de 125 a
**117**. Son retenciones por correspondencia de foto, no un borrado de recetas
del usuario. La evidencia de las 33 comprobaciones HTTP anteriores se conserva
como histórica, no se confunde con el total final de publicación.

Lecturas adicionales: tandas delimitadas de 40, 40 y 29 posibles recetas
mediante HTTP; se descartaron registros con URL externa antes de curación.
No se hizo un espejo de las 756 recetas ni se afirmó haberlas revisado todas.
