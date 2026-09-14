# Roxy Home — recorrido y preguntas de bienvenida

Revisión del 14 de septiembre de 2026. Se recuperó el trabajo existente; no se
reescribió el prototipo ni se cambió el registro publicado.

## Abrir las dos experiencias

- Historia interactiva preparada: http://127.0.0.1:8796/
- Preguntas reales de bienvenida, con perfil ficticio local: http://127.0.0.1:8768/lista#hoy

Estas vistas funcionan en este ordenador mientras sus servidores estén abiertos.
La primera personaliza sólo el prototipo; la segunda utiliza el código actual de
Home con datos temporales y proveedores bloqueados. Ninguna cambia el hogar real.

## Qué ocurre hoy al crear una cuenta pública

1. Nombre, usuario, contraseña de al menos12caracteres y repetición.
2. Confirmar mayoría de edad, lectura de privacidad y límites de la prueba;
   comprobación de Cloudflare.
3. Guardar los ocho códigos de respaldo para recuperar la cuenta.
4. Completar la bienvenida culinaria y revisar antes de guardar.

| Pantalla de cocina | Preguntas existentes |
| --- | --- |
| Tus sabores | Idioma español/inglés; país o región de origen opcional; un poco de todo, sabores del origen o cocinas seleccionadas. |
| Tus gustos | Dieta o «Prefiero no indicarlo»; alimentos favoritos opcionales; ingredientes que prefiere evitar; alergias opcionales con posibilidad de no declararlas. |
| Tu ritmo | Tiempo orientativo disponible o sin límite; experiencia en cocina o no indicarla. |
| Tu ficha | Resumen completo y consentimiento para guardar las preferencias privadas. |

El registro actual no pide una dirección postal, tarjeta bancaria ni datos de
cada mascota o habitación. Los datos propios de un módulo se piden al usarlo.
La bienvenida culinaria publicada todavía es obligatoria para todos los nuevos
miembros, incluso si su interés principal es otro módulo; la selección inicial
de módulos del prototipo aún no controla ese recorrido.

## La historia interactiva que ya estaba trabajada

Ocho capítulos de decisión:

1. **Cómo te acompaña Roxy:** cercana y natural, breve y práctica o explicación de cada paso.
2. **Su apariencia:** Clásica, Casual o Acuarela.
3. **Recetas:** organizar la semana, descubrir qué cocinar o dejarlo para después.
4. **Mascotas:** perro, otros animales o ninguna mascota. El ejemplo de perro está identificado como ficticio.
5. **Jardín:** si tiene plantas y quiere incluir su cuidado.
6. **Renueva:** explica fotos del espacio, ideas, prioridades y presupuesto; añadir u omitir.
7. **Nexo:** explica círculo, lugares, clima y permisos; añadir u omitir sin activar GPS ni invitar personas.
8. **Ambiente:** Clásico, Olivo, Costa o Terracota; revisión e inicio con los módulos elegidos.

Incluye cuatro clips ya generados; el video se detiene para esperar decisiones.
Renueva y Nexo usan escenas ilustradas fijas. Casual y Acuarela son retratos,
sin videos faciales propios. La narración del prototipo usa voz opcional del
dispositivo; la voz oficial de Home no está conectada a este recorrido.
Los ajustes permiten volver a la historia, cambiar apariencias, colores y módulos.

## Información de los módulos, cuando se configuran

| Módulo | Para qué sirve | Datos que sus formularios contemplan |
| --- | --- | --- |
| Recetas | Descubrir platos y organizar comidas/lista. | Idioma, preferencias culinarias, dieta, alimentos, alergias opcionales, tiempo y experiencia. |
| Mascotas | Organizar un perfil y cuidados por animal. | Cinco pasos: identidad y especie/raza/edad; salud y etapa; alimentación e indicaciones existentes; hábitat; rutinas y revisión. Las preguntas cambian con la especie. |
| Jardín | Identificar cada planta y organizar cuidados. | Cuatro pasos: foto/nombre/especie; lugar y luz; medio de cultivo/maceta/drenaje; ficha y revisión. |
| Renueva | Preparar cambios en un espacio. | Foto de habitación, nombre del proyecto, habitación/estilo, presupuesto, medidas, qué conservar y qué mejorar. Generación pagada excluida de la demo. |
| Nexo | Círculo, lugares y ubicación compartida. | Perfil y conexiones por invitación, lugares y permisos explícitos. La bienvenida no activa ubicación. |
| Compra | Lista de productos y cantidades. | Los artículos que la persona añade; no exige llenar un perfil adicional al registrarse. |
| Calendario | Eventos y recordatorios. | Evento, fecha/hora, duración, aviso, categoría y repetición; ubicación/notas/participantes cuando correspondan. |
| Ejercicios | Explorar material y preparar preferencias. | Banda de edad opcional, idioma/unidades, objetivo, disponibilidad, experiencia, lugares y equipo. El guardado público y los entrenamientos personalizados siguen pendientes. |

Los campos de esta tabla no son todos obligatorios ni se piden juntos al crear la
cuenta. No se completó ni guardó ningún perfil médico, de mascota o de ubicación
en esta revisión.

## Qué falta unir

- Conectar la historia y su selección de módulos a la cuenta real y al inicio público.
- Conciliar las apariencias del prototipo con las opciones reales de «Mi Roxy»;
  hoy son selecciones distintas.
- Añadir capítulos propios de Compra, Calendario y Ejercicios, y terminar las ramas
  detalladas que aún faltan. El prototipo contiene cinco módulos, no todo Home.
- Conectar la voz oficial de Home al recorrido bajo el alcance de acceso elegido.
- Completar la primera alta pública válida; la prueba local no sustituye Cloudflare.

## Evidencia de esta revisión

Runtime protegido del prototipo:28archivos íntegros;20pruebas de historia aprobadas,
incluidas2592combinaciones unitarias. Navegador: video welcome.mp4 conreadyState4,
playing y sinerror, después pausa en la decisión; apariencia, Recetas, ramas sin
mascotas/plantas, Renueva, Nexo y ambiente recorridos. Preguntas de cocina: cuatro
pantallas recorridas con datos ficticios/no declarados; no se pulsó Guardar.
Inicio final del prototipo verificado con Recetas y Nexo según las elecciones
del ejemplo; guardado únicamente en el prototipo del navegador. Se volvió a la
portada «Comenzar mi historia» y se conservaron las pestañas16y17 como entrega.
La bienvenida culinaria queda en el primer paso, sin guardar preferencias.
Los dos servidores se mantienen en127.0.0.1 para que Roberto pueda revisar.
Prototipo puerto8796; fixture Home puerto8768/PID63415, directorio temporal
`/var/folders/d9/j1tl468d4cd8y2zsrx53vj000000gn/T/roxy-login-qa-b0rdh7ed`.
No se usaron claves/proveedores ni se desplegó código por esta revisión.

Fuentes de implementación: `prototypes/roxy-cinema/README.md`, `src/story.ts`,
`src/Prototype.tsx`, `src/ModuleGuide.tsx`; `assets/roxy_recipe_onboarding.js`,
`assets/roxy_garden_guide.js`, `assets/roxy_fitness.js`, `assets/roxy_list.html`.
