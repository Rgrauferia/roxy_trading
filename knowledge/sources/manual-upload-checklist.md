# Roxy Knowledge Manual Upload Checklist

Este archivo enumera las fuentes que Roxy debe aprender cuando tengas copias legales. No descarga contenido con copyright automaticamente.

## Nivel 1: Biblioteca

Coloca PDFs, TXT o MD legales en `knowledge/inbox/libros`.

### Analisis tecnico

- Technical Analysis of the Financial Markets
- Encyclopedia of Chart Patterns
- Japanese Candlestick Charting Techniques
- The Art and Science of Technical Analysis
- Trading Price Action Trends
- Trading Price Action Reversals
- Trading Price Action Trading Ranges

### Psicologia

- Trading in the Zone
- The Disciplined Trader
- The Daily Trading Coach

### Gestion del riesgo

- Trade Your Way to Financial Freedom
- The New Trading for a Living

### Opciones

- Options as a Strategic Investment
- Trading Options Greeks

### Inversion

- The Intelligent Investor
- Security Analysis
- One Up On Wall Street

## Nivel 2: Cursos

Coloca transcripciones, notas o materiales autorizados en `knowledge/inbox/cursos`.

- TradingView
- ICT
- Smart Money Concepts
- Wyckoff
- Market Profile
- Volume Profile
- Options Trading
- Futures
- Forex
- Crypto

## Nivel 3: Datos de mercado

No subir llaves API al inbox. Las credenciales deben ir en variables de entorno. Los conectores se habilitan por separado.

- Polygon.io
- Alpaca
- Alpha Vantage
- Twelve Data
- Binance

## Nivel 4 a 8

- Indicadores: `knowledge/inbox/indicadores`
- Economia: `knowledge/inbox/economia`
- Noticias autorizadas: `knowledge/inbox/noticias`
- Estrategias internas: `knowledge/inbox/estrategias`
- Backtesting: `knowledge/inbox/backtesting`

Despues de subir archivos, ejecuta:

```bash
node scripts/ingestKnowledge.ts --dry-run
node scripts/ingestKnowledge.ts
```
