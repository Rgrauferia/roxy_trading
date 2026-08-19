# Roxy Trading y Roxy Crypto independientes

Roxy conserva una identidad común, pero las dos superficies de mercado se despliegan como servicios separados:

- `roxy-stocks`: acciones y ETFs.
- `roxy-crypto`: activos crypto disponibles 24/7.

Cada servicio obtiene el precio en el servidor: Trading consume el bridge sanitizado de acciones y Crypto consulta el ticker público del exchange mediante CCXT. El navegador no puede aportar ni alterar el contexto enviado a OpenAI. Si el proveedor no devuelve un precio y una fuente verificables, Roxy bloquea cualquier afirmación sobre el mercado actual.

## Aislamiento OpenAI

Trading utiliza exclusivamente `ROXY_TRADING_OPENAI_*`; Crypto utiliza exclusivamente `ROXY_CRYPTO_OPENAI_*`. Ninguno acepta `OPENAI_API_KEY`, claves de Study/Home ni la clave del otro mercado.

Variables obligatorias por servicio:

```text
ROXY_{TRADING|CRYPTO}_ACCESS_KEY
ROXY_{TRADING|CRYPTO}_OPENAI_ENABLED=1
ROXY_{TRADING|CRYPTO}_OPENAI_API_KEY
ROXY_{TRADING|CRYPTO}_OPENAI_ROUTINE_MODEL=gpt-5.6-luna
ROXY_{TRADING|CRYPTO}_OPENAI_DEEP_MODEL=gpt-5.6-terra
ROXY_{TRADING|CRYPTO}_OPENAI_MONTHLY_BUDGET_USD=20
ROXY_{TRADING|CRYPTO}_OPENAI_MAX_CALL_USD=0.25
ROXY_{TRADING|CRYPTO}_OPENAI_USAGE_DB=/var/data/alerts/roxy_{trading|crypto}_openai_usage.sqlite
```

Las llamadas usan Responses API con `store=false`. Luna atiende explicaciones rutinarias y Terra las investigaciones profundas. Cuando una consulta profunda solicita noticias, catalizadores, macro o regulación vigente, Terra fuerza `web_search` con `tool_choice="required"`; si no existe una llamada de búsqueda verificable, la respuesta se rechaza.

## Permisos

- OpenAI explica el precio, riesgo, evidencia y escenarios.
- Una instrucción de compra/venta requiere confirmación para generar únicamente un preview explicativo.
- `execution_allowed` siempre permanece en `false`.
- Los motores deterministas, fuentes reales y gates paper/live siguen teniendo autoridad.
- La clave OpenAI y la clave de acceso nunca se exponen en HTML o JavaScript.

## Desarrollo local

```bash
ROXY_MARKET_PRODUCT=trading ROXY_TRADING_ACCESS_KEY=local-key \
  uvicorn tools.roxy_market_service:app --port 8770

ROXY_MARKET_PRODUCT=crypto ROXY_CRYPTO_ACCESS_KEY=local-key \
  uvicorn tools.roxy_market_service:app --port 8771
```

En Render, `render.yaml` define discos, claves, presupuestos y URLs independientes. Antes de activar producción hay que introducir dos secretos distintos: `ROXY_TRADING_OPENAI_API_KEY` y `ROXY_CRYPTO_OPENAI_API_KEY`.
