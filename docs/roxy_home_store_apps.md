# Roxy Home en App Store y Google Play

## Estrategia

Roxy Home conservará FastAPI, la base de datos y las integraciones privadas en
el servicio `roxy-home` de Render. La aplicación móvil será un contenedor nativo
construido con Capacitor alrededor de la interfaz web existente; no será un
segundo producto ni compartirá secretos con Trading, Crypto, Finanzas o Study.

## Valor nativo mínimo

Para que la aplicación no sea una simple página empaquetada, la primera versión
de tienda debe incluir:

- inicio de sesión persistente en almacenamiento seguro;
- compartir mediante el menú nativo;
- micrófono y conversación con Roxy con permisos del sistema;
- notificaciones de listas compartidas y recordatorios;
- enlaces universales para NFC, recetas y listas;
- funcionamiento sin conexión para consultar y editar la lista;
- ventana segura del sistema para entregar el pago al comercio;
- accesibilidad, estados de carga, recuperación de errores y cierre de sesión.

## Checkout de productos físicos

Roxy prepara la compra y exige confirmación explícita. Después abre el checkout
autorizado del comercio en una ventana segura. La tienda mantiene cuenta,
dirección, inventario, sustituciones y pago. Roxy no guarda tarjetas ni
contraseñas y no marca una compra como terminada sin confirmación del comercio o
de la persona.

## Fases

1. Consolidar el flujo PWA y los adaptadores de comercios.
2. Crear el proyecto Capacitor con identificadores separados para iOS y Android.
3. Añadir almacenamiento seguro, enlaces universales, notificaciones y navegador
   seguro de checkout.
4. Probar mediante TestFlight y Google Play Internal Testing.
5. Preparar privacidad, capturas, metadatos, cuenta de soporte y notas de revisión.
6. Publicar primero una beta cerrada y después producción.

## Cuentas y secretos

Las credenciales de comercios y OpenAI permanecen exclusivamente en Render. El
cliente móvil recibe sesiones limitadas; nunca se incorporan claves API al
paquete iOS/Android. Apple y Google deben configurarse con cuentas de desarrollador
propias de Roxy Home y con identificadores que no reutilicen los productos de
Trading.

