# Rutinas educativas de fuente pública — candidato 192

Fecha de consulta y extracción: 2026-09-11. Estado: datos candidatos para integración y QA; este archivo no acredita despliegue, revisión clínica, idoneidad individual ni aprobación de NHS.

## Entrega

Archivo: `data/home_fitness_source_programs_192.json`, 39.422 bytes, SHA-256 `753ffec0e8add56ed50ed3c6a902f903311943f58c317746efc4e8b0b886d853` (se retiró sólo una línea vacía final antes del commit; extracciones sin cambios).

Tres rutinas completas en su contenido editorial de introducción y ejercicios: 16 movimientos, 67 párrafos de instrucciones EN y sus 67 traducciones ES, más 25 párrafos introductorios EN/ES.

| ID | Fuente original | Revisión publicada | Próxima revisión publicada | Movimientos | Párrafos |
|---|---|---|---|---:|---:|
| gentle-strength | [Strength exercises](https://www.nhs.uk/live-well/exercise/strength-exercises/) | 2024-02-28 | 2027-02-28 | 7 | 28 |
| gentle-balance | [Balance exercises](https://www.nhs.uk/live-well/exercise/balance-exercises/) | 2023-11-07 | 2026-11-07 | 5 | 19 |
| gentle-flexibility | [Flexibility exercises](https://www.nhs.uk/live-well/exercise/flexibility-exercises/) | 2023-11-20 | 2026-11-20 | 4 | 20 |

La frecuencia textual de las tres fuentes es al menos dos veces por semana, combinándolas con las otras rutinas de la serie. No son programas periodizados ni especifican días concretos. Fechas y días de la agenda deben ser una elección explícita del usuario, no una prescripción inferida.

## Procedencia e integridad

Cada fila conserva dos comprobantes diferentes:

- `source_html_sha256`: hash de los bytes HTML recibidos del artículo oficial; no se incluye ni redistribuye el HTML completo.
- `raw_source` y `source_sha256`: serialización JSON de una extracción editorial EN y su hash UTF-8. Conserva título, introducción, frecuencia, nombres e instrucciones. **No es JSON suministrado por NHS ni una reproducción byte por byte del HTML.**

Se extrajeron los párrafos editoriales, encabezados y lista de rutinas relacionadas. Los espacios de HTML se normalizaron a espacios simples; la redacción, puntuación, dosis y orden se conservaron. Se excluyeron navegación, encuestas, imágenes, pies de foto y créditos de imágenes. Los IDs de programas y movimientos son identificadores locales, no IDs oficiales.

Hashes de las extracciones editoriales:

- Fuerza: `6501a2eafc749539ec0a96adeb95651931a11f4008bd95518048fe4c64b43ae8`.
- Equilibrio: `1d29d9b787d4164591f93459eb7169f98c3d01846118265aad452ad193037284`.
- Flexibilidad: `57f329d0e0b4d76b1b51fdcf06eb634263ef4518899b66303ef518df5a9b6f9b`.

## Licencia y presentación

Los [términos generales NHS, apartados 3.3–3.6](https://www.nhs.uk/our-policies/terms-and-conditions/) permiten reutilización comercial y adaptación del texto elegible bajo OGL, con exclusiones. No se encontró en estos tres artículos una condición editorial más restrictiva. La lista de [exclusiones](https://www.nhs.uk/our-policies/terms-and-conditions/content-not-licensed-for-re-use/) no garantiza exhaustividad. Por ello **media=[]**: sin fotografías, vídeo, audio, logotipos ni ilustraciones; no se reutilizaron imágenes de personas o medios de terceros.

Separar en la interfaz:

- **Vista EN original**: atribución fechada por instancia, enlace al artículo correspondiente y aviso OGL; el campo `attribution_en` contiene la atribución y fecha `110926` exigida para la copia fechada. Mostrar también la fecha legible de consulta.
- **Vista ES**: “Adaptación al español de Roxy”, seguida de `Contains public sector information licensed under the Open Government Licence v3.0.`, enlazando a [OGL 3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). No mostrar NHS como autor, avalista o fuente de la **adaptación**, ni un sello de aprobación. El enlace para comparar la versión EN debe identificarse como procedencia del **texto original**, en una sección separada.
- No cobrar una tarifa específica de acceso a este contenido ni insinuar asociación o aprobación del producto; ver términos 3.10–3.11.

La adaptación puede invalidar la aprobación clínica formal de la fuente. Ninguna fila se marca clínicamente aprobada. Esta lectura de condiciones guía la implementación; no sustituye asesoría jurídica. El aviso y los enlaces deben quedar visibles, no sólo almacenados en JSON.

## Límites de contenido y uso

`duration_seconds`, `rest_seconds` y `progression` son nulos. No se añadieron cargas, descansos, minutos totales, calorías, rangos ni una progresión automática. Las indicaciones de progresar se conservan únicamente como texto original/traducido. `clinical_approval=false`; el consumo previsto es una guía educativa y una agenda temporal elegida, no activación de planes personales, cribado médico ni registros de entrenamientos realizados.

Cotejos importantes:

- “Hasta 5 segundos” no se convirtió en 5 obligatorios; “al menos 5 pasos” no se convirtió en un límite máximo.
- Se mantienen series, repeticiones y lados originales. La caminata lateral conserva “10 pasos por dirección **o** de un lado de la habitación al otro”.
- La extensión de pierna se identifica en ES como elevarla **hacia atrás estando de pie**; no se sustituye por una máquina de extensión de rodilla.
- Estiramiento de pantorrilla conserva “un pie de distancia”; la fuente no da tiempo de mantenimiento y no se inventa uno.
- Se mantiene el orden editorial original aunque una indicación de mantener la posición aparezca después del párrafo que describe volver a apoyarla.
- Las referencias textuales a “ejercicios sentado” se conservan como parte de la introducción, pero no implican una cuarta rutina integrada. Esa rutina queda fuera de esta tanda; no se suprimieron afirmaciones de su original para forzar su inclusión.

## Verificaciones realizadas

Validación local sin red: JSON válido; 3 IDs únicos; IDs de movimiento únicos por rutina; SHA de `raw_source`; igualdad exacta entre la extracción EN guardada y campos EN proyectados; listas EN/ES paralelas; todos los números de instrucciones preservados, en el mismo orden; ausencia de medios; campos de duración/descanso/progresión nulos.

Lectura semántica EN/ES completa de los 16 movimientos realizada por esta tarea. No equivale a revisión profesional, estudio de seguridad o demostración visual de técnica.

El agente de backend comunicó 77 pruebas nuevas aprobadas y 334 pruebas del bloque fitness aprobadas con el archivo candidato. Son resultados reportados por ese agente, no una ejecución repetida por esta tarea. La revisión final de UI, permisos, integración y despliegue corresponde al agente principal.

El archivo está bajo una carpeta ignorada por Git: debe incorporarse de forma explícita y acotada si el agente principal decide publicarlo. No se modificaron catálogos activos, aprobaciones existentes, rutinas clínicas ni datos de usuarios.
