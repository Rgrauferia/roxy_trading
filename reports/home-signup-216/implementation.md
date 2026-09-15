# Home216 — registro sin estados silenciosos

Corrección de Roberto: la persona completa Crear mi hogar privado, no cambia nada,
y después el login devuelve credenciales incorrectas. No asumir confusión de botones.
Consulta operativa solo de existencia para el usuario exacto mostrado: cero cuentas.
No se leen ni modifican contraseñas, recuperación, sesiones ni datos del hogar.
Registro público enabled:true; no evidencia de caída del almacén. Logs del servicio
consultados sin errores de aplicación visibles; no hay trazas de acceso para atribuir
un intento concreto. Causa exacta del dispositivo todavía no certificada.

Defectos reproducibles del cliente215: botón disabled hasta token sin estadovisible,
expiración silenciosa y carga Turnstile sin plazo/reintento. Validación nativa puede
impedir el submit antes de los mensajes JS. El POST no muestra texto de progreso.
Se corrigen estos estados preservando CAPTCHA, origen, rate limits, contraseña12–128,
privacidad de identidad, ausencia de reintentos POST automáticos y códigos de respaldo.

Trabajo216 en curso; pruebas y publicación pendientes. Fixture solo local31751,
PID7350, sesión90845, sin proveedores externos. Los previews8770/8771 se conservan.

## Verificación local

44Pythonpaquete/carga aprobadas y40Node login/recuperación aprobadas. Baseline
independiente272casos backend (cuentas/demo26, identidad246) aprobados, sin cambios
de backend. No sumar ejecuciones solapadas. Pase final conjunto76Node aprobadas (registro36, login/recuperación40).

CUA393×852: envío con contraseña corta muestra12–128caracteres; envío completo sin
CAPTCHA muestra que la cuenta aún no se creó y ofrece reintento. Reintento conserva
campos; desafío sintético aprobado; POST crea una cuenta aislada, muestra progreso
y ocho códigos. Cerrar códigos devuelve confirmación de cuenta creada. Login con
la misma contraseña abre bienvenida. No errores de consola ni overflow. No se
exportan ni guardan códigos; no se completan permisos ni configuraciones del hogar.
Capturas02password-feedback-mobile.jpg y03verification-feedback-mobile.jpg
inspeccionadas juntas. Prueba de app, no Safari físico ni proveedorTurnstile real.

JS sintaxis y git diff --check correctos. Código216 listo para publicar al servicio existente; sin cambios de infraestructura/autenticación.
