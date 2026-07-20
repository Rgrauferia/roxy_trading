#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const PROJECT_ROOT = path.resolve(__dirname, "..");
const STATUS_PATH = path.join(PROJECT_ROOT, "knowledge", "sources", "autonomous-update-status.json");
const LOG_DIR = path.join(PROJECT_ROOT, "knowledge", "logs");

function readJson(filePath, fallback) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return fallback;
  }
}

function launchdStatus() {
  const uid = String(process.getuid ? process.getuid() : "");
  if (!uid) return { available: false };
  const result = spawnSync("launchctl", ["print", `gui/${uid}/com.roxy.knowledge-autopilot`], {
    encoding: "utf8",
    maxBuffer: 1024 * 1024,
  });
  if (result.status !== 0) {
    return { installed: false, detail: result.stderr || result.stdout || "not loaded" };
  }
  const state = (result.stdout.match(/state = ([^\n]+)/) || [])[1] || "unknown";
  const interval = (result.stdout.match(/run interval = ([^\n]+)/) || [])[1] || "unknown";
  const lastExit = (result.stdout.match(/last exit code = ([^\n]+)/) || [])[1] || "unknown";
  return { installed: true, state, interval, lastExit };
}

function latestLog() {
  if (!fs.existsSync(LOG_DIR)) return null;
  const logs = fs.readdirSync(LOG_DIR)
    .filter((name) => /^knowledge-update-.*\.log$/.test(name))
    .map((name) => ({ name, path: path.join(LOG_DIR, name), mtime: fs.statSync(path.join(LOG_DIR, name)).mtimeMs }))
    .sort((a, b) => b.mtime - a.mtime);
  return logs[0] ? path.relative(PROJECT_ROOT, logs[0].path) : null;
}

const status = readJson(STATUS_PATH, null);
const payload = {
  autopilot: launchdStatus(),
  lastUpdate: status,
  latestLog: latestLog(),
};

console.log(JSON.stringify(payload, null, 2));
