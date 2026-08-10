#!/usr/bin/env node
// Deterministic static checks for /review-project.
//
// Generic engine: the actual checks (which files, which dirs, which imports are
// forbidden, ...) are repo-specific DATA, never hardcoded here. They are read from
// this skill's own overlay, `cla.io/overlays/project-review.md`, under a
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
//   node ${CLAUDE_PLUGIN_ROOT}/skills/project-review/scripts/mechanical-checks.mjs          # human table
//   node ${CLAUDE_PLUGIN_ROOT}/skills/project-review/scripts/mechanical-checks.mjs --json   # machine-readable
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

// Resolved against the REPO, not this script's own directory. Under a
// marketplace install the plugin tree is a read-only cache, so a per-repo check
// list stored next to the script would be unwritable — and a missing overlay is
// a legitimate "no checks configured" PASS, so the failure would be silent.
const OVERLAY_RELPATH = 'cla.io/overlays/project-review.md';
const defaultOverlayPath = () => r(OVERLAY_RELPATH);
// Overridable for the same reason as MECHANICAL_CHECKS_ROOT: lets a test point
// loadConfig() at a fixture file instead of this skill's own real overlay.
// Truthy check (matching getRoot()'s `if (process.env...)` above, not `??`) is
// deliberate: an empty-string override is never a usable path, so treating it
// the same as "unset" avoids a silent-override edge case where the env-var-set
// warning below and the actual override would otherwise disagree on whether
// anything is overridden at all.
const getOverlayPath = () => process.env.MECHANICAL_CHECKS_OVERLAY || defaultOverlayPath();

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
    // A genuinely-absent optional dir (ENOENT) is fine — return no files (the
    // caller's own zero-files guard turns that into an ERROR). But a real
    // failure (permissions, I/O, a renamed/moved path) must surface here
    // instead: swallowing it would look identical to "genuinely empty dir" and
    // reach that same ERROR path for the wrong reason, masking a real I/O
    // problem behind a generic "scanned 0 files" message.
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

/** Find every fenced code-block span in `lines` via pure open/close toggling on
 * ``` delimiters ALONE -- no heading awareness at all. This mirrors real
 * CommonMark fence semantics (a fence's content is exactly what's between its
 * open and close delimiters, full stop) and is the only way to unambiguously
 * tell "a line that looks like a heading" apart from "a line that's actually
 * fence content that happens to look like one": that distinction can ONLY be
 * made by first knowing the true fence boundaries, never by scanning for
 * headings and fences in the same interleaved pass (see the two-pass design
 * note on `extractFencedBlockUnderHeading` below for why an interleaved scan is
 * unsound). A fence that opens and is never closed gets `end: -1`. */
function findFenceSpans(lines) {
  const spans = []; // { start, end (exclusive; -1 = never closed), lang }
  let openStart = -1;
  let openLang = '';
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (openStart === -1 && trimmed.startsWith('```')) {
      openStart = i;
      openLang = trimmed.slice(3).trim().toLowerCase();
    } else if (openStart !== -1 && trimmed.startsWith('```')) {
      spans.push({ start: openStart, end: i, lang: openLang });
      openStart = -1;
    }
  }
  if (openStart !== -1) spans.push({ start: openStart, end: -1, lang: openLang });
  return spans;
}

/** Extract the fenced code-block body directly under a `## <headingRe>` heading,
 * stopping at the next heading of equal-or-shallower level. Prefers a fence
 * explicitly tagged ```json; falls back to the first fence of any tag if none is
 * json-tagged (so an untagged ``` still works, matching the schema docs' example).
 * Returns null if the heading isn't found, or no fence sits under it at all --
 * that is the documented, silent "no checks configured" state (e.g. a stub
 * overlay carrying only an explanatory HTML comment), NOT a defect. Throws if a
 * fence that STARTS under the heading is never closed BEFORE the section ends
 * -- a genuine broken authoring attempt -- regardless of whether an earlier,
 * well-formed fence already exists in the same section: silently keeping that
 * earlier fence's content (which may itself be stale, a leftover example, or an
 * empty stub) and dropping the dangling one with no signal at all is exactly
 * the silent-wrong-config outcome this function exists to prevent.
 *
 * Two-pass by necessity, not by choice: `findFenceSpans` above determines every
 * TRUE fence span first, using only ``` delimiters (so a fence's own content --
 * e.g. a shell comment or a quoted markdown heading starting with '#' -- can
 * never be mistaken for real document structure, however deep inside the fence
 * it sits). Only THEN is a heading-looking line treated as a real heading, and
 * only if it does not fall inside any true fence span. A single interleaved
 * scan cannot make this distinction: whether a `#`-line is "real" or "fence
 * content" depends on whether ITS OWN fence ever closes, which isn't knowable
 * until the whole document (not just up to that line) has been scanned for
 * delimiters -- an earlier single-pass version of this function used the
 * interleaved shape and was provably unsound (a fence that spans past a real
 * section boundary could be silently "closed" by an unrelated LATER section's
 * own fence, merging the two sections' content with no error at all).
 *
 * Residual case even THIS two-pass design can't rule out by construction: a
 * fence dangling under our heading, uncoincidentally "closed" by some later
 * section's own fence delimiter, reads as a perfectly balanced open/close pair
 * to pure toggle-counting -- indistinguishable, from inside this function's
 * own logic, from a genuinely well-formed fence. There is no local, forward-
 * scanning way to prove a heading-looking line is "real" without already
 * knowing whether its enclosing fence ever legitimately closes, which is
 * exactly what's in question. As a targeted (not general) safety net for this
 * one residual case: since a legitimate JSON config body can never itself
 * contain a line starting with '#', the SELECTED fence's extracted body is
 * checked for one after the fact, and throws if found -- see the comment at
 * that check for why this is sound for this function's actual use case (a
 * JSON-only config block) without generalizing to arbitrary fence content.
 *
 * `pathLabel` (the resolved overlay path, or a caller-supplied description for
 * a bare in-memory `text`) is used only in thrown messages. */
function extractFencedBlockUnderHeading(text, headingRe, pathLabel = 'the overlay file') {
  const lines = text.split('\n');
  const fenceSpans = findFenceSpans(lines);
  const insideAnyFence = (lineIdx) =>
    fenceSpans.some((f) => lineIdx > f.start && (f.end === -1 || lineIdx < f.end));

  const isRealHeadingLine = (lineIdx) => !insideAnyFence(lineIdx) && headingRe.test(lines[lineIdx].trim());

  let headingIdx = -1;
  for (let i = 0; i < lines.length; i++) {
    if (isRealHeadingLine(i)) {
      headingIdx = i;
      break;
    }
  }
  if (headingIdx === -1) return null;
  const headingLevel = lines[headingIdx].trim().match(/^#+/)?.[0].length ?? 0;

  let sectionEnd = lines.length;
  for (let i = headingIdx + 1; i < lines.length; i++) {
    if (insideAnyFence(i)) continue;
    const m = lines[i].trim().match(/^(#+)\s/);
    if (m && m[1].length <= headingLevel) {
      sectionEnd = i;
      break;
    }
  }

  // Only fences that START within this section count -- one that starts here
  // but isn't closed before sectionEnd (or never closes at all) is exactly the
  // dangling-fence defect this function exists to catch, whether or not some
  // LATER, unrelated fence's own closing delimiter would otherwise appear to
  // "balance" it out.
  const inSection = fenceSpans.filter((f) => f.start > headingIdx && f.start < sectionEnd);
  if (inSection.some((f) => f.end === -1 || f.end >= sectionEnd)) {
    throw new Error(
      `found an opened fence under the "Mechanical checks" heading in ${pathLabel} that is never closed`
    );
  }
  if (inSection.length === 0) return null;
  const jsonFence = inSection.find((f) => f.lang === 'json') ?? inSection[0];
  const body = lines.slice(jsonFence.start + 1, jsonFence.end);
  // Residual case the checks above cannot catch: a fence that opens here, is
  // never closed within ITS OWN section, but happens to get "closed" by some
  // unrelated LATER section's own fence delimiter -- toggle-counting alone
  // sees a balanced open/close pair and no line of this function's other logic
  // can locally tell that apart from a genuinely well-formed fence (whether a
  // heading-looking line is "real" or "fence content" is undecidable without
  // already knowing where its fence closes, which is exactly what's in
  // question). A legitimate JSON config body can never itself contain a line
  // starting with '#' (not valid JSON syntax), so if the SELECTED body does,
  // that is conclusive proof it swallowed real document structure rather than
  // being a well-formed, self-contained fence -- throw instead of silently
  // returning the merged content.
  if (body.some((line) => /^#+\s/.test(line.trim()))) {
    throw new Error(
      `found a fence under the "Mechanical checks" heading in ${pathLabel} that spans past what looks ` +
        'like a later section (its content contains a heading-shaped line) -- check it was actually closed within its own section'
    );
  }
  return body.join('\n');
}

function loadConfig() {
  const overlayPath = getOverlayPath();
  // Show the short, friendly repo-relative name in messages for the normal case
  // (no override), and the actual resolved path only when MECHANICAL_CHECKS_OVERLAY
  // is active -- so a real run's errors stay readable, while a test pointed at a
  // tmp fixture still gets a message naming the file it actually read.
  const overlayLabel = process.env.MECHANICAL_CHECKS_OVERLAY ? overlayPath : OVERLAY_RELPATH;
  if (!existsSync(overlayPath)) return [];
  const text = readFileSync(overlayPath, 'utf8');
  const block = extractFencedBlockUnderHeading(text, /^#{1,6}\s*mechanical checks/i, overlayLabel);
  if (block === null || block.trim() === '') return [];
  let parsed;
  try {
    parsed = JSON.parse(block);
  } catch (err) {
    throw new Error(
      `${overlayLabel} "Mechanical checks" config block is not valid JSON: ${err.message}`
    );
  }
  if (!Array.isArray(parsed.checks)) {
    throw new Error(
      `${overlayLabel} "Mechanical checks" config block must have a top-level "checks" array`
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
    // Guard against a vacuous PASS: an empty deriveLocale.localeFiles would
    // "verify" every derived key against zero locale files -- ERROR, a config gap.
    if (!localeFiles || localeFiles.length === 0) {
      return { status: 'ERROR', details: 'deriveLocale.localeFiles is empty — check cannot verify anything' };
    }
    const locales = localeFiles.map((p) => ({ path: p, data: readJson(r(p)) }));
    for (const k of all) {
      const derived = template.replace('{key}', k);
      for (const { path, data } of locales) {
        if (!(derived in data)) problems.push(`${derived} missing from ${path}`);
      }
    }
  }
  // A union of zero extracted keys agrees perfectly with itself and derives
  // nothing, so every comparison loop above is a no-op and the check reports
  // `PASS (0 keys)` -- the exact shape a silently-broken extraction pattern
  // takes. Zero keys means the sources or the pattern are wrong, not that the
  // repo is consistent.
  if (all.size === 0) {
    return { status: 'ERROR', details: 'extracted 0 keys — check sources/pattern, nothing was compared' };
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
  // ...and against the other vacuous PASS: `specMatches` is `forbidden.some(...)`,
  // and `[].some()` is always false, so an empty or absent list reports "clean"
  // on a source dir that DOES violate the boundary. Deleting one line from a
  // config turned an invariant into a green tick. Every other empty collection
  // in this file is already guarded this way, so this was an omission.
  if (!cfg.forbidden || cfg.forbidden.length === 0) {
    return { status: 'ERROR', details: 'forbidden is empty — the boundary would pass vacuously' };
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
    // Checked PER PAIR, not once for the whole config: one well-configured pair
    // must not vouch for a hollow sibling. An empty `forbidden` makes
    // `specMatches` unconditionally false, so that pair passes without testing
    // anything while the aggregate still reads PASS.
    if (!forbidden || forbidden.length === 0) {
      return { status: 'ERROR', details: `forbidden is empty for ${sourceDir} — that pair would pass vacuously` };
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
  // NOTE: this warning only fires through main() (the CLI entry point) -- a
  // hypothetical future caller that imports loadConfig()/getRoot() directly
  // (bypassing main()) would silently honor an override with no warning at all.
  // Not a live gap today: only this file's own test suite imports those
  // functions directly, and it does so deliberately.
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
  getOverlayPath,
  defaultOverlayPath,
  OVERLAY_RELPATH,
  walk,
  findFenceSpans,
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
