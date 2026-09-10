# Home 183: almacenamiento de Nexo y Comercio

Fecha: 2026-09-10. Bloque local verificado; este reporte no afirma despliegue ni recuperación de datos. Sólo se modifican los stores de Family/Commerce y pruebas de archivos temporales sintéticos. No se abrieron JSON privados, secretos ni datos de Render.

## Riesgo cerrado en este bloque

- `GET /v1/home-family` llama `_family_context`, que recuerda el directorio con una operación read→write. Antes, JSON corrupto/ilegible se convertía en un hogar vacío y podía reemplazar todo el archivo.
- `GET /v1/home-commerce/{user_id}/recommendations` registra observaciones de precios. Antes podía reemplazar preferencias, preparaciones e historial después del mismo fallback vacío.
- Ambos stores ahora fallan cerrado con `HomeFamilyStorageError` / `HomeCommerceStorageError`, derivadas de `HomePrivateStorageError`. El servicio debe mapear la clase base a 503 sin devolver datos vacíos ni detalles internos.
- Se reutiliza `home_private_storage`: rechazo de JSON duplicado/no finito, UTF-8 inválido, estructuras no válidas, archivo desaparecido después del marcador y errores de E/S; temporales únicos, permisos 0600, fsync y reemplazo atómico.
- Se conserva el bloqueo existente entre instancias y se comunica `committed=True` cuando el reemplazo pudo completarse pero falló la confirmación/fsync/desbloqueo. No se debe reintentar a ciegas en ese estado.
- `storage_status()` distingue `NEW` de `READY` sin exponer rutas. Leer datos válidos no los reescribe. Las operaciones GET conservan su comportamiento previo cuando los datos son válidos; no se han convertido en endpoints completamente libres de escritura.

## Compatibilidad

Family conserva esquema 3 y campos adicionales; acepta campos opcionales ausentes, pero no colecciones mal formadas, IDs contradictorios ni consentimientos de texto que podrían resultar verdaderos por coerción. Commerce conserva datos del esquema 2, migra en memoria a 3 como antes y añade únicamente colecciones de precio ausentes. Se preservan perfiles, preparaciones, handoffs y extensiones; no se mezclan claves de hogar y miembro.

El marcador `.initialized` no es respaldo ni recuperación. Sólo detecta una desaparición después de su creación, en el primer intento de commit de esta implementación. No detecta una pérdida anterior si tampoco existía marcador. No se cambia de ruta ni se reconstruyen datos privados automáticamente.

## Pruebas

Entorno Python 3.12.13 del proyecto:

```text
/Users/robertograu/roxy_trading/.venv/bin/python -m pytest -q \
  tests/test_roxy_home_family_commerce_storage_183.py \
  tests/test_roxy_home_family.py \
  tests/test_roxy_home_commerce.py \
  tests/test_roxy_home_private_storage_182.py

204 passed in 1.71s
git diff --check: limpio
```

El archivo nuevo aporta 52 casos. Cubre lectura nueva sin crear archivos; lectura heredada sin cambios; preservación de fotos/perfiles/extensiones y otro hogar/miembro; reinicio con otro cwd; corrupción, UTF-8, claves duplicadas, esquema desconocido y anidados; permisos; desaparición tras marcador; disco lleno/reemplazo fallido; temporales; fallo tras commit; salida de callback inválida; errores de lock; y 12 escrituras paralelas con instancias independientes. Las regresiones HTTP adicionales corresponden al bloque de integración del agente raíz.

Una primera ejecución con el `python3` del sistema (3.9) no servía para probar la aplicación, que importa `datetime.UTC`; se repitió con el runtime compatible indicado arriba, sin modificar ese código ajeno al bloque.

## Riesgos pendientes, fuera de este arreglo

Auditoría estática, no evidencia de que esos archivos estén actualmente corruptos:

| Prioridad | Store/tema | Siguiente corrección sugerida |
|---|---|---|
| P1 | Calendar, Google Calendar Sync | Reemplazar fallback vacío por error tipado conservando claves individuales y cifrado. GET de estado sólo lee; GET OAuth connect/callback sí muta. |
| P1 | Compra | Mismo fallback vacío y recorte de snapshots a 1.000 artículos. El módulo es compartido con otros productos: adaptación Home, no cambio global sin coordinación. |
| P1 | Presupuesto OpenAI | Lectura corrupta reinicia contadores; distinguir rollover legítimo de corrupción y bloquear nuevas reservas. |
| P1 | Manifiesto/presupuesto de imágenes | Fotos existentes pueden ocultarse y asociaciones/aprobaciones perderse al registrar una nueva; cuota puede reiniciarse. No tratar manifiesto como caché descartable. |
| P1 | Biblioteca/presupuesto de vídeos | Fallback vacío pierde estados y reservas de coste. Sync usa POST, no GET. |
| P2 | Conversación | Fallback vacío; además límite global de 100 personas y 12 entradas por persona, no archivo de conversación completo. |
| P2 | Cuentas | Corrupción ya falla cerrado; falta marcador para detectar desaparición de archivo previamente usado. |
| P1/P2 | Divergencia de rutas | HOME_MEMORY_PATH, CALENDAR_SYNC_PATH, AI_BUDGET_PATH y ELEVENLABS_CACHE_DIR están en YAML pero no en Docker. Verificar variables reales antes de fijar defaults o migrar; no aplicar Blueprint completo. |

HomeFood ya conserva respaldo `.bak` y falla cerrado; no sustituir su almacenamiento perdiendo esa protección. SQLite de recetas está en disco persistente y no se observó fallback vacío. La caché pública de productos usa por defecto `/app/data/roxy_home_products.sqlite`: puede reconstruirse, pero pierde calentamiento y puede aumentar latencia/coste tras desplegar. Miniaturas derivadas, pronósticos y cachés temporales de ofertas son reconstruibles; no tienen la prioridad de perfiles privados o libros de gasto.

No se cambió servicio, interfaz, variables de despliegue, continuidad ni ningún store de Trading en este bloque.
