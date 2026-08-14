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

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
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
    """Mirror `run_tests.py`'s discovery rule: a dir with BOTH a pytest-configured
    pyproject.toml and a tests/ subdir. Deliberately re-derived here rather than
    imported — `run_tests.py` sits at the plugin root with no package, and a drift
    between the two rules is itself worth catching."""
    pytest_dirs = {
        p.parent
        for p in _PLUGIN_ROOT.rglob("pyproject.toml")
        if not _EXCLUDED_DIRS & set(p.parts)
        and _PYTEST_MARKER in p.read_text(encoding="utf-8")
    }
    tests_dirs = {
        p.parent
        for p in _PLUGIN_ROOT.rglob("tests")
        if p.is_dir() and not _EXCLUDED_DIRS & set(p.parts)
    }
    return sorted(pytest_dirs & tests_dirs)


def real_skills_with_tests() -> int:
    """Scopes that are actually SKILLS, not merely directories under `skills/`.

    `skills/_shared/` is a scope and lives under `skills/`, but it has no SKILL.md
    and is therefore not a skill — counting it here would make every doc that says
    "N skills ship tests" wrong by one, which is exactly the drift this file is
    supposed to detect rather than cause."""
    return len(
        [
            d
            for d in real_scope_dirs()
            if d.parent.name == "skills" and (d / "SKILL.md").is_file()
        ]
    )


def _numbers_near(doc: str, phrase: str) -> list[int]:
    """Every integer on a line containing `phrase`. Returns [] when absent, which
    the caller treats as "the claim moved" rather than "the claim is fine"."""
    out = []
    for line in doc.splitlines():
        if phrase in line:
            out.extend(int(n) for n in re.findall(r"\b(\d{1,3})\b", line))
    return out


# ---------- the assertions ----------


def test_the_scope_discovery_rule_here_matches_what_run_tests_finds():
    """Non-vacuity with teeth: if this file's re-derived rule ever stops matching
    `run_tests.py`'s, every count below is measured against the wrong truth."""
    runner = (_PLUGIN_ROOT / "run_tests.py").read_text(encoding="utf-8")
    assert _PYTEST_MARKER in runner, (
        "run_tests.py no longer keys scope discovery on "
        f"{_PYTEST_MARKER!r}; re-derive real_scope_dirs() to match it"
    )
    scopes = real_scope_dirs()
    assert len(scopes) >= 8, f"scope discovery collapsed to {len(scopes)}"


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


@pytest.mark.parametrize("name", sorted(_DOCS))
def test_no_doc_names_a_plugin_path_that_no_longer_exists(name):
    """Paths under `.claude/plugins/cla/` named in prose, checked for existence.
    Concrete paths only — a glob or placeholder segment names a shape, not a file."""
    doc = _DOCS[name].read_text(encoding="utf-8")
    missing = []
    for raw in re.findall(r"\.claude/plugins/cla/[A-Za-z0-9._/-]+", doc):
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
