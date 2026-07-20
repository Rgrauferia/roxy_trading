#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const CONFIG = JSON.parse(fs.readFileSync(path.join(__dirname, "config.json"), "utf8"));
const REPORT_DIR = path.join(__dirname, "reports");

const CODE_EXTENSIONS = new Set([".py", ".ts", ".js", ".json", ".md", ".yml", ".yaml"]);

function shouldIgnore(relativePath) {
  return CONFIG.ignore.some((item) => relativePath === item || relativePath.startsWith(`${item}/`));
}

function walk(dir, files = []) {
  for (const name of fs.readdirSync(dir)) {
    const fullPath = path.join(dir, name);
    const relativePath = path.relative(ROOT, fullPath);
    if (shouldIgnore(relativePath)) continue;
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      walk(fullPath, files);
    } else if (CODE_EXTENSIONS.has(path.extname(name))) {
      files.push({ fullPath, relativePath, size: stat.size });
    }
  }
  return files;
}

function countMatches(text, pattern) {
  return (text.match(pattern) || []).length;
}

function analyzeFile(file) {
  const text = fs.readFileSync(file.fullPath, "utf8");
  const lines = text.split(/\r?\n/);
  return {
    path: file.relativePath,
    extension: path.extname(file.relativePath),
    size: file.size,
    lines: lines.length,
    functions: countMatches(text, /^\s*def\s+\w+|^\s*function\s+\w+|^\s*const\s+\w+\s*=\s*\(/gm),
    classes: countMatches(text, /^\s*class\s+\w+/gm),
    todos: countMatches(text, /\bTODO\b|\bFIXME\b|\bHACK\b/gi),
    chartMentions: countMatches(text, /chart|grafica|candl|vela|plotly|altair|tradingview/gi),
    strategyMentions: countMatches(text, /strategy|estrategia|signal|senal|entry|entrada|stop|target|risk|riesgo|backtest/gi),
    realtimeMentions: countMatches(text, /websocket|stream|live|tick|realtime|tiempo real/gi),
    possibleSecrets: countMatches(text, /api[_-]?key|secret|token|password/gi),
  };
}

function topBy(items, key, limit = 10) {
  return [...items].sort((a, b) => b[key] - a[key]).slice(0, limit);
}

function createFindings(files) {
  const findings = [];
  const hugeFiles = files.filter((file) => file.lines > 1200);
  for (const file of hugeFiles) {
    findings.push({
      severity: "high",
      area: "code_quality",
      file: file.path,
      title: "Archivo demasiado grande",
      detail: `${file.path} tiene ${file.lines} lineas. Roxy debe dividirlo por modulos para poder mejorarlo con menor riesgo.`,
    });
  }

  for (const file of files.filter((item) => item.chartMentions > 20 && item.realtimeMentions < 2)) {
    findings.push({
      severity: "medium",
      area: "chart_reliability",
      file: file.path,
      title: "Grafica sin suficiente contrato realtime visible",
      detail: "El archivo habla mucho de graficas, pero casi no declara flujo live/tick/realtime. Revisar calidad operativa.",
    });
  }

  for (const file of files.filter((item) => item.strategyMentions > 30 && item.chartMentions < 2)) {
    findings.push({
      severity: "medium",
      area: "strategy_research",
      file: file.path,
      title: "Estrategia sin visualizacion o trazabilidad clara",
      detail: "El archivo contiene mucha logica de estrategia, pero pocas referencias a graficas o explicacion visual.",
    });
  }

  for (const file of files.filter((item) => item.todos > 0)) {
    findings.push({
      severity: "low",
      area: "code_quality",
      file: file.path,
      title: "TODO/FIXME pendiente",
      detail: `${file.todos} marcador(es) pendiente(s).`,
    });
  }

  return findings;
}

function runCodeIndexer() {
  fs.mkdirSync(REPORT_DIR, { recursive: true });
  const files = walk(ROOT).map(analyzeFile);
  const report = {
    createdAt: new Date().toISOString(),
    projectRoot: ROOT,
    totals: {
      files: files.length,
      lines: files.reduce((sum, file) => sum + file.lines, 0),
      chartMentions: files.reduce((sum, file) => sum + file.chartMentions, 0),
      strategyMentions: files.reduce((sum, file) => sum + file.strategyMentions, 0),
    },
    hotspots: {
      largestFiles: topBy(files, "lines", 12),
      chartFiles: topBy(files.filter((file) => file.chartMentions > 0), "chartMentions", 12),
      strategyFiles: topBy(files.filter((file) => file.strategyMentions > 0), "strategyMentions", 12),
      realtimeFiles: topBy(files.filter((file) => file.realtimeMentions > 0), "realtimeMentions", 12),
    },
    findings: createFindings(files),
  };
  const outPath = path.join(REPORT_DIR, "code-index.json");
  fs.writeFileSync(outPath, JSON.stringify(report, null, 2));
  return report;
}

if (require.main === module) {
  console.log(JSON.stringify(runCodeIndexer(), null, 2));
}

module.exports = { runCodeIndexer };
