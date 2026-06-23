# Roxy Development Cadence

Fecha: 2026-06-12

Este archivo define la meta operativa de desarrollo de Roxy Trading. Su objetivo es que cualquier pestana de Codex o sesion futura trabaje sobre la misma direccion: construir una aplicacion comercial, rentable como producto, clara para operar y segura antes de ejecucion real.

## Meta Principal

Roxy debe evolucionar de scanner tecnico a plataforma comercial de decision de trading:

- Detectar oportunidades en acciones, opciones y criptomonedas.
- Explicar `Operar`, `Mirar Call`, `Esperar` o `No operar` con razones simples.
- Usar estrategias aprendidas, sin reemplazar reglas buenas existentes.
- Aprender de resultados reales/paper: 2%, 5%, 10% o stop.
- Mejorar graficas, educacion, laboratorio, alertas y gestion de riesgo.
- Mantener ejecucion real bloqueada hasta que paper trading, credenciales, controles y aprobacion esten listos.

## Cadencia Cada 20 Minutos: Graficas Y Experiencia Visual

Cada bloque de 20 minutos debe revisar y mejorar la experiencia grafica. Prioridad:

1. Confirmar que la grafica principal carga sin errores.
2. Mejorar velas, SMA/EMA, volumen, bandas, zonas, soportes/resistencias, entrada, stop y targets.
3. Hacer que un simbolo como `AAPL` pueda abrirse con una vista util de velas recientes, incluyendo al menos una semana cuando el timeframe lo permita.
4. Agregar informacion visual solo si ayuda a decidir: no saturar.
5. Revisar si la grafica explica el setup: canal alcista, lateral, pullback, rebote, cruce, ruptura, salto, cambio de canal.
6. Hacer la vista facil para telefono/tablet: botones claros, texto legible, no sobrecargar.
7. Validar que la grafica ayude a responder:
   - Donde entro?
   - Donde esta el stop?
   - Donde tomo 2%, 5%, 10%?
   - Que condicion falta?
   - Por que Roxy espera o evita?

Resultado esperado de cada ciclo de 20 minutos:

- Una mejora pequena pero real en graficas, layout, claridad o datos visuales.
- Si no hay mejora de codigo, dejar nota de auditoria con el proximo ajuste visual.

## Cadencia Cada 20 Minutos: Desarrollo Comercial Y Sincronizacion

Cada 20 minutos se debe revisar que cambiaron otras pestanas/sesiones y avanzar el producto completo. Prioridad:

1. Revisar `git status`, `MASTER_CONTEXT.md`, `ROXY_DEVELOPMENT_CADENCE.md` y archivos de sincronizacion como `training_videos/ROXY_LEARNING_SYNC.md`.
2. Identificar trabajo nuevo hecho por otras pestanas.
3. No sobrescribir cambios: enriquecer, conectar y ordenar.
4. Elegir el punto de mayor valor comercial:
   - alertas inteligentes sin ruido
   - memoria real de resultados
   - opciones profesionales
   - Alpaca paper practice
   - Roxy Lab
   - modo Estudios
   - contexto macro de newsletters semanales y noticias economicas
   - seguridad de plataformas
   - UI movil/tablet
   - graficas profesionales
5. Implementar una mejora concreta y verificable.
6. Ejecutar pruebas enfocadas.
7. Actualizar contexto si cambia una regla importante.

Resultado esperado de cada ciclo de 20 minutos:

- Roxy debe quedar mas cerca de un producto vendible.
- La app debe seguir corriendo.
- Las decisiones deben ser mas claras, no mas confusas.
- La ejecucion real debe seguir bloqueada hasta que sea seguro.

## Runner Local De Cadencia

Para que el proyecto no dependa de repetir instrucciones manualmente, existe un runner local:

- Script: `tools/roxy_development_cadence.py`
- LaunchAgent preparado: `deployment/com.roxy.development-cadence.plist` pero deshabilitado por defecto.
- Intervalo si se activa manualmente: auditoria diaria. No usar este runner como fuente de mercado live.
- Reporte actual: `logs/development_cadence/latest_report.md`
- Cola de siguientes tareas: `logs/development_cadence/NEXT_TASKS.md`
- Estado JSON: `logs/development_cadence/status.json`
- Historial JSONL: `logs/development_cadence/events.jsonl`

Este runner es `audit_only`: no edita codigo, no opera, no manda ordenes y no cambia reglas por su cuenta. Su funcion es dejar contexto para Roxy/Codex, no alimentar trades ni precios live.

Para trading, Roxy debe usar el dashboard live y proveedores de mercado con refresco en segundos. Una cadencia de reportes de 20 minutos no es aceptable para entradas, stops o alertas.

Limitacion importante: Codex no puede despertarse solo desde el chat si no hay una automatizacion activa de la app. Este runner mantiene la auditoria local en la Mac; una sesion de Codex debe leer los reportes para programar las mejoras.

## Regla De Trabajo Entre Pestanas

Cuando otra pestana de Codex trabaje en el mismo proyecto:

- Leer primero los archivos de contexto.
- Revisar cambios antes de editar.
- No revertir trabajo ajeno.
- Si hay conflicto, preservar el sistema mas seguro.
- Integrar el conocimiento nuevo como capa adicional, no como reemplazo ciego.
- Cualquier regla nueva debe pasar por backtest, paper o memoria antes de afectar alertas reales.

## Principio De Producto Comercial

Roxy debe ser unica por combinar:

- Estrategias humanas aprendidas de clases.
- Reglas medibles con medias moviles.
- Contexto macro/sectorial tomado de noticias, newsletters y calendario economico.
- Graficas profesionales.
- Riesgo claro.
- Opciones con datos serios.
- Memoria de resultados.
- Laboratorio de estrategias.
- Educacion integrada.
- Alertas 24h con poco ruido.
- Ruta segura hacia plataformas.

La promesa comercial no debe ser "ganancias garantizadas". La promesa correcta:

> Roxy ayuda a encontrar oportunidades con reglas claras, riesgo definido, explicacion simple y aprendizaje continuo.

## Checklist Permanente

- [ ] La grafica principal se entiende en menos de 10 segundos.
- [ ] El Trade Plan dice claramente `Operar`, `Mirar Call`, `Esperar` o `No operar`.
- [ ] Cada decision tiene entrada, stop, objetivos y razon.
- [ ] La alerta solo sale si 1h confirma, 15m da entrada, volumen acompana, riesgo es bajo y target 2% es viable.
- [ ] Cada senal se guarda para aprender si llego a 2%, 5%, 10% o stop.
- [ ] Las opciones no se sugieren sin DTE, delta, spread, volumen, OI, break-even y max loss.
- [ ] El laboratorio puede recomendar promover, vigilar, ajustar o pausar una estrategia.
- [ ] El modo estudio ensena las estrategias con ejemplos reales.
- [ ] La app se puede usar desde computadora, tablet y telefono.
- [ ] Ninguna orden real se envia sin controles, credenciales y aprobacion explicita.
