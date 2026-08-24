# OpenAI en Roxy Home

Roxy Home comparte la identidad y el tono de Roxy, pero funciona como un dominio separado de Roxy Trading y Study. No importa memoria, permisos, credenciales ni presupuesto de esos productos.

## Activación separada

1. Crea una clave de proyecto de OpenAI dedicada exclusivamente a Roxy Home.
2. En Render abre el servicio **roxy-home** → **Environment**.
3. Asigna la clave a `ROXY_HOME_OPENAI_API_KEY`. No uses `OPENAI_API_KEY`, una clave de Study ni una clave expuesta en el navegador.
4. Conserva estos valores, salvo que la cuenta de OpenAI indique otros identificadores autorizados:

   ```dotenv
   ROXY_HOME_OPENAI_ROUTINE_MODEL=gpt-5.6-luna
   ROXY_HOME_OPENAI_DEEP_MODEL=gpt-5.6-terra
   ROXY_HOME_MEMORY_PATH=/var/data/roxy_home/home_food.json
   ROXY_HOME_CONVERSATION_PATH=/var/data/roxy_home/conversations.json
   ROXY_HOME_CONVERSATION_MAX_TURNS=12
   ROXY_HOME_AI_BUDGET_PATH=/var/data/roxy_home/openai_budget.json
   ROXY_HOME_AI_DAILY_REQUEST_LIMIT=100
   ROXY_HOME_AI_DAILY_OUTPUT_TOKEN_LIMIT=100000
   ROXY_HOME_AI_MAX_OUTPUT_TOKENS=4000
   ROXY_HOME_REQUIRE_VERIFIED_RECIPES=1
   ```

5. Guarda los cambios y despliega nuevamente `roxy-home`.

La clave permanece en el servidor. La PWA usa la cookie segura de Roxy Home y nunca recibe ni almacena la clave de OpenAI. No hay fallback a claves genéricas ni se reutilizan secretos de otros productos.

### Imágenes exactas del recetario

Roxy Home no usa fotos generales de buscadores para las tarjetas. Una receta
solo muestra una imagen creada y aprobada para su título exacto. Si todavía no
existe, la interfaz deja el espacio limpio en vez de enseñar otro plato.

La biblioteca compartida puede completarse por lotes mediante Responses API:

```bash
.venv/bin/python tools/generate_roxy_home_recipe_images.py --category breakfast --limit 10
```

Cada imagen nueva queda pendiente de revisión salvo que se use `--approve`.
La generación usa únicamente `ROXY_HOME_OPENAI_API_KEY`, nunca secretos de
Study, Trading o Finanzas.

En la aplicación, las imágenes que falten entran automáticamente en una cola
de dos trabajos. El navegador reintenta la tarjeta y la imagen se reutiliza
desde el disco persistente para todos los usuarios. El límite diario se define
con `ROXY_HOME_RECIPE_IMAGE_DAILY_LIMIT` (600 durante la creación inicial);
nunca se genera dos veces el mismo
título ni se utiliza una imagen de otra receta.

### Recetario local antes de OpenAI

El recetario instalado contiene más de 500 títulos organizados por categoría, pero un título no se considera por sí solo una receta verificada. Con `ROXY_HOME_REQUIRE_VERIFIED_RECIPES=1`, Roxy solo usa directamente las fichas revisadas de manera individual. La primera vez que se abre un título pendiente, Terra ejecuta búsqueda web obligatoria, genera una edición canónica con salida estructurada, y el servidor rechaza instrucciones genéricas o incompletas. La ficha aprobada se guarda en la biblioteca compartida y se reutiliza para los demás usuarios, sin volver a pagar su generación. Si la investigación o la validación falla, la aplicación devuelve un error y no muestra la plantilla general como si fuera confiable.

Las fuentes encontradas por la Responses API se guardan con la ficha y se muestran en el detalle. Este mecanismo no convierte ninguna fuente individual en una verdad absoluta: para platos con variantes regionales, Roxy identifica la variante concreta elegida y mantiene cantidades y técnica coherentes con ella.

La respuesta local indica `generation_mode: local_recipe_catalog`, se guarda en la misma biblioteca y puede convertirse en lista o guía paso a paso. No se presenta como una respuesta de OpenAI. Sustituciones, planes semanales e investigación vigente siguen requiriendo la conexión OpenAI dedicada y responden `503` si no está disponible.

La herramienta de voz devuelve además `speech` y `must_speak`. El agente debe esperar el resultado y leer `speech` completo; el texto visible en pantalla no sustituye la respuesta hablada.

`gpt-5.6-luna` y `gpt-5.6-terra` son los identificadores exigidos por el contrato de Roxy Home. La cuenta/proyecto de OpenAI debe tener acceso a ellos; la aplicación no sustituye silenciosamente otro modelo.

## Comportamiento

- Luna atiende recetas rutinarias, sustituciones y planes semanales rápidos.
- Terra atiende razonamiento profundo.
- Las preguntas abiertas pasan por un diálogo estructurado: Roxy responde directamente, explica brevemente el motivo, recomienda cuando aporta valor y formula como máximo una pregunta de seguimiento.
- La conversación reciente se conserva por persona, no por hogar, con un máximo configurable de turnos. Se redactan patrones de claves y contraseñas antes de escribirla y nunca se comparte con otros productos.
- Preguntas como “¿por qué?”, “compárame estas opciones” o “¿qué me recomiendas?” usan Terra; saludos y consultas rutinarias usan Luna para controlar costo y latencia.
- La voz recibe el mismo contexto de Home —perfil, despensa, resumen diario, compras y calendario privado— y tiene instrucciones de sintetizar, comentar y diferenciar hechos de inferencias.
- Consultas vigentes de seguridad alimentaria o retiros fuerzan Terra, `web_search` y `tool_choice="required"`. La respuesta se rechaza si OpenAI no reporta una llamada de búsqueda.
- Las respuestas se crean mediante Responses API con `store=False`.
- Solo el contexto Home del hogar autenticado y el nombre del miembro activo se envían al modelo.
- El consumo se registra en un libro diario exclusivo de Home; no se mezcla con Study o Trading.
- Una receta se convierte primero en una vista previa. Solo `shopping-commit` con `confirmed: true` agrega ingredientes faltantes a `ShoppingListStore`.
- Las bebidas se guardan como `alcoholic` o `non_alcoholic`, se filtran por separado y conservan la misma confirmación antes de pasar ingredientes a la lista.
- Favoritos, notas, fotos y sesiones de cocina con temporizadores permanecen en la memoria privada del usuario.
- Comprar, pagar o controlar electrodomésticos/dispositivos está denegado.

## Datos y endpoints

La memoria privada vive en `ROXY_HOME_MEMORY_PATH`, agrupada por hogar. Incluye preferencias, alergias, productos de despensa, recetas y planes semanales compartidos. El contexto conversacional breve vive en `ROXY_HOME_CONVERSATION_PATH`, separado por miembro. Las identidades personales y sus hashes de contraseña viven separadamente en `ROXY_HOME_ACCOUNTS_PATH`. La lista de compras continúa en su almacenamiento existente y solo recibe los ingredientes confirmados.

La sesión de miembro proporciona a OpenAI y ElevenLabs únicamente el nombre visible, rol y hogar necesarios para dirigirse correctamente a la persona. No se envían contraseñas, hashes, cookies ni la clave de Home.

- `GET /v1/home-food/{user}`
- `PUT /v1/home-food/{user}/profile`
- `PUT /v1/home-food/{user}/pantry`
- `POST /v1/home-food/{user}/recipes`
- `PATCH /v1/home-food/{user}/recipes/{id}`
- `POST /v1/home-food/{user}/recipes/{id}/cooking-sessions`
- `POST /v1/home-food/{user}/cooking-sessions/{session}/timers`
- `DELETE /v1/home-food/{user}/cooking-sessions/{session}/timers/{timer}`
- `POST /v1/home-food/{user}/substitutions`
- `POST /v1/home-food/{user}/recipes/{id}/scale`
- `POST /v1/home-food/{user}/recipes/{id}/shopping-preview`
- `POST /v1/home-food/{user}/recipes/{id}/shopping-commit`
- `POST /v1/home-food/{user}/weekly-plans`
- `POST /v1/home-food/{user}/food-safety`

Todos requieren la autenticación existente de Roxy Home y aplican la misma autorización por usuario.

Los endpoints de identidad son `POST /v1/home-account/login`, `GET /v1/home-account/me`, `POST /v1/home-account/bootstrap` y `GET/POST /v1/home-account/members`. El alta inicial requiere una sesión Home anterior o el Bearer administrativo; las altas siguientes requieren el rol `OWNER`.

## Referencias oficiales

- [Migración y uso de Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses/)
- [Estado de conversación en Responses API](https://developers.openai.com/api/docs/guides/conversation-state/)
- [Generación de imágenes con Responses API](https://developers.openai.com/api/docs/guides/image-generation/)
- [Web search en Responses API](https://developers.openai.com/api/docs/guides/tools-web-search/)
- [Crear una Response](https://developers.openai.com/api/reference/resources/responses/methods/create/)

Las consultas de seguridad priorizan fuentes oficiales vigentes como FDA, USDA y CDC. Roxy debe mostrar los enlaces retornados por la búsqueda y no sustituye el consejo médico ni las instrucciones de una autoridad sanitaria.
