# Renueva 175 — presupuesto y procedencia de las recomendaciones

Estado: implementación `09298929e` desplegada y comprobada en público el 7/9/2026;
594 pruebas Home/compras aprobadas (50.60 s). JS/SW y diff válidos.

## Alcance

Auditoría visual limitada al proyecto sintético «Sala QA» y su comparativa de
presupuesto en móvil (409 × 734). Se siguió Product Design Audit con capturas
guardadas e inspeccionadas; no se generaron propuestas pagadas, no se contactó
con tiendas ni se modificó un proyecto público.

## 1. Comparativa anterior — fallo confirmado

La opción Completa mostraba $675.68 ante un presupuesto máximo de $500.50, pero
decía «Plan dentro de tu presupuesto». La barra fija al 100% no describía esa
diferencia. El texto del botón seleccionado era casi ilegible.
Una lectura basada en el formulario podía confundirse con un análisis de foto.

![Antes, captura inspeccionada](/tmp/roxy-pet-safety-172.PUzAxl/09-renueva-budget-before-175.png)

## 2. Comparativa corregida — comprobada en navegador local

Ahora muestra límite, objetivo y exceso exacto ($175.18), precios pendientes,
impuestos y envío; un indicador semántico representa el 135% del límite. La
selección tiene contraste blanco/verde, nombres legibles y estado aria-pressed.
Las ideas sin análisis visual se identifican por su origen en las respuestas.
El guardado no anuncia un análisis que no se va a ejecutar. La comparación
temporal sobrevive a refresh de datos, sin cambiar el límite ni datos guardados.

![Después, captura inspeccionada](/tmp/roxy-pet-safety-172.PUzAxl/12-renueva-budget-final-175.png)

La identidad crema/verde/dorado y estructura existente se conservan. No hay
desbordamiento horizontal; texto de advertencia a 12 px. No se afirma conformidad
WCAG integral ni pruebas de lector de pantalla. Las estimaciones no son ofertas
reales ni prueba de que se pueda completar una habitación a ese importe.

## Persistencia y límites del recorrido

Alta manual local de una sala con foto de prueba, presupuesto decimal, objetos
a conservar y prioridades; proyecto e imagen conservados al recargar.
Análisis y generación desactivados sin la clave de Home, aviso explícito.
El recorrido real de generación con proveedores no se verifica con este entorno
sin credenciales. No se añadieron afiliaciones, cuentas ni permisos.

## Inventario actualizado, sin datos de cuentas

`audit_catalog()`: 668 filas, 517 humanas, 57 preparaciones de mascotas y 94
guías de cuidado. Las 57 filas de preparaciones tienen activo individual marcado
como revisado; no implica 57 recetas distintas por mascota, ni aval clínico.
El catálogo personalizado elimina duplicados por preparación. Persisten 463
borradores humanos sujetos a revisión y sus restricciones de cocina/Compra.

HTML/APP 175, JS 176, CSS 125, SW 173. Registro público permanece apagado.

## Comprobación pública y cierre

`/lista`, `/assets/roxy_list.js`, `/assets/roxy_list.css` y `/lista-sw.js` devuelven
HTTP 200 y son idénticos byte a byte a los archivos del commit `09298929e`.
`/health`: `ok`; registro: `enabled:false`, `trial_days:5`.
Una recarga normal de la pestaña pública muestra meta 175, Bella y Luna, y las
miniaturas de ambas cargadas. No se modificaron sus perfiles ni compras.

El proyecto de las capturas es sintético y local; no demuestra una compra real,
análisis con IA ni afiliación activa. Servidor QA detenido, pestaña de prueba
cerrada y viewport restaurado; datos de prueba y capturas conservados localmente.
La guía de auditoría visual se utilizó para detectar la contradicción del
presupuesto, corregir contraste/legibilidad y comparar el resultado.

La demo abierta no está habilitada: faltan configuración y pruebas reales de
Turnstile/alta, recuperación/soporte, resolver avisos de facturación de Render y
ElevenLabs y completar la curación editorial humana pendiente. No se cambió
facturación ni se aceptaron acuerdos de proveedores.
