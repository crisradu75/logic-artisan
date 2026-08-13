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

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
_REPO_ROOT = _PLUGIN_ROOT.parents[2]

_PLUGIN_JSON = _PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
_MARKETPLACE_JSON = _REPO_ROOT / ".claude-plugin" / "marketplace.json"
_SKILL_MD = _PLUGIN_ROOT / "skills" / "release" / "SKILL.md"

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
            f"release/SKILL.md no longer names {required} — the two-part bump has "
            "silently become a one-part bump"
        )


def test_the_skill_states_the_never_move_invariant():
    """The one rule whose violation cannot be undone. If it is ever edited out of
    the skill, the skill has stopped being safe to run."""
    body = _SKILL_MD.read_text(encoding="utf-8").lower()
    assert "never moved" in body or "never move" in body, (
        "release/SKILL.md no longer states that a published tag is never moved"
    )
