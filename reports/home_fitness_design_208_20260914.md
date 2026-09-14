# Home208 — propuesta visual y requisitos ampliados

Petición de Roberto: entrenador personal profesional, visual vivo como película/juego,
casa o gimnasio según material, frecuencia y tiempo; ejercicios detallados, plan real,
seguimiento de resultados, peso y estatura; evaluar Apple Watch.

Propuesta interactiva entregada en conversación:
/Users/robertograu/.codex/visualizations/2026/09/14/01a09dd2-e577-7c91-9660-9d9674be240c/roxy-entrenador-personal.html
Vista local de revisión: http://127.0.0.1:60122/ (sesión93300).
Reutiliza la imagen actual de Roxy, sin editarla. No es película ni avatar nuevo.
Cuatro capítulos: perfil en tres pasos, semana, ficha detallada y resultados.
Casa/gimnasio cambia material; días/minutos cambian agenda de ejemplo. Muestra
peso/estatura y explicación de conexión del reloj sin guardar ni enviar datos.
Registro de ejemplo cambia progreso; minutos/calorías ausentes se mantienen sin dato.
No es lógica de prescripción ni calendario real. Ejemplo técnico limitado a la guía
NHS de sentarse/ponerse de pie, con enlace original; vídeo técnico pendiente.

QA: navegador real, gimnasio3días40min reflejado en semana; cambio de momento y
registro de ejemplo reflejado en resultados. Escritorio1280 y móvil393; contenido
interno361px/scroll361px, imagen cargada. Viewport reseteado; pestaña7 entregada,
pestañas5/6 preservadas. Fragmento531KB, sin llamadas de red ni almacenamiento.

## Criterios de implementación pendientes

1. Perfil privado: lugar por día, equipo real, nivel/objetivo, días, minutos, unidades,
   mediciones con fecha y antecedentes/restricciones pertinentes. Consentimiento y
   alternativas sin conectar dispositivos. No inferir salud de la imagen ni del peso.
2. Catálogo revisado casa/gimnasio por patrones de movimiento; ficha con técnica,
   series/repeticiones, descanso, errores, alternativas y fuente/derechos multimedia.
3. Motor de planificación basado en programas revisados, con recuperación, límites
   de tiempo y adaptación de material. No llamar plan profesional a tres guías
   genéricas ni resolver limitaciones individuales mediante texto improvisado.
4. Sesión interactiva: demostración revisada, voz oficial, pausa/repetición, registro
   de series/carga/esfuerzo, descansos y confirmación de lo efectivamente realizado.
5. Resultados privados: historial de peso/medidas, duración, cargas y cumplimiento;
   distinguir declarado/importado/estimado. Ninguna promesa automática de pérdida
   de peso o aumento de fuerza por calendario o consumo de calorías.
6. Apple: importador iOS HealthKit primero; evaluar watchOS y WorkoutKit después.
   Reporte separado con documentación oficial y permisos por tipo.

Público203 y datos existentes intactos. Código funcional sigue candidato207;
208 es propuesta de interfaz, no versión publicada ni funciones activadas.
