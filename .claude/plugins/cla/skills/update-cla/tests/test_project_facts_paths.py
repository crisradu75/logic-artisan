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

import re
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
_WRAP_CHARS = "`'\"(),;.:"

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


def _top_level_names(repo_root: Path) -> set[str]:
    """The repo's own real top-level entries (files + dirs), derived at runtime —
    NOT a hardcoded prefix list, so this ports to a repo of any layout."""
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
        pytest.fail(
            f"{len(stale)} stale path(s) found in cla.io/project-facts.md or a "
            f"per-skill overlay (path no longer exists on disk):\n{detail}"
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
    # not a hardcoded agentic-air list: a path under a fictitious top-level dir that
    # DOES exist in this tmp repo (`widgets/`) is checked (→ flagged when stale),
    # while a path whose first segment is NOT a real top-level entry is skipped.
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "widgets").mkdir()  # a top-level dir agentic-air does not have
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Checked (real top-level): `widgets/gone.ts`. "
        "Skipped (no such top-level): `nonexistent-top/foo.ts`.\n",
        encoding="utf-8",
    )
    stale = find_stale_paths(tmp_path)
    assert stale == [("cla.io/project-facts.md", 1, "widgets/gone.ts")]


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
