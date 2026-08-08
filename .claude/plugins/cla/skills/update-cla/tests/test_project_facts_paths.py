"""Staleness guard: every repo-relative path named in the consolidated project-facts
file or a per-skill overlay must still resolve on disk.

A portable, generic checker (``cla-context-refresh``) that pairs with the sibling
conformance guard (``test_no_project_tokens.py``) under this same ``tests/`` dir —
same "generic checker + per-repo data" shape, but this one lints PATHS rather than
project-token leakage. It scans ``cla.io/project-facts.md`` (the repo-level,
never-synced consolidated fact file — see the ``cla-context-refresh`` change) and
every per-skill ``references/project-context.md`` overlay (globbed generically —
NOT a hardcoded skill list, so it also lints future overlays and any new skill's
own overlay stub), extracts every token that looks like a repo-relative path, and
fails when any such path no longer resolves on disk.

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
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

PROJECT_FACTS_RELPATH = Path("cla.io") / "project-facts.md"
OVERLAY_GLOB = "*/references/project-context.md"

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
# paths, whose intent is unambiguous, are checked. (See TODO.md, PR #158.)


def _repo_root_from_here() -> Path:
    """Resolve the repo root as the parent of ``.claude/`` walked up from this
    file's own location — NOT the plugin root the conformance guard resolves to
    (``parent named "cla"``). The paths this guard checks are repo-relative and
    ``cla.io/project-facts.md`` sits at the repo root, outside the plugin tree, so
    the conformance guard's plugin-root resolution would be wrong here. Falls back
    to ``git rev-parse --show-toplevel`` if the ``.claude`` parent isn't found
    (e.g. an unusual layout), and finally to a fixed parents-index walk."""
    for parent in Path(__file__).resolve().parents:
        if parent.name == ".claude":
            return parent.parent
    try:
        import subprocess

        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parent,
            check=True,
        )
        top = out.stdout.strip()
        if top:
            return Path(top)
    except Exception:
        pass
    # Last-resort fallback for an unexpected layout:
    # tests/ -> update-cla/ -> skills/ -> cla/ -> plugins/ -> .claude/ -> root
    return Path(__file__).resolve().parents[6]


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
        if token and token[0] in _WRAP_CHARS:
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
            cwd=repo_root, capture_output=True, text=True, timeout=10,
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
    """Yield ``cla.io/project-facts.md`` (if present) and every per-skill
    ``references/project-context.md`` overlay (globbed generically under
    ``skills/*/references/``, not a hardcoded skill list)."""
    facts_file = repo_root / PROJECT_FACTS_RELPATH
    if facts_file.is_file():
        yield facts_file
    skills_root = repo_root / ".claude" / "plugins" / "cla" / "skills"
    if skills_root.is_dir():
        for path in sorted(skills_root.glob(OVERLAY_GLOB)):
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
    for path in _iter_scanned_files(repo_root):
        rel = path.relative_to(repo_root).as_posix()
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for candidate in extract_path_candidates(line, top_level_names):
                checked += 1
                if not (repo_root / candidate).exists():
                    stale.append((rel, lineno, candidate))
    return checked, stale


def find_stale_paths(repo_root: Path):
    """Return just the stale-path list (thin wrapper over ``scan``)."""
    return scan(repo_root)[1]


# ---------- the guard ----------


def test_no_stale_paths_in_project_facts_or_overlays():
    """Fail if any repo-relative path named in cla.io/project-facts.md or a
    per-skill overlay no longer resolves on disk (as a file or a directory)."""
    repo_root = _repo_root_from_here()
    facts_file = repo_root / PROJECT_FACTS_RELPATH
    # Skip ONLY when there is genuinely nothing to scan (a fresh repo with no
    # facts file AND no overlays). An absent facts file does NOT skip the overlay
    # scan: overlays are synced cross-repo and carry concrete paths, so a repo that
    # synced the skills but hasn't run /cla:sync-context still gets its overlays
    # linted (that is exactly when their pointers are most likely dangling).
    if not list(_iter_scanned_files(repo_root)):
        pytest.skip(
            "no cla.io/project-facts.md and no per-skill overlays — nothing to "
            "scan; run /cla:sync-context to populate the facts file"
        )
    checked, stale = scan(repo_root)
    # Non-vacuous guard: when the facts file is present it MUST yield concrete path
    # candidates. Zero-checked-with-facts-present means the extraction broke (wrong
    # root shrinking the top-level set, a heuristic regression) — a silent no-op
    # passing green is the exact failure this guard exists to preclude.
    if facts_file.is_file():
        assert checked > 0, (
            "cla.io/project-facts.md is present but zero path candidates were "
            "extracted — the path-extraction heuristic or repo-root resolution is "
            "broken (the guard would silently check nothing)"
        )
    if stale:
        detail = "\n".join(
            f"{rel}:{lineno}  stale path {candidate!r}" for rel, lineno, candidate in stale
        )
        # Report the derived top-level set too — a candidate's first segment
        # not being in this set is exactly what makes `_keep_if_path` skip it
        # (never flag it), so when a genuine staleness IS found here, seeing
        # which prefixes were recognized makes the result diagnosable rather
        # than looking like a flaky test tied to this checkout's contents.
        top_level = ", ".join(sorted(_top_level_names(repo_root))) or "(none)"
        pytest.fail(
            f"{len(stale)} stale path(s) found in cla.io/project-facts.md or a "
            f"per-skill overlay (path no longer exists on disk):\n{detail}\n"
            f"(recognized top-level prefixes: {top_level})"
        )


# ---------- self-tests of the checker's own machinery ----------


def test_stale_file_path_is_flagged(tmp_path):
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "apps").mkdir()
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "See `apps/retired-app/src/index.ts` for the old entry point.\n",
        encoding="utf-8",
    )
    stale = find_stale_paths(tmp_path)
    assert stale == [("cla.io/project-facts.md", 1, "apps/retired-app/src/index.ts")]


def test_stale_directory_path_is_flagged(tmp_path):
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "packages").mkdir()
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "The dataset lives at `packages/removed-package/data/`.\n", encoding="utf-8"
    )
    stale = find_stale_paths(tmp_path)
    assert stale == [("cla.io/project-facts.md", 1, "packages/removed-package/data/")]


def test_existing_file_and_directory_are_not_flagged(tmp_path):
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "apps" / "real-app" / "src").mkdir(parents=True)
    (tmp_path / "apps" / "real-app" / "src" / "index.ts").write_text("x", encoding="utf-8")
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "See `apps/real-app/src/index.ts` and `apps/real-app/src/` — both real.\n",
        encoding="utf-8",
    )
    assert find_stale_paths(tmp_path) == []


def test_url_glob_placeholder_and_unknown_top_level_segment_are_not_flagged(tmp_path):
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "apps").mkdir()
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Docs: `https://example.com/apps/foo` and `docs/**/*.md` and "
        "`apps/<app>/src/` and `references/project-context.md` (not repo-root) "
        "and `packages/engine/src/{types,ReachModel}.ts` (brace shorthand) and "
        "a bare `~/.gitconfig` path.\n",
        encoding="utf-8",
    )
    assert find_stale_paths(tmp_path) == []


def test_trailing_line_col_and_wrapping_punctuation_resolved_correctly(tmp_path):
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "packages" / "engine" / "src").mkdir(parents=True)
    (tmp_path / "packages" / "engine" / "src" / "engine.test.ts").write_text(
        "x", encoding="utf-8"
    )
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "See (`packages/engine/src/engine.test.ts:120`), and also "
        "`packages/engine/src/engine.test.ts:120:5`.\n",
        encoding="utf-8",
    )
    assert find_stale_paths(tmp_path) == []


def test_multiple_stale_paths_all_reported(tmp_path):
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "apps").mkdir()
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Bad: `apps/one/gone.ts`.\nAlso bad: `apps/two/gone.ts` and `apps/three/gone.ts`.\n",
        encoding="utf-8",
    )
    stale = find_stale_paths(tmp_path)
    assert len(stale) == 3
    assert {c for _, _, c in stale} == {
        "apps/one/gone.ts",
        "apps/two/gone.ts",
        "apps/three/gone.ts",
    }
    assert sorted(lineno for _, lineno, _ in stale) == [1, 2, 2]


def test_absent_facts_file_and_overlays_yield_no_scanned_files(tmp_path):
    assert list(_iter_scanned_files(tmp_path)) == []
    assert find_stale_paths(tmp_path) == []


def test_overlay_file_is_scanned_generically_not_hardcoded(tmp_path):
    skills = tmp_path / ".claude" / "plugins" / "cla" / "skills"
    (skills / "some-new-skill" / "references").mkdir(parents=True)
    (tmp_path / "apps").mkdir()
    (skills / "some-new-skill" / "references" / "project-context.md").write_text(
        "Stale: `apps/gone/here.ts`.\n", encoding="utf-8"
    )
    stale = find_stale_paths(tmp_path)
    assert stale == [
        (".claude/plugins/cla/skills/some-new-skill/references/project-context.md", 1, "apps/gone/here.ts")
    ]


def test_bare_non_backtick_path_is_flagged(tmp_path):
    # Pass B: a path written WITHOUT backticks (portable prose won't always wrap
    # paths) is still extracted and checked — the branch the real facts file leans on.
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "apps").mkdir()
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "The old entry was apps/retired/main.ts before the move.\n", encoding="utf-8"
    )
    stale = find_stale_paths(tmp_path)
    assert stale == [("cla.io/project-facts.md", 1, "apps/retired/main.ts")]


def test_bare_paren_wrapped_path_is_cleaned_and_flagged(tmp_path):
    # Pass B + wrapping strip on a bare (non-backtick) token wrapped in parens/comma.
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "apps").mkdir()
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "See the module (apps/gone/y.ts), which moved.\n", encoding="utf-8"
    )
    stale = find_stale_paths(tmp_path)
    assert stale == [("cla.io/project-facts.md", 1, "apps/gone/y.ts")]


def test_trailing_possessive_is_stripped(tmp_path):
    # `apps/operator's` in prose must resolve to apps/operator (real → not flagged);
    # a possessive on a stale path resolves to the stale base (→ flagged as that base).
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "apps" / "operator").mkdir(parents=True)
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "apps/operator's rail is real, but apps/gone's rail is not.\n", encoding="utf-8"
    )
    stale = find_stale_paths(tmp_path)
    assert stale == [("cla.io/project-facts.md", 1, "apps/gone")]


def test_top_level_prefix_set_is_repo_derived_not_hardcoded(tmp_path):
    # Proves the recognized prefixes come from THIS repo's own top-level entries,
    # not a hardcoded some-repo list: a path under a fictitious top-level dir that
    # DOES exist in this tmp repo (`widgets/`) is checked (→ flagged when stale),
    # while a path whose first segment is NOT a real top-level entry is skipped.
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "widgets").mkdir()  # a top-level dir some-repo does not have
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Checked (real top-level): `widgets/gone.ts`. "
        "Skipped (no such top-level): `nonexistent-top/foo.ts`.\n",
        encoding="utf-8",
    )
    stale = find_stale_paths(tmp_path)
    assert stale == [("cla.io/project-facts.md", 1, "widgets/gone.ts")]


def _init_git_repo(repo: Path, tracked_dirs: list[str]) -> None:
    """Minimal git repo with each of `tracked_dirs` committed as a top-level
    directory (each gets a placeholder file so git tracks the directory)."""
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    for d in tracked_dirs:
        (repo / d).mkdir(parents=True, exist_ok=True)
        (repo / d / "placeholder.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=repo, check=True)


def test_untracked_top_level_directory_is_not_recognized_in_a_real_repo(tmp_path):
    # The exact regression this guards: a live `repo_root.iterdir()` made the
    # guard's verdict depend on which stray UNTRACKED directories happen to
    # exist in a given checkout. Observed concretely — the same overlays
    # passed inside a clean worktree and failed on the primary clone, purely
    # because that clone contained an empty untracked `docs/`. With `docs/`
    # only committed, an untracked `stray-scratch/` in the SAME checkout must
    # not be recognized as a real top-level prefix.
    _init_git_repo(tmp_path, tracked_dirs=["cla.io", "apps"])
    (tmp_path / "stray-scratch").mkdir()  # untracked — never `git add`ed
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Skipped (untracked top-level, not in the committed tree): "
        "`stray-scratch/whatever.ts`.\n",
        encoding="utf-8",
    )
    assert find_stale_paths(tmp_path) == []


def test_tracked_top_level_directory_is_recognized_in_a_real_repo(tmp_path):
    # The positive half of the same fix: a COMMITTED top-level directory is
    # still recognized (and a stale path under it still flagged) once the
    # source switches from `iterdir()` to the committed tree.
    _init_git_repo(tmp_path, tracked_dirs=["cla.io", "apps"])
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Stale: `apps/gone.ts`.\n", encoding="utf-8",
    )
    assert find_stale_paths(tmp_path) == [("cla.io/project-facts.md", 1, "apps/gone.ts")]


def test_top_level_names_falls_back_to_iterdir_outside_a_git_repo(tmp_path):
    # This module's OWN self-tests (every test above this one) construct plain
    # `tmp_path` fixtures that are never git repos — the fallback below is not
    # hypothetical, it is what keeps all of them passing.
    (tmp_path / "widgets").mkdir()
    assert _top_level_names(tmp_path) == {"widgets"}


def test_tracked_top_level_names_returns_none_outside_a_git_repo(tmp_path):
    assert _tracked_top_level_names(tmp_path) is None


def test_tracked_top_level_names_returns_none_before_the_first_commit(tmp_path):
    # A repo right after `cla-init` scaffolds `cla.io/` but before the first
    # commit has an INDEX (once something is `git add`ed) but no `HEAD` yet —
    # this is exactly the case an earlier `git ls-tree HEAD`-based draft of
    # this function got wrong (rc != 0, "unknown revision"). Using the index
    # instead means a repo with nothing staged yet still correctly falls back
    # (empty index -> `names or None` -> `None`), rather than returning an
    # empty set that would make every path candidate silently unrecognized.
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    assert _tracked_top_level_names(tmp_path) is None


def test_scan_verdict_is_identical_regardless_of_a_stray_untracked_directory(tmp_path):
    # The most direct reproduction of the actual reported incident: the SAME
    # commit, compared with and without an empty untracked scratch directory
    # present — exactly the "clean worktree vs. primary clone with a stray
    # untracked docs/" scenario. The verdict must be byte-identical either way.
    _init_git_repo(tmp_path, tracked_dirs=["cla.io", "apps"])
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Stale: `apps/gone.ts`. Also references `docs/architecture.md`.\n",
        encoding="utf-8",
    )
    without_stray_dir = scan(tmp_path)
    (tmp_path / "docs").mkdir()  # the exact untracked directory from the incident
    with_stray_dir = scan(tmp_path)
    assert without_stray_dir == with_stray_dir


def test_a_staged_but_uncommitted_top_level_directory_is_recognized(tmp_path):
    # The gap `HEAD`-based resolution had and the index closes: a change that
    # adds a new top-level directory AND references a path under it in the
    # SAME uncommitted change must not go unrecognized until the next commit
    # — that would be the identical non-determinism this whole fix targets,
    # just re-keyed from "stray dirs" to "commit boundaries."
    _init_git_repo(tmp_path, tracked_dirs=["cla.io"])
    (tmp_path / "openspec").mkdir()
    (tmp_path / "openspec" / "new-file.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "openspec/new-file.md"], cwd=tmp_path, check=True)
    # Deliberately NOT committed — this is the state mid-flight in a working
    # session, before the change lands.
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Stale reference into the not-yet-committed dir: `openspec/gone.md`.\n",
        encoding="utf-8",
    )
    assert find_stale_paths(tmp_path) == [
        ("cla.io/project-facts.md", 1, "openspec/gone.md"),
    ]


def test_scan_reports_checked_count_and_is_nonzero_when_facts_present(tmp_path):
    # The non-vacuous signal the real-tree guard asserts on: `scan` reports how many
    # candidates were existence-checked, so a silent "checked nothing" no-op is
    # detectable rather than passing as an empty stale list.
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "apps" / "real").mkdir(parents=True)
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Real: `apps/real`. Stale: `apps/gone`.\n", encoding="utf-8"
    )
    checked, stale = scan(tmp_path)
    assert checked == 2
    assert stale == [("cla.io/project-facts.md", 1, "apps/gone")]


def test_bare_path_before_non_line_number_colon_is_resolved(tmp_path):
    # A bare (unbackticked) path glued to a non-line-number colon — prose like
    # "edit apps/x/y.ts: add a rule" — must strip the trailing colon and resolve,
    # not false-flag `apps/x/y.ts:` as a nonexistent path.
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "apps" / "x").mkdir(parents=True)
    (tmp_path / "apps" / "x" / "y.ts").write_text("k", encoding="utf-8")
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Edit apps/x/y.ts: add a rule there.\n", encoding="utf-8"
    )
    assert find_stale_paths(tmp_path) == []


def test_bare_single_segment_filename_is_not_checked(tmp_path):
    # Bare filenames (no `/`) are intentionally NOT checked — prose naming a
    # non-repo file (`package-lock.json`, `telemetry.json`) is indistinguishable
    # from a stale repo-file reference, so checking them false-positives.
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "apps").mkdir()
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "There is no package-lock.json anymore; the CLI's telemetry.json is external. "
        "But a real path `apps/gone/x.ts` is still checked.\n",
        encoding="utf-8",
    )
    stale = find_stale_paths(tmp_path)
    assert stale == [("cla.io/project-facts.md", 1, "apps/gone/x.ts")]


def test_markdown_emphasis_wrapped_path_resolved_but_real_glob_still_skipped(tmp_path):
    # `**path**`/`_path_` unwrap to the real path (checked); a genuine trailing-glob
    # `apps/*` (star at one end only) stays a glob and is skipped, not stripped.
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "apps").mkdir()
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Bold stale: **apps/gone/x.ts**. Emphasis stale: _apps/gone/y.ts_. "
        "A real glob is skipped: `apps/*`.\n",
        encoding="utf-8",
    )
    stale = find_stale_paths(tmp_path)
    assert {c for _, _, c in stale} == {"apps/gone/x.ts", "apps/gone/y.ts"}


def test_each_skip_reason_individually_yields_no_candidates(tmp_path):
    # Split from a single folded assert so a regression in ONE skip rule is
    # pinpointable rather than masked by the others.
    (tmp_path / "apps").mkdir()
    tln = _top_level_names(tmp_path)
    assert extract_path_candidates("`https://example.com/apps/foo`", tln) == []  # URL scheme
    assert extract_path_candidates("`docs/**/*.md`", tln) == []                  # glob
    assert extract_path_candidates("`apps/<app>/src/`", tln) == []               # <placeholder>
    assert extract_path_candidates("`packages/x/{a,b}.ts`", tln) == []           # brace shorthand
    assert extract_path_candidates("`~/.gitconfig`", tln) == []                  # ~ home path
    assert extract_path_candidates("`references/project-context.md`", tln) == [] # unknown top-level segment
    assert extract_path_candidates("`a-single-token-no-slash`", tln) == []       # no path separator


# --------------------------------------------------------------------------- #
# AA-8 — paths the staleness guard could not see (reported by a consuming repo)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "line, expected",
    [
        # A path inside a fenced JSON config block. Without `[`/`]` in
        # _WRAP_CHARS the quote never becomes an outer character, so a LIVE path
        # reads as stale forever.
        ('  "sources": ["cla.io/decisions"]', "cla.io/decisions"),
        # A single-element array presents BOTH brackets at once — which is why
        # one of the pair is not enough.
        ('["cla.io/feedback"]', "cla.io/feedback"),
        ('  ["cla.io/retro",', "cla.io/retro"),
    ],
)
def test_a_path_inside_a_json_block_is_still_extracted(line, expected, tmp_path):
    tops = {"cla.io"}
    assert expected in extract_path_candidates(line, tops), line


@pytest.mark.parametrize(
    "line",
    [
        "See [cla.io/decisions](cla.io/decisions) for the rationale.",
        "Compare [cla.io/retro][ref] against the ledger.",
    ],
)
def test_a_markdown_link_whose_text_is_a_path_is_not_reported_stale(line):
    """Adding brackets to _WRAP_CHARS alone breaks these: `[a/b](a/b)` cleans to
    `a/b](a/b`, a token that can never exist and so is flagged stale forever.
    Rejected by the two-char SEAM."""
    for cand in extract_path_candidates(line, {"cla.io"}):
        assert "](" not in cand and "][" not in cand, cand


def test_a_dynamic_route_segment_is_still_checkable():
    """Non-vacuity partner, and the reason the rejection is by seam rather than
    by brackets generally: `apps/x/[id]/page.tsx` contains `]/` and is a real,
    existence-checkable path. Rejecting brackets wholesale would discard it."""
    got = extract_path_candidates("edit apps/web/[id]/page.tsx now", {"apps"})
    assert any("[id]" in c for c in got), got
