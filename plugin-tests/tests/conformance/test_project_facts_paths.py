"""Unit tests for the promoted staleness checker.

The checker itself is no longer here. It is a program at
``skills/cla-setup/scripts/check_fact_paths.py`` — a consuming repo has no
pytest gate over the plugin cache, so a guard filed as a test module is
unreachable there in practice, while ``python3 <script>`` is not. What stays in
this file is the evidence that the checker works: the unit tests of its
extraction heuristics, and the CLI-layer tests of its exit-code contract.

The module is loaded **by file path** via ``importlib.util.spec_from_file_location``
rather than by adding a ``pythonpath`` entry to this scope's ``pyproject.toml``.
This scope deliberately has no ``pythonpath`` (its tests import nothing), and a
path-based load survives a later relocation of the checker with a one-line edit
instead of a scope-config change.

The repo-level assertion that used to live here —
``test_no_stale_paths_in_project_facts_or_overlays`` — is now the body of the
checker's ``main()``. Nothing else was dropped.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
CHECKER = _PLUGIN_ROOT / "skills" / "cla-setup" / "scripts" / "check_fact_paths.py"


def _vendored_repo_root():
    """The repo root ONLY when this plugin is vendored at `<root>/.claude/plugins/cla`.

    See the twin helper in `test_no_project_tokens.py` for the full rationale: a
    marketplace install puts the plugin in a version-keyed cache, where
    `parents[2]` is a cache directory, and running the real-repo gate from there
    reintroduces the wrong-root-reads-as-success defect the checkers were fixed
    for. Same layout rule the deleted `run_tests.py` used.
    """
    if _PLUGIN_ROOT.name != "cla" or _PLUGIN_ROOT.parent.name != "plugins":
        return None
    if _PLUGIN_ROOT.parents[1].name != ".claude":
        return None
    root = _PLUGIN_ROOT.parents[2]
    return root if (root / ".git").exists() else None


REPO_ROOT = _vendored_repo_root()


def _load_checker():
    spec = importlib.util.spec_from_file_location("_ut_check_fact_paths", CHECKER)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load the checker at {CHECKER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_checker = _load_checker()

# Bound at module level so every test below reads exactly as it did when the
# implementation lived in this file — the names and signatures are unchanged.
_repo_root_from_here = _checker._repo_root_from_here
_clean_candidate = _checker._clean_candidate
_tracked_top_level_names = _checker._tracked_top_level_names
_top_level_names = _checker._top_level_names
_iter_scanned_files = _checker._iter_scanned_files
extract_path_candidates = _checker.extract_path_candidates
scan = _checker.scan
find_stale_paths = _checker.find_stale_paths
main = _checker.main

EXIT_CLEAN = _checker.EXIT_CLEAN
EXIT_STALE = _checker.EXIT_STALE
EXIT_CANNOT_RUN = _checker.EXIT_CANNOT_RUN


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


# requirement: repo-context / Checking recorded paths
def test_a_machine_local_file_that_is_absent_is_skipped_not_reported(tmp_path):
    (tmp_path / "cla.io").mkdir()
    (tmp_path / ".claude").mkdir()
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Per-machine settings: `.claude/settings.local.json`, "
        "`cla.io/overlays/branch-prefix.local.md`. "
        "Real: `.claude`. Stale: `.claude/gone.json`.\n",
        encoding="utf-8",
    )
    stale = find_stale_paths(tmp_path)
    assert [c for _, _, c in stale] == [".claude/gone.json"]


def test_only_the_last_segment_and_a_whole_name_part_make_a_path_machine_local(tmp_path):
    # `notes.localized.md` and a `.local` directory are ordinary paths: stale when
    # absent. (`docs` is a real top-level here, so only the local rule could skip.)
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "docs" / "app.local").mkdir(parents=True)
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Gone: `docs/notes.localized.md` and `docs/app.local/gone.ts`.\n", encoding="utf-8"
    )
    assert [c for _, _, c in find_stale_paths(tmp_path)] == [
        "docs/notes.localized.md",
        "docs/app.local/gone.ts",
    ]


def test_a_tracked_file_with_a_local_name_part_is_checked(tmp_path):
    # The repo tracks files such as `cla.io/fleet.local.md`. Skipping every
    # `*.local.*` hid a rename of one; only an UNTRACKED one is machine-local.
    _init_git_repo(tmp_path, tracked_dirs=["cla.io", ".claude"])
    (tmp_path / "cla.io" / "fleet.local.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "cla.io/fleet.local.md"], cwd=tmp_path, check=True)
    (tmp_path / "cla.io" / "fleet.local.md").unlink()  # tracked, then renamed away
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Tracked: `cla.io/fleet.local.md`. Untracked: `.claude/settings.local.json`.\n",
        encoding="utf-8",
    )
    assert [c for _, _, c in find_stale_paths(tmp_path)] == ["cla.io/fleet.local.md"]


@pytest.mark.parametrize(
    "candidate, tracked, expected",
    [
        (".claude/settings.local.json", None, True),         # no index: nothing is tracked
        (".claude/settings.local.json", set(), True),         # untracked
        (".claude/settings.local.json", {".claude/settings.local.json"}, False),  # tracked
        ("cla.io/overlays/x.local.md/", {"cla.io/overlays/x.local.md"}, False),   # trailing slash
        ("apps/web/.env.local", set(), True),
        ("docs/notes.localized.md", set(), False),
        ("docs/app.local/gone.ts", set(), False),             # `.local` is not the file name
        ("docs/app.local.d/gone.ts", set(), False),           # `.local.` inside a directory name
        ("local/gone.ts", set(), False),
        ("apps/local/", set(), False),                        # a directory named `local`
        ("cla.io/x.local/", {"cla.io/x.local/f.md"}, False),  # a tracked directory
        ("cla.io/x.local/", {"cla.io/y.md"}, True),           # an untracked one
    ],
)
def test_is_machine_local(candidate, tracked, expected):
    assert _checker._is_machine_local(candidate, tracked) is expected


def test_a_directory_named_local_is_an_ordinary_path(tmp_path):
    # Only a `.local` NAME PART is machine-local; `local/` is just a directory.
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "local").mkdir()
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Gone: `local/gone.ts`.\n", encoding="utf-8"
    )
    assert [c for _, _, c in find_stale_paths(tmp_path)] == ["local/gone.ts"]


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


# requirement: repo-context / Checking recorded paths
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
    # A repo right after `cla-setup` scaffolds `cla.io/` but before the first
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
    checked, stale, _unreadable = scan(tmp_path)
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

# --------------------------------------------------------------------------- #
# Upstream #52 / #53 — the two ways this guard was silently inert downstream
# --------------------------------------------------------------------------- #


def test_a_leading_dot_survives_cleaning(tmp_path):
    """#53. `_WRAP_CHARS` contains `.`, and it was stripped from BOTH ends, so
    `.claude/x` became `claude/x` — whose first segment matches no tracked
    top-level entry, so `_keep_if_path` dropped it and the path was never
    checked. Every dotfile-rooted path was invisible: `.claude/**`, `.github/**`
    — exactly what a harness-facing facts file names most.

    Measured on the repo where it was found: 183 candidates checked, 0 stale,
    with four genuinely dead `.claude/`-rooted paths sitting in the scanned
    files. A trailing dot is still decoration and must still go.
    """
    assert _clean_candidate(".claude/hooks/x.py") == ".claude/hooks/x.py"
    assert _clean_candidate(".github/workflows/ci.yml") == ".github/workflows/ci.yml"
    assert _clean_candidate("`.claude/settings.json`.") == ".claude/settings.json"
    assert _clean_candidate("(src/app.ts:12),") == "src/app.ts"


def test_a_dead_dotfile_path_is_actually_reported(tmp_path):
    """The end-to-end partner: cleaning is only half of it — the candidate must
    reach the existence check and be reported."""
    _init_git_repo(tmp_path, [".claude", "src"])
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Hooks live in `.claude/hooks/gone.py`.\n", encoding="utf-8"
    )
    _checked, stale, _unreadable = scan(tmp_path)
    assert [s[2] for s in stale] == [".claude/hooks/gone.py"], (
        f"a dead .claude/-rooted path was not reported: {stale}"
    )


def test_the_repo_root_is_the_process_repo_not_the_users_home(monkeypatch, tmp_path):
    """#52. The old resolver walked to the first `.claude` ancestor of
    `__file__`. Under a marketplace install the plugin sits at
    `~/.claude/plugins/cache/...`, so that ancestor is the user's GLOBAL
    `.claude` and the function returned the HOME DIRECTORY — both guards in this
    scope then found no `cla.io/` there and skipped, green, in every consuming
    repo at once.

    Reproduced before the fix: resolved `C:\\Users\\<user>` for a repo at
    `C:\\code\\<repo>`.
    """
    _init_git_repo(tmp_path, ["src"])
    monkeypatch.chdir(tmp_path)
    resolved = _repo_root_from_here().resolve()
    assert resolved == tmp_path.resolve(), (
        f"resolved {resolved}, expected the process's repo {tmp_path}"
    )
    assert resolved != Path.home().resolve(), "resolved the user's home directory"


# --------------------------------------------------------------------------- #
# CLI layer — the exit-code contract the promotion introduced
# --------------------------------------------------------------------------- #
#
# The checker is now a program, so "does it exit 0/1/2 for the right reason" is
# a behaviour with no test above this line. Driven as a real subprocess rather
# than by calling `main()` in-process, because `sys.exit(main())` is part of the
# contract a consumer scripts against and an in-process call cannot see it.

_SCANNED_COUNT_RE = re.compile(r"(\d+) file\(s\) scanned")


def _run_cli(*args: str):
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120,
    )


def _seed_repo(tmp_path: Path, facts_body: str) -> None:
    (tmp_path / "cla.io").mkdir(exist_ok=True)
    (tmp_path / "apps" / "real").mkdir(parents=True, exist_ok=True)
    (tmp_path / "cla.io" / "project-facts.md").write_text(facts_body, encoding="utf-8")


def test_cli_exits_clean_and_reports_a_nonzero_scanned_file_count(tmp_path):
    # A zero-file scan reporting "0 stale paths" is the vacuous-pass bug, not a
    # pass — so the printed count is asserted, not merely the exit code.
    _seed_repo(tmp_path, "The real path is `apps/real`.\n")
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_CLEAN, result.stderr
    match = _SCANNED_COUNT_RE.search(result.stdout)
    assert match, f"no scanned-file count in output: {result.stdout!r}"
    assert int(match.group(1)) > 0, result.stdout


def test_cli_exits_clean_with_a_stated_reason_when_the_facts_file_is_absent(tmp_path):
    # A fresh repo that has installed the plugin but not yet run /cla:cla-setup
    # must not get a failing result — and must say why it passed.
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_CLEAN, result.stderr
    assert "project-facts.md" in result.stdout
    assert "nothing to scan" in result.stdout


def test_cli_exits_one_and_names_the_stale_path(tmp_path):
    _seed_repo(tmp_path, "Gone: `apps/retired/main.ts`.\n")
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_STALE, result.stdout + result.stderr
    assert "apps/retired/main.ts" in result.stdout


# requirement: repo-context / Checking recorded paths
def test_cli_exits_clean_on_an_absent_machine_local_path_and_one_on_an_ordinary_one(tmp_path):
    # Same file, one line each: the machine-local path is absent and skipped, the
    # ordinary path is absent and reported. The second half is what stops the skip
    # from being a blanket exemption.
    _seed_repo(tmp_path, "Real: `apps/real`. Local: `.claude/settings.local.json`.\n")
    (tmp_path / ".claude").mkdir()  # a real top-level dir, so only the `.local` rule can skip
    local_only = _run_cli("--repo-root", str(tmp_path))
    assert local_only.returncode == EXIT_CLEAN, local_only.stdout + local_only.stderr
    assert "settings.local.json" not in local_only.stdout

    _seed_repo(tmp_path, "Real: `apps/real`. Ordinary: `.claude/settings.json`.\n")
    ordinary = _run_cli("--repo-root", str(tmp_path))
    assert ordinary.returncode == EXIT_STALE, ordinary.stdout + ordinary.stderr
    assert ".claude/settings.json" in ordinary.stdout


def test_a_missing_tracked_file_index_is_reported_in_a_git_repo(monkeypatch, tmp_path, capsys):
    _init_git_repo(tmp_path, ["apps"])
    (tmp_path / "apps" / "real").mkdir(parents=True, exist_ok=True)
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "cla.io" / "project-facts.md").write_text("Real: `apps/real`.\n", encoding="utf-8")
    monkeypatch.setattr(_checker, "_tracked_paths", lambda repo_root: None)
    assert main(["--repo-root", str(tmp_path)]) == EXIT_CLEAN
    assert "could not list tracked files" in capsys.readouterr().out


def test_cli_reports_every_stale_path_not_only_the_first(tmp_path):
    # The accumulate-then-report promise: stopping at the first hit turns one run
    # into a fix-and-rerun loop, and a caller reading only the exit code cannot
    # tell the difference.
    _seed_repo(
        tmp_path,
        "First: `apps/one/gone.ts`.\nSecond: `apps/two/gone.ts`.\n",
    )
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_STALE, result.stdout + result.stderr
    assert "apps/one/gone.ts" in result.stdout, result.stdout
    assert "apps/two/gone.ts" in result.stdout, result.stdout


# --- the hint on a stale line whose path ends a tracked path elsewhere ---
#
# `scripts/common.py` written in an overlay to mean `invest/scripts/common.py` is
# checked at the root, where a different `scripts/` exists, and reported stale. No
# rule can tell that shorthand from a moved file, so it is still reported (exit 1);
# the line only gains a hint saying where the tail does exist.

_OVERLAY = Path("cla.io") / "overlays" / "review-change.md"
_HINT_PREFIX = "cla.io/overlays/review-change.md:3  stale path 'scripts/common.py'"


def _tail_repo(tmp_path: Path, files: list[str], body: str = "Run `scripts/common.py` first.\n") -> Path:
    """A real repo with a root `scripts/` (so `scripts/…` is a recognized path), the
    given extra tracked files, and an overlay holding `body` on its third line."""
    _init_git_repo(tmp_path, tracked_dirs=["cla.io", "scripts"])
    for rel in files:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x", encoding="utf-8")
    overlay = tmp_path / _OVERLAY
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.write_text("# overlay\n\n" + body, encoding="utf-8")
    _git(tmp_path, "add", "-A")
    return tmp_path


def _stale_lines(stdout: str) -> list[str]:
    return [ln for ln in stdout.splitlines() if "  stale path " in ln]


# requirement: repo-context / Checking recorded paths
def test_a_stale_path_that_ends_a_tracked_path_elsewhere_carries_a_hint(tmp_path):
    repo = _tail_repo(tmp_path, ["invest/scripts/common.py"])
    result = _run_cli("--repo-root", str(repo))
    assert result.returncode == EXIT_STALE, result.stdout + result.stderr
    (line,) = _stale_lines(result.stdout)
    assert line.startswith(_HINT_PREFIX)
    assert "not at the repo root; found at invest/scripts/common.py" in line
    assert "write it with a placeholder such as {plugin}/scripts/common.py" in line


def test_a_stale_path_with_no_tail_match_has_no_hint(tmp_path):
    repo = _tail_repo(tmp_path, ["invest/scripts/other.py"])
    result = _run_cli("--repo-root", str(repo))
    assert result.returncode == EXIT_STALE, result.stdout + result.stderr
    assert _stale_lines(result.stdout) == [_HINT_PREFIX]


def test_the_hint_never_alters_the_greppable_prefix_or_the_verdict(tmp_path):
    # Same input with and without a tail match: the same line prefix, the same exit
    # code, the same stale count. Only text after the prefix may differ.
    (tmp_path / "with").mkdir()
    (tmp_path / "without").mkdir()
    with_tail = _tail_repo(tmp_path / "with", ["invest/scripts/common.py"])
    without = _tail_repo(tmp_path / "without", [])
    hinted = _run_cli("--repo-root", str(with_tail))
    plain = _run_cli("--repo-root", str(without))
    assert hinted.returncode == plain.returncode == EXIT_STALE
    assert _stale_lines(hinted.stdout)[0].startswith(_stale_lines(plain.stdout)[0])
    assert _stale_lines(plain.stdout) == [_HINT_PREFIX]
    assert "1 stale path(s)" in hinted.stdout and "1 stale path(s)" in plain.stdout


def test_a_stale_directory_path_hints_at_the_tracked_directory(tmp_path):
    # `ls-files` lists files only, so a directory tail is found through its files.
    repo = _tail_repo(
        tmp_path, ["invest/scripts/sub/a.py"], body="See `scripts/sub` for the helpers.\n"
    )
    result = _run_cli("--repo-root", str(repo))
    assert result.returncode == EXIT_STALE, result.stdout + result.stderr
    (line,) = _stale_lines(result.stdout)
    assert line.startswith("cla.io/overlays/review-change.md:3  stale path 'scripts/sub'")
    assert "found at invest/scripts/sub — " in line


def test_the_hint_names_at_most_three_matches(tmp_path):
    repo = _tail_repo(tmp_path, [f"pkg{i}/scripts/common.py" for i in range(5)])
    result = _run_cli("--repo-root", str(repo))
    assert result.returncode == EXIT_STALE, result.stdout + result.stderr
    (line,) = _stale_lines(result.stdout)
    assert "found at pkg0/scripts/common.py, pkg1/scripts/common.py, pkg2/scripts/common.py (+2 more)" in line
    assert "pkg3/" not in line and "pkg4/" not in line


def test_without_git_the_line_has_no_hint_and_nothing_fails(monkeypatch, tmp_path, capsys):
    repo = _tail_repo(tmp_path, ["invest/scripts/common.py"])
    monkeypatch.setattr(_checker, "_tracked_paths", lambda repo_root: None)
    assert main(["--repo-root", str(repo)]) == EXIT_STALE
    assert _stale_lines(capsys.readouterr().out) == [_HINT_PREFIX]


@pytest.mark.parametrize(
    ("candidate", "tracked", "expected"),
    [
        ("scripts/common.py", None, []),
        ("scripts/common.py", {"invest/scripts/common.py"}, ["invest/scripts/common.py"]),
        # The candidate itself (deleted on disk but still in the index) is no "elsewhere".
        ("scripts/common.py", {"scripts/common.py"}, []),
        # A tail must start at a path segment, not mid-name.
        ("scripts/common.py", {"xscripts/common.py", "a/xscripts/common.py"}, []),
        ("scripts/sub", {"scripts/sub/a.py", "invest/scripts/sub/a.py", "invest/scripts/sub/b.py"},
         ["invest/scripts/sub"]),
        ("scripts/sub/", {"invest/scripts/sub/a.py"}, ["invest/scripts/sub"]),
    ],
)
def test_tail_matches(candidate, tracked, expected):
    assert _checker._tail_matches(candidate, tracked) == expected


def test_a_path_with_a_placeholder_is_never_checked(tmp_path):
    # What the hint tells the reader to write, and what the docs promise.
    repo = _tail_repo(
        tmp_path,
        ["invest/scripts/common.py"],
        # The real path keeps the scan from being the zero-candidates failure.
        # The placeholders sit AFTER the recognized top-level name `scripts`, so only
        # the placeholder rule (not the unknown-first-segment rule) can skip them.
        body="Real `scripts/placeholder.txt`; `scripts/{x}/common.py`; `scripts/<x>/common.py`.\n",
    )
    result = _run_cli("--repo-root", str(repo))
    assert result.returncode == EXIT_CLEAN, result.stdout + result.stderr
    assert _stale_lines(result.stdout) == []


def test_cli_exits_two_on_a_bad_argument():
    result = _run_cli("--not-a-real-flag")
    assert result.returncode == EXIT_CANNOT_RUN, result.stdout + result.stderr
    assert result.returncode != EXIT_STALE


def test_cli_exits_two_when_the_repo_root_does_not_exist(tmp_path):
    result = _run_cli("--repo-root", str(tmp_path / "no-such-dir"))
    assert result.returncode == EXIT_CANNOT_RUN, result.stdout + result.stderr
    assert "not a directory" in result.stderr


def test_cli_exits_two_when_a_scanned_file_is_present_but_unreadable(tmp_path):
    # The other half of "I could not look": a file that EXISTS and cannot be
    # decoded. Reporting it as clean is the vacuous-pass bug; reporting it as a
    # staleness sends the caller hunting a stale path that does not exist.
    # Added because the mutant that swapped this branch's exit code survived the
    # first batch run — the branch had no test at all.
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "cla.io" / "project-facts.md").write_bytes(
        b"See `apps/x/y.ts`\xff\xfe not utf-8\n"
    )
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_CANNOT_RUN, result.stdout + result.stderr
    assert result.returncode != EXIT_STALE
    assert "could not be read" in result.stderr


def test_cli_exits_two_when_a_present_facts_file_yields_no_candidates(tmp_path):
    # "I could not look" is not "I found nothing". A facts file that extracts
    # zero candidates means the heuristic or the root resolution broke, and
    # reporting that as a clean run is the exact silent no-op the guard exists
    # to preclude.
    _seed_repo(tmp_path, "Prose with no repo-relative path in it at all.\n")
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_CANNOT_RUN, result.stdout + result.stderr
    assert result.returncode != EXIT_CLEAN
    assert "zero path candidates" in result.stderr


def test_cli_exits_two_when_overlays_present_but_facts_file_absent_yields_no_candidates(tmp_path):
    # IMPORTANT-2: the zero-candidates blocker used to be gated on
    # `facts_file.is_file()`, so a repo with overlays but NO
    # cla.io/project-facts.md that extracts zero candidates exited 0 clean
    # instead of 2 — the guard silently checking nothing, just reached via the
    # overlay-only path instead of the facts-file path. An absent facts file
    # WITH overlays present must still lint the overlays and still be able to
    # report could-not-run.
    overlays = tmp_path / "cla.io" / "overlays"
    overlays.mkdir(parents=True)
    (overlays / "demo.md").write_text(
        "Prose with no repo-relative path in it at all.\n", encoding="utf-8"
    )
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_CANNOT_RUN, result.stdout + result.stderr
    assert result.returncode != EXIT_CLEAN
    assert "zero path candidates" in result.stderr


def test_main_exits_two_when_the_repo_root_cannot_be_resolved(monkeypatch, capsys):
    # IMPORTANT-4: a failed repo-root resolution used to fall back to
    # `Path.cwd()`, which reports a WRONG root as a trivial clean pass. Driven
    # in-process (not via subprocess) so the failure can be forced
    # deterministically regardless of the actual machine's git/`.claude` state.
    monkeypatch.setattr(_checker, "_repo_root_from_here", lambda: None)
    result = main([])
    captured = capsys.readouterr()
    assert result == EXIT_CANNOT_RUN
    assert result != EXIT_CLEAN
    assert "could not resolve the repo root" in captured.err


def test_iterdir_fallback_inside_a_real_git_repo_is_reported(monkeypatch, tmp_path, capsys):
    # SUGGESTION-9: `_tracked_top_level_names` returns `None` on ANY git
    # failure, not only the expected "this isn't a git repo" case, silently
    # reverting to the non-deterministic `iterdir()` mode the design rejected.
    # Forcing that branch INSIDE a real git repo must surface a diagnostic
    # rather than stay silent, even though it does not change the exit code.
    _init_git_repo(tmp_path, ["apps"])
    (tmp_path / "apps" / "real").mkdir(parents=True, exist_ok=True)
    (tmp_path / "cla.io").mkdir()
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Real: `apps/real`.\n", encoding="utf-8"
    )
    monkeypatch.setattr(_checker, "_tracked_top_level_names", lambda repo_root: None)
    result = main(["--repo-root", str(tmp_path)])
    captured = capsys.readouterr()
    assert result == EXIT_CLEAN  # the fallback is a diagnostic, not a failure
    # The exit code alone is NOT the subject of this test: EXIT_CLEAN is what the
    # branch returns whether or not it says anything. Assert the diagnostic
    # itself, or deleting the `print` leaves this test green while the silence
    # the test is named for comes straight back.
    assert "git ls-files` could not be used" in captured.out
    assert "live directory listing" in captured.out


# --------------------------------------------------------------------------- #
# A path under a top-level directory that was renamed or removed
# --------------------------------------------------------------------------- #
#
# `_keep_if_path` skips a path whose first segment is no tracked top-level name,
# so `old/src/x.ts` went unreported once `old/` was renamed. Git history tells that
# apart from plugin-relative shorthand (`skills/x/y.py`) or a repo name
# (`owner/name.js`), whose first segment was never a top-level name here.

_former_top_level_names = _checker._former_top_level_names


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _history_repo(tmp_path: Path, facts_body: str) -> Path:
    """A real repo whose history holds a top-level `old/` (renamed to `newer/`),
    a top-level `gone/` (deleted outright) and a top-level FILE `stale.txt`
    (deleted), with `apps/` and `cla.io/` still tracked."""
    _init_git_repo(tmp_path, tracked_dirs=["apps", "cla.io", "old", "gone"])
    (tmp_path / "stale.txt").write_text("x", encoding="utf-8")
    (tmp_path / "apps" / "dead.txt").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "stale.txt", "apps/dead.txt")
    _git(tmp_path, "commit", "-q", "-m", "add a top-level file and a file under apps")
    _git(tmp_path, "mv", "old", "newer")
    # `apps/dead.txt` is deleted but `apps/` stays: a still-live name must not count as former.
    _git(tmp_path, "rm", "-q", "-r", "gone", "stale.txt", "apps/dead.txt")
    (tmp_path / "cla.io" / "project-facts.md").write_text(facts_body, encoding="utf-8")
    _git(tmp_path, "add", "cla.io/project-facts.md")
    _git(tmp_path, "commit", "-q", "-m", "rename old, remove gone")
    return tmp_path


# requirement: repo-context / Checking recorded paths
def test_a_path_under_a_renamed_top_level_directory_is_reported(tmp_path):
    repo = _history_repo(tmp_path, "Real: `apps/placeholder.txt`. Old: `old/placeholder.txt`.\n")
    result = _run_cli("--repo-root", str(repo))
    assert result.returncode == EXIT_STALE, result.stdout + result.stderr
    assert "cla.io/project-facts.md:1  stale path 'old/placeholder.txt'" in result.stdout
    assert "git history is unavailable" not in result.stderr


# requirement: repo-context / Checking recorded paths
def test_a_path_under_a_deleted_top_level_directory_is_reported(tmp_path):
    # A rename-only query (`--diff-filter=R`) would miss this: nothing was renamed.
    repo = _history_repo(tmp_path, "Real: `apps/placeholder.txt`. Gone: `gone/placeholder.txt`.\n")
    result = _run_cli("--repo-root", str(repo))
    assert result.returncode == EXIT_STALE, result.stdout + result.stderr
    assert "stale path 'gone/placeholder.txt'" in result.stdout


# requirement: repo-context / Checking recorded paths
@pytest.mark.parametrize(
    "token",
    [
        "skills/cla-setup/scripts/x.py",  # plugin-relative shorthand
        "owner/name.js",                  # a repo name, not a path
        "_shared/references/x.md",
    ],
)
def test_a_first_segment_that_never_was_a_top_level_name_is_still_skipped(tmp_path, token):
    repo = _history_repo(tmp_path, f"Real: `apps/placeholder.txt`. Shorthand: `{token}`.\n")
    result = _run_cli("--repo-root", str(repo))
    assert result.returncode == EXIT_CLEAN, result.stdout + result.stderr
    assert token not in result.stdout


@pytest.mark.parametrize(
    "token",
    [
        "old/",                       # nothing after the first slash: a bare word such as a branch prefix
        "old/a\\|old/b",              # a grep pattern
        "gone/{a,b}.ts",              # brace shorthand is still a placeholder
        "newer/placeholder.txt",      # a current top-level name that does exist
        "stale.txt/x",                # a deleted top-level FILE never was a directory
    ],
)
def test_a_path_under_a_former_name_is_skipped_unless_it_looks_like_a_path_into_it(tmp_path, token):
    repo = _history_repo(tmp_path, f"Real: `apps/placeholder.txt`. Other: `{token}`.\n")
    result = _run_cli("--repo-root", str(repo))
    assert result.returncode == EXIT_CLEAN, result.stdout + result.stderr


def test_a_path_under_a_former_name_that_exists_on_disk_again_is_not_reported(tmp_path):
    # Untracked, so absent from the index, but present: a rename the user undid.
    repo = _history_repo(tmp_path, "Real: `apps/placeholder.txt`. Back: `old/placeholder.txt`.\n")
    (repo / "old").mkdir()
    (repo / "old" / "placeholder.txt").write_text("x", encoding="utf-8")
    assert _run_cli("--repo-root", str(repo)).returncode == EXIT_CLEAN


def test_a_bare_non_backtick_path_under_a_renamed_directory_is_reported(tmp_path):
    repo = _history_repo(tmp_path, "Real: `apps/placeholder.txt`. See old/placeholder.txt for it.\n")
    assert find_stale_paths(repo) == [("cla.io/project-facts.md", 1, "old/placeholder.txt")]


def test_a_rename_staged_but_not_committed_is_reported(tmp_path):
    # The usual moment this guard runs is right after `git mv`, before the commit.
    _init_git_repo(tmp_path, tracked_dirs=["apps", "cla.io", "old"])
    (tmp_path / "cla.io" / "project-facts.md").write_text(
        "Real: `apps/placeholder.txt`. Old: `old/placeholder.txt`.\n", encoding="utf-8"
    )
    _git(tmp_path, "mv", "old", "newer")
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_STALE, result.stdout + result.stderr
    assert "stale path 'old/placeholder.txt'" in result.stdout


def test_former_top_level_names_lists_only_directories_that_are_gone(tmp_path):
    repo = _history_repo(tmp_path, "Real: `apps/placeholder.txt`.\n")
    names, reason = _former_top_level_names(repo, _top_level_names(repo))
    assert (names, reason) == ({"old", "gone"}, "")


# requirement: repo-context / Checking recorded paths
def test_the_zero_candidates_exit_two_still_holds_when_history_names_former_directories(tmp_path):
    # Only never-top-level shorthand is named, so nothing is extracted: "I could not
    # look" stays exit 2 and is not turned into a clean pass by the history rule.
    repo = _history_repo(tmp_path, "Only shorthand: `skills/x/y.py` and `owner/name.js`.\n")
    result = _run_cli("--repo-root", str(repo))
    assert result.returncode == EXIT_CANNOT_RUN, result.stdout + result.stderr
    assert "zero path candidates" in result.stderr


# requirement: repo-context / Checking recorded paths
def test_a_shallow_clone_degrades_to_the_current_layout_and_says_so_on_stderr(tmp_path):
    (tmp_path / "source").mkdir()
    source = _history_repo(
        tmp_path / "source", "Real: `apps/placeholder.txt`. Old: `old/placeholder.txt`.\n"
    )
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", source.as_uri(), str(shallow)],
        check=True, capture_output=True,
    )
    assert (shallow / ".git" / "shallow").exists()
    result = _run_cli("--repo-root", str(shallow))
    # The renamed path goes unreported, as before this rule, and stderr says why.
    assert result.returncode == EXIT_CLEAN, result.stdout + result.stderr
    assert "git history is unavailable (shallow clone)" in result.stderr


def test_a_directory_that_is_not_a_git_repo_degrades_and_says_so_on_stderr(tmp_path):
    _seed_repo(tmp_path, "Real: `apps/real`. Old: `old/placeholder.txt`.\n")
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_CLEAN, result.stdout + result.stderr
    assert "git history is unavailable (not a git repository)" in result.stderr


def test_a_repo_with_no_commits_degrades_and_says_so_on_stderr(tmp_path):
    _seed_repo(tmp_path, "Real: `apps/real`.\n")
    _git(tmp_path, "init", "-q")
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_CLEAN, result.stdout + result.stderr
    assert "git history is unavailable (git log failed" in result.stderr


def test_a_repo_root_nested_in_a_larger_repo_sees_only_its_own_top_level_names(tmp_path):
    # git prints paths from ITS top level; the parent's deleted `old/` must not
    # become a former name of the subdirectory being checked.
    parent = _history_repo(tmp_path, "unused\n")
    sub = parent / "apps" / "sub"
    (sub / "cla.io").mkdir(parents=True)
    (sub / "real").mkdir()
    (sub / "real" / "f.txt").write_text("x", encoding="utf-8")
    (sub / "cla.io" / "project-facts.md").write_text(
        "Real: `real/f.txt`. Parent's old name: `old/placeholder.txt`.\n", encoding="utf-8"
    )
    _git(parent, "add", "apps/sub")
    (parent / "stagedgone").mkdir()
    (parent / "stagedgone" / "x.txt").write_text("x", encoding="utf-8")
    _git(parent, "add", "stagedgone")
    _git(parent, "commit", "-q", "-m", "add sub")
    _git(parent, "rm", "-q", "-r", "stagedgone")  # staged, not committed: a parent-level name
    names, reason = _former_top_level_names(sub, _top_level_names(sub))
    assert (names, reason) == (set(), "")
    assert _run_cli("--repo-root", str(sub)).returncode == EXIT_CLEAN


def test_a_failing_staged_diff_degrades_instead_of_reading_as_no_staged_deletions(monkeypatch, tmp_path):
    repo = _history_repo(tmp_path, "Real: `apps/placeholder.txt`.\n")
    real_run = subprocess.run

    def fail_the_diff(argv, *args, **kwargs):
        if "diff" in argv:
            return subprocess.CompletedProcess(argv, 1, "", "boom")
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(_checker.subprocess, "run", fail_the_diff)
    names, reason = _former_top_level_names(repo, _top_level_names(repo))
    assert names is None
    assert "git diff --cached failed" in reason


def test_git_that_cannot_be_run_degrades_instead_of_raising(monkeypatch, tmp_path):
    def boom(*args, **kwargs):
        raise OSError("no git here")

    monkeypatch.setattr(_checker.subprocess, "run", boom)
    names, reason = _former_top_level_names(tmp_path, set())
    assert names is None
    assert "git could not be run" in reason


def test_a_git_that_echoes_the_shallow_flag_back_degrades_instead_of_reading_full_history(monkeypatch, tmp_path):
    # Git before 2.15 does not know `--is-shallow-repository`: rev-parse prints the
    # flag back and exits 0. Read as "not shallow", a shallow clone would pass as full history.
    repo = _history_repo(tmp_path, "Real: `apps/placeholder.txt`.\n")
    real_run = subprocess.run

    def old_git(argv, *args, **kwargs):
        if "--is-shallow-repository" in argv:
            return subprocess.CompletedProcess(argv, 0, "--is-shallow-repository\n", "")
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(_checker.subprocess, "run", old_git)
    names, reason = _former_top_level_names(repo, _top_level_names(repo))
    assert names is None
    assert "git too old" in reason


def test_a_failed_shallow_probe_is_not_blamed_on_an_old_git(monkeypatch, tmp_path):
    repo = _history_repo(tmp_path, "Real: `apps/placeholder.txt`.\n")
    real_run = subprocess.run

    def broken(argv, *args, **kwargs):
        if "--is-shallow-repository" in argv:
            return subprocess.CompletedProcess(argv, 128, "", "fatal: boom")
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(_checker.subprocess, "run", broken)
    names, reason = _former_top_level_names(repo, _top_level_names(repo))
    assert names is None
    assert reason == "git rev-parse --is-shallow-repository failed (rc=128)"


def test_the_git_calls_share_one_time_budget(monkeypatch, tmp_path):
    repo = _history_repo(tmp_path, "Real: `apps/placeholder.txt`.\n")
    real_run = subprocess.run
    clock = [1000.0]
    timeouts = {}

    def slow_log(argv, *args, **kwargs):
        verb = "log" if "log" in argv else "diff" if "diff" in argv else "rev-parse"
        timeouts[verb] = kwargs["timeout"]
        if verb == "log":
            clock[0] += 50  # the history walk spends 50 of the 60 seconds
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(_checker.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(_checker.subprocess, "run", slow_log)
    names, _ = _former_top_level_names(repo, _top_level_names(repo))
    assert names == {"old", "gone"}
    assert timeouts["log"] == _checker._HISTORY_BUDGET_SECONDS
    assert timeouts["diff"] == _checker._HISTORY_BUDGET_SECONDS - 50


@pytest.mark.parametrize("verb", ["log", "diff"])
def test_a_git_call_past_the_budget_degrades_and_names_the_budget(monkeypatch, tmp_path, verb):
    repo = _history_repo(tmp_path, "Real: `apps/placeholder.txt`.\n")
    real_run = subprocess.run

    def hung_log(argv, *args, **kwargs):
        if verb in argv:
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(_checker.subprocess, "run", hung_log)
    names, reason = _former_top_level_names(repo, _top_level_names(repo))
    assert names is None
    assert reason == f"git ran past its {_checker._HISTORY_BUDGET_SECONDS}s budget"


# --------------------------------------------------------------------------- #
# CRITICAL-1 — nothing actually INVOKES this program anywhere in the repo
# --------------------------------------------------------------------------- #
#
# Every test above this line loads the checker as a MODULE (by file path) and
# calls its functions in-process — it never actually runs it as the program a
# consuming repo is meant to run. That gap is exactly how a synced-core leak
# (a curated token from cla.io/project-tokens.local.md appended to a SKILL.md,
# or here, a stale repo-relative path) can leave the suite fully green
# while the checker itself exits non-zero. This test is the missing
# invocation: it runs the real program, as a real subprocess, against the
# real repo root, so a real leak turns the suite red again.


@pytest.mark.skipif(
    REPO_ROOT is None,
    reason="plugin is not vendored at <root>/.claude/plugins/cla — see _vendored_repo_root",
)
def test_the_real_repo_is_clean_when_invoked_as_a_subprocess():
    result = subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=str(REPO_ROOT),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120,
    )
    detail = f"(cwd={REPO_ROOT})\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert result.returncode == 0, (
        f"check_fact_paths.py exited {result.returncode} against the real repo {detail}"
    )
    # Exit 0 alone is NOT enough — it also covers a trivial pass. Assert the scan
    # actually looked at something, or a resolver regression that scans nothing
    # keeps this gate green. Same reasoning as the twin gate in
    # `test_no_project_tokens.py`, where the trivial-pass mutation survived until
    # the summary line was asserted.
    scanned = re.search(r"(\d+) file\(s\) scanned", result.stdout)
    checked = re.search(r"(\d+) path candidate\(s\) checked", result.stdout)
    assert scanned and int(scanned.group(1)) > 0, f"zero files scanned {detail}"
    assert checked and int(checked.group(1)) > 0, (
        f"zero path candidates checked — the guard looked at nothing {detail}"
    )
