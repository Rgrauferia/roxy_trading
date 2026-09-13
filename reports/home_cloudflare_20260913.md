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

## Identidad de conexión: publicada y comprobada

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

Publicado commit `7ccc18d0fe637b2c3cff9126c134f1c490d3bd60`, Render
`dep-dajfpc2jnfac73f0n6qg`, Live56.4s. Shell nueva instancia confirma render_cf
efectivo y registro0. Hashes SHA256 de helper y servicio idénticos al código
probado. No cambio de assets: aplicación sigue meta196.

Comprobación pública acotada, sin cuentas nuevas ni contraseñas reales:

- Diez intentos con usuario sintético inexistente:401, sin cookies.
- Siguiente intento normal:429conRetry-After.
- Mismo cliente inyectando sólo X-Forwarded-For:429; no cambia el bucket.
- Inyección de CF-Connecting-IP (sola o junto aXFF):403HTML del edge Cloudflare,
  no respuesta JSON del servicio. No se eludió el bloqueo. No afirmar que esto
  demuestra que el backend recibió una cabecera sobrescrita en esa petición.
- Mismo usuario inexistente desde la conexión saliente del servidor Render:
  401, sin cookie; no comparte el contador agotado del equipo local.
- Confirmada privadamente ausencia del usuario sintético en cuentas. No se creó
  ni eliminó ninguna cuenta. La prueba sólo consumió contadores temporales.
- Health200; sesión Robert conservada tras recargar. Seguridad responde y muestra
  ausencia de códigos vigentes, sin rellenar contraseña ni generar códigos.

Dos conexiones y rechazo de spoofing son evidencia operativa de la frontera
documentada, no garantía de seguridad absoluta ni prueba de cada tipo de cliente.

## Pendientes antes de abrir

Prueba real del widget y Siteverify con token válido, alta y repetición rechazada.
El registro permanece cerrado; no se activó temporalmente para aparentar éxito.
Soporte para cuentas sin códigos de respaldo y alcance incompleto de otros
módulos siguen separados; Cloudflare no los resuelve por sí solo.
Pestaña Cloudflare34 conservada sin claves secretas visibles; Roxy36 conserva
Seguridad. Sin servidores locales nuevos ni archivos temporales con claves.
No redeploy adicional sólo por estas notas posteriores a la publicación.

## Fuentes oficiales

- [Crear widgets](https://developers.cloudflare.com/turnstile/get-started/widget-management/dashboard/).
- [Verificación en servidor](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/).
- [Cabecera de cliente en Render público](https://render.com/articles/host-pocketbase-on-render).
- [Variables de Render](https://render.com/docs/environment-variables).
- [Confianza de proxy Uvicorn](https://uvicorn.dev/settings/).
- [Red privada Render](https://render.com/docs/private-network).
