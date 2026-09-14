# Roxy Home — acceso público a la prueba, 14 de septiembre de 2026

## Estado comprobado

Enlace para compartir: https://roxy-home.onrender.com
La raíz redirige a `/home`; una sesión nueva ve «Crear mi hogar · 5 días gratis».
El registro público está habilitado. La primera alta real y la comprobación
positiva de Siteverify continúan pendientes de intervención humana en Safari.
No presentar este informe como un registro completo verificado.

La petición actual de Roberto autoriza que personas nuevas creen sus propios
hogares para probar Home. Se conserva el alcance aprobado: cinco días por hogar,
cinco solicitudes de Roxy al día, sin tarjeta ni cobro automático; después,
consulta de datos guardados. Hasta100hogares,20altas/día,3por conexión/día y6perfiles
por hogar. Voz del dispositivo para recetas; voz oficial premium y generación de
imágenes/vídeos siguen excluidas del piloto. Cuotas globales Home sin ampliación.

## Publicación

Única modificación de configuración: `ROXY_HOME_PUBLIC_SIGNUP_ENABLED=1` en el
servicio Render `srv-da0l3vs9v7es739kcmd0`; las otras44variables no se editaron.
Claves Turnstile existentes, Home exclusivamente; ningún secreto se leyó, copió
ni imprimió. El primer guardado desplegó pero conservó0: `dep-dajnn8e7bikc73cpr1v0`,
Live30.9s. Se detectó mediante endpoint público y el campo del indicador en Render.
Se volvió a editar el único campo, comprobó1 tras salir del campo y guardó.
Final `dep-dajnns8ae00c73ams010`, Live32.8s, mismo commit202
`49a3548a793f794fc34f2e06bc0c725c59063b6d`. No cambio de código/versión/activos.
Durante cada reinicio se observó502 transitorio; recuperación posterior200.

## Evidencia y límites

- GET registro200: enabledtrue, sitekeypresente,5días/5consultas.
- Safari en ventana privada nueva: raíz→home#hoy, acceso anónimo y botón de alta
  visibles; formulario con límites, contraseña12caracteres y códigos de respaldo.
- Widget real Cloudflare carga en español y muestra «Verifique que es un ser humano».
  No se marcó ni se simuló. Se pidió a Roberto completar la cuenta de prueba en esa
  ventana y guardar sus códigos; no enviar contraseñas por el chat.
- POST registro con token deliberadamente inválido422, sincookie; origen ajeno403,
  sincookie. GET cuenta y compras/local_user sin credenciales401, sincookie.
-253pruebas Python dirigidas de demo/cuentas/recuperación aprobadas en98.34s.
-47pruebas Node de registro/recuperación aprobadas.
- Aislamiento entre hogares, cuota/expiración y recuperación tienen evidencia de
  pruebas sintéticas; no se afirma haber completado alta/recuperación real hoy.
- No se crearon cuentas ni se enviaron mensajes a posibles participantes. No se
  modificaron compras, recetas, preferencias ni sesiones existentes por estas
  pruebas. La sesión de Roberto en Codex permanece separada de Safari privado.

Pendiente: alta real, entrada al hogar vacío, códigos/onboarding, salida y nuevo
login; comprobar también rechazo de reutilización de un token real cuando se
pueda hacer sin exponerlo. El registro queda abierto por solicitud de Roberto,
con CAPTCHA y límites originales. No crear cuentas saltándose la validación.

## Texto para compartir cuando se compruebe la primera alta

Te invito a probar Roxy Home: https://roxy-home.onrender.com
Pulsa «Crear mi hogar · 5 días gratis» y crea tu usuario y contraseña.
Tu hogar es privado. La prueba no pide tarjeta ni cobra automáticamente.
Guarda los códigos de respaldo que aparecen al registrarte.
