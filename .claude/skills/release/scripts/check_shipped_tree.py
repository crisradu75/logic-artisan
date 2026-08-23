#!/usr/bin/env python3
"""Refuse a release whose plugin tree carries anything a consumer cannot use.

WHY THIS EXISTS. The marketplace publishes `cla` as a `git-subdir` entry whose
descriptor supports `url`, `path`, `ref` and `sha` — and no exclusion field. The
ENTIRE subtree under `path` ships. When this check was written, 71 of the
plugin's 171 tracked files (41.5%) were validation machinery a consuming repo
could not invoke: every `tests/` tree, every mutation corpus, twelve
`pyproject.toml`, two runners, three source-repo-only markers, and one skill
whose whole subject is this plugin's own distribution. All of it reached every
consumer, and nothing detected that.

A published tag is never moved, so this runs BEFORE the tag, not after.

WHY AN ALLOWLIST, NOT A DENYLIST. The obvious check is "fail if the tree holds a
`tests/` dir, a `pyproject.toml`, a `mutants/` dir, a `*.test.mjs`, or a
`conftest.py`". Run against the tree as it stood, that denylist caught 65 of the
72 dev-only files and MISSED SEVEN: the three `SOURCE-REPO-ONLY.md`,
`check_script_drift.py`, `mutate.py`, `run_tests.py`, and `skills/release/`. Those
seven are precisely the drift this check was written to prevent — a denylist
would have reported clean on it.

The structural reason behind that measurement: what SHOULD ship is small, stable
and enumerable (14 shapes covering ~101 files); what should not is unbounded.

WHY THE PATTERNS ARE NARROW. An earlier 11-pattern draft was measured against
planted files and ACCEPTED FOUR dev-asset shapes a denylist catches:

    skills/<x>/scripts/mechanical-checks.test.mjs   `[^/]+` swallowed `.test`
    skills/<x>/scripts/conftest.py                  a legal script name
    hooks/tests/test_x.py                           `hooks/.+` — any file, any depth
    hooks/pyproject.toml                            same

So `hooks/**` is replaced by four narrow patterns covering the 15 files `hooks/`
actually holds; patterns 13 and 14 take `[^/.]+` stems, which rejects any
compound extension; and `conftest.py` is excluded by leaf name. `hooks/` is not a
waiver-worthy corner — it held 13 of the moved test files plus a `pyproject.toml`,
making it the single most likely place for a dev asset to reappear.

ENUMERATION IS `git ls-files`, NOT A WALK. `git-subdir` publishes from the
repository, so TRACKED files are exactly the files that ship. A filesystem walk
would additionally flag `__pycache__/` and `.pytest_cache/`, which the root
`.gitignore` excludes from tracking and which therefore never reach a consumer.

EXIT CONTRACT, three-valued on purpose:

    0  every enumerated file matched a pattern
    1  one or more files matched none — every offender named, in one run
    2  could not do the job: `git ls-files` failed, OR it enumerated ZERO files

Exit 2 on an empty enumeration is the load-bearing row. A scan run from the wrong
directory enumerates nothing and would otherwise report "0 violations" over a
tree it never read — the same shape as a ledger resolver that reports zero runs
and reads as a cold start.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PLUGIN_PREFIX = ".claude/plugins/cla"

EXIT_CLEAN = 0
EXIT_VIOLATIONS = 1
EXIT_CANNOT_RUN = 2

# The allowlist. Every entry carries the reason it exists, and the reason is the
# discipline rather than decoration: it is what makes a future addition arguable.
# Modelled on `test_guards_have_mutant_batches.py`'s `_EXEMPT` block, which runs
# the same convention with the same companion cap test.
#
# The list was FOURTEEN when this convention landed. A fifteenth pattern lands by
# raising the cap in `test_check_shipped_tree.py` in the SAME commit that adds
# the pattern and its reason — the cap is not a prohibition on growth, it is a
# prohibition on growth nobody argued for.
ALLOWLIST: tuple[tuple[str, str], ...] = (
    (r"README\.md",
     "The plugin's own front door; its install commands legitimately name this repo."),
    (r"\.gitattributes",
     "Carries the eol=lf pin for hooks/*.sh INSIDE the published tree, where a "
     "git-subdir install can see it."),
    (r"\.claude-plugin/plugin\.json",
     "The manifest. Exactly one file; the marketplace reads it."),
    (r"agents/[^/]+\.md",
     "Mechanical helper agents other skills delegate to."),
    (r"output-styles/[^/]+\.md",
     "The writing convention, force-for-plugin: true."),
    (r"lib/[^/]+\.py",
     "The shared ledger writer every retro-logging skill invokes as a program."),
    (r"hooks/[^/]+\.py",
     "The leaf hooks, the two dispatchers, and _dispatch_lib.py. Narrow, not "
     "hooks/**: the wide form accepted hooks/tests/test_x.py and hooks/pyproject.toml."),
    (r"hooks/hooks\.json",
     "The wiring the harness reads at load."),
    (r"hooks/[^/]+\.sh",
     "probe-python.sh, sourced by every wiring line."),
    (r"hooks/git/pre-push",
     "No extension at all — a #!/bin/sh script every clone copies into .git/hooks/."),
    (r"skills/_shared/README\.md",
     "The one README.md under skills/ that is not a skill's; _shared/ is not a skill."),
    (r"skills/[^/]+/SKILL\.md",
     "The skill itself."),
    (r"skills/[^/]+/references/[^/.]+\.(?:md|json)",
     "Supporting docs, plus the permission-set JSON files. Single-dot stem only, "
     "so a compound extension cannot slip through."),
    (r"skills/[^/]+/scripts/[^/.]+\.(?:py|mjs)",
     "Deterministic helpers a skill calls. Single-dot stem only — the wide form "
     "accepted mechanical-checks.test.mjs."),
)

# The one shape whose name is otherwise a legal script name. A pytest fixture
# module is never a shipped helper, so it is rejected by leaf name wherever it
# appears, ahead of every pattern above.
EXCLUDED_LEAF_NAMES = frozenset({"conftest.py"})

_COMPILED = tuple(re.compile(rf"^{pattern}$") for pattern, _ in ALLOWLIST)


def tracked_plugin_files(repo_root: Path) -> list[str]:
    """Plugin-root-relative paths of every TRACKED file under the plugin.

    Raises OSError/CalledProcessError upward: "git failed" is a could-not-run,
    never a clean result.
    """
    out = subprocess.run(
        ["git", "ls-files", PLUGIN_PREFIX],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if out.returncode != 0:
        raise RuntimeError(
            f"`git ls-files {PLUGIN_PREFIX}` exited {out.returncode}: "
            f"{out.stderr.strip()}"
        )
    prefix = PLUGIN_PREFIX + "/"
    return [
        line[len(prefix):]
        for line in out.stdout.splitlines()
        if line.startswith(prefix)
    ]


def is_allowed(rel: str) -> bool:
    """True when `rel` (plugin-root-relative, posix) matches a declared shape."""
    if rel.rsplit("/", 1)[-1] in EXCLUDED_LEAF_NAMES:
        return False
    return any(rx.match(rel) for rx in _COMPILED)


def violations(paths: list[str]) -> list[str]:
    """EVERY path matching no pattern, never stopping at the first.

    One run must name the whole set: a scan that reports one offender at a time
    turns a single cleanup into as many release attempts as there are files.
    """
    return sorted(rel for rel in paths if not is_allowed(rel))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    repo_root = Path(argv[0]).resolve() if argv else Path(__file__).resolve().parents[4]

    try:
        paths = tracked_plugin_files(repo_root)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"check_shipped_tree: could not enumerate the plugin tree: {exc}",
              file=sys.stderr)
        return EXIT_CANNOT_RUN

    if not paths:
        print(
            "check_shipped_tree: `git ls-files` returned ZERO files under "
            f"{PLUGIN_PREFIX} (repo root: {repo_root}). This is a could-not-run, "
            "not a clean tree — a scan that enumerated nothing has checked "
            "nothing.",
            file=sys.stderr,
        )
        return EXIT_CANNOT_RUN

    offenders = violations(paths)
    if offenders:
        print(
            f"check_shipped_tree: {len(paths)} files, {len(ALLOWLIST)} patterns, "
            f"{len(offenders)} violation(s)"
        )
        for rel in offenders:
            print(f"{PLUGIN_PREFIX}/{rel}")
        print(
            "\nThe marketplace publishes this directory whole — git-subdir has no "
            "exclusion field — so each file above would ship to every consuming "
            "repo, and a published tag is never moved. Move it out of the plugin, "
            "or add a pattern AND its reason to ALLOWLIST and raise the cap in "
            "plugin-tests/tests/skills/release/test_check_shipped_tree.py in the "
            "same commit.",
            file=sys.stderr,
        )
        return EXIT_VIOLATIONS

    print(
        f"check_shipped_tree: {len(paths)} files, {len(ALLOWLIST)} patterns, "
        "0 violations"
    )
    return EXIT_CLEAN


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
