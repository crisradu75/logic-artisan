#!/usr/bin/env python3
"""Staleness guard: every repo-relative path named in the consolidated project-facts
file or a per-skill overlay must still resolve on disk.

A portable, generic checker that pairs with the sibling conformance guard
(``${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/check_no_project_tokens.py``) —
same "generic checker + per-repo data" shape, but this one lints PATHS rather
than project-token leakage. It scans ``cla.io/project-facts.md`` (the repo-level,
never-synced consolidated fact file — see the ``cla-context-refresh`` change) and
every per-skill ``references/project-context.md`` overlay (globbed generically —
NOT a hardcoded skill list, so it also lints future overlays and any new skill's
own overlay stub), extracts every token that looks like a repo-relative path, and
fails when any such path no longer resolves on disk.

It lives with ``sync-context`` because it lints exactly what that skill produces,
and it reads the CONSUMING repo's data — which is why it is a skill helper rather
than a test: a consuming repo has no test gate over the plugin cache, so a
checker filed as a pytest module is unreachable there in practice.

RUN IT AS A PROGRAM, from anywhere inside the repo it should check::

    python3 ${CLAUDE_PLUGIN_ROOT}/skills/sync-context/scripts/check_fact_paths.py

EXIT CODES:
  - ``0`` — clean, or a trivial pass. One summary line names what was scanned and
    how many files, so a scan that inspected nothing is visible rather than
    indistinguishable from a clean result. A trivial pass states its reason.
  - ``1`` — stale paths found. Every one is named, one per line, in a single run;
    the checker never stops at the first.
  - ``2`` — the checker could not do its job: bad arguments, a repo root that
    could not be resolved at all, an input that exists but cannot be read, or
    anything was scanned (a facts file OR overlays) yet it yielded zero path
    candidates, which means the extraction is broken. Diagnostic goes to
    stderr. Never conflated with ``1``: "I found problems" and "I could not
    look" are different answers, and a caller scripting the exit code must be
    able to tell them apart.

``--repo-root <path>`` overrides the default self-resolution (git, then a
``.claude`` walk that refuses the user's global one, then a hard failure —
never a silent ``cwd`` fallback, which used to report a wrong root as clean).
It exists so the CLI layer is testable against a temporary tree; the skills
invoke the bare form.

COVERAGE LIMITS (read before trusting this guard blindly):
  - This is a **path-existence check only**. It does NOT validate the non-path
    mechanical facts the refresh skill (``/cla:sync-context``) produces — commands,
    ports, workspace-member counts, doc-sweep completeness. Those drift silently
    with respect to this guard; they are kept fresh by ``/cla:sync-context`` plus
    human review, not by this file.
  - It does NOT detect a fact **duplicated** between ``cla.io/project-facts.md`` and
    an overlay (the maintenance regression ``cla-context-refresh`` fights in the
    first place) — that is caught at trim time and by the refresh skill's own
    reconcile pass, never mechanically by this guard.
  - Most overlay path references are glob/placeholder-shaped (``docs/**/*.md``,
    ``apps/<app>/src/``) and are deliberately SKIPPED (see ``_keep_if_path`` and
    ``extract_path_candidates`` for the exact extraction rule) rather than checked
    — so effective true-positive coverage is the concrete-path subset of what each
    file names, not everything it names.
  - The extraction heuristic is deliberately conservative: on any ambiguous token
    it skips rather than flags, because a false staleness failure trains people to
    ignore the guard (see ``design.md`` Decision E of ``cla-context-refresh``).
  - Only ``/``-bearing repo-relative paths are checked. A BARE single-segment
    filename (``README.md``, ``CLAUDE.md`` with no path) is NOT checked: prose that
    merely names a file the repo doesn't contain (``package-lock.json`` in a
    "no longer exists" sentence, an external tool's ``telemetry.json``) is
    syntactically identical to a stale repo-file reference, so a bare-filename
    existence check false-positives on it (see the bare-filename NOTE below).

The checker obeys the same split it enforces: generic *procedure* (this file,
portable to any repo) driven by *data* it reads live off the repo tree (the facts
file + overlays + the repo's own top-level entries) — no repo name or path prefix
is hard-coded here.

The unit tests of every function below live in the canonical source repo's own
development tree, at ``plugin-tests/tests/conformance/test_project_facts_paths.py``,
which loads this file by path. They are not shipped: the plugin carries only
assets a consuming repo can use.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT_FACTS_RELPATH = Path("cla.io") / "project-facts.md"
OVERLAY_GLOB = "*.md"  # under cla.io/overlays/
# Where overlays lived before they moved into the repo. Still scanned so a
# consuming repo that has not migrated keeps its guard.
LEGACY_OVERLAY_GLOB = "*/references/project-context.md"

# Decision E's placeholder/glob character set, PLUS brace-expansion (`{a,b}`) —
# an obvious shorthand/placeholder notation (several overlays legitimately write
# `packages/engine/src/{types,ReachModel}.ts` to mean two real, separately-existing
# paths) that is not itself a literal path on disk. Treating it as a placeholder
# (skip, don't flag) is a direct application of Decision E's own governing
# principle — "on an ambiguous token, err toward NOT flagging" — rather than a
# deviation from it; the pinned `*`/`<`/`>`/`...` set was illustrative, not
# advertised as exhaustive of every shorthand notation prose might use.
_PLACEHOLDER_CHARS = ("*", "<", ">", "{", "}")
_ELLIPSIS = "..."

_URL_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")
_TRAILING_LINE_COL_RE = re.compile(r":\d+(:\d+)?$")
# A trailing colon is stripped as wrapping punctuation too (prose glues one onto a
# bare path — "edit apps/x/y.ts: add a rule"). It comes AFTER `:line[:col]` in the
# strip order (see `_clean_candidate`), so an `engine.test.ts:120` line-suffix is
# removed by `_strip_line_col` first and only a genuine lone trailing `:` is wrapped.
# `[` and `]` are here because a path inside a fenced JSON config block arrives
# as `["…/src"` or `…/src"]` — without brackets the QUOTE never becomes an outer
# character, so a live path reads as stale forever. Both are needed, not one: a
# single-element array (`["apps/x/src"]`) presents both at once.
#
# Adding them alone breaks markdown links whose text is a path:
# `[docs/a.md](docs/a.md)` would clean to `docs/a.md](docs/a.md`, a token that
# can never exist on disk and so is flagged stale forever. `_MARKDOWN_LINK_SEAM`
# below rejects those by their two-char seams instead — NOT by refusing to strip
# the bracket, and NOT by rejecting brackets generally, which would also discard
# a legitimate `apps/x/[id]/page.tsx` dynamic-route segment that has `]/` and
# stays perfectly checkable.
_WRAP_CHARS = "`'\"(),;.:[]"

# A token containing either seam is the residue of a markdown link, not a path.
_MARKDOWN_LINK_SEAMS = ("](", "][")

# Balanced markdown-emphasis wrappers (`**path**`, `_path_`, `*path*`). Stripped only
# when they wrap BOTH ends symmetrically, so a real trailing-glob `apps/*` (star at
# one end only) is left intact and still skipped as a glob.
_EMPHASIS_MARKERS = ("**", "__", "*", "_")

# NOTE — bare single-segment filenames (a token with NO `/`, e.g. `README.md`,
# `CLAUDE.md`) are deliberately NOT existence-checked. A bare filename reference is
# syntactically indistinguishable from prose that merely NAMES a file the repo does
# not contain — a general bare-filename check false-positives on exactly that (seen
# for real: `package-lock.json` in a "no longer exists" sentence, `telemetry.json`
# and `journal.jsonl` as external-tool artifacts). Only `/`-bearing repo-relative
# paths, whose intent is unambiguous, are checked. (See PR #158.)


def _repo_root_from_here() -> Path | None:
    """The repo being checked — asked of git, from the PROCESS's cwd. Returns
    ``None`` when resolution genuinely fails (no git, no non-global ``.claude``
    ancestor) — the caller must treat that as ``EXIT_CANNOT_RUN``, never as a
    silent trivial pass over whatever directory happens to be current.

    This guard's subject is the consuming repo's `cla.io/` files, so the root
    must be that repo. It used to walk up from `__file__` to the first `.claude`
    ancestor, which was right only while the plugin was vendored at
    `<repo>/.claude/plugins/<plugin>/`. Installed from a marketplace it lives
    at `~/.claude/plugins/cache/<marketplace>/cla/<version>/`, so the first
    `.claude` ancestor is the user's GLOBAL one and the function returned the
    user's HOME DIRECTORY. Both guards in this scope then looked for
    `cla.io/…` under `~`, found nothing, and skipped — green while checking
    nothing, in every marketplace install simultaneously (upstream issue #52).

    Two things made that unrecoverable rather than merely wrong: the `.claude`
    walk SUCCEEDED, so the git fallback below was never reached; and the
    fallback passed `cwd=__file__`'s parent, which is inside the read-only
    plugin cache and not a git repo, so it would have failed anyway. The
    consuming repo is the PROCESS cwd, never a path relative to this file.
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
    # Fallback for a non-git checkout: the `.claude` walk, but never accepting
    # the user's global `~/.claude` — that match is the defect above, not a
    # repo, and returning home silently disables the guard.
    home_claude = (Path.home() / ".claude").resolve()
    for parent in Path(__file__).resolve().parents:
        if parent.name == ".claude" and parent.resolve() != home_claude:
            return parent.parent
    # Nothing resolved. This used to return `Path.cwd()` as a last resort, which
    # made an unresolved root report as a trivial CLEAN pass over whatever
    # directory happened to be current — a wrong root silently producing a
    # green verdict. The caller now treats `None` as EXIT_CANNOT_RUN instead.
    return None


_BACKTICK_SPAN_RE = re.compile(r"`([^`]+)`")
_POSSESSIVE_RE = re.compile(r"'s$")


def _strip_wrapping(token: str) -> str:
    """Repeatedly strip wrapping punctuation (backticks, quotes, parens, commas,
    semicolons, a trailing sentence-ending period) from both ends, and a trailing
    English possessive ``'s`` glued directly onto a path-like word with no space
    (prose like ``apps/operator's own docked assistant rail``), until stable.
    Does NOT touch a colon — the trailing ``:line[:col]`` suffix is a separate,
    dedicated strip (see ``_strip_line_col``) since a bare char-class strip can't
    tell "line-number suffix" apart from a colon that might legitimately end a
    non-path token."""
    prev = None
    while prev != token:
        prev = token
        # A LEADING dot is never decoration — it is the path. `.claude/…`,
        # `.github/…`, `.gitattributes` are exactly the paths a harness-facing
        # facts file names most often, and stripping the dot left
        # `claude/hooks/…`, whose first segment matches no tracked top-level
        # entry, so `_keep_if_path` dropped it and the guard never checked it.
        # Measured: 183 candidates checked, 0 stale, while four genuinely dead
        # `.claude/`-rooted paths sat in the scanned files (upstream issue #53).
        # A TRAILING dot is still decoration (a sentence-ending period).
        if token and token[0] in _WRAP_CHARS and token[0] != ".":
            token = token[1:]
        if token and token[-1] in _WRAP_CHARS:
            token = token[:-1]
        token = _POSSESSIVE_RE.sub("", token)
    return token


def _strip_line_col(token: str) -> str:
    """Strip a trailing ``:123`` or ``:123:45`` line[:col] suffix, e.g. the
    ``engine.test.ts:120`` overlays cite."""
    return _TRAILING_LINE_COL_RE.sub("", token)


def _strip_emphasis(token: str) -> str:
    """Strip a BALANCED markdown-emphasis wrapper (``**x**``/``__x__``/``*x*``/
    ``_x_``) from both ends. Only symmetric pairs are stripped, so a genuine
    trailing-glob like ``apps/*`` (a star at one end only) is untouched and stays
    classified as a glob (skipped) — while ``**apps/foo/x.ts**`` unwraps to the
    real path instead of being mistaken for a glob on its stray ``*``."""
    prev = None
    while prev != token:
        prev = token
        for marker in _EMPHASIS_MARKERS:
            if (
                len(token) > 2 * len(marker)
                and token.startswith(marker)
                and token.endswith(marker)
            ):
                token = token[len(marker):-len(marker)]
                break
    return token


def _clean_candidate(raw: str) -> str:
    """Strip wrapping punctuation, markdown emphasis, and a ``:line[:col]`` suffix
    to a fixpoint, so any nesting order (``(**path.ts:12**),``) resolves to the bare
    path regardless of which decoration sits outside which."""
    prev = None
    token = raw
    while prev != token:
        prev = token
        token = _strip_wrapping(token)
        token = _strip_emphasis(token)
        token = _strip_line_col(token)
    return token


def _looks_like_placeholder_or_glob(token: str) -> bool:
    if _ELLIPSIS in token:
        return True
    return any(ch in token for ch in _PLACEHOLDER_CHARS)


# Environment variables git itself sets when invoking a hook (`GIT_DIR`,
# `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`). If this guard
# ever runs FROM inside a git hook, an inherited `GIT_DIR` overrides discovery
# and silently retargets `-C repo_root` at a different repository entirely —
# rc=0, no error, just the wrong answer. Popped rather than trusted.
_GIT_ENV_OVERRIDES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY")


def _clean_git_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in _GIT_ENV_OVERRIDES:
        env.pop(key, None)
    return env


def _tracked_top_level_names(repo_root: Path) -> set[str] | None:
    """Top-level entries from the git INDEX (`git ls-files --cached`, i.e. what
    is tracked or staged), or `None` when `repo_root` isn't a git repo or git
    is unavailable.

    This is the deterministic source `_top_level_names` prefers. A live
    `repo_root.iterdir()` makes the guard's verdict depend on which stray
    UNTRACKED directories happen to exist in a given checkout — observed
    concretely: the same overlays passed inside a clean worktree and failed on
    the primary clone, because that clone happened to contain an empty
    untracked `docs/`. With no `docs/` present, a bare token `docs/architecture.md`
    was skipped as "not a repo path"; with it present, the token was checked,
    didn't resolve, and failed — neither run wrong on its own terms, but the
    guard wasn't deterministic across checkouts of the identical commit.

    The INDEX, not `HEAD` (an earlier draft of this function used `git ls-tree
    HEAD`), is the reference point: `scan()` existence-checks candidates
    against the WORKING TREE (`(repo_root / candidate).exists()`), and the
    index — not the last commit — is what's about to match it. `HEAD` lags
    behind a freshly-`git add`ed new top-level directory, which would make a
    path reference added in the SAME uncommitted change silently unrecognized
    (skipped, never checked) until the next commit — reintroducing a
    same-shape non-determinism one level down. The index also resolves
    correctly in a repo with zero commits yet (right after `cla-init`
    scaffolds `cla.io/` but before the first commit), where `ls-tree HEAD`
    would simply fail (no revision named `HEAD`).

    `-z` (NUL-terminated, unquoted paths) avoids two failure modes a
    newline-split `--name-only` reading has: a non-ASCII top-level name
    (`café/`) that `core.quotePath` would otherwise C-escape into something
    that can never match a cleaned token again, and a name containing
    whitespace being corrupted by a per-line `.strip()`.

    Known, accepted residual gaps (same "conservative, err toward not
    flagging" posture the rest of this guard already takes — see the module
    docstring's COVERAGE LIMITS): a top-level directory that is genuinely
    GITIGNORED is invisible to the index just as it was invisible-when-absent
    to `iterdir()`'s replacement — this only matters if a real path this guard
    is meant to check ever lived under a gitignored top-level dir, which none
    of `cla.io/project-facts.md` or the skill overlays do today. A detached
    `HEAD` or mid-rebase state does not change the index's answer (the index
    reflects the checked-out working tree regardless), so it is not a
    residual gap of switching to the index — it was never solved by `HEAD`
    either."""
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotePath=false", "ls-files", "-z", "--cached", "--"],
            cwd=repo_root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
            env=_clean_git_env(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    names = {p.split("/", 1)[0] for p in result.stdout.split("\0") if p}
    return names or None


def _top_level_names(repo_root: Path) -> set[str]:
    """The repo's own real top-level entries (files + dirs). Prefers the git
    index (`_tracked_top_level_names`) so an untracked scratch directory can
    neither mask nor manufacture a violation; falls back to a live
    `repo_root.iterdir()` when `repo_root` isn't a git repo (or git is
    unavailable) — this module's own self-tests below construct plain
    `tmp_path` fixtures that are never git repos, so that fallback is not a
    hypothetical, it's what makes every self-test below still work. Neither
    path is a hardcoded prefix list, so this ports to a repo of any layout."""
    tracked = _tracked_top_level_names(repo_root)
    if tracked is not None:
        return tracked
    if not repo_root.is_dir():
        return set()
    return {p.name for p in repo_root.iterdir()}


def _keep_if_path(token: str, top_level_names: set[str]) -> str | None:
    """Apply the pinned Decision-E keep/skip rule to an already-cleaned token;
    return the token if it should be checked, else ``None``.

    Only a token WITH a ``/`` is treated as a repo-relative path — kept iff its
    first segment names a real top-level entry (repo-derived), existence-checked at
    that exact location. A bare single-segment token is never checked (see the
    bare-filename NOTE near the module constants)."""
    if not token or "/" not in token:
        return None
    # Residue of a markdown link whose text is itself a path: `[docs/a.md](docs/a.md)`
    # cleans to `docs/a.md](docs/a.md`, which can never exist on disk and would
    # be reported stale forever. Rejected by the SEAM rather than by refusing to
    # strip brackets, so `apps/x/[id]/page.tsx` — which has `]/` and is a real,
    # checkable dynamic-route path — still gets checked.
    if any(seam in token for seam in _MARKDOWN_LINK_SEAMS):
        return None
    if token.startswith("~"):
        return None
    if _URL_SCHEME_RE.match(token):
        return None
    if _looks_like_placeholder_or_glob(token):
        return None
    first_segment = token.split("/", 1)[0]
    if first_segment not in top_level_names:
        return None
    return token


def extract_path_candidates(line: str, top_level_names: set[str]) -> list[str]:
    """Return every repo-relative path candidate on ``line`` per the pinned
    Decision-E rule, kept file-or-directory-existence-checkable.

    Two passes, since markdown prose routinely glues trailing text (a possessive
    ``'s``, an adjacent second code span) directly onto a closing backtick with no
    intervening space — a single whitespace-token split alone can't tell a code
    span's own content apart from what follows it outside the backticks:

    - **Pass A (backtick-delimited spans):** every `` `...` `` code span on the
      line is its own candidate, extracted via regex so a closing backtick always
      ends the span regardless of what's glued on afterward (an apostrophe-s, a
      second adjacent code span, trailing punctuation).
    - **Pass B (bare, non-backtick tokens):** any whitespace-delimited token that
      contains NO backtick at all is cleaned and checked on its own (portable
      prose won't always wrap a path in backticks).
    """
    candidates: list[str] = []
    for match in _BACKTICK_SPAN_RE.finditer(line):
        cleaned = _clean_candidate(match.group(1))
        kept = _keep_if_path(cleaned, top_level_names)
        if kept:
            candidates.append(kept)
    for raw in line.split():
        if "`" in raw:
            continue  # handled by Pass A above
        cleaned = _clean_candidate(raw)
        kept = _keep_if_path(cleaned, top_level_names)
        if kept:
            candidates.append(kept)
    return candidates


def _iter_scanned_files(repo_root: Path):
    """Yield ``cla.io/project-facts.md`` (if present) and every per-skill overlay
    under ``cla.io/overlays/`` (globbed generically, not a hardcoded skill list).

    Both live in the repo, not the plugin: under a marketplace install the plugin
    tree is a read-only cache, so per-repo facts cannot live there. A consuming
    repo mid-migration may still hold overlays at the old
    ``skills/*/references/project-context.md`` path, so those are scanned too —
    dropping them would silently stop checking a repo that has not moved yet.
    """
    facts_file = repo_root / PROJECT_FACTS_RELPATH
    if facts_file.is_file():
        yield facts_file
    overlays_root = repo_root / "cla.io" / "overlays"
    if overlays_root.is_dir():
        for path in sorted(overlays_root.glob("*.md")):
            if path.is_file():
                yield path
    legacy_root = repo_root / ".claude" / "plugins" / "cla" / "skills"
    if legacy_root.is_dir():
        for path in sorted(legacy_root.glob(LEGACY_OVERLAY_GLOB)):
            if path.is_file():
                yield path


def scan(repo_root: Path):
    """Scan the facts file (if present) + all overlays and return
    ``(checked_count, stale)`` — ``checked_count`` is the total number of path
    candidates existence-checked (so a caller can assert the scan wasn't a silent
    no-op), ``stale`` is ``(rel_path, line_number, candidate)`` for every candidate
    that does not resolve on disk (as a file OR a directory)."""
    top_level_names = _top_level_names(repo_root)
    checked = 0
    stale: list[tuple[str, int, str]] = []
    unreadable: list[tuple[str, str]] = []
    for path in _iter_scanned_files(repo_root):
        rel = path.relative_to(repo_root).as_posix()
        # Per-file, so ONE unreadable input cannot discard every stale path found
        # before it. Letting the read raise out of the loop made an unreadable
        # file outrank confirmed findings — the same "a blocker masks violations"
        # inversion the sibling checker fixed, reached from the other side.
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            unreadable.append((rel, f"{type(exc).__name__}: {exc}"))
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for candidate in extract_path_candidates(line, top_level_names):
                checked += 1
                if not (repo_root / candidate).exists():
                    stale.append((rel, lineno, candidate))
    return checked, stale, unreadable


def find_stale_paths(repo_root: Path):
    """Return just the stale-path list (thin wrapper over ``scan``)."""
    return scan(repo_root)[1]


# ---------- the guard, as a program ----------

EXIT_CLEAN = 0
EXIT_STALE = 1
EXIT_CANNOT_RUN = 2

_PROG = "check_fact_paths"


def _force_utf8_streams() -> None:
    """Make stdout/stderr able to carry this checker's own report.

    A Windows console defaults to a legacy code page, so a stale path (or a
    recognized top-level prefix) with a non-ASCII segment would kill the program
    with ``UnicodeEncodeError`` instead of printing the finding. Invisible while
    this was a pytest module — pytest encodes its own failure messages — and a
    first-run crash the moment it became a program. ``_tracked_top_level_names``
    already goes out of its way to keep a ``café/`` name intact through
    extraction; dropping it at the print is the same bug one step later.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:  # pragma: no cover - not a TextIOWrapper
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):  # pragma: no cover - defensive
            pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=_PROG,
        description=(
            "Fail when a repo-relative path named in cla.io/project-facts.md or a "
            "per-skill overlay no longer resolves on disk."
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help=(
            "The repo to check. Defaults to the process's own repo (git, then a "
            "non-global `.claude` walk; exits 2 if neither resolves)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the staleness guard as a program and return its exit code.

    This carries the assertion `test_no_stale_paths_in_project_facts_or_overlays`
    made against the real repo, with pytest's skip/fail replaced by the pinned
    exit-code contract in the module docstring. Every stale path is reported in a
    single run; a fix-one-rerun loop wastes the caller's time, which is the whole
    reason the original guard collected before reporting.
    """
    _force_utf8_streams()
    # argparse exits 2 on a bad argument, which is already this program's
    # "could not do its job" code — a bad invocation is not a clean result and
    # must never read as one.
    args = _build_parser().parse_args(argv)

    if args.repo_root is None:
        repo_root = _repo_root_from_here()
    else:
        repo_root = Path(args.repo_root)
        if not repo_root.is_dir():
            print(
                f"{_PROG}: --repo-root {args.repo_root!r} is not a directory",
                file=sys.stderr,
            )
            return EXIT_CANNOT_RUN

    if repo_root is None:
        # `_repo_root_from_here` could not resolve anything at all (no git, no
        # non-global `.claude` ancestor). It used to fall back to `Path.cwd()`,
        # which reported a WRONG root as a trivial clean pass; never let an
        # unresolved root produce a clean verdict.
        print(
            f"{_PROG}: could not resolve the repo root to check — not inside a "
            "git working tree, and no non-global .claude ancestor found; pass "
            "--repo-root explicitly",
            file=sys.stderr,
        )
        return EXIT_CANNOT_RUN  # branch: repo-root resolution failed

    # Trivial pass ONLY when there is genuinely nothing to scan (a fresh repo
    # with no facts file AND no overlays). An absent facts file does NOT skip the
    # overlay scan: overlays carry concrete paths, so a repo that installed the
    # plugin but has not run /cla:sync-context still gets its overlays linted —
    # that is exactly when their pointers are most likely dangling.
    scanned_files = list(_iter_scanned_files(repo_root))
    if not scanned_files:
        print(
            f"{_PROG}: no {PROJECT_FACTS_RELPATH.as_posix()} and no per-skill "
            "overlays — nothing to scan; run /cla:sync-context to populate the "
            "facts file"
        )
        return EXIT_CLEAN

    # Report — but never gate on — a live `iterdir()` fallback for top-level-name
    # recognition. Firing INSIDE a real git repo means `git ls-files` failed
    # unexpectedly (not "this isn't a git repo", the expected/silent case), which
    # reverts to the non-deterministic mode `_tracked_top_level_names` exists to
    # avoid (see its docstring) — worth a diagnostic even though it isn't fatal.
    if _tracked_top_level_names(repo_root) is None and (repo_root / ".git").exists():
        print(
            f"{_PROG}: {repo_root} looks like a git repository but `git "
            "ls-files` could not be used to list tracked top-level entries — "
            "falling back to a live directory listing, which can vary between "
            "checkouts of the same commit (see _tracked_top_level_names)"
        )

    checked, stale, unreadable = scan(repo_root)

    # An input that EXISTS but cannot be read. Reporting it as "clean" would be
    # the vacuous-pass bug; reporting it as "stale paths found" would send the
    # caller hunting a staleness that does not exist. So it is always NAMED —
    # but it does not outrank confirmed stale paths, which are real findings the
    # caller can act on now. Precedence, in order: stale paths (1) > unreadable
    # input (2) > clean (0). Matches `check_no_project_tokens.py`, where real
    # violations likewise win over a coexisting blocker.
    for rel, why in unreadable:
        print(
            f"{_PROG}: {rel} could not be read ({why}) — the scan is incomplete",
            file=sys.stderr,
        )
    if unreadable and not stale:
        print(
            f"{_PROG}: {len(unreadable)} scanned file(s) could not be read and "
            "no stale path was found in the rest — no verdict is reported",
            file=sys.stderr,
        )
        return EXIT_CANNOT_RUN  # branch: unreadable input, nothing else to report

    # Non-vacuous guard: whenever ANY input was scanned (facts file present, OR
    # overlays present with no facts file — the early `scanned_files` gate above
    # already ruled out "nothing to scan"), the scan MUST yield concrete path
    # candidates. This used to be gated on `facts_file.is_file()`, so a repo with
    # overlays but no facts file that extracted zero candidates exited 0 clean —
    # the exact silent no-op this guard exists to preclude, just reached via the
    # overlay-only path instead of the facts-file path. Zero-checked-with-something-
    # scanned means the extraction broke (wrong root shrinking the top-level set,
    # a heuristic regression) — "could not look", not "nothing to report".
    if checked == 0:
        print(
            f"{_PROG}: {len(scanned_files)} file(s) scanned but zero path "
            "candidates were extracted — the path-extraction heuristic or "
            "repo-root resolution is broken (the guard would silently check "
            "nothing)",
            file=sys.stderr,
        )
        return EXIT_CANNOT_RUN  # branch: extraction yielded nothing

    summary = (
        f"{_PROG}: {len(scanned_files)} file(s) scanned, "
        f"{checked} path candidate(s) checked, {len(stale)} stale path(s)"
    )

    if not stale:
        print(summary)
        return EXIT_CLEAN

    print(summary)
    # Accumulate every violation and report them all. Never break out of this
    # loop on the first hit: surfacing one stale path at a time turns one run
    # into a fix-and-rerun loop.
    for rel, lineno, candidate in stale:
        print(f"{rel}:{lineno}  stale path {candidate!r}")
    # Report the derived top-level set too — a candidate's first segment not
    # being in this set is exactly what makes `_keep_if_path` skip it (never flag
    # it), so when a genuine staleness IS found, seeing which prefixes were
    # recognized makes the result diagnosable rather than looking like a flaky
    # verdict tied to this checkout's contents.
    top_level = ", ".join(sorted(_top_level_names(repo_root))) or "(none)"
    print(
        f"{len(stale)} stale path(s) found in "
        f"{PROJECT_FACTS_RELPATH.as_posix()} or a per-skill overlay "
        "(path no longer exists on disk)"
    )
    print(f"(recognized top-level prefixes: {top_level})")
    return EXIT_STALE


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
