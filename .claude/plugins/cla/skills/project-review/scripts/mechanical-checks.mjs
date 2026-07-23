#!/usr/bin/env node
// Deterministic static checks for /review-project.
//
// Generic engine: the actual checks (which files, which dirs, which imports are
// forbidden, ...) are repo-specific DATA, never hardcoded here. They are read from
// this skill's own overlay, `references/project-context.md`, under a
// "Mechanical checks — repo specifics" heading containing a fenced ```json``` block
// (see references/mechanical-checks.md for the schema). That overlay is excluded
// from update-cla's sync by name, so every destination repo authors its own check
// list instead of inheriting whatever repo this script was first written against.
// A repo with no such block configured gets a trivial "no checks configured" PASS,
// not a crash on paths that only ever existed in one specific workspace.
//
// This script owns the checks that are (a) genuinely deterministic and (b) NOT
// already covered by the repo's own build/lint/test (those are run by the skill
// workflow directly, as exit-code checks) -- the fast (<1s) cross-file static
// analysis a model would otherwise hand-grep inconsistently: JSON key-set parity,
// literal-key usage against locale files, cross-source key consistency, and
// import/dependency boundaries.
//
// Usage:
//   node .claude/plugins/cla/skills/project-review/scripts/mechanical-checks.mjs          # human table
//   node .claude/plugins/cla/skills/project-review/scripts/mechanical-checks.mjs --json   # machine-readable
//
// Exit code is 0 for a normal run (FAIL rows are data for the review, not a CI
// gate) and non-zero only if the overlay's config block itself is malformed --
// that is an authoring defect, not a review finding.

import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

// Repo root, resolved location-independently (via git) so this keeps working
// regardless of how deep the plugin nests -- it lives at
// .claude/plugins/cla/skills/project-review/scripts/ today, but the checks only
// ever want the repo root, never a path relative to this file. fileURLToPath (not
// raw .pathname) so a repo path containing spaces works.
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

const OVERLAY_PATH = join(HERE, '..', 'references', 'project-context.md');
const OVERLAY_RELPATH = 'references/project-context.md';

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

function truncate(list, n = 8) {
  const arr = [...list];
  if (arr.length <= n) return arr.join(', ');
  return `${arr.slice(0, n).join(', ')} … (+${arr.length - n} more)`;
}

/** Recursively collect files matching `exts` under a dir, skipping build/dep dirs. */
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

// ── config: read the fenced ```json``` block under the overlay's own heading ──

/** Extract the fenced code-block body directly under a `## <headingRe>` heading,
 * stopping at the next heading of equal-or-shallower level. Returns null if the
 * heading, or a fence under it, isn't found. */
function extractFencedBlockUnderHeading(text, headingRe) {
  const lines = text.split('\n');
  const headingIdx = lines.findIndex((l) => headingRe.test(l.trim()));
  if (headingIdx === -1) return null;
  const headingLevel = lines[headingIdx].match(/^#+/)?.[0].length ?? 0;
  let fenceStart = -1;
  for (let i = headingIdx + 1; i < lines.length; i++) {
    const line = lines[i];
    const headingMatch = line.match(/^(#+)\s/);
    if (headingMatch && headingMatch[1].length <= headingLevel) break;
    if (fenceStart === -1 && line.trim().startsWith('```')) {
      fenceStart = i + 1;
      continue;
    }
    if (fenceStart !== -1 && line.trim().startsWith('```')) {
      return lines.slice(fenceStart, i).join('\n');
    }
  }
  return null;
}

function loadConfig() {
  if (!existsSync(OVERLAY_PATH)) return [];
  const text = readFileSync(OVERLAY_PATH, 'utf8');
  const block = extractFencedBlockUnderHeading(text, /^#{1,6}\s*mechanical checks/i);
  if (block === null || block.trim() === '') return [];
  let parsed;
  try {
    parsed = JSON.parse(block);
  } catch (err) {
    throw new Error(
      `${OVERLAY_RELPATH} "Mechanical checks" config block is not valid JSON: ${err.message}`
    );
  }
  if (!Array.isArray(parsed.checks)) {
    throw new Error(
      `${OVERLAY_RELPATH} "Mechanical checks" config block must have a top-level "checks" array`
    );
  }
  return parsed.checks;
}

// ── generic check implementations (all params come from the overlay's config) ─

// json-key-parity: two JSON files must have the same top-level key set.
function checkJsonKeyParity(cfg) {
  const [pathA, pathB] = cfg.files;
  const a = new Set(Object.keys(readJson(r(pathA))));
  const b = new Set(Object.keys(readJson(r(pathB))));
  const aOnly = [...a].filter((k) => !b.has(k));
  const bOnly = [...b].filter((k) => !a.has(k));
  if (aOnly.length === 0 && bOnly.length === 0) {
    return { status: 'PASS', details: `key sets match (${a.size} keys)` };
  }
  const parts = [];
  if (aOnly.length) parts.push(`${pathA}-only: [${truncate(aOnly)}]`);
  if (bOnly.length) parts.push(`${pathB}-only: [${truncate(bOnly)}]`);
  return { status: 'FAIL', details: parts.join('; ') };
}

// json-key-usage: every static `t('key')`-shaped literal found under sourceDirs
// must resolve in every locale file. Dynamically-built keys are not resolvable
// statically and are silently skipped -- a known limitation.
function checkJsonKeyUsage(cfg) {
  const locales = cfg.localeFiles.map((p) => readJson(r(p)));
  const callRe = new RegExp(cfg.keyPattern ?? String.raw`\bt\(\s*['"]([^'"]+)['"]`, 'g');
  const files = cfg.sourceDirs.flatMap((base) => walk(r(base), cfg.extensions ?? ['.ts', '.tsx']));
  // Guard against a vacuous PASS: if the scan found nothing, the base paths are
  // wrong (or empty), not "every key resolves".
  if (files.length === 0) {
    return { status: 'FAIL', details: `scanned 0 source files — check sourceDirs ${cfg.sourceDirs.join(', ')}` };
  }
  const missing = new Set();
  for (const file of files) {
    const src = readFileSync(file, 'utf8');
    let m;
    while ((m = callRe.exec(src)) !== null) {
      const key = m[1];
      // Skip dynamically-composed keys, e.g. t('dashboard.genre.' + g): a trailing
      // '.' or a '+' right after the closing quote means this is a prefix being
      // concatenated, not a complete key.
      const after = src.slice(callRe.lastIndex).trimStart();
      if (key.endsWith('.') || after.startsWith('+')) continue;
      if (locales.some((locale) => !(key in locale))) missing.add(key);
    }
  }
  if (missing.size === 0) return { status: 'PASS', details: 'all static usages resolve in every locale file' };
  return { status: 'FAIL', details: `unresolved: [${truncate(missing)}]` };
}

function extractKeys(source) {
  if (source.kind === 'regex-array') {
    const text = readFileSync(r(source.file), 'utf8');
    const re = new RegExp(source.pattern, source.flags ?? '');
    const m = text.match(re);
    if (!m) throw new Error(`pattern did not match in ${source.file} (structure changed?)`);
    return [...m[1].matchAll(/'([^']+)'|"([^"]+)"/g)].map((mm) => mm[1] ?? mm[2]);
  }
  if (source.kind === 'json-array-field') {
    return readJson(r(source.file)).map((row) => row[source.field]);
  }
  throw new Error(`unknown source kind: ${source.kind}`);
}

// derived-key-consistency: N key sources (each a regex-extracted array from a
// source file, or a field pulled off a JSON array) must all agree on the same key
// set; optionally, each key must also resolve (via a `{key}` template) in every
// locale file.
function checkDerivedKeyConsistency(cfg) {
  const named = cfg.sources.map((s) => ({ label: s.label ?? s.file, keys: new Set(extractKeys(s)) }));
  const all = new Set(named.flatMap((n) => [...n.keys]));
  const problems = [];
  for (const k of all) {
    const missingFrom = named.filter((n) => !n.keys.has(k)).map((n) => n.label);
    if (missingFrom.length) problems.push(`${k}: missing from ${missingFrom.join(', ')}`);
  }
  if (cfg.deriveLocale) {
    const { template, localeFiles } = cfg.deriveLocale;
    const locales = localeFiles.map((p) => ({ path: p, data: readJson(r(p)) }));
    for (const k of all) {
      const derived = template.replace('{key}', k);
      for (const { path, data } of locales) {
        if (!(derived in data)) problems.push(`${derived} missing from ${path}`);
      }
    }
  }
  if (problems.length === 0) {
    return { status: 'PASS', details: `${named.map((n) => n.label).join(' = ')} (${all.size} keys)` };
  }
  return { status: 'FAIL', details: truncate(problems) };
}

const IMPORT_RE = /\bfrom\s+['"]([^'"]+)['"]/g;

function importsOf(base) {
  const specs = [];
  for (const file of walk(r(base))) {
    const src = readFileSync(file, 'utf8');
    let m;
    while ((m = IMPORT_RE.exec(src)) !== null) specs.push({ file: file.replace(ROOT, ''), spec: m[1] });
  }
  return specs;
}

// A forbidden entry matches a spec by exact string or substring, so a repo's
// overlay can pin as loosely or tightly as it needs (e.g. 'react' vs 'apps/').
function specMatches(spec, forbidden) {
  return forbidden.some((f) => spec === f || spec.includes(f));
}

// import-boundary: sourceDir must not import anything matching `forbidden`.
function checkImportBoundary(cfg) {
  if (walk(r(cfg.sourceDir)).length === 0) {
    return { status: 'FAIL', details: `scanned 0 files in ${cfg.sourceDir} — check sourceDir` };
  }
  const violations = [];
  for (const { file, spec } of importsOf(cfg.sourceDir)) {
    if (specMatches(spec, cfg.forbidden)) {
      violations.push(`${cfg.sourceDir} imports ${spec} (${file})${cfg.reason ? ` — ${cfg.reason}` : ''}`);
    }
  }
  if (violations.length === 0) return { status: 'PASS', details: cfg.passMessage ?? `${cfg.sourceDir} clean` };
  return { status: 'FAIL', details: truncate(violations) };
}

// cross-import-ban: several {sourceDir, forbidden} pairs in one check, e.g. two
// apps that must not import each other's source.
function checkCrossImportBan(cfg) {
  const violations = [];
  for (const { sourceDir, forbidden } of cfg.pairs) {
    for (const { file, spec } of importsOf(sourceDir)) {
      if (specMatches(spec, forbidden)) violations.push(`cross-boundary import: ${spec} (${file})`);
    }
  }
  if (violations.length === 0) return { status: 'PASS', details: cfg.passMessage ?? 'no cross-boundary imports' };
  return { status: 'FAIL', details: truncate(violations) };
}

const CHECK_TYPES = {
  'json-key-parity': checkJsonKeyParity,
  'json-key-usage': checkJsonKeyUsage,
  'derived-key-consistency': checkDerivedKeyConsistency,
  'import-boundary': checkImportBoundary,
  'cross-import-ban': checkCrossImportBan,
};

// ── run ─────────────────────────────────────────────────────────────────────

let checks;
try {
  checks = loadConfig();
} catch (err) {
  console.error(`error: ${err.message}`);
  process.exit(1);
}

const results = checks.map((check) => {
  const fn = CHECK_TYPES[check.type];
  const name = check.name ?? check.type;
  if (!fn) return { name, status: 'FAIL', details: `unknown check type: ${check.type}` };
  try {
    return { name, ...fn(check) };
  } catch (err) {
    return { name, status: 'FAIL', details: `check threw: ${err.message}` };
  }
});

const pass = results.filter((x) => x.status === 'PASS').length;
const fail = results.length - pass;

if (process.argv.includes('--json')) {
  console.log(JSON.stringify({ pass, fail, results }, null, 2));
} else if (results.length === 0) {
  console.log('\nStatic mechanical checks: none configured for this repo.');
  console.log(`Add a "Mechanical checks" fenced-json block to ${OVERLAY_RELPATH} to configure some`);
  console.log('(see references/mechanical-checks.md for the schema).\n');
} else {
  console.log('\nStatic mechanical checks (fast; build/lint/test are run separately by the workflow)\n');
  for (const { name, status, details } of results) {
    const mark = status === 'PASS' ? '✓' : '⚠';
    console.log(`${mark} ${status.padEnd(4)} | ${name}`);
    console.log(`         ${details}`);
  }
  console.log(`\n${pass} PASS, ${fail} FAIL\n`);
}
