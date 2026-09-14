# Roxy Home — preparación de publicación del bloque 204–215

Inspección de solo lectura realizada el 14 de septiembre de 2026. Este informe no
publica código, no cambia Render, no aprovisiona PostgreSQL y no lee valores de
credenciales. La edición 214 y el rediseño 215 siguen en curso mientras se escribe.

## Por qué el teléfono no muestra los cambios

La dirección del teléfono es el servicio público. Una petición nueva, sin sesión
ni caché de navegador, devuelve `APP_VERSION = '203'` en
`https://roxy-home.onrender.com/assets/roxy_list.js`; `/health` devuelve HTTP 200,
`status: ok`, `service: roxy-home`. La página y `/lista-sw.js` también devuelven 200.
Por tanto, los cambios locales posteriores a 203 todavía no están publicados.
No hay evidencia de que borrar los datos del teléfono resuelva esta diferencia.

La comprobación de GitHub coincide:

- Worktree de Home: `/Users/robertograu/.codex/worktrees/roxy-home-renueva`.
- Rama local: `codex/roxy-home-renueva`; HEAD `45ee2152`, documentación posterior
  a 203. Los cambios 204–214/215 todavía están sin commit al inspeccionar.
- Destino histórico de despliegue: `origin/codex/roxy-home-nfc`, que sigue en
  `8b3ab515b5ceeceb19d26abb3b2136e17dbf968c`, la publicación 203.
- El HEAD local desciende de ese commit: un commit local de documentación de
  diferencia antes de registrar la implementación nueva.
- La rama remota `codex/roxy-home-renueva` apunta a otro commit antiguo; subir
  solamente a esa rama no equivale a publicar en el destino histórico.
- Servicio documentado: `roxy-home`, `srv-da0l3vs9v7es739kcmd0`.

GitHub no presenta checks/status de Render en el commit 203. No se abrió el panel
privado de Render en esta inspección; su rama conectada y estado actual de
facturación deben comprobarse allí antes de un eventual despliegue. No se afirma
que el estado de infraestructura histórico siga intacto solo por leer documentos.

## Qué puede verse después de publicar el código

| Función | ¿Necesita PostgreSQL privado de Ejercicio? | Límite |
|---|---|---|
| Casa inmersiva, habitaciones, nuevo acceso Más | No | El código y todos sus medios deben estar incluidos en la imagen |
| Biblioteca, fichas, clases externas y guías educativas | No | Conserva autenticación, fuentes y límites de idiomas/derechos |
| Seis rutinas editoriales y detalle de sus movimientos | No para consultar | Elegir requisitos no equivale a guardar un plan |
| Preferencias personales de Ejercicio | Sí | Consentimiento y cuenta personal |
| Propuesta por disponibilidad y calendario privado | Sí | Revisión y confirmación antes de guardar |
| Peso/estatura opcionales y su historial | Sí | Consentimiento separado |
| Series, repeticiones, carga y duración registradas | Sí | Consentimiento separado, sesión propia y validación |
| Comparaciones de registros y objetivos para repetir | Sí | 214 pendiente de cierre de QA al escribir este informe |
| Calendario compartido de Home ya existente | No usa esta base de Ejercicio | Sigue su almacenamiento, permisos y confirmación originales |

Las rutas de consulta de biblioteca, guías y rutinas no abren la base. Las rutas
personales la necesitan y fallan con `private_storage_unavailable` si no puede
verificarse. No existe respaldo de datos de salud en JSON/localStorage. La API
`/status` indica configuración, **no** certifica conexión, permisos ni migraciones.
Tampoco `/health` prueba PostgreSQL.

La continuidad 213 registra PostgreSQL público sin configurar; el Blueprint de
Home no declara `ROXY_HOME_FITNESS_DATABASE_URL` ni un recurso PostgreSQL. No se
leyó el entorno privado actual, por lo que esto es evidencia documental y de
código, no una inspección reciente de variables del servicio.

## Requisitos concretos de la base privada

El runtime lee únicamente `ROXY_HOME_FITNESS_DATABASE_URL`. Debe apuntar a una
base exclusiva de Home con un rol de aplicación diferente del propietario, sin
superusuario, sin BYPASSRLS, sin pertenencia al rol propietario ni permisos DDL.
No se debe usar la URL administrativa como credencial del runtime.

La conexión fuerza `sslmode=verify-full` y confirma TLS desde `pg_stat_ssl`.
Hace falta un nombre de host que coincida con el certificado y una CA confiable
accesible por libpq; si corresponde, se configura `sslrootcert` en el servidor.
No rebajar TLS para que una prueba pase. Cifrado en reposo, copias de seguridad y
retención son responsabilidad de la infraestructura y deben quedar definidos.

Aplicar manualmente, en orden, mediante el propietario separado:

1. `migrations/fitness/001_foundation.sql`.
2. `migrations/fitness/002_activity_plan.sql`.
3. `migrations/fitness/003_measurements.sql`.
4. `migrations/fitness/004_training_logs.sql`.

Son migraciones de creación, no scripts idempotentes para ejecutar ciegamente
sobre una base existente. Inspeccionar primero su estado y conservar la evidencia
de cuáles se aplicaron. El marcador `schema_version` permanece en 1 por diseño.
El runtime nunca migra automáticamente.

Otorgar solo USAGE del esquema, SELECT de `schema_version` y
SELECT/INSERT/UPDATE/DELETE de estas ocho tablas al rol de aplicación:
`member_state`, `idempotency`, `activity_plan_state`,
`activity_plan_idempotency`, `measurements_state`, `measurements_idempotency`,
`training_logs_state`, `training_logs_idempotency`. Todas las tablas personales
deben conservar ENABLE y FORCE ROW LEVEL SECURITY y su política por miembro.

Antes de declarar guardado público operativo: comprobar desde el runtime de Home
TLS, rol, tablas y RLS; hacer un recorrido con datos de prueba de cuentas separadas,
guardar/recuperar tras reinicio, verificar aislamiento, conflictos de versión,
consentimiento y exportación/eliminación de esos datos de prueba. Las pruebas
locales con PostgreSQL sintético no sustituyen esta comprobación pública.

## Publicación segura de código en el servicio existente

1. Cerrar 214/215, corregir fallos y pasar las pruebas pertinentes, QA de escritorio
   y móvil, `git diff --check` y el checker de continuidad. Durante esta inspección
   el checker detectó HTML/APP 214 frente a continuidad 213: trabajo en curso,
   no una versión ya cerrada para publicar.
2. Verificar que Docker incluye cada script, CSS, dato y medio referenciado.
   `Dockerfile.roxy-home` ya copia los módulos nuevos de Ejercicio, migraciones,
   habitaciones y fondos. Revisar los assets de 215 al terminar. La imagen usa
   Python 3.11 y `psycopg[binary]`; no incluye el helper PostgreSQL local de QA.
3. Registrar solo los archivos de Home revisados. Preservar prototipos, fotos,
   películas y cambios existentes; no usar limpieza ni restablecimiento del
   worktree. No incorporar fixtures privadas de `/tmp` ni credenciales.
4. Comprobar en Render el servicio Home, rama conectada, Dockerfile y disco antes
   de subir. Releer la referencia remota; el destino debe admitir avance normal.
   Si continúa siendo `codex/roxy-home-nfc`, la operación prevista es un push
   normal del commit revisado a esa rama. No force-push ni publicación a `main`.
5. Seguir exclusivamente el despliegue del servicio Home hasta Live. Verificar
   `/health`, HTML/APP, service worker y hashes de los assets contra ese commit.
   Confirmar que la sesión y los datos del hogar permanecen, y probar el acceso
   Más → Ejercicio en la URL pública con el nuevo diseño.
6. Verificar actualización del service worker en el teléfono sin borrar datos
   de Home. La caché debe llevar la nueva versión y los módulos deben conservar
   sus rutas personales fuera de la caché. Un reinicio breve de Render puede
   producir 502 transitorio; esperar recuperación antes de afirmar éxito.

**No aplicar el Blueprint completo.** `render.yaml` incluye otros productos y
declara un disco Home de 1 GB, mientras la continuidad registra una ampliación
autorizada y comprobada a 10 GB. Un despliegue de código en el servicio existente
no debe sustituir configuración, regenerar claves ni cambiar disco/facturación.

## Autorización y límites de esta inspección

Los documentos históricos registran «Roberto autorizó continuar y publicar»
(estado 179) y una ampliación específica del disco Home a 10 GB. Son antecedentes
documentales, no una nueva autorización otorgada por una salida de herramienta.
La conversación vigente autoriza continuar el producto y corregir su presentación;
la tarea principal debe aplicar esa autorización según su alcance real.

No se encontró evidencia de autorización para contratar una nueva base pagada o
cambiar facturación. Antes de ese paso, preparar una opción concreta con coste y
configuración revisables. Los ajustes visuales pueden publicarse por separado de
ese gasto, manteniendo honesta la indisponibilidad del guardado privado.

No se hizo commit, push, deploy, alta de servicio, cambio de entorno ni escritura
en datos del hogar. Este informe es el único archivo creado por esta inspección.

Evidencia local principal: `ROXY_CURRENT_STATE.md`, `data/roxy_continuity.json`,
`reports/home_release_203_20260914.md`, `reports/home_fitness_local_postgres_207_20260914.md`,
`roxy_os/fitness/repository.py`, `roxy_os/fitness/router.py`, las cuatro migraciones,
`Dockerfile.roxy-home` y la sección Home de `render.yaml`.

## Revisión de código y correcciones antes de publicar 215

La tarea principal comprobó después en Render el servicio Home: rama conectada
`codex/roxy-home-nfc`, `Dockerfile.roxy-home`, disco de 10 GB en `/var/data` y ausencia
actual de `ROXY_HOME_FITNESS_DATABASE_URL` al inspeccionar solo nombres y valores
ocultos. Se prepara un despliegue de código del servicio existente, sin contratar
infraestructura. La publicación conserva el límite real del guardado privado.

### Dos defectos encontrados y corregidos

1. **Las cuentas de prueba no podían abrir las rutinas nuevas.** La política de
   demo omitía las rutas de catálogo y detalle de las seis rutinas, así como las
   propuestas y registros privados nuevos. Se añadieron exclusivamente rutas y
   métodos concretos en `home_demo.py`. Los catálogos no necesitan PostgreSQL ni
   gastan cuota IA. Las rutas privadas mantienen identidad personal, CSRF,
   consentimiento, validación, versiones y repositorio protegido. Alias, rutas
   inventadas y activación/generación/compras siguen denegados.
2. **La actualización de la PWA descargaba demasiado código opcional.** El shell
   de instalación había aumentado de su presupuesto de hasta 20 recursos a 36.
   Ejercicio se conserva en el manifiesto versionado, pero se cachea cuando se
   solicita. El shell vuelve a 20 recursos sin aumentar artificialmente el límite
   de la prueba. Todas las rutas `/v1/` y `/api/fitness/` siguen fuera de la caché.

Además, las cuentas cuya demo terminó pueden eliminar sus propias mediciones y
registros, completos o por UUID válido. Esta excepción solo admite DELETE; no
habilita nuevas escrituras tras la caducidad. Continúan obligatorios la identidad
actual, origen, cabeceras explícitas, versión y `confirm_delete: true`.

### Paquete, rutas y pruebas

- Auditoría estática de 192 referencias concretas encontradas en HTML, shell,
  escenas y módulos nuevos: todas existen y están cubiertas por los COPY de la
  imagen Home. `StaticFiles` sirve los assets bajo `/assets`; los catálogos de
  ejercicios conservan validación estricta de identificadores, medios y fuentes.
- Los módulos Python nuevos viven bajo `roxy_os`, que ya se incluye completo.
  Los datos de clases, migraciones, scripts, estilos y fondos nuevos tienen COPY.
  El helper PostgreSQL sintético y sus datos privados no se incorporan al runtime.
- Pase amplio de 78 módulos Python Home sin Ejercicio: **2474 aprobadas y un fallo**
  de shell detectado, posteriormente corregido. No se presenta ese pase como verde.
- **112 pruebas dirigidas finales aprobadas**: 47 nuevas de demo/rutas/privacidad,
  demo pública, paquete y carga/service worker. Incluyen el fallo anterior. Son
  suites solapadas; no sumar 112 al pase amplio como casos independientes.
- Pase de 21 módulos Node Home: **439 aprobadas y dos expectativas antiguas**.
  Referían `today → #hoy` y acceso inferior `recipes`; desde la casa inmersiva son
  `today → #dia` y `kitchen`, respectivamente. Se actualizaron solo esas dos
  expectativas. Las 17 pruebas finales del archivo de globo pasan, incluidas
  cancelación de carga al navegar y adyacencia Cocina/Ejercicio sin reorden CSS.
- La suite de Ejercicio ya la ejecutó la tarea principal; no se repitió aquí.
- Logs: `python-home-regression.log`, `python-release-fixes-final.log`,
  `node-home-regression.log` y `node-globe-final.log` en este directorio.

No queda otro bloqueo concreto detectado por esta revisión del paquete y rutas.
Eso no afirma que todo Home o el entrenador solicitado esté terminado. El guardado
privado de Ejercicio seguirá indisponible en público hasta configurar su base.
Esta revisión hizo las correcciones de código descritas por delegación de la tarea
principal; no hizo push, deploy, cambios de infraestructura ni escrituras en los
hogares reales.

## Build correction after first publication attempt

Render build1508e764 failed before service switch because data/home_fitness_classes_209.json was excluded by the broad data/*.json Git rule. Local file-existence/Docker-copy checks had not checked Git tracking. Added only the public attributed classes catalogue and a specific ignore exception. Audited every explicit DockerCOPY file against git ls-files: this was the only missing source. No privatedata/fixture added. Public203 remained running. Retry uses unchanged app215 code.
