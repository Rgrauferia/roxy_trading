#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const PROJECT_ROOT = path.resolve(__dirname, "..");
const TARGET_DIR = path.join(PROJECT_ROOT, "knowledge", "inbox", "documentos-publicos");
const SOURCES_LOG = path.join(PROJECT_ROOT, "knowledge", "sources", "public-downloads-log.json");

const SOURCES = [
  {
    id: "gutenberg-reminiscences-stock-operator",
    title: "Reminiscences of a Stock Operator",
    category: "libros",
    license: "Project Gutenberg public domain/terms",
    url: "https://www.gutenberg.org/cache/epub/60979/pg60979.txt",
    type: "text",
  },
  {
    id: "gutenberg-psychology-stock-market",
    title: "Psychology of the Stock Market",
    category: "libros",
    license: "Project Gutenberg public domain/terms",
    url: "https://www.gutenberg.org/cache/epub/75570/pg75570.txt",
    type: "text",
  },
  {
    id: "gutenberg-psychology-speculation",
    title: "The Psychology of Speculation",
    category: "libros",
    license: "Project Gutenberg public domain/terms",
    url: "https://www.gutenberg.org/cache/epub/73647/pg73647.txt",
    type: "text",
  },
  {
    id: "gutenberg-profitable-stock-exchange-investments",
    title: "Profitable Stock Exchange Investments",
    category: "libros",
    license: "Project Gutenberg public domain/terms",
    url: "https://www.gutenberg.org/cache/epub/44052/pg44052.txt",
    type: "text",
  },
  {
    id: "gutenberg-successful-speculation",
    title: "Successful Speculation",
    category: "libros",
    license: "Project Gutenberg public domain/terms",
    url: "https://www.gutenberg.org/files/26841/26841-0.txt",
    fallbackUrl: "https://www.gutenberg.org/files/26841/26841.txt",
    type: "text",
  },
  {
    id: "gutenberg-theory-stock-exchange-speculation",
    title: "The Theory of Stock Exchange Speculation",
    category: "libros",
    license: "Project Gutenberg public domain/terms",
    url: "https://www.gutenberg.org/cache/epub/59518/pg59518.txt",
    type: "text",
  },
  {
    id: "gutenberg-stock-exchange-from-within",
    title: "The Stock Exchange from Within",
    category: "libros",
    license: "Project Gutenberg public domain/terms",
    url: "https://www.gutenberg.org/cache/epub/60082/pg60082.txt",
    type: "text",
  },
  {
    id: "gutenberg-fifty-years-wall-street",
    title: "Fifty Years in Wall Street",
    category: "libros",
    license: "Project Gutenberg public domain/terms",
    url: "https://www.gutenberg.org/cache/epub/70377/pg70377.txt",
    type: "text",
  },
  {
    id: "gutenberg-the-stock-exchange",
    title: "The Stock Exchange",
    category: "libros",
    license: "Project Gutenberg public domain/terms",
    url: "https://www.gutenberg.org/cache/epub/59042/pg59042.txt",
    type: "text",
  },
  {
    id: "archive-studies-tape-reading",
    title: "Studies in Tape Reading",
    category: "libros",
    license: "Public domain historical source where available from Internet Archive",
    url: "https://archive.org/stream/studiesintaperea00wyckrich/studiesintaperea00wyckrich_djvu.txt",
    type: "text",
  },
  {
    id: "investor-gov-stocks",
    title: "Investor.gov - Stocks",
    category: "documentos-publicos",
    license: "U.S. SEC/Investor.gov public investor education",
    url: "https://www.investor.gov/introduction-investing/investing-basics/investment-products/stocks",
    type: "html",
  },
  {
    id: "investor-gov-bonds",
    title: "Investor.gov - Bonds",
    category: "documentos-publicos",
    license: "U.S. SEC/Investor.gov public investor education",
    url: "https://www.investor.gov/introduction-investing/investing-basics/investment-products/bonds-or-fixed-income-products/bonds",
    type: "html",
  },
  {
    id: "investor-gov-mutual-funds-etfs",
    title: "Investor.gov - Mutual Funds and ETFs",
    category: "documentos-publicos",
    license: "U.S. SEC/Investor.gov public investor education",
    url: "https://www.investor.gov/introduction-investing/investing-basics/investment-products/mutual-funds-and-exchange-traded-funds-etfs/mutual-funds",
    type: "html",
  },
  {
    id: "investor-gov-options",
    title: "Investor.gov - Options Glossary",
    category: "documentos-publicos",
    license: "U.S. SEC/Investor.gov public investor education",
    url: "https://www.investor.gov/introduction-investing/investing-basics/glossary/options",
    type: "html",
  },
  {
    id: "sec-introduction-options",
    title: "SEC Investor Bulletin - An Introduction to Options",
    category: "documentos-publicos",
    license: "U.S. SEC public investor education",
    url: "https://www.sec.gov/resources-for-investors/investor-alerts-bulletins/ib_introductionoptions",
    type: "html",
  },
  {
    id: "sec-etf-bulletin",
    title: "SEC Investor Bulletin - Exchange-Traded Funds",
    category: "documentos-publicos",
    license: "U.S. SEC public investor education PDF",
    url: "https://www.sec.gov/investor/alerts/etfs.pdf",
    type: "pdf",
  },
  {
    id: "investor-gov-glossary",
    title: "Investor.gov - Glossary",
    category: "documentos-publicos",
    license: "U.S. SEC/Investor.gov public investor education",
    url: "https://www.investor.gov/introduction-investing/investing-basics/glossary/all",
    type: "html",
  },
  {
    id: "sec-guide-saving-investing",
    title: "SEC Guide to Saving and Investing",
    category: "documentos-publicos",
    license: "U.S. SEC public investor education PDF",
    url: "https://www.sec.gov/investor/pubs/sec-guide-to-savings-and-investing.pdf",
    type: "pdf",
  },
  {
    id: "cftc-learn-protect",
    title: "CFTC Learn and Protect",
    category: "documentos-publicos",
    license: "U.S. CFTC public education",
    url: "https://www.cftc.gov/LearnAndProtect/index.htm",
    type: "html",
  },
  {
    id: "cftc-glossary",
    title: "CFTC Glossary",
    category: "documentos-publicos",
    license: "U.S. CFTC public education",
    url: "https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/CFTCGlossary/index.htm",
    type: "html",
  },
  {
    id: "fred-api-docs",
    title: "FRED API Documentation",
    category: "datos-mercado-api",
    license: "Federal Reserve Bank of St. Louis public API documentation",
    url: "https://fred.stlouisfed.org/docs/api/fred/",
    type: "html",
  },
  {
    id: "bls-api-docs",
    title: "BLS Public Data API",
    category: "calendario-economico",
    license: "U.S. Bureau of Labor Statistics public API documentation",
    url: "https://www.bls.gov/developers/",
    type: "html",
  },
  {
    id: "bls-api-features",
    title: "BLS API Features",
    category: "calendario-economico",
    license: "U.S. Bureau of Labor Statistics public API documentation",
    url: "https://www.bls.gov/bls/api_features.htm",
    type: "html",
  },
  {
    id: "bea-api-docs",
    title: "BEA API Documentation",
    category: "calendario-economico",
    license: "U.S. Bureau of Economic Analysis public API documentation",
    url: "https://apps.bea.gov/api/signup/",
    type: "html",
  },
];

function ensureDirs() {
  fs.mkdirSync(TARGET_DIR, { recursive: true });
}

function decodeHtmlEntities(value) {
  return String(value || "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(Number(code)))
    .replace(/&#x([0-9a-f]+);/gi, (_, code) => String.fromCharCode(parseInt(code, 16)));
}

function htmlToText(html) {
  return decodeHtmlEntities(
    String(html || "")
      .replace(/<script[\s\S]*?<\/script>/gi, " ")
      .replace(/<style[\s\S]*?<\/style>/gi, " ")
      .replace(/<noscript[\s\S]*?<\/noscript>/gi, " ")
      .replace(/<header[\s\S]*?<\/header>/gi, " ")
      .replace(/<footer[\s\S]*?<\/footer>/gi, " ")
      .replace(/<nav[\s\S]*?<\/nav>/gi, " ")
      .replace(/<\/(p|div|section|article|li|h1|h2|h3|h4|tr)>/gi, "\n")
      .replace(/<[^>]+>/g, " ")
      .replace(/[ \t]+/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim()
  );
}

function markdownEnvelope(source, body) {
  return [
    `# ${source.title}`,
    "",
    `category: ${source.category}`,
    `source: ${source.url}`,
    `license: ${source.license}`,
    `downloadedAt: ${new Date().toISOString()}`,
    "",
    body.trim(),
    "",
  ].join("\n");
}

async function fetchSource(source) {
  const urls = [source.url, source.fallbackUrl].filter(Boolean);
  let lastError = null;
  for (const url of urls) {
    try {
      const response = await fetch(url, {
        redirect: "follow",
        headers: {
          "User-Agent": "RoxyKnowledgeIngest/1.0 legal-public-sources",
        },
      });
      if (!response.ok) {
        lastError = new Error(`HTTP ${response.status}`);
        continue;
      }
      if (source.type === "pdf") {
        return { url, buffer: Buffer.from(await response.arrayBuffer()) };
      }
      const text = await response.text();
      return { url, text };
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error("No URL available");
}

async function downloadOne(source) {
  const downloaded = await fetchSource(source);
  const ext = source.type === "pdf" ? "pdf" : "md";
  const filePath = path.join(TARGET_DIR, `${source.id}.${ext}`);
  if (source.type === "pdf") {
    fs.writeFileSync(filePath, downloaded.buffer);
  } else {
    const raw = source.type === "html" ? htmlToText(downloaded.text) : downloaded.text;
    fs.writeFileSync(filePath, markdownEnvelope({ ...source, url: downloaded.url }, raw), "utf8");
  }
  return {
    id: source.id,
    title: source.title,
    category: source.category,
    url: downloaded.url,
    file: path.relative(PROJECT_ROOT, filePath),
    bytes: fs.statSync(filePath).size,
    status: "downloaded",
  };
}

async function main() {
  ensureDirs();
  const results = [];
  for (const source of SOURCES) {
    try {
      const result = await downloadOne(source);
      results.push(result);
      console.log(`downloaded ${result.id} -> ${result.file}`);
    } catch (error) {
      results.push({
        id: source.id,
        title: source.title,
        category: source.category,
        url: source.url,
        status: "failed",
        reason: error.message,
      });
      console.error(`failed ${source.id}: ${error.message}`);
    }
  }
  const summary = {
    downloadedAt: new Date().toISOString(),
    targetDir: path.relative(PROJECT_ROOT, TARGET_DIR),
    downloaded: results.filter((item) => item.status === "downloaded").length,
    failed: results.filter((item) => item.status === "failed").length,
    results,
  };
  fs.writeFileSync(SOURCES_LOG, JSON.stringify(summary, null, 2));
  console.log(JSON.stringify(summary, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
