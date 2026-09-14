# Ejercicio 214 — comparación y objetivos personales

Verificado localmente el 14 de septiembre de 2026. Incluido en el paquete 215 en preparación de publicación.

Mi evolución proyecta registros reales por ejercicio y versión. Compara fechas distintas; no ordena dos entradas del mismo día como entrenamientos consecutivos, ni trata omitidos como cero. Conserva cargas originales, ausencias de duración, versiones históricas y totales de ambos lados. No prescribe aumentos, calorías ni objetivos por peso/edad.

Repetir rutina permite consultar el registro, elegir copiarlo y editar objetivos por ejercicio/serie. Vuelve a confirmar material/capacidades, genera fechas desde disponibilidad y exige revisión del plan antes de guardar. El plan conserva objetivos opcionales separados de resultados. Los campos reales comienzan vacíos. Las sesiones con registros no permiten alterar retroactivamente sus objetivos. Fuentes y límites: progression-sources.md.

La API privada conserva identidad, CSRF, versiones e idempotencia. Mi evolución no escribe datos ni contacta IA. Ocultar/cambiar cuenta limpia los datos en memoria. El historial sigue consultable sin perfil; las nuevas sesiones exigen perfil adulto y permisos.

## Prueba funcional real de navegador

Perfil sintético de QA en8771 con PostgreSQL TLS/RLS existente. De8actividades y1registro iniciales se pasó a11actividades y2registros, sin cambiar los originales. Repetir el registro del14sept: copia inicialmente desmarcada; Montaña20s se eligió como objetivo15s, Gato/vaca5reps y hombros5reps; Árbol permaneció sin objetivo. Confirmación explícita de requisitos. Propuesta29sept/1oct/3oct; primera fecha editada manualmente al10sept18:00 para probar una entrada histórica sintética; otras2fechas conservadas.

Sesión nueva muestra objetivo15s y campo real vacío. Se introdujeron15s, Árbol omitido,4reps y4reps, duración11min y fecha declarada13sept. El historial muestra13vs14sept, +5s/+1repetición descriptivos, sin mejora automática. Guardar no marca actividad completada:2realizadas/9pendientes. Dos mediciones previas siguen presentes. Recarga recupera objetivos/11actividades/2registros. No se simuló ejercicio real de una persona.

Ver registro abre ahora directamente el resumen guardado y Volver a la sesión recupera la guía. Aviso anterior de plan guardado eliminado de la escena. Prueba393×852 y858×779, consola sin errores, sin overflow horizontal. Se conservó arte/lector213.

## Verificación

1093 casos Python verificados y363Node pasan; detalle de pases/solapamientos en test-review.md. Incluye48casos de PostgreSQL aislado real. Además QA de integración con fuentes reales y motor de progreso. No sumar pases solapados.

Escena final: session-mobile-final.jpg. Resumen directo: record-mobile.jpg. Capturas previas de progreso: progress-desktop.jpg y progress-mobile.jpg. Algunas capturas intermedias muestran el aviso previo corregido; no son la versión final.

## Límites

8770/PID63912 con voz fija intacto;8771/PID92240/sesión15682 sin proveedorTTS. Esta prueba no certifica voz pública ni AppleWatch ni revisión clínica. Faltan mayor variedad y alternativas individuales, además del almacenamiento privado público. Avatar/Runway pausados; Mascotas sigue después del trabajo prioritario de Ejercicio.
