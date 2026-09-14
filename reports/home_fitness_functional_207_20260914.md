# Home207 — agenda privada, calendario y progreso

Estado: base funcional verificada localmente. Sin publicación; público203 intacto.
Roberto pausó avatar/Runway y priorizó Ejercicio. Después precisó que quiere
entrenador personal casa/gimnasio, según equipo, nivel, días y minutos, con
peso/estatura, resultados y posible Apple Watch. Esa ampliación NO está terminada.

## Cambios comprobados

- Plan elegido por miembro, consentimiento propio y persistencia PostgreSQL exclusiva.
- Añadir fechas/horas, reprogramar pendientes, registrar realizada/omitida y volver
  explícitamente a pendiente. Historial protegido contra sobrescritura por PUT.
- GET/PUT/PATCH, exportación y eliminación privada; RLS forzado, rol no propietario,
  TLS, control de versión e idempotencia. Borrado global deja versión incluso sin
  plan previo para rechazar consentimientos iniciales obsoletos.
- Hoy/Mi plan/Progreso conectados. Ajustes exporta/elimina también un plan sin
  preferencias. Errores de conexión recuperables en español.
- Calendario recibe un borrador genérico con instante confirmado por servidor;
  exige elegir duración y confirmar. La revisión muestra inicio, fin y duración;
  recordatorio0 se lee Sin aviso. Reprogramar el plan no modifica automáticamente
  una copia anterior en el calendario compartido; la interfaz lo explica.

## Evidencia

- 452 pruebas Python aprobadas, incluidas todas las integraciones PostgreSQL reales
  de la selección; sin omisiones. 39 de paquete/demo repetidas tras versiones finales.
- 150 pruebas Node aprobadas: Ejercicio, plan, puente de calendario, guías y habitaciones.
- CUA8771: plan de dos actividades guardado; primera realizada solo tras confirmación;
  segunda reprogramada al16/09/2026,18:30 conservando historial. Guía fuerza pasos1→2.
- Copia genérica al calendario, duración elegida30min, revisión y confirmación;
  exactamente un evento16/09,18:30 visible después de recargar.
- Recarga recupera una realizada y una pendiente. Progreso393×852 sin overflow
  (scrollWidth/clientWidth393). Captura: home-fitness-207/progreso-movil.png.
- JS sintácticamente válido y git diff --check sin errores. Sin eliminar originales
  ni prototipos, sin escrituras en el hogar público ni proveedores pagados.

## Estado operativo y límites

Preview http://127.0.0.1:8771/lista#ejercicio, PID4355/sesión54082.
Estado sintético persistido: /tmp/roxy-home-fitness-207-65_2kmfh.
PostgreSQL17.11/venv privados descritos en home_fitness_local_postgres_207_20260914.md.
No claves reales de voz/IA en8771.8770 permanece preservado; apareció sin sesión
al inspeccionarlo después, no se reinició ni se alteraron sus datos.

Catálogo: fuerza7, equilibrio5, flexibilidad4 =16 movimientos de guías generales.
No es una rutina individual adaptativa ni un programa completo de gimnasio.
No calcula calorías ni mide resultados corporales. Producción necesita configurar
PostgreSQL Home y aplicar ambas migraciones antes de habilitar guardado.

Siguiente: implementar requisitos personalizados208 con catálogo y demostraciones
revisados, métricas privadas y criterios de progresión; integrar diseño tras revisión.
Propuesta visual aparte y Apple Watch: home_fitness_design_208_20260914.md y
home_fitness_watch_208_20260914.md. Avatar sigue pausado; no confundir imágenes
con película o demostración técnica certificada.
