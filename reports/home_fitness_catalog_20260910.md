# Roxy Home · ampliación educativa de Ejercicio

Comprobado el 10 de septiembre de 2026. **21 fichas, 19 originales en español y 2 en inglés, 67 párrafos y 44 ilustraciones.** Se añaden 13 fichas y 28 imágenes a la selección de ocho del 08/09, sin alterar aquellas ocho. Cero fotos, videos, planes personalizados o aprobaciones clínicas. Este informe documenta código y datos locales; la integración visual y publicación corresponden a la tarea principal.

## Cobertura real

| Grupo de wger | Fichas |
| --- | ---: |
| Brazos | 6 |
| Pecho | 4 |
| Piernas | 4 |
| Espalda | 3 |
| Hombros | 3 |
| Abdominales | 1 |

La selección incorpora remos, dominadas, una sentadilla frontal, zancadas caminando, presses, fondos y abdominales en banco inclinado. No se infiere de ello que cada variante sea apropiada para un principiante, que la biblioteca esté equilibrada para todo objetivo o que pueda asignar entrenamientos. El tronco, la actividad aeróbica y el entrenamiento sin material siguen poco cubiertos. No se inventan variantes o instrucciones para llenar esas carencias.

## Nuevas fichas, con asociaciones fijas

| Ejercicio wger | Original seleccionado | Idioma / traducción | Imágenes |
| --- | --- | --- | --- |
| 75 | Press de banca con mancuernas | ES / 2626 | 113, 114 |
| 84 | Remo inclinado con agarre invertido | ES / 3689 | 91, 92 |
| 152 | Dominadas con Agarre Supino | ES / 2708 | 73, 75 |
| 171 | Abdominales en Banco Inclinado | ES / 2699 | 135, 136 |
| 185 | Decline Bench Press Barbell | EN / 100 | 115, 116 |
| 197 | Fondos entre Bancos | ES / 2726 | 35, 36 |
| 206 | Zancadas Caminando con Mancuernas | ES / 2720 | 121, 122, 123, 124 |
| 246 | Press Francés con Barra SZ | ES / 2738 | 60, 61 |
| 257 | Sentadilla Frontal | ES / 2731 | 149, 150 |
| 513 | Remo en "T" | ES / 2936 | 77, 79 |
| 537 | Press inclinado con mancuernas | ES / 4379 | 105, 106 |
| 566 | Press de hombros con barra | ES / 4353 | 171, 172 |
| 567 | Press Militar mancuerna | ES / 2611 | 173, 174 |

Se consultaron los GET públicos `https://wger.de/api/v2/exerciseinfo/{id}/`, siguiendo la [documentación oficial](https://wger.readthedocs.io/en/latest/api/api.html). Se conservaron las palabras completas de la traducción seleccionada, retirando solo HTML y normalizando espacios. No se tradujeron con IA, no se añadieron series/cargas/descansos individuales, ni se recortaron párrafos. El original inglés de 185 coincide con el apoyo de pies de las ilustraciones; el español describe soportes de piernas que no aparecen en ellas. El material que falta en los metadatos de la fuente permanece sin confirmar: una lista vacía no significa «sin equipo».

Cada nueva imagen se descargó a un temporal para inspección visual individual de las posiciones y se contrastó con las instrucciones seleccionadas. Los PNG se siguen sirviendo desde wger, sin edición ni rehosting. La licencia por imagen es **CC BY-SA 3.0**, autor **Everkinetic**, `is_ai_generated=false`, según sus metadatos individuales en la respuesta oficial. El nombre del archivo no se tomó por prueba suficiente de variante ni de derechos.

## Derechos separados y trazabilidad

`data/home_fitness_catalog.json`, versión `fitness-open-catalog-20260910-v2`, conserva para cada recurso ID/UUID, autor, licencia, URL de licencia, actualización de la fuente, fecha de incorporación y SHA-256 de texto e imagen. La [lista de licencias del proveedor](https://wger.de/api/v2/license/) mantiene la correspondencia: 1 = CC BY-SA 3.0; 2 = CC BY-SA 4.0; 3 = CC0 1.0. Los metadatos base de la dominada 152 son CC0, mientras su texto ES es CC BY-SA 4.0 y sus dibujos CC BY-SA 3.0. **CC0 en metadatos no cambia los derechos del texto o los medios.** Se conserva crédito incluso para esos metadatos. La [declaración CC0](https://creativecommons.org/publicdomain/zero/1.0/) no implica respaldo ni garantía del autor.

La selección/normalización se ofrece bajo CC BY-SA 4.0, separada de la licencia del código. Las licencias y créditos por recurso se mantienen. No se contrataron servicios, crearon cuentas o usaron credenciales, datos personales o APIs privadas.

## Exclusiones deliberadas

Algunos registros oficiales no concordaban suficientemente con sus ilustraciones; no se incorporaron para alcanzar una cifra:

- 83: texto de codos pegados al cuerpo, pero imagen con codos abiertos.
- 167: instrucciones en suelo y medio con pantorrillas apoyadas sobre banco.
- 301: título a 45°, texto que termina horizontal y gráfico alineado con soporte inclinado.
- 377: texto sujetándose a un banco y gráficos tumbado en suelo.
- 394: texto de barra/agarre amplio y medios con asa cerrada.
- 576: texto de flexión lateral de pie con peso y gráficos de abdominal cruzado tumbado.
- 1392: texto de Good Morning con manos en caderas, pero imágenes con barra cargada.
- 348: el texto ES solamente incluye posición inicial. No se completó automáticamente.

La selección de fuentes y coherencia visual no sustituyen revisión profesional. Los originales pueden contener afirmaciones de entrenamiento del proveedor que aún requieren revisión. El servidor sigue devolviendo `education_only_professional_review_pending`, `clinical_approval=false`, `can_activate_training=false`. No se habilita el motor de sesiones, aunque un usuario haya guardado preferencias.

## Pruebas y límites

**167 pruebas de catálogo y API aprobadas** en 0,96 s. Incluyen asociaciones concretas de traducción/medio, conteos, seis grupos, 44 URL y hashes únicos, separación de licencias y aislamiento respecto a almacenamiento privado. Se preservan los controles de host/ruta, HTML activo, licencia desconocida, integridad y bloqueo de uso del catálogo educativo como entrada aprobada de entrenamiento. Son pruebas de software, no una evaluación clínica ni una nueva prueba real de PostgreSQL.

Comparación adicional contra las 13 respuestas oficiales y los 28 PNG recién consultados: párrafos, hashes, autores, licencias y asociaciones coinciden. Las ocho fichas previas son idénticas a HEAD. `git diff --check` correcto. Datos ~105 KB; los 28 PNG nuevos suman aproximadamente 3,0 MB, solicitados individualmente desde el proveedor cuando la UI los necesita. La disponibilidad futura de medios remotos no está garantizada; debe mantenerse el estado de error honesto y el enlace a la fuente, sin sustituirlos por otro ejercicio.

Evidencia temporal de consulta/inspección: `/tmp/roxy-fitness-expand-20260910`. Archivos duraderos: catálogo JSON, validador y pruebas. Sin cambios en navegación, rutas compartidas, cuentas, datos públicos, Trading o el prototipo existente. No se afirma verificación móvil ni despliegue en este bloque.
