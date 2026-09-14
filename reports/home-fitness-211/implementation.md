# Roxy Home211 — estudio interactivo local

Roberto aprobó las tres direcciones210. Se integran como entrada fotográfica,
mapa de espacios y lector de indicaciones sobre una escena amplia. El entorno
permanece al acceder a los módulos reales: biblioteca, plan privado, progreso y
preferencias. No se sustituyó el catálogo ni se modificaron datos domésticos.

## Implementación

- Nuevos roxy_fitness_world.js/css y tres fondos211; navegación directa desde Home.
- Guía compartida Programs/Planner: instrucciones numeradas, avance manual,
  texto completo/fuente conservados y voz mediante el canal oficial existente.
- Corrección lector→Progreso, firma TTS, callbacks obsoletos, contraste/tamaño,
  contenedores globales, regreso accesible y anclas móviles separadas.
- HTML211 / APP211 / SW211; list218, living5, fitness12, discovery3, programs5,
  planner6, worldJS2/CSS6 y sessionCSS1. Docker incluye nuevos códigos e imágenes.
  Los fondos grandes se descargan al usarse, no bloquean la instalación del shell.

## Verificación

481Python aprobadas (incluye PostgreSQL real, catálogo, API, paquete y demo),
218Node aprobadas (incluye11regresiones nuevas), 18pruebas del paquete repetidas
tras assets finales. Salidas en esta carpeta. Estas cifras no se suman entre
suite completa y subconjuntos. CUA desktop1487×1058 y móvil393×852; regresos,
filtros, lectura, plan existente y progreso verificados. QA visual: passed;
ver `design-qa.md` en la raíz y comparaciones conservadas aquí.

## Estado y límites

Preview real: http://127.0.0.1:8771/lista#ejercicio (PID22637, sesión47027;
misma instancia PostgreSQL y cuenta sintética207). Una actividad realizada y una
pendiente permanecen intactas.8770/PID63912 no se reinició: conserva voz fija en
memoria.8771 no tiene proveedor TTS; UI comprobó indisponibilidad controlada sin
fallback masculino. Imágenes estáticas con transiciones ambientales e interacciones;
no vídeo de técnica ni avatar animado. Personalización profesional, mediciones y
AppleWatch pendientes. No commit, push, deploy, contratación ni borrado de originales.
Público203 y sus datos intactos; PostgreSQL público sigue sin configurarse.
Galería2108798 y prototipo20860122 conservados. ComparadorQA8799 sólo local.

Próximo paso: revisar esta integración con Roberto y abordar entrenamiento
personalizado con contenido y progresiones revisadas, métricas privadas y calidad
funcional; no presentar la agenda general como prescripción personalizada.
