# Roxy Crypto · Pulso de la hora

Ruta privada `/pulso`, disponible solo con `ROXY_MARKET_PRODUCT=crypto` y la sesión existente. La portada enlaza al panel; `/contratos/1h` conserva revisión manual de costes, importación CSV y exportación local.

El panel empieza vacío. Cargar catálogo es una acción explícita; no hay lecturas al abrir. Seleccionar un contrato fija activo, strike, operador y vencimiento. Iniciar seguimiento lee REST público cada diez segundos, sin cuentas, cookies de proveedor ni credenciales. No hay WebSocket ni órdenes. Los errores, 403, datos caducados, cierre de ventana y vencimiento detienen el seguimiento y retiran cotizaciones actuales. La selección no cambia automáticamente.

El catálogo carga como máximo una página de 1000 instrumentos; si hay cursor muestra cobertura parcial. Durante el seguimiento se filtra por el símbolo seleccionado. Bid y ask nativos no se convierten a Sí/No. El precio BTC es el último cierre spot de 5m, con hora y fuente; no se presenta como índice CDNA. El contexto 1h agrupa cuatro velas reales cerradas de 15m.

La lectura técnica muestra distancia al nivel, EMA9/EMA21 y rango histórico observado. No genera porcentajes de acierto ni señales de compra. **Probabilidades de cierre del contrato y correspondencia económica Sí/No siguen pendientes de datos y validación.** El panel no debe describirse como un predictor listo para operar.

Validación local de este corte: 72 pruebas JavaScript (contrato, feed, agregación y UI), cuatro comprobaciones ASGI/estructura adicionales. La comprobación pública DCM del 13/10/2026 recibió HTTP403; no acredita conexión real. Revisión visual y estado de despliegue deben consultarse en el recibo de entrega.

Pruebas autocontenidas del commit:

```sh
python3 -B tests/test_crypto_pulso_routes.py
node --test tests/test_crypto_pulso_ui.js
```

Python >=3.10 y dependencias de `requirements-roxy-market.txt` más httpx para pruebas. Las pruebas usan credenciales sintéticas e IA inerte. El Docker de producción incluye las plantillas privadas y recursos estáticos; CSP permite solo el origen público fijo para estas dos rutas Crypto.
