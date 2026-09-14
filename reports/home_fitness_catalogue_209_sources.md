# Home209 — catálogo real y fuentes de variedad

Fecha de revisión: 14/09/2026. Investigación e implementación local; sin publicación, contratación, descarga de vídeos ni cambios a datos personales. Avatar y Runway siguen pausados.

## Qué existía realmente

- Biblioteca wger: 21 fichas, 19 en español y 2 en inglés; 44 ilustraciones originales verificadas anteriormente. Seis grupos musculares: brazos6, pecho4, piernas4, hombros3, espalda3, abdomen1.
- Guías NHS: 3 programas con 16 movimientos (fuerza7, equilibrio5, flexibilidad4). Las 16 indicaciones no incluyen las 21 fichas wger: son conjuntos distintos, no 16 ejercicios totales.
- Calistenia ya representada parcialmente por dominadas supinas y fondos entre bancos en wger. No había clases de yoga, Pilates ni cardio en estas colecciones.
- Cuatro fichas wger tienen material sin confirmar: Butterfly, Curl de piernas tumbado, Curl femoral sentado y Remo en T. Vacío no significa que se puedan hacer sin equipo.
- No existe elegibilidad individual ni prescripción basada en edad/peso; el backend de agenda207 sólo admite las tres guías originales.

## Implementación209 de descubrimiento

Nuevo catálogo independiente `data/home_fitness_classes_209.json`, lector `roxy_os/fitness/classes.py` y ruta autenticada `GET /api/fitness/v1/classes`. Devuelve 18 recursos: 15 clases completas publicadas por NHS e impartidas por InstructorLive, y 3 demostraciones de técnica de Mayo Clinic. Todas abren la página original; títulos y descripciones editoriales en español, originales en inglés. No se ha reproducido cada vídeo completo para verificar disponibilidad de reproducción, idioma de cada pista o técnica clínica. Las páginas y sus datos descriptivos sí se comprobaron.

El lector verifica firma SHA256 del directorio revisado, identidades y URLs exactas, fechas, tipos, capacidades desactivadas, metadatos desconocidos y ausencia de embeds. Falla explícitamente503 si falta o cambia el catálogo; nunca sustituye el fallo por una lista vacía satisfactoria. No lee PostgreSQL ni llama a proveedores. La autenticación y caché privada de Home se conservan.

| Recurso real | Modalidad | Formato | Duración publicada | Fuente original |
| --- | --- | --- | --- | --- |
| Yoga Vinyasa: movimiento y respiración | yoga | Clase | 50 min | [NHS](https://www.nhs.uk/live-well/exercise/pilates-and-yoga/yoga-with-lj/) |
| Pilates desde las bases | pilates | Clase | 45 min | [NHS](https://www.nhs.uk/live-well/exercise/pilates-and-yoga/pilates-for-beginners/) |
| Pilates: continúa practicando | pilates | Clase | 45 min | [NHS](https://www.nhs.uk/live-well/exercise/pilates-and-yoga/pyjama-pilates/) |
| Pilates con apoyo de una silla | pilates | Clase | ≈30 min | [NHS](https://www.nhs.uk/live-well/exercise/pilates-and-yoga/chair-based-pilates-exercise-video/) |
| Cardio: aeróbicos para comenzar | cardio | Clase | 45 min | [NHS](https://www.nhs.uk/live-well/exercise/aerobic-exercises/aerobics-for-beginners/) |
| Activa tu mañana | cardio | Clase | 45 min | [NHS](https://www.nhs.uk/live-well/exercise/aerobic-exercises/wake-up-workout/) |
| Baile: La Bomba | cardio | Clase | 45 min | [NHS](https://www.nhs.uk/live-well/exercise/aerobic-exercises/dance-la-bomba/) |
| Danza del vientre para comenzar | cardio | Clase | 45 min | [NHS](https://www.nhs.uk/live-well/exercise/aerobic-exercises/belly-dancing-for-beginners/) |
| Abdomen en 10 minutos | strength | Clase | 10 min | [NHS](https://www.nhs.uk/live-well/exercise/strength-and-resistance/body-blast-abs/) |
| Brazos en 10 minutos | strength | Clase | 10 min | [NHS](https://www.nhs.uk/live-well/exercise/strength-and-resistance/body-blast-arms/) |
| Piernas en 10 minutos | strength | Clase | 10 min | [NHS](https://www.nhs.uk/live-well/exercise/strength-and-resistance/body-blast-legs/) |
| Glúteos y caderas en 10 minutos | strength | Clase | 10 min | [NHS](https://www.nhs.uk/live-well/exercise/strength-and-resistance/body-blast-bums/) |
| Oblicuos en 10 minutos | strength | Clase | 10 min | [NHS](https://www.nhs.uk/live-well/exercise/strength-and-resistance/body-blast-waist/) |
| Preparar el cuerpo: calentamiento | mobility | Clase | Sin confirmar | [NHS](https://www.nhs.uk/live-well/exercise/strength-and-resistance/body-blast-warm-up/) |
| Vuelta a la calma y estiramientos | mobility | Clase | 10 min | [NHS](https://www.nhs.uk/live-well/exercise/strength-and-resistance/body-blast-cool-down/) |
| Sentadilla con peso corporal | calisthenics | Demostración | Sin confirmar | [Mayo Clinic](https://www.mayoclinic.org/healthy-lifestyle/fitness/multimedia/squat/vid-20084663) |
| Flexión de brazos modificada | calisthenics | Demostración | Sin confirmar | [Mayo Clinic](https://www.mayoclinic.org/healthy-lifestyle/fitness/multimedia/modified-pushup/vid-20084674) |
| Subir a un escalón | calisthenics | Demostración | Sin confirmar | [Mayo Clinic](https://www.mayoclinic.org/healthy-lifestyle/fitness/multimedia/step-up/vid-20084661) |

Las tres demostraciones de Mayo son ejercicios con resistencia del propio cuerpo según sus fuentes. Se etiquetan como calistenia y fuerza, sin convertirlas en clases completas, fijar duración, series, carga o nivel personal. Subir al escalón requiere un escalón o plataforma.

El calentamiento NHS tiene una discrepancia real: cabecera5min y descripción10min; `duration_minutes:null` y nota visible. Yoga Vinyasa indica50min en su cabecera específica, a pesar del texto genérico10–45 del portal. Pilates con silla indica aproximadamente30min y combina ejercicios de pie/sentados: no se promete que toda la sesión sea sentada o de bajo impacto. Pilates Pyjama pide experiencia básica y los cinco bloques de fuerza10min requieren base física. Ninguno se etiqueta automáticamente como principiante.

`equipment_complete:false` en todas las clases: sólo se incluyen materiales mencionados explícitamente, con requerido/opcional. No se puede filtrar este conjunto como «sin material» por vacío. No se añaden franjas de edad, límites de peso, ausencia de saltos ni calificación terapéutica sin evidencia.

## Embeds y derechos

`embed_url:null` y `media_mode:external_link` en los18recursos. No se descargó, modificó, dobló ni realojó ningún vídeo. No hace falta ampliar CSP para esta implementación.

Los [términos NHS](https://www.nhs.uk/our-policies/terms-and-conditions/) distinguen contenido bajo OGL de material de terceros y datos/imágenes de personas; no conceden automáticamente derechos sobre estas grabaciones. Su [lista de exclusiones](https://www.nhs.uk/our-policies/terms-and-conditions/content-not-licensed-for-re-use/) advierte que puede no ser exhaustiva. La presencia del reproductor en una página no autoriza a copiarlo a Home. Los metadatos editoriales derivados incluyen atribución OGL independiente del permiso sobre vídeo.

Existe un [programa oficial de sindicación](https://www.api.gov.uk/nd/nhs-syndicated-content-rest-apis/) que incluye vídeo. El [acuerdo de conexión](https://digital.nhs.uk/developer/guides-and-documentation/online-connection-agreement) limita el ámbito de sus usuarios, lengua y uso en vivo. No se ha contratado ni aprobado esta integración para Roxy. El enlace original sirve ahora; no se propone aceptar esos términos automáticamente.

## Adecuación personal: siguiente trabajo real

El catálogo amplía descubrimiento, pero no es un motor de entrenamiento personalizado. Lugar, material, frecuencia, tiempo, experiencia, movilidad, preferencias y restricciones necesitan decidir la selección y progresión. Edad y peso no bastan para asignar ejercicios o cargas. No asignar todos los mayores a silla ni impedir actividad sólo por peso. El [NIDDK](https://www.niddk.nih.gov/health-information/weight-management/staying-active-at-any-size) enfatiza actividad ajustada a condición y objetivos, progresión gradual y equipo adecuado; los [criterios NHS para mayores](https://www.nhs.uk/live-well/exercise/physical-activity-guidelines-older-adults/) incluyen fuerza, equilibrio y flexibilidad. No se han convertido estas orientaciones generales en prescripciones automáticas.

## Verificación

- 153 pruebas Python aprobadas en conjunto: `tests/test_roxy_home_fitness_classes.py`, `tests/test_roxy_home_fitness_catalog.py` y `tests/test_roxy_home_fitness_programs.py`.
- Nuevas pruebas cubren identidad y caché privada, ausencia de lecturas de almacenamiento personal, fuente corrupta503, inyección/URLs cambiadas, rechazo de capacidades o hechos sin revisión, material/duración desconocidos y separación clase/técnica.
- Las 21fichas y 3guías originales siguen presentes e íntegras. El nuevo endpoint no amplía los IDs aceptados por la agenda207 ni inventa un plan clínico.
- UI unificada, COPY de Docker, allowlist de demo y revisión visual están a cargo de la tarea principal; este informe no los da por completados.
