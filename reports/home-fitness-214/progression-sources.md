# Seguimiento descriptivo de entrenamientos · 214

Verificado el 14 de septiembre de 2026. Este bloque calcula un resumen de registros manuales ya validados. No prescribe cargas, no cambia series automáticamente y no interpreta diferencias como una mejora de fuerza o salud.

## Fuentes primarias consultadas

- [ACSM, actualización de recomendaciones de fuerza de 2026](https://acsm.org/resistance-training-guidelines-update-2026/), publicada el 17 de marzo de 2026. El comunicado describe recomendaciones para adultos sanos y da prioridad a la participación constante y a adaptar el programa a objetivos, preferencias y seguridad. La fuente no valida una regla universal para aumentar kilos a partir de dos registros. En este bloque no se implementa ninguna.
- [NIDDK, Health Tips for Adults](https://www.niddk.nih.gov/health-information/weight-management/healthy-eating-physical-activity-for-life/health-tips-for-adults), revisión indicada en la página: septiembre de 2020. Su apartado de actividad física propone llevar un diario y aumentar la actividad gradualmente; también indica dejar al menos un día de recuperación antes de volver a trabajar los mismos grupos musculares. Esta página no proporciona un algoritmo personalizado de progresión de cargas. Los controles existentes de agenda y recuperación pertenecen a la selección de rutinas, no a este resumen.

## Decisiones de implementación

`roxy_os/fitness/training_progress.py` recibe exclusivamente una instantánea validada de `TrainingLogsRepository`. No lee el perfil, peso, edad, permisos de dispositivos ni otra memoria de Roxy. No escribe en la agenda ni en el registro y no llama a proveedores externos.

- Muestra sesiones registradas, días con registro, ejercicios realizados/omitidos, series y duración informada. Una duración ausente conserva `null`; el total solo suma minutos declarados y expone cuántas sesiones no los informaron.
- Cada historial corresponde al mismo identificador de ejercicio, versión del contenido y unidad de registro. Un movimiento compartido entre dos rutinas puede aparecer en un solo historial, con el nombre de cada rutina en cada entrada.
- Compara con la fecha realizada anterior distinta, usando las fechas locales guardadas. No usa la hora de escritura como si fuese la hora de ejercicio. Si hay varias entradas del mismo movimiento en cualquiera de los dos días, no inventa su orden ni calcula una comparación.
- Conserva los ejercicios omitidos. Si una de las dos entradas fue omitida, no convierte la omisión en cero repeticiones ni busca una entrada más antigua para mejorar el resultado mostrado.
- Mantiene todas las series y cargas en sus unidades originales. Las diferencias de carga utilizan `load_kg` validado y comparan por posición de serie; una carga ausente o una serie sin pareja produce `null`. Un cero expresamente registrado sigue siendo cero.
- Las repeticiones y segundos suman lo escrito. Los movimientos por lado se identifican como tales; el resumen no duplica automáticamente sus cantidades.
- Los cambios se etiquetan `descriptive_only`. No se calculan calorías, récords, percentiles, fuerza estimada, 1RM ni dosis recomendadas.
- El contenido histórico retirado sigue visible con sus datos originales. `can_repeat` solo habilita la ruta de revisión de una rutina cuyo contenido actual y ejercicios de trabajo coinciden; no equivale a programarla ni a declarar elegibilidad personal.
- La proyección devuelve copias independientes y no modifica las entradas, el catálogo ni el historial al formar `latest`/`previous`.

## Evidencia automatizada

Comando ejecutado:

```text
/tmp/roxy-home-pg-207-12g4auxo/venv/bin/python -m pytest -q tests/test_roxy_home_fitness_training_progress.py
```

Resultado: **23 pruebas aprobadas**. Casos: vacío y ausencia de duración; sumas parciales; cambio kg/lb conservando originales; cero explícito; series adicionales; fracciones de segundos; movimiento compartido entre rutinas; duplicados en el día actual o anterior; registros editados o añadidos después; omisiones; versiones retiradas; unidades históricas ambiguas; restricciones de repetición; copias independientes; y uso del catálogo real de seis rutinas.

Las pruebas de este archivo validan el cálculo y su contrato. La comprobación de la API, aislamiento por miembro y presentación visual se documenta en el informe de integración del bloque 214.
