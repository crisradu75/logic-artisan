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
import re
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
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


def test_entries_are_distinctly_named_and_described():
    """Two entries sharing a name would collide: each user registers one
    marketplace per name, and within it a plugin name is the install handle."""
    entries = _manifest()["plugins"]
    names = [e["name"] for e in entries]
    assert len(names) == len(set(names)), f"duplicate plugin names: {names}"
    refs = [e["source"]["ref"] for e in entries]
    assert len(refs) == len(set(refs)), (
        f"two entries track the same ref ({refs}) — they are the same thing "
        "published twice"
    )
    for e in entries:
        assert e.get("description"), f"{e['name']}: an entry needs to say what it is"


# requirement: plugin-distribution / Installing a pinned release
def test_the_published_ref_matches_the_plugin_version():
    """The manifest pins an exact release tag rather than a moving major tag, so
    publishing a release means editing the `ref` here. That is the whole point —
    an explicit edit per release — but it also means this file and `plugin.json`
    can disagree, and a consumer installing 0.9.0 while the manifest says the
    plugin is 1.0.0 has no way to tell which is true.

    Tag shape is `{name}--v{version}`, which is what `claude plugin tag` creates
    and validates. It is not a bare `v{version}`: this repo could host a second
    plugin, and then a bare version tag names neither of them.
    """
    version = json.loads(_PLUGIN_JSON.read_text(encoding="utf-8"))["version"]
    for entry in _manifest()["plugins"]:
        ref = entry["source"]["ref"]
        assert ref == f"{entry['name']}--v{version}", (
            f"{entry['name']} publishes ref {ref!r}, but the release tag for "
            f"version {version!r} is {entry['name']}--v{version!r}. Use "
            "`claude plugin tag` so both files are checked for you."
        )


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


# ---------------------------------------------------------------------------
# GitHub Copilot CLI: a catalog under .github/plugin/ and an Agent Plugins 1.0
# manifest at the plugin root. NOT tested against a live Copilot CLI (none is
# installed); these tests pin the shape GitHub's docs describe, so they catch a
# typo or a drift, and say nothing about whether Copilot accepts the install.
#
# Sources, read raw from github/docs (content/copilot/reference/copilot-cli-
# reference/cli-plugin-reference.md) and the agentplugins/agent-plugins-spec
# repository (spec/1.0.0.md): the closed top-level field set, the `$schema`
# value, the name rule, the catalog search order and the `github` source shape.
# ---------------------------------------------------------------------------

_COPILOT_CATALOG = _REPO_ROOT / ".github" / "plugin" / "marketplace.json"
_COPILOT_PLUGIN_JSON = _PLUGIN_ROOT / "plugin.json"
_AGENT_PLUGINS_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
_AGENT_PLUGINS_FIELDS = frozenset({
    "$schema", "name", "version", "description", "author", "homepage",
    "repository", "license", "keywords", "extensions",
})
# 1-64 characters of a-z 0-9 - ., alphanumeric at both ends, no `--` or `..`.
# Use `.fullmatch`: `$` alone would also accept a trailing newline.
_AGENT_PLUGINS_NAME = re.compile(r"(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]{0,62}[a-z0-9])?")


def _copilot_catalog() -> dict:
    return json.loads(_COPILOT_CATALOG.read_text(encoding="utf-8"))


def _copilot_manifest() -> dict:
    return json.loads(_COPILOT_PLUGIN_JSON.read_text(encoding="utf-8"))


def _repo_slug() -> str:
    """`owner/repo`, from the repository URL the Claude manifest already declares."""
    url = json.loads(_PLUGIN_JSON.read_text(encoding="utf-8"))["repository"]
    return url.removeprefix("https://github.com/").removesuffix(".git").strip("/")


# requirement: plugin-distribution / Listing for GitHub Copilot CLI
def test_the_copilot_catalog_names_this_plugin_with_a_github_source():
    assert _COPILOT_CATALOG.is_file(), (
        f"{_COPILOT_CATALOG} is missing; Copilot CLI checks .github/plugin/ for a "
        "marketplace and finds none"
    )
    data = _copilot_catalog()
    for field in ("name", "owner", "plugins"):
        assert field in data, f"required field {field!r} missing"
    assert data["name"] == _manifest()["name"], (
        "the Copilot catalog must register under the same name as the Claude one, "
        "so the install line is `cla@<that name>` for both"
    )
    assert isinstance(data["owner"], dict) and data["owner"].get("name")
    entries = [e for e in data["plugins"] if e["name"] == "cla"]
    assert len(entries) == 1, f"expected exactly one `cla` entry, found {len(entries)}"
    src = entries[0]["source"]
    assert isinstance(src, dict), "a relative-path source would not pin a release tag"
    assert src.get("source") == "github", (
        f"source type {src.get('source')!r}: Copilot CLI documents `github` and "
        "`url`, not the `git-subdir` the Claude catalog uses"
    )
    assert src.get("repo") == _repo_slug()
    assert src.get("path") == _PLUGIN_ROOT.relative_to(_REPO_ROOT).as_posix()
    assert src.get("ref"), "no ref, so the entry would track the default branch"


# requirement: plugin-distribution / Listing for GitHub Copilot CLI
def test_the_copilot_root_manifest_uses_only_agent_plugins_1_0_fields():
    data = _copilot_manifest()
    assert data.get("$schema") == _AGENT_PLUGINS_SCHEMA, (
        "without the exact Agent Plugins `$schema` Copilot reads this as a legacy "
        "manifest, which changes what loads"
    )
    # The set is closed, so this also rejects the component path fields (`skills`,
    # `hooks`, ...) that the docs say 1.0 does not have.
    unknown = set(data) - _AGENT_PLUGINS_FIELDS
    assert not unknown, f"fields outside the closed Agent Plugins 1.0 set: {sorted(unknown)}"
    assert _AGENT_PLUGINS_NAME.fullmatch(data["name"]), f"invalid plugin name {data['name']!r}"
    assert data["name"] == json.loads(_PLUGIN_JSON.read_text(encoding="utf-8"))["name"], (
        "the two manifests must name the plugin identically"
    )
    # The spec makes a wrong type fatal (Copilot rejects the whole plugin), not a warning.
    for field in ("name", "version", "description", "homepage", "repository", "license"):
        assert isinstance(data.get(field, ""), str), f"{field!r} must be a string"
    author = data.get("author", {})
    assert isinstance(author, dict) and set(author) <= {"name", "email", "url"}
    assert all(isinstance(v, str) for v in author.values()), "author values must be strings"
    keywords = data.get("keywords", [])
    assert isinstance(keywords, list) and all(isinstance(k, str) for k in keywords)
    assert isinstance(data.get("extensions", {}), dict)


def test_the_agent_plugins_name_rule_rejects_what_the_docs_reject():
    """The rule above is only as good as the regex that states it."""
    for bad in ("My-Plugin", "-start", "end-", "has--double", "too..dots", "", "a" * 65,
                "cla\n"):
        assert not _AGENT_PLUGINS_NAME.fullmatch(bad), f"{bad!r} must be rejected"
    for good in ("cla", "acme.tools", "a", "a" * 64, "lint3r"):
        assert _AGENT_PLUGINS_NAME.fullmatch(good), f"{good!r} must be accepted"


# The disclosure must sit beside the command: in the same heading section and within this many
# characters of each occurrence of either install command (whitespace collapsed).
_DISCLOSURE_WINDOW = 1000
_INSTALL_COMMANDS = ("copilot plugin marketplace add", "copilot plugin install")
_DISCLOSURE_PHRASES = ("Copilot CLI only", "untested in a live Copilot CLI")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
_HEADING = re.compile(r"#{1,6} ")


def _sections(text: str) -> list[str]:
    """Split at Markdown headings outside code fences; a section starts with its heading."""
    sections: list[list[str]] = [[]]
    fence = ""
    for line in text.split("\n"):
        run = _FENCE.match(line)
        if fence:
            if run and run.group(1)[0] == fence[0] and len(run.group(1)) >= len(fence):
                fence = ""
        elif run:
            fence = run.group(1)
        elif _HEADING.match(line):
            sections.append([])
        sections[-1].append(line)
    return ["\n".join(lines) for lines in sections]


def _disclosure_gaps(text: str) -> list[str]:
    """Every install command in `text` that lacks a disclosure phrase beside it."""
    gaps = []
    for section in _sections(text):
        flat = " ".join(section.split())
        for command in _INSTALL_COMMANDS:
            for found in re.finditer(re.escape(command), flat):
                near = flat[max(0, found.start() - _DISCLOSURE_WINDOW):found.end() + _DISCLOSURE_WINDOW]
                gaps += [
                    f"{phrase!r} is not within {_DISCLOSURE_WINDOW} characters of {command!r} in its section"
                    for phrase in _DISCLOSURE_PHRASES if phrase not in near
                ]
    return gaps


# requirement: plugin-distribution / Disclosing the Copilot CLI install is untested
def test_every_doc_offering_the_copilot_install_says_it_is_untested_beside_it():
    """The install was never run in a live Copilot CLI. A doc that gives the
    command without saying so, beside it, would read as a tested instruction."""
    docs = {
        "README.md": _REPO_ROOT / "README.md",
        "DEVELOPER-GUIDE.md": _REPO_ROOT / "DEVELOPER-GUIDE.md",
        "CLAUDE.md": _REPO_ROOT / "CLAUDE.md",
        "plugin README.md": _PLUGIN_ROOT / "README.md",
    }
    texts = {label: path.read_text(encoding="utf-8") for label, path in docs.items()}
    assert _disclosure_gaps(texts["README.md"]) == [], "README.md: " + str(_disclosure_gaps(texts["README.md"]))
    assert any(c in texts["README.md"] for c in _INSTALL_COMMANDS), (
        "README.md no longer gives the Copilot install line"
    )
    for label, text in texts.items():
        gaps = _disclosure_gaps(text)
        assert not gaps, f"{label} offers the Copilot install without the disclosure beside it: {gaps}"


# requirement: plugin-distribution / Disclosing the Copilot CLI install is untested
def test_the_disclosure_check_needs_the_phrases_in_the_same_section_and_near_the_command():
    disclosure = "Copilot CLI only and untested in a live Copilot CLI."
    command = "copilot plugin install cla@x"
    assert _disclosure_gaps(f"### Copilot\n\n{disclosure}\n\n```bash\n{command}\n```\n") == []
    # A heading in a bash fence is a comment, not a section break.
    assert _disclosure_gaps(f"### Copilot\n{disclosure}\n```bash\n# install\n{command}\n```\n") == []
    # Wrapped across lines, the phrase still matches.
    assert _disclosure_gaps(f"### C\nCopilot CLI only, untested in a\nlive Copilot CLI.\n{command}\n") == []
    # The same words in another section do not count.
    elsewhere = f"### Notes\n\n{disclosure}\n\n### Install\n\n```bash\n{command}\n```\n"
    assert len(_disclosure_gaps(elsewhere)) == 2
    # Nor do they count from far away in the same section.
    far = f"### Install\n\n{disclosure}\n\n" + "filler " * 400 + f"\n\n{command}\n"
    assert len(_disclosure_gaps(far)) == 2
    # Each command is checked: a second one far from the words has a gap even if the first is fine.
    two = f"### Install\n{command}\n{disclosure}\n" + "filler " * 400 + "\ncopilot plugin marketplace add y\n"
    assert len(_disclosure_gaps(two)) == 2
    # One phrase present and the other missing is reported by name.
    only = _disclosure_gaps("### Install\nuntested in a live Copilot CLI.\n" + command + "\n")
    assert len(only) == 1 and "Copilot CLI only" in only[0]
    assert _disclosure_gaps("no command here, no gap\n") == []


# requirement: plugin-distribution / Disclosing the Copilot CLI install is untested
def test_the_shipped_copilot_manifest_does_not_say_the_install_is_untested():
    """The manifest sits inside the release tag, which is never moved, so a claim there would
    outlive the first live test. The docs and the spec carry it instead."""
    description = _copilot_manifest().get("description", "")
    assert description, "the root manifest needs a description"
    assert "untested" not in description.lower(), "the tagged manifest must not carry the untested claim"
