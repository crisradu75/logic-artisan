// Tests for mechanical-checks.mjs's generic check engine.
//
// Run: node --test .claude/plugins/cla/skills/project-review/scripts/mechanical-checks.test.mjs
//
// Not wired into run_tests.py: that runner discovers Python pytest scopes only
// (a dir with a pytest-configured pyproject.toml + a tests/ dir) -- this is a
// deliberately separate `node --test` file, not a `tests/` dir, so it stays
// invisible to (and can't trip) that discovery's near-miss detection.
//
// Path-based checks resolve everything through MECHANICAL_CHECKS_ROOT (see
// withRoot below) so no test touches this repo's real files; loadConfig's own
// tests use MECHANICAL_CHECKS_OVERLAY the same way.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const SCRIPT_PATH = fileURLToPath(new URL('./mechanical-checks.mjs', import.meta.url));

import {
  getOverlayPath,
  defaultOverlayPath,
  OVERLAY_RELPATH,
  extractFencedBlockUnderHeading,
  loadConfig,
  checkJsonKeyParity,
  checkJsonKeyUsage,
  checkDerivedKeyConsistency,
  checkImportBoundary,
  checkCrossImportBan,
  specMatches,
  runChecks,
  main,
} from './mechanical-checks.mjs';

const HEADING_RE = /^#{1,6}\s*mechanical checks/i;

/** Run `fn` with MECHANICAL_CHECKS_ROOT pointed at a fresh tmp dir (removed
 * afterward), so path-resolving check functions never touch the real repo. */
function withRoot(fn) {
  const dir = mkdtempSync(join(tmpdir(), 'mechanical-checks-test-'));
  const prev = process.env.MECHANICAL_CHECKS_ROOT;
  process.env.MECHANICAL_CHECKS_ROOT = dir;
  try {
    return fn(dir);
  } finally {
    if (prev === undefined) delete process.env.MECHANICAL_CHECKS_ROOT;
    else process.env.MECHANICAL_CHECKS_ROOT = prev;
    rmSync(dir, { recursive: true, force: true });
  }
}

function writeJson(root, relPath, data) {
  const full = join(root, relPath);
  mkdirSync(join(full, '..'), { recursive: true });
  writeFileSync(full, JSON.stringify(data), 'utf8');
}

function writeFile(root, relPath, content) {
  const full = join(root, relPath);
  mkdirSync(join(full, '..'), { recursive: true });
  writeFileSync(full, content, 'utf8');
}

/** Run `fn` with MECHANICAL_CHECKS_OVERLAY pointed at a fresh tmp file holding
 * `content` (removed afterward), so loadConfig() reads fixture content instead
 * of this skill's own real overlay. */
function withOverlay(content, fn) {
  const dir = mkdtempSync(join(tmpdir(), 'mechanical-checks-overlay-'));
  const file = join(dir, 'project-context.md');
  writeFileSync(file, content, 'utf8');
  const prev = process.env.MECHANICAL_CHECKS_OVERLAY;
  process.env.MECHANICAL_CHECKS_OVERLAY = file;
  try {
    return fn();
  } finally {
    if (prev === undefined) delete process.env.MECHANICAL_CHECKS_OVERLAY;
    else process.env.MECHANICAL_CHECKS_OVERLAY = prev;
    rmSync(dir, { recursive: true, force: true });
  }
}

// ── extractFencedBlockUnderHeading ───────────────────────────────────────────

test('extractFencedBlockUnderHeading: no heading returns null', () => {
  assert.equal(extractFencedBlockUnderHeading('# Other\n\nnothing here\n', HEADING_RE), null);
});

test('extractFencedBlockUnderHeading: heading with no fence returns null, no throw', () => {
  const text = '## Mechanical checks — repo specifics\n\njust an explanation, no fence.\n';
  assert.equal(extractFencedBlockUnderHeading(text, HEADING_RE), null);
});

test('extractFencedBlockUnderHeading: an opened-but-unclosed fence throws', () => {
  const text = '## Mechanical checks\n\n```json\n{"checks": []}\n';
  assert.throws(() => extractFencedBlockUnderHeading(text, HEADING_RE), /never closed/);
});

test('extractFencedBlockUnderHeading: a dangling fence AFTER an earlier well-formed one still throws (regression guard)', () => {
  // The bug this guards: if the "unclosed fence" check only fired when fences.length
  // === 0, a dangling fence following an earlier complete one was silently dropped
  // and the earlier (possibly stale/wrong) fence's content was returned instead --
  // with zero signal that the author's later edit never took effect.
  const text = [
    '## Mechanical checks',
    '',
    'Old stale example (author forgot to delete when editing):',
    '```json',
    '{"checks": []}',
    '```',
    '',
    'New real config the author meant to add but forgot to close:',
    '```json',
    '{"checks": ["should never surface -- the whole block must throw"]}',
    '',
  ].join('\n');
  assert.throws(() => extractFencedBlockUnderHeading(text, HEADING_RE), /never closed/);
});

test('extractFencedBlockUnderHeading: a fence dangling PAST a real section boundary still throws, even if a later section\'s own fence would otherwise "balance" the backtick count (regression guard)', () => {
  // The exact bug a retroactive review found in the first version of the
  // dangling-fence fix: skipping the heading-stop check entirely while inside an
  // open fence let the scan run straight through a REAL later heading and get
  // "closed" by a completely unrelated fence in a different section -- silently
  // merging the two sections' content instead of throwing. Two total ``` markers
  // after "## Mechanical checks" (even parity) used to read as "cleanly closed";
  // it must still throw, because the fence that opened under OUR heading never
  // closed before OUR section ended.
  const text = [
    '## Mechanical checks',
    '```json',
    '{"checks": []}',
    '',
    '## Some other, unrelated later section',
    'prose intro, then an example fence opens:',
    '```',
    'end of doc',
  ].join('\n');
  assert.throws(() => extractFencedBlockUnderHeading(text, HEADING_RE), /spans past what looks like a later section/);
});

test('extractFencedBlockUnderHeading: a "#"-prefixed line INSIDE a fence does not prematurely end the section', () => {
  // Guards against treating a fence's own content (e.g. a shell comment, a quoted
  // markdown heading shown as an example) as this section's heading-stop condition.
  const text = [
    '## Mechanical checks',
    '```bash',
    '# this looks like a heading but is inside a fence',
    '```',
    '```json',
    '{"checks": ["real"]}',
    '```',
    '',
  ].join('\n');
  assert.equal(extractFencedBlockUnderHeading(text, HEADING_RE).trim(), '{"checks": ["real"]}');
});

test('extractFencedBlockUnderHeading: extracts a json-tagged fence', () => {
  const text = '## Mechanical checks\n\n```json\n{"checks": []}\n```\n';
  assert.equal(extractFencedBlockUnderHeading(text, HEADING_RE).trim(), '{"checks": []}');
});

test('extractFencedBlockUnderHeading: extracts an untagged fence (backward compatible)', () => {
  const text = '## Mechanical checks\n\n```\n{"checks": []}\n```\n';
  assert.equal(extractFencedBlockUnderHeading(text, HEADING_RE).trim(), '{"checks": []}');
});

test('extractFencedBlockUnderHeading: prefers a json-tagged fence over an earlier untagged one', () => {
  const text = [
    '## Mechanical checks',
    '',
    'Example:',
    '```bash',
    'not the config',
    '```',
    '',
    '```json',
    '{"checks": ["real"]}',
    '```',
    '',
  ].join('\n');
  assert.equal(extractFencedBlockUnderHeading(text, HEADING_RE).trim(), '{"checks": ["real"]}');
});

test('extractFencedBlockUnderHeading: a deeper sub-heading does not stop extraction', () => {
  const text = [
    '## Mechanical checks',
    '### A sub-section',
    'prose',
    '```json',
    '{"checks": []}',
    '```',
    '',
  ].join('\n');
  assert.equal(extractFencedBlockUnderHeading(text, HEADING_RE).trim(), '{"checks": []}');
});

test('extractFencedBlockUnderHeading: stops at the next equal-level heading', () => {
  const text = [
    '## Mechanical checks',
    'prose, no fence here',
    '## Another section',
    '```json',
    '{"checks": ["should not be picked up"]}',
    '```',
    '',
  ].join('\n');
  assert.equal(extractFencedBlockUnderHeading(text, HEADING_RE), null);
});

// ── loadConfig ────────────────────────────────────────────────────────────────

test('loadConfig: absent overlay file returns []', () => {
  const missing = join(mkdtempSync(join(tmpdir(), 'mc-missing-')), 'project-context.md');
  const prev = process.env.MECHANICAL_CHECKS_OVERLAY;
  process.env.MECHANICAL_CHECKS_OVERLAY = missing;
  try {
    assert.deepEqual(loadConfig(), []);
  } finally {
    if (prev === undefined) delete process.env.MECHANICAL_CHECKS_OVERLAY;
    else process.env.MECHANICAL_CHECKS_OVERLAY = prev;
  }
});

test('loadConfig: no config block returns []', () => {
  withOverlay('## Mechanical checks\n\nnothing configured yet.\n', () => {
    assert.deepEqual(loadConfig(), []);
  });
});

test('loadConfig: valid config returns the checks array', () => {
  withOverlay(
    '## Mechanical checks\n\n```json\n{"checks": [{"type": "json-key-parity", "files": ["a.json", "b.json"]}]}\n```\n',
    () => {
      const checks = loadConfig();
      assert.equal(checks.length, 1);
      assert.equal(checks[0].type, 'json-key-parity');
    }
  );
});

test('loadConfig: malformed JSON throws with a clear message', () => {
  withOverlay('## Mechanical checks\n\n```json\n{ not json }\n```\n', () => {
    assert.throws(() => loadConfig(), /not valid JSON/);
  });
});

test('loadConfig: a non-array "checks" field throws with a clear message', () => {
  withOverlay('## Mechanical checks\n\n```json\n{"checks": "oops"}\n```\n', () => {
    assert.throws(() => loadConfig(), /"checks" array/);
  });
});

test('loadConfig: a dangling fence in the REAL overlay file throws end-to-end (integration, not just the pure function)', () => {
  // The prior review's headline bug was found via a real loadConfig() run, not
  // by calling extractFencedBlockUnderHeading directly -- so the regression
  // guard belongs at this boundary too, not only at the pure-function level.
  withOverlay(
    [
      '## Mechanical checks',
      '```json',
      '{"checks": []}',
      '',
      '## Some other, unrelated later section',
      'prose intro, then an example fence opens:',
      '```',
      'end of doc',
    ].join('\n'),
    () => {
      assert.throws(() => loadConfig(), /spans past what looks like a later section/);
    }
  );
});

test('loadConfig: error messages name the actual overlay file read, not a hardcoded constant', () => {
  withOverlay('## Mechanical checks\n\n```json\n{ not json }\n```\n', () => {
    const overlayPath = getOverlayPath();
    assert.throws(() => loadConfig(), new RegExp(overlayPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  });
});

test('getOverlayPath: an empty-string override is treated as unset, not as an empty path', () => {
  const prev = process.env.MECHANICAL_CHECKS_OVERLAY;
  process.env.MECHANICAL_CHECKS_OVERLAY = '';
  try {
    assert.equal(getOverlayPath(), defaultOverlayPath());
  } finally {
    if (prev === undefined) delete process.env.MECHANICAL_CHECKS_OVERLAY;
    else process.env.MECHANICAL_CHECKS_OVERLAY = prev;
  }
});

// ── checkJsonKeyParity ────────────────────────────────────────────────────────

test('checkJsonKeyParity: matching key sets PASS', () => {
  withRoot((root) => {
    writeJson(root, 'a.json', { x: 1, y: 2 });
    writeJson(root, 'b.json', { x: 1, y: 2 });
    const result = checkJsonKeyParity({ files: ['a.json', 'b.json'] });
    assert.equal(result.status, 'PASS');
  });
});

test('checkJsonKeyParity: mismatched key sets FAIL, listing both sides', () => {
  withRoot((root) => {
    writeJson(root, 'a.json', { x: 1, onlyA: 1 });
    writeJson(root, 'b.json', { x: 1, onlyB: 1 });
    const result = checkJsonKeyParity({ files: ['a.json', 'b.json'] });
    assert.equal(result.status, 'FAIL');
    assert.match(result.details, /onlyA/);
    assert.match(result.details, /onlyB/);
  });
});

test('checkJsonKeyParity: identical files[0]/files[1] ERRORs instead of vacuously passing', () => {
  withRoot((root) => {
    writeJson(root, 'a.json', { x: 1 });
    const result = checkJsonKeyParity({ files: ['a.json', 'a.json'] });
    assert.equal(result.status, 'ERROR');
    assert.match(result.details, /identical/);
  });
});

// ── checkJsonKeyUsage ──────────────────────────────────────────────────────────

test('checkJsonKeyUsage: empty localeFiles ERRORs instead of vacuously passing', () => {
  withRoot((root) => {
    writeFile(root, 'src/App.ts', "t('a.b');");
    const result = checkJsonKeyUsage({ localeFiles: [], sourceDirs: ['src'] });
    assert.equal(result.status, 'ERROR');
    assert.match(result.details, /localeFiles is empty/);
  });
});

test('checkJsonKeyUsage: zero source files ERRORs (regression guard)', () => {
  withRoot((root) => {
    writeJson(root, 'en.json', { 'a.b': 'x' });
    const result = checkJsonKeyUsage({ localeFiles: ['en.json'], sourceDirs: ['does-not-exist'] });
    assert.equal(result.status, 'ERROR');
    assert.match(result.details, /scanned 0 source files/);
  });
});

test('checkJsonKeyUsage: zero matched usages ERRORs instead of vacuously passing', () => {
  withRoot((root) => {
    writeJson(root, 'en.json', { 'a.b': 'x' });
    writeFile(root, 'src/App.ts', 'no translation calls in this file at all');
    const result = checkJsonKeyUsage({ localeFiles: ['en.json'], sourceDirs: ['src'] });
    assert.equal(result.status, 'ERROR');
    assert.match(result.details, /matched 0 usages/);
  });
});

test('checkJsonKeyUsage: custom extensions picks up a non-.ts/.tsx file', () => {
  withRoot((root) => {
    writeJson(root, 'en.json', { 'a.b': 'x' });
    writeFile(root, 'src/App.js', "t('a.b');");
    const withDefaultExts = checkJsonKeyUsage({ localeFiles: ['en.json'], sourceDirs: ['src'] });
    assert.equal(withDefaultExts.status, 'ERROR'); // scanned 0 files (no .ts/.tsx present)
    const withJsExt = checkJsonKeyUsage({ localeFiles: ['en.json'], sourceDirs: ['src'], extensions: ['.js'] });
    assert.equal(withJsExt.status, 'PASS');
  });
});

test('checkJsonKeyUsage: a static key present in every locale PASSes', () => {
  withRoot((root) => {
    writeJson(root, 'en.json', { 'a.b': 'x' });
    writeJson(root, 'ro.json', { 'a.b': 'y' });
    writeFile(root, 'src/App.ts', "t('a.b');");
    const result = checkJsonKeyUsage({ localeFiles: ['en.json', 'ro.json'], sourceDirs: ['src'] });
    assert.equal(result.status, 'PASS');
  });
});

test('checkJsonKeyUsage: a static key missing from one locale FAILs and lists it', () => {
  withRoot((root) => {
    writeJson(root, 'en.json', { 'a.b': 'x' });
    writeJson(root, 'ro.json', {});
    writeFile(root, 'src/App.ts', "t('a.b');");
    const result = checkJsonKeyUsage({ localeFiles: ['en.json', 'ro.json'], sourceDirs: ['src'] });
    assert.equal(result.status, 'FAIL');
    assert.match(result.details, /a\.b/);
  });
});

test('checkJsonKeyUsage: a dynamically composed key is skipped, not flagged missing', () => {
  withRoot((root) => {
    writeJson(root, 'en.json', { 'a.b': 'x' });
    writeFile(root, 'src/App.ts', "t('a.b'); t('dashboard.genre.' + g);");
    const result = checkJsonKeyUsage({ localeFiles: ['en.json'], sourceDirs: ['src'] });
    assert.equal(result.status, 'PASS');
  });
});

// ── checkDerivedKeyConsistency ─────────────────────────────────────────────────

test('checkDerivedKeyConsistency: empty sources ERRORs instead of vacuously passing', () => {
  withRoot(() => {
    const result = checkDerivedKeyConsistency({ sources: [] });
    assert.equal(result.status, 'ERROR');
    assert.match(result.details, /sources is empty/);
  });
});

test('checkDerivedKeyConsistency: matching sources PASS', () => {
  withRoot((root) => {
    writeFile(root, 'domain.ts', "const KEYS: K[] = ['prime', 'daytime'];");
    writeJson(root, 'data.json', [{ key: 'prime' }, { key: 'daytime' }]);
    const result = checkDerivedKeyConsistency({
      sources: [
        { kind: 'regex-array', file: 'domain.ts', pattern: 'KEYS\\s*:\\s*K\\[\\]\\s*=\\s*\\[([^\\]]+)\\]', label: 'domain.ts' },
        { kind: 'json-array-field', file: 'data.json', field: 'key', label: 'data.json' },
      ],
    });
    assert.equal(result.status, 'PASS');
  });
});

test('checkDerivedKeyConsistency: a key missing from one source FAILs and lists it', () => {
  withRoot((root) => {
    writeFile(root, 'domain.ts', "const KEYS: K[] = ['prime', 'daytime'];");
    writeJson(root, 'data.json', [{ key: 'prime' }]);
    const result = checkDerivedKeyConsistency({
      sources: [
        { kind: 'regex-array', file: 'domain.ts', pattern: 'KEYS\\s*:\\s*K\\[\\]\\s*=\\s*\\[([^\\]]+)\\]', label: 'domain.ts' },
        { kind: 'json-array-field', file: 'data.json', field: 'key', label: 'data.json' },
      ],
    });
    assert.equal(result.status, 'FAIL');
    assert.match(result.details, /daytime/);
  });
});

test('checkDerivedKeyConsistency: a "g" flag on a regex-array source is stripped, not left to break capture groups', () => {
  withRoot((root) => {
    writeFile(root, 'domain.ts', "const KEYS: K[] = ['prime', 'daytime'];");
    writeJson(root, 'data.json', [{ key: 'prime' }, { key: 'daytime' }]);
    // Without stripping 'g', text.match(re) would return whole-match strings
    // with no capture groups, and `m[1].matchAll(...)` below would throw on
    // `m[1]` being undefined instead of extracting the two keys.
    const result = checkDerivedKeyConsistency({
      sources: [
        { kind: 'regex-array', file: 'domain.ts', pattern: 'KEYS\\s*:\\s*K\\[\\]\\s*=\\s*\\[([^\\]]+)\\]', flags: 'g', label: 'domain.ts' },
        { kind: 'json-array-field', file: 'data.json', field: 'key', label: 'data.json' },
      ],
    });
    assert.equal(result.status, 'PASS');
  });
});

test('checkDerivedKeyConsistency: deriveLocale missing key FAILs', () => {
  withRoot((root) => {
    writeFile(root, 'domain.ts', "const KEYS: K[] = ['prime'];");
    writeJson(root, 'en.json', {});
    const result = checkDerivedKeyConsistency({
      sources: [{ kind: 'regex-array', file: 'domain.ts', pattern: 'KEYS\\s*:\\s*K\\[\\]\\s*=\\s*\\[([^\\]]+)\\]', label: 'domain.ts' }],
      deriveLocale: { template: 'dashboard.foo.{key}', localeFiles: ['en.json'] },
    });
    assert.equal(result.status, 'FAIL');
    assert.match(result.details, /dashboard\.foo\.prime/);
  });
});

test('checkDerivedKeyConsistency: an empty deriveLocale.localeFiles ERRORs instead of vacuously passing', () => {
  withRoot((root) => {
    writeFile(root, 'domain.ts', "const KEYS: K[] = ['prime'];");
    const result = checkDerivedKeyConsistency({
      sources: [{ kind: 'regex-array', file: 'domain.ts', pattern: 'KEYS\\s*:\\s*K\\[\\]\\s*=\\s*\\[([^\\]]+)\\]', label: 'domain.ts' }],
      deriveLocale: { template: 'dashboard.foo.{key}', localeFiles: [] },
    });
    assert.equal(result.status, 'ERROR');
    assert.match(result.details, /deriveLocale\.localeFiles is empty/);
  });
});

test('checkDerivedKeyConsistency: an unknown source kind throws', () => {
  withRoot(() => {
    assert.throws(
      () => checkDerivedKeyConsistency({ sources: [{ kind: 'bogus', file: 'x' }] }),
      /unknown source kind/
    );
  });
});

test('checkDerivedKeyConsistency: a regex-array pattern that does not match throws', () => {
  withRoot((root) => {
    writeFile(root, 'domain.ts', 'const KEYS = [1, 2, 3]; // structure changed, no longer matches the pattern below');
    assert.throws(
      () =>
        checkDerivedKeyConsistency({
          sources: [{ kind: 'regex-array', file: 'domain.ts', pattern: 'KEYS\\s*:\\s*K\\[\\]\\s*=\\s*\\[([^\\]]+)\\]' }],
        }),
      /structure changed\?/
    );
  });
});

// ── checkImportBoundary ────────────────────────────────────────────────────────

test('checkImportBoundary: zero files scanned ERRORs (regression guard)', () => {
  withRoot(() => {
    const result = checkImportBoundary({ sourceDir: 'does-not-exist', forbidden: ['react'] });
    assert.equal(result.status, 'ERROR');
    assert.match(result.details, /scanned 0 files/);
  });
});

test('checkImportBoundary: a forbidden static import FAILs', () => {
  withRoot((root) => {
    writeFile(root, 'src/index.ts', "import { useState } from 'react';\n");
    const result = checkImportBoundary({ sourceDir: 'src', forbidden: ['react'] });
    assert.equal(result.status, 'FAIL');
    assert.match(result.details, /react/);
  });
});

test('checkImportBoundary: no forbidden import PASSes (custom passMessage honored)', () => {
  withRoot((root) => {
    writeFile(root, 'src/index.ts', 'export const x = 1;\n');
    const result = checkImportBoundary({ sourceDir: 'src', forbidden: ['react'], passMessage: 'all clean' });
    assert.equal(result.status, 'PASS');
    assert.equal(result.details, 'all clean');
  });
});

test('checkImportBoundary: a forbidden require() import FAILs (not just static `from`)', () => {
  withRoot((root) => {
    writeFile(root, 'src/index.ts', "const react = require('react');\n");
    const result = checkImportBoundary({ sourceDir: 'src', forbidden: ['react'] });
    assert.equal(result.status, 'FAIL');
  });
});

test('checkImportBoundary: a forbidden dynamic import() FAILs', () => {
  withRoot((root) => {
    writeFile(root, 'src/index.ts', "await import('react');\n");
    const result = checkImportBoundary({ sourceDir: 'src', forbidden: ['react'] });
    assert.equal(result.status, 'FAIL');
  });
});

test('checkImportBoundary: a forbidden bare side-effect import (`import \'...\'`) FAILs', () => {
  withRoot((root) => {
    writeFile(root, 'src/index.ts', "import 'react';\n");
    const result = checkImportBoundary({ sourceDir: 'src', forbidden: ['react'] });
    assert.equal(result.status, 'FAIL');
  });
});

test('checkImportBoundary: custom extensions picks up a non-.ts/.tsx file', () => {
  withRoot((root) => {
    writeFile(root, 'src/index.js', "import { useState } from 'react';\n");
    const withDefaultExts = checkImportBoundary({ sourceDir: 'src', forbidden: ['react'] });
    assert.equal(withDefaultExts.status, 'ERROR'); // scanned 0 files (no .ts/.tsx present)
    assert.match(withDefaultExts.details, /scanned 0 files/);
    const withJsExt = checkImportBoundary({ sourceDir: 'src', forbidden: ['react'], extensions: ['.js'] });
    assert.equal(withJsExt.status, 'FAIL');
    assert.match(withJsExt.details, /react/);
  });
});

// ── checkCrossImportBan ─────────────────────────────────────────────────────────

test('checkCrossImportBan: empty pairs ERRORs instead of vacuously passing', () => {
  withRoot(() => {
    const result = checkCrossImportBan({ pairs: [] });
    assert.equal(result.status, 'ERROR');
    assert.match(result.details, /pairs is empty/);
  });
});

test('checkCrossImportBan: a pair whose sourceDir scans 0 files ERRORs (regression guard)', () => {
  withRoot((root) => {
    writeFile(root, 'apps/a/src/index.ts', 'export const x = 1;\n');
    const result = checkCrossImportBan({
      pairs: [
        { sourceDir: 'apps/a/src', forbidden: ['apps/b'] },
        { sourceDir: 'apps/typo-b/src', forbidden: ['apps/a'] },
      ],
    });
    assert.equal(result.status, 'ERROR');
    assert.match(result.details, /scanned 0 files/);
  });
});

test('checkCrossImportBan: a per-pair extensions override picks up a non-.ts/.tsx file', () => {
  withRoot((root) => {
    writeFile(root, 'apps/a/src/index.js', "import { x } from 'apps/b';\n");
    writeFile(root, 'apps/b/src/index.ts', 'export const y = 2;\n');
    const result = checkCrossImportBan({
      pairs: [
        { sourceDir: 'apps/a/src', forbidden: ['apps/b'], extensions: ['.js'] },
        { sourceDir: 'apps/b/src', forbidden: ['apps/a'] },
      ],
    });
    assert.equal(result.status, 'FAIL');
    assert.match(result.details, /cross-boundary import/);
  });
});

test('checkCrossImportBan: a real cross-app import FAILs', () => {
  withRoot((root) => {
    writeFile(root, 'apps/a/src/index.ts', 'export const x = 1;\n');
    writeFile(root, 'apps/b/src/index.ts', "import { x } from 'apps/a';\n");
    const result = checkCrossImportBan({
      pairs: [
        { sourceDir: 'apps/a/src', forbidden: ['apps/b'] },
        { sourceDir: 'apps/b/src', forbidden: ['apps/a'] },
      ],
    });
    assert.equal(result.status, 'FAIL');
    assert.match(result.details, /cross-boundary import/);
  });
});

test('checkCrossImportBan: no cross-app imports PASSes', () => {
  withRoot((root) => {
    writeFile(root, 'apps/a/src/index.ts', 'export const x = 1;\n');
    writeFile(root, 'apps/b/src/index.ts', 'export const y = 2;\n');
    const result = checkCrossImportBan({
      pairs: [
        { sourceDir: 'apps/a/src', forbidden: ['apps/b'] },
        { sourceDir: 'apps/b/src', forbidden: ['apps/a'] },
      ],
    });
    assert.equal(result.status, 'PASS');
  });
});

// ── specMatches ──────────────────────────────────────────────────────────────

test('specMatches: exact match', () => {
  assert.equal(specMatches('react', ['react']), true);
});

test('specMatches: substring match is intentional (documented "pin loosely" contract)', () => {
  assert.equal(specMatches('react-dom', ['react']), true);
  assert.equal(specMatches('apps/some-app/src', ['apps/']), true);
});

test('specMatches: no match', () => {
  assert.equal(specMatches('vue', ['react']), false);
});

// ── runChecks: ERROR vs FAIL vs PASS isolation ────────────────────────────────

test('runChecks: an unknown check type produces ERROR, not FAIL', () => {
  const [result] = runChecks([{ type: 'not-a-real-type' }]);
  assert.equal(result.status, 'ERROR');
  assert.match(result.details, /unknown check type/);
});

test('runChecks: a check whose function throws produces ERROR, not FAIL', () => {
  withRoot(() => {
    const [result] = runChecks([{ type: 'json-key-parity', files: ['missing-a.json', 'missing-b.json'] }]);
    assert.equal(result.status, 'ERROR');
    assert.match(result.details, /check threw/);
  });
});

test('runChecks: one bad check does not stop the others from running', () => {
  withRoot((root) => {
    writeJson(root, 'a.json', { x: 1 });
    writeJson(root, 'b.json', { x: 1 });
    const results = runChecks([
      { type: 'not-a-real-type' },
      { type: 'json-key-parity', files: ['a.json', 'b.json'] },
    ]);
    assert.equal(results.length, 2);
    assert.equal(results[0].status, 'ERROR');
    assert.equal(results[1].status, 'PASS');
  });
});

// ── main(): end-to-end CLI contract (argv handling, exit codes, --json shape) ──

/** Run `fn` with console.log/console.error captured instead of printed, restoring
 * both afterward regardless of how `fn` exits. */
function captureConsole(fn) {
  const logs = [];
  const errors = [];
  const prevLog = console.log;
  const prevError = console.error;
  console.log = (...args) => logs.push(args.join(' '));
  console.error = (...args) => errors.push(args.join(' '));
  try {
    const returned = fn();
    return { returned, logs, errors };
  } finally {
    console.log = prevLog;
    console.error = prevError;
  }
}

test('main: no checks configured returns 0 and prints the "none configured" message', () => {
  withRoot(() =>
    withOverlay('## Mechanical checks\n\nnothing configured yet.\n', () => {
      const { returned, logs } = captureConsole(() => main([]));
      assert.equal(returned, 0);
      assert.ok(logs.some((l) => l.includes('none configured for this repo')));
    })
  );
});

test('main: --json reports accurate pass/fail/error counts and a matching results array', () => {
  withRoot((root) =>
    withOverlay(
      [
        '## Mechanical checks',
        '',
        '```json',
        JSON.stringify({
          checks: [
            { type: 'json-key-parity', name: 'parity', files: ['a.json', 'b.json'] },
            { type: 'json-key-parity', name: 'mismatch', files: ['a.json', 'c.json'] },
            { type: 'not-a-real-type', name: 'bogus' },
          ],
        }),
        '```',
        '',
      ].join('\n'),
      () => {
        writeJson(root, 'a.json', { x: 1 });
        writeJson(root, 'b.json', { x: 1 });
        writeJson(root, 'c.json', { x: 1, y: 2 });
        const { returned, logs } = captureConsole(() => main(['--json']));
        assert.equal(returned, 0);
        const output = JSON.parse(logs.join('\n'));
        assert.equal(output.pass, 1);
        assert.equal(output.fail, 1);
        assert.equal(output.error, 1);
        assert.equal(output.results.length, 3);
        assert.deepEqual(
          output.results.map((r) => r.status),
          ['PASS', 'FAIL', 'ERROR']
        );
      }
    )
  );
});

test('main: a malformed config block returns 1 and prints an error, with no results', () => {
  withRoot(() =>
    withOverlay('## Mechanical checks\n\n```json\n{ not json }\n```\n', () => {
      const { returned, logs, errors } = captureConsole(() => main([]));
      assert.equal(returned, 1);
      assert.equal(logs.length, 0);
      assert.ok(errors.some((e) => e.includes('not valid JSON')));
    })
  );
});

test('main: the human-readable (non-JSON) table renders marks, padding, and the PASS/FAIL/ERROR summary line', () => {
  withRoot((root) =>
    withOverlay(
      [
        '## Mechanical checks',
        '',
        '```json',
        JSON.stringify({
          checks: [
            { type: 'json-key-parity', name: 'parity', files: ['a.json', 'b.json'] },
            { type: 'json-key-parity', name: 'mismatch', files: ['a.json', 'c.json'] },
            { type: 'not-a-real-type', name: 'bogus' },
          ],
        }),
        '```',
        '',
      ].join('\n'),
      () => {
        writeJson(root, 'a.json', { x: 1 });
        writeJson(root, 'b.json', { x: 1 });
        writeJson(root, 'c.json', { x: 1, y: 2 });
        const { returned, logs } = captureConsole(() => main([]));
        assert.equal(returned, 0);
        const out = logs.join('\n');
        // One row per check, each with its mark + padded status, then its details line.
        assert.match(out, /✓ PASS {2}\| parity/);
        assert.match(out, /⚠ FAIL {2}\| mismatch/);
        assert.match(out, /✗ ERROR \| bogus/);
        assert.match(out, /unknown check type: not-a-real-type/);
        assert.match(out, /1 PASS, 1 FAIL, 1 ERROR/);
      }
    )
  );
});

test('main: warns when MECHANICAL_CHECKS_ROOT/MECHANICAL_CHECKS_OVERLAY is active', () => {
  withRoot(() =>
    withOverlay('## Mechanical checks\n\nnothing configured yet.\n', () => {
      const { errors } = captureConsole(() => main([]));
      assert.ok(errors.some((e) => e.includes('MECHANICAL_CHECKS_ROOT/MECHANICAL_CHECKS_OVERLAY is set')));
    })
  );
});

// ── CLI subprocess smoke test: the real `node mechanical-checks.mjs` entry point ──

test('CLI subprocess: no checks configured exits 0', () => {
  withRoot(() =>
    withOverlay('## Mechanical checks\n\nnothing configured yet.\n', () => {
      const result = spawnSync(process.execPath, [SCRIPT_PATH], {
        encoding: 'utf8',
        env: process.env,
      });
      assert.equal(result.status, 0);
      assert.match(result.stdout, /none configured for this repo/);
    })
  );
});

test('CLI subprocess: a malformed config block exits 1', () => {
  withRoot(() =>
    withOverlay('## Mechanical checks\n\n```json\n{ not json }\n```\n', () => {
      const result = spawnSync(process.execPath, [SCRIPT_PATH], {
        encoding: 'utf8',
        env: process.env,
      });
      assert.equal(result.status, 1);
      assert.match(result.stderr, /not valid JSON/);
    })
  );
});

test('CLI subprocess: --json produces valid, well-shaped JSON on stdout', () => {
  withRoot((root) =>
    withOverlay(
      '## Mechanical checks\n\n```json\n{"checks": [{"type": "json-key-parity", "files": ["a.json", "b.json"]}]}\n```\n',
      () => {
        writeJson(root, 'a.json', { x: 1 });
        writeJson(root, 'b.json', { x: 1 });
        const result = spawnSync(process.execPath, [SCRIPT_PATH, '--json'], {
          encoding: 'utf8',
          env: process.env,
        });
        assert.equal(result.status, 0);
        const output = JSON.parse(result.stdout);
        assert.equal(output.pass, 1);
        assert.equal(output.results[0].status, 'PASS');
      }
    )
  );
});

// ── AA-7: vacuous PASS on empty input (reported by a consuming repo) ──────────
//
// `specMatches` is `forbidden.some(...)` and `[].some()` is always false, so an
// empty or absent list reported "clean" on a source dir that DOES violate.
// Deleting one line from a config turned a boundary invariant into a green tick.

test('checkImportBoundary: an empty forbidden list ERRORs instead of passing vacuously', () => {
  withRoot((dir) => {
    mkdirSync(join(dir, 'src'), { recursive: true });
    writeFileSync(join(dir, 'src', 'a.ts'), "import x from 'react';\n");
    const result = checkImportBoundary({ sourceDir: 'src', forbidden: [] });
    assert.equal(result.status, 'ERROR');
    assert.match(result.details, /forbidden is empty/);
  });
});

test('checkImportBoundary: an absent forbidden key ERRORs too', () => {
  withRoot((dir) => {
    mkdirSync(join(dir, 'src'), { recursive: true });
    writeFileSync(join(dir, 'src', 'a.ts'), "import x from 'react';\n");
    const result = checkImportBoundary({ sourceDir: 'src' });
    assert.equal(result.status, 'ERROR');
  });
});

test('checkImportBoundary: a populated forbidden list still works (non-vacuity partner)', () => {
  withRoot((dir) => {
    mkdirSync(join(dir, 'src'), { recursive: true });
    writeFileSync(join(dir, 'src', 'a.ts'), "import x from 'react';\n");
    assert.equal(checkImportBoundary({ sourceDir: 'src', forbidden: ['react'] }).status, 'FAIL');
    assert.equal(checkImportBoundary({ sourceDir: 'src', forbidden: ['vue'] }).status, 'PASS');
  });
});

test('checkCrossImportBan: an empty forbidden is caught PER PAIR, so one good pair cannot vouch for a hollow sibling', () => {
  withRoot((dir) => {
    mkdirSync(join(dir, 'a'), { recursive: true });
    mkdirSync(join(dir, 'b'), { recursive: true });
    writeFileSync(join(dir, 'a', 'x.ts'), "import q from 'vue';\n");
    writeFileSync(join(dir, 'b', 'y.ts'), "import q from 'react';\n");
    const result = checkCrossImportBan({
      pairs: [
        { sourceDir: 'a', forbidden: ['react'] },  // well-configured
        { sourceDir: 'b', forbidden: [] },         // hollow
      ],
    });
    assert.equal(result.status, 'ERROR');
    assert.match(result.details, /b/);
  });
});

test('checkDerivedKeyConsistency: a zero-key union ERRORs rather than reporting PASS (0 keys)', () => {
  withRoot((dir) => {
    // Two sources that each legitimately extract nothing. Zero keys agree
    // perfectly with zero keys and derive nothing, so every comparison loop is
    // a no-op -- the shape a silently-broken extraction pattern takes.
    writeFileSync(join(dir, 'a.json'), JSON.stringify([]));
    writeFileSync(join(dir, 'b.json'), JSON.stringify([]));
    writeFileSync(join(dir, 'en.json'), JSON.stringify({}));
    const result = checkDerivedKeyConsistency({
      sources: [
        { kind: 'json-array-field', label: 'a', file: 'a.json', field: 'name' },
        { kind: 'json-array-field', label: 'b', file: 'b.json', field: 'name' },
      ],
      deriveLocale: { template: 'x.{key}', localeFiles: ['en.json'] },
    });
    assert.equal(result.status, 'ERROR');
    assert.match(result.details, /0 keys/);
  });
});

test('checkDerivedKeyConsistency: a non-empty key union still passes (non-vacuity partner)', () => {
  withRoot((dir) => {
    writeFileSync(join(dir, 'a.json'), JSON.stringify([{ name: 'one' }]));
    writeFileSync(join(dir, 'b.json'), JSON.stringify([{ name: 'one' }]));
    writeFileSync(join(dir, 'en.json'), JSON.stringify({ 'x.one': 'One' }));
    const result = checkDerivedKeyConsistency({
      sources: [
        { kind: 'json-array-field', label: 'a', file: 'a.json', field: 'name' },
        { kind: 'json-array-field', label: 'b', file: 'b.json', field: 'name' },
      ],
      deriveLocale: { template: 'x.{key}', localeFiles: ['en.json'] },
    });
    assert.equal(result.status, 'PASS');
  });
});
