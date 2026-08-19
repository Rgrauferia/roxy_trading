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
   ROXY_HOME_AI_BUDGET_PATH=/var/data/roxy_home/openai_budget.json
   ROXY_HOME_AI_DAILY_REQUEST_LIMIT=100
   ROXY_HOME_AI_DAILY_OUTPUT_TOKEN_LIMIT=100000
   ROXY_HOME_AI_MAX_OUTPUT_TOKENS=4000
   ```

5. Guarda los cambios y despliega nuevamente `roxy-home`.

La clave permanece en el servidor. La PWA usa la cookie segura de Roxy Home y nunca recibe ni almacena la clave de OpenAI. No hay fallback a claves genéricas: si falta el secreto dedicado, los endpoints de IA responden `503`.

`gpt-5.6-luna` y `gpt-5.6-terra` son los identificadores exigidos por el contrato de Roxy Home. La cuenta/proyecto de OpenAI debe tener acceso a ellos; la aplicación no sustituye silenciosamente otro modelo.

## Comportamiento

- Luna atiende recetas rutinarias, sustituciones y planes semanales rápidos.
- Terra atiende razonamiento profundo.
- Consultas vigentes de seguridad alimentaria o retiros fuerzan Terra, `web_search` y `tool_choice="required"`. La respuesta se rechaza si OpenAI no reporta una llamada de búsqueda.
- Las respuestas se crean mediante Responses API con `store=False`.
- Solo el perfil, alergias y despensa del usuario autenticado se envían al modelo.
- El consumo se registra en un libro diario exclusivo de Home; no se mezcla con Study o Trading.
- Una receta se convierte primero en una vista previa. Solo `shopping-commit` con `confirmed: true` agrega ingredientes faltantes a `ShoppingListStore`.
- Comprar, pagar o controlar electrodomésticos/dispositivos está denegado.

## Datos y endpoints

La memoria privada vive en `ROXY_HOME_MEMORY_PATH`, agrupada por usuario. Incluye preferencias, alergias, productos de despensa, recetas y planes semanales. La lista de compras continúa en su almacenamiento existente y solo recibe los ingredientes confirmados.

- `GET /v1/home-food/{user}`
- `PUT /v1/home-food/{user}/profile`
- `PUT /v1/home-food/{user}/pantry`
- `POST /v1/home-food/{user}/recipes`
- `POST /v1/home-food/{user}/substitutions`
- `POST /v1/home-food/{user}/recipes/{id}/scale`
- `POST /v1/home-food/{user}/recipes/{id}/shopping-preview`
- `POST /v1/home-food/{user}/recipes/{id}/shopping-commit`
- `POST /v1/home-food/{user}/weekly-plans`
- `POST /v1/home-food/{user}/food-safety`

Todos requieren la autenticación existente de Roxy Home y aplican la misma autorización por usuario.

## Referencias oficiales

- [Migración y uso de Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses/)
- [Web search en Responses API](https://developers.openai.com/api/docs/guides/tools-web-search/)
- [Crear una Response](https://developers.openai.com/api/reference/resources/responses/methods/create/)

Las consultas de seguridad priorizan fuentes oficiales vigentes como FDA, USDA y CDC. Roxy debe mostrar los enlaces retornados por la búsqueda y no sustituye el consejo médico ni las instrucciones de una autoridad sanitaria.
