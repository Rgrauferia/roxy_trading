# Roxy Home — procedencia de preparaciones de mascotas

Fecha: 2026-09-08. Evaluación local para el bloque 177; este informe no acredita
despliegue ni incorporación de recetas externas. Alcance del subbloque: módulo
nuevo de evaluación, pruebas y este informe. Catálogo, almacén, perfiles,
capacidades, fotos, JS/CSS y datos públicos no modificados por este subbloque.

## Resultado verificable

Las 57 preparaciones instaladas no tienen evidencia de una publicación original
que contenga sus mismos ingredientes, cantidades y pasos. Las 57 conservaban la
etiqueta `verified_veterinary_guidance`, que no acredita procedencia ni validación
de cada receta. El código de las ocho preparaciones de Ferret ya explicaba que
eran preparaciones propias de Roxy basadas en orientación general; ese aviso no
las convierte en recetas originales externas como solicita Roberto.

Inventario reproducido mediante `_pet_templates()` y `local_recipe_by_key()`:

| Evaluación | Filas |
| --- | ---: |
| Preparaciones locales (`treat` / `complement`) | 57 |
| Perro, incluyendo variantes del catálogo | 25 |
| Gato | 12 |
| Ferret | 8 |
| Conejo / cobaya / hámster / ave | 3 por grupo |
| Con alguna referencia general de especie o seguridad | 49 |
| Sin referencia adjunta | 8 |
| Con nombre, medidas y pasos estructuralmente presentes | 57 |
| Con original completo verificado | 0 |
| Autorizadas por el nuevo evaluador para cocinar desde una fuente | 0 |

Las 25 filas de perro no son 25 recetas distintas visibles para cada perfil:
incluyen variantes históricas por raza. El evaluador no altera esa selección.
«Estructuralmente presente» no implica receta original, ingredientes completos
según fuente, suficiencia nutricional ni receta adecuada para un animal concreto.

## Fuentes oficiales consultadas y límites

Se consultaron páginas publicadas por sus fabricantes y veterinarios; no se
extrajeron recetas completas para el catálogo ni se descargaron videos/fotos.
Los enlaces permiten revisar la publicación en origen. No son una autorización
para reproducir texto, imágenes o contenidos dentro del producto comercial.

| Fuente | Evidencia encontrada | Límite para Roxy |
| --- | --- | --- |
| [Hill's: premios para perros](https://www.hillspet.com/dog-care/nutrition-feeding/healthy-homemade-dog-treats) | Preparaciones publicadas por el fabricante a partir de su alimento, con instrucciones y rendimiento aproximado. La página identifica autoría y revisión editorial veterinaria. | No coincide con las 25 filas locales. Requiere conservar forma del alimento, exclusiones, instrucciones y advertencias originales; no prueba idoneidad para Bella ni otra mascota. |
| [Hill's: premios para gatos](https://www.hillspet.com/cat-care/nutrition-feeding/healthy-homemade-cat-treats) | Varias preparaciones específicas con alimento del fabricante, cantidades e instrucciones. | No acredita la procedencia de las 12 recetas actuales. No trasladar recetas de gato a Ferret ni convertir un rendimiento aproximado en ración individual. |
| [Oxbow: uso de restos de heno](https://oxbowanimalhealth.com/blog/how-to-use-hay-fines-for-diy-snacks/) | Publicación original con galletas, bocados de banana y pimientos rellenos. | No integrada ni asignada automáticamente a especies. La instrucción de horno dice «325» sin unidad explícita; algunas medidas son vagas. Un parámetro de búsqueda `_species=ferrets` no demuestra compatibilidad con Ferret. |
| [VCA: alimentación de Ferret](https://vcahospitals.com/know-your-pet/feeding-ferrets) | Guía veterinaria de alimentación y premios ocasionales. | No contiene las ocho recetas locales, sus lotes, tiempos, temperaturas ni raciones. Se clasifica como referencia general. |
| [Oxbow: guía de Ferret](https://oxbowanimalhealth.com/wp-content/uploads/2023/10/Ferret-Care-Guide-Jul-2022.pdf) | Orientación del fabricante sobre cuidado y alimentación; resultado indexado confirma ejemplos generales de complementos animales. | No se presenta como fuente original de ninguna de las ocho preparaciones. No se volvió a descargar el PDF. |
| [NC State: cuidado de Ferret](https://hospital.cvm.ncsu.edu/services/small-animals/nutrition/caring-for-your-pet-ferret/) | La búsqueda oficial devuelve orientación alimentaria y ejemplos de premios. | La apertura de la página devolvió error en esta sesión; no se afirma verificación íntegra renovada. En el catálogo es referencia general, no original de receta. |

No se encontró, dentro de esta búsqueda acotada, una fuente oficial original con
las ocho recetas de Ferret y sus pasos/medidas completos. No se afirma que no
exista ninguna publicación de recetas para esa especie. TheMealDB no se usa como
fuente de recetas para mascotas y su posible licencia humana no cubre este vacío.

## Reproducción y permisos

[Los términos de Hill's](https://www.hillspet.com/terms-and-conditions), actualizados
en agosto de 2025, describen acceso personal/no comercial y una licencia limitada;
no se identificó una autorización de sindicación comercial para Roxy. Las páginas
mantienen reserva de derechos. Por eso las publicaciones se registran como enlaces
externos pendientes, sin copiar sus pasos ni sus imágenes al catálogo.

[Los términos de Oxbow](https://oxbowanimalhealth.com/terms-of-use/) consultados
identifican condiciones del sitio, y la página de recetas mantiene reserva de
derechos. No se identificó permiso expreso para incorporar esas recetas a Roxy.
La ausencia de una prohibición encontrada no se interpreta como licencia.
No se enviaron solicitudes a terceros, no se aceptaron acuerdos y no se pagó.

## Contrato de integración

Archivo nuevo: `roxy_os/home_recipe_provenance.py`.

1. `assess_recipe_provenance(recipe)` devuelve un objeto JSON sin modificar la
   receta. Evalúa `status`, `origin`, `source_role`, `label`, `message`, `sources`,
   `original_source_url`, `original_recipe_verified`, `can_present_as_original`,
   `content_reuse_authorized`, `can_cook_from_source`, `veterinary_validated`,
   `individual_pet_approved`, `clinical_scope`, `completeness` e `issues`.
2. Se debe llamar únicamente dentro del flujo de recetas de mascotas. La
   evaluación de procedencia se añade a los gates de especie, salud, ingredientes,
   etapa y perfil; nunca los sustituye ni aprueba automáticamente una ración.
3. Sin evidencia confiable, las actuales 57 filas devuelven
   `local_authored_unverified`, `original_recipe_verified=false` y
   `can_cook_from_source=false`. Sus datos, fotos, notas y favoritos pueden
   conservarse como material pendiente. Importaciones se marcan por separado.
4. `sources` distingue `general_species_reference`, `general_safety_reference`
   y `unverified_reference`. Una URL de receta publicada sigue sin demostrar que
   el contenido local coincide con ella. Las etiquetas enviadas por el cliente,
   flags de IA y `verified_veterinary_guidance` no conceden aprobación.
5. `trusted_evidence=` es opcional para futuras revisiones exclusivamente del
   servidor. **Nunca** pasarle campos recibidos del navegador, de la receta o de
   una respuesta de IA. No hay revisiones externas autorizadas incluidas hoy.
6. Un registro confiable requiere `role='original_recipe_source'`, `url`,
   `publisher`, `original_title`, `reviewed_on`, `review_reference`,
   `content_sha256`, `species` como lista, `original_recipe_verified=true`,
   `original_content_complete=true`, `scope='supplemental_treat'` y
   `clinical_claims_present=false`. El hash se obtiene mediante
   `recipe_content_fingerprint(recipe)`; cantidades, pasos, especie o
   afirmaciones diferentes invalidan el registro. Notas/foto/favorita personales
   no lo invalidan. Las referencias generales conocidas nunca se aceptan como
   originales, aunque un registro las etiquete así.
7. Para habilitar contenido/cocina dentro de Roxy además se exige
   `content_reuse_authorized=true` y `rights_reference`. Sin ello el resultado
   conserva `original_link_only`. El evaluador siempre devuelve
   `veterinary_validated=false` e `individual_pet_approved=false`.
8. Dietas completas, tratamientos y afirmaciones clínicas no habilitan cocina:
   `professional_review_required`. El cribado textual es conservador y no una
   evaluación veterinaria; la revisión humana del alcance continúa siendo
   requisito explícito para cualquier evidencia futura.
9. `pet_recipe_source_directory(species)` entrega únicamente enlaces de revisión:
   perros/gatos con publicaciones de Hill's; Ferret con guías VCA/Oxbow. Cada
   entrada indica `imported_recipe=false`, `individual_pet_approved=false` y
   `content_reuse_status='not_authorized'`. Para especies sin enlace aprobado
   devuelve lista vacía; no sugiere recetas por analogía.

## Verificación y continuidad

`tests/test_roxy_home_recipe_provenance.py`: **42 pruebas aprobadas**. Cubren las
57 preparaciones reales y las ocho de Ferret, flags de aprobación falsificados,
URL que no demuestra correspondencia, separación de permisos, hash de contenido,
cambios de especie, guías indebidamente atribuidas, restricciones clínicas,
originales cortos, medidas originales textuales y enlaces inválidos. Pruebas con
fuentes de `example.org` son fixtures sintéticos, no recetas o permisos reales.

Se leyó `ROXY_CURRENT_STATE.md` completo y `data/roxy_continuity.json`; al inicio
`git status --short` solo mostraba `?? prototypes/`. El check de handoff fue
intentado y falló porque `tools/roxy_context_handoff.py` no existe en Home. No se
copió configuración ni herramientas de Trading; se usó exclusivamente su
intérprete virtual aprobado. El agente principal integra los gates y actualiza
la continuidad consolidada; este subbloque no modifica esos archivos compartidos.

Pendiente real: obtener originales concretos por receta/especie, revisar fidelidad
y campos incompletos, aclarar permisos, integrar la evaluación en los recorridos
de catálogo/guardado/cocina/Compra y comprobar UI. Ninguno de esos pasos se declara
terminado por la existencia de este helper. No hay cobertura universal aprobada.
