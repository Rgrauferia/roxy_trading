# Home — Cloudflare Turnstile, 13 de septiembre de 2026

## Configuración comprobada

- Cuenta Cloudflare autenticada en el panel; no se crearon ni reutilizaron contraseñas.
- Un widget `Roxy Home — registro`: Managed, un hostname
  `roxy-home.onrender.com`, sin pre-clearance. No migración de DNS ni alojamiento.
- Cuatro variables añadidas únicamente al servicio Render Home
  `srv-da0l3vs9v7es739kcmd0`: `ROXY_HOME_TURNSTILE_SITE_KEY`,
  `ROXY_HOME_TURNSTILE_SECRET_KEY`, `ROXY_HOME_SIGNUP_HOSTS`,
  `ROXY_HOME_PUBLIC_SIGNUP_ENABLED=0`. Se conservaron las 37 variables previas.
- Claves transferidas directamente entre formularios del proveedor y Render;
  no se imprimieron ni guardaron en archivos, repositorio o almacenamiento local
  del navegador. Se descartó la copia temporal en memoria del controlador.
- Render `dep-dajfkq0jo6nc73dmcvkg`, commit196 `27ae50623e6b65fb9d9f878ba233c268b2e551de`,
  Live en36.0s. Shell de la nueva instancia confirma presencia de ambas claves,
  hostname correcto y registro cerrado. Health200 y registration200/enabledfalse.
- Llamada directa desde servidor al Siteverify oficial con token deliberadamente
  inválido: HTTP200, successfalse, invalid-input-response. Prueba conectividad
  y rechazo, **no** un registro humano exitoso ni prueba positiva del widget.

## Identidad de conexión: implementada y probada, pendiente de despliegue

La instancia Docker usa un worker, proxy_headers=true y confianza Uvicorn sólo
en127.0.0.1; FORWARDED_ALLOW_IPS y overrides UVICORN no están configurados.
`request.client.host` por sí solo no demuestra identidad del visitante detrás
del balanceador. No activar confianza `*` ni usar el primer X-Forwarded-For.

Se implementó el modo opt-in `ROXY_HOME_CLIENT_IP_SOURCE=render_cf`, exclusivo de
metadatos Render válidos y Host canónico. CF-Connecting-IP único y válido se
usa sólo para cuotas, nunca autenticación. Fuera de ese modo se conserva socket.
Cabeceras/configuración inválidas fallan cerradas, sin mensajes con IPs o secretos.

Frontera operativa: tráfico público entregado por Cloudflare/Render y
administradores/servicios propios del workspace confiables para el transporte.
Render documenta sustitución de CF-Connecting-IP al ingreso público. Un servicio
privado controlado por el administrador podría falsear un bucket; eso no sustituye
contraseña, cookie, Turnstile ni cupos globales. No se afirma aislamiento frente
a administradores del mismo workspace ni se contrata otro plan para aparentarlo.

`home_client_identity.py` integra las cuotas de API, login, recuperación y admisión
durable. Una única IP global normalizada, sin multicast/zonas/listas/duplicados;
URL y Host estrictos, sin confiar en XFF ni cambiar Uvicorn. Excepción genérica503.
Se añadió el modo a Render con **Save only**, para el siguiente despliegue del
código validado; el registro permanece0. Health no depende de cabeceras de cliente.
Pruebas finales:3155Python aprobadas/11PostgreSQL omitidas (74.92s),47Node
registro/recuperación aprobadas. Incluye238 casos unitarios nuevos y8integración.
Un fallo inicial de fixture esperaba503 donde CSRF devolvía403; caso ajustado
sin cambiar la protección de origen para probar la frontera correcta.

## Pendientes antes de abrir

Publicar/probar el ajuste de cuotas; prueba real del widget y Siteverify con
token válido, alta y repetición rechazada. El registro permanece cerrado.
Soporte para cuentas sin códigos de respaldo y alcance incompleto de otros
módulos siguen separados; Cloudflare no los resuelve por sí solo.

## Fuentes oficiales

- [Crear widgets](https://developers.cloudflare.com/turnstile/get-started/widget-management/dashboard/).
- [Verificación en servidor](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/).
- [Cabecera de cliente en Render público](https://render.com/articles/host-pocketbase-on-render).
- [Variables de Render](https://render.com/docs/environment-variables).
- [Confianza de proxy Uvicorn](https://uvicorn.dev/settings/).
- [Red privada Render](https://render.com/docs/private-network).
