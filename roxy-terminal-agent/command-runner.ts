#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const { classifyCommand, redactSecrets, splitCommand } = require("./safety.ts");

const AGENT_ROOT = __dirname;
const DEFAULT_CONFIG_PATH = path.join(AGENT_ROOT, "config.json");

function readJson(filePath, fallback) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return fallback;
  }
}

function ensureDirs() {
  fs.mkdirSync(path.join(AGENT_ROOT, "task-logs"), { recursive: true });
  fs.mkdirSync(path.join(AGENT_ROOT, "reports"), { recursive: true });
}

function slugify(value) {
  return String(value || "task")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60) || "task";
}

function timestampForFile(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, "-");
}

function normalizeTask(task) {
  if (typeof task === "string") {
    return { objective: task, commands: [] };
  }
  return {
    objective: task?.objective || task?.task || "Roxy terminal task",
    commands: Array.isArray(task?.commands) ? task.commands : [],
    approvedActions: Array.isArray(task?.approvedActions) ? task.approvedActions : [],
    dryRun: Boolean(task?.dryRun),
  };
}

function createPlan(task, config) {
  const objective = task.objective.toLowerCase();
  const commands = [];
  const notes = [];

  if (task.commands.length) {
    commands.push(...task.commands);
    notes.push("Plan creado desde comandos explicitos de la tarea.");
  } else {
    commands.push("pwd");
    commands.push("git status --short");
    if (/(buscar|encuentra|search|archivo|file|estructura|inspect|revis)/i.test(objective)) {
      commands.push("rg --files");
    }
    if (/(test|prueba|verifica|verify)/i.test(objective)) {
      commands.push("pytest");
    }
    if (/(build|compilar)/i.test(objective)) {
      commands.push("make test");
    }
    if (/(lint)/i.test(objective)) {
      commands.push("python -m compileall .");
    }
    notes.push("No se recibieron comandos explicitos; Roxy creo un plan conservador de inspeccion/verificacion.");
  }

  const max = config.maxCommandsPerTask || 20;
  return {
    objective: task.objective,
    commands: commands.slice(0, max),
    notes,
  };
}

function runCommand(command, config, task, logLines) {
  const classification = classifyCommand(command, config, { approvedActions: task.approvedActions });
  const startedAt = new Date();
  const entry = {
    command,
    startedAt: startedAt.toISOString(),
    status: "pending",
    exitCode: null,
    stdout: "",
    stderr: "",
    safety: classification,
  };

  logLines.push(`\n## $ ${command}`);
  if (!classification.allowed) {
    entry.status = classification.approvalRequired ? "approval_required" : "blocked";
    entry.stderr = classification.reasons.join("\n");
    entry.finishedAt = new Date().toISOString();
    logLines.push(`BLOCKED:\n${entry.stderr}`);
    return entry;
  }

  if (task.dryRun) {
    entry.status = "dry_run";
    entry.finishedAt = new Date().toISOString();
    logLines.push("DRY RUN: comando validado, no ejecutado.");
    return entry;
  }

  const parts = splitCommand(command);
  const executable = parts[0];
  const args = parts.slice(1);
  const result = spawnSync(executable, args, {
    cwd: config.projectRoot,
    encoding: "utf8",
    timeout: config.defaultTimeoutMs || 120000,
    maxBuffer: 1024 * 1024 * 40,
    env: {
      ...process.env,
      ROXY_TERMINAL_AGENT: "1",
      PYTHONPATH: config.projectRoot,
    },
  });

  entry.exitCode = result.status;
  entry.stdout = redactSecrets(result.stdout || "");
  entry.stderr = redactSecrets(result.stderr || "");
  entry.status = result.status === 0 ? "ok" : "failed";
  entry.finishedAt = new Date().toISOString();
  if (entry.stdout) logLines.push(entry.stdout.trim());
  if (entry.stderr) logLines.push(`STDERR:\n${entry.stderr.trim()}`);
  if (result.error) {
    entry.status = "failed";
    entry.stderr = redactSecrets(result.error.message);
    logLines.push(`ERROR:\n${entry.stderr}`);
  }
  return entry;
}

function summarize(entries) {
  const blocked = entries.filter((entry) => entry.status === "blocked");
  const approvalRequired = entries.filter((entry) => entry.status === "approval_required");
  const failed = entries.filter((entry) => entry.status === "failed");
  if (blocked.length) return "blocked";
  if (approvalRequired.length) return "approval_required";
  if (failed.length) return "failed";
  return "ok";
}

function writeArtifacts(task, plan, entries, status, logLines) {
  ensureDirs();
  const stamp = timestampForFile();
  const name = `${stamp}-${slugify(task.objective)}`;
  const logPath = path.join(AGENT_ROOT, "task-logs", `${name}.log`);
  const reportPath = path.join(AGENT_ROOT, "reports", `${name}.json`);
  const report = {
    agent: "Roxy Terminal Agent",
    status,
    objective: task.objective,
    createdAt: new Date().toISOString(),
    plan,
    commands: entries.map((entry) => ({
      command: entry.command,
      status: entry.status,
      exitCode: entry.exitCode,
      safetyReasons: entry.safety?.reasons || [],
      approvalRequired: entry.safety?.approvalRequired || null,
    })),
    explanation: buildExplanation(status, entries),
    logFile: path.relative(path.dirname(AGENT_ROOT), logPath),
  };
  fs.writeFileSync(logPath, `${logLines.join("\n")}\n`, "utf8");
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), "utf8");
  return { report, logPath, reportPath };
}

function buildExplanation(status, entries) {
  if (status === "blocked") {
    const blocked = entries.find((entry) => entry.status === "blocked");
    return `Me detuve porque detecte un comando peligroso o fuera de las reglas: ${blocked?.command}.`;
  }
  if (status === "approval_required") {
    const pending = entries.find((entry) => entry.status === "approval_required");
    return `Necesito aprobacion antes de ejecutar: ${pending?.command}.`;
  }
  if (status === "failed") {
    const failed = entries.find((entry) => entry.status === "failed");
    return `Ejecute el plan, pero fallo este comando: ${failed?.command}. Revisa el log para el error completo.`;
  }
  return "Ejecute el plan permitido, guarde logs y no detecte comandos peligrosos.";
}

function runTerminalTask(inputTask) {
  const config = readJson(DEFAULT_CONFIG_PATH, {});
  const task = normalizeTask(inputTask);
  ensureDirs();
  const plan = createPlan(task, config);
  const logLines = [
    "# Roxy Terminal Agent",
    `objective: ${task.objective}`,
    `startedAt: ${new Date().toISOString()}`,
    `projectRoot: ${config.projectRoot}`,
  ];
  const entries = [];

  for (const command of plan.commands) {
    const entry = runCommand(command, config, task, logLines);
    entries.push(entry);
    if (entry.status === "blocked" || entry.status === "approval_required") break;
  }

  const status = summarize(entries);
  const { report, logPath, reportPath } = writeArtifacts(task, plan, entries, status, logLines);
  return {
    ...report,
    logPath,
    reportPath,
  };
}

if (require.main === module) {
  const raw = process.argv.slice(2).join(" ");
  let task = raw || "Revisar estado del proyecto";
  if (raw.trim().startsWith("{")) {
    task = JSON.parse(raw);
  }
  const result = runTerminalTask(task);
  console.log(JSON.stringify(result, null, 2));
  if (result.status === "blocked") process.exit(2);
  if (result.status === "approval_required") process.exit(3);
  if (result.status === "failed") process.exit(1);
}

module.exports = {
  runTerminalTask,
};
