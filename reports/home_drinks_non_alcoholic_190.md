# Ampliación de bebidas sin licores — candidato 190

Fecha: 11/09/2026. Estado: **18 preparaciones bilingües locales después de QA
visual del integrador; no publicadas por esta subtarea**. Los conteos de 20
que siguen documentan el lote previo a la retirada de cuatro fotografías.

## Alcance y continuidad

Se leyó el estado Home vigente, incluido 189 publicado con 31 bebidas, se
consultó la continuidad estructurada y se revisó Git. El check de continuidad
se intentó y sigue ausente en este worktree Home; no se copió desde Trading.
Se preservaron catálogo compartido, datos de usuarios, prototipos y otros
archivos en curso. No pagos, suscripciones, claves ni mutaciones públicas.

Archivos propios: `data/home_drinks_expansion_non_alcoholic.json` (array de
filas para que el integrador seleccione/fusione) y este informe. No se añadió
ninguna fila directamente a `data/home_open_drinks.json`.

## Fuente y revisión

- Fuente: [Open Drinks](https://github.com/alfg/opendrinks).
- Revisión fija: `f446f0e9356b9b43155d207b4f7c5214d9da91ab`.
- [Declaración de licencia para código, recetas y contenido](https://github.com/alfg/opendrinks#license).
- [MIT y aviso completo](https://github.com/alfg/opendrinks/blob/f446f0e9356b9b43155d207b4f7c5214d9da91ab/LICENSE), ya conservado por Home en `assets/open-drinks-license.txt`.

Se retomó la investigación previa, sin aprobar las candidatas retenidas de
189. Se inspeccionaron cuatro tandas delimitadas de 25 nombres y seis originales
adicionales. Hubo una primera llamada sin salida recuperable que se repitió;
no se presenta como trabajo editorial nuevo. Las fichas con URL de tercero en
cualquier campo se excluyeron antes de traducción. No se espejó todo el repositorio.

Cada fila conserva `raw_source` exacto, hash SHA-256, ID/revisión, contribuidor,
foto de la misma variante y licencia. EN se conserva sin modificaciones. ES
traduce las mismas líneas y pasos, sin completar medidas ni inventar raciones.
No se publican descripciones terapéuticas o etiquetas dietarias del proveedor
como si fueran verificaciones de Roxy. No son recetas ensayadas en cocina.

## Candidatas antes de QA visual

20 candidatas, 81 líneas de ingredientes y 97 pasos, en ambos idiomas:

- Café/té/chocolate (8): cappuccino, café batido indio, Milo Dinosaur, té
  tailandés con leche de almendra, latte, affogato, infusión de jengibre/menta,
  cacao caliente con soja/arce.
- Batidos (6): lassi cremoso de mango/cardamomo/almendra, matcha con mango/banana/
  espinaca, Oreo, peppermint con caramelo, banana/cacao, arándanos/banana/germen de trigo.
- Refrescantes (4): cebada/pandán/melón confitado, albahaca morada/limón, leche
  de rosas y flotante de cola/helado (Vaca preta).
- Jugos (2): panaka de melón/lima y limonada de sandía.

Son preparaciones distintas de las 31 publicadas en 189 y de los nombres
actuales comunicados del catálogo local/MyPlate. No se cuentan versiones
ES/EN como recetas diferentes. Cappuccino/latte/affogato tienen estructura y
preparación distintas; no son tres etiquetas de la misma bebida. No se reintrodujo
el lassi dulce ni el batido de menta/chocolate de las dos fotos retenidas.
El lassi de mango nuevo contiene yogur, leche, mango, cardamomo y almendra;
no se identifica como un smoothie de fruta genérico.

## Defectos excluidos

Ejemplos observados, no convertidos en recetas listas:

- Aam Panna: varios ingredientes nunca usados y guarnición ajena al plato.
- Aamras: tipo de mango distinto y jengibre que no aparece en preparación.
- Amrit Chai y Mango Shake: azúcar listada sin uso en pasos.
- Bajigur/Beras Kencur: ingredientes divergentes y medidas defectuosas.
- Hot Espresso: 30 ml de agua en lista frente a 3.5 fl oz en instrucciones.
- Milk Tea/Noon Chai/Wedang Uwuh: agua o té principal sin cantidad.
- Pumpkin Juice: no incluye calabaza pero las instrucciones dicen que se
  sedimentará calabaza; no se añade una cantidad supuesta.
- Egyptian Fakhfakhina y Khoshaf: medidas incompletas o contradictorias.
- Mango Mocktail: lima adicional no listada y cambio en el jugo principal.
- Nannari Sarabath: el jarabe nunca se añade a la bebida final según los pasos.
- Caferio Cookie Shake: café en polvo de tipo no definido para mezcla en frío;
  queda sólo en la galería de investigación, no en el array de candidatas.
- Nam Thom: preparación con kratom; fuera del catálogo alimentario de esta tarea.
- Harry Potter Butterbeer: sake/lista incompatibles con los pasos; no es sin licores.
- Numerosas fichas enlazan explícitamente autores comerciales externos; no se
  copia su contenido/foto amparándose únicamente en la licencia del repositorio.

## Medidas, extras y límites preservados

No se cambia por gramos una medida original como manojo, puñado, pieza, bola o
vaso. Las notas identifican esos casos; no se califican de medidas exactas.
Hielo, guarniciones y crema adicionales presentes sólo en pasos se explican sin
inventar cantidades. Las variantes con leche condensada siguen mostrando que
contienen lácteos aunque lleven también leche de almendra. Extractos y marcas
deben revisarse en sus etiquetas cuando se necesite evitar todo alcohol o alérgenos.

No se ofrecen raciones, nutrientes, sustituciones o tiempos no escritos en la
fuente. Los procedimientos que usan máquinas de espresso conservan instrucciones
originales y nota separada de seguir el fabricante/evitar vapor y superficies calientes.

## Verificación técnica y visual

Comprobación local: 20 IDs únicos no presentes entre las 31 publicadas, hashes
correctos, pasos EN originales, longitudes de traducción iguales, sin URL externa
en `raw_source`. Las 20 fotos responden HTTP 200 `image/jpeg`, 17–190 KB, con
20 hashes binarios diferentes. No se reexportan archivos de imagen.

CUA de esta subtarea no tiene navegadores disponibles (`iab` no disponible,
inventario de browsers vacío). Se preparó con `apply_patch` una galería de
fotos remotas y el texto de cada ficha en
`/tmp/roxy-drinks-190-qa/nongallery.html`, servida por el QA del integrador en
`http://127.0.0.1:8787/nongallery.html`. Un servidor propio alternativo en 8792
se detuvo; no se detuvo el servidor 8787 ajeno. No se afirma QA visual sin ver
la evidencia.

### Resultado de QA visual del integrador

El integrador inspeccionó las 21 fotos de la galería en tres capturas de
1200×950; la candidata Caferio ya estaba excluida del JSON. Se retiraron cuatro
filas adicionales del array de expansión:

- `barley-drink`: marca de agua ©souperdiaries.com; derechos de la fotografía
  de tercero no confirmados. La declaración MIT general no los sustituye.
- `watermelon-lemonade`: marca de agua externa HERECOMES…; derechos sin confirmar.
- `creamy-mango-lassi`: foto con pistachos verdes y otras guarniciones, frente
  a las almendras/cardamomo que especifica la preparación.
- `matcha-green-tea-smoothie`: la foto lleva coco rallado que no está en receta.

No se sustituyeron fotos ni se añadieron ingredientes para acomodar imágenes.
Quedan **16 filas, 59 ingredientes y 76 pasos** en el array. Se conserva la
evidencia de 20 HTTP anteriores como histórica, no como conteo final.

Se hizo una última tanda delimitada de ocho nombres buscando jugos. Cherry
Limeade reutiliza el archivo genérico lemonade.jpg, por lo que se rechaza;
Magic Eye Juice diverge entre limón picado y jugo de limón. ABC Juice, Pineapple
Juice y Green Mango Sharbat se dejaron en una galería aparte para segunda
revisión (`more-juice.html`). No se cambió ni reprodujo
ninguna afirmación detox, terapéutica o de prevención de enfermedades.

### Entrega final estable

El integrador observó cargadas las fotos de ABC Juice (858 px) y Pineapple
Juice (600 px) y aceptó su correspondencia. Se añadieron sus originales y
traducciones cotejadas al array. Se retuvo Green Mango Sharbat porque no indica
duración ni punto de cocción del mango y la secuencia de hervir/pelar necesita
mejor explicación; no se inventó esa preparación para alcanzar una cuota.

**Resultado final: 18 filas nuevas, 69 ingredientes y 87 pasos por idioma.**
Categorías: 8 café/té/chocolate, 4 batidos, 3 refrescantes y 3 jugos.
Todas distintas por ID de las 31 publicadas. El array no sustituye ni modifica
el catálogo vigente; el integrador hará la fusión y publicación si pasa sus pruebas.

Comprobación final automatizada: 18 IDs únicos; SHA-256 de cada `raw_source`
correcto; ingredientes EN iguales a la concatenación sin pérdidas de la fuente;
pasos EN exactos; longitudes de listas ES/EN coincidentes; `alcoholic: false`;
URLs de receta e imagen ligadas a la revisión fija y al archivo de la fuente.
`git diff --check` terminó sin errores. La fusión del integrador ya incluye
estas 18 filas en su catálogo de 87; esta subtarea no editó ese archivo compartido.

En ABC, la recomendación original de refrigerar hasta 24–48 horas se conserva
como texto de fuente y se aclara que no constituye garantía sanitaria,
pasteurización ni beneficio detox de Roxy. En piña se explican los 2 vasos
sin volumen declarado; no se calculan porciones. Las afirmaciones de salud
de las descripciones no se trasladan a títulos ni a la guía ES.

No queda otro rastreo pendiente de esta subtarea. Las galerías temporales son
evidencia de QA con recursos remotos; no se borraron archivos de usuario ni
se dejaron servidores propios ejecutándose. Cualquier límite de derechos o
correspondencia descubierto posteriormente requiere retención de la ficha,
no reemplazar su foto con otra genérica.
