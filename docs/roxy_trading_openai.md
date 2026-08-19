# OpenAI en Roxy Trading

Roxy mantiene una sola identidad y ElevenLabs conserva su voz. OpenAI agrega
razonamiento textual al producto Trading, pero no sustituye el motor de mercado,
los proveedores de precios ni los gates de ejecución.

## Separación obligatoria

- Usa un proyecto y una clave exclusivos para Roxy Trading:
  `ROXY_TRADING_OPENAI_API_KEY`.
- El código no lee `OPENAI_API_KEY` ni una clave de Study/Home.
- La memoria de conversación no se comparte: cada llamada usa Responses API con
  `store=false` y recibe únicamente el contexto Trading sanitizado de esa sesión.
- El presupuesto y la telemetría viven en
  `alerts/roxy_trading_openai_usage.sqlite`, separados por producto. El archivo
  contiene modelo, tokens y costo estimado; nunca contiene la clave ni el prompt.
- La clave debe configurarse solo como secreto del servidor. No se envía a
  Streamlit, JavaScript, ElevenLabs ni al navegador.

## Routing

- Rutina y explicación breve: `gpt-5.6-luna`.
- Investigación vigente, noticias, macro y escenarios profundos:
  `gpt-5.6-terra`.
- Ambos nombres se pueden cambiar con variables `ROXY_TRADING_OPENAI_*_MODEL`
  sin modificar código.
- Referencia oficial de modelos y precios:
  https://developers.openai.com/api/docs/models

## Contrato de datos y seguridad

La ruta autenticada `POST /api/ai/explain` acepta una pregunta y un `context`
producido por Roxy. Las preguntas sobre mercado actual requieren `sources` y
deben incluir `data_as_of` cuando esté disponible. Roxy devuelve las mismas
fuentes en la respuesta y no completa precios, noticias, stops o targets
ausentes.

OpenAI solamente explica señales ya calculadas, riesgo y escenarios. Nunca
coloca órdenes, nunca marca una simulación como ejecutada y nunca evita gates
paper/live. Una instrucción sensible como “compra” o “vende” devuelve
`confirmation_required`; después de confirmar solo puede generar un preview y
`execution_allowed` permanece en `false`.

Ejemplo de payload:

```json
{
  "question": "Explica el riesgo de esta oportunidad de AAPL",
  "depth": "routine",
  "confirmed": false,
  "context": {
    "symbol": "AAPL",
    "signal": "WATCH",
    "entry": 231.42,
    "stop": 228.90,
    "target": 236.50,
    "data_as_of": "2026-08-19T14:31:00Z",
    "sources": [
      {"name": "Alpaca IEX", "as_of": "2026-08-19T14:31:00Z"},
      {"name": "Finviz Elite", "as_of": "2026-08-19T14:30:00Z"}
    ]
  }
}
```

## Activación

1. Crear un proyecto OpenAI exclusivo de Roxy Trading y aplicar allí límites de
   gasto del proveedor.
2. Añadir la clave y un presupuesto local mayor que cero en los secretos del
   servicio.
3. Verificar las cuatro tarifas por millón de tokens antes de producción. El
   template incluye el precio oficial consultado el 19 de agosto de 2026; si las
   tarifas se eliminan, el ledger cobra la reserva conservadora por llamada.
4. Establecer `ROXY_TRADING_OPENAI_ENABLED=1` y reiniciar el backend.
5. Consultar el estado público con `trading_openai_status()`; nunca devuelve la
   clave.
