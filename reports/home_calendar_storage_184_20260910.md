# Calendario: protección de persistencia 184

2026-09-10. Implementación local verificada; no commit, push ni despliegue en este bloque. Ningún dato real abierto, recreado o modificado. Servicio, assets, continuidad, prototipos y otros stores quedan fuera del alcance.

## Cambio

`roxy_os/home_calendar.py` deja de convertir JSON ilegible/corrupto en una agenda vacía y de filtrar silenciosamente filas mal formadas. Lecturas y mutaciones fallan con `HomeCalendarStorageError`, derivada de `HomePrivateStorageError`. El handler global ya existente devuelve 503 `HOME_STORAGE_UNAVAILABLE`, `private, no-store` y `Retry-After: 30`, sin divulgar rutas; probado mediante TestClient, sin modificar servicio.

Se reutiliza `home_private_storage`: marcador de inicialización, temporales únicos, reemplazo atómico, fsync, permisos 0600 y errores tipados. Se mantiene flock entre instancias. Fallos de confirmación posteriores al reemplazo o al desbloqueo indican `committed=True`, evitando afirmar que el cambio no se guardó.

Compatibilidad comprobada en el historial: el primer commit de Calendario, `437add5cc`, ya usaba esquema 1, eventos como lista y borradores por propietario. Se conserva ese esquema, los registros de distintos miembros y `legacy:household`, los campos adicionales y los borradores de creación/eliminación. La lectura también conserva archivos sin campo de versión que tengan estructura válida; no reescribe bytes ni añade marcador por una lectura normal. Esquemas futuros desconocidos se rechazan sin sobrescribirlos.

La validación nueva es de estructura e identidad: no ejecuta `_validate()` al leer, no normaliza fechas, textos, zonas, recurrencias ni recordatorios. No cambia el parser de voz, ICS ni reglas de creación/confirmación. Registros inválidos o ambiguos requieren revisión, no se eliminan.

La revisión adicional detectó y corrigió una incompatibilidad: editar un evento legacy sin `source`/`created_at` insertaba `None` en metadatos opcionales. `update()` ahora conserva el registro original y superpone únicamente campos editables validados; conserva también metadatos adicionales y no permite sustituir identidad ni origen mediante el payload. Prueba de lectura/edición/reinicio del registro mínimo aprobada; no se relajó el validador.

## Pruebas

Runtime: `/Users/robertograu/roxy_trading/.venv/bin/python` (sólo intérprete Python 3.12, checkout Home).

- `test_roxy_home_calendar_storage_184.py`: 42 casos nuevos, todos aprobados.
- Junto con `test_roxy_home_calendar.py` y `test_roxy_home_calendar_google.py`: **51 aprobados**, incluida corrección de metadatos legacy.
- Antes de añadir ese último caso, incluyendo Family/Commerce 183, private storage 182 y regresiones API 182/183: **175 aprobados en 2.84 s**.
- `git diff --check`: limpio.

Cobertura: agenda nueva sin escritura; reinicio con otro cwd; preservación byte a byte de lectura; eventos, borradores y extensiones de otros propietarios; JSON/UTF-8/duplicados inválidos; estructuras anidadas, identidades y referencias de borradores; desaparición tras marcador; lectura denegada; disco lleno; temporales; primer commit fallido; lock y confirmación de commit; 12 escrituras paralelas; confirmación explícita de creación/eliminación; recordatorio ICS; GET/POST HTTP 503 y autenticación antes de exponer errores de almacenamiento.

## Límites

El marcador no es respaldo ni recupera datos: detecta desaparición sólo después de su primer intento de commit. No se cambia la ruta del archivo, no se restaura otra copia ni se migra entre miembros/hogares. Los validadores no certifican corrección semántica de datos editados por fuera de la aplicación; las fechas siguen interpretándose mediante las funciones existentes.

Pendientes fuera de este bloque: almacenamiento Google Calendar Sync, Compra compartida con otros productos, manifiestos/presupuestos de medios, conversación y verificación de variables reales de despliegue. El presupuesto IA lo trabaja otro bloque; este reporte no afirma su estado final. No se declara la demo completa.
