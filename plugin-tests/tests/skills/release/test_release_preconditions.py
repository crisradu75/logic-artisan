"""The release skill's preconditions, asserted rather than described.

`/cla:release` is prose, and prose is the right shape for most of it — reading
`git status`, choosing a bump, deciding whether the work is reviewed. But its last
step is irreversible: once a tag is pushed and a consumer installs it, that tag is
what they fetched and it can never be corrected in place. `0.9.0` proved that; the
next fix had to become `0.9.1`.

So the two facts the tag depends on are checked here rather than trusted to a
careful reading:

  1. The three copies of the version — `plugin.json`, the marketplace `ref`, and
     `CLAUDE.md`'s release line — agree. `claude plugin tag` refuses when the
     first two disagree, but it never sees the third, and a stale third copy is
     exactly what shipped before.
  2. The tag NAME the skill will cut matches the shape the tooling expects
     (`cla--v<version>`), derived from the manifests rather than hand-typed.

Deliberately NOT tested here: that the tree is clean, that the branch is the
default one, that the suite is green. Those are properties of a moment, not of the
repo, and a test asserting them would either be vacuous or fail every time someone
worked on a branch — which is most of the time.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Three subjects in three different trees, so the repo root is resolved once and
# all three are derived from it. A single `parents[N]` cannot express this:
# `extract-dev-tree-from-plugin` left this test in the dev tree, its `SKILL.md`
# subject in the repo-local skills tree, and `plugin.json` in the published
# plugin. A "corrected depth" would have had to be three different depths.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PLUGIN_ROOT = _REPO_ROOT / ".claude" / "plugins" / "cla"

_PLUGIN_JSON = _PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
_MARKETPLACE_JSON = _REPO_ROOT / ".claude-plugin" / "marketplace.json"
_SKILL_MD = _REPO_ROOT / ".claude" / "skills" / "release" / "SKILL.md"

TAG_SHAPE = re.compile(r"^cla--v(\d+\.\d+\.\d+)$")


def _plugin_version() -> str:
    return json.loads(_PLUGIN_JSON.read_text(encoding="utf-8"))["version"]


def _marketplace_ref() -> str:
    catalog = json.loads(_MARKETPLACE_JSON.read_text(encoding="utf-8"))
    entries = [p for p in catalog["plugins"] if p["name"] == "cla"]
    assert len(entries) == 1, f"expected exactly one `cla` entry, found {len(entries)}"
    return entries[0]["source"]["ref"]


def test_the_tag_the_release_would_cut_has_the_expected_shape():
    """`claude plugin tag` builds `<name>--v<version>`. If the ref ever stops
    matching that shape, the skill's `git push origin cla--v<new>` line pushes a
    tag nobody created."""
    ref = _marketplace_ref()
    match = TAG_SHAPE.match(ref)
    assert match, f"marketplace ref {ref!r} is not of the form `cla--v<x.y.z>`"
    assert match.group(1) == _plugin_version(), (
        f"marketplace ref {ref!r} pins version {match.group(1)}, "
        f"but plugin.json declares {_plugin_version()}"
    )


def test_all_three_copies_of_the_version_agree():
    """The precondition `claude plugin tag` cannot check: it compares two of the
    three copies and never reads CLAUDE.md."""
    version = _plugin_version()
    claude_md = (_REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    match = re.search(r"\*\*Current release: `cla--v([0-9.]+)`", claude_md)
    assert match, "CLAUDE.md no longer states a `**Current release: `cla--v<x>`**` line"
    assert match.group(1) == version, (
        f"CLAUDE.md says {match.group(1)}, plugin.json says {version} — the release "
        "skill's step 3 bumps all three together for exactly this reason"
    )


def test_the_skill_names_every_file_its_own_procedure_bumps():
    """A release that edits two of the three files leaves the catalog advertising
    a version the prose contradicts. The skill's step 3 must keep naming all
    three, so this fails if one is ever dropped from the procedure."""
    body = _SKILL_MD.read_text(encoding="utf-8")
    for required in ("plugin.json", "marketplace.json", "CLAUDE.md"):
        assert required in body, (
            f"release/SKILL.md no longer names {required} — the three-file bump has "
            "silently become a one-part bump"
        )


def test_the_skill_states_the_never_move_invariant():
    """The one rule whose violation cannot be undone. If it is ever edited out of
    the skill, the skill has stopped being safe to run."""
    body = _SKILL_MD.read_text(encoding="utf-8")

    # A substring search anywhere in the file is NOT this assertion. Measured:
    # `never move` occurs three times — the frontmatter `description:`, the
    # normative statement, and a precondition-table cell — so rewriting the
    # normative one to "may be moved when convenient" left the other two alive
    # and the old `"never move" in body` check green. A mutant caught it; no
    # amount of reading would have. Pin the emphasized statement itself.
    assert "**A published tag is never moved.**" in body, (
        "release/SKILL.md no longer carries the emphasized invariant "
        '"**A published tag is never moved.**" as its own statement. Other '
        "mentions of the phrase elsewhere in the file do not substitute for it: "
        "this is the rule whose breach cannot be undone."
    )


def test_the_precondition_block_names_every_command_the_documented_gate_runs():
    """CLAUDE.md's "Before opening a PR" row is this repo's own statement of what
    the shipping gate consists of — currently two commands, `pytest plugin-tests`
    and the `node --test` run `pytest` cannot reach (`norecursedirs` excludes
    `node`). The deleted `run_tests.py` used to fold both into one 13-entry run,
    so cutting it over to this skill's two-command precondition list silently
    dropped Node coverage from the tag gate: `check_shipped_tree.py` ships
    `project-review/scripts/mechanical-checks.mjs`, and nothing in the
    preconditions ran its tests. Commit `ee3e359` on
    `extract-dev-tree-from-plugin` is the proof — it fixed that suite failing
    with `ERR_MODULE_NOT_FOUND` while `pytest` stayed green throughout.

    Derived from CLAUDE.md rather than hardcoded, so a future change to what
    "before opening a PR" runs is what this test forces release/SKILL.md to
    follow, instead of letting the two drift apart silently again."""
    claude_md = (_REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    match = re.search(r"\|\s*Before opening a PR\s*\|(.+)\|\s*\n", claude_md)
    assert match, "CLAUDE.md no longer states a 'Before opening a PR' gate row"
    gate_commands = re.findall(r"`([^`]+)`", match.group(1))
    assert gate_commands, (
        "no `command` spans found in CLAUDE.md's 'Before opening a PR' row — "
        "the gate can no longer be read out of the doc"
    )

    body = _SKILL_MD.read_text(encoding="utf-8")
    assert "## Step 1" in body, "release/SKILL.md no longer has a Step 1 section"
    assert "## Step 2" in body, (
        "release/SKILL.md no longer has a Step 2 heading — without it the Step 1 "
        "slice below runs to end of file and swallows Step 3's re-run block, "
        "which repeats these same commands, so Step 1 could lose one entirely "
        "and this test would still pass"
    )
    step1 = body.split("## Step 1", 1)[1].split("## Step 2", 1)[0]

    # Match against the RUNNABLE block, not the whole section. Step 1 also holds
    # a precondition TABLE that names both commands in backticks, so searching
    # the section made this test satisfiable by the prose describing the gate
    # rather than by the gate. Measured: deleting both commands from the fenced
    # bash block left this test passing.
    blocks = re.findall(r"```(?:bash|sh)?\n(.*?)```", step1, re.S)
    assert blocks, "release/SKILL.md's Step 1 has no fenced command block to run"
    runnable = "\n".join(blocks)
    missing = [cmd for cmd in gate_commands if cmd not in runnable]
    assert not missing, (
        f"release/SKILL.md's Step 1 preconditions do not run: {missing} — "
        "CLAUDE.md's documented shipping gate and the release skill's "
        "preconditions have drifted apart, exactly the drop this test exists "
        "to catch"
    )
