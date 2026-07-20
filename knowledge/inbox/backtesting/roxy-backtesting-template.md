# Roxy Backtesting Template

category: backtesting

Objetivo: cada estrategia debe probarse antes de usarse como senal operativa. Roxy debe guardar resultados con metricas suficientes para evitar conclusiones falsas.

## Campos obligatorios

Estrategia, activo, timeframe, periodo historico, fuente de datos, reglas exactas, costo de operacion, slippage, numero de operaciones, win rate, profit factor, expectancy, max drawdown, promedio ganador, promedio perdedor y condiciones de mercado.

## Evaluacion

Una estrategia no es valida solo porque tuvo ganancias en pocas operaciones. Roxy debe exigir muestra suficiente, estabilidad por regimen de mercado y comparacion contra un baseline. Si una estrategia solo funciona en tendencia fuerte, debe etiquetarse asi.

## Riesgo de sobreajuste

Demasiados filtros pueden crear una estrategia que explica el pasado pero falla en vivo. Roxy debe preferir reglas simples, robustas y faciles de ejecutar. Todo backtest debe incluir limitaciones.
