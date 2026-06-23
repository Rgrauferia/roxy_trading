# Estrategia de medias moviles 20/40/100/200

Este enfoque analiza acciones o criptomonedas usando solo medias moviles simples:

- SMA20: momentum corto.
- SMA40: tendencia operativa.
- SMA100: filtro de tendencia intermedia.
- SMA200: filtro principal de mercado.

La estrategia favorece compras cuando el precio esta por encima de SMA200 y las medias estan ordenadas:

```text
SMA20 > SMA40 > SMA100 > SMA200
```

## Senales

- `BUY`: tendencia alcista clara, continuacion o pullback sano, con score alto.
- `WATCH`: estructura aceptable, pero aun no suficientemente fuerte.
- `AVOID`: tendencia debil, bajista, extendida o sin confirmacion.
- `INSUFFICIENT_DATA`: faltan al menos 200 velas.
- `NO_DATA` / `ERROR`: no se pudo obtener data del simbolo.

## Setups

- `TREND_CONTINUATION`: precio por encima de todas las medias y medias alineadas al alza.
- `PULLBACK`: tendencia alcista, con precio cerca de SMA20 o SMA40.
- `EARLY_UPTREND`: estructura temprana con SMA20/SMA40/SMA100 mejorando sobre SMA200.
- `DOWNTREND`: precio bajo SMA200 o medias ordenadas a la baja.
- `NEUTRAL`: sin ventaja clara.

## Uso

Escanear una accion puntual:

```bash
.venv/bin/python tools/ma_scan.py --market stocks --symbols AAPL --stock-interval 1d --stock-period 2y
```

Escanear varias acciones:

```bash
.venv/bin/python tools/ma_scan.py --market stocks --symbols AAPL,MSFT,NVDA,TSLA --limit 20
```

Escanear acciones en 15 minutos y 1 hora, incluyendo premarket/postmarket cuando Yahoo Finance lo entrega:

```bash
.venv/bin/python tools/ma_scan.py --market stocks --symbols AAPL,MSFT,NVDA --stock-intervals 15m,1h --include-extended-hours --limit 30 --save
```

Escanear criptomonedas:

```bash
.venv/bin/python tools/ma_scan.py --market crypto --symbols BTC/USD,ETH/USD,SOL/USD --crypto-timeframe 1d
```

Escanear criptomonedas en 15 minutos y 1 hora:

```bash
.venv/bin/python tools/ma_scan.py --market crypto --symbols BTC/USD,ETH/USD,SOL/USD --crypto-timeframes 15m,1h --limit 30 --save
```

Usar las watchlists del proyecto:

```bash
.venv/bin/python tools/ma_scan.py --market both --limit 30 --save
```

El flag `--save` guarda un CSV en `output/ma_strategy_<market>_<timestamp>.csv`.

Scanner diario con filtro historico:

```bash
.venv/bin/python tools/ma_scan.py --market both --require-backtest-eligible --limit 30 --save
```

Con `--require-backtest-eligible`, una senal tecnica `BUY` solo se mantiene como `BUY` si el simbolo tambien paso el ultimo backtest guardado. Si no paso, el scanner conserva `raw_signal=BUY`, pero baja `signal` a `WATCH` y agrega la razon del filtro.

Generar reporte legible del ultimo scan:

```bash
.venv/bin/python tools/ma_report.py
```

Esto escribe:

- `alerts/ma_daily_report.txt`
- `alerts/ma_daily_summary.json`

Flujo diario en un solo comando:

```bash
.venv/bin/python tools/ma_daily.py
```

Para refrescar backtests antes del scan diario:

```bash
.venv/bin/python tools/ma_daily.py --refresh-backtests
```

## Automatizacion diaria en macOS

Instalar el LaunchAgent diario:

```bash
.venv/bin/python tools/ma_daily_launchd.py install
```

Por defecto queda programado todos los dias a las 18:05 hora local y ejecuta:

```bash
.venv/bin/python tools/ma_daily.py --market both --limit 30 --report-limit 12
```

Ver estado:

```bash
.venv/bin/python tools/ma_daily_launchd.py status
```

Ejecutar el flujo inmediatamente, sin esperar la hora programada:

```bash
.venv/bin/python tools/ma_daily_launchd.py run-now
```

Cambiar la hora:

```bash
.venv/bin/python tools/ma_daily_launchd.py install --hour 19 --minute 30
```

Desinstalar:

```bash
.venv/bin/python tools/ma_daily_launchd.py uninstall
```

Logs:

- `logs/ma_daily.out`
- `logs/ma_daily.err`

## Analisis live intradia

El modo live no es streaming tick-a-tick. Es un proceso continuo que reescanea cada 5 minutos por defecto usando velas de 15 minutos y 1 hora:

```bash
.venv/bin/python tools/ma_live.py
```

Ejecutar un solo ciclo live:

```bash
.venv/bin/python tools/ma_live.py --once
```

Instalar el servicio live en macOS:

```bash
.venv/bin/python tools/ma_live_launchd.py install
```

Ver estado:

```bash
.venv/bin/python tools/ma_live_launchd.py status
```

Desinstalar:

```bash
.venv/bin/python tools/ma_live_launchd.py uninstall
```

El servicio live:

- analiza acciones con `15m` y `1h`;
- analiza crypto con `15m` y `1h`;
- incluye premarket/postmarket para acciones intradia con `prepost=True`;
- actualiza `alerts/ma_live_report.txt`;
- actualiza `alerts/ma_live_summary.json`;
- guarda CSVs en `output/ma_live_strategy_<market>_<timestamp>.csv`;
- escribe logs en `logs/ma_live.out` y `logs/ma_live.err`.

## Estrategia especializada: confluencia 1h + 15m

La especializacion actual no compra solo porque un timeframe diga `BUY`. Primero combina dos capas:

- `1h`: filtro de tendencia.
- `15m`: gatillo de entrada.

Generar confluencia sobre el ultimo scan live:

```bash
.venv/bin/python tools/ma_confluence.py --save
```

Esto escribe:

- `output/ma_confluence_<timestamp>.csv`
- `alerts/ma_confluence_report.txt`
- `alerts/ma_confluence_summary.json`

Reglas para `Confluence BUY`:

- 1h no puede estar en `DOWNTREND`;
- 1h debe confirmar un setup alcista real: `TREND_CONTINUATION`, `PULLBACK` o `EARLY_UPTREND`;
- 1h debe estar sobre SMA200;
- 15m debe dar gatillo tecnico con `raw_signal=BUY`;
- 15m debe estar sobre SMA200 y con SMA20 > SMA40;
- el precio de 15m no debe estar demasiado extendido sobre SMA20;
- el simbolo debe pasar el filtro historico de backtest.

Interpretacion:

- `BUY`: tendencia 1h confirmada + gatillo 15m + backtest elegible.
- `WATCH`: la tendencia 1h ayuda, pero falta gatillo limpio o filtro historico.
- `AVOID`: no hay estructura suficiente o hay tendencia bajista.

La confluencia tambien calcula plan operativo:

- `entry`: cierre actual del 15m;
- `stop`: stop tecnico del 15m;
- `risk_pct`: riesgo porcentual hasta stop;
- `target_1r` y `target_2r`: objetivos por relacion riesgo/recompensa.
- `target_2pct_*`: viabilidad de tomar 2%;
- `target_5pct_*`: viabilidad de tomar 5%;
- `target_10pct_*`: viabilidad de tomar 10%;
- `trade_decision`: si se opera, se espera o se descarta por riesgo/beneficio.

Regla de gestion de riesgo:

- cada objetivo se evalua por separado contra el stop actual;
- 2% exige al menos 1R;
- 5% exige al menos 1.5R y mejor calidad de tendencia;
- 10% exige al menos 2R, confluencia fuerte, tendencia 1h mas solida y volumen suficiente;
- si ningun objetivo 2/5/10 compensa el riesgo del stop, la senal se baja a `WATCH`;
- si el precio toca el stop, se sale sin esperar a que la perdida crezca;
- para opciones, esta capa analiza primero el subyacente. La seleccion del contrato debe validar liquidez, spread, delta, vencimiento y riesgo de perdida de prima.

## Selector de opciones

El flujo de opciones parte del subyacente. Primero exige una confluencia operable en la accion; despues busca contratos call con filtros de riesgo:

```bash
.venv/bin/python tools/options_scan.py --save
```

Esto escribe:

- `output/options_candidates_<timestamp>.csv`
- `alerts/options_report.txt`
- `alerts/options_summary.json`

Filtros actuales:

- solo acciones con `Confluence BUY` y `trade_decision=TRADE_FOR_*`;
- calls con vencimiento entre 7 y 45 dias;
- spread maximo configurable, default 18%;
- volumen minimo configurable, default 50;
- open interest minimo configurable, default 100;
- strike cercano al precio actual y compatible con el objetivo del subyacente;
- calcula perdida maxima por contrato como `ask * 100`.

Limitacion importante:

- esta version usa liquidez, spread, vencimiento, strike y prima. No usa todavia delta/gamma/theta reales porque Yahoo Finance no siempre entrega Greeks completos. La siguiente mejora de opciones debe agregar una fuente de cadena de opciones con Greeks para filtrar por delta y theta.

## Backtesting

Antes de usar una senal, prueba el comportamiento historico:

```bash
.venv/bin/python tools/ma_backtest.py --market stocks --symbols AAPL,MSFT,NVDA,TSLA --stock-period 5y
```

Filtro estricto recomendado para encontrar candidatos:

```bash
.venv/bin/python tools/ma_backtest.py --market stocks --stock-period 5y --min-buy-hold-edge-pct 0 --only-eligible --save
```

Para criptomonedas:

```bash
.venv/bin/python tools/ma_backtest.py --market crypto --crypto-timeframe 1d --min-buy-hold-edge-pct 0 --only-eligible --save
```

El backtest:

- calcula la senal al cierre de una vela;
- entra en la apertura de la vela siguiente;
- descuenta fee y slippage;
- sale por stop, perdida de SMA40/SMA100 o fin de datos;
- compara el retorno contra buy-and-hold del activo y contra un benchmark ajustado al mismo tamano de posicion.

## Criterios minimos antes de operar

No uses una senal `BUY` de forma aislada. Para que un simbolo sea candidato real, el backtest deberia mostrar:

- `profit_factor` mayor que 1.2;
- `total_return_pct` positivo;
- `max_drawdown_pct` tolerable para el tamano de posicion;
- suficientes trades para que la muestra tenga sentido;
- rendimiento razonable frente a `buy_hold_account_return_pct`.

Si una accion o crypto tiene `BUY` hoy pero su backtest historico es pobre, debe quedar como `WATCH` operativo, no como compra automatica.

## Parametros utiles

- `--buy-score`: score minimo para `BUY` (default: 70).
- `--watch-score`: score minimo para `WATCH` (default: 45).
- `--max-extension-pct`: penaliza si el precio esta demasiado extendido sobre SMA20 (default: 12).
- `--pullback-band-pct`: define cercania a SMA20/SMA40 para pullbacks (default: 3).
- `--position-size-pct`: fraccion del capital por operacion en backtest (default: 0.25).
- `--cooldown-bars`: velas de espera despues de cerrar una operacion (default: 5).
- `--min-buy-hold-edge-pct`: exige ventaja minima contra buy-and-hold ajustado al mismo tamano de posicion.
