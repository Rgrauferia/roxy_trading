# Roxy Home – Lista NFC

## URL estable

Graba exactamente esta URL en el sticker NFC de producción:

```text
https://roxy-home.onrender.com/lista
```

Roxy Home se despliega como un servicio independiente. No comparte dominio, navegación, proceso ni disco con Roxy Trading. Reutiliza el núcleo `ShoppingListStore` de Roxy como biblioteca, de modo que la inteligencia y las futuras órdenes de voz usan el mismo contrato sin unir las dos interfaces.

Antes del primer uso remoto, Render debe tener:

- `ROXY_HOME_API_KEY`: clave larga y aleatoria generada por Render. No debe incluirse en la URL NFC.
- `ROXY_STATE_SYNC_USERS`: identificador exacto del usuario autorizado. Para la instalación personal predeterminada es `local_user`; si Roxy usa otro nombre de cuenta, sustitúyelo aquí y en la pantalla de conexión.
- `ROXY_SHOPPING_LIST_PATH=/var/data/roxy_home/shopping_list.json` (incluido en `render.yaml`).

La primera conexión cambia el Bearer por una cookie `HttpOnly`, `Secure`, `SameSite=Strict` ligada al usuario durante 30 días. La clave no se guarda en JavaScript ni se escribe en el sticker.

## Programar el sticker con NFC Tools en iPhone

1. Instala **NFC Tools** desde App Store y abre la pestaña **Escribir**.
2. Toca **Añadir un registro** y selecciona **URL / URI**.
3. Escribe `https://roxy-home.onrender.com/lista` sin parámetros, usuario ni clave.
4. Toca **OK** y después **Escribir**.
5. Acerca la parte superior del iPhone al sticker hasta que NFC Tools confirme la escritura.
6. Usa **Leer** en NFC Tools y abre la URL detectada para verificarla.
7. Si el sticker quedará en una nevera metálica, colócalo sobre una base anti-metal o separador; el metal puede impedir la lectura de un tag NFC adhesivo normal.
8. Bloquea el tag solo después de comprobarlo. El bloqueo es permanente y no es necesario para que Roxy funcione.

## Programarlo con Atajos de Apple

Atajos no reescribe la URL pública del tag: crea una automatización personal asociada a ese NFC en ese iPhone.

1. Abre **Atajos** > **Automatización** > **Nueva automatización**.
2. Selecciona **NFC**, toca **Escanear** y acerca el iPhone al sticker.
3. Ponle un nombre reconocible, por ejemplo `Roxy Lista Nevera`.
4. Añade la acción **Abrir URLs** con `https://roxy-home.onrender.com/lista`.
5. Activa la ejecución inmediata si la versión de iOS ofrece esa opción y guarda.
6. Prueba con el iPhone bloqueado y desbloqueado. El comportamiento de confirmación puede variar según el modelo y la versión de iOS.

Para que el mismo sticker funcione en cualquier teléfono compatible, conserva también la URL escrita con NFC Tools; una automatización de Atajos solo existe en el iPhone donde se creó.

## Instalar como PWA en iPhone

1. Abre la URL en **Safari**.
2. Conecta una vez el usuario autorizado y `ROXY_HOME_API_KEY`.
3. Toca **Compartir** y luego **Añadir a pantalla de inicio**.
4. Confirma el nombre `Lista Roxy` y toca **Añadir**.
5. Abre el icono instalado y verifica que la lista carga sin volver a escribir la clave.

El shell, la última lista visible y una cola de cambios se conservan para uso sin conexión. Los cambios pendientes se envían al servidor cuando vuelve internet. No se almacena la clave de acceso en IndexedDB, `localStorage` ni `sessionStorage`.

## Operación y recuperación

- **Compra hecha** requiere confirmación, archiva los artículos activos y crea un registro de historial.
- El historial no se elimina al borrar un artículo activo.
- La versión 2 del almacén se migra de forma compatible al leer un archivo de versión 1: agrega `trips` y `user_revisions` sin destruir los artículos existentes.
- Cada operación valida el usuario permitido y el propietario del artículo. Un usuario no puede leer ni modificar filas de otro.
- Roxy Voice utiliza el mismo `ShoppingListStore`; entiende altas con cantidad, consultas y eliminaciones.

## Prueba rápida después de desplegar

1. Abre `https://roxy-home.onrender.com/lista` con Wi-Fi.
2. Agrega `Leche` desde productos habituales y aumenta la cantidad.
3. Abre la misma URL en otro dispositivo, conecta el mismo usuario y confirma la sincronización.
4. Activa modo avión, agrega un artículo y vuelve a conectarte; debe aparecer el aviso de sincronización.
5. Comparte la lista desde el botón superior.
6. Pulsa **Compra hecha**, cancela una vez y luego confirma; comprueba el historial.
