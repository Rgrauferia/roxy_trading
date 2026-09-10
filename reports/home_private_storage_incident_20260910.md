# Jardín y Renueva: persistencia y fallo cerrado

10 de septiembre de 2026. Corrección preparada y probada con datos sintéticos;
no se han restaurado ni modificado registros del hogar real desde este bloque.

## Evidencia del incidente

La tarea raíz comprobó en Render que `ROXY_HOME_PLANTS_PATH`,
`ROXY_HOME_PLANTS_IMAGE_DIR`, `ROXY_HOME_DESIGN_PATH` y
`ROXY_HOME_DESIGN_IMAGE_DIR` estaban sin configurar. No encontró el archivo ni
el directorio de plantas en `/app/data`, ni plantas en `/var/data/roxy_home`.
Docker y el Blueprint omitían estas cuatro rutas. Sus valores por defecto
apuntaban a `/app/data`, fuera del disco persistente `/var/data`.

La versión181 no cambió el namespace de cuentas ni migró los registros. Seis
variantes sintéticas de Pothos antiguo, incluido un registro sin
`growing_medium`, se leyeron correctamente. Los lectores anteriores confundían
archivo ausente, error de permisos y JSON corrupto con una colección vacía;
una siguiente mutación podía reemplazar un archivo ilegible. Una respuesta
vacía también podía sustituir la copia local del cliente antiguo.

Esto no prueba que exista una copia recuperable de la planta o su fotografía.
Una captura de pantalla no es el registro original ni un respaldo del diario.

## Cambios del backend

- Rutas por defecto del contenedor y valores declarados del servicio Home:
  `ROXY_HOME_PLANTS_PATH=/var/data/roxy_home/plants.json`,
  `ROXY_HOME_PLANTS_IMAGE_DIR=/var/data/roxy_home/plants`,
  `ROXY_HOME_DESIGN_PATH=/var/data/roxy_home/design.json`,
  `ROXY_HOME_DESIGN_IMAGE_DIR=/var/data/roxy_home/design`.
- Nuevo `home_private_storage.py`, utilizado sólo por plantas y Renueva.
  JSON inválido, estructura inválida, claves duplicadas, números no finitos,
  UTF-8 ilegible o permisos insuficientes producen errores tipados. No hay
  lectura alternativa ni reemplazo silencioso por vacío.
- `HomePlantStorageError` y `HomeDesignStorageError`, con códigos internos
  acotados y mensajes públicos sin rutas, contenido ni secretos.
- `storage_status()` devuelve `NEW` para un archivo nunca inicializado y
  `READY` para un archivo existente válido. `HomePlantStore.snapshot()` lo
  incluye directamente. `NEW` no significa que se haya comprobado la ausencia
  histórica de datos; puede tratarse de una ruta recién configurada.
- Marcador `<archivo>.initialized` dentro del mismo almacenamiento persistente.
  Se crea antes del primer reemplazo atómico. Si desaparece el JSON pero queda
  el marcador, lecturas y escrituras fallan con `missing_initialized`.
  El marcador no es una copia de seguridad. Una primera escritura interrumpida
  después del marcador exige revisión; no se reinicializa automáticamente.
- JSON privado0600, archivo temporal en su mismo directorio, `fsync` de archivo,
  reemplazo atómico y `fsync` del directorio. Bloqueos y errores de E/S no
  confirman una operación fallida.
- Fotos nuevas se escriben sólo dentro de la mutación, después de validar el
  estado bajo el bloqueo. Exclusión de sobrescritura (`O_EXCL`) y permisos0600.
  Si falla el commit, sólo se retira la foto nueva no confirmada. Originales y
  diarios anteriores permanecen. Si falla la confirmación después de un
  reemplazo efectuado, se conserva el medio ya referenciado y el mensaje pide
  actualizar antes de reenviar.
- Renueva usa un nombre único para cada propuesta nueva; un error al guardar
  JSON no sobrescribe la propuesta anterior. Las propuestas anteriores no se
  purgan automáticamente en este bloque; su retención requiere una política.

La tarea raíz coordina los manejadores HTTP503, la marca de versión del cliente
y la preservación explícita de las copias locales. Esta corrección no sustituye
su comprobación del disco montado en producción. Si se pierde el montaje entero,
también puede faltar el marcador: verificar el montaje sigue siendo necesario.

## Comprobaciones

`tests/test_roxy_home_private_storage_182.py`:49 pruebas. Incluyen nuevo estado,
reinicio con otro directorio de trabajo, aislamiento por namespace, fotografía
exacta, permisos, corrupción, estructura anidada inválida, estado desaparecido,
marcador ilegible, symlink roto, fallo del bloqueo, medios no escribibles,
reemplazo denegado, fallo de confirmación posterior al commit, conservación de
diario y de propuesta previa y rutas de Docker/Blueprint.

Junto con plantas, Renueva, diario, comestibles y consentimiento de identificación:
110 pruebas aprobadas. No se ejercitaron fallos reales del disco de producción
ni se afirmaron garantías frente a todos los fallos de hardware.

## Recuperación manual segura pendiente

1. No borrar cachés ni recargar otro dispositivo que aún pueda tener la colección
   antigua. No presentar una copia local como estado actual del servidor.
2. Antes de otro cambio de configuración, inventariar sólo rutas concretas del
   servicio Home, copias/snapshots del disco y posibles originales locales. No
   buscar secretos ni copiar datos de otro producto u otro hogar.
3. Si aparece una fuente válida, conservar una copia inmutable con checksum y
   metadatos; validar JSON, namespace, IDs, fotos y diarios antes de cualquier
   restauración. Conservar también el destino actual si ya tiene datos. No
   fusionar por nombre de planta ni sobreescribir el destino automáticamente.
4. Las rutas `photo_path`, `proposal_path` y fotografías del diario se guardan
   dentro del JSON. Copiar sólo el JSON no mueve las fotos. Reubicar únicamente
   medios que existan y hayan sido verificados; conservar todos los IDs y la
   pertenencia original. No inventar archivos ni fotografías faltantes.
5. Probar primero la copia en un almacenamiento temporal aislado y validar
   recuentos, propietario y checksums. Cualquier restauración real necesita un
   plan explícito y verificación de la tarea raíz.
6. No sincronizar todo el Blueprint para aplicar estas cuatro rutas: su disco
   declarado es1GB y la tarea raíz reporta10GB en el servicio real. Un cambio de
   rutas no autoriza reducir disco ni modificar facturación.

Sin una fuente recuperable, informar de la pérdida sin afirmar recuperación.
No reconstruir el diario, la foto o condiciones anteriores por conjetura.
