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
// Exit code is 0 for a normal run (FAIL/ERROR rows are data for the review, not a
// CI gate) and non-zero only if the overlay's config block itself is malformed --
// that is an authoring defect, not a review finding.
//
// Testing: functions below are exported for `node --test` (see the sibling
// mechanical-checks.test.mjs) and the CLI itself only runs when this file is
// executed directly (not when imported). `MECHANICAL_CHECKS_ROOT` overrides repo
// -root resolution (mirrors this plugin's `CLAUDE_RETRO_DIR` convention elsewhere)
// so tests can point every check at an isolated tmp fixture tree;
// `MECHANICAL_CHECKS_OVERLAY` similarly overrides which file `loadConfig()` reads,
// so its JSON-validation error paths are exercisable against fixture content
// instead of this skill's own real overlay.

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
  } catch (err) {
    const fallback = fileURLToPath(new URL('../../../../../../', import.meta.url));
    console.error(
      `warning: git rev-parse --show-toplevel failed (${err.message}); falling back to ${fallback}`
    );
    return fallback;
  }
}

// Resolved lazily (not cached into a top-level const) so MECHANICAL_CHECKS_ROOT
// can be set/changed between calls -- the seam `node --test` uses to point every
// check at an isolated tmp fixture tree without touching the real repo. A single
// real run only ever calls this a handful of times, so the repeat git/env check
// costs nothing measurable.
let _cachedRoot;
function getRoot() {
  if (process.env.MECHANICAL_CHECKS_ROOT) return process.env.MECHANICAL_CHECKS_ROOT;
  if (_cachedRoot) return _cachedRoot;
  _cachedRoot = resolveRoot();
  return _cachedRoot;
}
const r = (...p) => join(getRoot(), ...p);

const DEFAULT_OVERLAY_PATH = join(HERE, '..', 'references', 'project-context.md');
const OVERLAY_RELPATH = 'references/project-context.md';
// Overridable for the same reason as MECHANICAL_CHECKS_ROOT: lets a test point
// loadConfig() at a fixture file instead of this skill's own real overlay.
const getOverlayPath = () => process.env.MECHANICAL_CHECKS_OVERLAY ?? DEFAULT_OVERLAY_PATH;

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
 * stopping at the next heading of equal-or-shallower level. Prefers a fence
 * explicitly tagged ```json; falls back to the first fence of any tag if none is
 * json-tagged (so an untagged ``` still works, matching the schema docs' example).
 * Returns null if the heading isn't found, or no fence sits under it at all --
 * that is the documented, silent "no checks configured" state (e.g. a stub
 * overlay carrying only an explanatory HTML comment), NOT a defect. Throws if an
 * OPENED fence under the heading is never closed -- a genuine broken authoring
 * attempt -- regardless of whether an earlier, well-formed fence already exists
 * in the same section: silently keeping that earlier fence's content (which may
 * itself be stale, a leftover example, or an empty stub) and dropping the
 * dangling one with no signal at all is exactly the silent-wrong-config outcome
 * this function exists to prevent. `pathLabel` (the resolved overlay path, or a
 * caller-supplied description for a bare in-memory `text`) is used only in this
 * thrown message. */
function extractFencedBlockUnderHeading(text, headingRe, pathLabel = 'the overlay file') {
  const lines = text.split('\n');
  const headingIdx = lines.findIndex((l) => headingRe.test(l.trim()));
  if (headingIdx === -1) return null;
  // Match against the TRIMMED line, same as the headingIdx search above — a
  // heading found via its trimmed form must have its level read the same way,
  // or leading whitespace (rare in practice, but not impossible) would read as
  // a lower level than the stop-condition comparison below expects.
  const headingLevel = lines[headingIdx].trim().match(/^#+/)?.[0].length ?? 0;
  const fences = []; // { lang, body }
  let fenceStart = -1;
  let fenceLang = '';
  for (let i = headingIdx + 1; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    // Only treat a line as the section's own end-of-heading stop condition when
    // NOT already inside an open fence -- a fenced example whose own content
    // happens to contain a line starting with '#' (a shell comment, a quoted
    // markdown heading) must not be mistaken for this section terminating.
    if (fenceStart === -1) {
      const headingMatch = trimmed.match(/^(#+)\s/);
      if (headingMatch && headingMatch[1].length <= headingLevel) break;
    }
    if (fenceStart === -1 && trimmed.startsWith('```')) {
      fenceStart = i + 1;
      fenceLang = trimmed.slice(3).trim().toLowerCase();
      continue;
    }
    if (fenceStart !== -1 && trimmed.startsWith('```')) {
      fences.push({ lang: fenceLang, body: lines.slice(fenceStart, i).join('\n') });
      fenceStart = -1;
    }
  }
  if (fenceStart !== -1) {
    throw new Error(
      `found an opened fence under the "Mechanical checks" heading in ${pathLabel} that is never closed`
    );
  }
  if (fences.length === 0) return null;
  const jsonFence = fences.find((f) => f.lang === 'json');
  return (jsonFence ?? fences[0]).body;
}

function loadConfig() {
  const overlayPath = getOverlayPath();
  if (!existsSync(overlayPath)) return [];
  const text = readFileSync(overlayPath, 'utf8');
  const block = extractFencedBlockUnderHeading(text, /^#{1,6}\s*mechanical checks/i, overlayPath);
  if (block === null || block.trim() === '') return [];
  let parsed;
  try {
    parsed = JSON.parse(block);
  } catch (err) {
    throw new Error(
      `${overlayPath} "Mechanical checks" config block is not valid JSON: ${err.message}`
    );
  }
  if (!Array.isArray(parsed.checks)) {
    throw new Error(
      `${overlayPath} "Mechanical checks" config block must have a top-level "checks" array`
    );
  }
  return parsed.checks;
}

// ── generic check implementations (all params come from the overlay's config) ─

// json-key-parity: two JSON files must have the same top-level key set.
function checkJsonKeyParity(cfg) {
  const [pathA, pathB] = cfg.files;
  // Guard against a vacuous PASS: a config typo pointing both entries at the same
  // file trivially "matches" (a file compared to itself), verifying nothing.
  if (pathA === pathB) {
    return { status: 'ERROR', details: `files[0] and files[1] are identical (${pathA}) — check config` };
  }
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
  // Guard against a vacuous PASS: an empty localeFiles list would make every key
  // trivially "resolve" (Array.prototype.some on [] is always false) regardless of
  // what the source actually contains. This is a config gap, not a review finding
  // about the repo, so it's ERROR (the check couldn't run meaningfully) not FAIL.
  if (!cfg.localeFiles || cfg.localeFiles.length === 0) {
    return { status: 'ERROR', details: 'localeFiles is empty — check cannot verify anything' };
  }
  const locales = cfg.localeFiles.map((p) => readJson(r(p)));
  const callRe = new RegExp(cfg.keyPattern ?? String.raw`\bt\(\s*['"]([^'"]+)['"]`, 'g');
  const files = cfg.sourceDirs.flatMap((base) => walk(r(base), cfg.extensions ?? ['.ts', '.tsx']));
  // Guard against a vacuous PASS: if the scan found nothing, the base paths are
  // wrong (or empty), not "every key resolves" -- ERROR, same reasoning as above.
  if (files.length === 0) {
    return { status: 'ERROR', details: `scanned 0 source files — check sourceDirs ${cfg.sourceDirs.join(', ')}` };
  }
  const missing = new Set();
  let usagesFound = 0;
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
      usagesFound++;
      if (locales.some((locale) => !(key in locale))) missing.add(key);
    }
  }
  // Guard against a vacuous PASS: zero matched usages across nonzero files means
  // keyPattern itself is likely misconfigured, not "every usage resolves" -- ERROR.
  if (usagesFound === 0) {
    return { status: 'ERROR', details: `matched 0 usages across ${files.length} files — check keyPattern` };
  }
  if (missing.size === 0) return { status: 'PASS', details: 'all static usages resolve in every locale file' };
  return { status: 'FAIL', details: `unresolved: [${truncate(missing)}]` };
}

function extractKeys(source) {
  if (source.kind === 'regex-array') {
    const text = readFileSync(r(source.file), 'utf8');
    // Strip a 'g' flag unconditionally: this code wants text.match(re)'s
    // single-match-with-capture-groups return shape (m[1]), but with a 'g' flag
    // match() instead returns an array of whole-match strings with NO capture
    // groups, silently breaking `m[1]` below. There is exactly one match wanted
    // here regardless of what a config author passes in `flags`.
    const flags = (source.flags ?? '').replace(/g/g, '');
    const re = new RegExp(source.pattern, flags);
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
  // Guard against a vacuous PASS: an empty sources list has no keys to disagree,
  // so it would otherwise report "0 keys" as a silent PASS -- ERROR, a config gap.
  if (!cfg.sources || cfg.sources.length === 0) {
    return { status: 'ERROR', details: 'sources is empty — check cannot verify anything' };
  }
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

// Matches a static `from '...'`, `require('...')`, `import('...')`, or a bare
// side-effect `import '...'` specifier. Four capture groups, exactly one set per
// match depending on which shape matched.
const IMPORT_RE =
  /\bfrom\s+['"]([^'"]+)['"]|\brequire\(\s*['"]([^'"]+)['"]\s*\)|\bimport\(\s*['"]([^'"]+)['"]\s*\)|\bimport\s+['"]([^'"]+)['"]/g;

function importsOf(base, extensions) {
  const specs = [];
  const root = getRoot();
  for (const file of walk(r(base), extensions)) {
    const src = readFileSync(file, 'utf8');
    let m;
    while ((m = IMPORT_RE.exec(src)) !== null) {
      const spec = m[1] ?? m[2] ?? m[3] ?? m[4];
      specs.push({ file: file.replace(root, ''), spec });
    }
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
  const extensions = cfg.extensions ?? ['.ts', '.tsx'];
  // Guard against a vacuous PASS: a typo'd/renamed sourceDir (or a too-narrow
  // extensions list) scans 0 files and would otherwise report "clean" for a
  // boundary never actually checked -- ERROR, a config gap.
  if (walk(r(cfg.sourceDir), extensions).length === 0) {
    return { status: 'ERROR', details: `scanned 0 files in ${cfg.sourceDir} — check sourceDir/extensions` };
  }
  const violations = [];
  for (const { file, spec } of importsOf(cfg.sourceDir, extensions)) {
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
  if (!cfg.pairs || cfg.pairs.length === 0) {
    return { status: 'ERROR', details: 'pairs is empty — check cannot verify anything' };
  }
  const violations = [];
  for (const { sourceDir, forbidden, extensions } of cfg.pairs) {
    const exts = extensions ?? ['.ts', '.tsx'];
    // Guard against a vacuous PASS: a typo'd/renamed sourceDir scans 0 files and
    // would otherwise report "no cross-boundary imports" for a pair never actually
    // scanned -- ERROR, a config gap.
    if (walk(r(sourceDir), exts).length === 0) {
      return { status: 'ERROR', details: `scanned 0 files in ${sourceDir} — check sourceDir/extensions` };
    }
    for (const { file, spec } of importsOf(sourceDir, exts)) {
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

/** Run every configured check. A thrown exception (bad path, malformed source
 * file, unknown source kind, ...) or an unrecognized `type` is a config/script
 * defect, not a review finding -- it gets its own `ERROR` status so it is never
 * confused with a genuine `FAIL` (a check that ran successfully and found a real
 * problem in the reviewed repo). */
function runChecks(checks) {
  return checks.map((check) => {
    const fn = CHECK_TYPES[check.type];
    const name = check.name ?? check.type;
    if (!fn) return { name, status: 'ERROR', details: `unknown check type: ${check.type}` };
    try {
      return { name, ...fn(check) };
    } catch (err) {
      return { name, status: 'ERROR', details: `check threw: ${err.message}` };
    }
  });
}

function main(argv) {
  // A stray MECHANICAL_CHECKS_ROOT/MECHANICAL_CHECKS_OVERLAY in the environment
  // (left over from a debugging session, or an unrelated tool reusing a generic
  // name) would otherwise silently redirect a real run at the wrong repo/overlay
  // with no way to tell from the output alone -- surface it loudly instead.
  if (process.env.MECHANICAL_CHECKS_ROOT || process.env.MECHANICAL_CHECKS_OVERLAY) {
    console.error(
      'warning: MECHANICAL_CHECKS_ROOT/MECHANICAL_CHECKS_OVERLAY is set in the environment -- ' +
        'this run is reading overridden locations, not the real repo/overlay'
    );
  }
  let checks;
  try {
    checks = loadConfig();
  } catch (err) {
    console.error(`error: ${err.message}`);
    return 1;
  }

  const results = runChecks(checks);
  const pass = results.filter((x) => x.status === 'PASS').length;
  const error = results.filter((x) => x.status === 'ERROR').length;
  const fail = results.length - pass - error;

  if (argv.includes('--json')) {
    console.log(JSON.stringify({ pass, fail, error, results }, null, 2));
  } else if (results.length === 0) {
    console.log('\nStatic mechanical checks: none configured for this repo.');
    console.log(`Add a "Mechanical checks" fenced-json block to ${OVERLAY_RELPATH} to configure some`);
    console.log('(see references/mechanical-checks.md for the schema).\n');
  } else {
    console.log('\nStatic mechanical checks (fast; build/lint/test are run separately by the workflow)\n');
    for (const { name, status, details } of results) {
      const mark = status === 'PASS' ? '✓' : status === 'ERROR' ? '✗' : '⚠';
      console.log(`${mark} ${status.padEnd(5)} | ${name}`);
      console.log(`         ${details}`);
    }
    console.log(`\n${pass} PASS, ${fail} FAIL, ${error} ERROR\n`);
  }
  return 0;
}

// Only run the CLI when this file is executed directly (`node mechanical-checks.mjs`),
// not when imported by a test file -- lets `node --test` import the functions below
// and call them directly against fixture data without triggering a real run.
const isMainModule = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
if (isMainModule) {
  process.exit(main(process.argv.slice(2)));
}

export {
  getRoot,
  walk,
  extractFencedBlockUnderHeading,
  loadConfig,
  checkJsonKeyParity,
  checkJsonKeyUsage,
  checkDerivedKeyConsistency,
  checkImportBoundary,
  checkCrossImportBan,
  specMatches,
  importsOf,
  runChecks,
  main,
  CHECK_TYPES,
};
