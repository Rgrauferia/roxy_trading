# Home 217 — navegación sencilla y correcciones móviles

Roberto confirmó «Ya entró; revisa estos detalles»: se cierra el incidente de acceso
como resuelto por confirmación del usuario, sin nueva consulta ni modificación de cuentas.
Después pidió reducir botones, carteles y pasos para encontrar los módulos. Se adopta
Casa / Espacios / Roxy como navegación principal; se conserva el entorno visual aprobado.
La propuesta opcional de conservar Ejercicio en la barra no recibió respuesta; se aplicó
la organización sencilla comunicada. No se implementó creación de avatares desde fotos.

## Cambios

- Espacios reúne ocho destinos únicos con arte existente: Cocina, Ejercicio, Compra,
  Mascotas, Jardín, Renueva, Nexo y Calendario. Abren directamente sus herramientas.
  Despensa tiene acceso contextual en Recetas; Mi día sigue en Casa. Enlaces antiguos
  permanecen válidos. Ajustes, guía, compartir y herramientas avanzadas están plegados.
- Casa ya no repite la cuadrícula de ocho habitaciones. Explorar mi casa abre Espacios.
  Las barras de retorno conservan Volver y no repiten Sala/Cocina. Ejercicio mantiene
  su estudio inmersivo y ofrece un botón textual Espacios para volver.
- Compra centra título, agregar, lista y terminar; comparación, identificación y
  productos habituales se despliegan a petición. No se eliminaron IDs ni datos.
  Cantidad y eliminar quedan en una segunda fila móvil con blancos de 44px.
- Se reprodujo el fallo de las fotos: body.rhl-scene-view main imponía ancho393px y
  padding inferior86px al recorrido, desplazado22px. Su contenido usa ahora una región
  section aislada, avatares2×2, CTA ajustada y pie Continuar fijo dentro del cuaderno.
  El mapa utiliza un icono gráfico en vez de emoji. Sin cambios en identidad, voz,
  autenticación, proveedores ni infraestructura.

## Pruebas y límites

CUA393×852 y320×740: artículo sintético con nombre largo, cantidad1→2→1; controles
44px y límites dentro del viewport. Datos sintéticos anteriores de Fitness conservados;
se añadió solo un artículo QA, no se tocaron hogares reales ni se efectuaron compras.
Bienvenida desde Casa: cuatroavatares dentro del ancho (320: x16..300), Símbolo
seleccionable, vuelta a En casa, continuar llega a revisión sin guardar. Cuaderno:
Español/mezcla→gustos; validación visible, opción no indicar→ritmo. Sin guardar perfil.
Capturas01/06 comparadas juntas;04/05Compra comparadas. Se corrigió título partido
al ancho320 tras la primera captura05; ver verificación final.

Accesos comprobados con CUA: Cocina→Recetas; Ejercicio→estudio; Compra→lista;
Mascotas→alta; Jardín→plantas; Renueva→proyecto; Nexo→hogar; Calendario→agenda.
El regreso usa Espacios, con acceso propio en el estudio de Ejercicio. Pruebas de
rutas no certifican que cada módulo esté completo ni verifican dispositivos físicos.
Proveedores externos deshabilitados enQA8771; no se certifica audio físico.

63 Node escenas/recorrido/integración pasan;18 Python paquete pasan. Prueba adicional
Fitness world pasa (conteo en node-fitness-nav.log). Revisión independiente: ningún
ID perdido/duplicado ni referencias aria/for rotas; hallazgo Despensa corregido.
Publicación pendiente al escribir esta sección. No dar217por público antes de verificar.

Pendientes anteriores: almacenamiento privado Fitness público sin PostgreSQL;
variedad/adaptación profesional y después Mascotas. AppleWatch y avatar/selfie pendientes.
