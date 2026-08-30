# Nuestro Nexo: ubicación compartida con consentimiento

## Alcance de la versión web

Roxy Home puede mostrar un mapa real, miembros de la misma casa, posición,
precisión, velocidad estimada por el dispositivo y el trayecto compartido.
Cada persona activa **Ubicación permanente** una sola vez. La preferencia queda
guardada en el servidor y Roxy intenta reanudar la actualización cada vez que
esa persona abre la aplicación. Solo **Desactivar y borrar** revoca esa
preferencia.

En la PWA, “permanente” significa que la elección persiste entre aperturas. El
navegador deja de ser un colector confiable cuando la página está completamente
cerrada o iOS la suspende. Roxy conserva la última posición autorizada para que
los demás puedan verla, pero no la presenta como una posición nueva.

**Detener y borrar** revoca el estado compartido y elimina tanto la última
posición como el trayecto del miembro. Las consultas están limitadas al hogar
autenticado; conocer un identificador de otro hogar no concede acceso.

## Conexiones de confianza externas

El propietario puede crear una invitación de un solo uso que caduca en siete
días. El servidor guarda únicamente el hash del token. Al aceptarla, la persona
entra con alcance `NEXO_ONLY`: puede compartir y ver presencia dentro de Nuestro
Nexo, pero no obtiene acceso a compras, recetas, despensa, calendario, plantas,
Renueva ni ajustes del hogar que la invitó.

El propietario puede retirar esa conexión. Al hacerlo se elimina el vínculo,
la última posición y el recorrido que esa persona compartió con ese Nexo.

## Google Maps exclusivo de Home

1. En el proyecto de Google Cloud de Roxy Home, habilitar Maps JavaScript API.
2. Crear una clave de navegador nueva. No reutilizar las claves de Finanzas,
   Trading ni otros productos.
3. Restringir la clave por referente HTTP a
   `https://roxy-home.onrender.com/*` y, para desarrollo, al origen local exacto.
4. Restringirla únicamente a Maps JavaScript API.
5. Configurar en Render `ROXY_HOME_GOOGLE_MAPS_BROWSER_KEY`. Un Map ID opcional
   puede guardarse en `ROXY_HOME_GOOGLE_MAP_ID`.

La clave de navegador no es un secreto de servidor, pero sus restricciones son
obligatorias para impedir uso desde otros sitios.

## Camino a ubicación real en segundo plano

La aplicación iOS/Android deberá obtener consentimiento del sistema y enviar el
mismo esquema de puntos al backend. Eso habilitará viajes completos, llegada y
salida de lugares, batería y alertas con la app cerrada. Esta web no promete esa
capacidad hasta que exista el colector nativo y sus controles de privacidad.
