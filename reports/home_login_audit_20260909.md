# Roxy Home — diagnóstico de acceso, 9 de septiembre de 2026

## Continuación comprobada el 10 de septiembre

Navegador real, cuenta sintética local en 8768: contraseña incorrecta rechazada
con mensaje visible, después contraseña correcta aceptada, recarga completa y
formulario cerrado. Hoy muestra «Hogar de prueba local» y Plan de comidas.
Captura guardada y vista: `/tmp/roxy-home-audit-20260910/login-success.png`,
1280×720. No es una prueba en el teléfono físico ni con la cuenta de Roberto.
41 pruebas Node (login y Ejercicio) y 5 backend cuentas aprobadas. No se
cambiaron credenciales, perfiles, mascotas ni listas públicas.

Antes del despliegue, público y Render siguen en 179 / commit 762ef1ae5.
Render tiene sesión abierta y muestra «Payment failed»: es un aviso de riesgo
de servicio comunicado al usuario, no evidencia de que cause el fallo de login.
No se abrió el formulario de tarjeta ni se efectuaron pagos.

## Hallazgo confirmado antes de corregir

El handler `login` de `assets/roxy_list.js` acepta la respuesta de autenticación,
pero termina con `location.replace(location.pathname + '#hoy')`. No cierra el
diálogo ni recarga los datos. Cambiar solo el fragmento no recarga el documento;
desde `#hoy` tampoco hay cambio de panel. Por tanto, una contraseña correcta
puede dejar la pantalla de acceso abierta y el contenido sin actualizar.

`git blame` identifica la introducción de este comportamiento en
`ce2fd3f53c`, del 6 de septiembre, anterior al catálogo de Ejercicio.

Prueba sintética nueva: `node --test tests/test_roxy_home_login_ui.cjs`.
El handler real se ejecuta sin red ni cuentas de producción y se modela la
navegación entre fragmentos del navegador. Estado inicial, antes del arreglo:

- 3 regresiones fallan: acceso correcto desde `#hoy`, `#mascotas` y `#ejercicio`.
- 2 controles pasan: contraseña rechazada y almacenamiento no disponible no
  deben simular un acceso ni recargar como si hubiera sido exitoso.

Corrección propuesta: navegación que fuerce una recarga del documento después
de confirmar la cookie, por ejemplo `history.replaceState(...)` seguido de
`location.reload()`. Así se reinicia también el estado en memoria de la cuenta
anterior. Desactivar el botón durante el intento evita solicitudes duplicadas.
Con autorización del agente principal se aplicó el arreglo exclusivamente a
`login`: reemplazo del estado de historial y recarga explícita tras éxito;
botón deshabilitado durante el intento; ante error recupera etiqueta/control
y conserva la contraseña para poder corregirla.

Después del arreglo: **8/8 pruebas Node aprobadas**, incluidas ambas rutas
`/lista` y `/home`, tres fragmentos iniciales, doble envío y reintento tras error.
`node --check assets/roxy_list.js` y `git diff --check` aprobados.
La validación en navegador y el despliegue siguen a cargo del agente principal;
estas pruebas no demuestran que el teléfono real ya use el archivo corregido.

## Fixture de acceso sin sesión inicial

`tools/roxy_home_login_preview.py`, fuera del Dockerfile, está preparada pero
no iniciada por esta subtarea. Comando desde el worktree Home:

```sh
/Users/robertograu/roxy_trading/.venv/bin/python -m tools.roxy_home_login_preview
```

URL `http://127.0.0.1:8768/lista#hoy`; usuario sintético `loginqa`, contraseña
de QA `Local-QA-only-2026`. Solo escucha loopback. Directorio temporal nuevo,
sin datos existentes; elimina variables Home/OpenAI/ElevenLabs/API del proceso,
deshabilita proveedores y rechaza peticiones salientes de `requests`.
Cookie local separada (`roxy_home_login_qa_session`), sin alterar la política
Secure de producción. No crea una sesión de entrada automática. El temporal
se limpia al cerrar normalmente el proceso. `py_compile` aprobado.

## Backend y caché revisados

`tests/test_roxy_home_accounts.py`: **5/5 aprobadas**, 4,43 s, intérprete Home
existente. Incluye sesiones de dos miembros, datos domésticos compartidos,
personalización, cookie HttpOnly/Secure y rechazo de contraseña incorrecta.
Son cuentas sintéticas temporales: no prueban la contraseña del usuario real.

El service worker no intercepta POST ni `/v1/`; la respuesta del login tiene
`private, no-store`. La navegación usa red primero y el HTML pide no almacenar
caché. No se encontró evidencia de que el worker guarde credenciales o la
respuesta de autenticación.

La comprobación de versión en el cliente se ejecuta al cambiar la visibilidad.
Una pestaña que permanece abierta puede seguir mostrando su documento anterior
hasta recarga/comprobación; esto no demuestra que el despliegue público falte.

## Pendiente si el acceso sigue fallando tras la corrección

Observar el mensaje/estado de un intento del propio usuario en su dispositivo,
sin solicitar su contraseña ni repetir intentos automatizados. Un HTTP 401 de
credenciales, 429 de límite y 503 de almacenamiento/configuración tienen causas
distintas de la navegación del frontend.

El archivo configurado en Docker y Render es
`/var/data/roxy_home/accounts.json`. La auditoría de código no comprueba su
existencia real, permisos, contenido ni el entorno actual de Render. Si hace
falta inspeccionarlo, usar diagnósticos que no muestren contraseñas/hashes,
claves ni cookies. No se realizó restablecimiento, creación de cuenta,
modificación pública ni intento con credenciales reales en esta auditoría.
