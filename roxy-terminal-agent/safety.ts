#!/usr/bin/env node

const path = require("path");

const SECRET_PATTERNS = [
  /sk-[A-Za-z0-9_-]{20,}/g,
  /[A-Za-z0-9_]*API[_-]?KEY[A-Za-z0-9_]*\s*[:=]\s*["']?[^"'\s]+/gi,
  /[A-Za-z0-9_]*SECRET[A-Za-z0-9_]*\s*[:=]\s*["']?[^"'\s]+/gi,
  /[A-Za-z0-9_]*TOKEN[A-Za-z0-9_]*\s*[:=]\s*["']?[^"'\s]+/gi,
  /-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----/g,
];

const ENV_FILE_PATTERN = /(^|[\s"'`=:/])\.env($|[\s"'`:/]|\.((?!example\b)[A-Za-z0-9_-]+))/i;
const DANGEROUS_SHELL_PATTERN = /(\brm\s+(-[A-Za-z]*r[A-Za-z]*f|-[A-Za-z]*f[A-Za-z]*r)\b|\bsudo\b|:\(\)\s*\{\s*:\|:&\s*\};:)/i;
const CHAINING_PATTERN = /(;|&&|\|\||\|)/;
const REDIRECT_PATTERN = /(>\s*\/|>>\s*\/)/;
const DANGEROUS_GIT_PATTERN = /\bgit\s+(reset\s+--hard|clean\s+-|checkout\s+--|restore\s+--source)/i;

function normalizeProjectRoot(projectRoot) {
  return path.resolve(projectRoot);
}

function splitCommand(command) {
  const parts = [];
  let current = "";
  let quote = null;
  let escaped = false;
  for (const char of command.trim()) {
    if (escaped) {
      current += char;
      escaped = false;
      continue;
    }
    if (char === "\\") {
      escaped = true;
      continue;
    }
    if (quote) {
      if (char === quote) quote = null;
      else current += char;
      continue;
    }
    if (char === "'" || char === '"') {
      quote = char;
      continue;
    }
    if (/\s/.test(char)) {
      if (current) {
        parts.push(current);
        current = "";
      }
      continue;
    }
    current += char;
  }
  if (current) parts.push(current);
  return parts;
}

function isInsideProject(projectRoot, candidate) {
  const root = normalizeProjectRoot(projectRoot);
  const resolved = path.resolve(root, candidate);
  return resolved === root || resolved.startsWith(`${root}${path.sep}`);
}

function classifyCommand(command, config = {}, context = {}) {
  const projectRoot = normalizeProjectRoot(config.projectRoot || process.cwd());
  const approvals = new Set(context.approvedActions || []);
  const trimmed = String(command || "").trim();
  const parts = splitCommand(trimmed);
  const executable = parts[0] || "";
  const args = parts.slice(1);
  const reasons = [];
  let approvalRequired = null;

  if (!trimmed) reasons.push("Comando vacio.");
  if (CHAINING_PATTERN.test(trimmed)) reasons.push("No se permiten cadenas de shell, pipes ni multiples comandos en una sola linea.");
  if (REDIRECT_PATTERN.test(trimmed)) reasons.push("No se permiten redirecciones a rutas absolutas.");
  if (DANGEROUS_SHELL_PATTERN.test(trimmed)) reasons.push("Comando peligroso bloqueado: sudo, rm -rf o patron destructivo.");
  if (DANGEROUS_GIT_PATTERN.test(trimmed)) reasons.push("Comando git destructivo bloqueado.");
  if (ENV_FILE_PATTERN.test(trimmed)) reasons.push("Bloqueado: no puede leer ni tocar archivos .env.");
  if (/(OPENAI|ALPACA|POLYGON|TWELVE|BINANCE|DERIV|SECRET|TOKEN|PASSWORD|API_KEY)/i.test(trimmed) && /\b(env|printenv|set)\b/i.test(trimmed)) {
    reasons.push("Bloqueado: no puede listar variables de entorno ni secretos.");
  }

  const allowedCommands = new Set(config.allowedCommands || []);
  if (executable && !allowedCommands.has(executable)) {
    reasons.push(`Comando no permitido: ${executable}`);
  }

  if (executable === "npm") {
    const subcommand = args[0] || "";
    const allowedNpm = new Set(config.allowedNpmSubcommands || []);
    if (!allowedNpm.has(subcommand)) reasons.push(`Subcomando npm no permitido: ${subcommand || "(vacio)"}`);
  }

  if ((executable === "node" && args[0] === "-e") || ((executable === "python" || executable === "python3") && args[0] === "-c")) {
    reasons.push("No se permite ejecutar codigo inline con node -e o python -c; crea un script auditable dentro del proyecto.");
  }

  if (executable === "find" && args.includes("-delete")) {
    reasons.push("find -delete esta bloqueado por seguridad.");
  }

  if (executable === "git" && args[0] === "push" && !approvals.has("git-push")) {
    approvalRequired = "git-push";
    reasons.push("Git push requiere aprobacion explicita.");
  }

  if (/\b(deploy|render deploy|vercel --prod|netlify deploy --prod|firebase deploy)\b/i.test(trimmed) && !approvals.has("deploy")) {
    approvalRequired = "deploy";
    reasons.push("Deploy requiere aprobacion explicita.");
  }

  if (/\b(alpaca|broker|submit_order|place_order|market_order|buy\s+\d+|sell\s+\d+|real\s+money|live\s+trading)\b/i.test(trimmed)) {
    approvalRequired = "real-money-trading";
    reasons.push("Operaciones con dinero real estan bloqueadas.");
  }

  for (const arg of args) {
    if (arg.startsWith("/") && !isInsideProject(projectRoot, arg)) {
      reasons.push(`Ruta absoluta fuera del proyecto bloqueada: ${arg}`);
    }
    if (arg === "~" || arg.startsWith("~/")) {
      reasons.push(`Ruta de home fuera del proyecto bloqueada: ${arg}`);
    }
    if ((arg.includes("../") || arg === "..") && !isInsideProject(projectRoot, arg)) {
      reasons.push(`Ruta relativa fuera del proyecto bloqueada: ${arg}`);
    }
  }

  return {
    allowed: reasons.length === 0,
    approvalRequired,
    executable,
    args,
    reasons,
  };
}

function redactSecrets(value) {
  let output = String(value || "");
  for (const pattern of SECRET_PATTERNS) {
    output = output.replace(pattern, "[REDACTED_SECRET]");
  }
  return output;
}

module.exports = {
  classifyCommand,
  isInsideProject,
  redactSecrets,
  splitCommand,
};
