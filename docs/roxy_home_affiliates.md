# Compras afiliadas en Roxy Home

Esta integración pertenece exclusivamente a **Roxy Home**. No comparte claves,
memoria, permisos ni datos de compra con Roxy Trading, Crypto, Finanzas o Study.

## Experiencia

1. La persona guarda su objetivo de compra en **Despensa → Mi perfil de compra**.
2. Roxy prepara los artículos desde la lista activa o desde los ingredientes que
   faltan para una receta.
3. La pantalla explica por qué recomienda cada búsqueda y avisa cuando hay
   alergias que requieren revisar la etiqueta.
4. La persona elige un comercio y confirma que desea generar los enlaces.
5. El precio, inventario, sustituciones, cuenta y pago se revisan en el comercio.
6. Roxy recuerda la entrega preparada y aprende qué comercios usa con más
   frecuencia cada miembro. Una entrega preparada no se presenta como venta.

Roxy nunca guarda contraseñas o tarjetas del comercio y no completa pagos. La
comisión no participa en la puntuación de productos. La divulgación de afiliado
se muestra antes de abrir cualquier enlace.

## Variables de Render

Guarda todas las credenciales en **roxy-home → Environment**. Nunca las pegues
en JavaScript, en la URL NFC ni en variables de Trading.

```text
ROXY_HOME_COMMERCE_PATH=/var/data/roxy_home/commerce.json
ROXY_HOME_INSTACART_API_KEY=
ROXY_HOME_INSTACART_API_URL=https://connect.instacart.com/idp/v1/products/products_link
ROXY_HOME_INSTACART_AFFILIATE_URL=
ROXY_HOME_KROGER_CLIENT_ID=
ROXY_HOME_KROGER_CLIENT_SECRET=
ROXY_HOME_KROGER_API_URL=https://api.kroger.com/v1
ROXY_HOME_AMAZON_ASSOCIATE_TAG=
ROXY_HOME_WALMART_AFFILIATE_LINK_TEMPLATE=
ROXY_HOME_TARGET_AFFILIATE_LINK_TEMPLATE=
ROXY_HOME_THRIVE_AFFILIATE_LINK_TEMPLATE=
ROXY_HOME_PRICE_FEED_URL=
ROXY_HOME_PRICE_FEED_API_KEY=
ROXY_HOME_PRICE_MAX_AGE_MINUTES=180
ROXY_HOME_PRICE_TIMEOUT_SECONDS=12
ROXY_HOME_PRICE_CACHE_SECONDS=900
```

Las plantillas de Walmart, Target y Thrive deben ser exactamente las entregadas
por el programa afiliado aprobado, usar HTTPS e incluir `{destination}`. Roxy
reemplaza ese marcador por la página del producto codificada. `{query}` es un
marcador opcional. Si la plantilla oficial permite un Sub ID, se puede colocar
`{sub_id}`: Roxy lo reemplaza por el identificador aleatorio de la preparación,
nunca por el nombre, correo o identificador de cuenta de la persona. No se deben
inventar parámetros de atribución.

Ejemplo estructural, no utilizable como credencial:

```text
https://enlace-aprobado-del-proveedor.example/click?dest={destination}
```

## Activación por proveedor

- **Instacart afiliado:** cuando Impact apruebe la cuenta, copia el enlace HTTPS
  exacto de seguimiento a `ROXY_HOME_INSTACART_AFFILIATE_URL`. Este modo abre
  Instacart con atribución, sin afirmar que la lista ya está en el carrito.
- **Instacart Developer Platform:** cuando Instacart apruebe la integración,
  copia la clave de producción a
  `ROXY_HOME_INSTACART_API_KEY`. La clave tiene prioridad sobre el enlace y
  permite producir un solo enlace para la lista completa. Instacart añade los
  parámetros de Impact a la respuesta para partners activos; Roxy no los
  codifica manualmente porque duplicarlos puede romper la atribución.
- **Amazon:** registra Roxy Home como propiedad aprobada en Associates y coloca
  el tracking ID en `ROXY_HOME_AMAZON_ASSOCIATE_TAG`. Esta fase abre una búsqueda
  afiliada por artículo; no muestra precios sin Product Advertising API. Roxy
  muestra junto a esos enlaces la divulgación exigida por Amazon Associates.
- **Walmart:** solicita Affiliate/Impact y pega la plantilla oficial en
  `ROXY_HOME_WALMART_AFFILIATE_LINK_TEMPLATE`.
- **Target:** solicita Target Partners/Impact y usa su plantilla oficial.
- **Thrive Market:** solicita el programa y usa la plantilla oficial cuando sea
  aprobada.

## Comparación personalizada de precios

### Kroger Public APIs

Roxy Home puede consultar directamente `Products (Public)` y `Locations
(Public)` con las credenciales de producción de Kroger. La ubicación se elige
con el código postal guardado en el perfil de compra; si falta, Roxy no atribuye
un precio a una tienda ni inventa una recomendación. El identificador y el
secreto permanecen únicamente en Render y nunca llegan al navegador.

Cada resultado conserva el nombre exacto del producto, su presentación, imagen
oficial cuando Kroger la ofrece, precio observado, comercio y enlace para
revisarlo. Las búsquedas repetidas se sirven desde la caché durante 15 minutos
para reducir latencia y respetar la cuota pública.

La tarjeta **Dónde conviene comprar** usa una fuente de catálogo aprobada y
servidor-a-servidor. `ROXY_HOME_PRICE_FEED_URL` debe ser HTTPS y
`ROXY_HOME_PRICE_FEED_API_KEY` permanece solo en Render. Al abrir Compra o tocar
**Actualizar**, Roxy envía nombres, cantidades, unidades, código postal y
preferencias; no envía correo, contraseña, dirección ni tarjeta.

Contrato de respuesta esperado:

```json
{
  "offers": [{
    "item_name": "Leche",
    "retailer_id": "walmart",
    "retailer_name": "Walmart",
    "product_title": "Leche entera, 1 galón",
    "brand": "Marca",
    "price": 3.48,
    "currency": "USD",
    "package_label": "1 galón",
    "unit_price": 0.027,
    "comparison_unit": "fl oz",
    "organic_certified": false,
    "dietary_labels": [],
    "availability": "available",
    "product_url": "https://enlace-afiliado-aprobado.example/producto",
    "observed_at": "2026-08-23T16:00:00Z",
    "source": "retailer_api"
  }]
}
```

La URL del producto debe ser el enlace oficial o afiliado devuelto por el
proveedor, no uno construido con parámetros inventados. Roxy rechaza HTTP,
precios inválidos, monedas distintas de USD, ofertas vencidas y productos sin
existencia. Solo calcula ahorro entre ofertas con el mismo
`comparison_unit`; nunca compara un paquete con precio por unidad contra otro
de tamaño desconocido. Si la preferencia orgánica es obligatoria, una oferta
solo puede mostrarse como orgánica cuando la fuente entregue
`organic_certified: true`.

Las consultas iguales se conservan 15 minutos en memoria
(`ROXY_HOME_PRICE_CACHE_SECONDS=900`) para reducir costo y límites de las APIs.
Cada perfil, código postal y lista genera una clave de caché distinta; la clave
secreta del proveedor no forma parte de ella ni se guarda en el navegador.

Amazon Creators API puede aportar título, imagen y precio una vez que la cuenta
cumpla los requisitos de acceso. Walmart, Instacart y los demás comercios deben
entrar mediante sus APIs/feeds aprobados o mediante un agregador autorizado.
Los enlaces de búsqueda afiliados existentes no cuentan como fuente de precio.

Después de guardar variables, vuelve a desplegar `roxy-home`. En **Preparar mi
compra**, cada proveedor cambiará de “pendiente” a “listo”.

## Privacidad y personalización

La lista, recetas y despensa pertenecen al hogar. El objetivo, tiendas, marcas,
preferencia orgánica y código postal se guardan por miembro autenticado. No se
guarda dirección exacta ni información de pago. Las alergias son restricciones
de seguridad: Roxy marca todos los resultados para revisión de etiqueta y nunca
garantiza que un producto sea seguro solo por el texto de búsqueda.

El historial local conserva únicamente que Roxy preparó una salida, el comercio,
la cantidad de artículos, el origen (lista o receta) y la fecha. No afirma que
hubo una compra. Las ventas y comisiones reales siguen siendo la fuente de verdad
de Impact, Amazon Associates o el portal del proveedor.

## Estado real de la integración

- Sin aprobación o credencial, el proveedor aparece como **pendiente** y no hay
  botón decorativo ni catálogo simulado.
- Sin feed de precios, la tarjeta explica que falta conectar una fuente y no
  muestra cantidades ni ahorros simulados.
- Con el enlace aprobado, Roxy abre la tienda con atribución y el usuario paga
  allí.
- Con una API de carrito aprobada, Roxy puede entregar la lista completa para
  revisión, pero nunca finaliza el pago.
- Para una aplicación pública con varias instancias, migra el registro de
  comercio de JSON a PostgreSQL antes del lanzamiento. Las credenciales siguen
  siendo secretos del servidor.

## Comprobación local

```bash
.venv/bin/python -m pytest tests/test_roxy_home_commerce.py tests/test_roxy_home_food_api.py tests/test_roxy_home_list.py -q
```

Sin credenciales, la preparación y el perfil siguen funcionando, pero los
botones comerciales quedan deshabilitados. Esto es intencional: producción no
usa productos, precios ni afiliaciones simuladas.
