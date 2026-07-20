#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const PROJECT_ROOT = path.resolve(__dirname, "..");
const KNOWLEDGE_ROOT = path.join(PROJECT_ROOT, "knowledge");
const LOG_DIR = path.join(KNOWLEDGE_ROOT, "logs");
const SOURCE_DIR = path.join(KNOWLEDGE_ROOT, "sources");
const PROCESSED_DIR = path.join(KNOWLEDGE_ROOT, "processed");
const CONFIG_PATH = path.join(SOURCE_DIR, "autonomous-update-config.json");
const STATUS_PATH = path.join(SOURCE_DIR, "autonomous-update-status.json");
const LOCK_PATH = path.join(SOURCE_DIR, ".autonomous-update.lock");

function ensureDirs() {
  fs.mkdirSync(LOG_DIR, { recursive: true });
  fs.mkdirSync(SOURCE_DIR, { recursive: true });
}

function readJson(filePath, fallback) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return fallback;
  }
}

function isoForFile(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, "-");
}

function isStaleLock(lock) {
  if (!lock || !lock.startedAt) return true;
  return Date.now() - Date.parse(lock.startedAt) > 1000 * 60 * 60 * 3;
}

function acquireLock() {
  if (fs.existsSync(LOCK_PATH)) {
    const existing = readJson(LOCK_PATH, null);
    if (!isStaleLock(existing)) {
      throw new Error(`Knowledge update already running since ${existing.startedAt}`);
    }
  }
  fs.writeFileSync(LOCK_PATH, JSON.stringify({
    pid: process.pid,
    startedAt: new Date().toISOString(),
  }, null, 2));
}

function releaseLock() {
  fs.rmSync(LOCK_PATH, { force: true });
}

function runStep(name, command, args, logLines) {
  const startedAt = new Date();
  logLines.push(`\n## ${name}`);
  logLines.push(`$ ${command} ${args.join(" ")}`);
  const result = spawnSync(command, args, {
    cwd: PROJECT_ROOT,
    encoding: "utf8",
    maxBuffer: 1024 * 1024 * 120,
  });
  if (result.stdout) logLines.push(result.stdout.trim());
  if (result.stderr) logLines.push(`STDERR:\n${result.stderr.trim()}`);
  const finishedAt = new Date();
  const step = {
    name,
    command: `${command} ${args.join(" ")}`,
    status: result.status === 0 ? "ok" : "failed",
    exitCode: result.status,
    startedAt: startedAt.toISOString(),
    finishedAt: finishedAt.toISOString(),
    durationMs: finishedAt.getTime() - startedAt.getTime(),
  };
  if (result.status !== 0) {
    step.error = result.stderr || result.stdout || "Unknown command failure";
  }
  return step;
}

function summarizeProcessedKnowledge() {
  const summary = {
    documents: 0,
    fragments: 0,
    fragmentsByCategory: {},
    failedDocuments: 0,
  };
  if (!fs.existsSync(PROCESSED_DIR)) return summary;
  for (const dirName of fs.readdirSync(PROCESSED_DIR)) {
    const dir = path.join(PROCESSED_DIR, dirName);
    if (!fs.statSync(dir).isDirectory()) continue;
    const manifestPath = path.join(dir, "manifest.json");
    const failedPath = path.join(dir, "failed.json");
    if (fs.existsSync(failedPath)) {
      summary.failedDocuments += 1;
      continue;
    }
    if (!fs.existsSync(manifestPath)) continue;
    const manifest = readJson(manifestPath, null);
    if (!manifest) continue;
    summary.documents += 1;
    summary.fragments += manifest.chunkCount || 0;
    const category = manifest.category || "sin-categoria";
    summary.fragmentsByCategory[category] = (summary.fragmentsByCategory[category] || 0) + (manifest.chunkCount || 0);
  }
  return summary;
}

function main() {
  ensureDirs();
  const config = readJson(CONFIG_PATH, { enabled: false, tasks: {} });
  const args = new Set(process.argv.slice(2));
  if (!config.enabled && !args.has("--force")) {
    const status = {
      status: "disabled",
      checkedAt: new Date().toISOString(),
      message: "Autonomous knowledge update is disabled in autonomous-update-config.json.",
    };
    fs.writeFileSync(STATUS_PATH, JSON.stringify(status, null, 2));
    console.log(JSON.stringify(status, null, 2));
    return;
  }

  const startedAt = new Date();
  const logFile = path.join(LOG_DIR, `knowledge-update-${isoForFile(startedAt)}.log`);
  const logLines = [
    `# Roxy Knowledge Autopilot`,
    `startedAt: ${startedAt.toISOString()}`,
    `project: ${PROJECT_ROOT}`,
    `legalMode: ${config.legalMode || "public_and_user_owned_only"}`,
  ];
  const steps = [];
  let status = "ok";

  try {
    acquireLock();
    if (config.tasks?.refreshInternalStudyNotes !== false) {
      steps.push(runStep("refresh-internal-study-notes", "node", ["scripts/createStudyNotes.ts"], logLines));
    }
    if (config.tasks?.refreshPublicSources !== false) {
      steps.push(runStep("refresh-public-sources", "node", ["scripts/downloadPublicKnowledge.ts"], logLines));
    }
    if (config.tasks?.refreshMacroData !== false) {
      steps.push(runStep("refresh-macro-data", "node", ["scripts/downloadMacroData.ts"], logLines));
    }
    if (config.tasks?.ingestInbox !== false) {
      steps.push(runStep("ingest-knowledge", "node", ["scripts/ingestKnowledge.ts"], logLines));
    }
    if (steps.some((step) => step.status !== "ok")) status = "partial_failure";
  } catch (error) {
    status = "failed";
    logLines.push(`\nERROR:\n${error.stack || error.message}`);
  } finally {
    releaseLock();
  }

  const finishedAt = new Date();
  const processed = summarizeProcessedKnowledge();
  const payload = {
    status,
    startedAt: startedAt.toISOString(),
    finishedAt: finishedAt.toISOString(),
    durationMs: finishedAt.getTime() - startedAt.getTime(),
    nextRecommendedRunHours: config.intervalHours || 6,
    logFile: path.relative(PROJECT_ROOT, logFile),
    steps,
    processed,
    safety: config.safety || {},
  };
  logLines.push(`\n## Summary`);
  logLines.push(JSON.stringify(payload, null, 2));
  fs.writeFileSync(logFile, `${logLines.join("\n")}\n`, "utf8");
  fs.writeFileSync(STATUS_PATH, JSON.stringify(payload, null, 2), "utf8");
  console.log(JSON.stringify(payload, null, 2));
  if (status === "failed") process.exit(1);
  if (status === "partial_failure") process.exit(2);
}

main();
