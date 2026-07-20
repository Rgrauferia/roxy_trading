# Roxy Self Improvement Loop

Este modulo le da a Roxy autonomia para mejorar codigo, graficas, estrategias, indicadores, tests y scripts dentro del proyecto sin pedir permiso en cada cambio interno.

## Autonomia permitida sin pedir permiso

- Calidad de codigo.
- Arreglos de tests.
- Graficas operativas.
- Matematica de indicadores.
- Investigacion de estrategias.
- Backtesting.
- Paper trading.
- Rendimiento UI.
- Scripts internos.

## Bloqueos que siguen siendo obligatorios

- Dinero real.
- `git push`.
- Deploy de produccion.
- Leer `.env`.
- Mostrar secretos/API keys.
- `sudo`, `rm -rf`, comandos destructivos o rutas fuera del proyecto.
- Cambios de sistema fuera de `/Users/robertograu/roxy_trading`.

## Ejecutar ciclo

```bash
node roxy-self-improvement/improvement-loop.ts
```

Solo analizar sin correr checks:

```bash
node roxy-self-improvement/improvement-loop.ts --skip-checks
```

## Salidas

- Reporte mas reciente: `roxy-self-improvement/reports/latest-improvement-cycle.json`
- Propuestas: `roxy-self-improvement/proposals`
- Memoria de intentos: `roxy-self-improvement/memory/improvement-memory.jsonl`

## Integracion deseada

El cerebro de Roxy debe llamar `runSelfImprovementCycle()` cuando detecte:

- Codigo repetido.
- Error en graficas.
- Estrategia debil.
- Indicador mal calculado.
- UI lenta.
- Test fallando.

Despues debe elegir una propuesta `auto_allowed`, modificar el proyecto con `Roxy Terminal Agent`, correr checks y guardar el resultado.
