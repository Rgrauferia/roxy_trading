# Ejercicio 207 — PostgreSQL local real

Se recompiló PostgreSQL 17.11 y se preparó un servidor Home local con datos
sintéticos persistentes. **11 pruebas de integración PostgreSQL aprobadas en
5,95 s** el 14 de septiembre de 2026. Este bloque no aprovisiona ni modifica
Render, otros productos ni la configuración pública de Home.

## Procedencia y entorno

- Fuente oficial: [PostgreSQL 17.11](https://www.postgresql.org/ftp/source/v17.11/).
- Archivo `postgresql-17.11.tar.bz2`, SHA-256 comparado con el archivo oficial:
  `dd27f2b3c59e73ed14aa3324901242bf69a032a6347805f274e6260322d42979`.
- Compilación privada: `/tmp/roxy-home-pg-207-12g4auxo`.
- Binarios: `/tmp/roxy-home-pg-207-12g4auxo/install/bin`.
- Python independiente: `/tmp/roxy-home-pg-207-12g4auxo/venv/bin/python`.
- Dependencias de `requirements-roxy-home.txt`, más pytest, httpx y
  python-multipart. psycopg 3.3.5, pytest 9.1.1, cryptography 46.0.7.
- OpenSSL de `/opt/homebrew/opt/openssl@3`; no servicio global ni Docker.
- Se tomó solamente el ejecutable Python existente para crear una venv nueva.
  No se instalaron dependencias ni se consultaron secretos de otro producto.

## Comprobaciones ejecutadas

```sh
ROXY_FITNESS_TEST_PG_BIN=/tmp/roxy-home-pg-207-12g4auxo/install/bin \
  /tmp/roxy-home-pg-207-12g4auxo/venv/bin/python -m pytest -q -rs \
  tests/test_roxy_home_fitness_postgres_integration.py
```

Resultado: `11 passed in 5.95s`. Cada prueba usa su clúster nuevo y lo elimina
al terminar. Cubren TLS, separación de roles, RLS, persistencia, concurrencia,
idempotencia, consentimiento y eliminación según el informe de integración
previo del 8 de septiembre. No incluyen todavía el contrato funcional del plan
personal 207, que se verifica por separado.

El clúster de vista previa se comprobó también mediante su rol de aplicación:
TLS 1.3, `sslmode=verify-full`, propietario separado y ENABLE/FORCE RLS activos
en `member_state`, `idempotency`, `activity_plan_state` y
`activity_plan_idempotency`. Las cuatro tienen permisos DML para el rol de
aplicación. El marcador de la base de preferencias sigue en versión 1, como
requiere la migración aditiva `002_activity_plan.sql`.

## Vista previa preservada

- Helper: `tools/roxy_home_fitness_plan_preview.py`.
- URL: `http://127.0.0.1:8771/lista#ejercicio`.
- Cuenta exclusivamente sintética: `loginqa / Local-QA-only-2026`.
- Estado: `/tmp/roxy-home-fitness-207-65_2kmfh`.
- Migraciones aplicadas: `001_foundation.sql` y `002_activity_plan.sql`.
- El directorio de estado es 0700 y su archivo de credenciales SQL es 0600.
- Los valores SQL y la clave de sesión no se imprimen ni se guardan en el repo.
- El helper elimina variables de proveedores y PostgreSQL heredadas de su
  proceso. Las llamadas Requests a proveedores quedan deshabilitadas.
- La cookie de QA es propia y el servidor escucha solamente en 127.0.0.1.
- La vista previa anterior del puerto 8770 conserva su proceso y datos.

El helper reutiliza `LocalPostgres` del archivo de integración real; requiere
los archivos de pruebas y su venv. No se incluye en la imagen de producción.
Al parar su servidor, detiene únicamente el clúster que inició y conserva SQL,
los archivos de Home y la configuración privada para una siguiente ejecución.
Se probó un segundo arranque contra el mismo estado: se rechazó y **el servidor
original permaneció activo**. No crea un servicio que arranque con el sistema.

Reanudar después de detener el proceso anterior:

```sh
/tmp/roxy-home-pg-207-12g4auxo/venv/bin/python \
  -m tools.roxy_home_fitness_plan_preview \
  --pg-bin /tmp/roxy-home-pg-207-12g4auxo/install/bin \
  --port 8771 --state-dir /tmp/roxy-home-fitness-207-65_2kmfh
```

La reanudación renueva certificados locales de dos días antes de arrancar el
clúster detenido. Los cambios Python del backend necesitan reiniciar esta
vista previa; los archivos estáticos se recargan desde el repo. La tarea
principal continúa las pruebas funcionales y de navegador del plan personal,
calendario y progreso. No se ha afirmado que la función pública esté activada.
