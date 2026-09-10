# Home 184 — integridad del presupuesto de IA

Estado: implementación local y pruebas, 10 septiembre 2026. Root integra/versiona
y publica. Alcance: `home_ai.py`, llamador de `HomePlantIdentifier.identify`, un
archivo nuevo de pruebas y este informe. No se editan otros almacenes, servicio,
frontend, continuidad, Trading, secretos, modelos, precios, cuotas ni acceso a
proveedores. El llamador de plantas fue autorizado expresamente por root.

## Fallo y corrección

`roxy_os/home_ai.py::HomeAIBudgetLedger._read` convertía cualquier OSError o JSON
ilegible en `{}`, y después trataba una fecha distinta como un día nuevo. Podía
reiniciar contadores al corromperse/desaparecer el archivo. También aceptaba
coerciones/truncamientos de contadores y descartaba campos extra.

Ahora se reutiliza el helper exclusivo Home `home_private_storage` sin editarlo:

- JSON/UTF-8 inválido, claves duplicadas, NaN/Infinity, estructura incompleta,
  contadores booleanos/fraccionarios/negativos/string y fecha inválida fallan
  explícitamente. Se conservan los bytes originales, sin restauración automática.
- Una fecha futura se bloquea (`future_budget_date`); no permite usar un retroceso
  del reloj como nuevo presupuesto. Un día anterior válido **sin una solicitud
  pendiente** reinicia sólo los dos contadores diarios y la fecha, manteniendo
  campos extra de contabilidad/reservas y recibos de liquidación.
- `.initialized` impide tratar una desaparición posterior como primer uso. Un
  archivo legacy válido se adopta también antes de rechazar una reserva agotada;
  leer/snapshot queda bloqueado y persistido para no perder esa protección al
  reiniciar la aplicación. El marcador no es respaldo ni permite recuperar datos.
- Escritura con temporal único, fsync, replace atómico y sincronización de
  directorio. Preserva el archivo anterior ante fallo previo al replace; señala
  `committed=True` cuando no puede confirmar la persistencia después del replace.
- RLock exclusivo del ledger Home para hilos y flock para procesos; presupuesto,
  lock y marcador se crean con permisos 0600. Sin flock se bloquea, no se ejecuta
  silenciosamente sin exclusión. Render/Linux y el entorno QA/macOS soportan flock.
- `record_output_tokens` exige un entero no negativo; registra cero legítimo y
  gasto superior al límite sin truncarlo ni devolver saldo. Los límites vigentes
  se siguen comprobando al reservar. No cambian configuración/env/defaults.
- `HomeAIBudgetStorageError` hereda `HomePrivateStorageError`, sin incluir rutas,
  contenido de archivos, prompts o secretos en su mensaje público.

## Contrato e integración

El ledger existente cuenta **solicitudes y output tokens**, no dólares. Los campos
adicionales de costo/reservas usados en fixtures se preservan, pero no son una nueva
contabilidad USD. No se añaden precios ni se calcula gasto monetario ficticio.

La revisión independiente detectó además una carrera: una respuesta podía consumir
tokens y fallar el registro antes del replace. El archivo anterior válido no
contenía ese gasto y permitía llamar otra vez. Se corrigió con el protocolo que
root aprobó:

1. Se construye/valida el contenido local y se resuelve el cliente antes de reservar.
   Fallos de serialización, imagen local inválida o cliente mal configurado no
   generan una reserva pendiente.
2. La reserva incrementa `requests` y persiste un UUID en `pending_request` en el
   mismo commit atómico, **antes** de entrar al proveedor. Si no se confirma la
   escritura, no se llama al proveedor.
3. Mientras exista un pendiente, ningún nuevo llamador del ledger Home puede
   reservar, incluso en otro hilo/proceso o después de un reinicio. Es una única
   llamada en vuelo para el presupuesto Home, no una nueva cuota por miembro.
4. Una respuesta con `usage.output_tokens` entero no negativo liquida el UUID:
   incrementa tokens, guarda un recibo y limpia el pendiente en un solo commit.
   Cero explícito es válido; ausencia de usage, booleano, string, negativo o decimal
   **no se convierten en cero**. El pendiente se conserva.
5. Si falla el registro antes del replace, el pendiente anterior bloquea nuevo
   gasto. Si falla sólo la confirmación posterior, el recibo permite reintentar la
   misma liquidación sin duplicar tokens. Un monto distinto para el mismo UUID se
   rechaza; un recibo antiguo nunca liquida otra solicitud pendiente.
6. Una excepción del proveedor, incluido timeout, se considera ambigua: no hay
   reembolso ni liberación automática. No se infiere que no consumió tokens por
   no haber recibido respuesta.
7. El pendiente no expira al cambiar de día. Mantiene fecha y contadores de su
   reserva hasta liquidarse. El consumo se atribuye a ese día, junto a la solicitud;
   después se aplica el rollover legítimo. Los recibos sobreviven al rollover para
   que un reconocimiento tardío no duplique consumo en el nuevo día.

El validador también rechaza UUID no string, pendiente con cero solicitudes,
fechas contradictorias, recibos futuros y totales inferiores a sus recibos del día.
Admite consumo legacy sin UUID, pero no reduce contadores para ajustarlos.

Los tres llamadores reales (`_respond`, importación por imagen e identificación de
planta) pasan el UUID explícito. El método de registro conserva compatibilidad de
incremento sin ID sólo cuando no hay pendiente; esa ruta no puede saldar un
pendiente ni reducir consumo. No se usa por estos tres llamadores.

El servicio tenía un handler de `HomePrivateStorageError`, pero `_ai_call` capturaba
`Exception` y lo transformaba en 502. Root ya añadió la propagación antes del catch
genérico; la prueba de integración confirma 503 sanitizado. El mensaje de
`pending_usage` pide esperar/reintentar y revisión si persiste, distinguiendo una
solicitud legítima aún en vuelo de una avería permanente. Este agente no editó el
servicio.
La ruta persistente ya declarada por Home es
`ROXY_HOME_AI_BUDGET_PATH=/var/data/roxy_home/openai_budget.json`; no se comprobó ni
modificó su contenido real en Render.

## Revisión y recuperación de un pendiente sin reiniciar el presupuesto

Procedimiento operativo propuesto, **no ejecutado sobre datos reales**:

- Esperar a que finalice una solicitud realmente en vuelo; no enviar más llamadas
  al proveedor para intentar resolver un timeout anterior.
- Un administrador autorizado inspecciona en servidor el UUID/fecha pendiente y
  contrasta la respuesta o evidencia de consumo del proveedor. No publicar prompts,
  credenciales, rutas privadas ni contenido doméstico en el chat/logs.
- Sólo con conteo autoritativo conocido, usar
  `ledger.record_output_tokens(conteo, reservation_id=uuid_pendiente)` sobre el
  ledger Home configurado. La operación no decrementa solicitudes ni borra historial;
  repetir el mismo UUID/conteo es idempotente.
- Si no existe evidencia de consumo, conservar el pendiente y escalar revisión.
  **No** asignar cero por suposición, editar/eliminar el JSON, borrar el marcador,
  cambiar la fecha ni aumentar cuotas. No hay botón de reset ni autoexpiración.
- Si el archivo está corrupto o falta tras inicializarse, recuperar requiere una
  fuente verificada y revisión operativa fuera de este bloque; el marcador no es
  una copia de seguridad.

## Verificación

Archivo nuevo `tests/test_roxy_home_ai_budget_storage_184.py`: **149 pruebas**.

- 66 combinaciones de corrupción × reservar/registrar/snapshot, conservando bytes.
- Legacy/marker/desaparición, rollover válido/concurrente, fecha futura/reloj,
  campos extra, contadores y límites inválidos, cero real y consumo mayor al tope.
- 40 trabajos en hilos: 40 reservas y 280 tokens. Límite concurrente al cambiar de
  día: 7 aceptadas de 32 intentos. Cuatro procesos reales: 23 reservas aceptadas de
  60 intentos y 253 tokens, sin pérdida de actualizaciones ni exceso de solicitudes.
  Los fixtures esperan/reintentan sólo tras liquidar otra llamada sintética;
  producción no añade una cola ni reintentos automáticos en este bloque.
- ENOSPC antes de replace, primer commit fallido, fsync después de replace,
  permisos0600, lectura denegada y plataforma sin flock.
- Dobles de proveedor: cero llamadas con ledger corrupto o reserva no persistida;
  respuesta exitosa seguida de ENOSPC deja pendiente y bloquea nuevo proceso, con
  recuperación por UUID/uso conocido sin resetear contadores.
- Liquidación duplicada, conflicto, UUID desconocido, recibo antiguo mientras otra
  llamada está pendiente, confirmación incierta tras replace y medianoche/reinicio.
- Ocho formas de usage ausente/inválido × los tres llamadores; cero explícito y
  persistencia previa comprobados en cada uno. Timeout en cada llamador, errores
  locales previos a reservar y segundo proveedor bloqueado mientras el primero
  está en vuelo. Nueve estructuras contradictorias de pendientes/recibos.

**232 pruebas focalizadas aprobadas**: nuevo archivo + `test_roxy_home_ai.py`,
`test_roxy_home_plants.py`, `test_roxy_home_private_storage_182.py` y el archivo de
integración de root `test_roxy_home_ai_storage_api_184.py`. Una corrida de plantas
carecía de `node` en PATH; se repitió con el runtime bundled y pasó.
`git diff --check` correcto. Sólo archivos/datos temporales pytest/subprocesos;
ninguna consulta de IA o datos/secretos de usuarios reales.

## Límites conservados, no resueltos por este bloque

- La API no reserva el máximo de tokens por llamada: una sola llamada admitida
  puede completar por encima del tope restante. Se conserva el total real y se
  bloquea la siguiente reserva; no se cambian cuotas ni max_output_tokens.
- Una solicitud ambigua puede bloquear temporalmente todas las funciones que usan
  este ledger Home hasta reconciliarla. Es la limitación conservadora aprobada,
  no una solución para alta concurrencia ni facturación de múltiples proveedores.
- Los recibos se mantienen sin autoexpiración; antes de escalar mucho volumen se
  necesitará retención/archivo transaccional que conserve la idempotencia.
- No hay evidencia de consumo recuperable automáticamente si la respuesta se
  pierde. No se inventan tokens ni precios para desbloquear el servicio.

Un ledger y su marcador eliminados conjuntamente no se pueden distinguir de una
instalación nueva con este formato; no se proporciona una acción de borrado/reset.
No es una garantía de exactitud de facturación ni de tope monetario duro.
