"""Generate the GitHub Copilot CLI copy of each helper agent from its Claude Code agent.

The plugin's five helper agents live once, in `agents/`, as Claude Code agent files. Copilot CLI
reads a plugin's custom agents from `com.github.copilot/agents/` when the plugin has an Agent
Plugins 1.0 root manifest, and the docs fix that location, so Copilot cannot be pointed at the
Claude files. This script writes the second copy, so the instructions are authored once:

- the Markdown body is copied unchanged;
- `name` and `description` are copied unchanged;
- `tools` is mapped to the tool aliases Copilot documents;
- `model` is mapped to a Copilot model ID;
- `color` is dropped (Copilot's frontmatter has no such field).

Sources, read raw from github/docs:
- https://docs.github.com/en/copilot/reference/custom-agents-configuration (`name`,
  `description`, `tools`, `model`, the tool alias table; unrecognized tool names are ignored)
- https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference
  (an Agent Plugins 1.0 plugin keeps Copilot custom agents in `com.github.copilot/agents/`)
- https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference
  ("Supported models", and "A declared model ... that can't be honored falls back to the session's
  value instead of failing the dispatch")

NOT TESTED in a live Copilot CLI (none is installed). The tests that call this module check that
each committed copy equals what `render` produces, plus the checks listed in that test file.

    python3 plugin-tests/scripts/sync_copilot_agents.py           # report copies out of step or orphaned
    python3 plugin-tests/scripts/sync_copilot_agents.py --write   # regenerate them, delete the orphans
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2] / ".claude" / "plugins" / "cla"
CLAUDE_DIR = PLUGIN_ROOT / "agents"
COPILOT_DIR = PLUGIN_ROOT / "com.github.copilot" / "agents"

# Claude Code agent `model` aliases -> Copilot model IDs from the CLI command reference's
# "Supported models" table. Copilot falls back to the session model for an ID it cannot honor, so a
# stale ID costs the model choice and does not break the agent. Update this table when GitHub
# renames a model.
MODEL_MAP = {
    "haiku": "claude-haiku-5.5",
    "sonnet": "claude-sonnet-5.5",
    "opus": "claude-opus-5.5",
}

# Tool aliases from the "Tool aliases" table of the custom agents configuration reference: every
# listed name (case-insensitive) -> its primary alias.
TOOL_ALIASES = {
    **{n: "execute" for n in ("execute", "shell", "bash", "powershell")},
    **{n: "read" for n in ("read", "notebookread")},
    **{n: "edit" for n in ("edit", "multiedit", "write", "notebookedit")},
    **{n: "search" for n in ("search", "grep", "glob")},
    **{n: "agent" for n in ("agent", "custom-agent", "task")},
    **{n: "web" for n in ("web", "websearch", "webfetch")},
    **{n: "todo" for n in ("todo", "todowrite")},
}

_PASS_THROUGH = ("name", "description")


def split_frontmatter(text: str) -> tuple[list[str], str]:
    """Return (frontmatter lines, body). The body keeps its exact text."""
    lines = text.split("\n")
    if lines[0] != "---":
        raise ValueError("agent file does not start with a '---' frontmatter fence")
    end = lines.index("---", 1)
    return lines[1:end], "\n".join(lines[end + 1:])


def map_tools(claude_tools: list[str]) -> list[str]:
    mapped: list[str] = []
    for tool in claude_tools:
        primary = TOOL_ALIASES.get(tool.lower())
        if primary is None:
            # Copilot ignores unknown names, which would silently shrink the tool set.
            raise ValueError(f"no documented Copilot alias for tool {tool!r}")
        if primary not in mapped:
            mapped.append(primary)
    return mapped


def render(claude_text: str) -> str:
    """The Copilot agent text for one Claude Code agent file's text."""
    front, body = split_frontmatter(claude_text)
    out: list[str] = []
    seen = {line.partition(":")[0] for line in front}
    for required in ("tools", "model"):
        if required not in seen:
            # A missing `tools` means all tools in both products; a missing `model` loses the choice.
            raise ValueError(f"the Claude agent has no {required!r} line; a copy would not mirror it")
    for line in front:
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"frontmatter line is not 'key: value': {line!r}")
        value = value.strip()
        if key in _PASS_THROUGH:
            out.append(line)
        elif key == "model":
            if value not in MODEL_MAP:
                raise ValueError(f"no Copilot model ID for model {value!r}")
            out.append(f"model: {MODEL_MAP[value]}")
        elif key == "tools":
            out.append("tools: " + json.dumps(map_tools(json.loads(value))))
        elif key == "color":
            continue
        else:
            raise ValueError(f"unmapped frontmatter key {key!r}: decide what Copilot gets")
    return "\n".join(["---", *out, "---", body])


def expected_copies(claude_dir: Path = CLAUDE_DIR) -> dict[str, str]:
    """Copilot file name -> text, for every Claude agent in `claude_dir`."""
    return {
        f"{path.stem}.agent.md": render(path.read_text(encoding="utf-8"))
        for path in sorted(claude_dir.glob("*.md"))
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--write", action="store_true", help="regenerate the Copilot copies")
    args = parser.parse_args(argv)
    expected = expected_copies(CLAUDE_DIR)
    stale = []
    for name, text in expected.items():
        target = COPILOT_DIR / name
        current = target.read_text(encoding="utf-8") if target.is_file() else None
        if current == text:
            continue
        stale.append(name)
        if args.write:
            COPILOT_DIR.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
    # A file whose Claude agent was renamed or removed would stay and fail the consistency test.
    orphans = (
        sorted(p.name for p in COPILOT_DIR.iterdir() if p.is_file() and p.name not in expected)
        if COPILOT_DIR.is_dir() else []
    )
    if args.write:
        for name in orphans:
            (COPILOT_DIR / name).unlink()
    elif stale or orphans:
        if stale:
            print("out of step with agents/: " + ", ".join(stale), file=sys.stderr)
        if orphans:
            print("no Claude agent for: " + ", ".join(orphans), file=sys.stderr)
        print("run with --write to regenerate" + (" and delete" if orphans else ""), file=sys.stderr)
        return 1
    removed = ("; deleted " + ", ".join(orphans)) if orphans else ""
    print(("wrote " if args.write else "in step: ") + (", ".join(stale) or "all copies") + removed)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
