# Recetario local de Roxy Home

Roxy Home incluye un catálogo local categorizado para responder sin depender de OpenAI en recetas cotidianas. El catálogo se define en `roxy_os/home_recipe_catalog.py` y se mezcla con las recetas históricas de `home_recipe_fallback.py` sin duplicar títulos en la respuesta pública.

Las categorías instaladas son: desayunos, pollo, carnes, pescados y mariscos, arroces, pastas y fideos, sopas/cremas/guisos, bowls y ensaladas, vegetarianas, horneados, acompañamientos y salsas, postres, café y bebidas calientes, jugos, batidos/smoothies y cócteles.

Cada entrada tiene ingredientes, pasos, porciones, categoría y subcategoría. La app consulta este catálogo primero. Solo una solicitud que no coincida con una receta instalada pasa a la biblioteca compartida o a OpenAI. Las recetas creadas por OpenAI reciben una categoría compatible para aparecer en la sección adecuada.

En el cliente, la biblioteca completa se conserva dentro de la instantánea de Home en IndexedDB. Las imágenes de categoría y la interfaz forman parte de la caché del service worker, por lo que la navegación básica y las recetas cargadas anteriormente continúan disponibles sin conexión.
