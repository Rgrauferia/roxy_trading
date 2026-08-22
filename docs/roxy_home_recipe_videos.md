# Videos reutilizables de recetas en Roxy Home

Roxy Home genera demostraciones prácticas de una receta una sola vez, las guarda en el disco persistente de Home y puede reutilizarlas para otros usuarios después de la revisión. La generación comienza automáticamente cuando alguien toca **Cocinar paso a paso**; no existe un botón separado de “Crear video”. Esta integración no usa ni comparte claves, memoria o presupuesto de Trading.

La versión 6 de los prompts exige una acción culinaria visible y usa el retrato oficial de Roxy como referencia de sujeto. La misma mujer representa a Roxy en todos los clips, con rostro, edad, tono de piel y cabello consistentes. Se prohíben planos estáticos, texto inventado, personas adicionales y resultados que no demuestren el paso. Los videos anteriores a esta versión no se reutilizan.

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

El adaptador usa `fal-ai/minimax/video-01-subject-reference`. Cada solicitud incluye `assets/roxy_avatar.jpg` mediante `subject_reference_image_url`, conserva la identidad visual y desactiva el optimizador para respetar la acción culinaria. El precio de referencia es USD 0.50 por clip, verificado el 21 de agosto de 2026 en la [documentación oficial de fal.ai](https://fal.ai/models/fal-ai/minimax/video-01-subject-reference/api).

El proveedor está aislado detrás de `FalRecipeVideoProvider`; se puede añadir Runway u otro proveedor sin cambiar recetas, usuarios o URLs de reproducción.

## Activación en Render

En **roxy-home → Environment** configura únicamente secretos de Home:

```text
ROXY_HOME_VIDEO_ENABLED=1
ROXY_HOME_VIDEO_FAL_KEY=<clave exclusiva de Roxy Home>
ROXY_HOME_VIDEO_MONTHLY_BUDGET_USD=20
ROXY_HOME_VIDEO_MAX_RECIPE_COST_USD=1.50
ROXY_HOME_VIDEO_ADMIN_KEY=<clave larga y aleatoria para revisión>
ROXY_HOME_VIDEO_ROXY_REFERENCE_URL=https://roxy-home.onrender.com/assets/roxy_avatar.jpg
```

Las rutas persistentes ya están preparadas en `render.yaml`:

```text
ROXY_HOME_VIDEO_LIBRARY_PATH=/var/data/roxy_home/recipe_video_library.json
ROXY_HOME_VIDEO_MEDIA_DIR=/var/data/roxy_home/recipe_videos
ROXY_HOME_VIDEO_SUBJECT_PRICE_PER_CLIP_USD=0.50
```

Con tres demostraciones, la estimación actual es USD 1.50 por receta. La generación permanece deshabilitada si no hay presupuesto, si falta la clave o si el costo estimado supera `ROXY_HOME_VIDEO_MAX_RECIPE_COST_USD`.

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
# Videoteca global de acciones de Roxy

Roxy Home usa un catálogo global versionado de 60 demostraciones genéricas. Los clips no contienen datos del hogar, nombres de usuarios, marcas ni texto visible. Una receta privada conserva únicamente la relación entre cada paso y la acción correspondiente; el archivo audiovisual aprobado puede reutilizarse entre hogares.

La versión inicial contiene 40 acciones de cocina, 8 de postres/panadería y 12 de bebidas. El clasificador determinista reconoce primero acciones específicas como amasar, cortar, hervir, hornear, macerar, agitar una coctelera o preparar el borde de una copa. Los pasos repetidos comparten un único archivo y guardan todos sus índices para que la interfaz muestre el clip solamente durante el paso correcto.

Cada clip debe mantener la identidad visual canónica: la misma mujer adulta del retrato de Roxy, cabello oscuro, delantal verde, cocina familiar cálida, formato vertical y ausencia de marcas, empaques o textos. El rostro aparece brevemente y la acción práctica permanece visible. Un clip solo entra a la biblioteca compartida después de revisión.

Para inspeccionar el lote y su costo sin iniciar generación:

```bash
.venv/bin/python tools/roxy_home_video_catalog.py --price-per-clip 0.102
```

El comando es deliberadamente de solo lectura: produce el manifiesto, los prompts y el costo estimado, pero nunca llama al proveedor. La generación pagada requiere un flujo administrativo separado y confirmación explícita. Con la referencia de 512p de seis segundos, 60 clips a USD 0.102 estiman USD 6.12 antes de repeticiones. El precio real debe comprobarse en el proveedor inmediatamente antes de confirmar el lote.

El progreso se expone dentro de `recipe_video_service.action_library`: total, aprobados, pendientes y desglose por familia. La aplicación puede reproducir clips ya aprobados aunque el generador esté temporalmente desactivado o sin presupuesto.
