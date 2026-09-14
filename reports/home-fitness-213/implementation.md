# Roxy Home 213 — rutinas y registros por ejercicio

## Entrega local verificada

Seis rutinas editoriales en español, con 28 movimientos de trabajo sumados entre ellas (hay movimientos compartidos), preparación y vuelta a la calma: fuerza con silla y pared, mancuernas en casa, mancuernas con banco plano para nivel intermedio, movilidad, yoga suave y control del centro. Las tres guías NHS, las fichas wger, los recursos externos y todos los originales anteriores permanecen disponibles. Auditoría factual y fuentes: content-audit.md.

Rutinas muestra los pasos y permite confirmar material y movimientos antes de buscar una semana. El servidor utiliza perfil adulto, experiencia, lugar, minutos, ventanas, traslado, zona horaria y recuperación entre sesiones de fuerza; conserva los días ya ocupados. Los tiempos son estimaciones editoriales con descansos, no duraciones exactas ni certificación clínica. Las confirmaciones se guardan por sesión; los kilos registrados no prescriben cargas. El borrador se revisa en Mi plan y se añade sin sustituir el historial. Las nuevas sesiones verifican la versión del perfil y los requisitos dentro de la transacción de guardado.

La sesión ocupa el estudio completo, con instrucciones grandes, pasos, navegación por movimiento y descanso manual. Los campos reales comienzan vacíos: series, repeticiones o segundos, cargas opcionales y duración declarada. Registro privado con consentimiento separado; corrección, exportación y borrado individual o total. Guardar un registro no completa la actividad: hay otra confirmación. Una actividad omitida debe volver a pendiente para registrar; conserva acceso de lectura/exportación/borrado de registros existentes. Las cargas solo se admiten en movimientos aptos, y se aclaran peso por mancuerna y totales de ambos lados.

## Privacidad y persistencia

Migración aditiva004_training_logs.sql; PostgreSQL real con TLS verificado, runtime sin propiedad/bypass y FORCE RLS. Sin secretos de otros productos, IA, telemetría de salud, almacenamiento local del navegador o datos de entrenamiento en el calendario del hogar. Orden de bloqueo foundation → agenda → registros; control de versión/idempotencia, aislamiento de miembros y protección del historial frente a reprogramaciones. Exportar/borrar el plan y borrado global de Ejercicio incluyen los registros. Cambiar identidad u ocultar la página limpia contenido privado. Privacidad publicada en assets/roxy_privacy.html actualizada.

## Pruebas y evidencia

- Cobertura Python del pase amplio: 984 casos. El primer pase dejó983 aprobados y1 expectativa antigua del paquete; corregida para213 y repetidos los39 casos de paquete/demo, todos aprobados. No sumar esos39 al total984. Logs python-final.log (con el fallo histórico de versión) y package-final.log (pase final corregido).
-304 pruebas Node aprobadas, incluyendo entrenamiento, integración padre/planificador y módulos previos; node-final.log.
- CUA real: adulto sintético con30min y martes/jueves/sábado18–19h. Yoga propone22/24/26sep18h. Se editó expresamente la tercera fecha a12sep para probar un registro retrospectivo local. Guardado conserva las5actividades previas y añade3: total8.
- Registro sintético realizado14sep: Montaña20s, Árbol omitido, Gato-vaca5repeticiones, hombros5repeticiones,12min declarados. Tras guardar, actividad seguía pendiente; después de confirmación separada quedó realizada. Reinicio de8771 y recarga recuperaron8actividades (2realizadas/6pendientes),1registro con esos valores y las2mediciones anteriores. Ninguna colección doméstica ni evento compartido fue modificado.
- Escritorio858px y móvil393×852, sin overflow horizontal de página. Descanso manual avanza0:00→0:05 y se detiene al pausarlo. Consola final vacía. Viewport restablecido.
- QA comparó juntos211/mobile-reader-final.jpg y213/session-immersive-mobile.jpg. Se corrigieron el contraste de dosis/cue y el marco anidado para recuperar la escena de pantalla completa. Evidencia final: session-immersive-desktop.jpg y session-immersive-mobile.jpg; capturas anteriores conservadas, incluido record-recovered-desktop.jpg.

## Ejecución y límites

HTML/APP/SW213, list220,fitness15,planner10,trainingJS2/CSS3. Docker incluye assets nuevos. Preview8771/PID78464/sesión96303, mismo estado /tmp/roxy-home-fitness-207-65_2kmfh, migraciones001–004.8770/PID63912 sigue intacto con su voz fija en memoria;8771 no tiene proveedorTTS. Sin commit/push/deploy. La versión pública203 no recibió estos cambios.

Este incremento permite elegir rutinas y registrar entrenamiento; aún no completa el entrenador profesional solicitado. Falta progresión entre sesiones, comparación longitudinal por ejercicio, más variedad y adaptación individual por capacidad/edad/objetivo con alternativas revisadas. Apple Watch no está conectado. Las escenas usan imágenes estáticas aprobadas y movimiento ambiental; no son vídeos de técnica, una película nueva ni un avatar animado. Avatar/Runway siguen pausados.

Orden aprobado: terminar Ejercicio y después abordar Mascotas con experiencia inmersiva y revisión funcional de perfiles, cuidados, historial, recordatorios, calendario y persistencia. Mascotas sigue en cola, no iniciado.
