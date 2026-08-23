# Roxy Calendar

Roxy Calendar pertenece únicamente a Roxy Home. No comparte memoria, permisos ni secretos con Trading, Finanzas o Study.

## Lo que funciona ahora

- Calendario privado por miembro del hogar con vistas Hoy, Semana, Mes y Año.
- Creación, edición y eliminación manual de eventos.
- Propuesta y confirmación obligatoria antes de guardar eventos nuevos.
- Comandos de voz para crear, confirmar, consultar y cancelar eventos.
- Eventos diarios, semanales y de lunes a viernes con fecha final obligatoria.
- Detección de conflictos, ubicación, notas, participantes, categorías y recordatorios.
- Exportación `.ics` con alarma para abrir el evento en Apple Calendar, Google Calendar u Outlook.
- Avisos del navegador mientras la PWA está abierta y tiene permiso de notificaciones.

La PWA no puede escribir silenciosamente en el calendario privado de un iPhone. El botón **Agregar al iPhone** descarga un `.ics`; Safari muestra la confirmación nativa y, una vez añadido, Apple Calendar se encarga del recordatorio aunque Roxy Home esté cerrada.

## Persistencia

En Render se usa el disco persistente:

```env
ROXY_HOME_CALENDAR_PATH=/var/data/roxy_home/calendar.json
```

Cada evento se guarda con el identificador del miembro autenticado. Una persona del hogar no puede leer el calendario privado de otra.

## Google Calendar (arquitectura preparada)

Las credenciales deben ser exclusivas de Home y permanecer en el servidor:

```env
ROXY_HOME_GOOGLE_CALENDAR_CLIENT_ID=
ROXY_HOME_GOOGLE_CALENDAR_CLIENT_SECRET=
```

La pantalla informa si el cliente OAuth está configurado, pero no muestra un botón decorativo ni inicia OAuth hasta que exista un URI de redirección autorizado. El flujo definitivo deberá usar autorización OAuth 2.0, cifrar los tokens en servidor y solicitar solamente el alcance de calendario necesario. Hasta entonces, `.ics` es el puente funcional y seguro con el iPhone.
