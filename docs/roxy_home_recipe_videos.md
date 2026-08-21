# Videos reutilizables de recetas en Roxy Home

Roxy Home genera demostraciones prácticas de una receta una sola vez, las guarda en el disco persistente de Home y puede reutilizarlas para otros usuarios después de la revisión. La generación comienza automáticamente cuando alguien toca **Cocinar paso a paso**; no existe un botón separado de “Crear video”. Esta integración no usa ni comparte claves, memoria o presupuesto de Trading.

La versión 2 de los prompts exige una acción culinaria visible: manos adultas añadiendo, mezclando, amasando, cortando, cocinando, sirviendo o ejecutando la técnica descrita. Se prohíben planos estáticos de ingredientes, tomas decorativas y resultados finales que no demuestren el paso. Los videos anteriores a esta versión no se reutilizan.

## Comportamiento

- La huella de una receta incluye título, categoría, porciones, ingredientes y pasos.
- Favoritos, notas, fotos y nombres del hogar nunca forman parte de la huella ni del video compartido.
- Una receta equivalente reutiliza el video `READY`; no solicita otra generación.
- Una generación que ya está en cola también se deduplica para que dos usuarios no paguen el mismo trabajo simultáneamente.
- `shared` permite compartir un video revisado entre usuarios.
- `household` mantiene el video disponible solamente para el hogar que lo creó.
- Los estados son `QUEUED`, `PROCESSING`, `REVIEW`, `READY`, `FAILED` y `REJECTED`.
- Un video compartido no es visible para otros hogares hasta quedar `READY`.
- El MP4 final se descarga al almacenamiento propio de Roxy. La reproducción no depende de que fal.ai conserve su URL temporal.
- La interfaz nunca reproduce automáticamente audio y conserva los pasos escritos como transcripción accesible.

## Proveedor inicial

El adaptador usa `fal-ai/minimax/hailuo-02/standard/text-to-video`. Las demostraciones duran seis segundos y el costo editable parte de USD 0.045 por segundo, verificado el 21 de agosto de 2026 en la [documentación de fal.ai](https://fal.ai/models/fal-ai/minimax/hailuo-02/standard/text-to-video/api). La versión 4 conserva instrucciones de acción estrictas y desactiva el optimizador cinematográfico para evitar tomas decorativas.

El proveedor está aislado detrás de `FalRecipeVideoProvider`; se puede añadir Runway u otro proveedor sin cambiar recetas, usuarios o URLs de reproducción.

## Activación en Render

En **roxy-home → Environment** configura únicamente secretos de Home:

```text
ROXY_HOME_VIDEO_ENABLED=1
ROXY_HOME_VIDEO_FAL_KEY=<clave exclusiva de Roxy Home>
ROXY_HOME_VIDEO_MONTHLY_BUDGET_USD=20
ROXY_HOME_VIDEO_MAX_RECIPE_COST_USD=1.00
ROXY_HOME_VIDEO_ADMIN_KEY=<clave larga y aleatoria para revisión>
```

Las rutas persistentes ya están preparadas en `render.yaml`:

```text
ROXY_HOME_VIDEO_LIBRARY_PATH=/var/data/roxy_home/recipe_video_library.json
ROXY_HOME_VIDEO_MEDIA_DIR=/var/data/roxy_home/recipe_videos
```

Con tres demostraciones de seis segundos, la estimación actual es USD 0.81 por receta. La generación permanece deshabilitada si no hay presupuesto, si falta la clave o si el costo estimado supera `ROXY_HOME_VIDEO_MAX_RECIPE_COST_USD`.

## Flujo de revisión

1. Un usuario toca **Cocinar paso a paso**; esa acción expresa la intención de cocinar y autoriza el video dentro del presupuesto configurado.
2. La guía de cocina abre inmediatamente, aunque el proveedor de video esté lento o caído.
3. Roxy busca un video o una generación equivalente ya existente.
4. Si no existe, reserva una sola entrada para evitar solicitudes duplicadas y comienza en segundo plano.
5. Mientras la guía de cocina está abierta, Roxy comprueba el progreso
   automáticamente y muestra los clips en la misma pantalla cuando terminan.
6. Al terminar, los MP4 se copian al disco persistente y quedan en `REVIEW`.
7. El propietario puede previsualizarlos; otros hogares todavía no.
8. Un revisor aprueba o rechaza usando la clave administrativa exclusivamente desde servidor o terminal segura.

Ejemplo de aprobación manual:

```bash
curl -X POST \
  -H "Authorization: Bearer $ROXY_HOME_API_KEY" \
  -H "X-Roxy-Video-Admin-Key: $ROXY_HOME_VIDEO_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"approved":true,"notes":"Ingredientes, técnica y seguridad revisados"}' \
  "https://roxy-home.onrender.com/v1/home-food/local_user/recipe-videos/VIDEO_ID/review"
```

No pegues ninguna de estas claves en JavaScript, capturas, NFC ni parámetros de URL.

## Seguridad y operación

- Iniciar la guía de cocina es la confirmación explícita para generar el video, siempre dentro de los límites configurados.
- Publicar exige revisión separada.
- Las URLs del proveedor se restringen a HTTPS y dominios de fal.ai.
- Las descargas aceptan MP4 y tienen un límite de 100 MB por clip.
- Los archivos privados usan `Cache-Control: private, no-store`.
- La ruta de reproducción comprueba usuario, visibilidad, estado y directorio permitido.
- Los videos son ilustrativos: los pasos escritos y la guía de Roxy siguen siendo la fuente principal para cantidades, temperatura, tiempos y seguridad alimentaria.

Antes de abrir esta función al público, añade un panel administrativo autenticado y alertas de presupuesto. La pantalla de cocina ya sincroniza automáticamente los trabajos en cola; si la persona cierra la aplicación, la sincronización se retoma al volver a abrir la receta. La generación automática no se inicia cuando el proveedor está desactivado o el presupuesto se agotó; la receta y la guía hablada continúan funcionando normalmente.

## Biblioteca global de recetas

Las recetas poco comunes generadas mediante OpenAI se guardan en `ROXY_HOME_RECIPE_LIBRARY_PATH`, una base SQLite transaccional separada de los hogares. La base conserva únicamente la receta canónica y hashes de búsquedas equivalentes:

- no guarda usuario, nombre, contraseña, despensa, notas, fotos ni lista de compras;
- una segunda persona reutiliza la receta sin una nueva llamada a OpenAI;
- las cantidades se escalan para solicitudes como “para 8 personas”;
- si los ingredientes chocan con una alergia o rechazo registrado, Roxy no reutiliza esa variante y prepara una compatible;
- el catálogo local de recetas comunes continúa siendo la primera opción y no consume OpenAI.

En Render la ruta persistente es:

```text
ROXY_HOME_RECIPE_LIBRARY_PATH=/var/data/roxy_home/recipe_library.sqlite
```

SQLite es adecuada mientras Roxy Home funcione como una sola instancia de Render. Antes de escalar a varias instancias para App Store y Google Play, se migrará el mismo contrato a PostgreSQL y los MP4 a almacenamiento de objetos/CDN; las aplicaciones seguirán usando las mismas APIs y no necesitarán cambios de comportamiento.
