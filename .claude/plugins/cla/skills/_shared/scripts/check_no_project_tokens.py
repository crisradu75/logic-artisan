#!/usr/bin/env python3
"""Conformance guard: no project-specific tokens in synced core.

A generic, repo-agnostic checker enforcing the cla plugin's fact/procedure
separation (``cla-overlay-convention`` + ``cla-skill-context-extraction``): a
project-specific token must live behind an overlay (``project-context.md`` /
``*.local.md``), never baked into a synced-core ``SKILL.md`` or
``references/**/*.md``, or the marketplace install would carry it verbatim into
every destination repo. The token list itself is a per-repo overlay
(``project-tokens.local.md``) read as data — the checker hard-codes no token.

The checker obeys the same split it enforces: generic *procedure* (this file,
distributed to every repo) + a repo-specific *fact* (the token list, which lives
in the repo's own ``cla.io/`` tree and is never distributed).

It lives in ``skills/_shared/`` — the shared area that belongs to no single
skill — because it enforces a rule about the WHOLE plugin. It reads the
CONSUMING repo's data, which is why it is a skill helper rather than a test: a
consuming repo has no test gate over the plugin cache, so a checker filed as a
pytest module is unreachable there in practice.

RUN IT AS A PROGRAM, from anywhere inside the repo it should check::

    python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/check_no_project_tokens.py

FOUR CHECKS, ALL IN ONE RUN. A single invocation performs every check this guard
is responsible for and never stops at the first that fails — surfacing one
violation at a time turns a run into a fix-and-rerun loop:

  (a) the PROSE scan for project tokens over synced-core ``SKILL.md`` and
      ``references/**/*.md``;
  (b) the SOURCE scan for project tokens over the plugin's scanned source roots
      (``.py`` and ``.json`` everywhere, plus ``agents/*.md`` and
      ``output-styles/*.md``);
  (c) the hardcoded absolute-DEVELOPER-PATH scan over that same source — a
      different scanner with its own regexes and its own exemption marker, and
      the only one of the four that needs no token list;
  (d) the READABILITY check that every file the scans claim to have inspected
      was actually readable.

Check (d) is not optional and is not plumbing. All three scanners above swallow
a decode/IO error per file so one odd file cannot take the guard down — which
means an unreadable file returns "no violations", exactly what a clean file
returns. (d) is what keeps the other three from passing vacuously.

EXIT CODES:
  - ``0`` — clean, or a trivial pass. One summary line names what was scanned and
    how many files, so a scan that inspected nothing is visible rather than
    indistinguishable from a clean result. A trivial pass states its reason.
  - ``1`` — violations found. Each is named with its repo-relative path, the
    matched token (or leak kind), the line number and an excerpt, one per line.
  - ``2`` — the checker could not do its job: bad arguments, a repo root that
    could not be resolved at all, an input that exists but cannot be read, a
    scan root that yielded zero files (checked on its own evidence — never
    gated on whether a token list happened to load, since checks (c)/(d) read
    the same file lists and need no list at all), or an expected source scan
    root missing entirely (a partial/broken install). Diagnostic goes to
    stderr. **Confirmed violations win when both are true in the same run** —
    if any violation was found, the run exits ``1`` and reports the blocker(s)
    too, rather than exiting ``2`` and letting "I could not look" mask "I found
    problems".

ABSENT VS. EMPTY TOKEN LIST. No token-list overlay → checks (a) and (b) are a
stated trivial pass; (c) and (d) still run, because neither needs a list and a
fresh repo is not a reason to stop checking for a leaked developer path. An
overlay that is PRESENT but yields no tokens → a violation: a populated list
broken by a later formatting change is a defect, not a fresh repo, and silently
skipping it would disable the safety check with no signal. Deleting the file is
the way to intentionally disable it.

``--repo-root <path>`` overrides the default self-resolution of the repo whose
token list is read (git, then a non-global ``.claude`` walk; exits 2 if neither
resolves — never a silent ``cwd`` fallback, which used to report a wrong root
as clean). When the plugin is vendored inside that repo, the tree scanned is
that repo's copy; otherwise the checker scans its own plugin root, as it does
under a marketplace install. The flag exists so the CLI layer is testable
against a temporary tree; the skills invoke the bare form.

The unit tests of every function below live in the canonical source repo's own
development tree, at ``plugin-tests/tests/conformance/test_no_project_tokens.py``,
which loads this file by path. They are not shipped: the plugin carries only
assets a consuming repo can use.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

OVERLAY_FILE_NAME = "project-context.md"
OVERLAY_LOCAL_SUFFIX = ".local.md"
EXCLUDED_SUBTREES = frozenset({"tests", "scripts"})
# Token-list overlay, relative to the REPO root — it is per-repo data, so it
# lives in `cla.io/` with the rest of it rather than inside the plugin tree.
# Being outside the synced core also means neither scan below can reach it, so
# it cannot flag its own contents.
TOKEN_LIST_RELPATH = Path("cla.io") / "project-tokens.local.md"
MAX_EXCERPT = 120


def _plugin_root() -> Path:
    """Resolve the plugin's own root directory from this file's own location — a
    fixed internal layout identical in every repo, with no repo-specific absolute
    path or repository name baked in."""
    for parent in Path(__file__).resolve().parents:
        if parent.name == "cla" and parent.parent.name == "plugins":
            return parent
    # Fallback for an unexpected layout: scripts/ -> _shared/ -> skills/ -> cla/
    # The depth and this comment are one fact written twice; the comment is what
    # makes the depth checkable. It was `parents[2]` while this checker lived
    # among the plugin's own guard tests, two levels below the plugin root. From
    # here that lands on `skills/`, not the plugin root. The primary
    # walk above still succeeds in every normal layout, so the wrong depth would
    # have failed silently and ONLY in the unexpected-layout case this fallback
    # exists to cover.
    return Path(__file__).resolve().parents[3]


def _repo_root() -> Path | None:
    """The repo being checked — asked of git, from the PROCESS's cwd. Returns
    ``None`` when resolution genuinely fails (no git, no non-global ``.claude``
    ancestor) — the caller must treat that as ``EXIT_CANNOT_RUN``, never fall
    back to a silent ``Path.cwd()`` that reports a wrong root as clean.

    The token list is per-repo data in `cla.io/`, so the anchor must be the
    consuming repo. This used to walk to the first `.claude` ancestor of
    `__file__`, which under a marketplace install is the user's GLOBAL
    `~/.claude` — so it returned the home directory, found no token list, and
    the guard skipped green in every consuming repo (upstream issue #52).
    """
    import subprocess

    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    home_claude = (Path.home() / ".claude").resolve()
    for parent in Path(__file__).resolve().parents:
        if parent.name == ".claude" and parent.resolve() != home_claude:
            return parent.parent
    # Nothing resolved. Previously fell back to `Path.cwd()`, which reported an
    # unresolved root as a trivial CLEAN pass over whatever directory happened
    # to be current.
    return None


def load_tokens(path: Path) -> list[str]:
    """Parse the markdown token-list overlay into a list of tokens.

    One token per ``- ``/``* `` bullet (the text after the marker, trimmed, with
    an optional trailing `` # comment`` and surrounding backticks stripped).
    ``#`` headings, blank lines, and ``<!-- ... -->`` comment lines are ignored.
    A missing file yields ``[]`` (trivial pass — see the main test)."""
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    # Strip HTML comment spans FIRST — they may span multiple lines and legitimately
    # contain `- `/`* ` bullets (e.g. this overlay's "excluded candidates" block),
    # which MUST NOT be parsed as tokens. Line-by-line skipping alone can't do this.
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    tokens: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- ") or line.startswith("* "):
            body = line[2:]
            # Strip an inline trailing "token  # why" comment. (A token containing a
            # literal '#' — a hex color, an anchor — is unsupported by this split, but
            # none is needed for the compound repo tokens this list holds.)
            if "#" in body:
                body = body.split("#", 1)[0]
            body = body.strip().strip("`").strip()
            if body:
                tokens.append(body)
    return tokens


def _is_overlay(path: Path) -> bool:
    leaf = path.name.lower()
    return leaf == OVERLAY_FILE_NAME or leaf.endswith(OVERLAY_LOCAL_SUFFIX)


def _iter_scanned_files(skills_root: Path):
    """Yield every ``SKILL.md`` + ``references/**/*.md`` under ``skills/**``,
    excluding overlay files and the ``tests/``/``scripts/`` subtrees."""
    if not skills_root.is_dir():
        return
    for path in sorted(skills_root.rglob("*.md")):
        if not path.is_file() or _is_overlay(path):
            continue
        ancestors = path.relative_to(skills_root).parts[:-1]
        if any(part in EXCLUDED_SUBTREES for part in ancestors):
            continue
        if path.name == "SKILL.md" or "references" in ancestors:
            yield path


def _body_lines(text: str, strip_frontmatter: bool):
    """Yield ``(1-based line number, line text)`` for a file's body, optionally
    skipping a leading YAML frontmatter block (``---`` ... ``---``) for MATCHING
    while keeping line numbers accurate. A skill's ``description:``/``argument-hint:``
    frontmatter legitimately names the host repo so the skill triggers — it is
    metadata, not portable procedure prose. ``strip_frontmatter`` is True ONLY for
    ``SKILL.md`` (the only file type that carries frontmatter); for a ``references``
    ``.md`` a leading ``---`` is a Markdown horizontal rule, never a frontmatter
    fence, so its body must not be silently exempted."""
    lines = text.splitlines()
    start = 0
    if strip_frontmatter and lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start = i + 1
                break
    for idx in range(start, len(lines)):
        yield idx + 1, lines[idx]


def _violations_in(path: Path, rel: str, lowered: list[tuple[str, str]], strip_fm: bool):
    """Token hits in one file's body, as ``(rel, token, line_number, excerpt)``."""
    found: list[tuple[str, str, int, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # A binary or unreadable file is not prose and not source we can check.
        # Swallowed so one odd file cannot take the guard down — but silence
        # here would mean the guard quietly stops covering that file, so
        # `test_every_scanned_file_is_actually_readable` asserts separately that
        # the set of unreadable files is empty.
        return found
    for lineno, line in _body_lines(text, strip_fm):
        haystack = line.lower()
        for tok, tok_l in lowered:
            if tok_l in haystack:
                excerpt = line.strip()
                if len(excerpt) > MAX_EXCERPT:
                    excerpt = excerpt[: MAX_EXCERPT - 3] + "..."
                found.append((rel, tok, lineno, excerpt))
    return found


def find_violations(skills_root: Path, report_root: Path, tokens: list[str]):
    """Return ``(rel_path, token, line_number, excerpt)`` for every case-insensitive
    literal-substring token hit in a scanned file's body. ``rel_path`` is reported
    relative to ``report_root`` (the plugin root in the real run)."""
    lowered = [(tok, tok.lower()) for tok in tokens]
    violations: list[tuple[str, str, int, str]] = []
    for path in _iter_scanned_files(skills_root):
        rel = path.relative_to(report_root).as_posix()
        violations.extend(
            _violations_in(path, rel, lowered, strip_fm=path.name == "SKILL.md")
        )
    return violations


# ---------- source-file scan: the prose guard's blind spots ----------
#
# The scan above deliberately covers PROSE only — `SKILL.md` and
# `references/**/*.md` under `skills/`. A real leak sat outside it on three
# independent counts at once, which is why it went unnoticed through several
# passes:
#
#   1. `.py` files. The prose scan globs `*.md`; a token in a Python string
#      literal or docstring was never in scope.
#   2. `tests/` and `scripts/`. Both are in `EXCLUDED_SUBTREES`, on the
#      reasoning that they carry no portable prose. They carry portable
#      STRINGS, and the install ships them to every destination repo just
#      the same.
#   3. `hooks/`, `agents/`, and `output-styles/`. None lives under `skills/`,
#      so all three are outside the prose scan's root entirely.
#
# Kept as a separate scanner rather than widening the one above, because the
# rules genuinely differ: the prose guard's frontmatter exemption exists for a
# `SKILL.md` `description:` that legitimately names the host repo so the skill
# triggers, which has no analogue in a `.py` file.

# The categories this guard keeps clean: the four dirs holding portable
# procedure that a consuming repo executes.
#
# This list was once DERIVED from `update-cla`'s `discover.SCAN_DIRS`, because a
# hand-typed copy here and a second one in the sync tool's tests BOTH missed
# `output-styles` when it was added to the real list — caught by review, not by
# any test, since every test against the stale copies stayed green. A comparison
# test guarded that drift until file-sync distribution was removed; with the
# sync tool deleted there is nothing left to compare against, so the list stands
# on its own and any new synced root must be added here by hand.
#
# These roots cover everything the marketplace publishes that this guard can
# meaningfully scan. The install ships the plugin dir as its `path` — the WHOLE
# directory — so the four "portable procedure" roots are not quite the whole
# shipped surface: `lib/` reaches a consuming repo too, and is scanned here.
#
# This list was EIGHT until `extract-dev-tree-from-plugin` moved the plugin's
# own validation machinery to `<repo>/plugin-tests/`. The three `*-checks/`
# scopes it also named no longer exist inside the plugin, and a root that is
# not a directory is skipped by `_iter_scanned_source_files`. Left in place
# they made `_missing_source_roots` fire on every install, so the shipped
# guard refused to run at all (exit 2) in every consuming repo. Pruned to the
# five roots that actually ship.
#
# SOME shipped `.md`/`.py` files fall outside both scanners above. Which ones is
# NOT written here. It was — as a list and a count, "counted, not estimated" —
# and the count went stale while nothing noticed, twice, in this comment and in
# CLAUDE.md. Checking a hand-written list once is not a mechanism; the next
# rename falsifies it silently, because a file no scanner opens returns exactly
# what a clean file returns.
#
# The canonical-source repo's `TOKEN_EXEMPT` map, in
# `plugin-tests/tests/conformance/test_shipped_files_are_scanned.py`, derives the
# split instead: every shipped `.md`/`.py` must be reached by a scanner above or
# carry a stated reason there, and an exemption whose file was deleted or has
# since been picked up fails too. Read that map for the current list.
#
# A deliberate path-parsing fixture stays scannable by carrying the
# `path-fixture-ok` marker on its line, rather than by exempting a whole file.
SOURCE_SCAN_ROOTS = (
    "skills",
    "agents",
    "hooks",
    "output-styles",
    "lib",
)
CACHE_DIRS = frozenset({"__pycache__", ".pytest_cache"})


def _missing_source_roots(plugin_root: Path) -> list[str]:
    """`SOURCE_SCAN_ROOTS` entries that are not a directory under `plugin_root`.

    All five ship as part of the same plugin directory in every install (the
    marketplace publishes the whole tree verbatim), so a root's absence here
    means a broken/partial install, not a smaller shipped surface. Without this,
    `_iter_scanned_source_files`'s `if not root.is_dir(): continue` skips an
    absent root SILENTLY — only reached roots were ever named, never
    expected-but-absent ones — so a heavy coverage loss (a whole scan root
    missing) still exits 0 clean."""
    return [name for name in SOURCE_SCAN_ROOTS if not (plugin_root / name).is_dir()]


def _iter_scanned_source_files(plugin_root: Path):
    """Yield every synced-core SOURCE file the prose scan cannot see.

    `.py` and `.json` anywhere under the synced roots (including `tests/` and
    `scripts/`), plus every `.md` under `agents/` or `output-styles/` (agent
    definitions and output-style files, neither reachable from the prose scan's
    `skills/` root). Overlays stay exempt by the same convention, and
    bytecode/cache directories are skipped — a stale `.pyc` still holds the
    string it was compiled from and would report a leak already fixed in source.

    `.json` was added last, and for one file rather than for tidiness.
    `skills/_shared/references/required-permissions.json` carries English prose
    in its `_comment` keys and already contained a phrase naming the workflow it
    serves "in this repo" — prose in synced core is precisely what this guard
    exists to catch, and no scanner opened it. The suffix reaches three shipped
    files in total (that one, its `-narrow` sibling under `spec-to-pr`, and
    `hooks/hooks.json`), identical in every install, so the widening adds no
    per-repo surface beyond those three. `.claude-plugin/plugin.json` is NOT
    among them: it sits outside every entry in `SOURCE_SCAN_ROOTS`, and is
    covered instead by the marketplace-manifest guard in the source repo.

    Not widened to `.sh` or to the suffix-less `hooks/git/pre-push`: neither has
    a demonstrated leak, and a suffix-less file needs a rule that is not keyed on
    suffix at all. Both are recorded as deliberate exemptions rather than
    oversights — see the source repo's `EXEMPT` map, which fails on an exemption
    a scanner has since grown to reach.
    """
    md_roots = ("agents", "output-styles")
    for root_name in SOURCE_SCAN_ROOTS:
        root = plugin_root / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or _is_overlay(path):
                continue
            if any(part in CACHE_DIRS for part in path.relative_to(root).parts):
                continue
            if path.suffix in (".py", ".json") or (
                root_name in md_roots and path.suffix == ".md"
            ):
                yield path


def find_source_violations(plugin_root: Path, tokens: list[str]):
    """`find_violations`'s counterpart over source files. Same result shape."""
    lowered = [(tok, tok.lower()) for tok in tokens]
    violations: list[tuple[str, str, int, str]] = []
    for path in _iter_scanned_source_files(plugin_root):
        rel = path.relative_to(plugin_root).as_posix()
        # An `agents/*.md` or `output-styles/*.md` frontmatter `description:` can
        # legitimately name the host repo (an agent that triggers on it, a style
        # description shown in the picker), the same reason a `SKILL.md` one does
        # — so both get the same exemption. A `.py` file has no frontmatter concept.
        violations.extend(
            _violations_in(path, rel, lowered, strip_fm=path.suffix == ".md")
        )
    return violations


# ---------- absolute-path guard: the list-free half ----------
#
# Both guards above need a curated `project-tokens.local.md` to do anything, and
# that model fits a CONSUMING repo most obviously, where the list is closed and
# self-known: you know your own project's vocabulary.
#
# This comment used to continue "In the SOURCE repo it inverts — there are no
# local product tokens to protect", and on that reasoning the source repo
# curated no list at all. The reasoning conflated two lists, and the half it got
# wrong shipped six leaks: the source repo's own name and one of its internal
# systems, both named inside portable core, plus a consuming repo's name in a
# docstring that then failed THAT repo's guard on arrival. (Naming any of them
# here would itself trip the guard — which is the shortest possible proof that
# the second list below is real.)
#
#   - Names of OTHER repos, arriving via pasted examples and fixtures. Listing
#     those does mean enumerating every repo the author works in: open-ended,
#     externally determined, stale the moment a new project starts, and it
#     catches only the names you already know — which are the ones you already
#     fixed. That objection stands, and the list-free path guard below is the
#     answer to it.
#   - The source repo's OWN name and systems. Closed, finite, self-known —
#     exactly like a consuming repo's vocabulary. A source repo does know what
#     it is called, and a source-side token is the more damaging of the two,
#     because once synced it reads as a fact about the DESTINATION.
#
# So the guards above are armed in both directions; only the list's contents
# differ per repo, which is what makes it an overlay.
#
# What still has no mechanical guard, stated so nobody assumes otherwise: prose
# that names no token but asserts a source-repo FACT — "this repo ships no
# product code", "this repo is on Windows". Measured before ruling it out: the
# synced tree has 113 occurrences of "this repo", and the overwhelming majority
# are legitimate deictics that re-bind per repo (`ask-git-identity`'s "this repo
# has no `user.email` configured" is about whatever repo is running it). No
# pattern separates those from a leak, so this class is watched by review, not
# by a test.
#
# This check needs no list. A synced-core file has no business carrying a
# hardcoded absolute DEVELOPER path — whatever repo or user it names — because
# such a path cannot be correct in any destination repo. That is closed-form,
# so it catches a name nobody has ever seen before. It is also what would
# actually have caught the real leak, which was mostly absolute paths.
#
# Tuned against the real tree rather than synthetic cases only. Two findings
# from that pass, both of which a synthetic-only rule would have shipped:
#   - A naive drive-letter pattern matches `https://…`, because `s:` followed
#     by `//` satisfies it. Hence the `(?<![A-Za-z0-9])` guard.
#   - Every remaining hit was a LEGITIMATE fixture (path-parsing tests need
#     realistic absolute paths). Hence the marker below rather than a blanket
#     ban or a `tests/` exemption — `tests/` is exactly where the real leak was.

ABS_PATH_EXEMPT_MARKER = "path-fixture-ok"
PLACEHOLDER_USERS = frozenset({
    "me", "you", "user", "username", "someuser", "someone", "dev",
})
# Separator-stripped Windows path (`C:UsersaliceAppData...`, path-fixture-ok). The shape
# `warn-stray-scratch-artifact.py` exists to parse, so its fixtures carry it —
# and with the separators gone neither pattern below can see it, which is
# exactly how a real developer username survived the previous sweep.
MANGLED_WIN_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:Users([A-Za-z0-9]+)")
# Single drive letter, NOT preceded by another alnum (or a URL scheme matches).
# Consumes the whole path-ish run, so the placeholder test below can inspect it.
#
# TWO separators are required, not one, and that is the fix for a real false
# positive rather than a tightening for its own sake. With one separator the
# pattern matched the tail of any Python source line ending a clause with a
# name: `except OSError as e:` followed by an escaped newline reads as drive
# `E:` + path `\n`, and `print("a:\tb")` reads as drive `A:` + path `\tb`. Both
# lines contain no path at all. A hardcoded developer path — the only thing this
# guard exists to catch — always has a second segment (`C:\Users\alice\...`),
# while an escape sequence never does, so the separator count separates them
# cleanly where a character-class tweak could not: `\t` is equally the start of
# `C:\temp` and of a tab.
WIN_ABS_PATH = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]{1,2}[A-Za-z0-9._<>-]+[\\/]{1,2}[A-Za-z0-9._<>\\/-]*"
)
HOME_ABS_PATH = re.compile(r"(?:^|[\s\"'`(])/(?:Users|home)/([A-Za-z0-9._-]+)/")
# `C:\Code\<repo>\...` and `C:\Users\...\AppData\...` are illustrative prose, not
# paths anyone could run. Exempt automatically — reserving the explicit marker for
# fixtures that genuinely need a REAL-looking absolute path (parser tests), so the
# marker keeps meaning "a human decided this one is fine" instead of becoming noise.
PLACEHOLDER_PATH_HINTS = ("<", "...")


def _starts_with_placeholder_user(segment: str) -> bool:
    """Whether a separator-stripped run begins with an obvious placeholder name.

    With the separators gone the username cannot be delimited, so the run is
    tested by prefix: ``someuserAppDataLocal`` is a placeholder, ``aliceAppData``
    names a real person.
    """
    low = segment.lower()
    return any(low.startswith(p) for p in PLACEHOLDER_USERS)


def find_absolute_path_leaks(plugin_root: Path):
    """Return ``(rel_path, kind, line_number, excerpt)`` per hardcoded absolute
    developer path in a synced-core source file.

    A line carrying ``path-fixture-ok`` is exempt — the declared way to keep a
    deliberate path-parsing fixture. A home path whose user segment is an
    obvious placeholder (``/Users/me/``) is exempt without a marker, since it
    names nobody.
    """
    leaks: list[tuple[str, str, int, str]] = []
    for path in _iter_scanned_source_files(plugin_root):
        rel = path.relative_to(plugin_root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if ABS_PATH_EXEMPT_MARKER in line:
                continue
            # Each shape is tested INDEPENDENTLY. An `elif` chain here meant a
            # line carrying a placeholder Windows path skipped the home-path
            # check entirely, so a real `/Users/<name>/` on that same line
            # shipped unreported.
            kinds: list[str] = []
            win = WIN_ABS_PATH.search(line)
            if win and not any(h in win.group(0) for h in PLACEHOLDER_PATH_HINTS):
                kinds.append("windows-drive-path")
            home = HOME_ABS_PATH.search(line)
            if home and home.group(1).lower() not in PLACEHOLDER_USERS:
                kinds.append("home-directory-path")
            mangled = MANGLED_WIN_PATH.search(line)
            if mangled and not _starts_with_placeholder_user(mangled.group(1)):
                kinds.append("mangled-windows-path")
            for kind in kinds:
                excerpt = line.strip()
                if len(excerpt) > MAX_EXCERPT:
                    excerpt = excerpt[: MAX_EXCERPT - 3] + "..."
                leaks.append((rel, kind, lineno, excerpt))
    return leaks


def find_unreadable_files(plugin_root: Path):
    """Every scanned file that cannot be decoded as UTF-8, as ``(rel, reason)``.

    All three scanners swallow a decode/IO error per file so one odd file cannot
    take the whole guard down. That is the right robustness choice and the wrong
    reporting one: an unreadable file returns "no violations", which is exactly
    what a clean file returns. The counters the scanners assert on
    (``assert scanned``) count files ITERATED, not files READ, so every file in
    the tree could fail to decode and every guard would still pass green.
    """
    bad: list[tuple[str, str]] = []
    seen: set[Path] = set()
    for path in list(_iter_scanned_files(plugin_root / "skills")) + list(
        _iter_scanned_source_files(plugin_root)
    ):
        if path in seen:
            continue
        seen.add(path)
        try:
            path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            bad.append((path.relative_to(plugin_root).as_posix(), type(exc).__name__))
    return bad


# ---------- the guard, as a program ----------

EXIT_CLEAN = 0
EXIT_VIOLATIONS = 1
EXIT_CANNOT_RUN = 2

_PROG = "check_no_project_tokens"


def _force_utf8_streams() -> None:
    """Make stdout/stderr able to carry this checker's own report.

    The violation format carries a ``→``, and a Windows console defaults to a
    legacy code page that cannot encode it — so the program died with
    ``UnicodeEncodeError`` instead of printing its findings. Invisible while the
    guard was a pytest module (pytest encodes its own failure messages); a
    first-run crash the moment it became a program. A repo-relative path with a
    non-ASCII segment would do the same to either checker.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:  # pragma: no cover - not a TextIOWrapper
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):  # pragma: no cover - defensive
            pass


def _vendored_plugin_root(repo_root: Path) -> Path | None:
    """The plugin tree inside ``repo_root``, when it is vendored there.

    Written as path components rather than as one literal string on purpose: a
    sibling conformance guard fails any synced-core file that spells the install
    path out, because that path resolves only in the repo that develops the
    plugin. Returns ``None`` under a marketplace install, where the plugin lives
    in a version-keyed cache outside the repo entirely.
    """
    candidate = repo_root / ".claude" / "plugins" / "cla"
    return candidate if candidate.is_dir() else None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=_PROG,
        description=(
            "Fail when a synced-core file leaks a project-specific token or a "
            "hardcoded absolute developer path, or when a file the scans claim "
            "to have inspected cannot actually be read."
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help=(
            "The repo whose token-list overlay is read. Defaults to the "
            "process's own repo (git, then a non-global `.claude` walk; exits 2 "
            "if neither resolves)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run all four checks as one program and return the exit code.

    This carries the four assertions the original pytest module made against the
    real repo — `test_no_project_tokens_in_synced_core`,
    `test_no_project_tokens_in_synced_source`,
    `test_no_absolute_developer_paths_in_synced_source` and
    `test_every_scanned_file_is_actually_readable` — with pytest's skip/fail
    replaced by the pinned exit-code contract in the module docstring.

    Violations accumulate ACROSS all four checks. There is no short-circuit: the
    original guards' "surface all violations in a single run" rule exists
    because a fix-one-rerun loop wastes a consumer's time, and check (d) in
    particular is invisible to every other assertion, so skipping it because an
    earlier check already reported would hide the one that keeps the rest
    honest.
    """
    _force_utf8_streams()
    # argparse exits 2 on a bad argument, which is already this program's
    # "could not do its job" code — a bad invocation is not a clean result.
    args = _build_parser().parse_args(argv)

    if args.repo_root is None:
        repo_root = _repo_root()
        plugin_root = _plugin_root()
    else:
        repo_root = Path(args.repo_root)
        if not repo_root.is_dir():
            print(
                f"{_PROG}: --repo-root {args.repo_root!r} is not a directory",
                file=sys.stderr,
            )
            return EXIT_CANNOT_RUN
        plugin_root = _vendored_plugin_root(repo_root) or _plugin_root()

    skills_root = plugin_root / "skills"
    # `repo_root` is needed ONLY to locate the consuming repo's token list, i.e.
    # for checks (a) and (b). Checks (c) absolute-developer-paths and (d)
    # readability read `plugin_root`, already resolved from `__file__`.
    token_path = None if repo_root is None else repo_root / TOKEN_LIST_RELPATH

    notes: list[str] = []
    blockers: list[str] = []
    violations: list[str] = []

    tokens: list[str] = []
    if token_path is None:
        # `_repo_root()` could not resolve anything at all (no git, no non-global
        # `.claude` ancestor). It used to fall back to `Path.cwd()`, which
        # reported a WRONG root as a trivial clean pass; never let an unresolved
        # root produce a clean verdict — so this is a BLOCKER.
        #
        # It is not, however, a reason to stop: returning here short-circuited
        # (c) and (d), which need no repo root, so a real absolute-path leak or
        # an unreadable synced file was masked by "I could not look". That is the
        # same blocker-outranks-violations inversion the precedence rule below
        # exists to prevent, reached one step earlier.
        blockers.append(
            "could not resolve the repo root — not inside a git working tree, "
            "and no non-global .claude ancestor found; the two token scans "
            "could not run (pass --repo-root explicitly). Checks (c) and (d) "
            "still ran against the plugin tree."
        )
    elif not token_path.is_file():
        # A fresh destination repo has installed the guard but not curated a
        # token list yet — trivial pass for the two token scans, NOT for (c) and
        # (d), neither of which needs a list.
        notes.append(
            f"no {TOKEN_LIST_RELPATH.as_posix()} overlay present — the two token "
            "scans are a trivial pass; each destination repo curates its own "
            "token list"
        )
    else:
        try:
            tokens = load_tokens(token_path)
        except (OSError, UnicodeDecodeError) as exc:
            blockers.append(
                f"{token_path} exists but could not be read "
                f"({type(exc).__name__}: {exc}) — no token verdict is reported"
            )
        else:
            if not tokens:
                # The file EXISTS but parses to zero tokens. That is a defect (a
                # broken/reformatted list), not a fresh repo — report it rather
                # than silently disabling the guard.
                violations.append(
                    f"{token_path.name} exists but yields no tokens — likely a "
                    "formatting error (each token must be a `- token` / `* token` "
                    "bullet). Delete the file to intentionally disable the guard."
                )

    prose_files = list(_iter_scanned_files(skills_root))
    source_files = list(_iter_scanned_source_files(plugin_root))
    missing_source_roots = _missing_source_roots(plugin_root)

    # ---- (a) prose scan ----
    # The zero-files blocker fires on ITS OWN evidence (the scan found nothing),
    # never gated on `tokens` — checks (c)/(d) below read the SAME `prose_files`/
    # `source_files` lists and need no token list at all, so a broken scan root
    # was previously invisible to them whenever no token list happened to be
    # present. Only the VIOLATION search (which needs something to search for)
    # stays gated on `tokens`.
    if not prose_files:
        blockers.append(
            f"guard scanned zero files under {skills_root} — the scan root or "
            "filters may be broken (a scan with nothing to check is a silent "
            "no-op for every one of the four checks, not only the token scans)"
        )
    if tokens:
        for rel, tok, lineno, excerpt in find_violations(skills_root, plugin_root, tokens):
            violations.append(f"{rel}:{lineno}  token {tok!r}  → {excerpt}")

    # ---- (b) source scan ----
    if not source_files:
        blockers.append(
            f"source guard scanned zero files under {plugin_root} — the scan "
            "roots or filters may be broken (a scan with nothing to check is a "
            "silent no-op for every one of the four checks, not only the token "
            "scans)"
        )
    if tokens:
        for rel, tok, lineno, excerpt in find_source_violations(plugin_root, tokens):
            violations.append(f"{rel}:{lineno}  token {tok!r}  → {excerpt}")

    if missing_source_roots:
        blockers.append(
            "expected source scan root(s) missing under "
            f"{plugin_root}: {', '.join(missing_source_roots)} — a partial or "
            "broken plugin install (heavy coverage loss would otherwise exit "
            "clean silently)"
        )

    # ---- (c) absolute developer paths — always armed, no token list needed ----
    for rel, kind, lineno, excerpt in find_absolute_path_leaks(plugin_root):
        violations.append(f"{rel}:{lineno}  [{kind}]  → {excerpt}")

    # ---- (d) readability — the check that keeps (a), (b) and (c) honest ----
    # An unreadable file is silently "clean" to every scanner above, so its
    # unreadability is itself the violation. Never gate this on `tokens`, and
    # never skip it because an earlier check already reported.
    for rel, reason in find_unreadable_files(plugin_root):
        violations.append(
            f"{rel}  [{reason}]  → cannot be read as UTF-8, so every token and "
            "path scan silently skipped it and reported clean"
        )

    # Name the roots actually reached, not just the count. A source scan that
    # collapsed to `skills/` alone would still report a large, healthy-looking
    # file count while covering a fraction of what this checker claims — and the
    # count on its own cannot show that.
    roots_reached = sorted(
        {path.relative_to(plugin_root).parts[0] for path in source_files}
    )
    summary = (
        f"{_PROG}: {len(prose_files)} prose file(s) and {len(source_files)} "
        f"source file(s) scanned under {plugin_root.name}, {len(tokens)} "
        f"token(s) loaded, {len(violations)} violation(s); source roots reached: "
        + (", ".join(roots_reached) or "(none)")
    )
    if missing_source_roots:
        summary += "; expected-but-absent: " + ", ".join(missing_source_roots)

    for note in notes:
        print(f"{_PROG}: {note}")

    print(summary)

    for line in violations:
        print(line)

    for line in blockers:
        print(f"{_PROG}: {line}", file=sys.stderr)

    # Confirmed violations win over a blocker: "I found problems" must not be
    # masked by "I could not look" when both are true in the same run — a
    # caller reading only the exit code must still see the real leak, not a
    # could-not-run verdict that reads as "nothing to act on".
    if violations:
        print(
            f"{len(violations)} conformance violation(s) in synced core — move the "
            "fact behind an overlay, rename the fixture value, curate the token out, "
            f"or mark a deliberate path fixture with `{ABS_PATH_EXEMPT_MARKER}`."
        )
        return EXIT_VIOLATIONS  # branch: confirmed violations win over a blocker

    if blockers:
        return EXIT_CANNOT_RUN  # branch: could not run, and no violation to report

    return EXIT_CLEAN


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
