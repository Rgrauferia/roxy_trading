# Auditoría integral de Roxy Home — 5 de septiembre de 2026

## Resultado y alcance

Primera pasada funcional y visual sobre Roxy Home pública 163 y candidato 164.
**No certifica que toda la aplicación esté lista para beta.** Se inspeccionaron
las pantallas públicas, el código y el catálogo completo con un inventario
automatizado. No se cocinaron ni se validaron clínicamente todas las recetas.
Las escrituras de prueba se hicieron en un hogar local aislado, sin proveedores,
sin calendarios externos y sin modificar Bella, Luna, ubicaciones ni compras reales.
La habilidad Product Design Audit exigió capturar e inspeccionar las pantallas
antes de formular los hallazgos. Se preservó la identidad crema, verde y dorado.

## Recorrido, evidencia y estado

Las capturas son locales y privadas en `/tmp/roxy-full-audit-20260905/`; no se
subieron al repositorio fotos ni datos privados del hogar. Los nombres siguientes
identifican las capturas inspeccionadas, no promesas de cobertura total.

1. **Hoy — revisión parcial, sin bloqueo visual en la pantalla observada.**
   `02-hoy.jpg`: plan de comidas por día y semana, imágenes visibles. Se conserva
   la pantalla simplificada pedida por Roberto. El plan automático, sus filtros
   y la conversión confirmada a Compra están cubiertos por pruebas automatizadas;
   falta repetir su recorrido completo en navegador después de este despliegue.
2. **Compra — defecto de formulario corregido.** `03-compra.jpg` y
   `10-roxy-texto.jpg`. El mínimo 0.01 con paso 1 rechazaba el valor inicial 1.
   Se corrigió el paso decimal y se guardó desde la UI local un producto ficticio
   de mascotas con cantidad 2. No se hizo ninguna compra real. También se eliminó
   la categoría repetida. La ilustración genérica de bolsa en algunos artículos
   de la lista sigue siendo una oportunidad; no es fotografía verificada de SKU.
3. **Recetas — bloqueo editorial de lanzamiento.** `04-recetas.jpg`.
   Los controles de importación para mascotas se filtraban al recetario humano
   porque CSS anulaba `hidden`; ahora se respeta en toda la interfaz. Búsqueda
   etiquetada y conteo humano separado. El inventario contiene 517 recetas humanas,
   57 preparaciones para mascotas y 94 guías de cuidados. De 668 fichas, 463 están
   marcadas `needs_canonical_review`. El detector encontró 89 fichas con señales
   que requieren revisión, no 89 errores clínicamente confirmados. Ejemplo real:
   Aderezo César incluía el propio aderezo como ingrediente.
   Esos borradores ya se identifican y se bloquean al cocinar/escalar/enviar a
   Compra, incluso si estaban guardados. La revisión con Roxy es explícita; si
   falta IA, no se devuelve la plantilla defectuosa como alternativa terminada.
   Tampoco se generan nuevas imágenes de borradores antes de su revisión.
   El inventario está en `home_catalog_audit_20260905.json`, reproducible con
   `python3 tools/roxy_home_catalog_audit.py`.
4. **Renueva — configuración no equivale a conexión verificada.**
   `05-renueva.jpg`: se inspeccionaron el inicio y las conexiones. Las etiquetas
   de CJ y otros proveedores configurados ahora dicen “Configurada · por verificar”.
   Amazon Associates se identifica como enlaces afiliados, no acceso de catálogo
   API ni precios garantizados. Presupuesto admite decimales válidos. Se conservan
   los proyectos en caché si una carga falla. Falta prueba manual completa de
   subir habitación → análisis real → propuestas → revisión de productos; las
   pruebas automatizadas de proveedores y generación usan respuestas simuladas.
5. **Jardín — estado vacío y continuidad corregidos.** `06-jardin.jpg` y
   `11-jardin-mobile.jpg` (390 × 844). Cero plantas ya no significa “bajo control”.
   Se cuenta cada planta pendiente una sola vez aunque tenga varios cuidados.
   Un fallo de carga conserva la última colección, y el modo sin conexión restaura
   también Jardín. Las APIs de alta, confirmación, observación, fotos y aislamiento
   están cubiertas por tests; el alta manual en UI quedó pendiente por el bloqueo
   del navegador descrito abajo. No hay sensor interior conectado; no se inventan
   medidas ni se riega o compra automáticamente.
6. **Mascotas — perfiles presentes; cobertura universal incompleta.**
   `01-mascotas.jpg`: Bella y Luna aparecen. Se observó una miniatura de Luna en
   la fila de perfiles; no prueba recuperación de su foto original y no fue una
   recuperación realizada en este trabajo. La frecuencia 1/día de Bella es un
   dato previo: ahora dice “Frecuencia guardada”, no recomendación nutricional.
   Se ejecutan regresiones de ferret, aves (periquito/canario/lori), betta, gecko,
   otros grupos, historial, importación y conservación de fotos/ID. Los seis
   perfiles sintéticos ya existentes sólo están en QA. No se hizo una nueva
   revisión veterinaria de cada especie, producto o preparación. Continúan
   pendientes acuarios compartidos, compatibilidad estructurada y fotografías
   exactas del catálogo restante. No hay afiliación veterinaria/Petco/PetSmart
   aprobada ni servicio contratado en este bloque.
7. **Nexo — privacidad y antigüedad mal representadas, corregidas.**
   `07-nexo.jpg`: Robert figuraba en ajustes con ubicación privada y Roxy compartía
   ubicación. La fila principal ocultaba a Robert por filtrar sólo participantes
   que compartían. Ahora incluye a todos sin habilitar ubicación ni permisos.
   Una posición de más de 15 minutos se identifica como última ubicación, no
   “ahora”. El botón que sólo prometía avisar al salir ahora abre lugares guardados
   y explica la limitación; no se afirma crear una alerta inexistente. Falta
   repetir radar/globo/recorridos. Después de desplegar 164 se verificaron en el
   navegador público ambos integrantes y sus etiquetas (`12-public-nexo-164.jpg`).
8. **Calendario — alta confirmada en QA; prueba externa pendiente.**
   `08-calendario.jpg`: Google aparece conectado en producción; no se crearon
   eventos reales. En QA se creó, revisó, confirmó y volvió a abrir “Revisión QA
   del hogar”. Al probar Eliminar, la automatización de la pestaña se bloqueó
   con un timeout; no se confirmó su eliminación. No se atribuye ese timeout a
   un fallo del servidor ni se da por verificada la limpieza por UI. La prueba
   local no tenía Google conectado. Falta comprobar entrega real en teléfono.
9. **Roxy — voz bloqueada por proveedor; texto funcional en QA.**
   `09-roxy-error.jpg`: al intentar Iniciar, el SDK de ElevenLabs devolvió
   `[payment_issue]` / pago pendiente del workspace. El micrófono sí fue obtenido.
   Requiere acción del administrador en facturación; no se modificó la cuenta.
   Nuevo mensaje accionable y formulario escrito mediante la API existente.
   `10-roxy-texto.jpg` confirma respuesta con el producto y cantidad reales del
   hogar de prueba. Se libera el micrófono al cerrar y se cancelan conexiones
   tardías; dos tests verifican las carreras de cierre/reconexión.
10. **Despensa y Más — pantallas revisadas; escrituras/permisos pendientes.**
    Después del despliegue se inspeccionaron `13-public-despensa-164.jpg` y
    `14-public-mas-164.jpg`: formularios, accesos e historial se muestran. Introducir
    despensa como texto con comas es poco guiado; conviene pasar a filas validadas.
    También queda revisar la etiqueta “ubicación aproximada” cuando el dispositivo
    guarda alta precisión. No se compartió información, aceptaron contratos ni
    alteraron datos ni permisos reales para probar. No se completó cada formulario.

## Fallos transversales corregidos

- El comparador de actualización usaba APP 157 contra HTML 163 en producción:
  podía recargar al volver a enfocar la página y perder un formulario abierto.
  Ahora APP coincide con HTML; una prueba evita volver a mezclarlo con la versión
  independiente del caché del service worker. También se atiende `hashchange`
  para enlaces internos y el botón Atrás sin seleccionar dos veces el mismo panel.
- Las peticiones de muchas fotos agotaban el mismo límite que las operaciones
  del hogar. Carga diferida real para imágenes fuera de pantalla, caché de fotos
  y presupuesto separado de peticiones de medios. Las respuestas 429 incluyen
  Retry-After. No se aumentaron límites ni gasto de proveedores.
- Una receta ya revisada con fuentes no se degrada a una plantilla del catálogo
  al recuperar los datos guardados.
- Fallos parciales de Jardín/Renueva ya no sobrescriben caché con listas vacías.

## Comprobaciones y límites

- Versiones candidatas: HTML/APP 164, JS 163, CSS 118, SW 160.
- `node --check` para JS y service worker; suite completa Home + Shopping.
- 105 referencias literales a archivos locales comprobadas: ninguna faltante.
  Esto no certifica fotografías remotas, concordancia visual o enlaces de tiendas.
- Antes de desplegar: servicio público de cobertura indicó 558/683 fotos listas,
  125 faltantes, cola pendiente 0; 80 errores históricos RateLimitError y 45 OSError.
  El estado no debe decir GENERATING con cola vacía: corregido a INCOMPLETE.
- Ninguna API de afiliación nueva, aprobación comercial, compra, nueva suscripción
  ni credencial de otro producto se usó. No se tocó Trading/Crypto.
- La pestaña QA de calendario quedó bloqueada para la automatización tras la
  confirmación nativa. Se pidió cerrar sólo la pestaña local y se continuó con
  pruebas del código. No se contabilizan clics sin resultado como pruebas aprobadas.
- Las credenciales de IA y tiendas no se probaron con solicitudes pagadas masivas.
  Verificar que hay una variable configurada no prueba que una API esté operativa.

## Antes de abrir la beta de cinco días

1. Resolver facturación de voz y repetir llamada completa, interrupción y cierre.
2. Revisar las recetas pendientes por lotes pequeños con fuentes, comprobar
   ingredientes/pasos/porciones y cada fotografía. No aprobar por cantidad.
3. Completar el recorrido UI pendiente, también en teléfono, sin alterar datos reales.
4. Validar Google Calendar, radar y tiendas con respuestas reales; separar lo que
   funciona de lo que sólo está configurado. Confirmar límites/coste de IA y alertas.
5. El almacenamiento aún conserva sólo las últimas 100 recetas, 100 sesiones y
   20 planes por hogar. Revisar esta política explícitamente antes de invitar a
   usuarios intensivos; esta auditoría no cambió ni borró esos datos.

El despliegue y su comprobación final se registran en ROXY_CURRENT_STATE.md y
data/roxy_continuity.json; este informe no convierte pruebas pendientes en completas.

## Verificación pública y hallazgo visual posterior

- 164 se comprobó por HTTP y DOM, con JS 163/CSS 118/SW 160 idénticos byte a byte
  a los archivos probados. Health ok; Bella y Luna presentes; navegación por hash
  operativa, Nexo con ambos integrantes y separación del recetario humano visible.
- La búsqueda pública de Aderezo César devolvió una ficha con aviso de revisión
  (`15-public-recetas-164.jpg`). Su fotografía mostraba una ensalada, no el aderezo.
  Se preparó 165 para poner únicamente esa imagen en cuarentena en servidor y
  cliente (también evita reutilizar su copia en caché). El archivo se conserva;
  no se reemplaza por una imagen genérica. La cuarentena requiere una revisión
  visual explícita de una sustitución antes de levantarla. Se conserva cualquier
  foto privada que la persona haya añadido a su receta.
- En 165 también se corrige el texto de la tarjeta: abrir una receta permite
  revisarla; no significa que ya se guardó automáticamente.
- Servidor local QA detenido al cerrar el bloque. No se añadieron datos sintéticos
  a producción. La pestaña local bloqueada puede cerrarse sin afectar datos reales.
