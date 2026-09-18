"""Unit tests for the promoted project-token / developer-path checker.

The checker itself is no longer here. It is a program at
``skills/_shared/scripts/check_no_project_tokens.py`` — a consuming repo has no
pytest gate over the plugin cache, so a guard filed as a test module is
unreachable there in practice, while ``python3 <script>`` is not. What stays in
this file is the evidence that the checker works: the unit tests of both
scanners, the non-vacuity tests, and the CLI-layer tests of the exit-code
contract.

The module is loaded **by file path** via ``importlib.util.spec_from_file_location``
rather than by adding a ``pythonpath`` entry to this scope's ``pyproject.toml``.
This scope deliberately has no ``pythonpath`` (its tests import nothing), and a
path-based load survives a later relocation of the checker with a one-line edit
instead of a scope-config change.

The FOUR repo-level assertions that used to live here —
``test_no_project_tokens_in_synced_core``,
``test_no_project_tokens_in_synced_source``,
``test_no_absolute_developer_paths_in_synced_source`` and
``test_every_scanned_file_is_actually_readable`` — are now the body of the
checker's ``main()``, which runs all four and accumulates across them. Nothing
else was dropped.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
CHECKER = _PLUGIN_ROOT / "skills" / "_shared" / "scripts" / "check_no_project_tokens.py"


def _vendored_repo_root():
    """The repo root ONLY when this plugin is vendored at `<root>/.claude/plugins/cla`.

    `_PLUGIN_ROOT.parents[2]` assumes that layout. A marketplace install does NOT
    have it — the plugin sits in a version-keyed cache under the user's global
    `~/.claude`, where `parents[2]` is a cache directory. Running the real-repo
    gate from there is the exact defect this file's own checker was fixed for
    (upstream issue #52, recorded in `check_no_project_tokens.py`'s `_repo_root`):
    a wrong root either fails a consuming repo for something it did not do, or —
    if the cache happens to sit under some git repo — resolves THAT repo, finds
    no token list, prints the trivial-pass note and exits 0. A green gate that
    never looked at the repo it claims to check.

    Same layout rule the deleted `run_tests.py` used. Returns None when it
    does not hold, and the gate below skips rather than asserting against a root
    it cannot trust.
    """
    if _PLUGIN_ROOT.name != "cla" or _PLUGIN_ROOT.parent.name != "plugins":
        return None
    if _PLUGIN_ROOT.parents[1].name != ".claude":
        return None
    root = _PLUGIN_ROOT.parents[2]
    return root if (root / ".git").exists() else None


REPO_ROOT = _vendored_repo_root()


def _load_checker():
    spec = importlib.util.spec_from_file_location("_ut_check_no_project_tokens", CHECKER)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load the checker at {CHECKER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_checker = _load_checker()

# Bound at module level so every test below reads exactly as it did when the
# implementation lived in this file — the names and signatures are unchanged.
_plugin_root = _checker._plugin_root
_repo_root = _checker._repo_root
load_tokens = _checker.load_tokens
_is_overlay = _checker._is_overlay
_iter_scanned_files = _checker._iter_scanned_files
_body_lines = _checker._body_lines
_violations_in = _checker._violations_in
find_violations = _checker.find_violations
_iter_scanned_source_files = _checker._iter_scanned_source_files
find_source_violations = _checker.find_source_violations
_starts_with_placeholder_user = _checker._starts_with_placeholder_user
find_absolute_path_leaks = _checker.find_absolute_path_leaks
find_unreadable_files = _checker.find_unreadable_files
main = _checker.main

ABS_PATH_EXEMPT_MARKER = _checker.ABS_PATH_EXEMPT_MARKER
TOKEN_LIST_RELPATH = _checker.TOKEN_LIST_RELPATH
SOURCE_SCAN_ROOTS = _checker.SOURCE_SCAN_ROOTS
EXIT_CLEAN = _checker.EXIT_CLEAN
EXIT_VIOLATIONS = _checker.EXIT_VIOLATIONS
EXIT_CANNOT_RUN = _checker.EXIT_CANNOT_RUN


def test_the_promoted_module_still_exposes_the_symbols_its_consumers_read():
    """`consistency-checks/tests/test_token_list_is_curated_here.py` reads these
    three off the guard rather than recomputing them, because a version of that
    check which computed its own repo root passed happily while the guard's
    anchor was off by one level and the guard skipped. A promotion that folded
    any of them into `main()` would break the guard that guards the token list,
    and nothing else would notice."""
    for name in ("_repo_root", "TOKEN_LIST_RELPATH", "load_tokens"):
        assert hasattr(_checker, name), (
            f"{name} is no longer a module-level name on the promoted checker"
        )


def test_the_positional_fallback_resolves_to_the_plugin_root_from_here():
    """The `parents[N]` fallback in `_plugin_root` is silent when wrong: the
    primary walk succeeds in every normal layout, so a stale depth surfaces only
    in the unexpected-layout case the fallback exists for. Checked by counting
    from the checker's ACTUAL location rather than by reading the literal."""
    depth = len(CHECKER.resolve().relative_to(_PLUGIN_ROOT).parts) - 1
    assert CHECKER.resolve().parents[depth] == _PLUGIN_ROOT
    source = CHECKER.read_text(encoding="utf-8")
    assert f"parents[{depth}]" in source, (
        f"the fallback depth should be parents[{depth}] from "
        f"{CHECKER.relative_to(_PLUGIN_ROOT).as_posix()}"
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


def test_a_skill_shaped_fixture_tree_under_an_excluded_subtree_is_not_scanned(tmp_path):
    # `EXCLUDED_SUBTREES` was unproven: emptying it left every test green. The
    # test above seeds plain `.md` files under `tests/` and `scripts/`, and those
    # are skipped anyway for being neither `SKILL.md` nor under a `references/`
    # ancestor — so the exclusion never decided anything there.
    #
    # It only bites for a fixture tree that MIMICS a skill, which is exactly what
    # a scope's `tests/` dir is likely to hold: a `references/` dir, or a
    # `SKILL.md`, nested inside `tests/` or `scripts/`. Found by a surviving
    # mutant, not by reading.
    skills = tmp_path / "skills"
    fixture_refs = skills / "demo" / "tests" / "fixtures" / "references"
    fixture_refs.mkdir(parents=True)
    (fixture_refs / "note.md").write_text("has funnel-demo\n", encoding="utf-8")
    fixture_skill = skills / "demo" / "scripts" / "fixtures"
    fixture_skill.mkdir(parents=True)
    (fixture_skill / "SKILL.md").write_text("has funnel-demo\n", encoding="utf-8")
    assert find_violations(skills, tmp_path, ["funnel-demo"]) == []


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


def test_source_scan_covers_json_under_the_scan_roots(tmp_path):
    # Issue #190. `required-permissions.json` carries English prose in `_comment`
    # keys and already named the workflow it serves "in this repo" — prose in
    # synced core, which is exactly what this guard exists to catch, sitting in
    # the one suffix no scanner opened. Both the prose-bearing shape and the
    # hook-wiring shape are pinned, because a rule reaching only files under
    # `references/` would pass the first of these and miss the second.
    _seed(
        tmp_path,
        "skills/_shared/references/required-permissions.json",
        '{\n  "_comment": "for the funnel-demo workflow",\n  "allow": []\n}\n',
    )
    _seed(tmp_path, "hooks/hooks.json", '{\n  "note": "wired for funnel-demo"\n}\n')
    # The prose scan globs `*.md`, so neither is reachable from it.
    assert find_violations(tmp_path / "skills", tmp_path, ["funnel-demo"]) == []
    rels = sorted(h[0] for h in find_source_violations(tmp_path, ["funnel-demo"]))
    assert rels == [
        "hooks/hooks.json",
        "skills/_shared/references/required-permissions.json",
    ]


def test_source_scan_leaves_json_outside_the_scan_roots_alone(tmp_path):
    # `.claude-plugin/plugin.json` ships, carries a `description`, and is NOT in
    # scope: the widening added a SUFFIX, not a root. Pinned because "scan .json"
    # read loosely would sweep the manifest in, and the manifest legitimately
    # names this repository.
    #
    # THE SECOND SEED IS A POSITIVE CONTROL, not decoration. The first version of
    # this test seeded only the manifest and asserted no violations — and with no
    # scan root present in `tmp_path` at all, `_iter_scanned_source_files`
    # `continue`s past all five and yields nothing. Absence asserted over an
    # empty scan is exactly what a scanner whose body is `return` produces, so
    # the test passed against the OLD scanner too and could not fail on any edit
    # to the suffix rule. Three reviewers measured that independently. Seeding a
    # `.json` inside a root and asserting the result is EXACTLY that file proves
    # the scan ran and that the manifest was excluded, in one assertion.
    _seed(tmp_path, ".claude-plugin/plugin.json", '{\n  "name": "funnel-demo"\n}\n')
    _seed(tmp_path, "hooks/hooks.json", '{\n  "note": "wired for funnel-demo"\n}\n')
    rels = sorted(h[0] for h in find_source_violations(tmp_path, ["funnel-demo"]))
    assert rels == ["hooks/hooks.json"]


def test_source_scan_reports_a_token_in_a_json_description_key(tmp_path):
    # Named for what it pins: a `description` key is NOT exempt in a `.json` the
    # way frontmatter is in an `agents/`/`output-styles/` `.md`. That exemption
    # exists for a `description:` legitimately naming the host repo so the asset
    # is selected for it; a `.json` has no such need and must not grow one, since
    # prose in a `_comment` or `description` key IS the leak that motivated
    # widening to `.json`.
    #
    # It was first called `..._does_not_strip_frontmatter_from_json`, and that
    # name promised something it cannot deliver. `_body_lines` skips nothing
    # unless line 1 is exactly `---`, and a JSON document opens with `{` — so
    # flipping `strip_fm` to `.json` is a NO-OP on this input and the test stays
    # green. Two reviewers ran both branches on this fixture and got byte-equal
    # output. The right response is not a `---`-fenced JSON fixture, which is not
    # realistic input and would be an unkillable mutant by CLAUDE.md's own rule;
    # it is to name the edit the test can actually catch.
    _seed(
        tmp_path,
        "skills/_shared/references/required-permissions.json",
        '{\n  "description": "funnel-demo permissions",\n  "allow": []\n}\n',
    )
    hits = find_source_violations(tmp_path, ["funnel-demo"])
    assert [h[0] for h in hits] == [
        "skills/_shared/references/required-permissions.json"
    ]


def test_source_scan_covers_sh_under_the_scan_roots(tmp_path):
    # Issue #254, and the same argument `.json` made one suffix earlier. The
    # plugin ships exactly one shell script, `hooks/probe-python.sh`, and that
    # file became the declared home of the hook wiring's rationale when the
    # loader rejected `hooks.json`'s `_comment` array. Moving ~37 lines of
    # hand-written English out of a scanned file and into an unscanned one is how
    # a leak surface is created, so the suffix moved with the prose.
    #
    # Both shapes are seeded for the reason the `.json` case seeds two: a rule
    # keyed on a path fragment rather than a suffix would pass on the real
    # file's location and miss a `.sh` anywhere else under the roots.
    _seed(tmp_path, "hooks/probe-python.sh", "# the funnel-demo wiring\nPYEXE=\n")
    _seed(tmp_path, "skills/demo/scripts/helper.sh", "# helper for funnel-demo\n")
    # The prose scan globs `*.md`, so neither is reachable from it.
    assert find_violations(tmp_path / "skills", tmp_path, ["funnel-demo"]) == []
    rels = sorted(h[0] for h in find_source_violations(tmp_path, ["funnel-demo"]))
    assert rels == ["hooks/probe-python.sh", "skills/demo/scripts/helper.sh"]


def test_source_scan_leaves_sh_outside_the_scan_roots_alone(tmp_path):
    # The widening added a SUFFIX, not a root — the same distinction the `.json`
    # case pins on the manifest. A `.sh` at the plugin root sits outside all five
    # roots and stays out of scope.
    #
    # THE SECOND SEED IS A POSITIVE CONTROL, for the reason recorded on the
    # `.json` twin: with no scan root present in `tmp_path`,
    # `_iter_scanned_source_files` `continue`s past all five and yields nothing,
    # so an absence asserted over an empty scan passes against ANY scanner,
    # including one that never grew the suffix. Asserting the result is EXACTLY
    # the in-root file proves the scan ran and that the outside one was excluded.
    _seed(tmp_path, "install.sh", "# installs funnel-demo\n")
    _seed(tmp_path, "hooks/probe-python.sh", "# the funnel-demo wiring\n")
    rels = sorted(h[0] for h in find_source_violations(tmp_path, ["funnel-demo"]))
    assert rels == ["hooks/probe-python.sh"]


def test_source_scan_reports_a_token_in_a_sh_comment(tmp_path):
    # What the widening is actually FOR. A shell script has no frontmatter
    # concept, so nothing is stripped and a comment is scanned like any other
    # line — which is the whole point, since the prose that moved into
    # `probe-python.sh` is entirely comments.
    _seed(
        tmp_path,
        "hooks/probe-python.sh",
        "# WHY THE CHECK IS -x. Measured against the funnel-demo wiring.\nPYEXE=\n",
    )
    hits = find_source_violations(tmp_path, ["funnel-demo"])
    assert [h[0] for h in hits] == ["hooks/probe-python.sh"]
    # The reported line is the comment itself, 1-based, not the file.
    assert [h[2] for h in hits] == [1]


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
    # The `.json` half is asserted against the REAL tree, not only a fixture:
    # the fixture test above proves the rule can fire, while this proves it fires
    # on the shipped files the widening was for. A rule correct in `tmp_path` and
    # unreachable in the real plugin — a root pruned, a suffix typo'd — passes
    # the fixture test and leaves the actual gap open.
    assert any(p.suffix == ".json" for p in scanned)
    # `.sh` gets the same real-tree assertion for the same reason, and it is the
    # narrowest of the three: the plugin ships exactly ONE shell script, so if a
    # root is pruned or the suffix typo'd, this is the only thing between that
    # and a silently unscanned file — the file that now holds the hook wiring's
    # entire rationale.
    assert any(p.suffix == ".sh" for p in scanned)


# --------------------------------------------------------------------------- #
# CLI layer — the exit-code contract the promotion introduced
# --------------------------------------------------------------------------- #
#
# The checker is now a program, so "does it exit 0/1/2 for the right reason, and
# does one run really perform all four checks" is a behaviour with no test above
# this line. Driven as a real subprocess rather than by calling `main()`
# in-process, because `sys.exit(main())` is part of the contract a consumer
# scripts against and an in-process call cannot see it.

_PROSE_COUNT_RE = re.compile(r"(\d+) prose file\(s\)")
_SOURCE_COUNT_RE = re.compile(r"(\d+) source file\(s\)")


def _run_cli(*args: str):
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120,
    )


def _seed_vendored_plugin(tmp_path: Path) -> Path:
    """A minimal, CLEAN vendored plugin tree inside a fake consuming repo.

    Built as path components rather than one literal string for the same reason
    the checker builds it that way: a sibling guard fails a synced-core file that
    spells the install path out.
    """
    plugin = tmp_path / ".claude" / "plugins" / "cla"
    (plugin / "skills" / "demo").mkdir(parents=True)
    (plugin / "skills" / "demo" / "SKILL.md").write_text(
        "# Demo\n\nPortable prose with nothing project-specific in it.\n",
        encoding="utf-8",
    )
    # A `.py` under skills/ as well as one under hooks/, so the source scan has
    # two roots to reach. `skills/**/*.md` is prose-only — it contributes nothing
    # to the source scan — so seeding SKILL.md alone would leave `skills` absent
    # from the reached-roots line and make that assertion meaningless.
    (plugin / "skills" / "demo" / "scripts").mkdir(parents=True)
    (plugin / "skills" / "demo" / "scripts" / "helper.py").write_text(
        'BASE = "skills/demo/fixtures"\n', encoding="utf-8"
    )
    (plugin / "hooks").mkdir(parents=True)
    (plugin / "hooks" / "sample.py").write_text(
        'BASE = "hooks/tests/fixtures"\n', encoding="utf-8"
    )
    # Every entry in SOURCE_SCAN_ROOTS must exist for this to read as a CLEAN,
    # complete install — `_missing_source_roots` (IMPORTANT-5 fix) treats an
    # absent root as a broken/partial install and blocks on it. The other six
    # roots carry no test content, so they're created empty; only `skills` and
    # `hooks` above need real files.
    for root_name in SOURCE_SCAN_ROOTS:
        (plugin / root_name).mkdir(parents=True, exist_ok=True)
    return plugin


def _seed_token_list(tmp_path: Path, body: str) -> None:
    path = tmp_path / TOKEN_LIST_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_cli_exits_clean_and_reports_nonzero_scanned_counts(tmp_path):
    # A zero-file scan reporting "0 violations" is the vacuous-pass bug, not a
    # pass — so the printed counts are asserted, not merely the exit code.
    _seed_vendored_plugin(tmp_path)
    _seed_token_list(tmp_path, "- funnel-demo\n")
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_CLEAN, result.stdout + result.stderr
    prose = _PROSE_COUNT_RE.search(result.stdout)
    source = _SOURCE_COUNT_RE.search(result.stdout)
    assert prose and int(prose.group(1)) > 0, result.stdout
    assert source and int(source.group(1)) > 0, result.stdout
    # The count alone cannot show a source scan that collapsed to one root, so
    # the run names the roots it reached and both seeded ones must appear.
    assert "source roots reached: hooks, skills" in result.stdout, result.stdout


def test_cli_exits_clean_with_a_stated_reason_when_the_token_list_is_absent(tmp_path):
    # A destination repo that has installed the plugin but not curated a list
    # must not get a failing result — and must say why it passed.
    _seed_vendored_plugin(tmp_path)
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_CLEAN, result.stdout + result.stderr
    assert "no token verdict" not in result.stderr
    assert TOKEN_LIST_RELPATH.as_posix() in result.stdout
    assert "trivial pass" in result.stdout


def test_cli_fails_on_a_present_but_empty_token_list_and_says_how_to_disable(tmp_path):
    # A populated list broken by a later formatting change is a defect, not a
    # fresh repo. Silently skipping it would disable the guard with no signal.
    _seed_vendored_plugin(tmp_path)
    _seed_token_list(tmp_path, "# heading only\n<!-- a comment -->\n\n")
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_VIOLATIONS, result.stdout + result.stderr
    assert "yields no tokens" in result.stdout
    assert "Delete the file" in result.stdout


def test_cli_reports_violations_from_more_than_one_check_in_a_single_run(tmp_path):
    # The accumulate-across-all-four promise. Three of the four checks are made
    # to fire at once: (a) a project token in prose, (c) a hardcoded developer
    # path in source, and (d) a file the scanners cannot read. Stopping after
    # the first would leave the other two invisible, and check (d) in particular
    # is invisible to every other assertion.
    plugin = _seed_vendored_plugin(tmp_path)
    _seed_token_list(tmp_path, "- funnel-demo\n")
    (plugin / "skills" / "demo" / "SKILL.md").write_text(
        "# Demo\n\nThis names funnel-demo in the body.\n", encoding="utf-8"
    )
    (plugin / "hooks" / "leak.py").write_text(
        'BASE = "C:/Users/alice/code/thing"\n', encoding="utf-8"  # path-fixture-ok
    )
    (plugin / "hooks" / "binary.py").write_bytes(b"\xff\xfe\x00\x01 not utf-8 \xff")
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_VIOLATIONS, result.stdout + result.stderr
    assert "funnel-demo" in result.stdout, result.stdout
    assert "windows-drive-path" in result.stdout, result.stdout
    assert "hooks/binary.py" in result.stdout, result.stdout


def test_cli_reports_the_readability_check_even_when_nothing_else_fires(tmp_path):
    # Check (d) on its own. It reads like plumbing and is the one keeping the
    # other three from passing vacuously, so it gets a case that cannot be
    # satisfied by any of them.
    plugin = _seed_vendored_plugin(tmp_path)
    _seed_token_list(tmp_path, "- funnel-demo\n")
    (plugin / "hooks" / "binary.py").write_bytes(b"\xff\xfe\x00\x01 not utf-8 \xff")
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_VIOLATIONS, result.stdout + result.stderr
    assert "hooks/binary.py" in result.stdout
    assert "cannot be read as UTF-8" in result.stdout


def test_cli_exits_two_on_a_bad_argument():
    result = _run_cli("--not-a-real-flag")
    assert result.returncode == EXIT_CANNOT_RUN, result.stdout + result.stderr
    assert result.returncode != EXIT_VIOLATIONS


def test_cli_exits_two_when_the_repo_root_does_not_exist(tmp_path):
    result = _run_cli("--repo-root", str(tmp_path / "no-such-dir"))
    assert result.returncode == EXIT_CANNOT_RUN, result.stdout + result.stderr
    assert "not a directory" in result.stderr


def test_cli_exits_two_when_a_populated_token_list_has_nothing_to_scan(tmp_path):
    # "I could not look" is not "I found nothing". A populated token list with an
    # empty scan root means the roots or filters broke; reporting that as clean
    # is the silent no-op the guard exists to preclude.
    plugin = tmp_path / ".claude" / "plugins" / "cla"
    plugin.mkdir(parents=True)
    _seed_token_list(tmp_path, "- funnel-demo\n")
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_CANNOT_RUN, result.stdout + result.stderr
    assert result.returncode != EXIT_CLEAN
    assert "scanned zero files" in result.stderr


def test_cli_exits_two_when_scan_finds_nothing_even_without_a_token_list(tmp_path):
    # IMPORTANT-3: the zero-files-scanned blocker used to fire ONLY when a
    # token list had loaded, so a scan that found NOTHING AT ALL — including
    # for checks (c)/(d), which the docstring says are always armed regardless
    # of a token list — silently passed clean whenever no token list existed.
    plugin = tmp_path / ".claude" / "plugins" / "cla"
    for root_name in SOURCE_SCAN_ROOTS:
        (plugin / root_name).mkdir(parents=True, exist_ok=True)
    # No token list, and every scan root exists but is empty.
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_CANNOT_RUN, result.stdout + result.stderr
    assert result.returncode != EXIT_CLEAN
    assert "scanned zero files" in result.stderr


def test_cli_exits_two_when_an_expected_source_scan_root_is_missing(tmp_path):
    # IMPORTANT-5: `_iter_scanned_source_files` silently `continue`s past an
    # absent scan root — only REACHED roots were ever named, never
    # expected-but-absent ones — so a whole missing root (heavy coverage loss)
    # used to exit 0 clean.
    plugin = _seed_vendored_plugin(tmp_path)
    _seed_token_list(tmp_path, "- funnel-demo\n")
    (plugin / "lib").rmdir()  # empty dir seeded by _seed_vendored_plugin
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_CANNOT_RUN, result.stdout + result.stderr
    assert result.returncode != EXIT_CLEAN
    assert "lib" in result.stderr
    assert "expected-but-absent: lib" in result.stdout


def test_cli_violations_win_over_a_coexisting_blocker(tmp_path):
    # IMPORTANT-10: when blockers and confirmed violations coexist in the same
    # run, violations must win — exit 1 with both reported — not exit 2, which
    # would let "I could not look" mask "I found problems" from a caller
    # reading only the exit code.
    plugin = _seed_vendored_plugin(tmp_path)
    # An unreadable token list is a BLOCKER (the token-load try/except).
    token_path = tmp_path / TOKEN_LIST_RELPATH
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_bytes(b"- funnel-demo\xff\xfe not utf-8\n")
    # An absolute developer path leak is a VIOLATION via check (c), which needs
    # no token list at all — independent of the blocker above.
    (plugin / "hooks" / "leak.py").write_text(
        'BASE = "C:/Users/alice/code/thing"\n', encoding="utf-8"  # path-fixture-ok
    )
    result = _run_cli("--repo-root", str(tmp_path))
    assert result.returncode == EXIT_VIOLATIONS, result.stdout + result.stderr
    assert result.returncode != EXIT_CANNOT_RUN
    assert "windows-drive-path" in result.stdout, result.stdout
    assert "could not be read" in result.stderr, result.stderr


def test_main_exits_two_when_the_repo_root_cannot_be_resolved(monkeypatch, capsys):
    # IMPORTANT-4: a failed repo-root resolution used to fall back to
    # `Path.cwd()`, which reports a WRONG root as a trivial clean pass. Driven
    # in-process (not via subprocess) so the failure can be forced
    # deterministically regardless of the actual machine's git/`.claude` state.
    monkeypatch.setattr(_checker, "_repo_root", lambda: None)
    result = main([])
    captured = capsys.readouterr()
    assert result == EXIT_CANNOT_RUN
    assert result != EXIT_CLEAN
    assert "could not resolve the repo root" in captured.err


# --------------------------------------------------------------------------- #
# CRITICAL-1 — nothing actually INVOKES this program anywhere in the repo
# --------------------------------------------------------------------------- #
#
# Every test above this line loads the checker as a MODULE (by file path) and
# calls its functions in-process — it never actually runs it as the program a
# consuming repo is meant to run. That gap is exactly how a synced-core leak
# (a curated token from cla.io/project-tokens.local.md appended to a SKILL.md)
# can leave the suite fully green while the checker itself exits 1. This
# test is the missing invocation: it runs the real program, as a real
# subprocess, against the real repo root, so a real leak turns the suite
# red again.


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
    detail = (
        f"(cwd={REPO_ROOT})\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert result.returncode == 0, (
        f"check_no_project_tokens.py exited {result.returncode} against the "
        f"real repo {detail}"
    )
    # Exit 0 alone is NOT enough, and this is the recursion of the very defect
    # this gate exists for: exit 0 also covers a TRIVIAL PASS. Point
    # `TOKEN_LIST_RELPATH` at a name that does not exist and the token scans
    # degrade to "0 token(s) loaded" and still exit 0 — the gate stays green with
    # checks (a) and (b) disarmed. Measured: that mutation survived until these
    # assertions existed. So assert the scan was non-vacuous, not just quiet.
    tokens = re.search(r"(\d+) token\(s\) loaded", result.stdout)
    assert tokens and int(tokens.group(1)) > 0, (
        f"the guard loaded no tokens — checks (a)/(b) were disarmed and it still "
        f"exited 0 {detail}"
    )
    prose = _PROSE_COUNT_RE.search(result.stdout)
    source = _SOURCE_COUNT_RE.search(result.stdout)
    assert prose and int(prose.group(1)) > 0, f"zero prose files scanned {detail}"
    assert source and int(source.group(1)) > 0, f"zero source files scanned {detail}"
