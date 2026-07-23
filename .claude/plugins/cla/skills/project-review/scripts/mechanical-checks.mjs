#!/usr/bin/env node
// Deterministic static checks for /review-project (agentic-air monorepo).
//
// This script owns the checks that are (a) genuinely deterministic and (b)
// NOT already covered by `pnpm -r run build|lint|test`. Build/lint/test are
// run by the skill workflow directly (they are already exit-code checks, and
// the workspace test run already covers e.g. apps/operator's own
// i18n keyParity test and the engine invariants) -- this script does the
// fast (<1s) cross-file static analysis the model otherwise hand-greps
// inconsistently: shared-i18n parity/usage, daypart-key consistency, the
// monorepo package-boundary invariants, and smoke-script string drift.
//
// Usage:
//   node .claude/plugins/cla/skills/project-review/scripts/mechanical-checks.mjs          # human table
//   node .claude/plugins/cla/skills/project-review/scripts/mechanical-checks.mjs --json   # machine-readable
//
// Exit code is always 0 -- FAIL rows are data for the review, not a CI gate.

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

// Repo root, resolved location-independently (via git) so this keeps working
// regardless of how deep the plugin nests -- it lives at
// .claude/plugins/cla/skills/project-review/scripts/ today, but the checks only
// ever want the repo root, never a path relative to this file. This mirrors the
// git-based `_repo_root()` the sibling Python scripts use. If git is somehow
// unavailable, fall back to a fixed walk up from this file: scripts/ ->
// project-review/ -> skills/ -> cla/ -> plugins/ -> .claude/ -> repo root (6 up).
// fileURLToPath (not raw .pathname) so a repo path containing spaces works.
const HERE = fileURLToPath(new URL('.', import.meta.url));
function resolveRoot() {
  try {
    return execSync('git rev-parse --show-toplevel', { cwd: HERE, encoding: 'utf8' }).trim();
  } catch {
    return fileURLToPath(new URL('../../../../../../', import.meta.url));
  }
}
const ROOT = resolveRoot();
const r = (...p) => join(ROOT, ...p);

const SHARED_EN = r('packages/design-system/src/i18n/en.json');
const SHARED_RO = r('packages/design-system/src/i18n/ro.json');
const MEDIA_DOMAIN = r('packages/media-schema/src/media-domain.ts');
const DAYPARTS_JSON = r('apps/funnel-demo/public/data/dayparts.json');
// t()-usage + boundary scans read these source trees.
const FUNNEL_SRC = ['apps/funnel-demo/src', 'packages/design-system/src'];

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

/** Recursively collect .ts/.tsx/.mjs files under a dir, skipping build/dep dirs. */
function walk(dir, exts = ['.ts', '.tsx']) {
  const out = [];
  let entries;
  try {
    entries = readdirSync(dir);
  } catch (err) {
    // A genuinely-absent optional dir (ENOENT) is fine — return no files. But a
    // real failure (permissions, I/O, a renamed/moved path) must surface: if it
    // were swallowed here, a walk-based check would scan zero files and PASS
    // vacuously, which for a trustworthiness tool is worse than a FAIL.
    if (err.code === 'ENOENT') return out;
    throw err;
  }
  for (const name of entries) {
    if (name === 'node_modules' || name === 'dist' || name === '.git') continue;
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) out.push(...walk(full, exts));
    else if (exts.includes(extname(name))) out.push(full);
  }
  return out;
}

function truncate(list, n = 8) {
  const arr = [...list];
  if (arr.length <= n) return arr.join(', ');
  return `${arr.slice(0, n).join(', ')} … (+${arr.length - n} more)`;
}

// ── Check 1: shared-i18n key parity (design-system en ↔ ro) ──────────────────
// apps/operator's own en/ro parity is already guarded by
// apps/operator/src/i18n/keyParity.test.ts (runs under `pnpm test`), so this
// only covers the shared layer, which has no such test.
function checkSharedI18nParity() {
  const en = new Set(Object.keys(readJson(SHARED_EN)));
  const ro = new Set(Object.keys(readJson(SHARED_RO)));
  const enOnly = [...en].filter((k) => !ro.has(k));
  const roOnly = [...ro].filter((k) => !en.has(k));
  if (enOnly.length === 0 && roOnly.length === 0) {
    return { status: 'PASS', details: `en/ro key sets match (${en.size} keys)` };
  }
  const parts = [];
  if (enOnly.length) parts.push(`en-only: [${truncate(enOnly)}]`);
  if (roOnly.length) parts.push(`ro-only: [${truncate(roOnly)}]`);
  return { status: 'FAIL', details: parts.join('; ') };
}

// ── Check 2: shared-i18n usage coverage ──────────────────────────────────────
// Every STATIC t('key') literal in the funnel-demo + design-system source must
// resolve in both shared JSON files. Dynamically-built keys (t(variable)) are
// not resolvable statically and are silently skipped -- a known limitation.
function checkSharedI18nUsage() {
  const en = new Set(Object.keys(readJson(SHARED_EN)));
  const ro = new Set(Object.keys(readJson(SHARED_RO)));
  const callRe = /\bt\(\s*['"]([^'"]+)['"]/g;
  const missing = new Set();
  const files = FUNNEL_SRC.flatMap((base) => walk(r(base)));
  // Guard against a vacuous PASS: if the scan found nothing, the base paths are
  // wrong (or empty), not "every key resolves".
  if (files.length === 0) return { status: 'FAIL', details: `scanned 0 source files — check paths ${FUNNEL_SRC.join(', ')}` };
  for (const file of files) {
    const src = readFileSync(file, 'utf8');
    let m;
    while ((m = callRe.exec(src)) !== null) {
      const key = m[1];
      // Skip dynamically-composed keys, e.g. t('dashboard.genre.' + g):
      // a trailing '.' or a '+' right after the closing quote means this
      // is a prefix being concatenated, not a complete key.
      const after = src.slice(callRe.lastIndex).trimStart();
      if (key.endsWith('.') || after.startsWith('+')) continue;
      if (!en.has(key) || !ro.has(key)) missing.add(key);
    }
  }
  if (missing.size === 0) return { status: 'PASS', details: 'all static t() keys resolve in both locales' };
  return { status: 'FAIL', details: `unresolved: [${truncate(missing)}]` };
}

// ── Check 3: daypart key consistency ─────────────────────────────────────────
// DAYPARTS (media-domain.ts) and dayparts.json keys must each have a
// dashboard.dayparts.<key> entry in both shared locales.
function checkDaypartKeys() {
  const domainSrc = readFileSync(MEDIA_DOMAIN, 'utf8');
  const arrMatch = domainSrc.match(/DAYPARTS\s*:\s*DaypartKey\[\]\s*=\s*\[([^\]]+)\]/);
  if (!arrMatch) return { status: 'FAIL', details: 'could not parse DAYPARTS from media-domain.ts (structure changed?)' };
  const domainKeys = [...arrMatch[1].matchAll(/'([^']+)'|"([^"]+)"/g)].map((m) => m[1] ?? m[2]);
  // dayparts.json is an array of { key, display_order, ... } cells.
  const dataKeys = readJson(DAYPARTS_JSON).map((d) => d.key);
  const en = readJson(SHARED_EN);
  const ro = readJson(SHARED_RO);
  const all = new Set([...domainKeys, ...dataKeys]);
  const problems = [];
  // domain vs dataset symmetric diff
  const dataSet = new Set(dataKeys);
  const domSet = new Set(domainKeys);
  for (const k of all) {
    if (!domSet.has(k)) problems.push(`${k}: in dayparts.json but not DAYPARTS`);
    else if (!dataSet.has(k)) problems.push(`${k}: in DAYPARTS but not dayparts.json`);
    const i18nKey = `dashboard.dayparts.${k}`;
    if (!(i18nKey in en)) problems.push(`${i18nKey} missing from en.json`);
    if (!(i18nKey in ro)) problems.push(`${i18nKey} missing from ro.json`);
  }
  if (problems.length === 0) {
    return { status: 'PASS', details: `DAYPARTS = dayparts.json = both locales (${domainKeys.length}: ${domainKeys.join('/')})` };
  }
  return { status: 'FAIL', details: truncate(problems) };
}

// ── Check 4: monorepo package boundaries ─────────────────────────────────────
// The core invariant of the workspace (openspec/specs/architecture): media-schema
// stays Node-safe (no React/DOM -- it is imported by the chat-server backend);
// engine depends only on media-schema among workspace packages; neither app
// imports the other's source.
function checkPackageBoundaries() {
  const violations = [];
  const importRe = /\bfrom\s+['"]([^'"]+)['"]/g;
  // Guard against a vacuous PASS: the two package dirs whose boundaries this
  // check exists to enforce must actually contain source. Zero files means a
  // wrong/renamed path, not "boundaries clean".
  if (walk(r('packages/media-schema/src')).length === 0 || walk(r('packages/engine/src')).length === 0) {
    return { status: 'FAIL', details: 'scanned 0 files in packages/media-schema/src or packages/engine/src — check base paths' };
  }
  const importsOf = (base) => {
    const specs = [];
    for (const file of walk(r(base))) {
      const src = readFileSync(file, 'utf8');
      let m;
      while ((m = importRe.exec(src)) !== null) specs.push({ file: file.replace(ROOT, ''), spec: m[1] });
    }
    return specs;
  };

  // media-schema must not pull in React / react-dom (Node-safe).
  for (const { file, spec } of importsOf('packages/media-schema/src')) {
    if (spec === 'react' || spec === 'react-dom' || spec.startsWith('react/') || spec.startsWith('react-dom/')) {
      violations.push(`media-schema imports ${spec} (${file}) — must stay Node-safe`);
    }
  }
  // engine must not depend on design-system (React) or any app.
  for (const { file, spec } of importsOf('packages/engine/src')) {
    if (spec === 'design-system' || spec.startsWith('design-system/')) violations.push(`engine imports design-system (${file})`);
    if (spec === 'react' || spec === 'react-dom') violations.push(`engine imports ${spec} (${file}) — must stay UI-agnostic`);
    if (spec.includes('apps/') || spec === 'funnel-demo' || spec === 'operator') violations.push(`engine imports app code: ${spec} (${file})`);
  }
  // Apps must not import each other's source.
  const crossPairs = [
    ['apps/funnel-demo/src', ['operator', 'apps/operator']],
    ['apps/operator/src', ['funnel-demo', 'apps/funnel-demo']],
  ];
  for (const [base, forbidden] of crossPairs) {
    for (const { file, spec } of importsOf(base)) {
      if (forbidden.some((f) => spec === f || spec.includes(`${f}/`))) violations.push(`cross-app import: ${spec} (${file})`);
    }
  }
  if (violations.length === 0) {
    return { status: 'PASS', details: 'media-schema Node-safe, engine depends only on media-schema, no cross-app imports' };
  }
  return { status: 'FAIL', details: truncate(violations) };
}

// NOTE: smoke-test string drift is deliberately NOT checked here. The repo
// already guards it at edit time via the .claude/plugins/cla/hooks/warn-smoke-test-drift.py
// PreToolUse hook (warns the moment an Edit/Write removes a string the smoke
// script asserts on) — strictly better than a periodic review-time scan, and
// the smoke scripts also assert on dataset strings (station names) and typed
// numbers that legitimately are not i18n values. Whether the smoke script is
// still current is a qualitative call for the Validation review dimension.

const CHECKS = [
  ['Shared i18n parity (design-system en↔ro)', checkSharedI18nParity],
  ['Shared i18n usage coverage', checkSharedI18nUsage],
  ['Daypart key consistency', checkDaypartKeys],
  ['Package boundaries', checkPackageBoundaries],
];

const results = CHECKS.map(([name, fn]) => {
  try {
    return { name, ...fn() };
  } catch (err) {
    return { name, status: 'FAIL', details: `check threw: ${err.message}` };
  }
});

const pass = results.filter((x) => x.status === 'PASS').length;
const fail = results.length - pass;

if (process.argv.includes('--json')) {
  console.log(JSON.stringify({ pass, fail, results }, null, 2));
} else {
  console.log('\nStatic mechanical checks (fast; build/lint/test are run separately by the workflow)\n');
  for (const { name, status, details } of results) {
    const mark = status === 'PASS' ? '✓' : '⚠';
    console.log(`${mark} ${status.padEnd(4)} | ${name}`);
    console.log(`         ${details}`);
  }
  console.log(`\n${pass} PASS, ${fail} FAIL\n`);
}
