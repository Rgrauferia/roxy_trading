#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { runTerminalTask } = require("../roxy-terminal-agent/command-runner.ts");
const { runCodeIndexer } = require("./code-indexer.ts");

const ROOT = path.resolve(__dirname, "..");
const CONFIG = JSON.parse(fs.readFileSync(path.join(__dirname, "config.json"), "utf8"));
const REPORT_DIR = path.join(__dirname, "reports");
const PROPOSAL_DIR = path.join(__dirname, "proposals");
const MEMORY_DIR = path.join(__dirname, "memory");

function ensureDirs() {
  fs.mkdirSync(REPORT_DIR, { recursive: true });
  fs.mkdirSync(PROPOSAL_DIR, { recursive: true });
  fs.mkdirSync(MEMORY_DIR, { recursive: true });
}

function stamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function createImprovementProposals(indexReport) {
  const proposals = [];
  for (const finding of indexReport.findings.slice(0, 12)) {
    const proposal = {
      id: `${finding.area}-${proposals.length + 1}`,
      status: CONFIG.autoApplyWithoutApproval.includes(finding.area) ? "auto_allowed" : "approval_required",
      area: finding.area,
      severity: finding.severity,
      file: finding.file,
      title: finding.title,
      reason: finding.detail,
      safeAutonomousActions: [],
      qualityGates: [],
    };

    if (finding.area === "chart_reliability") {
      proposal.safeAutonomousActions.push("Verificar que la grafica muestre precio live, entrada, stop, target, timeframe y fuente.");
      proposal.safeAutonomousActions.push("Crear o actualizar tests visuales/logicos de contrato de grafica.");
      proposal.qualityGates.push("No romper crypto ni acciones.");
      proposal.qualityGates.push("Debe preservar datos reales y fuente visible.");
    } else if (finding.area === "strategy_research") {
      proposal.safeAutonomousActions.push("Comparar reglas contra knowledge base y backtests.");
      proposal.safeAutonomousActions.push("Separar condiciones de entrada, invalidez, stop, target y riesgo.");
      proposal.qualityGates.push("Toda estrategia debe tener backtest o paper-trading report.");
    } else {
      proposal.safeAutonomousActions.push("Refactor interno conservador dentro del proyecto.");
      proposal.safeAutonomousActions.push("Agregar o actualizar pruebas enfocadas.");
      proposal.qualityGates.push("Compilacion y tests enfocados deben pasar.");
    }
    proposals.push(proposal);
  }
  return proposals;
}

function runQualityChecks() {
  const commands = ["python3 -m py_compile streamlit_app.py roxy_ai.py living_market.py symbol_detail.py"];
  for (const testPath of CONFIG.focusedTests || []) {
    if (fs.existsSync(path.join(ROOT, testPath))) {
      commands.push(`pytest ${testPath}`);
    }
  }
  return runTerminalTask({
    objective: "Roxy self-improvement quality checks",
    commands,
  });
}

function writeMemory(cycle) {
  const memoryPath = path.join(MEMORY_DIR, "improvement-memory.jsonl");
  fs.appendFileSync(memoryPath, `${JSON.stringify({
    createdAt: cycle.createdAt,
    status: cycle.status,
    findings: cycle.index.findings.length,
    proposals: cycle.proposals.length,
    qualityStatus: cycle.quality?.status || "not_run",
  })}\n`);
}

function runSelfImprovementCycle(options = {}) {
  ensureDirs();
  const index = runCodeIndexer();
  const proposals = createImprovementProposals(index);
  const quality = options.skipChecks ? null : runQualityChecks();
  const cycle = {
    createdAt: new Date().toISOString(),
    mode: CONFIG.mode,
    status: quality && quality.status !== "ok" ? "needs_autonomous_fix" : "ready",
    autonomy: {
      autoApplyWithoutApproval: CONFIG.autoApplyWithoutApproval,
      humanApprovalRequired: CONFIG.humanApprovalRequired,
      note: "Roxy puede aplicar cambios internos de codigo/trading paper/backtesting sin pedir permiso; dinero real, push y deploy siguen bloqueados.",
    },
    index,
    proposals,
    quality,
    nextActions: [
      "Conectar este ciclo a la UI/cerebro de Roxy.",
      "Permitir que Roxy elija una propuesta auto_allowed y genere un patch dentro del proyecto.",
      "Ejecutar quality checks despues de cada patch.",
      "Guardar aprendizaje de cada intento en memory/improvement-memory.jsonl.",
    ],
  };

  const reportPath = path.join(REPORT_DIR, `improvement-cycle-${stamp()}.json`);
  const latestPath = path.join(REPORT_DIR, "latest-improvement-cycle.json");
  const proposalPath = path.join(PROPOSAL_DIR, `proposals-${stamp()}.json`);
  fs.writeFileSync(reportPath, JSON.stringify(cycle, null, 2));
  fs.writeFileSync(latestPath, JSON.stringify(cycle, null, 2));
  fs.writeFileSync(proposalPath, JSON.stringify(proposals, null, 2));
  writeMemory(cycle);
  return cycle;
}

if (require.main === module) {
  const args = new Set(process.argv.slice(2));
  const result = runSelfImprovementCycle({ skipChecks: args.has("--skip-checks") });
  console.log(JSON.stringify({
    status: result.status,
    findings: result.index.findings.length,
    proposals: result.proposals.length,
    qualityStatus: result.quality?.status || "not_run",
    report: "roxy-self-improvement/reports/latest-improvement-cycle.json",
  }, null, 2));
}

module.exports = { runSelfImprovementCycle };
