# Mascotas — carga de fotos y tarjetas móviles, 2026-09-06

## Alcance y evidencia de esta sesión

Auditoría visual acotada usando la guía `product-design:audit` y el navegador
integrado, sin modificar los perfiles reales. No es una auditoría WCAG completa
ni una aprobación veterinaria universal. Capturas guardadas y abiertas antes de
usarlas; directorio `/tmp/roxy-pets-followup-Cbgxlb`.

1. `01-bella-recipes.png`: título de Alimentación complementaria cortado en mitad
   de una palabra en 409 px. El contador estrechaba el título.
2. `02-bella-cards.png`: 25 tarjetas con elementos img sin src; las imágenes de las
   primeras recetas visibles no se solicitaban. Texto alternativo roto ocupaba el
   espacio de la foto. El aviso de importación compartía celda con un botón.
3. `03-luna-products.png`: foto del transportador no cargada. El catálogo entregaba
   URLs de Kaytee, MidWest y Wix que la política img-src no autorizaba.
4. `04-ferret-recipes-fixed.png`: QA aislada, imágenes específicas de corazones,
   huevo revuelto y carnes visibles. Ingredientes/pasos del catálogo comprobados:
   el huevo de esta receta se revuelve, no se hierve; pavo/res son carne molida.
5. `05-mobile-heading-fixed.png`: título y explicación ocupan todo el ancho móvil;
   el contador queda debajo, sin cortar palabras normales.
6. `06-mobile-cards-fixed.png`: botones de importación en filas y explicación
   aparte; fotografías de recetas cargadas. Vista previa de medallones abierta,
   cinco pasos/ingrediente/advertencia de premio presentes; no se guardó ni compró.

## Correcciones del candidato 170

- La limpieza de observadores se difiere al final de la construcción síncrona del
  listado. Antes cancelaba cada imagen cuyo grid aún no se había insertado en DOM.
  Conserva carga diferida y descarta los elementos retirados; regresión reproduce
  25 tarjetas creadas fuera del DOM, su inserción y desplazamiento posterior.
- Imágenes de productos: lista cerrada de cuatro dominios oficiales añadida solo
  a img-src; no permisos de scripts/conexiones nuevos. Prueba comprueba todos los
  orígenes de imágenes del catálogo para detectar futuras discrepancias.
- Referrer-Policy no-referrer para fotos comerciales. Fallos usan el aviso existente
  de foto oficial no disponible, nunca una foto genérica de otro producto.
- Kaytee: URL de fotografía corregida con la imagen publicada en la ficha oficial.
  Sigue requiriendo medidas; no se presenta talla recomendada sin medir.
- MidWest: la foto 181 corresponde al modelo Single Unit; corregido el nombre que
  decía Double Unit. No se modifica ningún artículo previamente guardado ni compra.
- Encabezado móvil más corto y personalizado; acciones de importación desacopladas
  de la rejilla de historial, con áreas de pulsación de al menos 44 px.
- Corazones de pollo: retirada instrucción de enjuagar carne cruda para evitar
  contaminación por salpicaduras; mantiene la comprobación de 74 °C. No reemplaza
  silenciosamente recetas guardadas ni instrucciones veterinarias.

## Fuentes consultadas

- [Kaytee Come Along Carrier](https://www.kaytee.com/all-products/small-animal/come-along-carrier).
- [MidWest Ferret Nation](https://www.midwesthomes4pets.com/product/small-animal/habitats-cages/ferret-nation/).
- [Marshall High Back Litter Pan](https://www.marshallpet.com/product-page/high-back-litter-pan-1).
- [MDN Intersection Observer](https://developer.mozilla.org/en-US/docs/Web/API/Intersection_Observer_API).
- [USDA: no lavar aves crudas](https://ask.fsis.usda.gov/article/Should-I-wash-chicken-or-other-poultry-before-cooking).

## Validación antes del despliegue

522 tests Home/compras aprobados (59.35 s), `node --check` para JS y SW, y
`git diff --check` correctos. HTML/APP 170, JS 169, CSS 121, SW 166.
Pendiente la comprobación en público después del push.

### 170 comprobado en público; candidato 171

170, commit `6186b136d`: cinco archivos públicos HTTP 200 e idénticos al worktree,
health correcto y registro apagado. Bella y Luna siguen presentes. No se editaron
perfiles, recetas guardadas ni productos de Compra.

7. `08-public-heading-170.png`: título de Bella corregido en 409 px. La captura
   `09-public-bella-cards-170.png` es diagnóstico de carga pendiente, no evidencia
   de fotos terminadas. Algunas imágenes no existen todavía (404 anónimo).
8. `10` a `13-public-luna-recipes-170.png`: recorrido de las ocho preparaciones de
   Luna. Todas cargadas, ocho URLs diferentes; tipos de preparación revisados
   contra ingredientes/pasos. Ningún protocolo de cuidado dentro de Recetas.
9. `14` a `18-public-luna-products-170.png`: ocho fotos comerciales cargadas.
   Kaytee, Marshall y MidWest ya no están bloqueadas. La imagen de MidWest muestra
   un solo cuerpo, consistente con Single Unit. No se enviaron compras.
10. `19-qa-missing-photo-state-171.png`, `22-mobile-loaded-171.png` y
    `23-mobile-missing-171.png`: QA de estados disponibles/ausentes. 171 oculta
    únicamente la imagen mientras carga, la muestra al recibir load, e informa
    carga/generación/pendiente con texto. No reemplaza fotos faltantes. Capturas
    20/21 quedaron en los encabezados y se descartan como prueba de estos estados.

Consulta de cobertura durante 170: 557/683 disponibles, 126 pendientes, 20 trabajos
en cola; contador diario 1. Es una instantánea, no una promesa de generación final.
No se aumentaron límites ni se llamaron herramientas de generación de imágenes.
El servicio existente puede programar fotos al abrir recetas; no afirmar que
ninguna generación se haya iniciado por recorrer la UI.

171: HTML/APP 171, JS 170, CSS 122, SW 167; 522 pruebas Home/compras aprobadas
(60.26 s), comprobaciones JS/SW y diff correctas. Despliegue aún por verificar.

## Límites y siguiente bloque

Estas correcciones no generan fotos faltantes, no amplían el catálogo ni certifican
que todas sus preparaciones o productos sean apropiados para todos los perfiles.
Queda revisar la variedad real frente a duplicados por raza, ampliar correspondencia
plato-foto y asegurar restricciones por ingredientes completos del producto (no solo
su nombre). Registro público sigue apagado; CAPTCHA/soporte/voz siguen pendientes.

El diseño conserva textos pequeños que todavía requieren revisión de accesibilidad;
el filtro de productos puede perder su posición visible tras cambiar de categoría.
