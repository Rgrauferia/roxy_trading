# Correcciones 176 — recetas, Luna y clima

Estado de este informe: versión 176 publicada y comprobada en Render, commit
`65d829d42`. No significa demo lista ni catálogo completo. Home exclusivamente;
sin tocar Trading.

## Errores reproducidos y cambios

1. Huevos, tortilla, panqueques y tostadas estaban en Carnes; un proceso sustituía
   preparaciones cortas por seis instrucciones genéricas. Eliminada esa sustitución.
   Reparaciones por clave concreta, fuentes con alcance explícito (seguridad, no
   autoría ni ensayo de cocina). Revisadas preparaciones de pollo/huevos, postres,
   pan, pizza y bebidas; cantidades de los pasos principales no contradicen el
   escalado de ingredientes. Los moldes/tiempos siguen siendo orientativos.
2. Cinco originales revisadas recuperadas de duplicados instalados pendientes:
   arroz con vegetales, piña colada sin alcohol, mojito sin alcohol, avena nocturna
   y bowl de atún/garbanzos. 517 fichas humanas: 59 disponibles / 458 borradores.
   No se activaron borradores sólo para aumentar el contador. Filtro Todas,
   categorías sin resultados ocultas y carga distinta de recetario vacío.
3. La respuesta exacta del formulario «Ninguna diagnosticada» bloqueaba Luna.
   Corregida sin editar el perfil; ocho preparaciones conservadas con ocho activos
   individuales. Restricción real mantiene pestaña informativa pero bloquea
   preparación/importación/Compra. Peces/reptiles especialistas no reciben recetas
   inventadas. Véase informe específico de Ferret.
4. Las importaciones humanas cortas ya no se sustituyen por otra receta de igual
   título. Las copias del catálogo reciben correcciones preservando ID, foto,
   notas y favorita. La ausencia de coincidencia no se transforma en pollo.
5. Eliminadas promesas de generación automática en paneles sin video disponible.
6. Nexo usa hora de validez UTC, precipitación, nubosidad y viento; partículas más
   finas con profundidad, día/noche y sin destellos. Dato ausente/vencido (>45 min)
   apaga ambiente; refresco visible cada cinco minutos. Ubicación meteorológica
   guardada, no afirmación de GPS exacto. Modelo Open-Meteo distinto de radar real
   RainViewer. No es una tormenta fotorrealista ni medición de cada calle.

## TheMealDB preparado, no conectado

Adaptador y rutas autenticadas exclusivamente humanas, GET deliberado, sin
mutación ni publicación automática; demo bloquea consultas externas. Sólo envía
búsqueda, nunca perfil. Preserva texto inglés, medidas originales, fuente y foto;
no inventa porciones. Derechos de terceros sin confirmar excluidos. No claves en
navegador ni clave de prueba en producción. UI explica conexión pendiente.

Revisión oficial del 8/9: página principal anuncia $10 de una vez, mientras FAQ
pide nivel comercial Patreon y los términos limitan contenidos de terceros.
No se confirmó que el pago anunciado cubra Roxy comercial/App Store; no se pagó,
contrató ni activó el proveedor. Detalles y fuentes en informe de proveedor.

## Pruebas y evidencia

- 805 tests Home/compras/proveedor aprobados, 58.79 s; node --check de JS principal,
  proveedor y SW, git diff --check correctos. Test de mínimo arbitrario de cinco
  pasos reemplazado: las preparaciones cortas conservan instrucciones reales.
- QA loopback con datos temporales, no producción: Luna QA/Bella QA/Betta QA.
  Luna ocho recetas; huevos en Desayunos y guía de cinco pasos; panel sin video
  oculto; aviso TheMealDB pendiente comprobado en móvil 393 × 852.
- Capturas observadas: `/tmp/roxy-home-fixes-20260908/01-luna-missing-recipes.png`,
  `02-eggs-before.png`, `03-luna-local.png`, `04-eggs-local.png`,
  `05-provider-local.png`. Las fotos humanas no están copiadas en QA aislada:
  «pendiente» local no demuestra ausencia de esas fotos en producción.
- Capturas de clima sintético observadas: `/private/tmp/roxy-weather-20260908-`
  `storm.png`, `sun.png`, `stale.png`; fixture no usa mapa ni ubicación real.
- Versión: HTML/APP176, JS177, CSS126, SW174, proveedorJS1.

## Comprobación pública, 8 de septiembre

- `/lista`, JS, CSS, SW y proveedorJS: HTTP200 y byte a byte idénticos al commit.
  `/health` OK; meta 176 comprobada también en DOM del navegador.
- Bella y Luna conservadas con miniaturas. Luna visible como Ferret, ocho recetas
  y ocho rutas de foto diferentes cargadas al recorrer la lista. Verificación de
  carga, no certificación veterinaria ni recuperación de una foto anterior.
- Huevos con tostada integral guardados: Desayunos, ingredientes conservados,
  cinco pasos propios; ya no aparecen instrucciones genéricas de carne/63°C.
  Panel TheMealDB indica conexión pendiente sin controles activos engañosos.
- Google Maps, Robert y Roxy visibles. Clima estimado parcialmente nublado,
  fuente Open-Meteo, hora de validez y distinción de radar visibles. No se probó
  una tormenta real ni se cambió permiso/preferencia de ubicación. La ficha aún
  muestra velocidad junto a una ubicación antigua: revisar presentación antes
  del lanzamiento para evitar interpretación de movimiento actual.
- Capturas observadas: `06-luna-public-176.png`, `07-eggs-public-176.png`,
  `08-nexo-public-176.png` en `/tmp/roxy-home-fixes-20260908/`.
- Revisión independiente final: 26 tests focalizados aprobados y sintaxis de
  ambos JS tras el último guard de carga. Fixture Node en memoria del proveedor
  comprobó búsqueda explícita, textos originales, rechazo de imágenes ajenas,
  ausencia de escrituras y descarte de respuestas tardías; no proveedor vivo.

## Pendientes explícitos

458 borradores requieren curación; no se han rellenado cientos de recetas ni
validado todas sus fotos. No se generaron nuevas fotos en este bloque. La foto
del wrap mostrada por Roberto contiene un añadido no incluido en la lista:
necesita reemplazo específico revisado; no declarar cobertura fotográfica total.
TheMealDB requiere licencia/clave exclusiva Home y prueba real; traducción,
porciones y revisión de contenido antes de integrar a Compra. Voz sigue con
antecedente payment_issue, no se tocó facturación. Onboarding local y apertura de
registro no se publican en este bloque. La recuperación de la foto original de
Luna no está probada; no se recreó ni alteró su perfil.
