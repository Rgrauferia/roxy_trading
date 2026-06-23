# Deploy de Roxy Trading en Render

Objetivo: usar Roxy desde cualquier telefono, tablet o computadora con una URL publica fija, sin depender de que tu Mac este encendida.

## Opcion recomendada

Usar Render con Docker y el archivo `render.yaml` incluido en este repositorio.

Render lee `render.yaml`, crea el servicio web, pide los secretos marcados con `sync: false` y redeploya automaticamente cuando subes cambios al repositorio conectado.

## Pasos

1. Sube este repositorio a GitHub.
2. En Render, crea un nuevo Blueprint y conecta el repositorio.
3. Render detectara `render.yaml`.
4. Completa los secretos cuando Render los pida:
   - `ALPACA_API_KEY`
   - `ALPACA_API_SECRET`
   - `POLYGON_API_KEY` si quieres mejor data live/historica
   - `TRADINGVIEW_WEBHOOK_SECRET` si vas a recibir webhooks
   - variables de Pushover o Telegram si quieres alertas push
5. Espera el deploy.
6. Abre la URL publica de Render desde cualquier dispositivo.

## Seguridad de trading

El deploy queda en modo seguro:

```text
ALPACA_PAPER=true
ROXY_ENABLE_LIVE_BROKER_EXECUTION=0
ROXY_ALPACA_PAPER_AUTOTRADE=false
```

Esto mantiene Roxy en analisis, paper/manual y simulacion. No coloca ordenes reales.

## Datos persistentes

Render monta un disco en `/var/data`. Roxy usa ese disco para:

```text
ROXY_OUTPUT_DIR=/var/data/output
ROXY_ALERTS_DIR=/var/data/alerts
ROXY_DATA_DIR=/var/data/data
ROXY_DB_DIR=/var/data/db
```

Asi los historiales, alertas y memoria operativa no se pierden en cada redeploy.

## URL estable

Cuando Render termine, tendras una direccion parecida a:

```text
https://roxy-trading.onrender.com
```

Esa es la direccion que debes abrir en todos tus dispositivos.

## Importante para trading live

Un plan gratuito o dormido no sirve para tomar decisiones de trading activas porque puede tardar en despertar. Para operar todos los dias, usa un servicio siempre encendido y conecta fuentes de datos con baja latencia.

Si no configuras una fuente premium como Polygon/Alpaca con permisos suficientes, Roxy puede usar datos publicos o fallback y lo indicara en pantalla como delayed, stale o fallback.

## Desarrollo local

El desarrollo local sigue usando una sola direccion:

```bash
make dev-web
```

```text
http://localhost:3000
```
