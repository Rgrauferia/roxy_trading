# Roxy Live — continuidad con Codex

Fecha: 2026-09-17. PR #11, rama `chatgpt/roxy-live-programming-20260917`.

## Restricción del propietario

Continuar sobre el trabajo existente de Codex, no reemplazarlo. Mantener cambios aislados, revisables y reversibles. No fusionar ni desplegar sobre producción sin comprobar integración, autenticación y estado del servicio. No descartar cambios locales ni usar force-push.

## Punto de partida y alcance de esta continuación

- Inicio de esta entrega: `7b70ee26d6eeab16ea6e07b16aa167ae0120db36`.
- Base main observada al empezar: `f44a456c2d1508751a4411d92449c5ad20e49088`.
- Se añadió `roxy_live_mobile.py` y `tests/test_roxy_live_mobile.py`.
- Se cambió solamente la entrada `pages/1_Roxy_Live.py` para usar el renderer móvil. Esa página fue creada por el PR #11; no es la pantalla original de Opciones.
- Este documento es nuevo.
- No se modificaron `streamlit_app.py`, `roxy_live.py`, las pruebas originales, autenticación existente, voz, chat, órdenes, credenciales, dependencias, Docker ni `render.yaml`.
- La configuración versionada menciona `https://roxy-trading.onrender.com`; eso no acredita qué commit está desplegado ahora.

## Funciones añadidas

La vista móvil separa Mercado, Programación y Noticias mediante un selector. Solo consulta el proveedor del panel seleccionado, además del calendario. Reutiliza los helpers de `roxy_live.py` sin cambiar sus cálculos.

La gráfica compacta adapta una copia de la figura: conserva velas y niveles, reduce etiquetas, mueve soporte y resistencia a texto legible y desactiva el zoom accidental al desplazarse. Permite volver a la vista amplia. Los estilos usan clases `rlm-*`, sin modificar globalmente el terminal.

Muestra bloque actual, siguiente segmento y tiempo restante. Añade ventanas editoriales Pre-Market, Midday y Closing News: 09:15, 12:00 y 15:30 ET en sesión normal. Closing News sigue el cierre confirmado menos 30 minutos. No hay narración ni control de OBS implementados.

Cachés: velas 60 segundos, noticias 300 segundos, calendario 900 segundos. Fragmento de interfaz cada 30 segundos cuando se activa actualización automática. El botón manual respeta las cachés. Sin precios ni noticias ficticios; errores sin cuerpos de respuesta ni secretos.

## Acceso: desactivado por defecto

`pages/1_Roxy_Live.py` no importa el terminal y no hereda automáticamente su login. Por eso esta continuación desactiva la consulta de datos por defecto.

Para un preview público autorizado, el operador puede configurar `ROXY_LIVE_PUBLIC_PREVIEW=1`. Es una opción pública, NO una contraseña ni autenticación. No activarla en producción como atajo para el login privado; revisar primero permisos de redistribución de datos y noticias.

Para futura integración privada, `render_mobile_live(authorize=...)` acepta un validador real del servidor. Se evalúa al entrar y antes de cada actualización. Un resultado distinto de `True`, o una excepción, bloquea las consultas. El callback tiene prioridad sobre la opción pública. No aceptar autenticación desde query strings, perfiles del cliente ni un callback constante.

Prueba local de la vista, solamente en una copia del proyecto y con su entorno configurado:

```bash
ROXY_LIVE_PUBLIC_PREVIEW=1 python -m streamlit run pages/1_Roxy_Live.py --server.address 127.0.0.1 --server.port 8505
```

El renderer nuevo usa variables ya presentes en el proceso. No solicita claves al visitante. La vista es de solo lectura; no consulta cuentas, saldos ni posiciones, y no ejecuta órdenes ni llamadas a Codex/OpenAI.

## Validación realmente ejecutada

```bash
python -m pytest tests/test_roxy_live.py tests/test_roxy_live_mobile.py -q
# 54 passed in 0.53s (26 anteriores + 28 nuevas)
python -m py_compile roxy_live.py roxy_live_mobile.py pages/1_Roxy_Live.py tests/test_roxy_live.py tests/test_roxy_live_mobile.py
```

Las pruebas usan proveedores offline y un sustituto de Streamlit. La construcción de figuras usa Plotly real. Se comprobó que la adaptación móvil no modifica la figura de escritorio ni los precios, que no hay consultas cuando el acceso está desactivado/revocado, la selección de paneles y el escape de HTML.

Blobs locales contrastados con GitHub:
- `roxy_live.py`: `e2ff660b5284c7d66b5979b6a5357fafef1c726a`, intacto.
- `tests/test_roxy_live.py`: `beff7e429259c4f7e27f9b472b5a7dbc1c331d75`, intacto.
- `roxy_live_mobile.py`: `b569ce70b965ccd001e86f76a07add4fe3c90314`.
- `pages/1_Roxy_Live.py`: `e4e421f7d3fc17392bc17b19d84bb0dee6bc8ee2`.

NO se ejecutó la suite completa del repositorio, Streamlit real, Alpaca real, navegador móvil ni pruebas end-to-end. Streamlit no está instalado en el entorno de trabajo; el intento de navegador se detuvo porque faltaba el ejecutable de Chromium. No hay validación visual real de Safari que reportar.

## Pendientes antes de publicar

1. Recuperar íntegramente y revisar `streamlit_app.py`: la conexión devolvió contenido vacío, no evidencia de que el archivo esté vacío. No sobrescribirlo ni sustituirlo por esta vista.
2. Integrar el validador de acceso y la navegación real. `pages/` no acredita compatibilidad con una navegación `st.navigation` personalizada.
3. Ejecutar pruebas con dependencias reales; revisar anchos 320/390/768 y escritorio, scroll, selección de paneles, errores, cierre anticipado y retorno al terminal.
4. Conectar el servicio de Render y verificar rama, commit desplegado, healthcheck y logs. No se ha desplegado esta entrega ni modificado la configuración del servicio.
5. Preferir una previsualización aislada; no crear recursos de pago ni compartir discos de producción sin autorización. Validar derechos de datos antes de un preview público.
6. Integración de avatar/voz/chat, escenas OBS, clips y publicación social sigue pendiente.

## Reversión

Esta entrega añade commits sin reescribir el historial. Para revertir, usar commits de reversión limitados a esta continuación en la rama de desarrollo; no hacer reset de main ni borrar el trabajo de Codex. El commit inicial indicado conserva la versión anterior de la página.
