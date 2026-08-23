"""Drift guard: the counts and paths this repo's own docs assert must be true.

The plugin's behaviour lives mostly in markdown, and so does its documentation —
a prose edit ships like code but nothing compiles it. Five numbers in particular
are restated across four files (`CLAUDE.md`, `README.md`, `DEVELOPER-GUIDE.md`,
the plugin's own `README.md`) and every one of them has been wrong at least once:
the skill count, the pytest-scope count, the count of skills shipping tests, the
leaf-hook count, and the release version.

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

import json
import re
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


# ---------- ground truth, computed from the tree ----------


def real_skill_count() -> int:
    """A skill is a directory with a SKILL.md. `_shared/` has none, by design."""
    return len(list((_PLUGIN_ROOT / "skills").glob("*/SKILL.md")))


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
        if not _EXCLUDED_DIRS & set(p.parts)
        and _PYTEST_MARKER in p.read_text(encoding="utf-8")
    }
    tests_dirs = {
        p.parent
        for p in _REPO_ROOT.rglob("tests")
        if p.is_dir() and not _EXCLUDED_DIRS & set(p.parts)
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
