/**
 * convert-projects.mjs
 * Converts the Berkeley Carbon Trading Project CSV into a two-tier JSON
 * suitable for the Project Comparison feature.
 *
 * Usage: node scripts/convert-projects.mjs
 *
 * Input:  frontend/data/Voluntary-Registry-Offsets-Database--v*.csv (most recent)
 *         The CSV is gitignored — download the current release from the
 *         Berkeley Carbon Trading Project and drop it in frontend/data/.
 * Output:
 *   public/data/projects-summary.json  — lightweight (no _detail, developer promoted)
 *   public/data/projects-detail.json   — { id: _detail } map for lazy loading
 */

import { readFileSync, writeFileSync, readdirSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { derivePrimaryCertification } from '../src/lib/certificationRules.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const DATA_DIR = join(ROOT, 'data');
const OUTPUT_SUMMARY = join(ROOT, 'public', 'data', 'projects-summary.json');
const OUTPUT_DETAIL = join(ROOT, 'public', 'data', 'projects-detail.json');

// ---------------------------------------------------------------------------
// 1. Find the most recent CSV in data/
// ---------------------------------------------------------------------------
const csvFiles = readdirSync(DATA_DIR)
  .filter(f => f.startsWith('Voluntary-Registry-Offsets-Database') && f.endsWith('.csv'))
  .sort();

if (csvFiles.length === 0) {
  console.error(
    'No Berkeley CSV found in frontend/data/.\n' +
    'Download the latest "Voluntary Registry Offsets Database" release and save it there as\n' +
    '  frontend/data/Voluntary-Registry-Offsets-Database--vYYYY-MM.csv'
  );
  process.exit(1);
}

const csvFileName = csvFiles[csvFiles.length - 1];
const csvPath = join(DATA_DIR, csvFileName);
console.log(`Reading: ${csvFileName}`);

// Extract version from filename (e.g., "v2025-10" from "...--v2025-10.csv")
const versionMatch = csvFileName.match(/v(\d{4}-\d{2})/);
const version = versionMatch ? `v${versionMatch[1]}` : 'unknown';
const lastUpdated = versionMatch ? versionMatch[1] : new Date().toISOString().slice(0, 10);

// ---------------------------------------------------------------------------
// 2. Parse CSV (handles quoted fields with commas and newlines)
// ---------------------------------------------------------------------------
function parseCSV(text) {
  const rows = [];
  let current = '';
  let inQuotes = false;
  const lines = text.split('\n');

  for (const line of lines) {
    if (inQuotes) {
      current += '\n' + line;
    } else {
      current = line;
    }

    // Count unescaped quotes
    const quoteCount = (current.match(/"/g) || []).length;
    inQuotes = quoteCount % 2 !== 0;

    if (!inQuotes) {
      rows.push(parseCSVRow(current));
      current = '';
    }
  }

  return rows;
}

function parseCSVRow(row) {
  const fields = [];
  let field = '';
  let inQuotes = false;

  for (let i = 0; i < row.length; i++) {
    const char = row[i];

    if (inQuotes) {
      if (char === '"') {
        if (i + 1 < row.length && row[i + 1] === '"') {
          field += '"';
          i++; // skip escaped quote
        } else {
          inQuotes = false;
        }
      } else {
        field += char;
      }
    } else {
      if (char === '"') {
        inQuotes = true;
      } else if (char === ',') {
        fields.push(field.trim());
        field = '';
      } else if (char === '\r') {
        // skip carriage returns
      } else {
        field += char;
      }
    }
  }
  fields.push(field.trim());
  return fields;
}

// ---------------------------------------------------------------------------
// 3. Convert rows to two-tier JSON structure
// ---------------------------------------------------------------------------
function parseNumber(val) {
  if (!val || val === 'Not Specified' || val === '') return 0;
  const num = Number(val.replace(/,/g, ''));
  return isNaN(num) ? 0 : num;
}

function cleanString(val) {
  if (!val || val === 'Not Specified') return '';
  return val.trim();
}

const raw = readFileSync(csvPath, 'utf-8').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
const rows = parseCSV(raw);
const headers = rows[0];

console.log(`Parsed ${rows.length - 1} data rows, ${headers.length} columns`);

// Map column indices by header name (normalize newlines to single spaces)
const col = {};
headers.forEach((h, i) => { col[h.replace(/\s*\n\s*/g, ' ').trim()] = i; });

// ---------------------------------------------------------------------------
// 3a. Locate the four year-column blocks
//
// The workbook repeats the year headers (1996…) four times, so they CANNOT be
// looked up by name — `col` only keeps the last occurrence of each. Instead we
// detect runs of consecutive year headers positionally, which also survives
// Berkeley appending a new year each release.
//
// Expected order: issued-by-vintage, retired-by-vintage, remaining-by-vintage,
// issued-by-issuance-year. That order is asserted below, not assumed.
// ---------------------------------------------------------------------------
// The first three blocks are adjacent with no separating header, so a plain
// "run of year columns" scan merges them. Start a new block whenever the year
// sequence restarts (i.e. does not continue from the previous column).
const yearRuns = [];
let prev = null;
for (let i = 0; i < headers.length; i++) {
  const h = headers[i].trim();
  if (!/^(19|20)\d{2}$/.test(h)) { prev = null; continue; }
  const year = Number(h);
  if (prev === null || year !== prev + 1) {
    yearRuns.push({ start: i, years: [] });
  }
  yearRuns[yearRuns.length - 1].years.push(year);
  prev = year;
}

if (yearRuns.length !== 4) {
  throw new Error(
    `Expected 4 blocks of year columns in the Berkeley CSV, found ${yearRuns.length}. ` +
    `The workbook layout has changed — re-check the column mapping before trusting the output.`
  );
}

const [issuedByVintage, retiredByVintage, remainingByVintage, issuedByYear] = yearRuns;

/** Sum one year block for a row. */
function sumBlock(row, block) {
  let total = 0;
  for (let i = 0; i < block.years.length; i++) total += parseNumber(row[block.start + i]);
  return total;
}

/** Sparse { year: credits } map, omitting zero years to keep the payload small. */
function yearMap(row, block) {
  const out = {};
  for (let i = 0; i < block.years.length; i++) {
    const v = parseNumber(row[block.start + i]);
    if (v !== 0) out[block.years[i]] = v;
  }
  return out;
}

const projects = [];
// Block-identity check: each block must reconcile against its total column.
const blockMismatch = { issued: 0, retired: 0, remaining: 0, issuanceYear: 0 };
let reconciled = 0;

for (let r = 1; r < rows.length; r++) {
  const row = rows[r];
  if (!row || row.length < 5 || !row[col['Project ID']]) continue;

  const get = (name) => {
    if (!(name in col)) throw new Error(`Column not found in CSV header: "${name}"`);
    return row[col[name]] || '';
  };

  const totalIssued = parseNumber(get('Total Credits Issued'));
  const totalRetired = parseNumber(get('Total Credits Retired'));
  const totalRemaining = parseNumber(get('Total Credits Remaining'));

  // Verify each block means what we think it means (see 3a).
  reconciled++;
  if (sumBlock(row, issuedByVintage) !== totalIssued) blockMismatch.issued++;
  if (sumBlock(row, retiredByVintage) !== totalRetired) blockMismatch.retired++;
  if (sumBlock(row, remainingByVintage) !== totalRemaining) blockMismatch.remaining++;
  if (sumBlock(row, issuedByYear) !== totalIssued) blockMismatch.issuanceYear++;

  // Issuance activity. `neverIssued` is not stored — it is exactly
  // creditsIssued === 0, which the summary already carries.
  const issuance = yearMap(row, issuedByYear);
  const activeYears = Object.keys(issuance).map(Number).sort((a, b) => a - b);
  const lastIssuanceYear = activeYears.length ? activeYears[activeYears.length - 1] : undefined;
  // A gap means the project skipped one or more years mid-life.
  const span = activeYears.length
    ? activeYears[activeYears.length - 1] - activeYears[0] + 1
    : 0;
  const hasIssuanceGap = activeYears.length > 1 && span > activeYears.length ? true : undefined;

  const rawCertifications = cleanString(get('Certifications'));

  projects.push({
    id: cleanString(get('Project ID')),
    name: cleanString(get('Project Name')),
    registry: cleanString(get('Voluntary Registry')),
    status: cleanString(get('Voluntary Status')),
    scope: cleanString(get('Scope')),
    type: cleanString(get('Type')),
    reductionRemoval: cleanString(get('Reduction / Removal')),
    country: cleanString(get('Country')),
    region: cleanString(get('Region')),
    creditsIssued: totalIssued,
    creditsRetired: totalRetired,
    creditsRemaining: totalRemaining,
    // Stored as a year, not a derived "stalled" boolean — a boolean baked at
    // build time would silently rot as the release ages. The UI compares it
    // against the current year instead.
    lastIssuanceYear,
    hasIssuanceGap,
    certification: derivePrimaryCertification(rawCertifications),
    _detail: {
      issuedByYear: issuance,
      methodology: cleanString(get('Methodology / Protocol')),
      methodologyVersion: cleanString(get('Methodology Version')),
      state: cleanString(get('State')),
      siteLocation: cleanString(get('Project Site Location')),
      developer: cleanString(get('Project Developer')),
      owner: cleanString(get('Project Owner')),
      operator: cleanString(get('Offset Project Operator')),
      designee: cleanString(get('Authorized Project Designee')),
      verifier: cleanString(get('Verifier')),
      bufferPool: parseNumber(get('Total Buffer Pool Deposits')),
      annualReductions: parseNumber(get('Estimated Annual Emission Reductions')),
      pers: parseNumber(get('PERs')),
      arbWaProject: cleanString(get('ARB / WA Project')),
      arbWaStatus: cleanString(get('ARB / WA Status')),
      arbWaId: cleanString(get('ARB / WA ID')),
      registryArbWa: cleanString(get('Registry / ARB / WA')),
      poaId: cleanString(get('PoA / Aggregate ID')),
      poaStatus: cleanString(get('PoA / VPA Status')),
      listed: cleanString(get('Project Listed')),
      registered: cleanString(get('Project Registered')),
      firstIssuanceYear: cleanString(get('1st issuance yr (no hard code, hide)')),
      certifications: rawCertifications,
      registryType: cleanString(get('Project Type From the Registry')),
      registryDocs: cleanString(get('Registry Documents')),
      projectWebsite: cleanString(get('Project Website')),
      description: cleanString(get('Project Description')),
      registryNotes: cleanString(get('Notes from Registry')),
      berkeleyNotes: cleanString(get('Notes from Berkeley Carbon Trading Project')),
    },
  });
}

// ---------------------------------------------------------------------------
// 4. Write output
// ---------------------------------------------------------------------------
// Strip empty strings and zero values from _detail to reduce file size
function compactDetail(detail) {
  const compact = {};
  for (const [k, v] of Object.entries(detail)) {
    if (v === '' || v === 0 || v === undefined) continue;
    if (typeof v === 'object' && Object.keys(v).length === 0) continue;
    compact[k] = v;
  }
  return compact;
}

// ---------------------------------------------------------------------------
// Fail loudly if a year block no longer reconciles with its total column.
// A few rows legitimately disagree in Berkeley's own data, so allow 1%.
// ---------------------------------------------------------------------------
const TOLERANCE = 0.01;
for (const [name, count] of Object.entries(blockMismatch)) {
  const rate = count / reconciled;
  if (rate > TOLERANCE) {
    throw new Error(
      `Year block "${name}" failed to reconcile for ${count}/${reconciled} rows ` +
      `(${(rate * 100).toFixed(1)}%). The four year blocks may have been reordered ` +
      `in this release — verify before publishing charts built on them.`
    );
  }
  if (count > 0) console.log(`  note: "${name}" block differs from its total on ${count} row(s)`);
}

const compactProjects = projects.map(p => {
  const compact = { ...p, _detail: compactDetail(p._detail) };
  // Also strip empty top-level strings (keep 0 for credits since those are meaningful)
  for (const key of ['scope', 'region', 'reductionRemoval']) {
    if (compact[key] === '') delete compact[key];
  }
  return compact;
});

// --- Summary file: top-level fields only, developer promoted ---
const summaryProjects = compactProjects.map(p => {
  const { _detail, ...topLevel } = p;
  const summary = { ...topLevel };
  // Promote developer to top-level for search without needing _detail
  if (_detail.developer) summary.developer = _detail.developer;
  // Strip empty developer
  if (summary.developer === '') delete summary.developer;
  return summary;
});

const summaryOutput = {
  lastUpdated,
  version,
  totalCount: summaryProjects.length,
  projects: summaryProjects,
};

// --- Detail file: id → _detail map ---
const detailMap = {};
for (const p of compactProjects) {
  if (Object.keys(p._detail).length > 0) {
    detailMap[p.id] = p._detail;
  }
}

// Ensure output directory exists
const outputDir = dirname(OUTPUT_SUMMARY);
mkdirSync(outputDir, { recursive: true });

// Write summary
const summaryJson = JSON.stringify(summaryOutput);
writeFileSync(OUTPUT_SUMMARY, summaryJson);
const summaryMB = (Buffer.byteLength(summaryJson) / (1024 * 1024)).toFixed(2);
console.log(`Wrote ${summaryProjects.length} projects to public/data/projects-summary.json (${summaryMB} MB)`);

// Write detail map
const detailJson = JSON.stringify(detailMap);
writeFileSync(OUTPUT_DETAIL, detailJson);
const detailMB = (Buffer.byteLength(detailJson) / (1024 * 1024)).toFixed(2);
console.log(`Wrote ${Object.keys(detailMap).length} entries to public/data/projects-detail.json (${detailMB} MB)`);

// Write version constant for frontend cache-busting
const VERSION_FILE = join(ROOT, 'src', 'generated', 'projectVersion.ts');
mkdirSync(dirname(VERSION_FILE), { recursive: true });
writeFileSync(VERSION_FILE,
  `// Auto-generated by scripts/convert-projects.mjs — DO NOT EDIT\n` +
  `export const PROJECT_DATA_VERSION = '${version}';\n`
);
console.log(`Wrote version ${version} to src/generated/projectVersion.ts`);

// Independent data pipelines:
//   - Project data:     run this script (convert-projects.mjs)
//   - Document sources: run scripts/convert-csv-to-json.mjs separately
