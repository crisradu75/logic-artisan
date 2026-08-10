"""The marketplace manifest must stay loadable and must point at this plugin.

Structure only. This deliberately does NOT check that each `ref` resolves: the
stable channel tracks the `v1` tag, which does not exist until a release is cut,
and a test that failed until then would just be disabled. Ref existence is the
release process's job (Phase F), not this suite's.

Schema verified against the live docs (code.claude.com/docs/en/plugin-marketplaces)
rather than from memory: `git-subdir` takes `url` + `path`, with optional `ref`
and `sha`, and the manifest lives at `.claude-plugin/marketplace.json` in the
repository root.
"""

from __future__ import annotations

import json
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _PLUGIN_ROOT.parents[2]
_MANIFEST = _REPO_ROOT / ".claude-plugin" / "marketplace.json"
_PLUGIN_JSON = _PLUGIN_ROOT / ".claude-plugin" / "plugin.json"

# Names Anthropic reserves for official marketplaces. A marketplace registered
# under one of these stops loading entirely, and the failure reads as "untrusted
# source" rather than "bad name", so it is worth catching here.
_RESERVED = frozenset({
    "claude-code-marketplace", "claude-code-plugins", "claude-plugins-official",
    "claude-plugins-community", "claude-community", "anthropic-marketplace",
    "anthropic-plugins", "agent-skills", "anthropic-agent-skills",
    "knowledge-work-plugins", "life-sciences", "claude-for-legal",
    "claude-for-financial-services", "financial-services-plugins",
    "first-party-plugins", "healthcare",
})


def _manifest() -> dict:
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))


def test_the_manifest_exists_where_claude_code_looks_for_it():
    assert _MANIFEST.is_file(), (
        f"{_MANIFEST} is missing; Claude Code reports 'File not found: "
        ".claude-plugin/marketplace.json' and the marketplace does not load"
    )


def test_the_manifest_has_the_required_top_level_shape():
    data = _manifest()
    for field in ("name", "owner", "plugins"):
        assert field in data, f"required field {field!r} missing"
    assert isinstance(data["owner"], dict) and data["owner"].get("name")
    assert isinstance(data["plugins"], list) and data["plugins"]


def test_the_marketplace_name_is_not_reserved():
    name = _manifest()["name"]
    assert name not in _RESERVED, f"{name!r} is reserved for official Anthropic use"
    assert name == name.lower() and " " not in name, "name must be kebab-case, no spaces"


def test_every_entry_points_at_this_plugin_subdirectory():
    """Each channel must name the real plugin path. A typo here installs an empty
    plugin — Claude Code finds no manifest at the subdir and the install is inert,
    which reads to a user as 'the plugin does nothing' rather than as a bad path.
    """
    expected_path = _PLUGIN_ROOT.relative_to(_REPO_ROOT).as_posix()
    for entry in _manifest()["plugins"]:
        src = entry["source"]
        assert src["source"] == "git-subdir", f"{entry['name']}: unexpected source type"
        assert src["path"] == expected_path, (
            f"{entry['name']}: source path {src['path']!r} is not this plugin "
            f"({expected_path!r})"
        )
        assert src.get("url"), f"{entry['name']}: git-subdir requires a url"
        assert src.get("ref"), (
            f"{entry['name']}: no ref, so the channel silently tracks the "
            "repository default branch — name the branch or tag explicitly"
        )


def test_the_channels_are_distinct_and_named():
    """Two entries sharing a name would collide: each user registers one
    marketplace per name, and within it a plugin name is the install handle."""
    entries = _manifest()["plugins"]
    names = [e["name"] for e in entries]
    assert len(names) == len(set(names)), f"duplicate plugin names: {names}"
    refs = [e["source"]["ref"] for e in entries]
    assert len(refs) == len(set(refs)), (
        f"two channels track the same ref ({refs}) — they are the same channel "
        "under two names"
    )
    for e in entries:
        assert e.get("description"), f"{e['name']}: a channel needs to say what it is"


def test_the_plugin_manifest_is_loadable_and_versioned():
    data = json.loads(_PLUGIN_JSON.read_text(encoding="utf-8"))
    assert data.get("name") == "cla"
    version = data.get("version", "")
    assert version and version[0].isdigit(), f"unusable version {version!r}"


def test_the_plugin_declares_its_own_repository():
    """`/cla:report-upstream` reads this to know where to file an issue, and
    refuses to guess a slug when it is absent — portable core must not name a
    repository in its prose."""
    data = json.loads(_PLUGIN_JSON.read_text(encoding="utf-8"))
    assert data.get("repository"), (
        "plugin.json has no `repository`; /cla:report-upstream has nowhere to "
        "file and will stop and ask the user every time"
    )
