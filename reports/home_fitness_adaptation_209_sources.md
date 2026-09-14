# Roxy Home 209 — fuentes y reglas para ampliar Ejercicio

Verificación: 2026-09-14. Informe de diseño y evidencia; no cambia código ni acredita una evaluación clínica. Alcance solicitado: variedad real de ejercicios y selección según necesidades, edad, peso, lugar, equipo, tiempo y experiencia.

## Conclusión para la implementación

Se puede ampliar ahora la biblioteca y ofrecer filtros explicables por modalidad, lugar, equipo, nivel y duración verificados. La selección personalizada debe incorporar capacidad y preferencias; edad y peso no bastan para elegir una carga, intensidad o variante. Separar tres funciones visibles: **explorar una guía**, **organizarla en el calendario** y **recibir una rutina adaptada con progresión**. La última aún no está implementada en el producto inspeccionado.

El bloqueo `content_review_required` que hoy existe en `roxy_os/fitness/domain.py` es una decisión explícita del producto. Las fuentes consultadas no establecen que todo catálogo educativo necesite autorización clínica. Sí sustentan que una guía pública o un vídeo no evalúan a un usuario concreto ni justifican prometer idoneidad personal, rehabilitación o resultados.

## Fuentes oficiales verificadas

| Fuente | Evidencia utilizable y límite |
| --- | --- |
| [OMS — Physical activity](https://www.who.int/news-room/fact-sheets/detail/physical-activity) y [guías de actividad física y sedentarismo](https://www.who.int/publications/i/item/9789240015128) | Las recomendaciones distinguen grupos de edad y situaciones como embarazo, discapacidad y enfermedades crónicas. Cualquier cantidad de actividad puede aportar beneficios; todo movimiento cuenta. Son recomendaciones poblacionales, no una fórmula que produzca una sesión individual con peso y edad. |
| [CDC — actividad en adultos](https://www.cdc.gov/physical-activity-basics/adding-adults/what-counts.html) | Referencia general de actividad aeróbica y fortalecimiento; la fuerza puede trabajarse con peso corporal, bandas o pesas. La dificultad percibida depende de la persona. Sirve para clasificar variedad y explicar esfuerzo, sin inferir automáticamente intensidad desde el nombre del ejercicio. |
| [CDC — mayores de 65 años](https://www.cdc.gov/physical-activity-basics/adding-older-adults/what-counts.html) | Combinar actividad aeróbica, fuerza y equilibrio. Como orientación poblacional: 150 minutos moderados semanales o equivalente, y fuerza al menos dos días. Las actividades deben corresponder a capacidades y condiciones. Una persona mayor entrenada no debe recibir automáticamente solo ejercicios de silla. |
| [CDC — niños y adolescentes](https://www.cdc.gov/physical-activity-education/guidelines/index.html) | Para edades 6–17, actividades variadas, apropiadas para la edad y agradables; referencia de 60 minutos diarios con componentes aeróbicos, musculares y óseos. Este grupo requiere un flujo distinto al adulto, no reutilizar objetivos de pérdida de peso o cargas de adultos. |
| [NIDDK — Staying Active at Any Size](https://www.niddk.nih.gov/health-information/weight-management/staying-active-at-any-size) | Se puede practicar actividad con distintos tamaños corporales. Propone empezar con cantidades manejables, progresar gradualmente y elegir actividades agradables. Opciones como caminar, actividades acuáticas, fuerza y movimiento mente-cuerpo permiten variedad. La capacidad y las molestias importan para adaptar actividades. No presenta umbrales de peso que autoricen o prohíban modalidades. |
| [NCCIH — Yoga: Effectiveness and Safety](https://www.nccih.nih.gov/health/yoga-effectiveness-and-safety) | Yoga incluye prácticas suaves y exigentes; no es sinónimo de baja intensidad. Recomienda instructor cualificado, evitar prácticas extremas al comenzar y adaptar ante necesidades individuales. Embarazo, problemas de equilibrio y determinadas condiciones pueden requerir modificaciones. Un vídeo de yoga no prueba que toda postura sea adecuada para todos. |
| [NHS — Pilates and yoga exercise videos](https://www.nhs.uk/live-well/exercise/pilates-and-yoga/) | Ofrece clases de principiantes, yoga, Pilates y opciones en silla; también contenido para situaciones específicas. Es evidencia de disponibilidad de clases, no licencia automática de reutilización audiovisual ni autorización para prescribir contenidos por diagnóstico. |

Las siguientes reglas son una **propuesta de ingeniería derivada** de esa evidencia; no son un protocolo publicado por esas organizaciones.

## Contrato de selección determinista

1. **Edad conocida.** Mantener `null` como desconocida. Los rangos adultos existentes pueden seleccionar el contexto de orientación; no producir límites de carga arbitrarios por cumpleaños. En 65+ mostrar equilibrio entre las opciones y preguntar por apoyo/movilidad. Un usuario menor necesita una colección y experiencia familiar separadas; no etiquetar la actual como apta para todas las edades.
2. **Peso opcional y privado.** Usarlo, con unidad y fecha, para seguimiento elegido por la persona. No convertir peso, altura o IMC en una calificación de capacidad, una prohibición de yoga o un número de kilos a levantar. La selección debe seguir funcionando sin pesarse. No calcular calorías quemadas únicamente con el peso y un nombre de movimiento.
3. **Lugar y equipo real.** La categoría gimnasio no implica disponer de todas las máquinas. Una guía solo aparece como compatible cuando se confirmó su equipo obligatorio; silla/pared deben figurar como apoyos, no como material implícito. No ofrecer dominadas si no existe barra adecuada ni intercambiar máquinas como si fueran equivalentes.
4. **Experiencia y capacidad.** Preguntar por experiencia en la modalidad, no solo experiencia global. Añadir preferencias explícitas como `sin saltos`, `evitar suelo`, `prefiero silla` y `quiero apoyo para equilibrio`. Filtrar requisitos de movimiento documentados. Un valor desconocido no se interpreta como capacidad confirmada. No diagnosticar a partir de estas respuestas.
5. **Tiempo y frecuencia.** Encajar sesiones completas verificadas en ventanas disponibles. Incluir preparación, descansos y cierre cuando se conocen; no reducir a la fuerza una clase de 45 minutos para anunciarla como sesión de 10. `duration = null` permanece desconocida. La frecuencia solicitada organiza el calendario; no debe confundirse con la dosis recomendada por la fuente.
6. **Variedad sin selección aleatoria.** Clasificar calistenia/peso corporal, fuerza con equipo, cardio, yoga, Pilates, movilidad/flexibilidad, equilibrio y opciones con apoyo. Un movimiento puede tener varias etiquetas sin contarse varias veces como contenido único. Aplicar requisitos obligatorios primero, después ordenar por gustos, objetivo y variedad. Explicar coincidencias: «En casa · sin material · iniciación · 15 minutos».
7. **Objetivos realistas.** Mostrar que una actividad contribuye a fuerza, movilidad, resistencia o hábito cuando la fuente lo respalda. No prometer que una sesión garantiza adelgazamiento, cura dolor o trata una patología. La meta de peso no puede decidir automáticamente dosis o intensidad.
8. **Resultados observados.** Separar sesiones planificadas, realizadas por declaración, repeticiones/carga registradas, tiempo real, dificultad percibida y mediciones corporales. Nunca generar resultados al abrir una guía ni convertir agenda en calorías. Apple Watch, cuando exista integración, será una fuente independiente con origen, fecha y permisos explícitos; hoy no está conectado por esta propuesta.

## Qué debe contener cada ficha

- Identidad y variante exactas; modalidad, patrón de movimiento, equipo y apoyos necesarios.
- Instrucciones claras en español: preparación, ejecución, respiración, final y errores frecuentes documentados.
- Dosis de la fuente o plantilla revisada, con descansos/transiciones solo cuando estén establecidos.
- Alternativas verificadas para requisitos distintos; no improvisar una sustitución para una lesión.
- Demostración que corresponda al movimiento exacto, con autor, derechos y idioma conocidos. Una imagen decorativa o animación genérica no reemplaza una demostración técnica.
- Fuente, fecha de comprobación, nivel de revisión y explicación de por qué coincide con las preferencias.

## Estado del esquema inspeccionado y alcance viable hoy

`roxy_os/fitness/schemas.py` ya recoge rango de edad adulto, objetivos, experiencia básica, lugares, equipo, disponibilidad, minutos por sesión y traslado, zona horaria y preferencias de unidades. No guarda peso, altura, mediciones, capacidades, modalidad preferida, lesiones ni conexión a un reloj. `programs.py` contiene tres guías NHS con 16 movimientos y un contrato de lectura/organización; el consentimiento y la agenda privados no convierten esas guías en un entrenador adaptativo.

Alcance inmediato: ampliar fichas y clases con fuentes verificadas, hacer visibles modalidades y cantidades reales, agregar filtros por datos confirmados, conservar el lector en español y conectar solo contenido compatible con el contrato de agenda existente. No hace falta esperar al avatar para estas mejoras. Si el contenido añadido vive como enlace o clase externa, identificarlo así y no contarlo como ejercicio guiado nativo de Roxy.

Antes de activar planes adaptativos con progresión, completar metadatos, capacidades, reglas de carga/descanso y plantillas comprobadas. Versionar y probar las reglas con perfiles contrastantes: principiante en casa sin equipo, usuario experimentado en gimnasio, persona de 65+ que solicita apoyo, disponibilidad breve, equipo insuficiente, edad desconocida y persona que no desea registrar peso. Deben producir explicaciones verificables o reconocer falta de opciones, nunca inventar compatibilidad.

## Auditoría independiente del diseño 209 propuesto

El diseño comunicado conserva las 21 fichas ilustradas de `data/home_fitness_catalog.json` y las tres guías que contienen 16 movimientos, y añade clases NHS como recursos externos de exploración. Es una ampliación coherente si la interfaz conserva estas diferencias:

| Aspecto | Criterio de aceptación |
| --- | --- |
| Cantidades | Mostrar por separado fichas, guías y clases. No sumar 21 fichas + 16 pasos + clases para anunciar un total de ejercicios únicos. |
| Modalidad | Yoga, Pilates, cardio y fuerza deben tener recursos reales. «Calistenia» puede ser una colección de variantes con peso corporal verificadas, no una etiqueta de marketing aplicada a todo el catálogo. |
| Duración | Filtrar solo valores confirmados. Una ficha individual no tiene duración de sesión; un dato desconocido no debe pasar el filtro «hasta 15 minutos». |
| Idioma | Distinguir la ficha escrita en español del vídeo externo en inglés. El filtro «audio en español» no debe incluir vídeos ingleses por tener título traducido. |
| Material | «Sin material» exige evidencia positiva. `equipment = null`, lista vacía y metadatos incompletos no equivalen a peso corporal sin apoyos. |
| Acción principal | «Ver clase en NHS» comunica navegación externa. «Abrir guía» y «Ver ejercicio» distinguen experiencias que sí ocurren dentro de Roxy. No decir «Empezar mi entrenamiento personalizado» para un enlace externo. |
| Personalización | Usar «Coincide con tus filtros» para coincidencias literales. No decir «Adecuado para tu edad/peso» ni «Roxy lo adaptó a ti» sin reglas y datos suficientes. |
| Programación | No habilitar el guardado privado de IDs de clases externas en un contrato que solo admite las tres guías. Si el puente todavía no existe, el botón no debe simular guardado. |
| Filtros combinados | Intersección explícita, recuento actualizado, estado vacío y «Quitar filtros». No reintroducir resultados incompatibles para evitar una lista vacía. |

La presencia de clases externas amplía la variedad visible, pero por sí sola no completa el entrenador detallado y personalizado solicitado. La pantalla debe enseñar qué existe ahora y permitir llegar al contenido con una acción; la explicación técnica de revisión o licencias puede estar en información secundaria, sin llenar el recorrido principal de advertencias.

## Imágenes de calistenia reutilizables: hallazgo concreto

[Wger](https://wger.readthedocs.io/en/stable/) y su [API pública](https://github.com/wger-project/docs/blob/master/docs/api/api.rst) ofrecen datos de ejercicios con licencias Creative Commons por recurso; el software y los datos tienen licencias diferentes. Roxy ya conserva esa separación en su catálogo. Es la vía más compatible con la implementación actual para ampliar contenido ilustrado sin una contratación de proveedor.

El [proyecto original Everkinetic](https://github.com/everkinetic/data) contiene [datos de ejercicios](https://github.com/everkinetic/data/blob/main/exercises.json) y declara [CC BY-SA 4.0](https://github.com/everkinetic/data/blob/main/LICENSE.md). La lectura del JSON público verificó variantes con dos ilustraciones referenciadas: `push-ups` (ID 340), `pull-ups` (374), `chin-ups` (380), `side-plank` (456) y `crunches` (1043). Son candidatos para revisar, no incorporaciones realizadas. No se descargaron imágenes ni se verificó visualmente su técnica en esta tarea. La licencia directa actual del proyecto no debe sobrescribir la licencia individual preservada de una imagen distribuida antes por Wger.

La fuente tiene metadatos incompletos: `push-up-feet-elevated` aparece con equipo nulo; `bench-dips` dice solamente `body` pese al banco de la variante. Esto confirma que un filtro de equipo necesita revisión y no solo confiar en la etiqueta del proveedor. No confundir esas ilustraciones con demostraciones audiovisuales ni con validación profesional.

Para las clases NHS, [sus términos](https://www.nhs.uk/our-policies/terms-and-conditions/) y [exclusiones audiovisuales](https://www.nhs.uk/our-policies/terms-and-conditions/content-not-licensed-for-re-use/) advierten que parte de las imágenes y vídeos no está cubierta por la licencia general. En 209, enlazar a la página oficial permite explorar la clase sin afirmar que Roxy posee o produjo ese vídeo. No se ha verificado autorización para descargar, doblar o redistribuir estos vídeos dentro de Roxy.
