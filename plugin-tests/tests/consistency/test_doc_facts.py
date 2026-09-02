"""Drift guard: the counts and paths this repo's own docs assert must be true.

The plugin's behaviour lives mostly in markdown, and so does its documentation —
a prose edit ships like code but nothing compiles it. Five numbers in particular
are restated across four files (`CLAUDE.md`, `README.md`, `DEVELOPER-GUIDE.md`,
the plugin's own `README.md`) and every one of them has been wrong at least once:
the skill count, the pytest-scope count, the count of skills shipping tests, the
leaf-hook count, and the release version.

A sixth guarded fact is not a number: whether Claude may invoke a given skill — a
value that lives in each `SKILL.md`'s frontmatter and is restated in three docs
at once (the plugin README's phase table per skill, and a sentence naming the
skills in `CLAUDE.md` and `DEVELOPER-GUIDE.md`). It rots the same way and is
guarded the same way, at the end of this file.

They go wrong the same way every time. Someone deletes a skill or adds a scope,
fixes the number in the file they happened to be editing, and misses the other
three — and no test anywhere reads a `.md`, so the suite stays green while the
docs describe a repo that no longer exists. A 2026-08 review found exactly that:
a guide naming six hooks that did not exist and a scope count wrong in three
places at once.

This file is the repo-specific half of the pair. Its portable sibling,
`conformance-checks/tests/test_skill_lint.py`, lints the SKILL.md -> references
graph, which is true for every consuming repo. What is asserted here is true only
for THIS repo's own documentation, which is why it lives in `consistency-checks/`.

Anchoring rule: match a distinctive phrase and read the number out of it, rather
than pinning a whole sentence. Pinning the sentence would fail on any rewording
and train people to "fix" the test by loosening it.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_REPO_ROOT = _PLUGIN_ROOT.parents[2]

_DOCS = {
    "CLAUDE.md": _REPO_ROOT / "CLAUDE.md",
    "README.md": _REPO_ROOT / "README.md",
    "DEVELOPER-GUIDE.md": _REPO_ROOT / "DEVELOPER-GUIDE.md",
    "plugin README.md": _PLUGIN_ROOT / "README.md",
}

_PYTEST_MARKER = "[tool.pytest.ini_options]"
_EXCLUDED_DIRS = {"__pycache__", ".pytest_cache", ".git", ".venv", "node_modules"}

# Generated caches are excluded by NAME above. A nested CHECKOUT cannot be, and
# that distinction is the whole of `_is_nested_checkout` below.
#
# This repo's `new-worktree` skill puts a worktree at `.claude/worktrees/<name>`
# by default, and the Agent tool's worktree isolation uses the same place — so a
# second full checkout of the repo sits inside the repo whenever anyone works the
# way the repo tells them to. `real_scope_dirs()` then finds that copy's
# `plugin-tests/` and reports 2 pytest scopes, failing a doc claim that is
# CORRECT, which is the worst shape of false failure: it invites someone to
# "fix" the docs to match a miscount.
#
# Excluding the literal name `worktrees` was the first fix and it is too narrow.
# `manual_worktree.py` exposes `--worktree-dir`, so the default is an input, not
# a law; a worktree at `.worktrees/`, at `wt/`, or reached through a directory
# junction is still a second checkout and was still counted. It is also too
# broad in the other direction — it would hide any directory that merely happens
# to be named `worktrees`.
#
# A git worktree and a submodule both carry their own `.git` entry, and the repo
# root's own `.git` is the one that must not count. That is structural, so it
# holds for every placement rather than for the default one.
#
# `real_scope_dirs()` is the only repo-root-wide walk in this scope. Measured:
# `grep -rn 'rglob\|\.glob(' plugin-tests/tests/{consistency,conformance}/`
# returns 22 hits, of which exactly 2 are `_REPO_ROOT.rglob` and both are in
# `real_scope_dirs()`; the rest start from the plugin root, the dev tree,
# `cla.io/overlays`, or `.claude/skills`, none of which contains a checkout.


def _is_nested_checkout(directory: Path) -> bool:
    """True for a second checkout inside the repo — a worktree or a submodule.

    Both carry their own `.git` entry (a file for a worktree, a directory for a
    clone).

    The `!= _REPO_ROOT` guard is belt-and-braces, not the mechanism: `_excluded`
    walks ancestors STRICTLY BELOW the root, so this is never called with the
    root and a mutant removing the guard cannot be killed. What actually keeps
    the root's own `.git` harmless is that loop's starting point. The guard stays
    because this helper reads as general-purpose and a future caller may not
    share that invariant — but it is not what the tests are proving.
    """
    return directory != _REPO_ROOT and (directory / ".git").exists()


# ---------- ground truth, computed from the tree ----------


def real_skill_count() -> int:
    """A skill is a directory with a SKILL.md. `_shared/` has none, by design."""
    return len(list((_PLUGIN_ROOT / "skills").glob("*/SKILL.md")))


def _excluded(path: Path) -> bool:
    """True if `path` sits under an excluded directory INSIDE the repo.

    Relative to `_REPO_ROOT`, not against the absolute parts. The absolute form
    reads the parts of the whole filesystem path, so a repo that happens to be
    checked out under a directory with an excluded name excludes its own entire
    tree and every count silently becomes 0 — measured on this branch, running
    from `<repo>/.claude/worktrees/agent-<id>/` took `real_scope_dirs()` to `[]`
    and turned four correct doc claims red with `assert 0 in [1]`. That is the
    same false-failure shape the `worktrees` entry was added to remove, reached
    from the other side, and it applies to `.git`/`node_modules`/`.venv` too.
    """
    try:
        rel = path.relative_to(_REPO_ROOT)
    except ValueError:  # pragma: no cover - callers only pass paths under the root
        # Falling back to `path.parts` here would re-introduce the exact bug this
        # function exists to remove: it reads the parts of the whole filesystem
        # path, so a repo checked out below a directory with an excluded name
        # excludes its own entire tree. Say "not excluded" instead — a path
        # outside the root is not this repo's, and the caller's walk never
        # produces one.
        return False
    if _EXCLUDED_DIRS & set(rel.parts):
        return True
    # Any ANCESTOR that is itself a checkout means this path belongs to a second
    # copy of the repo, not to this one.
    directory = _REPO_ROOT
    for part in rel.parts[:-1]:
        directory = directory / part
        if _is_nested_checkout(directory):
            return True
    return False


def real_scope_dirs() -> list[Path]:
    """Every pytest scope in the repo: a dir with BOTH a pytest-configured
    pyproject.toml and a tests/ subdir.

    Scanned from the REPO root, not the plugin root. Before
    `extract-dev-tree-from-plugin` the twelve scopes lived inside the plugin,
    so scanning the plugin was the same question. They now live in
    `<repo>/plugin-tests/`, and a plugin-rooted scan would answer 0 — which
    would silently demand every doc claim "0 pytest scopes" rather than the
    one that exists."""
    pytest_dirs = {
        p.parent
        for p in _REPO_ROOT.rglob("pyproject.toml")
        if not _excluded(p) and _PYTEST_MARKER in p.read_text(encoding="utf-8")
    }
    tests_dirs = {
        p.parent
        for p in _REPO_ROOT.rglob("tests")
        if p.is_dir() and not _excluded(p)
    }
    return sorted(pytest_dirs & tests_dirs)


def real_skills_with_tests() -> int:
    """Directories under the dev tree's `tests/skills/` that are actually SKILLS.

    Re-derived over `plugin-tests/tests/skills/` rather than over the scope
    list. Before `extract-dev-tree-from-plugin` a skill's tests sat inside the
    skill and each was its own scope, so "scope under skills/ with a SKILL.md"
    was the whole question. The tests moved out; the FACT did not change and is
    still worth pinning, so the helper follows the tests rather than being
    deleted.

    `tests/skills/_shared/` has tests and lives under `skills/`, but `_shared/`
    has no SKILL.md and is therefore not a skill — counting it would make every
    doc that says "N skills ship tests" wrong by one, which is exactly the drift
    this file is supposed to detect rather than cause.

    A skill's SKILL.md may sit in the plugin OR in `<repo>/.claude/skills/`:
    `release` is a skill with tests, it is simply repo-local rather than
    shipped."""
    tests_root = _REPO_ROOT / "plugin-tests" / "tests" / "skills"
    if not tests_root.is_dir():
        return 0
    count = 0
    for d in sorted(tests_root.iterdir()):
        if not d.is_dir() or _EXCLUDED_DIRS & {d.name}:
            continue
        shipped = _PLUGIN_ROOT / "skills" / d.name / "SKILL.md"
        repo_local = _REPO_ROOT / ".claude" / "skills" / d.name / "SKILL.md"
        if shipped.is_file() or repo_local.is_file():
            count += 1
    return count


def _numbers_near(doc: str, phrase: str) -> list[int]:
    """Every integer on a line containing `phrase`. Returns [] when absent, which
    the caller treats as "the claim moved" rather than "the claim is fine"."""
    out = []
    for line in doc.splitlines():
        if phrase in line:
            out.extend(int(n) for n in re.findall(r"\b(\d{1,3})\b", line))
    return out


# ---------- the assertions ----------


# `test_the_scope_discovery_rule_here_matches_what_run_tests_finds` stood here.
# It read `run_tests.py` and asserted `len(real_scope_dirs()) >= 8`. Both halves
# died with `extract-dev-tree-from-plugin`: the runner is deleted, and the twelve
# scopes are now one, which no `>= 8` floor can satisfy. Do not restore it — a
# check against a file that no longer exists is not coverage.


def test_the_release_version_agrees_across_the_manifest_and_the_prose():
    """`test_marketplace_manifest.py` already pins plugin.json against the
    marketplace ref. CLAUDE.md carries a third copy that nothing checked, and it
    sat one release stale until a review caught it."""
    version = json.loads(
        (_PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )["version"]
    claude_md = _DOCS["CLAUDE.md"].read_text(encoding="utf-8")
    match = re.search(r"\*\*Current release: `cla--v([0-9.]+)`", claude_md)
    assert match, (
        "CLAUDE.md no longer states `**Current release: `cla--v<version>`**`. Either "
        "restore that phrasing or delete this assertion deliberately — do not let "
        "the claim drift back in unchecked."
    )
    assert match.group(1) == version, (
        f"CLAUDE.md says release {match.group(1)}, plugin.json says {version}"
    )


# The two path prefixes worth existence-checking in prose. Was
# `.claude/plugins/cla/` alone, which is exactly what `extract-dev-tree-from-plugin`
# broke: it moved the docs' most-cited paths — every test, the mutation runner,
# `mutate.py` invocations — into `plugin-tests/`, which sat unchecked by this
# guard the whole time the docs were being rewritten to point at it.
_DEAD_PATH_PREFIXES = (r"\.claude/plugins/cla/", r"plugin-tests/")


@pytest.mark.parametrize("name", sorted(_DOCS))
def test_no_doc_names_a_plugin_path_that_no_longer_exists(name):
    """Paths under `.claude/plugins/cla/` or `plugin-tests/` named in prose,
    checked for existence. Concrete paths only — a glob or placeholder segment
    names a shape, not a file."""
    doc = _DOCS[name].read_text(encoding="utf-8")
    missing = []
    for prefix in _DEAD_PATH_PREFIXES:
        for raw in re.findall(prefix + r"[A-Za-z0-9._/-]+", doc):
            cleaned = raw.rstrip(".,;:)`")
            if any(ch in cleaned for ch in "*<>") or cleaned.endswith("/"):
                continue
            if not (_REPO_ROOT / cleaned).exists():
                missing.append(f"  {name}: {cleaned}")
    assert not missing, "doc names a plugin path that does not exist:\n" + "\n".join(missing)


def test_the_skill_count_in_the_readme_is_the_real_one():
    doc = _DOCS["README.md"].read_text(encoding="utf-8")
    claimed = _numbers_near(doc, "workflow skills")
    assert claimed, "README.md no longer states an `<N> workflow skills` count"
    assert real_skill_count() in claimed, (
        f"README.md claims {claimed} workflow skills; the tree has {real_skill_count()}"
    )


@pytest.mark.parametrize(
    "name,phrase",
    [
        ("CLAUDE.md", "pytest scope —"),
        ("README.md", "every pytest scope"),
        ("DEVELOPER-GUIDE.md", "all pytest scopes"),
        ("plugin README.md", "isolated\npytest scope"),
    ],
)
def test_every_stated_pytest_scope_count_is_the_real_one(name, phrase):
    doc = _DOCS[name].read_text(encoding="utf-8")
    # The plugin README states the count across a wrapped line; normalise first.
    haystack = doc if "\n" not in phrase else doc
    lookup = phrase.replace("\n", " ")
    flat = " ".join(haystack.split())
    if lookup not in flat:
        pytest.fail(
            f"{name} no longer states its pytest-scope count near {lookup!r}; "
            "reword the doc or update this anchor deliberately"
        )
    window = flat[flat.index(lookup) : flat.index(lookup) + 220]
    claimed = [int(n) for n in re.findall(r"\b(\d{1,3})\b", window)]
    assert len(real_scope_dirs()) in claimed, (
        f"{name} states {claimed} near {lookup!r}; the real scope count is "
        f"{len(real_scope_dirs())}"
    )


def test_a_worktree_copy_is_not_counted_as_a_second_scope(tmp_path, monkeypatch):
    """Plant the worktree, rather than waiting for someone to have one.

    A live worktree is not a fixture — it exists on the machine of whoever
    happens to be mid-task and nowhere else, so on a clean clone this exclusion
    has no witness at all and a mutant that removes it would survive. The whole
    defect was invisible for the same reason: the checks above pass in a bare
    clone and go red the moment `/cla:new-worktree` or the Agent tool's worktree
    isolation puts a full checkout at `.claude/worktrees/<name>/`. Worse, they go
    red on a doc statement that is CORRECT, which invites someone to "fix" the
    docs to match the miscount — the exact drift this file exists to prevent,
    caused by this file.
    """
    real = tmp_path / "plugin-tests"
    (real / "tests").mkdir(parents=True)
    (real / "pyproject.toml").write_text(_PYTEST_MARKER + "\n", encoding="utf-8")

    # A real worktree carries its own `.git` — a FILE holding a `gitdir:`
    # pointer, where a clone would have a directory. The exclusion keys on that
    # rather than on the directory's name, so it holds wherever the worktree is
    # put. `manual_worktree.py` exposes `--worktree-dir`, so the default
    # `.claude/worktrees` is an input, not a law.
    wt = tmp_path / ".claude" / "worktrees" / "agent-xyz"
    (wt / "plugin-tests" / "tests").mkdir(parents=True)
    (wt / "plugin-tests" / "pyproject.toml").write_text(
        _PYTEST_MARKER + "\n", encoding="utf-8"
    )
    (wt / ".git").write_text("gitdir: /somewhere/.git/worktrees/agent-xyz\n", encoding="utf-8")

    monkeypatch.setattr(sys.modules[__name__], "_REPO_ROOT", tmp_path)
    found = real_scope_dirs()

    assert found == [real], (
        f"real_scope_dirs() returned {found}; a checkout under "
        ".claude/worktrees/ is the SAME scope seen twice, not a second one"
    )


@pytest.mark.parametrize(
    "where",
    [
        ".worktrees/agent-xyz",          # a leading-dot variant
        "wt/agent-xyz",                  # nothing worktree-shaped in the name
        ".claude/worktree/agent-xyz",    # singular, a plausible typo or config
        "vendor/nested/checkout",        # somewhere nobody would think to exclude
    ],
)
def test_a_checkout_is_excluded_wherever_it_is_placed(where, tmp_path, monkeypatch):
    """The name-based exclusion only covered the default placement.

    `manual_worktree.py` takes `--worktree-dir`, so a worktree can legitimately
    sit anywhere, and a submodule always does. Keying on the `.git` entry makes
    the rule structural: it is a second checkout because it carries its own
    checkout marker, not because of what someone named the directory.
    """
    real = tmp_path / "plugin-tests"
    (real / "tests").mkdir(parents=True)
    (real / "pyproject.toml").write_text(_PYTEST_MARKER + "\n", encoding="utf-8")

    nested = tmp_path / Path(where)
    (nested / "plugin-tests" / "tests").mkdir(parents=True)
    (nested / "plugin-tests" / "pyproject.toml").write_text(
        _PYTEST_MARKER + "\n", encoding="utf-8"
    )
    (nested / ".git").write_text("gitdir: /somewhere\n", encoding="utf-8")

    monkeypatch.setattr(sys.modules[__name__], "_REPO_ROOT", tmp_path)
    found = real_scope_dirs()
    assert found == [real], (
        f"a checkout at {where!r} was counted as a second scope; the exclusion "
        "is keyed on the directory's NAME rather than on it being a checkout"
    )


def test_a_directory_merely_named_worktrees_is_still_counted(tmp_path, monkeypatch):
    """The over-exclusion side, which the name-based rule got wrong.

    Excluding every directory called `worktrees` hides a real scope that
    happens to sit under one. No witness in this repo today, which is exactly
    why it needs planting rather than waiting for one.
    """
    real = tmp_path / "docs" / "worktrees" / "plugin-tests"
    (real / "tests").mkdir(parents=True)
    (real / "pyproject.toml").write_text(_PYTEST_MARKER + "\n", encoding="utf-8")

    monkeypatch.setattr(sys.modules[__name__], "_REPO_ROOT", tmp_path)
    found = real_scope_dirs()
    assert found == [real], (
        f"real_scope_dirs() returned {found}; a directory named 'worktrees' "
        "that holds no .git is not a checkout and must stay visible"
    )


def test_the_exclusion_reads_repo_relative_parts_not_absolute_ones(
    tmp_path, monkeypatch
):
    """The other side of the same coin, and the one with no natural witness.

    An exclusion matched against a path's ABSOLUTE parts is scoped to the whole
    filesystem, so it fires on the repo's own location: every file below a repo
    that happens to sit under an excluded name inherits that name, the scan
    excludes the entire tree, and four correct doc claims fail as
    `assert 0 in [1]`. It only shows up where the repo happens to live, so the
    root is planted under an excluded name here rather than hoping.

    The containing name must be one that is STILL excluded. This fixture used
    `worktrees`, and when the exclusion became structural — keyed on a `.git`
    entry rather than on the name — the fixture stopped reproducing the bug and
    a mutant restoring `path.parts` survived. `node_modules` is a name-based
    entry and is not going away.
    """
    root = tmp_path / "node_modules" / "clone"
    (root / "plugin-tests" / "tests").mkdir(parents=True)
    (root / "plugin-tests" / "pyproject.toml").write_text(
        _PYTEST_MARKER + "\n", encoding="utf-8"
    )

    monkeypatch.setattr(sys.modules[__name__], "_REPO_ROOT", root)

    assert real_scope_dirs() == [root / "plugin-tests"], (
        "a repo checked out under a directory with an excluded name excluded "
        "its own whole tree; the scan must be relative to the repo root"
    )


@pytest.mark.parametrize(
    "name,phrase",
    [
        ("CLAUDE.md", "skill that ships tests"),
        ("DEVELOPER-GUIDE.md", "skills with tests"),
        ("plugin README.md", "that ships tests*"),
    ],
)
def test_every_stated_skills_with_tests_count_is_the_real_one(name, phrase):
    flat = " ".join(_DOCS[name].read_text(encoding="utf-8").split())
    if phrase not in flat:
        pytest.fail(f"{name} no longer states a skills-with-tests count near {phrase!r}")
    # The count sits before the phrase in one file ("4 skills with tests") and
    # after it in another ("skill that ships tests (4 today)"), so look both ways.
    at = flat.index(phrase)
    window = flat[max(0, at - 40) : at + 120]
    claimed = [int(n) for n in re.findall(r"\b(\d{1,3})\b", window)]
    assert real_skills_with_tests() in claimed, (
        f"{name} states {claimed} near {phrase!r}; the real count is "
        f"{real_skills_with_tests()}"
    )


def real_leaf_hook_count() -> int:
    """Leaf guard hooks: every `hooks/*.py` that is neither a dispatcher nor a
    shared library. The dispatchers run the leaves; they are not guards."""
    hooks = _PLUGIN_ROOT / "hooks"
    return len(
        [
            p
            for p in hooks.glob("*.py")
            if not p.name.startswith("dispatch-") and not p.name.startswith("_")
        ]
    )


@pytest.mark.parametrize("name", ["CLAUDE.md", "DEVELOPER-GUIDE.md", "plugin README.md"])
def test_every_stated_leaf_hook_count_is_the_real_one(name):
    """The motivating drift for this whole file was a guide naming six hooks that
    did not exist. Counting them is the cheap half of catching that."""
    flat = " ".join(_DOCS[name].read_text(encoding="utf-8").split())
    if "leaf hook" not in flat:
        pytest.fail(
            f"{name} no longer states a leaf-hook count (phrase 'leaf hook'); "
            "reword the doc or update this anchor deliberately"
        )
    # These docs legitimately state TWO numbers around this phrase — the 7 leaves
    # the dispatchers run, and the 8 leaf hook FILES once the directly-wired
    # PostToolUse hook is counted. Requiring the real total to appear in ANY such
    # window keeps the assertion true without forcing one phrasing on the prose.
    claimed = set()
    for m in re.finditer("leaf hook", flat):
        window = flat[max(0, m.start() - 80) : m.start() + 80]
        claimed.update(int(n) for n in re.findall(r"\b(\d{1,3})\b", window))
    assert real_leaf_hook_count() in claimed, (
        f"{name} states {sorted(claimed)} near 'leaf hook'; the tree has "
        f"{real_leaf_hook_count()} leaf hooks"
    )


def test_every_named_leaf_hook_exists():
    """The other half, and the one that actually shipped: six invented hook names
    in a single guide section. A backticked `block-`/`ask-`/`warn-`/`guard-` name
    is read as a live hook; mention a deleted one WITHOUT backticks if the
    reference is historical.

    The `(?:\\.py)?` is load-bearing, not decoration: without it a backticked
    `` `guard-x.py` `` matched nothing at all — the character class cannot match a
    dot — so the one spelling most likely to name a real hook file was the one
    spelling this guard could not see."""
    missing = []
    for name, path in _DOCS.items():
        text = path.read_text(encoding="utf-8")
        for hook in re.findall(r"`((?:block|ask|warn|guard)-[a-z0-9-]+(?:\.py)?)`", text):
            stem = hook[:-3] if hook.endswith(".py") else hook
            if not (_PLUGIN_ROOT / "hooks" / f"{stem}.py").is_file():
                missing.append(f"  {name}: `{hook}` has no hooks/{stem}.py")
    assert not missing, (
        "doc names a guard hook that does not exist on disk:\n" + "\n".join(missing)
    )


def test_the_repo_roots_own_git_does_not_exclude_the_whole_tree(tmp_path, monkeypatch):
    """The identity guard in `_is_nested_checkout`, which has no natural witness.

    Every real repo root holds a `.git`. Without `directory != _REPO_ROOT` the
    root reads as a nested checkout, every path below it is "inside a checkout",
    and `real_scope_dirs()` returns [] — the same `assert 0 in [1]` failure the
    absolute-parts bug produces, reached from a third direction. No fixture in
    this file planted a root-level `.git`, so a mutant removing the guard
    survived while every other one was killed.
    """
    (tmp_path / ".git").mkdir()
    real = tmp_path / "plugin-tests"
    (real / "tests").mkdir(parents=True)
    (real / "pyproject.toml").write_text(_PYTEST_MARKER + "\n", encoding="utf-8")

    monkeypatch.setattr(sys.modules[__name__], "_REPO_ROOT", tmp_path)
    assert real_scope_dirs() == [real], (
        "the repo root's own .git made it read as a nested checkout, so the "
        "scan excluded the entire tree it was pointed at"
    )


# --- ground truth: the phase table's "Invoked by" column ---------------------
#
# The column restates a fact that lives in each skill's frontmatter, which is
# this file's whole subject: a derived value copied into prose goes stale when
# the source changes and nothing reads the prose. The named rot is a THIRD skill
# setting `disable-model-invocation: true` while the table still shows it as
# model-invocable, telling a reader Claude may start an unattended orchestrator
# on a description match.
#
# **Read the frontmatter with the repo's parser, not a string compare.** The
# first draft of this guard tested `line.strip() == "disable-model-invocation:
# true"`, which is one of at least six legal YAML spellings of that fact — and
# review found it misses `True`, `yes`, `"true"`, a doubled space, and an inline
# `# comment`. The last is the likely one: BOTH existing skills already carry
# exactly that rationale as a comment on the preceding lines, so an author
# shortening it to one line disarms the guard. Worse, it disarms it in the
# silent direction — if the table is also not updated, both sets stay at two and
# the guard passes in its own headline scenario.
#
# `test_skill_lint.parse_frontmatter` already bounds the block strictly, skips
# comment lines, and splits on `partition(":")`. It lives in another area
# directory, so it is loaded by path — the same `importlib` route
# `test_guards_have_mutant_batches.py` uses. Duplicating it here would give this
# repo two frontmatter parsers that can disagree, which is the class of defect
# the whole file exists to catch.

_USER_ONLY_MARK = "**you only**"

# Every value the Invoked by column may hold. Asserted as a closed set so that a
# DELETED cell, or a real skill relabelled as a non-skill row, is caught — the
# marked-set comparison below sees neither, because both leave the marks alone.
_LEGAL_INVOCATION_CELLS = {
    "you or Claude",
    _USER_ONLY_MARK,
    "n/a — vendored",
    "n/a — dispatched",
}

# YAML's spellings of true. `parse_frontmatter` hands back the raw value with an
# inline comment still attached, so the comment is stripped before comparison.
_YAML_TRUE = {"true", "yes", "on"}

_TABLE_HEADER = "| Phase | Skill | Invoked by | What it does |"


def _load_parse_frontmatter():
    """The repo's one frontmatter parser, loaded from the conformance area.

    Not importable by name: `tests/conformance` is not on `pythonpath` (see
    `plugin-tests/pyproject.toml`), and relying on pytest's import-mode side
    effects would make this depend on collection order.
    """
    path = Path(__file__).resolve().parents[1] / "conformance" / "test_skill_lint.py"
    spec = importlib.util.spec_from_file_location("_skill_lint_for_doc_facts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse_frontmatter


def _declares_user_only(text: str) -> bool:
    """True when this SKILL.md's frontmatter forbids model invocation."""
    mapping, error = _load_parse_frontmatter()(text)
    if error is not None:
        # A malformed SKILL.md is `test_skill_lint`'s finding, not this one.
        # Reporting it here too would give one defect two owners.
        return False
    value = mapping.get("disable-model-invocation", "")
    return value.split("#")[0].strip().strip("\"'").lower() in _YAML_TRUE


def skills_declaring_user_only(skills_dir: Path | None = None) -> set[str]:
    """Skills whose frontmatter forbids model invocation — from the source."""
    skills_dir = (_PLUGIN_ROOT / "skills") if skills_dir is None else skills_dir
    return {
        skill_md.parent.name
        for skill_md in skills_dir.glob("*/SKILL.md")
        if _declares_user_only(skill_md.read_text(encoding="utf-8"))
    }


def phase_table_rows(readme: Path | None = None) -> list[list[str]]:
    """The phase table's body rows, as lists of stripped cells.

    Bounded to the table rather than scanning every `|` line in the file. The
    README carries a second table (`Dependency | Reached by | How hard`), and a
    guard reading both would feed its columns into a comparison about skills.
    """
    readme = _DOCS["plugin README.md"] if readme is None else readme
    rows: list[list[str]] = []
    inside = False
    for line in readme.read_text(encoding="utf-8").splitlines():
        if line.strip() == _TABLE_HEADER:
            inside = True
            continue
        if not inside:
            continue
        if not line.startswith("|"):
            break
        if set(line.replace("|", "").strip()) <= {"-"}:
            continue  # the |---|---| separator
        rows.append([c.strip() for c in line.split("|")[1:-1]])
    return rows


def _row_skill_name(row: list[str]) -> str:
    """The skill a row names, or '' for the two non-skill rows."""
    name = row[1].strip("`() ")
    return "" if name.startswith("opsx:") or name == "agents" else name


def skills_marked_user_only_in_the_table(readme: Path | None = None) -> set[str]:
    """Skills the phase table marks user-invoked only.

    Reads cell 2 — the Invoked by column — rather than searching the whole row.
    An earlier draft used `mark in line`, which counted a row whose Invoked by
    cell said `you or Claude` and whose *description* happened to contain the
    marker: the guard agreed with the frontmatter while the column said the
    opposite of it.
    """
    readme = _DOCS["plugin README.md"] if readme is None else readme
    return {
        name
        for row in phase_table_rows(readme)
        if len(row) == 4 and row[2] == _USER_ONLY_MARK and (name := _row_skill_name(row))
    }


def test_the_invocation_column_is_not_vacuous() -> None:
    """Both halves must be non-empty AND at their real size.

    Two empty sets are equal, so the match test below passes on a tree where the
    column was deleted and every skill dropped the frontmatter key. The floor is
    the real population, not a decorative 1: measured with
    `grep -l '^disable-model-invocation: true' .claude/plugins/cla/skills/*/SKILL.md | wc -l`
    -> 2 (multi-lite, multi-pr). A floor below its population permits the
    shrinkage it exists to catch.
    """
    declared = skills_declaring_user_only()
    marked = skills_marked_user_only_in_the_table()
    assert len(declared) >= 2, (
        f"{len(declared)} skill(s) declare `disable-model-invocation: true`; the "
        f"tree had 2 when this floor was written. A genuine drop to one means "
        f"deleting a skill — update the floor in that commit, never to go green."
    )
    assert len(marked) >= 2, (
        f"the phase table marks {len(marked)} skill(s) {_USER_ONLY_MARK}. Either "
        f"the column was dropped or its marker was reworded."
    )


def test_the_invocation_column_matches_the_frontmatter() -> None:
    declared = skills_declaring_user_only()
    marked = skills_marked_user_only_in_the_table()
    assert marked == declared, (
        f"the phase table marks {sorted(marked)} as user-invoked only, but the "
        f"frontmatter declares {sorted(declared)}. The frontmatter is the source: "
        f"a skill sets `disable-model-invocation: true` and the table follows it, "
        f"never the other way round."
    )


def test_every_invocation_cell_holds_a_legal_value() -> None:
    """Catches a DELETED cell and a mislabelled row, which the set match cannot.

    Dropping the Invoked by cell from an unmarked row, or relabelling a real
    skill `n/a — dispatched`, leaves both marked sets untouched — so without
    this the table can misalign or lie about 20 of its 22 rows in silence.

    Counted with this module's own `phase_table_rows()`: 22 body rows, of which
    `_row_skill_name` reads 20 as naming a shipped skill and 2 as non-skill
    rows; the Invoked by column holds 18 `you or Claude`, 2 `**you only**`,
    1 `n/a — vendored` and 1 `n/a — dispatched`. The set match above pins only
    the 2 marked cells, which is where the other 20 come from.
    """
    for row in phase_table_rows():
        assert len(row) == 4, f"phase-table row has {len(row)} cells, expected 4: {row}"
        assert row[2] in _LEGAL_INVOCATION_CELLS, (
            f"row {row[1]!r} has Invoked by {row[2]!r}, which is not one of "
            f"{sorted(_LEGAL_INVOCATION_CELLS)}."
        )
        # The value has to agree with WHAT THE ROW IS, or `n/a` becomes a way to
        # opt a real skill out of the column: relabelling `annotate` as
        # `n/a — dispatched` kept every marked set identical and survived as a
        # mutant until this pair was added.
        names_a_skill = bool(_row_skill_name(row))
        if names_a_skill:
            assert not row[2].startswith("n/a"), (
                f"row {row[1]!r} names a shipped skill but its Invoked by cell "
                f"is {row[2]!r}. `n/a` is for the two rows that are not CLA "
                f"skills; a skill has a real invocation model."
            )
        else:
            assert row[2].startswith("n/a"), (
                f"row {row[1]!r} is not a CLA skill but its Invoked by cell is "
                f"{row[2]!r}. Its invocation model is not CLA's to state."
            )


def _shipped_skill_names(skills_dir: Path | None = None) -> set[str]:
    """Every skill that ships a SKILL.md — the population the docs describe."""
    skills_dir = (_PLUGIN_ROOT / "skills") if skills_dir is None else skills_dir
    return {p.parent.name for p in skills_dir.glob("*/SKILL.md")}


def test_the_phase_table_names_every_shipped_skill() -> None:
    """A skill added with no row, or a row left behind for a deleted skill."""
    tabled = {n for row in phase_table_rows() if (n := _row_skill_name(row))}
    on_disk = _shipped_skill_names()
    assert tabled == on_disk, (
        f"the phase table names {sorted(tabled - on_disk)} which ship no SKILL.md, "
        f"and omits {sorted(on_disk - tabled)} which do."
    )


# The two tests above run against the live tree, where the defect is absent by
# construction — so neither has been SHOWN able to fire. These feed the helpers
# a synthetic tree instead, which `test-quality.md` calls the better of the two
# ways out: a planted failure is evidence at one moment, a test supplying bad
# state keeps holding after a refactor turns the check into a no-op.


def _write_skill(root: Path, name: str, frontmatter: str) -> None:
    (root / name).mkdir(parents=True)
    (root / name / "SKILL.md").write_text(
        f"---\nname: {name}\n{frontmatter}---\n\n# {name}\n", encoding="utf-8"
    )


def test_the_frontmatter_reader_accepts_every_yaml_spelling_of_true(tmp_path) -> None:
    """The Critical this guard shipped with: one spelling of six was matched."""
    for i, value in enumerate(
        ["true", "True", '"true"', "yes", "true  # unattended orchestrator", " true"]
    ):
        _write_skill(tmp_path, f"skill{i}", f"disable-model-invocation:{value}\n")
    _write_skill(tmp_path, "ordinary", "argument-hint: something\n")
    found = skills_declaring_user_only(tmp_path)
    assert found == {f"skill{i}" for i in range(6)}, (
        f"a legal YAML spelling of true went unread: got {sorted(found)}. A skill "
        f"this misses is one the table is never forced to label."
    )


def test_the_frontmatter_reader_is_not_fooled_by_the_body(tmp_path) -> None:
    """A `---` rule in the body must not open a second frontmatter block."""
    (tmp_path / "prose").mkdir(parents=True)
    (tmp_path / "prose" / "SKILL.md").write_text(
        "---\nname: prose\n---\n\n# prose\n\n---\n\ndisable-model-invocation: true\n",
        encoding="utf-8",
    )
    assert skills_declaring_user_only(tmp_path) == set()


def test_the_table_reader_ignores_a_mark_outside_the_invocation_cell(tmp_path) -> None:
    """The Important this guard shipped with: `mark in line`, not `in the cell`."""
    readme = tmp_path / "README.md"
    readme.write_text(
        f"{_TABLE_HEADER}\n|---|---|---|---|\n"
        f"| | `multi-lite` | you or Claude | start it {_USER_ONLY_MARK} |\n",
        encoding="utf-8",
    )
    assert skills_marked_user_only_in_the_table(readme) == set(), (
        "a marker in the description cell was counted as an invocation mark, so "
        "the column could say the opposite of the frontmatter and still agree."
    )


def test_the_table_reader_stops_at_the_end_of_the_phase_table(tmp_path) -> None:
    """A later table's rows must not be read as phase-table rows."""
    readme = tmp_path / "README.md"
    readme.write_text(
        f"{_TABLE_HEADER}\n|---|---|---|---|\n"
        f"| | `multi-pr` | {_USER_ONLY_MARK} | chains spec-to-pr |\n"
        "\n## Another section\n\n"
        f"| Dependency | Reached by | How hard |\n|---|---|---|\n"
        f"| **OpenSpec** | `spec-to-pr` | {_USER_ONLY_MARK} |\n",
        encoding="utf-8",
    )
    assert skills_marked_user_only_in_the_table(readme) == {"multi-pr"}


# The same derived fact, in the two docs that are not the table.
#
# `CLAUDE.md` and `DEVELOPER-GUIDE.md` each qualify their "invocable by natural
# language" sentence by NAMING the two skills. That is the same copied derived
# value the assertions above exist for, and without these the guard's own
# headline failure mode — a third skill sets the key, the copy still names two —
# stays alive in two files, in the commit that added the guard against it.

_INVOCATION_CLAIM_PHRASE = "disable-model-invocation"

# A block break: a blank line, a list marker, or a heading. Bounding the claim to
# ONE bullet or ONE paragraph is what makes reading skill names out of it sound —
# the whole bullet list, or a section, would sweep in names from prose that makes
# no claim about invocation, and the assertion would fail on unrelated edits.
_BLOCK_BREAK = re.compile(r"^(?:[-*+] |\d+\. |#)")


def _claim_blocks(text: str, phrase: str) -> list[str]:
    """Every block of `text` that mentions `phrase`, as joined text."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or _BLOCK_BREAK.match(stripped):
            if current:
                blocks.append(current)
            current = []
        if stripped:
            current.append(line)
    if current:
        blocks.append(current)
    return ["\n".join(b) for b in blocks if phrase in "\n".join(b)]


def _skills_named_in(block: str, skills_dir: Path | None = None) -> set[str]:
    """The shipped skills a block of prose names in backticks."""
    on_disk = _shipped_skill_names(skills_dir)
    return {t for t in re.findall(r"`([^`]+)`", block) if t in on_disk}


@pytest.mark.parametrize("name", ["CLAUDE.md", "DEVELOPER-GUIDE.md"])
def test_every_doc_naming_the_user_only_skills_names_the_real_ones(name) -> None:
    """The third and fourth copies of the fact the phase table restates."""
    blocks = _claim_blocks(
        _DOCS[name].read_text(encoding="utf-8"), _INVOCATION_CLAIM_PHRASE
    )
    assert len(blocks) == 1, (
        f"{name} has {len(blocks)} passage(s) mentioning "
        f"`{_INVOCATION_CLAIM_PHRASE}`, expected exactly 1. Zero means the "
        f"qualification was dropped and the doc is back to claiming every skill "
        f"is model-invocable; more than one means two copies that can disagree, "
        f"and this guard cannot know which one a reader trusts."
    )
    named = _skills_named_in(blocks[0])
    assert named == skills_declaring_user_only(), (
        f"{name} names {sorted(named)} as the skills Claude may not invoke, but "
        f"the frontmatter declares {sorted(skills_declaring_user_only())}. The "
        f"frontmatter is the source; every doc that restates it follows."
    )


def test_the_claim_block_is_bounded_by_its_own_bullet(tmp_path) -> None:
    """A neighbouring bullet's skill names must not be read into the claim.

    The live docs pass by construction, so this feeds the reader prose whose
    neighbouring bullet names a skill the claim does not. An unbounded reader
    returns `annotate` too and the assertion above fails on an edit that is
    correct — which is how a guard gets loosened rather than fixed.
    """
    skills = tmp_path / "skills"
    for skill in ("multi-lite", "multi-pr", "annotate"):
        _write_skill(skills, skill, "argument-hint: x\n")
    doc = (
        "- **Skills** — all but `multi-lite` and `multi-pr`, which set\n"
        "  `disable-model-invocation: true`, answer to natural language.\n"
        "- **Pages** — `annotate` renders one.\n"
    )
    blocks = _claim_blocks(doc, _INVOCATION_CLAIM_PHRASE)
    assert len(blocks) == 1
    assert _skills_named_in(blocks[0], skills) == {"multi-lite", "multi-pr"}
