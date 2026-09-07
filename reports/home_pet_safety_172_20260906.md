# Roxy Home 172 — ingredientes, personalización y fotografías

Estado: candidato local con 565 pruebas Home/compras aprobadas (57.60 s); JS/SW, JSON y diff válidos. Verificación pública pendiente. No declarar demo lista.

## Cambios

- Cribado bilingüe por palabras completas: `res` no coincide con `fresa` ni `preserved`. Fórmulas oficiales de Mazuri, Oxbow, Wysong, Royal Canin y Hill’s revisadas el 2026-09-06. Sus fichas no garantizan ausencia de contaminación cruzada.
- Una restricción, condición o indicación veterinaria deja alimentos y sustancias pendientes de revisión; los conflictos identificados se excluyen. El equipo conserva avisos de materiales/talla. No hay certificación clínica automática.
- Endpoint específico de productos: ID estable, resuelve nuevamente mascota y catálogo en servidor, exige intención de añadir y rechaza productos incompatibles aunque el navegador envíe una aprobación falsa. Solo añade a la lista, no compra.
- Recetas de pavo/calabaza, res/judías, manzana/zanahoria/avena y plátano/calabaza: cantidades de todos los ingredientes presentes y verificadas en Compra. Las cantidades son de preparación, no una ración diaria.
- Cocción antes de deshidratar, temperatura interna medida; no se considera el secado casero conservación a temperatura ambiente. Conservación congelada corregida para cubos de fruta.
- Guardado del catálogo vinculado al perfil actual; cocina, escalado y Compra vuelven a comprobar restricciones. Recetas importadas no se sobrescriben por compartir un título del catálogo. Las copias del catálogo reciben correcciones conservando ID, mascota, notas, favorita y foto personal.
- El catálogo personalizado no repite una misma preparación con otro título por raza: 13 recetas distintas generales para perro, 15 para Bernese joven; todas con imagen individual revisada. Luna mantiene ocho preparaciones específicas de Ferret. Esto no implica variedad suficiente para toda especie.
- En móvil, las advertencias y los ingredientes ocupan todo el ancho de la tarjeta; filtros accesibles con estado y foco conservados.

## Evidencia y pendientes

Tests nuevos: `tests/test_roxy_home_pet_product_safety.py`, `tests/test_roxy_home_pet_recipe_quality.py`, prueba de autorización y vencimiento en `tests/test_roxy_home_public_demo.py`.
Navegador aislado: `/tmp/roxy-pets-qa-t23jv7vm`, 17 mascotas sintéticas. Pavo/calabaza guardada con foto correcta y dos ingredientes enviados a Compra después de confirmación. Ferret QA con restricción muestra Mazuri pendiente, sin botón de añadir y con ficha oficial. Ningún perfil ni carrito de producción se modificó.
Capturas: `/tmp/roxy-pet-safety-172.PUzAxl`.

Pendiente fuera de este bloque: restantes fotos de gatos/aves/pequeños mamíferos, revisión de productos exactos de especies menos comunes, receta importada arbitraria no equivale a revisión clínica, soporte/recuperación, módulos restantes y servicios de voz/facturación. Registro permanece apagado. Hallazgo para siguiente bloque: Compra suma gramos como «artículos» en el contador de pie.

## Fuentes consultadas

- [Mazuri](https://mazuri.com/products/mazuri-ferret-diet), [Oxbow](https://oxbowanimalhealth.com/product/essentials-ferret-food/), [Wysong](https://www.wysong.net/products/ferret-epigen-90).
- [Royal Canin](https://www.royalcanin.com/us/dogs/products/retail-products/large-puppy-3006), [Hill’s](https://www.hillspet.com/dog-food/science-diet-puppy-large-breed-dry).
- [Merck: alergia alimentaria](https://www.merckvetmanual.com/integumentary-system/food-allergy/cutaneous-food-allergy-in-animals).
- [FoodSafety.gov: temperaturas internas](https://www.foodsafety.gov/food-safety-charts/safe-minimum-internal-temperatures), [USDA: cocinar antes de deshidratar](https://www.fsis.usda.gov/food-safety/safe-food-handling-and-preparation/meat-fish/jerky).

## Imágenes y prompts finales

Método: herramienta integrada `imagegen`, una preparación por llamada; no CLI ni clave de otro producto. Originales conservados en la carpeta de imágenes generadas de Codex. Copias JPEG 1200 px con `sips`; no composición ni collage. Todas ilustran la preparación, no la cantidad que debe comer el animal. Se revisaron también diez imágenes individuales existentes; no se habilitaron collages.

### dog-banana-pumpkin-blended-v2.jpg

Archivo: `/Users/robertograu/.codex/worktrees/roxy-home-renueva/assets/roxy_home/recipes/pets/dog-banana-pumpkin-blended-v2.jpg`.

Prompt final:

> Use case: photorealistic-natural. Asset: one standalone exact recipe illustration for Roxy Home mobile food cards. Photograph of finished tiny frozen treats made by thoroughly blending ripe banana and pure pumpkin puree together, then freezing that homogeneous mixture in small cube molds. Uniform pale pumpkin-orange cubes, slightly creamy, frosty texture. Show 9 small cubes in one cream ceramic shallow bowl on cream stone with a muted dark green linen edge. Tight editorial food photography, natural window light, 3:2 landscape composition with main food in center for a narrow mobile crop. The ingredients are fully mashed and blended: no visible banana slices, no raw pumpkin chunks, no separate yellow versus orange batches, no yogurt, no milk, no other food, no garnishes. No animals, people, packaging, text, logo, watermark or collage. This represents a batch of occasional dog treats, not a full feeding portion.

### dog-hard-boiled-egg-v2.jpg

Archivo: `/Users/robertograu/.codex/worktrees/roxy-home-renueva/assets/roxy_home/recipes/pets/dog-hard-boiled-egg-v2.jpg`.

Prompt final:

> Use case: photorealistic-natural. Asset: one standalone exact recipe illustration for Roxy Home mobile food cards. Photograph of one completely hard-boiled peeled chicken egg cut into small bite-size pieces, both fully solid golden yolk and firm white clearly visible. Plain cooked egg only, irregular small quarters and diced pieces, no shell. On one small cream ceramic plate, cream stone surface, subtle dark olive green linen, warm natural window light, authentic food texture. 3:2 landscape composition, food centered so it remains readable cropped in a narrow mobile card. No scrambled egg, raw egg, runny yolk, salt, seasoning, mayonnaise, oil, vegetables, garnish, other dishes or ingredients. No animal, people, packaging, text, watermark or collage. A photographed preparation batch, not a pet feeding amount.

### dog-dehydrated-chicken-v2.jpg

Archivo: `/Users/robertograu/.codex/worktrees/roxy-home-renueva/assets/roxy_home/recipes/pets/dog-dehydrated-chicken-v2.jpg`.

Prompt final:

> Use case: photorealistic-natural. Asset: one standalone exact recipe illustration for Roxy Home mobile food cards. Photograph of plain chicken breast strips cooked completely then dehydrated into thin dry fibrous pale golden-brown strips. A small loose pile of about 10 narrow irregular strips on one matte cream ceramic plate. Visible longitudinal chicken muscle fibers and dry edges, natural uneven shapes, clearly chicken meat rather than biscuits or raw meat. Cream stone surface with muted forest-green linen at edge, soft window light, realistic editorial photography, 3:2 landscape, main strips centered for narrow portrait crop. No bones, skin, red/raw center, sauce, salt, seasonings, garnish, vegetables or other ingredients. No people, animals, packaging, text, watermark or collage. Depict the preparation batch, never imply all strips are one serving.

### dog-dehydrated-turkey-v2.jpg

Archivo: `/Users/robertograu/.codex/worktrees/roxy-home-renueva/assets/roxy_home/recipes/pets/dog-dehydrated-turkey-v2.jpg`.

Prompt final:

> Use case: photorealistic-natural. One standalone Roxy Home exact recipe illustration, not a collage. Editorial food photograph, natural window light, cream stone table, muted forest-green linen, shallow cream ceramic plate. Landscape 3:2 composition, food centered to survive a narrow mobile crop. No text, people, animals, packaging, utensils, garnish, raw ingredients or other dishes. This depicts the preparation, not the recommended serving amount for any animal. Subject: a small batch of slender plain turkey breast strips, fully cooked before dehydration, dry matte ivory/beige fibrous turkey jerky. Short thin irregular strips, no skin, fat, bones, sauce, oil, glaze, breading, spices or vegetables. Only dried turkey. Arrange them in a loose fan with visible fine dry texture, visually distinct from wet cooked turkey and from minced meat.

### dog-turkey-pumpkin-v2.jpg

Archivo: `/Users/robertograu/.codex/worktrees/roxy-home-renueva/assets/roxy_home/recipes/pets/dog-turkey-pumpkin-v2.jpg`.

Prompt final:

> Use case: photorealistic-natural. One standalone Roxy Home exact recipe illustration, not a collage. Editorial food photograph, natural window light, cream stone table, muted forest-green linen, shallow cream ceramic plate. Landscape 3:2 composition, food centered to survive a narrow mobile crop. No text, people, animals, packaging, utensils, garnish, raw ingredients or other dishes. This depicts the preparation, not the recommended serving amount for any animal. Subject: nine very small baked bites made from 250 g plain ground turkey mixed uniformly with 60 g pure pumpkin puree. Round irregular mini meatballs, pale warm golden-orange meat fibers mixed evenly with pumpkin, completely cooked to the center. All nine bites have the SAME mixture/color/shape, no separate pumpkin treats. No oats, egg, bread, herbs, salt, spices, sauce, filling or oil; only turkey and pumpkin. Detail should read as soft baked turkey mini meatballs, not cookies or molded bones.
