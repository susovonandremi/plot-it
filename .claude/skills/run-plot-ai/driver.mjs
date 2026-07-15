#!/usr/bin/env node
// PlotIt smoke driver — zero npm deps. Node 18+ (global fetch).
// Drives the RUNNING app: backend HTTP smoke + frontend screenshot.
//
//   node driver.mjs              # backend smoke + screenshot (default)
//   node driver.mjs smoke        # backend HTTP smoke only
//   node driver.mjs shot [url]   # screenshot the frontend only
//
// Env:
//   API=http://127.0.0.1:8000   backend base (default)
//   WEB=http://localhost:5173   frontend base (default; note: localhost, Vite binds ::1)
//   CHROME=<path>               chrome.exe override
//   OUT=<dir>                   screenshot output dir (default: ./scratch next to skill)

import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const API = process.env.API || 'http://127.0.0.1:8000';
const WEB = process.env.WEB || 'http://localhost:5173';
const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = process.env.OUT || join(HERE, 'scratch');

const CHROME_CANDIDATES = [
  process.env.CHROME,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
].filter(Boolean);

const ok = (m) => console.log(`  ✓ ${m}`);
const die = (m) => { console.error(`  ✗ ${m}`); process.exit(1); };

async function getJson(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(`HTTP ${r.status} for ${url}`);
  return r.json();
}

async function smoke() {
  console.log(`Backend smoke @ ${API}`);

  const health = await getJson(`${API}/health`).catch((e) => die(`/health unreachable: ${e.message} (is uvicorn running?)`));
  if (health.status?.includes('running')) ok(`/health -> v${health.version}, ${health.features.length} features`);
  else die(`/health unexpected: ${JSON.stringify(health)}`);

  const styles = await getJson(`${API}/api/v1/styles`);
  if (styles.success && Array.isArray(styles.data)) ok(`/styles -> ${styles.data.length} presets`);
  else die(`/styles bad shape`);

  // /generate is the hot path: structured input, no LLM key needed.
  const gen = await getJson(`${API}/api/v1/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      plot_size_sqft: 1200, floors: 1,
      rooms: [
        { type: 'bedroom', count: 2 }, { type: 'kitchen', count: 1 },
        { type: 'bathroom', count: 1 }, { type: 'living', count: 1 },
      ],
      prompt: '1200 sqft 2BHK house facing north',
    }),
  }).catch((e) => die(`/generate failed: ${e.message}`));
  const d = gen.data || {};
  if (gen.success && d.rooms_placed > 0) {
    ok(`/generate -> engine=${d.engine}, rooms=${d.rooms_placed}, floors=${d.floors_generated}, score=${d.blueprint_score?.overall}`);
  } else die(`/generate returned success=${gen.success} data=${JSON.stringify(d).slice(0, 200)}`);

  // /parse needs GROQ_API_KEY; keyless it degrades to consultation mode (still HTTP 200).
  const parse = await getJson(`${API}/api/v1/parse`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: 'Generate a 3BHK 1200 sqft east-facing house' }),
  });
  if (parse.success) {
    const needs = parse.data?.consultation?.needed;
    ok(`/parse -> success (consultation.needed=${needs}${needs ? ', GROQ key absent = expected' : ''})`);
  } else die(`/parse failed`);

  console.log('Backend smoke PASSED\n');
}

function findChrome() {
  for (const c of CHROME_CANDIDATES) if (existsSync(c)) return c;
  return null;
}

function shot(url = WEB) {
  console.log(`Screenshot @ ${url}`);
  const chrome = findChrome();
  if (!chrome) die(`no Chrome/Edge found. Set CHROME=<path>. Tried:\n    ${CHROME_CANDIDATES.join('\n    ')}`);
  if (!existsSync(OUT)) mkdirSync(OUT, { recursive: true });
  const png = join(OUT, 'plotai-home.png');
  execFileSync(chrome, [
    '--headless', '--disable-gpu', '--hide-scrollbars',
    '--window-size=1440,900', `--screenshot=${png}`,
    '--virtual-time-budget=5000', url,
  ], { stdio: 'ignore' });
  if (!existsSync(png)) die('screenshot not produced');
  ok(`wrote ${png}`);
  console.log('Open that PNG to confirm the SPA rendered (dark CAD UI, "NO BLUEPRINT LOADED").\n');
}

const cmd = process.argv[2] || 'all';
if (cmd === 'smoke') await smoke();
else if (cmd === 'shot') shot(process.argv[3]);
else { await smoke(); shot(); }
