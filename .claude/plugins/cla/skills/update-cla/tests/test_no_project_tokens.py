"""Conformance guard: no project-specific tokens in synced core.

A generic, repo-agnostic checker enforcing the cla plugin's fact/procedure
separation (``cla-overlay-convention`` + ``cla-skill-context-extraction``): a
project-specific token must live behind an overlay (``project-context.md`` /
``*.local.md``), never baked into a synced-core ``SKILL.md`` or
``references/**/*.md``, or ``update-cla``'s sync would carry it verbatim into
every destination repo. The token list itself is a per-repo overlay
(``project-tokens.local.md``) read as data — the checker hard-codes no token.

The checker obeys the same split it enforces: generic *procedure* (this file,
synced to every repo) + a repo-specific *fact* (the token list, never synced).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# `discover.SCAN_DIRS` is the single source of truth for what update-cla syncs.
# Imported (not re-typed) so this file's scan roots can never drift from it —
# see the SOURCE_SCAN_ROOTS derivation below for why that drift is a real,
# already-happened failure mode, not a hypothetical one.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import discover  # noqa: E402

OVERLAY_FILE_NAME = "project-context.md"
OVERLAY_LOCAL_SUFFIX = ".local.md"
EXCLUDED_SUBTREES = frozenset({"tests", "scripts"})
# Token-list overlay, relative to the skills/ root. Its ``.local.md`` leaf also
# makes it a recognized overlay, so the scan below never flags its own contents.
TOKEN_LIST_RELPATH = Path("update-cla") / "references" / "project-tokens.local.md"
MAX_EXCERPT = 120


def _plugin_root() -> Path:
    """Resolve the ``.claude/plugins/cla`` root from this file's own location — a
    fixed internal layout identical in every repo, with no repo-specific absolute
    path or repository name baked in."""
    for parent in Path(__file__).resolve().parents:
        if parent.name == "cla" and parent.parent.name == "plugins":
            return parent
    # Fallback for an unexpected layout: tests/ -> update-cla/ -> skills/ -> cla/
    return Path(__file__).resolve().parents[3]


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
#      STRINGS, and `update-cla` syncs them into every destination repo just
#      the same.
#   3. `hooks/`, `agents/`, and `output-styles/`. None lives under `skills/`,
#      so all three are outside the prose scan's root entirely.
#
# Kept as a separate scanner rather than widening the one above, because the
# rules genuinely differ: the prose guard's frontmatter exemption exists for a
# `SKILL.md` `description:` that legitimately names the host repo so the skill
# triggers, which has no analogue in a `.py` file.

# Derived from `discover.SCAN_DIRS`, not hand-typed: this list was independently
# maintained here (and a third time in test_sync_claude_assets.py) and BOTH
# copies missed `output-styles` when it was added to the real `SCAN_DIRS` —
# caught only by review, not by any test, because every test that referenced
# the stale copy stayed green. Deriving makes that class of drift structurally
# impossible: a future 5th category added to SCAN_DIRS alone is scanned here
# automatically, with no second edit to remember.
SOURCE_SCAN_ROOTS = tuple(d.rsplit("/", 1)[-1] for d in discover.SCAN_DIRS)
CACHE_DIRS = frozenset({"__pycache__", ".pytest_cache"})


def _iter_scanned_source_files(plugin_root: Path):
    """Yield every synced-core SOURCE file the prose scan cannot see.

    `.py` anywhere under the synced roots (including `tests/` and `scripts/`),
    plus every `.md` under `agents/` or `output-styles/` (agent definitions and
    output-style files, neither reachable from the prose scan's `skills/` root).
    Overlays stay exempt by the same convention, and bytecode/cache directories
    are skipped — a stale `.pyc` still holds the string it was compiled from and
    would report a leak already fixed in source.
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
            if path.suffix == ".py" or (root_name in md_roots and path.suffix == ".md"):
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


# ---------- the guard ----------


def test_no_project_tokens_in_synced_core():
    """Fail if any non-overlay synced-core file leaks a listed project token."""
    plugin_root = _plugin_root()
    skills_root = plugin_root / "skills"
    token_path = skills_root / TOKEN_LIST_RELPATH
    if not token_path.is_file():
        # A fresh destination repo has synced the guard but not curated a token list
        # yet (the overlay is never seeded by sync) — trivial pass, not a red CI.
        pytest.skip(
            "no project-tokens.local.md overlay present — trivial pass; each "
            "destination repo curates its own token list"
        )
    tokens = load_tokens(token_path)
    if not tokens:
        # The file EXISTS but parses to zero tokens. That is a defect (a broken/
        # reformatted list), not a fresh repo — fail loudly rather than silently
        # disabling the guard. To intentionally disable it, DELETE the file.
        pytest.fail(
            f"{token_path.name} exists but yields no tokens — likely a formatting "
            "error (each token must be a `- token` / `* token` bullet). Delete the "
            "file to intentionally disable the guard."
        )
    scanned = list(_iter_scanned_files(skills_root))
    assert scanned, (
        f"guard scanned zero files under {skills_root} — the scan root or filters "
        "may be broken (a populated token list with nothing to scan is a silent no-op)"
    )
    violations = find_violations(skills_root, plugin_root, tokens)
    if violations:
        detail = "\n".join(
            f"{rel}:{lineno}  token {tok!r}  → {excerpt}"
            for rel, tok, lineno, excerpt in violations
        )
        pytest.fail(
            f"{len(violations)} project-token leak(s) in synced core "
            f"(move the fact behind an overlay, or curate the token out):\n{detail}"
        )


def test_no_project_tokens_in_synced_source():
    """Fail if any synced-core SOURCE file leaks a listed project token.

    Same contract as the prose guard, over the files it cannot see. Split into
    its own test so a failure names which surface leaked — prose and source get
    curated differently (prose moves behind an overlay; a source hit is usually
    a fixture string that should just be neutral).
    """
    plugin_root = _plugin_root()
    token_path = plugin_root / "skills" / TOKEN_LIST_RELPATH
    if not token_path.is_file():
        pytest.skip(
            "no project-tokens.local.md overlay present — trivial pass; each "
            "destination repo curates its own token list"
        )
    tokens = load_tokens(token_path)
    if not tokens:
        pytest.fail(
            f"{token_path.name} exists but yields no tokens — likely a formatting "
            "error (each token must be a `- token` / `* token` bullet). Delete the "
            "file to intentionally disable the guard."
        )
    scanned = list(_iter_scanned_source_files(plugin_root))
    assert scanned, (
        f"source guard scanned zero files under {plugin_root} — the scan roots or "
        "filters may be broken (a populated token list with nothing to scan is a "
        "silent no-op)"
    )
    violations = find_source_violations(plugin_root, tokens)
    if violations:
        detail = "\n".join(
            f"{rel}:{lineno}  token {tok!r}  → {excerpt}"
            for rel, tok, lineno, excerpt in violations
        )
        pytest.fail(
            f"{len(violations)} project-token leak(s) in synced source files "
            f"(rename the fixture value, or curate the token out):\n{detail}"
        )


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


def test_no_absolute_developer_paths_in_synced_source():
    """Unlike the two token guards, this one is always armed — no overlay needed."""
    plugin_root = _plugin_root()
    leaks = find_absolute_path_leaks(plugin_root)
    if leaks:
        detail = "\n".join(
            f"{rel}:{lineno}  [{kind}]  → {excerpt}"
            for rel, kind, lineno, excerpt in leaks
        )
        pytest.fail(
            f"{len(leaks)} hardcoded absolute developer path(s) in synced core — "
            "such a path cannot be correct in any destination repo. Use a relative "
            f"path, or mark a deliberate fixture line with `{ABS_PATH_EXEMPT_MARKER}`:"
            f"\n{detail}"
        )


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


def test_every_scanned_file_is_actually_readable():
    plugin_root = _plugin_root()
    bad = find_unreadable_files(plugin_root)
    assert not bad, (
        "these synced-core files cannot be read as UTF-8, so every token and "
        "path guard silently skips them and reports clean:\n"
        + "\n".join(f"{rel}  [{reason}]" for rel, reason in bad)
    )


def test_the_readability_check_can_actually_fail(tmp_path):
    """Otherwise the guard above is a no-op that passes forever."""
    (tmp_path / "hooks").mkdir(parents=True)
    (tmp_path / "hooks" / "binary.py").write_bytes(b"\xff\xfe\x00\x01 not utf-8 \xff")
    assert find_unreadable_files(tmp_path)


# ---------- self-tests of the absolute-path scanner ----------
#
# The tree-wide test above asserts the real plugin is CLEAN, which it would also
# do if this scanner returned nothing at all — a broken regex, an inverted
# condition and a swallowed exception all pass it identically. These pin the
# scanner positively, so the guard cannot rot into a no-op.


def _scan_one(tmp_path: Path, line: str):
    """Run the scanner over a single-line source file under a fake plugin root."""
    (tmp_path / "hooks").mkdir(parents=True, exist_ok=True)
    (tmp_path / "hooks" / "sample.py").write_text(line + "\n", encoding="utf-8")
    return find_absolute_path_leaks(tmp_path)


@pytest.mark.parametrize(
    "line, expected_kind",
    [
        (r'BASE = "C:\Users\alice\code\thing"', "windows-drive-path"),  # path-fixture-ok
        ('BASE = "C:/Users/alice/AppData"', "windows-drive-path"),  # path-fixture-ok
        ('BASE = "/Users/alice/code/thing"', "home-directory-path"),  # path-fixture-ok
        ('BASE = "/home/alice/code/thing"', "home-directory-path"),  # path-fixture-ok
        # Separator-stripped — invisible to both patterns above.
        ('P = "C:UsersaliceAppDataLocalTempscratch.txt"', "mangled-windows-path"),  # path-fixture-ok
    ],
)
def test_absolute_developer_paths_are_flagged(tmp_path, line, expected_kind):
    leaks = _scan_one(tmp_path, line)
    assert [k for _, k, _, _ in leaks] == [expected_kind], leaks


@pytest.mark.parametrize(
    "line",
    [
        # The empirical finding that retuned this rule: `s:` + `//` satisfies a
        # naive drive-letter shape. Deleting the `(?<![A-Za-z0-9])` lookbehind
        # must fail this case.
        'URL = "https://example.com/x"',
        'URL = "ftp://example.com/x"',
        'URL = "file:///tmp/x"',
        # Placeholder users name nobody.
        'BASE = "/Users/me/code/thing"',
        'BASE = "/home/user/code/thing"',
        'P = "C:UserssomeuserAppDataLocalTempscratch.txt"',
        # Illustrative prose, not a runnable path.
        r'# e.g. C:\Code\<repo>\file.py',
        r"# e.g. C:\Users\...\AppData",
        # A Python escape sequence is not a path. Reported from a real tree, not
        # invented: `... as e:` + `\n` reads as drive `E:` + path `\n`, and the
        # line it fired on contained no path at all. Deleting either separator
        # requirement in WIN_ABS_PATH must fail these two.
        r'msg = f"failed as e:\n{detail}"',
        r'print("a:\tb")',
        # Relative paths are the whole point of the rule.
        'BASE = "hooks/tests/fixtures"',
    ],
)
def test_non_leaks_are_not_flagged(tmp_path, line):
    assert _scan_one(tmp_path, line) == []


def test_exempt_marker_clears_a_real_looking_path(tmp_path):
    marked = r'BASE = "C:\Users\alice\code"  # ' + ABS_PATH_EXEMPT_MARKER  # path-fixture-ok
    assert _scan_one(tmp_path, marked) == []


def test_each_shape_on_one_line_is_reported_independently(tmp_path):
    """A placeholder Windows path must not suppress a real home-path leak.

    This is the `elif` bug: the Windows arm matched, was exempted as a
    placeholder, and the home-path arm was never reached — so the real leak on
    the same line shipped.
    """
    line = r'# on Windows C:\Code\<repo>\x, on macOS /Users/alice/code/x'  # path-fixture-ok
    kinds = [k for _, k, _, _ in _scan_one(tmp_path, line)]
    assert kinds == ["home-directory-path"], kinds


def test_the_scanner_reaches_output_styles_not_just_hooks(tmp_path):
    # `_scan_one` above always writes to hooks/sample.py, so every parametrized
    # case using it proves the PATTERNS work without proving this scanner is
    # actually wired to output-styles/ — the exact gap that let the real
    # SOURCE_SCAN_ROOTS addition ship untested. Seeded directly here instead.
    (tmp_path / "output-styles").mkdir(parents=True, exist_ok=True)
    (tmp_path / "output-styles" / "CLA.md").write_text(
        'See C:\\Users\\alice\\code\\thing\n', encoding="utf-8"  # path-fixture-ok
    )
    leaks = find_absolute_path_leaks(tmp_path)
    assert [rel for rel, *_ in leaks] == ["output-styles/CLA.md"]


def test_the_scanner_is_not_vacuous(tmp_path):
    """A guard that can never fire would pass every test above by accident."""
    assert _scan_one(tmp_path, r'BASE = "C:\Users\alice\x"')  # path-fixture-ok


# ---------- self-tests of the checker's own machinery ----------


def test_load_tokens_parses_bullets_strips_comments_and_backticks(tmp_path):
    p = tmp_path / "project-tokens.local.md"
    p.write_text(
        "# Tokens\n\n"
        "- `some-repo`  # repo name\n"
        "* packages/engine # a package path\n"
        "- 5173\n"
        "<!-- excluded: apps/ pnpm -->\n"
        "not-a-bullet-is-ignored\n",
        encoding="utf-8",
    )
    assert load_tokens(p) == ["some-repo", "packages/engine", "5173"]


def test_absent_or_empty_token_list_yields_no_tokens(tmp_path):
    assert load_tokens(tmp_path / "missing.local.md") == []
    empty = tmp_path / "project-tokens.local.md"
    empty.write_text("# heading only\n<!-- a comment -->\n\n", encoding="utf-8")
    assert load_tokens(empty) == []


def test_body_token_is_flagged_with_accurate_line(tmp_path):
    skills = tmp_path / "skills"
    (skills / "demo").mkdir(parents=True)
    (skills / "demo" / "SKILL.md").write_text(
        "# Demo\n\nThis names funnel-demo in the body.\n", encoding="utf-8"
    )
    violations = find_violations(skills, tmp_path, ["funnel-demo"])
    assert violations == [("skills/demo/SKILL.md", "funnel-demo", 3,
                           "This names funnel-demo in the body.")]


def test_overlay_files_are_not_flagged(tmp_path):
    skills = tmp_path / "skills"
    refs = skills / "demo" / "references"
    refs.mkdir(parents=True)
    (refs / "project-context.md").write_text("funnel-demo everywhere\n", encoding="utf-8")
    (refs / "project-tokens.local.md").write_text("- funnel-demo\n", encoding="utf-8")
    assert find_violations(skills, tmp_path, ["funnel-demo"]) == []


def test_frontmatter_is_excluded_but_body_is_flagged(tmp_path):
    skills = tmp_path / "skills"
    (skills / "demo").mkdir(parents=True)
    # line 1 ---, 2 description (frontmatter, exempt), 3 ---, 4 blank,
    # 5 body, 6 body-with-token
    (skills / "demo" / "SKILL.md").write_text(
        "---\n"
        "description: all about the funnel-demo repo\n"
        "---\n"
        "\n"
        "Portable prose here.\n"
        "But funnel-demo in the body leaks.\n",
        encoding="utf-8",
    )
    violations = find_violations(skills, tmp_path, ["funnel-demo"])
    assert len(violations) == 1
    assert violations[0][2] == 6  # accurate line number despite skipped frontmatter


def test_references_md_scanned_but_stray_md_and_subtrees_ignored(tmp_path):
    skills = tmp_path / "skills"
    (skills / "demo" / "references").mkdir(parents=True)
    (skills / "demo" / "tests").mkdir(parents=True)
    (skills / "demo" / "scripts").mkdir(parents=True)
    (skills / "demo" / "references" / "note.md").write_text("has funnel-demo\n", encoding="utf-8")
    (skills / "demo" / "random.md").write_text("has funnel-demo\n", encoding="utf-8")  # not SKILL.md / references
    (skills / "demo" / "tests" / "note.md").write_text("has funnel-demo\n", encoding="utf-8")
    (skills / "demo" / "scripts" / "note.md").write_text("has funnel-demo\n", encoding="utf-8")
    violations = find_violations(skills, tmp_path, ["funnel-demo"])
    assert [v[0] for v in violations] == ["skills/demo/references/note.md"]


def test_matching_is_case_insensitive(tmp_path):
    skills = tmp_path / "skills"
    (skills / "demo").mkdir(parents=True)
    (skills / "demo" / "SKILL.md").write_text("# X\n\nThe Kantar gateway.\n", encoding="utf-8")
    violations = find_violations(skills, tmp_path, ["kantar"])
    assert len(violations) == 1


def test_load_tokens_ignores_bullets_inside_html_comment_blocks(tmp_path):
    # Multi-line <!-- ... --> blocks legitimately contain `- ` bullets (this repo's
    # own token overlay documents its excluded candidates that way) — none may leak in.
    p = tmp_path / "project-tokens.local.md"
    p.write_text(
        "<!--\n"
        "  header note with a bullet:\n"
        "  - funnel-demo  # INSIDE a comment, must be ignored\n"
        "-->\n"
        "- `some-repo`  # the one real token\n"
        "<!-- excluded candidates:\n"
        "  - apps/  # also inside a comment\n"
        "  - pnpm\n"
        "-->\n",
        encoding="utf-8",
    )
    assert load_tokens(p) == ["some-repo"]


def test_multiple_violations_all_collected_not_first_hit(tmp_path):
    # Guards the "surface every leak at once, not first-hit-only" promise: multiple
    # hits of one token across lines, plus two tokens on one line, must all report.
    skills = tmp_path / "skills"
    (skills / "demo").mkdir(parents=True)
    (skills / "demo" / "SKILL.md").write_text(
        "# Demo\n\nfunnel-demo here.\nfunnel-demo again.\nboth kantar and funnel-demo.\n",
        encoding="utf-8",
    )
    violations = find_violations(skills, tmp_path, ["funnel-demo", "kantar"])
    assert len(violations) == 4  # lines 3,4,5 (funnel-demo) + line 5 (kantar)
    assert sorted(v[2] for v in violations) == [3, 4, 5, 5]
    assert {v[1] for v in violations} == {"funnel-demo", "kantar"}


def test_frontmatter_skip_applies_only_to_skill_md(tmp_path):
    # A references .md opening with a Markdown horizontal rule (`---`) is NOT
    # frontmatter — its body must be scanned, not silently exempted.
    skills = tmp_path / "skills"
    refs = skills / "demo" / "references"
    refs.mkdir(parents=True)
    (refs / "note.md").write_text(
        "---\nfunnel-demo in a horizontal-rule block, not frontmatter.\n---\nbody.\n",
        encoding="utf-8",
    )
    violations = find_violations(skills, tmp_path, ["funnel-demo"])
    assert len(violations) == 1
    assert violations[0][2] == 2  # scanned, because non-SKILL.md files aren't frontmatter-stripped


# ---------- self-tests of the source scanner ----------
#
# Each of the first three pins one blind spot the prose scan had. They are
# written as "the prose scan misses this AND the source scan catches it" rather
# than just the latter, because the pairing is the actual regression: a future
# refactor that quietly narrows the source scan back to the prose scan's shape
# would still pass a one-sided assertion.


def _seed(tmp_path: Path, rel: str, body: str) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def test_source_scan_catches_a_py_file_the_prose_scan_globs_past(tmp_path):
    _seed(tmp_path, "skills/demo/scripts/helper.py", 'ROOT = "C:/Code/funnel-demo"\n')  # path-fixture-ok
    assert find_violations(tmp_path / "skills", tmp_path, ["funnel-demo"]) == []
    hits = find_source_violations(tmp_path, ["funnel-demo"])
    assert [h[0] for h in hits] == ["skills/demo/scripts/helper.py"]


def test_source_scan_reaches_into_the_tests_subtree(tmp_path):
    # `tests/` is in EXCLUDED_SUBTREES for prose, and it is where the real leak
    # lived — 19 occurrences across three scopes' test fixtures.
    _seed(tmp_path, "skills/demo/tests/test_thing.py", 'PATH = "/src/funnel-demo/x"\n')
    assert find_violations(tmp_path / "skills", tmp_path, ["funnel-demo"]) == []
    assert len(find_source_violations(tmp_path, ["funnel-demo"])) == 1


def test_source_scan_covers_hooks_and_agents_outside_the_skills_root(tmp_path):
    _seed(tmp_path, "hooks/some-hook.py", '# example: C:/Code/funnel-demo\n')  # path-fixture-ok
    _seed(tmp_path, "agents/some-agent.md", "Body naming funnel-demo directly.\n")
    # The prose scan's root is skills/ — neither tree is reachable from it.
    assert find_violations(tmp_path / "skills", tmp_path, ["funnel-demo"]) == []
    rels = sorted(h[0] for h in find_source_violations(tmp_path, ["funnel-demo"]))
    assert rels == ["agents/some-agent.md", "hooks/some-hook.py"]


def test_source_scan_covers_output_styles_outside_the_skills_root(tmp_path):
    # The same class of gap as hooks/agents above, pinned separately: a fourth
    # root added to SCAN_DIRS is worth nothing to this guard unless this
    # scanner's own md_roots is widened to match, which is a second edit that
    # nothing forces anyone to remember. This is that forcing function.
    _seed(tmp_path, "output-styles/CLA.md", "Body naming funnel-demo directly.\n")
    assert find_violations(tmp_path / "skills", tmp_path, ["funnel-demo"]) == []
    rels = [h[0] for h in find_source_violations(tmp_path, ["funnel-demo"])]
    assert rels == ["output-styles/CLA.md"]


def test_source_scan_exempts_agent_frontmatter_but_flags_the_body(tmp_path):
    # Same reasoning as the prose guard's SKILL.md exemption: a description
    # legitimately names the host repo so the agent is selected for it.
    _seed(
        tmp_path,
        "agents/a.md",
        "---\nname: a\ndescription: Use in funnel-demo.\n---\n\nPortable prose.\n",
    )
    assert find_source_violations(tmp_path, ["funnel-demo"]) == []
    _seed(
        tmp_path,
        "agents/b.md",
        "---\nname: b\n---\n\nHardcoded funnel-demo in the body.\n",
    )
    assert [h[0] for h in find_source_violations(tmp_path, ["funnel-demo"])] == ["agents/b.md"]


def test_source_scan_exempts_output_style_frontmatter_but_flags_the_body(tmp_path):
    # An output style's `description:` is shown in the /config picker and can
    # legitimately name the host project, same reasoning as the agent case
    # above — checked as its own case because md_roots exempting "any .md" by
    # accident (rather than specifically agents/output-styles) would pass the
    # agent-only version of this test just as easily.
    _seed(
        tmp_path,
        "output-styles/a.md",
        "---\nname: a\ndescription: Use in funnel-demo.\n---\n\nPortable prose.\n",
    )
    assert find_source_violations(tmp_path, ["funnel-demo"]) == []
    _seed(
        tmp_path,
        "output-styles/b.md",
        "---\nname: b\n---\n\nHardcoded funnel-demo in the body.\n",
    )
    assert [h[0] for h in find_source_violations(tmp_path, ["funnel-demo"])] == [
        "output-styles/b.md"
    ]


def test_source_scan_ignores_bytecode_and_overlays(tmp_path):
    # A stale .pyc still holds the string it was compiled from, so scanning it
    # would report a leak already fixed in source.
    _seed(tmp_path, "skills/demo/tests/__pycache__/x.cpython-313.pyc", "funnel-demo\n")
    _seed(tmp_path, "skills/demo/references/project-context.md", "funnel-demo\n")
    _seed(tmp_path, "skills/demo/references/notes.local.md", "funnel-demo\n")
    assert find_source_violations(tmp_path, ["funnel-demo"]) == []


def test_source_scan_of_the_real_plugin_is_non_vacuous():
    # Guards the "scanned zero files" silent no-op independently of whether a
    # token list happens to exist on this machine.
    scanned = list(_iter_scanned_source_files(_plugin_root()))
    assert len(scanned) > 20, f"expected the real plugin to have source files, got {len(scanned)}"
    assert any(p.suffix == ".py" for p in scanned)
