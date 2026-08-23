"""Mutation batch for check_shipped_tree.py — break each guarantee, confirm a test fails.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/release/test_check_shipped_tree.py

Mutating what the scan TOUCHES, not only what it targets. CLAUDE.md records two
commits that each said "three mutations checked, all caught" and each shipped a
critical, because the mutants covered the branch the author was reasoning about
and not the branch they got wrong. So the set below deliberately includes the
three-valued exit contract and the report-all loop, not just the pattern list:

  1. the empty-enumeration branch — the whole non-vacuity guarantee. If this
     returns CLEAN, a scan run from the wrong directory reports "0 violations"
     over a tree it never read.
  2. an anchor dropped from one pattern — the silent WIDENING that a hand-typed
     regex reintroduces every release.
  3. the `[^/.]+` stem widened to `[^/]+` — the exact defect measured on the
     11-pattern draft, which accepted `mechanical-checks.test.mjs`.
  4. the report-all loop given an early exit — one offender named per run turns a
     single cleanup into as many release attempts as there are files.
  5. the conftest.py leaf-name exclusion neutered — the one dev-asset shape whose
     name is otherwise a legal script name.
  6. the test_*.py / *_test.py leaf-shape exclusion widened to never match — the
     hole a review measured directly: `skills/foo/scripts/test_foo.py`,
     `hooks/test_x.py`, and `lib/test_x.py` all returned ALLOW before this
     exclusion existed, because a pytest module is exactly a denylist shape and
     matches pattern 14 (or the hooks/lib patterns) just as legitimately as a
     real helper does.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
REPO = DEV.parent
SCAN = REPO / ".claude" / "skills" / "release" / "scripts" / "check_shipped_tree.py"

TARGETS = [DEV / "tests" / "skills" / "release"]

# `mutate.py` reads `read_bytes().decode()`, so line endings survive verbatim and
# a hardcoded `\n` does not match a CRLF checkout. Read the separator off the
# file rather than assuming it: a wrong guess fails the preflight loudly, but
# only after someone has spent a round wondering why.
_NL = "\r\n" if b"\r\n" in SCAN.read_bytes() else "\n"

MUTANTS = [
    (
        "an empty enumeration reports clean instead of could-not-run",
        SCAN,
        _NL.join(["            file=sys.stderr,", "        )", "        return EXIT_CANNOT_RUN", "", "    offenders"]),
        _NL.join(["            file=sys.stderr,", "        )", "        return EXIT_CLEAN", "", "    offenders"]),
        TARGETS,
    ),
    (
        "the SKILL.md pattern loses its end anchor, so SKILL.md.bak ships",
        SCAN,
        '_COMPILED = tuple(re.compile(rf"^{pattern}$") for pattern, _ in ALLOWLIST)',
        '_COMPILED = tuple(re.compile(rf"^{pattern}") for pattern, _ in ALLOWLIST)',
        TARGETS,
    ),
    (
        "the scripts pattern stem widens, re-accepting mechanical-checks.test.mjs",
        SCAN,
        r'(r"skills/[^/]+/scripts/[^/.]+\.(?:py|mjs)",',
        r'(r"skills/[^/]+/scripts/[^/]+\.(?:py|mjs)",',
        TARGETS,
    ),
    (
        "the references pattern stem widens, re-accepting a compound extension",
        SCAN,
        r'(r"skills/[^/]+/references/[^/.]+\.(?:md|json)",',
        r'(r"skills/[^/]+/references/[^/]+\.(?:md|json)",',
        TARGETS,
    ),
    (
        "the report-all loop stops at the first offender",
        SCAN,
        "    return sorted(rel for rel in paths if not is_allowed(rel))",
        "    return sorted(rel for rel in paths if not is_allowed(rel))[:1]",
        TARGETS,
    ),
    (
        "the conftest.py leaf-name exclusion is neutered",
        SCAN,
        'EXCLUDED_LEAF_NAMES = frozenset({"conftest.py"})',
        "EXCLUDED_LEAF_NAMES = frozenset()",
        TARGETS,
    ),
    (
        "hooks/ reverts to the wide pattern that accepted hooks/tests/test_x.py",
        SCAN,
        r'(r"hooks/[^/]+\.py",',
        r'(r"hooks/.+",',
        TARGETS,
    ),
    (
        "the test_*.py / *_test.py leaf-shape exclusion never matches, "
        "re-accepting a pytest module as a shipped script",
        SCAN,
        r'_EXCLUDED_LEAF_PATTERN = re.compile(r"^(?:test_.+|.+_test)\.(?:py|mjs)$")',
        r'_EXCLUDED_LEAF_PATTERN = re.compile(r"(?!x)x")',
        TARGETS,
    ),
]
