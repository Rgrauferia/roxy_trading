# Roxy Home — revisión editorial de 20 candidatas ES

Fecha: 10 de septiembre de 2026. Alcance: auditoría de solo lectura; **no publicación, corrección de recetas, certificación culinaria ni autorización para cocinar/comprar**. No se modificó el manifiesto, el runtime ni Docker.

## Resultado y alcance real

El lote de 510 candidatas **no equivale a 510 recetas confirmadas**. Contiene 121 originales ES y 389 EN. Se leyó el inventario ES, se examinaron ingredientes/pasos de 33 candidatas y se seleccionaron las 20 de abajo para leer además su wikitext completo y priorizar revisión. No es una muestra aleatoria ni permite extrapolar una tasa de error al lote entero.

En las 20 hay 97 líneas de ingredientes y 133 pasos; los 20 SHA-256 coinciden con el wikitext conservado. Eso acredita integridad de la instantánea, no corrección culinaria. Se distinguieron:

- **A — 3 candidatas sencillas prioritarias:** no encontré contradicción material en la preparación básica leída. Aún requieren revisión editorial/alérgenos, foto y prueba culinaria; no están aprobadas.
- **B — 7 candidatas con aclaraciones concretas:** hay que resolver alcance, cantidades, tiempos o conservación antes de guiar a una persona.
- **C — 10 candidatas retenidas:** hay omisión, contradicción o parámetro necesario no definido. No completar mediante IA ni inferir la intención del autor.

**0/20 tienen foto demostrada de la ejecución de esa receta exacta; 0/20 están aprobadas culinariamente.** El manifiesto conserva `publishable:false`, `can_cook_with_roxy:false` y `can_add_to_shopping:false` para las 20. La selección es una cola de trabajo de 20, no una entrega de 20 listas.

Instantánea: `data/home_recipe_candidates_20260910.json`; generación `2026-09-10T16:12:50.371433+00:00`; importador `wikibooks-candidate-import-4`; SHA-256 del archivo `746ced612d6ca725084128ad9b4c7e9dca602171d0eb1a3621c883de02ee83c5`.

## Lista priorizada por receta

Todos los títulos enlazan la revisión exacta leída. `I/P` = líneas de ingredientes/pasos, **no número de porciones**. “Sin foto” significa sin referencia de imagen en el wikitext de esa revisión, no que sea imposible obtener otra con derechos y correspondencia verificados.

| Prioridad / ID | Receta y fuente original | I/P | Evidencia y pendiente concreto | Foto |
|---|---|---:|---|---|
| A · 39203 | [Guacamol guatemalteco, rev. 212184](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FGuacamol+guatemalteco&oldid=212184) | 5/7 | Aguacate, limón y cebolla en unidades; orégano y sal al gusto. Los cinco ingredientes aparecen en la preparación. Las tortillas son acompañamiento de servicio, no están cuantificadas: no enviarlas a Compra por inferencia. La categoría de origen «Diabetes» no demuestra idoneidad clínica y no debe convertirse en recomendación. | Sin foto. |
| A · 20590 | [Coctel de frutas con yogurt, rev. 210661](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FCoctel+de+frutas+con+yogurt&oldid=210661) | 4/4 | Yogur, miel, nuez y melón aparecen con cantidades y se utilizan. Rinde «1 a 2»: no dividir nutrientes como si fueran dos porciones confirmadas. No explica corte/lavado del melón; el minuto declarado no cubre necesariamente esa preparación. Revisar lácteos/frutos secos y unidades de taza antes de normalizar. | Sin foto. |
| A · 20788 | [Quesadillas, rev. 210974](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FQuesadillas&oldid=210974) | 2/4 | Tres tortillas y 50 g de queso; comal, fuego lento y final de queso fundido definidos. Solo se revisó la variante básica. El bloque externo de trucos propone muchos rellenos sin recetas: no convertirlos en variantes completas ni aplicarles estos cuatro pasos. | Sin foto. |
| B · 9305 | [Salsa alioli fácil, rev. 426933](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FSalsa+alioli+f%C3%A1cil&oldid=426933) | 4/6 | Ajo y mayonesa cuantificados; perejil/sal a gusto. Preparación base coherente como mezcla de mayonesa ya preparada, no como receta de mayonesa. El bloque de trucos ofrece mayonesa casera sin método/pasteurización: requiere revisión de seguridad; faltan conservación y porción servida. | Sin foto. |
| B · 63701 | [Granadina, rev. 424373](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FGranadina&oldid=424373) | 2/4 | Jugo y azúcar medidos en ml, sin conversión a gramos. Los pasos mezclan, hierven, reducen y enfrían. No fija volumen final, tiempo de reducción ni conservación. Es un jarabe/ingrediente; «4 comensales» no define dosis de consumo. No contar como comida ni completar una bebida inexistente. | Sin foto. |
| B · 56852 | [Alajú, rev. 354034](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FAlaj%C3%BA&oldid=354034) | 5/6 | Miel/frutos secos/pan rallado pesados y obleas de 20 cm. Agua del extracto de corteza no cuantificada; después habla de gotas de «esencia» obtenida, no de esencia comercial intercambiable. Falta intensidad/tiempo de cocción y enfriado antes de servir. Revisar manipulación de miel caliente. | Sin foto. |
| B · 39490 | [Atol de elote, rev. 216111](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FAtol+de+elote&oldid=216111) | 5/7 | El agua «necesaria» se concreta en pasos: completar la mezcla a un litro; no es añadir un litro extra. Diez minutos tras hervir indicados. La canela de la lista es en raja; el acabado añade canela en polvo no separada. Revisar textura final, retirada de raja y tiempo total de 1,5 h. | Sin foto. |
| B · 31992 | [Pimientos asados con vinagreta de comino, rev. 153811](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FPimientos+asados+con+vinagreta+de+comino&oldid=153811) | 6/7 | Ingredientes principales cuantificados; horno 180 °C/30 min. Declara 45 min pero exige refrigerar «algunas horas». No define ese intervalo ni enfriado/manipulación para pelar. Dos cucharadas de comino son explícitas, no corregirlas silenciosamente aunque merezcan prueba de sabor. | Sin foto. |
| B · 25922 | [Gazpacho morañiego, rev. 426743](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FGazpacho+mora%C3%B1iego&oldid=426743) | 8/4 | Aceite/vinagre en «chorritos» y media hogaza sin peso. La página incluye una preparación alternativa triturada y un picadillo fuera de los cuatro pasos extraídos. No mezclar versiones; la alternativa necesita al menos 2 h de frío, ausentes del tiempo de 10 min. | Sin foto. |
| B · 63824 | [Extracto de té, rev. 424863](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FExtracto+de+t%C3%A9&oldid=424863) | 2/4 | 240 ml de agua, té y cinco minutos de infusión; reducción al 10 % explícita. Es concentrado, no taza de té lista: faltan aplicación/dilución, porción y conservación. No presentarlo como bebida para cuatro sin aclaración. | Sin foto. |
| C · 21371 | [Pan de Pita, rev. 377882](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FPan+de+Pita&oldid=377882) | 5/5 | Harina 500 g; agua en vaso sin capacidad; rendimiento declarado **0**. Levadura «prensada o de panadería» no aclara equivalencia seca/fresca. Falta unidad de los 220 grados y duración del segundo levado; los 60 min no separan tiempo activo y reposos. No calcular hidratación/raciones por suposición. | Sin foto. |
| C · 16363 | [Horchata de chufa, rev. 416032](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FHorchata+de+chufa&oldid=416032) | 3/11 | Las tres extracciones de 1,5 l sí suman los 4,5 l declarados. Pero el remojo dura 12–14 h frente a ficha de 20 min, sin condición de refrigeración definida. La bebida sin tratamiento térmico requiere revisión de higiene/conservación y rendimiento; «4 comensales» no aporta volumen servido. | Sin foto. |
| C · 63547 | [Dobladitas, rev. 422989](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FDobladitas&oldid=422989) | 7/10 | Cantidades métricas, horno 200 °C/15–20 min y barniz de huevo. El aceite de bandeja no figura en ingredientes; el rendimiento oscila entre 20 y 30 piezas. Faltan tamaño/espesor para validar horneado. No adoptar calorías ni equivalencias de cucharadas del texto sin cálculo/revisión independiente. | Sin foto. |
| C · 20071 | [Bizcocho de almendras, rev. 209931](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FBizcocho+de+almendras&oldid=209931) | 3/5 | Huevos, almendra y azúcar cuantificados; pasos requieren mantequilla de molde no listada. Falta tamaño del molde/unidad de 180 grados; «verter la masa en el horno» es redacción ambigua. Los trucos añaden grasa/levadura sin cantidades completas: no incorporarlos automáticamente. Revisar cocción central, no solo dorado. | Sin foto. |
| C · 63650 | [Rosegones de Alpuente, rev. 423394](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FRosegones+de+Alpuente&oldid=423394) | 4/5 | Cantidades de cuatro ingredientes presentes. Primer horneado sin duración, grados sin unidad ni precalentado; no hay dimensiones de los tres panes. Solo fija cinco minutos después de dar vuelta. La nota de lata metálica no es una vida útil validada ni sustituye el enfriado. | Sin foto. |
| C · 39539 | [Pastelitos criollos, rev. 426901](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FPastelitos+criollos&oldid=426901) | 7/14 | La lista pide **300 g** de manteca; pasos asignan **150+50+50=250 g**. Un vaso de agua sirve de referencia ambigua para masa y almíbar. Fritura sin rango de temperatura. Hay buena secuencia/espesores, pero no se puede decidir dónde van los 50 g restantes. Nutrición en la plantilla sin validación. | M2: licencia abierta; imagen ilustrativa. |
| C · 63700 | [Baklava, rev. 425298](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FBaklava&oldid=425298) | 8/16 | Ingredientes cuantificados, capas y horno 180 °C/25 min. El paso 12 alude a una «licuadora» usada para derretir mantequilla, mientras el paso 3 usa cacerola. No define molde/tamaño de hojas ni detalle de engrase entre láminas. Mantener ambigüedad retenida; no reescribir como procedimiento verificado. | Sin foto. |
| C · 27363 | [Tortellini a la crema, rev. 210997](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FTortellini+a+la+crema&oldid=210997) | 9/4 | Parmesano de 60 g se reparte coherentemente. Canela de lista **una pizca**, preparación **media cucharadita**. El tortellini no identifica fresco/seco/relleno y fija ocho minutos. Requiere resolver variante y cantidad; no inferir temperatura de seguridad ni tiempo del producto elegido. | Sin foto. |
| C · 15389 | [Arroz con leche, rev. 426679](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FArroz+con+leche&oldid=426679) | 4/7 | Cuatro vasos de arroz sin capacidad/variedad; agua de remojo y cocción sin cuantificar. Remojo nocturno o mínimo 3 h frente a ficha de 1 h. La transición de arroz cocido/leche no aclara escurrido o cocción conjunta; refrigeración sin manejo/enfriado definidos. No cambiar proporciones por intuición. | M3: foto de pastelería, no receta exacta. |
| C · 28433 | [Mostachón de Utrera, rev. 209305](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FMostach%C3%B3n+de+Utrera&oldid=209305) | 4/3 | Cantidades presentes pero **no hay temperatura ni duración del horno**, ni dimensión de piezas. El tercer paso presupone horneado ya terminado. Debe verificarse soporte apto para horno y ejecución completa; una foto del resultado no repara los pasos faltantes. | M1: licencia abierta; imagen ilustrativa. |

## Medios: tres hallazgos, ninguna foto exacta acreditada

Se revisaron páginas descriptivas/licencias de Commons, no se realizó inspección visual de píxeles ni se descargaron archivos. Una foto utilizada por Wikibooks prueba asociación editorial con el plato, **no que se cocinó la formulación de esa revisión**.

| ID | Archivo y atribución | Licencia comprobada / pertinencia |
|---|---|---|
| M1 | [Mostachon Utrera.jpg](https://commons.wikimedia.org/w/index.php?title=File:Mostachon_Utrera.jpg&oldid=450656830), Tirithel, obra propia, 2000×1500 | La página permite elegir CC BY-SA 4.0 (entre otras). Describe mostachón de Utrera, sin vínculo a estas cantidades/pasos. |
| M2 | [Pastelitos criollos argentinos.jpg](https://commons.wikimedia.org/w/index.php?title=File:Pastelitos_criollos_argentinos.jpg&oldid=1052865041), El rrienseolava, obra propia, 694×600 | CC BY-SA 4.0 disponible entre las licencias indicadas. Describe pastelitos típicos argentinos; no confirma relleno/masa exactos. |
| M3 | [ArrozLeche-Cubero-2009.jpg](https://commons.wikimedia.org/w/index.php?title=File:ArrozLeche-Cubero-2009.jpg&oldid=1083022336), Tamorlan, obra propia, 3888×2592 | CC BY 3.0; la descripción identifica una pastelería de Valladolid. No es evidencia de la ejecución de la receta de Wikibooks. |

Reutilización sujeta a atribución, enlace a licencia e indicación de cambios; CC BY-SA añade condiciones sobre adaptaciones. No implicar apoyo del fotógrafo a Roxy. [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/).

## Defectos del lote detectados, sin corregir aquí

1. **Alta · confianza alta — falso negativo de imágenes.** Las 121 ES tienen `source_image_names:[]`; 14 wikitextos enlazan imágenes en el cuerpo/galerías. El extractor solo mira `image`/`imagen` de la plantilla. Tres ocurren en las 20 revisadas. Es un defecto de cobertura, no licencia automática. Debe rastrearse contexto, atribución y variante antes de crear un campo utilizable por UI.
2. **Alta · confianza alta — notas no expuestas.** Seis de las 20 contienen `Artes culinarias/Trucos` mientras `notes_source_wikitext` está vacío: alioli fácil, quesadillas, gazpacho, bizcocho, pastelitos y rosegones. El wikitext completo sí está guardado. También hay un método alternativo de gazpacho fuera de los pasos. No llamar a las columnas extraídas «página íntegra».
3. **Alta · confianza alta — validación sintáctica demasiado débil para calidad editorial.** «1 vaso», «120 de leche», «1 unidad aceite» o un rendimiento cero superan checks de presencia. Los flags vacíos no significan ausencia de problemas. El estado `source_structure_complete_pending_editorial_review` solo afirma que hay listas parseables; no calidad, precisión o seguridad.
4. **Alta · confianza alta — ejemplos descartados del grupo prioritario.** [Frita de tomate, rev. 194102](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FFrita+de+tomate&oldid=194102): 5 cucharadas de sal/500 g de tomate y «1 unidad aceite». [Mayonessa alioli, rev. 209301](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FMayonessa+alioli&oldid=209301): 500 centilitros de leche y 250 centilitros de aceite; no asumir que pretendía mililitros. [Patatas sin aceite, rev. 380124](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FPatatas+fritas+al+horno+sin+aceite&oldid=380124): exige aceite y conserva texto de plantilla como tiempo. [Fainá, rev. 305607](https://es.wikibooks.org/w/index.php?title=Artes+culinarias%2FRecetas%2FFain%C3%A1&oldid=305607): seis cucharadas de aceite no listadas, horno sin temperatura, 20 min declarados frente a una hora de reposo. No son errores inventados por Roxy, pero tampoco deben propagarse.

No se aplicó una temperatura universal a bizcochos, panes o cada ingrediente. La revisión de huevo crudo y de variantes debe seguir la población, preparación y orientación pertinente; las fuentes de referencia no certifican estas recetas. [FDA, seguridad del huevo](https://www.fda.gov/food/buy-store-serve-safe-food/what-you-need-know-about-egg-safety), [FoodSafety.gov, cocción por alimento](https://www.foodsafety.gov/food-safety-charts/safe-minimum-internal-temperatures).

## Reproducción mínima de los conteos

Desde la raíz del worktree; solo lectura. Las decisiones A/B/C son juicio editorial documentado arriba, no resultado de este script. Revisar original y revisión de fuente antes de cualquier promoción.

```python
import hashlib, json, re
from pathlib import Path

p = Path("data/home_recipe_candidates_20260910.json")
raw = p.read_bytes()
assert hashlib.sha256(raw).hexdigest() == "746ced612d6ca725084128ad9b4c7e9dca602171d0eb1a3621c883de02ee83c5"
d = json.loads(raw)
ids = [39203, 20590, 20788, 9305, 63701, 56852, 39490, 31992,
       25922, 63824, 21371, 16363, 63547, 20071, 63650, 39539,
       63700, 27363, 15389, 28433]
lookup = {r["id"]: r for r in d["recipes"]}
rows = [lookup[f"wikibooks-es-{i}"] for i in ids]
es = [r for r in d["recipes"] if r["language"] == "es"]
assert (len(d["recipes"]), len(es), len(rows)) == (510, 121, 20)
assert sum(len(r["ingredients_original"]) for r in rows) == 97
assert sum(len(r["steps_original"]) for r in rows) == 133
for r in rows:
    assert hashlib.sha256(r["original_wikitext"].encode()).hexdigest() == r["source_sha256"]
    assert r["audit"]["publishable"] is False
    assert r["audit"]["can_cook_with_roxy"] is False
    assert r["audit"]["can_add_to_shopping"] is False
    assert r["source_image_names"] == []
image = r"(?:\[\[|^)(?:Image|File|Archivo|Imagen):"
assert sum(bool(re.search(image, r["original_wikitext"], re.I | re.M)) for r in es) == 14
assert sum(bool(re.search(image, r["original_wikitext"], re.I | re.M)) for r in rows) == 3
assert sum("Artes culinarias/Trucos" in r["original_wikitext"]
           and not r["notes_source_wikitext"] for r in rows) == 6
print("20 candidatas verificadas contra instantánea; ninguna aprobada/publicada")
```

## Siguiente paso recomendado

Enviar las tres A y las siete B a un revisor culinario con el original, preguntas pendientes y prueba de ejecución; producir fotografía de esa ejecución o conseguir evidencia/licencia equivalente. Mantener las diez C retenidas hasta resolución de fuente. No hacer 20 correcciones silenciosas para conseguir un número.

Para llegar a 500 con pasos y foto vinculados, usar la negociación/editorial descrita en `reports/home_recipe_provider_options_20260910.md`; este lote abierto no demuestra ese nivel. Toda futura normalización debe guardar original, cambios aprobados y versión, tratar alternativas como tales, separar tiempo activo/espera y revisar foto/plato/variante. No crear raciones, equivalencias, nutrición, alérgenos resueltos o compras donde la fuente no los sostiene.
