# Roxy Home 173 — fotografías de gatos y conteo de Compra

Estado: público comprobado, commit `8bafa33a5`. 569 pruebas Home/compras aprobadas (51.01 s), JS/SW y diff válidos. HTML/JS/SW y ocho imágenes nuevas descargados del sitio público y comparados byte a byte con el commit; HTTP 200 y coincidencia exacta.

Recarga normal en navegador: meta 173, Bella y Luna presentes, ambas miniaturas cargadas. Captura `/tmp/roxy-pet-safety-172.PUzAxl/05-public-profiles-173.png`. No se modificaron datos de producción. CSS 124 no cambió desde la verificación pública de 172.

QA móvil aislado: contador con 250 g + 60 g + una transportadora muestra 3 productos; gato Maine Coon muestra 12 preparaciones y fotos individuales, sin desbordamiento horizontal. Captura `/tmp/roxy-pet-safety-172.PUzAxl/04-qa-cat-173.png`. Ninguna mascota ni compra de producción modificada.

- Ocho imágenes individuales generadas mediante la herramienta imagegen; cada una muestra solo la preparación indicada. Se revisaron las ocho, sin collages ni fotos genéricas; originales conservados. Las imágenes ilustran preparación, no ración diaria.
- Doce preparaciones distintas para gatos, doce fotos específicas. Pruebas con Domestic Shorthair, Siamese y Maine Coon: identidad de perfil y restricciones conservadas. No se afirma que la raza por sí sola determine dieta.
- Compra cuenta productos, no suma cantidades con unidades incompatibles; singular/plural y estado vacío verificados por ejecución JS.
- HTML/APP 173, JS 174, CSS 124, SW 171; no cambios de permisos, cuentas o facturación.

## Prompts y archivos

### cat-dehydrated-whitefish-v2

Original: `/Users/robertograu/.codex/generated_images/01a05d3b-8e50-7f90-bb0a-4df5de364216/exec-57f93a97-5eb5-49a1-9f5a-30d8fde70318.png`.
Copia: `/Users/robertograu/.codex/worktrees/roxy-home-renueva/assets/roxy_home/recipes/pets/cat-dehydrated-whitefish-v2.jpg`.

Prompt final:

> Use case: photorealistic-natural. Create ONE standalone exact recipe photograph for the Roxy Home pet cookbook, not a collage. Landscape 3:2, close editorial natural window light, matte cream plate on cream stone with subtle forest green linen, central food clear in narrow mobile crop. No text, animals, people, hands, packaging, utensils, raw ingredients, side dishes or garnish. This illustrates a preparation, NOT the amount a cat should eat. Plain cooked animal ingredient only: no oil, salt, spices, herbs, breading, vegetables, bones, skin, sauce or red raw flesh. Tiny thin fully cooked then dehydrated whitefish flakes, dry papery pale beige-white edges, gently curled crisp fibers, loose small pile. Only dry whitefish, visibly different from moist steamed fish.

### cat-dehydrated-chicken-v2

Original: `/Users/robertograu/.codex/generated_images/01a05d3b-8e50-7f90-bb0a-4df5de364216/exec-d5a123ff-699e-4257-8b8c-a36f6e81accb.png`.
Copia: `/Users/robertograu/.codex/worktrees/roxy-home-renueva/assets/roxy_home/recipes/pets/cat-dehydrated-chicken-v2.jpg`.

Prompt final:

> Use case: photorealistic-natural. Create ONE standalone exact recipe photograph for the Roxy Home pet cookbook, not a collage. Landscape 3:2, close editorial natural window light, matte cream plate on cream stone with subtle forest green linen, central food clear in narrow mobile crop. No text, animals, people, hands, packaging, utensils, raw ingredients, side dishes or garnish. This illustrates a preparation, NOT the amount a cat should eat. Plain cooked animal ingredient only: no oil, salt, spices, herbs, breading, vegetables, bones, skin, sauce or red raw flesh. Tiny fully cooked then dehydrated chicken breast crumbs, irregular dry pale golden fibrous flakes and crumbs smaller than strips, scattered in a small shallow dish. Only dry chicken, no wet diced meat.

### cat-rabbit-morsels-v2

Original: `/Users/robertograu/.codex/generated_images/01a05d3b-8e50-7f90-bb0a-4df5de364216/exec-fd1edc1c-1696-4394-8643-5cb08bd2cc2b.png`.
Copia: `/Users/robertograu/.codex/worktrees/roxy-home-renueva/assets/roxy_home/recipes/pets/cat-rabbit-morsels-v2.jpg`.

Prompt final:

> Use case: photorealistic-natural. Create ONE standalone exact recipe photograph for the Roxy Home pet cookbook, not a collage. Landscape 3:2, close editorial natural window light, matte cream plate on cream stone with subtle forest green linen, central food clear in narrow mobile crop. No text, animals, people, hands, packaging, utensils, raw ingredients, side dishes or garnish. This illustrates a preparation, NOT the amount a cat should eat. Plain cooked animal ingredient only: no oil, salt, spices, herbs, breading, vegetables, bones, skin, sauce or red raw flesh. Small boneless thoroughly cooked rabbit meat morsels, ivory and light taupe tender lean fibers, moist not raw, chopped irregular tiny cubes. Only cooked rabbit meat.

### cat-turkey-flakes-v2

Original: `/Users/robertograu/.codex/generated_images/01a05d3b-8e50-7f90-bb0a-4df5de364216/exec-3328293c-0355-408c-9c47-cde6cd5a8b93.png`.
Copia: `/Users/robertograu/.codex/worktrees/roxy-home-renueva/assets/roxy_home/recipes/pets/cat-turkey-flakes-v2.jpg`.

Prompt final:

> Use case: photorealistic-natural. Create ONE standalone exact recipe photograph for the Roxy Home pet cookbook, not a collage. Landscape 3:2, close editorial natural window light, matte cream plate on cream stone with subtle forest green linen, central food clear in narrow mobile crop. No text, animals, people, hands, packaging, utensils, raw ingredients, side dishes or garnish. This illustrates a preparation, NOT the amount a cat should eat. Plain cooked animal ingredient only: no oil, salt, spices, herbs, breading, vegetables, bones, skin, sauce or red raw flesh. Small very fine freshly cooked turkey breast shreds and thin moist flakes, natural creamy ivory longitudinal fibers. A small loose mound of shredded turkey, no medallions or dried strips.

### cat-whitefish-flakes-v2

Original: `/Users/robertograu/.codex/generated_images/01a05d3b-8e50-7f90-bb0a-4df5de364216/exec-3f3098b1-634e-48e1-a736-2a2a4206bc5f.png`.
Copia: `/Users/robertograu/.codex/worktrees/roxy-home-renueva/assets/roxy_home/recipes/pets/cat-whitefish-flakes-v2.jpg`.

Prompt final:

> Use case: photorealistic-natural. Create ONE standalone exact recipe photograph for the Roxy Home pet cookbook, not a collage. Landscape 3:2, close editorial natural window light, matte cream plate on cream stone with subtle forest green linen, central food clear in narrow mobile crop. No text, animals, people, hands, packaging, utensils, raw ingredients, side dishes or garnish. This illustrates a preparation, NOT the amount a cat should eat. Plain cooked animal ingredient only: no oil, salt, spices, herbs, breading, vegetables, bones, skin, sauce or red raw flesh. Freshly baked plain boneless cod separated into small soft moist white flakes, recognizable natural layered flaky fish texture, no browned crust, no dried or crunchy edges. Only thoroughly cooked cod.

### cat-beef-crumbles-v2

Original: `/Users/robertograu/.codex/generated_images/01a05d3b-8e50-7f90-bb0a-4df5de364216/exec-c9c2c739-bcf0-413a-8697-fbde8c229b39.png`.
Copia: `/Users/robertograu/.codex/worktrees/roxy-home-renueva/assets/roxy_home/recipes/pets/cat-beef-crumbles-v2.jpg`.

Prompt final:

> Use case: photorealistic-natural. Create ONE standalone exact recipe photograph for the Roxy Home pet cookbook, not a collage. Landscape 3:2, close editorial natural window light, matte cream plate on cream stone with subtle forest green linen, central food clear in narrow mobile crop. No text, animals, people, hands, packaging, utensils, raw ingredients, side dishes or garnish. This illustrates a preparation, NOT the amount a cat should eat. Plain cooked animal ingredient only: no oil, salt, spices, herbs, breading, vegetables, bones, skin, sauce or red raw flesh. Plain fully cooked lean ground beef, dark warm brown tiny loose irregular crumbles, drained of extra fat, not meatballs or patties. Small low mound of fine cooked beef granules.

### cat-plain-shrimp-v2

Original: `/Users/robertograu/.codex/generated_images/01a05d3b-8e50-7f90-bb0a-4df5de364216/exec-2bc35c37-ba71-41aa-a299-f82a0eb4f6c0.png`.
Copia: `/Users/robertograu/.codex/worktrees/roxy-home-renueva/assets/roxy_home/recipes/pets/cat-plain-shrimp-v2.jpg`.

Prompt final:

> Use case: photorealistic-natural. Create ONE standalone exact recipe photograph for the Roxy Home pet cookbook, not a collage. Landscape 3:2, close editorial natural window light, matte cream plate on cream stone with subtle forest green linen, central food clear in narrow mobile crop. No text, animals, people, hands, packaging, utensils, raw ingredients, side dishes or garnish. This illustrates a preparation, NOT the amount a cat should eat. Plain cooked animal ingredient only: no oil, salt, spices, herbs, breading, vegetables, bones, skin, sauce or red raw flesh. Plain peeled deveined fully boiled shrimp chopped into very small opaque white and pale pink pieces. No whole shrimp, tails, shells or raw translucency. A few curved chopped sections show recognizable shrimp texture.

### cat-hard-boiled-egg-v2

Original: `/Users/robertograu/.codex/generated_images/01a05d3b-8e50-7f90-bb0a-4df5de364216/exec-2ca7f3db-bda9-45f6-9047-c54761e85755.png`.
Copia: `/Users/robertograu/.codex/worktrees/roxy-home-renueva/assets/roxy_home/recipes/pets/cat-hard-boiled-egg-v2.jpg`.

Prompt final:

> Use case: photorealistic-natural. Create ONE standalone exact recipe photograph for the Roxy Home pet cookbook, not a collage. Landscape 3:2, close editorial natural window light, matte cream plate on cream stone with subtle forest green linen, central food clear in narrow mobile crop. No text, animals, people, hands, packaging, utensils, raw ingredients, side dishes or garnish. This illustrates a preparation, NOT the amount a cat should eat. Plain cooked animal ingredient only: no oil, salt, spices, herbs, breading, vegetables, bones, skin, sauce or red raw flesh. One peeled hard-boiled egg finely crumbled into tiny irregular firm egg-white pieces and fully set yellow yolk crumbs. Small loose low pile, no large quarters, no scrambled egg, shell, runny yolk or other ingredients.
