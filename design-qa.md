# QA215 — Más y seguimiento214

Source visual truth: reports/home-more-215/01-user-public-more.jpg (pantalla rechazada,589×1279), assets/roxy_home/world/living-room-205.png (arte aprobado1672×941), reports/home-fitness-213/session-immersive-mobile.jpg (393×852).
Implementation: reports/home-more-215/02-more-mobile.jpg y03-rooms-mobile.jpg (393×852); reports/home-fitness-214/session-mobile-final.jpg (393×852). Escritorio858×779 observado. Densidad1enpreview; foto usuario≈1,5conSafari. Comparación centrada encontenido, sin atribuir diferencias del sistema a la app.

Las tres capturas Más original/nueva/estancias se abrieron juntas en una llamada.213/214sesión se abrieron juntas en otra llamada. El menú cambia intencionalmente según corrección del usuario; la sesión conserva su composición. Tipografía serif ysans decontroles, ritmovertical, tokensverde/crema, imágenes reales y textosES revisados. No se sustituyó arte por figurasCSS. Detalles legibles en capturas393; no hizo falta recorte adicional.

Hallazgos corregidos: [P2] barra Sala/Cocina+ayuda duplicada desplazaban escenaMás; se ocultó solo la barra enMás yse integró ayuda enhero. [P2] aviso viejo deplan rompía sesión; eliminado alentrar lector. [P2] Verregistro abría preparación; ahoraabre resultados guardados. Evidencia posterior:02-more-mobile.jpg ysession-mobile-final.jpg,record-mobile.jpg.

Interacciones:Más→Mascotas→Más→ajustes;Más→Ejercicio→plan→progreso→Verregistro→sesión. Creación de3sesiones/1registro nuevo deQA preservó anteriores; objetivos15s separadosdecampo realvacío. Consola vacía; nooverflow393. Movimiento solohover limitado yrespetareduce. Límites:prueba enbrowserCodex,noSafari físico; módulos noauditadoscompletos por esta pasada.

final result: passed

---

# QA visual — Roxy Home 213

**final result: passed**

Alcance: Rutinas y registros por ejercicio en el estudio local aprobado211. No certifica entrenador profesional completo, nueva película, vídeo de técnica, voz de8771 ni producción.

Referencia211/mobile-reader-final.jpg e implementación213/session-immersive-mobile.jpg inspeccionadas juntas en la misma entrada visual. Conserva habitación aprobada, protagonista ambiental, tipografía serif, verde/crema, pasos grandes y controles accesibles. Se corrigieron textos de dosis/cue con contraste insuficiente y marcos de formularios que reducían la inmersión; ahora la sesión llena el estudio. La etiqueta de imagen aclara «Escena de ambiente».

CUA real858px y393×852; controles y registro legibles, ancho de página393/393 sin desbordamiento. Se comprobó elección/requisitos, propuesta y revisión, series vacías, omisión explícita, guardado con consentimiento, completar por separado y recuperación tras reiniciar. Descanso0:00→0:05 pausado; consola vacía y viewport restablecido. Los datos visibles son exclusivamente sintéticos. Evidencia final en reports/home-fitness-213/session-immersive-desktop.jpg y session-immersive-mobile.jpg. Capturas anteriores conservadas; su marco anidado no representa el resultado final. Informe implementation.md incluye los límites pendientes.

---

# QA visual — Roxy Home 212

**final result: passed**

Alcance: integración local de mediciones y agenda por disponibilidad dentro del estudio aprobado211. No certifica el módulo completo de entrenamiento, vídeo, voz de la prueba ni producción.

Referencia e implementación inspeccionadas juntas: reports/home-fitness-211/progress-final.jpg y reports/home-fitness-212/progress-desktop.jpg. Se conserva habitación, crema/verde, serif y controles; no se sustituyó la imagen aprobada. Progreso agrupa conteos e historial plegado y añade medidas opcionales en una tarjeta coherente.

CUA real858px y393×852, sin overflow de página, campos legibles y botones de44px o más. Evidencia: reports/home-fitness-212/progress-desktop.jpg y progress-mobile.jpg. Se corrigió el historial que desplazaba las medidas demasiado abajo. No se inventaron valores: las capturas contienen exclusivamente dos registros introducidos en la cuenta sintética local. Formularios de revisión/consentimiento y recuperación comprobados con UI y tests. Ver reports/home-fitness-212/implementation.md para alcance y limitaciones.

---

# QA visual — Roxy Home 211

**final result: passed**

Alcance: integración de la dirección visual210 aprobada («Me encantan») en la
aplicación Home existente. No certifica entrenamiento personalizado, demostraciones
animadas, voz del servidor de prueba ni despliegue público.

## Artefactos y comparación

Fuentes visuales: `reports/home-fitness-210/01-estudio-cinematografico.png`,
`02-casa-jugable.png`, `03-sesion-de-pelicula.png` (1487×1058).
Implementación real: `http://127.0.0.1:8771/lista#ejercicio`, cuenta sintética local,
con plan207 conservado y backend PostgreSQL. Capturas finales:

- `reports/home-fitness-211/entry-r2.jpg` — entrada, 1487×1058.
- `reports/home-fitness-211/map-r3.jpg` — mapa, 1487×1058.
- `reports/home-fitness-211/reader-r4.jpg` — primer movimiento, 1487×1058.
- `reports/home-fitness-211/progress-final.jpg` — plan sintético: 1 realizada, 1 pendiente.
- `reports/home-fitness-211/mobile-map-final.jpg` — marco393×852; captura completa393×997.
- `reports/home-fitness-211/mobile-reader-final.jpg` — 393×852, sin overflow horizontal.

Viewport desktop verificado en DOM1487×1058, DPR1. Fuentes y capturas a1×;
normalizadas al mismo tamaño en el comparador HTML, sin manipular los píxeles.
Los archivos de captura recibidos de CUA son JPEG y usan extensión.jpg.
Se abrieron fuente y aplicación JUNTAS en `reports/home-fitness-211/compare.html`.
Comparaciones finales guardadas: `compare-entry-r2.jpg`, `compare-map-final.jpg`,
`compare-reader-r4.jpg`. Las dos últimas incluyen comparación completa y recorte
ampliado de marca/título; el texto y controles también se inspeccionaron a tamaño
real en la aplicación, y se comprobaron sus nombres y estados en DOM.

## Historial de hallazgos y correcciones

1. P1: el título de entrada heredaba max-width640px y saltaba a tres líneas en
   desktop; el título del mapa heredaba verde sobre vegetación oscura. Evidencia
   `compare-entry-r1.jpg`, `compare-map-r1.jpg`. Se fijaron ancho, escala y color
   explícitos de los títulos del estudio. R2 muestra dos líneas y crema legible.
2. P1: lector limitado por el main global de860px, cortando la escena y ocultando
   el encabezado durante el enfoque. `reader-r1.jpg`. Se eliminó ese límite sólo
   en el estudio, se amplió escena/controles y se ajustaron enfoque y margen del
   lector bajo la barra persistente. `reader-r2.jpg` muestra escena de ancho completo.
3. P1: R2 usaba retrato recortado en vez de la habitación amplia del concepto3.
   `compare-reader-r2.jpg`. Se generó fondo limpio a partir del concepto aprobado,
   conservando persona, pose, silla y cuarto; se mantuvo explícito que es guía escrita.
4. P2: primer encuadre del fondo ancho recortaba la cabeza con cover/bottom.
   `compare-reader-final.jpg` corresponde a R3, anterior a la corrección.
   Se encajó la altura completa y se alineó a la derecha; R4 muestra cabeza y zapatos
   enteros (`compare-reader-r4.jpg`). No se convirtió la imagen en una demostración.
5. P2 móvil: botones Fuerza y Mi semana se solapaban19px, regreso perdía nombre al
   ocultar su texto y algunos controles eran37px. `mobile-map.jpg`. Se separaron
   anclas, añadieron aria-label dinámico y objetivos44px. `mobile-map-final.jpg` y
   DOM393px verifican rectángulos separados, todos los destinos y overflow0.
   El fondo del mapa móvil ahora se desplaza con sus objetos.
6. P1 funcional: lector abierto persistía al cambiar de Mi plan a Progreso.
   Se cierra sólo el lector al cambiar vista y se detiene su voz. DOM real y nueva
   regresión verifican Progreso con conteos guardados y sin PATCH de actividad.

## Superficies obligatorias

- Tipografía: Georgia para titulares y Arial/Helvetica para controles; títulos de
  dos líneas en desktop, jerarquía y caracteres españoles legibles. Diferencias de
  grosor respecto a letras rasterizadas del concepto son aceptables. En móvil la
  entrada usa tres líneas deliberadas y las instrucciones18px con interlineado1.65.
- Espaciado y estructura: entorno de pantalla completa, objetos encima de sus
  zonas, selección visible, herramientas sobre la misma habitación y regreso
  accesible. La guía sustituye el reproductor de muestra por indicaciones y
  transporte reales. No hay solapamientos/recortes P0–P2 pendientes.
- Color: verde profundo, crema, madera cálida y luz dorada; contraste de títulos
  corregido. Panel de instrucción translúcido y botones claros distinguen estado
  activo, navegación y voz. El mapa final es algo más luminoso: refinamiento P3.
- Imagen: fondos raster generados desde cada referencia real; no arte CSS/SVG
  sustitutivo. Originales intactos. R4 conserva habitación y cuerpo entero. Marca
  usa monograma existente y los controles la familia Material Symbols del producto.
- Contenido: botones reflejan biblioteca/plan/progreso existentes; filtros de
  Yoga/Pilates y Fuerza/Calistenia correctos. No hay estadísticas ficticias ni
  etiqueta de vídeo reproducible. Fuentes, texto completo, idioma y licencia
  permanecen accesibles. Escena ilustrativa; no técnica de ejercicio validada.

## Interacciones verificadas

Entrada desde navegación Home; mapa/objetos/selección; filtro fuerza y calistenia;
guías en español; indicación siguiente y movimiento siguiente; Mi plan recuperado;
lector→Progreso; regreso a mapa/entrada/Casa. Móvil393×852 con scroll y sin overflow.
Control de movimiento y reduced-motion cubiertos por pruebas. El botón de voz usa
la firma real de RoxyHomeTour y muestra indisponibilidad controlada en8771, que no
contiene proveedor TTS. No se oye voz masculina alternativa. No se realizaron
escrituras de preferencias, actividades, calendario o datos corporales en este QA.
Logs de consola de la aplicación revisados: [] errores. Un marco de QA temporal
fue rechazado por la política de framing existente; se conservó la protección y
se verificó el viewport real mediante la capacidad del navegador después de cerrar
la pestaña temporal. No se usó ese marco como evidencia móvil.

## Pendiente fuera de esta entrega visual

Demostraciones en movimiento revisadas, entrenamiento profesional adaptado a
edad/capacidad/objetivos/material/tiempo, mediciones/peso/estatura, HealthKit/Apple
Watch y prueba de voz en este servidor. Público203 no modificado. Avatar/Runway
permanecen pausados.

## Checklist de implementación

- [x] Comparar fuente y captura juntas; corregir P0/P1/P2 y repetir captura.
- [x] Conservar archivos, funciones, datos privados y navegación Home.
- [x] Verificar desktop y móvil con dimensiones reales.
- [x] Diferenciar imágenes ilustrativas de demostración y progreso declarado.
- [x] Registrar límites y evidencia; no afirmar publicación ni plan profesional.
