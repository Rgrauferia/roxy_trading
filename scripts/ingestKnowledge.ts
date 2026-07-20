#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const os = require("os");
const { spawnSync } = require("child_process");

const PROJECT_ROOT = path.resolve(__dirname, "..");
const KNOWLEDGE_ROOT = path.join(PROJECT_ROOT, "knowledge");
const INBOX_DIR = path.join(KNOWLEDGE_ROOT, "inbox");
const PROCESSED_DIR = path.join(KNOWLEDGE_ROOT, "processed");
const SOURCES_DIR = path.join(KNOWLEDGE_ROOT, "sources");
const SOURCE_CATALOG = path.join(SOURCES_DIR, "source-catalog.json");
const SUPPORTED_EXTENSIONS = new Set([".txt", ".md", ".pdf"]);

function ensureDirs() {
  for (const dir of [INBOX_DIR, PROCESSED_DIR, SOURCES_DIR]) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function parseArgs(argv) {
  const args = {
    dryRun: false,
    limit: 0,
    chunkSize: 1400,
    overlap: 160,
    ocrPages: 12,
  };
  for (let i = 2; i < argv.length; i += 1) {
    const item = argv[i];
    if (item === "--dry-run") args.dryRun = true;
    else if (item === "--limit") args.limit = Number(argv[++i] || "0");
    else if (item === "--chunk-size") args.chunkSize = Number(argv[++i] || "1400");
    else if (item === "--overlap") args.overlap = Number(argv[++i] || "160");
    else if (item === "--ocr-pages") args.ocrPages = Number(argv[++i] || "12");
    else if (item === "--help" || item === "-h") {
      printHelp();
      process.exit(0);
    }
  }
  args.chunkSize = Math.max(500, Math.min(5000, args.chunkSize || 1400));
  args.overlap = Math.max(0, Math.min(500, args.overlap || 0));
  args.ocrPages = Math.max(1, Math.min(50, args.ocrPages || 12));
  return args;
}

function printHelp() {
  console.log(`Knowledge Ingestion Pipeline

Uso:
  node scripts/ingestKnowledge.ts [--dry-run] [--limit 10] [--chunk-size 1400] [--ocr-pages 12]

Entrada:
  knowledge/inbox/*.txt
  knowledge/inbox/*.md
  knowledge/inbox/*.pdf

Salida:
  knowledge/processed/<documento>/fragments.json
  knowledge/processed/<documento>/manifest.json
  knowledge/processed/<documento>/failed.json si no se pudo extraer texto
`);
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function slugify(value) {
  return String(value || "document")
    .normalize("NFKD")
    .replace(/[^\w\s.-]/g, "")
    .replace(/[\s.]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase()
    .slice(0, 80) || "document";
}

function listInboxFiles() {
  ensureDirs();
  const files = [];
  const visit = (dir) => {
    for (const name of fs.readdirSync(dir)) {
      const file = path.join(dir, name);
      const stat = fs.statSync(file);
      if (stat.isDirectory()) {
        visit(file);
        continue;
      }
      if (stat.isFile() && SUPPORTED_EXTENSIONS.has(path.extname(file).toLowerCase())) {
        files.push(file);
      }
    }
  };
  visit(INBOX_DIR);
  return files.sort((a, b) => a.localeCompare(b));
}

function readCatalog() {
  if (!fs.existsSync(SOURCE_CATALOG)) return {};
  try {
    return JSON.parse(fs.readFileSync(SOURCE_CATALOG, "utf8"));
  } catch {
    return {};
  }
}

function inferTitle(filePath, text) {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === ".md") {
    const heading = String(text || "").split(/\r?\n/).find((line) => /^#\s+/.test(line.trim()));
    if (heading) return heading.replace(/^#\s+/, "").trim();
  }
  const firstNonEmpty = String(text || "").split(/\r?\n/).find((line) => line.trim().length > 8);
  if (firstNonEmpty && firstNonEmpty.length < 90 && !firstNonEmpty.includes(".")) {
    return firstNonEmpty.trim();
  }
  return path.basename(filePath, ext);
}

function inferCategory(filePath, text) {
  const relativePath = path.relative(INBOX_DIR, filePath).toLowerCase();
  const combined = `${relativePath}\n${String(text || "").slice(0, 4000)}`.toLowerCase();
  const frontMatterMatch = String(text || "").match(/(?:^|\n)category\s*:\s*([^\n]+)/i);
  if (frontMatterMatch) return frontMatterMatch[1].trim();
  if (relativePath.includes("documentos-publicos/fred")) return "datos-mercado-api";
  if (relativePath.includes("documentos-publicos/bls") || relativePath.includes("documentos-publicos/bea")) {
    return "calendario-economico";
  }
  if (relativePath.includes("documentos-publicos/sec-") || relativePath.includes("documentos-publicos/investor-") || relativePath.includes("documentos-publicos/cftc-")) {
    return "documentos-publicos";
  }
  if (/curso|course|trainingview|ict|wyckoff|smart-money|market-profile|volume-profile/.test(combined)) return "cursos";
  if (/indicador|indicator|ema|sma|vwap|rsi|macd|atr|adx|bollinger|fibonacci|ichimoku/.test(combined)) return "indicadores";
  if (/noticia|news|reuters|bloomberg|marketwatch|investing/.test(combined)) return "noticias";
  if (/diario|journal|bitacora|trade log|entrada|salida/.test(combined)) return "diario-trading";
  if (/backtest|win rate|profit factor|drawdown|sharpe/.test(combined)) return "backtesting";
  if (/estrategia|checklist|regla|setup|entrada|stop|target/.test(combined)) return "estrategias-internas";
  if (/fomc|cpi|pce|nfp|calendario|fed|inflacion|tasas/.test(combined)) return "calendario-economico";
  if (/api|quote|ohlc|market data|websocket/.test(combined)) return "datos-mercado-api";
  if (/libro|book|chapter|capitulo|isbn/.test(combined)) return "libros";
  if (/sec|federal reserve|public|official|reporte|documento/.test(combined)) return "documentos-publicos";
  return "apuntes-propios";
}

function normalizeText(text) {
  return String(text || "")
    .replace(/\r/g, "\n")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function chunkText(text, chunkSize, overlap) {
  const clean = normalizeText(text);
  if (!clean) return [];
  const paragraphs = clean.split(/\n{2,}/).map((item) => item.trim()).filter(Boolean);
  const chunks = [];
  let current = "";
  for (const paragraph of paragraphs) {
    if ((current + "\n\n" + paragraph).trim().length <= chunkSize) {
      current = (current ? `${current}\n\n${paragraph}` : paragraph).trim();
      continue;
    }
    if (current) chunks.push(current);
    if (paragraph.length <= chunkSize) {
      current = paragraph;
    } else {
      for (let start = 0; start < paragraph.length; start += Math.max(1, chunkSize - overlap)) {
        chunks.push(paragraph.slice(start, start + chunkSize).trim());
      }
      current = "";
    }
  }
  if (current) chunks.push(current);
  return chunks.filter(Boolean);
}

function commandExists(command) {
  const result = spawnSync("which", [command], { encoding: "utf8" });
  return result.status === 0;
}

function readTextFile(filePath) {
  return fs.readFileSync(filePath, "utf8");
}

function extractPdfTextWithPython(filePath) {
  const python = path.join(PROJECT_ROOT, ".venv", "bin", "python");
  const executable = fs.existsSync(python) ? python : "python3";
  const code = `
import sys
from pathlib import Path
try:
    from pypdf import PdfReader
except Exception as exc:
    print("", end="")
    raise SystemExit(0)
path = Path(sys.argv[1])
try:
    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    print("\\n\\n".join(parts))
except Exception:
    print("", end="")
`;
  const result = spawnSync(executable, ["-c", code, filePath], {
    encoding: "utf8",
    maxBuffer: 1024 * 1024 * 80,
  });
  return result.status === 0 ? result.stdout : "";
}

function extractPdfTextWithOcr(filePath, maxPages) {
  if (!commandExists("pdftoppm") || !commandExists("tesseract")) {
    return { text: "", reason: "OCR requiere pdftoppm y tesseract instalados." };
  }
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "roxy-pdf-ocr-"));
  try {
    const prefix = path.join(tempDir, "page");
    const convert = spawnSync(
      "pdftoppm",
      ["-r", "160", "-f", "1", "-l", String(maxPages), "-png", filePath, prefix],
      { encoding: "utf8", maxBuffer: 1024 * 1024 * 20 }
    );
    if (convert.status !== 0) {
      return { text: "", reason: convert.stderr || "pdftoppm no pudo convertir el PDF." };
    }
    const images = fs.readdirSync(tempDir).filter((name) => name.endsWith(".png")).sort();
    const parts = [];
    for (const image of images) {
      const result = spawnSync("tesseract", [path.join(tempDir, image), "stdout", "-l", "eng+spa"], {
        encoding: "utf8",
        maxBuffer: 1024 * 1024 * 20,
      });
      if (result.status === 0 && result.stdout.trim()) {
        parts.push(result.stdout.trim());
      }
    }
    return { text: parts.join("\n\n"), reason: parts.length ? "" : "OCR no encontro texto legible." };
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
}

function extractPdfText(filePath, ocrPages) {
  const embedded = normalizeText(extractPdfTextWithPython(filePath));
  if (embedded.length >= 80) {
    return { text: embedded, extraction: "pdf_text", failedReason: "" };
  }
  const ocr = extractPdfTextWithOcr(filePath, ocrPages);
  const ocrText = normalizeText(ocr.text);
  if (ocrText.length >= 80) {
    return { text: ocrText, extraction: "ocr", failedReason: "" };
  }
  return {
    text: embedded || ocrText,
    extraction: embedded ? "pdf_text_partial" : "failed",
    failedReason: ocr.reason || "PDF sin texto legible.",
  };
}

function loadDocument(filePath, options) {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === ".txt" || ext === ".md") {
    return { text: normalizeText(readTextFile(filePath)), extraction: "text", failedReason: "" };
  }
  if (ext === ".pdf") {
    return extractPdfText(filePath, options.ocrPages);
  }
  return { text: "", extraction: "unsupported", failedReason: `Extension no soportada: ${ext}` };
}

function removePreviousOutputsForSource(source, dryRun) {
  if (dryRun || !fs.existsSync(PROCESSED_DIR)) return;
  for (const name of fs.readdirSync(PROCESSED_DIR)) {
    const dir = path.join(PROCESSED_DIR, name);
    if (!fs.statSync(dir).isDirectory()) continue;
    const manifestPath = path.join(dir, "manifest.json");
    const failedPath = path.join(dir, "failed.json");
    for (const metadataPath of [manifestPath, failedPath]) {
      if (!fs.existsSync(metadataPath)) continue;
      try {
        const metadata = JSON.parse(fs.readFileSync(metadataPath, "utf8"));
        if (metadata.source === source || metadata.sourceFile === source) {
          fs.rmSync(dir, { recursive: true, force: true });
        }
      } catch {
        // Keep unreadable directories intact; they may have been created manually.
      }
    }
  }
}

function writeFailed(filePath, reason, extraction, dryRun) {
  const slug = slugify(path.basename(filePath, path.extname(filePath)));
  const targetDir = path.join(PROCESSED_DIR, slug);
  const source = path.relative(PROJECT_ROOT, filePath);
  const payload = {
    status: "failed",
    sourceFile: source,
    sourceHash: sha256(fs.readFileSync(filePath)),
    extraction,
    reason,
    processedAt: new Date().toISOString(),
  };
  if (!dryRun) {
    removePreviousOutputsForSource(source, dryRun);
    fs.mkdirSync(targetDir, { recursive: true });
    fs.writeFileSync(path.join(targetDir, "failed.json"), JSON.stringify(payload, null, 2));
  }
  return payload;
}

function processFile(filePath, options, catalog) {
  const loaded = loadDocument(filePath, options);
  if (!loaded.text || loaded.text.length < 80) {
    return writeFailed(filePath, loaded.failedReason || "No hay texto suficiente para fragmentar.", loaded.extraction, options.dryRun);
  }

  const title = inferTitle(filePath, loaded.text);
  const category = inferCategory(filePath, loaded.text);
  const source = path.relative(PROJECT_ROOT, filePath);
  const sourceHash = sha256(fs.readFileSync(filePath));
  const processedAt = new Date().toISOString();
  const rawChunks = chunkText(loaded.text, options.chunkSize, options.overlap);
  const documentSlug = slugify(`${path.basename(filePath, path.extname(filePath))}-${sourceHash.slice(0, 10)}`);
  const targetDir = path.join(PROCESSED_DIR, documentSlug);
  const fragments = rawChunks.map((content, idx) => ({
    id: `${documentSlug}-${String(idx + 1).padStart(4, "0")}`,
    title,
    category,
    source,
    sourceHash,
    sourceCatalogVersion: catalog.version || null,
    processedAt,
    chunkIndex: idx + 1,
    chunkCount: rawChunks.length,
    extraction: loaded.extraction,
    content,
  }));
  const manifest = {
    status: "processed",
    title,
    category,
    source,
    sourceHash,
    processedAt,
    extraction: loaded.extraction,
    chunkCount: fragments.length,
    outputDir: path.relative(PROJECT_ROOT, targetDir),
  };

  if (!options.dryRun) {
    removePreviousOutputsForSource(source, options.dryRun);
    fs.mkdirSync(targetDir, { recursive: true });
    fs.writeFileSync(path.join(targetDir, "fragments.json"), JSON.stringify(fragments, null, 2));
    fs.writeFileSync(path.join(targetDir, "manifest.json"), JSON.stringify(manifest, null, 2));
    for (const fragment of fragments) {
      fs.writeFileSync(path.join(targetDir, `${fragment.id}.json`), JSON.stringify(fragment, null, 2));
    }
  }
  return manifest;
}

function main() {
  const options = parseArgs(process.argv);
  ensureDirs();
  const catalog = readCatalog();
  const files = listInboxFiles();
  const selected = options.limit > 0 ? files.slice(0, options.limit) : files;
  const results = [];
  for (const file of selected) {
    results.push(processFile(file, options, catalog));
  }
  const summary = {
    inbox: path.relative(PROJECT_ROOT, INBOX_DIR),
    processed: path.relative(PROJECT_ROOT, PROCESSED_DIR),
    found: files.length,
    processedThisRun: results.filter((item) => item.status === "processed").length,
    failedThisRun: results.filter((item) => item.status === "failed").length,
    dryRun: options.dryRun,
    results,
  };
  console.log(JSON.stringify(summary, null, 2));
}

main();
