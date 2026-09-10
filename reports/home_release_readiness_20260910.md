# Roxy Home — estado de lanzamiento, 10 de septiembre de 2026

No está listo el producto completo para la demo abierta. Este documento distingue
contenido disponible, revisión pendiente y configuración comercial; no certifica
seguridad médica, nutricional ni aprobación de afiliados.

## Acceso y disponibilidad

La publicación al iniciar esta revisión es 179 / 762ef1ae5, confirmada por HTML y
Render. Existe una corrección local del login: contraseña válida recarga Hoy,
en lugar de cambiar solo el fragmento y dejar el formulario abierto. Recorrido
real con cuenta sintética comprobado; no se han probado las credenciales reales
de Roberto ni su teléfono. Ver `home_login_audit_20260909.md`.

Render muestra «Payment failed»; el usuario debe resolver facturación. No se
puede atribuir a ese aviso el fallo del formulario sin más evidencia. La web
pública responde en la revisión. No se cambiaron tarjetas, pagos ni servicios.

## Recetas

El catálogo de originales contiene seis recetas Wikibooks, de seis cocinas,
31 líneas de ingredientes y 36 pasos originales en inglés, con revisiones y
atribuciones. Tres tienen imagen de fuente enlazada. No confundirlas con
517 fichas del catálogo humano local: 458 son borradores y 59 no llevan ese
estado; de estas últimas, 26 carecen de estado editorial y 24 son cócteles.
Una fuente genérica de seguridad alimentaria no acredita una receta original.

TheMealDB tiene adaptador y pantallas preparados, pero no cuenta/clave de Home
ni licencia comercial confirmadas. No está activado en producción. Las seis
recetas abiertas conservan el original; no tienen aún conversión habilitada
a Compra. No se puede prometer un recetario completo, traducido y comprable.

Mascotas conserva 57 preparaciones, ninguna verificada como original cocinable,
y 94 guías de cuidados. Luna/Ferret conserva ocho fichas pendientes: no son ocho
recetas aprobadas por veterinarios. No se han eliminado perfiles ni fotos en
esta revisión. Ampliar exige fuentes con derechos y revisión apropiada por especie.

## Ejercicio

Ocho fichas educativas, 16 ilustraciones y ningún vídeo: cuatro curls de brazo,
una apertura de pecho, dos curls de pierna y un encogimiento de hombros. No es
una biblioteca equilibrada. Faltan espalda/remo, sentadilla/bisagra, empuje básico,
tronco, peso corporal y actividad aeróbica. Los entrenamientos no están activos.
PostgreSQL privado se probó localmente, no está confirmado en producción; cribado
y plantillas siguen pendientes de revisión profesional.

## Clima y compras

El clima visual publicado es Canvas/CSS, no una escena fotorealista equivalente
a la referencia. Lluvia y tormenta comparten movimiento; todavía no se ha validado
su acabado en una tormenta real desde el teléfono. No confundir modelo Open-Meteo,
radar RainViewer y observación exacta de la calle. No inventar alertas.

En el candidato 180 se corrigió la cabecera del globo: valida frescura, muestra
fecha/fuente del modelo, mantiene 0° numérico real y omite temperatura ausente.
El estado de fallo no afirma que el clima siga disponible. 32 pruebas de clima
aprobadas; no es un cambio del acabado gráfico.

Compra tenía contaminación de preferencias: dieta humana aplicada a mascotas y
limpieza. El arreglo local separa categorías y valida unidades de Instacart.
No acredita una compra real ni una comisión. La afiliación IDP se solicita mediante
Impact y requiere comprobar aprobación/atribución del acuerdo concreto de Roxy.
Ver `home_instacart_review_20260909.md` para documentación oficial y limitaciones.

## Prioridad siguiente

1. Publicar y verificar la corrección de acceso; usuario reintenta sin compartir contraseña.
2. Resolver el aviso de facturación y verificar persistencia privada antes de ampliar datos.
3. Activar una fuente de recetas con derechos confirmados, pasos/fotos fieles y traducción revisada.
4. Completar un catálogo de ejercicio equilibrado y la revisión profesional antes de planes activos.
5. Iterar visuales meteorológicos sobre datos frescos, con pruebas en teléfono físico.

El lanzamiento el próximo mes es una meta del usuario, no una fecha garantizada.
No se añadieron servicios pagados, se aceptaron acuerdos ni se cambiaron cuentas.

## Validación del candidato 180

1.289 pruebas Python aprobadas, 11 omitidas de PostgreSQL en el runtime normal;
41 pruebas Node aprobadas. Las once de PostgreSQL se habían ejecutado con base
real en 179; esa capa no cambia en 180. Rondas anteriores detectaron el ejecutable
Node fuera de PATH y expectativas de versión/texto antiguas: se corrigió el PATH
del comando y se actualizaron esas expectativas; la última ejecución completa
terminó sin fallos. `git diff --check` y sintaxis JS/JSON correctos.

Navegador público previo: Más y Nexo responden, mapa Google visible con modelo
mayormente despejado, no tormenta. La actualización GPS está pendiente del permiso
del navegador; no se solicitó ni concedió permiso. No se modificaron datos del hogar.
Esto no demuestra todavía que el teléfono del usuario use la nueva publicación.

## Publicación comprobada al cerrar

180 / bb81c99e5 publicado en `codex/roxy-home-nfc` y confirmado live en Render.
HTML, JS181 y SW178 públicos HTTP200 idénticos byte a byte; health200/ok.
Navegador meta180, sesión conservada, mapa Google y radar RainViewer cargados;
globo con Modelo Open-Meteo y hora válida visible. Captura guardada/vista:
`/tmp/roxy-home-audit-20260910/globe-180.png`. No prueba de tormenta ni teléfono.
La versión corrige funcionamiento/metadatos, no entrega el rediseño meteorológico.
El aviso de facturación de Render continúa; no bloqueó este despliegue.
