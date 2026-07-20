#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const PROJECT_ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(PROJECT_ROOT, "knowledge", "inbox", "notas-estudio");

const NOTES = [
  {
    id: "modern-market-structure",
    title: "Roxy Study Notes - Market Structure Moderna",
    category: "apuntes-propios",
    body: `
Estas notas son contenido propio de Roxy. No copian cursos privados. Resumen conceptos generales que Roxy debe entender antes de producir senales.

## Estructura de mercado

Roxy debe leer maximos y minimos relativos para decidir si el precio esta en tendencia alcista, bajista o rango. Una tendencia alcista necesita maximos mas altos y minimos mas altos. Una tendencia bajista necesita maximos mas bajos y minimos mas bajos. Un rango exige paciencia: comprar en medio del rango suele tener mala relacion riesgo/recompensa.

## Liquidez

La liquidez suele acumularse sobre maximos previos, bajo minimos previos y alrededor de numeros redondos. Roxy no debe asumir manipulacion; debe observar si el precio toma liquidez y luego rechaza con volumen o desplazamiento. Una barrida sin confirmacion no es entrada.

## Confirmacion

Una oportunidad de alta calidad combina direccion, contexto, volumen, momentum y riesgo medible. Si falta una pieza, el estado debe ser esperar confirmacion. Si el stop queda demasiado lejos, Roxy debe rechazar la operacion aunque el setup se vea bonito.
`
  },
  {
    id: "options-futures-forex-crypto",
    title: "Roxy Study Notes - Opciones, Futuros, Forex y Crypto",
    category: "apuntes-propios",
    body: `
## Opciones

Una opcion es un contrato derivado. Calls ganan valor si el subyacente sube y puts ganan valor si el subyacente baja, pero el precio tambien depende de tiempo, volatilidad implicita y griegas. Roxy debe distinguir entre direccion correcta y contrato correcto. Una buena direccion puede perder si la expiracion, strike o volatilidad son malos.

## Futuros

Los futuros tienen apalancamiento y vencimientos. Roxy debe controlar tamano de posicion, margen, tick value y calendario economico. En futuros, operar noticias sin plan puede producir movimientos rapidos y stops ineficientes.

## Forex

Forex se mueve por tasas, diferencial economico, politica monetaria y flujos globales. Roxy debe vigilar calendario macro y sesiones. Pares con spread alto o baja liquidez no son ideales para scalping.

## Crypto

Crypto opera 24/7 y puede moverse con liquidez fragmentada. Roxy debe medir volatilidad, volumen, funding, zonas de liquidacion y correlacion con BTC. Una senal de altcoin puede invalidarse si BTC cambia bruscamente.
`
  },
  {
    id: "risk-playbook",
    title: "Roxy Study Notes - Riesgo y Decision Operativa",
    category: "estrategias-internas",
    body: `
## Riesgo primero

Roxy debe calcular entrada, stop, target, riesgo porcentual, ratio riesgo/recompensa y estado operativo antes de recomendar. Si no puede calcular stop, no debe recomendar operar.

## Estados

OPERAR AHORA: direccion, estructura, volumen, momentum y riesgo estan alineados.

ESPERAR CONFIRMACION: hay oportunidad potencial, pero falta cierre, retest, volumen o confirmacion de timeframe superior.

NO OPERAR: el precio esta extendido, el riesgo es malo, hay noticia cerca, el mercado esta lateral o la senal contradice el contexto.

## Registro

Cada operacion debe guardar tesis, activo, timeframe, entrada, stop, target, resultado y leccion. Roxy debe aprender de errores repetidos: entrar tarde, mover stop, operar por emocion, sobreapalancarse o saltarse confirmacion.
`
  },
  {
    id: "indicator-limitations",
    title: "Roxy Study Notes - Limites de Indicadores",
    category: "indicadores",
    body: `
Los indicadores son derivados del precio y volumen. Roxy no debe tratarlos como predictores magicos.

EMA y SMA ayudan a suavizar direccion, pero se retrasan.
RSI mide momentum, pero puede quedarse sobrecomprado en tendencia fuerte.
MACD confirma impulso, pero reacciona tarde en cambios bruscos.
Bollinger Bands muestran volatilidad, pero una banda rota no garantiza continuacion.
ATR ayuda a definir stops, pero no predice direccion.
VWAP sirve como referencia institucional intradia, pero no reemplaza estructura.

La regla operativa es simple: indicador + estructura + volumen + riesgo. Sin riesgo definido, no hay trade.
`
  },
  {
    id: "strategy-library-expansion",
    title: "Roxy Study Notes - Biblioteca de Estrategias",
    category: "estrategias-internas",
    body: `
## Pullback
Operar continuidad despues de retroceso controlado. Requiere tendencia clara, zona logica, vela de confirmacion y stop bajo estructura.

## Breakout
Operar ruptura de rango o nivel clave. Requiere compresion, volumen, cierre y plan de retest o entrada directa.

## Reversal
Operar giro cuando hay agotamiento y confirmacion. Requiere stop pequeno y no debe confundirse con adivinar techos o pisos.

## Gap trading
Analizar gaps por noticias, earnings o flujos. Roxy debe distinguir gap and go, gap fill y gap trap.

## ORB
Definir rango inicial y operar ruptura con volumen. Evitar rangos demasiado grandes o dias con noticia inmediata.

## Momentum
Operar fuerza cuando precio, volumen y mercado general estan alineados. Evitar entrar cuando la vela ya recorrio demasiado.
`
  }
];

function ensureDir() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
}

function writeNote(note) {
  const filePath = path.join(OUT_DIR, `${note.id}.md`);
  const payload = [
    `# ${note.title}`,
    "",
    `category: ${note.category}`,
    "source: Roxy internal study notes",
    `createdAt: ${new Date().toISOString()}`,
    "",
    note.body.trim(),
    "",
  ].join("\n");
  fs.writeFileSync(filePath, payload, "utf8");
  return path.relative(PROJECT_ROOT, filePath);
}

function main() {
  ensureDir();
  const files = NOTES.map(writeNote);
  console.log(JSON.stringify({ created: files.length, files }, null, 2));
}

main();
