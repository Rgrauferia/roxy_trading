# Inteligencia de productos en Roxy Home

Este módulo pertenece únicamente a **Roxy Home**. No reutiliza claves, memoria,
permisos ni presupuesto de Trading, Finanzas o Study.

## Fuentes

- **Open Food Facts API v3:** identifica alimentos por código de barras y aporta nombre,
  marca, imagen del envase, ingredientes, alérgenos y nutrición declarada. Es una
  base comunitaria; la etiqueta física prevalece.
- **USDA FoodData Central:** añade una referencia nutricional oficial cuando se
  configura `ROXY_HOME_USDA_API_KEY` en el servidor.
- **CPSC Recalls:** busca posibles coincidencias textuales en retiros de productos
  de consumo de Estados Unidos. Una búsqueda sin coincidencias no garantiza que
  no exista un retiro.

Los resultados públicos se guardan temporalmente en SQLite para reducir llamadas.
La clave de caché está cifrada mediante hash y el archivo se crea con permisos
privados. La caché nunca incluye el usuario, el hogar ni su lista de compras.

## Configuración

```dotenv
ROXY_HOME_PRODUCT_CACHE_PATH=data/roxy_home_products.sqlite
ROXY_HOME_PRODUCT_USER_AGENT=RoxyHome/1.0 (product-support; contact: roxy@grau360.com)
ROXY_HOME_PRODUCT_TIMEOUT_SECONDS=8
ROXY_HOME_PRODUCT_CACHE_HOURS=168
ROXY_HOME_USDA_API_KEY=
```

Open Food Facts y CPSC funcionan sin clave. Para USDA, crea una clave exclusiva
de Roxy Home en `api.data.gov` y guárdala solo como variable privada del servicio
Render. Nunca debe añadirse al JavaScript ni al repositorio.

## Contrato

- `GET /v1/home-products/{user_id}/status`
- `POST /v1/home-products/{user_id}/lookup`

Ambas rutas usan la autenticación y autorización del hogar. La consulta no compra
ni añade artículos por sí sola: la persona debe pulsar **Agregar a mi lista**.
