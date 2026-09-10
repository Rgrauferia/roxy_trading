# Recetario de 500 — inventario con fuentes, no aprobación de 500 recetas

Fecha: 10 de septiembre de 2026. Producto: exclusivamente Roxy Home.

## Resultado del bloque

Se construyó y ejecutó un importador determinista sobre la API oficial de
Wikibooks. Inspeccionó **4.868 páginas**: 1.043 del espacio de recetas español y
3.825 de la categoría inglesa. Conserva **510 candidatos** con listas de
ingredientes, indicios de cantidades originales, rendimiento y pasos numerados
extraíbles: **121 ES y 389 EN**, **3.859 líneas de ingredientes** y **3.275 pasos**.
Seis páginas inglesas ya están en la selección pública de 14; no son seis
recetas nuevas. El resto no se ha incorporado al catálogo público.

**No hay 500 recetas confirmadas detalle por detalle.** Hay más de 500 fuentes
estructuradas para revisión. El muestreo encontró contradicciones, medidas
incompletas y prácticas que necesitan revisión de seguridad. No se ha hecho un
ensayo culinario, aprobación profesional, prueba de voz ni traducción de esas
510 fichas. No se puede garantizar que Roxy no se equivoque por importar texto.

Archivos:

- `tools/roxy_home_recipe_import_wikibooks.py`: importador y clasificación.
- `data/home_recipe_candidates_20260910.json`: bandeja editorial, unos 5 MB;
  **no la carga el servidor público**. Contiene 510 originales con sus revisiones
  y un índice compacto de las otras 4.358 páginas y sus motivos de exclusión.
- `tests/test_roxy_home_recipe_import_wikibooks.py`: pruebas de extracción,
  integridad, duplicados, omisiones y de que ninguna ficha se active sola.

No se tocaron recetas guardadas, mascotas, compras ni el manifiesto público de
14 originales. No se llamaron modelos de IA, no se generaron imágenes, no se
contrataron APIs y no se usaron claves de otro producto.

## Qué verifica y qué no verifica el importador

La fuente, ID de página, revisión inmutable, fecha, URL de historial, texto
original y SHA-256 permanecen juntos. Se preservan medidas y orden: no se
calculan conversiones, sustituyen ingredientes, inventan raciones ni rellenan
pasos. Las notas originales se conservan como evidencia aparte, incluidas
variaciones que podrían cambiar cantidades.

Se excluyen índices sin receta, listas sin raciones, ingredientes sin medida,
plantillas desconocidas, secciones narrativas no convertibles con fidelidad,
grupos anidados no resueltos, avisos de derechos/mantenimiento y duplicados
marcados en origen. La detección de duplicados exactos usa el contenido, no el
nombre. No demuestra que todas las variantes o traducciones sean platos únicos:
esa deduplicación editorial sigue pendiente.

El primer pase conservador dio 529 candidatos, incluidos 131 ES. El muestreo
encontró fracciones sin unidad y páginas etiquetadas como duplicadas. Se
endurecieron las reglas, sin corregir el original por suposición, y el resultado
final bajó a 510/121 ES. Se solicitó un margen técnico de 525 y no se alcanzó;
sí se supera el umbral de 500 **candidatos**, no de aprobaciones.

Las señales adicionales son prioridades de revisión, no un dictamen clínico:
133 fichas contienen huevo, 71 aves, 63 carnes; 38 incluyen menciones de
conservación/temperatura ambiente/noche, ocho germinación/deshidratación y varias
posibles omisiones de ingredientes. Los conteos se solapan. **209 sin señal
heurística tampoco están aprobadas.** Los algoritmos pueden omitir problemas y
marcar falsos positivos, por ejemplo agua de lavado o una sugerencia de servir.

Todas las filas declaran `publishable: false`, `can_cook_with_roxy: false`,
`can_add_to_shopping: false`, revisión culinaria/alérgenos/imagen no realizada.
La importación no cambia esos campos a partir de cantidad de tests o de una
segunda IA. El contenido externo nunca es una instrucción para el sistema.

## Fotografías: fuente real no significa fotografía correcta

94 recetas referencian un archivo en su ficha original inglesa. Se consultaron
93 nombres distintos en la API oficial de Commons y sus metadatos independientes
de autor, licencia, descripción, revisión, hash y dimensiones. 93 fichas tienen
metadatos de licencia abierta dentro de la lista conservadora del importador.
Poutine queda pendiente por una licencia GFDL no implementada en esa lista.
**Cero fotos aprobadas visualmente y cero descargadas.** No se hereda la licencia
del texto para las imágenes. No hay sustitutos genéricos.

Hay una reutilización real en origen: **Iced Tea y Hawthorn Tea apuntan al mismo
archivo**. Se marca en ambas, aunque el archivo tenga licencia válida. No se
mostrarán como dos fotografías específicas revisadas. Las otras 416 fichas no
tienen imagen identificada en el campo principal; ello no prueba que no exista
una imagen en otra parte del original. Las 121 españolas necesitan ese trabajo
adicional. Este catálogo, por sí solo, no resuelve la petición de foto exacta
para cada receta.

## Muestreo editorial reproducible

Se inspeccionaron ingredientes, pasos y notas completos de una muestra estable
de 12 fichas finales: ordenar por SHA-256 de `review-20260910:` + ID y tomar las
12 primeras. Es lectura humana/asistida de coherencia, **no cocina de prueba**.
El muestreo no permite estimar una tasa de seguridad ni certificar las demás.

| Ficha / revisión | Observación de la lectura | Resultado |
| --- | --- | --- |
| Maitorieska, EN-102208 / 4513087 | El horno figura a 300 °C o a su máximo; no se debe convertir esto en una instrucción universal para cualquier aparato. | Revisión de límites y técnica. |
| Spice Rub for Chicken, EN-128799 / 4516622 | Es una mezcla de especias; termina remitiendo a la cocción habitual del pollo. No es una receta completa de pollo. | Mantener como condimento y resolver dependencia antes de una guía de plato. |
| Flan, ES-20029 / 194792 | Pasos añaden vainilla/canela/limón, maicena y caramelo ausentes de ingredientes; falta temperatura del horno. | No publicar como guía completa. |
| Sopa fuchifu con pollo, ES-21251 / 426922 | Menudencias y huevo; no hay temperatura interna ni señal precisa para el huevo final. | Revisión de cocción segura, sin inventar tiempos. |
| Easy Peach Cobbler, EN-138402 / 4587371 | La receta usa una barra de margarina; notas precisan capacidad del molde y alternativa de conserva. | Aclarar unidad regional y mostrar notas; no escalar automáticamente. |
| Asparagus Soup, EN-34623 / 4523683 | Notas modifican agua según crema elegida; el enfriado necesita condiciones más precisas para guiar a principiantes. | Conservar variantes completas y revisar conservación. |
| Applesauce Cake, EN-451964 / 4516865 | No especifica diámetro de los dos moldes; hay una errata en equivalencia de onzas. | Revisar recipiente y equivalencias antes de convertir unidades. |
| Mostachón, ES-28292 / 209304 | Canela opcional aparece solo en pasos; horno «medio» y cocción «unos minutos», con erratas. | No guía detallada lista. |
| Split Peas (Cooked), EN-124512 / 4525248 | Usa agua salada aunque la sal no figura en ingredientes; notas permiten carnes opcionales. | Revisar lista y variantes, no usar etiquetas dietarias automáticas. |
| Cheese Egg Toast, EN-283009 / 4523929 | Se guía por color exterior; hay huevo sobre el sándwich. | Revisar criterio de cocción; no afirmar que dorado demuestra seguridad. |
| Two-Ingredient Brownies, EN-451734 / 4587472 | Incluye huevos y crema comercial de avellanas. Tiene molde/tiempo/temperatura; falta verificación de cocción y fórmula/alérgenos del producto. | Candidato para revisión, no aprobación alimentaria. |
| Matzah Lasagne, EN-191061 / 4630257 | Paso 9 añade media taza de agua y primer paso grasa para el molde, no listadas. | Resolver lista original antes de Compra o guía final. |

Cada revisión está enlazada en la fila de `data/home_recipe_candidates_20260910.json`.
No se corrigieron silenciosamente ni se divulgaron estos candidatos a usuarios.

Casos dirigidos adicionales que motivaron reglas o prioridades:

- **Ternera con salsa de piñones y pasas**, ES-39453/rev215680: `1/4 de pasas`
  y `1/2 de piñones` omiten la unidad. Excluida: no se asumió kg, taza ni paquete.
- **Orange Soda II**, EN-479550/rev4601581: categoría de duplicado del original.
  Excluida hasta comparar variantes, aunque tenga cantidades y pasos.
- **Garlic Pork Chops with Black Mushrooms**, EN-40944/rev4524743: ingredientes
  indican caldo de cerdo y pasos caldo de pollo. Señal de ingrediente distinto;
  no reemplazar uno por otro automáticamente.
- **Saj Bread I**, EN-415428/rev4505509: media taza de harina frente a 250 g de
  agua. Proporción sospechosa que requiere comprobar el original y un ensayo;
  no inventar conversión o una nueva cantidad para que funcione.
- **Tiramisú**, ES-28332/rev287740: huevo sin cocción/pasteurización explícita.
  Revisión especial; FDA recomienda huevos/productos pasteurizados en recetas
  que se sirven con huevo crudo o poco cocido. [FDA: seguridad del huevo](https://www.fda.gov/food/buy-store-serve-safe-food/what-you-need-to-know-about-egg-safety).
- **Pan esenio**, ES-58231/rev379674: germinación y deshidratación a 50 °C, más
  un marcador de paso dentro de otro. No aprobación: la FDA explica riesgos
  microbiológicos de germinados incluso en casa. [FDA: frutas, vegetales y germinados](https://www.fda.gov/food/buy-store-serve-safe-food/selecting-and-serving-produce-safely).
- **Seco de gallina**, ES-39519/rev426918: «carne suave» no es una temperatura
  comprobada. El criterio oficial utiliza termómetro; no rellenar una receta
  mediante un tiempo aleatorio. [FoodSafety.gov: temperaturas](https://www.foodsafety.gov/food-safety-charts/safe-minimum-internal-temperatures).
- **Fiambre guatemalteco**, ES-31985/rev210805: verdura cocida en vinagre queda
  a temperatura ambiente, sin validación de acidificación, duración o frío.
  Necesita revisión antes de guiar; no asumir que añadir vinagre valida una
  conserva. [USDA FSIS: sobras y conservación](https://www.fsis.usda.gov/food-safety/safe-food-handling-and-preparation/food-safety-basics/leftovers-and-food-safety).

## Fuentes y condiciones verificadas

**Wikibooks oficial:** texto reutilizable con atribución y CC BY-SA 4.0; conservar
avisos adicionales y revisar cada archivo multimedia por separado. Se incluye
URL de autores/historial, revisión y nota de transformación en cada ficha.
La licencia aplica al contenido derivado, no se declara que cambie la licencia
del software de Roxy. [Política fija, revisión 4622060](https://en.wikibooks.org/w/index.php?title=Wikibooks:Copyrights&oldid=4622060).
API en lotes, secuencial, mínimo un segundo, `maxlag`, caché y retroceso al
recibir límites. [Etiqueta de la API](https://www.mediawiki.org/wiki/API:Etiquette).

**TheMealDB:** la API de producción permite catálogo completo para supporters;
la clave 1 es de desarrollo. FAQ pide un nivel comercial; términos permiten
apps pagadas respetando límites y atribución, pero no transfieren derechos de
terceros. La FAQ también dice sin límites, mientras los términos sí los
mencionan: confirmar plan concreto por escrito. No cuenta, clave, contratación
o precio comercial confirmado para Roxy. No se intentó extraer sus páginas.
[API](https://www.themealdb.com/api.php), [FAQ](https://www.themealdb.com/faq.php),
[Términos](https://www.themealdb.com/terms_of_use.php).

**USDA/MyPlate:** las URLs oficiales probadas devolvieron 403; no se eludió.
MyPlate.food ofrece un archivo independiente de 1.072 recetas y declara acceso
comercial gratuito por consulta, 20/minuto y 100 detalles/día/IP. Su traducción,
estructura enriquecida e imágenes remasterizadas requieren licencia para
replicar la base. No es una API oficial USDA. No se descargó ni copió su archivo
ni se agregó otro adaptador: [API y límites](https://myplate.food/api),
[Licencias del archivo](https://myplate.food/partners).

## Puerta necesaria para las 500 utilizables

1. Priorizar las 121 fuentes españolas y platos con fotos originales verificables.
2. Comprobar todos los ingredientes contra todos los pasos y variantes; localizar
   una fuente más completa cuando algo falte. No completar por intuición.
3. Revisión culinaria/seguridad de cada ficha, con versión del revisor y alcance;
   recetas de conserva, germinados, crudos y técnicas especiales por una ruta propia.
4. Verificar foto exacta, autor, licencia y ausencia de reutilización engañosa.
5. Traducir cuando corresponda conservando original y revisión bilingüe; registrar
   incertidumbres, unidades regionales y cambios, sin raciones inventadas.
6. Probar la guía determinista paso a paso y la voz contra la misma revisión.
   Roxy puede explicar un paso aprobado, no generar uno que falte ni alterar la
   seguridad. Compra exige ingredientes y cantidades aprobados y acción del usuario.

El avance medible de este bloque es tener el material y el filtro reproducible
para revisar a escala. No es cumplir todavía las 500 confirmadas y fotografiadas.

## Reproducir y validar

```sh
python tools/roxy_home_recipe_import_wikibooks.py \
  --output /tmp/roxy_recipe_candidates_NEW.json \
  --cache-dir /tmp/roxy-recipe-source-cache-20260910 \
  --target 525 --max-pages 6000 --retain-complete-only --inspect-media

python -m pytest tests/test_roxy_home_recipe_import_wikibooks.py \
  tests/test_roxy_home_open_recipes_177.py -q
```

Resultado del 10/09: **67 pruebas aprobadas**, incluyendo el catálogo público
existente sin reemplazarlo. `git diff --check` correcto. Este bloque no se
publica solo; lo integra el agente coordinador después de revisar los cambios.
