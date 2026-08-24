# Roxy Calendar

Roxy Calendar pertenece únicamente a Roxy Home. No comparte memoria, permisos ni secretos con Trading, Finanzas o Study.

## Lo que funciona ahora

- Calendario privado por miembro del hogar con vistas Hoy, Semana, Mes y Año.
- Creación, edición y eliminación manual de eventos.
- Propuesta y confirmación obligatoria antes de guardar eventos nuevos.
- Comandos de voz para crear, confirmar, consultar y cancelar eventos.
- Eventos diarios, semanales y de lunes a viernes con fecha final obligatoria.
- Detección de conflictos, ubicación, notas, participantes, categorías y recordatorios.
- Sincronización automática Roxy → Google Calendar por miembro del hogar.
- Exportación `.ics` con alarma como alternativa para Apple Calendar, Google Calendar u Outlook.
- Avisos del navegador mientras la PWA está abierta y tiene permiso de notificaciones.

La PWA no puede escribir directamente en EventKit. Google Calendar funciona como puente: Roxy crea, actualiza o elimina el evento en la cuenta Google autorizada y el teléfono entrega el aviso aunque Roxy Home esté cerrada.

## Persistencia

En Render se usa el disco persistente:

```env
ROXY_HOME_CALENDAR_PATH=/var/data/roxy_home/calendar.json
ROXY_HOME_CALENDAR_SYNC_PATH=/var/data/roxy_home/calendar_sync.json
ROXY_HOME_CALENDAR_ENCRYPTION_KEY=una-clave-aleatoria-larga
```

Cada evento se guarda con el identificador del miembro autenticado. Una persona del hogar no puede leer el calendario privado de otra.

## Activar Google Calendar

Las credenciales deben ser exclusivas de Home y permanecer en el servidor:

```env
ROXY_HOME_GOOGLE_CALENDAR_CLIENT_ID=
ROXY_HOME_GOOGLE_CALENDAR_CLIENT_SECRET=
ROXY_HOME_GOOGLE_CALENDAR_REDIRECT_URI=https://roxy-home.onrender.com/v1/home-calendar/google/callback
```

1. En Google Cloud crea un proyecto exclusivo para **Roxy Home**.
2. Habilita **Google Calendar API**.
3. Configura la pantalla de consentimiento OAuth y añade las dos cuentas del hogar como usuarios de prueba mientras la app no esté verificada.
4. Crea un cliente **Web application** y registra exactamente el URI de redirección anterior.
5. Coloca el client ID y client secret en las variables secretas del servicio `roxy-home` en Render. No uses las credenciales de Trading ni las expongas al navegador.
6. En Roxy Home abre **Calendario → Conectar** y autoriza la cuenta Google correspondiente a ese usuario.

La autorización usa `access_type=offline`, estado aleatorio de un solo uso y el alcance mínimo `calendar.events`. Access tokens y refresh tokens se cifran con AES-GCM antes de persistirse. La interfaz solo recibe `configured`, `connected` y la fecha de la última sincronización.

## Recibir avisos en iPhone

En el iPhone abre **Configuración → Apps → Calendario → Cuentas de calendario → Agregar cuenta → Google**, inicia sesión con la misma cuenta autorizada en Roxy y activa **Calendarios**. Desde ese momento los recordatorios creados en Roxy llegan por Google/Apple Calendar sin mantener la PWA abierta.

La sincronización actual es deliberadamente unidireccional: Roxy → Google. No importa ni expone otros eventos privados de Google dentro de Roxy Home.
