# Ejercicio — integración PostgreSQL real, 2026-09-08

Verificado localmente: **11 pruebas reales aprobadas en 2,20 s** con PostgreSQL
17.11 y psycopg 3.3.5. También pasan las **34 pruebas de contrato SQL** existentes.
Este resultado comprueba el repositorio y la migración contra un servidor real;
no constituye aprovisionamiento ni comprobación de la base pública de Render.

## Entorno y procedencia

No se encontraron `postgres`, `pg_ctl`, `initdb` ni `psql` instalados. Se compiló
la distribución oficial de PostgreSQL en un directorio temporal propio, sin
instalar un servicio, modificar Docker ni cambiar configuración global.

- Fuente: [PostgreSQL 17.11](https://www.postgresql.org/ftp/source/v17.11/).
- Archivo: `postgresql-17.11.tar.bz2`.
- SHA-256 comprobado contra el archivo oficial:
  `dd27f2b3c59e73ed14aa3324901242bf69a032a6347805f274e6260322d42979`.
- Compilación local: `/tmp/roxy-home-pg-build.CQwLS8`.
- Binarios: `/tmp/roxy-home-pg-build.CQwLS8/install/bin`.
- Intérprete independiente: `/tmp/roxy-home-pg-build.CQwLS8/venv/bin/python`.
- Dependencias de esa venv: psycopg 3.3.5, pytest 9.1.1, Pydantic 2.13.5 y
  cryptography 46.0.7. No se instaló nada en el entorno de Trading.

Cada ejecución crea un clúster nuevo con puerto aleatorio, escucha exclusivamente
en `127.0.0.1`, certificado TLS de dos días, CA temporal y contraseñas aleatorias.
El socket de administración existe dentro del directorio privado temporal.
El propietario de tablas y el rol de aplicación son distintos. Este último no
es superusuario, no tiene BYPASSRLS, ni pertenencia al propietario, ni permisos
DDL o TRUNCATE. Se aplica el archivo real
`migrations/fitness/001_foundation.sql` y sus concesiones mínimas indicadas.

Los identificadores y preferencias son ficticios. No se consultan DSN de
producto, claves Home/Trading, datos de salud reales ni servidores externos.
Al cerrar cada prueba se detiene únicamente su clúster y se elimina su directorio
temporal, incluidas las contraseñas y claves. Al final no quedó ningún proceso
`roxy-fitness-pg-*` activo. Se conserva la compilación y la venv temporal (337 MB)
para poder repetir estas comprobaciones durante la tarea.

## Evidencia cubierta

Las pruebas están en `tests/test_roxy_home_fitness_postgres_integration.py` y
usan `PostgresFitnessRepository` con el controlador real, sin inyectar dobles.

1. TLS real y `verify-full`; nombre correcto y CA correcta funcionan. CA ajena y
   nombre incorrecto fallan. Un DSN con `sslmode=disable` no evita la verificación
   exigida por el repositorio. PostgreSQL rechaza conexiones TCP sin cifrado.
2. Atributos de los roles, propietario distinto, RLS y FORCE RLS en ambas tablas.
   Se rechazan `SET ROLE` al propietario, DDL, TRUNCATE y escritura del marcador.
   El repositorio rechaza una conexión con el rol propietario.
3. Separación de miembros A/B en `member_state` e `idempotency`: consultas directas
   sin filtro solo ven el miembro de la transacción; las lecturas, actualizaciones
   y eliminaciones dirigidas al otro miembro no afectan filas. INSERT y cambios
   de identidad que incumplen `WITH CHECK` fallan. También se verifica FORCE RLS
   usando el propietario sin BYPASSRLS.
4. Consentimiento previo, rollback de un guardado sin consentimiento, preferencias
   persistidas, exportación propia, repetición idempotente y conflictos por carga
   distinta o versión antigua.
5. Revocación borra preferencias; eliminación borra preferencias/consentimiento,
   conserva la versión y un único hash de solicitud, y mantiene intacto al otro
   miembro. Las solicitudes antiguas no pueden recrear datos eliminados.
6. Dos conexiones concurrentes en el primer consentimiento y al guardar perfil:
   solo una gana la versión esperada; la otra recibe conflicto. Se ejercita el
   bloqueo de transacción real de PostgreSQL.
7. La identidad configurada en la transacción desaparece tras commit y rollback;
   una conexión reutilizada sin identidad no ve filas.
8. Deshabilitar RLS o FORCE RLS en el esquema temporal hace fallar el repositorio;
   el fixture restaura ambas condiciones.
9. Parada y arranque reales de PostgreSQL: se conservan el perfil del miembro B,
   la eliminación del miembro A y la protección frente a versiones antiguas.

La interpretación de TLS sigue la [documentación oficial de libpq](https://www.postgresql.org/docs/17/libpq-ssl.html).
Las comprobaciones de propietario, BYPASSRLS y FORCE RLS siguen la
[documentación oficial de seguridad por filas](https://www.postgresql.org/docs/17/ddl-rowsecurity.html).

## Repetición

```sh
ROXY_FITNESS_TEST_PG_BIN=/tmp/roxy-home-pg-build.CQwLS8/install/bin \
  /tmp/roxy-home-pg-build.CQwLS8/venv/bin/python -m pytest -q -rs \
  tests/test_roxy_home_fitness_postgres_integration.py
```

En otro equipo se necesita PostgreSQL con SSL, las dependencias Python indicadas
y un usuario de sistema sin privilegios de root. La suite acepta solamente la
ruta a binarios y genera su propia base; no acepta una base existente ni remota.
Sin binarios, se comprobó una salida explícita de **11 skipped** con la razón de
dependencia ausente. Un skip no debe presentarse como integración aprobada.

## Límites

Quedan fuera de esta comprobación el aprovisionamiento público, el certificado
del proveedor, cifrado del disco/respaldos, retención y restauración de backups,
conexión desde el servicio Home público y recorrido de navegador con PostgreSQL.
RLS usa la identidad fijada por el backend autenticado: el rol SQL pertenece al
servidor, no se entrega a miembros ni al navegador. No es un aislamiento frente
a una persona que ya posea la credencial de aplicación y pueda ejecutar SQL.
No se verifican aquí catálogo, cribado profesional ni activación de entrenamientos.

No se cambió código de producción durante este bloque. La continuidad breve y
estructurada será actualizada por la tarea principal con el estado conjunto.
