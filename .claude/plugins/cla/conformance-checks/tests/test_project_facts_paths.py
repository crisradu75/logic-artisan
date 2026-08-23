"""Unit tests for the promoted staleness checker.

The checker itself is no longer here. It is a program at
``skills/sync-context/scripts/check_fact_paths.py`` — a consuming repo has no
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

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
CHECKER = _PLUGIN_ROOT / "skills" / "sync-context" / "scripts" / "check_fact_paths.py"


def _vendored_repo_root():
    """The repo root ONLY when this plugin is vendored at `<root>/.claude/plugins/cla`.

    See the twin helper in `test_no_project_tokens.py` for the full rationale: a
    marketplace install puts the plugin in a version-keyed cache, where
    `parents[2]` is a cache directory, and running the real-repo gate from there
    reintroduces the wrong-root-reads-as-success defect the checkers were fixed
    for. Same layout rule as `run_tests.py`'s `_is_source_repo`.
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
    # A fresh repo that has installed the plugin but not yet run /cla:sync-context
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
# CRITICAL-1 — nothing actually INVOKES this program anywhere in the repo
# --------------------------------------------------------------------------- #
#
# Every test above this line loads the checker as a MODULE (by file path) and
# calls its functions in-process — it never actually runs it as the program a
# consuming repo is meant to run. That gap is exactly how a synced-core leak
# (a curated token from cla.io/project-tokens.local.md appended to a SKILL.md,
# or here, a stale repo-relative path) can leave `run_tests.py` fully green
# while the checker itself exits non-zero. This test is the missing
# invocation: it runs the real program, as a real subprocess, against the
# real repo root, so a real leak turns this scope — and therefore
# `run_tests.py` — red again.


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
