# Roxy Home · Ejercicio — implementación y entrega

Fecha: 2026-09-08. Candidato local **178**, sin desplegar. La última versión
pública verificada sigue siendo **177**; este bloque no la modifica ni acredita
que Ejercicio o la demo pública estén listos para lanzamiento.

## Alcance implementado

`assets/roxy_fitness.js` y `assets/roxy_fitness.css` incorporan una bienvenida y
cinco pasos de preferencias: contexto personal voluntario, objetivo, disponibilidad,
espacios/material y decisión de guardado. No son un cuestionario clínico ni una
evaluación de aptitud. La imagen de bienvenida se identifica como ilustrativa,
sin presentarla como demostración de técnica.

Las seis secciones son Hoy, Mi semana, Ejercicios, Progreso, Alimentación y
Servicios. Muestran preferencias, disponibilidad o estados pendientes explícitos;
no contienen sesiones asignadas, progreso ficticio, calorías o precios inventados.
Los enlaces a Recetas y al plan de comidas existente solo navegan: no cambian el
perfil alimentario del hogar, el calendario ni Compra.

`roxy_os/fitness/` añade contratos estrictos, consentimiento versionado, API privada
y repositorio exclusivo PostgreSQL. La identidad procede del miembro autenticado;
el acceso compartido del hogar no autoriza leer ni guardar preferencias personales.
Las mutaciones exigen mismo origen, cabecera explícita, versión e idempotencia.
Los cambios de identidad y el rechazo `personal_login_required` limpian el estado
privado de la interfaz, incluidos los fallos durante exportación o eliminación.

La vista previa conserva selecciones solo en memoria; no hay caché personal en
localStorage, IndexedDB ni service worker. La API responde con `private, no-store`.
Retirar consentimiento elimina las preferencias activas; eliminar datos también
retira el consentimiento. Se conserva una versión técnica para rechazar escrituras
antiguas. La retención de copias de seguridad depende de la infraestructura y no
equivale a borrado instantáneo de todos los respaldos.

## Verificación y límites

La tarea principal verificó **1.174 pruebas Python de Home/compras** y **25 pruebas
Node de Ejercicio**. Las pruebas incluyen aislamiento, consentimiento, idempotencia,
revocación, eliminación, sesiones caducadas, respuestas tardías, cambios de persona
y progreso compatible con CSP. Evidencia reproducible: `tests/test_roxy_home_fitness_*.py`
y `tests/test_roxy_fitness_ui.cjs`, además de la suite Home/compras existente.

**No se aprovisionó ni probó PostgreSQL real.** El daemon Docker no estaba
disponible. Las pruebas del repositorio usan un doble SQL sintético: no demuestran
RLS, certificados, concurrencia ni permisos en un servidor PostgreSQL real.
Exportación, persistencia y eliminación completas siguen pendientes de esa
integración. No se contrataron servicios, configuraron secretos ni modificaron
datos públicos; no se reutilizaron claves o memoria de Trading/Crypto.

## Activación pendiente de almacenamiento

1. Aprovisionar una base exclusiva de Home y configurar manualmente
   `ROXY_HOME_FITNESS_DATABASE_URL` en servidor. No hay fallback de datos personales
   a JSON ni migración automática al arrancar.
2. Ejecutar `migrations/fitness/001_foundation.sql` con un propietario separado del
   rol de ejecución. Este último no debe ser propietario, superusuario ni tener
   `BYPASSRLS`, pertenecer al rol propietario o poder crear/alterar el esquema.
   Otorgar únicamente los permisos descritos en la migración.
3. Mantener `ENABLE` y `FORCE ROW LEVEL SECURITY` en **member_state e idempotency**,
   con políticas de lectura y escritura por miembro autenticado. El repositorio
   comprueba ambas tablas, el rol y la versión del esquema antes de leer datos.
4. Configurar certificado raíz de confianza cuando corresponda. La conexión exige
   TLS `verify-full`, verifica que la sesión use SSL y no admite rebajarlo mediante
   la DSN. Preparar cifrado y retención de almacenamiento/respaldos por separado.
5. Ejecutar un recorrido real con dos miembros del mismo hogar: aislamiento de
   lectura/escritura/exportación, consentimiento, revocación, eliminación,
   reintentos, conflictos simultáneos, cambio de sesión y demo caducada. Confirmar
   permisos RLS y fallos de TLS con el rol real antes de habilitar el guardado.

## Entrenamientos y fuentes

No hay catálogo aprobado, cribado habilitado ni plantillas autorizadas. La API
mantiene `can_activate_plans:false`; la evaluación preliminar nunca devuelve
sesiones, prescripciones o autorización médica. Los cálculos de duración son
auxiliares deterministas para futuras entradas revisadas, no una aprobación de
cargas o rutinas. Suplementos, reservas, afiliados, wearables y servicios siguen
inactivos. Habilitar almacenamiento no habilita entrenamientos.

Consultar `reports/home_fitness_sources_20260908.md` para fuentes, licencias y
puertas editoriales/profesionales: CDC y CSEP son enlaces educativos; CSEP no está
licenciado para integrar su cuestionario; wger es una fuente investigada sin
catálogo incorporado y MuscleWiki no está contratado ni conectado. La procedencia
y límites del activo decorativo constan en `reports/home_fitness_asset_20260908.md`.
Ninguna fuente consultada sustituye la revisión profesional y los derechos por
ficha, traducción y medio antes de activar contenido.

## Vista previa local

Desde este worktree y con las dependencias Home instaladas:

```sh
python -m tools.roxy_home_fitness_preview
```

Abrir `http://127.0.0.1:8767/fitness-preview`. El helper crea una cuenta/perfil
sintético en un directorio temporal, descarta la configuración de proveedores y
PostgreSQL, y sirve únicamente en loopback. El guardado queda indisponible; las
selecciones de Ejercicio desaparecen al recargar o cerrar. El helper no se incluye
en la imagen Docker de Home. Este recorrido permite revisar la interfaz sin
escribir en hogares reales y no sustituye las pruebas de integración pendientes.
