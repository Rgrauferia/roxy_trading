# Mascotas: desaparición del recetario de Luna — 2026-09-08

Estado: correcciones locales verificadas; este informe no afirma despliegue ni
validación veterinaria individual. No se modificaron perfiles, fotos, historial,
recetas guardadas ni carrito de producción.

## Causa reproducida

El cuestionario ofrece `Ninguna diagnosticada` como respuesta de salud para
Ferret, perros, gatos y otros grupos, y `Ninguna observada` para algunos animales
acuáticos/invertebrados. El cribado médico exacto añadido anteriormente aceptaba
`Ninguna`, pero omitía esas dos respuestas reales del formulario.

Así, un perfil adulto sin enfermedad declarada quedaba marcado como restringido,
su catálogo personalizado pasaba de ocho preparaciones a cero y la capacidad
`recipes:false` ocultaba toda la pestaña. El mismo error bloqueaba productos
alimentarios. La revisión de la interfaz pública por la tarea principal confirmó
Luna adulta, Ferret, alergias `Ninguna conocida` y salud `Ninguna diagnosticada`;
el formulario se cerró sin guardar. No faltaban las ocho recetas del catálogo.

## Cambios

- Añadidas sólo las dos respuestas negativas exactas. `Ninguna salvo diabetes`,
  negativas acompañadas de otra condición, dieta veterinaria, indicaciones del
  veterinario y alergias indeterminadas continúan bloqueando.
- Separados `recipe_tab` (navegación) y `recipes` / `recipe_import` (disponibilidad).
  Las especies con preparaciones conservan la pestaña con explicación y acceso a
  editar el perfil si necesitan revisión. No se muestran instrucciones ni acciones
  de cocinar/importar/Compra para el perfil restringido.
- Peces, serpientes y otros grupos especialistas conservan Información y cuidados,
  sin una pestaña de recetas inventadas. Aves desconocidas/nectarívoras tampoco
  reciben recetas de otra especie.
- Las opciones seleccionadas del cuestionario exponen `aria-pressed`.
- Las ocho preparaciones existentes de Ferret conservan sus fotos individuales.
  El horneado de pato ahora indica temperatura del horno, punto interno y uso de
  termómetro. Carne molida: punto interno preciso; no se usa el color como prueba.
  Todas incluyen conservación y distinguen lote de preparación de ración animal.
- La ficha aclara que son preparaciones propias de Roxy apoyadas en orientación,
  no recetas certificadas por las fuentes ni una dieta completa formulada para Luna.

## Verificación local

- 123 pruebas de disponibilidad, importación, seguridad de productos y calidad de
  recetas: aprobadas (3.11 s), después del último cambio de pasos/fuentes.
- Primera pasada de disponibilidad/importación/calidad/demo-readiness:
  246 aprobadas (41.60 s), antes de la última mejora de pasos/fuentes.
- `node --check assets/roxy_list.js` y `git diff --check`: correctos.
- El test de API utiliza sólo un hogar temporal: Bella y Luna conservadas,
  ocho recetas de Luna con ocho rutas de foto distintas; perfil y archivo sin
  mutación por consultar recomendaciones. Se comprueba que una restricción real
  no borra una receta guardada y sí impide cocinarla/enviarla a Compra.
- Matriz: respuestas de salud reales de todos los grupos; ocho perfiles de
  preparaciones; nueve perfiles especialistas; etapas sin confirmar y crías;
  enfermedad, dieta prescrita, indicación veterinaria y alergia indeterminada.
- Las fotos no se regeneraron ni sustituyeron: se comprobó presencia de activos y
  asociación única. La comprobación visual pública posterior pertenece a la tarea
  principal; no confundir pruebas sintéticas con revisión clínica o datos reales.

## Fuentes y límites

Consultadas el 8 de septiembre de 2026:

- [NC State Veterinary Hospital: Caring for Your Pet Ferret](https://hospital.cvm.ncsu.edu/services/small-animals/nutrition/caring-for-your-pet-ferret/):
  orientación de alimentación completa para Ferret; admite pequeñas cantidades
  de carne cocida sin sal y menciona clara de huevo cocida entre los premios.
  No valida nuestras ocho recetas, sus lotes ni la cantidad individual para Luna.
- [USDA FSIS: Leftovers and Food Safety](https://www.fsis.usda.gov/food-safety/safe-food-handling-and-preparation/food-safety-basics/leftovers-and-food-safety):
  temperaturas internas para aves y carnes molidas; refrigeración rápida, dos
  horas fuera y una hora en ambiente caluroso. Es higiene alimentaria, no nutrición
  veterinaria.
- [USDA FSIS: Duck and Goose from Farm to Table](https://www.fsis.usda.gov/food-safety/safe-food-handling-and-preparation/poultry/duck-and-goose-farm-table):
  piezas de pato a 165 °F internos, medida con termómetro; el color no demuestra
  seguridad.
- [USDA FSIS: temperatura mínima del horno](https://ask.fsis.usda.gov/article/What-oven-temperature-is-safe-for-cooking-meat-and-poultry):
  mínimo 325 °F para carnes y aves. Los 190 °C de nuestra preparación no se
  presentan como una receta de USDA ni un tiempo de cocción universal.
- [Oxbow Animal Health: Ferret Care Guide](https://oxbowanimalhealth.com/wp-content/uploads/2023/10/Ferret-Care-Guide-Jul-2022.pdf):
  enlace existente comprobado; su orientación incluye carne y huevos cocidos
  como alimentos suplementarios. Tampoco prescribe la cantidad para Luna ni
  certifica nuestras instrucciones. No se extrapoló su mención de alimentos
  crudos/deshidratados a una receta nueva sin un protocolo validado.

No se amplió el catálogo con dietas completas, deshidratados o recetas clínicas
sin evidencia. El acceso a fuentes no equivale a afiliación con veterinarias ni a
licencia para reproducir sus recetas. La variedad de comida completa debe venir
de fórmulas apropiadas y de un plan profesional cuando corresponda.
