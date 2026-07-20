#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const PROJECT_ROOT = path.resolve(__dirname, "..");
const OUT_DIR = path.join(PROJECT_ROOT, "knowledge", "inbox", "economia");

const SERIES = [
  { id: "FEDFUNDS", name: "Federal Funds Effective Rate", theme: "tasas" },
  { id: "DGS10", name: "10-Year Treasury Constant Maturity Rate", theme: "bonos" },
  { id: "DGS2", name: "2-Year Treasury Constant Maturity Rate", theme: "bonos" },
  { id: "CPIAUCSL", name: "Consumer Price Index for All Urban Consumers", theme: "inflacion" },
  { id: "CPILFESL", name: "Core CPI", theme: "inflacion" },
  { id: "PPIACO", name: "Producer Price Index by Commodity", theme: "inflacion" },
  { id: "UNRATE", name: "Unemployment Rate", theme: "empleo" },
  { id: "PAYEMS", name: "All Employees, Total Nonfarm", theme: "empleo" },
  { id: "GDP", name: "Gross Domestic Product", theme: "crecimiento" },
  { id: "VIXCLS", name: "CBOE Volatility Index", theme: "volatilidad" }
];

function ensureDir() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
}

function parseCsv(csv) {
  return String(csv || "")
    .trim()
    .split(/\r?\n/)
    .slice(1)
    .map((line) => {
      const [date, value] = line.split(",");
      return { date, value };
    })
    .filter((row) => row.date && row.value && row.value !== ".");
}

async function fetchSeries(series) {
  const url = `https://fred.stlouisfed.org/graph/fredgraph.csv?id=${encodeURIComponent(series.id)}`;
  const response = await fetch(url, { headers: { "User-Agent": "RoxyMacroData/1.0" } });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const rows = parseCsv(await response.text());
  const recent = rows.slice(-36);
  const filePath = path.join(OUT_DIR, `fred-${series.id.toLowerCase()}.md`);
  const body = [
    `# FRED ${series.id} - ${series.name}`,
    "",
    "category: calendario-economico",
    `source: ${url}`,
    "license: FRED public data access",
    `downloadedAt: ${new Date().toISOString()}`,
    `theme: ${series.theme}`,
    "",
    "## Uso para Roxy",
    "",
    "Esta serie ayuda a Roxy a contextualizar riesgo macro, volatilidad y sesgo de mercado. No es una senal de entrada por si sola.",
    "",
    "## Ultimos datos descargados",
    "",
    "| Fecha | Valor |",
    "| --- | ---: |",
    ...recent.map((row) => `| ${row.date} | ${row.value} |`),
    "",
  ].join("\n");
  fs.writeFileSync(filePath, body, "utf8");
  return {
    id: series.id,
    file: path.relative(PROJECT_ROOT, filePath),
    rows: rows.length,
    latest: recent[recent.length - 1] || null,
  };
}

async function main() {
  ensureDir();
  const results = [];
  for (const series of SERIES) {
    try {
      const result = await fetchSeries(series);
      results.push({ ...result, status: "downloaded" });
      console.log(`downloaded ${series.id} -> ${result.file}`);
    } catch (error) {
      results.push({ id: series.id, status: "failed", reason: error.message });
      console.error(`failed ${series.id}: ${error.message}`);
    }
  }
  console.log(JSON.stringify({
    downloaded: results.filter((item) => item.status === "downloaded").length,
    failed: results.filter((item) => item.status === "failed").length,
    results,
  }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
